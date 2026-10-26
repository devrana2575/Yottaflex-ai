"""Command-line interface for YottaFlex."""

import json
from datetime import datetime
from pathlib import Path

import click
import pandas as pd
from rich.console import Console
from rich.table import Table

from . import __version__, __generator_version__, __schema_version__
from .config import Config, DataScaleConfig
from .id_generator import IDGenerator
from .generator import DataGenerator
from .simulation import ProcessSimulator
from .scenarios import ScenarioInjector
from .detection import DetectionEngine
from .evaluation import Evaluator
from .validation import Validator
from .persistence import Database

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli():
    """YottaFlex Industrial Pump, Tank, Valve and Flow Anomaly Detection Simulator"""
    pass


@cli.command()
@click.option('--mode', type=click.Choice(['starter', 'full']), default='full', help='Data generation mode')
@click.option('--seed', type=int, default=20261022, help='Random seed')
@click.option('--output-dir', default='data/processed', help='Output directory')
def generate(mode, seed, output_dir):
    """Generate master data."""
    console.print(f"[bold green]Generating {mode} data with seed {seed}[/bold green]")
    
    config = Config()
    config.simulation.random_seed = seed
    if mode == 'starter':
        config.scale = DataScaleConfig.starter()
    else:
        config.scale = DataScaleConfig.full()
    config.output_dir = output_dir
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    id_gen = IDGenerator(seed=seed)
    gen = DataGenerator(config, id_gen)
    
    master_data = gen.generate_all()
    
    # Validate topology
    is_valid, issues = gen.validate_topology()
    console.print(f"Topology valid: {is_valid}, issues: {len(issues)}")
    if not is_valid:
        raise click.ClickException(f"Generated topology is invalid: {issues}")
    
    # Save to CSV
    for name, df in master_data.items():
        path = Path(output_dir) / f"{name}.csv"
        df.to_csv(path, index=False)
        console.print(f"Saved {name}.csv ({len(df)} rows)")
    
    # Save config
    config.save(Path(output_dir) / "config.json")
    
    console.print("[bold green]Master data generation complete![/bold green]")


@cli.command()
@click.option('--mode', type=click.Choice(['starter', 'full']), default='full')
@click.option('--seed', type=int, default=20261022)
@click.option('--duration', type=int, default=24, help='Duration in hours')
@click.option('--output-dir', default='data/processed')
def simulate(mode, seed, duration, output_dir):
    """Run simulation."""
    console.print(f"[bold green]Running simulation ({duration}h) with seed {seed}[/bold green]")
    
    config = Config()
    config.simulation.random_seed = seed
    config.simulation.duration_hours = duration
    if mode == 'starter':
        config.scale = DataScaleConfig.starter()
    else:
        config.scale = DataScaleConfig.full()
    config.output_dir = output_dir
    
    id_gen = IDGenerator(seed=seed)
    
    # Load master data
    master_data = {}
    for name in ['facilities', 'pumps', 'tanks', 'valves', 'pipes', 'sensors', 'operating_modes']:
        path = Path(output_dir) / f"{name}.csv"
        if path.exists():
            master_data[name] = pd.read_csv(path)
        else:
            raise click.ClickException(f"Missing {name}.csv; run generate first")
    
    # Create simulation run
    sim_run_id = id_gen.simulation_run_id()
    
    simulator = ProcessSimulator(config, master_data, id_gen)
    telemetry_df, sim_meta = simulator.simulate_baseline(sim_run_id, duration)
    console.print(f"Generated {len(telemetry_df)} telemetry records")
    
    # Inject scenarios
    injector = ScenarioInjector(config, master_data, id_gen)
    telemetry_df, scenarios_df, ground_truth_df = injector.generate_scenarios(sim_run_id, telemetry_df)
    console.print(f"Injected scenarios: {len(scenarios_df)}")
    
    # Save
    telemetry_df = telemetry_df.drop(
        columns=["scenario_id", "physical_state_value"], errors="ignore"
    )
    telemetry_df.to_csv(Path(output_dir) / "telemetry.csv", index=False)
    if not scenarios_df.empty:
        scenarios_df.to_csv(Path(output_dir) / "scenario_definitions.csv", index=False)
    if not ground_truth_df.empty:
        ground_truth_df.to_csv(Path(output_dir) / "ground_truth.csv", index=False)
    
    # Save simulation run
    sim_run = {
        'simulation_run_id': sim_run_id,
        'configuration_hash': config.get_config_hash(),
        'random_seed': seed,
        'generator_version': __generator_version__,
        'schema_version': __schema_version__,
        'start_time': config.simulation.start_time,
        'end_time': (datetime.fromisoformat(config.simulation.start_time) + 
                     __import__('datetime').timedelta(hours=duration)).isoformat(),
        'status': 'COMPLETED',
        'input_manifest': json.dumps({'master_data_files': list(master_data.keys())}),
        'assumptions': json.dumps({'physics_model': 'simplified', 'tolerance': config.simulation.mass_balance_tolerance}),
        'outcome_summary': json.dumps(sim_meta),
        'created_at': datetime.now().isoformat()
    }
    pd.DataFrame([sim_run]).to_csv(Path(output_dir) / "simulation_runs.csv", index=False)
    
    console.print("[bold green]Simulation complete![/bold green]")


@cli.command()
@click.option('--output-dir', default='data/processed')
def detect(output_dir):
    """Run anomaly detection."""
    console.print("[bold green]Running anomaly detection[/bold green]")
    
    config = Config()
    id_gen = IDGenerator(seed=config.simulation.random_seed)
    
    # Load data
    master_data = {}
    for name in ['facilities', 'pumps', 'tanks', 'valves', 'pipes', 'sensors', 'operating_modes']:
        path = Path(output_dir) / f"{name}.csv"
        if path.exists():
            master_data[name] = pd.read_csv(path)
    
    telemetry_path = Path(output_dir) / "telemetry.csv"
    if not telemetry_path.exists():
        console.print("[red]Missing telemetry.csv, run simulate first[/red]")
        return
    telemetry_df = pd.read_csv(telemetry_path)

    simulation_runs_path = Path(output_dir) / "simulation_runs.csv"
    if not simulation_runs_path.exists():
        raise click.ClickException("Missing simulation_runs.csv; run simulate first")
    sim_runs = pd.read_csv(simulation_runs_path)
    sim_run_id = sim_runs.iloc[0]['simulation_run_id']
    
    detector = DetectionEngine(config, master_data, id_gen)
    alarms_df = detector.detect(sim_run_id, telemetry_df)
    
    console.print(f"Generated {len(alarms_df)} alarms")
    
    if not alarms_df.empty:
        alarms_df.to_csv(Path(output_dir) / "alarms.csv", index=False)
    else:
        alarms_df.to_csv(Path(output_dir) / "alarms.csv", index=False)
    
    console.print("[bold green]Detection complete![/bold green]")


@cli.command()
@click.option('--output-dir', default='data/processed')
def evaluate(output_dir):
    """Evaluate detection performance."""
    console.print("[bold green]Evaluating detection performance[/bold green]")
    
    # Load data
    alarms_path = Path(output_dir) / "alarms.csv"
    gt_path = Path(output_dir) / "ground_truth.csv"
    scenarios_path = Path(output_dir) / "scenario_definitions.csv"
    
    alarms_df = (
        pd.read_csv(alarms_path)
        if alarms_path.exists() and alarms_path.stat().st_size
        else pd.DataFrame()
    )
    ground_truth_df = pd.read_csv(gt_path) if gt_path.exists() else pd.DataFrame()
    scenarios_df = pd.read_csv(scenarios_path) if scenarios_path.exists() else pd.DataFrame()
    
    evaluator = Evaluator()
    metrics = evaluator.evaluate(alarms_df, ground_truth_df, scenarios_df)
    
    console.print(json.dumps(metrics, indent=2))
    
    # Save
    with open(Path(output_dir) / "evaluation_metrics.json", 'w') as f:
        json.dump(metrics, f, indent=2)
    
    console.print("[bold green]Evaluation complete![/bold green]")


@cli.command()
@click.option('--output-dir', default='data/processed')
def validate(output_dir):
    """Validate dataset."""
    console.print("[bold green]Validating dataset[/bold green]")
    
    master_data = {}
    for name in ['facilities', 'pumps', 'tanks', 'valves', 'pipes', 'sensors', 'operating_modes']:
        path = Path(output_dir) / f"{name}.csv"
        if path.exists():
            master_data[name] = pd.read_csv(path)
    simulation_runs_path = Path(output_dir) / "simulation_runs.csv"
    simulation_runs = (
        pd.read_csv(simulation_runs_path)
        if simulation_runs_path.exists()
        else pd.DataFrame()
    )
    
    validator = Validator()
    master_results = validator.validate_master_data(master_data)
    neg_results = validator.test_negative_scenarios(master_data)
    lineage_results = validator.validate_simulation_runs(simulation_runs)
    
    all_results = master_results + lineage_results + neg_results
    validator.results = all_results
    report = validator.generate_report(Path(output_dir) / "validation_summary.json")
    
    # Print summary
    table = Table(title="Validation Summary")
    table.add_column("Status", style="cyan")
    table.add_column("Count", style="magenta")
    table.add_row("PASS", str(report['validation_summary']['passed']))
    table.add_row("FAIL", str(report['validation_summary']['failed']))
    table.add_row("WARN", str(report['validation_summary']['warnings']))
    table.add_row("NOT_IMPLEMENTED", str(report['validation_summary']['not_implemented']))
    console.print(table)
    
    console.print("[bold green]Validation complete![/bold green]")


@cli.command()
@click.option('--mode', type=click.Choice(['starter', 'full']), default='full')
@click.option('--seed', type=int, default=20261022)
@click.option('--output-dir', default='data/processed')
def pipeline(mode, seed, output_dir):
    """Run full pipeline."""
    console.print(f"[bold cyan]Running full pipeline for {mode} mode[/bold cyan]")
    
    ctx = click.get_current_context()
    ctx.invoke(generate, mode=mode, seed=seed, output_dir=output_dir)
    ctx.invoke(simulate, mode=mode, seed=seed, duration=24, output_dir=output_dir)
    ctx.invoke(detect, output_dir=output_dir)
    ctx.invoke(evaluate, output_dir=output_dir)
    ctx.invoke(validate, output_dir=output_dir)
    
    console.print("[bold green]Full pipeline complete![/bold green]")


@cli.command()
@click.option('--output-dir', default='data/processed')
def export_sql(output_dir):
    """Export to SQLite database."""
    console.print("[bold green]Exporting to SQLite[/bold green]")
    
    from .persistence import Database
    from .schema import SCHEMA_SQL
    
    db_path = Path(output_dir) / "yottaflex.db"
    db = Database(str(db_path))
    db.create_schema()
    
    # Load and insert all CSVs
    for table in ['facilities', 'pumps', 'tanks', 'valves', 'pipes', 'sensors', 
                  'operating_modes', 'simulation_runs', 'scenario_definitions', 
                  'telemetry', 'alarms', 'ground_truth']:
        path = Path(output_dir) / f"{table}.csv"
        if path.exists():
            df = pd.read_csv(path)
            db.insert_dataframe(df, table)
            console.print(f"Inserted {len(df)} rows into {table}")
    
    console.print(f"[bold green]Database saved to {db_path}[/bold green]")


if __name__ == '__main__':
    cli()

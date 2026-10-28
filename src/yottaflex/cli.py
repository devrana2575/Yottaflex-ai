"""Command-line interface for YottaFlex 2.0.0."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import click
import pandas as pd
from rich.console import Console
from rich.table import Table

from . import __generator_version__, __schema_version__, __version__
from .config import Config, DataScaleConfig, load_config_for_dir
from .detection import DetectionEngine
from .evaluation import Evaluator
from .exports import EXPORT_TABLES, MASTER_TABLES, export_json_tables, export_sql_seed
from .generator import DataGenerator
from .id_generator import IDGenerator
from .persistence import Database
from .scenarios import ScenarioInjector
from .simulation import ProcessSimulator, required_steps_for_target
from .state_history import generate_equipment_state_events
from .validation import Validator

console = Console()

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sensor_count_for_scale(scale: DataScaleConfig) -> int:
    """Sensor composition is 2/pump + 4/tank + 1/valve."""
    return scale.pumps * 2 + scale.tanks * 4 + scale.valves


def _target_duration_hours(target_rows: int, sensor_count: int, interval: int) -> float:
    steps = required_steps_for_target(target_rows, sensor_count)
    return steps * int(interval) / 3600.0


def _config_for_new_run(
    mode: str,
    seed: int,
    scenario_set: str,
    duration: float,
    sampling_interval: int,
    output_dir: str,
    target_rows: int | None = None,
) -> Config:
    config = Config()
    config.scale = DataScaleConfig.starter() if mode == "starter" else DataScaleConfig.full()
    config.simulation.random_seed = seed
    config.simulation.sampling_interval_seconds = int(sampling_interval)
    # The simulation integrator and the telemetry cadence are kept identical
    # unless a caller explicitly builds a different config.
    config.simulation.time_step_seconds = int(sampling_interval)
    if target_rows is not None:
        if int(target_rows) <= 0:
            raise click.ClickException("--target-telemetry-rows must be positive")
        sensor_count = _sensor_count_for_scale(config.scale)
        config.simulation.telemetry_target_rows = int(target_rows)
        config.simulation.duration_hours = _target_duration_hours(
            int(target_rows), sensor_count, int(sampling_interval)
        )
    else:
        config.simulation.duration_hours = float(duration)
    config.scenarios.scenario_set = scenario_set
    config.output_dir = output_dir
    config.raw_dir = str(Path(output_dir) / "raw")
    config.reports_dir = str(Path(output_dir) / "reports")
    config.database_path = str(Path(output_dir) / "yottaflex.db")
    return config


def _load_config(output_dir: str) -> Config:
    path = Path(output_dir) / "config.json"
    if not path.exists():
        raise click.ClickException(
            f"Missing {path}; run `yottaflex generate` for this output directory first"
        )
    return load_config_for_dir(output_dir)


def _load_master(output_dir: str) -> Dict[str, pd.DataFrame]:
    master: Dict[str, pd.DataFrame] = {}
    for name in MASTER_TABLES:
        path = Path(output_dir) / f"{name}.csv"
        if not path.exists():
            raise click.ClickException(f"Missing {path}; run `yottaflex generate` first")
        master[name] = pd.read_csv(path)
    return master


def _write_manifest(output_dir: str) -> Path:
    root = Path(output_dir)
    entries = {}
    for path in sorted(root.glob("*.csv")):
        if path.name == "validation_results.csv":
            continue
        entries[path.name] = {
            "sha256": _sha256_file(path),
            "rows": int(sum(1 for _ in path.open("rb")) - 1),
        }
    config_path = root / "config.json"
    if config_path.exists():
        entries[config_path.name] = {"sha256": _sha256_file(config_path)}
    manifest = {
        "schema_version": __schema_version__,
        "generator_version": __generator_version__,
        "package_version": __version__,
        "files": entries,
    }
    path = root / "run_manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def _generate_run(
    mode: str,
    seed: int,
    scenario_set: str,
    duration: float | None,
    sampling_interval: int,
    output_dir: str,
    target_rows: int | None = None,
) -> Config:
    if target_rows is not None:
        sensor_count = _sensor_count_for_scale(
            DataScaleConfig.starter() if mode == "starter" else DataScaleConfig.full()
        )
        derived = _target_duration_hours(
            int(target_rows), sensor_count, int(sampling_interval)
        )
        if duration is not None and abs(float(duration) - derived) > 1e-9:
            raise click.ClickException(
                "--duration cannot override a target-row configuration; "
                f"the derived duration is {derived:.6f} h"
            )
    elif duration is None:
        duration = 24.0
    config = _config_for_new_run(
        mode, seed, scenario_set, duration, sampling_interval, output_dir, target_rows
    )
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    id_gen = IDGenerator(seed=seed)
    generator = DataGenerator(config, id_gen)
    master_data = generator.generate_all()
    valid, issues = generator.validate_topology()
    if not valid:
        raise click.ClickException(f"Generated topology is invalid: {issues}")
    for name, frame in master_data.items():
        frame.to_csv(Path(output_dir) / f"{name}.csv", index=False)
    config.save(str(Path(output_dir) / "config.json"))
    console.print(
        f"Master data: {len(master_data['facilities'])} facilities, "
        f"{len(master_data['pumps'])} pumps, {len(master_data['tanks'])} tanks, "
        f"{len(master_data['valves'])} valves, {len(master_data['sensors'])} sensors"
    )
    return config


def _simulate_run(
    output_dir: str,
    duration: float | None = None,
    seed: int | None = None,
    scenario_set: str | None = None,
) -> Config:
    config = _load_config(output_dir)
    if seed is not None:
        config.simulation.random_seed = int(seed)
    if config.simulation.telemetry_target_rows is not None:
        sensor_count = len(_load_master(output_dir)["sensors"])
        target_duration = _target_duration_hours(
            int(config.simulation.telemetry_target_rows),
            sensor_count,
            int(config.simulation.sampling_interval_seconds),
        )
        if duration is not None and abs(float(duration) - target_duration) > 1e-9:
            raise click.ClickException(
                "--duration cannot override a target-row configuration; "
                f"the required duration is {target_duration:.6f} h"
            )
        config.simulation.duration_hours = target_duration
    elif duration is not None:
        config.simulation.duration_hours = float(duration)
    if scenario_set is not None:
        config.scenarios.scenario_set = scenario_set
    config.save(str(Path(output_dir) / "config.json"))
    master_data = _load_master(output_dir)

    sensor_intervals = set(
        int(value) for value in master_data["sensors"]["sampling_interval_seconds"].unique()
    )
    if sensor_intervals != {int(config.simulation.sampling_interval_seconds)}:
        raise click.ClickException(
            "Configured sampling interval does not match the generated sensor "
            f"metadata ({sorted(sensor_intervals)}); rerun generate to change it"
        )

    id_gen = IDGenerator(seed=config.simulation.random_seed)
    simulation_run_id = id_gen.simulation_run_id()
    simulator = ProcessSimulator(config, master_data, id_gen)
    telemetry_df, sim_meta = simulator.simulate_baseline(
        simulation_run_id, config.simulation.duration_hours
    )
    injector = ScenarioInjector(config, master_data, id_gen)
    telemetry_df, scenarios_df, ground_truth_df = injector.generate_scenarios(
        simulation_run_id, telemetry_df
    )
    if telemetry_df.empty:
        raise click.ClickException("Simulation produced no telemetry")
    expected_target = config.simulation.telemetry_target_rows
    if expected_target is not None and len(telemetry_df) != int(expected_target):
        raise click.ClickException(
            "The selected scenario set removed telemetry rows and no longer "
            f"matches --target-telemetry-rows={expected_target} "
            f"(actual={len(telemetry_df)}). Use the `baseline` scenario set for "
            "an exact-budget run."
        )

    telemetry_df = telemetry_df.sort_values(["timestamp", "sensor_id"]).reset_index(drop=True)
    telemetry_df.to_csv(Path(output_dir) / "telemetry.csv", index=False)
    scenarios_df.to_csv(Path(output_dir) / "scenario_definitions.csv", index=False)
    ground_truth_df.to_csv(Path(output_dir) / "ground_truth.csv", index=False)
    state_events_df = generate_equipment_state_events(
        config, master_data, scenarios_df, simulation_run_id
    )
    state_events_df.to_csv(Path(output_dir) / "equipment_state_events.csv", index=False)

    start = datetime.fromisoformat(config.simulation.start_time)
    end = start + timedelta(hours=config.simulation.duration_hours)
    master_hashes = {
        f"{name}.csv": _sha256_file(Path(output_dir) / f"{name}.csv")
        for name in MASTER_TABLES
    }
    scenario_counts = (
        scenarios_df["issue_type"].value_counts().sort_index().to_dict()
        if not scenarios_df.empty
        else {}
    )
    sim_run = {
        "simulation_run_id": simulation_run_id,
        "configuration_hash": config.get_config_hash(),
        "random_seed": int(config.simulation.random_seed),
        "generator_version": __generator_version__,
        "schema_version": __schema_version__,
        "scenario_set": config.scenarios.scenario_set,
        "sampling_interval_seconds": int(config.simulation.sampling_interval_seconds),
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "status": "COMPLETED",
        "input_manifest": json.dumps(
            {"master_data_sha256": master_hashes}, sort_keys=True
        ),
        "assumptions": json.dumps(
            {
                "physics_model": "mass-consistent simplified water model",
                "head_to_pressure_bar": sim_meta["head_to_pressure_bar"],
                "scenario_set": config.scenarios.scenario_set,
            },
            sort_keys=True,
        ),
        "outcome_summary": json.dumps(
            {
                "telemetry_rows": int(len(telemetry_df)),
                "scenario_windows": int(len(scenarios_df)),
                "scenario_counts": scenario_counts,
                "sensor_count": int(sim_meta["sensor_count"]),
                "steps": int(sim_meta["steps"]),
                "state_event_rows": int(len(state_events_df)),
                "telemetry_target_rows": (
                    int(config.simulation.telemetry_target_rows)
                    if config.simulation.telemetry_target_rows is not None
                    else None
                ),
            },
            sort_keys=True,
        ),
        # Deterministic so a repeated run produces identical core outputs.
        "created_at": start.isoformat(),
    }
    pd.DataFrame([sim_run]).to_csv(Path(output_dir) / "simulation_runs.csv", index=False)
    (Path(output_dir) / "simulation_metadata.json").write_text(
        json.dumps(sim_meta, indent=2), encoding="utf-8"
    )
    if config.simulation.telemetry_target_rows is not None:
        allocation = sim_meta.get("sample_count_distribution", {})
        console.print(
            f"Telemetry: {len(telemetry_df):,} rows ({sim_meta['sensor_count']} sensors, "
            f"exact target {config.simulation.telemetry_target_rows:,}; sample "
            f"distribution={allocation}); scenarios: {len(scenarios_df)} windows "
            f"({scenario_counts}); state events: {len(state_events_df)}"
        )
    else:
        console.print(
            f"Telemetry: {len(telemetry_df):,} rows ({sim_meta['sensor_count']} sensors x "
            f"{sim_meta['steps']} samples); scenarios: {len(scenarios_df)} windows "
            f"({scenario_counts}); state events: {len(state_events_df)}"
        )
    return config


def _detect_run(output_dir: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = _load_config(output_dir)
    master_data = _load_master(output_dir)
    telemetry_path = Path(output_dir) / "telemetry.csv"
    runs_path = Path(output_dir) / "simulation_runs.csv"
    if not telemetry_path.exists():
        raise click.ClickException(f"Missing {telemetry_path}; run simulate first")
    if not runs_path.exists():
        raise click.ClickException(f"Missing {runs_path}; run simulate first")
    telemetry_df = pd.read_csv(telemetry_path)
    runs = pd.read_csv(runs_path)
    simulation_run_id = str(runs.iloc[-1]["simulation_run_id"])

    id_gen = IDGenerator(seed=config.simulation.random_seed)
    detector = DetectionEngine(config, master_data, id_gen)
    alarms = detector.detect(simulation_run_id, telemetry_df)
    alarms.to_csv(Path(output_dir) / "alarms.csv", index=False)
    detector.alarm_events.to_csv(Path(output_dir) / "alarm_events.csv", index=False)
    by_category = (
        alarms["alarm_category"].value_counts().to_dict() if not alarms.empty else {}
    )
    console.print(
        f"Alarms: {len(alarms)} episodes ({by_category}); "
        f"history events: {len(detector.alarm_events)}"
    )
    return alarms, detector.alarm_events


def _flatten_metrics(result: Dict[str, Any], simulation_run_id: str) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    event = result.get("event_level", {})
    point = result.get("point_level", {})
    metric_names = [
        "true_positives",
        "false_negatives",
        "false_positives",
        "true_negatives",
        "precision",
        "recall",
        "f1_score",
        "false_positive_rate",
        "matched_event_count",
        "missed_event_count",
        "false_alarm_incident_count",
        "unknown_incident_count",
    ]
    for name in metric_names:
        if name in event:
            rows.append(
                {
                    "evaluation_level": "EVENT",
                    "scope": "overall",
                    "metric_name": name,
                    "metric_value": event.get(name),
                    "details": None,
                }
            )
    latency = event.get("detection_latency_seconds", {})
    for name in ("mean", "median", "min", "max"):
        rows.append(
            {
                "evaluation_level": "EVENT",
                "scope": "detection_latency_seconds",
                "metric_name": name,
                "metric_value": latency.get(name),
                "details": None,
            }
        )
    confusion = point.get("confusion_matrix", {}) if point.get("status") == "EVALUATED" else {}
    for name in (
        "true_positives",
        "false_positives",
        "true_negatives",
        "false_negatives",
        "precision",
        "recall",
        "f1_score",
        "false_positive_rate",
    ):
        if name in confusion:
            rows.append(
                {
                    "evaluation_level": "POINT",
                    "scope": "overall",
                    "metric_name": name,
                    "metric_value": confusion.get(name),
                    "details": "explicit labelled samples only; unknown excluded",
                }
            )
    for scope_name in ("by_scenario_type", "by_category", "by_severity"):
        for scope_value, values in result.get(scope_name, {}).items():
            for name in ("injected", "detected", "missed", "recall", "mean_detection_latency_seconds"):
                rows.append(
                    {
                        "evaluation_level": "EVENT",
                        "scope": f"{scope_name}:{scope_value}",
                        "metric_name": name,
                        "metric_value": values.get(name),
                        "details": None,
                    }
                )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame.insert(0, "simulation_run_id", simulation_run_id)
    frame.insert(0, "metric_id", [f"MET-{i + 1:06d}" for i in range(len(frame))])
    frame["evaluated_at"] = datetime.now().astimezone().isoformat()
    return frame


def _evaluate_run(output_dir: str) -> Dict[str, Any]:
    config = _load_config(output_dir)
    runs_path = Path(output_dir) / "simulation_runs.csv"
    if not runs_path.exists():
        raise click.ClickException(f"Missing {runs_path}; run simulate first")
    runs = pd.read_csv(runs_path)
    simulation_run_id = str(runs.iloc[-1]["simulation_run_id"])

    def read_optional(name: str) -> pd.DataFrame:
        path = Path(output_dir) / name
        if not path.exists() or path.stat().st_size == 0:
            return pd.DataFrame()
        return pd.read_csv(path)

    alarms = read_optional("alarms.csv")
    ground_truth = read_optional("ground_truth.csv")
    scenarios = read_optional("scenario_definitions.csv")
    telemetry_path = Path(output_dir) / "telemetry.csv"
    telemetry = pd.read_csv(telemetry_path) if telemetry_path.exists() else None

    evaluator = Evaluator(config)
    result = evaluator.evaluate(alarms, ground_truth, scenarios, telemetry)
    with open(Path(output_dir) / "evaluation_metrics.json", "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)

    metrics_frame = _flatten_metrics(result, simulation_run_id)
    metrics_frame.to_csv(Path(output_dir) / "evaluation_metrics.csv", index=False)
    evaluator.incidents_df.to_csv(
        Path(output_dir) / "alarm_incidents.csv", index=False
    )
    events_export = evaluator.events_df.copy()
    if not events_export.empty:
        events_export.insert(
            0,
            "evaluation_event_id",
            [f"EVAL-EVT-{i + 1:06d}" for i in range(len(events_export))],
        )
        events_export.insert(1, "simulation_run_id", simulation_run_id)
        events_export["expected_sensors"] = events_export["expected_sensors"].apply(
            lambda value: json.dumps(list(value)) if isinstance(value, (list, tuple)) else value
        )
    events_export.to_csv(Path(output_dir) / "evaluation_events.csv", index=False)

    events = result.get("event_level", {})
    point = result.get("point_level", {})
    console.print(
        "Event level: TP={tp} FN={fn} FP={fp} precision={p} recall={r} F1={f}".format(
            tp=events.get("true_positives"),
            fn=events.get("false_negatives"),
            fp=events.get("false_positives"),
            p=_fmt(events.get("precision")),
            r=_fmt(events.get("recall")),
            f=_fmt(events.get("f1_score")),
        )
    )
    if point.get("status") == "EVALUATED":
        confusion = point["confusion_matrix"]
        console.print(
            "Point level: TP={tp} FP={fp} TN={tn} FN={fn} precision={p} recall={r}".format(
                tp=confusion["true_positives"],
                fp=confusion["false_positives"],
                tn=confusion["true_negatives"],
                fn=confusion["false_negatives"],
                p=_fmt(confusion["precision"]),
                r=_fmt(confusion["recall"]),
            )
        )
    return result


def _fmt(value: Any) -> str:
    return "None" if value is None else f"{float(value):.4f}"


def _validate_run(output_dir: str) -> Dict[str, Any]:
    config = _load_config(output_dir)
    validator = Validator(config=config)
    validator.validate_dataset(output_dir)
    report = validator.generate_report(Path(output_dir) / "validation_summary.json")
    results_frame = pd.DataFrame(validator.results)
    if not results_frame.empty:
        results_frame.to_csv(Path(output_dir) / "validation_results.csv", index=False)
    summary = report["validation_summary"]
    table = Table(title="Validation Summary")
    table.add_column("Status")
    table.add_column("Count", justify="right")
    table.add_row("PASS", str(summary["passed"]))
    table.add_row("FAIL", str(summary["failed"]))
    table.add_row("WARN", str(summary["warnings"]))
    table.add_row("NOT_IMPLEMENTED", str(summary["not_implemented"]))
    console.print(table)
    if summary["failed"]:
        failed = [r for r in validator.results if r["status"] == "FAIL"]
        for item in failed:
            console.print(f"[red]FAIL[/red] {item['test_case_id']}: {item['description']}")
    return report


def _export_sql_run(output_dir: str, recreate: bool = True) -> Path:
    config = _load_config(output_dir)
    db_path = Path(config.database_path)
    db = Database(str(db_path))
    db.create_schema(reset=recreate)
    for table in EXPORT_TABLES:
        path = Path(output_dir) / f"{table}.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        if frame.empty:
            continue
        db.insert_dataframe(frame, table)
    integrity = db.integrity_check()
    violations = db.foreign_key_violations()
    db.close()
    if integrity != "ok":
        raise click.ClickException(f"SQLite integrity check failed: {integrity}")
    if violations:
        raise click.ClickException(f"SQLite foreign-key violations: {violations[:3]}")
    console.print(f"SQLite: {db_path} (integrity ok, {len(EXPORT_TABLES)} tables exported)")
    return db_path


def _write_html_report(output_dir: str, result: Dict[str, Any]) -> Path:
    """Write a human-readable Markdown evaluation report."""
    event = result.get("event_level", {})
    point = result.get("point_level", {})
    lines = [
        "# YottaFlex Evaluation Report",
        "",
        "Point-level and event-level metrics are separate units and are not combined.",
        "",
        "## Event level",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key in (
        "positive_event_count",
        "matched_event_count",
        "missed_event_count",
        "false_alarm_incident_count",
        "unknown_incident_count",
        "precision",
        "recall",
        "f1_score",
        "false_positive_rate",
    ):
        lines.append(f"| {key} | {_fmt(event.get(key))} |")
    lines += ["", "## Point level", "", "| Metric | Value |", "|---|---|"]
    confusion = point.get("confusion_matrix", {}) if point.get("status") == "EVALUATED" else {}
    for key in (
        "true_positives",
        "false_positives",
        "true_negatives",
        "false_negatives",
        "precision",
        "recall",
        "f1_score",
        "false_positive_rate",
    ):
        lines.append(f"| {key} | {_fmt(confusion.get(key))} |")
    lines += ["", "## By scenario type", "", "| Type | Injected | Detected | Missed | Recall |", "|---|---:|---:|---:|---:|"]
    for name, values in result.get("by_scenario_type", {}).items():
        lines.append(
            f"| {name} | {values['injected']} | {values['detected']} | "
            f"{values['missed']} | {_fmt(values['recall'])} |"
        )
    lines += ["", "## By severity", "", "| Severity | Injected | Detected | Missed | Recall |", "|---|---:|---:|---:|---:|"]
    for name, values in result.get("by_severity", {}).items():
        lines.append(
            f"| {name} | {values['injected']} | {values['detected']} | "
            f"{values['missed']} | {_fmt(values['recall'])} |"
        )
    path = Path(output_dir) / "evaluation_summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@click.group()
@click.version_option(version=__version__)
def cli():
    """YottaFlex industrial pump, tank, valve and flow anomaly simulator."""
    pass


@cli.command()
@click.option("--mode", type=click.Choice(["starter", "full"]), default="full")
@click.option("--seed", type=int, default=20261022)
@click.option(
    "--scenario-set",
    type=click.Choice(["default", "calibration", "evaluation", "compact", "baseline"]),
    default="default",
)
@click.option(
    "--duration",
    type=float,
    default=None,
    help="Simulation duration in hours; defaults to 24 when no target is set",
)
@click.option("--sampling-interval", type=int, default=60, help="Telemetry cadence in seconds")
@click.option(
    "--target-telemetry-rows",
    type=int,
    default=None,
    help="Exact telemetry budget; duration is derived from the allocation",
)
@click.option("--output-dir", default="data/processed")
def generate(
    mode: str,
    seed: int,
    scenario_set: str,
    duration: float | None,
    sampling_interval: int,
    target_telemetry_rows: int | None,
    output_dir: str,
):
    """Generate master data and run configuration."""
    _generate_run(
        mode,
        seed,
        scenario_set,
        duration,
        sampling_interval,
        output_dir,
        target_telemetry_rows,
    )
    console.print(f"Configuration saved to {Path(output_dir) / 'config.json'}")


@cli.command()
@click.option("--output-dir", default="data/processed")
@click.option("--duration", type=float, default=None, help="Override duration in hours")
@click.option("--seed", type=int, default=None, help="Override simulation seed")
@click.option(
    "--scenario-set",
    type=click.Choice(["default", "calibration", "evaluation", "compact", "baseline"]),
    default=None,
)
def simulate(output_dir: str, duration: float | None, seed: int | None, scenario_set: str | None):
    """Run simulation and inject the configured scenario set."""
    _simulate_run(output_dir, duration, seed, scenario_set)
    console.print("Simulation complete")


@cli.command()
@click.option("--output-dir", default="data/processed")
def detect(output_dir: str):
    """Run anomaly detection on observed telemetry only."""
    _detect_run(output_dir)
    console.print("Detection complete")


@cli.command()
@click.option("--output-dir", default="data/processed")
def evaluate(output_dir: str):
    """Evaluate event-level and point-level detection performance."""
    result = _evaluate_run(output_dir)
    _write_html_report(output_dir, result)
    console.print("Evaluation complete")


@cli.command()
@click.option("--output-dir", default="data/processed")
def validate(output_dir: str):
    """Run dataset, physics, lineage, detection and evaluation validation."""
    _validate_run(output_dir)
    console.print("Validation complete")


@cli.command("export-sql")
@click.option("--output-dir", default="data/processed")
@click.option("--recreate/--append", default=True)
def export_sql(output_dir: str, recreate: bool):
    """Export CSV outputs to a normalized SQLite database."""
    _export_sql_run(output_dir, recreate)
    console.print("SQLite export complete")


@cli.command("export-json")
@click.option("--output-dir", default="data/processed")
@click.option("--output", default=None, help="JSON directory (default: <output-dir>/json_exports)")
def export_json(output_dir: str, output: str | None):
    """Export all CSV tables to deterministic JSON arrays."""
    destination = Path(output) if output else Path(output_dir) / "json_exports"
    manifest = export_json_tables(output_dir, destination)
    console.print(
        f"JSON export: {destination} ({len(manifest['tables'])} tables, "
        f"{sum(item['rows'] for item in manifest['tables'].values()):,} rows)"
    )


@cli.command("export-sql-script")
@click.option("--output-dir", default="data/processed")
@click.option(
    "--output",
    default=None,
    help="SQL file (default: <output-dir>/yottaflex_seed.sql)",
)
def export_sql_script(output_dir: str, output: str | None):
    """Write a portable SQL schema + seed-data script."""
    destination = Path(output) if output else Path(output_dir) / "yottaflex_seed.sql"
    manifest = export_sql_seed(output_dir, destination)
    console.print(
        f"SQL seed script: {destination} ({manifest['total_rows']:,} rows, "
        f"sha256={manifest['sha256'][:12]}...)"
    )


@cli.command()
@click.option("--output-dir", default="data/processed")
@click.option("--mode", type=click.Choice(["starter", "full"]), default="full")
@click.option("--seed", type=int, default=20261022)
@click.option(
    "--scenario-set",
    type=click.Choice(["default", "calibration", "evaluation", "compact", "baseline"]),
    default="default",
)
@click.option("--duration", type=float, default=None,
              help="Simulation duration in hours; defaults to 24 when no target is set")
@click.option("--sampling-interval", type=int, default=60)
@click.option(
    "--target-telemetry-rows",
    type=int,
    default=None,
    help="Exact telemetry budget; duration is derived from the allocation",
)
@click.option("--skip-sql", is_flag=True, default=False)
def pipeline(
    output_dir: str,
    mode: str,
    seed: int,
    scenario_set: str,
    duration: float | None,
    sampling_interval: int,
    target_telemetry_rows: int | None,
    skip_sql: bool,
):
    """Run generate, simulate, detect, evaluate, validate, export and SQL checks."""
    console.print(f"[bold cyan]YottaFlex pipeline: {mode} / {scenario_set}[/bold cyan]")
    _generate_run(
        mode,
        seed,
        scenario_set,
        duration,
        sampling_interval,
        output_dir,
        target_telemetry_rows,
    )
    _simulate_run(output_dir)
    _detect_run(output_dir)
    result = _evaluate_run(output_dir)
    _write_html_report(output_dir, result)
    # Export first so validation can check the live SQLite database.
    if not skip_sql:
        _export_sql_run(output_dir, recreate=True)
    _validate_run(output_dir)
    if not skip_sql:
        # Re-export to include validation_results.csv.
        _export_sql_run(output_dir, recreate=True)
        _run_sql_queries(output_dir, "sql/analysis_queries.sql")
    _write_manifest(output_dir)
    console.print(f"[bold green]Pipeline complete: {output_dir}[/bold green]")


def _run_sql_queries(output_dir: str, sql_file: str, output: str | None = None) -> Dict[str, Any]:
    config = _load_config(output_dir)
    db_path = Path(config.database_path)
    if not db_path.exists():
        raise click.ClickException(f"Missing {db_path}; run export-sql first")
    sql_path = Path(sql_file)
    if not sql_path.exists():
        raise click.ClickException(f"Missing SQL file {sql_path}")
    script = sql_path.read_text(encoding="utf-8")
    statements = [item.strip() for item in re.split(r";\s*", script) if item.strip()]
    db = Database(str(db_path))
    report = []
    for index, statement in enumerate(statements, start=1):
        label = next(
            (
                line.strip("- ").strip()
                for line in statement.splitlines()
                if line.strip().startswith("--")
            ),
            f"query_{index}",
        )
        expectation_match = re.search(r"expect=([a-z_]+)", statement)
        expectation = expectation_match.group(1) if expectation_match else "nonempty"
        try:
            rows = db.execute_query(statement)
            payload = [dict(row) for row in rows]
            status = "PASS"
            reason = None
            if expectation == "nonempty" and not payload:
                status = "FAIL"
                reason = "expected at least one row, got zero"
            elif expectation == "zero_rows" and payload:
                status = "FAIL"
                reason = f"expected zero rows, got {len(payload)}"
            report.append(
                {
                    "query_number": index,
                    "label": label,
                    "expectation": expectation,
                    "sql": statement,
                    "row_count": len(payload),
                    "rows": payload,
                    "status": status,
                    "reason": reason,
                }
            )
        except Exception as exc:  # pragma: no cover - reported to the user
            report.append(
                {
                    "query_number": index,
                    "label": label,
                    "expectation": expectation,
                    "sql": statement,
                    "row_count": 0,
                    "rows": [],
                    "status": "FAIL",
                    "error": str(exc),
                }
            )
    db.close()
    failed = sum(item["status"] == "FAIL" for item in report)
    output_path = Path(output) if output else Path(output_dir) / "sql_query_report.json"
    output_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    console.print(
        f"SQL: {len(report)} statements, {len(report) - failed} passed, {failed} failed; "
        f"report: {output_path}"
    )
    if failed:
        raise click.ClickException(f"{failed} SQL statement(s) failed")
    return {"queries": len(report), "failed": failed, "report": str(output_path)}


@cli.command("run-sql")
@click.option("--output-dir", default="data/processed")
@click.option("--sql-file", default="sql/analysis_queries.sql")
@click.option("--output", default=None, help="JSON report path")
def run_sql(output_dir: str, sql_file: str, output: str | None):
    """Execute every SQL statement in a file and validate it returns rows."""
    _run_sql_queries(output_dir, sql_file, output)


if __name__ == "__main__":
    cli()

# YottaFlex Industrial Pump, Tank, Valve and Flow Anomaly Detection Simulator

A reproducible, physics-inspired industrial process simulator that generates equipment master data and time-series telemetry, models industrial topology, injects controlled operational anomalies, detects abnormal conditions, records alarms and simulation outcomes, and evaluates detection performance against independent ground truth.

## Project Summary

This is a synthetic simulation and analytics project for industrial process monitoring. It demonstrates end-to-end capabilities including master data generation, topology modeling, physics-inspired simulation, controlled anomaly injection, rule-based detection, ground-truth evaluation, and comprehensive validation.

**Note:** This is a synthetic simulation and analytics project, not a safety-certified industrial control system or a validated digital twin.

## Business Problem

Industrial facilities need robust anomaly detection systems to identify leaks, blockages, pump degradation, and sensor faults before they cause significant issues. This simulator provides a controlled environment to test and evaluate detection algorithms with known ground truth.

## Architecture

```
yottaflex/
├── src/yottaflex/          # Core modules
│   ├── config.py           # Configuration management
│   ├── id_generator.py     # Deterministic ID generation
│   ├── generator.py        # Master data generation
│   ├── simulation.py       # Physics-inspired simulation
│   ├── scenarios.py        # Anomaly injection
│   ├── detection.py        # Rule-based detection
│   ├── evaluation.py       # Performance evaluation
│   ├── validation.py       # Validation framework
│   ├── persistence.py      # SQLite persistence
│   ├── schema.py           # Database schema
│   └── cli.py              # Command-line interface
├── tests/                  # Test suite
├── data/                   # Generated data
├── sql/                    # SQL queries
├── docs/                   # Documentation
└── ai_usage/               # AI prompt history
```

## Technology Stack

- **Python 3.11+** - Core language
- **Pandas** - Data manipulation
- **NumPy** - Numerical computing
- **NetworkX** - Graph topology analysis
- **SQLite** - Local relational database
- **pytest** - Testing framework
- **Click** - CLI framework
- **Rich** - Terminal formatting
- **SQLite / Python standard library** - Local query execution and event-level metrics

## Setup Instructions

### Prerequisites
- Python 3.11 or compatible version
- Windows/Linux/macOS

### Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Install the package in development mode:
```bash
pip install -e .
```

## Example Commands

### Clean starter workflow

Use a new output directory for a clean run:
```bash
yottaflex pipeline --mode starter --seed 20261022 --output-dir data/processed/starter-run
```

### Full-volume workflow

The full configuration creates 3 facilities, 20 pumps, 30 tanks, and 60 valves. Each equipment item has two sensors, so a 24-hour, 60-second simulation writes 316,800 telemetry rows (220 sensors × 1,440 samples).
```bash
yottaflex pipeline --mode full --seed 20261022 --output-dir data/processed/full-run
```

The commands can also be run individually, using the same output directory:
```bash
yottaflex generate --mode full --seed 20261022 --output-dir data/processed/full-run
yottaflex simulate --mode full --seed 20261022 --duration 24 --output-dir data/processed/full-run
yottaflex detect --output-dir data/processed/full-run
yottaflex evaluate --output-dir data/processed/full-run
yottaflex validate --output-dir data/processed/full-run
yottaflex export-sql --output-dir data/processed/full-run
```

Run the SQL analytics against the exported database:
```bash
python -c "import pathlib, sqlite3, sys; db=sqlite3.connect(pathlib.Path(sys.argv[1])/'yottaflex.db'); [print(db.execute(q).fetchall()) for q in pathlib.Path('sql/analysis_queries.sql').read_text(encoding='utf-8').split(';') if q.strip()]" data/processed/full-run
```

### Tests
```bash
pytest tests/ -v
```

## Data Model

### Core Entities (10)
1. **Facility** - Industrial facilities
2. **Pump** - Pumps with performance curves
3. **Tank** - Storage tanks
4. **Valve** - Flow control valves
5. **Pipe** - Process piping
6. **Sensor** - Measurement sensors
7. **Telemetry** - Time-series measurements
8. **OperatingMode** - Operating modes
9. **Alarm** - Detected anomalies
10. **SimulationRun** - Simulation metadata

See [data_dictionary.md](docs/data_dictionary.md) for complete field specifications.

## Scenario Descriptions

### Normal Operation
Baseline steady-state operation with typical variations.

### Leak (A)
Controlled loss represented by an accelerated decline in a tank's observed level.

### Blockage (B)
Flow restriction causing reduced flow and increased upstream pressure.

### Pump Degradation (C)
Gradual performance degradation affecting pump head/flow characteristics.

### Sensor Fault (D)
Measurement errors (bias, drift) while process remains normal - tested separately from process faults.

## Detection Methodology

Rule-based detection engine with transparent rules:
- **RULE-001**: Tank level out of bounds [10%, 90%]
- **RULE-002**: Tank level falls by at least 0.75 percentage points over a five-minute window
- **RULE-003**: Sensor stuck at constant value
- **RULE-004**: Bad/uncertain/missing quality status or implausible flow reading
- **RULE-005**: Five-minute mean pump flow below 80% of nominal flow

Detection consumes measured values, sensor metadata, and quality status. It discards internal simulated physical-state values and does not consume scenario or ground-truth IDs. Evaluation links alarms to ground-truth events by equipment, time overlap, and (when present) sensor. The telemetry CSV does not contain scenario labels or physical-state truth.

## Evaluation Methodology

- **Event-level evaluation**: Each injected scenario is evaluated as an event
- **Metrics**: TP, FP, FN, Precision, Recall, F1, Detection Rate. True negatives are reported as unavailable because no normal-event population is defined.
- **Per-scenario breakdown**: Performance by anomaly type
- **Separation**: Sensor faults evaluated separately from process anomalies

## Reproducibility

Generated master data, telemetry values, scenarios, ground truth, and alarms are deterministic for a fixed seed and configuration. Run metadata and reports include wall-clock timestamps and therefore are not byte-for-byte deterministic:
- Fixed default seed: 20261022
- Deterministic ID generation
- Stable row ordering
- Configuration hashing
- Repeated runs produce matching deterministic data rows

## Limitations

- **Simplified physics**: Uses approximate models, not full CFD/hydraulic simulation
- **Rule-based detection**: Simple thresholds, not ML-based anomaly detection
- **Synthetic data only**: No real industrial data
- **Limited scenarios**: Four controlled mechanisms (leak, blockage, pump degradation, sensor fault)
- **No real-time control**: Batch simulation only

## Configuration

Configuration defaults are defined in Python dataclasses and a copy is written to each generated output directory. Key parameters:
- Random seed: 20261022
- Sampling interval: 60 seconds
- Duration: 24 hours
- Mass balance tolerance: 1%
- Stuck sensor threshold: 30 minutes

## License

This is a synthetic project for evaluation purposes.

## AI-Use Disclosure

See [ai_usage/](ai_usage/) directory for complete AI prompt history and implementation decisions.

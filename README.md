# YottaFlex Industrial Pump, Tank, Valve and Flow Anomaly Detection Simulator

YottaFlex is a reproducible, physics-inspired industrial process simulator. It generates
equipment master data and time-series telemetry, injects controlled process and sensor anomalies,
detects abnormal conditions from observed measurements, stores alarm episodes and append-only
history, evaluates detection against isolated ground truth, exports a relational SQLite database,
and executes validation and SQL checks.

The project is a synthetic engineering and analytics exercise. It is **not** a safety-certified
industrial control system and not a validated digital twin.

## Status at a Glance

| Item | Result |
|---|---|
| Version | 2.0.0 |
| Facilities / pumps / tanks / valves | 3 / 20 / 30 / 60 |
| Sensors, full scale | 220 (20x2 pump + 30x4 tank + 60x1 valve) |
| Full default telemetry | 316,800 rows (220 sensors x 1,440 samples) |
| ~100k configuration | 99,000 rows (220 sensors x 450 samples, 7.5 h) |
| Primary independent evaluation | 11 events: TP=10, FN=1, FP=0; event precision=1.0, recall=0.9091, F1=0.9524 |
| Point evaluation (evaluation set) | TP=844, FP=10, TN=112,190, FN=206; precision=0.9883, recall=0.8038 |
| Validation | 87 PASS / 0 FAIL / 0 WARN / 0 NOT_IMPLEMENTED |
| SQL analytics | 20 statements, 20 PASS |
| Tests | 61 passed |
| Reproducibility | 19 deterministic artifacts byte-identical across two clean runs |

The full evidence, including per-event results, false-alarm analysis and the requirement matrix, is
in [`docs/validation_report.md`](docs/validation_report.md).

## What Changed in 2.0

The 1.x implementation reported an event-level true-positive count against a raw alarm-row
false-positive count. The full 1.x run produced 1,245 alarm rows for four events and reported
precision `0.010638`; that number mixed incompatible units and is not used in 2.0. The main changes
are:

- **Separate event-level and point-level evaluation.** Units are never combined.
- **Alarm episodes and incidents.** One row per rule/equipment/sensor, with persistence,
  hysteresis, mode suppression and CREATED/RESOLVED history. Overlapping episodes become one
  incident for event matching.
- **Explicit labels.** Anomaly and NORMAL windows are half-open and disjoint; unknown samples are
  excluded and counted, not treated as negatives.
- **Mass-consistent simulation.** Tank level, inlet/outlet flow and hydrostatic pressure agree;
  pump flow and pressure follow the pump curve. Leaks create a physical balance residual.
- **No ground-truth leak through sensor quality.** Bias, drift, stuck and missing faults are
  observed, not flagged by the injector.
- **Four scenario sets.** `default`, `calibration`, `evaluation` and `compact`; calibration and
  evaluation use different windows, equipment and severities.
- **Executable claims.** 87 validation checks, 20 SQL assertions and a 61-test suite run against
  generated artifacts.

## Architecture

```
yottaflex/
├── src/yottaflex/
│   ├── config.py          # Configuration, scenario sets, thresholds, path-independent hash
│   ├── id_generator.py    # Deterministic IDs
│   ├── generator.py       # Facilities, equipment, pipes, sensors, modes, topology
│   ├── simulation.py      # Pump curves, mass-consistent tanks, modes, sensor noise
│   ├── scenarios.py       # Scenario matrix, injection, NORMAL complements, ground truth
│   ├── detection.py       # Rules, episode tracker, persistence/hysteresis, history
│   ├── evaluation.py      # Incidents, one-to-one matching, event and point metrics
│   ├── validation.py      # 87 executable checks and status report
│   ├── persistence.py     # SQLite export/query/integrity helpers
│   ├── schema.py          # 2.0.0 DDL, constraints, indexes
│   └── cli.py             # generate, simulate, detect, evaluate, validate, export-sql, run-sql, pipeline
├── tests/                 # 61 tests
├── sql/                   # 20 analytical statements with declared expectations
├── docs/                  # Methodology, decisions, baseline and validation evidence
├── reports/final/         # Compact final-run evidence from clean runs
└── ai_usage/              # AI prompt history, decisions and verification notes
```

## Setup

Requirements: Python 3.11 or newer, Windows/Linux/macOS.

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

Verify the installation and CLI:

```bash
yottaflex --version
yottaflex --help
```

## Quick Start

### Default full pipeline (316,800 rows)

```bash
yottaflex pipeline --mode full --seed 20261022 --output-dir data/processed/full-run
```

The pipeline runs generate, simulate, detect, evaluate, validate, SQLite export and SQL checks, and
writes a manifest. It uses the `default` scenario set unless `--scenario-set` is given.

### Independent evaluation set

```bash
yottaflex pipeline --mode full --seed 20261022 --scenario-set evaluation \
  --output-dir data/processed/evaluation-run
```

The evaluation run has 316,740 telemetry rows because the labelled missing-sensor scenario removes
60 rows. The missing rows are intentional and are not a data-quality defect.

### ~100,000-row configuration

```bash
yottaflex pipeline --mode full --seed 20261022 --scenario-set compact --duration 7.5 \
  --output-dir data/processed/compact-run
```

`compact` uses 450 one-minute samples, producing exactly 220 x 450 = 99,000 rows. The required
full-volume configuration remains 316,800 rows.

### Calibration set

```bash
yottaflex pipeline --mode full --seed 20261022 --scenario-set calibration \
  --output-dir data/processed/calibration-run
```

Calibration uses different events and severities from the evaluation set. It checks that each
mechanism is detectable; it is not the reported evaluation set.

### Step-by-step commands

Use the same output directory for each step:

```bash
yottaflex generate  --mode full --seed 20261022 --output-dir data/processed/full-run
yottaflex simulate  --mode full --seed 20261022 --duration 24 --output-dir data/processed/full-run
yottaflex detect    --output-dir data/processed/full-run
yottaflex evaluate  --output-dir data/processed/full-run
yottaflex validate  --output-dir data/processed/full-run
yottaflex export-sql --output-dir data/processed/full-run
yottaflex run-sql   --output-dir data/processed/full-run --sql-file sql/analysis_queries.sql
```

### Tests

```bash
python -m pytest -q
```

The suite includes unit, data-integrity, scenario, detection, evaluation, validation, integration
and reproducibility tests. The existing 11 tests are retained.

## Data Model

Core entities: facility, pump, tank, valve, pipe, sensor, telemetry, operating mode, alarm,
simulation run. Version 2.0 adds tank height, sensor roles, alarm category/occurrence/peak/
attribution, scenario and ground-truth severity/expected sensors, append-only alarm history,
alarm incidents, and evaluation/validation tables.

### Sensor composition

| Equipment | Sensors per item | Roles |
|---|---:|---|
| Pump | 2 | discharge flow, discharge pressure |
| Tank | 4 | level, hydrostatic pressure, inlet flow, outlet flow |
| Valve | 1 | through flow |

Full scale: 3 facilities, 20 pumps, 30 tanks, 60 valves, 135 pipes, 220 sensors. The sensor count is
preserved relative to the original requirement by using one flow sensor per valve and four
physically necessary sensors per tank.

Telemetry is the observed dataset. `physical_state_value` is persisted for physics validation and
is explicitly excluded from detector input. Scenario, ground-truth and expected-label columns never
appear on the telemetry table, and alarms carry no `scenario_id`.

See [`docs/data_dictionary.md`](docs/data_dictionary.md) for field-level definitions.

## Physics Model

### Pump

```
H(Q) = max(0, H_shutoff - k * Q^2)
H_shutoff = 1.20 * H_nominal
k = (H_shutoff - H_nominal) / Q_nominal^2
P = H * 0.0981 bar
```

Normal flow is 92% of nominal with slow sinusoidal and AR(1) variation. Blockage reduces flow and
raises pressure relative to the curve; degradation reduces both flow and head.

### Tank

```
V = capacity_m3 * level_pct / 100
dV/dt = Q_in - Q_out
P = level_pct / 100 * height_m * 0.0981 bar
```

Outflow uses a proportional level controller. Leak injection removes volume and produces a
positive `Q_in - Q_out - dV/dt` residual; a flow-sensor bias changes only the measurement. Normal
windows satisfy the mass balance within tolerance.

STARTUP and SHUTDOWN are explicit 20-minute ramps. Process rules are suppressed in these modes;
sensor-integrity rules are not.

## Scenario Sets

| Set | Duration | Positive events | NORMAL windows | Purpose |
|---|---:|---:|---:|---|
| `default` | 24 h | 4 | 6 | Demonstration |
| `calibration` | 24 h | 7 | 8 | Exercise mechanisms and severities |
| `evaluation` | 24 h | 11 | 8 | Independent reported evaluation |
| `compact` | 7.5 h | 4 | 5 | 99,000-row configuration |

Mechanisms:

- **Leak** - volume loss from a tank, with a physical flow-balance residual and hydrostatic response.
- **Blockage** - pump flow restriction with increased upstream pressure.
- **Pump degradation** - reduced pump flow and head relative to the nominal curve.
- **Sensor fault** - bias, drift, stuck value, or missing telemetry; the physical process stays normal.

The evaluation set covers light, medium and severe process faults plus all four sensor-fault
mechanisms. The light leak is deliberately below the documented sensitivity floor.

## Detection Rules

All thresholds are in `src/yottaflex/config.py` and copied into each run's `config.json`.

| Rule | Alarm | Inputs | Activation | Recovery / persistence | Category |
|---|---|---|---|---|---|
| RULE-001 | Tank level out of bounds | level | `< 10%` or `> 90%` | exits inside `[12%, 88%]`; 120 s + 3 samples | PROCESS_FAULT |
| RULE-002 | Rapid tank level decline | level | fall `>= 0.30` pp over 5 min | recovery at `>= -0.15` pp; 120 s + 3 samples | PROCESS_FAULT |
| RULE-003 | Sensor stuck | any | unchanged (`<= 1e-9`) for `>= 30 min` | clear on change; 1 sample | SENSOR_FAULT |
| RULE-004 | Sensor quality | quality | not `GOOD` (BAD/UNCERTAIN/MISSING) | 1 sample | SENSOR_FAULT |
| RULE-005 | Pump low-flow deviation | pump flow | 5-min mean `< 80%` of nominal | recovery `> 85%`; 240 s + 3 samples | PROCESS_FAULT |
| RULE-006 | Tank flow-balance loss | level, pressure, inlet, outlet | 10-min residual above `max(5 m3/h, 8%)` **and** level decline `>= 0.15 pp` | 480 s + 5 samples; mode-suppressed | PROCESS_FAULT |
| RULE-006U | Flow-balance inconsistency | same | residual above uncertainty, no corroborating decline | 480 s + 5 samples | UNCERTAIN |
| RULE-007 | Pump operating point off curve | pump flow, pressure | relative head error `> 10%` while flow `< 90%` nominal | recovery `< 6%`; 300 s + 3 samples | PROCESS_FAULT |
| RULE-008 | Implausible reading | any | flow outside `[0, 500] m3/h`, pressure outside `[0, 60] bar`, level outside `[0, 100]%` | 1 sample | SENSOR_FAULT |
| RULE-009 | Missing telemetry | timestamps | contiguous gap at the expected cadence | one episode per gap | SENSOR_FAULT |
| RULE-010 | Level/pressure disagreement | level, pressure | observed level differs from hydrostatic estimate by `> 4 pp` | 180 s + 3 samples | SENSOR_FAULT |

Rules RULE-001, RULE-002, RULE-005, RULE-006 and RULE-007 are suppressed during STARTUP, SHUTDOWN
and MAINTENANCE. RULE-006U reports insufficient evidence instead of labelling a sensor bias as a
leak. RULE-010 records ambiguous redundancy attribution rather than guessing which channel failed.

See [`docs/detection_methodology.md`](docs/detection_methodology.md) for rationale and threshold
selection.

## Evaluation

Two independent evaluations are reported:

### Event level

- Unit: one positive ground-truth event or one merged alarm incident.
- Overlapping/touching alarm episodes on the same equipment merge into one incident.
- Matching requires equipment, expected category, sensor overlap where known, and onset within
  `600 s` for process events or `3,600 s` for sensor faults. A `60 s` pre-event tolerance is allowed.
- Matching is one-to-one and greedy by closest onset.
- Unmatched incidents overlapping a NORMAL window (or an unmatchable positive event) are event false
  positives. Incidents outside all labelled windows are `UNKNOWN` and excluded from precision, with
  the count reported.
- A long alarm cannot claim several events; duplicate rules on one event are corroborating evidence,
  not extra true positives.

### Point level

- Unit: one `(sensor, timestamp)` telemetry sample.
- `POSITIVE` only inside explicit anomaly windows for that event's expected sensor.
- `NEGATIVE` only inside explicit NORMAL windows.
- Other samples are `UNKNOWN` and excluded. Missing/unobserved samples are excluded even inside a
  labelled window.
- Predictions use the detector's actual active interval, including resolution tails.
- Precision, recall, F1 and FPR return `null` when their denominator is zero.

See [`docs/evaluation_methodology.md`](docs/evaluation_methodology.md) for the exact policy and
worked examples.

## Verified Results

### Reproduced 1.x baseline (before changes)

| Run | Telemetry rows | Alarm rows | Reported precision | Reported recall | Reported F1 |
|---|---:|---:|---:|---:|---:|
| starter | 51,840 | 929 | 0.0800 | 1.000 | 0.1481 |
| full | 316,800 | 1,245 | 0.010638 | 1.000 | 0.021053 |

The baseline repeated alarms per sample, had no lifecycle, and mixed event TP with raw alarm-row FP.
The defects are documented in [`docs/baseline_findings.md`](docs/baseline_findings.md).

### Final 2.0 runs

| Run | Rows | Events (TP/FN/FP) | Event P / R / F1 | Point P / R | Episodes / incidents |
|---|---:|---|---|---|---:|
| starter, default | 51,840 | 4 / 0 / 0 | 1.000 / 1.000 / 1.000 | 0.9921 / 0.9778 | 7 / 4 |
| full, default | 316,800 | 4 / 0 / 0 | 1.000 / 1.000 / 1.000 | 0.9910 / 0.9800 | 7 / 4 |
| full, compact (99k) | 99,000 | 4 / 0 / 0 | 1.000 / 1.000 / 1.000 | 0.9801 / 0.9318 | 7 / 4 |
| full, calibration | 316,740 | 7 / 0 / 0 | 1.000 / 1.000 / 1.000 | 0.9864 / 0.8467 | 10 / 7 |
| **full, evaluation** | **316,740** | **10 / 1 / 0** | **1.000 / 0.9091 / 0.9524** | **0.9883 / 0.8038** | **15 / 10** |

The evaluation set is the primary independent result. The only missed event is the
`1.5% of capacity/hour` light leak (CSV row `GT-000001`, scenario-matrix label `E-LEAK-01`), below
the balance/decline sensitivity floor. All 8 NORMAL windows had no alarm incident. Event false
positives are zero; the 10 point false positives are short episode tails after anomalies end, not
alarm incidents in normal operation.

Detailed per-event tables and false-alarm analysis are in
[`docs/validation_report.md`](docs/validation_report.md).

## Validation, SQL and Tests

- **87 validation checks** cover primary/foreign keys, topology, bounds, sensor composition,
  lineage/config hashes, telemetry cadence/quality/completeness, scenarios and windows, physics,
  alarm lifecycle, evaluation formulas, ground-truth isolation, negative cases and SQLite integrity.
  Final result: 87 PASS.
- **20 SQL statements** in `sql/analysis_queries.sql` each declare `expect=nonempty` or
  `expect=zero_rows`. The runner executes them and fails on an unmet expectation. Final result:
  20 PASS.
- **61 pytest tests** cover IDs, generation, physics, detection lifecycle/grouping/mode suppression/
  isolation, evaluation units and zero denominators, data integrity, scenarios, validation, SQL and
  reproducibility. Final result: 61 passed.

## Reproducibility

For a fixed seed (`20261022`), configuration and scenario set, the deterministic artifacts are
byte-identical. Two clean full/default runs produced identical:

- master data (7 CSVs), telemetry, scenario definitions and ground truth;
- alarms, alarm history and incidents;
- evaluation events, evaluation metrics JSON and readable evaluation summary;
- simulation run and metadata records;
- SQL report.

The path-independent configuration hash is identical (`d422f3bbee3dcadc` for full/default). The
comparison includes 19 artifacts and is recorded in
[`reports/final/reproducibility.json`](reports/final/reproducibility.json). `config.json` contains
absolute output paths, and `evaluation_metrics.csv` / `validation_results.csv` contain wall-clock
timestamps, so those files are excluded from byte-level comparison. `run_manifest.json` hashes
those timestamped/path-bearing files and therefore also differs; its per-file hashes for
deterministic artifacts match.

## Limitations

- Synthetic data and simplified hydraulics; results do not establish real-plant performance.
- Rule-based detection only; no machine learning.
- Light leak below the sensitivity floor is intentionally missed (`E-LEAK-01`).
- Point false positives are episode tails after anomaly end; point false negatives include detection
  latency and the light leak.
- Sensor-fault localization can be ambiguous between redundant level/pressure channels.
- Event matching scores onset and category, not duration; point metrics expose duration/latency.
- No real-time streaming or dashboard; batch CLI only.
- SQLite is suitable for local analytics, not high-concurrency deployment.

See [`docs/assumptions.md`](docs/assumptions.md) for the full list and interpretation guidance.

## Documentation Map

| Document | Contents |
|---|---|
| [`docs/baseline_findings.md`](docs/baseline_findings.md) | Reproduced 1.x baseline and 12 defects |
| [`docs/detection_methodology.md`](docs/detection_methodology.md) | Rules, thresholds, lifecycle, uncertainty |
| [`docs/evaluation_methodology.md`](docs/evaluation_methodology.md) | Event/point units, matching, unknown labels |
| [`docs/implementation_decisions.md`](docs/implementation_decisions.md) | Decisions, evidence, rejected alternatives |
| [`docs/validation_report.md`](docs/validation_report.md) | Final metrics, per-event results, requirement matrix |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | CSV/SQLite field definitions |
| [`docs/architecture.md`](docs/architecture.md) | Modules, data flow, reporting |
| [`docs/assumptions.md`](docs/assumptions.md) | Modelling and evaluation assumptions |
| [`docs/handover_guide.md`](docs/handover_guide.md) | Onboarding and reproduction guide |
| [`reports/final/`](reports/final/) | Compact machine-readable evidence and logs |

## License and AI-Use Disclosure

This is a synthetic project for evaluation purposes. AI prompt history, tool usage and
implementation decisions are recorded in [`ai_usage/`](ai_usage/). The workspace was not pushed or
published as part of the 2.0 work.

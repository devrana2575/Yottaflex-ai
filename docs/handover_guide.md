# Implementation Handover Guide (YottaFlex 2.0.0)

This guide is for a reviewer or candidate who needs to run, inspect and explain the project. The
authoritative evidence is in [`validation_report.md`](validation_report.md); the pre-change audit is
in [`baseline_findings.md`](baseline_findings.md).

## 1. Setup

```bash
cd D:\PROJECTS\yottaflex
python -m pip install -r requirements.txt
python -m pip install -e .
yottaflex --version
```

Expected version: `2.0.0`. Python 3.11+ is required; all reported runs used Python 3.14.4.

## 2. Recommended Runs

Use a fresh output directory for each run.

```bash
# Required full volume: 316,800 rows
yottaflex pipeline --mode full --seed 20261022 --output-dir data/processed/full-run

# Independent evaluation set: 316,740 rows (60 labelled missing rows)
yottaflex pipeline --mode full --seed 20261022 --scenario-set evaluation \
  --output-dir data/processed/evaluation-run

# Calibration set: different windows/equipment/severities
yottaflex pipeline --mode full --seed 20261022 --scenario-set calibration \
  --output-dir data/processed/calibration-run

# ~100,000-row configuration: 99,000 rows
yottaflex pipeline --mode full --seed 20261022 --scenario-set compact --duration 7.5 \
  --output-dir data/processed/compact-run

# Small end-to-end run: 51,840 rows
yottaflex pipeline --mode starter --seed 20261022 --output-dir data/processed/starter-run
```

`pipeline` runs generate, simulate, detect, evaluate, validate, SQLite export and SQL checks. If a
step fails, the CLI exits non-zero; do not treat a partial directory as evidence.

Individual steps (same output directory):

```bash
yottaflex generate   --mode full --seed 20261022 --output-dir data/processed/full-run
yottaflex simulate   --mode full --seed 20261022 --duration 24 --output-dir data/processed/full-run
yottaflex detect     --output-dir data/processed/full-run
yottaflex evaluate   --output-dir data/processed/full-run
yottaflex validate   --output-dir data/processed/full-run
yottaflex export-sql --output-dir data/processed/full-run
yottaflex run-sql    --output-dir data/processed/full-run --sql-file sql/analysis_queries.sql
```

Tests:

```bash
python -m pytest -q
```

## 3. Module Map

| Module | Purpose | Key entry point |
|---|---|---|
| `config.py` | Dataclass configuration, scenario sets, thresholds, path-independent hash | `Config`, `DetectionConfig` |
| `id_generator.py` | Deterministic IDs | `IDGenerator` |
| `generator.py` | Facilities, pumps, tanks, valves, pipes, sensors, modes, topology | `DataGenerator.generate_all()` |
| `simulation.py` | Pump curves, mass-consistent tanks, hydrostatic pressure, modes, noise | `ProcessSimulator.simulate_baseline()` |
| `scenarios.py` | Scenario matrix, injection, NORMAL complements, ground truth | `ScenarioInjector` |
| `detection.py` | Rules, episode tracker, persistence/hysteresis, history | `DetectionEngine.detect()` |
| `evaluation.py` | Incidents, one-to-one matching, event/point metrics | `Evaluator.evaluate()` |
| `validation.py` | 87 executable checks and status report | `Validator.run_all()` |
| `persistence.py` | SQLite export/query/integrity helpers | `Database` |
| `schema.py` | 2.0.0 DDL, constraints, indexes | schema constants |
| `cli.py` | CLI commands | `yottaflex` console script |

## 4. What the Simulator Produces

Full scale: 3 facilities, 20 pumps, 30 tanks, 60 valves, 135 pipes, 220 sensors.

| Equipment | Sensors | Roles |
|---|---:|---|
| Pump | 2 | discharge flow, discharge pressure |
| Tank | 4 | level, pressure, inlet flow, outlet flow |
| Valve | 1 | through flow |

Sensor composition is deliberate: tank flow balance needs inlet and outlet flow, and hydrostatic
redundancy needs level and pressure. The total remains 220 by using one flow sensor per valve.

- Full default: 220 sensors x 1,440 samples = 316,800 telemetry rows.
- Compact: 220 x 450 = 99,000 rows.
- Starter: 36 x 1,440 = 51,840 rows.
- Evaluation/calibration: 316,740 rows because the missing-sensor scenario removes 60 rows.

Missing rows are intentional and confined to the labelled sensor-fault window.

## 5. Core Equations

### Pump

```text
H(Q) = max(0, H_shutoff - k * Q^2)
H_shutoff = 1.20 * H_nominal
k = (H_shutoff - H_nominal) / Q_nominal^2
P = H * 0.0981 bar
```

### Tank

```text
V = capacity_m3 * level_pct / 100
dV/dt = Q_in - Q_out
P = level_pct / 100 * height_m * 0.0981 bar
```

### Mass balance

```text
residual = Q_in - Q_out - dV/dt
```

Normal operation satisfies the residual within `max(5 m3/h, 8% of mean flow)`. A leak produces a
positive residual; a biased flow meter changes only the measurement.

## 6. Detection Rules

| Rule | Alarm | Activation | Category |
|---|---|---|---|
| RULE-001 | Tank level out of bounds | level `< 10%` or `> 90%`; exit `[12%, 88%]`; 120 s + 3 samples | PROCESS_FAULT |
| RULE-002 | Rapid tank level decline | `>= 0.30 pp` fall over 5 min; recovery `>= -0.15 pp`; 120 s + 3 samples | PROCESS_FAULT |
| RULE-003 | Sensor stuck | unchanged `<= 1e-9` for `>= 30 min` | SENSOR_FAULT |
| RULE-004 | Sensor quality | status not `GOOD` | SENSOR_FAULT |
| RULE-005 | Pump low flow | 5-min mean `< 80%` nominal; recovery `> 85%`; 240 s + 3 samples | PROCESS_FAULT |
| RULE-006 | Tank flow-balance loss | residual `> max(5 m3/h, 8%)` **and** level decline `>= 0.15 pp`; 480 s + 5 samples | PROCESS_FAULT |
| RULE-006U | Balance inconsistency | residual above uncertainty without decline | UNCERTAIN |
| RULE-007 | Pump off curve | relative head error `> 10%`, flow `< 90%` nominal; recovery `< 6%`; 300 s + 3 samples | PROCESS_FAULT |
| RULE-008 | Implausible reading | flow outside `[0, 500]`, pressure outside `[0, 60]`, level outside `[0, 100]` | SENSOR_FAULT |
| RULE-009 | Missing telemetry | contiguous gap at expected cadence | SENSOR_FAULT |
| RULE-010 | Level/pressure disagreement | hydrostatic difference `> 4 pp`; 180 s + 3 samples | SENSOR_FAULT |

Process rules RULE-001/002/005/006/007 are suppressed in STARTUP, SHUTDOWN and MAINTENANCE.
Sensor-integrity rules are not suppressed. RULE-006U reports uncertainty instead of calling a
possible sensor bias a leak; RULE-010 reports ambiguous redundancy attribution instead of guessing
which channel is faulty.

## 7. How Detection Is Evaluated

Two independent units:

- **Event:** one positive ground-truth event or one merged alarm incident. Overlapping episodes on
  the same equipment merge. Matching requires equipment, category, sensor overlap where known, and
  onset within 600 s (process) or 3,600 s (sensor), with 60 s pre-event tolerance. Assignment is
  one-to-one and deterministic. Event FP = unmatched incident; unknown incidents are reported and
  excluded.
- **Point:** one `(sensor, timestamp)` sample. Positive only in explicit anomaly windows for the
  expected sensor; negative only in explicit NORMAL windows; everything else is UNKNOWN and
  excluded. Predictions use the detector's actual active interval, including tails. Zero
  denominators return `null`.

Do not compare the 1.x `0.010638` precision with the 2.0 numbers. The 1.x value mixed event TP with
raw alarm-row FP; it was not an event or point metric.

## 8. Verified Results

| Run | Rows | Event TP/FN/FP | Event P/R/F1 | Point P/R |
|---|---:|---|---|---|
| starter/default | 51,840 | 4/0/0 | 1.0000 / 1.0000 / 1.0000 | 0.9921 / 0.9778 |
| full/default | 316,800 | 4/0/0 | 1.0000 / 1.0000 / 1.0000 | 0.9910 / 0.9800 |
| full/compact | 99,000 | 4/0/0 | 1.0000 / 1.0000 / 1.0000 | 0.9801 / 0.9318 |
| full/calibration | 316,740 | 7/0/0 | 1.0000 / 1.0000 / 1.0000 | 0.9864 / 0.8467 |
| full/evaluation | 316,740 | 10/1/0 | 1.0000 / 0.9091 / 0.9524 | 0.9883 / 0.8038 |

Evaluation set details:

- The only missed event is the 1.5% of capacity/hour light leak (`GT-000001`, matrix label
  `E-LEAK-01`), below the balance/decline sensitivity floor.
- All 8 NORMAL windows were alarm-free at the incident level.
- The 10 point false positives are 1-5 sample episode tails after events end. They are retained.
- The 2 unknown predictions at SNS-003 11:00-11:01 are excluded and reported, not counted as FP.
- Sensor-fault latency is longer (60-3,180 s) than process latency (240-360 s), by design.
- All 87 validation checks, 20 SQL assertions and 61 tests pass.

## 9. Verification and Evidence

```bash
python -m pytest -q
yottaflex validate --output-dir data/processed/evaluation-run
yottaflex run-sql --output-dir data/processed/evaluation-run \
  --sql-file sql/analysis_queries.sql
```

Evidence:

- [`validation_report.md`](validation_report.md) — results, per-event tables, requirement matrix.
- [`baseline_findings.md`](baseline_findings.md) — reproduced 1.x baseline and 12 defects.
- [`reports/final/summary.json`](../reports/final/summary.json) — machine-readable run summary.
- [`reports/final/reproducibility.json`](../reports/final/reproducibility.json) — 19-file hash
  comparison.
- [`reports/final/yf2-evaluation/`](../reports/final/yf2-evaluation/) — compact evaluation evidence.

Two clean full/default runs produced 19 byte-identical deterministic artifacts and the same
path-independent configuration hash (`d422f3bbee3dcadc`). `config.json` paths and wall-clock columns
are expected to differ.

## 10. The Five Original Negative Tests and the Two Executable Guards

The original five negative fixtures remain in `tests/test_negative_scenarios.py`:

| Test | Scenario | Expected |
|---|---|---|
| NEG-001 | Pipe references a missing node | Shared endpoint validator rejects it |
| NEG-002 | Tank level exceeds 100% | Shared bounds validator rejects it |
| NEG-003 | Flow conservation violated beyond tolerance | Residual exceeds configured tolerance |
| NEG-004 | Simulation output lacks input config | Lineage validator rejects it |
| NEG-005 | Sensor fault classified as process fault | Sensor-quality alarm only; no ground-truth ID |

The 2.0 validator adds two executable negative checks: `NEG-006-DUPLICATE-ALARMS` (overlapping
alarms count once at event level) and `NEG-007-IMPLAUSIBLE-SENSOR` (implausible reading becomes a
sensor fault, not a process fault).

## 11. Troubleshooting

| Symptom | Check |
|---|---|
| `yottaflex` not found | Run `python -m pip install -e .` |
| Missing telemetry/scenarios | Run generate, then simulate, in the same output directory |
| SQL file not found | Run from the repository root or pass an absolute `--sql-file` |
| SQLite locked | Close other connections; export recreates the DB by default |
| Out of memory | Use starter or compact; full telemetry is ~29 MB CSV |
| Test collection error | `pytest.ini` restricts collection to `tests/test_*.py` |
| Validation failure | Read `validation_results.csv`; `FAIL` rows include details |
| SQL assertion failure | Read `sql_query_report.json`; each query declares its expectation |

## 12. Known Limitations

- Synthetic, simplified hydraulics; not a validated digital twin.
- Rule-based detection only; no ML.
- Light leak below the sensitivity floor is intentionally missed.
- Point false positives are episode tails; point false negatives include activation latency.
- Sensor-fault localization can be ambiguous between redundant channels.
- Event matching scores onset/category, not duration; point metrics carry duration/latency.
- No real-time streaming or dashboard; SQLite is for local analytics.
- The original verbatim task prompt was not retained; prompt history marks the reconstruction.

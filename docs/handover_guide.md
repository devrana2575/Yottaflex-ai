# Implementation Handover Guide (YottaFlex 2.0.0)

This guide is for a reviewer or candidate who needs to run, inspect and explain the project. The
authoritative evidence is in [`validation_report.md`](validation_report.md); the pre-change audit is
in [`baseline_findings.md`](baseline_findings.md).

## 1. Setup

```bash
cd <repository-root>
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS:      source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
yottaflex --version
```

Expected version: `2.0.0`. Python 3.11+ is required; all reported runs used Python 3.14.4. A fresh
virtual environment (pandas 3.1.0 / NumPy 2.5.4, pytest 9.2.0) was recreated for final acceptance on
2026-10-29 using the README core install (`pip install -e . pytest`); all 68 tests passed, and the
exact-100k, full/default and evaluation pipelines reproduced the counts and metrics.

## 2. Recommended Runs

Use a fresh output directory for each run.

```bash
# Required full volume: 316,800 rows
yottaflex pipeline --mode full --seed 20261022 --output-dir <fresh-output-dir>/full-run

# Independent evaluation set: 316,740 rows (60 labelled missing rows)
yottaflex pipeline --mode full --seed 20261022 --scenario-set evaluation \
  --output-dir <fresh-output-dir>/evaluation-run

# Calibration set: different windows/equipment/severities
yottaflex pipeline --mode full --seed 20261022 --scenario-set calibration \
  --output-dir <fresh-output-dir>/calibration-run

# Exact 100,000-row baseline: 120 x 455 + 100 x 454, 7.583 h
yottaflex pipeline --mode full --seed 20261022 --scenario-set baseline \
  --target-telemetry-rows 100000 --output-dir <fresh-output-dir>/baseline-100k

# Historical compact demonstration: 99,000 rows
yottaflex pipeline --mode full --seed 20261022 --scenario-set compact --duration 7.5 \
  --output-dir <fresh-output-dir>/compact-run

# Small end-to-end run: 51,840 rows
yottaflex pipeline --mode starter --seed 20261022 --output-dir <fresh-output-dir>/starter-run

# Portable exports
yottaflex export-json --output-dir <fresh-output-dir>/baseline-100k
yottaflex export-sql-script --output-dir <fresh-output-dir>/baseline-100k
```

`pipeline` runs generate, simulate, detect, evaluate, validate, SQLite export and SQL checks. If a
step fails, the CLI exits non-zero; do not treat a partial directory as evidence. The exact target
derives the duration; `--duration` cannot override it, and a scenario set that removes telemetry
rows is rejected for exact-budget runs.

Individual steps (same output directory):

```bash
yottaflex generate   --mode full --seed 20261022 --output-dir <fresh-output-dir>/full-run
yottaflex simulate   --mode full --seed 20261022 --duration 24 --output-dir <fresh-output-dir>/full-run
yottaflex detect     --output-dir <fresh-output-dir>/full-run
yottaflex evaluate   --output-dir <fresh-output-dir>/full-run
yottaflex validate   --output-dir <fresh-output-dir>/full-run
yottaflex export-sql --output-dir <fresh-output-dir>/full-run
yottaflex run-sql    --output-dir <fresh-output-dir>/full-run --sql-file sql/analysis_queries.sql
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
| `state_history.py` | Append-only equipment initialization/scenario transitions and validation | `generate_equipment_state_events()` |
| `validation.py` | 87 executable checks and status report | `Validator.run_all()` |
| `persistence.py` | SQLite export/query/integrity helpers | `Database` |
| `exports.py` | Per-table JSON and portable SQL schema/seed exports | `export_json_tables()`, `export_sql_seed()` |
| `schema.py` | 2.0.0 DDL, constraints, indexes, state history | schema constants |
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
- Exact 100k baseline: 120 sensors x 455 + 100 sensors x 454 = 100,000 rows.
- Compact historical demonstration: 220 x 450 = 99,000 rows.
- Starter: 36 x 1,440 = 51,840 rows.
- Evaluation/calibration: 316,740 rows because the missing-sensor scenario removes 60 rows.

Missing rows in evaluation/calibration are intentional and confined to the labelled sensor-fault
window. The exact 100k baseline omits the row-removing missing-sensor fault so the post-injection
count stays exact. The 100k baseline also populates `equipment_state_events` with 341 real
initialization/scenario transitions; the table is not detector input.

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
| full/exact 100k baseline | 100,000 | 4/0/0 | 1.0000 / 1.0000 / 1.0000 | 0.9800 / 0.9280 |
| full/compact (historical) | 99,000 | 4/0/0 | 1.0000 / 1.0000 / 1.0000 | 0.9801 / 0.9318 |
| full/calibration | 316,740 | 7/0/0 | 1.0000 / 1.0000 / 1.0000 | 0.9864 / 0.8467 |
| full/evaluation | 316,740 | 10/1/0 | 1.0000 / 0.9091 / 0.9524 | 0.9883 / 0.8038 |

Evaluation set details:

- The only missed event is the 1.5% of capacity/hour light leak (`GT-000001`, matrix label
  `E-LEAK-01`). Its balance residual is above the absolute floor, but the 5-minute decline
  corroboration and 480 s persistence do not both hold; it is a documented sensitivity miss, not a
  balance-floor failure.
- All 8 NORMAL windows were alarm-free at the incident level.
- The 10 point false positives are 1-5 sample episode tails after events end. They are retained.
- The 2 unknown predictions at SNS-003 11:00-11:01 are excluded and reported, not counted as FP.
- Sensor-fault latency is longer (60-3,180 s) than process latency (240-360 s), by design.
- All 87 executable validation rows, 20 SQL assertions and 68 tests pass in both the main and fresh
  clean environments. Review-level caveats (light leak, reconstructed earlier prompt records, and
  cross-version last-bit float serialization) are tracked separately in the validation report; they
  are not rows in the 87-row validation CSV. Publication was explicitly authorized on 2026-10-28.

## 9. Verification and Evidence

```bash
python -m pytest -q
yottaflex validate --output-dir <fresh-output-dir>/evaluation-run
yottaflex run-sql --output-dir <fresh-output-dir>/evaluation-run \
  --sql-file sql/analysis_queries.sql
```

Evidence:

- [`validation_report.md`](validation_report.md) — results, per-event tables, requirement matrix.
- [`baseline_findings.md`](baseline_findings.md) — reproduced 1.x baseline and 12 defects.
- [`reports/final/summary.json`](../reports/final/summary.json) — machine-readable run summary.
- [`reports/final/reproducibility.json`](../reports/final/reproducibility.json) — prior 19-file
  full/default hash comparison.
- [`reports/final/reproducibility_100k.json`](../reports/final/reproducibility_100k.json) — exact
  100k two-run comparison and portable-export checks.
- [`reports/final/yf2-100k/`](../reports/final/yf2-100k/) - compact exact-100k evidence.
- [`reports/final/yf2-compact-99k/`](../reports/final/yf2-compact-99k/) - historical compact 99k evidence.
- [`reports/final/yf2-evaluation/`](../reports/final/yf2-evaluation/) — compact evaluation evidence.

Two fresh exact-100k runs in the main environment produced 20/23 byte-identical files; the other
three differed only in wall-clock `evaluated_at` / `validated_at` fields and were logically equal.
All 19 SQLite tables matched logically, with 18 populated tables and zero FK violations. The prior
full/default comparison remains 19/19 within the main environment with the same path-independent
configuration hash (`d422f3bbee3dcadc`); at that time 17 tables were populated. A fresh pandas
3.1.0 / NumPy 2.5.4 environment passed all 68 tests and reproduced the exact-100k counts and
metrics; 19/23 artifacts were byte-identical, with three timestamp-only differences and one
last-bit float report difference. The prior full/default clean-environment comparison remains
17/19 artifacts with two files differing only in `peak_value` floats at about `1e-13`. The
2026-10-29 verification also reproduced clean full/default and evaluation counts and event/point
metrics, matching main.

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
- Light leak is a corroboration/persistence sensitivity miss; its balance residual is above the
  absolute floor, but decline corroboration and 480 s persistence do not both hold.
- Point false positives are episode tails; point false negatives include activation latency.
- Sensor-fault localization can be ambiguous between redundant channels.
- Event matching scores onset/category, not duration; point metrics carry duration/latency.
- No real-time streaming or dashboard; SQLite is for local analytics.
- The original verbatim task prompt was not retained; prompt history marks the reconstruction.

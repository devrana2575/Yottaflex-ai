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
| Exact 100k baseline | 100,000 rows in 7.583 h: 120 sensors x 455 + 100 sensors x 454 |
| Equipment state history | 341 populated rows for the 100k baseline (333 initialization + 8 scenario transitions) |
| Primary independent evaluation | 11 events: TP=10, FN=1, FP=0; event precision=1.0, recall=0.9091, F1=0.9524 |
| Point evaluation (evaluation set) | TP=844, FP=10, TN=112,190, FN=206; precision=0.9883, recall=0.8038 |
| Validation | 87 executable PASS / 0 FAIL / 0 CSV WARN / 0 NOT_IMPLEMENTED; review-level caveats tracked separately |
| SQL analytics | 20 statements, 20 PASS |
| Tests | 68 passed |
| Reproducibility (exact 100k) | 20/23 files byte-identical across two fresh runs; the other 3 differ only in wall-clock `evaluated_at`/`validated_at` fields and are logically identical |
| Portable exports | CSV, SQLite (18 populated tables), per-table JSON, SQL schema+seed; 100k export verified with `integrity_check=ok` and zero FK violations |

The full evidence, including per-event results, false-alarm analysis and the requirement matrix, is
in [`docs/validation_report.md`](docs/validation_report.md). The `87` count is the executable
validation CSV only. Review-level caveats (light-leak coverage, reconstructed prompt history, and
cross-version last-bit float serialization) are tracked there separately and are not added to that
denominator. Publication was explicitly authorized on 2026-10-28 and reaffirmed by the 2026-10-29
final-audit instruction.

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
- **Five scenario sets.** `default`, `calibration`, `evaluation`, `baseline` and `compact`;
  calibration and evaluation use different windows, equipment and severities. `baseline` is the
  exact 100k set and omits the row-removing missing-sensor fault.
- **Exact telemetry target.** `--target-telemetry-rows 100000` derives the duration and allocates
  455 samples to 120 sensors and 454 to 100, giving exactly 100,000 real samples without padding,
  duplication or silent removal. The historical 316,800-row path is unchanged when no target is set.
- **Populated state history.** `equipment_state_events` records initialization and scenario
  transitions with an explicit allowed-transition state machine; it is append-only and not detector
  input.
- **Portable exports.** In addition to CSV and SQLite, `export-json` writes deterministic per-table
  JSON and `export-sql-script` writes a portable SQL schema + seed script.
- **Executable claims.** 87 validation checks, 20 SQL assertions and a 68-test suite run against
  generated artifacts.

## Architecture

```
yottaflex/
â”œâ”€â”€ src/yottaflex/
â”‚   â”œâ”€â”€ config.py          # Configuration, scenario sets, thresholds, path-independent hash
â”‚   â”œâ”€â”€ id_generator.py    # Deterministic IDs
â”‚   â”œâ”€â”€ generator.py       # Facilities, equipment, pipes, sensors, modes, topology
â”‚   â”œâ”€â”€ simulation.py      # Pump curves, tanks, modes, noise, exact-budget allocation
â”‚   â”œâ”€â”€ scenarios.py       # Scenario matrix, injection, NORMAL complements, ground truth
â”‚   â”œâ”€â”€ state_history.py   # Append-only equipment state transitions and validators
â”‚   â”œâ”€â”€ detection.py       # Rules, episode tracker, persistence/hysteresis, history
â”‚   â”œâ”€â”€ evaluation.py      # Incidents, one-to-one matching, event and point metrics
â”‚   â”œâ”€â”€ validation.py      # 87 executable checks and status report
â”‚   â”œâ”€â”€ persistence.py     # SQLite export/query/integrity helpers
â”‚   â”œâ”€â”€ exports.py         # JSON table export and portable SQL seed generation
â”‚   â”œâ”€â”€ schema.py          # 2.0.0 DDL, constraints, indexes
â”‚   â””â”€â”€ cli.py             # generate, simulate, detect, evaluate, validate, export-*, run-sql, pipeline
â”œâ”€â”€ tests/                 # 68 tests
â”œâ”€â”€ sql/                   # 20 analytical statements with declared expectations
â”œâ”€â”€ docs/                  # Methodology, decisions, data dictionary, requirement matrix and evidence
â”œâ”€â”€ reports/final/         # Compact final-run evidence from clean runs
â””â”€â”€ ai_usage/              # AI prompt history, decisions and verification notes
```

## Setup

Requirements: Python 3.11 or newer, Windows/Linux/macOS. A fresh virtual environment is
recommended. From the repository root:

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install pytest
```

`pip install -e .` installs the core runtime declared in `setup.py`. `requirements.txt` is the
complete development/optional-tooling list (including pytest, the dashboard, SQLAlchemy, and
documentation/QA tools); use `python -m pip install -r requirements.txt` instead of the
`pytest` line when those optional tools are needed. If the package is not installed, the checked-in
`pytest.ini` still adds `src/` to the test import path, so `python -m pytest -q` can run from a
checkout; installing the package is still required for the `yottaflex` console command.

Verify the installation and CLI:

```bash
yottaflex --version
yottaflex --help
```

A fresh virtual environment (Python 3.14.4, pandas 3.1.0, NumPy 2.5.4, pytest 9.2.0) was installed
and tested during the 2026-10-29 final verification. It passed all 68 tests and reproduced the
exact-100k, full/default and evaluation pipelines with matching counts and metrics. The main
environment also ran two fresh exact-100k runs, full/default, evaluation, exports, independent
metrics and the 17-test targeted suite. The current tree contains six additional submission tests
and collects **68 tests**. The package has no
`pyproject.toml`; `setup.py` is the packaging metadata, and editable installation works with current
pip/setuptools.

## Quick Start

### Default full pipeline (316,800 rows)

```bash
yottaflex pipeline --mode full --seed 20261022 --output-dir <fresh-output-dir>/full-run
```

The pipeline runs generate, simulate, detect, evaluate, validate, SQLite export and SQL checks, and
writes a manifest. It uses the `default` scenario set unless `--scenario-set` is given.

### Independent evaluation set

```bash
yottaflex pipeline --mode full --seed 20261022 --scenario-set evaluation \
  --output-dir <fresh-output-dir>/evaluation-run
```

The evaluation run has 316,740 telemetry rows because the labelled missing-sensor scenario removes
60 rows. The missing rows are intentional and are not a data-quality defect.

### Exact 100,000-row baseline

```bash
yottaflex pipeline --mode full --seed 20261022 --scenario-set baseline \
  --target-telemetry-rows 100000 --output-dir <fresh-output-dir>/baseline-100k
```

The target derives a duration of `455 * 60 s = 7.5833 h` and allocates 455 samples to 120 sensors
and 454 to 100: `120 x 455 + 100 x 454 = 100,000`. The `baseline` scenario set deliberately omits
the row-removing missing-sensor fault, so the count remains exactly 100,000 after injection.
`--duration` is rejected if it conflicts with the target-derived duration. The historical full
configuration remains 316,800 rows when no target is supplied.

The historical `compact` set remains available as a 99,000-row demonstration:

```bash
yottaflex pipeline --mode full --seed 20261022 --scenario-set compact --duration 7.5 \
  --output-dir <fresh-output-dir>/compact-run
```

### Calibration set

```bash
yottaflex pipeline --mode full --seed 20261022 --scenario-set calibration \
  --output-dir <fresh-output-dir>/calibration-run
```

Calibration uses different events and severities from the evaluation set. It checks that each
mechanism is detectable; it is not the reported evaluation set.

### Step-by-step commands

Use the same output directory for each step:

```bash
yottaflex generate  --mode full --seed 20261022 --output-dir <fresh-output-dir>/full-run
yottaflex simulate  --mode full --seed 20261022 --duration 24 --output-dir <fresh-output-dir>/full-run
yottaflex detect    --output-dir <fresh-output-dir>/full-run
yottaflex evaluate  --output-dir <fresh-output-dir>/full-run
yottaflex validate  --output-dir <fresh-output-dir>/full-run
yottaflex export-sql --output-dir <fresh-output-dir>/full-run
yottaflex export-json --output-dir <fresh-output-dir>/full-run
yottaflex export-sql-script --output-dir <fresh-output-dir>/full-run
yottaflex run-sql   --output-dir <fresh-output-dir>/full-run --sql-file sql/analysis_queries.sql
```

`export-json` defaults to `<output-dir>/json_exports/` and writes one JSON array per table plus a
manifest with a relative `source_root` (no absolute local path). `export-sql-script` defaults to
`<output-dir>/yottaflex_seed.sql` and writes a portable schema + INSERT script that can create a new
SQLite database. The 100k JSON is about 32 MB and the SQL seed about 30 MB; both are generated
outside version control.

### Tests

```bash
python -m pytest -q
```

Run this from the repository root. No `PYTHONPATH` variable is needed: `pytest.ini` sets
`pythonpath = src`, and an editable install (`python -m pip install -e .`) provides the CLI. The
suite includes unit, data-integrity, scenario, detection, evaluation, validation, integration,
submission-artifact and reproducibility tests. The historical 11 tests are retained and extended;
the current suite collects 68 tests and the final remediation run reports 68 passed.

## Data Model

Core entities: facility, pump, tank, valve, pipe, sensor, telemetry, operating mode, alarm,
simulation run. Version 2.0 adds tank height, sensor roles, alarm category/occurrence/peak/
attribution, scenario and ground-truth severity/expected sensors, append-only alarm history,
alarm incidents, evaluation/validation tables, and a populated append-only
`equipment_state_events` history with explicit allowed transitions. The state history is not
detector input. The exact 100k baseline records 341 state events: 333 initialization events plus
8 scenario start/recovery events.

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
| `baseline` | 7.583 h | 4 | 5 | Exact 100,000-row configuration; no missing-sensor fault |
| `compact` | 7.5 h | 4 | 5 | Historical 99,000-row demonstration |

Mechanisms:

- **Leak** - volume loss from a tank, with a physical flow-balance residual and hydrostatic response.
- **Blockage** - pump flow restriction with increased upstream pressure.
- **Pump degradation** - reduced pump flow and head relative to the nominal curve.
- **Sensor fault** - bias, drift, stuck value, or missing telemetry; the physical process stays normal.

The evaluation set covers light, medium and severe process faults plus all four sensor-fault
mechanisms. The light leak is retained as a documented sensitivity miss: its balance residual is
above the absolute `5 m3/h` floor, but the corroborating level-decline and persistence requirements
are not met.

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
| full, exact 100k baseline | 100,000 | 4 / 0 / 0 | 1.000 / 1.000 / 1.000 | 0.9800 / 0.9280 | 107 / 62 |
| full, compact (99k historical) | 99,000 | 4 / 0 / 0 | 1.000 / 1.000 / 1.000 | 0.9801 / 0.9318 | 7 / 4 |
| full, calibration | 316,740 | 7 / 0 / 0 | 1.000 / 1.000 / 1.000 | 0.9864 / 0.8467 | 10 / 7 |
| **full, evaluation** | **316,740** | **10 / 1 / 0** | **1.000 / 0.9091 / 0.9524** | **0.9883 / 0.8038** | **15 / 10** |

The evaluation set is the primary independent result. The only missed event is the
`1.5% of capacity/hour` light leak (CSV row `GT-000001`, scenario-matrix label `E-LEAK-01`). Its
10-minute balance residual is **above** the absolute `5 m3/h` floor (median `8.32 m3/h`; 82 of 90
samples above it), but the 5-minute level decline is only `-0.131 pp` median, just below the
`0.15 pp` corroboration trigger. The longest corroborated run was `300 s` and the longest
active-without-corroboration run was `420 s`, both below the `480 s` persistence requirement;
RULE-002's `0.30 pp` trigger did not fire for this event. The miss is a corroboration/persistence sensitivity
limit, not a balance-floor failure, and is retained. All 8 NORMAL windows had no alarm incident.
Event false positives are zero; the 10 point false positives are short episode tails after anomalies
end, not alarm incidents in normal operation.

Detailed per-event tables and false-alarm analysis are in
[`docs/validation_report.md`](docs/validation_report.md).

## Validation, SQL and Tests

- **87 executable validation checks** cover primary/foreign keys, topology, bounds, sensor
  composition, lineage/config hashes, telemetry cadence/quality/completeness, scenarios and windows,
  physics, alarm lifecycle, evaluation formulas, ground-truth isolation, negative cases and SQLite
  integrity. Final result: **87 PASS, 0 FAIL, 0 WARN, 0 NOT_IMPLEMENTED** in
  `validation_results.csv`.
- **Review-level caveats are tracked separately** and are not rows in that CSV: light-leak
  detection coverage, the reconstructed prompt records, and cross-version last-bit float
  serialization. They are explained in
  [`docs/validation_report.md`](docs/validation_report.md) section 10.
- **20 SQL statements** in `sql/analysis_queries.sql` each declare `expect=nonempty` or
  `expect=zero_rows`. The runner executes them and fails on an unmet expectation. Final result:
  **20 PASS**.
- **68 pytest tests** cover IDs, generation, physics, detection lifecycle/grouping/mode suppression/
  isolation, evaluation units and zero denominators, data integrity, scenarios, validation, SQL,
  exact-target allocation, state-history transitions, CSV/JSON/SQLite/SQL consistency and
  reproducibility. Final result: **68 passed** in the main environment and **68 passed** in a fresh
  Python 3.14.4 virtual environment (pandas 3.1.0 / NumPy 2.5.4) created with the README commands.
  The audit also fixed a pandas 3.1 fill-value deprecation warning and a point-coverage counter
  that counted unobserved positive rows as observed; regression assertions were added.
- **State history** is generated and exported rather than left as an empty placeholder. The 100k
  baseline has 341 events; tests validate every allowed transition, references, timestamps and the
  database row count. The schema adds `previous_state`/`new_state`/`reason`/`source` fields without
  changing the 2.0.0 schema version.
- **Portable export** commands write JSON and SQL from the same CSVs. A 100k export was executed
  into a new SQLite database with `integrity_check=ok`, zero foreign-key violations and matching
  telemetry IDs across CSV, JSON, SQLite and the SQL seed.

## Reproducibility

For a fixed seed (`20261022`), configuration, scenario set and dependency environment, the
deterministic artifacts are byte-identical. Two fresh full/default runs executed after the audit
fixes in the main environment produced identical:

- master data (7 CSVs), telemetry, scenario definitions and ground truth;
- alarms, alarm history and incidents;
- evaluation events, evaluation metrics JSON and readable evaluation summary;
- simulation run and metadata records;
- SQL report.

The path-independent configuration hash is identical for the same configuration. For the exact
100k baseline, two fresh runs were compared across 23 artifacts: **20 were byte-identical**,
including telemetry, state history, master data, scenarios/truth, alarms, incidents, evaluation
events, evaluation metrics JSON, simulation metadata and the SQL report. The remaining three
(`evaluation_metrics.csv`, `validation_results.csv`, `validation_summary.json`) differ only in
wall-clock `evaluated_at` / `validated_at` fields; after removing those documented fields they are
logically identical. `config.json` contains absolute output paths and `run_manifest.json` hashes
path/timestamp-bearing files, so they are excluded from byte-level comparison. The two SQLite
databases matched logically across all 19 tables, with 18 populated tables (the legacy
`detection_results` table is the only empty one), `integrity_check=ok`, zero foreign-key violations
and identical rows after excluding the wall-clock columns. The comparison is recorded in
[`reports/final/reproducibility_100k.json`](reports/final/reproducibility_100k.json).

The prior full/default and evaluation reproducibility evidence remains in
[`reports/final/reproducibility.json`](reports/final/reproducibility.json); those results predate
the state-history/export additions. The exact-100k baseline was also generated in a fresh Python
3.14.4 / pandas 3.1.0 / NumPy 2.5.4 virtual environment on 2026-10-29. It matched the main
environment's counts and metrics; 19/23 files were byte-identical, three differed only in wall-clock
fields and `sql_query_report.json` differed only in last-bit float serialization. The clean
environment also reproduced the full/default and evaluation runs with matching event/point metrics.
The 17/19 prior full/default artifact comparison and its `peak_value` caveat remain historical.

## Limitations

- Synthetic data and simplified hydraulics; results do not establish real-plant performance.
- Rule-based detection only; no machine learning.
- Light leak (`E-LEAK-01`) is a documented corroboration/persistence sensitivity miss: its balance
  residual is above the absolute floor, but the decline corroboration and 480 s persistence do not
  both hold. It is retained, not tuned away.
- Point false positives are episode tails after anomaly end; point false negatives include detection
  latency and the light leak.
- Sensor-fault localization can be ambiguous between redundant level/pressure channels.
- Event matching scores onset and category, not duration; point metrics expose duration/latency.
- No real-time streaming or dashboard; batch CLI only.
- Dependencies are lower-bounded, not upper-pinned; within one environment reruns are byte-identical,
  while cross-version peak floats can differ at about `1e-13` without changing metrics.
- SQLite is suitable for local analytics, not high-concurrency deployment.

See [`docs/assumptions.md`](docs/assumptions.md) for the full list and interpretation guidance.

## Documentation Map

| Document | Contents |
|---|---|
| [`docs/baseline_findings.md`](docs/baseline_findings.md) | Reproduced 1.x baseline and 12 defects |
| [`docs/detection_methodology.md`](docs/detection_methodology.md) | Rules, thresholds, lifecycle, uncertainty |
| [`docs/evaluation_methodology.md`](docs/evaluation_methodology.md) | Event/point units, matching, unknown labels |
| [`docs/implementation_decisions.md`](docs/implementation_decisions.md) | Decisions, evidence, rejected alternatives |
| [`docs/validation_report.md`](docs/validation_report.md) | Final metrics, per-event results, validation evidence |
| [`docs/requirement_matrix.md`](docs/requirement_matrix.md) | Requirement-by-requirement implementation, evidence and status |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | CSV/SQLite field definitions for core entities and history |
| [`docs/architecture.md`](docs/architecture.md) | Modules, data flow, reporting |
| [`docs/assumptions.md`](docs/assumptions.md) | Modelling and evaluation assumptions |
| [`docs/handover_guide.md`](docs/handover_guide.md) | Onboarding and reproduction guide |
| [`reports/final/`](reports/final/) | Compact machine-readable evidence and logs |

## License and AI-Use Disclosure

This is a synthetic project for evaluation purposes. AI prompt history, tool usage and
implementation decisions are recorded in [`ai_usage/`](ai_usage/). The 2.0 implementation was
committed as `6103e1a` and published to `origin/main` only after explicit authorization. The
2026-10-27 audit corrections were committed and pushed to `origin/main` after separate explicit
authorization. The 2026-10-28 remediation was committed locally and, after the user explicitly
authorized publication with the prompt `push`, pushed to `origin/main` after the final audit. The
2026-10-29 final audit re-ran the evidence, changed documentation/report and prompt records only,
and published those reviewed changes normally. No force-push or shared-history rewrite occurred.

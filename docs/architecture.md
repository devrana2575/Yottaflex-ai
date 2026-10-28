# Architecture (YottaFlex 2.0.0)

## System overview

YottaFlex is a modular Python batch application that generates industrial master data, simulates
mass-consistent telemetry, injects deterministic anomalies, detects observed anomalies, records
append-only equipment state transitions, evaluates event- and point-level performance against
isolated ground truth, exports CSV/SQLite/JSON/portable SQL, and executes validation and SQL checks.

```
Config -> IDGenerator -> DataGenerator -> ProcessSimulator -> ScenarioInjector
       -> state_history -> DetectionEngine -> Evaluator -> Validator
       -> CSV/SQLite/JSON/SQL exports -> CLI reports
```

The exact telemetry-budget path is a deliberate branch in `ProcessSimulator`: the historical
`telemetry_target_rows=None` path emits the rectangular `sensors x steps` table, while an explicit
target uses a deterministic quotient/remainder allocation across real sensors and cadence
timestamps. The target does not pad, duplicate or silently drop rows.

## Design principles

1. **Determinism** - fixed seed/config produce identical core data and metrics.
2. **Ground-truth isolation** - labels never enter detector input; the detector selects observed
   columns explicitly.
3. **Separation of units** - event and point evaluations are separate and never averaged.
4. **Evidence over suppression** - alarms are recorded even when evaluation calls them false; the
   method is fixed before tuning.
5. **Transparent thresholds** - every rule, unit, persistence and attribution is documented and
   configurable.
6. **Executable claims** - validation and SQL expectations run against generated artifacts.

## Modules

| Module | Responsibility |
|---|---|
| `config.py` | Dataclasses for simulation, scale, scenarios, detection, evaluation; path-independent hash |
| `id_generator.py` | Deterministic entity/alarm/scenario/event IDs |
| `generator.py` | Facilities, pumps, tanks, valves, pipes, sensors, operating modes and topology |
| `simulation.py` | Pump curves, mass-consistent tanks, hydrostatic pressure, flows, modes and sensor noise |
| `scenarios.py` | Scenario sets, anomaly injection, explicit NORMAL complements, ground truth |
| `detection.py` | Rule engine, episode tracker, persistence/hysteresis, modes, uncertainty/attribution |
| `evaluation.py` | Incidents, one-to-one matching, event/point metrics, labels and policies |
| `state_history.py` | Append-only equipment initialization/scenario state transitions and validators |
| `validation.py` | 87 executable checks: keys, FKs, topology, physics, isolation, alarms, evaluation, DB |
| `persistence.py` | SQLite create/insert/query/integrity helpers |
| `exports.py` | Deterministic per-table JSON and portable SQL schema/seed exports |
| `schema.py` | 2.0.0 DDL, constraints, indexes, populated state history |
| `cli.py` | `generate`, `simulate`, `detect`, `evaluate`, `validate`, `export-sql`, `export-json`, `export-sql-script`, `run-sql`, `pipeline` |

## Data model

Master data: facilities, pumps, tanks, valves, pipes, sensors, operating modes. A pump has 2
sensors (discharge flow/pressure), a tank has 4 (level, pressure, inlet flow, outlet flow), and a
valve has 1 through-flow sensor. Full scale is 3 facilities, 20 pumps, 30 tanks, 60 valves and
220 sensors; starter scale is 1/3/5/10 and 36 sensors.

Observed telemetry is separate from scenario definitions, ground truth, alarms, alarm history,
equipment state history, incidents, evaluation and validation. `physical_state_value` is persisted
for physics validation but is not a detector input. Alarm rows carry no `scenario_id`.
`equipment_state_events` is append-only: 333 initialization events (3 facilities + 20 pumps + 30
tanks + 60 valves + 220 sensors) plus two transitions per injected scenario. In the exact 100k
baseline, 4 scenarios add 8 events, giving 341 rows. No placeholder rows are inserted.

## Physical model

### Pump

```
H(Q) = max(0, H_shutoff - k Q^2)
H_shutoff = 1.20 * H_nominal
k = (H_shutoff - H_nominal) / Q_nominal^2
P = H * 0.0981 bar
```

Normal pump flow is 92% of nominal with slow sinusoidal and AR(1) variation. Blockage scales flow
down and pressure up relative to the curve; degradation scales flow and head down.

### Tank

```
V = capacity * level/100
dV/dt = Q_in - Q_out
P = level/100 * height * 0.0981 bar
```

Inlet flow has a slow variation; outflow uses a proportional level controller. This makes level,
pressure and both flows mutually consistent in normal operation. A leak subtracts volume over time
and lowers hydrostatic pressure consistently; a flow-sensor fault changes only that measurement.

### Modes

STARTUP and SHUTDOWN ramps are explicit operating modes with `OPM-*` IDs. Process rules suppress
these modes, so ramp behaviour does not become false process alarms.

## Scenario architecture

Each `ScenarioPlan` defines issue type, equipment kind/index, time, severity, expected category,
sensor role/fault type and parameters. Injection modifies physical and measured values (leaks,
pump effects, sensor bias/drift/stuck) or removes rows (missing). It records scenario and ground
truth rows separately. NORMAL windows cover the remaining time and are split into chunks.

Scenario sets:

| Set | Duration | Purpose |
|---|---:|---|
| default | 24 h | Demonstration |
| calibration | 24 h | Exercise mechanisms/severities, including all sensor faults |
| evaluation | 24 h | Independent report set, light/medium/severe |
| baseline | 7.583 h | Exact 100,000 rows; 120 x 455 + 100 x 454; omits row-removing missing fault |
| compact | 7.5 h | Historical demonstration: 220 x 450 = 99,000 rows |

For target runs the CLI derives the duration from `ceil(target/220)` cadence steps; `--duration`
cannot override the target. For the historical full run no target is set, so the duration remains
24 h and the row count remains 316,800.

## Detection architecture

The engine builds one tracker per rule/equipment/sensor. Trackers require persistence, apply
hysteresis, suppress process rules in non-NORMAL modes, hold through short gaps, and write
CREATED/RESOLVED history. Rules cover level bounds/decline, stuck/quality/range/missing sensors,
pump low flow/curve, tank flow balance (with corroboration or UNCERTAIN), and level/pressure
redundancy. See `detection_methodology.md`.

## Evaluation architecture

Alarm episodes merge into equipment-level incidents. One-to-one category/equipment/sensor/latency
matching assigns incidents to positive events. Unmatched incidents become FALSE_ALARM only when
they overlap labelled windows; otherwise UNKNOWN. Point labels use explicit NORMAL/anomaly windows,
exclude unknown and unobserved samples, and score predictions from the actual episode interval. See
`evaluation_methodology.md`.

## Persistence and reporting

SQLite export recreates the 19-table schema and writes 18 populated tables: 7 master tables,
simulation runs, equipment state events, scenarios, telemetry, ground truth, alarms, alarm events,
incidents, evaluation metrics/events and validation results. The legacy `detection_results` table is
the only empty table. `export-sql --append` is available but not used by the pipeline.

`export-json` reads the CSV artifacts and writes one deterministic JSON array per table plus a
manifest with row counts and SHA-256 hashes. The manifest stores a relative `source_root`, never an
absolute local path. `export-sql-script` writes a portable DDL + INSERT script; executing it in a
new SQLite database reproduces the CSV identifiers and values. The 100k artifacts are large (about
32 MB JSON and 30 MB SQL), so they are generated on demand outside Git.

`run_manifest.json` records SHA-256 hashes and row counts; `validation_results.csv`,
`validation_summary.json`, `evaluation_metrics.csv` and the SQL report may contain wall-clock
timestamps and are excluded from byte-for-byte reproducibility comparisons. In the 100k
reproducibility check, 20/23 compared files were byte-identical and the remaining three were
logically identical after removing `evaluated_at` / `validated_at` fields.

## Verification layers

1. Unit tests for IDs, generation, physics, detection, evaluation and scenarios.
2. Integration tests for the CLI pipeline, artifacts and reproducibility.
3. Data-integrity tests for counts, keys, cadence, labels and SQLite.
4. Validation checks against actual files, including physics, isolation and evaluation formulas.
5. SQL analytics with declared `expect=nonempty` / `expect=zero_rows` assertions.
6. Independent reruns compared on deterministic CSVs, JSON metrics, incidents and manifests.

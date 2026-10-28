# YottaFlex Data Dictionary

Schema/application version: **2.0.0** (the remediation remains compatible with the
existing 2.0 CSV/SQLite contract and adds the previously empty equipment-state
history as a populated append-only table).

This dictionary covers the ten core entities, the explicit state-history table,
the scenario/ground-truth separation, alarm history, and evaluation/validation
outputs. CSV and SQLite use the same logical field names and units. SQLite
column types are shown as `TEXT`, `REAL` or `INTEGER`; CSV values are text
representations of those values.

## Conventions

- **Required** means the value must not be null in the generated/exported data.
  Where SQLite has no `NOT NULL` constraint, the application validation still
  enforces the requirement and this is stated explicitly.
- **PK** = primary key; **FK** = foreign key or a validated polymorphic
  reference. `-` means not a key.
- Timestamps are ISO 8601 strings. Generated samples use
  `YYYY-MM-DDTHH:MM:SS` in the configured simulation timezone (no implicit
  timezone conversion).
- All time windows are half-open: `[start_time, end_time)`.
- Unless noted, no SQL `DEFAULT` is declared. The generator supplies the value;
  an empty/default value is therefore an application-level default, not a
  database default.
- Deletion is not part of the pipeline contract. Foreign keys are restrictive
  (SQLite `FOREIGN KEY` without `ON DELETE`); the database is rebuilt from
  artifacts by `yottaflex export-sql` rather than patched in place.
- Identifier formats are stable generator conventions. They are not a
  substitute for referential checks; all references are validated.

## 1. Facility (`facilities`)

A physical site. One facility owns many pumps, tanks, valves, pipes and sensors.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| facility_id | TEXT | Yes | PK | `FAC-###` | - | Yes | generated | Primary key; parent of all facility-scoped rows. |
| facility_name | TEXT | Yes | - | non-empty string | - | No | generated | Must be non-empty. Display/business name. |
| location_code | TEXT | Yes | - | non-empty string, e.g. `NR-01` | - | No | generated | Must be non-empty; not used as a key. |
| lifecycle_state | TEXT | Yes | - | `ACTIVE`, `INACTIVE`, `MAINTENANCE` | - | No | `ACTIVE` (generator) | SQL `CHECK`; current lifecycle state. State transitions are recorded in `equipment_state_events`; history is not overwritten. |
| created_at | TEXT | Yes | - | ISO 8601 timestamp | - | No | `2026-01-01T00:00:00` (generator) | Must parse as a timestamp; asset creation time, not the run start time. |

**Cardinality:** 1 facility → 0..N pumps, tanks, valves, pipes, sensors.
**Lifecycle:** `ACTIVE` is the generated baseline; `INACTIVE` and `MAINTENANCE`
are allowed SQL states. No facility is deleted by the generator.

## 2. Pump (`pumps`)

A rotating flow source with a nominal operating point. Each pump has exactly two
generated sensors: discharge flow and discharge pressure.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| pump_id | TEXT | Yes | PK | `PUMP-###` | - | Yes | generated | Primary key; referenced by sensors and pipes through `NODE-<pump_id>`. |
| facility_id | TEXT | Yes | FK → facilities.facility_id | existing facility ID | - | No | generated | Required FK; must resolve to a facility. |
| pump_name | TEXT | Yes | - | non-empty string | - | No | generated | Display name; must be non-empty. |
| nominal_flow_m3_h | REAL | Yes | - | > 0 | m3/h | No | generated | Positive finite number; used by the pump curve and detectors. |
| nominal_head_m | REAL | Yes | - | > 0 | m | No | generated | Positive finite number; head is converted to pressure. |
| rated_power_kw | REAL | Yes | - | > 0 | kW | No | generated | Positive finite number; engineering reference value. |
| efficiency_pct | REAL | Yes | - | 0 < value ≤ 100 | % | No | generated | Percentage; the generator uses roughly 65–85%. |
| lifecycle_state | TEXT | Yes | - | `ACTIVE`, `INACTIVE`, `MAINTENANCE` | - | No | `ACTIVE` | SQL `CHECK`; current state only. Use `equipment_state_events` for history. |

**Cardinality:** 1 pump → exactly 2 generated sensors (FLOW/discharge and
PRESSURE/discharge); 1 pump → 0..N pipe endpoints through its node ID.
**Lifecycle:** process state can transition to `DEGRADED` in a scenario; the
state history records `ACTIVE → DEGRADED → ACTIVE`. The lifecycle column is not
rewritten when a scenario is injected.

## 3. Tank (`tanks`)

A storage volume. Each tank has four generated sensors: level, hydrostatic
pressure, inlet flow and outlet flow.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| tank_id | TEXT | Yes | PK | `TANK-###` | - | Yes | generated | Primary key; referenced by sensors and pipes through `NODE-<tank_id>`. |
| facility_id | TEXT | Yes | FK → facilities.facility_id | existing facility ID | - | No | generated | Required FK. |
| tank_name | TEXT | Yes | - | non-empty string | - | No | generated | Display name. |
| capacity_m3 | REAL | Yes | - | > 0 | m3 | No | generated | SQL `CHECK(capacity_m3 > 0)`; used for mass balance and leak injection. |
| height_m | REAL | Yes | - | > 0 | m | No | generated | SQL `CHECK(height_m > 0)`; hydrostatic pressure = level fraction × height. |
| initial_level_pct | REAL | Yes | - | 0 ≤ value ≤ 100 | % | No | generated | SQL `CHECK`; initial condition only, not a historical level. |
| lifecycle_state | TEXT | Yes | - | `ACTIVE`, `INACTIVE`, `MAINTENANCE` | - | No | `ACTIVE` | SQL `CHECK`; current lifecycle state. |

**Cardinality:** 1 tank → exactly 4 generated sensors; 1 tank → 0..N pipe
endpoints through its node ID.
**Lifecycle:** leak scenarios use the process state `LEAKING` in
`equipment_state_events`; recovery returns to `ACTIVE`. The tank's
`tank_levels` runtime value is not persisted as master data.

## 4. Valve (`valves`)

A flow-control asset. Each valve has one generated through-flow sensor.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| valve_id | TEXT | Yes | PK | `VALVE-###` | - | Yes | generated | Primary key; referenced by sensors and pipe nodes. |
| facility_id | TEXT | Yes | FK → facilities.facility_id | existing facility ID | - | No | generated | Required FK. |
| valve_name | TEXT | Yes | - | non-empty string | - | No | generated | Display name. |
| valve_type | TEXT | Yes | - | `BALL`, `GATE`, `GLOBE`, `BUTTERFLY`, `CHECK` | - | No | generated | SQL `CHECK`; `CHECK` is in the schema vocabulary even though the generator currently samples the first four. |
| initial_state | TEXT | Yes | - | `OPEN`, `CLOSED`, `PARTIAL` | - | No | generated | SQL `CHECK`; initial process position. |
| opening_pct | REAL | Yes | - | 0 ≤ value ≤ 100 | % | No | generated | SQL `CHECK`; OPEN is roughly 90–100, CLOSED 0–5, PARTIAL 20–80. |
| lifecycle_state | TEXT | Yes | - | `ACTIVE`, `INACTIVE`, `MAINTENANCE` | - | No | `ACTIVE` | SQL `CHECK`; current lifecycle state. |

**Cardinality:** 1 valve → exactly 1 generated FLOW/through sensor; 1 valve →
0..N pipe endpoints through its node ID.
**Lifecycle:** valve state history uses the process-position vocabulary
`OPEN/CLOSED/PARTIAL`, initialized from `initial_state`; the lifecycle column
remains separate.

## 5. Pipe (`pipes`)

A hydraulic connection between two equipment nodes.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| pipe_id | TEXT | Yes | PK | `PIPE-###` | - | Yes | generated | Primary key. |
| facility_id | TEXT | Yes | FK → facilities.facility_id | existing facility ID | - | No | generated | Required FK; both endpoints must belong to the same facility in valid data. |
| source_node_id | TEXT | Yes | validated node reference | `NODE-<equipment_id>` | - | No | generated | Must resolve to a generated pump/tank/valve node; self-loops rejected. |
| target_node_id | TEXT | Yes | validated node reference | `NODE-<equipment_id>` | - | No | generated | Must resolve to a generated pump/tank/valve node; must differ from source. |
| length_m | REAL | Yes | - | > 0 | m | No | generated | SQL `CHECK(length_m > 0)`. |
| diameter_mm | REAL | Yes | - | > 0 | mm | No | generated | SQL `CHECK(diameter_mm > 0)`. |
| roughness_factor | REAL | Yes | - | > 0 | dimensionless relative roughness | No | generated | Positive finite number; engineering reference, not used for a pressure-drop solver. |
| lifecycle_state | TEXT | Yes | - | `ACTIVE`, `INACTIVE`, `MAINTENANCE` | - | No | `ACTIVE` | SQL `CHECK`; current lifecycle state. |

**Cardinality:** a pipe has exactly two endpoint references; an equipment node
may be the endpoint of many pipes. Pipe endpoints are polymorphic references to
the node registry, so SQLite cannot declare a single-column FK; the
`PIPE-ENDPOINTS` validation and `validate_topology()` enforce them.
**Lifecycle:** pipes are static in the current scenario set; no pipe state
events are generated.

## 6. Sensor (`sensors`)

A measurement point attached to equipment. The generated composition is
2 sensors per pump, 4 per tank and 1 per valve.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| sensor_id | TEXT | Yes | PK | `SNS-###` | - | Yes | generated | Primary key; referenced by telemetry and sensor-fault scenarios. |
| facility_id | TEXT | Yes | FK → facilities.facility_id | existing facility ID | - | No | generated | Required FK; must match the attached equipment's facility. |
| equipment_id | TEXT | No (schema), Yes (generated) | validated reference | PUMP/TANK/VALVE/PIPE/JUNCTION ID | - | No | generated | Must resolve to known equipment; the generated rows always attach to a pump/tank/valve. A polymorphic reference is validated in code. |
| equipment_type | TEXT | No (schema), Yes (generated) | - | `PUMP`, `TANK`, `VALVE`, `PIPE`, `JUNCTION` | - | No | generated | SQL `CHECK`; must match `equipment_id` and the facility. |
| sensor_type | TEXT | Yes | - | `FLOW`, `PRESSURE`, `LEVEL`, `TEMPERATURE` | - | No | generated | SQL `CHECK`; determines the unit. |
| sensor_role | TEXT | Yes | - | `discharge`, `level`, `pressure`, `inlet`, `outlet`, `through` | - | No | generated | Must be the documented role for the equipment/type pair. |
| measurement_unit | TEXT | Yes | - | `m3/h` for FLOW, `bar` for PRESSURE, `%` for LEVEL, `C` for TEMPERATURE | unit | No | generated | Must match `sensor_type`; telemetry copies this value. |
| sampling_interval_seconds | INTEGER | Yes | - | > 0; generated 60 | s | No | generated from config | Positive integer; must match the run cadence. |
| accuracy_tolerance | REAL | Yes | - | > 0 | % of reading | No | generated | Positive percentage; noise is a fraction of this value. |
| lifecycle_state | TEXT | Yes | - | `ACTIVE`, `INACTIVE`, `MAINTENANCE` | - | No | `ACTIVE` | SQL `CHECK`; current lifecycle state. |

**Cardinality:** 1 equipment item → 0..N sensors; 1 sensor → 0..N telemetry
samples (normally exactly one per allocated timestamp); 1 sensor → 0..N
scenario/ground-truth references.
**Required composition:** pump = FLOW/discharge + PRESSURE/discharge; tank =
LEVEL/level + PRESSURE/pressure + FLOW/inlet + FLOW/outlet; valve =
FLOW/through.
**Lifecycle:** sensor faults use the separate `FAULTY` state in
`equipment_state_events`; the `sensors.lifecycle_state` master value remains
`ACTIVE`.

## 7. Telemetry (`telemetry`)

Observed time-series samples. This is the detector input table. It deliberately
contains no scenario, ground-truth or expected-label columns.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| telemetry_id | TEXT | Yes | PK | `TEL-############` | - | Yes | generated | Primary key; unique within a run/export. |
| sensor_id | TEXT | Yes | FK → sensors.sensor_id | existing sensor ID | - | No | generated | Required FK; every sample has a real sensor. |
| simulation_run_id | TEXT | Yes | FK → simulation_runs.simulation_run_id | existing run ID | - | No | generated | Required FK; all samples in a run share it. |
| timestamp | TEXT | Yes | - | ISO 8601 cadence timestamp | - | No | generated | Must lie on the configured cadence and start at the run start. `(sensor_id,timestamp)` is unique. |
| measured_value | REAL | Yes | - | finite number | sensor-dependent | No | generated | Must be finite; no null observed value is exported. Detector uses this field only. |
| measurement_unit | TEXT | Yes | - | same vocabulary as sensors | unit | No | copied | Must equal the sensor's `measurement_unit`. |
| quality_status | TEXT | Yes | - | `GOOD`, `UNCERTAIN`, `BAD`, `MISSING` | - | No | `GOOD` | SQL `CHECK`; missing samples are represented by absent rows, not by a `MISSING` row in the generator. |
| operating_mode_id | TEXT | No | FK → operating_modes.operating_mode_id | existing mode ID | - | No | generated | Required in generated data; SQLite allows null for compatibility. |
| physical_state_value | REAL | No | - | finite number | sensor-dependent | No | generated | Simulator internal value for validation/physics checks. **Explicitly excluded from detector input**; not a label. |

**Cardinality:** 1 sensor → many telemetry rows; 1 run → many telemetry rows;
1 operating mode → many telemetry rows.
**Cadence and budget:** the historical full run is `220 sensors × 1,440 = 316,800`
rows. The exact baseline target is `100,000` rows. Because 100,000 is not
divisible by 220, the generator allocates 455 samples to the first 120 sensor IDs
(lexicographic) and 454 to the remaining 100: `120×455 + 100×454 = 100,000`.
Every row is a real `(sensor, timestamp)` sample; there is no padding, duplicate
or removed full-run row. See `docs/assumptions.md` and the README.
**Lifecycle:** telemetry is append-only for a run and is not updated by
detection/evaluation. Deletion of a parent sensor/run is restricted by FKs.

## 8. Operating Mode (`operating_modes`)

A mode that explains expected process behavior and suppresses process rules
during startup/shutdown/maintenance.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| operating_mode_id | TEXT | Yes | PK | `OPM-###` | - | Yes | generated | Primary key; referenced by telemetry. |
| mode_name | TEXT | Yes | - | `NORMAL`, `STARTUP`, `SHUTDOWN`, `MAINTENANCE` | - | Yes | generated | SQL `UNIQUE`; detector uses these names for suppression. |
| description | TEXT | Yes | - | non-empty string | - | No | generated | Human-readable purpose. |
| permitted_configuration | TEXT | No | - | non-empty configuration code | - | No | generated | e.g. `ALL_EQUIPMENT_ACTIVE`; reference text, not a FK. |
| effective_from | TEXT | Yes | - | ISO 8601 timestamp | - | No | generated | Must parse; mode definition effective start. |
| effective_to | TEXT | No | - | ISO 8601 timestamp or null | - | No | null | If present must be ≥ `effective_from`; no generated expiry. |
| lifecycle_state | TEXT | Yes | - | `ACTIVE`, `INACTIVE` | - | No | `ACTIVE` | SQL `CHECK`; mode definition status, not the run's current mode. |

**Cardinality:** 1 mode → many telemetry samples. A sample has exactly one
mode; a mode has zero or many samples.
**Lifecycle:** effective dates define when the mode definition applies; telemetry
stores the mode selected for each sample. The run's `STARTUP`/`SHUTDOWN` ramps
are not process faults.

## 9. Alarm (`alarms`)

One row per active alarm episode, produced from observed telemetry only. An
episode is grouped by rule/equipment/sensor with persistence and hysteresis.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| alarm_id | TEXT | Yes | PK | `ALARM-######` | - | Yes | generated | Primary key; referenced by `alarm_events`. |
| simulation_run_id | TEXT | Yes | FK → simulation_runs.simulation_run_id | existing run ID | - | No | generated | Required FK. |
| equipment_id | TEXT | No | validated reference | pump/tank/valve/facility ID | - | No | derived | Attribution equipment; alarms on a sensor still identify its parent equipment where available. |
| sensor_id | TEXT | No | FK → sensors.sensor_id | existing sensor ID | - | No | derived | Triggering sensor; null for equipment-only rules. |
| alarm_type | TEXT | Yes | - | human-readable rule name | - | No | derived | Non-empty; describes the diagnostic. |
| alarm_category | TEXT | Yes | - | `PROCESS_FAULT`, `SENSOR_FAULT`, `UNCERTAIN` | - | No | derived | SQL `CHECK`; sensor-quality evidence must not silently become a process-fault label. |
| severity | TEXT | Yes | - | `INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` | - | No | derived | SQL `CHECK`; ordered severity. |
| first_detected_at | TEXT | Yes | - | ISO 8601 | - | No | derived | Must be ≤ `last_detected_at`; first active sample in the episode. |
| last_detected_at | TEXT | Yes | - | ISO 8601 | - | No | derived | Last active sample; history is append-only. |
| evidence_summary | TEXT | Yes | - | non-empty explanatory text | - | No | derived | Threshold/peak/attribution evidence; no ground-truth ID. |
| rule_id | TEXT | Yes | - | `RULE-001` … `RULE-010` | - | No | derived | Stable detector rule identifier. |
| alarm_status | TEXT | Yes | - | `ACTIVE`, `ACKNOWLEDGED`, `RESOLVED`, `FALSE_ALARM` | - | No | derived | SQL `CHECK`; current episode status. Lifecycle events are in `alarm_events`. |
| occurrence_count | INTEGER | Yes | - | ≥ 1 | samples | No | derived | Number of active observations in the episode. |
| peak_value | REAL | No | - | finite number | rule-dependent | No | derived | Extreme observed value; unit follows the rule. |
| peak_at | TEXT | No | - | ISO 8601 | - | No | derived | Timestamp of `peak_value`. |
| attribution | TEXT | No | - | evidence class, e.g. `OBSERVED_LEVEL` | - | No | derived | Explains which observation supported the diagnosis. |
| operating_mode | TEXT | No | - | `NORMAL`, `STARTUP`, `SHUTDOWN`, `MAINTENANCE` | - | No | derived | Mode at episode activation. |
| scenario_id | — | — | — | — | — | — | — | **Deliberately absent**; alarms cannot carry ground-truth labels. |

**Cardinality:** 1 alarm → 1..N `alarm_events`; 1 run → many alarms; 1 incident
(in `alarm_incidents`) groups one or more alarms for event evaluation.
**Lifecycle:** `CREATED` and `RESOLVED` events are append-only; a resolved
episode is not deleted or overwritten.

## 10. SimulationRun (`simulation_runs`)

Traceability record for one deterministic simulation invocation.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| simulation_run_id | TEXT | Yes | PK | `SIM-2026-######` | - | Yes | generated | Primary key; parent of telemetry, scenarios, truth, alarms and state history. |
| configuration_hash | TEXT | Yes | - | 16 lowercase hex characters | - | No | computed | SHA-256 of path-independent config; must equal saved config hash. |
| random_seed | INTEGER | Yes | - | integer; default `20261022` | - | No | `20261022` | Deterministic seed recorded for regeneration. |
| generator_version | TEXT | Yes | - | semantic version, currently `2.0.0` | - | No | package version | Must match package at validation time. |
| schema_version | TEXT | Yes | - | semantic version, currently `2.0.0` | - | No | package version | Must match SQLite schema. |
| scenario_set | TEXT | Yes | - | `default`, `calibration`, `evaluation`, `compact`, `baseline` | - | No | `default` | Must have a defined scenario matrix; `baseline` is used for the exact 100k budget. |
| sampling_interval_seconds | INTEGER | Yes | - | > 0; generated 60 | s | No | config | Must match telemetry cadence and sensor metadata. |
| start_time | TEXT | Yes | - | ISO 8601 | - | No | config | Run start; telemetry begins here. |
| end_time | TEXT | Yes | - | ISO 8601 | - | No | start + duration | Must be ≥ start; scenario windows are bounded by it. |
| status | TEXT | Yes | - | `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED` | - | No | `COMPLETED` | SQL `CHECK`; validation requires `COMPLETED` for a finished artifact. |
| input_manifest | TEXT (JSON) | No | - | object with master-data SHA-256 map | - | No | computed | Must contain hashes for all master CSVs; validated against files. |
| assumptions | TEXT (JSON) | No | - | object | - | No | configured | Physics model, head conversion and scenario set. |
| outcome_summary | TEXT (JSON) | No | - | object | - | No | computed | Telemetry rows, sensor/steps count, state-event rows and exact target; must agree with artifacts. |
| created_at | TEXT | Yes | - | ISO 8601 | - | No | run start | Deterministic run start for reproducible core outputs. |

**Cardinality:** 1 run → many telemetry, scenario, ground-truth, alarm and
state-event rows. A run has exactly one configuration hash.
**Lifecycle:** created `COMPLETED` by the pipeline. A failed run is not exported
as a completed baseline.

## Equipment state history (`equipment_state_events`)

This table is **populated and exported** after the remediation. It is an
append-only lifecycle history, not a detector input. Rows are generated only for
real transitions: master-data initialization and scenario start/recovery. No
placeholder row is inserted merely to make the table non-empty.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| event_id | TEXT | Yes | PK | `ESE-######` | - | Yes | generated | Primary key. |
| equipment_id | TEXT | Yes | validated reference | facility/pump/tank/valve/sensor ID | - | No | generated | Must resolve to the entity named by `equipment_type`. |
| equipment_type | TEXT | Yes | - | `FACILITY`, `PUMP`, `TANK`, `VALVE`, `SENSOR` | - | No | generated | SQL `CHECK`; selects the state vocabulary. |
| simulation_run_id | TEXT | Yes | FK → simulation_runs.simulation_run_id | existing run ID | - | No | generated | Required FK. |
| previous_state | TEXT | Yes | - | state vocabulary for type | - | No | derived | Must be a valid state and form an allowed transition with `new_state`. |
| new_state | TEXT | Yes | - | state vocabulary for type | - | No | derived | Must be a valid state; transition validated. |
| state_value | TEXT | Yes | - | same as `new_state` | - | No | derived | Compatibility column; equals `new_state`. |
| event_timestamp | TEXT | Yes | - | ISO 8601 | - | No | derived | Must lie inside the run window. |
| reason | TEXT | Yes | - | non-empty description | - | No | derived | e.g. initialization or scenario start/recovery. |
| source | TEXT | Yes | - | `SIMULATION`, `SCENARIO`, `OPERATOR`, `SYSTEM` | - | No | derived | SQL `CHECK`; source of the transition. |
| source_reference | TEXT | No | - | run ID or scenario ID | - | No | derived | Resolves to the run or a scenario definition. |
| event_data | TEXT (JSON) | No | - | object | - | No | derived | Event kind, master table or scenario metadata. |

**State vocabularies and allowed transitions**

| Type | States | Allowed transitions (previous → new) |
|---|---|---|
| FACILITY | UNKNOWN, ACTIVE, INACTIVE, MAINTENANCE | UNKNOWN→ACTIVE; ACTIVE↔INACTIVE; ACTIVE↔MAINTENANCE |
| PUMP | UNKNOWN, ACTIVE, DEGRADED, INACTIVE, MAINTENANCE | UNKNOWN→ACTIVE; ACTIVE↔DEGRADED; ACTIVE↔MAINTENANCE; ACTIVE↔INACTIVE |
| TANK | UNKNOWN, ACTIVE, LEAKING, INACTIVE, MAINTENANCE | UNKNOWN→ACTIVE; ACTIVE↔LEAKING; ACTIVE↔MAINTENANCE; ACTIVE↔INACTIVE |
| VALVE | UNKNOWN, OPEN, CLOSED, PARTIAL | UNKNOWN→OPEN/CLOSED/PARTIAL; OPEN/CLOSED/PARTIAL pair transitions |
| SENSOR | UNKNOWN, ACTIVE, FAULTY, INACTIVE, MAINTENANCE | UNKNOWN→ACTIVE; ACTIVE↔FAULTY; ACTIVE↔MAINTENANCE; ACTIVE↔INACTIVE |

The canonical implementation is `src/yottaflex/state_history.py`; the regression
tests are `tests/test_submission_artifacts.py::test_equipment_state_history_is_append_only_and_valid`
and `::test_invalid_state_transition_is_rejected`. The history is separate from
telemetry, so a detector cannot read these labels.

## Scenario definitions (`scenario_definitions`)

Controlled injection instructions. They are not detector inputs.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| scenario_id | TEXT | Yes | PK | `SCN-######` | - | Yes | generated | One-to-one with a ground-truth row. |
| simulation_run_id | TEXT | Yes | FK → runs | existing run ID | - | No | generated | Parent run. |
| issue_type | TEXT | Yes | - | `NORMAL`, `LEAK`, `BLOCKAGE`, `PUMP_DEGRADATION`, `SENSOR_FAULT` | - | No | generated | SQL `CHECK`; controlled vocabulary. |
| severity | TEXT | Yes | - | `light`, `medium`, `severe`, `normal` | - | No | generated | Severity label, not a detector threshold. |
| affected_equipment_id | TEXT | No | validated reference | equipment ID | - | No | generated | Required for process faults; points to the affected asset. |
| affected_sensor_id | TEXT | No | validated reference | sensor ID | - | No | generated | Required for sensor-fault scenarios; resolves to `sensors`. |
| expected_sensor_ids | TEXT (JSON list) | No | - | JSON array of sensor IDs | - | No | generated | The observable point-label sensor(s), not an alarm input. |
| start_time | TEXT | Yes | - | ISO 8601 | - | No | generated | Half-open window start; inside run. |
| end_time | TEXT | Yes | - | ISO 8601 | - | No | generated | Must be > start and ≤ run end. |
| injection_parameters | TEXT (JSON) | No | - | object with severity/physical parameters | - | No | generated | Documents the injection; not read by the detector. |
| expected_observable | TEXT | No | - | non-empty text | - | No | generated | Human-readable expected symptom. |

## Ground truth (`ground_truth`)

Explicit labels, including explicit NORMAL windows covering the complement of
anomaly windows. No telemetry row carries these labels.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| gt_id | TEXT | Yes | PK | `GT-######` | - | Yes | generated | One-to-one with a scenario. |
| simulation_run_id | TEXT | Yes | FK → runs | existing run ID | - | No | generated | Parent run. |
| scenario_id | TEXT | Yes | FK → scenario_definitions | existing scenario ID | - | Yes | generated | Exactly one GT row per scenario. |
| issue_type | TEXT | Yes | - | same vocabulary as scenarios | - | No | copied | Must agree with scenario. |
| severity | TEXT | Yes | - | `light`, `medium`, `severe`, `normal` | - | No | copied | Must agree with scenario. |
| affected_equipment_id | TEXT | No | validated reference | equipment ID | - | No | copied | Process-fault attribution. |
| affected_sensor_id | TEXT | No | validated reference | sensor ID | - | No | copied | Sensor-fault attribution. |
| expected_sensor_ids | TEXT (JSON list) | No | - | JSON array | - | No | copied | Point-label sensors. |
| start_time | TEXT | Yes | - | ISO 8601 | - | No | generated | Half-open label start. |
| end_time | TEXT | Yes | - | ISO 8601 | - | No | generated | Half-open label end. |
| expected_detection | TEXT | Yes | - | `YES`, `NO` | - | No | generated | SQL `CHECK`; `NO` for NORMAL. |
| expected_alarm_category | TEXT | No | - | `PROCESS_FAULT`, `SENSOR_FAULT`, `NORMAL` | - | No | generated | Must agree with scenario. |
| injection_parameters | TEXT (JSON) | No | - | object | - | No | copied | Audit of the injection. |

**Cardinality:** scenario 1:1 ground truth; run 1:N both. The one-to-one is
enforced by `SCENARIO-GROUND-TRUTH-ONE-TO-ONE` and the `scenario_id` uniqueness
check, not only by a database unique constraint.

## Alarm history (`alarm_events`)

Append-only episode lifecycle. `CREATED` is emitted once per alarm; `RESOLVED`
is emitted once when the episode closes. The table is retained even if the
alarm status changes.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| event_id | TEXT | Yes | PK | `EVT-############` | - | Yes | generated | Primary key. |
| alarm_id | TEXT | Yes | FK → alarms | existing alarm ID | - | No | generated | Parent episode. |
| simulation_run_id | TEXT | Yes | FK → runs | existing run ID | - | No | generated | Parent run. |
| event_type | TEXT | Yes | - | `CREATED`, `UPDATED`, `ACKNOWLEDGED`, `RESOLVED`, `ESCALATED` | - | No | generated | SQL `CHECK`; current pipeline emits CREATED/RESOLVED. |
| event_timestamp | TEXT | Yes | - | ISO 8601 | - | No | generated | Event time; must be ordered per alarm. |
| event_data | TEXT (JSON) | No | - | object | - | No | generated | Rule/category/mode or resolution detail. |

## Alarm incidents (`alarm_incidents`)

Evaluation grouping of overlapping alarm episodes on one equipment. This is an
evaluation unit, not a normalized many-to-many bridge table.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| incident_id | TEXT | Yes | PK | `INC-######` | - | Yes | generated | Primary key. |
| simulation_run_id | TEXT | Yes | FK → runs | existing run ID | - | No | generated | Parent run. |
| equipment_id | TEXT | No | validated reference | equipment ID | - | No | derived | Shared equipment of merged alarms. |
| sensor_ids | TEXT (JSON list) | No | - | JSON array | - | No | derived | Member sensor IDs. |
| categories | TEXT (JSON list) | No | - | JSON array | - | No | derived | Member alarm categories. |
| rules | TEXT (JSON list) | No | - | JSON array | - | No | derived | Member rule IDs. |
| severity_max | TEXT | No | - | alarm severity vocabulary | - | No | derived | Highest member severity. |
| first_detected_at | TEXT | Yes | - | ISO 8601 | - | No | derived | Earliest member onset. |
| last_detected_at | TEXT | Yes | - | ISO 8601 | - | No | derived | Latest member end. |
| alarm_count | INTEGER | Yes | - | ≥ 1 | episodes | No | derived | Number of merged episodes. |
| alarm_ids | TEXT (JSON list) | Yes | - | JSON array of alarm IDs | - | No | derived | Denormalized membership list; no bridge table is needed for the ephemeral evaluation grouping. |
| matched_gt_id | TEXT | No | validated reference | GT ID | - | No | derived | Matched event, if any. |
| classification | TEXT | Yes | - | `MATCHED`, `FALSE_ALARM`, `UNKNOWN` | - | No | derived | SQL `CHECK`; unknown labels are not treated as negatives. |
| assigned_normal_gt_id | TEXT | No | validated reference | GT ID | - | No | derived | NORMAL window for a false alarm. |
| latency_seconds | REAL | No | - | ≥ 0 | s | No | derived | Onset latency. |

## Evaluation metrics (`evaluation_metrics`)

Long-format metrics with the evaluation unit kept explicit.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| metric_id | TEXT | Yes | PK | `MET-######` | - | Yes | generated | Primary key. |
| simulation_run_id | TEXT | Yes | FK → runs | existing run ID | - | No | generated | Parent run. |
| evaluation_level | TEXT | Yes | - | `EVENT`, `POINT` | - | No | computed | SQL `CHECK`; units are never combined. |
| scope | TEXT | Yes | - | `overall` or breakdown key | - | No | computed | e.g. `by_scenario_type:LEAK`. |
| metric_name | TEXT | Yes | - | e.g. `precision`, `recall`, `f1_score` | - | No | computed | Metric name. |
| metric_value | REAL | No | - | finite number or null | metric-dependent | No | computed | Null when denominator is zero; not silently replaced with 0. |
| denominator | REAL | No | - | ≥ 0 or null | unit-dependent | No | computed | Optional explicit denominator. |
| details | TEXT | No | - | text | - | No | computed | Policy/diagnostic note. |
| evaluated_at | TEXT | Yes | - | ISO 8601 | - | No | wall clock | Excluded from deterministic content comparisons. |

## Evaluation events (`evaluation_events`)

One row per ground-truth event with its matched/missed outcome.

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| evaluation_event_id | TEXT | Yes | PK | `EVAL-EVT-######` | - | Yes | generated | Primary key. |
| simulation_run_id | TEXT | Yes | FK → runs | existing run ID | - | No | generated | Parent run. |
| gt_id | TEXT | Yes | validated reference | GT ID | - | Yes | derived | One row per ground-truth event. |
| issue_type | TEXT | Yes | - | scenario vocabulary | - | No | derived | Event type. |
| severity | TEXT | Yes | - | severity vocabulary | - | No | derived | Event severity. |
| affected_equipment_id | TEXT | No | - | equipment ID | - | No | derived | Attribution. |
| expected_sensors | TEXT (JSON) | No | - | JSON array | - | No | derived | Point-label sensors. |
| expected_alarm_category | TEXT | No | - | category vocabulary | - | No | derived | Expected category. |
| start_time / end_time | TEXT | No | - | ISO 8601 | - | No | derived | Event window. |
| is_positive / is_normal | INTEGER | Yes | - | 0/1 | - | No | derived | Window role; mutually exclusive. |
| matched | INTEGER | Yes | - | 0/1 | - | No | derived | Whether an alarm incident matched. |
| matched_incident_id | TEXT | No | - | incident ID | - | No | derived | Matched incident. |
| latency_seconds | REAL | No | - | ≥ 0 | s | No | derived | Detection onset latency. |
| outcome | TEXT | Yes | - | `DETECTED`, `MISSED`, `NORMAL_NO_ALARM`, `NORMAL_ALARMED` | - | No | derived | Per-event result. |

## Validation results (`validation_results`)

| Field | Type | Req | Key | Allowed values / enum | Unit | Unique | Default | Validation and relationship |
|---|---|---|---|---|---|---|---|---|
| validation_id | TEXT | Yes | PK | `VAL-######` | - | Yes | generated | Primary key. |
| simulation_run_id | TEXT | No | FK-like reference | existing run ID | - | No | optional | The validator currently emits run-agnostic checks; null is allowed. |
| validation_type | TEXT | Yes | - | e.g. `PRIMARY_KEY`, `FOREIGN_KEY`, `PHYSICS`, `EVALUATION` | - | No | computed | Check category. |
| test_case_id | TEXT | Yes | - | stable check ID | - | No | computed | Manually inspected stable ID. |
| status | TEXT | Yes | - | `PASS`, `FAIL`, `WARN`, `NOT_IMPLEMENTED` | - | No | computed | SQL `CHECK`; review-level WARNs are documented separately when they are not CSV rows. |
| entity_type / entity_id | TEXT | No | - | entity reference | - | No | computed | What was checked. |
| description | TEXT | Yes | - | non-empty text | - | No | computed | What the check proves. |
| details | TEXT | No | - | text | - | No | computed | Observed values/failure details. |
| validated_at | TEXT | Yes | - | ISO 8601 | - | No | wall clock | Excluded from deterministic comparisons. |

## Legacy detection results (`detection_results`)

Retained for schema compatibility with 1.x. It is **not populated** by the 2.0
pipeline; event/point evaluation is stored in `evaluation_events` and
`evaluation_metrics`. If populated by an old consumer, its `simulation_run_id`
must resolve to `simulation_runs`.

## Relationship and cardinality summary

| Relationship | Cardinality | Enforcement |
|---|---|---|
| Facility → pumps/tanks/valves/pipes/sensors | 1:N | SQL FKs from each child `facility_id`. |
| Pump/Tank/Valve → sensors | 1:N (generated exactly 2/4/1) | Application composition + `SENSOR-COMPOSITION`. |
| Pump/Tank/Valve → pipe endpoints | 1:N via `NODE-<id>` | Polymorphic endpoint validation; no single SQL FK. |
| Sensor → telemetry | 1:N | SQL FK `telemetry.sensor_id`. |
| SimulationRun → telemetry/scenario/truth/alarm/state events | 1:N | SQL FKs. |
| OperatingMode → telemetry | 1:N (optional) | SQL FK. |
| Scenario → ground truth | 1:1 | Unique/scenario-set validation; not only an FK. |
| Alarm → alarm events | 1:N | SQL FK. |
| Incident → alarms | evaluation grouping | JSON `alarm_ids` and `alarm_count`; no bridge table because incidents are recomputed evaluation aggregates, not durable master data. |
| Sensor/asset → expected labels | label list | JSON `expected_sensor_ids`; labels are deliberately outside observed telemetry. |

**Genuine many-to-many relationships:** none in the persisted core model. Alarm
incidents and expected-sensor labels are aggregation/label lists, not master-data
associations. The design intentionally does not add a bridge table where the
relationship is an evaluation artifact rather than a durable entity link.

## History and lifecycle rules

1. Master tables hold the current lifecycle value only; they do not overwrite
   history.
2. `equipment_state_events` is append-only and records initialization plus
   scenario-driven transitions. It is never used as a detector feature.
3. `alarm_events` is append-only. A `CREATED` event is emitted once per episode;
   `RESOLVED` is emitted once at closure.
4. `scenario_definitions` and `ground_truth` are separate from telemetry and
   alarms. The detector receives only observed telemetry columns.
5. NORMAL ground-truth rows are explicit complements of anomaly windows; samples
   outside all labels are UNKNOWN and excluded from point denominators.
6. Deletion/update of parent entities is not part of the pipeline; a new database
   is built from CSV/JSON/SQL exports for reproducibility.

## Export consistency

`yottaflex export-sql` builds SQLite from the CSVs; `yottaflex export-json`
writes deterministic per-table JSON arrays; `yottaflex export-sql-script` writes
a portable DDL + INSERT script. All three are generated from the same CSV
artifacts, so primary keys, foreign keys, labels, units and timestamps must
agree. `SQLITE-ROW-COUNTS`, the manifest hashes, and
`tests/test_submission_artifacts.py` check this consistency.

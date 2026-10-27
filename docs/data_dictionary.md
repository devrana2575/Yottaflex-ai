# Data Dictionary (YottaFlex 2.0.0)

The CSV files and SQLite export share these schemas. `physical_state_value` is persisted for
validation but is explicitly excluded from detector input; scenario/ground-truth/expected-label
columns never appear on the telemetry table.

## facilities
| Field | Type | Required | Key | Allowed values | Description |
|---|---|---|---|---|---|
| facility_id | TEXT | Yes | PK | FAC-XXX | Facility identifier |
| facility_name | TEXT | Yes | - | - | Display name |
| location_code | TEXT | Yes | - | - | Location code |
| lifecycle_state | TEXT | Yes | - | ACTIVE, INACTIVE, MAINTENANCE | Lifecycle |
| created_at | TEXT (ISO8601) | Yes | - | - | Creation timestamp |

## pumps
| Field | Type | Required | Key | Unit | Description |
|---|---|---|---|---|---|
| pump_id | TEXT | Yes | PK | - | Pump identifier |
| facility_id | TEXT | Yes | FK facilities | - | Parent facility |
| pump_name | TEXT | Yes | - | - | Display name |
| nominal_flow_m3_h | REAL | Yes | - | m3/h | Nominal flow |
| nominal_head_m | REAL | Yes | - | m | Nominal head |
| rated_power_kw | REAL | Yes | - | kW | Rated power |
| efficiency_pct | REAL | Yes | - | % | Efficiency |
| lifecycle_state | TEXT | Yes | - | - | ACTIVE, INACTIVE, MAINTENANCE |

## tanks
| Field | Type | Required | Key | Unit | Description |
|---|---|---|---|---|---|
| tank_id | TEXT | Yes | PK | - | Tank identifier |
| facility_id | TEXT | Yes | FK facilities | - | Parent facility |
| tank_name | TEXT | Yes | - | - | Display name |
| capacity_m3 | REAL | Yes | - | m3 | Geometric capacity |
| height_m | REAL | Yes | - | m | Height used for hydrostatic pressure |
| initial_level_pct | REAL | Yes | - | % | Initial level, 0-100 |
| lifecycle_state | TEXT | Yes | - | - | ACTIVE, INACTIVE, MAINTENANCE |

## valves
| Field | Type | Required | Key | Unit | Description |
|---|---|---|---|---|---|
| valve_id | TEXT | Yes | PK | - | Valve identifier |
| facility_id | TEXT | Yes | FK facilities | - | Parent facility |
| valve_name | TEXT | Yes | - | - | Display name |
| valve_type | TEXT | Yes | - | - | BALL, GATE, GLOBE, BUTTERFLY, CHECK |
| initial_state | TEXT | Yes | - | - | OPEN, CLOSED, PARTIAL |
| opening_pct | REAL | Yes | - | % | Opening, 0-100 |
| lifecycle_state | TEXT | Yes | - | - | ACTIVE, INACTIVE, MAINTENANCE |

## pipes
| Field | Type | Required | Key | Unit | Description |
|---|---|---|---|---|---|
| pipe_id | TEXT | Yes | PK | - | Pipe identifier |
| facility_id | TEXT | Yes | FK facilities | - | Parent facility |
| source_node_id | TEXT | Yes | - | - | `NODE-<equipment_id>` |
| target_node_id | TEXT | Yes | - | - | `NODE-<equipment_id>` |
| length_m | REAL | Yes | - | m | Length |
| diameter_mm | REAL | Yes | - | mm | Diameter |
| roughness_factor | REAL | Yes | - | - | Relative roughness |
| lifecycle_state | TEXT | Yes | - | - | ACTIVE, INACTIVE, MAINTENANCE |

## sensors
| Field | Type | Required | Key | Unit | Description |
|---|---|---|---|---|---|
| sensor_id | TEXT | Yes | PK | - | Sensor identifier |
| facility_id | TEXT | Yes | FK facilities | - | Parent facility |
| equipment_id | TEXT | No | - | - | PUMP/TANK/VALVE identifier |
| equipment_type | TEXT | No | - | - | PUMP, TANK, VALVE, PIPE, JUNCTION |
| sensor_type | TEXT | Yes | - | - | FLOW, PRESSURE, LEVEL, TEMPERATURE |
| sensor_role | TEXT | Yes | - | - | discharge, level, pressure, inlet, outlet, through |
| measurement_unit | TEXT | Yes | - | - | m3/h, bar, %, C |
| sampling_interval_seconds | INTEGER | Yes | - | s | Nominal cadence |
| accuracy_tolerance | REAL | Yes | - | % | Accuracy as percentage of reading |
| lifecycle_state | TEXT | Yes | - | - | ACTIVE, INACTIVE, MAINTENANCE |

Required composition: every pump has discharge FLOW + PRESSURE; every tank has LEVEL, PRESSURE,
inlet FLOW, outlet FLOW; every valve has through FLOW.

## operating_modes
| Field | Type | Required | Key | Description |
|---|---|---|---|---|
| operating_mode_id | TEXT | Yes | PK | OPM-XXX |
| mode_name | TEXT | Yes | unique | NORMAL, STARTUP, SHUTDOWN, MAINTENANCE |
| description | TEXT | Yes | - | Human description |
| permitted_configuration | TEXT | No | - | Permitted configuration |
| effective_from | TEXT (ISO8601) | Yes | - | Start |
| effective_to | TEXT (ISO8601) | No | - | End |
| lifecycle_state | TEXT | Yes | - | ACTIVE, INACTIVE |

## simulation_runs
| Field | Type | Required | Key | Description |
|---|---|---|---|---|
| simulation_run_id | TEXT | Yes | PK | SIM-YYYY-XXXXXX |
| configuration_hash | TEXT | Yes | - | Path-independent 16-hex config hash |
| random_seed | INTEGER | Yes | - | Seed |
| generator_version | TEXT | Yes | - | 2.0.0 |
| schema_version | TEXT | Yes | - | 2.0.0 |
| scenario_set | TEXT | Yes | - | default, calibration, evaluation, compact |
| sampling_interval_seconds | INTEGER | Yes | - | Cadence |
| start_time / end_time | TEXT (ISO8601) | Yes | - | Run window |
| status | TEXT | Yes | - | RUNNING, COMPLETED, FAILED, CANCELLED |
| input_manifest | TEXT (JSON) | No | - | SHA-256 of master CSVs |
| assumptions | TEXT (JSON) | No | - | Model assumptions |
| outcome_summary | TEXT (JSON) | No | - | Row/window/sensor counts |
| created_at | TEXT (ISO8601) | Yes | - | Deterministic run start |

## telemetry
| Field | Type | Required | Key | Unit | Description |
|---|---|---|---|---|---|
| telemetry_id | TEXT | Yes | PK | - | TEL-XXXXXXXXXXXX |
| sensor_id | TEXT | Yes | FK sensors | - | Source sensor |
| simulation_run_id | TEXT | Yes | FK simulation_runs | - | Run |
| timestamp | TEXT (ISO8601) | Yes | - | - | Sample time |
| measured_value | REAL | Yes | - | varies | Observed value |
| measurement_unit | TEXT | Yes | - | - | Unit |
| quality_status | TEXT | Yes | - | - | GOOD, UNCERTAIN, BAD, MISSING |
| operating_mode_id | TEXT | No | FK operating_modes | - | Mode |
| physical_state_value | REAL | No | - | varies | Simulator internal value; **not detector input** |

The detector selects only sensor_id, timestamp, measured_value, quality_status and
operating_mode_id. `physical_state_value` exists for validation/physics checks and is not used for
detection or evaluation labels.

## scenario_definitions
| Field | Type | Required | Key | Description |
|---|---|---|---|---|
| scenario_id | TEXT | Yes | PK | SCN-XXXXXX |
| simulation_run_id | TEXT | Yes | FK simulation_runs | Run |
| issue_type | TEXT | Yes | - | NORMAL, LEAK, BLOCKAGE, PUMP_DEGRADATION, SENSOR_FAULT |
| severity | TEXT | Yes | - | light, medium, severe, normal |
| affected_equipment_id | TEXT | No | - | Affected asset |
| affected_sensor_id | TEXT | No | FK sensors | Target sensor for sensor faults |
| expected_sensor_ids | TEXT (JSON list) | No | - | Observable sensors |
| start_time / end_time | TEXT (ISO8601) | Yes | - | Half-open window |
| injection_parameters | TEXT (JSON) | No | - | Severity/physical parameters |
| expected_observable | TEXT | No | - | Expected symptom |

## ground_truth
| Field | Type | Required | Key | Description |
|---|---|---|---|---|
| gt_id | TEXT | Yes | PK | GT-XXXXXX |
| simulation_run_id | TEXT | Yes | FK simulation_runs | Run |
| scenario_id | TEXT | Yes | FK scenario_definitions | One-to-one scenario |
| issue_type | TEXT | Yes | - | Same vocabulary as scenario |
| severity | TEXT | Yes | - | light, medium, severe, normal |
| affected_equipment_id | TEXT | No | - | Equipment |
| affected_sensor_id | TEXT | No | FK sensors | Target sensor |
| expected_sensor_ids | TEXT (JSON list) | No | - | Point-label sensors |
| start_time / end_time | TEXT (ISO8601) | Yes | - | Half-open labelled window |
| expected_detection | TEXT | Yes | - | YES for anomalies, NO for NORMAL |
| expected_alarm_category | TEXT | No | - | PROCESS_FAULT, SENSOR_FAULT, NORMAL |
| injection_parameters | TEXT (JSON) | No | - | Injection details |

NORMAL rows have `expected_detection=NO`, `expected_alarm_category=NORMAL`, and no affected
equipment/sensor. They are explicit negatives, not "everything outside an event".

## alarms
| Field | Type | Required | Key | Description |
|---|---|---|---|---|
| alarm_id | TEXT | Yes | PK | ALARM-XXXXXX |
| simulation_run_id | TEXT | Yes | FK simulation_runs | Run |
| equipment_id | TEXT | No | - | Attributed equipment |
| sensor_id | TEXT | No | FK sensors | Triggering sensor |
| alarm_type | TEXT | Yes | - | Human-readable rule name |
| alarm_category | TEXT | Yes | - | PROCESS_FAULT, SENSOR_FAULT, UNCERTAIN |
| severity | TEXT | Yes | - | INFO, LOW, MEDIUM, HIGH, CRITICAL |
| first_detected_at / last_detected_at | TEXT (ISO8601) | Yes | - | Active episode interval |
| evidence_summary | TEXT | Yes | - | Threshold, peak and attribution |
| rule_id | TEXT | Yes | - | RULE-001 ... RULE-010 |
| alarm_status | TEXT | Yes | - | ACTIVE, ACKNOWLEDGED, RESOLVED, FALSE_ALARM |
| occurrence_count | INTEGER | Yes | - | Active readings in the episode |
| peak_value | REAL | No | - | Extreme value (mode depends on rule) |
| peak_at | TEXT (ISO8601) | No | - | Time of extreme value |
| attribution | TEXT | No | - | Evidence class, e.g. OBSERVED_LEVEL |
| operating_mode | TEXT | No | - | Mode at activation |

There is no `scenario_id` on alarms; alarms cannot carry labels.

## alarm_events
Append-only episode history for CREATED/RESOLVED (and future lifecycle events).

| Field | Type | Required | Key | Description |
|---|---|---|---|---|
| event_id | TEXT | Yes | PK | EVT-XXXXXXXXXXXX |
| alarm_id | TEXT | Yes | FK alarms | Episode |
| simulation_run_id | TEXT | Yes | FK simulation_runs | Run |
| event_type | TEXT | Yes | - | CREATED, UPDATED, ACKNOWLEDGED, RESOLVED, ESCALATED |
| event_timestamp | TEXT (ISO8601) | Yes | - | Event time |
| event_data | TEXT (JSON) | No | - | Rule/category/mode or last-active detail |

## alarm_incidents
Evaluation grouping of overlapping alarm episodes on one equipment.

| Field | Type | Required | Description |
|---|---|---|---|
| incident_id | TEXT | Yes | INC-XXXXXX |
| simulation_run_id | TEXT | Yes | Run |
| equipment_id | TEXT | No | Equipment |
| sensor_ids / categories / rules | TEXT (JSON lists) | No | Membership |
| severity_max | TEXT | No | Highest severity in incident |
| first_detected_at / last_detected_at | TEXT | Yes | Incident interval |
| alarm_count | INTEGER | Yes | Number of episodes merged |
| alarm_ids | TEXT (JSON list) | Yes | Member alarm IDs |
| matched_gt_id | TEXT | No | Assigned event, if matched |
| classification | TEXT | Yes | MATCHED, FALSE_ALARM, UNKNOWN |
| assigned_normal_gt_id | TEXT | No | NORMAL window for a false alarm |
| latency_seconds | REAL | No | Onset latency (>= 0) |

## evaluation_metrics
Long-format EVENT and POINT metrics.

| Field | Type | Required | Description |
|---|---|---|---|
| metric_id | TEXT | Yes | MET-XXXXXX |
| simulation_run_id | TEXT | Yes | Run |
| evaluation_level | TEXT | Yes | EVENT or POINT |
| scope | TEXT | Yes | overall or a breakdown key |
| metric_name | TEXT | Yes | e.g. precision, recall, f1_score |
| metric_value | REAL | No | NULL when denominator is zero |
| denominator | REAL | No | Optional explicit denominator |
| details | TEXT | No | Policy note |
| evaluated_at | TEXT (ISO8601) | Yes | Evaluation wall clock (CSV only; not in JSON) |

## evaluation_events
One row per ground-truth event with its outcome.

| Field | Type | Required | Description |
|---|---|---|---|
| evaluation_event_id | TEXT | Yes | EVAL-EVT-XXXXXX |
| simulation_run_id | TEXT | Yes | Run |
| gt_id | TEXT | Yes | Ground truth |
| issue_type / severity | TEXT | Yes | Event type and severity |
| affected_equipment_id | TEXT | No | Equipment |
| expected_sensors | TEXT (JSON) | No | Point-label sensors |
| expected_alarm_category | TEXT | No | Expected category |
| start_time / end_time | TEXT | No | Window |
| is_positive / is_normal | INTEGER | Yes | Window role |
| matched | INTEGER | Yes | Matched to an incident |
| matched_incident_id | TEXT | No | Incident |
| latency_seconds | REAL | No | Onset latency |
| outcome | TEXT | Yes | DETECTED, MISSED, NORMAL_NO_ALARM, NORMAL_ALARMED |

## validation_results
| Field | Type | Required | Description |
|---|---|---|---|
| validation_id | TEXT | Yes | VAL-XXXXXX |
| simulation_run_id | TEXT | No | Run |
| validation_type | TEXT | Yes | PRIMARY_KEY, FOREIGN_KEY, PHYSICS, EVALUATION, etc. |
| test_case_id | TEXT | Yes | Stable check ID |
| status | TEXT | Yes | PASS, FAIL, WARN, NOT_IMPLEMENTED |
| entity_type / entity_id | TEXT | No | Checked object |
| description | TEXT | Yes | What was checked |
| details | TEXT | No | Observed values |
| validated_at | TEXT (ISO8601) | Yes | Wall clock; excluded from deterministic comparison |

## Legacy tables

`equipment_state_events` and `detection_results` remain in `schema.py` for compatibility with
1.x, but the 2.0.0 export does not populate or export them. Event evaluation is stored in
`evaluation_events` / `evaluation_metrics`, and alarm lifecycle history is in `alarm_events`.

## Notes

- All timestamps are ISO 8601.
- Half-open windows are `[start, end)`; an event ending at 08:00 does not label the 08:00 sample.
- Ground-truth, scenario and expected-label columns are absent from telemetry and alarms.
- `physical_state_value` is persisted for validation but is not a detector input.
- Deterministic CSVs are listed in `run_manifest.json`; timestamped reports are excluded from
  byte-for-byte reproducibility claims.

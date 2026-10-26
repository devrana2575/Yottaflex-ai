# Data Dictionary

## Overview
Complete specification of all fields in the YottaFlex database schema.

## facilities
| Field | Type | Required | PK/FK | Allowed Values | Unit | Description |
|-------|------|----------|-------|----------------|------|-------------|
| facility_id | TEXT | Yes | PK | FAC-XXX | - | Unique facility identifier |
| facility_name | TEXT | Yes | - | - | - | Facility name |
| location_code | TEXT | Yes | - | - | - | Location code |
| lifecycle_state | TEXT | Yes | - | ACTIVE, INACTIVE, MAINTENANCE | - | Current state |
| created_at | TEXT (ISO8601) | Yes | - | - | - | Creation timestamp |

## pumps
| Field | Type | Required | PK/FK | Allowed Values | Unit | Description |
|-------|------|----------|-------|----------------|------|-------------|
| pump_id | TEXT | Yes | PK | PUMP-XXX | - | Unique pump identifier |
| facility_id | TEXT | Yes | FK->facilities | FAC-XXX | - | Parent facility |
| pump_name | TEXT | Yes | - | - | - | Pump name |
| nominal_flow_m3_h | REAL | Yes | - | >0 | m3/h | Nominal flow rate |
| nominal_head_m | REAL | Yes | - | >0 | m | Nominal head |
| rated_power_kw | REAL | Yes | - | >0 | kW | Rated power |
| efficiency_pct | REAL | Yes | - | 0-100 | % | Efficiency |
| lifecycle_state | TEXT | Yes | - | ACTIVE, INACTIVE, MAINTENANCE | - | Current state |

## tanks
| Field | Type | Required | PK/FK | Allowed Values | Unit | Description |
|-------|------|----------|-------|----------------|------|-------------|
| tank_id | TEXT | Yes | PK | TANK-XXX | - | Unique tank identifier |
| facility_id | TEXT | Yes | FK->facilities | FAC-XXX | - | Parent facility |
| tank_name | TEXT | Yes | - | - | - | Tank name |
| capacity_m3 | REAL | Yes | - | >0 | m3 | Tank capacity |
| initial_level_pct | REAL | Yes | - | 0-100 | % | Initial level |
| lifecycle_state | TEXT | Yes | - | ACTIVE, INACTIVE, MAINTENANCE | - | Current state |

## valves
| Field | Type | Required | PK/FK | Allowed Values | Unit | Description |
|-------|------|----------|-------|----------------|------|-------------|
| valve_id | TEXT | Yes | PK | VALVE-XXX | - | Unique valve identifier |
| facility_id | TEXT | Yes | FK->facilities | FAC-XXX | - | Parent facility |
| valve_name | TEXT | Yes | - | - | - | Valve name |
| valve_type | TEXT | Yes | - | BALL, GATE, GLOBE, BUTTERFLY, CHECK | - | Valve type |
| initial_state | TEXT | Yes | - | OPEN, CLOSED, PARTIAL | - | Initial state |
| opening_pct | REAL | Yes | - | 0-100 | % | Opening percentage |
| lifecycle_state | TEXT | Yes | - | ACTIVE, INACTIVE, MAINTENANCE | - | Current state |

## pipes
| Field | Type | Required | PK/FK | Allowed Values | Unit | Description |
|-------|------|----------|-------|----------------|------|-------------|
| pipe_id | TEXT | Yes | PK | PIPE-XXX | - | Unique pipe identifier |
| facility_id | TEXT | Yes | FK->facilities | FAC-XXX | - | Parent facility |
| source_node_id | TEXT | Yes | - | NODE-* | - | Source node |
| target_node_id | TEXT | Yes | - | NODE-* | - | Target node |
| length_m | REAL | Yes | - | >0 | m | Pipe length |
| diameter_mm | REAL | Yes | - | >0 | mm | Pipe diameter |
| roughness_factor | REAL | Yes | - | >0 | - | Roughness factor |
| lifecycle_state | TEXT | Yes | - | ACTIVE, INACTIVE, MAINTENANCE | - | Current state |

## sensors
| Field | Type | Required | PK/FK | Allowed Values | Unit | Description |
|-------|------|----------|-------|----------------|------|-------------|
| sensor_id | TEXT | Yes | PK | SNS-XXX | - | Unique sensor identifier |
| facility_id | TEXT | Yes | FK->facilities | FAC-XXX | - | Parent facility |
| equipment_id | TEXT | No | - | PUMP-XXX/TANK-XXX/VALVE-XXX | - | Associated equipment |
| equipment_type | TEXT | No | - | PUMP, TANK, VALVE, PIPE, JUNCTION | - | Equipment type |
| sensor_type | TEXT | Yes | - | FLOW, PRESSURE, LEVEL, TEMPERATURE | - | Measurement type |
| measurement_unit | TEXT | Yes | - | m3/h, bar, %, C | - | Unit of measure |
| sampling_interval_seconds | INTEGER | Yes | - | >0 | s | Sampling interval |
| accuracy_tolerance | REAL | Yes | - | >0 | - | Accuracy tolerance |
| lifecycle_state | TEXT | Yes | - | ACTIVE, INACTIVE, MAINTENANCE | - | Current state |

## telemetry
| Field | Type | Required | PK/FK | Allowed Values | Unit | Description |
|-------|------|----------|-------|----------------|------|-------------|
| telemetry_id | TEXT | Yes | PK | TEL-XXXXXXXXXXXX | - | Unique telemetry identifier |
| sensor_id | TEXT | Yes | FK->sensors | SNS-XXX | - | Source sensor |
| simulation_run_id | TEXT | Yes | FK->simulation_runs | SIM-YYYY-XXXXXX | - | Simulation run |
| timestamp | TEXT (ISO8601) | Yes | - | - | - | Measurement time |
| measured_value | REAL | Yes | - | - | varies | Measured value |
| measurement_unit | TEXT | Yes | - | - | - | Unit |
| quality_status | TEXT | Yes | - | GOOD, UNCERTAIN, BAD, MISSING | - | Data quality |
| operating_mode_id | TEXT | No | FK->operating_modes | OPM-XXX | - | Operating mode |

## operating_modes
| Field | Type | Required | PK/FK | Allowed Values | Unit | Description |
|-------|------|----------|-------|----------------|------|-------------|
| operating_mode_id | TEXT | Yes | PK | OPM-XXX | - | Unique mode identifier |
| mode_name | TEXT | Yes | - | NORMAL, STARTUP, SHUTDOWN, MAINTENANCE | - | Mode name |
| description | TEXT | Yes | - | - | - | Description |
| permitted_configuration | TEXT | No | - | - | - | Permitted config |
| effective_from | TEXT (ISO8601) | Yes | - | - | - | Effective start |
| effective_to | TEXT (ISO8601) | No | - | - | - | Effective end |
| lifecycle_state | TEXT | Yes | - | ACTIVE, INACTIVE | - | Current state |

## simulation_runs
| Field | Type | Required | PK/FK | Allowed Values | Unit | Description |
|-------|------|----------|-------|----------------|------|-------------|
| simulation_run_id | TEXT | Yes | PK | SIM-YYYY-XXXXXX | - | Unique run identifier |
| configuration_hash | TEXT | Yes | - | - | - | Hash of config |
| random_seed | INTEGER | Yes | - | - | - | Random seed used |
| generator_version | TEXT | Yes | - | - | - | Generator version |
| schema_version | TEXT | Yes | - | - | - | Schema version |
| start_time | TEXT (ISO8601) | Yes | - | - | - | Simulation start |
| end_time | TEXT (ISO8601) | Yes | - | - | - | Simulation end |
| status | TEXT | Yes | - | RUNNING, COMPLETED, FAILED, CANCELLED | - | Run status |
| input_manifest | TEXT (JSON) | No | - | - | - | Input files manifest |
| assumptions | TEXT (JSON) | No | - | - | - | Model assumptions |
| outcome_summary | TEXT (JSON) | No | - | - | - | Results summary |
| created_at | TEXT (ISO8601) | Yes | - | - | - | Creation time |

## alarms
| Field | Type | Required | PK/FK | Allowed Values | Unit | Description |
|-------|------|----------|-------|----------------|------|-------------|
| alarm_id | TEXT | Yes | PK | ALARM-XXXXXX | - | Unique alarm identifier |
| simulation_run_id | TEXT | Yes | FK->simulation_runs | SIM-YYYY-XXXXXX | - | Simulation run |
| equipment_id | TEXT | No | - | - | - | Affected equipment |
| sensor_id | TEXT | No | FK->sensors | SNS-XXX | - | Triggering sensor |
| alarm_type | TEXT | Yes | - | - | - | Alarm type/name |
| severity | TEXT | Yes | - | INFO, LOW, MEDIUM, HIGH, CRITICAL | - | Severity level |
| first_detected_at | TEXT (ISO8601) | Yes | - | - | - | First detection time |
| last_detected_at | TEXT (ISO8601) | Yes | - | - | - | Last detection time |
| evidence_summary | TEXT | Yes | - | - | - | Detection evidence |
| rule_id | TEXT | Yes | - | RULE-XXX | - | Rule that triggered |
| alarm_status | TEXT | Yes | - | ACTIVE, ACKNOWLEDGED, RESOLVED, FALSE_ALARM | - | Alarm status |
| scenario_id | TEXT | No | FK->scenario_definitions | SCN-XXXXXX | - | Associated scenario |

## scenario_definitions
| Field | Type | Required | PK/FK | Allowed Values | Unit | Description |
|-------|------|----------|-------|----------------|------|-------------|
| scenario_id | TEXT | Yes | PK | SCN-XXXXXX | - | Unique scenario identifier |
| simulation_run_id | TEXT | Yes | FK->simulation_runs | SIM-YYYY-XXXXXX | - | Simulation run |
| issue_type | TEXT | Yes | - | NORMAL, LEAK, BLOCKAGE, PUMP_DEGRADATION, SENSOR_FAULT | - | Anomaly type |
| affected_equipment_id | TEXT | No | - | - | - | Affected equipment |
| affected_sensor_id | TEXT | No | FK->sensors | SNS-XXX | - | Affected sensor |
| start_time | TEXT (ISO8601) | Yes | - | - | - | Scenario start |
| end_time | TEXT (ISO8601) | Yes | - | - | - | Scenario end |
| injection_parameters | TEXT (JSON) | No | - | - | - | Injection details |
| expected_observable | TEXT | No | - | - | - | Expected symptoms |

## ground_truth
| Field | Type | Required | PK/FK | Allowed Values | Unit | Description |
|-------|------|----------|-------|----------------|------|-------------|
| gt_id | TEXT | Yes | PK | GT-XXXXXX | - | Unique GT identifier |
| simulation_run_id | TEXT | Yes | FK->simulation_runs | SIM-YYYY-XXXXXX | - | Simulation run |
| scenario_id | TEXT | Yes | FK->scenario_definitions | SCN-XXXXXX | - | Related scenario |
| issue_type | TEXT | Yes | - | NORMAL, LEAK, BLOCKAGE, PUMP_DEGRADATION, SENSOR_FAULT | - | Anomaly type |
| affected_equipment_id | TEXT | No | - | - | - | Affected equipment |
| affected_sensor_id | TEXT | No | FK->sensors | SNS-XXX | - | Affected sensor |
| start_time | TEXT (ISO8601) | Yes | - | - | - | Scenario start |
| end_time | TEXT (ISO8601) | Yes | - | - | - | Scenario end |
| expected_detection | TEXT | Yes | - | YES, NO | - | Should be detected |
| expected_alarm_category | TEXT | No | - | PROCESS_FAULT, SENSOR_FAULT | - | Expected category |
| injection_parameters | TEXT (JSON) | No | - | - | - | Injection details |

## Notes
- All timestamps in ISO8601 format
- Ground truth and scenario IDs are stored separately and are not included in telemetry CSVs
- Physical-state values are internal to scenario injection and are not persisted to telemetry
- The detector operates on measured values, sensor metadata, and observed quality status only
- Append-only tables (alarm_events, equipment_state_events) preserve history

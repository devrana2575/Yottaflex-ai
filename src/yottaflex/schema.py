"""Database schema definitions (YottaFlex 2.0.0).

The schema keeps observed telemetry, detector output, append-only alarm history,
ground truth, and evaluation in separate tables.  Ground truth is never stored
on the telemetry table, so a detector cannot read it by accident.
"""

SCHEMA_VERSION = "2.0.0"

SCHEMA_SQL = """
-- YottaFlex Database Schema 2.0.0
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS facilities (
    facility_id TEXT PRIMARY KEY,
    facility_name TEXT NOT NULL,
    location_code TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('ACTIVE','INACTIVE','MAINTENANCE')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pumps (
    pump_id TEXT PRIMARY KEY,
    facility_id TEXT NOT NULL,
    pump_name TEXT NOT NULL,
    nominal_flow_m3_h REAL NOT NULL,
    nominal_head_m REAL NOT NULL,
    rated_power_kw REAL NOT NULL,
    efficiency_pct REAL NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('ACTIVE','INACTIVE','MAINTENANCE')),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
);

CREATE TABLE IF NOT EXISTS tanks (
    tank_id TEXT PRIMARY KEY,
    facility_id TEXT NOT NULL,
    tank_name TEXT NOT NULL,
    capacity_m3 REAL NOT NULL,
    height_m REAL NOT NULL,
    initial_level_pct REAL NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('ACTIVE','INACTIVE','MAINTENANCE')),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id),
    CHECK(capacity_m3 > 0),
    CHECK(height_m > 0),
    CHECK(initial_level_pct >= 0 AND initial_level_pct <= 100)
);

CREATE TABLE IF NOT EXISTS valves (
    valve_id TEXT PRIMARY KEY,
    facility_id TEXT NOT NULL,
    valve_name TEXT NOT NULL,
    valve_type TEXT NOT NULL CHECK(valve_type IN ('BALL','GATE','GLOBE','BUTTERFLY','CHECK')),
    initial_state TEXT NOT NULL CHECK(initial_state IN ('OPEN','CLOSED','PARTIAL')),
    opening_pct REAL NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('ACTIVE','INACTIVE','MAINTENANCE')),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id),
    CHECK(opening_pct >= 0 AND opening_pct <= 100)
);

CREATE TABLE IF NOT EXISTS pipes (
    pipe_id TEXT PRIMARY KEY,
    facility_id TEXT NOT NULL,
    source_node_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    length_m REAL NOT NULL,
    diameter_mm REAL NOT NULL,
    roughness_factor REAL NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('ACTIVE','INACTIVE','MAINTENANCE')),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id),
    CHECK(length_m > 0),
    CHECK(diameter_mm > 0),
    CHECK(source_node_id != target_node_id)
);

CREATE TABLE IF NOT EXISTS sensors (
    sensor_id TEXT PRIMARY KEY,
    facility_id TEXT NOT NULL,
    equipment_id TEXT,
    equipment_type TEXT CHECK(equipment_type IN ('PUMP','TANK','VALVE','PIPE','JUNCTION')),
    sensor_type TEXT NOT NULL CHECK(sensor_type IN ('FLOW','PRESSURE','LEVEL','TEMPERATURE')),
    sensor_role TEXT NOT NULL,
    measurement_unit TEXT NOT NULL,
    sampling_interval_seconds INTEGER NOT NULL,
    accuracy_tolerance REAL NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('ACTIVE','INACTIVE','MAINTENANCE')),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
);

CREATE TABLE IF NOT EXISTS operating_modes (
    operating_mode_id TEXT PRIMARY KEY,
    mode_name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    permitted_configuration TEXT,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('ACTIVE','INACTIVE'))
);

CREATE TABLE IF NOT EXISTS simulation_runs (
    simulation_run_id TEXT PRIMARY KEY,
    configuration_hash TEXT NOT NULL,
    random_seed INTEGER NOT NULL,
    generator_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    scenario_set TEXT NOT NULL,
    sampling_interval_seconds INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('RUNNING','COMPLETED','FAILED','CANCELLED')),
    input_manifest TEXT,
    assumptions TEXT,
    outcome_summary TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenario_definitions (
    scenario_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL,
    issue_type TEXT NOT NULL CHECK(issue_type IN ('NORMAL','LEAK','BLOCKAGE','PUMP_DEGRADATION','SENSOR_FAULT')),
    severity TEXT NOT NULL,
    affected_equipment_id TEXT,
    affected_sensor_id TEXT,
    expected_sensor_ids TEXT,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    injection_parameters TEXT,
    expected_observable TEXT,
    FOREIGN KEY (simulation_run_id) REFERENCES simulation_runs(simulation_run_id)
);

CREATE TABLE IF NOT EXISTS telemetry (
    telemetry_id TEXT PRIMARY KEY,
    sensor_id TEXT NOT NULL,
    simulation_run_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    measured_value REAL NOT NULL,
    measurement_unit TEXT NOT NULL,
    quality_status TEXT NOT NULL CHECK(quality_status IN ('GOOD','UNCERTAIN','BAD','MISSING')),
    operating_mode_id TEXT,
    physical_state_value REAL,
    FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id),
    FOREIGN KEY (simulation_run_id) REFERENCES simulation_runs(simulation_run_id),
    FOREIGN KEY (operating_mode_id) REFERENCES operating_modes(operating_mode_id)
);

CREATE TABLE IF NOT EXISTS alarms (
    alarm_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL,
    equipment_id TEXT,
    sensor_id TEXT,
    alarm_type TEXT NOT NULL,
    alarm_category TEXT NOT NULL CHECK(alarm_category IN ('PROCESS_FAULT','SENSOR_FAULT','UNCERTAIN')),
    severity TEXT NOT NULL CHECK(severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')),
    first_detected_at TEXT NOT NULL,
    last_detected_at TEXT NOT NULL,
    evidence_summary TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    alarm_status TEXT NOT NULL CHECK(alarm_status IN ('ACTIVE','ACKNOWLEDGED','RESOLVED','FALSE_ALARM')),
    occurrence_count INTEGER NOT NULL,
    peak_value REAL,
    peak_at TEXT,
    attribution TEXT,
    operating_mode TEXT,
    FOREIGN KEY (simulation_run_id) REFERENCES simulation_runs(simulation_run_id)
);

CREATE TABLE IF NOT EXISTS alarm_events (
    event_id TEXT PRIMARY KEY,
    alarm_id TEXT NOT NULL,
    simulation_run_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('CREATED','UPDATED','ACKNOWLEDGED','RESOLVED','ESCALATED')),
    event_timestamp TEXT NOT NULL,
    event_data TEXT,
    FOREIGN KEY (alarm_id) REFERENCES alarms(alarm_id),
    FOREIGN KEY (simulation_run_id) REFERENCES simulation_runs(simulation_run_id)
);

CREATE TABLE IF NOT EXISTS equipment_state_events (
    event_id TEXT PRIMARY KEY,
    equipment_id TEXT NOT NULL,
    equipment_type TEXT NOT NULL,
    simulation_run_id TEXT NOT NULL,
    state_value TEXT NOT NULL,
    event_timestamp TEXT NOT NULL,
    event_data TEXT,
    FOREIGN KEY (simulation_run_id) REFERENCES simulation_runs(simulation_run_id)
);

CREATE TABLE IF NOT EXISTS ground_truth (
    gt_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL,
    scenario_id TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    affected_equipment_id TEXT,
    affected_sensor_id TEXT,
    expected_sensor_ids TEXT,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    expected_detection TEXT NOT NULL CHECK(expected_detection IN ('YES','NO')),
    expected_alarm_category TEXT,
    injection_parameters TEXT,
    FOREIGN KEY (simulation_run_id) REFERENCES simulation_runs(simulation_run_id),
    FOREIGN KEY (scenario_id) REFERENCES scenario_definitions(scenario_id)
);

CREATE TABLE IF NOT EXISTS alarm_incidents (
    incident_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL,
    equipment_id TEXT,
    sensor_ids TEXT,
    categories TEXT,
    rules TEXT,
    severity_max TEXT,
    first_detected_at TEXT NOT NULL,
    last_detected_at TEXT NOT NULL,
    alarm_count INTEGER NOT NULL,
    alarm_ids TEXT,
    matched_gt_id TEXT,
    classification TEXT NOT NULL CHECK(classification IN ('MATCHED','FALSE_ALARM','UNKNOWN')),
    assigned_normal_gt_id TEXT,
    latency_seconds REAL,
    FOREIGN KEY (simulation_run_id) REFERENCES simulation_runs(simulation_run_id)
);

CREATE TABLE IF NOT EXISTS evaluation_metrics (
    metric_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL,
    evaluation_level TEXT NOT NULL CHECK(evaluation_level IN ('EVENT','POINT')),
    scope TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    denominator REAL,
    details TEXT,
    evaluated_at TEXT NOT NULL,
    FOREIGN KEY (simulation_run_id) REFERENCES simulation_runs(simulation_run_id)
);

CREATE TABLE IF NOT EXISTS evaluation_events (
    evaluation_event_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL,
    gt_id TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    affected_equipment_id TEXT,
    expected_sensors TEXT,
    expected_alarm_category TEXT,
    start_time TEXT,
    end_time TEXT,
    is_positive INTEGER,
    is_normal INTEGER,
    matched INTEGER NOT NULL,
    matched_incident_id TEXT,
    latency_seconds REAL,
    outcome TEXT NOT NULL,
    FOREIGN KEY (simulation_run_id) REFERENCES simulation_runs(simulation_run_id)
);

CREATE TABLE IF NOT EXISTS validation_results (
    validation_id TEXT PRIMARY KEY,
    simulation_run_id TEXT,
    validation_type TEXT NOT NULL,
    test_case_id TEXT,
    status TEXT NOT NULL CHECK(status IN ('PASS','FAIL','WARN','NOT_IMPLEMENTED')),
    entity_type TEXT,
    entity_id TEXT,
    description TEXT NOT NULL,
    details TEXT,
    validated_at TEXT NOT NULL
);

-- Legacy detection_results retained for compatibility; event-level evaluation
-- is stored in evaluation_events/evaluation_metrics in schema 2.0.0.
CREATE TABLE IF NOT EXISTS detection_results (
    result_id TEXT PRIMARY KEY,
    simulation_run_id TEXT NOT NULL,
    alarm_id TEXT,
    scenario_id TEXT,
    prediction TEXT NOT NULL CHECK(prediction IN ('ANOMALY','NORMAL')),
    actual TEXT NOT NULL CHECK(actual IN ('ANOMALY','NORMAL')),
    true_positive INTEGER,
    false_positive INTEGER,
    true_negative INTEGER,
    false_negative INTEGER,
    detection_latency_seconds INTEGER,
    rule_id TEXT,
    evaluated_at TEXT NOT NULL,
    FOREIGN KEY (simulation_run_id) REFERENCES simulation_runs(simulation_run_id)
);

CREATE INDEX IF NOT EXISTS idx_telemetry_sensor_time ON telemetry(sensor_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_telemetry_sim_run ON telemetry(simulation_run_id);
CREATE INDEX IF NOT EXISTS idx_alarms_sim_run ON alarms(simulation_run_id);
CREATE INDEX IF NOT EXISTS idx_alarms_equipment ON alarms(equipment_id);
CREATE INDEX IF NOT EXISTS idx_alarm_events_alarm ON alarm_events(alarm_id);
CREATE INDEX IF NOT EXISTS idx_pipes_facility ON pipes(facility_id);
CREATE INDEX IF NOT EXISTS idx_sensors_equipment ON sensors(equipment_id);
CREATE INDEX IF NOT EXISTS idx_scenario_sim_run ON scenario_definitions(simulation_run_id);
CREATE INDEX IF NOT EXISTS idx_ground_truth_sim_run ON ground_truth(simulation_run_id);
CREATE INDEX IF NOT EXISTS idx_incidents_sim_run ON alarm_incidents(simulation_run_id);
"""

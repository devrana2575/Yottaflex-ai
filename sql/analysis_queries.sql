-- YottaFlex 2.0.0 analytical queries.
-- Each statement declares a machine-checkable expectation used by `yottaflex run-sql`.

-- Q1 | Master-data scale | expect=nonempty
SELECT 'facilities' AS entity, COUNT(*) AS row_count FROM facilities
UNION ALL SELECT 'pumps', COUNT(*) FROM pumps
UNION ALL SELECT 'tanks', COUNT(*) FROM tanks
UNION ALL SELECT 'valves', COUNT(*) FROM valves
UNION ALL SELECT 'sensors', COUNT(*) FROM sensors
UNION ALL SELECT 'telemetry', COUNT(*) FROM telemetry;

-- Q2 | Highest-alarm equipment | expect=nonempty
SELECT
    equipment_id,
    COUNT(*) AS alarm_episodes,
    COUNT(DISTINCT simulation_run_id) AS runs_with_alarms,
    SUM(occurrence_count) AS active_readings
FROM alarms
WHERE equipment_id IS NOT NULL
GROUP BY equipment_id
ORDER BY alarm_episodes DESC, equipment_id
LIMIT 20;

-- Q3 | Alarms by facility, category and severity | expect=nonempty
SELECT
    f.facility_id,
    f.facility_name,
    a.alarm_category,
    a.severity,
    COUNT(*) AS alarm_count
FROM alarms a
LEFT JOIN sensors s ON a.sensor_id = s.sensor_id
LEFT JOIN facilities f ON s.facility_id = f.facility_id
GROUP BY f.facility_id, f.facility_name, a.alarm_category, a.severity
ORDER BY f.facility_id, a.alarm_category, a.severity;

-- Q4 | Telemetry quality distribution | expect=nonempty
SELECT
    quality_status,
    COUNT(*) AS reading_count,
    COUNT(DISTINCT sensor_id) AS sensors
FROM telemetry
GROUP BY quality_status
ORDER BY reading_count DESC;

-- Q5 | Tank level operating envelope | expect=nonempty
SELECT
    tk.tank_id,
    tk.tank_name,
    tk.capacity_m3,
    tk.height_m,
    ROUND(MIN(t.measured_value), 3) AS min_level_pct,
    ROUND(MAX(t.measured_value), 3) AS max_level_pct,
    ROUND(AVG(t.measured_value), 3) AS avg_level_pct
FROM tanks tk
JOIN sensors s
  ON s.equipment_id = tk.tank_id
 AND s.equipment_type = 'TANK'
 AND s.sensor_type = 'LEVEL'
JOIN telemetry t ON t.sensor_id = s.sensor_id
GROUP BY tk.tank_id, tk.tank_name, tk.capacity_m3, tk.height_m
ORDER BY tk.tank_id;

-- Q6 | Pump flow deviation from nominal | expect=nonempty
SELECT
    p.pump_id,
    p.pump_name,
    p.nominal_flow_m3_h,
    ROUND(AVG(t.measured_value), 3) AS avg_measured_flow,
    ROUND(
        ABS(AVG(t.measured_value) - p.nominal_flow_m3_h)
        / p.nominal_flow_m3_h * 100.0,
        3
    ) AS deviation_pct
FROM pumps p
JOIN sensors s
  ON s.equipment_id = p.pump_id
 AND s.equipment_type = 'PUMP'
 AND s.sensor_type = 'FLOW'
JOIN telemetry t ON t.sensor_id = s.sensor_id
GROUP BY p.pump_id, p.pump_name, p.nominal_flow_m3_h
ORDER BY deviation_pct DESC;

-- Q7 | Event-level ground-truth detection by type | expect=nonempty
SELECT
    gt.issue_type,
    COUNT(*) AS injected,
    SUM(CASE WHEN ee.matched = 1 THEN 1 ELSE 0 END) AS detected,
    ROUND(
        SUM(CASE WHEN ee.matched = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS detection_rate_pct,
    ROUND(AVG(CASE WHEN ee.matched = 1 THEN ee.latency_seconds END), 1) AS mean_latency_seconds
FROM ground_truth gt
LEFT JOIN evaluation_events ee ON ee.gt_id = gt.gt_id
WHERE gt.issue_type <> 'NORMAL'
GROUP BY gt.issue_type
ORDER BY gt.issue_type;

-- Q8 | Event-level metrics with explicit denominators | expect=nonempty
SELECT
    evaluation_level,
    scope,
    metric_name,
    metric_value
FROM evaluation_metrics
WHERE evaluation_level = 'EVENT'
  AND scope = 'overall'
ORDER BY metric_name;

-- Q9 | Point-level metrics with explicit denominators | expect=nonempty
SELECT
    metric_name,
    metric_value
FROM evaluation_metrics
WHERE evaluation_level = 'POINT'
  AND scope = 'overall'
ORDER BY metric_name;

-- Q10 | Alarm incident classifications | expect=nonempty
SELECT
    classification,
    COUNT(*) AS incidents,
    ROUND(AVG(latency_seconds), 1) AS mean_latency_seconds
FROM alarm_incidents
GROUP BY classification
ORDER BY classification;

-- Q11 | Scenario windows by issue type and severity | expect=nonempty
SELECT
    issue_type,
    severity,
    COUNT(*) AS windows,
    MIN(start_time) AS first_start,
    MAX(end_time) AS last_end
FROM scenario_definitions
GROUP BY issue_type, severity
ORDER BY issue_type, severity;

-- Q12 | Alarm history integrity problems | expect=zero_rows
SELECT a.alarm_id
FROM alarms a
WHERE NOT EXISTS (
        SELECT 1 FROM alarm_events e
        WHERE e.alarm_id = a.alarm_id AND e.event_type = 'CREATED'
    )
   OR (
        a.alarm_status = 'RESOLVED'
        AND NOT EXISTS (
            SELECT 1 FROM alarm_events e
            WHERE e.alarm_id = a.alarm_id AND e.event_type = 'RESOLVED'
        )
    );

-- Q13 | Matched incidents without a per-event evaluation row | expect=zero_rows
SELECT i.incident_id
FROM alarm_incidents i
WHERE i.classification = 'MATCHED'
  AND NOT EXISTS (
      SELECT 1 FROM evaluation_events e
      WHERE e.matched_incident_id = i.incident_id
  );

-- Q14 | Sensors with the fewest readings (missing-data review) | expect=nonempty
SELECT
    s.sensor_id,
    s.equipment_id,
    s.sensor_type,
    s.sensor_role,
    COUNT(t.telemetry_id) AS reading_count
FROM sensors s
LEFT JOIN telemetry t ON t.sensor_id = s.sensor_id
GROUP BY s.sensor_id, s.equipment_id, s.sensor_type, s.sensor_role
ORDER BY reading_count ASC, s.sensor_id
LIMIT 10;

-- Q15 | Simulation-run lineage and config hash | expect=nonempty
SELECT
    simulation_run_id,
    random_seed,
    generator_version,
    schema_version,
    scenario_set,
    sampling_interval_seconds,
    configuration_hash,
    status,
    start_time,
    end_time
FROM simulation_runs
ORDER BY created_at DESC;

-- Q16 | Alarm rule/category distribution | expect=nonempty
SELECT
    rule_id,
    alarm_category,
    COUNT(*) AS episodes,
    SUM(occurrence_count) AS active_readings,
    ROUND(AVG(occurrence_count), 1) AS mean_duration_samples
FROM alarms
GROUP BY rule_id, alarm_category
ORDER BY episodes DESC, rule_id;

-- Q17 | Largest positive tank mass-balance residuals | expect=nonempty
WITH tank_values AS (
    SELECT
        s.equipment_id,
        t.timestamp,
        t.physical_state_value AS value,
        s.sensor_role
    FROM telemetry t
    JOIN sensors s ON s.sensor_id = t.sensor_id
    WHERE s.equipment_type = 'TANK'
      AND s.sensor_role IN ('level', 'inlet', 'outlet')
),
wide AS (
    SELECT
        timestamp,
        equipment_id,
        MAX(CASE WHEN sensor_role = 'level' THEN value END) AS level_pct,
        MAX(CASE WHEN sensor_role = 'inlet' THEN value END) AS inlet_m3_h,
        MAX(CASE WHEN sensor_role = 'outlet' THEN value END) AS outlet_m3_h
    FROM tank_values
    GROUP BY timestamp, equipment_id
),
lagged AS (
    SELECT
        w.equipment_id,
        w.timestamp,
        w.inlet_m3_h,
        w.outlet_m3_h,
        w.level_pct,
        LAG(w.level_pct) OVER (
            PARTITION BY w.equipment_id ORDER BY w.timestamp
        ) AS previous_level_pct,
        (
            JULIANDAY(w.timestamp) - JULIANDAY(
                LAG(w.timestamp) OVER (
                    PARTITION BY w.equipment_id ORDER BY w.timestamp
                )
            )
        ) * 24.0 AS dt_hours,
        tk.capacity_m3
    FROM wide w
    JOIN tanks tk ON tk.tank_id = w.equipment_id
)
SELECT
    equipment_id,
    timestamp,
    ROUND(inlet_m3_h - outlet_m3_h
        - ((level_pct - previous_level_pct) / 100.0 * capacity_m3 / dt_hours), 3
    ) AS balance_residual_m3_h
FROM lagged
WHERE previous_level_pct IS NOT NULL
  AND dt_hours > 0
ORDER BY balance_residual_m3_h DESC
LIMIT 10;

-- Q18 | Ground-truth detection by severity | expect=nonempty
SELECT
    gt.severity,
    COUNT(*) AS events,
    SUM(CASE WHEN ee.matched = 1 THEN 1 ELSE 0 END) AS detected,
    ROUND(
        SUM(CASE WHEN ee.matched = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS detection_rate_pct
FROM ground_truth gt
LEFT JOIN evaluation_events ee ON ee.gt_id = gt.gt_id
WHERE gt.issue_type <> 'NORMAL'
GROUP BY gt.severity
ORDER BY gt.severity;

-- Q19 | SQLite foreign-key violations | expect=zero_rows
PRAGMA foreign_key_check;

-- Q20 | SQLite integrity check | expect=nonempty
PRAGMA integrity_check;

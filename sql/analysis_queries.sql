-- YottaFlex SQL Analytics Queries

-- 1. Highest-alarm equipment
SELECT 
    equipment_id,
    COUNT(*) as alarm_count,
    COUNT(DISTINCT simulation_run_id) as runs_with_alarms
FROM alarms
WHERE equipment_id IS NOT NULL
GROUP BY equipment_id
ORDER BY alarm_count DESC
LIMIT 20;

-- 2. Alarm counts by facility and severity
SELECT 
    f.facility_id,
    f.facility_name,
    a.severity,
    COUNT(*) as alarm_count
FROM alarms a
JOIN sensors s ON a.sensor_id = s.sensor_id
JOIN facilities f ON s.facility_id = f.facility_id
GROUP BY f.facility_id, f.facility_name, a.severity
ORDER BY f.facility_id, 
    CASE a.severity 
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        WHEN 'LOW' THEN 4
        WHEN 'INFO' THEN 5
    END;

-- 3. Sensor-quality failures
SELECT 
    sensor_id,
    quality_status,
    COUNT(*) as count
FROM telemetry
WHERE quality_status IN ('UNCERTAIN', 'BAD', 'MISSING')
GROUP BY sensor_id, quality_status
ORDER BY count DESC;

-- 4. Flow-balance violations over time (simplified)
SELECT 
    DATE(timestamp) as date,
    COUNT(*) as records,
    AVG(measured_value) as avg_flow
FROM telemetry t
JOIN sensors s ON t.sensor_id = s.sensor_id
WHERE s.sensor_type = 'FLOW'
GROUP BY DATE(timestamp)
ORDER BY date;

-- 5. Pump performance deviations
SELECT 
    p.pump_id,
    p.pump_name,
    p.nominal_flow_m3_h,
    AVG(CASE WHEN s.sensor_type = 'FLOW' THEN t.measured_value END) as avg_measured_flow,
    ABS(AVG(CASE WHEN s.sensor_type = 'FLOW' THEN t.measured_value END) - p.nominal_flow_m3_h) / p.nominal_flow_m3_h * 100 as deviation_pct
FROM pumps p
JOIN sensors s ON s.equipment_id = p.pump_id AND s.equipment_type = 'PUMP'
JOIN telemetry t ON t.sensor_id = s.sensor_id
GROUP BY p.pump_id, p.pump_name, p.nominal_flow_m3_h
HAVING deviation_pct > 10
ORDER BY deviation_pct DESC;

-- 6. Tank levels approaching operating limits
SELECT 
    tk.tank_id,
    tk.tank_name,
    tk.capacity_m3,
    s.sensor_id,
    MIN(t.measured_value) as min_level_pct,
    MAX(t.measured_value) as max_level_pct,
    AVG(t.measured_value) as avg_level_pct
FROM tanks tk
JOIN sensors s ON s.equipment_id = tk.tank_id AND s.equipment_type = 'TANK' AND s.sensor_type = 'LEVEL'
JOIN telemetry t ON t.sensor_id = s.sensor_id
GROUP BY tk.tank_id, tk.tank_name, tk.capacity_m3, s.sensor_id
HAVING min_level_pct < 15 OR max_level_pct > 85
ORDER BY min_level_pct ASC;

-- 7. Detection performance by scenario type
SELECT 
    gt.issue_type,
    COUNT(*) as injected,
    SUM(CASE WHEN EXISTS (
        SELECT 1
        FROM alarms a
        WHERE a.equipment_id = gt.affected_equipment_id
          AND a.first_detected_at <= gt.end_time
          AND a.last_detected_at >= gt.start_time
          AND (gt.affected_sensor_id IS NULL OR a.sensor_id = gt.affected_sensor_id)
    ) THEN 1 ELSE 0 END) as detected,
    ROUND(SUM(CASE WHEN EXISTS (
        SELECT 1
        FROM alarms a
        WHERE a.equipment_id = gt.affected_equipment_id
          AND a.first_detected_at <= gt.end_time
          AND a.last_detected_at >= gt.start_time
          AND (gt.affected_sensor_id IS NULL OR a.sensor_id = gt.affected_sensor_id)
    ) THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as detection_rate_pct
FROM ground_truth gt
GROUP BY gt.issue_type;

-- 8. False positives and missed anomalies
SELECT 
    'False Positives' as category,
    COUNT(*) as count
FROM alarms a
WHERE NOT EXISTS (
      SELECT 1
      FROM ground_truth gt
      WHERE gt.affected_equipment_id = a.equipment_id
        AND a.first_detected_at <= gt.end_time
        AND a.last_detected_at >= gt.start_time
        AND (gt.affected_sensor_id IS NULL OR a.sensor_id = gt.affected_sensor_id)
  )
UNION ALL
SELECT 
    'Missed Anomalies' as category,
    COUNT(*) as count
FROM ground_truth gt
WHERE NOT EXISTS (
    SELECT 1
    FROM alarms a
    WHERE a.equipment_id = gt.affected_equipment_id
      AND a.first_detected_at <= gt.end_time
      AND a.last_detected_at >= gt.start_time
      AND (gt.affected_sensor_id IS NULL OR a.sensor_id = gt.affected_sensor_id)
);

-- 9. Simulation-run status and configuration lineage
SELECT 
    simulation_run_id,
    random_seed,
    generator_version,
    schema_version,
    configuration_hash,
    status,
    start_time,
    end_time,
    created_at
FROM simulation_runs
ORDER BY created_at DESC;

-- 10. Equipment with missing or stale telemetry
SELECT 
    s.equipment_id,
    s.equipment_type,
    s.sensor_id,
    s.sensor_type,
    MAX(t.timestamp) as last_reading,
    COUNT(t.telemetry_id) as reading_count,
    JULIANDAY('now') - JULIANDAY(MAX(t.timestamp)) as hours_since_last
FROM sensors s
LEFT JOIN telemetry t ON t.sensor_id = s.sensor_id
WHERE s.lifecycle_state = 'ACTIVE'
GROUP BY s.equipment_id, s.equipment_type, s.sensor_id, s.sensor_type
HAVING hours_since_last > 1 OR reading_count = 0
ORDER BY hours_since_last DESC;

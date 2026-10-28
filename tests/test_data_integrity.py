"""Data-integrity and lineage tests across master data, telemetry and outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from yottaflex import __generator_version__, __schema_version__
from yottaflex.config import Config, DataScaleConfig
from yottaflex.persistence import Database
from yottaflex.schema import SCHEMA_VERSION
from yottaflex.validation import Validator

PRIMARY_KEYS = {
    "facilities": "facility_id",
    "pumps": "pump_id",
    "tanks": "tank_id",
    "valves": "valve_id",
    "pipes": "pipe_id",
    "sensors": "sensor_id",
    "operating_modes": "operating_mode_id",
}

FORBIDDEN_TELEMETRY_COLUMNS = {
    "scenario_id",
    "ground_truth_id",
    "gt_id",
    "issue_type",
    "expected_detection",
    "expected_alarm_category",
    "expected_sensor_ids",
}


def test_master_primary_keys_and_references(master_data):
    for table, key in PRIMARY_KEYS.items():
        frame = master_data[table]
        assert not frame.empty, table
        assert frame[key].notna().all()
        assert not frame[key].duplicated().any(), table

    facilities = set(master_data["facilities"]["facility_id"])
    equipment = {}
    for table, key in (
        ("pumps", "pump_id"),
        ("tanks", "tank_id"),
        ("valves", "valve_id"),
    ):
        frame = master_data[table]
        assert set(frame["facility_id"]) <= facilities
        equipment.update(dict(zip(frame[key], frame["facility_id"])))

    for sensor in master_data["sensors"].itertuples():
        assert sensor.equipment_id in equipment
        assert equipment[sensor.equipment_id] == sensor.facility_id

    nodes = {f"NODE-{item}" for item in equipment}
    pipes = master_data["pipes"]
    assert not pipes.empty
    assert set(pipes["source_node_id"]) <= nodes
    assert set(pipes["target_node_id"]) <= nodes
    assert (pipes["source_node_id"] != pipes["target_node_id"]).all()


def test_sensor_composition_and_units(master_data):
    sensors = master_data["sensors"]
    assert len(sensors) == 3 * 2 + 5 * 4 + 10 * 1
    expected_roles = {
        "PUMP": {("FLOW", "discharge"): 1, ("PRESSURE", "discharge"): 1},
        "TANK": {
            ("LEVEL", "level"): 1,
            ("PRESSURE", "pressure"): 1,
            ("FLOW", "inlet"): 1,
            ("FLOW", "outlet"): 1,
        },
        "VALVE": {("FLOW", "through"): 1},
    }
    for table, key in (("pumps", "pump_id"), ("tanks", "tank_id"), ("valves", "valve_id")):
        kind = table[:-1].upper()
        for equipment_id in master_data[table][key]:
            subset = sensors[sensors["equipment_id"] == equipment_id]
            counts = subset.groupby(["sensor_type", "sensor_role"]).size().to_dict()
            assert counts == expected_roles[kind], equipment_id
    units = {"FLOW": "m3/h", "PRESSURE": "bar", "LEVEL": "%", "TEMPERATURE": "C"}
    assert all(
        sensor.measurement_unit == units[sensor.sensor_type]
        for sensor in sensors.itertuples()
    )
    assert (sensors["sampling_interval_seconds"] == 60).all()
    assert sensors["lifecycle_state"].isin({"ACTIVE", "INACTIVE", "MAINTENANCE"}).all()


def test_telemetry_cadence_uniqueness_and_isolation(pipeline_dir):
    telemetry = pd.read_csv(pipeline_dir / "telemetry.csv")
    sensors = pd.read_csv(pipeline_dir / "sensors.csv")
    config = Config.load(str(pipeline_dir / "config.json"))

    assert len(telemetry) == len(sensors) * 450
    assert not telemetry.duplicated(["sensor_id", "timestamp"]).any()
    assert not telemetry["telemetry_id"].duplicated().any()
    assert not (FORBIDDEN_TELEMETRY_COLUMNS & set(telemetry.columns))
    assert set(telemetry["sensor_id"]) == set(sensors["sensor_id"])
    assert telemetry["quality_status"].isin({"GOOD", "UNCERTAIN", "BAD", "MISSING"}).all()
    assert pd.to_numeric(telemetry["measured_value"], errors="coerce").notna().all()

    unit_map = sensors.set_index("sensor_id")["measurement_unit"]
    assert (telemetry["sensor_id"].map(unit_map) == telemetry["measurement_unit"]).all()

    timestamps = pd.to_datetime(telemetry["timestamp"])
    expected = pd.date_range(
        start=config.simulation.start_time,
        periods=450,
        freq="60s",
    )
    assert set(timestamps.unique()) == set(expected)
    assert timestamps.min() == expected[0]
    assert timestamps.max() == expected[-1]


def test_scenario_truth_lineage_windows_and_isolation(pipeline_dir):
    scenarios = pd.read_csv(pipeline_dir / "scenario_definitions.csv")
    truth = pd.read_csv(pipeline_dir / "ground_truth.csv")
    telemetry = pd.read_csv(pipeline_dir / "telemetry.csv", usecols=["sensor_id", "timestamp"])
    alarms = pd.read_csv(pipeline_dir / "alarms.csv")
    sensors = set(pd.read_csv(pipeline_dir / "sensors.csv")["sensor_id"])

    assert not scenarios.empty and not truth.empty
    assert scenarios["scenario_id"].is_unique
    assert truth["gt_id"].is_unique
    assert set(scenarios["scenario_id"]) == set(truth["scenario_id"])
    assert len(scenarios) == len(truth)
    assert not ({"scenario_id", "gt_id"} & set(telemetry.columns))
    assert "scenario_id" not in alarms.columns

    truth["start_time"] = pd.to_datetime(truth["start_time"])
    truth["end_time"] = pd.to_datetime(truth["end_time"])
    assert (truth["end_time"] > truth["start_time"]).all()
    assert truth["severity"].isin({"light", "medium", "severe", "normal"}).all()

    positive = truth[truth["issue_type"] != "NORMAL"]
    normal = truth[truth["issue_type"] == "NORMAL"]
    assert not positive.empty and not normal.empty
    for _, left in positive.iterrows():
        for _, right in normal.iterrows():
            assert max(left["start_time"], right["start_time"]) >= min(
                left["end_time"], right["end_time"]
            )
    for row in positive.itertuples():
        expected = json.loads(row.expected_sensor_ids)
        assert expected
        assert set(expected) <= sensors
        assert row.expected_alarm_category in {"PROCESS_FAULT", "SENSOR_FAULT"}
        assert row.expected_detection == "YES"

    # Every sample is covered by a window; windows are half-open and contiguous.
    windows = sorted(
        zip(truth["start_time"], truth["end_time"]), key=lambda item: item[0]
    )
    assert windows[0][0] == pd.Timestamp("2026-01-01T00:00:00")
    for (_, end), (next_start, _) in zip(windows, windows[1:]):
        assert next_start == end
    assert windows[-1][1] == pd.Timestamp("2026-01-01T07:30:00")


def test_alarm_and_history_integrity(pipeline_dir):
    alarms = pd.read_csv(pipeline_dir / "alarms.csv")
    events = pd.read_csv(pipeline_dir / "alarm_events.csv")
    assert not alarms.empty
    assert alarms["alarm_id"].is_unique
    assert alarms["alarm_category"].isin(
        {"PROCESS_FAULT", "SENSOR_FAULT", "UNCERTAIN"}
    ).all()
    assert (pd.to_numeric(alarms["occurrence_count"]) >= 1).all()
    first = pd.to_datetime(alarms["first_detected_at"])
    last = pd.to_datetime(alarms["last_detected_at"])
    assert (first <= last).all()
    assert (first >= pd.Timestamp("2026-01-01T00:00:00")).all()
    assert (last <= pd.Timestamp("2026-01-01T07:30:00")).all()

    assert not events["event_id"].duplicated().any()
    created = set(events.loc[events["event_type"] == "CREATED", "alarm_id"])
    resolved = set(events.loc[events["event_type"] == "RESOLVED", "alarm_id"])
    assert created == set(alarms["alarm_id"])
    assert resolved == set(
        alarms.loc[alarms["alarm_status"] == "RESOLVED", "alarm_id"]
    )
    assert alarm_history_closed_once(events)


def alarm_history_closed_once(events: pd.DataFrame) -> bool:
    counts = (
        events[events["event_type"] == "RESOLVED"]
        .groupby("alarm_id")
        .size()
    )
    return bool((counts <= 1).all())


def test_config_roundtrip_path_independent_hash_and_scale(tmp_path):
    config = Config()
    config.scale = DataScaleConfig.full()
    config.simulation.random_seed = 20261022
    config.scenarios.scenario_set = "compact"
    config.output_dir = str(tmp_path / "a")
    config.database_path = str(tmp_path / "a" / "db.sqlite")
    original = config.get_config_hash()

    path = tmp_path / "config.json"
    config.save(str(path))
    loaded = Config.load(str(path))
    assert loaded.to_dict() == config.to_dict()
    assert loaded.get_config_hash() == original

    loaded.output_dir = str(tmp_path / "b")
    loaded.database_path = str(tmp_path / "b" / "db.sqlite")
    assert loaded.get_config_hash() == original

    loaded.simulation.random_seed += 1
    assert loaded.get_config_hash() != original

    assert config.scale.facilities == 3
    assert config.scale.pumps == 20
    assert config.scale.tanks == 30
    assert config.scale.valves == 60
    expected_sensors = 20 * 2 + 30 * 4 + 60
    assert expected_sensors == 220
    # 100,000 = 120 sensors x 455 samples + 100 sensors x 454 samples.
    assert 120 * 455 + 100 * 454 == 100_000
    loaded.simulation.telemetry_target_rows = 100_000
    assert loaded.get_config_hash() != original


def test_version_consistency(pipeline_dir):
    config = Config.load(str(pipeline_dir / "config.json"))
    run = pd.read_csv(pipeline_dir / "simulation_runs.csv").iloc[-1]
    assert __schema_version__ == "2.0.0"
    assert __generator_version__ == "2.0.0"
    assert SCHEMA_VERSION == __schema_version__
    assert config.schema_version == __schema_version__
    assert config.generator_version == __generator_version__
    assert run["schema_version"] == __schema_version__
    assert run["generator_version"] == __generator_version__

    manifest = json.loads((pipeline_dir / "run_manifest.json").read_text())
    assert manifest["schema_version"] == __schema_version__
    assert manifest["package_version"] == __schema_version__


def test_manifest_hashes_match_files(pipeline_dir):
    manifest = json.loads((pipeline_dir / "run_manifest.json").read_text())
    for name, entry in manifest["files"].items():
        path = Path(pipeline_dir) / name
        assert path.exists(), name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == entry["sha256"], name


def test_sqlite_export_integrity_and_row_counts(pipeline_dir):
    config = Config.load(str(pipeline_dir / "config.json"))
    db = Database(config.database_path)
    try:
        assert db.integrity_check() == "ok"
        assert db.foreign_key_violations() == []
        tables = set(db.table_names())
        expected = {
            "facilities",
            "pumps",
            "tanks",
            "valves",
            "pipes",
            "sensors",
            "operating_modes",
            "simulation_runs",
            "equipment_state_events",
            "scenario_definitions",
            "telemetry",
            "ground_truth",
            "alarms",
            "alarm_events",
            "alarm_incidents",
            "evaluation_metrics",
            "evaluation_events",
            "validation_results",
        }
        assert expected <= tables
        for table in sorted(expected):
            csv_path = Path(pipeline_dir) / f"{table}.csv"
            csv_rows = len(pd.read_csv(csv_path)) if csv_path.exists() else 0
            assert db.get_table_count(table) == csv_rows, table
        assert db.scalar("SELECT COUNT(*) FROM telemetry") == 36 * 450
        assert db.scalar(
            "SELECT COUNT(*) FROM sensors WHERE sensor_role NOT IN "
            "('discharge','level','pressure','inlet','outlet','through')"
        ) == 0
    finally:
        db.close()


def test_evaluation_artifact_keeps_scopes_separate(pipeline_dir):
    result = json.loads((pipeline_dir / "evaluation_metrics.json").read_text())
    assert result["event_level"]["status"] == "EVALUATED"
    assert result["point_level"]["status"] == "EVALUATED"
    assert result["evaluation_units"]["event"] != result["evaluation_units"]["point"]
    assert "combined" not in result["event_level"]
    assert result["event_level"]["false_positives"] == result["event_level"][
        "false_alarm_incident_count"
    ]
    assert result["point_level"]["confusion_matrix"]["false_positives"] >= 0
    assert result["event_level"]["matching_policy"]["false_alarm_unit"] == "unmatched alarm incident"


def test_validator_accepts_generated_dataset(pipeline_dir):
    config = Config.load(str(pipeline_dir / "config.json"))
    validator = Validator(config=config)
    results = validator.validate_dataset(str(pipeline_dir))
    statuses = {row["status"] for row in results}
    assert statuses == {"PASS"}, [
        row for row in results if row["status"] != "PASS"
    ]
    ids = {row["test_case_id"] for row in results}
    assert {
        "PK-SENSORS",
        "SENSOR-COMPOSITION",
        "SENSOR-COUNT",
        "TELEMETRY-CADENCE",
        "SCENARIO-WINDOW-DISJOINT",
        "PHYSICS-TANK-MASS-BALANCE",
        "ALARM-HISTORY-COMPLETE",
        "EVENT-FP-UNIT",
        "POINT-UNKNOWN-EXCLUDED",
        "ZERO-DENOMINATOR",
        "DETECTOR-ISOLATION",
        "SQLITE-INTEGRITY",
    } <= ids
    assert len(results) == 87

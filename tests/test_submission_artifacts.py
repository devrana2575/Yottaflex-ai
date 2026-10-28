"""Submission artifacts: exact row budget, JSON/SQL exports, state history."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from yottaflex.config import Config
from yottaflex.exports import EXPORT_TABLES, export_json_tables, export_sql_seed
from yottaflex.state_history import (
    ALLOWED_TRANSITIONS,
    EVENT_COLUMNS,
    transition_allowed,
    validate_state_events,
)


def test_exact_100k_cadence_and_foreign_keys(baseline_100k_dir):
    config = Config.load(str(baseline_100k_dir / "config.json"))
    telemetry = pd.read_csv(baseline_100k_dir / "telemetry.csv")
    sensors = pd.read_csv(baseline_100k_dir / "sensors.csv")
    runs = pd.read_csv(baseline_100k_dir / "simulation_runs.csv")
    metadata = json.loads((baseline_100k_dir / "simulation_metadata.json").read_text())

    assert config.simulation.telemetry_target_rows == 100_000
    assert len(telemetry) == 100_000
    assert telemetry["telemetry_id"].is_unique
    assert not telemetry.duplicated(["sensor_id", "timestamp"]).any()
    assert set(telemetry["sensor_id"]) == set(sensors["sensor_id"])
    assert set(telemetry["simulation_run_id"]) == set(runs["simulation_run_id"])
    assert set(telemetry["operating_mode_id"]) <= set(
        pd.read_csv(baseline_100k_dir / "operating_modes.csv")["operating_mode_id"]
    )
    counts = telemetry.groupby("sensor_id").size()
    assert counts.value_counts().to_dict() == {455: 120, 454: 100}
    assert metadata["total_records"] == 100_000
    assert metadata["sample_count_distribution"] == {"454": 100, "455": 120}

    timestamps = pd.to_datetime(telemetry["timestamp"])
    assert timestamps.is_monotonic_increasing
    start = pd.Timestamp(config.simulation.start_time)
    interval = pd.Timedelta(seconds=config.simulation.sampling_interval_seconds)
    for sensor_id, subset in telemetry.groupby("sensor_id"):
        sensor_times = pd.to_datetime(subset["timestamp"]).sort_values()
        assert sensor_times.iloc[0] == start, sensor_id
        assert (sensor_times.diff().dropna() == interval).all(), sensor_id
        assert len(sensor_times) in {454, 455}


def test_json_sqlite_and_sql_seed_preserve_ids(pipeline_dir, tmp_path):
    json_dir = tmp_path / "json"
    sql_path = tmp_path / "seed.sql"
    manifest = export_json_tables(pipeline_dir, json_dir)
    sql_manifest = export_sql_seed(pipeline_dir, sql_path)
    assert set(manifest["tables"]) == set(EXPORT_TABLES) & {
        path.stem for path in pipeline_dir.glob("*.csv")
    }
    assert not Path(manifest["source_root"]).is_absolute()
    assert sql_manifest["path"] == "seed.sql"
    assert sql_manifest["rows"]["telemetry"] == 36 * 450

    telemetry_csv = pd.read_csv(pipeline_dir / "telemetry.csv")
    telemetry_json = pd.DataFrame(json.loads((json_dir / "telemetry.json").read_text()))
    assert telemetry_csv["telemetry_id"].tolist() == telemetry_json["telemetry_id"].tolist()

    seed_db = tmp_path / "seed.db"
    conn = sqlite3.connect(seed_db)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(sql_path.read_text(encoding="utf-8"))
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0] == 36 * 450
        sql_ids = [row[0] for row in conn.execute("SELECT telemetry_id FROM telemetry ORDER BY rowid")]
        assert sql_ids == telemetry_csv["telemetry_id"].tolist()
        assert conn.execute("SELECT COUNT(*) FROM equipment_state_events").fetchone()[0] > 0
    finally:
        conn.close()


def test_equipment_state_history_is_append_only_and_valid(baseline_100k_dir):
    events = pd.read_csv(baseline_100k_dir / "equipment_state_events.csv")
    master = {
        name: pd.read_csv(baseline_100k_dir / f"{name}.csv")
        for name in ("facilities", "pumps", "tanks", "valves", "sensors")
    }
    config = Config.load(str(baseline_100k_dir / "config.json"))
    run = pd.read_csv(baseline_100k_dir / "simulation_runs.csv").iloc[-1]
    scenarios = pd.read_csv(baseline_100k_dir / "scenario_definitions.csv")
    assert list(events.columns) == EVENT_COLUMNS
    assert len(events) == 341
    assert events["event_id"].is_unique
    assert set(events["source"]) <= {"SIMULATION", "SCENARIO", "OPERATOR", "SYSTEM"}
    assert set(events["equipment_type"]) == {"FACILITY", "PUMP", "TANK", "VALVE", "SENSOR"}
    initializations = events.loc[events["previous_state"] == "UNKNOWN"]
    assert len(initializations) == 333
    assert initializations["equipment_id"].is_unique
    assert set(initializations["equipment_id"]) == set(
        pd.concat(
            [
                master["facilities"]["facility_id"],
                master["pumps"]["pump_id"],
                master["tanks"]["tank_id"],
                master["valves"]["valve_id"],
                master["sensors"]["sensor_id"],
            ]
        )
    )
    assert (initializations["source"] == "SIMULATION").all()
    injected = scenarios.loc[scenarios["issue_type"] != "NORMAL", "scenario_id"]
    assert set(events["source_reference"]) >= set(injected)
    errors = validate_state_events(
        events,
        master,
        str(run["simulation_run_id"]),
        config.simulation.start_time,
        run["end_time"],
    )
    assert errors == []
    for row in events.itertuples():
        assert (row.previous_state, row.new_state) in ALLOWED_TRANSITIONS[row.equipment_type]
        assert row.state_value == row.new_state


def test_invalid_state_transition_is_rejected():
    assert not transition_allowed("PUMP", "ACTIVE", "LEAKING")
    assert not transition_allowed("SENSOR", "UNKNOWN", "OPEN")
    assert transition_allowed("PUMP", "ACTIVE", "DEGRADED")
    assert transition_allowed("TANK", "LEAKING", "ACTIVE")


def test_state_history_validation_catches_bad_transition(baseline_100k_dir):
    events = pd.read_csv(baseline_100k_dir / "equipment_state_events.csv")
    master = {
        name: pd.read_csv(baseline_100k_dir / f"{name}.csv")
        for name in ("facilities", "pumps", "tanks", "valves", "sensors")
    }
    config = Config.load(str(baseline_100k_dir / "config.json"))
    run = pd.read_csv(baseline_100k_dir / "simulation_runs.csv").iloc[-1]
    broken = events.copy()
    index = broken.index[broken["equipment_type"] == "PUMP"][0]
    broken.loc[index, "new_state"] = "LEAKING"
    errors = validate_state_events(
        broken,
        master,
        str(run["simulation_run_id"]),
        config.simulation.start_time,
        run["end_time"],
    )
    assert any("forbidden transition" in error for error in errors)

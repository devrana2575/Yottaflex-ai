"""Targeted detector tests: persistence, hysteresis, grouping, modes and isolation."""

from __future__ import annotations

import warnings

import pandas as pd

from yottaflex.config import Config
from yottaflex.detection import DetectionEngine, PROCESS_FAULT, SENSOR_FAULT, _EpisodeTracker
from yottaflex.id_generator import IDGenerator


def _tracker(config: Config, **overrides) -> _EpisodeTracker:
    payload = {
        "config": config,
        "id_gen": IDGenerator(),
        "simulation_run_id": "SIM-TEST",
        "rule_id": "RULE-TEST",
        "alarm_type": "Test alarm",
        "category": PROCESS_FAULT,
        "severity": "HIGH",
        "equipment_id": "PUMP-001",
        "sensor_id": "SNS-001",
        "evidence_base": "test evidence",
        "persistence_seconds": 120,
        "persistence_samples": 3,
    }
    payload.update(overrides)
    return _EpisodeTracker(**payload)


def test_persistence_and_hysteresis_close_episode():
    config = Config()
    tracker = _tracker(config)
    start = pd.Timestamp("2026-01-01T00:00:00")
    tracker.feed(start, False)
    tracker.feed(start + pd.Timedelta(minutes=1), True, 1.0)
    tracker.feed(start + pd.Timedelta(minutes=2), True, 2.0)
    assert tracker.episodes == []
    tracker.feed(start + pd.Timedelta(minutes=3), True, 3.0)
    assert len(tracker.episodes) == 1
    episode = tracker.episodes[0]
    assert episode["first_detected_at"] == "2026-01-01T00:03:00"
    assert episode["peak_value"] == 3.0

    tracker.feed(start + pd.Timedelta(minutes=4), False)
    assert tracker.episodes[0]["alarm_status"] == "ACTIVE"
    tracker.feed(start + pd.Timedelta(minutes=5), False)
    assert tracker.episodes[0]["alarm_status"] == "RESOLVED"
    assert len(tracker.episodes) == 1
    assert [event["event_type"] for event in tracker.history] == ["CREATED", "RESOLVED"]


def test_peak_timestamp_tracks_extreme_not_last_reading():
    tracker = _tracker(Config(), peak_mode="absmax")
    start = pd.Timestamp("2026-01-01T00:00:00")
    for minute, value in enumerate((1.0, 2.0, 3.0, 5.0, 4.0)):
        tracker.feed(start + pd.Timedelta(minutes=minute), True, value)
    episode = tracker.episodes[0]
    assert episode["peak_value"] == 5.0
    assert episode["peak_at"] == "2026-01-01T00:03:00"


def test_short_dropout_does_not_split_episode():
    config = Config()
    tracker = _tracker(config, suppress_modes=())
    start = pd.Timestamp("2026-01-01T00:00:00")
    for minute in range(4):
        tracker.feed(start + pd.Timedelta(minutes=minute), True, 1.0)
    assert len(tracker.episodes) == 1
    tracker.feed(start + pd.Timedelta(minutes=4), False)
    tracker.feed(start + pd.Timedelta(minutes=5), True, 1.0)
    assert len(tracker.episodes) == 1
    assert tracker._open is not None


def test_mode_suppression_prevents_process_alarm():
    config = Config()
    tracker = _tracker(config, suppress_modes=("STARTUP",))
    start = pd.Timestamp("2026-01-01T00:00:00")
    for minute in range(5):
        tracker.feed(start + pd.Timedelta(minutes=minute), True, 1.0, mode="STARTUP")
    assert tracker.episodes == []
    tracker.feed(start + pd.Timedelta(minutes=5), True, 1.0, mode="NORMAL")
    tracker.feed(start + pd.Timedelta(minutes=6), True, 1.0, mode="NORMAL")
    tracker.feed(start + pd.Timedelta(minutes=7), True, 1.0, mode="NORMAL")
    assert len(tracker.episodes) == 1


def test_missing_rows_raise_sensor_gap_alarm():
    config = Config()
    sensors = pd.DataFrame(
        [
            {
                "sensor_id": "SNS-001",
                "facility_id": "FAC-001",
                "equipment_id": "PUMP-001",
                "equipment_type": "PUMP",
                "sensor_type": "FLOW",
                "sensor_role": "discharge",
                "measurement_unit": "m3/h",
                "accuracy_tolerance": 1.0,
                "sampling_interval_seconds": 60,
                "lifecycle_state": "ACTIVE",
            }
        ]
    )
    pumps = pd.DataFrame(
        [
            {
                "pump_id": "PUMP-001",
                "facility_id": "FAC-001",
                "nominal_flow_m3_h": 100.0,
                "nominal_head_m": 50.0,
            }
        ]
    )
    telemetry = pd.DataFrame(
        [
            {
                "sensor_id": "SNS-001",
                "timestamp": timestamp,
                "measured_value": 90.0,
                "quality_status": "GOOD",
                "operating_mode_id": None,
            }
            for timestamp in ("2026-01-01T00:00:00", "2026-01-01T00:02:00")
        ]
    )
    engine = DetectionEngine(
        config,
        {"sensors": sensors, "pumps": pumps, "tanks": pd.DataFrame()},
        IDGenerator(),
    )
    alarms = engine.detect("SIM-GAP", telemetry)
    assert not alarms.empty
    gap = alarms[alarms["rule_id"] == "RULE-009"]
    assert len(gap) == 1
    assert gap.iloc[0]["alarm_category"] == SENSOR_FAULT
    assert gap.iloc[0]["sensor_id"] == "SNS-001"


def test_missing_mode_defaults_to_normal_without_deprecation_warning():
    config = Config()
    sensors = pd.DataFrame(
        [
            {
                "sensor_id": "SNS-001",
                "facility_id": "FAC-001",
                "equipment_id": "PUMP-001",
                "equipment_type": "PUMP",
                "sensor_type": "FLOW",
                "sensor_role": "discharge",
                "measurement_unit": "m3/h",
                "accuracy_tolerance": 1.0,
                "sampling_interval_seconds": 60,
                "lifecycle_state": "ACTIVE",
            }
        ]
    )
    pumps = pd.DataFrame(
        [
            {
                "pump_id": "PUMP-001",
                "facility_id": "FAC-001",
                "nominal_flow_m3_h": 100.0,
                "nominal_head_m": 50.0,
            }
        ]
    )
    telemetry = pd.DataFrame(
        [
            {
                "sensor_id": "SNS-001",
                "timestamp": "2026-01-01T00:00:00",
                "measured_value": 90.0,
                "quality_status": "GOOD",
                "operating_mode_id": float("nan"),
            }
        ]
    )
    engine = DetectionEngine(
        config,
        {"sensors": sensors, "pumps": pumps, "tanks": pd.DataFrame()},
        IDGenerator(),
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        frame = engine._frame("SNS-001", telemetry)
    assert frame["mode"].tolist() == ["NORMAL"]


def test_detector_ignores_ground_truth_columns(pipeline_dir):
    telemetry = pd.read_csv(pipeline_dir / "telemetry.csv")
    config = Config.load(str(pipeline_dir / "config.json"))
    master = {
        name: pd.read_csv(pipeline_dir / f"{name}.csv")
        for name in ("sensors", "pumps", "tanks", "operating_modes")
    }
    observed_columns = [
        "sensor_id",
        "timestamp",
        "measured_value",
        "quality_status",
        "operating_mode_id",
    ]
    observed = telemetry[observed_columns].head(5000).copy()
    poisoned = observed.copy()
    poisoned["scenario_id"] = "LEAK"
    poisoned["ground_truth_id"] = "GT-LEAK"
    poisoned["physical_state_value"] = -1.0
    clean_engine = DetectionEngine(config, master, IDGenerator(seed=config.simulation.random_seed))
    clean = clean_engine.detect("SIM-TEST", observed)
    dirty_engine = DetectionEngine(config, master, IDGenerator(seed=config.simulation.random_seed))
    dirty = dirty_engine.detect("SIM-TEST", poisoned)
    columns = ["rule_id", "equipment_id", "sensor_id", "alarm_category", "first_detected_at"]
    assert clean[columns].reset_index(drop=True).equals(dirty[columns].reset_index(drop=True))
    assert "scenario_id" not in clean.columns


def test_sensor_faults_do_not_match_process_category(pipeline_dir):
    alarms = pd.read_csv(pipeline_dir / "alarms.csv")
    truth = pd.read_csv(pipeline_dir / "ground_truth.csv")
    sensor_truth = truth[truth["issue_type"] == "SENSOR_FAULT"]
    assert not sensor_truth.empty
    for _, event in sensor_truth.iterrows():
        overlapping = alarms[
            (alarms["equipment_id"] == event["affected_equipment_id"])
            & (pd.to_datetime(alarms["first_detected_at"]) < pd.Timestamp(event["end_time"]))
            & (pd.to_datetime(alarms["last_detected_at"]) >= pd.Timestamp(event["start_time"]))
        ]
        assert set(overlapping["alarm_category"]) <= {SENSOR_FAULT, "UNCERTAIN"}

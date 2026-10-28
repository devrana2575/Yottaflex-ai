"""Scenario-set, injection and ~100k-row configuration tests."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from yottaflex.config import Config, DataScaleConfig
from yottaflex.id_generator import IDGenerator
from yottaflex.scenarios import (
    SCENARIO_MATRIX,
    ScenarioInjector,
    ScenarioPlan,
    get_scenario_plans,
)


def _minimal_master() -> dict[str, pd.DataFrame]:
    return {
        "facilities": pd.DataFrame(
            [
                {
                    "facility_id": "FAC-001",
                    "facility_name": "Test Facility",
                    "location_code": "TEST",
                    "lifecycle_state": "ACTIVE",
                }
            ]
        ),
        "tanks": pd.DataFrame(
            [
                {
                    "tank_id": "TANK-001",
                    "facility_id": "FAC-001",
                    "tank_name": "TK-001",
                    "capacity_m3": 100.0,
                    "height_m": 10.0,
                    "initial_level_pct": 50.0,
                    "lifecycle_state": "ACTIVE",
                }
            ]
        ),
        "sensors": pd.DataFrame(
            [
                {
                    "sensor_id": "SNS-LEVEL",
                    "facility_id": "FAC-001",
                    "equipment_id": "TANK-001",
                    "equipment_type": "TANK",
                    "sensor_type": "LEVEL",
                    "sensor_role": "level",
                    "measurement_unit": "%",
                    "sampling_interval_seconds": 60,
                    "accuracy_tolerance": 0.5,
                    "lifecycle_state": "ACTIVE",
                },
                {
                    "sensor_id": "SNS-PRESSURE",
                    "facility_id": "FAC-001",
                    "equipment_id": "TANK-001",
                    "equipment_type": "TANK",
                    "sensor_type": "PRESSURE",
                    "sensor_role": "pressure",
                    "measurement_unit": "bar",
                    "sampling_interval_seconds": 60,
                    "accuracy_tolerance": 1.0,
                    "lifecycle_state": "ACTIVE",
                },
                {
                    "sensor_id": "SNS-INLET",
                    "facility_id": "FAC-001",
                    "equipment_id": "TANK-001",
                    "equipment_type": "TANK",
                    "sensor_type": "FLOW",
                    "sensor_role": "inlet",
                    "measurement_unit": "m3/h",
                    "sampling_interval_seconds": 60,
                    "accuracy_tolerance": 1.0,
                    "lifecycle_state": "ACTIVE",
                },
                {
                    "sensor_id": "SNS-OUTLET",
                    "facility_id": "FAC-001",
                    "equipment_id": "TANK-001",
                    "equipment_type": "TANK",
                    "sensor_type": "FLOW",
                    "sensor_role": "outlet",
                    "measurement_unit": "m3/h",
                    "sampling_interval_seconds": 60,
                    "accuracy_tolerance": 1.0,
                    "lifecycle_state": "ACTIVE",
                },
            ]
        ),
    }


def _baseline(minutes: int = 30) -> pd.DataFrame:
    rows = []
    timestamps = pd.date_range("2026-01-01T00:00:00", periods=minutes, freq="60s")
    for timestamp in timestamps:
        for sensor_id, value in (
            ("SNS-LEVEL", 50.0),
            ("SNS-PRESSURE", 0.49),
            ("SNS-INLET", 2.0),
            ("SNS-OUTLET", 2.0),
        ):
            rows.append(
                {
                    "telemetry_id": f"TEL-{len(rows) + 1:012d}",
                    "sensor_id": sensor_id,
                    "simulation_run_id": "SIM-TEST",
                    "timestamp": timestamp.isoformat(),
                    "measured_value": value,
                    "physical_state_value": value,
                    "measurement_unit": "%" if sensor_id == "SNS-LEVEL" else ("bar" if sensor_id == "SNS-PRESSURE" else "m3/h"),
                    "quality_status": "GOOD",
                    "operating_mode_id": "OPM-002",
                }
            )
    return pd.DataFrame(rows)


def _config() -> Config:
    config = Config()
    config.scale = DataScaleConfig.starter()
    config.simulation.start_time = "2026-01-01T00:00:00"
    config.simulation.duration_hours = 0.5
    config.simulation.sampling_interval_seconds = 60
    config.simulation.time_step_seconds = 60
    config.scenarios.include_normal_windows = True
    return config


def _plan(name: str, fault_type: str, start: float = 0.1, end: float = 0.2) -> ScenarioPlan:
    return ScenarioPlan(
        name,
        "SENSOR_FAULT",
        "TANK",
        0,
        start,
        end,
        "medium",
        "SENSOR_FAULT",
        sensor_role="level",
        sensor_fault_type=fault_type,
        parameters={"bias_pct": 5.0, "missing_minutes": 6},
        expected_observable="unit test fault",
    )


@pytest.mark.parametrize("name", sorted(SCENARIO_MATRIX))
def test_scenario_sets_are_well_formed(name):
    plans = get_scenario_plans(name)
    assert plans
    assert len({plan.key for plan in plans}) == len(plans)
    max_end = 7.5 if name == "compact" else 24.0
    for plan in plans:
        assert 0 <= plan.start_hour < plan.end_hour <= max_end
        assert plan.severity in {"light", "medium", "severe", "normal"}
        assert plan.expected_category in {"PROCESS_FAULT", "SENSOR_FAULT"}
        assert plan.expected_observable
    assert all(plan.issue_type != "NORMAL" for plan in plans)


def test_calibration_and_evaluation_are_distinct_sets():
    calibration = get_scenario_plans("calibration")
    evaluation = get_scenario_plans("evaluation")
    assert {plan.issue_type for plan in calibration} == {
        "LEAK",
        "BLOCKAGE",
        "PUMP_DEGRADATION",
        "SENSOR_FAULT",
    }
    assert {plan.issue_type for plan in evaluation} == {
        "LEAK",
        "BLOCKAGE",
        "PUMP_DEGRADATION",
        "SENSOR_FAULT",
    }
    calibration_faults = {
        plan.sensor_fault_type for plan in calibration if plan.issue_type == "SENSOR_FAULT"
    }
    assert calibration_faults == {"bias", "drift", "stuck", "missing"}
    calibration_windows = {
        (plan.issue_type, plan.equipment_index, plan.start_hour, plan.end_hour)
        for plan in calibration
    }
    evaluation_windows = {
        (plan.issue_type, plan.equipment_index, plan.start_hour, plan.end_hour)
        for plan in evaluation
    }
    assert calibration_windows.isdisjoint(evaluation_windows)
    assert {plan.severity for plan in evaluation} == {"light", "medium", "severe"}
    assert {plan.severity for plan in calibration} <= {"light", "medium", "severe"}


def test_compact_set_fits_7_5_hours():
    plans = get_scenario_plans("compact")
    assert max(plan.end_hour for plan in plans) <= 7.5
    assert {plan.issue_type for plan in plans} == {
        "LEAK",
        "BLOCKAGE",
        "PUMP_DEGRADATION",
        "SENSOR_FAULT",
    }


def test_bias_injection_changes_only_measured_level(monkeypatch):
    monkeypatch.setitem(SCENARIO_MATRIX, "unit_bias", [_plan("U-BIAS", "bias")])
    config = _config()
    config.scenarios.scenario_set = "unit_bias"
    baseline = _baseline()
    original = baseline.copy()
    injector = ScenarioInjector(config, _minimal_master(), IDGenerator(seed=1))
    telemetry, scenarios, truth = injector.generate_scenarios("SIM-TEST", baseline)

    assert original.equals(baseline)  # injector must not mutate its input
    assert len(telemetry) == len(baseline)
    assert "scenario_id" not in telemetry.columns
    window = (pd.to_datetime(telemetry["timestamp"]) >= pd.Timestamp("2026-01-01T00:06:00")) & (
        pd.to_datetime(telemetry["timestamp"]) < pd.Timestamp("2026-01-01T00:12:00")
    )
    level = telemetry[window & (telemetry["sensor_id"] == "SNS-LEVEL")]
    assert len(level) == 6
    residual = level["measured_value"] - level["physical_state_value"]
    assert ((residual - 5.0).abs() < 1e-9).all()
    other = telemetry[window & (telemetry["sensor_id"] != "SNS-LEVEL")]
    assert (other["measured_value"] == other["physical_state_value"]).all()

    assert len(scenarios) == 1 + len(
        [row for row in truth.itertuples() if row.issue_type == "NORMAL"]
    )
    row = truth[truth["issue_type"] == "SENSOR_FAULT"].iloc[0]
    assert row["affected_sensor_id"] == "SNS-LEVEL"
    assert json.loads(row["expected_sensor_ids"]) == ["SNS-LEVEL"]
    assert row["expected_alarm_category"] == "SENSOR_FAULT"
    assert row["expected_detection"] == "YES"

    normal = truth[truth["issue_type"] == "NORMAL"]
    assert not normal.empty
    assert normal["expected_detection"].eq("NO").all()
    assert normal["expected_alarm_category"].eq("NORMAL").all()
    # Explicit NORMAL windows cover exactly the complement of the anomaly.
    intervals = sorted(
        zip(pd.to_datetime(truth["start_time"]), pd.to_datetime(truth["end_time"]))
    )
    assert intervals[0][0] == pd.Timestamp("2026-01-01T00:00:00")
    assert intervals[-1][1] == pd.Timestamp("2026-01-01T00:30:00")
    for (_, end), (next_start, _) in zip(intervals, intervals[1:]):
        assert next_start == end


def test_missing_injection_removes_exact_window(monkeypatch):
    monkeypatch.setitem(SCENARIO_MATRIX, "unit_missing", [_plan("U-MISSING", "missing")])
    config = _config()
    config.scenarios.scenario_set = "unit_missing"
    baseline = _baseline()
    injector = ScenarioInjector(config, _minimal_master(), IDGenerator(seed=1))
    telemetry, _, truth = injector.generate_scenarios("SIM-TEST", baseline)

    assert len(telemetry) == len(baseline) - 6
    level_times = pd.to_datetime(
        telemetry.loc[telemetry["sensor_id"] == "SNS-LEVEL", "timestamp"]
    )
    missing_start = pd.Timestamp("2026-01-01T00:06:00")
    missing_end = pd.Timestamp("2026-01-01T00:12:00")
    assert not ((level_times >= missing_start) & (level_times < missing_end)).any()
    assert len(level_times) == 24
    # Missingness is represented by absent rows, not by a quality flag.
    assert (telemetry["quality_status"] == "GOOD").all()
    assert truth[truth["issue_type"] == "SENSOR_FAULT"].iloc[0]["affected_sensor_id"] == "SNS-LEVEL"


def test_scenario_injection_is_deterministic(monkeypatch):
    monkeypatch.setitem(SCENARIO_MATRIX, "unit_bias", [_plan("U-BIAS", "bias")])
    config = _config()
    config.scenarios.scenario_set = "unit_bias"
    baseline = _baseline()
    first = ScenarioInjector(config, _minimal_master(), IDGenerator(seed=7)).generate_scenarios(
        "SIM-TEST", baseline
    )
    second = ScenarioInjector(config, _minimal_master(), IDGenerator(seed=7)).generate_scenarios(
        "SIM-TEST", baseline
    )
    pd.testing.assert_frame_equal(first[0], second[0])
    pd.testing.assert_frame_equal(first[1], second[1])
    pd.testing.assert_frame_equal(first[2], second[2])


def test_baseline_is_exactly_100k_and_detected(baseline_100k_dir):
    telemetry = pd.read_csv(
        baseline_100k_dir / "telemetry.csv", usecols=["sensor_id", "timestamp"]
    )
    sensors = pd.read_csv(baseline_100k_dir / "sensors.csv")
    metrics = json.loads((baseline_100k_dir / "evaluation_metrics.json").read_text())
    config = json.loads((baseline_100k_dir / "config.json").read_text())
    assert len(telemetry) == 100_000
    assert telemetry["sensor_id"].nunique() == 220
    assert len(sensors) == 220
    assert config["simulation"]["telemetry_target_rows"] == 100_000
    counts = telemetry.groupby("sensor_id").size()
    assert counts.value_counts().to_dict() == {455: 120, 454: 100}
    assert counts.sum() == 100_000
    assert pd.read_csv(baseline_100k_dir / "facilities.csv").shape[0] == 3
    assert pd.read_csv(baseline_100k_dir / "pumps.csv").shape[0] == 20
    assert pd.read_csv(baseline_100k_dir / "tanks.csv").shape[0] == 30
    assert pd.read_csv(baseline_100k_dir / "valves.csv").shape[0] == 60
    event = metrics["event_level"]
    assert event["positive_event_count"] == 4
    assert event["true_positives"] == 4
    assert event["false_negatives"] == 0
    assert event["false_positives"] == 0
    assert event["f1_score"] == 1.0
    assert metrics["point_level"]["status"] == "EVALUATED"

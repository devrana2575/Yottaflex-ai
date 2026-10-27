"""Evaluation methodology tests: units, matching, labels and zero denominators."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from yottaflex.config import Config
from yottaflex.evaluation import Evaluator, PROCESS_FAULT, SENSOR_FAULT


def _gt(
    gt_id: str,
    issue_type: str,
    start: str,
    end: str,
    equipment: str | None = None,
    sensor: str | None = None,
    sensors: list[str] | None = None,
    category: str = PROCESS_FAULT,
    severity: str = "medium",
    expected: str = "YES",
) -> dict:
    return {
        "gt_id": gt_id,
        "issue_type": issue_type,
        "severity": severity,
        "affected_equipment_id": equipment,
        "affected_sensor_id": sensor,
        "expected_sensor_ids": json.dumps(sensors or ([] if sensor is None else [sensor])),
        "start_time": start,
        "end_time": end,
        "expected_detection": expected,
        "expected_alarm_category": category,
    }


def _alarm(
    alarm_id: str,
    equipment: str,
    sensor: str | None,
    start: str,
    end: str,
    category: str = PROCESS_FAULT,
    rule: str = "RULE-006",
) -> dict:
    return {
        "alarm_id": alarm_id,
        "equipment_id": equipment,
        "sensor_id": sensor,
        "alarm_category": category,
        "severity": "HIGH",
        "rule_id": rule,
        "first_detected_at": start,
        "last_detected_at": end,
    }


def _telemetry(rows: list[tuple[str, str, float | None]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "sensor_id": sensor,
                "timestamp": timestamp,
                "measured_value": value,
                "quality_status": "GOOD" if value is not None else "MISSING",
            }
            for sensor, timestamp, value in rows
        ]
    )


def test_zero_denominators_return_none_not_zero():
    evaluator = Evaluator(Config())
    normal_only = pd.DataFrame(
        [
            _gt(
                "GT-NORMAL",
                "NORMAL",
                "2026-01-01T00:00:00",
                "2026-01-01T00:10:00",
                category="NORMAL",
                expected="NO",
            )
        ]
    )
    result = evaluator.evaluate(pd.DataFrame(), normal_only)
    event = result["event_level"]
    assert event["true_positives"] == 0
    assert event["false_positives"] == 0
    assert event["precision"] is None
    assert event["recall"] is None
    assert event["f1_score"] is None

    positive_only = pd.DataFrame(
        [
            _gt(
                "GT-1",
                "LEAK",
                "2026-01-01T00:00:00",
                "2026-01-01T00:10:00",
                "TANK-001",
                "SNS-1",
            )
        ]
    )
    result = evaluator.evaluate(pd.DataFrame(), positive_only)
    event = result["event_level"]
    assert event["true_positives"] == 0
    assert event["false_negatives"] == 1
    assert event["precision"] is None  # TP + FP == 0
    assert event["recall"] == 0.0
    assert event["f1_score"] is None
    assert event["false_positives"] == 0


def test_overlapping_alarm_rows_merge_to_one_incident():
    evaluator = Evaluator(Config())
    gt = pd.DataFrame(
        [
            _gt(
                "GT-1",
                "LEAK",
                "2026-01-01T00:00:00",
                "2026-01-01T00:10:00",
                "TANK-001",
                "SNS-1",
            ),
            _gt(
                "GT-NORMAL",
                "NORMAL",
                "2026-01-01T00:10:00",
                "2026-01-01T00:20:00",
                category="NORMAL",
                expected="NO",
            ),
        ]
    )
    alarms = pd.DataFrame(
        [
            _alarm("A1", "TANK-001", "SNS-1", "2026-01-01T00:01:00", "2026-01-01T00:04:00"),
            _alarm("A2", "TANK-001", "SNS-1", "2026-01-01T00:03:00", "2026-01-01T00:06:00"),
        ]
    )
    result = evaluator.evaluate(alarms, gt)
    event = result["event_level"]
    assert event["true_positives"] == 1
    assert event["false_negatives"] == 0
    assert event["false_positives"] == 0
    assert event["alarm_incident_count"] == 1
    assert event["matched_alarm_event_count"] == 2
    assert event["corroborating_alarm_event_count"] == 1
    assert event["precision"] == 1.0
    assert event["recall"] == 1.0


def test_one_incident_matches_at_most_one_event():
    evaluator = Evaluator(Config())
    gt = pd.DataFrame(
        [
            _gt(
                "GT-1",
                "LEAK",
                "2026-01-01T00:00:00",
                "2026-01-01T00:05:00",
                "TANK-001",
                "SNS-1",
            ),
            _gt(
                "GT-2",
                "LEAK",
                "2026-01-01T00:20:00",
                "2026-01-01T00:25:00",
                "TANK-001",
                "SNS-1",
            ),
        ]
    )
    alarms = pd.DataFrame(
        [
            _alarm(
                "A1",
                "TANK-001",
                "SNS-1",
                "2026-01-01T00:00:00",
                "2026-01-01T00:25:00",
            )
        ]
    )
    result = evaluator.evaluate(alarms, gt)
    event = result["event_level"]
    assert event["alarm_incident_count"] == 1
    assert event["true_positives"] == 1
    assert event["false_negatives"] == 1
    assert event["false_positives"] == 0
    assert event["precision"] == 1.0
    assert event["recall"] == 0.5


def test_late_alarm_is_false_alarm_incident_and_missed_event():
    config = Config()
    config.evaluation.process_latency_seconds = 600
    evaluator = Evaluator(config)
    gt = pd.DataFrame(
        [
            _gt(
                "GT-1",
                "LEAK",
                "2026-01-01T00:00:00",
                "2026-01-01T00:05:00",
                "TANK-001",
                "SNS-1",
            ),
            _gt(
                "GT-NORMAL",
                "NORMAL",
                "2026-01-01T00:05:00",
                "2026-01-01T01:00:00",
                category="NORMAL",
                expected="NO",
            ),
        ]
    )
    alarms = pd.DataFrame(
        [
            _alarm(
                "A-LATE",
                "TANK-001",
                "SNS-1",
                "2026-01-01T00:20:00",
                "2026-01-01T00:30:00",
            )
        ]
    )
    result = evaluator.evaluate(alarms, gt)
    event = result["event_level"]
    assert event["true_positives"] == 0
    assert event["false_negatives"] == 1
    assert event["false_positives"] == 1
    assert event["false_positive_window_count"] == 1
    assert event["false_positive_rate"] == 1.0
    incidents = evaluator.incidents_df
    assert incidents.iloc[0]["classification"] == "FALSE_ALARM"
    assert incidents.iloc[0]["assigned_normal_gt_id"] == "GT-NORMAL"


def test_sensor_truth_is_not_matched_by_process_only_alarm():
    evaluator = Evaluator(Config())
    gt = pd.DataFrame(
        [
            _gt(
                "GT-SENSOR",
                "SENSOR_FAULT",
                "2026-01-01T00:00:00",
                "2026-01-01T00:10:00",
                "TANK-001",
                "SNS-1",
                category=SENSOR_FAULT,
            )
        ]
    )
    alarms = pd.DataFrame(
        [
            _alarm(
                "A-PROCESS",
                "TANK-001",
                "SNS-1",
                "2026-01-01T00:02:00",
                "2026-01-01T00:05:00",
                category=PROCESS_FAULT,
            )
        ]
    )
    result = evaluator.evaluate(alarms, gt)
    event = result["event_level"]
    assert event["true_positives"] == 0
    assert event["false_negatives"] == 1
    assert event["matched_incident_count"] == 0
    assert result["per_event"][0]["outcome"] == "MISSED"


def test_sensor_truth_matches_sensor_alarm_within_sensor_latency():
    config = Config()
    config.evaluation.sensor_latency_seconds = 3600
    evaluator = Evaluator(config)
    gt = pd.DataFrame(
        [
            _gt(
                "GT-SENSOR",
                "SENSOR_FAULT",
                "2026-01-01T00:00:00",
                "2026-01-01T00:10:00",
                "TANK-001",
                "SNS-1",
                category=SENSOR_FAULT,
            )
        ]
    )
    alarms = pd.DataFrame(
        [
            _alarm(
                "A-SENSOR",
                "TANK-001",
                "SNS-1",
                "2026-01-01T00:30:00",
                "2026-01-01T00:40:00",
                category=SENSOR_FAULT,
                rule="RULE-010",
            )
        ]
    )
    result = evaluator.evaluate(alarms, gt)
    event = result["event_level"]
    assert event["true_positives"] == 1
    assert event["detection_latency_seconds"]["mean"] == 1800.0


def test_point_labels_explicit_and_half_open():
    evaluator = Evaluator(Config())
    gt = pd.DataFrame(
        [
            _gt(
                "GT-1",
                "LEAK",
                "2026-01-01T00:00:00",
                "2026-01-01T00:02:00",
                "TANK-001",
                "SNS-1",
            ),
            _gt(
                "GT-NORMAL",
                "NORMAL",
                "2026-01-01T00:02:00",
                "2026-01-01T00:04:00",
                category="NORMAL",
                expected="NO",
            ),
        ]
    )
    telemetry = _telemetry(
        [
            ("SNS-1", "2026-01-01T00:00:00", 50.0),
            ("SNS-1", "2026-01-01T00:01:00", 49.0),
            ("SNS-1", "2026-01-01T00:02:00", 48.0),
            ("SNS-1", "2026-01-01T00:03:00", 47.0),
        ]
    )
    alarms = pd.DataFrame(
        [_alarm("A1", "TANK-001", "SNS-1", "2026-01-01T00:00:00", "2026-01-01T00:01:00")]
    )
    result = evaluator.evaluate(alarms, gt, telemetry_df=telemetry)
    point = result["point_level"]
    assert point["positive_rows"] == 2
    assert point["negative_rows"] == 2
    assert point["unknown_samples"] == 0
    confusion = point["confusion_matrix"]
    assert confusion["true_positives"] == 2
    assert confusion["false_positives"] == 0
    assert confusion["true_negatives"] == 2
    assert confusion["false_negatives"] == 0


def test_unknown_point_labels_are_excluded_not_counted_as_negatives():
    evaluator = Evaluator(Config())
    gt = pd.DataFrame(
        [
            _gt(
                "GT-1",
                "LEAK",
                "2026-01-01T00:00:00",
                "2026-01-01T00:01:00",
                "TANK-001",
                "SNS-1",
            )
        ]
    )
    telemetry = _telemetry(
        [
            ("SNS-1", "2026-01-01T00:00:00", 50.0),
            ("SNS-1", "2026-01-01T00:05:00", 45.0),
            ("SNS-1", "2026-01-01T00:06:00", 44.0),
        ]
    )
    alarms = pd.DataFrame(
        [_alarm("A1", "TANK-001", "SNS-1", "2026-01-01T00:00:00", "2026-01-01T00:06:00")]
    )
    result = evaluator.evaluate(alarms, gt, telemetry_df=telemetry)
    point = result["point_level"]
    assert point["labelled_rows"] == 1
    assert point["unknown_samples"] == 2
    assert point["unknown_predictions"] == 2
    confusion = point["confusion_matrix"]
    assert confusion["true_positives"] == 1
    assert confusion["false_positives"] == 0
    assert confusion["true_negatives"] == 0
    assert confusion["false_negatives"] == 0


def test_missing_measurements_are_excluded_from_point_denominator():
    evaluator = Evaluator(Config())
    gt = pd.DataFrame(
        [
            _gt(
                "GT-1",
                "LEAK",
                "2026-01-01T00:00:00",
                "2026-01-01T00:03:00",
                "TANK-001",
                "SNS-1",
            )
        ]
    )
    telemetry = _telemetry(
        [
            ("SNS-1", "2026-01-01T00:00:00", 50.0),
            ("SNS-1", "2026-01-01T00:01:00", None),
            ("SNS-1", "2026-01-01T00:02:00", 48.0),
        ]
    )
    result = evaluator.evaluate(pd.DataFrame(), gt, telemetry_df=telemetry)
    point = result["point_level"]
    assert point["positive_rows"] == 2
    assert point["unobserved_labelled_rows"] == 1
    assert point["positive_rows_observed"] == 2
    assert point["positive_rows_expected"] == 3.0
    assert point["positive_row_coverage"] == pytest.approx(2.0 / 3.0)
    assert point["confusion_matrix"]["false_negatives"] == 2


def test_event_breakdowns_and_invalid_windows():
    evaluator = Evaluator(Config())
    gt = pd.DataFrame(
        [
            _gt(
                "GT-1",
                "LEAK",
                "2026-01-01T00:00:00",
                "2026-01-01T00:10:00",
                "TANK-001",
                "SNS-1",
                severity="light",
            ),
            _gt(
                "GT-2",
                "BLOCKAGE",
                "2026-01-01T00:20:00",
                "2026-01-01T00:30:00",
                "PUMP-001",
                "SNS-2",
                severity="severe",
            ),
            {
                **_gt("GT-BAD", "LEAK", "2026-01-01T01:00:00", "2026-01-01T00:30:00"),
            },
        ]
    )
    alarms = pd.DataFrame(
        [
            _alarm("A1", "TANK-001", "SNS-1", "2026-01-01T00:02:00", "2026-01-01T00:08:00"),
            _alarm(
                "A2",
                "PUMP-001",
                "SNS-2",
                "2026-01-01T00:21:00",
                "2026-01-01T00:28:00",
                rule="RULE-007",
            ),
        ]
    )
    result = evaluator.evaluate(alarms, gt)
    assert len(result["invalid_ground_truth_events"]) == 1
    assert result["by_scenario_type"]["LEAK"]["detected"] == 1
    assert result["by_scenario_type"]["BLOCKAGE"]["recall"] == 1.0
    assert result["by_severity"]["light"]["injected"] == 1
    assert result["by_severity"]["severe"]["detected"] == 1

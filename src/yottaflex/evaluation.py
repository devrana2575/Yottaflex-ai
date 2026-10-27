"""Detection evaluation with separate point-level and event-level scopes.

Point level
    One observation = one (sensor, timestamp) sample.  Labels come only from
    explicit ground-truth windows.  Timestamps without a positive or normal
    window are UNKNOWN and are excluded from all denominators.

Event level
    One unit = one alarm incident (overlapping alarm episodes for the same
    equipment merged) and one ground-truth event.  Matching is one-to-one,
    category-aware, sensor-aware where applicable, and limited by a documented
    detection latency.  Repeated alarm rows for one incident cannot inflate TP.

Metrics use ``None`` whenever a denominator is zero.  No metric defaults to a
favourable zero.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd

from .config import Config, EvaluationConfig

PROCESS_FAULT = "PROCESS_FAULT"
SENSOR_FAULT = "SENSOR_FAULT"
UNCERTAIN = "UNCERTAIN"
NORMAL = "NORMAL"
POSITIVE = "POSITIVE"
NEGATIVE = "NEGATIVE"


def _safe_div(numerator: float, denominator: float) -> Optional[float]:
    if denominator is None or denominator == 0:
        return None
    return float(numerator) / float(denominator)


def _f1(precision: Optional[float], recall: Optional[float]) -> Optional[float]:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return None
    return 2.0 * precision * recall / (precision + recall)


def _mean(values: Sequence[float]) -> Optional[float]:
    return float(np.mean(values)) if values else None


def _median(values: Sequence[float]) -> Optional[float]:
    return float(np.median(values)) if values else None


def _as_list(value: Any) -> List[str]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            return [text]
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        return [str(parsed)]
    return [str(value)]


def _category_from_rule(rule_id: str) -> str:
    if rule_id == "RULE-006U":
        return UNCERTAIN
    if rule_id in {"RULE-003", "RULE-004", "RULE-008", "RULE-009", "RULE-010"}:
        return SENSOR_FAULT
    return PROCESS_FAULT


@dataclass
class PreparedEvent:
    index: int
    gt_id: str
    issue_type: str
    severity: str
    equipment_id: Optional[str]
    sensor_id: Optional[str]
    expected_sensors: List[str]
    start: pd.Timestamp
    end: pd.Timestamp
    expected_category: str
    expected_detection: str
    is_positive: bool
    is_normal: bool


class Evaluator:
    """Evaluate alarm episodes against explicit ground-truth windows."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.eval_config: EvaluationConfig = self.config.evaluation
        self.incidents_df = pd.DataFrame()
        self.events_df = pd.DataFrame()

    # ------------------------------------------------------------------
    # Preparation
    # ------------------------------------------------------------------
    def _prepare_ground_truth(self, ground_truth_df: pd.DataFrame) -> Tuple[List[PreparedEvent], List[Dict[str, Any]]]:
        required = {"start_time", "end_time", "issue_type"}
        missing = required - set(ground_truth_df.columns)
        if missing:
            raise ValueError(f"Ground truth is missing columns: {sorted(missing)}")
        events: List[PreparedEvent] = []
        invalid: List[Dict[str, Any]] = []
        for position, (_, row) in enumerate(ground_truth_df.iterrows()):
            start = pd.to_datetime(row["start_time"], errors="coerce")
            end = pd.to_datetime(row["end_time"], errors="coerce")
            gt_id = str(row.get("gt_id", f"GT-ROW-{position + 1:06d}"))
            if pd.isna(start) or pd.isna(end) or end < start:
                invalid.append(
                    {
                        "gt_id": gt_id,
                        "reason": "invalid_time_window",
                        "start_time": str(row.get("start_time")),
                        "end_time": str(row.get("end_time")),
                    }
                )
                continue
            issue_type = str(row.get("issue_type", "UNKNOWN")).upper()
            expected_detection = str(row.get("expected_detection", "YES" if issue_type != NORMAL else "NO")).upper()
            expected_category = str(
                row.get(
                    "expected_alarm_category",
                    NORMAL if issue_type == NORMAL else PROCESS_FAULT,
                )
            ).upper()
            is_normal = issue_type == NORMAL or expected_detection == "NO"
            is_positive = expected_detection == "YES" and not is_normal
            sensors = _as_list(row.get("expected_sensor_ids"))
            affected_sensor = row.get("affected_sensor_id")
            if pd.notna(affected_sensor) and str(affected_sensor) not in sensors:
                sensors.append(str(affected_sensor))
            events.append(
                PreparedEvent(
                    index=position,
                    gt_id=gt_id,
                    issue_type=issue_type,
                    severity=str(row.get("severity", "unknown")),
                    equipment_id=(
                        str(row["affected_equipment_id"])
                        if pd.notna(row.get("affected_equipment_id"))
                        else None
                    ),
                    sensor_id=str(affected_sensor) if pd.notna(affected_sensor) else None,
                    expected_sensors=sensors,
                    start=pd.Timestamp(start),
                    end=pd.Timestamp(end),
                    expected_category=expected_category,
                    expected_detection=expected_detection,
                    is_positive=is_positive,
                    is_normal=is_normal,
                )
            )
        return events, invalid

    def _prepare_alarms(self, alarms_df: pd.DataFrame) -> pd.DataFrame:
        if alarms_df is None or alarms_df.empty:
            return pd.DataFrame(
                columns=[
                    "alarm_id",
                    "equipment_id",
                    "sensor_id",
                    "alarm_category",
                    "severity",
                    "rule_id",
                    "first_detected_at",
                    "last_detected_at",
                    "start",
                    "end",
                ]
            )
        required = {"equipment_id", "first_detected_at", "last_detected_at"}
        missing = required - set(alarms_df.columns)
        if missing:
            raise ValueError(f"Alarms are missing columns: {sorted(missing)}")
        frame = alarms_df.copy()
        frame["start"] = pd.to_datetime(frame["first_detected_at"], errors="coerce")
        frame["end"] = pd.to_datetime(frame["last_detected_at"], errors="coerce")
        frame = frame.dropna(subset=["start", "end"]).copy()
        frame = frame[frame["end"] >= frame["start"]]
        if "alarm_category" not in frame:
            frame["alarm_category"] = frame.get("rule_id", "").map(_category_from_rule)
        frame["alarm_category"] = frame["alarm_category"].fillna(
            frame.get("rule_id", "").map(_category_from_rule)
        )
        frame["rule_id"] = frame.get("rule_id", "UNKNOWN")
        frame["sensor_id"] = frame.get("sensor_id", pd.Series([None] * len(frame))).where(
            frame.get("sensor_id", pd.Series([None] * len(frame))).notna(), None
        )
        frame["equipment_id"] = frame["equipment_id"].where(frame["equipment_id"].notna(), None)
        frame["severity"] = frame.get("severity", "UNKNOWN").fillna("UNKNOWN")
        frame["alarm_id"] = frame.get(
            "alarm_id", pd.Series([f"ALARM-ROW-{i:06d}" for i in range(len(frame))], index=frame.index)
        )
        return frame.sort_values(["equipment_id", "start", "end", "alarm_id"]).reset_index(drop=True)

    # ------------------------------------------------------------------
    # Incidents and event matching
    # ------------------------------------------------------------------
    def _build_incidents(self, alarms: pd.DataFrame) -> List[Dict[str, Any]]:
        if alarms.empty:
            return []
        incidents: List[Dict[str, Any]] = []
        merge_gap = pd.Timedelta(seconds=self.eval_config.incident_merge_seconds)
        for equipment_key, group in alarms.groupby(
            alarms["equipment_id"].fillna("__NO_EQUIPMENT__"), sort=True
        ):
            group = group.sort_values(["start", "end"])
            current: Optional[Dict[str, Any]] = None
            for _, alarm in group.iterrows():
                if current is not None and alarm["start"] <= current["end"] + merge_gap:
                    current["end"] = max(current["end"], alarm["end"])
                    current["alarm_ids"].append(str(alarm["alarm_id"]))
                    current["sensor_ids"].add(str(alarm["sensor_id"]) if pd.notna(alarm["sensor_id"]) else None)
                    current["categories"].add(str(alarm["alarm_category"]))
                    current["rules"].add(str(alarm["rule_id"]))
                    current["severities"].add(str(alarm["severity"]))
                    continue
                if current is not None:
                    incidents.append(current)
                current = {
                    "equipment_id": None if equipment_key == "__NO_EQUIPMENT__" else str(equipment_key),
                    "start": pd.Timestamp(alarm["start"]),
                    "end": pd.Timestamp(alarm["end"]),
                    "alarm_ids": [str(alarm["alarm_id"])],
                    "sensor_ids": {str(alarm["sensor_id"]) if pd.notna(alarm["sensor_id"]) else None},
                    "categories": {str(alarm["alarm_category"])},
                    "rules": {str(alarm["rule_id"])},
                    "severities": {str(alarm["severity"])},
                }
            if current is not None:
                incidents.append(current)
        incidents.sort(key=lambda item: (str(item["equipment_id"]), item["start"], item["end"]))
        for index, incident in enumerate(incidents):
            incident["incident_id"] = f"INC-{index + 1:06d}"
            incident["matched_gt_id"] = None
            incident["classification"] = "UNKNOWN"
            incident["assigned_normal_gt_id"] = None
            incident["latency_seconds"] = None
        return incidents

    def _candidate_latency(self, event: PreparedEvent) -> int:
        if event.expected_category == SENSOR_FAULT:
            return int(self.eval_config.sensor_latency_seconds)
        return int(self.eval_config.process_latency_seconds)

    def _is_candidate(
        self, event: PreparedEvent, incident: Dict[str, Any]
    ) -> Tuple[bool, Optional[float]]:
        if event.equipment_id is not None and incident["equipment_id"] != event.equipment_id:
            return False, None
        if event.expected_sensors:
            incident_sensors = {sensor for sensor in incident["sensor_ids"] if sensor is not None}
            if incident_sensors and not (incident_sensors & set(event.expected_sensors)):
                return False, None
        if self.eval_config.require_category_match:
            if event.expected_category not in incident["categories"]:
                return False, None
        latency = (incident["start"] - event.start).total_seconds()
        if latency < -self.eval_config.pre_event_tolerance_seconds:
            return False, None
        if latency > self._candidate_latency(event):
            return False, None
        if incident["end"] < event.start - pd.Timedelta(seconds=self.eval_config.pre_event_tolerance_seconds):
            return False, None
        return True, latency

    def _match_events(
        self, positives: List[PreparedEvent], incidents: List[Dict[str, Any]]
    ) -> None:
        candidates: List[Tuple[float, pd.Timestamp, str, int, int, float]] = []
        for event_index, event in enumerate(positives):
            for incident_index, incident in enumerate(incidents):
                eligible, latency = self._is_candidate(event, incident)
                if not eligible:
                    continue
                score = max(0.0, float(latency))
                candidates.append(
                    (score, event.start, event.gt_id, event_index, incident_index, float(latency))
                )
        candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4]))
        matched_events: Set[int] = set()
        matched_incidents: Set[int] = set()
        for _, _, _, event_index, incident_index, latency in candidates:
            if event_index in matched_events or incident_index in matched_incidents:
                continue
            matched_events.add(event_index)
            matched_incidents.add(incident_index)
            incident = incidents[incident_index]
            incident["matched_gt_id"] = positives[event_index].gt_id
            incident["classification"] = "MATCHED"
            incident["latency_seconds"] = max(0.0, latency)
            positives[event_index].__dict__["matched_incident_id"] = incident["incident_id"]
            positives[event_index].__dict__["latency_seconds"] = max(0.0, latency)

    @staticmethod
    def _overlap_seconds(start_a: pd.Timestamp, end_a: pd.Timestamp, start_b: pd.Timestamp, end_b: pd.Timestamp) -> float:
        latest_start = max(start_a, start_b)
        earliest_end = min(end_a, end_b)
        return max(0.0, (earliest_end - latest_start).total_seconds())

    def _classify_incidents(
        self,
        positives: List[PreparedEvent],
        normals: List[PreparedEvent],
        incidents: List[Dict[str, Any]],
    ) -> None:
        for incident in incidents:
            if incident["classification"] == "MATCHED":
                continue
            best_normal = None
            best_overlap = 0.0
            for normal_event in normals:
                overlap = self._overlap_seconds(
                    incident["start"], incident["end"], normal_event.start, normal_event.end
                )
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_normal = normal_event
            overlaps_positive = any(
                self._overlap_seconds(
                    incident["start"], incident["end"], event.start, event.end
                )
                > 0
                for event in positives
            )
            if best_normal is not None:
                incident["classification"] = "FALSE_ALARM"
                incident["assigned_normal_gt_id"] = best_normal.gt_id
            elif overlaps_positive:
                incident["classification"] = "FALSE_ALARM"
            else:
                incident["classification"] = "UNKNOWN"

    # ------------------------------------------------------------------
    # Point-level evaluation
    # ------------------------------------------------------------------
    def _point_level(
        self,
        positives: List[PreparedEvent],
        normals: List[PreparedEvent],
        alarms: pd.DataFrame,
        telemetry_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        policy = {
            "positive_class": (
                "A (sensor, timestamp) sample inside an explicit injected-anomaly window "
                "for that sensor's expected observable. One sample = one unit."
            ),
            "negative_class": (
                "A (sensor, timestamp) sample inside an explicit NORMAL ground-truth window. "
                "Unlabelled samples are UNKNOWN and excluded."
            ),
            "timestamp_matching": "Exact sample timestamp equality; alarm episodes cover first..last detected timestamps inclusive.",
            "missing_label_policy": "Unknown labels are excluded and counted; a missing measurement is excluded even inside a labelled window.",
            "missing_measurement_policy": "Rows with null measured_value or quality_status=MISSING are excluded as unobserved.",
        }
        if telemetry_df is None or telemetry_df.empty:
            return {
                "status": "NOT_EVALUATED",
                "reason": "Telemetry was not supplied to the evaluator.",
                "policy": policy,
            }
        required = {"sensor_id", "timestamp"}
        missing = required - set(telemetry_df.columns)
        if missing:
            return {
                "status": "NOT_EVALUATED",
                "reason": f"Telemetry is missing {sorted(missing)}",
                "policy": policy,
            }
        frame = telemetry_df.copy()
        frame["ts"] = pd.to_datetime(frame["timestamp"], errors="coerce")
        frame = frame.dropna(subset=["ts"]).sort_values(["ts", "sensor_id"]).reset_index(drop=True)
        frame["label"] = None
        frame["label_category"] = None

        for event in normals:
            mask = (frame["ts"] >= event.start) & (frame["ts"] < event.end)
            frame.loc[mask & frame["label"].isna(), "label"] = NEGATIVE
            frame.loc[mask & frame["label"].isna(), "label_category"] = NORMAL

        positive_rows_observed = 0
        positive_rows_expected = 0.0
        interval = max(int(self.config.simulation.sampling_interval_seconds), 1)
        for event in positives:
            sensors = event.expected_sensors
            if not sensors:
                continue
            expected_samples = (
                (event.end - event.start).total_seconds() / interval
            ) * len(sensors)
            positive_rows_expected += expected_samples
            mask = (
                frame["sensor_id"].isin(sensors)
                & (frame["ts"] >= event.start)
                & (frame["ts"] < event.end)
            )
            frame.loc[mask, "label"] = POSITIVE
            frame.loc[mask, "label_category"] = event.expected_category
            positive_rows_observed += int(mask.sum())

        # Predictions: every alarm episode covers its sensor's sample range.
        for column in ("pred_any", "pred_process", "pred_sensor", "pred_uncertain"):
            frame[column] = False
        for _, alarm in alarms.iterrows():
            if pd.isna(alarm.get("sensor_id")):
                continue
            mask = (
                (frame["sensor_id"] == alarm["sensor_id"])
                & (frame["ts"] >= alarm["start"])
                & (frame["ts"] <= alarm["end"])
            )
            category = str(alarm["alarm_category"])
            frame.loc[mask, "pred_any"] = True
            if category == PROCESS_FAULT:
                frame.loc[mask, "pred_process"] = True
            elif category == SENSOR_FAULT:
                frame.loc[mask, "pred_sensor"] = True
            elif category == UNCERTAIN:
                frame.loc[mask, "pred_uncertain"] = True

        observed = frame["label"].notna()
        if "measured_value" in frame:
            observed &= pd.to_numeric(frame["measured_value"], errors="coerce").notna()
        if "quality_status" in frame:
            observed &= frame["quality_status"].fillna("MISSING") != "MISSING"
        unknown_predictions = int(
            (frame["label"].isna() & frame["pred_any"]).sum()
        )
        # Unknown labels are excluded from every confusion-matrix denominator.
        evaluated = frame[observed & frame["label"].notna()].copy()

        def confusion(
            mask_label: Optional[pd.Series] = None,
            prediction_column: str = "pred_any",
            only_category: Optional[str] = None,
        ):
            subset = evaluated
            if only_category is not None:
                # A category metric must not count positives from the other
                # category as false negatives. Only this category's positives
                # and the explicit normal negatives form the denominator.
                subset = evaluated[
                    (evaluated["label"] == NEGATIVE)
                    | (evaluated["label_category"] == only_category)
                ]
            elif mask_label is not None:
                subset = evaluated[mask_label]
            if subset.empty:
                return {
                    "true_positives": 0,
                    "false_positives": 0,
                    "true_negatives": 0,
                    "false_negatives": 0,
                    "precision": None,
                    "recall": None,
                    "f1_score": None,
                    "false_positive_rate": None,
                }
            positive = subset["label"] == POSITIVE
            predicted = subset[prediction_column].astype(bool)
            tp = int((positive & predicted).sum())
            fp = int(((~positive) & predicted).sum())
            tn = int(((~positive) & (~predicted)).sum())
            fn = int((positive & (~predicted)).sum())
            precision = _safe_div(tp, tp + fp)
            recall = _safe_div(tp, tp + fn)
            return {
                "true_positives": tp,
                "false_positives": fp,
                "true_negatives": tn,
                "false_negatives": fn,
                "precision": precision,
                "recall": recall,
                "f1_score": _f1(precision, recall),
                "false_positive_rate": _safe_div(fp, fp + tn),
            }

        overall = confusion()
        process_metrics = confusion(
            prediction_column="pred_process", only_category=PROCESS_FAULT
        )
        sensor_metrics = confusion(
            prediction_column="pred_sensor", only_category=SENSOR_FAULT
        )
        label_counts = {
            str(key): int(value) for key, value in evaluated["label"].value_counts().items()
        }
        coverage = (
            float(positive_rows_observed) / positive_rows_expected
            if positive_rows_expected > 0
            else None
        )
        return {
            "status": "EVALUATED",
            "positive_class": policy["positive_class"],
            "policy": policy,
            "confusion_matrix": overall,
            "overall": overall,
            "process_faults": process_metrics,
            "sensor_faults": sensor_metrics,
            "labelled_rows": int(len(evaluated)),
            "positive_rows": int((evaluated["label"] == POSITIVE).sum()),
            "negative_rows": int((evaluated["label"] == NEGATIVE).sum()),
            "label_counts": label_counts,
            "unknown_samples": int((frame["label"].isna()).sum()),
            "unknown_predictions": unknown_predictions,
            "unobserved_labelled_rows": int((frame["label"].notna() & ~observed).sum()),
            "positive_row_coverage": coverage,
            "positive_rows_observed": positive_rows_observed,
            "positive_rows_expected": positive_rows_expected,
            "normal_windows": len(normals),
            "positive_windows": len(positives),
        }

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def evaluate(
        self,
        alarms_df: pd.DataFrame,
        ground_truth_df: pd.DataFrame,
        scenario_defs_df: pd.DataFrame | None = None,
        telemetry_df: pd.DataFrame | None = None,
    ) -> Dict[str, Any]:
        """Calculate separate event- and point-level metrics."""
        if ground_truth_df is None or ground_truth_df.empty:
            return {
                "evaluation_units": {"event": "ground-truth event", "point": "(sensor, timestamp) sample"},
                "event_level": {
                    "status": "NOT_EVALUATED",
                    "reason": "No ground truth scenarios",
                    "metrics": {},
                },
                "point_level": {"status": "NOT_EVALUATED", "reason": "No ground truth scenarios"},
                "by_scenario_type": {},
                "by_category": {},
                "by_severity": {},
                "per_event": [],
                "invalid_ground_truth_events": [],
            }

        events, invalid = self._prepare_ground_truth(ground_truth_df)
        positives = [event for event in events if event.is_positive]
        normals = [event for event in events if event.is_normal]
        alarms = self._prepare_alarms(alarms_df)
        incidents = self._build_incidents(alarms)
        self._match_events(positives, incidents)
        self._classify_incidents(positives, normals, incidents)

        matched_events = [event for event in positives if getattr(event, "matched_incident_id", None)]
        missed_events = [event for event in positives if not getattr(event, "matched_incident_id", None)]
        matched_incidents = [incident for incident in incidents if incident["classification"] == "MATCHED"]
        false_alarm_incidents = [
            incident for incident in incidents if incident["classification"] == "FALSE_ALARM"
        ]
        unknown_incidents = [
            incident for incident in incidents if incident["classification"] == "UNKNOWN"
        ]

        true_positive = len(matched_events)
        false_negative = len(missed_events)
        false_positive_incidents = len(false_alarm_incidents)
        precision = _safe_div(true_positive, true_positive + false_positive_incidents)
        recall = _safe_div(true_positive, true_positive + false_negative)
        f1 = _f1(precision, recall)

        normal_with_false_alarm = {
            incident["assigned_normal_gt_id"]
            for incident in false_alarm_incidents
            if incident["assigned_normal_gt_id"]
        }
        false_positive_windows = len(normal_with_false_alarm)
        true_negative_windows = max(0, len(normals) - false_positive_windows)
        false_positive_rate = _safe_div(
            false_positive_windows, false_positive_windows + true_negative_windows
        )

        matched_alarm_ids: Set[str] = set()
        for incident in matched_incidents:
            matched_alarm_ids.update(incident["alarm_ids"])
        corroborating = len(matched_alarm_ids) - len(matched_incidents)
        latencies = [
            float(getattr(event, "latency_seconds"))
            for event in matched_events
            if getattr(event, "latency_seconds", None) is not None
        ]

        event_level = {
            "status": "EVALUATED",
            "unit": "ground-truth event / alarm incident",
            "ground_truth_event_count": len(events),
            "positive_event_count": len(positives),
            "normal_event_count": len(normals),
            "matched_event_count": true_positive,
            "missed_event_count": false_negative,
            "detection_rate": recall,
            "true_positives": true_positive,
            "false_negatives": false_negative,
            "false_positives": false_positive_incidents,
            "true_negatives": true_negative_windows,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "false_positive_rate": false_positive_rate,
            "false_positive_rate_denominator": "normal windows with an alarm / all normal windows",
            "total_alarm_events": int(len(alarms)),
            "alarm_incident_count": len(incidents),
            "matched_incident_count": len(matched_incidents),
            "unmatched_incident_count": len(false_alarm_incidents) + len(unknown_incidents),
            "false_alarm_incident_count": false_positive_incidents,
            "unknown_incident_count": len(unknown_incidents),
            "unmatched_alarm_event_count": int(len(alarms) - len(matched_alarm_ids)),
            "matched_alarm_event_count": len(matched_alarm_ids),
            "corroborating_alarm_event_count": corroborating,
            "false_positive_window_count": false_positive_windows,
            "true_negative_window_count": true_negative_windows,
            "detection_latency_seconds": {
                "values": latencies,
                "mean": _mean(latencies),
                "median": _median(latencies),
                "min": min(latencies) if latencies else None,
                "max": max(latencies) if latencies else None,
            },
            "matching_policy": {
                "unit": "alarm incident (overlapping alarm episodes for one equipment merged)",
                "one_to_one": True,
                "equipment": "exact affected_equipment_id",
                "sensor": "alarm incident must include the expected sensor when one is defined; ambiguous sensor evidence may match",
                "category": "expected_alarm_category must be present in the incident category set",
                "timing": (
                    "incident onset must be no earlier than event start minus pre-event tolerance "
                    "and no later than event start plus the category-specific permitted latency"
                ),
                "process_latency_seconds": int(self.eval_config.process_latency_seconds),
                "sensor_latency_seconds": int(self.eval_config.sensor_latency_seconds),
                "pre_event_tolerance_seconds": int(self.eval_config.pre_event_tolerance_seconds),
                "duplicate_handling": "alarm grouping plus incident merging; corroborating alarm events are not counted as TP",
                "false_alarm_unit": "unmatched alarm incident",
                "false_positive_rate_unit": "normal ground-truth window with an unmatched incident",
                "ambiguity": (
                    "If one incident overlaps multiple events, a deterministic greedy assignment gives it to the "
                    "closest event; the other event is a false negative. Late alarms are an incident false alarm and "
                    "the event is a false negative. An alarm before the event (outside tolerance) does not count as a "
                    "detection of that event."
                ),
            },
        }

        # Per-event detail ------------------------------------------------
        per_event: List[Dict[str, Any]] = []
        normal_alarm_map: Dict[str, List[str]] = {}
        for incident in false_alarm_incidents:
            if incident["assigned_normal_gt_id"]:
                normal_alarm_map.setdefault(incident["assigned_normal_gt_id"], []).append(
                    incident["incident_id"]
                )
        for event in events:
            matched_id = getattr(event, "matched_incident_id", None)
            row = {
                "gt_id": event.gt_id,
                "issue_type": event.issue_type,
                "severity": event.severity,
                "affected_equipment_id": event.equipment_id,
                "expected_sensors": event.expected_sensors,
                "expected_alarm_category": event.expected_category,
                "start_time": event.start.isoformat(),
                "end_time": event.end.isoformat(),
                "is_positive": event.is_positive,
                "is_normal": event.is_normal,
                "matched": bool(matched_id),
                "matched_incident_id": matched_id,
                "latency_seconds": getattr(event, "latency_seconds", None),
                "outcome": (
                    "DETECTED"
                    if matched_id
                    else ("NORMAL_NO_ALARM" if event.is_normal and event.gt_id not in normal_alarm_map else ("NORMAL_ALARMED" if event.is_normal else "MISSED"))
                ),
            }
            per_event.append(row)

        # Breakdowns ------------------------------------------------------
        def event_breakdown(key: str) -> Dict[str, Any]:
            breakdown: Dict[str, Any] = {}
            groups = sorted({getattr(event, key) for event in positives})
            for value in groups:
                group = [event for event in positives if getattr(event, key) == value]
                detected = [event for event in group if getattr(event, "matched_incident_id", None)]
                group_latencies = [
                    float(getattr(event, "latency_seconds"))
                    for event in detected
                    if getattr(event, "latency_seconds", None) is not None
                ]
                recall_value = _safe_div(len(detected), len(group))
                breakdown[str(value)] = {
                    "injected": len(group),
                    "detected": len(detected),
                    "missed": len(group) - len(detected),
                    "recall": recall_value,
                    "detection_rate": recall_value,
                    "mean_detection_latency_seconds": _mean(group_latencies),
                }
            return breakdown

        point_level = self._point_level(positives, normals, alarms, telemetry_df)
        result = {
            "evaluation_units": {
                "event": "one ground-truth event or alarm incident",
                "point": "one (sensor, timestamp) telemetry sample",
                "note": "Point and event metrics are reported separately and are never combined into one precision value.",
            },
            "event_level": event_level,
            "point_level": point_level,
            "by_scenario_type": event_breakdown("issue_type"),
            "by_category": event_breakdown("expected_category"),
            "by_severity": event_breakdown("severity"),
            "per_event": per_event,
            "invalid_ground_truth_events": invalid,
            "scenario_definitions_present": bool(
                scenario_defs_df is not None and not scenario_defs_df.empty
            ),
        }

        # Incident table for CSV/SQL transparency.
        incident_rows = []
        for incident in incidents:
            incident_rows.append(
                {
                    "incident_id": incident["incident_id"],
                    "simulation_run_id": (
                        str(alarms["simulation_run_id"].iloc[0])
                        if "simulation_run_id" in alarms and not alarms.empty
                        else None
                    ),
                    "equipment_id": incident["equipment_id"],
                    "sensor_ids": json.dumps(sorted(str(s) for s in incident["sensor_ids"] if s is not None)),
                    "categories": json.dumps(sorted(incident["categories"])),
                    "rules": json.dumps(sorted(incident["rules"])),
                    "severity_max": _max_severity(incident["severities"]),
                    "first_detected_at": incident["start"].isoformat(),
                    "last_detected_at": incident["end"].isoformat(),
                    "alarm_count": len(incident["alarm_ids"]),
                    "alarm_ids": json.dumps(sorted(incident["alarm_ids"])),
                    "matched_gt_id": incident["matched_gt_id"],
                    "classification": incident["classification"],
                    "assigned_normal_gt_id": incident["assigned_normal_gt_id"],
                    "latency_seconds": incident["latency_seconds"],
                }
            )
        self.incidents_df = pd.DataFrame(incident_rows)
        self.events_df = pd.DataFrame(per_event)
        return result


def _max_severity(values: Iterable[str]) -> str:
    order = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4, "UNKNOWN": -1}
    return max(values, key=lambda value: order.get(str(value), -1), default="UNKNOWN")

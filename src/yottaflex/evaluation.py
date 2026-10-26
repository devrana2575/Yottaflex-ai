"""Evaluation and metrics calculation."""

from __future__ import annotations

from typing import Any

import pandas as pd


class Evaluator:
    """Evaluate detection performance against ground truth."""
    
    def evaluate(self, alarms_df: pd.DataFrame, ground_truth_df: pd.DataFrame, 
                 scenario_defs_df: pd.DataFrame) -> dict[str, Any]:
        """Calculate evaluation metrics."""
        results = {
            'overall': {},
            'by_scenario_type': {},
            'summary': {}
        }
        
        if ground_truth_df.empty:
            results['summary']['note'] = 'No ground truth scenarios'
            return results
        
        total_injected = len(ground_truth_df)
        matched_alarm_indexes = set()
        detected_scenarios = set()

        required_gt = {"affected_equipment_id", "start_time", "end_time"}
        required_alarms = {
            "equipment_id",
            "first_detected_at",
            "last_detected_at",
        }
        if not required_gt.issubset(ground_truth_df.columns):
            raise ValueError(f"Ground truth is missing {sorted(required_gt - set(ground_truth_df.columns))}")
        if not alarms_df.empty and not required_alarms.issubset(alarms_df.columns):
            raise ValueError(f"Alarms are missing {sorted(required_alarms - set(alarms_df.columns))}")

        for gt_index, gt in ground_truth_df.iterrows():
            start = pd.to_datetime(gt["start_time"], errors="coerce")
            end = pd.to_datetime(gt["end_time"], errors="coerce")
            matches = []
            if pd.notna(start) and pd.notna(end):
                for alarm_index, alarm in alarms_df.iterrows():
                    if alarm["equipment_id"] != gt["affected_equipment_id"]:
                        continue
                    alarm_start = pd.to_datetime(alarm["first_detected_at"], errors="coerce")
                    alarm_end = pd.to_datetime(alarm["last_detected_at"], errors="coerce")
                    if pd.isna(alarm_start) or pd.isna(alarm_end):
                        continue
                    if alarm_start <= end and alarm_end >= start:
                        affected_sensor = gt.get("affected_sensor_id")
                        if pd.notna(affected_sensor) and alarm.get("sensor_id") != affected_sensor:
                            continue
                        matches.append(alarm_index)

            if matches:
                detected_scenarios.add(gt_index)
                matched_alarm_indexes.update(matches)

        detected = len(detected_scenarios)
        missed = total_injected - detected
        false_alarms = len(alarms_df) - len(matched_alarm_indexes)
        
        total_alarms = len(alarms_df)
        detection_rate = detected / total_injected if total_injected > 0 else 0.0
        
        results['overall'] = {
            'true_positives': detected,
            'false_negatives': missed,
            'false_positives': false_alarms,
            'true_negatives': None,
            'precision': detected / (detected + false_alarms) if (detected + false_alarms) > 0 else 0.0,
            'recall': detection_rate,
            'f1_score': 0.0,
            'detection_rate': detection_rate,
            'total_injected': total_injected,
            'total_alarms': total_alarms
        }
        
        if results['overall']['precision'] + results['overall']['recall'] > 0:
            results['overall']['f1_score'] = 2 * (results['overall']['precision'] * results['overall']['recall']) / \
                                           (results['overall']['precision'] + results['overall']['recall'])
        
        # By scenario type
        for issue_type in ground_truth_df['issue_type'].unique():
            gt_st = ground_truth_df[ground_truth_df['issue_type'] == issue_type]
            total_st = len(gt_st)
            detected_st = sum(index in detected_scenarios for index in gt_st.index)
            results['by_scenario_type'][issue_type] = {
                'injected': total_st,
                'detected': detected_st,
                'missed': total_st - detected_st,
                'detection_rate': detected_st / total_st if total_st > 0 else 0.0
            }
        
        results['summary'] = {
            'event_level_detection_rate': detection_rate,
            'missed_scenarios': missed,
            'false_alarms': false_alarms,
            'note': 'Evaluation based on scenario-level association',
            'true_negatives_note': 'Not measurable: the dataset has no defined population of normal events'
        }
        
        return results

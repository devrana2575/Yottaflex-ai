# YottaFlex Evaluation Report

Point-level and event-level metrics are separate units and are not combined.

## Event level

| Metric | Value |
|---|---|
| positive_event_count | 4.0000 |
| matched_event_count | 4.0000 |
| missed_event_count | 0.0000 |
| false_alarm_incident_count | 0.0000 |
| unknown_incident_count | 0.0000 |
| precision | 1.0000 |
| recall | 1.0000 |
| f1_score | 1.0000 |
| false_positive_rate | 0.0000 |

## Point level

| Metric | Value |
|---|---|
| true_positives | 246.0000 |
| false_positives | 5.0000 |
| true_negatives | 40915.0000 |
| false_negatives | 18.0000 |
| precision | 0.9801 |
| recall | 0.9318 |
| f1_score | 0.9553 |
| false_positive_rate | 0.0001 |

## By scenario type

| Type | Injected | Detected | Missed | Recall |
|---|---:|---:|---:|---:|
| BLOCKAGE | 1 | 1 | 0 | 1.0000 |
| LEAK | 1 | 1 | 0 | 1.0000 |
| PUMP_DEGRADATION | 1 | 1 | 0 | 1.0000 |
| SENSOR_FAULT | 1 | 1 | 0 | 1.0000 |

## By severity

| Severity | Injected | Detected | Missed | Recall |
|---|---:|---:|---:|---:|
| light | 1 | 1 | 0 | 1.0000 |
| medium | 3 | 3 | 0 | 1.0000 |

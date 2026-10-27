# YottaFlex Evaluation Report

Point-level and event-level metrics are separate units and are not combined.

## Event level

| Metric | Value |
|---|---|
| positive_event_count | 11.0000 |
| matched_event_count | 10.0000 |
| missed_event_count | 1.0000 |
| false_alarm_incident_count | 0.0000 |
| unknown_incident_count | 0.0000 |
| precision | 1.0000 |
| recall | 0.9091 |
| f1_score | 0.9524 |
| false_positive_rate | 0.0000 |

## Point level

| Metric | Value |
|---|---|
| true_positives | 844.0000 |
| false_positives | 10.0000 |
| true_negatives | 112190.0000 |
| false_negatives | 206.0000 |
| precision | 0.9883 |
| recall | 0.8038 |
| f1_score | 0.8866 |
| false_positive_rate | 0.0001 |

## By scenario type

| Type | Injected | Detected | Missed | Recall |
|---|---:|---:|---:|---:|
| BLOCKAGE | 2 | 2 | 0 | 1.0000 |
| LEAK | 3 | 2 | 1 | 0.6667 |
| PUMP_DEGRADATION | 2 | 2 | 0 | 1.0000 |
| SENSOR_FAULT | 4 | 4 | 0 | 1.0000 |

## By severity

| Severity | Injected | Detected | Missed | Recall |
|---|---:|---:|---:|---:|
| light | 3 | 2 | 1 | 0.6667 |
| medium | 5 | 5 | 0 | 1.0000 |
| severe | 3 | 3 | 0 | 1.0000 |

# Evaluation Methodology (YottaFlex 2.0.0)

## 1. Why there are two evaluations

A single "precision" number cannot describe both:

- **Event level** - did the system find each injected incident, and how many alarm incidents were
  raised when nothing was wrong?
- **Point level** - at each labelled `(sensor, timestamp)` sample, was an alarm active?

The old evaluator mixed these units: it used event-level true positives but raw alarm-row false
positives. That number had no defined denominator and is not used anywhere in 2.0.0. Event and
point results are stored separately in `evaluation_metrics.json`, `evaluation_metrics.csv`, the
Markdown report and the SQLite `evaluation_metrics` table. They are never averaged or combined.

## 2. Ground-truth model

`ground_truth.csv` contains one row per scenario, including explicit `NORMAL` windows:

- `issue_type` is `NORMAL`, `LEAK`, `BLOCKAGE`, `PUMP_DEGRADATION`, or `SENSOR_FAULT`.
- `expected_detection` is `YES` for injected anomalies and `NO` for NORMAL windows.
- `expected_alarm_category` is `PROCESS_FAULT`, `SENSOR_FAULT`, or `NORMAL`.
- `expected_sensor_ids` lists the observable sensor(s) that carry the event.
- `start_time`/`end_time` define a **half-open** interval `[start, end)`.
- `severity` is `light`, `medium`, `severe`, or `normal`.

NORMAL windows are the complement of the merged anomaly intervals, split into chunks. They are
explicit labels, not an assumption that "everything outside an injection is negative". The
validation suite checks that positive and NORMAL windows are disjoint and that their union covers
the run without gaps.

Ground truth is never supplied to the detector. It is joined only after detection, in
`Evaluator`, and is stored in separate tables from telemetry and alarms.

## 3. Event-level evaluation

### 3.1 Alarm incidents

Raw alarm episodes are grouped into **incidents**:

- Group by `equipment_id`.
- Sort by start time.
- Merge two alarms when `next.start <= current.end + incident_merge_seconds`. The default merge
  gap is `0`, so overlapping or exactly touching episodes merge; a positive gap splits them.
- The incident spans the earliest start to the latest end and records all alarm IDs, rules,
  sensors, categories and severities.

This makes the evaluation unit an incident, not an alarm row. Two rules firing on the same pump
during one blockage are one incident with corroborating evidence.

### 3.2 One-to-one matching

For every positive ground-truth event and every incident, a candidate pair is eligible only if:

1. **Equipment** matches exactly (when the event names equipment).
2. **Sensor** overlaps when the event names expected sensors and the incident has known sensor(s).
   An incident with no sensor information can still match; ambiguous sensor evidence is not
   silently discarded.
3. **Category** matches when `require_category_match=true`: the incident's category set must
   contain the event's expected category.
4. **Onset timing** is not earlier than `event.start - 60 s` and not later than
   `event.start + latency_allowance`.
   - Process events: `600 s`.
   - Sensor-fault events: `3,600 s` (slow drift, 30-minute stuck threshold and persistence can
     legitimately take much longer than a process excursion).
5. The incident has not ended before the event began minus the pre-event tolerance.

Candidates are sorted by non-negative onset latency, then event start, `gt_id`, and indices. A
greedy pass assigns each event and each incident at most once. This is deterministic and prevents
one long alarm from claiming several events, or several alarms from inflating one event into
multiple true positives. If two events compete for one incident, the closer onset wins and the
other event is a false negative.

Latency is reported as `max(0, incident.start - event.start)`. An alarm that starts one minute
before the labelled event start is inside the 60 s tolerance and has zero reported latency.

### 3.3 Incident classification

After matching:

| Classification | Rule | Counted as |
|---|---|---|
| `MATCHED` | Assigned to a positive event | One event TP; not an FP |
| `FALSE_ALARM` | Not matched, and overlaps a NORMAL window (assigned to the best-overlap NORMAL window) **or** overlaps a positive event but could not be matched | One event FP |
| `UNKNOWN` | Not matched and overlaps no labelled window | Reported separately, **not** counted as TP or FP |

The "overlaps a positive event but could not be matched" case is important: an alarm during a
sensor fault with a process-only category, or an alarm that starts too early/late, is evidence of a
wrong alarm even though it is near an injected event. It is counted as a false alarm rather than
being excused. `UNKNOWN` incidents are not silently counted as correct; they are reported because
there is insufficient label information to call them either way.

### 3.4 Event metrics

Let:

- `TP` = positive events with a matched incident
- `FN` = positive events without a matched incident
- `FP` = `FALSE_ALARM` incidents
- `TN` = NORMAL windows with no false-alarm incident
- `N_normal` = number of NORMAL windows

Then:

```
precision = TP / (TP + FP)          # None if TP + FP == 0
recall    = TP / (TP + FN)          # None if TP + FN == 0
F1        = 2PR / (P + R)           # None if P or R is None or P + R == 0
FPR       = false_positive_windows / N_normal   # None if N_normal == 0
```

`false_positive_windows` is the number of distinct NORMAL windows that contain at least one
false-alarm incident. Multiple incidents in the same NORMAL window count once for FPR, while each
incident still counts separately in event precision.

The event result also reports:

- positive/normal/matched/missed event counts
- total alarm rows, incident count, matched incident count
- matched and corroborating alarm-row counts
- unmatched alarm-row count (for transparency, **not** the FP denominator)
- false-alarm and unknown incident counts
- latency distribution (mean, median, min, max)
- the complete matching policy
- per-event outcomes (`DETECTED`, `MISSED`, `NORMAL_NO_ALARM`, `NORMAL_ALARMED`)
- breakdowns by scenario type, expected category and severity

## 4. Point-level evaluation

### 4.1 Labels

Each telemetry row is one `(sensor, timestamp)` sample. One sample is one point-evaluation unit.

1. Start with all labels `UNKNOWN`.
2. Assign `NEGATIVE` to samples in explicit `[start, end)` NORMAL windows.
3. Assign `POSITIVE` to samples in explicit `[start, end)` anomaly windows for that event's
   expected sensors. Positive assignment overrides NORMAL at a boundary; windows are validated to
   be disjoint, so this is a safety rule rather than an expected case.
4. Samples outside every window remain `UNKNOWN`.
5. A sample with null `measured_value`, or `quality_status=MISSING`, is **unobserved** and is
   excluded even if its timestamp is labelled.

The evaluation reports `unknown_samples`, `unknown_predictions`, `unobserved_labelled_rows`, and
`positive_row_coverage` (observed positive samples divided by expected samples). It never turns an
unknown into a negative.

### 4.2 Predictions

An alarm episode predicts positive for its own sensor from `first_detected_at` through
`last_detected_at`, inclusive. This is deliberately the detector's actual active interval, not the
ground-truth window. An alarm tail after the physical event ends therefore appears as a point false
positive, and detection latency appears as point false negatives. This is what point-level
evaluation is intended to expose.

### 4.3 Point metrics

On the evaluated samples only:

```
TP = labelled positive and predicted
FP = labelled negative and predicted
TN = labelled negative and not predicted
FN = labelled positive and not predicted

precision = TP / (TP + FP)
recall    = TP / (TP + FN)
F1        = 2PR / (P + R)
FPR       = FP / (FP + TN)
```

Every denominator is explicit. If `TP + FP == 0`, precision is `None`; if `TP + FN == 0`, recall
is `None`; if the positive class is absent, F1 is `None`; if there are no negatives, FPR is `None`.
The code uses a shared safe-division helper, so a zero denominator can never become `0.0` "for
convenience".

Category-specific point metrics restrict the subset to:

- all explicit NORMAL samples, plus
- positive samples whose `label_category` equals the requested category.

Positive samples from the other category are excluded from that category's denominator rather than
counted as false negatives. The overall confusion matrix still includes both categories.

## 5. Worked examples

### Duplicate detection does not inflate an event

Ground truth: one leak on `TANK-001`, `[00:00, 00:10)`.
Alarms: `RULE-002` `[00:01, 00:06)` and `RULE-006` `[00:02, 00:08)`.

The overlapping alarms merge into one incident. Event result: `TP=1`, `FP=0`,
`matched_alarm_event_count=2`, `corroborating_alarm_event_count=1`. The second rule is evidence,
not a second detection.

### One incident cannot match two events

Two events on the same tank at `[00:00, 00:05)` and `[00:20, 00:25)`, with one alarm
`[00:00, 00:25)`. The incident onset is 1,200 s before the second event, outside the 60 s
pre-event tolerance, so it can only match the first event. Result: `TP=1`, `FN=1`, `FP=0`.

### Late alarm

A leak at `[00:00, 00:05)`, a NORMAL window `[00:05, 01:00)`, and an alarm at `[00:20, 00:30)`.
The alarm is later than the 600 s process allowance. Result: the event is `FN`, the incident is a
`FALSE_ALARM` assigned to the NORMAL window, and event precision/recall reflect both.

### Unknown labels are excluded

Ground truth: positive `[00:00, 00:01)` on `SNS-1`; telemetry at `00:00`, `00:05`, `00:06`; alarm
active `[00:00, 00:06)`. Only `00:00` is labelled; `00:05` and `00:06` are `UNKNOWN`. Point result:
`TP=1`, `FP=0`, `TN=0`, `FN=0`, `unknown_samples=2`, `unknown_predictions=2`. Counting the unknown
samples as negatives would fabricate a large false-positive count; excluding them is explicit and
reported.

### Point tail

If the physical leak ends at `00:05` and the episode resolves at `00:07`, samples at `00:05` and
`00:06` are labelled NORMAL (or UNKNOWN outside a NORMAL window) while the alarm is still active.
That is a point FP, not an event FP, because the incident still matches the event. This distinction
is intentional.

## 6. Reproducibility and reporting

Every run writes:

- `evaluation_metrics.json` - full nested result, including policy and per-event detail
- `evaluation_metrics.csv` - flattened EVENT and POINT metrics with explicit `evaluation_level`
- `evaluation_events.csv` - one row per ground-truth event with outcome and latency
- `alarm_incidents.csv` - incident membership, classification and assigned ground truth
- `evaluation_summary.md` - human-readable event/point/scenario/severity tables
- SQLite tables `evaluation_metrics`, `evaluation_events`, `alarm_incidents`

The CSV flattened metrics contain a wall-clock `evaluated_at`; all metric values and event/incident
rows are deterministic for a fixed seed and configuration. The JSON result contains no wall-clock
timestamp and is byte-identical across repeated runs.

## 7. Limitations and interpretation

- Event matching uses onset latency, not full-window overlap. A detector that starts early and
  ends early can still match; duration accuracy is not scored. Point metrics expose duration.
- Category matching is strict. A sensor-fault alarm cannot satisfy a process event even if the
  equipment and time are right, by design.
- Sensor-fault matching allows up to one hour of latency, which is much longer than process
  latency. This reflects the physical evidence (stuck/drift/redundancy) rather than leniency in
  event counting.
- `UNKNOWN` incidents are excluded from precision. The count is always reported; a run with many
  unknown incidents should be interpreted with that caveat.
- A single incident that spans a NORMAL window and a positive event may be classified as a false
  alarm if it cannot match; the per-incident table shows the assignment.
- Ground truth is complete by construction in simulation. Real deployments do not have this
  advantage, and the metrics do not estimate performance on unlabelled real data.
- Point metrics count each sample equally, so long events dominate short events. Event metrics
  count each injected event equally. Neither is "the" correct weighting; they answer different
  questions.

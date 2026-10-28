# Implementation Decisions (2.0.0)

This document records what was changed, why, what evidence supported each change, and what was
deliberately **not** done. The pre-change audit is in
[`baseline_findings.md`](baseline_findings.md); the final evidence is in
[`validation_report.md`](validation_report.md).

## 1. Starting point and constraints

The repository already contained a working 1.x simulator, detector, evaluator, validator, schema
and CLI. The task was to improve and verify it, not to rebuild it. The first action was therefore to
reproduce the baseline from clean output directories:

| Run | Telemetry | Alarm rows | Reported precision | Reported recall | Reported F1 |
|---|---:|---:|---:|---:|---:|
| starter 24 h | 51,840 | 929 | 0.0800 | 1.000 | 0.1481 |
| full 24 h | 316,800 | 1,245 | 0.010638 | 1.000 | 0.021053 |

The reported precision was not a valid event- or point-level statistic. The old evaluator set
event-level `TP=4` but `FP=372` raw unmatched alarm rows and discarded 873 event-overlapping alarm
rows. This mixed an event numerator with a row-level denominator. Fixing evaluation semantics was
the first priority; detector tuning without a valid metric would have been meaningless.

Additional constraints retained from the task:

- Do not suppress alarms or alter denominators to make metrics look good.
- Keep ground truth isolated from detector inputs.
- Do not classify sensor faults as physical process faults without evidence.
- Keep existing tests passing and add targeted tests.
- Preserve the full 316,800-row volume and provide an exact 100,000-row configuration, while
  retaining the earlier 99,000-row compact demonstration.
- Do not publish or push to GitHub without explicit authorization.

## 2. Evaluation decisions

### 2.1 Separate event and point evaluation

**Decision:** Report two independent evaluations, never a combined precision.

**Why:** Events and samples are different units. A long event with many samples cannot be compared
to an injected-event count. The evaluator now emits `event_level` and `point_level` blocks, and the
flattened metrics carry an explicit `evaluation_level`.

**Evidence:** `VALIDATION-SEPARATION`, `EVENT-FP-UNIT`, `POINT-LABEL-CONSISTENCY`; see
`docs/evaluation_methodology.md`.

### 2.2 Event false positives are unmatched incidents

**Decision:** Merge overlapping/touching alarm episodes on the same equipment into incidents;
count only unmatched incidents as false positives.

**Why:** One physical event produced hundreds of raw alarm rows in 1.x. Counting rows made
precision depend on event duration and alarm chatter. Incident-level FP matches the event unit.

**Evidence:** Duplicate-alarm test (`NEG-006`), `EVENT-INCIDENT-ACCOUNTING`,
`INCIDENT-ONE-TO-ONE`, and `alarm_incidents.csv`.

### 2.3 One-to-one category-aware matching with latency

**Decision:** Require equipment, category, sensor overlap (when known), and an onset within a
category-specific latency; assign greedily one-to-one by closest onset.

**Why:** Unconstrained overlap let any rule on the same equipment count as a detection. Category
matching prevents a sensor-quality alarm from satisfying a process event. One-to-one assignment
prevents both duplicate TPs and one alarm claiming several events. See
`docs/evaluation_methodology.md` for the exact order and tie-breaks.

**Latency choices:** Process `600 s`; sensor `3,600 s`; pre-event tolerance `60 s`. The sensor
allowance was fixed before inspecting evaluation results because stuck/drift/redundancy evidence
legitimately takes longer than a process excursion.

### 2.4 Explicit NORMAL windows and UNKNOWN exclusion

**Decision:** Generate explicit NORMAL complement windows, label points half-open, exclude
unlabelled samples from every point denominator, and exclude unobserved samples.

**Why:** Treating "outside an injection" as negative would let any incidental alarm outside a
window inflate FP, and would count sensor outages as normal. Unknown is a third state and is
reported. Positive/NORMAL windows are disjoint and cover the run.

**Evidence:** `SCENARIO-WINDOW-DISJOINT`, `SCENARIO-WINDOW-COVERAGE`, `POINT-UNKNOWN-EXCLUDED`,
`ZERO-DENOMINATOR`.

### 2.5 `None` for undefined metrics

**Decision:** Return `null`/`None` when a denominator is zero.

**Why:** `0.0` precision on a run with no alarms is not a measured precision; it is an undefined
quantity. The validator executes a zero-denominator case rather than only documenting the policy.

## 3. Simulator and scenario decisions

### 3.1 Mass-consistent tank model

**Decision:** Integrate tank level from inlet/outlet flows, derive pressure from hydrostatic head,
and persist inlet/outlet flow sensors.

**Why:** The old level was an unconstrained random walk, pressure was independent, and flow was
not persisted. That made flow-balance validation impossible and caused RULE-002 nuisance alarms.
The new model satisfies `dV/dt = Q_in - Q_out` in normal operation, so a leak creates a real
residual and a sensor bias creates a redundancy disagreement.

**Evidence:** `PHYSICS-HYDROSTATIC-PRESSURE`, `PHYSICS-TANK-MASS-BALANCE`,
`PHYSICS-LEAK-SIGNAL`, `PHYSICS-PUMP-CURVE`, `PHYSICS-PUMP-FAULT-SIGNAL`.

**Boundary decision:** The steady-state mass-balance validation excludes the first sample after a
scenario boundary because removing an injected offset creates a one-sample recovery step. This is a
validation edge effect, not relaxed detector tolerance. The same check would fail on a real
transient; it is documented rather than hidden.

### 3.2 Sensor composition changed without reducing the sensor count

**Decision:** Pumps keep 2 sensors (discharge flow and pressure). Tanks use 4 sensors (level,
pressure, inlet flow, outlet flow). Valves use 1 flow sensor. Full scale remains 220 sensors;
starter remains 36.

**Why:** Flow balance requires both tank flows, and hydrostatic redundancy requires level and
pressure. The total was preserved by reducing redundant valve sensors from two to one flow sensor
and reorganizing tank sensors, so the required 316,800-row full volume is unchanged.

### 3.3 Scenario matrix and calibration/evaluation split

**Decision:** Define five deterministic scenario sets: `default`, `calibration`, `evaluation`,
`compact`, and `baseline`. Calibration and evaluation use different times, equipment and severities.
The historical `compact` set fits in 7.5 hours for the 99,000-row demonstration; the additive
`baseline` set fits in 7.583 hours and omits the row-removing missing-sensor fault so the exact
100,000-row budget survives injection.

**Why:** Tuning and reporting on the same events is overfitting. The evaluation set contains
light, medium and severe leaks/blockages/degradations and all four sensor-fault mechanisms
(bias, drift, stuck, missing). The default set is a demonstration set, not the reported evaluation
set.

**Evidence:** scenario tests, `SCENARIO-*` validation checks, and the final evaluation run.

### 3.4 No injected quality-status label leak

**Decision:** Sensor faults are injected by modifying the measured value (bias, drift, stuck) or by
removing rows (missing). The injector does not set `UNCERTAIN` to mark a fault window.

**Why:** The old sensor-fault detection was reading the injector's label. The detector must earn the
alarm from observed bias, drift, constancy, redundancy disagreement or absence. Quality rules still
exist for real quality flags, but they are not the injected fault signal.

**Evidence:** `PHYSICS-SENSOR-FAULT-SIGNAL`, `NEG-007-IMPLAUSIBLE-SENSOR`, and the sensor-fault
point/event results.

## 4. Detector decisions

### 4.1 Grouped episodes with persistence and hysteresis

**Decision:** Emit one episode per rule/equipment/sensor; require sustained activation; hold
through short dropouts; resolve after clear samples; write CREATED/RESOLVED history.

**Why:** This fixes alarm-row explosion and alarm chatter, and makes event-level membership
well-defined. The tracker now records an ACTIVE episode at activation and mutates the same row to
RESOLVED, so the output is observable before run end and history is append-only.

### 4.2 Mode-aware process rules

**Decision:** Suppress process rules in STARTUP/SHUTDOWN/MAINTENANCE; do not suppress sensor
integrity rules.

**Why:** Low flow and changing levels during ramps are expected. Suppression resets candidate
timers, so an alarm cannot "count" suppressed readings. Sensor faults remain visible in every mode.

### 4.3 Balance rule requires corroboration

**Decision:** RULE-006 fires only when a positive flow residual is accompanied by a level decline.
Without the decline, RULE-006U emits `UNCERTAIN`.

**Why:** A residual can be a flow-sensor bias or an unmeasured leak; the evidence cannot distinguish
them. Calling every residual a process fault would violate the sensor-fault separation requirement.
This is a deliberate uncertainty report, not alarm suppression: RULE-006U is still an alarm, just a
different category.

### 4.4 Pump curve and low-flow rules

**Decision:** Keep a curve-residual rule (flow and pressure) and a five-minute low-flow rule.

**Why:** Low flow alone cannot distinguish blockage from degradation, and a fixed threshold misses
small curve shifts. The curve rule detects both directions and uses the same physical curve as the
simulator; low flow remains a robust gross-loss check.

### 4.5 Redundancy rule attributes ambiguity

**Decision:** A level/pressure disagreement raises SENSOR_FAULT with
`attribution=REDUNDANCY_AMBIGUOUS` but does not assert which sensor is wrong.

**Why:** With two measurements and no third reference, the faulty device is ambiguous. Reporting
certainty would be false. A maintenance investigation is the correct next step.

### 4.6 What was not tuned

The light evaluation leak (`E-LEAK-01`, 1.5% capacity/hour) has a balance residual above the
absolute `5 m3/h` floor, but the 5-minute decline (`-0.131 pp` median) and persistence do not satisfy
RULE-006's corroboration requirement, and RULE-002's `0.30 pp` trigger is not reached for this event. It is
reported as a missed event. Lowering thresholds until it was detected would have been tuning on the
evaluation set and would likely increase false alarms; the corroboration/persistence limitation is
documented instead.

## 5. Data, schema and reporting decisions

- **Schema 2.0.0** adds `tanks.height_m`, `sensors.sensor_role`, alarm category/occurrence/peak/
  attribution fields, scenario/ground-truth `severity` and `expected_sensor_ids`, append-only
  `alarm_events`, `alarm_incidents`, `evaluation_metrics`, `evaluation_events`, and
  `validation_results`. It removes the alarm `scenario_id`, which was a ground-truth leak.
- **SQLite export is recreate-by-default** and exports 18 populated tables into the 19-table schema,
  including validation, evaluation and append-only `equipment_state_events`. The legacy
  `detection_results` table remains empty; `equipment_state_events` now contains real
  initialization and scenario transitions. `export-sql --append` remains available but is not used
  by the default pipeline.
- **SQL analytics** contain 20 statements. Each declares `expect=nonempty` or `expect=zero_rows`,
  and the runner fails the pipeline if an expectation is not met. The queries are read-only.
- **Manifest** records SHA-256 and row counts for output CSVs and `config.json`.
  `validation_results.csv` is excluded because it contains wall-clock timestamps. The manifest
  still includes timestamped `evaluation_metrics.csv` and path-bearing `config.json`, so the
  manifest itself is not byte-identical between output directories; it is evidence, not the
  reproducibility checksum. The deterministic comparison is recorded separately in
  `reports/final/reproducibility.json`.
- **Exact 100k configuration** is
  `--mode full --scenario-set baseline --target-telemetry-rows 100000`. The minimum cadence is
  `ceil(100000/220)=455` steps; 120 lexicographically first sensors receive 455 samples and the
  remaining 100 receive 454. The duration is `455*60 s = 7.5833 h`. Every row is a real
  `(sensor,timestamp)` sample; there is no padding, duplication or silent deletion. The baseline
  set omits the row-removing missing-sensor fault so injection leaves the count exact. The
  historical `compact` configuration remains 220 x 450 = 99,000 rows. The default full run remains
  316,800 rows (220 x 1,440) when no target is configured.
- **State history is append-only and real.** Master-data initialization creates 333 events (3
  facilities + 20 pumps + 30 tanks + 60 valves + 220 sensors), and each injected scenario adds
  start/recovery events. The 100k baseline has 341 rows. `ESE-######` IDs are separate from alarm
  history IDs so existing deterministic alarm outputs are not shifted. State rows are not detector
  input.

## 6. Verification and testing decisions

- Added `tests/conftest.py` with deterministic starter and full-compact fixtures.
- Added targeted tests for detection lifecycle/grouping/mode suppression/isolation, evaluation
  units and edge cases, data integrity, scenario injection, validation/SQL, integration and
  reproducibility.
- Kept the original 11 tests; 51 targeted tests were added. The detection engine still accepts
  telemetry without `operating_mode_id` for backward compatibility.
- Added `pytest.ini` to prevent collection of non-Python `test_out.txt`.
- Validation grew from 18 to 87 executable checks; each result is PASS/FAIL/WARN/NOT_IMPLEMENTED
  and is written to CSV/JSON.
- The 2026-10-27 audit fixed two genuine defects found during re-verification: the operating-mode
  mapping now casts to object before filling the `NORMAL` fallback (removing the pandas 3.1
  deprecation warning), and point coverage now counts only observed positive rows. Regression
  assertions cover both; neither change alters the final evaluation metrics.
- Final remediation test suite: **68 passed** in both the main environment and the 2026-10-28
  fresh virtual environment. The clean environment also reproduced the exact-100k counts and
  metrics; its last-bit float serialization differences are documented in the validation report.

## 7. Alternatives considered and rejected

| Alternative | Why rejected |
|---|---|
| Report event precision using raw alarm rows | Mixes units; the old 1.06% number is the defect being fixed |
| Count every alarm outside a positive window as FP | Treats unknown timestamps as confirmed negatives |
| Drop RULE-002 because it was noisy | The root cause was unphysical level random walk; fix physics and persistence first |
| Set `quality_status=UNCERTAIN` for sensor faults | Label leak; detector would not observe the fault |
| Merge all overlapping alarms across equipment | Would hide simultaneous events on different assets |
| Tune thresholds on the evaluation set | Overfits the reported result; calibration and evaluation are separate |
| Lower thresholds until the light leak is found | Hides a real sensitivity limit and raises false alarms |
| Suppress process alarms during known sensor faults | Requires ground truth at detection time; evaluation should count them |
| Replace the whole 1.x codebase | Unnecessary and risked losing working behavior/tests |

## 8. Known limitations

- The simulator is simplified and synthetic; results do not establish real-plant performance.
- The light evaluation leak is missed because the decline corroboration and persistence do not both
  hold; the balance residual itself is above the absolute floor.
- Point false positives occur at episode tails after anomaly end; point false negatives include
  detection latency and the light leak.
- Sensor-fault localization can be ambiguous between redundant channels.
- Event matching uses onset, not duration; point metrics carry duration/latency information.
- Dependencies are lower-bounded; cross-version float serialization can change peak values at about
  `1e-13` without changing metrics (same-environment reruns are byte-identical).
- No dashboard or real-time streaming was added.
- The 2.0 implementation is commit `6103e1a` on `origin/main` after explicit authorization. The
  2026-10-27 audit corrections were committed and pushed after separate explicit authorization.
  The 2026-10-28 remediation was committed locally and pushed to `origin/main` after the user
  explicitly authorized publication with the prompt `push`. No force-push or history rewrite was
  performed.

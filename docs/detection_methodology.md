# Detection Methodology (YottaFlex 2.0.0)

## 1. Scope and input isolation

The detector consumes **observed telemetry only**:

- `sensor_id`
- `timestamp`
- `measured_value`
- `quality_status`
- `operating_mode_id` (optional)

`DetectionEngine.detect()` explicitly selects these columns and ignores every other column. In
particular it never reads `physical_state_value`, `scenario_id`, `gt_id`, `issue_type`,
`expected_detection`, `expected_sensor_ids`, or `expected_alarm_category`. The validation suite
proves this by poisoning those columns and comparing detector output with and without them. The
detector also receives master metadata (sensor role, pump nominal curve, tank geometry) but not
ground truth.

The detector does not suppress alarms to improve a metric. Thresholds are physical/noise based,
and every alarm episode is written, including episodes that evaluation later classifies as false
alarms.

## 2. Alarm lifecycle

Each rule/equipment/sensor combination has its own `_EpisodeTracker`:

1. **Candidate** - an abnormal condition must be continuously true for both a sample count and a
   time span (`persistence_samples`, `persistence_seconds`). At 60 s cadence, 120 s and 3 samples
   both require three readings. A single spike cannot open an episode.
2. **Activation** - when persistence is met, one episode row is emitted with
   `alarm_status=ACTIVE`, `first_detected_at` equal to the activation reading, and a `CREATED`
   history event.
3. **Continuation** - while the condition remains true, `last_detected_at`, `occurrence_count`,
   and the extreme value are updated. The extreme is selected by `absmax`, `max`, or `min` as
   appropriate for the rule.
4. **Recovery/hysteresis** - rules can use a recovery threshold that is less strict than the
   activation threshold, so a value hovering around the trigger does not chatter.
5. **Clear** - after `clear_samples=2` consecutive inactive readings, or when the inactive gap
   exceeds `grouping_gap_seconds=300`, the episode is marked `RESOLVED` and a `RESOLVED` history
   event is written. A short dropout therefore does not split one incident into several rows.
6. **Run end** - an episode still open at the end of the run is kept as `ACTIVE` and has a
   `CREATED` event but no `RESOLVED` event.

History events are append-only and are not rewritten when later evidence changes. The category
assigned at activation is retained for the life of the episode.

## 3. Rules

All thresholds are defaults in `src/yottaflex/config.py` (`DetectionConfig`) and are copied to
each run's `config.json`.

| Rule | Alarm | Inputs | Activation logic | Recovery / persistence | Category |
|---|---|---|---|---|---|
| RULE-001 | Tank level out of bounds | level | `< 10%` or `> 90%` | exits only inside `[12%, 88%]`; 120 s + 3 samples | PROCESS_FAULT |
| RULE-002 | Rapid tank level decline | level | level fall `>= 0.30` percentage points over a 5-minute regression window | recovery at `>= -0.15` pp; 120 s + 3 samples | PROCESS_FAULT |
| RULE-003 | Sensor stuck | any | value unchanged (`<= 1e-9`) for `>= 30 min` | immediate clear on change; one sample | SENSOR_FAULT |
| RULE-004 | Sensor quality | quality | not `GOOD` (BAD/UNCERTAIN/MISSING) | one sample | SENSOR_FAULT |
| RULE-005 | Pump low-flow deviation | pump flow | 5-minute mean `< 80%` of nominal | recovery `> 85%`; 240 s + 3 samples | PROCESS_FAULT |
| RULE-006 | Tank flow-balance loss | level, pressure, inlet, outlet | 10-minute `R = Q_in - Q_out - dV/dt` above `max(5 m3/h, 8% of mean flow)` **and** corroborated by a level decline of `>= 0.15 pp` | 480 s + 5 samples; process modes suppressed | PROCESS_FAULT |
| RULE-006U | Flow-balance inconsistency | same as RULE-006 | residual above uncertainty but **no** corroborating decline | 480 s + 5 samples | UNCERTAIN |
| RULE-007 | Pump operating point off curve | pump flow, pressure | `|observed head - H(Q)| / H(Q) > 10%` while flow `< 90%` of nominal | recovery `< 6%`; 300 s + 3 samples | PROCESS_FAULT |
| RULE-008 | Implausible reading | any | flow outside `[0, 500] m3/h`, pressure outside `[0, 60] bar`, level outside `[0, 100]%` | one sample | SENSOR_FAULT |
| RULE-009 | Missing telemetry | timestamp gaps | a run of expected samples is absent at the configured cadence | one episode per contiguous gap | SENSOR_FAULT |
| RULE-010 | Level/pressure disagreement | level, pressure | observed level differs from the hydrostatic estimate by `> 4 pp` | 180 s + 3 samples | SENSOR_FAULT |

### 3.1 Rule rationale

- **Tank level and decline** use the measured level, not the simulated physical level. The
  hydrostatic pressure channel is an independent check; a level/pressure disagreement is treated
  as a sensor problem rather than a leak because the source sensor is ambiguous.
- **Flow balance** is the primary leak signal. A residual alone can be caused by a biased flow
  meter, so RULE-006 fires only when the level also declines. Without that corroboration the
  residual is reported as RULE-006U/`UNCERTAIN`, not as a confirmed process fault.
- **Pump curve** compares measured flow and pressure with the same quadratic curve used by the
  simulator. This detects blockages (flow down, pressure up) and degradation (flow and head down)
  without relying on a fixed flow threshold. The flow gate avoids evaluating the curve near
  shutoff where relative error is unstable.
- **Pump low flow** is a complementary five-minute mean rule for gross flow loss. It is slower
  than the curve rule and is not used to claim a specific cause.
- **Sensor quality, range and stuck** are measurement-integrity rules. They never produce a
  `PROCESS_FAULT` label and cannot match a process-event ground truth.
- **Missing telemetry** is represented by absent rows, not by an injected `MISSING` flag. The gap
  rule detects the absence from the expected cadence.
- **Mode awareness**: RULE-001, RULE-002, RULE-005, RULE-006 and RULE-007 are suppressed during
  `STARTUP`, `SHUTDOWN`, and `MAINTENANCE`, when low or changing process values are expected.
  Suppressed readings reset the candidate timer; an alarm can only activate after the mode returns
  to `NORMAL` and the condition persists. Sensor-integrity rules are not mode-suppressed.

### 3.2 Threshold selection

Thresholds were chosen from the simulator's noise model and physical scale, not by grid-searching
the evaluation scenarios:

- Level noise floor is `0.03 pp`; a `0.30 pp / 5 min` decline is ten times the noise floor and
  corresponds to roughly `3.6 pp/h`. Medium leaks are `5% of capacity per hour` (about
  `4-6 pp/h` for the generated tanks). The `1.5%/h` light leak produces a balance residual above
  the absolute `5 m3/h` floor, but its 5-minute decline is only about `0.13 pp` and does not
  reliably satisfy the `0.15 pp` corroboration condition for `480 s`; it is retained as a known miss.
- Balance tolerance combines an absolute `5 m3/h` floor (sensor/model uncertainty at low flow) with
  an `8%` relative term. This avoids a tolerance that vanishes at low flow and avoids a fixed
  threshold that ignores tank size.
- Pump low flow uses `80%` of nominal with `85%` recovery; normal operation is `92% +/-` small
  variation, so the gap is much larger than normal noise.
- Pump curve tolerance is `10%`, twice the nominal curve's noise band; recovery at `6%` provides
  hysteresis.
- Level/pressure redundancy uses `4 pp`, above level noise and hydrostatic rounding, while injected
  bias/drift is `6-9 pp`.
- Stuck detection uses a `30 min` duration; the sensor-fault scenarios hold for `60 min`, leaving
  margin for activation.
- Persistence values (2-8 minutes depending on rule) require a sustained condition but keep
  process latency below the event-evaluation allowance of 600 s.

The calibration scenario set uses different windows, equipment and severities from the evaluation
set. It is used to check that each mechanism is detectable and that the thresholds are not
obviously mis-scaled; it is not used to optimize a metric on the evaluation set. No threshold was
changed after inspecting evaluation results. The sensor-fault latency allowance (3,600 s) was fixed
before the evaluation run was inspected.

The light-leak audit measured a 10-minute residual median of `8.32 m3/h` (mean `7.97`), with 82 of
90 samples above the absolute `5 m3/h` floor, and a 5-minute decline median of `-0.131 pp`. The
longest continuous active-and-corroborated run was `300 s`; the longest active run without
corroboration was `420 s`. Both are below the `480 s` persistence requirement, so neither
RULE-006 nor RULE-006U fired for this event. This is a persistence/corroboration limitation, not a failure of the
absolute balance floor.

## 4. Sensor fault versus process fault versus uncertainty

| Output | Meaning | Examples |
|---|---|---|
| `PROCESS_FAULT` | Observed process behaviour is abnormal and is explained by a physical mechanism | level decline, flow-balance loss with level corroboration, pump curve deviation, low flow, level bounds |
| `SENSOR_FAULT` | The measurement or data channel is untrustworthy | bad quality, stuck, implausible range, missing telemetry, level/pressure disagreement |
| `UNCERTAIN` | Process inconsistency exists but the evidence cannot distinguish a physical leak from a sensor bias | positive flow-balance residual without a corroborating level decline |

A sensor fault is never automatically re-labelled as a process fault. When redundancy disagrees,
the affected sensor is not known with certainty, so RULE-010 records
`attribution=REDUNDANCY_AMBIGUOUS` and does not assert which of level or pressure is wrong.
RULE-006U explicitly records `attribution=INSUFFICIENT_EVIDENCE`.

## 5. Alarm evidence and attribution

Each alarm row records:

- `rule_id`, `alarm_type`, `alarm_category`, `severity`
- `first_detected_at`, `last_detected_at`, `occurrence_count`
- `peak_value`, `peak_at`
- `operating_mode` at activation
- `attribution`: `OBSERVED_LEVEL`, `OBSERVED_FLOW`, `MASS_BALANCE_WITH_LEVEL_CORROBORATION`,
  `CURVE_RESIDUAL`, `REDUNDANCY_AMBIGUOUS`, `INSUFFICIENT_EVIDENCE`, `MEASUREMENT_METADATA`,
  `RANGE_CHECK`, `TEMPORAL_CONSISTENCY`, or `DATA_AVAILABILITY`
- `evidence_summary`, a human-readable statement including the threshold, peak and category

The evidence summary is descriptive, not a causal proof. For example, a flow-balance alarm says
"possible leak" and states that the residual is corroborated by a level decline; it does not claim
that a leak was physically confirmed.

## 6. Grouping semantics

Grouping happens at two levels:

1. **Within the detector**, one episode per rule/equipment/sensor. A rule does not emit one row
   per abnormal sample. Short gaps (up to 300 s) remain one episode.
2. **In evaluation**, overlapping alarm episodes on the same equipment are merged into one
   **incident** for event matching. Multiple rules detecting the same physical event therefore
   count once as a true positive; the additional episodes are reported as corroborating evidence.

Grouping is deliberately not applied across different equipment, because two simultaneous events
on different assets are distinct incidents. It is also not applied across long gaps, so a genuine
recurrence becomes a separate incident and can be evaluated as such.

## 7. False alarms, uncertainty and known limits

- A process alarm during a labelled sensor fault is an evaluation false alarm. The detector cannot
  use ground truth to know that the process is normal, so this is reported rather than suppressed.
- A level/pressure disagreement is attributed to the pair, not to a specific sensor. The alarm is a
  sensor fault but the exact faulty device may require maintenance inspection.
- The `1.5% of capacity/hour` light leak (`E-LEAK-01`) is not detected. Its balance residual is
  above the absolute `5 m3/h` floor, but the decline corroboration and `480 s` persistence do not
  both hold and RULE-002's `0.30 pp` trigger is not reached for this event. It is documented as a
  corroboration/persistence sensitivity limit, not tuned away.
- Point-level false positives occur at the tail of an episode after the physical anomaly ends,
  because the detector needs two clear readings and a grouping gap before resolving. This is
  visible in the point metrics and is not hidden by event-level grouping.
- The rules assume the generated sensor roles and units. A real plant with different redundancy or
  unmeasured disturbances would need site-specific thresholds.
- The simulator is a simplified water model. It is internally mass-consistent, but it is not a
  validated digital twin and these results do not establish performance on real equipment.

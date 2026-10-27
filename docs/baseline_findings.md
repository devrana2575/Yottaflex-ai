# Baseline Findings (Pre-Improvement Audit)

**Date:** 2026-10-27
**Auditor:** OpenCode (DeepSeek V4.1 Flash Free)
**Repository state:** commit `f4b3f75`, before this audit's changes
**Seed:** 20261022
**Runtime:** Python 3.14.4, Windows 11

All numbers below were reproduced from clean output directories during this audit. They are
observations, not inputs. The historical report was accurate about entity and row counts and
about the numeric output of the old evaluator, but the old evaluator's headline metrics were
not a valid precision/recall/F1 calculation.

## Reproduced baseline

| Workflow | Telemetry rows | Alarm rows | Reported TP | Reported FP | Reported precision | Reported recall | Reported F1 | Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| starter, 24 h @ 60 s | 51,840 | 929 | 4 | 46 | 0.0800 | 1.000 | 0.1481 | 12.2 s |
| full, 24 h @ 60 s | 316,800 | 1,245 | 4 | 372 | 0.010638 | 1.000 | 0.021053 | 42.4 s |

Entity counts reproduced: 3 facilities, 20 pumps, 30 tanks, 60 valves, 134 pipes, 220 sensors,
4 scenarios, 4 ground-truth rows. All 11 original tests passed. The original validator reported
18 PASS / 0 FAIL / 0 WARN / 0 NOT_IMPLEMENTED.

## Defect 1 - The headline metric mixes incompatible units

`Evaluator.evaluate()` sets `true_positives = number_of_ground_truth_events_detected` but
`false_positives = number_of_unmatched_alarm_rows`. Every raw alarm row is a single telemetry
sample. Repeated alarms from one incident are therefore not represented in the numerator or
denominator consistently:

- 1,245 raw alarm rows, of which 873 overlap an injected event window on the affected equipment.
- 372 raw alarm rows do not overlap an event window.
- The old precision is `4 / (4 + 372) = 1.06%`.
- The 873 event-overlapping alarm rows are silently discarded from the denominator rather than
  grouped, matched one-to-one, or counted as corroborating evidence.

This is not event-level precision and it is not point-level precision. It is a hybrid with no
defined statistical meaning. Reported F1 is derived from that hybrid.

## Defect 2 - Alarm records are not events

Detection emits one alarm row per abnormal telemetry sample. A four-hour pump degradation
produces 438-458 alarms in the full run (and 458 in starter), all for one incident. There is no
open/continue/resolve lifecycle, no alarm grouping, no recovery state, no hysteresis, and no
duplicate suppression. `alarm_status` is always `ACTIVE`. The schema contains an append-only
`alarm_events` table, but no code writes to it.

## Defect 3 - Event matching is an unconstrained overlap test

Old matching accepts any alarm whose timestamp lies within a ground-truth window and whose
equipment matches. If the ground truth has an `affected_sensor_id`, the sensor must also match.
It does **not** require:

- the expected alarm category (process vs sensor fault),
- a maximum detection latency,
- one-to-one assignment (one alarm can match several events; several alarms can match one event),
- duplicate handling,
- exclusion of alarms that were already active before the event started.

The leak event (TANK-001, 04:00-08:00) was considered detected from only 5-15 matching samples,
because the old leak injection did not reliably produce a sustained level decline. Conversely,
any unrelated rule on the same equipment inside the window would have counted as a detection.

## Defect 4 - No point-level evaluation and no explicit negative labels

There is no TP/TN/FP/FN at timestamp level, no false-positive rate, and no defined positive class
or timestamp-matching rule. True negatives are reported as `null` with the note that no normal
event population exists, while unmatched alarm samples are still counted as false positives.
Every time outside the four anomaly windows is implicitly treated as negative for FP purposes,
without an explicit normal label or an unknown-label category.

## Defect 5 - No normal baseline scenarios

The simulator cannot distinguish a false alarm caused by evaluation logic from one caused by a
detector rule, because there are no labelled normal windows. Startup, shutdown, maintenance,
steady-state variation, and nuisance transients are not in the ground truth. The operating-mode
columns exist, but every simulated sample is `NORMAL`; the detector never reads them.

## Defect 6 - Simulation is not physically consistent

- Tank level is an unconstrained random walk driven by independently sampled inlet and outlet
  flows. The flows are not persisted, so no flow balance can be checked.
- Tank pressure is sampled independently from `Uniform(3, 8)` bar and is unrelated to level.
- Pump pressure is sampled independently from `Uniform(3, 8)` bar, while nominal head is
  30-150 m (approximately 3-15 bar). Pump flow is sampled from 80-100% of nominal even though
  the pump curve function already exists; the curve is never used by the simulator.
- `calculate_mass_balance_residual()` exists and is unit-tested, but is not used by simulation,
  detection, validation, or evaluation.
- Leak injection subtracts independent random decrements of 0.1-0.3 percentage points per
  sample. The persisted `leak_rate_m3_h=5.5` is unrelated to the actual volume removed.
- Blockage parameters (`blockage_factor=0.6`) and degradation parameters
  (`degradation_factor=0.75`) also disagree with the applied multipliers (0.7 and 0.85).

## Defect 7 - Sensor-fault ground truth leaks through `quality_status`

The sensor-fault scenario sets `quality_status = UNCERTAIN` exactly for the injected fault
window. RULE-004 then alarms solely because the injector told the detector the sensor was bad.
The detector never has to observe a bias, drift, stuck value, or missing sample. This is a
label leak through a measurement-metadata field: it makes the sensor-fault result trivially
100% and does not test sensor-fault detection.

## Defect 8 - Rule-level false-alarm analysis has no support

The 372 unmatched samples in the full run consist of:

| Rule | Total alarms | Interpretation |
|---|---:|---|
| RULE-002 rapid tank level decline | 384 | 369-372 occur outside the leak window because the random-walk tank level frequently falls faster than 0.75 pp / 5 min |
| RULE-004 sensor quality | 181 | All arise from the injector's UNCERTAIN flag, not from observed sensor behaviour |
| RULE-005 pump low flow | 680 | ~677 fall inside blockage/degradation windows; 3 are boundary effects |

The dominant genuine nuisance is RULE-002 on an unphysical random-walk level. It is not evidence
that the detector is fundamentally bad; it is evidence that the simulator plus threshold are
inconsistent. The old report did not separate this from evaluation-definition error.

## Defect 9 - Configuration is not honoured end-to-end

`detect` and `evaluate` construct a default `Config` instead of loading `config.json`. Custom
sampling interval, duration, scenario set, and detection thresholds in the run directory are
ignored. `simulate` does not persist its CLI duration/sampling overrides. The `--mode` used for
detection is not checked against the master-data scale.

## Defect 10 - Tests do not verify the claims

The 11 tests cover IDs, master-data counts, one pump-curve monotonicity assertion, tank volume,
a three-number residual subtraction, and fixture construction for the negative checks. There is
no test for detection rules, alarm grouping, matching, metrics, normal windows, sensor faults,
ground-truth isolation, SQL execution, CSV schemas, or reproducibility.

## Defect 11 - Persistence and export weaknesses

- `export-sql` appends to an existing database and fails on a second run through primary-key
  conflicts.
- `alarm_events`, `equipment_state_events`, `validation_results`, and `detection_results` tables
  are never populated.
- The CLI pipeline did not include export, so the documented SQL workflow was never exercised
  by `pipeline`.
- The README SQL command splits on `;` naively, which is adequate only because the current file
  contains no semicolons in strings.

## Defect 12 - False-positive denominator and zero-denominator behaviour

Zero denominators return `0.0`, which fabricates a defined metric. Where a denominator is
undefined the correct representation is `null` plus a reason. The old code also cannot report
point-level false-positive rate because it never defines TN.

## Root causes, ranked

1. **Evaluation error:** mixing event TP with record-level FP. This is the main reason the
   reported precision is 1.06%.
2. **No alarm grouping:** one incident produces hundreds of rows.
3. **Simulation-injection inconsistency:** a random-walk level with a mismatched threshold
   produces RULE-002 nuisance alarms; injection parameters do not match applied physics.
4. **Missing labels:** no normal windows and no point labels.
5. **Sensor-fault label leak:** quality status is set by the injector.
6. **No operating-mode or redundancy awareness:** sensor faults and process faults cannot be
   distinguished from multiple measurements.

## What must not be done

- Do not fix precision by suppressing alarms without fixing labels or physics.
- Do not drop RULE-002 simply because it is noisy; replace the unphysical level random walk with
  a mass-balance model, require persistence, and add hysteresis.
- Do not count the 873 event-overlapping raw alarms as true positives or omit them from a
  grouped incident.
- Do not tune thresholds on the evaluation scenario set and present the result as independent.
- Do not treat unlabelled timestamps as confirmed negatives. Normal windows must be explicit.

These findings drive the implementation described in
[docs/implementation_decisions.md](implementation_decisions.md).

# Validation Report (YottaFlex 2.0.0)

**Status:** PASS with three review-level WARNs: light-leak coverage, reconstructed earlier prompt
records (1.x and the 2026-10-28 remediation record), and cross-version last-bit float serialization.
The main suite, targeted 17-test suite, fresh clean-environment suite, two exact-100k runs, clean
exact/full/default/evaluation pipelines, exports and independent metrics were re-run on 2026-10-29.
Publication was explicitly authorized on 2026-10-28 and reaffirmed by the 2026-10-29 final-audit
instruction. The executable validation CSV is **87 PASS, 0 FAIL, 0 WARN, 0 NOT_IMPLEMENTED**; these
review caveats are not rows in that CSV and are not added to its denominator.

- **Date:** 2026-10-27 submission-readiness audit; extended 2026-10-28 for exact
  100k/state-history/portable-export remediation; independently re-audited 2026-10-29.
- **Environment:** Main environment Python 3.14.4, pandas 3.0.3, NumPy 2.4.6, pytest 9.1.1, Windows 11;
  fresh 2026-10-29 acceptance virtual environment Python 3.14.4, pandas 3.1.0, NumPy 2.5.4,
  pytest 9.2.0; seed `20261022`, 60 s cadence. The clean environment passed all 68 tests and
  reproduced exact-100k, full/default and evaluation with matching counts and metrics; only
  last-bit cross-version float serialization differed.
- **Repository state:** the 2.0 implementation and prior audit corrections are on `origin/main`.
  The 2026-10-29 verification pass started at `main` commit
  `f8f8d6ae208cf3024ec031dbecc5b80c69841c19` with a clean working tree. It changed only
  documentation, machine-readable evidence, the light-leak diagnostic and prompt/AI-use records; the
  reviewed changes were committed and pushed to `origin/main` without force-push or history rewrite.
- **Primary evidence:** clean run directories `yf2-evaluation`, `yf2-calibration`, `yf2-full`,
  `yf2-starter`, `yf2-100k` (exact 100k), `yf2-compact-99k` (historical compact 99k), plus fresh
  2026-10-29 external runs `baseline-100k`, `baseline-100k-b`, `exact-clean-current`, `full-default`,
  `evaluation`, `full-default-clean-current` and `evaluation-clean-current`; compact copies are in
  `reports/final/`. Absolute local paths in copied evidence are redacted as
  described in §12.
- **Final acceptance evidence:** the fresh 2026-10-29 main and clean runs above, with commands,
  checksums, independent metric counts and clean-environment comparison summarized in
  [`reports/final/reproducibility_100k.json`](../reports/final/reproducibility_100k.json) and
  [`reports/final/summary.json`](../reports/final/summary.json).

## 1. Executive Summary

The 1.x baseline was reproduced first. It reported precision `0.0800` for the starter run and
`0.010638` for the full run, but those values mixed event-level true positives with raw alarm-row
false positives. The full run produced 1,245 alarm rows for four events and discarded 873
event-overlapping rows from the denominator. That metric has no valid event or point interpretation.

The 2.0 detector emits grouped episodes instead of one row per sample, and evaluation is split into
two independent units:

- **Event level:** positive ground-truth events vs merged alarm incidents.
- **Point level:** explicit `(sensor, timestamp)` labels with unknown samples excluded.

The primary independent evaluation set contains 11 positive events and 8 explicit NORMAL windows.
Final result: **TP=10, FN=1, FP=0** at event level (precision `1.0000`, recall `0.9091`, F1
`0.9524`) and **TP=844, FP=10, TN=112,190, FN=206** at point level (precision `0.9883`, recall
`0.8038`, F1 `0.8866`). The only missed event is the `1.5% of capacity/hour` light leak. Its
10-minute balance residual is above the absolute `5 m3/h` floor (median `8.32 m3/h`; 82/90 samples
above it), but the 5-minute level decline is only `-0.131 pp` median, just below the `0.15 pp`
corroboration trigger. The longest corroborated run was `300 s` and the longest
active-without-corroboration run was `420 s`, both below the `480 s` persistence requirement;
RULE-002's `0.30 pp` trigger did not fire for this event. The miss is therefore a corroboration/persistence
sensitivity limit, not a balance-floor failure, and is retained. All 8 NORMAL windows were
alarm-free at the incident level. The 10 point false positives are short episode tails after
anomalies end; they are retained and reported, not suppressed.

All 87 executable validation rows pass, all 20 SQL assertions pass, and all 68 tests pass in both
the main environment and a fresh clean virtual environment. Review-level caveats are tracked
separately: light-leak coverage, reconstructed earlier prompt records, and cross-version last-bit
float serialization. The clean environment also reproduced exact-100k, full/default and evaluation.
Publication was explicitly authorized on 2026-10-28. The 2026-10-28 remediation added an exact 100k
baseline with 100,000 real telemetry rows, a populated append-only `equipment_state_events` table
(341 rows in that baseline), and CSV/JSON/SQLite/portable-SQL export verification. Two fresh
exact-100k runs produced 20/23 byte-identical files; the other three differed only in wall-clock
`evaluated_at`/`validated_at` fields and were logically identical. All 19 SQLite tables matched
logically, 18 were populated, `integrity_check` was `ok`, and there were zero FK violations. The
clean-environment exact-100k rerun reproduced the counts and metrics, and its full/default and
evaluation reruns matched the main metrics; cross-version float/artifact differences are recorded in §8.

## 2. Controls and Evidence Rules

- **Baseline first.** The pre-change workflows were run from clean directories before any source
  edits. Historical figures were treated as observations to verify, not as inputs.
- **Same seed and cadence.** All reported runs use seed `20261022` and 60 s sampling.
- **Ground truth isolated.** The detector selects only sensor ID, timestamp, measured value, quality
  status, operating mode and master metadata. Validation poisons scenario/ground-truth/physical
  columns and confirms detector output is unchanged. Because the built-in three-hour poison slice
  happened to produce zero alarms, the audit also poisoned a four-hour 08:00-12:00 slice (52,800
  rows) that produced three alarms; clean and poisoned runs had identical alarm records.
- **No alarm suppression.** Every episode is written. Evaluation classifies all incidents, including
  false alarms and unknowns.
- **No denominator manipulation.** Event false positives are unmatched incidents. Unknown samples
  and unknown incidents are excluded and counted. Zero denominators return `null`.
- **Method fixed before evaluation inspection.** Thresholds were based on noise/physics, and the
  sensor-fault latency allowance was fixed before the evaluation result was inspected.
- **Calibration and evaluation separated.** They use different windows, equipment and severities.

## 3. Reproduced 1.x Baseline

| Run | Telemetry rows | Alarm rows | Reported TP | Reported FP | Reported precision | Reported recall | Reported F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| starter, 24 h | 51,840 | 929 | 4 | 46 | 0.0800 | 1.000 | 0.1481 |
| full, 24 h | 316,800 | 1,245 | 4 | 372 | 0.010638 | 1.000 | 0.021053 |

Reproduced entity counts: 3 facilities, 20 pumps, 30 tanks, 60 valves, 220 sensors. The original
11 tests passed and the original validator returned 18 PASS. The 12 reproduced defects are
documented in [`baseline_findings.md`](baseline_findings.md); the main ones were:

1. Event TP divided by raw alarm-row FP, with 873 matching rows discarded (mixed units).
2. One alarm row per abnormal sample; no lifecycle, grouping or hysteresis.
3. Unconstrained time/equipment matching without category, latency or one-to-one assignment.
4. No point evaluation and no explicit NORMAL windows; unlabelled time implicitly negative.
5. No normal baseline scenarios; all simulated modes were `NORMAL`.
6. Inconsistent physics: random-walk tank level, independent pressure, unused pump curve, unused
   mass balance.
7. Sensor-fault ground truth leaked through `quality_status=UNCERTAIN`.
8. No support for rule-level false-alarm analysis.
9. `detect`/`evaluate` ignored the run configuration.
10. Tests did not verify detection, evaluation, SQL or reproducibility.
11. SQLite export appended and failed on repeat; several tables were never populated.
12. Zero denominators returned `0.0` instead of `null`.

## 4. Final Run Inventory

| Run | Mode | Scenario set | Duration | Telemetry rows | State events | Scenario/GT windows | Alarm episodes | Incidents | Validation | SQL |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| `yf2-starter` | starter | default | 24 h | 51,840 | n/a (pre-remediation) | 10 | 7 | 4 | 87 PASS | 20 PASS |
| `yf2-full` | full | default | 24 h | 316,800 | n/a (pre-remediation) | 10 | 7 | 4 | 87 PASS | 20 PASS |
| `yf2-compact-99k` (historical) | full | compact | 7.5 h | 99,000 | n/a (pre-remediation) | 9 | 7 | 4 | 87 PASS | 20 PASS |
| `yf2-100k` (exact) / `baseline-100k`, `baseline-100k-b` | full | baseline | 7.583 h | 100,000 | 341 | 9 | 107 | 62 | 87 PASS | 20 PASS |
| `yf2-calibration` | full | calibration | 24 h | 316,740 | 347 | 15 | 10 | 7 | 87 PASS | 20 PASS |
| `yf2-evaluation` / `evaluation`, `evaluation-clean-current` | full | evaluation | 24 h | 316,740 | 355 | 19 | 15 | 10 | 87 PASS | 20 PASS |

Calibration and evaluation have 316,740 rows because the labelled missing-sensor scenario removes
60 rows. The missing rows are intentional. The exact 100k baseline uses `120 x 455 + 100 x 454 =
100,000` real `(sensor, timestamp)` samples; the uneven cadence is the documented allocation, not
missing data. The historical compact run remains exactly `220 x 450 = 99,000` rows.

### 4.1 Final metric summary

| Run | Event TP/FN/FP | Event P / R / F1 | Point TP/FP/TN/FN | Point P / R / F1 |
|---|---|---|---|---:|---|
| starter, default | 4 / 0 / 0 | 1.0000 / 1.0000 / 1.0000 | 880 / 7 / 23,753 / 20 | 0.9921 / 0.9778 / 0.9849 |
| full, default | 4 / 0 / 0 | 1.0000 / 1.0000 / 1.0000 | 882 / 8 / 145,192 / 18 | 0.9910 / 0.9800 / 0.9855 |
| full, exact 100k baseline | 4 / 0 / 0 | 1.0000 / 1.0000 / 1.0000 | 245 / 5 / 41,915 / 19 | 0.9800 / 0.9280 / 0.9533 |
| full, compact (historical) | 4 / 0 / 0 | 1.0000 / 1.0000 / 1.0000 | 246 / 5 / 40,915 / 18 | 0.9801 / 0.9318 / 0.9553 |
| full, calibration | 7 / 0 / 0 | 1.0000 / 1.0000 / 1.0000 | 508 / 7 / 171,593 / 92 | 0.9864 / 0.8467 / 0.9112 |
| **full, evaluation** | **10 / 1 / 0** | **1.0000 / 0.9091 / 0.9524** | **844 / 10 / 112,190 / 206** | **0.9883 / 0.8038 / 0.8866** |

The default, exact 100k baseline and compact runs are demonstration/regression configurations. The
calibration set checks mechanism coverage. The evaluation set is the reported independent result;
it was re-run on 2026-10-28 after the remediation and reproduced the same metrics.

## 5. Independent Evaluation Set

### 5.1 Event-level result

| Metric | Value |
|---|---:|
| Ground-truth rows | 19 (11 positive + 8 NORMAL) |
| True positives | 10 |
| False negatives | 1 |
| False positives (unmatched incidents) | 0 |
| True negatives (NORMAL windows with no incident) | 8 |
| Precision | 1.0000 |
| Recall | 0.9091 |
| F1 | 0.9524 |
| False-positive rate | 0.0000 (0 / 8 NORMAL windows) |
| Alarm episodes / incidents | 15 / 10 |
| Matched incidents / unmatched incidents | 10 / 0 |
| Unknown incidents | 0 |
| Corroborating alarm episodes | 5 |
| Unmatched alarm episodes | 0 |
| Latency: mean / median / min / max | 702 s / 300 s / 60 s / 3,180 s |

Five alarm episodes were corroborating evidence on already-matched incidents; they did not inflate
the event TP count. No incident was left unmatched, so there were no event false alarms and no
unknown incidents.

### 5.2 Per-event results

Point TP/FN are for the event's expected sensor and labelled window. `—` means no detection
latency because the event was missed.

| GT | Type | Severity | Equipment | Sensor | Window | Event | Latency | Point TP/FN |
|---|---|---|---|---|---:|---|---:|---:|
| GT-000001 | LEAK (light) | light | TANK-002 | SNS-019 | 02:00-03:30 | **MISSED** | — | 0 / 90 |
| GT-000002 | LEAK | medium | TANK-003 | SNS-023 | 06:00-08:00 | DETECTED | 360 s | 114 / 6 |
| GT-000003 | LEAK | severe | TANK-004 | SNS-027 | 13:00-15:00 | DETECTED | 240 s | 116 / 4 |
| GT-000004 | BLOCKAGE | light | PUMP-002 | SNS-003 | 09:00-11:00 | DETECTED | 300 s | 115 / 5 |
| GT-000005 | BLOCKAGE | severe | PUMP-003 | SNS-005 | 17:00-19:00 | DETECTED | 300 s | 115 / 5 |
| GT-000006 | PUMP_DEGRADATION | light | PUMP-001 | SNS-001 | 10:00-12:00 | DETECTED | 300 s | 115 / 5 |
| GT-000007 | PUMP_DEGRADATION | severe | PUMP-002 | SNS-003 | 20:00-22:00 | DETECTED | 300 s | 115 / 5 |
| GT-000008 | SENSOR_FAULT (bias) | medium | TANK-001 | SNS-015 | 04:00-05:30 | DETECTED | 180 s | 87 / 3 |
| GT-000009 | SENSOR_FAULT (drift) | medium | TANK-005 | SNS-031 | 15:30-17:00 | DETECTED | 3,180 s | 37 / 53 |
| GT-000010 | SENSOR_FAULT (stuck) | medium | TANK-001 | SNS-015 | 18:00-19:00 | DETECTED | 1,800 s | 30 / 30 |
| GT-000011 | SENSOR_FAULT (missing) | medium | TANK-002 | SNS-019 | 21:00-22:00 | DETECTED | 60 s | 0 / 0 |

The missed event is the scenario-matrix label `E-LEAK-01` (CSV row `GT-000001`), a 1.5% of
capacity/hour leak. Its 10-minute residual median is `8.32 m3/h` (82/90 samples above the absolute
`5 m3/h` floor), but the 5-minute decline median is `-0.131 pp`, below the `0.15 pp` corroboration
trigger; the longest corroborated run is `300 s` and the longest active-without-corroboration run is
`420 s`, both below `480 s` persistence. RULE-002's `0.30 pp` trigger did not fire for this event. It is retained as
a documented corroboration/persistence sensitivity limitation rather than tuned away on the
evaluation set.

The missing-sensor event removes all 60 expected samples, so there are no observed point rows to
score; the event is still detected from the absence of telemetry (RULE-009). This is why positive
row coverage is below 100%.

### 5.3 Point-level result

| Subset | TP | FP | TN | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Overall | 844 | 10 | 112,190 | 206 | 0.9883 | 0.8038 | 0.8866 |
| Process faults | 690 | 9 | 112,191 | 120 | 0.9871 | 0.8519 | 0.9145 |
| Sensor faults | 154 | 1 | 112,199 | 86 | 0.9935 | 0.6417 | 0.7797 |

Point false-positive rate = `10 / (10 + 112,190) = 0.0000891`.

Label accounting:

| Item | Value |
|---|---:|
| Labelled rows | 113,250 |
| Positive rows | 1,050 |
| Negative rows | 112,200 |
| Unknown samples (excluded) | 203,490 |
| Unknown predictions (excluded, counted) | 2 |
| Unobserved labelled rows (excluded) | 0 |
| Positive row coverage | 1,050 / 1,110 = 0.9459 |

The two unknown predictions are SNS-003 samples at 11:00 and 11:01. The PUMP-002 blockage ended at
11:00, but the global anomaly union still contains the PUMP-001 degradation window, so those
timestamps are not labelled NORMAL. They are excluded and reported, not counted as false positives
and not counted as true negatives.

### 5.4 False-alarm analysis

**Event level:** zero false-alarm incidents and zero unknown incidents. All 8 NORMAL windows were
free of alarm incidents. The 15 alarm episodes merged into 10 incidents, exactly matching the 10
detected events; 5 episodes were corroborating evidence.

**Point level:** 10 false positives, all in explicit NORMAL windows and all at the tail of an
episode after the physical event ended:

| Sensor | Equipment | Samples | Rule | Cause |
|---|---|---|---:|---|
| SNS-005 | PUMP-003 | 19:00-19:04 (5) | RULE-005 | Severe blockage ended at 19:00; the five-minute mean and clearance logic kept the episode active until 19:04. |
| SNS-003 | PUMP-002 | 22:00-22:03 (4) | RULE-005 | Severe degradation ended at 22:00; the episode cleared at 22:03. |
| SNS-019 | TANK-002 | 22:00 (1) | RULE-009 | Missing telemetry ended at 22:00; the gap episode included the first resumed sample. |

These are one to five samples per tail. They are not event false alarms and are not removed. The
2 unknown tail samples at SNS-003 11:00-11:01 are excluded because no explicit label exists there.

**Point false negatives:** 206 total.

| Cause | FN |
|---|---:|
| Light leak (corroboration/persistence sensitivity; GT-000001) | 90 |
| Process-event onset latency | 30 |
| Sensor bias onset latency | 3 |
| Sensor drift onset latency | 53 |
| Sensor stuck activation latency | 30 |
| Missing telemetry (rows absent, no point rows) | 0 |

Point recall is therefore a latency/sensitivity measure, not evidence that the events were missed.
The event result is the primary detection-coverage measure; the point result shows how long the
detector took to react and where episode tails extend past the event.

### 5.5 Results by type, category and severity

| Scenario type | Injected | Detected | Missed | Recall | Mean latency |
|---|---:|---:|---:|---:|---:|
| LEAK | 3 | 2 | 1 | 0.6667 | 300 s |
| BLOCKAGE | 2 | 2 | 0 | 1.0000 | 300 s |
| PUMP_DEGRADATION | 2 | 2 | 0 | 1.0000 | 300 s |
| SENSOR_FAULT | 4 | 4 | 0 | 1.0000 | 1,305 s |

| Category | Injected | Detected | Missed | Recall | Mean latency |
|---|---:|---:|---:|---:|---:|
| PROCESS_FAULT | 7 | 6 | 1 | 0.8571 | 300 s |
| SENSOR_FAULT | 4 | 4 | 0 | 1.0000 | 1,305 s |

| Severity | Injected | Detected | Missed | Recall | Mean latency |
|---|---:|---:|---:|---:|---:|
| light | 3 | 2 | 1 | 0.6667 | 300 s |
| medium | 5 | 5 | 0 | 1.0000 | 1,116 s |
| severe | 3 | 3 | 0 | 1.0000 | 280 s |

The only miss is the light leak. All medium/severe process faults and all four sensor-fault
mechanisms were detected. Sensor-fault latency is longer by design (stuck threshold is 30 minutes;
the matching allowance is 3,600 s).

## 6. Supporting Runs and Overfitting Control

| Run | What it checks | Result |
|---|---|---|
| starter/default | Small-scale end-to-end behavior and regression | 4/4 events, 0 FP; point P 0.9921 / R 0.9778 |
| full/default | Required 316,800-row volume and demonstration set | 4/4 events, 0 FP; point P 0.9910 / R 0.9800 |
| full/exact 100k baseline | Exact-budget configuration and state history | Exactly 100,000 rows; 341 state events; 4/4 events, 0 FP |
| full/compact (historical) | Previous ~100k demonstration | Exactly 99,000 rows; 4/4 events, 0 FP |
| full/calibration | Different windows/equipment/severities; all four sensor faults | 7/7 events, 0 FP; event F1 1.0000 |
| full/evaluation | Independent reported set | 10/11 events, 0 FP; F1 0.9524 |

Calibration and evaluation do not share event windows or equipment selections. The calibration run
detected bias, drift, stuck and missing faults with different severities; its point recall `0.8467`
reflects expected sensor activation latency, while its event recall is 1.0000. No threshold was
changed after the evaluation run was inspected.

## 7. Validation and SQL Evidence

### 7.1 Validation checks

Final executable validation result (all final runs, including the exact 100k baseline): **87 PASS,
0 FAIL, 0 WARN, 0 NOT_IMPLEMENTED**. The seven final validation CSVs aggregate 609/609 PASS
(87 each). The review-level caveats in section 10 are not rows in this CSV.

| Validation type | Checks | Status |
|---|---:|---|
| Primary key | 7 | PASS |
| Foreign key | 2 | PASS |
| Topology / bounds | 3 | PASS |
| Sensor schema | 2 | PASS |
| Scale | 2 | PASS |
| Lineage | 8 | PASS |
| Telemetry | 13 | PASS |
| Isolation | 3 | PASS |
| Scenario | 9 | PASS |
| Physics | 6 | PASS |
| Alarm | 11 | PASS |
| Evaluation | 16 | PASS |
| Negative | 2 | PASS |
| Database | 3 | PASS |
| **Total** | **87** | **PASS** |

The 16 evaluation checks include event/point separation, denominator/formula checks, incident
accounting, one-to-one matching, sensor/process separation, point label consistency, unknown
exclusion and an executable zero-denominator case. The 3 isolation checks include a poison test
that confirms detector output is unchanged when ground-truth/scenario/physical columns are altered.
The built-in three-hour slice produced zero alarms, so the audit additionally re-ran the poison
comparison on a four-hour slice with three alarms; the outputs were identical.

The two `NEGATIVE` rows in the CSV are the extended controls `NEG-006` (duplicate alarm rows do not
create duplicate event TPs) and `NEG-007` (an implausible flow reading is a sensor fault, not a
process fault). The five original negative controls (`NEG-001` to `NEG-005`) are exercised by
`tests/test_negative_scenarios.py`; they are part of the 68-test suite, not the 87-row CSV.

### 7.2 SQL analytics

All 20 statements in `sql/analysis_queries.sql` executed successfully against the exported SQLite
database in every final run: **20 PASS, 0 FAIL**.

| # | Query | Expectation | Result |
|---:|---|---|---|
| 1 | Master-data scale | nonempty | PASS, 6 rows |
| 2 | Highest-alarm equipment | nonempty | PASS, 8 rows |
| 3 | Alarms by facility/category/severity | nonempty | PASS, 2 rows |
| 4 | Telemetry quality distribution | nonempty | PASS, 1 row |
| 5 | Tank level operating envelope | nonempty | PASS, 30 rows |
| 6 | Pump flow deviation from nominal | nonempty | PASS, 20 rows |
| 7 | Event-level detection by type | nonempty | PASS, 4 rows |
| 8 | Event metrics with denominators | nonempty | PASS, 12 rows |
| 9 | Point metrics with denominators | nonempty | PASS, 8 rows |
| 10 | Alarm incident classifications | nonempty | PASS, 1 row |
| 11 | Scenario windows by type/severity | nonempty | PASS, 9 rows |
| 12 | Alarm history integrity problems | zero_rows | PASS, 0 rows |
| 13 | Matched incidents missing event rows | zero_rows | PASS, 0 rows |
| 14 | Sensors with fewest readings | nonempty | PASS, 10 rows |
| 15 | Simulation-run lineage/config hash | nonempty | PASS, 1 row |
| 16 | Alarm rule/category distribution | nonempty | PASS, 7 rows |
| 17 | Largest positive tank residuals | nonempty | PASS, 10 rows |
| 18 | Ground-truth detection by severity | nonempty | PASS, 3 rows |
| 19 | SQLite foreign-key violations | zero_rows | PASS, 0 rows |
| 20 | SQLite integrity check | nonempty | PASS, 1 row |

The SQLite export writes 18 populated tables into a 19-table schema; the legacy
`detection_results` table is empty, while `equipment_state_events` is populated. The database passes
`PRAGMA integrity_check`, has an empty `PRAGMA foreign_key_check`, and its exported row counts match
the CSV artifacts. The join-bearing queries were reviewed and executed: Q3 left-joins alarms to
sensors/facilities without dropping equipment-level alarms, Q5/Q6 aggregate the relevant
tank/pump sensors to equipment, Q7 left-joins event evaluation to ground truth, Q13 checks that
matched incidents have evaluation rows, and Q17 joins physical telemetry to tank metadata. No
join fan-out or unexpected null-facility rows were observed in the final evaluation database.

### 7.3 Test suite

`python -m pytest -q` → **68 passed in 43.31 s** in the 2026-10-29 main-environment run; the targeted
negative/state/submission command (`tests/test_negative_scenarios.py`, `tests/test_scenarios.py`,
`tests/test_submission_artifacts.py`) passed **17/17 in 31.56 s**. A fresh Python 3.14.4 / pandas
3.1.0 / NumPy 2.5.4 virtual environment created with the README commands (no `PYTHONPATH`) passed
**68/68 in 34.52 s**. The original 11 tests are retained and extended with exact-target
allocation, 100k cadence/FK, state-history transition/reference, invalid-transition, JSON/SQL
consistency and negative-control assertions. The earlier audit fixes remain covered by the updated
point-coverage assertions and a missing-operating-mode regression test that treats pandas
deprecation warnings as errors.

## 8. Reproducibility

### 8.1 Exact 100,000-row baseline (2026-10-29)

Two fresh final-acceptance runs (`baseline-100k` and `baseline-100k-b`) used seed `20261022`, the `baseline`
scenario set and `--target-telemetry-rows 100000`. **Twenty of 23 compared files were
byte-identical**, including:

- 7 master-data CSVs, telemetry (100,000 rows), scenarios and ground truth;
- `equipment_state_events.csv` (341 rows);
- alarms, alarm history and incidents;
- evaluation events, evaluation metrics JSON and evaluation summary;
- simulation runs, simulation metadata and SQL query report.

Three files (`evaluation_metrics.csv`, `validation_results.csv`, `validation_summary.json`) differed
only in wall-clock `evaluated_at` / `validated_at` fields; after removing those fields they were
logically equal. The two SQLite databases matched across all 19 tables, with 18 populated tables,
`integrity_check=ok`, zero foreign-key violations and identical rows after excluding the wall-clock
columns. Representative hashes:

| Artifact | SHA-256 (both runs) |
|---|---|
| `telemetry.csv` | `625c38b2ca6285fd05abbe637f74609110bb6d57d52d84812546d17ce6400eeb` |
| `equipment_state_events.csv` | `2759aa10a1786bdd2017e35a0bc6b496a2623244e03d66fdb2627f941a319dcb` |
| `alarms.csv` | `2da4e13835ca9569e7f52c6cabe3e7d510733132d8ec7ccd2404b30ea5d6ca10` |
| `alarm_events.csv` | `073c2b9765cd0e624acf17c16a284ae5b61e8cf2342d600937719098a693dc85` |
| `evaluation_metrics.json` | `a9820c60e2775be1784201e28ff3807292f13663b7255a10231eb4fa301fd987` |

The exact-100k comparison is recorded in
[`reports/final/reproducibility_100k.json`](../reports/final/reproducibility_100k.json). CSV, JSON,
SQLite and SQL-seed telemetry IDs were additionally compared for the development 100k run: all four
formats matched, the SQL seed executed into a new database with `integrity_check=ok` and zero FK
violations, and the database contained 100,000 telemetry and 341 state-history rows.

The clean pandas 3.1.0 / NumPy 2.5.4 environment regenerated the same 100,000 rows, 341 state events,
87/87 validation PASS, 20/20 SQL PASS and identical event/point metrics. Compared with the main
environment, 19/23 deterministic artifacts were byte-identical; three differed only in wall-clock
fields, and `sql_query_report.json` differed only in last-bit floating-point values. The SQLite
comparison found 16/19 tables exactly equal and 17/19 after removing timestamp columns;
`telemetry` and `evaluation_metrics` differed only at about `7e-15`/`1e-16`, leaving all 19
logically equal with no semantic or metric difference. The clean environment also reproduced the
full/default run (316,800 rows, event `4/0/0`, point `882/8/145192/18`) and the evaluation run
(316,740 rows, event `10/1/0`, point `844/10/112190/206`) with matching validation, SQL and
metrics.

### 8.2 Prior full/default comparison (2026-10-27)

Two fresh full/default audit runs after the source fixes (`audit A` and `audit B`, external temp
directories) were compared. **19 of 19 deterministic artifacts were byte-identical**, including:

- 7 master-data CSVs: facilities, pumps, tanks, valves, pipes, sensors, operating modes;
- telemetry, scenario definitions and ground truth;
- alarms, alarm history and alarm incidents;
- evaluation events, evaluation metrics JSON and readable evaluation summary;
- simulation runs, simulation metadata and SQL query report.

Key hashes (identical in both runs):

| Artifact | SHA-256 |
|---|---|
| `telemetry.csv` | `fb634b7e31f60f425dfaeb3764ccf7c6db4453373ec926d9c1ddbc7c2f9d3e1f` |
| `alarms.csv` | `d0120b194e0b1939fa35d7de9c818493e0bd4471e3547265fe482a0a5958da10` |
| `alarm_events.csv` | `62d0ad5fe995b98e4b202bc675c07467ccda72d3750ad3fc0596180eb9b64e88` |
| `alarm_incidents.csv` | `e22675491270cd59f87792d9e4cd6272ead984a20ba11d3bc0796f745d498ca4` |
| `evaluation_metrics.json` | `66284142f8144dcc59ea3c2605a0f7622b2e98b280a73732f34f18feea282e7a` |

The path-independent configuration hash is identical: `d422f3bbee3dcadc`. Telemetry row counts are
316,800 in both runs. At that time the two SQLite databases matched logically: 19 schema tables, 17 populated
plus the legacy empty `detection_results` and the then-empty `equipment_state_events`; `PRAGMA integrity_check`
returned `ok`, `PRAGMA foreign_key_check` returned no rows, and all populated table rows were
identical after excluding the wall-clock `evaluation_metrics.evaluated_at` and
`validation_results.validated_at` columns. A fresh post-fix evaluation-set run reproduced the stored
`alarms.csv`, `alarm_events.csv`, `alarm_incidents.csv`, `evaluation_events.csv`,
`evaluation_metrics.json`, `evaluation_summary.md`, `simulation_metadata.json`, `simulation_runs.csv`
and `sql_query_report.json` byte-for-byte.

**Cross-environment note:** The 19/19 byte comparison above is within one environment (main
environment: pandas 3.0.3 / NumPy 2.4.6). A fresh virtual environment (pandas 3.1.0 / NumPy 2.5.4)
reproduced all evaluation metrics, events, incidents and 17 of 19 artifacts exactly; `alarms.csv`
and `sql_query_report.json` differed only in a few `peak_value` floats at about `8e-13` (maximum
observed difference), caused by dependency-version floating-point serialization. Dependencies are
lower-bounded rather than upper-pinned; this is a documented cross-environment caveat, not seed
nondeterminism or a metrics difference.

Files excluded from byte-level comparison:

- `config.json` contains absolute output/raw/reports/database paths;
- `evaluation_metrics.csv` contains wall-clock `evaluated_at`;
- `validation_results.csv` contains wall-clock `validated_at`;
- `run_manifest.json` hashes the timestamped evaluation CSV and path-bearing config, so the manifest
  itself differs even though every deterministic per-file hash matches.

Machine-readable evidence:
[`reports/final/reproducibility.json`](../reports/final/reproducibility.json).

## 9. Counts and Data Integrity

| Item | Required / expected | Actual | Status |
|---|---|---:|---|
| Facilities | 3 | 3 | PASS |
| Pumps | 20 | 20 (7 / 7 / 6 per facility) | PASS |
| Tanks | 30 | 30 (10 / 10 / 10) | PASS |
| Valves | 60 | 60 (20 / 20 / 20) | PASS |
| Pipes | topology-defined | 135 | PASS |
| Sensors, full | 220 | 220 (40 pump + 120 tank + 60 valve) | PASS |
| Telemetry, full | 316,800 | 316,800 | PASS |
| Telemetry, exact 100k baseline | 100,000 | 100,000 (120x455 + 100x454) | PASS |
| Telemetry, compact historical | 99,000 | 99,000 | PASS |
| Telemetry, evaluation | 316,740 (60 labelled rows removed) | 316,740 | PASS |
| Equipment state events, 100k baseline | populated, valid transitions | 341 (333 initialization + 8 scenario) | PASS |
| Duplicate `(sensor, timestamp)` samples | 0 | 0 | PASS |
| Unlabelled gaps in window coverage | 0 | 0 | PASS |
| SQLite populated tables / schema tables | 18 / 19 | 18 / 19 (legacy `detection_results` empty) | PASS |
| SQLite integrity / FK violations | ok / 0 | ok / 0 | PASS |
| CSV / JSON / SQLite / SQL telemetry IDs | identical | identical (100k export) | PASS |

Sensor composition was verified by validation: every pump has discharge flow and pressure; every
tank has level, pressure, inlet flow and outlet flow; every valve has through flow. The sensor count
is preserved at 220 by using one valve flow sensor and four physically necessary tank sensors.

Telemetry contains no scenario/ground-truth/expected-label columns. Alarms carry no `scenario_id`.
Detector isolation was checked both by column inspection and by poisoning label/physical columns.
The built-in three-hour slice produced no alarms, so the audit repeated the check on a four-hour,
52,800-row slice with three alarms; clean and poisoned output was identical.

## 10. Requirement Matrix

The detailed requirement-to-evidence matrix, including the five negative controls, exact-100k
allocation and publication authorization record, is in
[`docs/requirement_matrix.md`](requirement_matrix.md). The summary below is retained for continuity.

| Requirement | Evidence | Result | Status |
|---|---|---|---|
| Reproduce actual baseline before editing | `docs/baseline_findings.md`; clean starter/full runs; 929 / 1,245 alarm rows; reported P 0.0800 / 0.010638 | Baseline reproduced exactly; old metric shown to mix units | PASS |
| Separate point-level and event-level evaluation | `evaluation_metrics.json` `event_level` / `point_level`; 16 evaluation validations; separate CSV `evaluation_level` | Independent metrics, never combined | PASS |
| Document matching, unknown labels, duplicates, latency, zero denominators | `docs/evaluation_methodology.md`; `EVENT-FP-UNIT`, `INCIDENT-ONE-TO-ONE`, `POINT-UNKNOWN-EXCLUDED`, `ZERO-DENOMINATOR` | Policy, worked examples and executable checks | PASS |
| Fix evaluation before detector tuning | Baseline audit first; thresholds from noise/physics; calibration/evaluation split | No evaluation-set grid search; single documented miss | PASS |
| Do not suppress alarms or manipulate denominators | All 15 evaluation episodes written; 10 point FP retained; event FP = unmatched incidents only | No suppression; tails and miss reported | PASS |
| Persistence, hysteresis, mode-aware rules, sensor quality, pump curve, flow balance, grouping where supported | `detection.py`; alarm lifecycle checks; `ALARM-HISTORY-COMPLETE`; rule table in README | Grouped episodes, persistence, 2-sample clear, 300 s grouping, mode suppression, curve/balance/redundancy rules | PASS |
| Calibration and evaluation scenario sets; deterministic seeds; no overfitting | `calibration` and `evaluation` sets differ; seed 20261022; `reports/final/summary.json` | Calibration 7/7 events; evaluation 10/11; no shared windows | PASS |
| Ground truth isolated from detector inputs | `DETECTOR-ISOLATION` poison test; `TELEMETRY-NO-GROUND-TRUTH`; `ALARM-NO-SCENARIO-ID` | Output unchanged under poisoned label columns | PASS |
| Sensor faults not automatically classified as process faults; uncertainty reported | RULE-006U `UNCERTAIN`; RULE-010 `REDUNDANCY_AMBIGUOUS`; category matching; 4/4 sensor events | Sensor faults detected as sensor faults; ambiguous attribution disclosed | PASS |
| Preserve existing tests and add targeted tests | Original 11 tests retained and extended; `python -m pytest -q` | 68 passed in main (43.31 s) and clean (34.52 s) on 2026-10-29; targeted suite 17 passed (31.56 s); no original test removed | PASS |
| 3 facilities, 20 pumps, 30 tanks, 60 valves | Master counts; `MASTER-SCALE`, `SENSOR-COUNT`; `reports/final/summary.json` | Exact counts reproduced | PASS |
| Exact 100,000-row configuration while retaining 316,800-row full volume | `--scenario-set baseline --target-telemetry-rows 100000`; 120x455 + 100x454; default full 316,800 | 100,000 exact; full path unchanged; compact 99,000 retained as historical demonstration | PASS |
| Run all SQL queries and validate actual results | `sql_query_report.json` for every run; 20 declared expectations; SQLite export | 20/20 PASS; zero-row assertions return 0 | PASS |
| Machine-readable and readable reports with PASS/FAIL/WARN/NOT_IMPLEMENTED | `validation_results.csv`, `evaluation_metrics.json/csv`, `sql_query_report.json`, `evaluation_summary.md`, `reports/final/summary.json` | Reports generated and copied to `reports/final/` | PASS |
| Clean install, packaging, CLI and database initialization | Fresh 2026-10-29 virtual environment: `python -m venv`, `python -m pip install -e . pytest`, `yottaflex --version`, exact/full/default/evaluation pipelines and SQLite checks | 68/68 tests passed in 34.52 s; CLI and all pipelines completed under pandas 3.1.0 / NumPy 2.5.4; SQLite integrity `ok`, zero FK violations | PASS |
| Reproducibility after the audit fixes | 2026-10-27 full/default reproduction plus 2026-10-29 exact-100k `baseline-100k`, `baseline-100k-b` and clean `exact-clean-current`; `reports/final/reproducibility.json` and `reproducibility_100k.json` | Main exact 20/23 byte-identical, 3 timestamp-only differences logically equal; clean exact 19/23 with timestamp/last-bit differences; all 19 SQLite tables logically equal | PASS |
| Cross-version exact-100k rerun | Fresh pandas 3.1.0 / NumPy 2.5.4 environment; exact-100k pipeline; compare counts, metrics and artifacts | Same 100,000/341/87/20 results and metrics; 19/23 artifacts byte-identical; 3 timestamp-only plus one last-bit float report difference; raw SQLite 16/19 exact, 17/19 after timestamp removal, 19/19 logically equal with two float-only tables | WARN |
| Cross-version full/default and evaluation pipelines | Clean `full-default-clean-current` and `evaluation-clean-current` reruns | Counts, validation/SQL and event/point metrics match main; only exact-100k files show documented last-bit float differences | PASS |
| Observed-only point coverage | `tests/test_evaluation.py::test_missing_measurements_are_excluded_from_point_denominator`; `positive_rows_observed` excludes missing quality/null measurements | Coverage counts 2 of 3 expected positive rows, not 3 of 3 | PASS |
| Secrets, personal information and large-file review | Tracked-file scan; absolute path redaction in copied evidence; no credential/token/private-key hits | No tracked file over 1 MB; local paths redacted without changing metrics; original config hashes retained in manifests and redaction mismatch documented | PASS |
| Update README and create methodology/validation/decision documents | `README.md`, `docs/detection_methodology.md`, `docs/evaluation_methodology.md`, `docs/validation_report.md`, `docs/implementation_decisions.md` | All present and linked | PASS |
| Record complete task prompt in AI prompt history | `ai_usage/prompt_history.md`; `ai_usage/prompts/2026-10-28-remediation.md`; `ai_usage/prompts/2026-10-28-final-verification.md` | Final verification prompt recorded verbatim; publication authorization `push` recorded verbatim; 2026-10-27 audit prompt recorded verbatim; the prior 2026-10-28 remediation and earlier 1.x/2.0 implementation prompts remain explicitly reconstructed | WARN |
| Do not push/publish without explicit authorization | `6103e1a` and 2026-10-27 corrections are on `origin/main` after prior authorizations; the user explicitly authorized the 2026-10-28 push with the prompt `push` | Final push to `origin/main` after the audit; no force-push/history rewrite | PASS |
| Detection coverage on independent evaluation set | 11 events; 1 light-leak miss; residual above absolute floor but corroboration/persistence fails; event recall 0.9091 | Documented sensitivity limitation, not hidden or tuned away | WARN |
| Populate real equipment state history | `equipment_state_events` in CSV/SQLite/JSON/SQL; 341 rows in 100k baseline; allowed-transition tests | Initialization + scenario transitions only; no placeholder rows; transitions, refs, timestamps and DB count verified | PASS |
| Field-level documentation for all ten core entities | `docs/data_dictionary.md` | Types, keys, constraints, units, defaults, relationships, cardinality, lifecycle and history documented; state-history table covered | PASS |
| CSV, JSON, SQLite and portable SQL exports | `export-json`, `export-sql-script`, `export-sql`; 100k export test | 18 tables, 101,275 rows; SQL seed executed into new DB with integrity `ok`, zero FK violations and matching telemetry IDs | PASS |
| State transitions validated | `state_history.py`; `test_equipment_state_history_is_append_only_and_valid`; invalid-transition test | Allowed transitions enforced; invalid PUMP ACTIVE?LEAKING rejected | PASS |
| Negative scenarios and unrelated data intact | `tests/test_negative_scenarios.py`; five NEG controls | 5/5 PASS; baseline shapes unchanged after each copy-based control | PASS |

Overall status: **PASS with three review-level WARNs**: light-leak coverage (WARN), reconstructed
earlier prompt records (WARN), and cross-version last-bit float serialization (WARN). The
clean-environment installation, 68-test suite and exact/full/default/evaluation reruns were directly
verified, and ignored generated outputs were removed. These caveats are not rows in the executable
validation CSV and are not merged into its 87-row denominator. None is a fabricated success; each is
an explicit limitation.

## 11. Interpretation and Limitations

- The 2.0 metrics are not comparable to the 1.x numbers because the units changed. Do not quote
  `0.010638` as if it were event precision; it was a hybrid statistic.
- Event recall `0.9091` means 10 of 11 injected events were found. It does not mean the detector has
  perfect point accuracy or zero latency.
- Point recall `0.8038` is dominated by the 90-sample light leak and activation latency. Point
  precision `0.9883` includes 10 tail samples that are intentionally retained.
- Event false positives are zero because every incident matched an event. The point false positives
  show that episode resolution is not instantaneous; this is exactly what separate point evaluation
  is meant to expose.
- Sensor-fault latency is longer than process latency by design. A stuck sensor needs 30 minutes of
  evidence; a 3,600 s matching allowance reflects that, not leniency in counting.
- The light leak's 10-minute residual is above the absolute `5 m3/h` floor, but the `0.15 pp`
  decline corroboration and `480 s` persistence are not both met; RULE-002's `0.30 pp` trigger did
  not fire for this event. Lowering thresholds until it was detected would be evaluation-set tuning and would
  likely increase false alarms.
- Point coverage now counts only observed positive rows. Missing/null measurements are excluded from
  both the point denominators and the coverage numerator. The audit fix did not change the final
  evaluation metrics because the missing-sensor scenario removes rows and the remaining labelled
  rows are observed.
- Sensor-fault localization can be ambiguous between level and pressure. The detector reports the
  ambiguity instead of asserting a specific faulty device.
- The simulator is synthetic and simplified. These results do not establish real-plant performance.
- Dependencies are lower-bounded, not upper-pinned. Within one environment, reruns are byte-identical;
  across pandas/NumPy versions, peak floats can differ at about `1e-13` while all metrics and
  classifications remain identical.
- The original verbatim task prompt was not retained in the conversation record; the prompt history
  contains a detailed reconstruction and says so explicitly.

## 12. Reproduction Commands

From the repository root (PowerShell or bash; use a fresh output directory each time):

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS:      source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
yottaflex --version

# Default full run (316,800 rows)
yottaflex pipeline --mode full --seed 20261022 --output-dir <fresh-output-dir>/full-run

# Independent evaluation set (316,740 rows; 60 labelled missing rows)
yottaflex pipeline --mode full --seed 20261022 --scenario-set evaluation \
  --output-dir <fresh-output-dir>/evaluation-run

# Calibration set
yottaflex pipeline --mode full --seed 20261022 --scenario-set calibration \
  --output-dir <fresh-output-dir>/calibration-run

# Exact 100,000-row baseline (120 x 455 + 100 x 454; 7.583 h)
yottaflex pipeline --mode full --seed 20261022 --scenario-set baseline \
  --target-telemetry-rows 100000 --output-dir <fresh-output-dir>/baseline-100k

# Historical 99,000-row compact demonstration
yottaflex pipeline --mode full --seed 20261022 --scenario-set compact --duration 7.5 \
  --output-dir <fresh-output-dir>/compact-run

# Portable exports from any completed run
yottaflex export-json --output-dir <fresh-output-dir>/baseline-100k
yottaflex export-sql-script --output-dir <fresh-output-dir>/baseline-100k

# Tests, validation, SQL
python -m pytest -q
yottaflex validate --output-dir <fresh-output-dir>/evaluation-run
yottaflex run-sql --output-dir <fresh-output-dir>/evaluation-run \
  --sql-file sql/analysis_queries.sql

# Exact-100k reproducibility: run twice and compare the documented deterministic files
yottaflex pipeline --mode full --seed 20261022 --scenario-set baseline \
  --target-telemetry-rows 100000 --output-dir <fresh-output-dir>/repro-a
yottaflex pipeline --mode full --seed 20261022 --scenario-set baseline \
  --target-telemetry-rows 100000 --output-dir <fresh-output-dir>/repro-b
```

The 2026-10-29 exact-100k comparison used two fresh external runs (`baseline-100k`,
`baseline-100k-b`) and is recorded in `reports/final/reproducibility_100k.json`. Twenty of 23 files
were byte-identical; the three differences were wall-clock-only fields in
`evaluation_metrics.csv`, `validation_results.csv` and `validation_summary.json`. Absolute paths in
`config.json` and timestamped manifest entries are expected to differ between directories. The
prior full/default comparison remains recorded in `reports/final/reproducibility.json`. A fresh
2026-10-29 virtual environment installed package metadata version `2.0.0`, passed 68 tests and ran
the exact/full/default/evaluation pipelines; the cross-version differences are recorded in §8.1
and `reproducibility_100k.json`.

**Privacy redaction:** absolute local-path strings in copied evidence (`baseline_tests.txt`,
`reports/final/reproducibility.json`, and the six `reports/final/yf2-*/config.json` and
`pipeline.log` files) were replaced with neutral labels (`<external-temp>` / `<local-user>`). No
reported metric, row count, status or log message was changed, and the path-independent
configuration hash is unaffected. The redacted `config.json` copies no longer match the original
`config.json` SHA-256 entries in their `run_manifest.json`; those original entries are retained and
the difference is due solely to path redaction. No credentials, tokens, private keys or files over
1 MB were found in tracked files.

## 13. 2026-10-29 Final Verification Evidence

This verification pass re-ran the workflows rather than relying on the prior acceptance report. The
starting repository was `main` at `f8f8d6ae208cf3024ec031dbecc5b80c69841c19` with a clean tree. No
source-code defect was found, so no source, threshold, scenario, label or matching behavior was
changed. All pipeline and test commands below exited `0`; each test run reported zero failures and
zero skips.

- **Main and targeted tests:** `python -m pytest -q` ? **68 passed in 43.31 s**. The targeted
  negative/state/submission suite, `python -m pytest -q tests/test_negative_scenarios.py
  tests/test_scenarios.py tests/test_submission_artifacts.py`, ? **17 passed in 31.56 s**.
- **Clean-environment tests:** a fresh Python 3.14.4 venv with pandas 3.1.0, NumPy 2.5.4 and pytest
  9.2.0 was installed with `python -m pip install -e . pytest`; `<clean-venv>/Scripts/python -m
  pytest -q` ? **68 passed in 34.52 s**; `yottaflex --version` ? **2.0.0**.
- **Fresh exact-100k:** `baseline-100k` and `baseline-100k-b` each produced **100,000** telemetry
  rows (`120 x 455 + 100 x 454`), **3/20/30/60** facilities/pumps/tanks/valves, **135** pipes,
  **220** sensors, **341** state events, **87 PASS / 0 FAIL / 0 WARN / 0 NOT_IMPLEMENTED**,
  **20/20 SQL PASS**, and **18 populated SQLite tables** (19 schema tables; `detection_results`
  empty). Telemetry IDs, sensor/timestamp pairs, references, cadence, ordering, topology and
  foreign keys were checked directly. A third exact run, `exact-clean-current`, reproduced the same
  counts and metrics in the clean environment.
- **Full/default:** main and clean runs produced **316,800** rows, 341 state events,
  validation/SQL **87/20**, event TP/FN/FP **4/0/0**, and point TP/FP/TN/FN
  **882/8/145192/18**; metrics matched across environments.
- **Evaluation:** main and clean runs produced **316,740** rows, 355 state events, validation/SQL
  **87/20**, **15** alarm episodes merged into **10** incidents. Independent recomputation from
  ground truth, alarms, incidents and telemetry gave event TP/FN/FP **10/1/0**,
  precision/recall/F1 **1.0000/0.9091/0.9524**, and point TP/FP/TN/FN
  **844/10/112190/206**, precision/recall/F1 **0.9883/0.8038/0.8866**, with point FPR
  **0.0000891**. Latency min/median/mean/max was **60/300/702/3180 s**; 203,490 unknown samples were
  excluded, two predictions outside labelled windows were reported but not counted as FP, all
  4/4 sensor-fault events matched `SENSOR_FAULT` incidents, and the eight NORMAL windows were
  alarm-free at incident level. Clean metrics matched the main metrics.
- **Five negative controls:** direct `Validator.test_negative_scenarios()` output returned
  `NEG-001` through `NEG-005` **PASS**; baseline master-data shapes remained unchanged. State-history
  tests passed and the 341-row table contains 333 initialization plus 8 scenario start/recovery
  events.
- **Exports:** JSON **18 tables / 101,275 rows**; portable SQL seed **29,733,009 bytes / 101,275
  rows**. Main run A SHA-256 values are `380154ad9dd8b72de9592e63181ceed8dcbe4cf1b675bc88a79a4704686a7338`
  for SQL and `b952b5a26134a42ef44855499c973a134f55d3ae92fce755535f19539eb05ca5` for the JSON
  manifest; run B produced `fcac66dfe7d13dce90d03aeb31758a5c107898980cae60cc69ed830cce62e5d7`
  and `85e922665a8feb3021e6dfa56410a5fc76b4242596619f95fe11f3b2a5f0e63c` respectively because
  timestamps are included. Both SQL seeds executed into fresh SQLite databases with
  `integrity_check=ok`, zero FK violations, 100,000 telemetry rows and 341 state events; CSV, JSON,
  SQLite and SQL telemetry ID sets matched.
- **Light leak:** `GT-000001` remains **MISSED**. Diagnostic: 90 samples, residual median
  **8.322721 m3/h** (mean 7.968123), 82/90 above the `5 m3/h` floor, level-decline median
  **-0.1315 pp**, and zero overlapping alarms. The longest active-and-corroborated run was 5 samples
  (240 s elapsed, 300 s sample-count duration); the longest active-without-corroboration run was 7
  samples (360 s elapsed, 420 s sample-count duration). RULE-006/RULE-006U corroboration and 480 s
  persistence do not both hold; this is retained as a documented limitation, not tuned away. The
  full diagnostic is in [`reports/final/light_leak_diagnostic.json`](../reports/final/light_leak_diagnostic.json).
- **Reproducibility:** main exact A/B **20/23** byte-identical; the other three differ only in
  wall-clock `evaluated_at`/`validated_at` fields and are logically equal. All 19 SQLite tables are
  logically equal (raw-exact 17/19; 19/19 after timestamp removal). The fresh clean environment
  produced **19/23** byte-identical files: three timestamp-only differences plus one last-bit
  float difference in `sql_query_report.json`; raw SQLite **16/19**, **17/19** after timestamp
  removal, and 19/19 logically equal with the documented float tolerance. No counts, classes or
  metrics changed. Clean exact/full/default/evaluation metrics match main.
- **Installation and CLI:** the clean venv installed the package and pytest from the repository,
  reported version 2.0.0, and ran exact-100k, full/default and evaluation pipelines successfully.
- **AI-use and hygiene:** the current 2026-10-29 prompt is preserved verbatim; earlier records remain
  labelled reconstructed. The final security/PII/large-file scan found no secrets or PII, no tracked
  file over 1 MB, no forced history changes and no whitespace errors in `git diff --check`.
  Ignored generated logs, caches and `data/processed/` run outputs were removed; tracked
  `.gitkeep` placeholders remain.

The final matrix with the requested seven columns is in
[`docs/requirement_matrix.md`](requirement_matrix.md). The machine-readable evidence bundle is
[`reports/final/summary.json`](../reports/final/summary.json),
[`reports/final/reproducibility_100k.json`](../reports/final/reproducibility_100k.json) and
[`reports/final/light_leak_diagnostic.json`](../reports/final/light_leak_diagnostic.json).

## 14. Artifact Index

| Artifact | Contents |
|---|---|
| `reports/final/summary.json` | Machine-readable metrics, validation reconciliation and review caveats for all final runs |
| `reports/final/reproducibility.json` | Prior 19-file full/default hash comparison, config hashes and DB logical comparison |
| `reports/final/reproducibility_100k.json` | 2026-10-29 exact-100k two-run hash/logical comparison, clean-environment comparison and artifact counts |
| `reports/final/light_leak_diagnostic.json` | Current `GT-000001` residual, decline, longest corroboration/persistence runs and zero overlapping alarms |
| `reports/final/yf2-100k/` | Compact exact-100k evidence: redacted config, metadata, telemetry count/hash manifest, master CSVs, alarms, evaluation events, validation, metrics, SQL report, state events and hash summary |
| `docs/requirement_matrix.md` | Requirement-to-implementation/evidence/status matrix and review caveats |
| `ai_usage/prompts/2026-10-28-remediation.md` | Reconstructed 2026-10-28 prompt record; verbatim source not retained |
| `ai_usage/prompts/2026-10-29-final-audit.md` | Verbatim 2026-10-29 final-audit prompt record |
| `reports/final/yf2-evaluation/evaluation_metrics.json` | Full nested evaluation result |
| `reports/final/yf2-evaluation/evaluation_events.csv` | Per-event outcome/latency |
| `reports/final/yf2-evaluation/alarm_incidents.csv` | Incident membership/classification |
| `reports/final/yf2-evaluation/alarms.csv` | Alarm episodes |
| `reports/final/yf2-evaluation/alarm_events.csv` | Append-only CREATED/RESOLVED history |
| `reports/final/yf2-evaluation/validation_results.csv` | 87 validation rows |
| `reports/final/yf2-evaluation/sql_query_report.json` | 20 SQL assertions/results |
| `reports/final/yf2-evaluation/evaluation_summary.md` | Human-readable evaluation report |
| `reports/final/yf2-evaluation/pipeline.log` | Clean-run console log |
| `reports/final/yf2-full/` | Default full-run evidence |
| `reports/final/yf2-starter/` | Starter-run evidence |
| `reports/final/yf2-compact-99k/` | Historical compact 99,000-row evidence |
| `reports/final/yf2-calibration/` | Calibration evidence |
| `reports/final/yf2-repro/` | Second full/default reproducibility run |
| `docs/baseline_findings.md` | Pre-change audit |
| `docs/detection_methodology.md` | Rules, lifecycle and thresholds |
| `docs/evaluation_methodology.md` | Event/point policy and examples |
| `docs/implementation_decisions.md` | Decisions and rejected alternatives |
| `docs/handover_guide.md` | Onboarding and reproduction |

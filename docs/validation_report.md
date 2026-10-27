# Validation Report (YottaFlex 2.0.0)

**Status:** PASS with one documented detection-coverage WARN (light leak sensitivity) and one
documentation WARN (the original task prompt was reconstructed, not retained verbatim).

**Date:** 2026-10-27  
**Environment:** Python 3.14.4, pytest 9.1.1, Windows 11, seed `20261022`, 60 s cadence  
**Repository state:** commit `f4b3f75` plus the uncommitted 2.0 changes; no push or publication  
**Primary evidence:** clean run directories `yf2-evaluation`, `yf2-calibration`, `yf2-full`,
`yf2-starter`, `yf2-100k`, `yf2-repro` (compact copies in `reports/final/`)

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
`0.8038`, F1 `0.8866`). The only missed event is the `1.5% of capacity/hour` light leak, which is
below the documented balance/decline sensitivity floor. All 8 NORMAL windows were alarm-free at the
incident level. The 10 point false positives are short episode tails after anomalies end; they are
retained and reported, not suppressed.

All 87 validation checks, all 20 SQL assertions and all 61 tests pass. Two clean full/default runs
produced 19 byte-identical deterministic artifacts, and the path-independent configuration hash
matched.

## 2. Controls and Evidence Rules

- **Baseline first.** The pre-change workflows were run from clean directories before any source
  edits. Historical figures were treated as observations to verify, not as inputs.
- **Same seed and cadence.** All reported runs use seed `20261022` and 60 s sampling.
- **Ground truth isolated.** The detector selects only sensor ID, timestamp, measured value, quality
  status, operating mode and master metadata. Validation poisons scenario/ground-truth/physical
  columns and confirms detector output is unchanged.
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

| Run | Mode | Scenario set | Duration | Telemetry rows | Scenario/GT windows | Alarm episodes | Incidents | Validation | SQL |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| `yf2-starter` | starter | default | 24 h | 51,840 | 10 | 7 | 4 | 87 PASS | 20 PASS |
| `yf2-full` | full | default | 24 h | 316,800 | 10 | 7 | 4 | 87 PASS | 20 PASS |
| `yf2-100k` | full | compact | 7.5 h | 99,000 | 9 | 7 | 4 | 87 PASS | 20 PASS |
| `yf2-calibration` | full | calibration | 24 h | 316,740 | 15 | 10 | 7 | 87 PASS | 20 PASS |
| `yf2-evaluation` | full | evaluation | 24 h | 316,740 | 19 | 15 | 10 | 87 PASS | 20 PASS |

Calibration and evaluation have 316,740 rows because the labelled missing-sensor scenario removes
60 rows. The missing rows are intentional. The compact run is exactly `220 x 450 = 99,000` rows.

### 4.1 Final metric summary

| Run | Event TP/FN/FP | Event P / R / F1 | Point TP/FP/TN/FN | Point P / R / F1 |
|---|---|---|---|---:|---|
| starter, default | 4 / 0 / 0 | 1.0000 / 1.0000 / 1.0000 | 880 / 7 / 23,753 / 20 | 0.9921 / 0.9778 / 0.9849 |
| full, default | 4 / 0 / 0 | 1.0000 / 1.0000 / 1.0000 | 882 / 8 / 145,192 / 18 | 0.9910 / 0.9800 / 0.9855 |
| full, compact | 4 / 0 / 0 | 1.0000 / 1.0000 / 1.0000 | 246 / 5 / 40,915 / 18 | 0.9801 / 0.9318 / 0.9553 |
| full, calibration | 7 / 0 / 0 | 1.0000 / 1.0000 / 1.0000 | 508 / 7 / 171,593 / 92 | 0.9864 / 0.8467 / 0.9112 |
| **full, evaluation** | **10 / 1 / 0** | **1.0000 / 0.9091 / 0.9524** | **844 / 10 / 112,190 / 206** | **0.9883 / 0.8038 / 0.8866** |

The default and compact runs are demonstration/regression configurations. The calibration set
checks mechanism coverage. The evaluation set is the reported independent result.

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
capacity/hour leak. It is below the `max(5 m3/h, 8%)` balance floor and below the 0.30 pp / 5 min
decline threshold. It is retained as a documented sensitivity limit rather than tuned away on the
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
| Light leak below sensitivity floor (GT-000001) | 90 |
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
| full/compact | ~100k-row configuration | Exactly 99,000 rows; 4/4 events, 0 FP |
| full/calibration | Different windows/equipment/severities; all four sensor faults | 7/7 events, 0 FP; event F1 1.0000 |
| full/evaluation | Independent reported set | 10/11 events, 0 FP; F1 0.9524 |

Calibration and evaluation do not share event windows or equipment selections. The calibration run
detected bias, drift, stuck and missing faults with different severities; its point recall `0.8467`
reflects expected sensor activation latency, while its event recall is 1.0000. No threshold was
changed after the evaluation run was inspected.

## 7. Validation and SQL Evidence

### 7.1 Validation checks

Final validation result (all five final runs): **87 PASS, 0 FAIL, 0 WARN, 0 NOT_IMPLEMENTED**.

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

The SQLite export contains 17 tables, passes `PRAGMA integrity_check`, and has an empty
`PRAGMA foreign_key_check`. Row counts match the CSV artifacts.

### 7.3 Test suite

`python -m pytest -q` → **61 passed in 90.17 s** on the final re-run. The original 11 tests are
retained; 50 targeted tests were added for detection lifecycle/grouping/mode suppression/isolation,
evaluation units and edge cases, data integrity, scenario injection, validation/SQL and
integration/reproducibility.

## 8. Reproducibility

Two clean full/default runs (`yf2-full` and `yf2-repro`) were compared. **19 of 19 deterministic
artifacts were byte-identical**, including:

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
316,800 in both runs.

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
| Telemetry, compact | ~100,000 | 99,000 | PASS |
| Telemetry, evaluation | 316,740 (60 labelled rows removed) | 316,740 | PASS |
| Duplicate `(sensor, timestamp)` samples | 0 | 0 | PASS |
| Unlabelled gaps in window coverage | 0 | 0 | PASS |
| SQLite tables exported | 17 | 17 | PASS |
| SQLite integrity / FK violations | ok / 0 | ok / 0 | PASS |

Sensor composition was verified by validation: every pump has discharge flow and pressure; every
tank has level, pressure, inlet flow and outlet flow; every valve has through flow. The sensor count
is preserved at 220 by using one valve flow sensor and four physically necessary tank sensors.

Telemetry contains no scenario/ground-truth/expected-label columns. Alarms carry no `scenario_id`.
Detector isolation is proven by the poison test, not only by inspecting column lists.

## 10. Requirement Matrix

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
| Preserve existing tests and add targeted tests | Original 11 tests retained; 50 added; `python -m pytest -q` | 61 passed | PASS |
| 3 facilities, 20 pumps, 30 tanks, 60 valves | Master counts; `MASTER-SCALE`, `SENSOR-COUNT`; `reports/final/summary.json` | Exact counts reproduced | PASS |
| ~100,000-row configuration while retaining 316,800-row full volume | `--scenario-set compact --duration 7.5`; 99,000 rows; default full 316,800 | Both volumes verified | PASS |
| Run all SQL queries and validate actual results | `sql_query_report.json` for every run; 20 declared expectations; SQLite export | 20/20 PASS; zero-row assertions return 0 | PASS |
| Machine-readable and readable reports with PASS/FAIL/WARN/NOT_IMPLEMENTED | `validation_results.csv`, `evaluation_metrics.json/csv`, `sql_query_report.json`, `evaluation_summary.md`, `reports/final/summary.json` | Reports generated and copied to `reports/final/` | PASS |
| Update README and create methodology/validation/decision documents | `README.md`, `docs/detection_methodology.md`, `docs/evaluation_methodology.md`, `docs/validation_report.md`, `docs/implementation_decisions.md` | All present and linked | PASS |
| Record complete task prompt in AI prompt history | `ai_usage/prompt_history.md` | Session brief reconstructed in detail; original verbatim text was not retained, so marked as reconstructed | WARN |
| Do not push or publish to GitHub | `git remote -v` exists; no push/commit performed; all changes remain uncommitted | No publication | PASS |
| Detection coverage on independent evaluation set | 11 events; 1 light-leak miss; event recall 0.9091 | Documented sensitivity floor, not hidden or tuned away | WARN |

Overall status: **PASS with two WARN items** — the light-leak sensitivity floor and the reconstructed
prompt record. Neither is a fabricated success; both are explicit limitations.

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
- The light leak is below the physical sensitivity floor. Lowering thresholds until it was detected
  would be evaluation-set tuning and would likely increase false alarms.
- Sensor-fault localization can be ambiguous between level and pressure. The detector reports the
  ambiguity instead of asserting a specific faulty device.
- The simulator is synthetic and simplified. These results do not establish real-plant performance.
- The original verbatim task prompt was not retained in the conversation record; the prompt history
  contains a detailed reconstruction and says so explicitly.

## 12. Reproduction Commands

From the repository root (PowerShell or bash; use a fresh output directory each time):

```bash
python -m pip install -r requirements.txt
python -m pip install -e .

# Default full run (316,800 rows)
yottaflex pipeline --mode full --seed 20261022 --output-dir data/processed/full-run

# Independent evaluation set (316,740 rows; 60 labelled missing rows)
yottaflex pipeline --mode full --seed 20261022 --scenario-set evaluation \
  --output-dir data/processed/evaluation-run

# Calibration set
yottaflex pipeline --mode full --seed 20261022 --scenario-set calibration \
  --output-dir data/processed/calibration-run

# ~100,000-row compact configuration
yottaflex pipeline --mode full --seed 20261022 --scenario-set compact --duration 7.5 \
  --output-dir data/processed/compact-run

# Tests, validation, SQL
python -m pytest -q
yottaflex validate --output-dir data/processed/evaluation-run
yottaflex run-sql --output-dir data/processed/evaluation-run \
  --sql-file sql/analysis_queries.sql

# Reproducibility: run the full/default pipeline twice and compare
yottaflex pipeline --mode full --seed 20261022 --output-dir data/processed/repro-a
yottaflex pipeline --mode full --seed 20261022 --output-dir data/processed/repro-b
```

The independent comparison for this report used `yf2-full` and `yf2-repro` and is recorded in
`reports/final/reproducibility.json`. Absolute paths in `config.json` and wall-clock fields in the
timestamped CSVs are expected to differ between directories.

## 13. Artifact Index

| Artifact | Contents |
|---|---|
| `reports/final/summary.json` | Machine-readable metrics for all five final runs |
| `reports/final/reproducibility.json` | 19-file hash comparison and config hashes |
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
| `reports/final/yf2-100k/` | Compact 99,000-row evidence |
| `reports/final/yf2-calibration/` | Calibration evidence |
| `reports/final/yf2-repro/` | Second full/default reproducibility run |
| `docs/baseline_findings.md` | Pre-change audit |
| `docs/detection_methodology.md` | Rules, lifecycle and thresholds |
| `docs/evaluation_methodology.md` | Event/point policy and examples |
| `docs/implementation_decisions.md` | Decisions and rejected alternatives |
| `docs/handover_guide.md` | Onboarding and reproduction |

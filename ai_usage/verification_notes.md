# Independent Verification Notes (Historical 1.x Record; 2.0 Audit Appended)

> **Historical record — not current evidence for the 1.x numbers.** The 1.x audit below was performed
> on version 1.0.0 (18 validation checks, 11 tests). Its 1,245-alarm-row result and
> `precision=0.010638` are the defective metric reproduced and explained in
> [`docs/baseline_findings.md`](../docs/baseline_findings.md). The 2.0 results are in
> [`docs/validation_report.md`](../docs/validation_report.md): 87 executable validation rows,
> 20 SQL assertions, 68 tests, and separate event/point metrics. The Git publication note in the 1.x
> section is historical; the current 2.0/audit/remediation status is recorded below.

## 2026-10-28 Exact-100k/State-History/Export Remediation (Current)

- **Tool/model:** OpenCode / DeepSeek V4.1 Flash Free
- **Scope:** Add an exact 100,000-row configuration without disturbing the 316,800-row path, populate
  real equipment state history, add CSV/JSON/SQLite/portable-SQL exports, document all core entities,
  and re-verify the existing detector/evaluator without tuning. No thresholds, existing scenarios,
  ground truth or matching rules were changed.

**Commands and observed results:**

- `python -m pytest -q` → **68 passed** in the main environment. The prior 62-test suite
  passed in the 2026-10-27 main and fresh environments. The final acceptance pass below re-ran the
  68-test suite in the fresh pandas 3.1.0 / NumPy 2.5.4 environment; both runs passed.
- Exact-100k baseline (`--scenario-set baseline --target-telemetry-rows 100000`): **100,000** rows;
  **120 sensors x 455 + 100 sensors x 454**; duration **7.583333 h**; 341 state events; 87
  validation PASS / 0 FAIL / 0 WARN / 0 NOT_IMPLEMENTED; 20/20 SQL PASS; 18 populated SQLite tables.
- Full/default rerun: **316,800** rows, 341 state events, same 87/20 validation/SQL result; event
  TP/FN/FP `4/0/0`; point TP/FP/TN/FN `882/8/145192/18`.
- Evaluation rerun: **316,740** rows; event TP/FN/FP `10/1/0`, P/R/F1
  `1.0000/0.9091/0.9524`; point TP/FP/TN/FN `844/10/112190/206`, P/R/F1
  `0.9883/0.8038/0.8866`. The light-leak miss is preserved.
- Light-leak diagnostic: 90 samples; residual median `8.3227 m3/h`; 82/90 above the absolute
  `5 m3/h` floor; decline median `-0.1315 pp`; longest corroborated run `300 s`; longest
  active-without-corroboration `420 s`. Neither RULE-006 nor RULE-006U fired.
- Exact-100k two-run comparison (`yf-repro-100k/a,b`): **20/23 files byte-identical**; the other
  three (`evaluation_metrics.csv`, `validation_results.csv`, `validation_summary.json`) differed only
  in wall-clock `evaluated_at` / `validated_at` fields and were logically equal after removing those
  fields. All **19 SQLite tables** were logically equal, **18 populated**, `integrity_check=ok`,
  **zero foreign-key violations**.
- Portable exports: JSON 18 tables / 101,275 rows; SQL seed 101,275 rows / 29,733,009 bytes
  (remediation-era `sha256=86372f77388c7e6769744010f7706652fb2e35972aead77b5bf94cf0f7ea9f04`; the
  final-acceptance seed hash differs because it includes current audit timestamps); executed into a
  new SQLite database with `integrity_check=ok`, zero FK violations, 100,000 telemetry rows and 341
  state events; CSV/JSON/SQLite/SQL telemetry IDs matched. The JSON manifest stores a relative
  `source_root` (`..`) rather than an absolute path, so the export directory remains portable.
- State history: 341 rows = 333 initialization + 8 scenario transitions; unique `ESE-######` IDs;
  allowed transitions and references validated; no placeholder rows; not detector input.
- Security/PII/large-file scan: 0 secret/PII hits; no tracked file over 1 MB; `git diff --check`
  clean. Ignored `data/processed/` outputs remain untracked and were not treated as evidence.
- Git: final audit and local commit followed by an explicit `push` authorization from the user;
  pushed to `origin/main` without force-push or history rewrite.

**Remaining caveats:** light-leak sensitivity (WARN); reconstructed prompt records because the
original 1.x and prior 2026-10-28 prompt text were not retained verbatim (WARN; the latest `push`
prompt is verbatim); ignored local generated outputs remain untracked (WARN). The final acceptance
pass below re-ran the clean environment and supersedes the earlier "not repeated" note.

## 2026-10-28 Final Acceptance Verification (Current)

- **Tool/model:** OpenCode / DeepSeek V4.1 Flash Free.
- **Exact-100k commands:** `yottaflex pipeline --mode full --seed 20261022 --scenario-set baseline
  --target-telemetry-rows 100000 --output-dir <temp>/exact-a` and the same command into `exact-b`.
  Both produced **100,000** rows, **120 x 455 + 100 x 454**, 3/20/30/60 master counts, 135 pipes,
  220 sensors, 341 state events, 87 validation PASS, 20/20 SQL PASS and 18 populated SQLite tables.
  All telemetry IDs and `(sensor_id, timestamp)` pairs are unique; references, 60 s cadence,
  timestamp ordering and topology checks pass; no label columns are present in telemetry.
- **Independent metrics:** recomputed directly from the fresh evaluation run's ground truth,
  alarms, incidents and telemetry: event TP/FN/FP **10/1/0**, P/R/F1
  **1.0000/0.9091/0.9524**, 15 alarm episodes merged into 10 incidents, 5 corroborating episodes;
  point TP/FP/TN/FN **844/10/112190/206**, P/R/F1 **0.9883/0.8038/0.8866**, FPR **0.0000891**;
  latency min/median/max **60/300/3180 s**. The only miss is `GT-000001` (light leak); 203,490
  unknown samples were excluded and 2 unknown predictions were reported outside the denominator.
- **Light-leak diagnostic:** reproduced the detector's 10-minute regression-window calculation on
  `SNS-019`/`SNS-021`/`SNS-022`: 90 samples, residual median **8.322721 m3/h** (mean 7.968123),
  **82/90** above the absolute `5 m3/h` floor; 5-minute decline median **-0.1315 pp**. The event
  remains missed because decline corroboration and 480 s persistence do not both hold.
- **Full/default and evaluation:** fresh runs produced **316,800** rows (event 4/0/0; point
  `882/8/145192/18`) and **316,740** rows (event 10/1/0; point `844/10/112190/206`) respectively.
- **Clean installation:** fresh Python 3.14.4 venv (pandas 3.1.0, NumPy 2.5.4, pytest 9.2.0)
  created with `python -m venv`, `python -m pip install -e .`, `python -m pip install pytest`;
  `yottaflex --version` returned 2.0.0 and `python -m pytest -q` returned **68 passed**. The clean
  environment also regenerated the exact-100k baseline with identical counts and metrics.
- **Exports:** JSON 18 tables / **101,275** rows; SQL seed **29,733,009** bytes / **101,275** rows
  (current SHA-256 `15214c418346...`); executed into a new SQLite database with `integrity_check=ok`,
  zero FK violations, 100,000 telemetry IDs and 341 state events; CSV/JSON/SQLite/SQL IDs match.
- **Negative/state/model:** five negative controls PASS, state-history transition/reference tests
  PASS, `docs/data_dictionary.md` covers all ten core entities and lifecycle/effective-window rules.
- **Reproducibility:** main environment exact-a/b **20/23** byte-identical; the other three differ
  only in wall-clock `evaluated_at`/`validated_at` fields and are logically equal; all 19 SQLite
  tables logically equal after audit-timestamp removal. Clean environment: **19/23** byte-identical,
  with three timestamp-only differences and one last-bit float difference in `sql_query_report.json`;
  17/19 SQLite tables exactly equal, with telemetry/evaluation_metrics differing only at ~1e-15.
- **Remaining caveats:** light-leak sensitivity (WARN); reconstructed earlier prompt records (WARN);
  cross-version full/default and evaluation pipelines not repeated (WARN); ignored local generated
  outputs (WARN). No unverified secret/PII result is claimed.

## 2026-10-27 2.0 Submission-Readiness Audit (Historical)

- **Tool/model:** OpenCode / DeepSeek V4.1 Flash Free
- **Scope:** Re-run the 2.0 workflows against generated artifacts, reconcile documentation, verify
  isolation/negative controls/determinism, and fix only re-verified defects. No thresholds, scenarios,
  ground truth, or matching rules were changed.

**Commands and observed results:**

- Main environment (`Python 3.14.4`, pandas `3.0.3`, NumPy `2.4.6`): `python -m pytest -q` →
  **62 passed in 89.37 s** (final run). The main editable-install metadata was stale at `1.0.0`;
  the audit refreshed it with `pip install -e . --no-deps`, after which `pip show yottaflex` and
  `yottaflex --version` both reported `2.0.0`.
- Fresh virtual environment (`Python 3.14.4`, pandas `3.1.0`, NumPy `2.5.4`):
  `pip install -r requirements.txt`, `pip install -e .`, `yottaflex --version` → `2.0.0`;
  full/evaluation pipeline → 316,740 rows, event TP/FN/FP `10/1/0`, point TP/FP/TN/FN
  `844/10/112190/206`, validation `87 PASS / 0 FAIL / 0 WARN / 0 NOT_IMPLEMENTED`, SQL
  `20/20`, SQLite integrity `ok`; `pytest -q` → **62 passed in 77.07 s** with no warning summary.
- Fresh main-environment post-fix evaluation run: deterministic `alarms.csv`, `alarm_events.csv`,
  `alarm_incidents.csv`, `evaluation_events.csv`, `evaluation_metrics.json`,
  `evaluation_summary.md`, `simulation_metadata.json`, `simulation_runs.csv` and
  `sql_query_report.json` were byte-identical to the stored evaluation evidence.
- Two fresh full/default runs after the fixes in the main environment: 19/19 deterministic
  artifacts byte-identical; configuration hash `d422f3bbee3dcadc`; 316,800 telemetry rows; SQLite
  integrity `ok`, zero foreign-key violations; 17 populated tables logically identical except
  wall-clock `evaluated_at`/`validated_at`. The clean pandas 3.1.0 / NumPy 2.5.4 environment matched
  all metrics and 17/19 artifacts; `alarms.csv` and `sql_query_report.json` differed only in
  `peak_value` floats at about `1e-13`.
- Independent isolation check: poisoned scenario/ground-truth/physical columns over a four-hour
  08:00-12:00 slice (52,800 rows) produced the same three alarms as the clean run.
- Light leak: 10-minute residual median `8.32 m3/h` (82/90 samples above the absolute `5 m3/h`
  floor); 5-minute decline median `-0.131 pp`; longest corroborated run `300 s`, longest
  active-without-corroboration `420 s`, persistence `480 s`; neither RULE-006 nor RULE-006U fired
  for this event.
- The audit fixed and covered two re-verified defects: pandas 3.1 mode-fill deprecation warning and
  point coverage counting unobserved positive rows as observed. The fixes did not change reported
  metrics.
- Git: 2.0 commit `6103e1a` is on `origin/main` after explicit authorization; the audit corrections
  were committed and pushed to `origin/main` after separate explicit authorization. No force-push or
  history rewrite was performed.

Current evidence is consolidated in [`docs/validation_report.md`](../docs/validation_report.md) and
[`reports/final/`](../reports/final/). The 1.x notes below are retained as historical context.

---

**Date:** 2026-10-26
**Runtime:** Python 3.14.4, Windows
**Seed:** 20261022

## Workflows actually run

- `pip install -r requirements.txt` — completed successfully.
- `pip install -e .` — completed successfully; `yottaflex --version` reports 1.0.0.
- `yottaflex pipeline --mode starter --seed 20261022 --output-dir data/processed/starter-run` — run from a previously absent output directory.
- `yottaflex pipeline --mode full --seed 20261022 --output-dir <temporary full-a directory>` — completed.
- The individual full-mode `generate`, `simulate`, `detect`, `evaluate`, `validate`, and `export-sql` commands from the README were also run in sequence.
- The README SQL command executed all 10 statements in `sql/analysis_queries.sql`.
- `pytest tests/ -v` — 11 passed.
- `python -m compileall -q src tests` — completed successfully.
- Ruff passes on the rewritten `detection.py`, `evaluation.py`, and `validation.py`. A whole-repository Ruff run still reports 69 findings, predominantly existing unused imports and typing/style rules; see the final audit summary.

## Full-scale output and integrity

| CSV | Rows |
|---|---:|
| facilities.csv | 3 |
| pumps.csv | 20 |
| tanks.csv | 30 |
| valves.csv | 60 |
| pipes.csv | 134 |
| sensors.csv | 220 |
| operating_modes.csv | 4 |
| simulation_runs.csv | 1 |
| scenario_definitions.csv | 4 |
| ground_truth.csv | 4 |
| telemetry.csv | 316,800 |
| alarms.csv | 1,245 |

The full mode distributes pumps 7/7/6, tanks 10/10/10, and valves 20/20/20 across the three facilities. All three equipment graphs were connected. Independent checks confirmed facility, equipment, pipe-node, telemetry, simulation-run, operating-mode, alarm, scenario, and ground-truth references. SQLite `PRAGMA foreign_key_check` returned no rows.

The 316,800 telemetry rows are calculated as 220 sensors times 1,440 one-minute samples. The prior nominal `telemetry_points` setting was unused and has been removed so it no longer implies a 100,000-row cap.

## Anomaly and detection evidence

The four generated ground-truth event types were all associated with alarms by equipment/time (and affected sensor where applicable):

| Event | Observed evidence | Associated alarm rules |
|---|---|---|
| Leak | Tank-level mean 57.4489% in the preceding hour, 56.4123% during the event | RULE-002 |
| Blockage | Pump flow mean 51.7550 to 36.0824 m3/h; pressure 5.4330 to 7.2202 bar | RULE-005 |
| Pump degradation | Pump flow mean 45.0030 to 38.6753 m3/h | RULE-005 |
| Sensor fault | 181/181 affected readings marked UNCERTAIN; measured flow mean 136.4762 to 152.1464 m3/h | RULE-004 only |

The detector drops `scenario_id` and `physical_state_value` before evaluating telemetry. The persisted telemetry CSV contains neither field. The evaluator matches alarm time/equipment against ground truth only after detection. The negative sensor-fault test also verifies that the uncertain fixture produces RULE-004 only and no ground-truth label in the alarm output.

Full-run event metrics were TP=4, FN=0, unmatched alarm records=372, precision=0.0106383, recall/detection rate=1.0, F1=0.0210526, and total alarms=1,245. True negatives are now reported as null because no normal-event population is defined. The high unmatched alarm count is a material quality limitation; do not present the 100% event detection rate without that context.

## Negative scenarios and validator

Starter and full output validation each completed with 18 PASS, 0 FAIL, 0 WARN, and 0 NOT_IMPLEMENTED results. All five negative cases passed through executable shared validation/detection logic:

1. Missing pipe endpoint is rejected.
2. Tank level above 100% is rejected.
3. A flow residual of 40 exceeds the configured 1% tolerance.
4. Missing configuration hash/input manifest is rejected.
5. Uncertain sensor data produces a sensor-quality alarm, not a process alarm or ground-truth association.

## SQL analytics

All ten SQL statements executed successfully. Result row counts were `20, 4, 1, 1, 12, 0, 4, 2, 1, 220` in query order. Query 6 returned zero qualifying tank rows; the stale-telemetry query returned all 220 sensors because the default simulation period is in January 2026 and is over one hour old at audit time.

## Independent reproducibility comparison

Two full runs used seed 20261022 and the same configuration hash (`41197cfdae11de5b`). All 12 CSV row counts matched and all canonical SHA-256 content checksums matched. The `created_at` field was excluded from the simulation-run checksum because it is wall-clock metadata; it is not deterministic. The telemetry CSV SHA-256 was:

`1639b490a4e104e9ee31c147ec4d2d2001449a1c7eee42e2ee4ae53ce20a9008`

Output directories differed, but the configuration hash is now independent of output-path settings.

## Defects corrected during verification

- Removed stray Markdown fences that made seven Python modules and three tests syntactically invalid, plus a trailing fence in the SQL file.
- Fixed full-mode pump generation, which previously created 18 rather than the configured 20 pumps.
- Fixed the CLI's missing pandas import and the invalid pandas `.empty()` assertions.
- Replaced five negative-scenario checks that previously passed based on fixture construction alone with checks against the executable validators/detector.
- Implemented observed-data rules for rapid level decline and sustained pump-flow deviation; removed silent exception swallowing in detection.
- Removed scenario/physical-state leakage from persisted telemetry and alarm output; event evaluation now joins by equipment/time/sensor.
- Replaced the fabricated `true_negatives: 0` with null and an explanation.
- Fixed duplicate validation-summary rows and made the configuration hash independent of output paths.
- Corrected the SQL analytics to associate detection with scenario windows instead of relying on injected scenario labels.
- Removed standard-library modules (`hashlib`, `pathlib`) from pip requirements.
- Documented that full telemetry count is derived from sensor/sample volume and clarified that simulation run timestamps are not deterministic.

## Remaining caveats

- Whole-repository Ruff reports 69 findings; the three rewritten core modules pass Ruff. Existing findings are primarily unused imports, older typing forms, and style issues.
- The optional dashboard remains unimplemented.
- The original development master prompt is represented only by a summary in `prompt_history.md`; this audit prompt is now recorded verbatim, and the file gives a template for subsequent prompts.
- At the time of the 1.x verification, this workspace had no Git metadata. The target repository was
  subsequently confirmed empty, and the user's later explicit instruction authorized its first
  publication. The 2.0 implementation is now commit `6103e1a` on `origin/main`; the audit
  corrections were subsequently committed and pushed after separate explicit authorization. Earlier
  external publication history cannot be established.
- The root `out.txt` and `test_out.txt` are stale prior-run logs, not the results of this verification.

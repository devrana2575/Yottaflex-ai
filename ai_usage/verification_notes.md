# Independent Verification Notes (Historical 1.x Record; 2.0 Audit Appended)

> **Historical record — not current evidence for the 1.x numbers.** The 1.x audit below was performed
> on version 1.0.0 (18 validation checks, 11 tests). Its 1,245-alarm-row result and
> `precision=0.010638` are the defective metric reproduced and explained in
> [`docs/baseline_findings.md`](../docs/baseline_findings.md). The 2.0 results are in
> [`docs/validation_report.md`](../docs/validation_report.md): 87 executable validation rows,
> 20 SQL assertions, 62 tests, and separate event/point metrics. The Git publication note in the 1.x
> section is historical; the current 2.0/audit status is recorded below.

## 2026-10-27 2.0 Submission-Readiness Audit (Current)

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

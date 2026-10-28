# Requirement Matrix and Final Verification

**Project:** YottaFlex 2.0.0
**Verification date:** 2026-10-28
**Seed:** `20261022`
**Status vocabulary:** `PASS`, `WARN`, `FAIL`, `NOT VERIFIED`

This matrix maps each remediation requirement to the implementation, executed check and actual
artifact. A `PASS` means the command was executed and the stated result was inspected; it is not
based only on a file existing. The executable validation CSV remains **87 PASS, 0 FAIL, 0 WARN,
0 NOT_IMPLEMENTED**. Review-level caveats are listed separately in §3 and are not added to that
denominator.

## 1. Functional and preservation requirements

| ID | Requirement | Implementation / source | Executed verification and evidence | Actual result | Status |
|---|---|---|---|---|---|
| R01 | Preserve the existing repository and working functionality; do not rebuild it. | Existing modules and 62 historical tests retained; changes are additive/limited to target allocation, state history, exports and exact-count validation. | `python -m pytest -q`; final suite in main environment; review of `git diff`. | 68 passed in the final main-environment run; no existing test removed; thresholds, detector and evaluator logic unchanged. | PASS |
| R02 | Preserve master data: 3 facilities, 20 pumps, 30 tanks, 60 valves. | `src/yottaflex/generator.py`; full/starter scales. | Exact-100k run `yf-repro-100k/a`; `tests/test_generation.py::test_full_generation`; SQL Q1. | 3 / 20 / 30 / 60; also 135 pipes, 220 sensors, 4 operating modes. | PASS |
| R03 | Preserve the historical 316,800-row full/default path. | `ProcessSimulator` rectangular branch when `telemetry_target_rows=None`; default CLI has no target. | Fresh `yf-final-full` run. | 316,800 rows (220 x 1,440), 341 state events, 87 validation PASS, 20/20 SQL PASS. | PASS |
| R04 | Add an exact 100,000-record telemetry configuration. | `--target-telemetry-rows 100000`; `allocate_sample_counts()`; `baseline` scenario set; CLI rejects an overriding duration. | Fresh `yf-100k-dev`, `yf-repro-100k/a`, `yf-repro-100k/b`; `tests/test_submission_artifacts.py::test_exact_100k_cadence_and_foreign_keys`. | Exactly 100,000 rows: 120 sensors x 455 + 100 sensors x 454; duration 7.583333 h. | PASS |
| R05 | Preserve deterministic generation with seed `20261022`. | Path-independent configuration hash; deterministic IDs, scenarios and noise. | Two fresh 100k runs `a`/`b`; `reports/final/reproducibility_100k.json`. | 20/23 files byte-identical; the other 3 differ only in wall-clock `evaluated_at` / `validated_at` fields and are logically equal after removing those fields. | PASS |
| R06 | Do not fake padding, duplicate telemetry, or silently remove valid records. | Real cadence allocation; no synthetic rows; missing-sensor fault excluded from `baseline` so the exact count survives injection. | `telemetry.csv` checks: 100,000 rows, unique `(sensor_id,timestamp)`, unique `telemetry_id`, every row a real sensor/timestamp; manifest and metadata distribution. | No duplicates, no null measured values, no fabricated rows; 455/454 allocation is explicit in config and metadata. | PASS |
| R07 | Do not tune thresholds, change scenarios/ground truth, or change matching rules to improve metrics. | No changes to `detection.py`, `evaluation.py`, thresholds, existing scenario plans, ground-truth rules or matching policy. Only the additive `baseline` set was introduced. | `git diff` inspection; fresh evaluation rerun; light-leak comparison. | Evaluation metrics unchanged: event TP/FN/FP `10/1/0`; point TP/FP/TN/FN `844/10/112190/206`; documented light leak remains missed. | PASS |
| R08 | Preserve the documented light-leak miss. | RULE-006 corroboration/persistence remains unchanged. | Fresh `yf-final-eval`; diagnostic calculation on `telemetry.csv`. | 90 samples in event window; residual median `8.3227 m3/h`, 82/90 above the `5 m3/h` floor; decline median `-0.1315 pp`; longest corroborated run `300 s`, longest active-without-corroboration `420 s`; event remains a miss. | PASS |
| R09 | Complete field-level documentation for all ten core entities. | `docs/data_dictionary.md`; schema and generator behavior. | Manual section review; table counts. | Ten core entities documented with types, keys, constraints, units, defaults, relationships, cardinality, lifecycle and history; additional state/export tables documented. | PASS |
| R10 | Implement real equipment state-history generation and persistence; no meaningless placeholders. | `src/yottaflex/state_history.py`; `equipment_state_events` schema; CSV/SQLite/JSON/SQL export. | `yf-repro-100k/a` state table; `test_equipment_state_history_is_append_only_and_valid`; `test_state_history_validation_catches_bad_transition`; `test_invalid_state_transition_is_rejected`. | 341 rows in 100k baseline: 333 initialization + 8 scenario start/recovery events; all transitions allowed; IDs unique; all timestamps inside run; table is not detector input. | PASS |
| R11 | Provide actual CSV, JSON, SQLite and portable SQL schema/seed exports. | CSV pipeline; `export-sql`; `export-json`; `export-sql-script`; `src/yottaflex/exports.py`. | `yf-100k-dev` exports: 18 tables / 101,275 rows; SQL seed executed into a new SQLite DB; `test_json_sqlite_and_sql_seed_preserve_ids`. | CSV, JSON, SQLite and SQL seed contain matching telemetry IDs; SQLite `integrity_check=ok`; zero FK violations; SQL seed 29,733,009 bytes and 101,275 rows. | PASS |
| R12 | Add minimal tests for all five required negative scenarios and verify unrelated data is not corrupted. | `tests/test_negative_scenarios.py`; shared validators/detector; copy-based controls. | `python -m pytest -q tests/test_negative_scenarios.py`; full suite. | 5/5 PASS: missing endpoint, level >100%, mass-balance violation, missing lineage, sensor quality vs process category; baseline master-data shapes unchanged after controls. | PASS |
| R13 | Verify topology and foreign-key integrity. | `generator.validate_topology()`; schema FKs; validation checks. | `test_topology_validation`, `test_master_primary_keys_and_references`, validation topology/FK rows, SQLite `foreign_key_check`. | All equipment graphs connected; 135 pipes; zero FK violations in full and 100k databases. | PASS |
| R14 | Verify physics and mass balance. | Pump curve, tank mass balance, hydrostatic pressure, sensor units. | `test_pump_curve`, `test_tank_volume`, `test_mass_balance`, validation PHYSICS checks, SQL Q17. | Physics validation `6/6` PASS in fresh runs; mass-balance residual within configured tolerance in normal operation. | PASS |
| R15 | Verify anomaly injection and ground-truth isolation. | `scenarios.py`; observed-only telemetry; detector selects observed columns. | `test_scenario_injection_is_deterministic`, `test_bias_injection_changes_only_measured_level`, `test_missing_injection_removes_exact_window`, `test_detector_ignores_ground_truth_columns`, `test_scenario_truth_lineage_windows_and_isolation`. | Injection deterministic; sensor bias changes measured level only; missing fault removes the exact window; poisoning ground-truth/scenario columns does not change detector output. | PASS |
| R16 | Verify installation, CLI and database initialization. | `setup.py`; `requirements.txt`; Click CLI; SQLite export. | Current environment `yottaflex --version` / `--help`; pipeline and SQLite runs; prior fresh venv audit. | Version 2.0.0; with the package uninstalled and `PYTHONPATH` unset, `python -m pytest -q` collected and passed 68 tests; editable install restored; pipeline completes; SQLite creates, populates and passes integrity checks. Prior clean pandas 3.1.0/NumPy 2.5.4 run passed 62 tests; remediation clean rerun not repeated. | PASS |
| R17 | Verify detection and evaluation counts from generated artifacts. | `detection.py`, `evaluation.py`, CSV/JSON outputs. | Fresh `yf-final-eval`; recomputation from `evaluation_events.csv`, `evaluation_metrics.json`; SQL Q7/Q13. | Event TP/FN/FP `10/1/0`, P/R/F1 `1.0000/0.9091/0.9524`; point TP/FP/TN/FN `844/10/112190/206`, P/R/F1 `0.9883/0.8038/0.8866`; 11 events, 1 light-leak miss, 0 false alarms. | PASS |
| R18 | Verify validation counts and SQL analytics. | `validation.py`, `sql/analysis_queries.sql`, `run-sql`. | Fresh full, evaluation, and exact-100k runs. | 87 PASS / 0 FAIL / 0 WARN / 0 NOT_IMPLEMENTED per run; all seven final validation CSVs aggregate 609/609 PASS; 20/20 SQL PASS; SQLite 18 populated tables of 19 schema tables. | PASS |
| R19 | Keep the historical compact 99,000-row configuration available. | `compact` scenario set and config path remain. | `reports/final/yf2-compact-99k/` evidence; current code supports `--scenario-set compact --duration 7.5`. | 99,000 rows, 4/4 events, 0 FP; labelled historical, not the exact-100k deliverable. | PASS |
| R20 | Record every recoverable prompt; label reconstructed history; do not claim completeness unless verified. | `ai_usage/prompt_history.md`; `ai_usage/prompts/2026-10-28-remediation.md`. | Manual review of prompt records and labels. | The latest publication-authorization prompt `push` is recorded verbatim; 2026-10-27 audit prompt retained verbatim; the prior 2026-10-28 remediation and original 1.x prompts remain explicitly reconstructed because their verbatim sources were not retained. | WARN |
| R21 | Run final secret/PII/large-file/untracked-file audit and review the actual diff. | Repository scan; `git diff --check`; `git status --short`; tracked/unignored file scan. | Python secret/PII scan over tracked and untracked text files; size scan; diff review. | 0 secret/PII hits; no tracked file >1 MB; `git diff --check` clean; ignored `data/processed` outputs remain untracked and are not evidence or committed artifacts. | PASS |
| R22 | Do not force-push, rewrite shared history, or publish without explicit authorization. | Git remote inspection; local remediation commit; explicit user authorization `push`. | `git remote -v`, `git status`, `git log`; push executed only after authorization and final audit. | Pre-remediation HEAD `1bcec46`; remediation committed locally after review; final push to `origin/main`; no force-push or history rewrite. | PASS |

## 2. Reproducibility and artifact checks

| Check | Method | Actual result | Status |
|---|---|---|---|
| Exact-100k allocation | `telemetry.groupby('sensor_id').size()` | `{455: 120, 454: 100}`; total 100,000 | PASS |
| Duplicate samples | `duplicated(['sensor_id','timestamp'])` | 0 | PASS |
| Sensor references | Set equality against `sensors.csv` | All 220 sensors represented | PASS |
| Run references | Set equality against `simulation_runs.csv` | All telemetry uses the run ID | PASS |
| State-event initialization | `previous_state == UNKNOWN` count | 333 unique assets/sensors | PASS |
| State-event scenario transitions | Source/reference checks | 8 events for 4 baseline scenarios | PASS |
| SQLite schema | `sqlite_master`, row counts | 19 tables, 18 populated, `detection_results` empty | PASS |
| SQLite integrity | `PRAGMA integrity_check` | `ok` | PASS |
| Foreign keys | `PRAGMA foreign_key_check` | 0 violations | PASS |
| JSON export | `manifest.json` | 18 tables, 101,275 rows | PASS |
| SQL seed | Execute into new SQLite DB | 101,275 rows, `integrity_check=ok`, 0 FK violations, 100,000 telemetry rows, 341 state events | PASS |
| Exact-100k two-run comparison | SHA-256 per artifact | 20/23 byte-identical; 3 timestamp-only differences, logically equal | PASS |
| Database two-run comparison | Pandas equality after wall-clock columns removed | All 19 tables logically equal | PASS |
| Full/default and evaluation rerun | Fresh pipeline after remediation | Metrics unchanged; 316,800 / 316,740 rows | PASS |
| Light-leak diagnostic | Recompute residual/decline window | 8.3227 m3/h median; 82/90 above floor; miss preserved | PASS |

## 3. Review-level caveats

| Item | Why it remains open | Status |
|---|---|---|
| Light-leak sensitivity | The 1.5% capacity/hour leak is intentionally missed because decline corroboration and 480 s persistence do not both hold. It was not tuned away. | WARN |
| Prompt completeness | The original 1.x master prompt and the prior 2026-10-28 remediation prompt were not present verbatim in the retained continuation record. Those records are explicitly reconstructed; the 2026-10-27 audit prompt and the latest `push` authorization are verbatim. | WARN |
| Cross-version environment | The remediation suite and exact-100k pipeline were run in the main environment. The prior pandas 3.1.0 / NumPy 2.5.4 environment was not recreated for the new code. | NOT VERIFIED |
| Ignored generated outputs | `data/processed/` contains old ignored run outputs, including a stale telemetry file with historical columns. They are not tracked, not used as evidence and not part of the submission; the scan did not remove user data. | WARN |

## 4. Reproduction commands

From the repository root:

```bash
python -m pytest -q
yottaflex pipeline --mode full --seed 20261022 --scenario-set evaluation \
  --output-dir <fresh-output-dir>/evaluation
yottaflex pipeline --mode full --seed 20261022 --scenario-set baseline \
  --target-telemetry-rows 100000 --output-dir <fresh-output-dir>/baseline-100k
yottaflex export-json --output-dir <fresh-output-dir>/baseline-100k
yottaflex export-sql-script --output-dir <fresh-output-dir>/baseline-100k
yottaflex validate --output-dir <fresh-output-dir>/baseline-100k
yottaflex run-sql --output-dir <fresh-output-dir>/baseline-100k \
  --sql-file sql/analysis_queries.sql
```

Expected final results for the 100k baseline: **100,000 telemetry rows**, **341 state events**,
**87 validation PASS**, **20/20 SQL PASS**, **18 populated SQLite tables**, and **68 tests passing**
in the main environment. The two-run comparison is recorded in
[`reports/final/reproducibility_100k.json`](../reports/final/reproducibility_100k.json).

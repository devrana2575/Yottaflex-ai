# Requirement Matrix and Final Verification

**Project:** YottaFlex 2.0.0
**Verification date:** 2026-10-29 (final audit; prior remediation evidence retained below)
**Seed:** `20261022`
**Status vocabulary:** `PASS`, `WARN`, `FAIL`, `NOT VERIFIED`

This matrix maps each remediation requirement to the implementation, executed check and actual
artifact. A `PASS` means the command was executed and the stated result was inspected; it is not
based only on a file existing. The executable validation CSV remains **87 PASS, 0 FAIL, 0 WARN,
0 NOT_IMPLEMENTED**. Review-level caveats are listed separately in §3 and are not added to that
denominator. The 2026-10-29 final audit re-ran the main and clean test suites, fresh exact-100k,
full/default and evaluation pipelines, exports, independent metrics, five negative controls and
repository checks. Section 5 records that final evidence with the requested seven columns.

## 1. Functional and preservation requirements

| ID | Requirement | Implementation / source | Executed verification and evidence | Actual result | Status |
|---|---|---|---|---|---|
| R01 | Preserve the existing repository and working functionality; do not rebuild it. | Existing modules and 62 historical tests retained; changes are additive/limited to target allocation, state history, exports and exact-count validation. | `python -m pytest -q`; final suite in main and fresh clean environments; review of `git diff`. | 68 passed in both the final main-environment and clean-environment runs; no existing test removed; thresholds, detector and evaluator logic unchanged. | PASS |
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
| R16 | Verify installation, CLI and database initialization. | `setup.py`; `requirements.txt`; Click CLI; SQLite export. | Current environment `yottaflex --version` / `--help`; pipeline and SQLite runs; fresh 2026-10-28 venv created with README commands. | Version 2.0.0; fresh clean environment (Python 3.14.4, pandas 3.1.0, NumPy 2.5.4) installed with `pip install -e .` plus pytest, passed all 68 tests, and regenerated the exact-100k baseline with 87/87 validation and 20/20 SQL PASS. SQLite creates, populates and passes integrity checks. | PASS |
| R17 | Verify detection and evaluation counts from generated artifacts. | `detection.py`, `evaluation.py`, CSV/JSON outputs. | Fresh `yf-final-eval`; recomputation from `evaluation_events.csv`, `evaluation_metrics.json`; SQL Q7/Q13. | Event TP/FN/FP `10/1/0`, P/R/F1 `1.0000/0.9091/0.9524`; point TP/FP/TN/FN `844/10/112190/206`, P/R/F1 `0.9883/0.8038/0.8866`; 11 events, 1 light-leak miss, 0 false alarms. | PASS |
| R18 | Verify validation counts and SQL analytics. | `validation.py`, `sql/analysis_queries.sql`, `run-sql`. | Fresh full, evaluation, and exact-100k runs. | 87 PASS / 0 FAIL / 0 WARN / 0 NOT_IMPLEMENTED per run; all seven final validation CSVs aggregate 609/609 PASS; 20/20 SQL PASS; SQLite 18 populated tables of 19 schema tables. | PASS |
| R19 | Keep the historical compact 99,000-row configuration available. | `compact` scenario set and config path remain. | `reports/final/yf2-compact-99k/` evidence; current code supports `--scenario-set compact --duration 7.5`. | 99,000 rows, 4/4 events, 0 FP; labelled historical, not the exact-100k deliverable. | PASS |
| R20 | Record every recoverable prompt; label reconstructed history; do not claim completeness unless verified. | `ai_usage/prompt_history.md`; `ai_usage/prompts/2026-10-28-remediation.md`; `ai_usage/prompts/2026-10-28-final-verification.md`. | Manual review of prompt records and labels. | The final verification prompt is recorded verbatim; publication authorization `push` and 2026-10-27 audit prompt retained verbatim; the prior 2026-10-28 remediation and original 1.x prompts remain explicitly reconstructed because their verbatim sources were not retained. | WARN |
| R21 | Run final secret/PII/large-file/untracked-file audit and review the actual diff. | Repository scan; `git diff --check`; `git status --short`; tracked/unignored file scan. | Python secret/PII scan over tracked and untracked text files; size scan; diff review. | 0 secret/PII hits; no tracked file >1 MB; `git diff --check` clean; ignored `data/processed` outputs remain untracked and are not evidence or committed artifacts. | PASS |
| R22 | Do not force-push, rewrite shared history, or publish without explicit authorization. | Git remote inspection; local remediation commit; explicit user authorization `push` and the 2026-10-29 final-audit instruction. | `git remote -v`, `git status`, `git log`; push executed only after authorization and final audit. | 2026-10-29 audit starting HEAD `5969314`; only reviewed documentation/report/prompt changes were committed after review and pushed to `origin/main`; no force-push or history rewrite. | PASS |

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
| Cross-version environment | The 2026-10-28 clean pandas 3.1.0 / NumPy 2.5.4 environment passed all 68 tests and the exact-100k pipeline; full/default and evaluation pipelines were not repeated there. Cross-version float serialization caused last-bit-only differences in one SQL report and two SQLite tables, with no metric or semantic change. | WARN |
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
in both the main and fresh clean environments. The two-run comparison is recorded in
[`reports/final/reproducibility_100k.json`](../reports/final/reproducibility_100k.json).

## 5. Final-audit requirement matrix (2026-10-29)

This is the requested seven-column matrix for the latest audit. Fresh artifacts live outside the
repository under `<external-temp>/yottaflex-final-audit-20261028/`; compact evidence is under
`reports/final/`.

| Requirement | Implementation file | Relevant test | Generated artifact | Verification method | Actual result | Status |
|---|---|---|---|---|---|---|
| F01. Preserve the existing repository and working behavior; no rebuild or unnecessary refactor. | Existing `src/yottaflex/`, `tests/`, configuration and docs | `python -m pytest -q`; `git diff` review | Current source tree; main and clean test logs | Reviewed tracked diff and reran the complete suite in both environments | 68 passed in main (104.89 s) and 68 passed in a fresh clean venv (85.25 s); no source logic changed | PASS |
| F02. Preserve master-data counts: 3 facilities, 20 pumps, 30 tanks, 60 valves. | `src/yottaflex/generator.py`, `config/` | `tests/test_generation.py::test_full_generation`; SQL Q1 | `<external-temp>/.../exact-a/{facilities,pumps,tanks,valves}.csv` | Independent pandas row counts on fresh CSVs and SQLite | 3 / 20 / 30 / 60; also 135 pipes, 220 sensors, 4 operating modes | PASS |
| F03. Produce exactly 100,000 telemetry records without padding or duplicate rows. | `--target-telemetry-rows 100000`; `alloc_sample_counts()`; simulator | `tests/test_submission_artifacts.py::test_exact_100k_cadence_and_foreign_keys` | `exact-a/telemetry.csv`; `exact-a/yottaflex.db` | Counted CSV and SQLite rows; checked allocation, unique IDs and unique `(sensor_id,timestamp)` | 100,000 rows = 120 x 455 + 100 x 454; 100,000 unique IDs and unique sensor/timestamp pairs | PASS |
| F04. Deterministic immutable IDs and fixed-seed generation. | `src/yottaflex/id_generator.py`; config seed `20261022` | ID and reproducibility tests; exact-a/b comparison | Master CSVs; `simulation_runs.csv`; run manifest | Regex checks, cross-run hashes, exact/full master comparison | `FAC-001..003`, `PUMP-001..020`, `TANK-001..030`, `VALVE-001..060`, `SNS-001..220`, `SIM-2026-000001`; masters identical across scales | PASS |
| F05. Valid topology and entity references, including pipe endpoints and foreign keys. | `generator.validate_topology()`, `validation.py`, SQLite schema | Topology, primary-key/reference and negative endpoint tests; SQL Q1/Q17 | `pipes.csv`, `sensors.csv`, `yottaflex.db` | Endpoint membership, same-facility checks, `PRAGMA foreign_key_check`, SQL joins | 135 pipes; all endpoints valid; no self-loops; 0 FK violations; 20/20 SQL assertions | PASS |
| F06. Complete field-level documentation for all ten core entities. | `docs/data_dictionary.md` | Manual dictionary audit against generated schemas | All master/telemetry CSVs and SQLite tables | Checked every observed CSV column appears with type/required/key/constraint/unit/relationship coverage | All observed fields documented; no missing generated columns; ten core entities covered | PASS |
| F07. Document cardinality, lifecycle/effective dates and explicit event history. | `docs/data_dictionary.md`; `src/yottaflex/state_history.py` | `test_equipment_state_history_is_append_only_and_valid`; invalid-transition tests | `equipment_state_events.csv`; SQLite `equipment_state_events` | Counted events; checked previous/new state, timestamp, reason, run reference and allowed transitions | 341 events = 333 initialization + 8 scenario transitions; unique IDs; append-only; no placeholder rows | PASS |
| F08. Verify all five required negative scenarios independently. | `src/yottaflex/validation.py`; copy-based controls | `tests/test_negative_scenarios.py`; targeted suite | Direct `Validator.test_negative_scenarios()` output | Ran the shared validators/detector on controlled mutations and checked baseline shapes | `NEG-001`–`NEG-005` all PASS; baseline master-data shapes unchanged | PASS |
| F09. Distinguish sensor faults from process faults. | Detector sensor-quality rules; incident classification | Sensor-fault classification and incident tests | `evaluation-run/alarm_incidents.csv`, `alarms.csv` | Compared incident categories with sensor/process ground truth; checked duplicate handling | 4/4 sensor-fault events matched SENSOR_FAULT incidents; process events remained PROCESS_FAULT | PASS |
| F10. Keep ground truth separate from detector input features. | `src/yottaflex/detection.py`; isolation validation; observed-only telemetry | Isolation/poisoning tests; `validation_results.csv` | `telemetry.csv`, validation rows | Checked detector column selection and poisoned-label invariance; inspected isolation PASS rows | 3/3 isolation checks PASS; no scenario/ground-truth labels in telemetry or detector input | PASS |
| F11. Generate verified CSV, JSON, SQLite and portable SQL exports. | `src/yottaflex/exports.py`; export CLI commands; SQLite schema | `test_json_sqlite_and_sql_seed_preserve_ids`; export execution | 18 CSV tables; `json_exports/`; `yottaflex.db`; `yottaflex_seed.sql` | Counted rows, checked manifests/hashes, executed SQL seed into a new DB, compared ID sets | 18 JSON tables / 101,275 rows; SQL 101,275 rows / 29,733,009 bytes; integrity `ok`; 0 FK violations; IDs match | PASS |
| F12. Verify documented installation and CLI packaging. | `setup.py`; `requirements.txt`; README setup | Fresh `python -m venv`; `pip install -e .`; `pip install pytest`; CLI version | Clean venv; `yottaflex --version` output | Executed README-compatible installation and CLI in a fresh environment | Python 3.14.4 / pandas 3.1.0 / NumPy 2.5.4; version 2.0.0; 68 tests passed; exact-100k regenerated | PASS |
| F13. Run the complete test suite, plus targeted negative/state tests. | `tests/` | `python -m pytest -q`; targeted two-file suite | Main/clean pytest logs | Ran after the fresh generated runs; recorded exit status and counts | Main 68 passed (104.89 s); clean 68 passed (85.25 s); targeted 6 passed (78.01 s); zero failures/skips | PASS |
| F14. Recalculate event and point detection metrics from artifacts. | `src/yottaflex/evaluation.py`; `detection.py` | Independent recomputation script; evaluation tests | `evaluation-run/{evaluation_events,evaluation_metrics,alarms,alarm_incidents,telemetry}.csv` | Rebuilt labels from ground truth and predictions from alarm intervals; compared persisted metrics | Event TP/FN/FP 10/1/0, P/R/F1 1.0000/0.9091/0.9524; point 844/10/112190/206, P/R/F1 0.9883/0.8038/0.8866; latency 60/300/3180 s | PASS |
| F15. Preserve and explain the documented light-leak miss. | RULE-006/RULE-006U detector logic; no threshold change | Light-leak diagnostic; evaluation outcome | `evaluation-run` telemetry; `light_leak_diagnostic.json` | Recomputed the detector's 10-minute residual and 5-minute decline on `SNS-019/021/022` | GT-000001 remains MISSED: 90 samples, residual median 8.3227 m3/h, 82/90 above floor, decline median -0.1315 pp, 0 overlapping alarms | WARN |
| F16. Verify exact-100k reproducibility in independent directories. | Pipeline; deterministic seed/config; export writers | exact-a vs exact-b comparison | 23 compared files; SQLite DBs | SHA-256, recursive timestamp removal, Pandas logical equality | 20/23 byte-identical; 3 timestamp-only differences; all 19 SQLite tables logically equal; 18 populated | PASS |
| F17. Distinguish byte, logical and cross-version reproducibility. | Same pipeline in fresh clean environment | exact-clean vs exact-a comparison | Clean logs, 23 artifacts, SQLite DBs | Separate SHA-256 and logical comparisons; identified float-only differences | 19/23 byte-identical; 3 timestamp-only differences plus 1 last-bit SQL-report float difference; raw SQLite 16/19, 17/19 after timestamps, 19/19 with documented 1e-15 floats; metrics match | WARN |
| F18. Reconcile validation and SQL counts across reports. | `src/yottaflex/validation.py`; `sql/analysis_queries.sql`; `run-sql` | Fresh exact, full/default and evaluation runs; SQL report | `validation_results.csv`, `validation_summary.json`, `sql_query_report.json` | Re-read actual CSVs and machine summaries; counted statuses and SQL assertions | 87 PASS / 0 FAIL / 0 WARN / 0 NOT_IMPLEMENTED per run; 20/20 SQL PASS; 18 populated SQLite tables of 19 | PASS |
| F19. Preserve the historical full/default and compact paths. | `ProcessSimulator` rectangular branch; compact scenario set | Full/default and compact evidence checks | `full-default/` outputs; `reports/final/yf2-compact-99k/` | Fresh full/default run and historical compact evidence inspection | 316,800 rows, 341 state events, 87/20 validation/SQL, event 4/0/0; compact 99,000 remains historical | PASS |
| F20. Preserve recoverable AI prompts and label reconstructed records. | `ai_usage/prompt_history.md`; `ai_usage/prompts/`; tools/verification notes | Manual prompt-history audit | `ai_usage/prompts/2026-10-29-final-audit.md` and prior records | Compared records with live/recoverable text; checked labels and completeness claims | 2026-10-29 final-audit prompt recorded verbatim; 2026-10-28 final verification and push authorization retained; earlier 1.x and 2026-10-28 remediation records remain explicitly reconstructed | WARN |
| F21. Audit secrets, PII, caches, large files, stale reports and diff hygiene. | Repository tree; `.gitignore`; ignored outputs | Secret/PII scan; `git status --short`; `git diff --check`; `git diff --stat` | Tracked source/docs/reports; ignored local outputs | Scanned tracked/untracked text patterns, sizes, caches, docs and final diff; did not delete user data | No secret/PII hits; no tracked file >1 MB; no whitespace errors (Git emitted only LF/CRLF conversion warnings); ignored `data/processed/` remains untracked and is not evidence | PASS |
| F22. Publish only reviewed changes to the confirmed remote, without force-push. | Git remote/branch; reviewed audit files | `git fetch`; safe push; remote HEAD check | Commit on `origin/main` | Confirmed remote, reviewed diff, committed documentation/report/prompt changes, pushed normally | Starting HEAD `5969314`; reviewed changes committed and pushed to `https://github.com/devrana2575/Yottaflex-ai.git`; no force-push or history rewrite | PASS |
| F23. Cross-version full/default and evaluation coverage. | Clean-env installation; same pipeline | Not run in clean env; main exact and clean exact only | Main full/default/evaluation artifacts; clean exact artifacts | Recorded scope explicitly rather than assuming equivalence | Full/default and evaluation were rerun in the main environment but not repeated in the clean environment | NOT VERIFIED |

Status totals for this final matrix: **19 PASS**, **3 WARN** (F15 light-leak sensitivity; F17
cross-version byte/float differences; F20 reconstructed earlier prompt records), **0 FAIL**, and
**1 NOT VERIFIED** (F23: full/default and evaluation pipelines were not repeated in the clean
environment). The executable validation CSV remains 87/87 PASS; it does not include review-level
caveats or the un-repeated clean cross-version scope.

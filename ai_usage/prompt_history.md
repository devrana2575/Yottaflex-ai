# AI Prompt History

This document records every prompt that is recoverable from the project history. Where the original
wording was not retained, the record is explicitly labelled **reconstructed**; no reconstructed
record is presented as a verbatim quotation.

## Project: Industrial Pump, Tank, Valve and Flow Anomaly Detection Simulator
**Candidate:** YottaFlex Candidate
**Date Started:** 2026-10-26
**AI Tool:** OpenCode (Big Pickle model)

## Master Prompt

**Timestamp:** 2026-10-26T19:56:00Z
**Tool:** OpenCode
**Task:** Complete implementation of YottaFlex simulator per specifications
**Record status:** Summary only; the original verbatim prompt was not retained.

The full master prompt provided detailed requirements for building a complete working solution including:
- 10 core entities
- Physics-inspired simulation
- 4 anomaly types + sensor faults
- Rule-based detection
- Ground truth separation
- 5 negative scenarios
- Full validation framework
- Reproducibility
- 100,000 telemetry points support
- Complete documentation

## Subsequent Prompt Recording

For each subsequent AI interaction, append the date/time, tool/model, task, and the complete prompt text below. Do not replace a full prompt with a summary.

### Independent verification prompt

**Timestamp:** 2026-10-26
**Tool:** Copilot SDK in VS Code
**Task:** Independently verify the simulator, execute documented workflows and analytics, fix reproducible defects, and report evidence.

> Perform a final independent verification of the Industrial Pump, Tank, Valve and Flow Anomaly Detection Simulator.
>
> Do not assume the previous implementation report is correct.
>
> 1. Inspect the actual source code and generated artifacts.
> 2. Execute the documented starter workflow from a clean output directory.
> 3. Execute the full-volume generation workflow.
> 4. Verify all required entity counts and foreign-key relationships.
> 5. Verify topology connectivity according to the documented requirements.
> 6. Execute all five negative-scenario tests.
> 7. Verify that the four required anomaly mechanisms have executable scenarios and that detection is based on observed data, not ground-truth labels.
> 8. Verify that sensor faults are not automatically treated as physical process failures.
> 9. Execute the complete test suite and report actual results.
> 10. Execute the documented SQL analytics.
> 11. Regenerate the outputs independently using the same seed and configuration.
> 12. Compare row counts and deterministic content checksums.
> 13. Check that every README command works as documented.
> 14. Check for missing files, placeholder implementations, hardcoded evaluation metrics, accidental ground-truth leakage, and obvious secrets.
> 15. Verify that AI prompt history contains this master prompt and provides a mechanism to document subsequent prompts.
> 16. Confirm that no GitHub publication occurred without authorization.
>
> Fix any reproducible defects you discover, rerun the affected checks, and update the documentation.
>
> Produce a final audit table with columns:
>
> - Requirement
> - Verification method
> - Actual result
> - PASS / FAIL / WARN / NOT_IMPLEMENTED
> - Evidence or artifact path
>
> Never fabricate successful checks or numerical results. Do not mark an item PASS merely because a corresponding function or test file exists. Execute it and inspect the result.
>
> Finish with exact commands for a candidate to reproduce the successful checks locally and a list of decisions the candidate should understand before the interview.

## 2.0 Improvement and Verification Session

**Timestamp:** 2026-10-27
**Tool:** OpenCode
**Model:** DeepSeek V4.1 Flash Free
**Task:** Improve and independently verify the existing YottaFlex anomaly-detection project without
rebuilding it from scratch.
**Record status:** The original verbatim prompt was not retained in the conversation record.
The following is a detailed reconstruction of the session brief, not a quotation.

### Reconstructed session brief

> Improve and verify the existing YottaFlex industrial anomaly-detection project. Reproduce the
> actual baseline before editing; treat historical figures as observations, not inputs. Fix the
> evaluation methodology first, investigate false alarms, improve the detector only where evidence
> supports it, expand tests and scenarios, verify reproducibility, SQL and validation, and document
> the evidence.
>
> Separate point-level and event-level evaluation. Document matching rules, unknown labels,
> duplicate handling, latency, and zero-denominator behaviour. Do not suppress alarms or manipulate
> denominators to improve metrics.
>
> Add persistence, hysteresis, mode-aware behaviour, sensor-quality handling, pump-curve
> diagnostics, flow-balance diagnostics and alarm grouping only where evidence supports them. Add
> calibration and independent evaluation scenario sets with deterministic seeds. Do not tune on the
> evaluation set. Keep ground truth isolated from detector inputs.
>
> Ensure sensor faults are not automatically classified as physical process faults, and report
> uncertainty when the evidence is insufficient.
>
> Preserve the existing tests and add targeted simulation, detection, evaluation, data-integrity
> and integration tests.
>
> Verify 3 facilities, 20 pumps, 30 tanks and 60 valves. Provide a configuration near 100,000
> telemetry rows while retaining the 316,800-row full volume.
>
> Run all SQL queries and validate actual results. Generate machine-readable and readable reports
> with PASS / FAIL / WARN / NOT_IMPLEMENTED status.
>
> Update the README and create `docs/detection_methodology.md`, `docs/evaluation_methodology.md`,
> `docs/validation_report.md` and `docs/implementation_decisions.md`. Record the complete task
> prompt in the AI prompt history.
>
> Do not push or publish to GitHub. The final response must include a summary, changed files,
> decisions, commands, test results, baseline and final metrics, per-scenario results, false-alarm
> analysis, reproducibility evidence, entity/row counts, validation results, limitations,
> reproduction commands, and a Requirement | Evidence | Result | Status table.

### Work performed

- Reproduced the 1.x baseline exactly: starter 51,840 rows / 929 alarms; full 316,800 rows / 1,245
  alarms; reported precision 0.0800 / 0.010638. The old evaluator mixed event TP with raw alarm-row
  FP and discarded 873 event-overlapping rows.
- Rewrote the simulator for mass consistency, added tank flow/pressure redundancy, pump-curve
  behavior and explicit operating modes, and preserved 220 sensors and 316,800 rows.
- Replaced per-sample alarms with grouped episodes, persistence, hysteresis, mode suppression,
  CREATED/RESOLVED history and explicit uncertainty/attribution.
- Split evaluation into event and point units, added explicit NORMAL windows, incident merging,
  one-to-one category/equipment/sensor/latency matching and unknown-label accounting.
- Added `default`, `calibration`, `evaluation` and `compact` scenario sets.
- Added 87 validation checks, 20 SQL assertions, 51 targeted tests (62 total) and reproducibility
  checks.
- Final evaluation: 11 events, TP=10, FN=1, FP=0; event P/R/F1 = 1.0000/0.9091/0.9524. The miss is
  the documented light-leak corroboration/persistence limitation; its balance residual is above the
  absolute floor.
- Wrote the methodology, decision, baseline, validation and handover documents; compact evidence is
  in `reports/final/`.

### Deliverable mapping

- Baseline: [`docs/baseline_findings.md`](../docs/baseline_findings.md)
- Method: [`docs/detection_methodology.md`](../docs/detection_methodology.md),
  [`docs/evaluation_methodology.md`](../docs/evaluation_methodology.md)
- Decisions: [`docs/implementation_decisions.md`](../docs/implementation_decisions.md)
- Final evidence: [`docs/validation_report.md`](../docs/validation_report.md)
- Machine-readable evidence: [`reports/final/`](../reports/final/)

## Submission-Readiness Audit Session

- **Timestamp:** 2026-10-27
- **Tool:** OpenCode
- **Model:** DeepSeek V4.1 Flash Free
- **Task:** Submission-readiness audit of the existing YottaFlex 2.0 repository.
- **Record status:** Verbatim user prompt content copied from the audit request; markdown line wrapping
  is normalized for readability. No system/developer harness instructions are included.

```text
Complete a submission-readiness audit of the existing YottaFlex 2.0 repository without rebuilding it. Re-run the workflows, verify the claims against generated artifacts, correct documentation that is stale or overstated, and fix genuine defects if found.

Working directory: `D:\PROJECTS\yottaflex`.

## Required audit

1. Repository state and setup
- Inspect Git status, remotes, latest commits, and whether the tree is clean.
- Re-run the documented installation from a clean state: `pip install -r requirements.txt` and `pip install -e .`, plus CLI version/help.
- Check `pyproject.toml`/`setup.py`, package metadata, entry points, Python version constraints, dependency pinning, relative-path assumptions, output-directory creation, and database initialization.
- Run the full test suite and record exact pass/fail counts.

2. Evaluation and results
- Re-run the final evaluation workflow from a fresh output directory and compare metrics to the README.
- Verify event-level TP/FN/FP and point-level TP/FP/TN/FN against generated CSV/JSON outputs, not just documentation.
- Recalculate precision, recall, F1, and false-positive rate where feasible.
- Reconcile any discrepancy in validation counts, PASS/WARN/FAIL labels, or test counts.
- Check that validation checks actually execute real assertions and are not placeholders.

3. Detection and data integrity
- Verify topology, primary/foreign keys, flow conservation, units, sensor counts, and expected row counts.
- Audit negative scenarios and confirm they fail for the intended reason.
- Verify the detector cannot read ground truth or scenario labels.
- Check the missed light-leak event and explain whether it is a threshold, labeling, or persistence issue. Do not tune thresholds to make it pass unless the existing detector is demonstrably wrong.
- Verify seed determinism and reruns reproduce identical artifacts where expected.

4. SQL and analytics
- Execute all SQL queries and validate results, including joins and zero-row checks.
- Confirm the database has expected tables and constraints, with no integrity or foreign-key violations.

5. Documentation and AI-use records
- Update `README.md`, validation report, methodology docs, decisions, assumptions, handover notes, and AI-use/prompt records if stale or inaccurate.
- Make sure prompts, tool usage, and verification notes are truthful and complete. Preserve reconstructed labels where verbatim history is unavailable.
- Check for secrets, personal information, and large files; remove or redact anything inappropriate without falsifying evidence.

6. Final checks
- Re-run validation, SQL, tests, and reproducibility workflow after any changes.
- Run `git diff --check`.
- Review final diff and commit audit changes locally. Do not push, force-push, rewrite shared history, or publish without separate authorization.
- Report exact commands, observed results, remaining defects, and any WARN items separately from PASS counts.

## Constraints
- Preserve working features and the missed light-leak event; document limitations honestly.
- Do not tune thresholds, remove scenarios, alter ground truth, or change matching rules to improve metrics.
- Use existing architecture and code; do not rebuild the project.
- Do not invent results. If something cannot be verified, say so.
- Do not expose secrets or personal data in your final response.
- Keep final response concise but evidence-rich.
```

### Audit work performed

- Re-ran the main and fresh-environment test suites: **62 passed** in each.
- Re-ran evaluation, validation and SQL; reproduced the reported event/point metrics and
  **87 PASS / 0 FAIL / 0 WARN / 0 NOT_IMPLEMENTED** plus **20/20 SQL**.
- Ran two fresh full/default runs after fixes: **19/19 deterministic artifacts byte-identical**
  within the main environment; SQLite logical comparison passed. A fresh clean environment matched
  all metrics and 17/19 artifacts, with last-bit `peak_value` differences in two files.
- Re-ran negative controls, isolation poisoning, seed determinism and light-leak diagnostics.
- Corrected stale counts, Git publication statements, light-leak wording, packaging/setup guidance,
  local-path privacy, and AI-use records.
- Fixed the pandas mode-fill deprecation and point-coverage counting defects; added regression
  assertions. No thresholds, scenarios, ground truth or matching rules were changed.

Current evidence: [`docs/validation_report.md`](../docs/validation_report.md),
[`reports/final/`](../reports/final/), and the current audit section in
[`verification_notes.md`](verification_notes.md).

## 2026-10-28 Exact-100k, State-History and Export Remediation

- **Timestamp:** 2026-10-28
- **Tool:** OpenCode
- **Model:** DeepSeek V4.1 Flash Free
- **Task:** Complete the final remediation and submission-readiness pass for the existing YottaFlex
  2.0 repository.
- **Record status:** **RECONSTRUCTED — the full verbatim prompt was not present in the retained
  continuation record.** The recovered requirement summary is stored in
  [`prompts/2026-10-28-remediation.md`](prompts/2026-10-28-remediation.md) and is not represented as
  a quotation.

### Work performed

- Added `--target-telemetry-rows`, deterministic quotient/remainder allocation, derived duration and
  the exact `baseline` scenario set; retained the historical 316,800-row path.
- Added real append-only `equipment_state_events` generation, schema fields and transition
  validation; the exact-100k baseline contains 341 events (333 initialization + 8 scenario).
- Added deterministic per-table JSON and portable SQL seed exports; verified CSV/JSON/SQLite/SQL
  telemetry-ID consistency and executed the seed into a new SQLite database.
- Rewrote the ten-entity data dictionary, requirement matrix, README, architecture, assumptions,
  validation, handover and evidence documents.
- Added targeted tests for exact allocation, state transitions, export consistency and negative
  controls; final suite **68 passed** in the main environment.
- Re-ran exact-100k pipelines twice: 20/23 files byte-identical; the other three were timestamp-only
  and logically equal. Full/default and evaluation metrics were unchanged; the light-leak miss was
  preserved.
- Re-ran validation (87 PASS), SQL (20/20 PASS), SQLite integrity (`ok`) and foreign-key checks.
- Ran secret/PII/large-file/untracked-file audits; no secret/PII hits, no tracked file over 1 MB.
- Prepared the remediation for a local commit. Publication remains pending explicit authorization.

### Evidence

- [`docs/requirement_matrix.md`](../docs/requirement_matrix.md)
- [`docs/validation_report.md`](../docs/validation_report.md)
- [`reports/final/baseline_100k/`](../reports/final/baseline_100k/)
- [`reports/final/reproducibility_100k.json`](../reports/final/reproducibility_100k.json)

## Notes
- This is the initial implementation session
- All code has been written by the AI agent following the specifications
- Candidate should review and understand all implementation decisions
- The 2.0 session brief above is reconstructed because the original verbatim prompt was not retained;
  it is not presented as a quotation.
- The 2026-10-27 submission-readiness prompt above is recorded verbatim.
- The 2026-10-28 remediation prompt is reconstructed from the retained requirement summary; the
  original verbatim text was not available. The 2.0 implementation prompt remains explicitly marked
  as reconstructed. Prompt completeness is therefore a documented WARN, not a claim of completeness.

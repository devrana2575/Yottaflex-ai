# AI Prompt History

This document records all prompts submitted to AI tools during the development of the YottaFlex project.

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
- Added 87 validation checks, 20 SQL assertions, 50 targeted tests (61 total) and reproducibility
  checks.
- Final evaluation: 11 events, TP=10, FN=1, FP=0; event P/R/F1 = 1.0000/0.9091/0.9524. The miss is
  the documented light-leak sensitivity floor.
- Wrote the methodology, decision, baseline, validation and handover documents; compact evidence is
  in `reports/final/`.

### Deliverable mapping

- Baseline: [`docs/baseline_findings.md`](../docs/baseline_findings.md)
- Method: [`docs/detection_methodology.md`](../docs/detection_methodology.md),
  [`docs/evaluation_methodology.md`](../docs/evaluation_methodology.md)
- Decisions: [`docs/implementation_decisions.md`](../docs/implementation_decisions.md)
- Final evidence: [`docs/validation_report.md`](../docs/validation_report.md)
- Machine-readable evidence: [`reports/final/`](../reports/final/)

## Notes
- This is the initial implementation session
- All code has been written by the AI agent following the specifications
- Candidate should review and understand all implementation decisions
- The 2.0 session brief above is reconstructed because the original verbatim prompt was not retained;
  it is not presented as a quotation

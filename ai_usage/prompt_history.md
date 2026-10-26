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

## Notes
- This is the initial implementation session
- All code has been written by the AI agent following the specifications
- Candidate should review and understand all implementation decisions

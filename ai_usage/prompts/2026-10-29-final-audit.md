# 2026-10-29 Final Audit Prompt Record

**Tool/model:** OpenCode / DeepSeek V4.1 Flash Free
**Record status:** **VERBATIM** — copied from the live user message for the 2026-10-29 final audit.
System/developer harness instructions are not included.

````text
# YottaFlex AI Candidate Project: Final Audit and Submission Readiness

Act as a senior Python engineer, industrial simulation engineer, data engineer, QA engineer, and technical reviewer.

You are working inside my existing YottaFlex AI Candidate Project repository. The project has already undergone multiple implementation and remediation passes.

The latest reported state includes:
- 68 passing tests.
- A baseline configuration targeting exactly 100,000 telemetry points.
- 3 facilities, 20 pumps, 30 tanks, and 60 valves.
- Industrial simulation and anomaly detection.
- Five required negative scenarios.
- CSV, JSON, SQLite, and SQL export functionality.
- Data validation, evaluation, and reproducibility reports.
- Equipment state-history handling.

These are claims to verify against the actual repository, not assumptions.

## MAIN OBJECTIVE

Perform one final, evidence-based audit against the original problem statement.

Fix genuine remaining defects, verify the generated outputs, update inaccurate documentation, and prepare the project for submission.

**Do not rebuild the project from scratch. Do not perform unnecessary refactoring. Do not change working behavior without a clear reason.**

---

## PHASE 1: INSPECT THE CURRENT REPOSITORY

Before editing:

1. Confirm the repository root.
2. Inspect the source code, configuration, tests, documentation, SQL files, and generated artifacts.
3. Check Git status, current branch, remotes, and latest commit.
4. Read the README, data dictionary, validation report, evaluation report, reproducibility report, and requirement matrix.
5. Identify which requirements are implemented, tested, generated, or merely documented.

Create or update a requirement matrix with these columns:

- Requirement
- Implementation file
- Relevant test
- Generated artifact
- Verification method
- Actual result
- Status: PASS, WARN, FAIL, or NOT VERIFIED

Do not mark a requirement PASS just because a file or function exists.

Preserve unrelated changes and never overwrite user work.

## PHASE 2: VERIFY THE EXACT BASELINE DATASET

The required baseline is:

| Entity | Required count |
|---|---:|
| Facility | 3 |
| Pump | 20 |
| Tank | 30 |
| Valve | 60 |
| Telemetry | Exactly 100,000 records |

The project reportedly has a configuration under `reports/final/yf2-100k/`.

Inspect the actual generator configuration and produce a fresh dataset in a temporary directory.

Verify the real generated files and database, not only the manifest or summary report.

Check:

1. Exactly 3 facilities.
2. Exactly 20 pumps.
3. Exactly 30 tanks.
4. Exactly 60 valves.
5. Exactly 100,000 telemetry records.
6. Unique primary keys.
7. Valid foreign-key references.
8. Valid sensor and equipment relationships.
9. Valid timestamp ordering.
10. Consistent IDs across CSV, JSON, and SQLite exports.
11. Valid topology.
12. Ground-truth labels are separate from detector input features.
13. All derived values use the appropriate source records.

Do not generate padding records, duplicate telemetry, or discard valid data merely to achieve the target count.

Preserve the full-scale configuration and ensure the starter and full datasets use the same generator.

If the current implementation fails, fix the underlying defect, regenerate the output, and rerun the relevant tests.

## PHASE 3: VERIFY DETERMINISTIC IDENTIFIERS

Confirm the project uses the required naming conventions:

- `FAC-001`
- `PUMP-001`
- `TANK-001`
- `VALVE-001`
- `SNS-001`
- `SIM-2026-000001`

Verify that identifiers are deterministic, immutable within generated datasets, and referenced consistently across all exports.

Use the documented fixed seed, expected to be `20261022` unless the actual project configuration specifies otherwise.

Check that changing the dataset scale does not break referential integrity or identifier generation.

## PHASE 4: VERIFY THE INDUSTRIAL SIMULATION

Inspect the actual implementation of:

- Facility and equipment topology.
- Pump nominal curves.
- Tank capacity and level.
- Valve operating states.
- Sensor measurements for flow, pressure, and tank level.
- Approximate mass balance.
- Operating modes.
- Leak scenarios.
- Blockage scenarios.
- Pump degradation scenarios.
- Sensor-fault scenarios.
- Simulation assumptions and outcomes.
- Traceability between simulation inputs and outputs.

Verify that:

1. Every component belongs to a valid facility.
2. Every pipe connects valid nodes in valid baseline data.
3. Required connectivity constraints are enforced.
4. Physical units are explicit and consistent.
5. Measurements and derived quantities are calculated from source data.
6. Ground-truth labels are generated using documented scenario rules.
7. Detector features do not leak ground-truth labels.
8. Simulation runs can be traced to their input configuration.
9. Historical state changes are retained as explicit records where appropriate.
10. Deliberate anomaly scenarios do not silently corrupt unrelated baseline data.

Document model assumptions and limitations honestly.

Do not invent unsupported physical accuracy claims.

## PHASE 5: AUDIT THE TEN CORE ENTITIES

Verify the implementation and documentation of:

1. Facility
2. Pump
3. Tank
4. Valve
5. Pipe
6. Sensor
7. Telemetry
8. OperatingMode
9. Alarm
10. SimulationRun

For each entity, ensure the data dictionary documents every field's:

- Name
- Data type
- Required or optional status
- Primary-key or foreign-key status
- Allowed values
- Units, where applicable
- Uniqueness requirements
- Default values, where applicable
- Validation rules
- Relationships and constraints

Document:

- One-to-one relationships.
- One-to-many relationships.
- Many-to-many relationships.
- Optional relationships.
- Relationship cardinality.
- Effective dates.
- Lifecycle states.
- Event-history behavior.

Use bridge tables where actual many-to-many relationships require them. Do not create unnecessary bridge tables.

Confirm that SQL joins and relationships work correctly.

## PHASE 6: VERIFY ALL FIVE REQUIRED NEGATIVE SCENARIOS

Test each scenario independently:

1. A pipe references a missing node.
2. A tank level exceeds capacity.
3. Flow conservation is violated beyond the documented tolerance.
4. Simulation output lacks its input configuration.
5. A sensor fault is incorrectly labelled as a process fault.

For every scenario:

- Create a controlled test fixture.
- Run the relevant validator or detection logic.
- Verify the expected exception or classification.
- Confirm that the error is reported clearly.
- Ensure unrelated baseline records remain valid.
- Add a regression test if necessary.

The sensor-fault scenario must distinguish instrumentation problems from actual process failures.

Do not simply document a negative scenario without verifying its behavior.

## PHASE 7: VERIFY STATE HISTORY AND TRACEABILITY

Inspect equipment state-history records and simulation traceability.

Verify that relevant state changes are represented as explicit historical events rather than silently overwriting previous states.

Where applicable, historical records should identify:

- Equipment
- Previous state
- New state
- Timestamp
- Reason
- Source or simulation run

Check that:

- State transitions are valid.
- Event timestamps are consistent.
- Foreign keys resolve correctly.
- Simulation outputs retain references to their input configuration.
- Alarm records can be traced to relevant detections and source data.

Do not add meaningless placeholder events to satisfy a superficial row-count requirement.

## PHASE 8: VERIFY CSV, JSON, SQLITE, AND SQL EXPORTS

Confirm that the project actually generates:

- Master-data CSV files.
- Telemetry CSV.
- Ground-truth CSV or JSON.
- Simulation outputs.
- Alarm and detection outputs.
- JSON exports.
- SQLite database.
- SQL schema and seed-data script.
- Source manifest.
- Validation report.
- Reproducibility report.

Verify actual output files, row counts, identifiers, and relationships.

Do not confuse SQL analytical queries with a portable SQL seed-data script.

If the full telemetry dataset is excluded from Git, ensure that:

1. The README documents the exact regeneration command.
2. The generator works.
3. The resulting count is exactly 100,000.
4. The manifest matches the generated artifact.
5. The repository contains a reasonable sample dataset or representative outputs where useful.

Avoid committing unnecessary large generated datasets.

## PHASE 9: VERIFY ANOMALY DETECTION AND METRICS

Run the documented evaluation workflow against the actual generated ground truth and detection results.

Verify event-level and point-level metrics separately.

Check:

- True positives.
- False positives.
- True negatives.
- False negatives.
- Precision.
- Recall.
- F1.
- False-positive rate, where defined.
- Detection latency, where supported.
- Event matching rules.
- Duplicate alarm handling.
- Unknown-label handling.
- Sensor-fault classification.

Previously reported results included:

- Event-level precision: 100%.
- Event-level recall: 90.91%.
- Event-level F1: 95.24%.
- Detected events: 10 of 11.
- Point-level precision: 98.83%.
- Point-level recall: 80.38%.
- Point-level F1: 88.66%.

Recalculate these values from the current artifacts. Do not reuse the figures unless the latest run confirms them.

Investigate the previously missed light-leak event.

Determine whether the issue is caused by:

- A detector limitation.
- A software defect.
- Incorrect scenario generation.
- Incorrect ground-truth labels.
- An evaluation defect.

Fix genuine defects. If the light leak remains undetected, document the limitation and its implications.

Never manipulate thresholds, labels, scenarios, or evaluation boundaries merely to improve metrics.

## PHASE 10: VERIFY REPRODUCIBILITY

Generate the same dataset twice in independent temporary directories using the documented seed and configuration.

Compare:

- Master-data contents.
- Telemetry contents.
- Ground-truth labels.
- Simulation outputs.
- Detection outputs.
- Alarm records.
- Logical database contents.
- Exported data.
- Validation results.
- Checksums.

The previous report claimed that 20 of 23 artifacts were byte-identical, with three differing only in timestamps.

Verify this independently.

If differences remain, identify their precise causes and determine whether the underlying data and analytical results are equivalent.

Clearly distinguish:

- Byte-for-byte reproducibility.
- Logical data equivalence.
- Timestamp-dependent metadata differences.

Update the reproducibility report using actual results.

Do not claim reproducibility was verified if the commands did not execute successfully.

## PHASE 11: RECONCILE VALIDATION REPORTS

Inspect the README, detailed validation report, machine-readable summaries, and generated validation outputs.

Recalculate actual PASS, WARN, FAIL, and NOT_IMPLEMENTED counts.

Make all summaries consistent.

Separate:

- Data-integrity validation.
- Schema validation.
- Negative-scenario tests.
- Detection evaluation.
- Reproducibility checks.
- Documentation review.
- Checks not executed.

Do not suppress warnings to make the report appear perfect.

Mark any unverified requirement as NOT VERIFIED.

## PHASE 12: VERIFY INSTALLATION AND TESTS

Inspect the actual package configuration and README installation instructions.

Where possible, create a clean virtual environment and follow the documented setup.

For example, on Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pytest -q
```

Use the correct command for the project's actual dependency and packaging configuration.

Run the complete test suite.

Report:

- Exact commands executed.
- Actual exit status.
- Passed tests.
- Failed tests.
- Skipped tests.
- Environmental limitations.

Do not report the previous 68 passing tests unless the latest execution confirms them.

Fix genuine packaging or setup issues without unnecessarily changing working application logic.

## PHASE 13: AUDIT AI PROMPT HISTORY

Review:

- `ai_usage/prompt_history.md`
- `ai_usage/tools_used.md`
- Other AI-use documentation.

Preserve all recoverable original prompts.

Clearly label reconstructed prompts and identify missing historical records.

Do not invent verbatim prompts or claim the history is complete without evidence.

Document which AI tools were used and what assistance they provided.

The documentation should help me understand and explain:

- System architecture.
- Design decisions.
- Simulation assumptions.
- Detection logic.
- Evaluation methodology.
- Known limitations.
- Testing and validation.

Keep the disclosure factual and transparent.

## PHASE 14: FINAL SECURITY AND GIT AUDIT

Check for:

- API keys and credentials.
- Personal or sensitive information.
- Unauthorized proprietary code.
- Virtual environments.
- Python caches.
- Temporary files.
- Unnecessary binaries.
- Duplicate datasets.
- Unrelated modifications.
- Stale reports.

Run:

```bash
git status --short
git diff --check
git diff --stat
```

Inspect the final diff.

Do not delete unrelated user work.

Do not force-push or rewrite shared Git history.

Do not publish to an unconfirmed repository.

## PHASE 15: PUBLIC GITHUB SUBMISSION

Inspect the configured Git remote and branch.

If the destination repository is correct, publishing is authorized, and authentication is available:

1. Review all files that will be committed.
2. Commit reviewed changes using a descriptive message.
3. Check remote changes before pushing.
4. Push safely without force-pushing.
5. Verify that the push succeeds.
6. Confirm the latest commit is visible on the intended branch.

If the repository destination is unknown, authentication is unavailable, or conflicts exist, stop and explain what is needed.

Do not invent a repository URL or claim that a push succeeded without evidence.

## FINAL ACCEPTANCE CHECKLIST

Report the actual status of each item:

- [ ] Three facilities.
- [ ] Twenty pumps.
- [ ] Thirty tanks.
- [ ] Sixty valves.
- [ ] Exactly 100,000 telemetry records independently counted.
- [ ] Deterministic IDs and fixed-seed generation.
- [ ] Valid topology and entity relationships.
- [ ] Complete field-level data dictionary.
- [ ] Documented cardinality and lifecycle behavior.
- [ ] Appropriate event-history handling.
- [ ] All five negative scenarios verified.
- [ ] Ground truth isolated from detector input features.
- [ ] CSV, JSON, SQLite, and SQL exports verified.
- [ ] Installation instructions verified.
- [ ] Complete test suite executed.
- [ ] Detection metrics recalculated.
- [ ] Known limitations disclosed.
- [ ] Reproducibility independently checked.
- [ ] Validation reports reconciled.
- [ ] AI prompt history accurately documented.
- [ ] No secrets or unauthorized material.
- [ ] Public GitHub publication verified, if authorized.

Use these status labels:

- PASS: Verified through execution or direct inspection.
- WARN: Partially satisfied or a documented limitation remains.
- FAIL: A requirement is demonstrably unsatisfied.
- NOT VERIFIED: Insufficient evidence.

## REQUIRED FINAL RESPONSE

Provide:

1. Final repository status.
2. Actual master-data and telemetry counts.
3. Test commands and results.
4. Verified detection metrics.
5. Validation counts.
6. Reproducibility findings.
7. Export verification.
8. AI prompt-history status.
9. Remaining limitations.
10. Files changed.
11. Git branch, commit hash, remote, and push status where verifiable.
12. Final submission-readiness verdict.

Do not produce another broad refactor. Perform only necessary corrections, preserve working functionality, and provide evidence for every claim.

**The project is ready only when its actual implementation and generated outputs support the claims made in its documentation.**
````

# 2026-10-28 Final Verification Prompt Record

**Tool/model:** OpenCode / DeepSeek V4.1 Flash Free
**Record status:** **VERBATIM** — copied from the live user message for the final acceptance pass.
System/developer harness instructions are not included.

````text
# YottaFlex AI Candidate Project: Final Verification and Submission

You are working on my existing YottaFlex AI Candidate Project repository.

The project has already undergone several implementation and remediation passes. The latest reported version has 68 passing tests, an exact 100,000-point baseline configuration, expanded export functionality, equipment state history, and updated validation and reproducibility reports.

Your task is to perform the FINAL verification, resolve only genuine remaining defects, and prepare the repository for submission.

**Do not rebuild the project. Do not repeat completed work unnecessarily. Do not change working logic merely to make the code look different.**

## 1. Establish the Actual Current State

Before editing anything:

1. Confirm the repository root.
2. Inspect the current Git branch, working tree, remotes, and latest commit.
3. Read the README and the latest validation, evaluation, and reproducibility reports.
4. Inspect the existing source code, tests, configuration, export logic, and AI-use documentation.
5. Identify which previously reported results can be verified directly.

Treat previously reported results as claims to verify, not facts to assume.

Preserve unrelated changes and do not overwrite user work.

## 2. Verify the Exact 100,000-Point Baseline

The baseline requirements are:

- 3 facilities
- 20 pumps
- 30 tanks
- 60 valves
- Exactly 100,000 telemetry points

Use the project's documented generation command to generate the baseline in a temporary output directory.

Then verify the actual generated files and database.

Check:
- Exact telemetry row count.
- Master-data counts.
- Primary-key uniqueness.
- Foreign-key integrity.
- Sensor and equipment references.
- Timestamp ordering.
- Valid topology.
- Stable IDs.
- Fixed-seed behavior.
- Separation of ground truth from detector input features.

Do not rely solely on manifest claims, filenames, or reports.

If the generator does not produce exactly 100,000 telemetry records, fix the underlying issue and rerun the checks.

Do not add padding records, duplicate telemetry, or silently remove valid records.

Preserve the existing full-scale generation configuration.

## 3. Verify Installation and All Tests

Use the actual installation instructions in the README.

Where feasible, create a clean virtual environment and install the project using the documented commands.

Run the complete test suite, for example:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pytest -q
```

Use the appropriate commands if the project has separate development dependencies or a different supported installation process.

Verify that a new user can follow the instructions without relying on hidden environment settings.

Report:
- Exact commands executed.
- Actual exit status.
- Number of passed, failed, and skipped tests.
- Any environmental limitations.

Do not report the previously claimed 68 passing tests unless the current run confirms it.

## 4. Verify All Required Exports

Confirm that the project actually generates and preserves consistent:

- Master-data CSV files.
- Telemetry CSV files.
- Ground-truth CSV or JSON.
- Alarm and simulation outputs.
- JSON exports.
- SQLite database.
- SQL schema and seed-data scripts.
- Source manifest.
- Validation report.
- Reproducibility report.

Verify actual outputs, row counts, identifiers, and relationships.

If a large generated dataset is intentionally excluded from Git, ensure that the README gives a working command to regenerate it and that the manifest is accurate.

Avoid committing unnecessary large generated datasets merely to prove that generation works.

## 5. Verify the Data Model and Negative Scenarios

Check the ten required entities:

- Facility
- Pump
- Tank
- Valve
- Pipe
- Sensor
- Telemetry
- OperatingMode
- Alarm
- SimulationRun

Confirm that primary keys, foreign keys, field constraints, units, cardinality, optional relationships, lifecycle behavior, and effective dates are documented appropriately.

Verify that the project handles the five required negative scenarios:

1. Pipe references a missing node.
2. Tank level exceeds capacity.
3. Flow conservation exceeds the documented tolerance.
4. Simulation output lacks its input configuration.
5. Sensor fault is incorrectly labelled as a process fault.

Check that the validators and tests actually detect these cases.

Confirm that state history is handled according to the documented design and that historical events are not silently overwritten.

Fix only genuine gaps.

## 6. Verify Anomaly Detection and Evaluation

Run the documented detection and evaluation pipeline against the appropriate ground truth.

Verify event-level and point-level metrics independently.

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
- Duplicate alarm handling.
- Unknown-label handling.
- Sensor-fault classification.

Investigate the previously documented missed light-leak event.

If the event remains undetected, retain the limitation and explain it clearly.

Do not alter thresholds, remove difficult scenarios, change ground-truth labels, or manipulate evaluation boundaries merely to improve the results.

Ensure that all reported metrics match the actual evaluation outputs.

## 7. Verify Reproducibility

Generate the same configuration twice in separate temporary directories using the documented fixed seed, expected to be `20261022` unless the actual project configuration specifies otherwise.

Compare:
- Master-data contents.
- Telemetry contents.
- Ground-truth labels.
- Simulation outputs.
- Alarm and detection outputs.
- Logical database contents.
- Exported files.
- Artifact checksums.

The previous report claimed that 20 of 23 files were byte-identical, with three differences attributed to timestamps.

Verify this independently.

If the three differences remain, establish that they are genuinely limited to documented nondeterministic metadata and that the underlying generated data and analytical results remain reproducible.

Do not claim complete byte-for-byte reproducibility if the comparison does not support it.

Update the report with the actual commands, files compared, counts, checksums, differences, and conclusions.

## 8. Reconcile Validation Reports

Inspect the README, detailed validation report, and machine-readable validation outputs.

Ensure they report consistent results.

Distinguish:
- Successful checks.
- Failed checks.
- Warnings.
- Unimplemented requirements.
- Checks that were not run.
- Detection-evaluation limitations.
- Documentation limitations.

Do not suppress warnings or change counts without evidence.

Mark any unverified result as `NOT VERIFIED`.

## 9. Audit AI Prompt History and Disclosure

Review:
- `ai_usage/prompt_history.md`
- `ai_usage/tools_used.md`
- Any other AI-use documentation.

Preserve all recoverable original prompts.

Clearly distinguish original prompts from reconstructed prompts.

Do not fabricate historical prompts or claim the history is complete if some records are missing.

Document:
- Which AI tools were used.
- What assistance they provided.
- Which implementation choices I reviewed.
- What I personally tested and validated.
- What limitations remain in recovering prompt history.

Keep this documentation factual and transparent.

Do not create a misleading account of work that was not performed.

## 10. Perform the Final Repository Audit

Check for:
- API keys and credentials.
- Personal or sensitive information.
- Unauthorized proprietary code.
- Virtual environments.
- Python caches.
- Temporary files.
- Unnecessary binaries.
- Duplicate datasets.
- Incorrect or stale reports.
- Missing setup instructions.
- Uncommitted unrelated changes.

Run:

```bash
git status --short
git diff --check
git diff --stat
```

Review the final diff.

Do not delete user changes or force-push.

## 11. Verify Public GitHub Publication

The recruitment requirements call for a dedicated public GitHub repository.

Inspect the configured remote and confirm that it points to the intended repository.

If the repository destination is correct, publishing is authorized, and authentication is available:

1. Commit the reviewed changes using a descriptive message.
2. Fetch and inspect the remote state.
3. Push safely without force-pushing or rewriting shared history.
4. Verify that the push succeeds.
5. Confirm that the latest commit is visible on the intended branch.

If the destination is unknown, authentication is unavailable, or the remote has conflicting changes, stop and explain what is required.

Do not invent a repository URL.

Do not claim that the project is published based only on a local commit or a previous report.

## 12. Final Acceptance Checklist

Produce a final checklist covering:

- [ ] Exact baseline master-data counts.
- [ ] Exactly 100,000 telemetry records verified from generated output.
- [ ] Valid IDs and relationships.
- [ ] Complete data dictionary.
- [ ] Required negative scenarios verified.
- [ ] Ground truth separated from detector features.
- [ ] Event history handled correctly.
- [ ] CSV, JSON, SQLite, and SQL exports verified.
- [ ] All tests executed successfully, or failures clearly reported.
- [ ] Detection metrics independently verified.
- [ ] Known light-leak limitation disclosed.
- [ ] Reproducibility independently checked.
- [ ] Validation reports reconciled.
- [ ] Installation instructions verified.
- [ ] AI prompt history accurately documented.
- [ ] No secrets or unauthorized material.
- [ ] Public GitHub publication verified, if authorized.

Use these statuses:
- PASS: directly verified.
- WARN: partially satisfied or a known limitation remains.
- FAIL: a requirement is demonstrably unsatisfied.
- NOT VERIFIED: insufficient evidence.

## 13. Final Response

Provide a concise but complete report containing:

1. Final repository state.
2. Actual master-data and telemetry counts.
3. Exact test command and results.
4. Verified detection metrics.
5. Validation counts.
6. Reproducibility findings.
7. Export verification.
8. AI prompt-history status.
9. Remaining limitations.
10. Files changed.
11. Commit hash, branch, repository URL, and push status where verifiable.
12. A final submission-readiness verdict.

**Final rule: Do not perform another broad refactor. Verify the current project, make only necessary corrections, preserve honest limitations, and provide evidence for every claim.**
````

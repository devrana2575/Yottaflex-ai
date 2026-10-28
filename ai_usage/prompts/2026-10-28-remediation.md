# 2026-10-28 Remediation Prompt Record

**Tool/model:** OpenCode / DeepSeek V4.1 Flash Free
**Record status:** **RECONSTRUCTED — not a verbatim quotation.** The full prompt text was not
retained verbatim in the continuation record available to this agent. The recovered requirement
summary below is copied from the serialized conversation checkpoint and is preserved so the work is
auditable. It must not be represented as the exact prompt wording.

## Recovered remediation brief

> Complete the final remediation and submission readiness of the existing YottaFlex 2.0 repository,
> verify every claim from execution, and prepare evidence without rebuilding or overwriting working
> functionality.

Original requirement summary recovered from the checkpoint:

- Preserve the existing repository/functionality and master data: 3 facilities, 20 pumps, 30 tanks,
  60 valves.
- Add an exact 100,000 telemetry-record configuration while preserving the historical 316,800-row
  path.
- Preserve deterministic generation with seed `20261022`; no fake padding, duplicate telemetry, or
  silent removal of valid records.
- Do not tune thresholds, change scenarios, ground truth, or matching rules; preserve the documented
  light-leak miss.
- Complete field-level documentation for all ten core entities, including types, keys, constraints,
  units, defaults, relationships, cardinality, lifecycle, and history.
- Implement and validate real equipment state-history generation and persistence; no meaningless
  placeholder rows.
- Provide actual CSV, JSON, SQLite, and portable SQL schema/seed export capability.
- Add minimal tests for all five required negative scenarios and verify unrelated data is not
  corrupted.
- Verify topology, physics, mass balance, anomaly injection, ground-truth isolation, installation,
  detection/evaluation, validation counts, and deterministic regeneration.
- Record every recoverable prompt; label reconstructed history; do not claim completeness unless
  verified.
- Run final secret/PII/large-file/untracked-file audit and review the actual diff before committing.
- Do not force-push or rewrite shared history; publish only if destination and authorization are
  confirmed.
- Final response must use only `PASS`, `WARN`, `FAIL`, and `NOT VERIFIED` status labels.

## Outcome constraints used

- Exact 100,000 allocation: 120 lexicographically first sensors x 455 + 100 sensors x 454.
- Derived duration: `455 x 60 s = 7.583333... h`.
- `telemetry_target_rows=None` preserves the historical 316,800-row path.
- The `baseline` scenario set excludes the row-removing missing-sensor fault.
- The historical `compact` 99,000-row configuration is retained and labelled historical.
- State history uses separate `ESE-######` IDs so alarm-history IDs are not shifted.
- Existing schema/application version remains `2.0.0`; compatibility is documented.
- JSON and portable SQL exports read exported CSVs so identifiers remain consistent.
- Publication is not authorized in this record; no push is claimed.

## Recovery note

The original 1.x master prompt remains unrecoverable and is labelled reconstructed in
`ai_usage/prompt_history.md`. The 2026-10-27 submission-readiness audit prompt is preserved verbatim
in that file. This 2026-10-28 record is a reconstructed requirement summary, not a verbatim prompt.

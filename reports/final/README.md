# Final Evidence Bundle

This directory contains compact evidence copied from clean runs executed on 2026-10-27 and
2026-10-28 with seed `20261022` and a 60-second sampling interval. It intentionally excludes the
large telemetry, JSON and SQL-seed files; the full run directories are outside the repository and
are identified in `docs/validation_report.md`.

**2026-10-28 remediation:** Added an exact 100,000-row `baseline` configuration, populated
append-only equipment state history, and CSV/JSON/SQLite/portable-SQL exports. The baseline has
100,000 real rows (120 sensors x 455 + 100 sensors x 454), 341 state events, 87 validation PASS per
run (all seven final CSVs: 609/609 PASS), 20/20 SQL PASS and 18 populated SQLite tables. Two fresh
runs produced 20/23 byte-identical files;
the other three differed only in wall-clock `evaluated_at` / `validated_at` fields and were
logically identical. The test suite reports **68 passed**. See `yf2-100k/`,
`yf2-compact-99k/` (historical 99k) and `reproducibility_100k.json`.

**Prior audit re-verification:** The 2026-10-27 submission-readiness audit re-ran the
full/evaluation pipeline, validation, SQL and tests in the main and fresh environments, and re-ran
two full/default reproducibility runs after the source fixes. Deterministic evaluation artifacts
matched this bundle byte-for-byte, and the two fresh runs matched each other on all 19 compared
files within the main environment. A fresh pandas 3.1.0 / NumPy 2.5.4 environment reproduced every
metric and 17/19 artifacts; two files differed only in `peak_value` floats at about `1e-13` (see
`reproducibility.json`).

| Directory | Mode | Scenario set | Duration | Telemetry rows | State events |
|---|---|---|---|---:|---|
| `yf2-starter` | starter | default | 24 h | 51,840 | n/a (pre-remediation evidence) |
| `yf2-full` | full | default | 24 h | 316,800 | n/a (pre-remediation evidence) |
| `yf2-compact-99k` (historical) | full | compact | 7.5 h | 99,000 | n/a (pre-remediation evidence) |
| `yf2-100k` (exact evidence) | full | baseline | 7.583 h | 100,000 | 341 |
| `yf2-calibration` | full | calibration | 24 h | 316,740 | n/a (pre-remediation evidence) |
| `yf2-evaluation` | full | evaluation | 24 h | 316,740 | n/a (pre-remediation evidence) |
| `yf2-repro` | full | default | 24 h | 316,800 | n/a (pre-remediation evidence) |

Current pipeline runs also write `equipment_state_events.csv`; the 2026-10-28 baseline evidence
contains the 341 rows. The historical `yf2-*` directories predate that table, so no state-event count
is claimed for them.

Each run directory contains:

- `config.json`, `simulation_runs.csv`, `simulation_metadata.json`
- `alarms.csv`, `alarm_events.csv`, `alarm_incidents.csv`
- current runs additionally contain `equipment_state_events.csv`
- `evaluation_metrics.json`, `evaluation_metrics.csv`, `evaluation_events.csv`,
  `evaluation_summary.md`
- `validation_results.csv`, `sql_query_report.json`, `run_manifest.json`
- `pipeline.log`

Top-level files:

- `summary.json` — machine-readable metrics, validation/SQL counts and per-event results for the
  prior five primary runs plus the exact-100k baseline.
- `reproducibility.json` — prior byte-level comparison of two fresh full/default audit runs across
  19 deterministic artifacts, including SHA-256 hashes, configuration hashes and SQLite logical
  comparison. Neutral run labels replace absolute local paths.
- `reproducibility_100k.json` — 2026-10-28 exact-100k two-run comparison (20/23 byte-identical,
  3 timestamp-only), SQLite logical equality, and portable CSV/JSON/SQLite/SQL export checks.
- `yf2-100k/` ? compact exact-100k evidence: redacted config, simulation metadata, direct
  telemetry count/hash manifest, master CSVs, alarms, evaluation events, 87 validation rows, SQL
  report, 341 state events and a hash/count summary.
- `yf2-compact-99k/` ? historical compact 99,000-row demonstration, preserved under its actual
  count rather than the old misleading `yf2-100k` name.

## Reading the evidence

- The primary independent result is `yf2-evaluation`. The exact-100k baseline is a
  demonstration/regression configuration, not a replacement evaluation set.
- `validation_results.csv` is the complete 87-row executable PASS/FAIL/WARN/NOT_IMPLEMENTED record:
  87 PASS, 0 FAIL, 0 WARN, 0 NOT_IMPLEMENTED. Review-level caveats (light-leak coverage,
  reconstructed prompt records, un-repeated cross-version rerun, and ignored generated outputs) are
  documented in `docs/validation_report.md` and are not CSV rows.
- `sql_query_report.json` contains each SQL statement, expectation, result rows and status.
- `evaluation_metrics.json` is the full nested result; `evaluation_summary.md` is the readable
  version.
- `run_manifest.json` is evidence of artifact hashes. It is not byte-identical across directories
  because it hashes path-bearing `config.json` and timestamped `evaluation_metrics.csv`; see
  `reproducibility.json`, `reproducibility_100k.json` and `docs/validation_report.md`.

**Privacy note:** Absolute local-path strings in the copied `config.json`, `pipeline.log` and
`baseline_tests.txt` evidence were replaced with `<external-temp>` / `<local-user>` labels. The
exact-100k evidence uses the redacted `config.json` for the same reason; its absolute paths are not
copied. No reported metric, row count, status or log message was changed, and the path-independent
configuration hash is unaffected. Because `config.json` is redacted, its copied bytes no longer
match the original `config.json` SHA-256 recorded in `run_manifest.json`; the original manifest
entry is retained as the historical hash. The manifest also lists `telemetry.csv`, which is not
committed; the directly measured count and SHA-256 are recorded in
`yf2-100k/telemetry_manifest.json`. `pipeline.log` and `baseline_tests.txt` are not hashed by
the manifest.

## Reproduce

From the repository root:

```bash
# Primary independent evaluation
yottaflex pipeline --mode full --seed 20261022 --scenario-set evaluation \
  --output-dir <fresh-output-dir>/evaluation

# Exact 100,000-row baseline
yottaflex pipeline --mode full --seed 20261022 --scenario-set baseline \
  --target-telemetry-rows 100000 --output-dir <fresh-output-dir>/baseline-100k

# Portable exports
yottaflex export-json --output-dir <fresh-output-dir>/baseline-100k
yottaflex export-sql-script --output-dir <fresh-output-dir>/baseline-100k
```

See `docs/validation_report.md` for the full command list and interpretation.

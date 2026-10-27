# Final Evidence Bundle

This directory contains compact evidence copied from six clean runs (five primary runs plus a
reproducibility run) executed on 2026-10-27 with seed `20261022` and a 60-second sampling interval.
It intentionally excludes the large telemetry files; the full run directories are outside the
repository and are identified in `docs/validation_report.md`.

**Audit re-verification:** The 2026-10-27 submission-readiness audit re-ran the full/evaluation
pipeline, validation, SQL and tests in the main and fresh environments, and re-ran two full/default
reproducibility runs after the source fixes. Deterministic evaluation artifacts matched this bundle
byte-for-byte, and the two fresh runs matched each other on all 19 compared files within the main
environment. A fresh pandas 3.1.0 / NumPy 2.5.4 environment reproduced every metric and 17/19
artifacts; two files differed only in `peak_value` floats at about `1e-13` (see
`reproducibility.json`).

| Directory | Mode | Scenario set | Duration | Telemetry rows |
|---|---|---|---:|---:|
| `yf2-starter` | starter | default | 24 h | 51,840 |
| `yf2-full` | full | default | 24 h | 316,800 |
| `yf2-100k` | full | compact | 7.5 h | 99,000 |
| `yf2-calibration` | full | calibration | 24 h | 316,740 |
| `yf2-evaluation` | full | evaluation | 24 h | 316,740 |
| `yf2-repro` | full | default | 24 h | 316,800 |

Each run directory contains:

- `config.json`, `simulation_runs.csv`, `simulation_metadata.json`
- `alarms.csv`, `alarm_events.csv`, `alarm_incidents.csv`
- `evaluation_metrics.json`, `evaluation_metrics.csv`, `evaluation_events.csv`,
  `evaluation_summary.md`
- `validation_results.csv`, `sql_query_report.json`, `run_manifest.json`
- `pipeline.log`

Top-level files:

- `summary.json` — machine-readable metrics, validation/SQL counts and per-event results for all
  five primary runs.
- `reproducibility.json` — byte-level comparison of two fresh full/default audit runs across 19
  deterministic artifacts, including SHA-256 hashes, configuration hashes and SQLite logical
  comparison. Neutral run labels replace absolute local paths.

## Reading the evidence

- The primary independent result is `yf2-evaluation`.
- `validation_results.csv` is the complete 87-row executable PASS/FAIL/WARN/NOT_IMPLEMENTED record:
  87 PASS, 0 FAIL, 0 WARN, 0 NOT_IMPLEMENTED. Two review-level WARNs (light-leak coverage and the
  reconstructed 1.x prompt) are documented in `docs/validation_report.md` and are not CSV rows.
- `sql_query_report.json` contains each SQL statement, expectation, result rows and status.
- `evaluation_metrics.json` is the full nested result; `evaluation_summary.md` is the readable
  version.
- `run_manifest.json` is evidence of artifact hashes. It is not byte-identical across directories
  because it hashes path-bearing `config.json` and timestamped `evaluation_metrics.csv`; see
  `reproducibility.json` and `docs/validation_report.md`.

**Privacy note:** Absolute local-path strings in the copied `config.json`, `pipeline.log` and
`baseline_tests.txt` evidence were replaced with `<external-temp>` / `<local-user>` labels. No
reported metric, row count, status or log message was changed, and the path-independent
configuration hash is unaffected. Because `config.json` is redacted, its copied bytes no longer
match the original `config.json` SHA-256 recorded in `run_manifest.json`; the original manifest
entry is retained as the historical hash. `pipeline.log` and `baseline_tests.txt` are not hashed by
the manifest.

## Reproduce

From the repository root:

```bash
yottaflex pipeline --mode full --seed 20261022 --scenario-set evaluation \
  --output-dir <fresh-output-dir>
```

See `docs/validation_report.md` for the full command list and interpretation.

# Final Evidence Bundle

This directory contains compact evidence copied from six clean runs executed on 2026-10-27 with
seed `20261022` and a 60-second sampling interval. It intentionally excludes the large telemetry
files; the full run directories are outside the repository and are identified in
`docs/validation_report.md`.

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
- `reproducibility.json` — byte-level comparison of `yf2-full` and `yf2-repro` across 19
  deterministic artifacts, including SHA-256 hashes and configuration hashes.

## Reading the evidence

- The primary independent result is `yf2-evaluation`.
- `validation_results.csv` is the complete 87-row PASS/FAIL/WARN/NOT_IMPLEMENTED record.
- `sql_query_report.json` contains each SQL statement, expectation, result rows and status.
- `evaluation_metrics.json` is the full nested result; `evaluation_summary.md` is the readable
  version.
- `run_manifest.json` is evidence of artifact hashes. It is not byte-identical across directories
  because it hashes path-bearing `config.json` and timestamped `evaluation_metrics.csv`; see
  `reproducibility.json` and `docs/validation_report.md`.

## Reproduce

From the repository root:

```bash
yottaflex pipeline --mode full --seed 20261022 --scenario-set evaluation \
  --output-dir data/processed/evaluation-run
```

See `docs/validation_report.md` for the full command list and interpretation.

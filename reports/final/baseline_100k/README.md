# Exact 100,000-Row Baseline Evidence (2026-10-28)

This directory is compact evidence from a clean full-scale run with seed `20261022`, the
`baseline` scenario set and `--target-telemetry-rows 100000`. The run directory and the 32 MB
JSON / 30 MB SQL seed exports are outside the repository; they are not committed.

- Telemetry: **100,000** real `(sensor, timestamp)` rows; 120 sensors x 455 + 100 sensors x 454.
- Master data: 3 facilities, 20 pumps, 30 tanks, 60 valves, 135 pipes, 220 sensors.
- Equipment state history: **341** rows (333 initialization + 8 scenario transitions).
- Validation: 87 PASS / 0 FAIL / 0 WARN / 0 NOT_IMPLEMENTED.
- SQL: 20 PASS / 0 FAIL.
- Exports verified: CSV, SQLite (18 populated tables), per-table JSON and portable SQL seed;
  telemetry IDs matched across all four; SQLite `integrity_check=ok`; zero FK violations.

`config.redacted.json` replaces the local user/temp path with `<external-temp>`; the run's
original absolute paths are intentionally not copied. Metrics, row counts, validation and state
events are unchanged. See `reports/final/reproducibility_100k.json` for the two-run comparison.

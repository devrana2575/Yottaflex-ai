# Exact 100,000-Row Baseline Evidence (2026-10-28)

This directory is compact evidence from a clean full-scale run with seed `20261022`, the
`baseline` scenario set and `--target-telemetry-rows 100000`. The exact label is supported by the
actual generated `telemetry.csv` row count, not by the directory name: the external run contained
**100,000** rows. The 9.3 MB telemetry CSV, 32 MB JSON export and 30 MB SQL seed are intentionally
not committed; `telemetry_manifest.json` records the directly measured count, distribution and
SHA-256 of that file.

- Telemetry: **100,000** real `(sensor, timestamp)` rows; 120 sensors x 455 + 100 sensors x 454.
- Duration: **7.583333 h**; seed `20261022`; 60-second cadence.
- Master data: 3 facilities, 20 pumps, 30 tanks, 60 valves, 135 pipes, 220 sensors.
- Equipment state history: **341** rows (333 initialization + 8 scenario transitions).
- Validation: 87 PASS / 0 FAIL / 0 WARN / 0 NOT_IMPLEMENTED.
- SQL: 20 PASS / 0 FAIL; 18 populated SQLite tables (19 in the schema).
- Exports verified: CSV, SQLite, per-table JSON and portable SQL seed; telemetry IDs matched across
  all four; SQLite `integrity_check=ok`; zero foreign-key violations.

`config.json` replaces local user/temp paths with `<external-temp>`; the original absolute paths
are intentionally not copied. Metrics, row counts, validation and state events are unchanged. See
`reports/final/reproducibility_100k.json` for the fresh two-run comparison and
`reports/final/yf2-compact-99k/` for the historical compact 99,000-row evidence.

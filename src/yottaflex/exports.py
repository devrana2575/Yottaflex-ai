"""Portable JSON and SQL seed exports.

CSV remains the canonical intermediate format.  These helpers add two distinct
submission artifacts:

* JSON: one deterministic JSON array per table plus a manifest.
* SQL: a portable schema + INSERT script that can create a new SQLite database;
  it is not the same thing as the binary SQLite file.

The helpers deliberately read the exported CSVs rather than in-memory objects so
the JSON, SQL and SQLite exports all refer to the same identifiers and values.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd

from .schema import SCHEMA_SQL

MASTER_TABLES = (
    "facilities",
    "pumps",
    "tanks",
    "valves",
    "pipes",
    "sensors",
    "operating_modes",
)

EXPORT_TABLES = MASTER_TABLES + (
    "simulation_runs",
    "equipment_state_events",
    "scenario_definitions",
    "telemetry",
    "ground_truth",
    "alarms",
    "alarm_events",
    "alarm_incidents",
    "evaluation_metrics",
    "evaluation_events",
    "validation_results",
)

# Reverse dependency order for clearing a previously seeded database.
_DELETE_ORDER = tuple(reversed(EXPORT_TABLES))


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def _rows(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    normalized = frame.astype(object).where(pd.notna(frame), None)
    return normalized.to_dict(orient="records")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_json_tables(
    output_dir: str | Path,
    destination: str | Path,
    tables: Sequence[str] = EXPORT_TABLES,
) -> Dict[str, Any]:
    """Write one stable JSON array per exported table plus a manifest."""
    root = Path(output_dir)
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    # Store a relative source location, never an absolute local path.  This
    # keeps the manifest portable and avoids leaking the user's home directory
    # when the JSON export directory is moved with the run artifacts.
    try:
        source_root = Path(os.path.relpath(root, target)).as_posix()
    except ValueError:
        source_root = "<output-dir>"
    manifest: Dict[str, Any] = {
        "format": "json-tables-v1",
        "source_root": source_root,
        "tables": {},
    }
    for table in tables:
        csv_path = root / f"{table}.csv"
        if not csv_path.exists():
            continue
        frame = pd.read_csv(csv_path)
        payload = _rows(frame)
        json_path = target / f"{table}.json"
        with json_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False, default=_json_default)
            handle.write("\n")
        manifest["tables"][table] = {
            "rows": int(len(frame)),
            "source_csv": f"{table}.csv",
            "source_sha256": _sha256(csv_path),
            "json_sha256": _sha256(json_path),
        }
    manifest_path = target / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _sql_literal(value: Any) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "NULL"
    if isinstance(value, (np.integer,)):
        return str(int(value))
    if isinstance(value, (np.floating,)):
        return repr(float(value))
    if isinstance(value, (bool, np.bool_)):
        return "1" if bool(value) else "0"
    if isinstance(value, (int, float)):
        return repr(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


def export_sql_seed(
    output_dir: str | Path,
    destination: str | Path,
    tables: Sequence[str] = EXPORT_TABLES,
) -> Dict[str, Any]:
    """Write a portable SQLite schema + INSERT seed script.

    The script is destructive to the named tables when it is run against an
    existing database; it is intended to create a clean, reproducible database
    from the CSV artifacts.
    """
    root = Path(output_dir)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    counts: Dict[str, int] = {}
    lines: List[str] = [
        "-- YottaFlex portable schema + seed data",
        "-- Generated from exported CSV artifacts; deterministic row order.",
        SCHEMA_SQL.rstrip(),
        "",
        "BEGIN TRANSACTION;",
    ]
    for table in _DELETE_ORDER:
        lines.append(f"DELETE FROM {table};")
    lines.append("")
    for table in tables:
        csv_path = root / f"{table}.csv"
        if not csv_path.exists():
            continue
        frame = pd.read_csv(csv_path)
        counts[table] = int(len(frame))
        if frame.empty:
            continue
        columns = list(frame.columns)
        column_sql = ", ".join(columns)
        normalized = frame.astype(object).where(pd.notna(frame), None)
        for row in normalized.itertuples(index=False, name=None):
            values = ", ".join(_sql_literal(value) for value in row)
            lines.append(f"INSERT INTO {table} ({column_sql}) VALUES ({values});")
    lines.extend(["", "COMMIT;", ""])
    target.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    manifest = {
        "format": "sqlite-seed-sql-v1",
        "path": target.name,
        "rows": counts,
        "total_rows": int(sum(counts.values())),
        "sha256": _sha256(target),
        "tables": list(tables),
    }
    return manifest

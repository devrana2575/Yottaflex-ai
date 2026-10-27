"""Database persistence layer for YottaFlex 2.0.0."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd

from .schema import SCHEMA_SQL


class Database:
    """SQLite database manager with clean-recreate support."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
        return self.conn

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def create_schema(self, reset: bool = False) -> None:
        """Create tables; optionally remove any previous database first."""
        if reset:
            self.close()
            path = Path(self.db_path)
            if path.exists():
                path.unlink()
        conn = self.connect()
        conn.executescript(SCHEMA_SQL)
        conn.commit()

    def insert_dataframe(
        self, df: pd.DataFrame, table_name: str, if_exists: str = "append"
    ) -> int:
        if df is None or df.empty:
            return 0
        frame = df.copy()
        # SQLite does not know numpy scalar types or pandas nullable booleans.
        for column in frame.columns:
            if pd.api.types.is_bool_dtype(frame[column]):
                frame[column] = frame[column].astype(int)
        frame = frame.astype(object).where(pd.notna(frame), None)
        conn = self.connect()
        frame.to_sql(table_name, conn, if_exists=if_exists, index=False)
        conn.commit()
        return len(frame)

    def execute_query(
        self, query: str, params: Sequence[Any] = ()
    ) -> list[sqlite3.Row]:
        conn = self.connect()
        cursor = conn.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def execute_script(self, script: str) -> None:
        conn = self.connect()
        conn.executescript(script)
        conn.commit()

    def get_table_count(self, table_name: str) -> int:
        rows = self.execute_query(f"SELECT COUNT(*) AS cnt FROM {table_name}")
        return int(rows[0]["cnt"]) if rows else 0

    def table_names(self) -> list[str]:
        rows = self.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        return [str(row["name"]) for row in rows]

    def integrity_check(self) -> str:
        rows = self.execute_query("PRAGMA integrity_check")
        return str(rows[0][0]) if rows else "unknown"

    def foreign_key_violations(self) -> list[dict[str, Any]]:
        rows = self.execute_query("PRAGMA foreign_key_check")
        return [dict(row) for row in rows]

    def scalar(self, query: str, params: Sequence[Any] = ()) -> Any:
        rows = self.execute_query(query, params)
        return rows[0][0] if rows else None

    # Backwards-compatible helper used by older callers.
    def insert_many(self, table: str, columns: Iterable[str], rows: Iterable[Sequence[Any]]) -> int:
        column_list = list(columns)
        placeholders = ", ".join("?" for _ in column_list)
        sql = f"INSERT INTO {table} ({', '.join(column_list)}) VALUES ({placeholders})"
        conn = self.connect()
        payload = [tuple(row) for row in rows]
        conn.executemany(sql, payload)
        conn.commit()
        return len(payload)

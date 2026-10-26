"""Database persistence layer."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import pandas as pd

from .schema import SCHEMA_SQL
from .config import Config


class Database:
    """SQLite database manager."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        
    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        # Enable foreign keys
        self.conn.execute("PRAGMA foreign_keys = ON")
        return self.conn
    
    def create_schema(self):
        conn = self.connect()
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        conn.close()
        
    def insert_dataframe(self, df: pd.DataFrame, table_name: str, if_exists: str = 'append'):
        if df.empty:
            return
        conn = self.connect()
        df.to_sql(table_name, conn, if_exists=if_exists, index=False)
        conn.commit()
        conn.close()
    
    def execute_query(self, query: str, params: tuple = ()):
        conn = self.connect()
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        return rows
    
    def get_table_count(self, table_name: str) -> int:
        rows = self.execute_query(f"SELECT COUNT(*) as cnt FROM {table_name}")
        return rows[0]['cnt'] if rows else 0

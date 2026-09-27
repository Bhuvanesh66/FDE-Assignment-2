"""SQLite retrieval.

Rules followed (Class 5):
* retrieve only the rows/columns the workflow needs - every query lives in
  ``sql/*.sql`` so it can be reviewed and rerun on its own;
* never transform in SQL - the raw extract is preserved *with* its defects so
  the cleaning stage can show what it changed;
* an empty result is a recorded fact, not an exception; a missing table or
  database is a hard, clearly worded failure.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ..io_utils import sha256_file, write_csv, write_text
from ..logging_utils import get_logger


class SqlSourceError(RuntimeError):
    """Database missing, unreadable, or a required table/column is absent."""


@dataclass
class SqlExtract:
    name: str
    rows: int
    columns: list[str]
    sql_file: str
    raw_path: str
    params: dict = field(default_factory=dict)


class SqlSource:
    def __init__(self, db_path: Path, sql_dir: Path, raw_dir: Path):
        self.db_path = Path(db_path)
        self.sql_dir = Path(sql_dir)
        self.raw_dir = Path(raw_dir) / "sql"
        self.log = get_logger()
        if not self.db_path.exists():
            raise SqlSourceError(f"SQLite database not found: {self.db_path}")
        if self.db_path.stat().st_size == 0:
            raise SqlSourceError(f"SQLite database is empty (0 bytes): {self.db_path}")
        self.db_sha256 = sha256_file(self.db_path)
        self.extracts: list[SqlExtract] = []

    # ------------------------------------------------------------------ utils
    def _connect(self) -> sqlite3.Connection:
        # read-only URI so the pipeline can never modify the client database
        return sqlite3.connect(f"file:{self.db_path.as_posix()}?mode=ro", uri=True)

    def list_tables(self) -> list[str]:
        with self._connect() as con:
            rows = con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        return [r[0] for r in rows]

    def table_columns(self, table: str) -> list[str]:
        with self._connect() as con:
            return [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]

    def row_count(self, table: str) -> int:
        with self._connect() as con:
            return int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    # --------------------------------------------------------------- extracts
    def extract(self, name: str, table: str, params: dict | None = None) -> pd.DataFrame:
        """Run ``sql/<name>.sql`` and preserve the untouched result as CSV."""
        sql_file = self.sql_dir / f"{name}.sql"
        if not sql_file.exists():
            raise SqlSourceError(f"SQL file missing: {sql_file}")
        if table not in self.list_tables():
            raise SqlSourceError(
                f"Table '{table}' not found in {self.db_path.name}. Available: {self.list_tables()}"
            )
        sql = sql_file.read_text(encoding="utf-8")
        params = dict(params or {})
        try:
            with self._connect() as con:
                # read every column as text: type coercion is a cleaning decision, not a retrieval one
                df = pd.read_sql_query(sql, con, params=params, dtype="object")
        except (sqlite3.DatabaseError, pd.errors.DatabaseError) as exc:
            raise SqlSourceError(f"Query {sql_file.name} failed on table '{table}': {exc}") from exc
        raw_path = write_csv(df, self.raw_dir / f"{name}.csv")
        write_text(sql, self.raw_dir / f"{name}.sql")
        self.extracts.append(SqlExtract(name, len(df), list(df.columns), str(sql_file.name), str(raw_path), params))
        self.log.info("SQL extract %-22s table=%-12s rows=%5d cols=%d -> %s", name, table, len(df), len(df.columns), raw_path.name)
        if len(df) == 0:
            self.log.warning("SQL extract %s returned ZERO rows - downstream metrics will be UNKNOWN", name)
        return df

    def scalar_query(self, name: str) -> dict:
        """Run an independent check query (single-row result) and return it as a dict."""
        sql_file = self.sql_dir / f"{name}.sql"
        if not sql_file.exists():
            raise SqlSourceError(f"SQL file missing: {sql_file}")
        with self._connect() as con:
            df = pd.read_sql_query(sql_file.read_text(encoding="utf-8"), con)
        return {} if df.empty else {k: (None if pd.isna(v) else v) for k, v in df.iloc[0].to_dict().items()}

    def manifest(self) -> dict:
        return {
            "database": str(self.db_path),
            "database_sha256": self.db_sha256,
            "tables": {t: {"rows": self.row_count(t), "columns": self.table_columns(t)} for t in self.list_tables()},
            "extracts": [e.__dict__ for e in self.extracts],
        }

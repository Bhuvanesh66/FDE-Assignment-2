"""Small I/O helpers: hashing, JSON/CSV writers that never silently fail."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_default(o: Any):
    if isinstance(o, (pd.Timestamp,)):
        return None if pd.isna(o) else o.isoformat()
    if isinstance(o, (pd.Timedelta,)):
        return None if pd.isna(o) else o.total_seconds()
    if isinstance(o, Path):
        return str(o)
    if hasattr(o, "item"):           # numpy scalars
        v = o.item()
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return v
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if isinstance(o, set):
        return sorted(o)
    return str(o)


def write_json(obj: Any, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=_json_default, ensure_ascii=False)
    return path


def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_csv(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def write_text(text: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def df_to_markdown(df: pd.DataFrame, floatfmt: str = "{:,.2f}", max_rows: int | None = None) -> str:
    """Dependency-free markdown table renderer (tabulate is not required)."""
    if df is None or len(df.columns) == 0:
        return "_(empty)_"
    d = df if max_rows is None else df.head(max_rows)
    cols = [str(c) for c in d.columns]

    def fmt(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return ""
        if isinstance(v, bool):
            return str(v)
        if hasattr(v, "item") and not isinstance(v, (str, bytes)):   # numpy scalar -> python
            v = v.item()
        if isinstance(v, float) and (math.isnan(v)):
            return ""
        if isinstance(v, float):
            return floatfmt.format(v)
        if isinstance(v, pd.Timestamp):
            return v.isoformat(sep=" ", timespec="seconds")
        return str(v).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for row in d.itertuples(index=False, name=None):      # itertuples keeps each column's dtype (iterrows upcasts ints to float)
        lines.append("| " + " | ".join(fmt(v) for v in row) + " |")
    if max_rows is not None and len(df) > max_rows:
        lines.append(f"| … {len(df) - max_rows} more rows … |" + " |" * (len(cols) - 1))
    return "\n".join(lines)

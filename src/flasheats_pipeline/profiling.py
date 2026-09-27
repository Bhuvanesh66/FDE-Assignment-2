"""Profiling: understand before you clean.

For every dataset the profiler records rows, columns, inferred kind, null %,
distinct counts, top values, numeric ranges, identifier layouts, timestamp
layouts and duplicate keys.  Output is JSON (machine) + Markdown (evaluator).
Nothing here modifies data.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from .io_utils import df_to_markdown

_TS_HINT = re.compile(r"(_at$|^timestamp$|_eta$|_time$)")
_ID_HINT = re.compile(r"_id$")


def _layout(v: str) -> str:
    return re.sub(r"[A-Za-z]", "a", re.sub(r"\d", "9", v))


@dataclass
class ColumnProfile:
    column: str
    kind: str                       # id | timestamp | category | numeric | text
    non_null: int
    null_pct: float
    distinct: int
    top_values: dict = field(default_factory=dict)
    layouts: dict = field(default_factory=dict)
    numeric: dict = field(default_factory=dict)
    timestamp: dict = field(default_factory=dict)
    blank_strings: int = 0
    whitespace_padded: int = 0

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class DatasetProfile:
    name: str
    rows: int
    columns: list[str]
    key: str | None
    duplicate_key_rows: int
    exact_duplicate_rows: int
    column_profiles: list[ColumnProfile]
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d["column_profiles"] = [c.as_dict() for c in self.column_profiles]
        return d


def _kind(col: str, s: pd.Series) -> str:
    if _ID_HINT.search(col):
        return "id"
    if _TS_HINT.search(col):
        return "timestamp"
    num = pd.to_numeric(s.dropna(), errors="coerce")
    if len(num) and num.notna().mean() > 0.95:
        return "numeric"
    nn = s.dropna()
    if len(nn) and nn.nunique() <= max(12, int(0.02 * len(nn))):
        return "category"
    return "text"


def profile_column(col: str, s: pd.Series) -> ColumnProfile:
    s_obj = s.astype("object")
    non_null = int(s_obj.notna().sum())
    strs = s_obj[s_obj.map(lambda v: isinstance(v, str))]
    cp = ColumnProfile(
        column=col,
        kind=_kind(col, s_obj),
        non_null=non_null,
        null_pct=round(100.0 * (1 - non_null / len(s_obj)), 2) if len(s_obj) else 0.0,
        distinct=int(s_obj.dropna().nunique()),
        blank_strings=int((strs.str.strip() == "").sum()) if len(strs) else 0,
        whitespace_padded=int((strs != strs.str.strip()).sum()) if len(strs) else 0,
    )
    nn = s_obj.dropna()
    if cp.kind in ("category", "id", "text"):
        cp.top_values = {str(k): int(v) for k, v in nn.astype(str).value_counts().head(12).items()}
    if cp.kind in ("id", "timestamp"):
        cp.layouts = {k: int(v) for k, v in nn.astype(str).map(_layout).value_counts().head(8).items()}
    if cp.kind == "numeric":
        num = pd.to_numeric(nn, errors="coerce")
        cp.numeric = {k: (None if pd.isna(v) else round(float(v), 4)) for k, v in num.describe().to_dict().items()}
        cp.numeric["unparseable"] = int(num.isna().sum())
    if cp.kind == "timestamp":
        try:
            parsed = pd.to_datetime(nn.astype(str), format="mixed", errors="coerce")
        except ValueError:            # mixed tz-aware / naive values - profile in UTC, cleaning handles the real parse
            parsed = pd.to_datetime(nn.astype(str), format="mixed", errors="coerce", utc=True).dt.tz_localize(None)
        cp.timestamp = {
            "parsed": int(parsed.notna().sum()),
            "unparseable": int(parsed.isna().sum()),
            "min": None if parsed.notna().sum() == 0 else parsed.min().isoformat(),
            "max": None if parsed.notna().sum() == 0 else parsed.max().isoformat(),
        }
    return cp


def profile_dataset(name: str, df: pd.DataFrame, key: str | None = None) -> DatasetProfile:
    cols = [profile_column(c, df[c]) for c in df.columns]
    dup_key = int(df[key].duplicated().sum()) if key and key in df.columns else 0
    exact = int(df.duplicated().sum()) if len(df.columns) else 0
    prof = DatasetProfile(name=name, rows=int(len(df)), columns=list(df.columns), key=key,
                          duplicate_key_rows=dup_key, exact_duplicate_rows=exact, column_profiles=cols)
    if len(df) == 0:
        prof.notes.append("EMPTY dataset")
    if dup_key:
        prof.notes.append(f"{dup_key} rows share an existing {key} (grain is not one row per {key})")
    if exact:
        prof.notes.append(f"{exact} rows are exact duplicates")
    for c in cols:
        if c.whitespace_padded:
            prof.notes.append(f"{c.column}: {c.whitespace_padded} values carry leading/trailing whitespace")
        if c.kind == "timestamp" and c.timestamp.get("unparseable"):
            prof.notes.append(f"{c.column}: {c.timestamp['unparseable']} unparseable timestamps")
        if c.kind == "numeric" and c.numeric.get("unparseable"):
            prof.notes.append(f"{c.column}: {c.numeric['unparseable']} non-numeric values")
    return prof


def profile_all(datasets: dict[str, tuple[pd.DataFrame, str | None]]) -> list[DatasetProfile]:
    return [profile_dataset(name, df, key) for name, (df, key) in datasets.items()]


def profiles_to_markdown(profiles: list[DatasetProfile]) -> str:
    out = ["# Data profile (raw, before any cleaning)", ""]
    summary = pd.DataFrame([{
        "dataset": p.name, "rows": p.rows, "columns": len(p.columns), "key": p.key or "",
        "duplicate_key_rows": p.duplicate_key_rows, "exact_duplicate_rows": p.exact_duplicate_rows,
        "notes": "; ".join(p.notes) or "-",
    } for p in profiles])
    out += [df_to_markdown(summary), ""]
    for p in profiles:
        out += [f"## {p.name}  ({p.rows} rows)", ""]
        rows = []
        for c in p.column_profiles:
            detail = ""
            if c.kind == "numeric" and c.numeric:
                detail = f"min={c.numeric.get('min')} p50={c.numeric.get('50%')} max={c.numeric.get('max')}"
            elif c.kind == "timestamp" and c.timestamp:
                detail = f"{c.timestamp.get('min')} → {c.timestamp.get('max')}; unparseable={c.timestamp.get('unparseable')}; layouts={c.layouts}"
            elif c.kind == "id":
                detail = f"layouts={c.layouts}"
            else:
                detail = ", ".join(f"{k}={v}" for k, v in list(c.top_values.items())[:8])
            rows.append({"column": c.column, "kind": c.kind, "non_null": c.non_null, "null_%": c.null_pct,
                         "distinct": c.distinct, "padded": c.whitespace_padded, "detail": detail})
        out += [df_to_markdown(pd.DataFrame(rows)), ""]
    return "\n".join(out)

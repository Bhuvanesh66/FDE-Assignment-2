"""CSV / JSON retrieval with explicit structure checks.

Every reader:
* checks the file exists and is not empty,
* preserves a byte-for-byte copy (plus SHA-256) under ``data/raw/<run>/files/``,
* reads every column as text (no silent numeric coercion),
* normalises column names (strip + lower) so ``Order_ID`` and ``order_id`` match,
* verifies required columns, reports extra ones, counts malformed rows,
* returns the frame **and** a ``FileReadResult`` describing what it saw.
"""
from __future__ import annotations

import json
import shutil
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ..io_utils import sha256_file
from ..logging_utils import get_logger


class SourceFileError(RuntimeError):
    """File missing, unreadable or not the expected type."""


class SourceSchemaError(SourceFileError):
    """Required columns/keys are absent."""


@dataclass
class FileReadResult:
    name: str
    path: str
    kind: str                              # csv | json
    rows: int = 0
    columns: list[str] = field(default_factory=list)
    sha256: str = ""
    size_bytes: int = 0
    raw_copy: str = ""
    missing_required: list[str] = field(default_factory=list)
    extra_columns: list[str] = field(default_factory=list)
    malformed_rows: int = 0
    empty: bool = False
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _preserve(path: Path, raw_dir: Path) -> tuple[Path, str, int]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / path.name
    shutil.copy2(path, dest)
    return dest, sha256_file(path), path.stat().st_size


def _check_exists(path: Path, name: str) -> None:
    if not path.exists():
        raise SourceFileError(f"[{name}] source file not found: {path}")
    if path.stat().st_size == 0:
        raise SourceFileError(f"[{name}] source file is empty (0 bytes): {path}")


def read_csv_source(path: Path, name: str, required: list[str], raw_dir: Path) -> tuple[pd.DataFrame, FileReadResult]:
    log = get_logger()
    path = Path(path)
    _check_exists(path, name)
    raw_copy, digest, size = _preserve(path, Path(raw_dir) / "files")
    res = FileReadResult(name=name, path=str(path), kind="csv", sha256=digest, size_bytes=size, raw_copy=str(raw_copy))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            df = pd.read_csv(path, dtype="str", keep_default_na=True, na_values=["", "NA", "N/A", "null", "NULL", "None"],
                             on_bad_lines="warn", encoding="utf-8-sig")
        except pd.errors.EmptyDataError:
            df = pd.DataFrame(columns=required)
            res.empty = True
            res.notes.append("file has no header/rows - treated as empty table")
        except (UnicodeDecodeError, pd.errors.ParserError) as exc:
            raise SourceFileError(f"[{name}] cannot parse CSV {path}: {exc}") from exc
    res.malformed_rows = sum(1 for w in caught if "Skipping line" in str(w.message) or "Expected" in str(w.message))

    df.columns = [str(c).strip().lower() for c in df.columns]
    # strip surrounding whitespace in every text cell - representation only, values are unchanged otherwise
    for c in df.columns:
        df[c] = df[c].map(lambda v: v.strip() if isinstance(v, str) else v)
        df[c] = df[c].mask(df[c] == "", None)

    res.rows, res.columns = int(len(df)), list(df.columns)
    res.missing_required = [c for c in required if c not in df.columns]
    res.extra_columns = [c for c in df.columns if c not in required]
    if res.missing_required:
        raise SourceSchemaError(
            f"[{name}] required columns missing: {res.missing_required}. Found: {list(df.columns)}"
        )
    if len(df) == 0:
        res.empty = True
        res.notes.append("header only - zero data rows")
    log.info("CSV  %-22s rows=%5d cols=%2d malformed=%d extra=%s sha256=%s", name, len(df), len(df.columns), res.malformed_rows, res.extra_columns or "-", digest[:12])
    return df, res


def read_json_source(path: Path, name: str, raw_dir: Path) -> tuple[Any, FileReadResult]:
    log = get_logger()
    path = Path(path)
    _check_exists(path, name)
    raw_copy, digest, size = _preserve(path, Path(raw_dir) / "files")
    res = FileReadResult(name=name, path=str(path), kind="json", sha256=digest, size_bytes=size, raw_copy=str(raw_copy))
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            obj = json.load(f)
    except json.JSONDecodeError as exc:
        raise SourceFileError(f"[{name}] invalid JSON in {path}: {exc}") from exc
    res.rows = len(obj) if isinstance(obj, (list, dict)) else 0
    res.empty = res.rows == 0
    log.info("JSON %-22s top-level=%s items=%d sha256=%s", name, type(obj).__name__, res.rows, digest[:12])
    return obj, res


# --------------------------------------------------------------------------- driver events
DRIVER_EVENT_COLUMNS = ["driver_id", "order_id", "type", "timestamp", "lat", "lon"]


def flatten_driver_events(obj: Any, result: FileReadResult | None = None) -> pd.DataFrame:
    """Flatten the nested ``[{driver_id, events:[{order_id,type,timestamp,lat,lon}]}]`` layout.

    Tolerates: a flat list of event dicts (already flattened), events without
    ``lat``/``lon``, drivers with no ``events`` key, and unexpected extra keys.
    Structural problems are counted into ``result.notes`` instead of raising.
    """
    rows: list[dict] = []
    bad_drivers = bad_events = 0
    if isinstance(obj, dict) and "events" in obj and isinstance(obj["events"], list):
        obj = [obj]
    if not isinstance(obj, list):
        raise SourceSchemaError(f"driver_events: expected a JSON list, got {type(obj).__name__}")
    for item in obj:
        if not isinstance(item, dict):
            bad_drivers += 1
            continue
        if "events" in item:                      # nested layout
            driver_id = item.get("driver_id")
            events = item.get("events")
            if not isinstance(events, list):
                bad_drivers += 1
                continue
            for ev in events:
                if not isinstance(ev, dict):
                    bad_events += 1
                    continue
                rows.append({"driver_id": driver_id, **ev})
        elif "order_id" in item or "type" in item:    # already-flat event layout
            rows.append(dict(item))
        else:                                     # a driver object without events - nothing to flatten
            bad_drivers += 1
    df = pd.DataFrame(rows)
    for c in DRIVER_EVENT_COLUMNS:
        if c not in df.columns:
            df[c] = None
    extra = [c for c in df.columns if c not in DRIVER_EVENT_COLUMNS]
    df = df[DRIVER_EVENT_COLUMNS + extra]
    for c in ["driver_id", "order_id", "type", "timestamp"]:
        df[c] = df[c].map(lambda v: v.strip() if isinstance(v, str) else v).astype("object")
    if result is not None:
        result.rows = int(len(df))
        result.columns = list(df.columns)
        result.extra_columns = extra
        if bad_drivers:
            result.notes.append(f"{bad_drivers} driver objects skipped (not a dict / events not a list)")
        if bad_events:
            result.notes.append(f"{bad_events} event entries skipped (not a dict)")
        if len(df) == 0:
            result.empty = True
    return df

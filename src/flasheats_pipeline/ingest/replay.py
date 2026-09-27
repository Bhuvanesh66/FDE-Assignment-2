"""Rebuild a run from its preserved raw inputs (``data/raw/<run_id>/``) - no client system is touched.

The assignment asks for "a runnable pipeline/script that reproduces the final output from
raw inputs". ``--replay <run_id>`` does exactly that: every preserved artefact is first
checked against the SHA-256 recorded when it was retrieved. A single changed byte stops the
run (``ReplayIntegrityError``) - evidence that has been edited is not evidence.
"""
from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath

import pandas as pd

from ..io_utils import read_json, sha256_file
from .api_source import IngestionReport


class ReplayIntegrityError(RuntimeError):
    """Preserved raw inputs are missing or no longer match the hashes recorded at retrieval."""


def load_preserved_manifest(raw_root: Path, run_id: str) -> tuple[Path, dict]:
    run_dir = Path(raw_root) / run_id
    mpath = run_dir / "ingestion_manifest.json"
    if not mpath.exists():
        raise ReplayIntegrityError(f"no preserved run '{run_id}' (missing {mpath})")
    return run_dir, read_json(mpath)


def preserved_artifacts(run_dir: Path, manifest: dict) -> list[dict]:
    """Every preserved artefact with the hash recorded at retrieval time (paths are rebuilt relative to run_dir)."""
    items = []
    for e in (manifest.get("sql") or {}).get("extracts", []):
        items.append({"artifact": f"sql/{e['name']}.csv", "path": run_dir / "sql" / f"{e['name']}.csv", "expected": e.get("sha256")})
    for name, f in (manifest.get("files") or {}).items():
        if f.get("status") == "ok" and f.get("raw_copy"):
            # PureWindowsPath splits on both "\" and "/": a run preserved on Windows must replay on Linux (CI)
            fn = PureWindowsPath(f["raw_copy"]).name
            items.append({"artifact": f"files/{fn}", "path": run_dir / "files" / fn, "expected": f.get("sha256")})
    for page, digest in ((manifest.get("dispatch_api") or {}).get("raw_page_sha256") or {}).items():
        items.append({"artifact": f"api/{page}", "path": run_dir / "api" / page, "expected": digest})
    wx = manifest.get("external_weather") or {}
    if wx.get("mode") == "live" and wx.get("raw_sha256"):
        items.append({"artifact": "external/open_meteo_archive.json", "path": run_dir / "external" / "open_meteo_archive.json", "expected": wx["raw_sha256"]})
    return items


def verify(run_dir: Path, manifest: dict) -> pd.DataFrame:
    rows = []
    for it in preserved_artifacts(run_dir, manifest):
        actual = sha256_file(it["path"]) if it["path"].exists() else None
        status = "MISSING" if actual is None else ("NO_HASH_RECORDED" if not it["expected"] else ("OK" if actual == it["expected"] else "MODIFIED"))
        rows.append({"artifact": it["artifact"], "expected_sha256": it["expected"], "actual_sha256": actual, "status": status})
    df = pd.DataFrame(rows, columns=["artifact", "expected_sha256", "actual_sha256", "status"])
    if df.empty:
        raise ReplayIntegrityError(f"run {run_dir.name} has no preserved artefacts to replay")
    bad = df[df["status"].isin(["MISSING", "MODIFIED"])]
    if len(bad):
        raise ReplayIntegrityError(f"preserved raw inputs of {run_dir.name} failed verification: " +
                                   "; ".join(f"{r.artifact}={r.status}" for r in bad.itertuples()))
    return df


def read_sql_extract(run_dir: Path, name: str) -> pd.DataFrame:
    p = run_dir / "sql" / f"{name}.csv"
    if not p.exists():
        raise ReplayIntegrityError(f"preserved SQL extract missing: {p}")
    df = pd.read_csv(p, dtype="str", keep_default_na=True)
    return df.astype("object").where(df.notna(), None)


def read_api_pages(run_dir: Path, manifest: dict) -> tuple[list[dict], IngestionReport]:
    pages = sorted((run_dir / "api").glob("dispatch_page_*.json"))
    records: list[dict] = []
    for p in pages:
        with open(p, "r", encoding="utf-8") as f:
            records.extend(r for r in json.load(f).get("payload", {}).get("data", []) if isinstance(r, dict))
    orig = manifest.get("dispatch_api") or {}
    rep = IngestionReport(mode="replay", base_url=str(run_dir / "api"), pages_fetched=len(pages), records_fetched=len(records),
                          unique_order_ids=len({r.get("order_id") for r in records}), expected_total=orig.get("expected_total"),
                          raw_pages=[str(p) for p in pages], raw_page_sha256=dict(orig.get("raw_page_sha256") or {}))
    rep.complete = bool(records) and rep.unique_order_ids == len(records) and (rep.expected_total in (None, len(records)))
    rep.issues.append(f"replayed from preserved pages of {run_dir.name} (hashes verified)")
    if not rep.complete:
        rep.issues.append(f"preserved pages hold {len(records)} records, original run expected {rep.expected_total}")
    return records, rep

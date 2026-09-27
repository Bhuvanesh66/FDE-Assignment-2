"""Completeness proof against control totals, and period scoping for partitioned (weekly) runs.

Control totals: the client pack publishes ``manifest.json`` with record counts per system. Retrieval is
only called complete when what we pulled equals what the owner says exists (plus the Dispatch API's own
``total_records`` and a server-side ``COUNT(*)`` for the SQL window). A mismatch refuses publication.

Period scoping: a weekly run keeps the orders created in the window, plus every child record that
belongs to those orders. Child records of *other* periods' orders are set aside and counted
("out_of_period"), so the record ledger still balances. Child records whose order exists nowhere are
kept, so the identifier rules still flag them.
"""
from __future__ import annotations

import pandas as pd

from .cleaning import CleaningReport
from .config import PipelineConfig
from .logging_utils import get_logger

# dataset -> timestamp column used when the order id is missing
CHILD_TIME = {"tickets": "created_at", "restaurant_status": "last_updated_at", "app_actions": "action_at",
              "interventions": "intervention_at", "driver_events": "timestamp", "dispatch": "assigned_at"}


def control_totals(cfg: PipelineConfig, observed: dict[str, int | None]) -> tuple[pd.DataFrame, str]:
    """Compare observed counts with the client's published control totals (source_systems/manifest.json)."""
    path = cfg.source_root / "manifest.json"
    if not path.exists():
        return pd.DataFrame(columns=["control", "published", "observed", "status"]), "UNKNOWN"
    import json
    published = (json.loads(path.read_text(encoding="utf-8")) or {}).get("record_counts", {})
    rows = []
    for key, val in published.items():
        obs = observed.get(key)
        rows.append({"control": key, "published": val, "observed": obs,
                     "status": "UNKNOWN" if obs is None else ("MATCH" if int(obs) == int(val) else "MISMATCH")})
    df = pd.DataFrame(rows)
    if df.empty:
        return df, "UNKNOWN"
    status = "FAIL" if (df["status"] == "MISMATCH").any() else ("PASS" if (df["status"] == "MATCH").all() else "WARN")
    return df, status


def _norm_ids(s: pd.Series) -> pd.Series:
    return s.map(lambda v: v.strip().upper() if isinstance(v, str) else v)


def scope_to_period(clean: dict[str, pd.DataFrame], rep: CleaningReport, cfg: PipelineConfig, all_order_ids: set[str]) -> dict[str, pd.DataFrame]:
    win = cfg.period_window
    if win is None:
        return clean
    start, end = win
    log = get_logger()
    o = clean.get("orders")
    if o is None or "created_at" not in o.columns:
        return clean
    in_win = o["created_at"].ge(start) & o["created_at"].lt(end)
    rep.add("orders", "created_at", "out_of_period (order created outside the run window)", int((~in_win).sum()),
            f"window {cfg.period_start} .. {cfg.period_end}")
    clean["orders"] = o[in_win].reset_index(drop=True)
    window_ids = set(clean["orders"]["order_id"].dropna())
    for ds, tcol in CHILD_TIME.items():
        d = clean.get(ds)
        if d is None or "order_id" not in d.columns or len(d) == 0:
            continue
        ids = d["order_id"]
        keep = ids.isin(window_ids) | (ids.notna() & ~ids.isin(all_order_ids))
        if tcol in d.columns:
            keep = keep | (ids.isna() & d[tcol].ge(start) & d[tcol].lt(end))
        dropped = int((~keep).sum())
        rep.add(ds, "order_id", "out_of_period (record of another period's order)", dropped)
        clean[ds] = d[keep].reset_index(drop=True)
    for k, v in clean.items():
        rep.clean_row_counts[k] = int(len(v))
    log.info("period scope %s..%s: %d orders in window", cfg.period_start, cfg.period_end, len(window_ids))
    return clean


def scope_reference(ref: pd.DataFrame | None, clean: dict[str, pd.DataFrame], cfg: PipelineConfig) -> pd.DataFrame | None:
    if ref is None or cfg.period_window is None or "order_id" not in ref.columns:
        return ref
    ids = set(clean["orders"]["order_id"].dropna())
    return ref[_norm_ids(ref["order_id"]).isin(ids)].reset_index(drop=True)

"""Standardisation and cleaning - representation fixes only, everything logged.

Principles (Class 6):
* ``"Delivered"`` vs ``"delivered"`` is *representation* -> safe to normalise.
* ``"handoff"`` vs ``"handed_off"`` or ``"ETA issue"`` vs ``"eta_changed"`` is
  *semantics* -> NOT merged; kept, flagged, and listed for owner confirmation.
* duplicates are removed only when they are exact copies; conflicting copies of
  a business key keep the first row and the conflict is recorded.
* nothing is dropped from the data set - records that cannot be used are moved
  to a quarantine table with the reason, so the KPI population is explicit.

Every action is appended to a ``CleaningReport`` that becomes part of the
data-quality report.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from .config import PipelineConfig
from .logging_utils import get_logger
from .timestamps import parse_timestamps

# canonical vocabularies (what the business says these fields may contain)
VOCAB: dict[tuple[str, str], set[str]] = {
    ("orders", "final_status"): {"delivered", "cancelled"},
    ("orders", "traffic_bucket"): {"low", "medium", "high", "severe"},
    ("orders", "weather_bucket"): {"clear", "rain", "heavy_rain"},
    ("restaurant_status", "status"): {"preparing", "ready", "handed_off", "unknown"},
    ("tickets", "category"): {"late_delivery", "eta_changed", "restaurant_delay", "ready_but_waiting", "status_mismatch", "driver_not_moving"},
    ("app_actions", "action_type"): {"ETA_VIEWED", "SUPPORT_OPENED", "CANCEL_ATTEMPTED"},
    ("interventions", "intervention_type"): {"DRIVER_REASSIGNMENT", "RESTAURANT_CONTACT", "PRIORITY_DISPATCH", "CUSTOMER_CREDIT"},
    ("interventions", "initiated_by"): {"support", "dispatch", "operations"},
    ("dispatch", "dispatch_status"): {"completed", "cancelled"},
    ("driver_events", "type"): {"assigned", "gps_ping", "picked_up", "delivered"},
    ("drivers", "vehicle_type"): {"bike", "scooter", "ebike"},
}
# columns whose canonical form is UPPER_SNAKE instead of lower_snake
UPPER_VOCAB = {("app_actions", "action_type"), ("interventions", "intervention_type")}

# semantic look-alikes that we deliberately do NOT merge automatically
SEMANTIC_CANDIDATES = {
    ("restaurant_status", "status"): {"handoff": "handed_off"},
    ("tickets", "category"): {"eta_issue": "eta_changed"},
}

ID_COLUMNS = {
    "orders": ["order_id", "customer_id", "restaurant_id", "driver_id"],
    "customers": ["customer_id"], "drivers": ["driver_id"], "restaurants": ["restaurant_id"],
    "tickets": ["ticket_id", "order_id"], "restaurant_status": ["order_id", "restaurant_id"],
    "app_actions": ["action_id", "order_id", "customer_id"], "interventions": ["intervention_id", "order_id"],
    "dispatch": ["order_id", "driver_id", "original_driver_id"], "driver_events": ["driver_id", "order_id"],
}
TS_COLUMNS = {
    "orders": ["created_at", "promised_eta", "pickup_at", "actual_delivery_at"],
    "tickets": ["created_at"], "restaurant_status": ["last_updated_at"], "app_actions": ["action_at"],
    "interventions": ["intervention_at"], "dispatch": ["assigned_at", "reassigned_at", "estimated_pickup_at", "current_delivery_eta"],
    "driver_events": ["timestamp"],
}
NUM_COLUMNS = {
    "orders": ["distance_km_estimate"], "customers": ["lat", "lon"], "restaurants": ["lat", "lon", "manual_status_updates"],
    "drivers": ["rating", "experience_months"], "driver_events": ["lat", "lon"],
}
BUSINESS_KEYS = {
    "orders": "order_id", "customers": "customer_id", "drivers": "driver_id", "restaurants": "restaurant_id",
    "tickets": "ticket_id", "app_actions": "action_id", "interventions": "intervention_id", "dispatch": "order_id",
}
_ID_LAYOUT = re.compile(r"^[A-Z]{1,4}-?\d{3,6}$")


@dataclass
class CleaningAction:
    dataset: str
    column: str
    action: str
    count: int
    detail: str = ""


@dataclass
class CleaningReport:
    actions: list[CleaningAction] = field(default_factory=list)
    timestamp_stats: list[dict] = field(default_factory=list)
    unexpected_categories: dict[str, dict[str, int]] = field(default_factory=dict)   # "dataset.column" -> {value: n}
    semantic_candidates: dict[str, dict[str, str]] = field(default_factory=dict)      # "dataset.column" -> {value: candidate}
    quarantine: dict[str, pd.DataFrame] = field(default_factory=dict)
    duplicate_conflicts: dict[str, pd.DataFrame] = field(default_factory=dict)
    raw_row_counts: dict[str, int] = field(default_factory=dict)
    clean_row_counts: dict[str, int] = field(default_factory=dict)

    def add(self, dataset: str, column: str, action: str, count: int, detail: str = "") -> None:
        if count:
            self.actions.append(CleaningAction(dataset, column, action, int(count), detail))

    def actions_frame(self) -> pd.DataFrame:
        return pd.DataFrame([a.__dict__ for a in self.actions]) if self.actions else pd.DataFrame(columns=["dataset", "column", "action", "count", "detail"])

    def as_dict(self) -> dict:
        return {
            "actions": [a.__dict__ for a in self.actions],
            "timestamp_stats": self.timestamp_stats,
            "unexpected_categories": self.unexpected_categories,
            "semantic_candidates": self.semantic_candidates,
            "quarantine_counts": {k: int(len(v)) for k, v in self.quarantine.items()},
            "duplicate_conflict_counts": {k: int(len(v)) for k, v in self.duplicate_conflicts.items()},
            "raw_row_counts": self.raw_row_counts,
            "clean_row_counts": self.clean_row_counts,
        }


# --------------------------------------------------------------------------- helpers
def _norm_text(v):
    if not isinstance(v, str):
        return v
    v = v.strip()
    return v if v else None


def normalise_ids(df: pd.DataFrame, dataset: str, rep: CleaningReport) -> pd.DataFrame:
    for c in ID_COLUMNS.get(dataset, []):
        if c not in df.columns:
            continue
        before = df[c].astype("object")
        after = before.map(lambda v: v.strip().upper() if isinstance(v, str) else v)
        after = after.map(lambda v: None if (isinstance(v, str) and v == "") else v)
        changed = int(((before != after) & before.notna()).sum())
        rep.add(dataset, c, "normalise_id (trim + upper-case)", changed)
        df[c] = after.astype("object")
    return df


def normalise_category(df: pd.DataFrame, dataset: str, column: str, rep: CleaningReport) -> pd.DataFrame:
    if column not in df.columns:
        return df
    vocab = VOCAB.get((dataset, column))
    before = df[column].astype("object")
    upper = (dataset, column) in UPPER_VOCAB

    def canon(v):
        if not isinstance(v, str):
            return v
        t = re.sub(r"[\s\-]+", "_", v.strip())
        t = t.upper() if upper else t.lower()
        return t or None

    after = before.map(canon)
    changed = int(((before != after) & before.notna()).sum())
    rep.add(dataset, column, "normalise_category (trim, case, spaces->_)", changed,
            "; ".join(f"{a!r}->{b!r}" for a, b in sorted({(x, y) for x, y in zip(before, after) if isinstance(x, str) and x != y})[:8]))
    df[column] = after.astype("object")
    if vocab is not None:
        unexpected = after[after.notna() & ~after.isin(vocab)]
        if len(unexpected):
            rep.unexpected_categories[f"{dataset}.{column}"] = {str(k): int(v) for k, v in unexpected.value_counts().items()}
            cands = {k: v for k, v in SEMANTIC_CANDIDATES.get((dataset, column), {}).items() if k in set(unexpected)}
            if cands:
                rep.semantic_candidates[f"{dataset}.{column}"] = cands
    return df


def parse_ts_columns(df: pd.DataFrame, dataset: str, rep: CleaningReport, cfg: PipelineConfig) -> pd.DataFrame:
    for c in TS_COLUMNS.get(dataset, []):
        if c not in df.columns:
            continue
        parsed, stats = parse_timestamps(df[c], column=f"{dataset}.{c}", source_tz=cfg.source_timezone)
        df[c] = parsed
        rep.timestamp_stats.append(stats.as_dict())
        rep.add(dataset, c, "parse_timestamp: unparseable -> NaT", stats.unparseable, "; ".join(stats.unparseable_samples))
        rep.add(dataset, c, "parse_timestamp: tz-aware converted to naive source tz", stats.tz_aware_converted)
    return df


def parse_num_columns(df: pd.DataFrame, dataset: str, rep: CleaningReport) -> pd.DataFrame:
    for c in NUM_COLUMNS.get(dataset, []):
        if c not in df.columns:
            continue
        before = df[c]
        after = pd.to_numeric(before, errors="coerce")
        bad = int((before.notna() & after.isna()).sum())
        rep.add(dataset, c, "to_numeric: non-numeric -> NaN", bad, "; ".join(map(str, before[before.notna() & after.isna()].head(5))))
        df[c] = after
    return df


def dedupe(df: pd.DataFrame, dataset: str, rep: CleaningReport) -> pd.DataFrame:
    exact = int(df.duplicated().sum())
    if exact:
        df = df.drop_duplicates().copy()
        rep.add(dataset, "*", "drop_exact_duplicate_rows", exact)
    key = BUSINESS_KEYS.get(dataset)
    if key and key in df.columns:
        dup_mask = df[key].notna() & df[key].duplicated(keep=False)
        if dup_mask.any():
            conflicts = df[dup_mask].copy()
            # which columns actually differ within each key?
            diff_cols = {}
            for k, g in conflicts.groupby(key):
                diff_cols[k] = [c for c in g.columns if c != key and g[c].astype(str).nunique() > 1]
            conflicts["conflicting_columns"] = conflicts[key].map(lambda k: ";".join(diff_cols.get(k, [])))
            rep.duplicate_conflicts[dataset] = conflicts
            n_drop = int(df[key].notna().sum() - df[key].dropna().nunique())
            df = df[~(df[key].notna() & df[key].duplicated(keep="first"))].copy()
            rep.add(dataset, key, "drop_conflicting_duplicate_key_rows (keep first)", n_drop,
                    f"{len(diff_cols)} keys duplicated; differing columns: {sorted({c for v in diff_cols.values() for c in v})}")
    return df


def quarantine_missing_key(df: pd.DataFrame, dataset: str, key: str, rep: CleaningReport) -> pd.DataFrame:
    if key not in df.columns:
        return df
    bad = df[df[key].isna()]
    if len(bad):
        q = bad.copy()
        q["quarantine_reason"] = f"missing {key}"
        rep.quarantine[f"{dataset}_missing_{key}"] = q
        rep.add(dataset, key, f"quarantine rows with missing {key}", len(bad))
        df = df[df[key].notna()].copy()
    return df


# --------------------------------------------------------------------------- main entry
def standardise(raw: dict[str, pd.DataFrame], cfg: PipelineConfig) -> tuple[dict[str, pd.DataFrame], CleaningReport]:
    """Return a cleaned copy of every raw dataset plus the report of what changed."""
    log = get_logger()
    rep = CleaningReport()
    clean: dict[str, pd.DataFrame] = {}
    for name, df in raw.items():
        if df is None:
            continue
        rep.raw_row_counts[name] = int(len(df))
        d = df.copy()
        d.columns = [str(c).strip().lower() for c in d.columns]
        for c in d.columns:
            if d[c].dtype == object or str(d[c].dtype) in ("str", "string"):
                d[c] = d[c].astype("object").map(_norm_text)
        d = normalise_ids(d, name, rep)
        for (ds, col) in list(VOCAB):
            if ds == name:
                d = normalise_category(d, name, col, rep)
        d = parse_ts_columns(d, name, rep, cfg)
        d = parse_num_columns(d, name, rep)
        d = dedupe(d, name, rep)
        if name == "orders":
            d = quarantine_missing_key(d, name, "order_id", rep)
        if name in ("customers", "drivers", "restaurants"):
            d = quarantine_missing_key(d, name, BUSINESS_KEYS[name], rep)
        if name == "driver_events":
            d = quarantine_missing_key(d, name, "order_id", rep)
        d = d.reset_index(drop=True)
        rep.clean_row_counts[name] = int(len(d))
        clean[name] = d
        log.info("clean %-16s raw=%5d -> clean=%5d", name, rep.raw_row_counts[name], len(d))
    for a in rep.actions:
        log.info("  action %-16s %-22s %-55s n=%d %s", a.dataset, a.column, a.action, a.count, a.detail[:80])
    for k, v in rep.unexpected_categories.items():
        log.warning("  unexpected categories in %s: %s (retained + flagged)", k, v)
    return clean, rep

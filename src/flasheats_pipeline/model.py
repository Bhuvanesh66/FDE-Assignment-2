"""Business workflow model (Class 7).

Source systems are organised by *system*; the model re-organises them around
the **order lifecycle**:

    customer places order -> dispatch assigns driver -> restaurant prepares
    -> driver picks up -> driver delivers (or order is cancelled)
    while the customer watches the ETA / opens support and the ops team intervenes.

Entities   : customer, restaurant, driver, order, support ticket, intervention
Events     : ORDER_CREATED, DRIVER_ASSIGNED, DRIVER_REASSIGNED, RESTAURANT_STATUS_*,
             PICKED_UP, DELIVERED, APP_*, SUPPORT_TICKET, INTERVENTION_*
States     : final_status (delivered / cancelled) + outcome_bucket
Interaction: what the customer did (app actions, support tickets)
Intervention: what FlashEats did (reassignment, restaurant contact, priority dispatch, credit)
Outcome    : late_flag / delay_min / outcome_bucket

Tables produced (all at an explicit grain):
    dim_customer, dim_restaurant, dim_driver           one row per entity
    fact_order                                          one row per order (enriched with Dispatch + telemetry)
    fact_event                                          one row per lifecycle event
    fact_interaction                                    one row per customer interaction
    fact_intervention                                   one row per intervention
    order_journey                                       one row per order: interaction -> intervention -> outcome

One-to-many tables are **aggregated to order grain before joining** so the
order count can never be inflated; every merge is cardinality-checked.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import PipelineConfig
from .logging_utils import get_logger
from .rules import RuleResult, kpi_exclusions, order_flags
from .timestamps import minutes_between

DISTANCE_BINS = [0, 3, 6, 10, 20, 50]
DISTANCE_LABELS = ["0-3 km", "3-6 km", "6-10 km", "10-20 km", "20-50 km"]


@dataclass
class ModelBundle:
    tables: dict[str, pd.DataFrame]
    join_checks: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __getitem__(self, k: str) -> pd.DataFrame:
        return self.tables[k]


def _checked_merge(left: pd.DataFrame, right: pd.DataFrame, on: str, name: str, checks: list[dict], how: str = "left") -> pd.DataFrame:
    """Left-join a table that must be unique on ``on``; record the cardinality evidence."""
    dup_right = int(right[on].duplicated().sum())
    if dup_right:
        right = right.drop_duplicates(on, keep="first")
    out = left.merge(right, on=on, how=how, validate="one_to_one" if left[on].is_unique else "many_to_one")
    ok = len(out) == len(left)
    checks.append({"merge": name, "left_rows": int(len(left)), "right_rows": int(len(right)), "result_rows": int(len(out)),
                   "right_duplicates_dropped": dup_right, "matched_rows": int(out[right.columns.difference([on])[0]].notna().sum()) if len(right.columns) > 1 else None,
                   "row_count_preserved": ok})
    if not ok:  # pragma: no cover - validate= already guards this
        raise RuntimeError(f"merge {name} changed the row count {len(left)} -> {len(out)}")
    return out


def _ts(df: pd.DataFrame, col: str) -> pd.Series:
    return df[col] if col in df.columns else pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")


def _col(df: pd.DataFrame, col: str, default=None) -> pd.Series:
    return df[col] if col in df.columns else pd.Series(default, index=df.index, dtype="object")


# --------------------------------------------------------------------------- builders
def build_dimensions(clean: dict[str, pd.DataFrame], results: list[RuleResult], cfg: PipelineConfig) -> dict[str, pd.DataFrame]:
    dims = {}
    c = clean.get("customers", pd.DataFrame(columns=["customer_id", "lat", "lon"]))
    dims["dim_customer"] = c[[x for x in ["customer_id", "lat", "lon"] if x in c.columns]].drop_duplicates("customer_id").reset_index(drop=True)
    r = clean.get("restaurants", pd.DataFrame(columns=["restaurant_id"])).copy()
    bad_coords = set(next((x.violating_keys for x in results if x.rule.id == "RG-02"), []))
    r["coords_valid"] = ~r["restaurant_id"].astype(str).isin(bad_coords) if "restaurant_id" in r.columns else True
    dims["dim_restaurant"] = r.drop_duplicates("restaurant_id").reset_index(drop=True)
    d = clean.get("drivers", pd.DataFrame(columns=["driver_id"]))
    dims["dim_driver"] = d.drop_duplicates("driver_id").reset_index(drop=True)
    return dims


def build_fact_order(clean: dict[str, pd.DataFrame], results: list[RuleResult], cfg: PipelineConfig, checks: list[dict]) -> pd.DataFrame:
    o = clean["orders"].copy()
    base_cols = ["order_id", "customer_id", "restaurant_id", "driver_id", "city", "created_at", "promised_eta", "pickup_at",
                 "actual_delivery_at", "final_status", "distance_km_estimate", "traffic_bucket", "weather_bucket"]
    for c in base_cols:
        if c not in o.columns:
            o[c] = pd.NaT if c in ("created_at", "promised_eta", "pickup_at", "actual_delivery_at") else None
    f = o[base_cols].rename(columns={"driver_id": "recorded_driver_id"})

    # Dispatch enrichment (one row per order in the API) ------------------------------
    dp = clean.get("dispatch")
    if dp is not None and "order_id" in dp.columns and len(dp):
        keep = {"driver_id": "final_driver_id", "original_driver_id": "original_driver_id", "assigned_at": "assigned_at",
                "reassigned_at": "reassigned_at", "estimated_pickup_at": "estimated_pickup_at", "current_delivery_eta": "current_delivery_eta",
                "dispatch_status": "dispatch_status", "eta_model_version": "eta_model_version"}
        dpx = dp[["order_id"] + [c for c in keep if c in dp.columns]].rename(columns=keep)
        f = _checked_merge(f, dpx, "order_id", "fact_order <- dispatch", checks)
    for c in ["final_driver_id", "original_driver_id", "dispatch_status", "eta_model_version"]:
        if c not in f.columns:
            f[c] = None
    for c in ["assigned_at", "reassigned_at", "estimated_pickup_at", "current_delivery_eta"]:
        if c not in f.columns:
            f[c] = pd.NaT
    f["reassigned_flag"] = f["reassigned_at"].notna()
    f["driver_id"] = f["final_driver_id"].where(f["final_driver_id"].notna(), f["recorded_driver_id"])

    # Driver telemetry (aggregate to order grain first) ---------------------------------
    de = clean.get("driver_events")
    if de is not None and {"order_id", "type", "timestamp"} <= set(de.columns) and len(de):
        piv = de[de["type"].isin(["assigned", "picked_up", "delivered"])].groupby(["order_id", "type"])["timestamp"].min().unstack()
        piv = piv.rename(columns={"assigned": "ev_assigned_at", "picked_up": "ev_picked_up_at", "delivered": "ev_delivered_at"}).reset_index()
        pings = de[de["type"] == "gps_ping"].groupby("order_id").size().rename("gps_ping_count").reset_index()
        tele = piv.merge(pings, on="order_id", how="outer")
        f = _checked_merge(f, tele, "order_id", "fact_order <- driver_events (aggregated)", checks)
    for c in ["ev_assigned_at", "ev_picked_up_at", "ev_delivered_at"]:
        if c not in f.columns:
            f[c] = pd.NaT
    if "gps_ping_count" not in f.columns:
        f["gps_ping_count"] = 0
    f["gps_ping_count"] = f["gps_ping_count"].fillna(0).astype(int)

    # Data-quality flags and KPI population --------------------------------------------
    excl = kpi_exclusions(results)
    flags = order_flags(results)
    f["dq_flags"] = f["order_id"].map(lambda k: ";".join(flags.get(str(k), [])) or "")
    f["kpi_exclusion_reason"] = f["order_id"].map(lambda k: ";".join(excl.get(str(k), [])) or "")
    f["delivered_flag"] = (f["final_status"] == "delivered")
    f["kpi_population"] = f["delivered_flag"] & (f["kpi_exclusion_reason"] == "") & f["promised_eta"].notna() & f["actual_delivery_at"].notna()

    # Outcome ---------------------------------------------------------------------------
    f["delay_min"] = minutes_between(f["actual_delivery_at"], f["promised_eta"]).round(2)
    f["late_flag"] = np.where(f["kpi_population"], f["delay_min"] > cfg.late_threshold_min, np.nan)
    f["late_over_threshold_flag"] = np.where(f["kpi_population"], f["delay_min"] > cfg.meaningful_late_threshold_min, np.nan)
    f["late_flag"] = f["late_flag"].astype("float")
    f["late_over_threshold_flag"] = f["late_over_threshold_flag"].astype("float")

    def bucket(row):
        if row["final_status"] == "cancelled":
            return "cancelled"
        if row["final_status"] != "delivered":
            return "other_status"
        if row["kpi_population"]:
            return "delivered_late" if row["late_flag"] == 1.0 else "delivered_on_time"
        if pd.isna(row["actual_delivery_at"]) or pd.isna(row["promised_eta"]):
            return "unknown_missing_timestamp"
        return "excluded_dq_rule"
    f["outcome_bucket"] = f.apply(bucket, axis=1)

    # Sensitivity: back-fill missing delivery time from the driver 'delivered' event ----
    f["actual_delivery_at_backfilled"] = f["actual_delivery_at"].where(f["actual_delivery_at"].notna(), f["ev_delivered_at"])
    f["backfilled_from_driver_event"] = f["actual_delivery_at"].isna() & f["ev_delivered_at"].notna() & f["delivered_flag"]
    f["delay_min_backfilled"] = minutes_between(f["actual_delivery_at_backfilled"], f["promised_eta"]).round(2)

    # Stage durations (workflow) ----------------------------------------------------------
    f["dispatch_wait_min"] = minutes_between(f["assigned_at"], f["created_at"]).round(2)
    f["pickup_wait_min"] = minutes_between(f["pickup_at"], f["assigned_at"]).round(2)         # travel-to-restaurant + prep wait (not separable: no arrival event)
    f["transit_min"] = minutes_between(f["actual_delivery_at"], f["pickup_at"]).round(2)
    f["total_cycle_min"] = minutes_between(f["actual_delivery_at"], f["created_at"]).round(2)
    f["promised_window_min"] = minutes_between(f["promised_eta"], f["created_at"]).round(2)
    f["planned_pickup_min"] = minutes_between(f["estimated_pickup_at"], f["created_at"]).round(2)
    f["planned_transit_min"] = minutes_between(f["promised_eta"], f["estimated_pickup_at"]).round(2)
    f["pickup_overrun_min"] = minutes_between(f["pickup_at"], f["estimated_pickup_at"]).round(2)
    f["transit_overrun_min"] = (f["transit_min"] - f["planned_transit_min"]).round(2)
    f["eta_revision_min"] = minutes_between(f["current_delivery_eta"], f["promised_eta"]).round(2)

    # Convenience dimensions -----------------------------------------------------------------
    f["order_date"] = f["created_at"].dt.date
    f["hour_of_day"] = f["created_at"].dt.hour
    f["day_of_week"] = f["created_at"].dt.day_name()
    f["distance_band"] = pd.cut(f["distance_km_estimate"], bins=DISTANCE_BINS, labels=DISTANCE_LABELS, include_lowest=True).astype("object")
    f.loc[f["distance_km_estimate"].isna() | (f["distance_km_estimate"] <= 0) | (f["distance_km_estimate"] > cfg.max_plausible_distance_km), "distance_band"] = "invalid/unknown"
    return f.reset_index(drop=True)


def build_fact_event(clean: dict[str, pd.DataFrame], fact_order: pd.DataFrame) -> pd.DataFrame:
    parts = []

    def add(df, time_col, event_type, actor_type, actor_col, source, detail_col=None):
        if df is None or len(df) == 0 or time_col not in df.columns:
            return
        d = pd.DataFrame({
            "order_id": df["order_id"].values,
            "event_time": df[time_col].values,
            "event_type": event_type if isinstance(event_type, str) else event_type.values,
            "actor_type": actor_type,
            "actor_id": df[actor_col].values if actor_col and actor_col in df.columns else None,
            "source_system": source,
            "detail": df[detail_col].values if detail_col and detail_col in df.columns else None,
        })
        parts.append(d[d["event_time"].notna()])

    fo = fact_order
    add(fo, "created_at", "ORDER_CREATED", "customer", "customer_id", "order_platform")
    add(fo, "assigned_at", "DRIVER_ASSIGNED", "dispatch", "original_driver_id", "dispatch_api")
    add(fo[fo["reassigned_at"].notna()], "reassigned_at", "DRIVER_REASSIGNED", "dispatch", "final_driver_id", "dispatch_api")
    add(fo, "estimated_pickup_at", "PICKUP_ESTIMATED", "dispatch", "final_driver_id", "dispatch_api")
    add(fo, "pickup_at", "PICKED_UP", "driver", "driver_id", "order_platform")
    add(fo, "actual_delivery_at", "DELIVERED", "driver", "driver_id", "order_platform")
    rs = clean.get("restaurant_status")
    if rs is not None and len(rs) and {"order_id", "status", "last_updated_at"} <= set(rs.columns):
        add(rs, "last_updated_at", ("RESTAURANT_" + rs["status"].astype(str).str.upper()), "restaurant", "restaurant_id", "restaurant_status_feed", "status")
    de = clean.get("driver_events")
    if de is not None and len(de) and {"order_id", "type", "timestamp"} <= set(de.columns):
        add(de, "timestamp", ("DRIVER_APP_" + de["type"].astype(str).str.upper()), "driver", "driver_id", "driver_app")
    aa = clean.get("app_actions")
    if aa is not None and len(aa) and {"order_id", "action_type", "action_at"} <= set(aa.columns):
        add(aa, "action_at", ("APP_" + aa["action_type"].astype(str)), "customer", "customer_id", "customer_app", "channel")
    t = clean.get("tickets")
    if t is not None and len(t) and {"order_id", "created_at"} <= set(t.columns):
        tt = t[t["order_id"].notna()]
        add(tt, "created_at", "SUPPORT_TICKET", "customer", "ticket_id", "support_desk", "category")
    iv = clean.get("interventions")
    if iv is not None and len(iv) and {"order_id", "intervention_type", "intervention_at"} <= set(iv.columns):
        add(iv, "intervention_at", ("INTERVENTION_" + iv["intervention_type"].astype(str)), "system_or_agent", "initiated_by", "interventions_log", "reason")
    if not parts:
        return pd.DataFrame(columns=["order_id", "event_time", "event_type", "actor_type", "actor_id", "source_system", "detail"])
    ev = pd.concat(parts, ignore_index=True)
    ev["event_time"] = pd.to_datetime(ev["event_time"])
    return ev.sort_values(["order_id", "event_time", "event_type"]).reset_index(drop=True)


def build_fact_interaction(clean: dict[str, pd.DataFrame]) -> pd.DataFrame:
    parts = []
    aa = clean.get("app_actions")
    if aa is not None and len(aa) and {"order_id", "action_type", "action_at"} <= set(aa.columns):
        parts.append(pd.DataFrame({"interaction_id": _col(aa, "action_id"), "order_id": aa["order_id"], "customer_id": _col(aa, "customer_id"),
                                   "interaction_type": aa["action_type"], "interaction_at": aa["action_at"],
                                   "channel": _col(aa, "channel", "mobile_app"), "detail": None, "source_system": "customer_app"}))
    t = clean.get("tickets")
    if t is not None and len(t) and {"order_id", "created_at"} <= set(t.columns):
        parts.append(pd.DataFrame({"interaction_id": _col(t, "ticket_id"), "order_id": t["order_id"], "customer_id": None,
                                   "interaction_type": "SUPPORT_TICKET", "interaction_at": t["created_at"], "channel": "support",
                                   "detail": _col(t, "category"), "source_system": "support_desk"}))
    if not parts:
        return pd.DataFrame(columns=["interaction_id", "order_id", "customer_id", "interaction_type", "interaction_at", "channel", "detail", "source_system"])
    return pd.concat(parts, ignore_index=True).sort_values(["order_id", "interaction_at"]).reset_index(drop=True)


def build_fact_intervention(clean: dict[str, pd.DataFrame], fact_order: pd.DataFrame) -> pd.DataFrame:
    iv = clean.get("interventions")
    if iv is None or len(iv) == 0:
        return pd.DataFrame(columns=["intervention_id", "order_id", "intervention_type", "intervention_at", "initiated_by", "reason"])
    f = iv.copy()
    ref = fact_order[["order_id", "created_at", "promised_eta", "actual_delivery_at"]]
    f = f.merge(ref, on="order_id", how="left")
    f["minutes_after_created"] = minutes_between(f["intervention_at"], f["created_at"]).round(2)
    f["before_promised_eta"] = f["intervention_at"] < f["promised_eta"]
    f["before_delivery"] = f["intervention_at"] < f["actual_delivery_at"]
    return f.drop(columns=["created_at", "promised_eta", "actual_delivery_at"]).reset_index(drop=True)


def build_order_journey(fact_order: pd.DataFrame, fact_interaction: pd.DataFrame, fact_intervention: pd.DataFrame, checks: list[dict]) -> pd.DataFrame:
    j = fact_order[["order_id", "customer_id", "restaurant_id", "driver_id", "final_status", "kpi_population", "late_flag",
                    "late_over_threshold_flag", "delay_min", "outcome_bucket", "reassigned_flag", "dq_flags", "created_at", "promised_eta", "actual_delivery_at"]].copy()

    # customer interactions -> order grain
    fi = fact_interaction
    if len(fi):
        app = fi[fi["source_system"] == "customer_app"]
        agg_app = app.groupby("order_id").agg(
            app_action_count=("interaction_id", "size"),
            eta_view_count=("interaction_type", lambda s: int((s == "ETA_VIEWED").sum())),
            support_opened=("interaction_type", lambda s: bool((s == "SUPPORT_OPENED").any())),
            cancel_attempted=("interaction_type", lambda s: bool((s == "CANCEL_ATTEMPTED").any())),
            first_app_action_at=("interaction_at", "min"),
        ).reset_index()
        tk = fi[fi["source_system"] == "support_desk"]
        agg_tk = tk.groupby("order_id").agg(
            ticket_count=("interaction_id", "size"),
            ticket_categories=("detail", lambda s: ";".join(sorted({str(x) for x in s.dropna()}))),
            first_ticket_at=("interaction_at", "min"),
        ).reset_index()
        j = _checked_merge(j, agg_app, "order_id", "order_journey <- app_actions (aggregated)", checks)
        j = _checked_merge(j, agg_tk, "order_id", "order_journey <- tickets (aggregated)", checks)
    for c, v in [("app_action_count", 0), ("eta_view_count", 0), ("support_opened", False), ("cancel_attempted", False), ("ticket_count", 0), ("ticket_categories", "")]:
        if c not in j.columns:
            j[c] = v
        j[c] = j[c].fillna(v)
    for c in ["first_app_action_at", "first_ticket_at"]:
        if c not in j.columns:
            j[c] = pd.NaT
    j["app_action_count"] = j["app_action_count"].astype(int)
    j["eta_view_count"] = j["eta_view_count"].astype(int)
    j["ticket_count"] = j["ticket_count"].astype(int)
    j["support_opened"] = j["support_opened"].astype(bool)
    j["cancel_attempted"] = j["cancel_attempted"].astype(bool)
    j["interaction_count"] = j["app_action_count"] + j["ticket_count"]
    j["support_contact"] = j["support_opened"] | (j["ticket_count"] > 0)

    # interventions -> order grain
    fv = fact_intervention
    if len(fv):
        agg_iv = fv.groupby("order_id").agg(
            intervention_count=("intervention_id", "size"),
            intervention_types=("intervention_type", lambda s: ";".join(sorted({str(x) for x in s.dropna()}))),
            first_intervention_at=("intervention_at", "min"),
            intervention_initiated_by=("initiated_by", lambda s: ";".join(sorted({str(x) for x in s.dropna()}))),
        ).reset_index()
        j = _checked_merge(j, agg_iv, "order_id", "order_journey <- interventions (aggregated)", checks)
    for c, v in [("intervention_count", 0), ("intervention_types", ""), ("intervention_initiated_by", "")]:
        if c not in j.columns:
            j[c] = v
        j[c] = j[c].fillna(v)
    if "first_intervention_at" not in j.columns:
        j["first_intervention_at"] = pd.NaT
    j["intervention_count"] = j["intervention_count"].astype(int)
    j["has_intervention"] = j["intervention_count"] > 0
    j["intervention_before_delivery"] = j["first_intervention_at"] < j["actual_delivery_at"]
    j["frustrated_no_intervention"] = j["support_contact"] & ~j["has_intervention"]
    j["frustrated_intervened_still_late"] = j["support_contact"] & j["has_intervention"] & (j["late_flag"] == 1.0)
    return j.reset_index(drop=True)


def build_model(clean: dict[str, pd.DataFrame], results: list[RuleResult], cfg: PipelineConfig) -> ModelBundle:
    log = get_logger()
    checks: list[dict] = []
    tables = build_dimensions(clean, results, cfg)
    fo = build_fact_order(clean, results, cfg, checks)
    tables["fact_order"] = fo
    tables["fact_event"] = build_fact_event(clean, fo)
    tables["fact_interaction"] = build_fact_interaction(clean)
    tables["fact_intervention"] = build_fact_intervention(clean, fo)
    tables["order_journey"] = build_order_journey(fo, tables["fact_interaction"], tables["fact_intervention"], checks)
    bundle = ModelBundle(tables=tables, join_checks=checks)
    for name, t in tables.items():
        log.info("model %-18s rows=%6d cols=%3d", name, len(t), len(t.columns))
    for c in checks:
        log.info("join-check %-52s left=%5d right=%5d result=%5d preserved=%s", c["merge"], c["left_rows"], c["right_rows"], c["result_rows"], c["row_count_preserved"])
    if len(fo) and not fo["order_id"].is_unique:
        raise RuntimeError("fact_order is not unique on order_id - grain violated")
    if len(tables["order_journey"]) != len(fo):
        raise RuntimeError("order_journey row count differs from fact_order - aggregation error")
    bundle.notes.append("No explicit 'driver arrived at restaurant' event exists in any source: restaurant prep time and driver wait cannot be separated (pickup_wait_min mixes both).")
    bundle.notes.append("No cancellation timestamp exists: cancelled orders have no terminal event in the event log.")
    return bundle

"""Business-oriented data-quality rules (validation contract).

Each rule states, in plain language: what the business assumes, why it matters
for the late-delivery KPI, how it is detected, what the pipeline does about it
(correct / flag / reject / retain) and who owns the unresolved question.

Actions:
* ``reject``  - the record is excluded from the KPI population (never deleted;
                it stays in the fact table with ``kpi_population=False`` and a reason)
* ``flag``    - the record is kept in the KPI population but carries a dq flag
* ``retain``  - informational; nothing changes
* ``correct`` - representation already fixed by the cleaning stage; reported here

Statuses: PASS (no violations), WARN (violations, decision-safe with caveat),
FAIL (metric cannot be trusted), UNKNOWN (cannot be tested with this data).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .cleaning import VOCAB, CleaningReport
from .config import PipelineConfig
from .logging_utils import get_logger
from .timestamps import minutes_between


@dataclass
class Rule:
    id: str
    name: str
    dataset: str
    business_reason: str
    detection: str
    action: str                         # reject | flag | retain | correct
    owner: str = "Data Team"
    warn_status: str = "WARN"           # status when violations exist
    fail_pct: float | None = None       # violation share above which status becomes FAIL


@dataclass
class RuleResult:
    rule: Rule
    violations: int
    population: int
    status: str
    detail: str = ""
    sample_keys: list = field(default_factory=list)
    violating_keys: list = field(default_factory=list)   # order ids / record keys used to flag the model
    extra: dict = field(default_factory=dict)

    @property
    def pct(self) -> float:
        return round(100.0 * self.violations / self.population, 2) if self.population else 0.0

    def as_dict(self) -> dict:
        return {
            "rule_id": self.rule.id, "rule": self.rule.name, "dataset": self.rule.dataset, "action": self.rule.action,
            "owner": self.rule.owner, "status": self.status, "violations": self.violations, "population": self.population,
            "violation_pct": self.pct, "business_reason": self.rule.business_reason, "detection": self.rule.detection,
            "detail": self.detail, "sample_keys": self.sample_keys[:10], "extra": self.extra,
        }


def _status(rule: Rule, violations: int, population: int) -> str:
    if population == 0:
        return "UNKNOWN"
    if violations == 0:
        return "PASS"
    if rule.fail_pct is not None and 100.0 * violations / population > rule.fail_pct:
        return "FAIL"
    return rule.warn_status


def _result(rule: Rule, mask: pd.Series, keys: pd.Series, detail: str = "", extra: dict | None = None) -> RuleResult:
    mask = mask.fillna(False).astype(bool)
    viol = keys[mask].dropna().astype(str).tolist()
    return RuleResult(rule, int(mask.sum()), int(len(mask)), _status(rule, int(mask.sum()), int(len(mask))),
                      detail=detail, sample_keys=sorted(set(viol))[:10], violating_keys=viol, extra=extra or {})


def _empty_result(rule: Rule, detail: str) -> RuleResult:
    return RuleResult(rule, 0, 0, "UNKNOWN", detail=detail)


# --------------------------------------------------------------------------- rule catalogue
R = {
    "GR-01": Rule("GR-01", "One row per business order", "orders",
                  "Every KPI denominator counts orders; a repeated order would count twice.",
                  "order_id duplicated after cleaning (raw duplicates reported by the cleaning stage)", "correct", "Data Team", fail_pct=0.0),
    "ID-01": Rule("ID-01", "order_id present and well-formed", "orders",
                  "An order without an identifier cannot be joined to any other system.",
                  "null order_id (quarantined) or layout not matching the O##### pattern", "flag"),
    "ID-02": Rule("ID-02", "orders.customer_id maps to a known customer", "orders",
                  "Customer-level metrics and app-interaction joins need a real customer.", "customer_id not in customers", "flag", "Data Team"),
    "ID-03": Rule("ID-03", "orders.restaurant_id maps to a known restaurant", "orders",
                  "Restaurant attribution of delay is impossible for an unknown restaurant.", "restaurant_id null or not in restaurants", "flag", "Restaurant Ops"),
    "ID-04": Rule("ID-04", "orders.driver_id maps to a known driver", "orders",
                  "Driver attribution and telemetry joins need a real driver.", "driver_id null or not in drivers", "flag", "Fleet Ops"),
    "ID-05": Rule("ID-05", "tickets.order_id maps to an order", "tickets",
                  "A complaint that cannot be tied to an order cannot be reconciled with the operational story.", "order_id null or not in orders", "flag", "Support Lead"),
    "ID-06": Rule("ID-06", "restaurant_status rows map to an order and agree on the restaurant", "restaurant_status",
                  "Status events for a foreign order (another platform?) would corrupt restaurant metrics.", "order_id not in orders OR restaurant_id differs from the order's restaurant", "flag", "Restaurant Ops"),
    "ID-07": Rule("ID-07", "app actions map to an order and its customer", "app_actions",
                  "Customer interaction counts must belong to the right order.", "order_id not in orders OR customer_id differs from the order's customer", "flag", "Product / App"),
    "ID-08": Rule("ID-08", "interventions map to an order", "interventions",
                  "An intervention without an order cannot be linked to an outcome.", "order_id not in orders", "flag", "Support Lead"),
    "ID-09": Rule("ID-09", "orders and Dispatch cover each other", "orders",
                  "Assignment/reassignment context comes only from Dispatch; missing coverage hides reassignments.", "order missing in dispatch, or dispatch record whose order is unknown", "flag", "Dispatch"),
    "ID-10": Rule("ID-10", "driver events map to an order", "driver_events",
                  "Telemetry for unknown orders cannot be used for pickup/delivery inference.", "order_id not in orders", "flag", "Fleet Ops"),
    "ST-01": Rule("ST-01", "final_status uses an agreed vocabulary", "orders",
                  "The KPI counts 'delivered' orders only; a new status ('suspended', 'Delivered') would silently leave the population.",
                  "value not in {delivered, cancelled} after representation normalisation", "flag", "VP Operations", fail_pct=10.0),
    "ST-02": Rule("ST-02", "traffic_bucket uses an agreed vocabulary", "orders", "Traffic breakdowns need consistent buckets.", "value not in {low, medium, high, severe}", "flag", "Operations"),
    "ST-03": Rule("ST-03", "weather_bucket uses an agreed vocabulary", "orders", "Weather breakdowns need consistent buckets.", "value not in {clear, rain, heavy_rain}", "flag", "Operations"),
    "ST-04": Rule("ST-04", "restaurant status uses an agreed vocabulary", "restaurant_status", "'handoff' vs 'handed_off' may be two systems or two meanings.", "value not in {preparing, ready, handed_off, unknown}", "flag", "Restaurant Ops"),
    "ST-05": Rule("ST-05", "ticket category uses an agreed vocabulary", "tickets", "Complaint mix by category drives the customer-view comparison.", "value not in the six support categories", "flag", "Support Lead"),
    "ST-06": Rule("ST-06", "app action_type uses an agreed vocabulary", "app_actions", "support_opened / cancel_attempted flags depend on it.", "value not in {ETA_VIEWED, SUPPORT_OPENED, CANCEL_ATTEMPTED}", "flag", "Product / App"),
    "ST-07": Rule("ST-07", "intervention_type uses an agreed vocabulary", "interventions", "Intervention metrics are grouped by type.", "value not in the four intervention types", "flag", "Support Lead"),
    "ST-08": Rule("ST-08", "dispatch_status uses an agreed vocabulary", "dispatch", "Cross-check of order status against Dispatch.", "value not in {completed, cancelled}", "flag", "Dispatch"),
    "ST-09": Rule("ST-09", "driver event type uses an agreed vocabulary", "driver_events", "Lifecycle reconstruction relies on assigned/picked_up/delivered.", "value not in {assigned, gps_ping, picked_up, delivered}", "flag", "Fleet Ops"),
    "TS-00": Rule("TS-00", "KPI timestamps are parseable", "orders",
                  "Unparseable promised_eta / actual_delivery_at silently shrink the KPI population.", "value present but not parseable as a datetime", "reject", "Data Team", fail_pct=10.0),
    "TS-01": Rule("TS-01", "Promised ETA is after order creation", "orders",
                  "A promise made before the order exists is not a promise; lateness against it is meaningless.", "promised_eta < created_at", "reject", "Product / ETA service"),
    "TS-02": Rule("TS-02", "Delivery happens after pickup", "orders",
                  "A delivery timestamp earlier than pickup means one of the two clocks is wrong.", "actual_delivery_at < pickup_at", "reject", "Fleet Ops"),
    "TS-03": Rule("TS-03", "Pickup happens after order creation", "orders", "Stage durations would be negative.", "pickup_at < created_at", "reject", "Fleet Ops"),
    "TS-04": Rule("TS-04", "Delivered orders carry an actual delivery time", "orders",
                  "Without actual_delivery_at the order's lateness is unknown; excluding it biases the rate if the missing ones are not random.",
                  "final_status == delivered and actual_delivery_at is null", "reject", "Data Team / Fleet Ops", fail_pct=15.0),
    "TS-05": Rule("TS-05", "Cancelled orders carry no delivery time", "orders", "A cancelled order with a delivery time is a status bug.", "final_status == cancelled and actual_delivery_at not null", "flag", "Data Team"),
    "TS-06": Rule("TS-06", "Dispatch chronology (created <= assigned <= reassigned)", "dispatch", "Assignment timing feeds the dispatch-wait stage.", "assigned_at < created_at OR reassigned_at < assigned_at", "flag", "Dispatch"),
    "TS-07": Rule("TS-07", "Driver-event chronology (assigned <= picked_up <= delivered)", "driver_events", "Telemetry used to recover missing delivery times must be internally consistent.", "picked_up < assigned OR delivered < picked_up per order", "flag", "Fleet Ops"),
    "RG-01": Rule("RG-01", "Delivery distance is plausible", "orders", "A 999 km 'estimate' would distort any distance analysis.", "distance <= 0 or > max_plausible_distance_km or null", "flag", "Operations"),
    "RG-02": Rule("RG-02", "Restaurant coordinates are inside the service area", "restaurants", "Geo-based prep/travel inference is impossible with lat=95.", "lat/lon outside the Bengaluru bounding box", "flag", "Restaurant Ops"),
    "RG-03": Rule("RG-03", "GPS pings are inside the service area", "driver_events", "Outlier pings would corrupt any route/arrival inference.", "lat/lon outside the Bengaluru bounding box", "flag", "Fleet Ops"),
    "RG-04": Rule("RG-04", "Driver attributes in range", "drivers", "Sanity of the driver dimension.", "rating outside 0-5 or experience_months < 0", "flag", "Fleet Ops"),
    "CX-01": Rule("CX-01", "orders.driver_id agrees with Dispatch's final driver", "orders",
                  "If the orders table keeps the ORIGINAL driver after a reassignment, driver-level metrics blame the wrong person.",
                  "orders.driver_id != dispatch.driver_id", "retain", "Dispatch / Data Team"),
    "CX-02": Rule("CX-02", "orders.pickup_at agrees with the driver picked_up event", "orders", "Two systems, one fact - they should agree.", "abs difference > 60 s", "retain", "Fleet Ops"),
    "CX-03": Rule("CX-03", "Intervention log agrees with Dispatch reassignments", "interventions",
                  "If DRIVER_REASSIGNMENT interventions do not appear in Dispatch (or vice versa), one log is incomplete.",
                  "orders with a DRIVER_REASSIGNMENT intervention vs orders with dispatch.reassigned_at", "retain", "Support Lead / Dispatch"),
    "FR-01": Rule("FR-01", "Restaurant status updates are fresh enough for the intended use", "restaurant_status",
                  "'ready' recorded after the driver already picked up is useless for live ETA and unfair for restaurant accountability.",
                  "status in {ready, handed_off} with last_updated_at later than the order's pickup_at (+ SLA)", "flag", "Restaurant Ops"),
    "KPI-01": Rule("KPI-01", "'Late' has one agreed definition and owner", "orders",
                   "Four stakeholders define late differently; publishing one number without an owner invites disputes.",
                   "client_metric_definitions.json lists conflicting definitions and no canonical owner", "retain", "VP Operations (proposed)"),
}


# --------------------------------------------------------------------------- engine
def run_rules(clean: dict[str, pd.DataFrame], rep: CleaningReport, cfg: PipelineConfig, metric_definitions: dict | None = None) -> list[RuleResult]:
    log = get_logger()
    res: list[RuleResult] = []
    o = clean.get("orders", pd.DataFrame())
    oid = o["order_id"] if "order_id" in o.columns else pd.Series([], dtype="object")
    order_ids = set(oid.dropna())

    # GR-01
    raw_dups = sum(a.count for a in rep.actions if a.dataset == "orders" and "duplicate" in a.action)
    r = _result(R["GR-01"], oid.duplicated(keep=False), oid, detail=f"raw duplicate rows removed by cleaning: {raw_dups}")
    if raw_dups and r.status == "PASS":
        r.status, r.detail = "WARN", r.detail + " (corrected; conflicting copies kept in quarantine)"
    res.append(r)

    # ID-01
    q_missing = len(rep.quarantine.get("orders_missing_order_id", []))
    bad_layout = ~oid.astype(str).str.match(r"^O\d{5}$") & oid.notna()
    r = _result(R["ID-01"], bad_layout, oid, detail=f"{q_missing} rows quarantined for null order_id; {int(bad_layout.sum())} ids with a different layout (kept)")
    if q_missing and r.status == "PASS":
        r.status = "WARN"
    res.append(r)

    # ID-02..04 dimension coverage
    for rid, col, dim in [("ID-02", "customer_id", "customers"), ("ID-03", "restaurant_id", "restaurants"), ("ID-04", "driver_id", "drivers")]:
        d = clean.get(dim)
        if col not in o.columns or d is None or col not in d.columns:
            res.append(_empty_result(R[rid], f"{col} or {dim} not available"))
            continue
        known = set(d[col].dropna())
        mask = o[col].isna() | ~o[col].isin(known)
        res.append(_result(R[rid], mask, oid, detail=f"null={int(o[col].isna().sum())}, unknown={int((o[col].notna() & ~o[col].isin(known)).sum())}",
                           extra={"coverage_pct": round(100.0 * (1 - mask.mean()), 2) if len(o) else None}))

    # ID-05 tickets
    t = clean.get("tickets")
    if t is not None and "order_id" in t.columns:
        mask = t["order_id"].isna() | ~t["order_id"].isin(order_ids)
        res.append(_result(R["ID-05"], mask, t["ticket_id"] if "ticket_id" in t.columns else t["order_id"],
                           detail=f"null={int(t['order_id'].isna().sum())}, unknown={int((t['order_id'].notna() & ~t['order_id'].isin(order_ids)).sum())}",
                           extra={"coverage_pct": round(100.0 * (1 - mask.mean()), 2) if len(t) else None}))
    else:
        res.append(_empty_result(R["ID-05"], "tickets not available"))

    # ID-06 restaurant_status
    rs = clean.get("restaurant_status")
    if rs is not None and "order_id" in rs.columns and "restaurant_id" in o.columns:
        m = rs.merge(o[["order_id", "restaurant_id"]].rename(columns={"restaurant_id": "order_restaurant_id"}), on="order_id", how="left")
        unknown = ~m["order_id"].isin(order_ids)
        mismatch = m["order_id"].isin(order_ids) & m["restaurant_id"].notna() & m["order_restaurant_id"].notna() & (m["restaurant_id"] != m["order_restaurant_id"])
        res.append(_result(R["ID-06"], unknown | mismatch, m["order_id"], detail=f"unknown order={int(unknown.sum())}, restaurant mismatch={int(mismatch.sum())}",
                           extra={"coverage_pct": round(100.0 * (1 - unknown.mean()), 2) if len(m) else None}))
    else:
        res.append(_empty_result(R["ID-06"], "restaurant_status not available"))

    # ID-07 app actions
    aa = clean.get("app_actions")
    if aa is not None and "order_id" in aa.columns:
        m = aa.merge(o[["order_id", "customer_id"]].rename(columns={"customer_id": "order_customer_id"}), on="order_id", how="left")
        unknown = ~m["order_id"].isin(order_ids)
        mismatch = pd.Series(False, index=m.index)
        if "customer_id" in m.columns:
            mismatch = m["order_id"].isin(order_ids) & m["customer_id"].notna() & m["order_customer_id"].notna() & (m["customer_id"] != m["order_customer_id"])
        res.append(_result(R["ID-07"], unknown | mismatch, m["order_id"], detail=f"unknown order={int(unknown.sum())}, customer mismatch={int(mismatch.sum())}",
                           extra={"coverage_pct": round(100.0 * (1 - unknown.mean()), 2) if len(m) else None}))
    else:
        res.append(_empty_result(R["ID-07"], "app_actions not available"))

    # ID-08 interventions
    iv = clean.get("interventions")
    if iv is not None and "order_id" in iv.columns:
        mask = iv["order_id"].isna() | ~iv["order_id"].isin(order_ids)
        res.append(_result(R["ID-08"], mask, iv["order_id"], extra={"coverage_pct": round(100.0 * (1 - mask.mean()), 2) if len(iv) else None}))
    else:
        res.append(_empty_result(R["ID-08"], "interventions not available"))

    # ID-09 dispatch <-> orders
    dp = clean.get("dispatch")
    if dp is not None and "order_id" in dp.columns and len(o):
        dp_ids = set(dp["order_id"].dropna())
        missing_in_dispatch = ~oid.isin(dp_ids)
        unknown_in_dispatch = int((~dp["order_id"].isin(order_ids)).sum())
        r = _result(R["ID-09"], missing_in_dispatch, oid, detail=f"orders without dispatch record={int(missing_in_dispatch.sum())}; dispatch records for unknown orders={unknown_in_dispatch}",
                    extra={"orders_coverage_pct": round(100.0 * (1 - missing_in_dispatch.mean()), 2), "dispatch_unknown_orders": unknown_in_dispatch})
        if unknown_in_dispatch and r.status == "PASS":
            r.status = "WARN"
        res.append(r)
    else:
        res.append(_empty_result(R["ID-09"], "dispatch not available"))

    # ID-10 driver events
    de = clean.get("driver_events")
    if de is not None and "order_id" in de.columns:
        mask = ~de["order_id"].isin(order_ids)
        res.append(_result(R["ID-10"], mask, de["order_id"], extra={"coverage_pct": round(100.0 * (1 - mask.mean()), 2) if len(de) else None}))
    else:
        res.append(_empty_result(R["ID-10"], "driver_events not available"))

    # ST-* vocabularies
    st_map = {"ST-01": ("orders", "final_status"), "ST-02": ("orders", "traffic_bucket"), "ST-03": ("orders", "weather_bucket"),
              "ST-04": ("restaurant_status", "status"), "ST-05": ("tickets", "category"), "ST-06": ("app_actions", "action_type"),
              "ST-07": ("interventions", "intervention_type"), "ST-08": ("dispatch", "dispatch_status"), "ST-09": ("driver_events", "type")}
    for rid, (ds, col) in st_map.items():
        d = clean.get(ds)
        if d is None or col not in d.columns:
            res.append(_empty_result(R[rid], f"{ds}.{col} not available"))
            continue
        mask = d[col].notna() & ~d[col].isin(VOCAB[(ds, col)])
        corrected = sum(a.count for a in rep.actions if a.dataset == ds and a.column == col and a.action.startswith("normalise_category"))
        keys = d["order_id"] if "order_id" in d.columns else d[col]
        unexpected = {str(k): int(v) for k, v in d.loc[mask, col].value_counts().items()}
        cands = rep.semantic_candidates.get(f"{ds}.{col}", {})
        r = _result(R[rid], mask, keys, detail=f"representation fixes={corrected}; unexpected values={unexpected}; semantic candidates (owner decision)={cands}",
                    extra={"unexpected": unexpected, "semantic_candidates": cands, "representation_fixes": corrected})
        if corrected and r.status == "PASS":
            r.status = "WARN"
        res.append(r)

    # TS-00 parseability of KPI columns (from cleaning stats)
    ts = {s["column"]: s for s in rep.timestamp_stats}
    unp = sum(ts.get(f"orders.{c}", {}).get("unparseable", 0) for c in ["promised_eta", "actual_delivery_at", "created_at"])
    tot = len(o)
    r = RuleResult(R["TS-00"], int(unp), int(tot), _status(R["TS-00"], int(unp), int(tot)),
                   detail="; ".join(f"{k}: unparseable={v['unparseable']}, tz-aware={v['tz_aware_converted']}" for k, v in ts.items() if k.startswith("orders.")))
    res.append(r)

    # TS-01..05 order chronology
    def col(c):
        return o[c] if c in o.columns else pd.Series(pd.NaT, index=o.index)
    created, promised, pickup, actual = col("created_at"), col("promised_eta"), col("pickup_at"), col("actual_delivery_at")
    status = col("final_status")
    res.append(_result(R["TS-01"], promised < created, oid, detail="minutes early: " + str(sorted(set(minutes_between(created, promised)[promised < created].round(1).tolist()))[:6])))
    res.append(_result(R["TS-02"], actual < pickup, oid, detail="minutes before pickup: " + str(sorted(set(minutes_between(pickup, actual)[actual < pickup].round(1).tolist()))[:6])))
    res.append(_result(R["TS-03"], pickup < created, oid))
    delivered_missing = (status == "delivered") & actual.isna()
    recoverable = 0
    if de is not None and {"order_id", "type", "timestamp"} <= set(de.columns):
        dl = de[(de["type"] == "delivered") & de["timestamp"].notna()]["order_id"]
        recoverable = int(oid[delivered_missing].isin(set(dl)).sum())
    res.append(_result(R["TS-04"], delivered_missing, oid, detail=f"{int(delivered_missing.sum())} delivered orders lack actual_delivery_at; {recoverable} of them have a driver 'delivered' event that could back-fill it (owner decision)",
                       extra={"recoverable_from_driver_events": recoverable}))
    res.append(_result(R["TS-05"], (status == "cancelled") & actual.notna(), oid))

    # TS-06 dispatch chronology
    if dp is not None and {"order_id", "assigned_at"} <= set(dp.columns):
        m = dp.merge(o[["order_id", "created_at"]], on="order_id", how="left")
        bad = (m["assigned_at"] < m["created_at"])
        if "reassigned_at" in m.columns:
            bad = bad | (m["reassigned_at"] < m["assigned_at"])
        res.append(_result(R["TS-06"], bad, m["order_id"]))
    else:
        res.append(_empty_result(R["TS-06"], "dispatch not available"))

    # TS-07 driver-event chronology
    if de is not None and {"order_id", "type", "timestamp"} <= set(de.columns) and len(de):
        piv = de[de["type"].isin(["assigned", "picked_up", "delivered"])].groupby(["order_id", "type"])["timestamp"].min().unstack()
        for c in ["assigned", "picked_up", "delivered"]:
            if c not in piv.columns:
                piv[c] = pd.NaT
        bad = (piv["picked_up"] < piv["assigned"]) | (piv["delivered"] < piv["picked_up"])
        res.append(_result(R["TS-07"], bad.reset_index(drop=True), pd.Series(piv.index, dtype="object"),
                           detail=f"picked_up<assigned={int((piv['picked_up'] < piv['assigned']).sum())}, delivered<picked_up={int((piv['delivered'] < piv['picked_up']).sum())}"))
    else:
        res.append(_empty_result(R["TS-07"], "driver_events not available"))

    # RG-01 distance
    if "distance_km_estimate" in o.columns:
        dist = o["distance_km_estimate"]
        res.append(_result(R["RG-01"], dist.isna() | (dist <= 0) | (dist > cfg.max_plausible_distance_km), oid,
                           detail=f"null={int(dist.isna().sum())}, <=0={int((dist <= 0).sum())}, >{cfg.max_plausible_distance_km}km={int((dist > cfg.max_plausible_distance_km).sum())}"))
    else:
        res.append(_empty_result(R["RG-01"], "distance_km_estimate column missing"))

    # RG-02 restaurant coordinates
    rest = clean.get("restaurants")
    if rest is not None and {"lat", "lon"} <= set(rest.columns):
        bad = rest["lat"].isna() | rest["lon"].isna() | ~rest["lat"].between(*cfg.lat_range) | ~rest["lon"].between(*cfg.lon_range)
        res.append(_result(R["RG-02"], bad, rest["restaurant_id"], detail="; ".join(f"{r_.restaurant_id}: ({r_.lat}, {r_.lon})" for r_ in rest[bad].itertuples())))
    else:
        res.append(_empty_result(R["RG-02"], "restaurants not available"))

    # RG-03 gps pings
    if de is not None and {"lat", "lon", "type"} <= set(de.columns):
        pings = de[de["type"] == "gps_ping"]
        bad = pings["lat"].isna() | pings["lon"].isna() | ~pings["lat"].between(*cfg.lat_range) | ~pings["lon"].between(*cfg.lon_range)
        res.append(_result(R["RG-03"], bad.reset_index(drop=True), pings["order_id"].reset_index(drop=True)))
    else:
        res.append(_empty_result(R["RG-03"], "driver_events not available"))

    # RG-04 drivers
    dr = clean.get("drivers")
    if dr is not None and {"rating", "experience_months"} <= set(dr.columns):
        bad = ~dr["rating"].between(0, 5) | (dr["experience_months"] < 0)
        res.append(_result(R["RG-04"], bad, dr["driver_id"]))
    else:
        res.append(_empty_result(R["RG-04"], "drivers not available"))

    # CX-01 driver consistency with dispatch
    if dp is not None and {"order_id", "driver_id"} <= set(dp.columns) and "driver_id" in o.columns:
        m = o[["order_id", "driver_id"]].merge(dp[["order_id", "driver_id"] + (["original_driver_id"] if "original_driver_id" in dp.columns else [])].rename(columns={"driver_id": "dispatch_driver_id"}), on="order_id", how="inner")
        mism = m["driver_id"].notna() & m["dispatch_driver_id"].notna() & (m["driver_id"] != m["dispatch_driver_id"])
        eq_orig = int((m["driver_id"] == m["original_driver_id"]).sum()) if "original_driver_id" in m.columns else None
        res.append(_result(R["CX-01"], mism, m["order_id"], detail=f"orders.driver_id equals dispatch ORIGINAL driver for {eq_orig} orders -> the orders table is not updated after reassignment; Dispatch is authoritative for the final driver",
                           extra={"matches_original_driver": eq_orig}))
    else:
        res.append(_empty_result(R["CX-01"], "dispatch or driver_id not available"))

    # CX-02 pickup agreement
    if de is not None and {"order_id", "type", "timestamp"} <= set(de.columns) and "pickup_at" in o.columns:
        pk = de[de["type"] == "picked_up"].groupby("order_id")["timestamp"].min().rename("ev_pickup")
        m = o[["order_id", "pickup_at"]].merge(pk, left_on="order_id", right_index=True, how="inner")
        diff = (m["pickup_at"] - m["ev_pickup"]).abs() > pd.Timedelta(seconds=60)
        res.append(_result(R["CX-02"], diff, m["order_id"], detail=f"compared {len(m)} orders"))
    else:
        res.append(_empty_result(R["CX-02"], "driver_events not available"))

    # CX-03 reassignment reconciliation
    if dp is not None and iv is not None and "reassigned_at" in dp.columns and "intervention_type" in iv.columns:
        dp_re = set(dp.loc[dp["reassigned_at"].notna(), "order_id"])
        iv_re = set(iv.loc[iv["intervention_type"] == "DRIVER_REASSIGNMENT", "order_id"])
        only_iv, only_dp, both = iv_re - dp_re, dp_re - iv_re, iv_re & dp_re
        union = iv_re | dp_re
        r = RuleResult(R["CX-03"], len(only_iv) + len(only_dp), len(union), "WARN" if (only_iv or only_dp) else ("PASS" if union else "UNKNOWN"),
                       detail=f"dispatch reassigned={len(dp_re)}, intervention DRIVER_REASSIGNMENT={len(iv_re)}, in both={len(both)}, only in interventions={len(only_iv)}, only in dispatch={len(only_dp)}",
                       sample_keys=sorted(only_iv)[:5] + sorted(only_dp)[:5], violating_keys=sorted(only_iv | only_dp),
                       extra={"dispatch_reassigned": len(dp_re), "intervention_reassignments": len(iv_re), "overlap": len(both)})
        res.append(r)
    else:
        res.append(_empty_result(R["CX-03"], "dispatch or interventions not available"))

    # FR-01 freshness
    if rs is not None and {"order_id", "status", "last_updated_at"} <= set(rs.columns) and "pickup_at" in o.columns:
        m = rs.merge(o[["order_id", "created_at", "pickup_at", "actual_delivery_at"]], on="order_id", how="inner")
        lag = minutes_between(m["last_updated_at"], m["pickup_at"])              # + = status written after pickup
        stale = m["status"].isin(["ready", "handed_off"]) & (lag > cfg.status_freshness_sla_min)
        before_creation = m["last_updated_at"] < m["created_at"]
        covered_orders = m["order_id"].nunique()
        r = _result(R["FR-01"], stale | before_creation, m["order_id"],
                    detail=f"status rows joined={len(m)} covering {covered_orders} of {len(order_ids)} orders ({round(100.0 * covered_orders / len(order_ids), 1) if order_ids else 0}%); "
                           f"ready/handed_off written >{cfg.status_freshness_sla_min:.0f} min after pickup={int(stale.sum())}; updated before order creation={int(before_creation.sum())}; "
                           f"median lag vs pickup={round(float(lag.median()), 1) if lag.notna().any() else 'n/a'} min; timestamps have minute precision only",
                    extra={"orders_covered": int(covered_orders), "coverage_pct": round(100.0 * covered_orders / len(order_ids), 2) if order_ids else None,
                           "median_lag_vs_pickup_min": None if not lag.notna().any() else round(float(lag.median()), 2),
                           "p90_lag_vs_pickup_min": None if not lag.notna().any() else round(float(lag.quantile(0.9)), 2)})
        res.append(r)
    else:
        res.append(_empty_result(R["FR-01"], "restaurant_status not available"))

    # KPI-01 definition ownership (organisational)
    md = metric_definitions or {}
    defs = md.get("stakeholders", {}) if isinstance(md, dict) else {}
    r = RuleResult(R["KPI-01"], 0, 0, "UNKNOWN", detail=("no canonical KPI owner documented; " if not md.get("owner") else "") + f"{len(defs)} stakeholder definitions found: " + "; ".join(f"{k}: {v}" for k, v in defs.items()))
    res.append(r)

    for r in res:
        log.info("rule %-6s %-7s viol=%5d / %5d  %s", r.rule.id, r.status, r.violations, r.population, r.rule.name)
    return res


def results_frame(results: list[RuleResult]) -> pd.DataFrame:
    return pd.DataFrame([r.as_dict() for r in results])


def kpi_exclusions(results: list[RuleResult]) -> dict[str, list[str]]:
    """order_id -> list of reject-rule ids (defines the KPI population)."""
    out: dict[str, list[str]] = {}
    for r in results:
        if r.rule.action == "reject" and r.rule.dataset == "orders":
            for k in r.violating_keys:
                out.setdefault(k, []).append(r.rule.id)
    return out


def order_flags(results: list[RuleResult]) -> dict[str, list[str]]:
    """order_id -> all rule ids that flagged/rejected it (for the fact table's dq_flags column)."""
    out: dict[str, list[str]] = {}
    for r in results:
        if r.rule.dataset in ("orders",) or r.rule.id in ("ID-05", "ID-06", "ID-07", "ID-08", "ID-10", "TS-06", "TS-07", "RG-03", "FR-01", "CX-03"):
            for k in r.violating_keys:
                if r.rule.id not in out.setdefault(k, []):
                    out[k].append(r.rule.id)
    return out

"""Business metrics linked to the project KPI (reduce Late Delivery Rate).

Five metrics, each answering a business question:

M1  Late Delivery Rate              outcome      How large is the problem?  (the project KPI)
M2  Lateness severity               outcome      How late is late? (median among late, P90 of all delivered)
M3  Delay accumulation by stage     workflow     WHERE in the lifecycle does the lateness build up?
M4  Support contact rate on late    interaction  How often does a late order turn into a customer contact?
M5  Intervention coverage & effect  intervention Do interventions reach late-risk orders, and how do outcomes compare?

Every metric carries numerator, denominator, population and edge-case notes.
Association is never presented as causation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import PipelineConfig
from .logging_utils import get_logger
from .model import DISTANCE_LABELS, ModelBundle


@dataclass
class MetricsResult:
    metrics: pd.DataFrame
    breakdowns: dict[str, pd.DataFrame] = field(default_factory=dict)
    checks: list[dict] = field(default_factory=list)
    headline: dict = field(default_factory=dict)


def _pct(num, den) -> float | None:
    return None if not den else round(100.0 * num / den, 2)


def _rate_table(df: pd.DataFrame, by: str, min_n: int = 1) -> pd.DataFrame:
    """late rate + delay stats per group, only over the KPI population."""
    d = df[df["kpi_population"]]
    if len(d) == 0:
        return pd.DataFrame(columns=[by, "orders", "late_orders", "late_rate_pct", "median_delay_min", "mean_delay_min"])
    g = d.groupby(by, dropna=False, observed=True).agg(orders=("order_id", "size"), late_orders=("late_flag", "sum"),
                                                        median_delay_min=("delay_min", "median"), mean_delay_min=("delay_min", "mean")).reset_index()
    g["late_orders"] = g["late_orders"].astype(int)
    g["late_rate_pct"] = (100.0 * g["late_orders"] / g["orders"]).round(1)
    g["median_delay_min"] = g["median_delay_min"].round(1)
    g["mean_delay_min"] = g["mean_delay_min"].round(1)
    g[by] = g[by].astype(str).replace({"nan": "unknown", "None": "unknown"})
    g = g[g["orders"] >= min_n][[by, "orders", "late_orders", "late_rate_pct", "median_delay_min", "mean_delay_min"]]
    if by == "distance_band":                       # keep bands in distance order, not alphabetical
        order = {lbl: i for i, lbl in enumerate(DISTANCE_LABELS + ["invalid/unknown"])}
        g = g.assign(_o=g[by].map(order).fillna(99)).sort_values("_o").drop(columns="_o")
    return g.reset_index(drop=True)


def compute_metrics(model: ModelBundle, cfg: PipelineConfig, reference_outcomes: pd.DataFrame | None = None) -> MetricsResult:
    log = get_logger()
    fo = model["fact_order"]
    oj = model["order_journey"]
    rows: list[dict] = []
    bd: dict[str, pd.DataFrame] = {}
    checks: list[dict] = []

    pop = fo[fo["kpi_population"]]
    n_pop = int(len(pop))
    late = pop[pop["late_flag"] == 1.0]
    n_late = int(len(late))
    delivered = fo[fo["delivered_flag"]]

    def add(mid, name, category, value, unit, num, den, population, definition, kpi_link, notes=""):
        rows.append({"metric_id": mid, "metric": name, "category": category, "value": value, "unit": unit, "numerator": num,
                     "denominator": den, "population": population, "definition": definition, "kpi_link": kpi_link, "notes": notes})

    # ---------------------------------------------------------------- M1 late delivery rate
    add("M1", "Late delivery rate (validated population)", "outcome", _pct(n_late, n_pop), "%", n_late, n_pop,
        "delivered orders with valid promised_eta + actual_delivery_at, passing chronology rules TS-01/02/03",
        f"late = actual_delivery_at - promised_eta > {cfg.late_threshold_min:g} min", "PROJECT KPI",
        "cancelled orders excluded (Finance); delivered orders without a delivery timestamp are 'unknown', not on-time")

    hist = delivered[delivered["actual_delivery_at"].notna() & delivered["promised_eta"].notna()]
    hist_late = int((hist["delay_min"] > cfg.late_threshold_min).sum())
    add("M1a", "Late delivery rate (historical dashboard definition)", "outcome", _pct(hist_late, len(hist)), "%", hist_late, int(len(hist)),
        "delivered orders with non-null actual delivery time (Data Team definition, no chronology rules)",
        "same formula as M1 on the historical population", "PROJECT KPI (comparison)",
        "reproduces the leadership claim; differs from M1 only by the chronology-violating orders")
    n_late10 = int((pop["delay_min"] > cfg.meaningful_late_threshold_min).sum())
    add("M1b", f"Meaningfully late rate (> {cfg.meaningful_late_threshold_min:g} min)", "outcome", _pct(n_late10, n_pop), "%", n_late10, n_pop,
        "validated population", f"delay_min > {cfg.meaningful_late_threshold_min:g}", "PROJECT KPI (Support Lead definition)")
    bf = fo[fo["delivered_flag"] & (fo["kpi_exclusion_reason"].str.replace("TS-04", "").str.strip(";") == "") & fo["delay_min_backfilled"].notna()]
    bf_late = int((bf["delay_min_backfilled"] > cfg.late_threshold_min).sum())
    add("M1c", "Late delivery rate (sensitivity: back-fill missing delivery time from driver telemetry)", "outcome", _pct(bf_late, len(bf)), "%", bf_late, int(len(bf)),
        "validated population + delivered orders whose missing actual_delivery_at is back-filled from the driver 'delivered' event",
        "delay computed on the back-filled timestamp", "PROJECT KPI (sensitivity)",
        f"{int(fo['backfilled_from_driver_event'].sum())} orders back-filled; NOT the published number - needs Fleet Ops to confirm the driver event is authoritative")

    # ---------------------------------------------------------------- M2 severity
    add("M2", "Median lateness among late orders", "outcome", None if n_late == 0 else round(float(late["delay_min"].median()), 1), "min", None, n_late,
        "late orders in the validated population", "median(delay_min | late)", "severity of the KPI")
    add("M2a", "P90 delay across all validated deliveries", "outcome", None if n_pop == 0 else round(float(pop["delay_min"].quantile(0.9)), 1), "min", None, n_pop,
        "validated population", "90th percentile of delay_min (negative = early)", "severity of the KPI")
    add("M2b", "Worst single delay", "outcome", None if n_pop == 0 else round(float(pop["delay_min"].max()), 1), "min", None, n_pop, "validated population", "max(delay_min)", "severity of the KPI")

    # ---------------------------------------------------------------- M3 stage decomposition
    st = pop[pop["pickup_overrun_min"].notna() & pop["transit_overrun_min"].notna()]
    st_late = st[st["late_flag"] == 1.0]
    pre = float(st_late["pickup_overrun_min"].clip(lower=0).sum()) if len(st_late) else 0.0
    tra = float(st_late["transit_overrun_min"].clip(lower=0).sum()) if len(st_late) else 0.0
    share_pre = _pct(pre, pre + tra)
    add("M3", "Share of lateness accumulated before pickup (vs in transit)", "workflow", share_pre, "%", round(pre, 1), round(pre + tra, 1),
        f"late orders with Dispatch estimated_pickup_at ({len(st_late)} orders)",
        "delay = (pickup_at - estimated_pickup_at) + ((actual - pickup) - (promised - estimated_pickup)); share = sum(max(pre-pickup overrun,0)) / sum(all positive overruns)",
        "WHERE delay accumulates -> which stage to fix first",
        "pre-pickup mixes restaurant prep and driver travel-to-restaurant: no 'arrived at restaurant' event exists to split them")
    add("M3a", "Median pre-pickup overrun on late orders", "workflow", None if len(st_late) == 0 else round(float(st_late["pickup_overrun_min"].median()), 1), "min", None, len(st_late),
        "late orders with dispatch estimates", "median(pickup_at - estimated_pickup_at)", "stage diagnosis")
    add("M3b", "Median transit overrun on late orders", "workflow", None if len(st_late) == 0 else round(float(st_late["transit_overrun_min"].median()), 1), "min", None, len(st_late),
        "late orders with dispatch estimates", "median((actual - pickup) - (promised - estimated_pickup))", "stage diagnosis")
    stage_cols = ["dispatch_wait_min", "pickup_wait_min", "transit_min", "total_cycle_min", "promised_window_min", "pickup_overrun_min", "transit_overrun_min", "eta_revision_min"]
    if len(pop):
        stage = pop.groupby(pop["late_flag"].map({1.0: "late", 0.0: "on_time"}))[stage_cols].median().round(1).T.reset_index().rename(columns={"index": "stage_metric"})
        stage["late_minus_on_time"] = (stage.get("late", np.nan) - stage.get("on_time", np.nan)).round(1)
        bd["stage_durations_by_outcome"] = stage
    # where does the overrun sit for late orders: both / pre only / transit only
    if len(st_late):
        cls = np.select([(st_late["pickup_overrun_min"] > 0) & (st_late["transit_overrun_min"] > 0), st_late["pickup_overrun_min"] > 0, st_late["transit_overrun_min"] > 0],
                        ["both stages overran", "pre-pickup only", "transit only"], "neither (rounding)")
        bd["late_orders_by_overrun_stage"] = pd.Series(cls).value_counts().rename_axis("overrun_pattern").reset_index(name="late_orders").assign(
            share_pct=lambda d: (100 * d["late_orders"] / d["late_orders"].sum()).round(1))

    # ---------------------------------------------------------------- M4 interaction
    oj_pop = oj[oj["kpi_population"]]
    oj_late = oj_pop[oj_pop["late_flag"] == 1.0]
    oj_ontime = oj_pop[oj_pop["late_flag"] == 0.0]
    add("M4", "Support contact rate on late orders", "interaction", _pct(int(oj_late["support_contact"].sum()), len(oj_late)), "%",
        int(oj_late["support_contact"].sum()), int(len(oj_late)), "late orders (validated population)",
        "order has a support ticket OR a SUPPORT_OPENED app action", "customer impact of the KPI",
        f"on-time comparison: {_pct(int(oj_ontime['support_contact'].sum()), len(oj_ontime))}% of on-time orders had a support contact")
    add("M4a", "Support contact rate on on-time orders", "interaction", _pct(int(oj_ontime["support_contact"].sum()), len(oj_ontime)), "%",
        int(oj_ontime["support_contact"].sum()), int(len(oj_ontime)), "on-time orders", "same definition as M4", "baseline for M4")
    add("M4b", "Frustrated journeys with no intervention", "interaction", int(oj["frustrated_no_intervention"].sum()), "orders",
        int(oj["frustrated_no_intervention"].sum()), int(oj["support_contact"].sum()), "all orders with a support contact",
        "support contact AND intervention_count == 0", "missed opportunities for the ops team")
    add("M4c", "Median ETA views per order (late vs on-time)", "interaction",
        None if len(oj_late) == 0 else f"{oj_late['eta_view_count'].median():.0f} vs {oj_ontime['eta_view_count'].median():.0f}", "views", None, None,
        "validated population", "median(eta_view_count)", "early-warning signal candidate", "association only")

    # ---------------------------------------------------------------- M5 interventions
    n_iv = int(oj_pop["has_intervention"].sum())
    add("M5", "Intervention coverage of delivered orders", "intervention", _pct(n_iv, len(oj_pop)), "%", n_iv, int(len(oj_pop)),
        "validated population", "orders with >= 1 intervention / orders", "how much of the workflow the ops team touches")
    with_iv = oj_pop[oj_pop["has_intervention"]]
    without_iv = oj_pop[~oj_pop["has_intervention"]]
    add("M5a", "Late rate WITH an intervention", "intervention", _pct(int((with_iv["late_flag"] == 1.0).sum()), len(with_iv)), "%",
        int((with_iv["late_flag"] == 1.0).sum()), int(len(with_iv)), "validated orders with an intervention", "late orders / orders (with intervention)",
        "does intervening coincide with better outcomes?", "ASSOCIATION ONLY: interventions target late-risk orders (selection effect)")
    add("M5b", "Late rate WITHOUT an intervention", "intervention", _pct(int((without_iv["late_flag"] == 1.0).sum()), len(without_iv)), "%",
        int((without_iv["late_flag"] == 1.0).sum()), int(len(without_iv)), "validated orders without an intervention", "late orders / orders (no intervention)", "baseline for M5a")
    fv = model["fact_intervention"]
    if len(fv):
        top = fv["intervention_type"].value_counts()
        add("M5c", "Most common intervention type", "intervention", f"{top.index[0]} ({int(top.iloc[0])})", "type", int(top.iloc[0]), int(len(fv)), "all interventions", "mode(intervention_type)", "what the ops team actually does")
        iv_type = fv.merge(oj[["order_id", "kpi_population", "late_flag", "delay_min"]], on="order_id", how="left")
        iv_type = iv_type[iv_type["kpi_population"] == True]  # noqa: E712
        g = iv_type.groupby("intervention_type").agg(orders=("order_id", "nunique"), late_orders=("late_flag", "sum"), median_delay_min=("delay_min", "median"),
                                                     before_promised_eta_pct=("before_promised_eta", lambda s: round(100 * s.mean(), 1))).reset_index()
        g["late_orders"] = g["late_orders"].astype(int)
        g["late_rate_pct"] = (100 * g["late_orders"] / g["orders"]).round(1)
        g["median_delay_min"] = g["median_delay_min"].round(1)
        base = pd.DataFrame([{"intervention_type": "(no intervention)", "orders": int(len(without_iv)), "late_orders": int((without_iv["late_flag"] == 1.0).sum()),
                              "median_delay_min": round(float(without_iv["delay_min"].median()), 1) if len(without_iv) else None, "before_promised_eta_pct": None,
                              "late_rate_pct": _pct(int((without_iv["late_flag"] == 1.0).sum()), len(without_iv))}])
        bd["late_rate_by_intervention_type"] = pd.concat([g, base], ignore_index=True).sort_values("late_rate_pct", ascending=False)

    # ---------------------------------------------------------------- breakdowns (Class 5 Ch2 / Class 7 Ch5)
    bd["definition_comparison"] = pd.DataFrame([
        {"definition": "VP Operations: any delivered order after promised ETA (validated population)", "late_rate_pct": _pct(n_late, n_pop), "late": n_late, "population": n_pop},
        {"definition": "Data Team: delivered orders with non-null actual delivery time (historical dashboard)", "late_rate_pct": _pct(hist_late, len(hist)), "late": hist_late, "population": int(len(hist))},
        {"definition": f"Support Lead: only > {cfg.meaningful_late_threshold_min:g} min beyond ETA", "late_rate_pct": _pct(n_late10, n_pop), "late": n_late10, "population": n_pop},
        {"definition": "Finance: cancelled/refunded excluded (already true in every definition above)", "late_rate_pct": _pct(n_late, n_pop), "late": n_late, "population": n_pop},
        {"definition": "Sensitivity: back-fill missing delivery time from driver telemetry", "late_rate_pct": _pct(bf_late, len(bf)), "late": bf_late, "population": int(len(bf))},
    ])
    bd["outcome_distribution"] = fo["outcome_bucket"].value_counts().rename_axis("outcome_bucket").reset_index(name="orders").assign(share_pct=lambda d: (100 * d["orders"] / d["orders"].sum()).round(1))
    bd["late_rate_by_traffic"] = _rate_table(fo, "traffic_bucket")
    bd["late_rate_by_weather"] = _rate_table(fo, "weather_bucket")
    bd["late_rate_by_distance_band"] = _rate_table(fo, "distance_band")
    bd["late_rate_by_hour"] = _rate_table(fo, "hour_of_day")
    bd["late_rate_by_day_of_week"] = _rate_table(fo, "day_of_week")
    bd["late_rate_by_eta_model_version"] = _rate_table(fo, "eta_model_version")
    bd["late_rate_by_reassignment"] = _rate_table(fo.assign(reassigned=fo["reassigned_flag"].map({True: "reassigned", False: "not reassigned"})), "reassigned")
    rest = _rate_table(fo.assign(restaurant_id=fo["restaurant_id"].fillna("UNKNOWN")), "restaurant_id", min_n=5)
    if len(rest):
        rest["share_of_all_late_pct"] = (100 * rest["late_orders"] / max(n_late, 1)).round(1)
        bd["top_restaurants_by_late_orders"] = rest.sort_values(["late_orders", "late_rate_pct"], ascending=False).head(10)
    drv = _rate_table(fo.assign(driver_id=fo["driver_id"].fillna("UNKNOWN")), "driver_id", min_n=5)
    if len(drv):
        bd["top_drivers_by_late_rate"] = drv.sort_values(["late_rate_pct", "orders"], ascending=False).head(10)
    bd["worst_delays"] = pop.sort_values("delay_min", ascending=False)[["order_id", "restaurant_id", "driver_id", "promised_eta", "actual_delivery_at", "delay_min", "traffic_bucket", "weather_bucket", "distance_km_estimate", "reassigned_flag", "dq_flags"]].head(10)
    # customer view vs system view (Class 5 Ch3)
    fi = model["fact_interaction"]
    tk = fi[fi["source_system"] == "support_desk"].merge(fo[["order_id", "kpi_population", "late_flag", "delay_min", "outcome_bucket"]], on="order_id", how="left")
    if len(tk):
        cv = tk.groupby("detail", dropna=False).agg(tickets=("interaction_id", "size"), orders_matched=("kpi_population", lambda s: int(s.notna().sum())),
                                                   late_share_pct=("late_flag", lambda s: _pct(int((s == 1.0).sum()), int(s.notna().sum()))),
                                                   median_delay_min=("delay_min", "median")).reset_index().rename(columns={"detail": "ticket_category"})
        cv["median_delay_min"] = cv["median_delay_min"].round(1)
        cv["ticket_category"] = cv["ticket_category"].fillna("(unknown)")
        bd["customer_view_vs_system_view"] = cv.sort_values("tickets", ascending=False)
    # journeys: support + intervention + still late
    bd["journey_patterns"] = pd.DataFrame([
        {"pattern": "late orders", "orders": int(len(oj_late))},
        {"pattern": "late + support contact", "orders": int(oj_late["support_contact"].sum())},
        {"pattern": "late + intervention", "orders": int(oj_late["has_intervention"].sum())},
        {"pattern": "late + support contact + intervention (still late)", "orders": int(oj["frustrated_intervened_still_late"].sum())},
        {"pattern": "support contact + NO intervention (any outcome)", "orders": int(oj["frustrated_no_intervention"].sum())},
        {"pattern": "cancel attempted in app", "orders": int(oj["cancel_attempted"].sum())},
    ])

    # ---------------------------------------------------------------- sanity checks
    checks.append({"check": "KPI denominator > 0", "status": "PASS" if n_pop > 0 else "FAIL", "evidence": f"validated population = {n_pop}"})
    checks.append({"check": "late + on-time == validated population", "status": "PASS" if n_late + int((pop["late_flag"] == 0.0).sum()) == n_pop else "FAIL",
                   "evidence": f"{n_late} + {int((pop['late_flag'] == 0.0).sum())} == {n_pop}"})
    checks.append({"check": "outcome buckets sum to unique orders", "status": "PASS" if int(bd["outcome_distribution"]["orders"].sum()) == len(fo) else "FAIL",
                   "evidence": f"{int(bd['outcome_distribution']['orders'].sum())} == {len(fo)}"})
    checks.append({"check": "stage decomposition is exact (pre-pickup + transit overrun == delay)", "status": "PASS" if len(st) == 0 or float(((st["pickup_overrun_min"] + st["transit_overrun_min"]) - st["delay_min"]).abs().max()) < 0.05 else "FAIL",
                   "evidence": f"max abs residual = {float(((st['pickup_overrun_min'] + st['transit_overrun_min']) - st['delay_min']).abs().max()) if len(st) else 0:.3f} min over {len(st)} orders"})
    if reference_outcomes is not None and len(reference_outcomes) and {"order_id", "late_flag", "delay_min"} <= set(reference_outcomes.columns):
        ref = reference_outcomes.copy()
        ref["order_id"] = ref["order_id"].astype(str).str.strip().str.upper()
        ref["late_flag"] = pd.to_numeric(ref["late_flag"], errors="coerce")
        ref["delay_min"] = pd.to_numeric(ref["delay_min"], errors="coerce")
        m = hist[["order_id", "delay_min"]].merge(ref[["order_id", "late_flag", "delay_min"]].rename(columns={"late_flag": "ref_late", "delay_min": "ref_delay"}), on="order_id", how="left")
        ref_late = int(ref["late_flag"].fillna(0).sum())
        max_diff = float((m["delay_min"] - m["ref_delay"]).abs().max()) if len(m) else 0.0
        same = (hist_late == ref_late) and max_diff < 0.05
        checks.append({"check": "independent reconciliation vs client order_outcomes.csv (historical definition)", "status": "PASS" if same else "WARN",
                       "evidence": f"pipeline late={hist_late} vs reference late={ref_late}; max |delay diff| = {max_diff:.3f} min over {len(m)} orders"})
    for c in model.join_checks:
        checks.append({"check": f"join cardinality: {c['merge']}", "status": "PASS" if c["row_count_preserved"] else "FAIL",
                       "evidence": f"left={c['left_rows']} right={c['right_rows']} result={c['result_rows']} (right duplicates dropped={c['right_duplicates_dropped']})"})

    metrics = pd.DataFrame(rows)
    headline = {"late_delivery_rate_pct": _pct(n_late, n_pop), "late_orders": n_late, "validated_population": n_pop,
                "historical_definition_pct": _pct(hist_late, len(hist)), "median_lateness_min": None if n_late == 0 else round(float(late["delay_min"].median()), 1),
                "share_lateness_before_pickup_pct": share_pre, "support_contact_rate_late_pct": _pct(int(oj_late["support_contact"].sum()), len(oj_late)),
                "intervention_coverage_pct": _pct(n_iv, len(oj_pop))}
    for r in rows:
        log.info("metric %-4s %-70s = %s %s (n=%s/%s)", r["metric_id"], r["metric"][:70], r["value"], r["unit"], r["numerator"], r["denominator"])
    for c in checks:
        (log.warning if c["status"] != "PASS" else log.info)("check %-7s %s | %s", c["status"], c["check"], c["evidence"])
    return MetricsResult(metrics=metrics, breakdowns=bd, checks=checks, headline=headline)

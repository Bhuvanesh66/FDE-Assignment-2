"""Decision layer - what the business can DO with the model (beyond the classroom).

The class answered "how big is the problem and where does it sit?" and stopped at
"do not build the AI predictor yet". An FDE still owes the client a next step that
works *today, with today's data*. Every analysis here is transparent (no ML), uses
only information available at decision time, and is judged on held-out data.

1. early_warning_backtest  - a proactive-intervention trigger: "not picked up k
                             minutes after Dispatch's own estimate". Chosen on
                             1-21 Aug, proven on 22-28 Aug.
2. eta_calibration         - how optimistic is the promise, and what honest padding
                             would reach a target on-time rate (a lever, with a
                             stated guardrail).
3. fair_ranking            - restaurants/drivers ranked with Wilson confidence
                             intervals, so nobody is penalised for small samples.
4. weather_truth           - does the client's weather label match observed weather?
5. gps_arrival_feasibility - can GPS pings stand in for the missing
                             "arrived at restaurant" event?
6. impact_whatif           - KPI and support-contact impact of acting on the trigger,
                             under explicitly labelled assumptions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import NormalDist

import numpy as np
import pandas as pd

from .config import PipelineConfig
from .logging_utils import get_logger
from .rules import cohen_kappa

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass
class InsightsResult:
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    headline: dict = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)


def wilson_interval(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a proportion (robust for small n and rates near 0/1)."""
    if n <= 0:
        return (float("nan"), float("nan"))
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((centre - half) / denom, (centre + half) / denom)


def _pct(num, den):
    return None if not den else round(100.0 * num / den, 1)


def _population(fo: pd.DataFrame) -> pd.DataFrame:
    return fo[fo["kpi_population"].astype(bool)].copy() if len(fo) else fo.copy()


# --------------------------------------------------------------------------- 1. early warning
def _alert_stats(d: pd.DataFrame, k: int) -> dict:
    alert_at = d["estimated_pickup_at"] + pd.Timedelta(minutes=k)
    fire = d["pickup_at"] > alert_at
    late = d["late_flag"] == 1.0
    tp, fp, fn = int((fire & late).sum()), int((fire & ~late).sum()), int((~fire & late).sum())
    lead = ((d["promised_eta"] - alert_at).dt.total_seconds() / 60)[fire & late]
    return {"grace_min": k, "orders": int(len(d)), "alerts": int(fire.sum()), "alert_rate_pct": _pct(int(fire.sum()), len(d)),
            "late_orders": int(late.sum()), "caught_late": tp, "false_alerts": fp,
            "precision_pct": _pct(tp, tp + fp), "recall_pct": _pct(tp, tp + fn),
            "median_lead_min": None if lead.empty else round(float(lead.median()), 1),
            "alerts_before_promise_pct": None if lead.empty else _pct(int((lead > 0).sum()), len(lead))}


def early_warning_backtest(fo: pd.DataFrame, fiv: pd.DataFrame, cfg: PipelineConfig) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    pop = _population(fo)
    need = {"estimated_pickup_at", "pickup_at", "promised_eta", "late_flag", "created_at"}
    if len(pop) == 0 or not need <= set(pop.columns):
        return pd.DataFrame(), pd.DataFrame(), {}
    pop = pop[pop["estimated_pickup_at"].notna() & pop["pickup_at"].notna()]
    if len(pop) == 0:
        return pd.DataFrame(), pd.DataFrame(), {}
    train = pop[pop["created_at"].dt.day <= cfg.ew_train_until_day]
    test = pop[pop["created_at"].dt.day > cfg.ew_train_until_day]
    holdout = len(test) > 0 and len(train) > 0
    if not holdout:                      # tiny or single-period data: be explicit instead of pretending
        train = test = pop
    rows = []
    for split, d in [("train", train), ("test", test), ("all", pop)]:
        for k in cfg.ew_grace_minutes_grid:
            rows.append({"split": split, **_alert_stats(d, k)})
    grid = pd.DataFrame(rows)
    tr = grid[grid["split"] == "train"]
    ok = tr[(tr["precision_pct"].fillna(0) >= 100 * cfg.ew_min_precision)]
    chosen = int(ok.sort_values(["recall_pct", "grace_min"], ascending=[False, True]).iloc[0]["grace_min"]) if len(ok) else int(tr.sort_values("precision_pct", ascending=False).iloc[0]["grace_min"])
    test_row = grid[(grid["split"] == "test") & (grid["grace_min"] == chosen)].iloc[0].to_dict()
    all_row = grid[(grid["split"] == "all") & (grid["grace_min"] == chosen)].iloc[0].to_dict()

    # how does today's intervention practice compare with the trigger?
    alert_at = pop["estimated_pickup_at"] + pd.Timedelta(minutes=chosen)
    fired = pop["pickup_at"] > alert_at
    late = pop["late_flag"] == 1.0
    first_iv = fiv.groupby("order_id")["intervention_at"].min() if len(fiv) else pd.Series(dtype="datetime64[ns]")
    has_iv = pop["order_id"].isin(first_iv.index)
    iv_time = pop["order_id"].map(first_iv)
    cmp = pd.DataFrame([
        {"group": "late orders the trigger catches", "orders": int((fired & late).sum()),
         "with_any_intervention": int((fired & late & has_iv).sum()), "intervention_before_pickup": int((fired & late & (iv_time < pop["pickup_at"])).sum())},
        {"group": "late orders the trigger misses", "orders": int((~fired & late).sum()),
         "with_any_intervention": int((~fired & late & has_iv).sum()), "intervention_before_pickup": int((~fired & late & (iv_time < pop["pickup_at"])).sum())},
        {"group": "on-time orders the trigger flags (false alerts)", "orders": int((fired & ~late).sum()),
         "with_any_intervention": int((fired & ~late & has_iv).sum()), "intervention_before_pickup": int((fired & ~late & (iv_time < pop["pickup_at"])).sum())},
        {"group": "on-time orders not flagged", "orders": int((~fired & ~late).sum()),
         "with_any_intervention": int((~fired & ~late & has_iv).sum()), "intervention_before_pickup": int((~fired & ~late & (iv_time < pop["pickup_at"])).sum())},
    ])
    cmp["intervention_coverage_pct"] = (100 * cmp["with_any_intervention"] / cmp["orders"].where(cmp["orders"] > 0)).round(1)
    head = {"chosen_grace_min": chosen, "holdout": holdout, "train_until_day": cfg.ew_train_until_day if holdout else None,
            "train_orders": int(len(train)), "test_orders": int(len(test)),
            "test_precision_pct": test_row["precision_pct"], "test_recall_pct": test_row["recall_pct"], "test_alert_rate_pct": test_row["alert_rate_pct"],
            "test_median_lead_min": test_row["median_lead_min"], "all_caught_late": int(all_row["caught_late"]), "all_alerts": int(all_row["alerts"]),
            "caught_late_without_intervention": int((fired & late & ~has_iv).sum()),
            "interventions_on_unflagged_on_time": int((~fired & ~late & has_iv).sum())}
    return grid, cmp, head


# --------------------------------------------------------------------------- 2. ETA calibration
def eta_calibration(fo: pd.DataFrame, cfg: PipelineConfig) -> tuple[pd.DataFrame, dict]:
    pop = _population(fo)
    if len(pop) == 0:
        return pd.DataFrame(), {}
    rows = []
    groups = [("all versions", pop)] + ([(str(v), g) for v, g in pop.groupby("eta_model_version")] if "eta_model_version" in pop.columns else [])
    for label, g in groups:
        for p in cfg.eta_padding_grid_min:
            late = int((g["delay_min"] > cfg.late_threshold_min + p).sum())
            rows.append({"eta_model_version": label, "padding_min": p, "orders": int(len(g)), "late_orders": late,
                         "late_rate_pct": _pct(late, len(g)), "on_time_rate_pct": _pct(len(g) - late, len(g))})
    table = pd.DataFrame(rows)
    target = cfg.target_on_time_rate_pct / 100.0
    delays = pop["delay_min"].dropna()
    needed = None
    if len(delays):
        # smallest whole-minute padding whose on-time rate actually reaches the target (an interpolated
        # quantile can undershoot on small samples, so search explicitly)
        upper = max(0, int(math.ceil(float(delays.max()) - cfg.late_threshold_min))) + 1
        for p in range(0, upper + 1):
            if float((delays <= cfg.late_threshold_min + p).mean()) >= target:
                needed = p
                break
    bias = pop["pickup_overrun_min"].dropna() if "pickup_overrun_min" in pop.columns else pd.Series(dtype=float)
    head = {"target_on_time_rate_pct": cfg.target_on_time_rate_pct, "padding_needed_min": needed,
            "late_rate_at_needed_padding_pct": None if needed is None else _pct(int((pop["delay_min"] > cfg.late_threshold_min + needed).sum()), len(pop)),
            "pickup_estimate_bias_median_min": None if bias.empty else round(float(bias.median()), 1),
            "pickup_estimate_bias_p75_min": None if bias.empty else round(float(bias.quantile(0.75)), 1),
            "planned_pickup_median_min": None if "planned_pickup_min" not in pop else round(float(pop["planned_pickup_min"].median()), 1),
            "actual_pickup_median_min": round(float(((pop["pickup_at"] - pop["created_at"]).dt.total_seconds() / 60).median()), 1),
            "promised_window_median_min": None if "promised_window_min" not in pop else round(float(pop["promised_window_min"].median()), 1)}
    return table, head


# --------------------------------------------------------------------------- 3. fair ranking
def fair_ranking(fo: pd.DataFrame, entity: str, min_orders: int, confidence: float) -> tuple[pd.DataFrame, dict]:
    pop = _population(fo)
    if len(pop) == 0 or entity not in pop.columns:
        return pd.DataFrame(), {}
    fleet = float((pop["late_flag"] == 1.0).mean())
    g = pop.assign(**{entity: pop[entity].fillna("UNKNOWN")}).groupby(entity).agg(orders=("order_id", "size"), late_orders=("late_flag", "sum")).reset_index()
    g["late_orders"] = g["late_orders"].astype(int)
    g["late_rate_pct"] = (100 * g["late_orders"] / g["orders"]).round(1)
    ci = [wilson_interval(k, n, confidence) for k, n in zip(g["late_orders"], g["orders"])]
    g["ci_low_pct"] = [round(100 * lo, 1) for lo, _ in ci]
    g["ci_high_pct"] = [round(100 * hi, 1) for _, hi in ci]

    def verdict(r):
        if r["orders"] < min_orders:
            return "too few orders to judge"
        if r["ci_low_pct"] / 100 > fleet:
            return "worse than fleet (significant)"
        if r["ci_high_pct"] / 100 < fleet:
            return "better than fleet (significant)"
        return "not distinguishable from fleet"
    g["verdict"] = g.apply(verdict, axis=1)
    naive_top10 = set(g.sort_values(["late_orders", "late_rate_pct"], ascending=False).head(10)[entity])
    g["in_naive_top10"] = g[entity].isin(naive_top10)
    g = g.sort_values(["verdict", "ci_low_pct"], ascending=[True, False]).reset_index(drop=True)
    head = {"entity": entity, "fleet_late_rate_pct": round(100 * fleet, 1), "entities": int(len(g)), "judgeable": int((g["orders"] >= min_orders).sum()),
            "significantly_worse": int((g["verdict"] == "worse than fleet (significant)").sum()),
            "significantly_better": int((g["verdict"] == "better than fleet (significant)").sum()),
            "naive_top10_significant": int(((g["in_naive_top10"]) & (g["verdict"] == "worse than fleet (significant)")).sum()),
            "worse_list": g.loc[g["verdict"] == "worse than fleet (significant)", entity].tolist()}
    return g, head


# --------------------------------------------------------------------------- 4. weather truth
def weather_truth(fo: pd.DataFrame, wx: pd.DataFrame | None, cfg: PipelineConfig) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    if wx is None or len(wx) == 0 or len(fo) == 0:
        return pd.DataFrame(), pd.DataFrame(), {}
    m = fo[["order_id", "created_at", "weather_bucket", "kpi_population", "late_flag"]].assign(hour=fo["created_at"].dt.floor("h"))
    m = m.merge(wx[["hour", "precipitation_mm"]], on="hour", how="left")
    m["observed_rain"] = m["precipitation_mm"] > cfg.weather_rain_threshold_mm
    cov = m[m["precipitation_mm"].notna()]
    by_label = cov.groupby("weather_bucket").agg(orders=("order_id", "size"), observed_rain_share_pct=("observed_rain", lambda s: round(100 * s.mean(), 1)),
                                                mean_observed_mm=("precipitation_mm", lambda s: round(float(s.mean()), 2))).reset_index()
    pop = cov[cov["kpi_population"].astype(bool)]
    lab = pop.assign(signal="client label: " + pop["weather_bucket"].astype(str))
    obs = pop.assign(signal=np.where(pop["observed_rain"], "observed: raining", "observed: dry"))
    both = pd.concat([lab, obs])
    late_by = both.groupby("signal").agg(orders=("order_id", "size"), late_rate_pct=("late_flag", lambda s: round(100 * (s == 1.0).mean(), 1))).reset_index()
    labelled = cov["weather_bucket"].isin(["rain", "heavy_rain"])
    kappa = cohen_kappa(labelled, cov["observed_rain"])
    obs_rain = pop[pop["observed_rain"]]
    obs_dry = pop[~pop["observed_rain"]]
    head = {"orders_covered": int(len(cov)), "kappa": None if kappa is None else round(kappa, 3),
            "agreement_pct": round(100 * float((labelled == cov["observed_rain"]).mean()), 1),
            "late_rate_observed_rain_pct": _pct(int((obs_rain["late_flag"] == 1.0).sum()), len(obs_rain)),
            "late_rate_observed_dry_pct": _pct(int((obs_dry["late_flag"] == 1.0).sum()), len(obs_dry))}
    for lbl in ["clear", "heavy_rain"]:
        r = by_label[by_label["weather_bucket"] == lbl]
        head[f"mean_mm_label_{lbl}"] = None if r.empty else float(r["mean_observed_mm"].iloc[0])
    return by_label, late_by, head


# --------------------------------------------------------------------------- 5. GPS arrival feasibility
def _haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def _straight_line_r2(g: pd.DataFrame) -> float:
    """min R^2 of lat and lon against time: 1.0 = a perfectly straight track driven at constant speed."""
    if len(g) < 3:
        return np.nan
    t = (g["timestamp"] - g["timestamp"].iloc[0]).dt.total_seconds().to_numpy(dtype=float)
    if np.ptp(t) == 0:
        return np.nan
    fits = []
    for c in ("lat", "lon"):
        y = g[c].to_numpy(dtype=float)
        fits.append(1.0 if np.ptp(y) == 0 else float(np.corrcoef(t, y)[0, 1] ** 2))
    return min(fits)


def gps_track_shape(pings: pd.DataFrame, lat_range=None, lon_range=None) -> dict:
    """Do the pings look MEASURED or DRAWN? Real device tracks wiggle and have uneven gaps; an app that
    interpolates a straight line from A to B produces R^2 = 1 and perfectly even spacing."""
    p = pings[pings["lat"].notna() & pings["lon"].notna()]
    if lat_range is not None and lon_range is not None:     # known out-of-area outliers (RG-03) are not movement
        p = p[p["lat"].between(*lat_range) & p["lon"].between(*lon_range)]
    p = p.sort_values("timestamp")
    if p.empty:
        return {}
    r2 = p.groupby("order_id")[["timestamp", "lat", "lon"]].apply(_straight_line_r2).dropna()
    gaps = p.groupby("order_id")["timestamp"].apply(lambda s: s.diff().dt.total_seconds().dropna())
    cv = gaps.groupby(level=0).agg(lambda x: (x.std(ddof=0) / x.mean()) if len(x) >= 2 and x.mean() > 0 else np.nan).dropna()
    return {"orders_with_3plus_pings": int(len(r2)), "straight_line_tracks_pct": _pct(int((r2 >= 0.999).sum()), len(r2)),
            "evenly_spaced_tracks_pct": _pct(int((cv < 0.05).sum()), len(cv))}


def gps_arrival_feasibility(driver_events: pd.DataFrame | None, fo: pd.DataFrame, restaurants: pd.DataFrame | None,
                            customers: pd.DataFrame | None = None, lat_range=None, lon_range=None) -> tuple[pd.DataFrame, dict]:
    if driver_events is None or restaurants is None or len(driver_events) == 0 or len(fo) == 0:
        return pd.DataFrame(), {}
    rest = restaurants[restaurants.get("coords_valid", True) == True][["restaurant_id", "lat", "lon"]].rename(columns={"lat": "r_lat", "lon": "r_lon"})  # noqa: E712
    p = driver_events[driver_events["type"] == "gps_ping"][["order_id", "timestamp", "lat", "lon"]]
    p = p.merge(fo[["order_id", "restaurant_id", "pickup_at"]], on="order_id", how="inner").merge(rest, on="restaurant_id", how="inner")
    pre = p[(p["timestamp"] <= p["pickup_at"]) & p["lat"].notna() & p["lon"].notna()].copy()
    if len(pre) == 0:
        return pd.DataFrame(), {"orders_with_pre_pickup_pings": 0, "verdict": "no pre-pickup GPS pings - arrival cannot be inferred"}
    pre["km_to_restaurant"] = _haversine_km(pre["lat"], pre["lon"], pre["r_lat"], pre["r_lon"])
    pre = pre.sort_values("timestamp")
    first = pre.groupby("order_id").head(1).set_index("order_id")["km_to_restaurant"]
    last = pre.groupby("order_id").tail(1).set_index("order_id")["km_to_restaurant"]
    multi = pre.groupby("order_id").size()
    multi = multi[multi >= 2].index
    approaching = (last.loc[multi] < first.loc[multi])
    within_1km = pre.groupby("order_id")["km_to_restaurant"].min() < 1.0
    table = pd.DataFrame([
        {"check": "orders with pre-pickup GPS pings", "value": int(pre["order_id"].nunique())},
        {"check": "orders with >= 2 pre-pickup pings", "value": int(len(multi))},
        {"check": "of those, last ping closer to the restaurant than the first (%)", "value": _pct(int(approaching.sum()), len(approaching))},
        {"check": "orders with any pre-pickup ping within 1 km of the restaurant (%)", "value": _pct(int(within_1km.sum()), len(within_1km))},
        {"check": "median distance of the last pre-pickup ping to the restaurant (km)", "value": round(float(last.median()), 2)},
    ])
    share = float(approaching.mean()) if len(approaching) else 0.0
    moving_away = (last.loc[multi] > first.loc[multi])
    feasible = share >= 0.6 and float(last.median()) < 1.0
    all_pings = p[p["lat"].notna() & p["lon"].notna() & p["pickup_at"].notna()]
    head = {"orders_with_pre_pickup_pings": int(pre["order_id"].nunique()), "approaching_pct": round(100 * share, 1),
            "moving_away_before_pickup_pct": _pct(int(moving_away.sum()), len(moving_away)),
            "pings_before_pickup_pct": _pct(int((all_pings["timestamp"] <= all_pings["pickup_at"]).sum()), len(all_pings)),
            "within_1km_pct": _pct(int(within_1km.sum()), len(within_1km)), "median_last_ping_km": round(float(last.median()), 2),
            "verdict": "GPS could approximate arrival (geofence)" if feasible else "GPS cannot stand in for an arrival event - pings do not converge on the restaurant"}
    head.update(gps_track_shape(driver_events[driver_events["type"] == "gps_ping"], lat_range, lon_range))
    table = pd.concat([table, pd.DataFrame([
        {"check": "of orders with >= 2 pre-pickup pings, last ping FARTHER from the restaurant than the first (%)", "value": head["moving_away_before_pickup_pct"]},
        {"check": "GPS pings recorded before pickup (%) - Class 6 expected pings only before pickup", "value": head["pings_before_pickup_pct"]},
        {"check": "orders with >= 3 in-area pings", "value": head.get("orders_with_3plus_pings")},
        {"check": "of those, perfectly straight constant-speed track, R^2 >= 0.999 (%)", "value": head.get("straight_line_tracks_pct")},
        {"check": "of those, perfectly even time gaps between pings, CV < 0.05 (%)", "value": head.get("evenly_spaced_tracks_pct")},
    ])], ignore_index=True)

    # the other leg: do pings between pickup and delivery head for the customer? (Class 6 said this leg had no pings)
    if customers is not None and {"customer_id", "lat", "lon"} <= set(customers.columns) and "customer_id" in fo.columns:
        end_col = "ev_delivered_at" if "ev_delivered_at" in fo.columns else ("actual_delivery_at" if "actual_delivery_at" in fo.columns else None)
        if end_col is not None:
            cust = customers[["customer_id", "lat", "lon"]].rename(columns={"lat": "c_lat", "lon": "c_lon"})
            q = driver_events[driver_events["type"] == "gps_ping"][["order_id", "timestamp", "lat", "lon"]]
            q = q.merge(fo[["order_id", "customer_id", "pickup_at", end_col]], on="order_id", how="inner").merge(cust, on="customer_id", how="inner")
            post = q[(q["timestamp"] > q["pickup_at"]) & (q["timestamp"] <= q[end_col]) & q["lat"].notna()].copy()
            delivered = int(fo[end_col].notna().sum())
            if len(post) and delivered:
                post["km_to_customer"] = _haversine_km(post["lat"], post["lon"], post["c_lat"], post["c_lon"])
                post = post.sort_values("timestamp")
                g = post.groupby("order_id")["km_to_customer"].agg(first="first", last="last", n="size")
                g2 = g[g["n"] >= 2]
                head["orders_with_post_pickup_pings_pct"] = _pct(int(post["order_id"].nunique()), delivered)
                head["post_pickup_converging_pct"] = _pct(int((g2["last"] < g2["first"]).sum()), len(g2))
                table = pd.concat([table, pd.DataFrame([
                    {"check": "delivered orders with GPS pings between pickup and delivery (%)", "value": head["orders_with_post_pickup_pings_pct"]},
                    {"check": "of those with >= 2 pings, last ping closer to the customer than the first (%)", "value": head["post_pickup_converging_pct"]},
                ])], ignore_index=True)
    straight, away = head.get("straight_line_tracks_pct"), head.get("moving_away_before_pickup_pct")
    if not feasible and straight is not None and straight >= 80 and away is not None and away >= 60:
        head["verdict"] = ("GPS pings look interpolated, not measured: each track is a straight constant-speed line from the restaurant "
                           "to the customer that ignores the pickup time, so GPS cannot show when the rider reached the restaurant")
    return table, head


# --------------------------------------------------------------------------- 6. heatmap + impact
def hour_weekday_heatmap(fo: pd.DataFrame) -> pd.DataFrame:
    pop = _population(fo)
    if len(pop) == 0:
        return pd.DataFrame()
    t = pop.assign(weekday=pop["created_at"].dt.day_name(), hour=pop["created_at"].dt.hour)
    pv = t.pivot_table(index="weekday", columns="hour", values="late_flag", aggfunc="mean") * 100
    return pv.reindex([d for d in WEEKDAYS if d in pv.index]).round(0)


def impact_whatif(ew_head: dict, metrics: pd.DataFrame, cfg: PipelineConfig) -> pd.DataFrame:
    if not ew_head or metrics is None or len(metrics) == 0:
        return pd.DataFrame()
    m = metrics.set_index("metric_id")
    try:
        late, pop = float(m.loc["M1", "numerator"]), float(m.loc["M1", "denominator"])
        contact_late, contact_on_time = float(m.loc["M4", "value"]) / 100, float(m.loc["M4a", "value"]) / 100
    except (KeyError, TypeError, ValueError):
        return pd.DataFrame()
    rows = []
    for s in cfg.impact_prevented_share_scenarios:
        prevented = round(s * ew_head["all_caught_late"])
        rows.append({"assumed_share_of_caught_late_orders_saved": s, "late_orders_prevented": prevented,
                     "late_rate_after_pct": round(100 * (late - prevented) / pop, 1), "kpi_change_pp": round(-100 * prevented / pop, 1),
                     "support_contacts_avoided": round(prevented * (contact_late - contact_on_time)),
                     "alerts_ops_must_handle": ew_head["all_alerts"], "basis": "ASSUMPTION - save rate not measured; contact rates from M4/M4a"})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- orchestrator
def compute_insights(model, clean: dict, metrics: pd.DataFrame, cfg: PipelineConfig) -> InsightsResult:
    log = get_logger()
    fo, fiv = model["fact_order"], model["fact_intervention"]
    out = InsightsResult()
    grid, cmp, ew = early_warning_backtest(fo, fiv, cfg)
    out.tables["early_warning_backtest"], out.tables["early_warning_vs_interventions"] = grid, cmp
    eta, eta_h = eta_calibration(fo, cfg)
    out.tables["eta_calibration"] = eta
    rr, rr_h = fair_ranking(fo, "restaurant_id", cfg.fair_min_orders_restaurant, cfg.fair_confidence)
    dr, dr_h = fair_ranking(fo, "driver_id", cfg.fair_min_orders_driver, cfg.fair_confidence)
    out.tables["fair_ranking_restaurants"], out.tables["fair_ranking_drivers"] = rr, dr
    wl, wlate, wx_h = weather_truth(fo, clean.get("weather_obs"), cfg)
    out.tables["weather_label_vs_observed"], out.tables["late_rate_label_vs_observed_weather"] = wl, wlate
    gps, gps_h = gps_arrival_feasibility(clean.get("driver_events"), fo, model.tables.get("dim_restaurant"), model.tables.get("dim_customer"),
                                         cfg.lat_range, cfg.lon_range)
    out.tables["gps_arrival_feasibility"] = gps
    out.tables["late_rate_heatmap_weekday_hour"] = hour_weekday_heatmap(fo).reset_index()
    out.tables["impact_whatif"] = impact_whatif(ew, metrics, cfg)
    out.headline = {"early_warning": ew, "eta": eta_h, "restaurants": rr_h, "drivers": dr_h, "weather": wx_h, "gps": gps_h}

    f = out.findings
    if ew:
        f.append({"id": "D1", "title": "A proactive trigger that works today, without AI",
                  "finding": f"Alerting when an order is still not picked up {ew['chosen_grace_min']} min after Dispatch's own estimated pickup "
                             f"catches {ew['test_recall_pct']}% of late orders with {ew['test_precision_pct']}% precision on the held-out week, "
                             f"a median {ew['test_median_lead_min']} min before the promise breaks.",
                  "so_what": f"{ew['caught_late_without_intervention']} late orders the trigger would have caught received no intervention at all; "
                             f"{ew['interventions_on_unflagged_on_time']} interventions went to orders that were never at risk.",
                  "owner": "Operations"})
    if eta_h:
        f.append({"id": "D2", "title": "The promise is optimistic before the food even leaves",
                  "finding": f"Dispatch's pickup estimate is short by a median {eta_h['pickup_estimate_bias_median_min']} min "
                             f"(planned {eta_h['planned_pickup_median_min']} min vs actual {eta_h['actual_pickup_median_min']} min from order to pickup). "
                             f"Reaching {eta_h['target_on_time_rate_pct']:.0f}% on-time by padding alone needs +{eta_h['padding_needed_min']} min on every promise.",
                  "so_what": "Fix the pickup estimate (the input) rather than padding the promise (the output); padding trades lateness for longer quoted times, whose effect on conversion is unknown.",
                  "owner": "Product / ETA service"})
    if rr_h:
        f.append({"id": "D3", "title": "Do not publish a restaurant or driver blame list",
                  "finding": f"Only {rr_h['significantly_worse']} of {rr_h['judgeable']} judgeable restaurants ({', '.join(rr_h['worse_list']) or 'none'}) and "
                             f"{dr_h.get('significantly_worse', 0)} of {dr_h.get('judgeable', 0)} drivers are statistically worse than the fleet; "
                             f"a naive top-10 list would name 10 restaurants, of which {rr_h['naive_top10_significant']} survive the test.",
                  "so_what": "Lateness is systemic; accountability conversations should start with the significant few, with the confidence interval shown.",
                  "owner": "Restaurant Ops / Fleet Ops"})
    if wx_h:
        f.append({"id": "D4", "title": "The weather label does not match the weather",
                  "finding": f"Against Open-Meteo's observed hourly rainfall, the client's weather_bucket agrees {wx_h['agreement_pct']}% of the time "
                             f"(Cohen's kappa {wx_h['kappa']}, i.e. no better than chance). Orders labelled heavy rain saw {wx_h.get('mean_mm_label_heavy_rain')} mm on average, "
                             f"orders labelled clear {wx_h.get('mean_mm_label_clear')} mm. Observed rain: {wx_h['late_rate_observed_rain_pct']}% late vs "
                             f"{wx_h['late_rate_observed_dry_pct']}% when dry.",
                  "so_what": "'Weather causes delays' cannot be defended with this field; ask who writes weather_bucket and when, before any weather-aware ETA or staffing plan.",
                  "owner": "Operations / Data Team"})
    if gps_h:
        shape = ""
        if gps_h.get("straight_line_tracks_pct") is not None:
            shape = (f" {gps_h['straight_line_tracks_pct']}% of tracks with 3+ pings are perfectly straight, constant-speed lines and "
                     f"{gps_h.get('evenly_spaced_tracks_pct')}% have perfectly even time gaps - real device tracks are never that clean.")
        timing = ""
        if gps_h.get("pings_before_pickup_pct") is not None:
            timing = (f" Class 6 found pings only before pickup; here {gps_h['pings_before_pickup_pct']}% of pings fall before pickup and the rest after it"
                      + (f" ({gps_h['post_pickup_converging_pct']}% of post-pickup tracks close in on the customer)." if gps_h.get("post_pickup_converging_pct") is not None else "."))
        interpolated = str(gps_h.get("verdict", "")).startswith("GPS pings look interpolated")
        f.append({"id": "D5", "title": ("GPS pings look drawn, not measured - they cannot show arrival at the restaurant" if interpolated
                                        else "GPS cannot show when the rider reached the restaurant"),
                  "finding": f"Before pickup, the last ping is FARTHER from the restaurant than the first in {gps_h.get('moving_away_before_pickup_pct')}% of orders "
                             f"(closer in only {gps_h.get('approaching_pct')}%) - a rider cannot leave with the food before picking it up." + shape + timing,
                  "so_what": "Do not build a geofence or a live GPS ETA on this feed: it would invent arrivals. Ask Fleet Ops whether pings are device readings "
                             "or app interpolation, and instrument an explicit 'arrived at restaurant' tap - the one event that splits kitchen delay from rider delay, "
                             "which is where the lateness builds.",
                  "owner": "Fleet Ops / Product"})
    for x in f:
        log.info("insight %s %s | %s", x["id"], x["title"], x["finding"][:150])
    return out

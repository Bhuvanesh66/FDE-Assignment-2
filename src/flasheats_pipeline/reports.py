"""Evidence writers: profile, data-quality report, metrics, evidence table, charts, dashboard, manifest."""
from __future__ import annotations

import base64
import io
from pathlib import Path

import pandas as pd

from .cleaning import CleaningReport
from .config import PipelineConfig
from .gate import gate_to_markdown
from .io_utils import df_to_markdown, write_csv, write_json, write_text
from .logging_utils import get_logger
from .metrics import MetricsResult
from .model import ModelBundle
from .profiling import DatasetProfile, profiles_to_markdown
from .rules import RuleResult, results_frame


def _num(v) -> str:
    """Render counts without a trailing .0 and NaN as a dash."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    if isinstance(v, float) and float(v).is_integer():
        return str(int(v))
    return str(v)


def write_profile(profiles: list[DatasetProfile], out: Path) -> None:
    write_json([p.as_dict() for p in profiles], out / "profile" / "profile.json")
    write_text(profiles_to_markdown(profiles), out / "profile" / "profile.md")


def write_data_quality(rep: CleaningReport, results: list[RuleResult], out: Path) -> None:
    rf = results_frame(results)
    write_csv(rf.drop(columns=["extra"]), out / "data_quality_rules.csv")
    write_json({"cleaning": rep.as_dict(), "rules": [r.as_dict() for r in results]}, out / "data_quality_report.json")
    qdir = out / "quarantine"
    for name, df in rep.quarantine.items():
        write_csv(df, qdir / f"{name}.csv")
    for name, df in rep.duplicate_conflicts.items():
        write_csv(df, qdir / f"{name}_duplicate_conflicts.csv")

    lines = ["# Data-quality report", "",
             "Flow: **understand → profile → detect → explain → fix → validate**. Nothing is deleted: corrected values are logged, "
             "unusable records are quarantined with a reason, and every business rule below records what it found and what the pipeline did.", "",
             "## 1. Cleaning actions (representation only)", "", df_to_markdown(rep.actions_frame()), "",
             "## 2. Timestamp parsing", "", df_to_markdown(pd.DataFrame(rep.timestamp_stats)[["column", "total", "null_or_blank", "parsed", "unparseable", "tz_aware_converted", "formats_seen"]]) if rep.timestamp_stats else "_none_", "",
             "## 3. Unexpected category values (retained + flagged, owner decision needed)", ""]
    if rep.unexpected_categories:
        for k, v in rep.unexpected_categories.items():
            lines.append(f"- `{k}`: {v}  → semantic candidates: {rep.semantic_candidates.get(k, {}) or 'none'}")
    else:
        lines.append("_none_")
    lines += ["", "## 4. Quarantine & duplicate conflicts", ""]
    for k, v in rep.quarantine.items():
        lines.append(f"- quarantine/{k}.csv: {len(v)} rows")
    for k, v in rep.duplicate_conflicts.items():
        lines.append(f"- quarantine/{k}_duplicate_conflicts.csv: {len(v)} rows (conflicting columns: {sorted(set(';'.join(v['conflicting_columns']).split(';')) - {''})})")
    if not rep.quarantine and not rep.duplicate_conflicts:
        lines.append("_none_")
    lines += ["", "## 5. Business rules (validation contract)", "",
              "| Rule | Name | Dataset | Status | Violations | Population | Action | Owner | Business reason | Detection | Detail |", "|---|---|---|---|---:|---:|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r.rule.id} | {r.rule.name} | {r.rule.dataset} | **{r.status}** | {r.violations} | {r.population} | {r.rule.action} | {r.rule.owner} | {r.rule.business_reason} | {r.rule.detection} | {str(r.detail).replace('|', '/')} |")
    lines += ["", "## 6. Row counts", "", df_to_markdown(pd.DataFrame([{"dataset": k, "raw_rows": rep.raw_row_counts.get(k), "clean_rows": rep.clean_row_counts.get(k)} for k in rep.raw_row_counts]))]
    write_text("\n".join(lines), out / "data_quality_report.md")


def write_model(model: ModelBundle, processed: Path) -> None:
    import sqlite3
    processed.mkdir(parents=True, exist_ok=True)
    db = processed / "flasheats_model.sqlite"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    try:
        for name, df in model.tables.items():
            write_csv(df, processed / f"{name}.csv")
            d = df.copy()
            for c in d.columns:
                if str(d[c].dtype).startswith("datetime64"):
                    d[c] = d[c].dt.strftime("%Y-%m-%dT%H:%M:%S.%f")
                elif d[c].dtype == bool:
                    d[c] = d[c].astype(int)
                elif d[c].dtype == object:
                    d[c] = d[c].map(lambda v: v if (v is None or isinstance(v, (str, int, float))) else str(v))
            d.to_sql(name, con, index=False, if_exists="replace")
    finally:
        con.close()
    write_json(model.join_checks, processed / "join_checks.json")


def write_metrics(mr: MetricsResult, out: Path) -> None:
    write_csv(mr.metrics, out / "metrics.csv")
    write_json({"headline": mr.headline, "metrics": mr.metrics.to_dict("records"), "checks": mr.checks}, out / "metrics.json")
    write_csv(pd.DataFrame(mr.checks), out / "metric_checks.csv")
    bdir = out / "breakdowns"
    for name, df in mr.breakdowns.items():
        write_csv(df, bdir / f"{name}.csv")
    table = mr.metrics[["metric_id", "metric", "category", "value", "unit", "numerator", "denominator", "population"]].copy()
    table["numerator"] = table["numerator"].map(_num)
    table["denominator"] = table["denominator"].map(_num)
    lines = ["# Metrics", "", df_to_markdown(table), "",
             "## Definitions", ""]
    for r in mr.metrics.itertuples():
        lines.append(f"- **{r.metric_id} {r.metric}** — {r.definition}. Population: {r.population}. KPI link: {r.kpi_link}. {('Notes: ' + r.notes) if r.notes else ''}")
    lines += ["", "## Breakdowns", ""]
    for name, df in mr.breakdowns.items():
        lines += [f"### {name}", "", df_to_markdown(df, max_rows=25), ""]
    write_text("\n".join(lines), out / "metrics.md")


def write_evidence_table(mr: MetricsResult, gate: dict, cfg: PipelineConfig, out: Path, kual: str, ins=None) -> None:
    core = mr.metrics[mr.metrics["metric_id"].isin(["M1", "M2", "M3", "M4", "M5"])]
    lines = ["# Evidence table — FlashEats late-delivery KPI", "", f"Run `{cfg.run_id}` · gate: **{gate['overall_status']}**", "",
             "| # | Metric | Value | Numerator / Denominator | Population | Business question |", "|---|---|---:|---|---|---|"]
    for r in core.itertuples():
        lines.append(f"| {r.metric_id} | {r.metric} | **{r.value} {r.unit}** | {_num(r.numerator)} / {_num(r.denominator)} | {r.population} | {r.kpi_link} |")
    lines += ["", "Supporting metrics (M1a-c, M2a-b, M3a-b, M4a-c, M5a-c) and all breakdowns are in `metrics.md`.", "",
              "## Definition comparison (why one number needs an owner)", "", df_to_markdown(mr.breakdowns["definition_comparison"]), "",
              "## Where delay accumulates", "", df_to_markdown(mr.breakdowns.get("stage_durations_by_outcome", pd.DataFrame())), "",
              "## Interventions (association, not causation)", "", df_to_markdown(mr.breakdowns.get("late_rate_by_intervention_type", pd.DataFrame())), ""]
    if ins is not None and ins.findings:
        lines += ["## Decision layer (beyond the classroom)", "", "| # | Finding | So what | Owner |", "|---|---|---|---|"]
        lines += [f"| {f['id']} {f['title']} | {f['finding']} | {f['so_what']} | {f['owner']} |" for f in ins.findings]
        lines += ["", "Details: `insights/insights.md` · actions: `decision_memo.md`", ""]
    lines += [kual, "", "## Validation gate", "", gate_to_markdown(gate).split("\n", 2)[2]]
    write_text("\n".join(lines), out / "evidence_table.md")


def write_charts(mr: MetricsResult, model: ModelBundle, out: Path) -> list[Path]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        get_logger().warning("matplotlib unavailable - charts skipped (%s)", exc)
        return []
    cdir = out / "charts"
    cdir.mkdir(parents=True, exist_ok=True)
    paths = []

    def bar(df, x, y, title, fname, ylabel):
        if df is None or len(df) == 0:
            return
        fig, ax = plt.subplots(figsize=(7, 3.8))
        ax.bar(df[x].astype(str), df[y], color="#4C72B0")
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="x", rotation=25)
        for i, v in enumerate(df[y]):
            if pd.notna(v):
                ax.annotate(f"{v:.1f}", (i, v), ha="center", va="bottom", fontsize=8)
        fig.tight_layout()
        p = cdir / fname
        fig.savefig(p, dpi=120)
        plt.close(fig)
        paths.append(p)

    bd = mr.breakdowns
    bar(bd.get("late_rate_by_traffic"), "traffic_bucket", "late_rate_pct", "Late rate by traffic bucket", "late_rate_by_traffic.png", "late rate %")
    bar(bd.get("late_rate_by_weather"), "weather_bucket", "late_rate_pct", "Late rate by weather", "late_rate_by_weather.png", "late rate %")
    bar(bd.get("late_rate_by_distance_band"), "distance_band", "late_rate_pct", "Late rate by distance band", "late_rate_by_distance.png", "late rate %")
    bar(bd.get("late_rate_by_hour"), "hour_of_day", "late_rate_pct", "Late rate by hour of order creation", "late_rate_by_hour.png", "late rate %")
    bar(bd.get("late_rate_by_intervention_type"), "intervention_type", "late_rate_pct", "Late rate by intervention type (association only)", "late_rate_by_intervention.png", "late rate %")
    st = bd.get("stage_durations_by_outcome")
    if st is not None and len(st):
        s = st[st["stage_metric"].isin(["dispatch_wait_min", "pickup_wait_min", "transit_min"])]
        fig, ax = plt.subplots(figsize=(7, 3.8))
        w = 0.38
        idx = range(len(s))
        ax.bar([i - w / 2 for i in idx], s["on_time"], w, label="on time", color="#55A868")
        ax.bar([i + w / 2 for i in idx], s["late"], w, label="late", color="#C44E52")
        ax.set_xticks(list(idx))
        ax.set_xticklabels(["dispatch wait", "assign→pickup", "transit"])
        ax.set_ylabel("median minutes")
        ax.set_title("Median stage duration: late vs on-time orders")
        ax.legend()
        fig.tight_layout()
        p = cdir / "stage_durations.png"
        fig.savefig(p, dpi=120)
        plt.close(fig)
        paths.append(p)
    od = bd.get("outcome_distribution")
    if od is not None and len(od):
        bar(od, "outcome_bucket", "orders", "Order outcomes", "outcome_distribution.png", "orders")
    return paths


def write_dashboard(mr: MetricsResult, gate: dict, charts: list[Path], cfg: PipelineConfig, out: Path, visuals: list[Path] | None = None) -> None:
    core = mr.metrics[mr.metrics["metric_id"].isin(["M1", "M2", "M3", "M4", "M5"])]
    tiles = "".join(f"<div class='tile'><div class='v'>{r.value} <span class='u'>{r.unit}</span></div><div class='n'>{r.metric_id} · {r.metric}</div><div class='d'>{r.numerator} / {r.denominator} · {r.population}</div></div>" for r in core.itertuples())
    # the visual story is linked (visuals/ sits next to this file), not embedded, to keep the dashboard small
    story = "".join(f"<figure class='wide'><a href='visuals/{p.name}'><img src='visuals/{p.name}' alt='{p.stem}'></a><figcaption>{p.stem}</figcaption></figure>"
                    for p in (visuals or []))
    story = f"<h2>Visual story</h2>{story}" if story else ""
    imgs = ""
    for p in charts:
        b64 = base64.b64encode(p.read_bytes()).decode()
        imgs += f"<figure><img src='data:image/png;base64,{b64}' alt='{p.stem}'><figcaption>{p.stem}</figcaption></figure>"
    checks = "".join(f"<tr><td>{c['check']}</td><td class='s {c['status']}'>{c['status']}</td><td>{c['evidence']}</td></tr>" for c in gate["checks"])
    html = f"""<!doctype html><html><head><meta charset='utf-8'><title>FlashEats late-delivery KPI</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#222;background:#fafafa}} .tiles{{display:flex;flex-wrap:wrap;gap:12px}}
.tile{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px;min-width:220px;flex:1}} .v{{font-size:28px;font-weight:600}} .u{{font-size:14px;color:#666}}
.n{{font-size:13px;margin-top:4px}} .d{{font-size:11px;color:#777}} figure{{display:inline-block;margin:8px}} img{{max-width:440px;border:1px solid #eee;background:#fff}}
table{{border-collapse:collapse;font-size:13px}} td,th{{border:1px solid #ddd;padding:4px 8px;vertical-align:top}} .PASS{{color:#2a7}} .WARN{{color:#c80}} .FAIL{{color:#c22}} .UNKNOWN{{color:#777}}
.banner{{padding:10px 14px;border-radius:8px;background:#eef;margin-bottom:16px}} figure.wide img{{max-width:920px;width:100%}}</style></head><body>
<h1>FlashEats — late-delivery KPI pipeline</h1><div class='banner'><b>Run</b> {cfg.run_id} · <b>Gate:</b> <span class='{gate['overall_status']}'>{gate['overall_status']}</span> · {gate['publish_decision']}</div>
<div class='tiles'>{tiles}</div>{story}<h2>Charts</h2>{imgs}<h2>Validation gate</h2><table><tr><th>Check</th><th>Status</th><th>Evidence</th></tr>{checks}</table>
<p style='color:#777;font-size:12px'>Generated by the pipeline; all numbers are traceable to output/metrics.csv and output/data_quality_report.md.</p></body></html>"""
    write_text(html, out / "dashboard.html")


def _mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def write_insights(ins, out: Path, cfg: PipelineConfig, charts: bool = True) -> list[Path]:
    """Decision-layer tables (output/insights/*.csv), headline json and charts."""
    idir = out / "insights"
    for name, df in ins.tables.items():
        if df is not None and len(df):
            write_csv(df, idir / f"{name}.csv")
    write_json({"headline": ins.headline, "findings": ins.findings}, idir / "insights.json")
    lines = ["# Decision layer — beyond the classroom", "",
             "Transparent, non-ML analyses that turn the model into actions the client can take now. Every number is recomputed on each run.", ""]
    for f in ins.findings:
        lines += [f"## {f['id']} · {f['title']}", "", f"**Finding.** {f['finding']}", "", f"**So what.** {f['so_what']}", "", f"**Owner.** {f['owner']}", ""]
    for name, df in ins.tables.items():
        if df is not None and len(df):
            lines += [f"### {name}", "", df_to_markdown(df, max_rows=20), ""]
    write_text("\n".join(lines), idir / "insights.md")
    if not charts:
        return []
    try:
        plt = _mpl()
    except Exception:  # pragma: no cover
        return []
    cdir = out / "charts"
    cdir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    ew = ins.tables.get("early_warning_backtest")
    if ew is not None and len(ew):
        t = ew[ew["split"] == "test"]
        chosen = ins.headline.get("early_warning", {}).get("chosen_grace_min")
        fig, ax = plt.subplots(figsize=(7, 3.8))
        ax.plot(t["grace_min"], t["precision_pct"], marker="o", label="precision (alert was right)", color="#4C72B0")
        ax.plot(t["grace_min"], t["recall_pct"], marker="o", label="recall (late orders caught)", color="#C44E52")
        ax.plot(t["grace_min"], t["alert_rate_pct"], marker=".", linestyle="--", label="orders alerted", color="#8C8C8C")
        if chosen is not None:
            ax.axvline(chosen, color="#55A868", linestyle=":", label=f"chosen on 1-{cfg.ew_train_until_day} Aug: {chosen} min")
        ax.set_xlabel("minutes after Dispatch's estimated pickup, still not picked up")
        ax.set_ylabel("% (held-out week)")
        ax.set_title("Early-warning trigger, backtested on the held-out week")
        ax.legend(fontsize=8)
        fig.tight_layout()
        p = cdir / "early_warning_tradeoff.png"
        fig.savefig(p, dpi=120)
        plt.close(fig)
        paths.append(p)
    eta = ins.tables.get("eta_calibration")
    if eta is not None and len(eta):
        fig, ax = plt.subplots(figsize=(7, 3.8))
        for label, g in eta.groupby("eta_model_version"):
            ax.plot(g["padding_min"], g["late_rate_pct"], marker="o", label=label, linewidth=2.2 if label == "all versions" else 1)
        ax.axhline(100 - cfg.target_on_time_rate_pct, color="#55A868", linestyle=":", label=f"target: {cfg.target_on_time_rate_pct:.0f}% on time")
        ax.set_xlabel("minutes added to every promised ETA")
        ax.set_ylabel("late rate %")
        ax.set_title("What padding the promise would do (a lever, not a fix)")
        ax.legend(fontsize=8)
        fig.tight_layout()
        p = cdir / "eta_padding_curve.png"
        fig.savefig(p, dpi=120)
        plt.close(fig)
        paths.append(p)
    rr = ins.tables.get("fair_ranking_restaurants")
    if rr is not None and len(rr):
        from .insights import wilson_interval
        fleet = ins.headline["restaurants"]["fleet_late_rate_pct"]
        fig, ax = plt.subplots(figsize=(7, 3.8))
        colors = rr["verdict"].map({"worse than fleet (significant)": "#C44E52", "better than fleet (significant)": "#55A868"}).fillna("#8C8C8C")
        ax.scatter(rr["orders"], rr["late_rate_pct"], c=colors, s=22)
        ns = list(range(max(3, int(rr["orders"].min())), int(rr["orders"].max()) + 2))
        lo = [100 * wilson_interval(fleet / 100 * n, n, cfg.fair_confidence)[0] for n in ns]      # expected count at the fleet rate
        hi = [100 * wilson_interval(fleet / 100 * n, n, cfg.fair_confidence)[1] for n in ns]
        ax.plot(ns, lo, color="#8C8C8C", linestyle="--", linewidth=1)
        ax.plot(ns, hi, color="#8C8C8C", linestyle="--", linewidth=1, label=f"{cfg.fair_confidence:.0%} band around the fleet rate")
        ax.axhline(fleet, color="#4C72B0", linewidth=1, label=f"fleet late rate {fleet}%")
        for r in rr[rr["verdict"] == "worse than fleet (significant)"].itertuples():
            ax.annotate(r.restaurant_id, (r.orders, r.late_rate_pct), fontsize=8, xytext=(3, 3), textcoords="offset points")
        ax.set_xlabel("orders (validated population)")
        ax.set_ylabel("late rate %")
        ax.set_title("Restaurants: funnel plot (only red dots are out of line)")
        ax.legend(fontsize=8)
        fig.tight_layout()
        p = cdir / "restaurant_funnel_plot.png"
        fig.savefig(p, dpi=120)
        plt.close(fig)
        paths.append(p)
    hm = ins.tables.get("late_rate_heatmap_weekday_hour")
    if hm is not None and len(hm):
        mat = hm.set_index("weekday")
        fig, ax = plt.subplots(figsize=(8, 3.6))
        im = ax.imshow(mat.values.astype(float), aspect="auto", cmap="RdYlGn_r", vmin=20, vmax=90)
        ax.set_yticks(range(len(mat.index)))
        ax.set_yticklabels(mat.index)
        ax.set_xticks(range(len(mat.columns)))
        ax.set_xticklabels([str(c) for c in mat.columns])
        ax.set_xlabel("hour order was created")
        ax.set_title("Late rate % by weekday and hour")
        fig.colorbar(im, ax=ax, label="late %")
        fig.tight_layout()
        p = cdir / "late_rate_heatmap.png"
        fig.savefig(p, dpi=120)
        plt.close(fig)
        paths.append(p)
    wl = ins.tables.get("weather_label_vs_observed")
    if wl is not None and len(wl):
        fig, ax = plt.subplots(figsize=(7, 3.6))
        ax.bar(wl["weather_bucket"], wl["observed_rain_share_pct"], color=["#4C72B0", "#C44E52", "#DD8452"][: len(wl)])
        for i, v in enumerate(wl["observed_rain_share_pct"]):
            ax.annotate(f"{v:.0f}%", (i, v), ha="center", va="bottom", fontsize=9)
        ax.set_ylabel("% of orders in an hour that actually rained")
        ax.set_title("Client weather label vs observed rainfall (Open-Meteo)")
        ax.set_ylim(0, 100)
        fig.tight_layout()
        p = cdir / "weather_label_vs_observed.png"
        fig.savefig(p, dpi=120)
        plt.close(fig)
        paths.append(p)
    return paths


def write_decision_memo(mr: MetricsResult, ins, gate: dict, cfg: PipelineConfig, out: Path) -> None:
    """One-page Situation → Complication → Resolution memo with owned, measurable actions."""
    h = mr.headline
    ew = ins.headline.get("early_warning", {}) if ins else {}
    eta = ins.headline.get("eta", {}) if ins else {}
    rr = ins.headline.get("restaurants", {}) if ins else {}
    wx = ins.headline.get("weather", {}) if ins else {}
    gps = ins.headline.get("gps", {}) if ins else {}
    m = mr.metrics.set_index("metric_id")

    def val(mid):
        return m.loc[mid, "value"] if mid in m.index else None
    lines = [
        "# Decision memo — FlashEats late deliveries", "",
        f"**For:** VP Operations · **cc:** Support Lead, Dispatch, Fleet Ops, Restaurant Ops, Product · **Run:** `{cfg.run_id}` · **Data gate:** {gate['overall_status']}", "",
        "## Situation", "",
        f"FlashEats promises an ETA at checkout. In August, **{h.get('late_delivery_rate_pct')}%** of {h.get('validated_population')} validated deliveries missed it "
        f"(median {h.get('median_lateness_min')} min late; {val('M1b')}% were more than {cfg.meaningful_late_threshold_min:g} min late). "
        f"Leadership's \"56%\" is right for the dashboard definition ({h.get('historical_definition_pct')}%).", "",
        "## Complication", "",
        f"- The delay is created **before pickup**, not on the road: {h.get('share_lateness_before_pickup_pct')}% of overrun minutes on late orders accrue before the driver collects the food."
        + (f" Dispatch's own pickup estimate is short by a median {eta.get('pickup_estimate_bias_median_min')} min." if eta else ""),
        f"- Late orders turn into support contacts {val('M4')}% of the time (vs {val('M4a')}% on time); today's interventions reach {val('M5')}% of orders with no visible effect on the late rate.",
        "- The data cannot say whether the kitchen or the rider owns the pre-pickup delay: no *arrived at restaurant* event exists"
        + (f". GPS cannot fill the gap: before pickup, pings move AWAY from the restaurant in {gps.get('moving_away_before_pickup_pct')}% of orders"
           + (f", and {gps.get('straight_line_tracks_pct')}% of tracks are perfectly straight constant-speed lines, so the pings look interpolated rather than measured."
              if gps.get("straight_line_tracks_pct") is not None else ".")
           if gps else "."),
    ]
    if wx:
        lines.append(f"- The weather explanation does not hold up: the client's weather label agrees with observed rainfall only {wx.get('agreement_pct')}% of the time (kappa {wx.get('kappa')}).")
    lines += ["", "## Resolution — recommended actions", "",
              "| # | Action | Owner | Evidence | How we will know |", "|---|---|---|---|---|"]
    if ew:
        lines.append(f"| 1 | Switch on a **pickup-overrun trigger**: alert ops when an order is not picked up {ew['chosen_grace_min']} min after Dispatch's estimated pickup, and intervene on those orders first | Operations | held-out week: {ew['test_precision_pct']}% precision, {ew['test_recall_pct']}% recall, median {ew['test_median_lead_min']} min before the promise breaks; {ew['caught_late_without_intervention']} caught late orders had no intervention | M5 coverage of alerted orders ↑, M1 ↓ over 4 weeks |")
    if eta:
        lines.append(f"| 2 | **Recalibrate Dispatch's pickup estimate** (+{eta.get('pickup_estimate_bias_median_min')} min median bias) instead of padding promises; padding to {eta.get('target_on_time_rate_pct'):.0f}% on time would need +{eta.get('padding_needed_min')} min on every order | Product / ETA service | ETA calibration table | promise error (delay_min) median → 0 without longer quotes |")
    lines += [
        "| 3 | **Instrument** an *arrived at restaurant* tap and make the delivery timestamp mandatory on the `delivered` transition | Fleet Ops / Product | TS-04 (37 missing), D5 | pre-pickup delay split into kitchen vs rider; TS-04 = 0 |",
        "| 4 | **Sign off the definition of late** (any delay vs > 10 min) and name the KPI owner | VP Operations | KPI-01, definition comparison | gate check moves from UNKNOWN to PASS |",
    ]
    if rr:
        lines.append(f"| 5 | Restaurant accountability only for the **statistically significant** few ({', '.join(rr.get('worse_list', [])) or 'none'}), with confidence intervals shown | Restaurant Ops | fair ranking: {rr.get('significantly_worse')} of {rr.get('judgeable')} judgeable restaurants | no restaurant penalised on < {cfg.fair_min_orders_restaurant} orders |")
    if wx:
        lines.append("| 6 | Stop using `weather_bucket` to explain delays until Operations confirms who writes it and when | Operations / Data Team | WX-01 | label agrees with observed weather (kappa ≥ 0.4) |")
    wi = ins.tables.get("impact_whatif") if ins else None
    if wi is not None and len(wi):
        lines += ["", "## What acting on action 1 could be worth (assumption-labelled)", "", df_to_markdown(wi.drop(columns=["basis"])), "",
                  "_The save rate is an assumption, not a measurement; run the trigger as a switchback pilot (alternate days) to measure it._"]
    lines += ["", "## Decision on the AI delay predictor", "",
              "**Not yet.** Revisit when (a) the arrival event has been live for four weeks, (b) delivery-timestamp completeness is above 99 %, and "
              "(c) the rule-based trigger above is in production, because it becomes the **baseline any model must beat** on the same held-out test.", "",
              f"_Generated by the pipeline from run `{cfg.run_id}`; every number traces to output/metrics.csv, output/insights/ and output/validation_gate.md._"]
    write_text("\n".join(lines), out / "decision_memo.md")


def write_gate(gate: dict, out: Path) -> None:
    write_json(gate, out / "validation_gate.json")
    write_text(gate_to_markdown(gate), out / "validation_gate.md")

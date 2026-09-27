"""FlashEats decision dashboard (Streamlit).

    streamlit run app/dashboard.py

Reads only what the pipeline wrote (output/runs/<run_id>/ and data/processed/),
so every number on screen is traceable to a run. The two simulators recompute
the early-warning trigger and the ETA padding live from the modelled order table,
using the same functions as the pipeline, so stakeholders can try their own
policy values before they change config/pipeline.yaml.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from flasheats_pipeline.insights import _alert_stats, wilson_interval  # noqa: E402

OUTPUT = Path(os.getenv("FLASHEATS_OUTPUT_DIR", ROOT / "output"))
PROCESSED = Path(os.getenv("FLASHEATS_PROCESSED_DIR", ROOT / "data" / "processed"))
STATUS_ICON = {"PASS": "🟢", "WARN": "🟠", "FAIL": "🔴", "UNKNOWN": "⚪"}
TS_COLS = ["created_at", "promised_eta", "pickup_at", "actual_delivery_at", "assigned_at", "estimated_pickup_at"]


def runs() -> list[str]:
    root = OUTPUT / "runs"
    if not root.is_dir():
        return []
    ok = [d.name for d in root.iterdir() if d.is_dir() and (d / "metrics.csv").exists()]
    return sorted(ok, reverse=True)


@st.cache_data(show_spinner=False)
def read_csv(path: str, mtime: float) -> pd.DataFrame:
    return pd.read_csv(path)


def load(path: Path) -> pd.DataFrame | None:
    return read_csv(str(path), path.stat().st_mtime) if path.exists() else None


@st.cache_data(show_spinner=False)
def fact_order(path: str, mtime: float) -> pd.DataFrame:
    df = pd.read_csv(path)
    for c in TS_COLS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def main() -> None:
    st.set_page_config(page_title="FlashEats late deliveries", page_icon="🛵", layout="wide")
    st.title("FlashEats — late deliveries: evidence and decisions")
    available = runs()
    if not available:
        st.error(f"No completed pipeline runs in {OUTPUT / 'runs'}. Run `python run_pipeline.py --start-api` first.")
        st.stop()
    run_id = st.sidebar.selectbox("Pipeline run", available, index=0)
    rdir = OUTPUT / "runs" / run_id
    manifest = json.loads((rdir / "run_manifest.json").read_text(encoding="utf-8")) if (rdir / "run_manifest.json").exists() else {}
    gate = json.loads((rdir / "validation_gate.json").read_text(encoding="utf-8")) if (rdir / "validation_gate.json").exists() else {}
    st.sidebar.markdown(f"**Gate:** {STATUS_ICON.get(gate.get('overall_status'), '')} {gate.get('overall_status', 'n/a')}")
    st.sidebar.caption(f"status {manifest.get('status', 'n/a')} · {manifest.get('duration_s', '?')} s · policy {Path(manifest.get('config', {}).get('config_file') or 'defaults').name}")

    tabs = st.tabs(["📊 Executive", "🧭 Decision memo", "⏱️ Early-warning simulator", "📐 ETA calibration", "⚖️ Fair ranking",
                    "🌧️ Weather check", "🧪 Data quality", "🔎 Order explorer", "🗂️ Run history"])
    metrics = load(rdir / "metrics.csv")

    with tabs[0]:
        st.subheader(f"Run {run_id}")
        st.info(gate.get("publish_decision", ""))
        if metrics is not None:
            core = metrics[metrics["metric_id"].isin(["M1", "M2", "M3", "M4", "M5"])]
            cols = st.columns(len(core))
            for c, r in zip(cols, core.itertuples()):
                c.metric(f"{r.metric_id} · {r.metric}", f"{r.value} {r.unit}")
        c1, c2 = st.columns(2)
        for col, img, cap in [(c1, "stage_durations.png", "Where the time goes: late vs on-time"), (c2, "late_rate_heatmap.png", "Late rate by weekday and hour")]:
            p = rdir / "charts" / img
            if p.exists():
                col.image(str(p), caption=cap, width="stretch")
        bd = load(rdir / "breakdowns" / "definition_comparison.csv")
        if bd is not None:
            st.markdown("**One number, four definitions**")
            st.dataframe(bd, hide_index=True, width="stretch")

    with tabs[1]:
        memo = rdir / "decision_memo.md"
        st.markdown(memo.read_text(encoding="utf-8") if memo.exists() else "_decision memo not produced in this run_")

    fo_path = PROCESSED / "fact_order.csv"
    fo = fact_order(str(fo_path), fo_path.stat().st_mtime) if fo_path.exists() else None
    pop = None if fo is None else fo[fo["kpi_population"].astype(bool) & fo["estimated_pickup_at"].notna() & fo["pickup_at"].notna()]

    with tabs[2]:
        st.markdown("Alert when an order is **still not picked up _k_ minutes after Dispatch's own estimated pickup**. "
                    "Pick _k_ and see what ops would get. Computed live on the latest modelled orders.")
        if pop is None or pop.empty:
            st.warning("data/processed/fact_order.csv not found")
        else:
            k = st.slider("grace minutes (k)", 0, 40, 10, 1)
            split = st.radio("evaluate on", ["held-out week (22–28 Aug)", "all of August"], horizontal=True)
            d = pop[pop["created_at"].dt.day > 21] if split.startswith("held") else pop
            if d.empty:
                st.info("This data has no orders after 21 Aug, so there is no held-out week - showing all orders instead.")
                d = pop
            s = _alert_stats(d, k)
            c = st.columns(5)
            c[0].metric("orders alerted", f"{s['alerts']} ({s['alert_rate_pct']}%)")
            c[1].metric("precision", f"{s['precision_pct']}%")
            c[2].metric("late orders caught", f"{s['caught_late']} ({s['recall_pct']}%)")
            c[3].metric("false alerts", s["false_alerts"])
            c[4].metric("median warning before breach", f"{s['median_lead_min']} min")
            grid = pd.DataFrame([_alert_stats(d, g) for g in range(0, 41, 5)]).set_index("grace_min")[["precision_pct", "recall_pct", "alert_rate_pct"]]
            st.line_chart(grid)
            st.caption("Policy value used by the pipeline lives in config/pipeline.yaml → early_warning. The pipeline chooses k on 1–21 Aug only.")

    with tabs[3]:
        if fo is None:
            st.warning("data/processed/fact_order.csv not found")
        else:
            vp = fo[fo["kpi_population"].astype(bool)]
            pad = st.slider("minutes added to every promised ETA", 0, 40, 0, 1)
            late = float((vp["delay_min"] > pad).mean() * 100)
            c = st.columns(3)
            c[0].metric("late rate after padding", f"{late:.1f}%", delta=f"{late - float((vp['delay_min'] > 0).mean() * 100):.1f} pp", delta_color="inverse")
            c[1].metric("Dispatch pickup estimate bias (median)", f"{vp['pickup_overrun_min'].median():.1f} min")
            c[2].metric("median promised window today", f"{vp['promised_window_min'].median():.0f} min")
            st.warning("Padding hides lateness by quoting longer times; its effect on conversion is unknown. The recommended lever is fixing the pickup estimate.")
            t = load(rdir / "insights" / "eta_calibration.csv")
            if t is not None:
                st.dataframe(t, hide_index=True, width="stretch")

    with tabs[4]:
        who = st.radio("entity", ["restaurants", "drivers"], horizontal=True)
        t = load(rdir / "insights" / f"fair_ranking_{who}.csv")
        p = rdir / "charts" / "restaurant_funnel_plot.png"
        if who == "restaurants" and p.exists():
            st.image(str(p), width="stretch")
        if t is not None:
            only = st.checkbox("show only entities that are significantly different from the fleet", value=True)
            view = t[t["verdict"].str.contains("significant")] if only else t
            st.dataframe(view, hide_index=True, width="stretch")
            st.caption("Wilson 95% interval. 'in_naive_top10' shows who a simple 'most late orders' list would have blamed.")

    with tabs[5]:
        p = rdir / "charts" / "weather_label_vs_observed.png"
        if p.exists():
            st.image(str(p), width="stretch")
        for f in ["weather_label_vs_observed.csv", "late_rate_label_vs_observed_weather.csv"]:
            t = load(rdir / "insights" / f)
            if t is not None:
                st.dataframe(t, hide_index=True, width="stretch")
        wx = manifest.get("inputs", {}).get("external_weather", {})
        st.caption(f"Source: Open-Meteo archive, mode={wx.get('mode')}, hours={wx.get('hours')}. Raw response preserved under data/raw/{run_id}/external/.")

    with tabs[6]:
        if gate:
            g = pd.DataFrame(gate["checks"])
            g.insert(0, " ", g["status"].map(STATUS_ICON))
            st.dataframe(g, hide_index=True, width="stretch")
        rules = load(rdir / "data_quality_rules.csv")
        if rules is not None:
            pick = st.multiselect("rule status", ["FAIL", "WARN", "UNKNOWN", "PASS"], default=["FAIL", "WARN", "UNKNOWN"])
            st.dataframe(rules[rules["status"].isin(pick)][["rule_id", "rule", "status", "violations", "population", "action", "owner", "detail"]], hide_index=True, width="stretch")
        ledger = load(rdir / "reconciliation_ledger.csv")
        if ledger is not None:
            st.markdown("**Record ledger — nothing disappears silently**")
            st.dataframe(ledger, hide_index=True, width="stretch")
        q = rdir / "quarantine"
        for f in sorted(q.glob("*.csv")) if q.exists() else []:
            with st.expander(f"quarantine / {f.name}"):
                st.dataframe(load(f), hide_index=True, width="stretch")

    with tabs[7]:
        ev_path = PROCESSED / "fact_event.csv"
        if fo is None or not ev_path.exists():
            st.warning("modelled tables not found")
        else:
            examples = {"late + support + intervention": None}
            oj = load(PROCESSED / "order_journey.csv")
            if oj is not None:
                ex = oj[oj["frustrated_intervened_still_late"].astype(bool)]["order_id"]
                examples["late + support + intervention"] = ex.iloc[0] if len(ex) else None
            default = examples["late + support + intervention"] or fo["order_id"].iloc[0]
            oid = st.text_input("order id", value=default).strip().upper()
            row = fo[fo["order_id"] == oid]
            if row.empty:
                st.error("unknown order id")
            else:
                r = row.iloc[0]
                c = st.columns(4)
                c[0].metric("outcome", r["outcome_bucket"])
                c[1].metric("delay vs promise", f"{r['delay_min']} min" if pd.notna(r["delay_min"]) else "unknown")
                c[2].metric("pre-pickup overrun", f"{r['pickup_overrun_min']} min" if pd.notna(r["pickup_overrun_min"]) else "n/a")
                c[3].metric("dq flags", r["dq_flags"] if isinstance(r["dq_flags"], str) and r["dq_flags"] else "none")
                ev = load(ev_path)
                st.dataframe(ev[ev["order_id"] == oid].sort_values("event_time"), hide_index=True, width="stretch")

    with tabs[8]:
        hist = []
        for rid in available:
            mp = OUTPUT / "runs" / rid / "run_manifest.json"
            if mp.exists():
                m = json.loads(mp.read_text(encoding="utf-8"))
                h = m.get("stages", {}).get("metrics", {}).get("headline", {})
                hist.append({"run": rid, "status": m.get("status"), "gate": m.get("stages", {}).get("gate", {}).get("overall"),
                             "late_rate_pct": h.get("late_delivery_rate_pct"), "population": h.get("validated_population"), "seconds": m.get("duration_s")})
        st.dataframe(pd.DataFrame(hist), hide_index=True, width="stretch")
        cmp = rdir / "run_comparison.md"
        if cmp.exists():
            st.markdown(cmp.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()

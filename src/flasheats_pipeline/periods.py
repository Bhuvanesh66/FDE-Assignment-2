"""Partitioned, repeatable operation: one full pipeline run per period + a cross-period scorecard.

A client does not run a KPI pipeline once; it runs it every week or month and must be able to
say, for each period, *published or refused, and why*. ``--weekly`` splits the data span into
7-day windows (1-7, 8-14, 15-21, 22-28 Aug for the classroom data). Each window is a complete run
with its own raw snapshot, gate, evidence folder (``output/periods/<window>/``) and processed
tables (``data/processed/periods/<window>/``). The scorecard then shows the KPI trend, week-over-week
drift, the status of every period and a partition check (every order in exactly one period).
"""
from __future__ import annotations

import sqlite3
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path

import pandas as pd

from .config import PipelineConfig
from .ingest.replay import read_sql_extract
from .io_utils import df_to_markdown, read_json, write_csv, write_json, write_text
from .logging_utils import configure_logging
from .timestamps import parse_timestamps

STATUS = {"COMPLETED": "PUBLISHED", "GATE_FAILED": "REFUSED", "FAILED": "FAILED"}


def data_span(cfg: PipelineConfig) -> tuple[pd.Timestamp, pd.Timestamp]:
    if cfg.replay_run_id:
        created = read_sql_extract(cfg.raw_root / cfg.replay_run_id, "orders_extract")["created_at"]
    else:
        con = sqlite3.connect(f"file:{cfg.db_path.as_posix()}?mode=ro", uri=True)
        try:
            created = pd.read_sql_query("SELECT created_at FROM orders", con, dtype="object")["created_at"]
        finally:
            con.close()
    ts, _ = parse_timestamps(created, "orders.created_at", cfg.source_timezone)
    ts = ts.dropna()
    if ts.empty:
        raise ValueError("no parseable order creation times - cannot define periods")
    return ts.min().normalize(), ts.max().normalize()


def weekly_periods(cfg: PipelineConfig, days: int = 7) -> list[tuple[str, str]]:
    first, last = data_span(cfg)
    out, start = [], first
    while start <= last:
        end = min(start + pd.Timedelta(days=days - 1), last)
        out.append((start.date().isoformat(), end.date().isoformat()))
        start += pd.Timedelta(days=days)
    return out


def run_periods(base: PipelineConfig, periods: list[tuple[str, str]]) -> dict:
    from .pipeline import MockApiProcess, run_pipeline      # local import: pipeline imports this module's siblings
    root_out = base.output_dir
    rows, runs = [], []
    api = MockApiProcess(base.mock_api_script, base.api_base_url) if (base.start_mock_api and not base.replay_run_id) else nullcontext()
    with api:
        for start, end in periods:
            label = f"{start}_{end}"
            cfg = replace(base, period_start=start, period_end=end, period_label=label, run_id=f"{base.run_id}_{label}",
                          output_dir=root_out / "periods" / label, start_mock_api=False)
            run = run_pipeline(cfg)
            runs.append(run)
            h = run.headline or {}
            ins = ((run.manifest.get("stages") or {}).get("insights") or {}).get("headline", {})
            rows.append({"period": label, "run_id": cfg.run_id, "status": STATUS.get(run.status, run.status),
                         "gate": (run.gate or {}).get("overall_status"), "orders": ((run.manifest.get("stages") or {}).get("clean") or {}).get("rows", {}).get("orders"),
                         "validated_population": h.get("validated_population"), "late_orders": h.get("late_orders"),
                         "late_rate_pct": h.get("late_delivery_rate_pct"), "median_lateness_min": h.get("median_lateness_min"),
                         "share_before_pickup_pct": h.get("share_lateness_before_pickup_pct"),
                         "support_contact_late_pct": h.get("support_contact_rate_late_pct"), "intervention_coverage_pct": h.get("intervention_coverage_pct"),
                         "pickup_estimate_bias_min": (ins.get("eta") or {}).get("pickup_estimate_bias_median_min"),
                         "error": run.error or ""})
    configure_logging(root_out / "periods" / "scorecard.log")
    card = pd.DataFrame(rows)
    card["wow_change_pp"] = pd.to_numeric(card["late_rate_pct"], errors="coerce").diff().round(2)
    card["drift_flag"] = card["wow_change_pp"].abs() > base.kpi_drift_alert_pp
    published = card[card["status"] == "PUBLISHED"]
    # partition check: every order of the source lands in exactly one period
    total_orders = None
    try:
        ct = read_json(root_out / "periods" / card.iloc[0]["period"] / "runs" / card.iloc[0]["run_id"] / "run_manifest.json")
        rows_ct = (ct.get("inputs", {}).get("control_totals") or {}).get("rows", [])
        total_orders = next((r["observed"] for r in rows_ct if r["control"] == "unique_orders"), None)
    except Exception:
        pass
    in_periods = int(pd.to_numeric(card["orders"], errors="coerce").fillna(0).sum())
    partition = {"orders_in_periods": in_periods, "unique_orders_in_source": total_orders,
                 "status": "UNKNOWN" if total_orders is None else ("PASS" if in_periods == int(total_orders) else "FAIL")}
    # the periods must add back up to the full-period run published in output/ (same population, same late orders)
    full = {}
    try:
        full = ((read_json(root_out / "run_manifest.json").get("stages") or {}).get("metrics") or {}).get("headline") or {}
    except Exception:
        full = {}
    if full and len(published) == len(card):
        pop_sum = int(pd.to_numeric(card["validated_population"], errors="coerce").fillna(0).sum())
        late_sum = int(pd.to_numeric(card["late_orders"], errors="coerce").fillna(0).sum())
        partition["full_run_population"], partition["full_run_late_orders"] = full.get("validated_population"), full.get("late_orders")
        partition["periods_population"], partition["periods_late_orders"] = pop_sum, late_sum
        partition["adds_up_to_full_run"] = (pop_sum == full.get("validated_population")) and (late_sum == full.get("late_orders"))
        if not partition["adds_up_to_full_run"]:
            partition["status"] = "FAIL"
    overall = "COMPLETE" if len(published) == len(card) else ("PARTIAL" if len(published) else "NONE_PUBLISHED")
    write_csv(card, root_out / "scorecard.csv")
    write_json({"overall": overall, "periods": card.to_dict("records"), "partition_check": partition, "drift_threshold_pp": base.kpi_drift_alert_pp},
               root_out / "scorecard.json")
    chart = _chart(card, root_out, base) if base.write_charts else None
    lines = ["# Period scorecard — late-delivery KPI, one validated run per period", "",
             f"**Overall: {overall}** · {len(published)} of {len(card)} periods published · partition check **{partition['status']}** "
             f"({in_periods} orders across periods vs {total_orders} unique orders in the source"
             + (f"; the periods add up to the full-period run: {partition['periods_population']} validated deliveries and {partition['periods_late_orders']} late orders "
                f"vs {partition['full_run_population']} and {partition['full_run_late_orders']} → {'yes' if partition['adds_up_to_full_run'] else 'NO'}"
                if "adds_up_to_full_run" in partition else "") + ")", "",
             df_to_markdown(card[["period", "status", "gate", "orders", "validated_population", "late_orders", "late_rate_pct", "wow_change_pp", "drift_flag",
                                  "median_lateness_min", "share_before_pickup_pct", "support_contact_late_pct", "pickup_estimate_bias_min"]]), "",
             f"Drift flag: the late rate moved more than {base.kpi_drift_alert_pp:g} pp versus the previous period (policy: `monitoring.kpi_drift_alert_pp`).",
             "Each period's full evidence (gate, data-quality report, metrics, decision memo) is in `output/periods/<period>/`.", ""]
    if chart:
        lines += [f"![weekly late rate](charts/{chart.name})", ""]
    refused = card[card["status"] != "PUBLISHED"]
    if len(refused):
        lines += ["## Periods not published", ""] + [f"- {r.period}: {r.status} ({r.gate}) {r.error}" for r in refused.itertuples()]
    write_text("\n".join(lines), root_out / "scorecard.md")
    return {"overall": overall, "scorecard": card, "partition_check": partition, "runs": runs}


def _chart(card: pd.DataFrame, root_out: Path, cfg: PipelineConfig):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # pragma: no cover
        return None
    d = card[card["status"] == "PUBLISHED"]
    if d.empty:
        return None
    fig, ax = plt.subplots(figsize=(7, 3.6))
    x = [p.replace("_", "\n") for p in d["period"]]
    ax.plot(x, d["late_rate_pct"], marker="o", color="#C44E52", label="late rate %")
    ax.plot(x, d["share_before_pickup_pct"], marker="s", color="#4C72B0", label="% of lateness before pickup")
    for i, v in enumerate(d["late_rate_pct"]):
        ax.annotate(f"{v:.1f}", (i, v), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8)
    ax.set_ylim(0, 105)
    ax.set_title("Weekly runs: KPI and where the delay sits")
    ax.legend(fontsize=8)
    fig.tight_layout()
    p = root_out / "charts" / "weekly_scorecard.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, dpi=120)
    plt.close(fig)
    return p

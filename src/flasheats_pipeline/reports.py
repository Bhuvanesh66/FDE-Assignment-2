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


def write_evidence_table(mr: MetricsResult, gate: dict, cfg: PipelineConfig, out: Path, kual: str) -> None:
    core = mr.metrics[mr.metrics["metric_id"].isin(["M1", "M2", "M3", "M4", "M5"])]
    lines = ["# Evidence table — FlashEats late-delivery KPI", "", f"Run `{cfg.run_id}` · gate: **{gate['overall_status']}**", "",
             "| # | Metric | Value | Numerator / Denominator | Population | Business question |", "|---|---|---:|---|---|---|"]
    for r in core.itertuples():
        lines.append(f"| {r.metric_id} | {r.metric} | **{r.value} {r.unit}** | {_num(r.numerator)} / {_num(r.denominator)} | {r.population} | {r.kpi_link} |")
    lines += ["", "Supporting metrics (M1a-c, M2a-b, M3a-b, M4a-c, M5a-c) and all breakdowns are in `metrics.md`.", "",
              "## Definition comparison (why one number needs an owner)", "", df_to_markdown(mr.breakdowns["definition_comparison"]), "",
              "## Where delay accumulates", "", df_to_markdown(mr.breakdowns.get("stage_durations_by_outcome", pd.DataFrame())), "",
              "## Interventions (association, not causation)", "", df_to_markdown(mr.breakdowns.get("late_rate_by_intervention_type", pd.DataFrame())), "",
              kual, "", "## Validation gate", "", gate_to_markdown(gate).split("\n", 2)[2]]
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


def write_dashboard(mr: MetricsResult, gate: dict, charts: list[Path], cfg: PipelineConfig, out: Path) -> None:
    core = mr.metrics[mr.metrics["metric_id"].isin(["M1", "M2", "M3", "M4", "M5"])]
    tiles = "".join(f"<div class='tile'><div class='v'>{r.value} <span class='u'>{r.unit}</span></div><div class='n'>{r.metric_id} · {r.metric}</div><div class='d'>{r.numerator} / {r.denominator} · {r.population}</div></div>" for r in core.itertuples())
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
.banner{{padding:10px 14px;border-radius:8px;background:#eef;margin-bottom:16px}}</style></head><body>
<h1>FlashEats — late-delivery KPI pipeline</h1><div class='banner'><b>Run</b> {cfg.run_id} · <b>Gate:</b> <span class='{gate['overall_status']}'>{gate['overall_status']}</span> · {gate['publish_decision']}</div>
<div class='tiles'>{tiles}</div><h2>Charts</h2>{imgs}<h2>Validation gate</h2><table><tr><th>Check</th><th>Status</th><th>Evidence</th></tr>{checks}</table>
<p style='color:#777;font-size:12px'>Generated by the pipeline; all numbers are traceable to output/metrics.csv and output/data_quality_report.md.</p></body></html>"""
    write_text(html, out / "dashboard.html")


def write_gate(gate: dict, out: Path) -> None:
    write_json(gate, out / "validation_gate.json")
    write_text(gate_to_markdown(gate), out / "validation_gate.md")

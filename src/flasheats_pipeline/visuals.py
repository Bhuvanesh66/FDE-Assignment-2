"""Visual evidence: the pipeline draws its own story from the run's outputs.

Every figure reads the files a run just wrote (metrics, gate, ledger, insights, ingestion
manifest, processed tables), so a picture can never drift away from the evidence behind it.
Figures are written to ``<run>/visuals/NN_name.png`` and published with the run.

The numbering follows the story told in the demo video:
    01 overview · 02-03 sources + retrieval · 04-05 validation · 06-08 workflow + model
    09-11 metrics + K/U/A/L · 12-13 dependability · 14 judgement call · 15 what is different

    python make_visuals.py        # redraw from the published output/ (e.g. after --replay / --weekly)
"""
from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd

INK = "#1F2933"
C = {"blue": "#2F5D9E", "green": "#2E7D4F", "red": "#B83227", "orange": "#C2691A", "purple": "#5E4B99", "gray": "#5F6B76", "teal": "#1F7A7A"}
FILL = {"blue": "#E7EEF8", "green": "#E4F2E9", "red": "#F9E4E1", "orange": "#FCEFE2", "purple": "#EDEAF6", "gray": "#EEF0F2", "teal": "#E2F1F1", "white": "#FFFFFF"}
STATUS_COLOR = {"PASS": "green", "WARN": "orange", "FAIL": "red", "UNKNOWN": "gray"}


# --------------------------------------------------------------------------- drawing helpers
def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.titleweight": "bold"})
    return plt


def _canvas(w: float, h: float):
    """A blank drawing board where 1 data unit = 0.1 inch."""
    plt = _plt()
    fig = plt.figure(figsize=(w, h), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w * 10)
    ax.set_ylim(0, h * 10)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    return fig, ax


def _title(ax, w, h, title, subtitle=None):
    ax.text(w * 5, h * 10 - 3.0, title, ha="center", va="top", fontsize=18, weight="bold", color=INK)
    if subtitle:
        ax.text(w * 5, h * 10 - 8.6, subtitle, ha="center", va="top", fontsize=11, color=C["gray"])


def _wrap(text, width: int) -> str:
    return "\n".join(textwrap.wrap(str(text), width)) if text else ""


def _bwrap(text, width: int) -> str:
    """Wrap into balanced lines (no one-word orphan on the last line)."""
    text = str(text or "")
    if len(text) <= width:
        return text
    n = -(-len(text) // width)
    return _wrap(text, -(-len(text) // n) + 3)


def _rbox(ax, x, y, w, h, color="blue", fill=None, dashed=False, lw=1.8):
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=1.6", fc=fill or FILL[color], ec=C[color],
                                lw=lw, linestyle="--" if dashed else "-"))


def _box(ax, x, y, w, h, title=None, lines=(), color="blue", title_size=11.5, text_size=9.2, wrap=34, dashed=False, align="center", fill=None):
    """Rounded box with a bold title and wrapped lines flowing from the top."""
    _rbox(ax, x, y, w, h, color, fill=fill, dashed=dashed)
    cx = x + w / 2 if align == "center" else x + 1.4
    top = y + h - 1.6
    if title:
        t = _wrap(title, wrap + 4) if len(title) > wrap + 4 else title
        ax.text(cx, top, t, ha=align, va="top", fontsize=title_size, weight="bold", color=C[color])
        top -= 2.3 * (t.count("\n") + 1) * title_size / 11.5 + 1.1
    for ln in lines:
        t = _wrap(ln, wrap)
        ax.text(cx, top, t, ha=align, va="top", fontsize=text_size, color=INK, linespacing=1.25)
        top -= 1.95 * (t.count("\n") + 1) * text_size / 9.2 + 0.75


def _cbox(ax, x, y, w, h, text, color="blue", size=10.0, wrap=40, weight="normal", fill=None, dashed=False, tcolor=None):
    """Rounded box with text centred both ways."""
    _rbox(ax, x, y, w, h, color, fill=fill, dashed=dashed)
    ax.text(x + w / 2, y + h / 2, _bwrap(text, wrap), ha="center", va="center", fontsize=size, color=tcolor or INK, weight=weight, linespacing=1.3)


def _arrow(ax, p1, p2, color="gray", lw=2.0, text=None, text_offset=(0, 1.4), fontsize=8.8, style="-|>", rad=0.0, ls="-", alpha=1.0):
    ax.annotate("", xy=p2, xytext=p1, arrowprops=dict(arrowstyle=style, color=C[color], lw=lw, shrinkA=2, shrinkB=2, linestyle=ls, alpha=alpha,
                                                      connectionstyle=f"arc3,rad={rad}", mutation_scale=16))
    if text:
        ax.text((p1[0] + p2[0]) / 2 + text_offset[0], (p1[1] + p2[1]) / 2 + text_offset[1], text, ha="center", va="bottom",
                fontsize=fontsize, color=C[color], weight="bold")


def _pill(ax, x, y, status, w=9.5, h=2.6, size=9.6):
    from matplotlib.patches import FancyBboxPatch
    col = STATUS_COLOR.get(status, "gray")
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1,rounding_size=1.2", fc=C[col], ec=C[col]))
    ax.text(x + w / 2, y + h / 2, status, ha="center", va="center", fontsize=size, weight="bold", color="white")


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor="white", metadata={"Software": None})
    _plt().close(fig)
    return path


# --------------------------------------------------------------------------- context (everything read from the run's own files)
def _read_json(p: Path, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_csv(p: Path, **kw) -> pd.DataFrame | None:
    try:
        return pd.read_csv(p, **kw)
    except Exception:
        return None


def _rows(p: Path) -> int | None:
    try:
        with open(p, "r", encoding="utf-8") as f:
            return max(0, sum(1 for _ in f) - 1)
    except Exception:
        return None


def load_context(run_out: Path, raw_dir: Path | None, processed_dir: Path, published_root: Path | None = None) -> dict:
    run_out, processed_dir = Path(run_out), Path(processed_dir)
    root = Path(published_root) if published_root else run_out
    m = _read_json(run_out / "metrics.json", {}) or {}
    gate = _read_json(run_out / "validation_gate.json", {}) or {}
    return {
        "run_id": gate.get("run_id", ""),
        "headline": m.get("headline", {}),
        "metrics": pd.DataFrame(m.get("metrics", [])),
        "checks": pd.DataFrame(m.get("checks", [])),
        "gate": gate,
        "insights": _read_json(run_out / "insights" / "insights.json", {}) or {},
        "rules": _read_csv(run_out / "data_quality_rules.csv"),
        "ledger": _read_csv(run_out / "reconciliation_ledger.csv"),
        "stage": _read_csv(run_out / "breakdowns" / "stage_durations_by_outcome.csv"),
        "outcomes": _read_csv(run_out / "breakdowns" / "outcome_distribution.csv"),
        "definitions": _read_csv(run_out / "breakdowns" / "definition_comparison.csv"),
        "ew": _read_csv(run_out / "insights" / "early_warning_backtest.csv"),
        "ingestion": (_read_json(Path(raw_dir) / "ingestion_manifest.json", {}) or {}) if raw_dir else {},
        "raw_dir": Path(raw_dir) if raw_dir else None,
        "join_checks": _read_json(processed_dir / "join_checks.json", []) or [],
        "tables": {t: _rows(processed_dir / f"{t}.csv") for t in ["dim_customer", "dim_restaurant", "dim_driver", "fact_order", "fact_event",
                                                                 "fact_interaction", "fact_intervention", "order_journey"]},
        "processed_dir": processed_dir,
        "replay": _read_json(root / "replay_proof.json"),
        "scorecard": _read_json(root / "scorecard.json"),
        "comparison": _read_json(run_out / "run_comparison.json", {}) or {},
    }


def _metric(ctx, mid, col="value"):
    m = ctx["metrics"]
    if m is None or m.empty or mid not in set(m["metric_id"]):
        return None
    v = m.set_index("metric_id").loc[mid, col]
    return None if pd.isna(v) else v


def _fmt(v, nd=1):
    if v is None:
        return "n/a"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if np.isnan(f):
        return "n/a"
    return f"{int(f):,}" if f.is_integer() else f"{f:,.{nd}f}"


def _rule(ctx, rid, col="violations"):
    r = ctx["rules"]
    if r is None or rid not in set(r["rule_id"]):
        return None
    return r.set_index("rule_id").loc[rid, col]


def _check_passed(ctx, prefix: str) -> bool:
    ch = ctx["checks"]
    if ch is None or ch.empty:
        return False
    hit = ch[ch["check"].str.startswith(prefix)]
    return len(hit) > 0 and bool((hit["status"] == "PASS").all())


def _gate_evidence(ctx, prefix: str) -> str:
    for c in ctx["gate"].get("checks", []):
        if str(c.get("check", "")).startswith(prefix):
            return str(c.get("evidence", ""))
    return ""


def _ledger_raw(ctx, dataset="orders"):
    led = ctx["ledger"]
    if led is None or dataset not in set(led["dataset"]):
        return None
    return int(led.set_index("dataset").loc[dataset, "raw_rows"])


def _outcome_counts(ctx) -> pd.Series:
    oc = ctx["outcomes"]
    return oc.set_index("outcome_bucket")["orders"] if oc is not None and len(oc) else pd.Series(dtype=int)


def _ins(ctx, key) -> dict:
    return ctx["insights"].get("headline", {}).get(key, {}) or {}


def _in_population(s: pd.Series) -> pd.Series:
    return s.map(lambda v: str(v).lower() in ("true", "1"))


# --------------------------------------------------------------------------- 01 the whole path on one page
def fig_trustworthy_path(ctx, out: Path) -> Path:
    W, H = 17, 6.3
    fig, ax = _canvas(W, H)
    h, ing = ctx["headline"], ctx["ingestion"] or {}
    api = ing.get("dispatch_api", {}) or {}
    ct_rows = (ing.get("control_totals") or {}).get("rows", [])
    ct_match = sum(1 for r in ct_rows if r.get("status") == "MATCH")
    n_rules = 0 if ctx["rules"] is None else len(ctx["rules"])
    joins = ctx["join_checks"]
    ew, eta = _ins(ctx, "early_warning"), _ins(ctx, "eta")
    both = _check_passed(ctx, "SQL metric layer") and _check_passed(ctx, "independent reconciliation vs client")
    decision = str(ctx["gate"].get("publish_decision", "")).split(":")[0].lower()
    _title(ax, W, H, "A trustworthy path from client systems to a business decision",
           f"FlashEats late deliveries · run {ctx['run_id']} · data gate: {ctx['gate'].get('overall_status', 'n/a')} → {decision}")
    stages = [
        ("1  CLIENT SYSTEMS", "gray", ["7 client systems", "+ Open-Meteo as an outside check", "SQL · REST API · CSV · JSON"], None),
        ("2  RETRIEVE", "blue", [f"{_fmt(api.get('records_fetched'))}/{_fmt(api.get('expected_total'))} API records, {_fmt(api.get('pages_fetched'))} pages, "
                                 f"{_fmt(api.get('retries'))} retries",
                                 f"{ct_match}/{len(ct_rows)} client control totals match" if ct_rows else "no control totals published",
                                 "every raw input kept + SHA-256"], "STOP if a count differs from the client's control total"),
        ("3  VALIDATE", "orange", [f"{n_rules} business rules, each with an owner", f"{_fmt(_ledger_raw(ctx))} rows → {_fmt(h.get('validated_population'))} trusted deliveries",
                                   "nothing silently fixed or dropped"], "STOP if a defect is over its tolerance"),
        ("4  MODEL", "purple", ["one row per order (the order journey)", f"{sum(1 for j in joins if j.get('row_count_preserved'))}/{len(joins)} joins keep the row count",
                                f"{_fmt(ctx['tables'].get('fact_event'))} lifecycle events"], "STOP if the one-row-per-order grain breaks"),
        ("5  MEASURE", "red", [f"late rate {_fmt(h.get('late_delivery_rate_pct'), 2)} % (M1)", f"{_fmt(h.get('share_lateness_before_pickup_pct'))} % of lateness before pickup",
                               "SQL = pandas = client's own file" if both else "independent checks"], "STOP if two methods disagree"),
        ("6  DECIDE", "green", [f"trigger: {_fmt(ew.get('test_precision_pct'))} % precise, ~{_fmt(ew.get('test_median_lead_min'), 0)} min warning" if ew else "decision layer",
                                f"fix the pickup estimate ({_fmt(eta.get('pickup_estimate_bias_median_min'))} min short)" if eta else "",
                                "AI predictor: not yet (rule = baseline)"], "the owner signs off the definition of 'late'"),
    ]
    bw, gap, x0, y0, bh = 24.2, 4.0, 2.6, 19.0, 27.0
    for i, (title, col, lines, guard) in enumerate(stages):
        x = x0 + i * (bw + gap)
        _box(ax, x, y0, bw, bh, title, [f"✓ {ln}" for ln in lines if ln], col, title_size=12.5, text_size=10.2, wrap=25, align="left")
        if guard:
            stop = guard.startswith("STOP")
            _cbox(ax, x, y0 - 9.4, bw, 6.8, guard, "red" if stop else "gray", size=9.2, wrap=27, weight="bold", tcolor=C["red"] if stop else C["gray"])
        if i < len(stages) - 1:
            _arrow(ax, (x + bw + 0.4, y0 + bh / 2), (x + bw + gap - 0.4, y0 + bh / 2), "gray", lw=2.6)
    rp, sc = ctx.get("replay") or {}, ctx.get("scorecard") or {}
    rerun = []
    if rp:
        rerun.append(f"replay from preserved raw: {rp.get('outputs_identical')}/{rp.get('outputs_compared')} outputs byte-identical")
    if sc:
        pc = sc.get("partition_check", {})
        rerun.append(f"{len(sc.get('periods', []))} weekly runs add up to the month" + (" ✓" if pc.get("adds_up_to_full_run") else f" ({pc.get('status')})"))
    rerun.append("drift alert vs the last run · policy file with owners · automated tests")
    ax.text(W * 5, 4.2, "RE-RUNNABLE TRUST:  " + "   ·   ".join(rerun), ha="center", va="center", fontsize=10, color=C["teal"], weight="bold")
    return _save(fig, out / "01_trustworthy_path.png")


# --------------------------------------------------------------------------- 02 source map
def fig_source_map(ctx, out: Path) -> Path:
    W, H = 17, 10.8
    fig, ax = _canvas(W, H)
    api = (ctx["ingestion"] or {}).get("dispatch_api", {}) or {}
    oc = _outcome_counts(ctx)
    raw, uniq = _ledger_raw(ctx), (int(oc.sum()) if len(oc) else None)
    cov = re.search(r"\(([\d.]+)%\)", _gate_evidence(ctx, "Freshness"))
    _title(ax, W, H, "Source map: business question → information needed → system that holds it",
           "Session 5 · where the truth lives, who owns it, what one row means, and the gap that shapes every conclusion")
    qs = [("Q1  How big is the late problem?", "promise · delivery time · status", [0, 1]),
          ("Q2  Where in the lifecycle is time lost?", "assigned · est. pickup · picked up · delivered · kitchen status", [0, 1, 2, 3]),
          ("Q3  How do customers react?", "ETA views · support opened · tickets", [4, 5]),
          ("Q4  What does ops do, and does it help?", "interventions · reassignments", [6, 1]),
          ("Q5  Is 'weather causes delay' true?", "observed rainfall by hour vs the client's label", [7, 0])]
    dup = f" ({raw - uniq} duplicated)" if raw and uniq and raw > uniq else ""
    srcs = [("Orders DB (SQLite)", f"SQL · Data Team · 1 row = 1 order{dup}", "trusted: promise + delivery time", "green"),
            (f"Dispatch API (REST, {_fmt(api.get('pages_fetched'))} pages)", "API · Dispatch · 1 record = 1 order", "trusted: assignment + final driver", "green"),
            ("Driver app events (JSON)", "file · Fleet Ops · 1 row = 1 event", "no 'arrived' event · GPS looks drawn", "orange"),
            ("Restaurant status feed (CSV)", "file · Restaurant Ops · 1 row = 1 update", f"covers {cov.group(1)} % of orders" if cov else "partial coverage", "orange"),
            ("Customer app actions (CSV)", "file · Product · 1 row = 1 action", "trusted for behaviour", "green"),
            ("Support tickets (CSV)", "file · Support Lead · 1 row = 1 ticket", "the customer's view, not the event log", "orange"),
            ("Interventions log (CSV)", "file · Support/Dispatch/Ops · 1 row = 1 action", "disagrees with Dispatch", "orange"),
            ("Open-Meteo archive (public API)", "API · independent · 1 row = 1 hour", "checks the client's weather label", "teal")]
    qx, qw, qh = 3, 54, 11.5
    sx, sw, sh = 104, 63, 8.3
    s_top = 91.0
    s_y = [s_top - sh - i * 9.3 for i in range(len(srcs))]
    q_step = (s_top - qh - s_y[-1]) / (len(qs) - 1)
    q_y = [s_top - qh - i * q_step for i in range(len(qs))]
    ax.text(qx, 93.2, "5 BUSINESS QUESTIONS", fontsize=10.5, color=C["blue"], weight="bold", va="bottom")
    ax.text(sx, 93.2, f"{len(srcs)} SOURCES  ·  SQL + 2 REST APIs + CSV + JSON", fontsize=10.5, color=C["gray"], weight="bold", va="bottom")
    for (q, need, _), y in zip(qs, q_y):
        _box(ax, qx, y, qw, qh, q, [f"needs: {need}"], "blue", title_size=11.5, text_size=9.8, wrap=64, align="left")
    for (name, meta, trust, col), y in zip(srcs, s_y):
        _box(ax, sx, y, sw, sh, name, [f"{meta}  ·  {trust}"], col, title_size=10.8, text_size=8.9, wrap=96, align="left")
    for (_, _, targets), yq in zip(qs, q_y):
        for k, t in enumerate(targets):
            if k == 0:
                _arrow(ax, (qx + qw + 0.8, yq + qh / 2), (sx - 0.8, s_y[t] + sh / 2), "blue", lw=2.2)
            else:
                _arrow(ax, (qx + qw + 0.8, yq + qh / 2), (sx - 0.8, s_y[t] + sh / 2), "gray", lw=1.3, ls="--", alpha=0.75)
    ax.text(W * 5, 14.0, "+ the client's own reference files: four teams' definitions of 'late' (JSON) and their outcome file (CSV), used only to cross-check",
            ha="center", fontsize=9.6, color=C["gray"])
    _box(ax, 3, 2.6, 164, 8.4, "GAP  ·  no 'driver arrived at restaurant' event in any source",
         ["so the time before pickup, where the lateness builds, cannot be split into kitchen delay and rider delay → instrument it"],
         "red", title_size=11.5, text_size=10, wrap=170)
    return _save(fig, out / "02_source_map.png")


# --------------------------------------------------------------------------- 03 retrieval proof
def fig_retrieval(ctx, out: Path) -> Path:
    plt = _plt()
    ing = ctx["ingestion"] or {}
    api = ing.get("dispatch_api", {}) or {}
    fig = plt.figure(figsize=(17, 6.8), dpi=150)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.2, 1.25, 0.85], left=0.05, right=0.985, top=0.8, bottom=0.17, wspace=0.34)
    fig.suptitle("Retrieval: prove we got ALL of it, and keep the raw evidence", fontsize=18, weight="bold", color=INK, y=0.975)
    fig.text(0.5, 0.885, "Session 5 · SQL + REST API + CSV + JSON · completeness is proved against the client's own control totals, not assumed",
             ha="center", fontsize=11, color=C["gray"])
    ax = fig.add_subplot(gs[0])
    sizes = []
    rd = ctx.get("raw_dir")
    if rd and (rd / "api").exists():
        for p in sorted((rd / "api").glob("dispatch_page_*.json")):
            try:
                sizes.append(len(json.loads(p.read_text(encoding="utf-8"))["payload"]["data"]))
            except Exception:
                sizes.append(0)
    retried = {e.get("page"): e.get("status", e.get("error")) for e in api.get("http_errors", [])}
    pages = list(range(1, len(sizes) + 1))
    ax.bar(pages, sizes, color=[C["orange"] if p in retried else C["blue"] for p in pages], width=0.72)
    for k, (p, why) in enumerate(sorted(retried.items())):
        if p in pages:
            ax.annotate(f"page {p}: HTTP {why}\nretried ✓", (p, sizes[p - 1]), xytext=(0, 8 + 34 * (k % 2)), textcoords="offset points", ha="center",
                        fontsize=9.2, color=C["orange"], weight="bold", arrowprops=dict(arrowstyle="-", color=C["orange"], lw=0.8))
    ax.set_ylim(0, max(sizes + [1]) * 1.65)
    ax.set_xticks(pages)
    ax.tick_params(axis="x", labelsize=8.5)
    ax.set_xlabel("API page")
    ax.set_ylabel("records on the page")
    ax.set_title(f"Dispatch API: {sum(sizes):,} records = server total {_fmt(api.get('expected_total'))}", fontsize=12)
    ax.spines[["top", "right"]].set_visible(False)

    ax2 = fig.add_subplot(gs[1])
    rows = (ing.get("control_totals") or {}).get("rows", [])
    if rows:
        names = [r["control"].replace("_", " ") for r in rows]
        pub = [r["published"] for r in rows]
        obs = [r["observed"] or 0 for r in rows]
        y = np.arange(len(rows))
        ax2.barh(y + 0.2, pub, height=0.38, color="#B8C7DE", label="the client says exists")
        ax2.barh(y - 0.2, obs, height=0.38, color=C["green"], label="we retrieved")
        for i, r in enumerate(rows):
            ok = r["status"] == "MATCH"
            ax2.text(max(pub[i], obs[i]) * 1.3, i, f"{obs[i]:,} / {pub[i]:,} " + ("✓" if ok else f"✗ {r['status']}"), va="center", fontsize=10,
                     color=C["green"] if ok else C["red"], weight="bold")
        ax2.set_yticks(list(y))
        ax2.set_yticklabels(names, fontsize=10)
        ax2.set_xscale("log")
        ax2.set_xlim(8, max(pub) * 60)
        ax2.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
        ax2.legend(fontsize=9.5, loc="upper center", bbox_to_anchor=(0.45, -0.02), ncol=2, frameon=False)
    ax2.set_title("Our counts vs the client's control totals", fontsize=12)
    ax2.spines[["top", "right", "bottom"]].set_visible(False)

    ax3 = fig.add_subplot(gs[2])
    ax3.axis("off")
    ax3.set_xlim(0, 10)
    ax3.set_ylim(0, 10)
    n_sql = len((ing.get("sql") or {}).get("extracts", []))
    n_files = sum(1 for f in (ing.get("files") or {}).values() if f.get("status") == "ok")
    n_pages = len((api.get("raw_page_sha256") or {})) or api.get("pages_fetched") or 0
    n_wx = 1 if (ing.get("external_weather") or {}).get("raw_sha256") else 0
    server = ing.get("orders_extract_vs_server_count") or {}
    ax3.text(0, 9.7, "Raw evidence kept (SHA-256)", fontsize=12, weight="bold", color=INK)
    same = server.get("extracted") is not None and server.get("extracted") == server.get("server_count")
    items = [(f"{n_sql} SQL extracts + their queries", "blue"), (f"{n_files} files (CSV / JSON), byte for byte", "blue"),
             (f"{n_pages} raw API pages, as received", "blue"), (f"{n_wx} observed-weather response", "teal"),
             (f"orders extract: {_fmt(server.get('extracted'))} rows\n   = the server's own COUNT(*)" + (" ✓" if same else " ✗"), "green" if same else "red"),
             ("--replay rebuilds everything from these", "green")]
    y = 8.3
    for i, (t, col) in enumerate(items):
        ax3.text(0.1, y, "■ " + t, fontsize=10.2, color=C[col], weight="bold" if i >= 4 else "normal", va="top", linespacing=1.3)
        y -= 0.62 * (t.count("\n") + 1) + 0.5
    ax3.text(0.1, 0.2, f"= {n_sql + n_files + n_pages + n_wx} preserved artefacts", fontsize=11.5, weight="bold", color=INK)
    return _save(fig, out / "03_retrieval_proof.png")


# --------------------------------------------------------------------------- 04 KPI funnel
def fig_kpi_funnel(ctx, out: Path) -> Path:
    plt = _plt()
    h = ctx["headline"]
    oc = _outcome_counts(ctx)
    raw = _ledger_raw(ctx)
    uniq = int(oc.sum()) if len(oc) else None
    cancelled, other = int(oc.get("cancelled", 0)), int(oc.get("other_status", 0))
    missing, excluded = int(oc.get("unknown_missing_timestamp", 0)), int(oc.get("excluded_dq_rule", 0))
    delivered = (uniq or 0) - cancelled - other
    steps = [("raw order rows (orders DB)", raw, "gray", ""),
             ("unique orders", uniq, "gray", f"−{(raw or 0) - (uniq or 0)} duplicate rows (first kept, the conflict quarantined)"),
             ("delivered orders", delivered, "blue", f"−{cancelled} cancelled (nothing to be late)" + (f", −{other} other status" if other else "")),
             ("with a delivery time", delivered - missing, "blue", f"−{missing} no delivery time: outcome UNKNOWN, never guessed"),
             ("trusted deliveries = KPI population", h.get("validated_population"), "purple",
              f"−{excluded} impossible timestamps (promise before order, delivery before pickup)"),
             ("LATE deliveries", h.get("late_orders"), "red", f"= {_fmt(h.get('late_delivery_rate_pct'), 2)} % late (M1)")]
    fig, ax = plt.subplots(figsize=(16, 7.2), dpi=150)
    fig.subplots_adjust(left=0.2, right=0.985, top=0.83, bottom=0.1)
    fig.suptitle(f"From {_fmt(raw)} raw rows to a number you can defend", fontsize=18, weight="bold", color=INK, y=0.97)
    fig.text(0.5, 0.885, "Session 6 · every exclusion is a named business rule, and nothing disappears without a reason (the ledger balances)",
             ha="center", fontsize=11, color=C["gray"])
    vals = [s[1] or 0 for s in steps]
    mx = max(vals) if vals else 1
    ys = list(range(len(steps)))[::-1]
    ax.barh(ys, vals, color=[C[s[2]] for s in steps], height=0.62)
    for yv, s, v in zip(ys, steps, vals):
        ax.text(v + mx * 0.012, yv, f"{v:,}", va="center", fontsize=12.5, weight="bold", color=INK)
        if s[3]:
            late = s[2] == "red"
            ax.text((v + mx * 0.1) if late else mx * 1.16, yv, s[3], va="center", fontsize=10.5 if late else 10,
                    color=C["red"] if late else C["gray"], weight="bold" if late else "normal")
    ax.set_yticks(ys)
    ax.set_yticklabels([s[0] for s in steps], fontsize=11.5)
    ax.set_xlim(0, mx * 2.2)
    ax.spines[["top", "right", "bottom"]].set_visible(False)
    ax.set_xticks([])
    d = ctx["definitions"]
    if d is not None and not d.empty:
        dash = d[d["definition"].str.startswith("Data Team")]
        if len(dash):
            r = dash.iloc[0]
            fig.text(0.2, 0.035, f"Leadership's '56 %' is the dashboard definition: {int(r.late)} of {int(r.population)} = {r.late_rate_pct} %. "
                                 "Same data, a different population: the definition is printed next to every number.", fontsize=10, color=C["blue"])
    return _save(fig, out / "04_kpi_funnel.png")


# --------------------------------------------------------------------------- 05 validation gate
GATE_NAMES = [("Retrieval", "Retrieval completeness"), ("Business grain", "Business grain (one row per order)"),
              ("Timestamp", "Timestamp chronology & completeness"), ("KPI definition", "KPI definition ownership"),
              ("Category", "Category semantics"), ("Cross-source", "Cross-source mapping"), ("Freshness", "Freshness (restaurant feed)"),
              ("Metric sanity", "Metric sanity & independent checks"), ("Independent", "Weather label vs observed rain"),
              ("Run-over-run", "Run-over-run stability")]


def _gate_name(check: str) -> str:
    return next((short for key, short in GATE_NAMES if check.startswith(key)), check[:40])


def _gate_line(check: str, evidence: str, ctx) -> str:
    ing = ctx["ingestion"] or {}
    api = ing.get("dispatch_api", {}) or {}
    ct = (ing.get("control_totals") or {}).get("rows", [])
    if check.startswith("Retrieval"):
        return (f"{_fmt(api.get('records_fetched'))}/{_fmt(api.get('expected_total'))} API records · "
                f"{sum(1 for r in ct if r.get('status') == 'MATCH')}/{len(ct)} client control totals · raw kept with hashes")
    if check.startswith("Business grain"):
        n = re.search(r"cleaning: (\d+)", evidence)
        return f"{n.group(1) if n else '?'} duplicated order rows fixed (first kept) · the conflicting copies are quarantined"
    if check.startswith("Timestamp"):
        return (f"{_fmt(_rule(ctx, 'TS-01'))} promises before the order + {_fmt(_rule(ctx, 'TS-02'))} deliveries before pickup excluded · "
                f"{_fmt(_rule(ctx, 'TS-04'))} outcomes UNKNOWN")
    if check.startswith("KPI definition"):
        n = re.search(r"(\d+) stakeholder definitions", evidence)
        return f"{n.group(1) if n else 'several'} teams define 'late' differently and no owner is named → the definition is printed with the number"
    if check.startswith("Category"):
        fixes = sum(int(x) for x in re.findall(r"fixes=(\d+)", evidence))
        return f"{fixes} spelling/case fixes · 'handoff' and 'eta_issue' kept apart until their owners confirm the meaning"
    if check.startswith("Cross-source"):
        return "the orders table keeps the OLD driver after a reassignment → Dispatch is used for the final driver"
    if check.startswith("Freshness"):
        cov = re.search(r"\(([\d.]+)%\)", evidence)
        late = re.search(r">15 min after pickup=(\d+)", evidence)
        return (f"the status feed covers {cov.group(1) if cov else '?'} % of orders; {late.group(1) if late else '?'} 'ready' updates arrive after pickup "
                f"→ fine for weekly analytics, not for live ETAs")
    if check.startswith("Metric sanity"):
        n = 0 if ctx["checks"].empty else len(ctx["checks"])
        p = 0 if ctx["checks"].empty else int((ctx["checks"]["status"] == "PASS").sum())
        return f"{p}/{n} checks pass: SQL = pandas · = client's own outcome file · ledgers balance · joins keep rows"
    if check.startswith("Independent"):
        w = _ins(ctx, "weather")
        return f"the client's weather label vs real rain: kappa {w.get('kappa')} (chance) → don't blame weather with this field" if w else evidence[:110]
    if check.startswith("Run-over-run"):
        cmp = ctx.get("comparison") or {}
        if not cmp.get("baseline_run"):
            return "first published run: nothing to compare with yet"
        kpi = next((x for x in cmp.get("headline", []) if x.get("metric") == "late_delivery_rate_pct"), None)
        fp = cmp.get("fingerprints") or {}
        parts = [f"KPI moved {kpi['delta']:+.2f} pp vs the last published run" if kpi and kpi.get("delta") is not None else "KPI not comparable",
                 "no rule got worse" if "no rule got worse" in str(cmp.get("summary")) else "some rules got worse"]
        if fp.get("compared"):
            parts.append(f"{fp.get('identical')}/{fp.get('compared')} outputs byte-identical")
        return " · ".join(parts)
    return evidence[:115]


def fig_gate(ctx, out: Path) -> Path:
    gate = ctx["gate"]
    checks = gate.get("checks", [])
    n, row = max(len(checks), 1), 10.0
    W, H = 17, (25 + (n - 1) * row + 18.6) / 10
    fig, ax = _canvas(W, H)
    _title(ax, W, H, "Validation gate: is this data safe enough for THIS decision?",
           "Session 6 · PASS / WARN / FAIL / UNKNOWN · a FAIL anywhere stops publication automatically")
    first = H * 10 - 25
    for i, c in enumerate(checks):
        yy = first - i * row
        _pill(ax, 3, yy, c["status"], w=12.5, h=7.0, size=10)
        ax.text(18.5, yy + 3.5, _gate_name(c["check"]), va="center", fontsize=11.5, weight="bold", color=INK)
        ax.text(63, yy + 3.5, _gate_line(c["check"], str(c.get("evidence", "")), ctx), va="center", fontsize=10.2, color=INK)
    col = STATUS_COLOR.get(gate.get("overall_status"), "gray")
    head, _, rest = str(gate.get("publish_decision", "")).partition(":")
    _box(ax, 3, 2.6, W * 10 - 6, 12, f"OVERALL: {gate.get('overall_status')}  →  {head}", [rest.strip()], col, title_size=12.5, text_size=10.4, wrap=175)
    return _save(fig, out / "05_validation_gate.png")


# --------------------------------------------------------------------------- 06 one order, seven systems
LANES = [("order_platform", "Orders DB", "Data Team", "blue"), ("dispatch_api", "Dispatch API", "Dispatch", "blue"),
         ("restaurant_status_feed", "Restaurant feed", "Restaurant Ops", "orange"), ("driver_app", "Driver app", "Fleet Ops", "purple"),
         ("customer_app", "Customer app", "Product", "teal"), ("support_desk", "Support desk", "Support Lead", "red"),
         ("interventions_log", "Interventions log", "Ops teams", "green")]


def _event_label(t: str) -> str:
    for p in ("DRIVER_APP_", "APP_", "RESTAURANT_", "INTERVENTION_"):
        if t.startswith(p):
            t = t[len(p):]
            break
    return t.replace("_", " ").lower().replace("eta", "ETA")


def _pick_order(fe: pd.DataFrame, fo: pd.DataFrame) -> str | None:
    """A real late order that touches as many systems as possible (deterministic choice)."""
    pop = fo[_in_population(fo["kpi_population"]) & (fo["late_flag"] == 1)]
    ev = fe[fe["order_id"].isin(pop["order_id"]) & ~fe["event_type"].str.contains("GPS", na=False)]
    if ev.empty:
        return None
    g = ev.groupby("order_id").agg(systems=("source_system", "nunique"), events=("event_type", "size"),
                                   ticket=("event_type", lambda s: bool(s.eq("SUPPORT_TICKET").any())),
                                   interv=("event_type", lambda s: bool(s.str.startswith("INTERVENTION").any())))
    g = g.join(pop.set_index("order_id")["delay_min"])
    cand = g[g["ticket"] & g["interv"] & g["events"].between(8, 18)]
    cand = cand if len(cand) else g
    cand = cand.assign(neg_sys=-cand["systems"], neg_bad=-(cand["delay_min"] > 15).astype(int)).reset_index()
    return str(cand.sort_values(["neg_sys", "neg_bad", "events", "order_id"]).iloc[0]["order_id"])


def fig_one_order(ctx, out: Path) -> Path | None:
    plt = _plt()
    pdir = ctx["processed_dir"]
    fe = _read_csv(pdir / "fact_event.csv", parse_dates=["event_time"])
    fo = _read_csv(pdir / "fact_order.csv", parse_dates=["created_at", "promised_eta", "actual_delivery_at"])
    if fe is None or fo is None or fe.empty:
        return None
    oid = _pick_order(fe, fo)
    if oid is None:
        return None
    o = fo.set_index("order_id").loc[oid]
    oe = fe[fe["order_id"] == oid].sort_values("event_time")
    t0 = o["created_at"]

    def mins(t):
        return (t - t0).total_seconds() / 60
    fig, ax = plt.subplots(figsize=(17, 8.2), dpi=150)
    fig.subplots_adjust(left=0.14, right=0.975, top=0.8, bottom=0.1)
    delay = float(o["delay_min"])
    has_ticket = bool(oe["event_type"].eq("SUPPORT_TICKET").any())
    has_int = bool(oe["event_type"].str.startswith("INTERVENTION").any())
    fig.suptitle(f"Start with one order: {oid}, as seven systems saw it", fontsize=18, weight="bold", color=INK, y=0.975)
    sub = f"Session 7 · 'start with one order, not an ER diagram' · delivered {delay:.1f} min after the promise"
    if has_ticket and has_int and delay > 15:
        sub += " · ticket + intervention, still > 15 min late = the intervention did not work"
    fig.text(0.5, 0.885, sub, ha="center", fontsize=11, color=C["gray"])
    n = len(LANES)
    xs_all = [mins(t) for t in oe["event_time"]] + [mins(o["promised_eta"]), mins(o["actual_delivery_at"])]
    for i, (sysname, name, owner, col) in enumerate(LANES):
        y = n - 1 - i
        ax.axhspan(y - 0.45, y + 0.45, color=FILL[col], alpha=0.55, lw=0)
        evs = oe[oe["source_system"] == sysname]
        gps = evs[evs["event_type"].str.contains("GPS", na=False)]
        if len(gps):
            ax.scatter([mins(t) for t in gps["event_time"]], [y] * len(gps), s=22, color=C["gray"], marker="o", zorder=3)
            ax.annotate(f"{len(gps)} GPS pings (grey dots)", (mins(gps["event_time"].iloc[0]), y), xytext=(0, 10), textcoords="offset points",
                        fontsize=8.6, color=C["gray"], ha="center", va="bottom")
        other = evs[~evs["event_type"].str.contains("GPS", na=False)]
        grouped = other.groupby("event_time", sort=True)["event_type"].apply(lambda s: " + ".join(_event_label(x) for x in s))
        for k, (t, lbl) in enumerate(grouped.items()):
            m = mins(t)
            ax.scatter([m], [y], s=90, color=C[col], zorder=4, edgecolor="white", linewidth=1.2)
            up = k % 2 == 0
            ax.annotate(lbl, (m, y), xytext=(0, 10 if up else -10), textcoords="offset points", ha="center", va="bottom" if up else "top",
                        fontsize=8.9, color=INK, weight="bold")
    pe, ad = mins(o["promised_eta"]), mins(o["actual_delivery_at"])
    ax.axvline(pe, color=INK, ls="--", lw=1.6)
    ax.axvline(ad, color=C["red"], ls="--", lw=1.6)
    ax.axvspan(pe, ad, color=C["red"], alpha=0.08)
    ax.text(pe, n - 0.35, "promised ETA ", ha="right", va="bottom", fontsize=9.5, weight="bold", color=INK)
    ax.text(ad, n - 0.35, f" delivered, {delay:.0f} min late", ha="left", va="bottom", fontsize=9.5, weight="bold", color=C["red"])
    ax.set_yticks(range(n))
    ax.set_yticklabels([f"{name}\n({owner})" for _, name, owner, _ in LANES][::-1], fontsize=10)
    ax.set_ylim(-0.6, n + 0.1)
    ax.set_xlim(min(xs_all + [0]) - 4, max(xs_all) + 24)
    ax.set_xlabel("minutes after the order was created")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    return _save(fig, out / "06_one_order_journey.png")


# --------------------------------------------------------------------------- 07 lifecycle
OUTCOME_LABEL = {"delivered_late": "delivered late", "delivered_on_time": "delivered on time", "cancelled": "cancelled",
                 "unknown_missing_timestamp": "no delivery time", "excluded_dq_rule": "impossible timestamps", "other_status": "other status"}


def fig_lifecycle(ctx, out: Path) -> Path:
    W, H = 17, 8.8
    fig, ax = _canvas(W, H)
    _title(ax, W, H, "The order workflow as the data sees it",
           "Session 7 · events and states · customer interactions · ops interventions · outcomes · median minutes for LATE vs ON-TIME orders")
    st = ctx["stage"]
    med = {}
    if st is not None and not st.empty:
        s = st.set_index("stage_metric")
        med = {k: (float(s.loc[k, "late"]), float(s.loc[k, "on_time"])) for k in ["dispatch_wait_min", "pickup_wait_min", "transit_min"] if k in s.index}
    y, bh, bw = 50, 10.5, 25
    xs = [4, 38, 72, 106, 140]
    events = [("ORDER CREATED", "customer · orders DB", "blue", False), ("DRIVER ASSIGNED", "Dispatch API", "blue", False),
              ("ARRIVED AT RESTAURANT", "NOT RECORDED anywhere", "red", True), ("PICKED UP", "driver app + orders DB", "blue", False),
              ("DELIVERED", "driver app + orders DB", "green", False)]
    for x, (t, sub, col, dashed) in zip(xs, events):
        _box(ax, x, y, bw, bh, t, [sub], col, title_size=11, text_size=9.4, wrap=30, dashed=dashed)
    for i in range(4):
        _arrow(ax, (xs[i] + bw + 0.3, y + bh / 2), (xs[i + 1] - 0.3, y + bh / 2), "gray", lw=2.4)
    if "dispatch_wait_min" in med:
        late, on = med["dispatch_wait_min"]
        ax.text((xs[0] + bw + xs[1]) / 2, y + bh + 1.3, f"late {late:g} · on time {on:g}", ha="center", fontsize=9.2, color=C["gray"], weight="bold")
    if "pickup_wait_min" in med:
        late, on = med["pickup_wait_min"]
        ax.plot([xs[1] + bw, xs[3]], [y + bh + 5.0, y + bh + 5.0], color=C["red"], lw=1.8)
        ax.text((xs[1] + bw + xs[3]) / 2, y + bh + 6.3, f"assigned → picked up:  late {late:g} min  vs  on time {on:g} min  (+{late - on:.1f})",
                ha="center", fontsize=11, color=C["red"], weight="bold")
    if "transit_min" in med:
        late, on = med["transit_min"]
        ax.text((xs[3] + bw + xs[4]) / 2, y + bh + 1.3, f"late {late:g} · on time {on:g}", ha="center", fontsize=9.2, color=C["gray"], weight="bold")
    oc = _outcome_counts(ctx)
    n_cancel = int(oc.get("cancelled", 0))
    _box(ax, 140, 36.5, bw, 9.5, "CANCELLED", [f"{n_cancel} orders · not in the KPI"], "gray", title_size=10.5, text_size=9.2, dashed=True)
    cx = xs[0] + bw / 2
    ax.plot([cx, cx, 137.0], [y - 0.4, 41.25, 41.25], color=C["gray"], lw=1.4, ls="--")
    _arrow(ax, (136.0, 41.25), (139.8, 41.25), "gray", lw=1.4)
    ax.text(80, 42.0, "cancelled before delivery: no delivery time exists, so it cannot be late", ha="center", fontsize=9.2, color=C["gray"])
    pdir = ctx["processed_dir"]
    fi, fv = _read_csv(pdir / "fact_interaction.csv", usecols=["interaction_type"]), _read_csv(pdir / "fact_intervention.csv", usecols=["intervention_type"])
    act = fi["interaction_type"].value_counts() if fi is not None else pd.Series(dtype=int)
    ivc = fv["intervention_type"].value_counts() if fv is not None else pd.Series(dtype=int)
    ax.text(4, 31.8, "CUSTOMER INTERACTIONS · the customer's reaction", fontsize=11, weight="bold", color=C["orange"])
    for i, (k, lbl) in enumerate([("ETA_VIEWED", "ETA viewed"), ("SUPPORT_OPENED", "support opened"), ("SUPPORT_TICKET", "ticket raised"), ("CANCEL_ATTEMPTED", "cancel attempted")]):
        _cbox(ax, 4 + i * 41, 23.2, 37, 6.4, f"{lbl}:  {int(act.get(k, 0)):,}", "orange", size=10.5)
    ax.text(4, 18.4, "OPS INTERVENTIONS · what FlashEats did (invisible in the orders table, which only says 'delivered')", fontsize=11, weight="bold", color=C["purple"])
    for i, (k, lbl) in enumerate([("DRIVER_REASSIGNMENT", "driver reassignment"), ("RESTAURANT_CONTACT", "restaurant contact"),
                                  ("PRIORITY_DISPATCH", "priority dispatch"), ("CUSTOMER_CREDIT", "customer credit")]):
        _cbox(ax, 4 + i * 41, 9.8, 37, 6.4, f"{lbl}:  {int(ivc.get(k, 0)):,}", "purple", size=10.5)
    if len(oc):
        txt = "   ·   ".join(f"{OUTCOME_LABEL.get(k, k)} {int(v):,}" for k, v in oc.items())
        ax.text(W * 5, 5.0, "OUTCOME per order:  " + txt, ha="center", fontsize=10.2, weight="bold", color=C["green"])
    ax.text(W * 5, 1.8, "Entities: customer · restaurant · driver · order · ticket      Events: created · assigned · reassigned · picked up · delivered      "
                        "State: final status + outcome", ha="center", fontsize=9.2, color=C["gray"])
    return _save(fig, out / "07_order_lifecycle.png")


# --------------------------------------------------------------------------- 08 data model
def fig_data_model(ctx, out: Path) -> Path:
    W, H = 17, 9.6
    fig, ax = _canvas(W, H)
    t = ctx["tables"]
    joins = ctx["join_checks"]
    _title(ax, W, H, "Data model: organised around the order, not around the source systems",
           "Session 7 · every table has a grain · the many side is aggregated to one row per order BEFORE the join, so counts cannot inflate")

    def ent(x, y, w, h, name, grain, extra, col, wrap=30):
        _box(ax, x, y, w, h, name, [f"1 row = {grain}", extra, f"{_fmt(t.get(name))} rows"], col, title_size=12, text_size=9.8, wrap=wrap)
    ent(8, 62, 36, 15, "dim_customer", "customer", "PK customer_id (no PII)", "gray")
    ent(66, 62, 36, 15, "dim_restaurant", "restaurant", "PK restaurant_id · coords_valid", "gray")
    ent(124, 62, 36, 15, "dim_driver", "driver", "PK driver_id", "gray")
    ent(56, 33, 56, 20, "fact_order", "order", "PK order_id · FKs customer, restaurant, final driver (from Dispatch) · late_flag · delay · stage overruns · dq flags",
        "blue", wrap=58)
    ent(4, 6, 38, 17, "fact_event", "lifecycle event", "created → assigned → picked up → delivered, app actions, tickets, interventions", "purple", wrap=38)
    ent(48, 6, 38, 17, "fact_interaction", "customer interaction", "ETA viewed · support opened · ticket", "orange", wrap=38)
    ent(92, 6, 38, 17, "fact_intervention", "intervention", "reassignment · restaurant contact · priority · credit", "purple", wrap=38)
    ent(134, 31, 34, 22, "order_journey", "order", "interaction → intervention → outcome in ONE row", "green", wrap=32)
    for x in (26, 84, 142):
        _arrow(ax, (x, 62), (84, 53.4), "gray", lw=1.6, text="1 : N", text_offset=(0, 0.2), style="-")
    for x in (23, 67, 111):
        _arrow(ax, (84, 33), (x, 23.2), "gray", lw=1.6, text="1 : N", text_offset=(0, 0.2), style="-")
    _arrow(ax, (112.4, 43.0), (133.6, 42.0), "green", lw=2.6, text="aggregate, then 1 : 1", text_offset=(0, 0.8), style="-|>", fontsize=9.2)
    ok = sum(1 for j in joins if j.get("row_count_preserved"))
    ax.text(151, 27.5, f"{ok}/{len(joins)} joins checked:\nrow count preserved", ha="center", va="top", fontsize=10.2, color=C["green"], weight="bold")
    return _save(fig, out / "08_data_model.png")


# --------------------------------------------------------------------------- 09 metrics board
def fig_metrics(ctx, out: Path) -> Path:
    W, H = 17, 6.4
    fig, ax = _canvas(W, H)
    _title(ax, W, H, "Five metrics, each tied to the KPI: reduce the late-delivery rate",
           "Session 7 · outcome · severity · where · customer reaction · intervention · computed in pandas AND in SQL, and they agree")
    tiles = [("M1", "LATE DELIVERY RATE", "red", "How big is the problem?", "late ÷ trusted deliveries", "{n} of {d} trusted deliveries", 2),
             ("M2", "MEDIAN LATENESS", "orange", "How late is late?", "median delay of late orders", "across {d} late orders", 1),
             ("M3", "LATENESS BEFORE PICKUP", "purple", "Where is time lost?", "pre-pickup overrun ÷ all overrun", "{n} of {d} overrun minutes", 1),
             ("M4", "SUPPORT CONTACT (LATE)", "blue", "How do customers react?", "late orders with a ticket or support", "{n} of {d} late orders", 1),
             ("M5", "INTERVENTION COVERAGE", "green", "Does ops reach them?", "orders with ≥ 1 intervention", "{n} of {d} deliveries", 1)]
    bw, gap, x0, y0, bh = 30.5, 3.4, 3.2, 8.5, 38
    for i, (mid, name, col, q, formula, sub, nd) in enumerate(tiles):
        x = x0 + i * (bw + gap)
        v, unit = _metric(ctx, mid), _metric(ctx, mid, "unit")
        num, den = _metric(ctx, mid, "numerator"), _metric(ctx, mid, "denominator")
        _box(ax, x, y0, bw, bh, f"{mid} · {name}", [], col, title_size=10.6, wrap=30)
        ax.text(x + bw / 2, y0 + bh - 14.5, f"{_fmt(v, nd)}{' %' if unit == '%' else (' ' + str(unit) if unit else '')}", ha="center", va="center",
                fontsize=30, weight="bold", color=C[col])
        ax.text(x + bw / 2, y0 + bh - 23.5, sub.format(n=_fmt(round(float(num))) if num is not None else "?", d=_fmt(round(float(den))) if den is not None else "?"),
                ha="center", fontsize=10.2, color=C["gray"])
        ax.text(x + bw / 2, y0 + 9.2, q, ha="center", fontsize=11, weight="bold", color=INK)
        ax.text(x + bw / 2, y0 + 3.8, formula, ha="center", fontsize=9.4, color=C["gray"])
    extra = []
    m4a = _metric(ctx, "M4a")
    if m4a is not None:
        extra.append(f"on-time orders contact support only {m4a} % of the time")
    m5a, m5b = _metric(ctx, "M5a"), _metric(ctx, "M5b")
    if m5a is not None:
        extra.append(f"late rate with / without an intervention: {m5a} % / {m5b} % (association, not effect)")
    ax.text(W * 5, 3.6, "   ·   ".join(extra), ha="center", fontsize=10, color=C["gray"])
    return _save(fig, out / "09_metrics_board.png")


# --------------------------------------------------------------------------- 10 where the delay builds
def fig_where_delay(ctx, out: Path) -> Path | None:
    plt = _plt()
    st = ctx["stage"]
    if st is None or st.empty:
        return None
    s = st.set_index("stage_metric")
    parts = [("dispatch_wait_min", "dispatch wait", "#9AA5B1"), ("pickup_wait_min", "assigned → picked up (kitchen + ride to the restaurant)", C["red"]),
             ("transit_min", "transit to the customer", C["blue"])]
    fig, ax = plt.subplots(figsize=(16, 5.8), dpi=150)
    fig.subplots_adjust(left=0.13, right=0.97, top=0.8, bottom=0.22)
    fig.suptitle("Where the time is lost: late orders lose it BEFORE pickup, not on the road", fontsize=17, weight="bold", color=INK, y=0.97)
    fig.text(0.5, 0.875, f"median minutes per stage · {ctx['headline'].get('share_lateness_before_pickup_pct')} % of the overrun minutes on late orders "
                         "happen before pickup (M3)", ha="center", fontsize=11, color=C["gray"])
    for yi, grp in enumerate(["on_time", "late"]):
        left = 0.0
        for key, lbl, col in parts:
            v = float(s.loc[key, grp]) if key in s.index else 0.0
            ax.barh(yi, v, left=left, color=col, height=0.55, label=lbl if yi == 0 else None)
            ax.text(left + v / 2, yi, f"{v:g}", ha="center", va="center", color="white", fontsize=12, weight="bold")
            left += v
        pw = float(s.loc["promised_window_min", grp]) if "promised_window_min" in s.index else None
        if pw:
            ax.plot([pw, pw], [yi - 0.38, yi + 0.38], color=INK, lw=2.2, ls="--")
            ax.text(pw, yi + 0.42, f"promised ETA {pw:g} min", ha="center", fontsize=9.5, color=INK)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["ON-TIME orders", "LATE orders"], fontsize=12.5, weight="bold")
    ax.set_xlabel("minutes after the order was created (medians)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylim(-0.6, 1.85)
    if "pickup_wait_min" in s.index and "transit_min" in s.index:
        d1 = float(s.loc["pickup_wait_min", "late"] - s.loc["pickup_wait_min", "on_time"])
        d2 = float(s.loc["transit_min", "late"] - s.loc["transit_min", "on_time"])
        ax.text(0.01, 0.97, f"late vs on time:  +{d1:.1f} min before pickup   ·   +{d2:.1f} min in transit", transform=ax.transAxes, ha="left", va="top",
                fontsize=12, weight="bold", color=C["red"])
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=3, frameon=False, fontsize=10.5)
    return _save(fig, out / "10_where_delay_builds.png")


# --------------------------------------------------------------------------- 11 K/U/A/L
def fig_kual(ctx, out: Path) -> Path:
    W, H = 17, 7.0
    fig, ax = _canvas(W, H)
    h = ctx["headline"]
    eta, wx, gps = _ins(ctx, "eta"), _ins(ctx, "weather"), _ins(ctx, "gps")
    _title(ax, W, H, "Known · Unknown · Assumption · Limitation",
           "what the evidence proves, what needs an owner, what we assumed, and what this data cannot do")
    gps_line = (f"GPS pings look interpolated ({gps.get('straight_line_tracks_pct')} % are perfect straight lines): no arrival signal"
                if gps.get("straight_line_tracks_pct") is not None else "GPS cannot show arrival at the restaurant")
    quads = [
        (3, 32, "KNOWN · verified in this run", "green", [
            f"{_fmt(h.get('late_delivery_rate_pct'), 2)} % of {_fmt(h.get('validated_population'))} trusted deliveries were late (M1)",
            f"{_fmt(h.get('share_lateness_before_pickup_pct'))} % of the lateness builds up before pickup (M3)",
            f"Dispatch's pickup estimate is {eta.get('pickup_estimate_bias_median_min')} min too short" if eta else "stage durations are measured",
            "the orders table keeps the old driver after a reassignment"]),
        (86, 32, "UNKNOWN · needs an owner", "orange", [
            "which definition of 'late' is official → VP Operations",
            f"why {_fmt(_rule(ctx, 'TS-04'))} delivered orders have no delivery time → Fleet Ops",
            "who writes the weather label, and when → Operations",
            "when riders reach the restaurant: nothing records it"]),
        (3, 3, "ASSUMPTIONS · stated and configurable", "blue", [
            "late = delivered after the promised ETA (> 10 min shown too)",
            "timestamps are Bengaluru local time; cancelled orders excluded",
            "spelling may be fixed; meaning is never merged",
            "what-if save rates are scenarios, not measurements"]),
        (86, 3, "LIMITATIONS", "gray", [
            "interventions target risky orders: association, not effect",
            gps_line,
            f"the weather label matches real rain only by chance (kappa {wx.get('kappa')})" if wx else "one weather point for the whole city",
            "synthetic data: one city, one month, one held-out week"]),
    ]
    for x, y, title, col, lines in quads:
        _box(ax, x, y, 81, 25.5, title, [f"•  {ln}" for ln in lines], col, title_size=14, text_size=12, wrap=100, align="left")
    return _save(fig, out / "11_known_unknown.png")


# --------------------------------------------------------------------------- 12 pipeline flow
def fig_pipeline(ctx, out: Path) -> Path:
    W, H = 17, 9.0
    fig, ax = _canvas(W, H)
    _title(ax, W, H, "The dependable pipeline: 10 logged stages, and it stops itself when trust breaks",
           "Session 8 · ingest → validate → transform/model → metric output · one command: python run_pipeline.py --start-api")
    stages = [("1 INGEST", "SQL · API · CSV · JSON · weather; raw kept + SHA-256", "blue", True),
              ("2 PROFILE", "rows, nulls, formats, ranges, duplicates", "blue", False),
              ("3 CLEAN", "spelling only; duplicates and quarantine logged", "orange", False),
              ("4 VALIDATE", "38 business rules → the KPI population", "orange", True),
              ("5 MODEL", "one row per order; every join row-checked", "purple", True),
              ("6 METRICS", "M1–M5 + SQL layer + ledgers + client file", "red", True),
              ("7 DECIDE", "trigger · ETA · fair ranking · weather · GPS", "green", False),
              ("8 GATE", "PASS/WARN/FAIL/UNKNOWN + drift vs the last run", "red", True),
              ("9 MEMO", "situation → complication → resolution", "green", False),
              ("10 PUBLISH", "evidence · dashboard · charts · visuals · manifest", "teal", False)]
    bw, bh, gap = 29.5, 13.5, 3.9
    row_y = [58.5, 33.0]
    for i, (t, sub, col, stop) in enumerate(stages):
        row, pos = divmod(i, 5)
        x = 3.5 + pos * (bw + gap)
        y = row_y[row]
        _box(ax, x, y, bw, bh, t, [sub], col, title_size=12, text_size=10, wrap=28)
        if stop:
            ax.text(x + bw - 1.2, y + bh + 0.35, "STOP", ha="right", va="bottom", fontsize=8.6, weight="bold", color="white",
                    bbox=dict(boxstyle="round,pad=0.25", fc=C["red"], ec=C["red"]))
        if pos < 4:
            _arrow(ax, (x + bw + 0.3, y + bh / 2), (x + bw + gap - 0.3, y + bh / 2), "gray", lw=2.2)
    x_end = 3.5 + 4 * (bw + gap) + bw / 2
    x_start = 3.5 + bw / 2
    y_mid = (row_y[0] + row_y[1] + bh) / 2 + 1.0
    ax.plot([x_end, x_end, x_start], [row_y[0] - 0.4, y_mid, y_mid], color=C["gray"], lw=2.2)
    _arrow(ax, (x_start, y_mid), (x_start, row_y[1] + bh + 0.4), "gray", lw=2.2)
    rp, sc = ctx.get("replay") or {}, ctx.get("scorecard") or {}
    modes = [("LIVE", "python run_pipeline.py --start-api", "retrieves from the client systems now", "blue"),
             ("REPLAY", "python run_pipeline.py --replay run_example",
              f"rebuilds from preserved raw: {rp.get('outputs_identical')}/{rp.get('outputs_compared')} outputs identical" if rp else "rebuilds from preserved raw, hash-checked", "teal"),
             ("WEEKLY", "python run_pipeline.py --start-api --weekly",
              f"{len(sc.get('periods', []))} gated weekly runs that add up to the month" if sc else "one gated run per week + a scorecard", "purple")]
    for i, (t, cmd, what, col) in enumerate(modes):
        _box(ax, 3.5 + i * 55, 4, 51, 15, t, [cmd, what], col, title_size=12, text_size=9.8, wrap=60)
    ax.text(W * 5, 23.5, "three ways to run the same code   ·   STOP = the run refuses to publish when this stage's check fails (each one is tested)",
            ha="center", fontsize=10, color=C["gray"], weight="bold")
    return _save(fig, out / "12_pipeline_flow.png")


# --------------------------------------------------------------------------- 13 reproducibility
def fig_reproducibility(ctx, out: Path) -> Path:
    plt = _plt()
    rp, sc = ctx.get("replay"), ctx.get("scorecard")
    fig = plt.figure(figsize=(16.5, 6.6), dpi=150)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.05, 1], left=0.02, right=0.98, top=0.8, bottom=0.15, wspace=0.18)
    fig.suptitle("Trust that re-runs: same inputs give the same evidence, and the weeks add up to the month", fontsize=16.5, weight="bold", color=INK, y=0.97)
    fig.text(0.5, 0.88, "Session 8 · rerun behaviour · the final output is reproduced from the raw inputs", ha="center", fontsize=11, color=C["gray"])
    ax = fig.add_subplot(gs[0])
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    if rp:
        verdict = rp.get("verdict", "")
        vcol = {"REPRODUCED": "green", "DIFFERENT": "red"}.get(verdict, "gray")
        _box(ax, 1, 30, 30, 24, "PRESERVED RAW", [f"data/raw/{rp.get('replayed_run')}", f"{rp.get('artifacts_verified')}/{rp.get('artifacts')} artefacts", "SHA-256 match ✓"],
             "blue", wrap=24, text_size=10.4, title_size=12.5)
        _box(ax, 36, 30, 26, 24, "--replay", ["no client system contacted", "hashes checked first"], "teal", wrap=26, text_size=10.4, title_size=12.5)
        _box(ax, 67, 30, 32, 24, verdict, [f"{rp.get('outputs_identical')}/{rp.get('outputs_compared')} outputs", "byte-identical" + (" ✓" if verdict == "REPRODUCED" else "")],
             vcol, wrap=26, text_size=11, title_size=13)
        _arrow(ax, (31.4, 42), (35.6, 42), "gray", lw=2.4)
        _arrow(ax, (62.4, 42), (66.6, 42), "gray", lw=2.4)
        _box(ax, 1, 4, 98, 19, "AND IF SOMEONE EDITS THE EVIDENCE?",
             ["change one byte of a preserved file, or delete an API page → the replay STOPS and names the file (tested)"], "red", wrap=88, text_size=10.6, title_size=12.5)
    else:
        ax.text(50, 30, "run  python run_pipeline.py --replay <run_id>  to draw this panel", ha="center", fontsize=11, color=C["gray"])
    ax2 = fig.add_subplot(gs[1])
    if sc and sc.get("periods"):
        d = pd.DataFrame(sc["periods"])
        d = d[d["status"] == "PUBLISHED"]
        x = [p.replace("_", "\n→ ") for p in d["period"]]
        bars = ax2.bar(x, d["late_rate_pct"], color=[C["orange"] if f else C["blue"] for f in d["drift_flag"]])
        for b, r in zip(bars, d.itertuples()):
            ax2.text(b.get_x() + b.get_width() / 2, b.get_height() + 1, f"{r.late_rate_pct:.1f} %\n{int(r.late_orders)}/{int(r.validated_population)}", ha="center",
                     fontsize=10, weight="bold")
        pc = sc.get("partition_check", {})
        ax2.set_ylim(0, 88)
        ax2.set_ylabel("late rate %")
        ax2.set_title(f"Weekly runs: {int(d['validated_population'].sum()):,} deliveries and {int(d['late_orders'].sum())} late orders"
                      + (" = the month ✓" if pc.get("adds_up_to_full_run") else ""), fontsize=12)
        ax2.text(0.5, 0.94, f"orange = moved more than {sc.get('drift_threshold_pp', 2):g} pp vs the previous week (drift alert)", transform=ax2.transAxes,
                 ha="center", fontsize=9.6, color=C["orange"])
        ax2.spines[["top", "right"]].set_visible(False)
        ax2.tick_params(axis="x", labelsize=9)
    else:
        ax2.axis("off")
        ax2.text(0.5, 0.5, "run  python run_pipeline.py --start-api --weekly  to draw this panel", ha="center", fontsize=11, color=C["gray"], transform=ax2.transAxes)
    return _save(fig, out / "13_reproducibility.png")


# --------------------------------------------------------------------------- 14 the judgement call
def fig_early_warning(ctx, out: Path) -> Path | None:
    plt = _plt()
    ew_head = _ins(ctx, "early_warning")
    grid = ctx["ew"]
    if not ew_head or grid is None or grid.empty:
        return None
    k = int(ew_head["chosen_grace_min"])
    fo = _read_csv(ctx["processed_dir"] / "fact_order.csv", parse_dates=["created_at", "estimated_pickup_at", "pickup_at", "promised_eta", "actual_delivery_at"])
    fig = plt.figure(figsize=(16.5, 8.4), dpi=150)
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1.15], left=0.07, right=0.97, top=0.85, bottom=0.08, hspace=0.5)
    fig.suptitle("The FDE judgement call: a rule ops can switch on now, not an AI model", fontsize=17, weight="bold", color=INK, y=0.975)
    fig.text(0.5, 0.905, f"alert when an order is still not picked up {k} min after Dispatch's OWN estimated pickup · k chosen on the first three weeks, "
                         f"proven on the held-out last week", ha="center", fontsize=11, color=C["gray"])
    ax = fig.add_subplot(gs[0])
    ex = None
    train_until = ew_head.get("train_until_day")          # None when the data was too small for a hold-out week
    if fo is not None:
        held_out = (fo["created_at"].dt.day > int(train_until)) if train_until else pd.Series(True, index=fo.index)
        pop = fo[_in_population(fo["kpi_population"]) & (fo["late_flag"] == 1) & held_out].copy()
        pop["alert_at"] = pop["estimated_pickup_at"] + pd.Timedelta(minutes=k)
        pop = pop[pop["pickup_at"] > pop["alert_at"]]
        if len(pop):
            pop["lead"] = (pop["promised_eta"] - pop["alert_at"]).dt.total_seconds() / 60
            target = float(ew_head.get("test_median_lead_min") or pop["lead"].median())
            ex = pop.iloc[(pop["lead"] - target).abs().argsort().iloc[0]]
    if ex is not None:
        t0 = ex["created_at"]
        pts = [("order created", ex["created_at"], C["gray"]), ("Dispatch's estimated pickup", ex["estimated_pickup_at"], C["blue"]),
               (f"ALERT: +{k} min, not picked up", ex["alert_at"], C["orange"]), ("actually picked up", ex["pickup_at"], C["purple"]),
               ("promised ETA", ex["promised_eta"], INK), ("delivered (late)", ex["actual_delivery_at"], C["red"])]
        mins = [(lbl, (t - t0).total_seconds() / 60, col) for lbl, t, col in pts]
        ax.axhline(0, color="#C9CED3", lw=3, zorder=0)
        for i, (lbl, m, col) in enumerate(mins):
            ax.scatter([m], [0], s=130, color=col, zorder=3)
            up = i % 2 == 0
            ax.annotate(f"{lbl}\n{m:.0f} min", (m, 0), xytext=(0, 24 if up else -24), textcoords="offset points", ha="center",
                        va="bottom" if up else "top", fontsize=9.8, color=col, weight="bold", arrowprops=dict(arrowstyle="-", color=col, lw=1))
        a, p = mins[2][1], mins[4][1]
        ax.axvspan(a, p, color=C["orange"], alpha=0.12)
        ax.text((a + p) / 2, 0.86, f"{p - a:.0f} minutes of warning to act: reassign, call the restaurant, tell the customer", ha="center", va="center",
                fontsize=10.5, weight="bold", color=C["orange"])
        ax.set_ylim(-1, 1.05)
        ax.set_xlim(-5, max(m for _, m, _ in mins) + 8)
        ax.set_yticks([])
        ax.set_xlabel("minutes after the order was created")
        ax.set_title(f"One real late order {'from the held-out week' if train_until else 'caught by the rule'} ({ex['order_id']})", fontsize=12)
        ax.spines[["top", "right", "left"]].set_visible(False)
    else:
        ax.axis("off")
    ax2 = fig.add_subplot(gs[1])
    t = grid[grid["split"] == "test"]
    ax2.plot(t["grace_min"], t["precision_pct"], marker="o", lw=2.4, color=C["blue"], label="precision: the alert was right")
    ax2.plot(t["grace_min"], t["recall_pct"], marker="o", lw=2.4, color=C["red"], label="recall: late orders caught")
    ax2.plot(t["grace_min"], t["alert_rate_pct"], marker=".", ls="--", color=C["gray"], label="share of orders alerted (ops workload)")
    ax2.axvline(k, color=C["green"], ls=":", lw=2)
    row = t[t["grace_min"] == k]
    if len(row):
        r = row.iloc[0]
        span = float(t["grace_min"].max() - t["grace_min"].min()) or 1.0
        ax2.annotate(f"k = {k} min:  {r.precision_pct:.0f} % precise · {r.recall_pct:.0f} % of late orders caught · {r.median_lead_min:.0f} min warning",
                     (k, r.precision_pct), xytext=(k + span * 0.2, 72), textcoords="data", fontsize=10.5,
                     weight="bold", color=C["green"], arrowprops=dict(arrowstyle="->", color=C["green"]))
    ax2.set_xlabel("k = minutes after Dispatch's estimated pickup")
    ax2.set_ylabel("% on the held-out week")
    ax2.set_ylim(0, 108)
    ax2.legend(loc="lower left", fontsize=9.5, frameon=False)
    ax2.spines[["top", "right"]].set_visible(False)
    return _save(fig, out / "14_judgement_call.png")


# --------------------------------------------------------------------------- 15 class vs FDE
def fig_what_is_different(ctx, out: Path) -> Path:
    W, H = 17, 9.8
    fig, ax = _canvas(W, H)
    ew, eta, wx, gps, rr = (_ins(ctx, k) for k in ("early_warning", "eta", "weather", "gps", "restaurants"))
    rp, sc = ctx.get("replay") or {}, ctx.get("scorecard") or {}
    ct = ((ctx["ingestion"] or {}).get("control_totals") or {}).get("rows", [])
    _title(ax, W, H, "Where the class stopped, and what an FDE adds on top", "same FlashEats case · six moves that turn a diagnosis into a decision the client can act on")
    rows = [
        ("SESSION 5 SYNTHESIS", "Decide whether to build the AI delay predictor now", "A rule ops can switch on today, and the baseline any AI must beat",
         f"{ew.get('test_precision_pct')} % precise · {ew.get('test_recall_pct')} % of late orders caught · ~{_fmt(ew.get('test_median_lead_min'), 0)} min warning, "
         f"on a week the rule never saw" if ew else "n/a"),
        ("SESSION 6 KEY INSIGHT", "GPS has pings before pickup and none after it", "Re-tested it on this client's data: the pings look drawn, not measured",
         f"{_fmt(gps.get('pings_before_pickup_pct'))} % of pings before pickup · before pickup {_fmt(gps.get('moving_away_before_pickup_pct'))} % move AWAY from the "
         f"restaurant · {_fmt(gps.get('straight_line_tracks_pct'))} % perfect straight lines" if gps else "n/a"),
        ("SESSION 5 FINDING", "Heavy rain goes with +6.6 min of delay", "Checked the client's weather label against the real sky",
         f"label vs observed rainfall: agreement {wx.get('agreement_pct')} %, kappa {wx.get('kappa')} = chance" if wx else "n/a"),
        ("CLIENT BRIEF", "'Our ETAs are unreliable'", "Measured which part of the promise is wrong",
         f"Dispatch's pickup estimate is {eta.get('pickup_estimate_bias_median_min')} min short · padding the promise instead needs "
         f"+{eta.get('padding_needed_min')} min on every order" if eta else "n/a"),
        ("THE USUAL NEXT STEP", "List the restaurants with the most late orders", "Fair ranking before blame (confidence intervals)",
         f"of {rr.get('judgeable')} restaurants, only {rr.get('significantly_worse')} is really worse than the fleet ({', '.join(rr.get('worse_list', []))}) · "
         f"a raw top-10 names {10 - int(rr.get('naive_top10_significant') or 0)} that are not" if rr else "n/a"),
        ("CLASS NOTEBOOKS", "Run cell by cell, once", "Trust that re-runs by itself",
         f"{sum(1 for r in ct if r.get('status') == 'MATCH')}/{len(ct)} client control totals · replay: {rp.get('outputs_identical')}/{rp.get('outputs_compared')} "
         f"outputs identical · {len(sc.get('periods', []))} weekly runs = the month" if (ct and rp and sc) else "control totals · replay · weekly runs"),
    ]
    ax.text(4, 79.5, "WHERE THE CLASS STOPPED", fontsize=11, weight="bold", color=C["gray"], va="bottom")
    ax.text(58, 79.5, "WHAT THIS PROJECT ADDS", fontsize=11, weight="bold", color=C["green"], va="bottom")
    ax.text(110, 79.5, "EVIDENCE FROM THIS RUN", fontsize=11, weight="bold", color=C["blue"], va="bottom")
    for i, (src, cls, add, ev) in enumerate(rows):
        y = 67 - i * 12.3
        _rbox(ax, 4, y, 47, 10.2, "gray")
        ax.text(5.4, y + 8.6, src, fontsize=8.4, weight="bold", color=C["gray"], va="top")
        ax.text(27.5, y + 3.9, _bwrap(cls, 52), fontsize=10.4, color=INK, ha="center", va="center")
        _arrow(ax, (51.6, y + 5.1), (57.4, y + 5.1), "green", lw=2.6)
        _cbox(ax, 58, y, 48, 10.2, add, "green", size=10.6, wrap=46, weight="bold", tcolor=C["green"])
        _cbox(ax, 110, y, 58, 10.2, ev, "blue", size=9.8, wrap=66, fill=FILL["white"])
    return _save(fig, out / "15_what_is_different.png")


FIGURES = [fig_trustworthy_path, fig_source_map, fig_retrieval, fig_kpi_funnel, fig_gate, fig_one_order, fig_lifecycle, fig_data_model,
           fig_metrics, fig_where_delay, fig_kual, fig_pipeline, fig_reproducibility, fig_early_warning, fig_what_is_different]


def build_visuals(run_out: Path, raw_dir: Path | None, processed_dir: Path, published_root: Path | None = None) -> list[Path]:
    """Draw every figure from the run's own evidence into <run_out>/visuals/ (stale figures are removed first)."""
    from .logging_utils import get_logger
    log = get_logger()
    ctx = load_context(run_out, raw_dir, processed_dir, published_root)
    out = Path(run_out) / "visuals"
    if out.exists():
        for old in out.glob("*.png"):
            old.unlink()
    made = []
    for fn in FIGURES:
        try:
            p = fn(ctx, out)
            if p:
                made.append(p)
        except Exception as exc:  # a picture must never break the evidence run
            log.warning("visual %s skipped: %s", fn.__name__, exc)
    log.info("visual story: %d figures in %s", len(made), out)
    return made

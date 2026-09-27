"""Dependability add-ons: record reconciliation ledger and run-over-run drift monitoring.

* Ledger - for every dataset, prove that ``raw = clean + dropped exact duplicates +
  dropped conflicting duplicates + quarantined``. Nothing may disappear silently.
  For orders, also prove that every unique order lands in exactly one outcome bucket.
* Run comparison - a repeatable pipeline is re-run every month; the business needs
  to know what moved since the last *published* run and whether data quality got worse.
"""
from __future__ import annotations

import pandas as pd

from .cleaning import CleaningReport

ORDER = {"PASS": 0, "UNKNOWN": 1, "WARN": 2, "FAIL": 3}


def build_ledger(rep: CleaningReport, fact_order: pd.DataFrame | None = None) -> tuple[pd.DataFrame, list[dict]]:
    rows = []
    for ds, raw in rep.raw_row_counts.items():
        acts = [a for a in rep.actions if a.dataset == ds]
        exact = sum(a.count for a in acts if a.action == "drop_exact_duplicate_rows")
        conflict = sum(a.count for a in acts if a.action.startswith("drop_conflicting_duplicate"))
        quarantined = sum(a.count for a in acts if a.action.startswith("quarantine"))
        out_of_period = sum(a.count for a in acts if a.action.startswith("out_of_period"))
        clean = rep.clean_row_counts.get(ds, 0)
        rows.append({"dataset": ds, "raw_rows": raw, "exact_duplicates_dropped": exact, "conflicting_duplicates_dropped": conflict,
                     "quarantined": quarantined, "out_of_period": out_of_period, "clean_rows": clean,
                     "balanced": raw == clean + exact + conflict + quarantined + out_of_period})
    ledger = pd.DataFrame(rows)
    checks = [{"check": "record ledger: raw = clean + dropped duplicates + quarantined + out of period (every dataset)",
               "status": "PASS" if len(ledger) and bool(ledger["balanced"].all()) else ("UNKNOWN" if not len(ledger) else "FAIL"),
               "evidence": "; ".join(f"{r.dataset}: {r.raw_rows}={r.clean_rows}+{r.exact_duplicates_dropped}+{r.conflicting_duplicates_dropped}+{r.quarantined}+{r.out_of_period}"
                                     for r in ledger.itertuples() if (r.raw_rows != r.clean_rows) or not r.balanced) or "no rows removed anywhere"}]
    if fact_order is not None and len(fact_order):
        b = fact_order["outcome_bucket"].value_counts()
        pop = int(fact_order["kpi_population"].sum())
        checks.append({"check": "order ledger: every unique order in exactly one outcome bucket; population = late + on time",
                       "status": "PASS" if int(b.sum()) == len(fact_order) and pop == int(b.get("delivered_late", 0) + b.get("delivered_on_time", 0)) else "FAIL",
                       "evidence": f"{len(fact_order)} orders = " + " + ".join(f"{int(v)} {k}" for k, v in b.items()) + f"; KPI population {pop}"})
    return ledger, checks


# outputs whose bytes depend only on the inputs and the policy (no run id, no timestamps)
FINGERPRINTED = ["metrics.csv", "metric_checks.csv", "data_quality_rules.csv", "reconciliation_ledger.csv", "sql_metric_layer_check.csv"]
FINGERPRINTED_DIRS = ["breakdowns", "insights", "sql_metric_views", "quarantine"]


def fingerprint_outputs(run_out, processed_dir) -> dict:
    """SHA-256 of every deterministic output - proves that a rerun on the same inputs is byte-identical."""
    from pathlib import Path
    from .io_utils import sha256_file
    run_out, processed_dir = Path(run_out), Path(processed_dir)
    fingerprints = {}
    for name in FINGERPRINTED:
        f = run_out / name
        if f.exists():
            fingerprints[name] = sha256_file(f)
    for d in FINGERPRINTED_DIRS:
        folder = run_out / d
        if folder.exists():
            for f in sorted(folder.glob("*.csv")):
                fingerprints[f"{d}/{f.name}"] = sha256_file(f)
    for f in sorted(processed_dir.glob("*.csv")):
        fingerprints[f"processed/{f.name}"] = sha256_file(f)
    return fingerprints


def compare_runs(previous: dict | None, current: dict, drift_pp: float) -> dict:
    """Compare the current run with the last published run manifest.

    A re-run under the same run id is compared with that id's previous publication: re-running the
    same inputs must reproduce the same evidence, which is exactly what this check should prove."""
    if not previous:
        return {"status": "UNKNOWN", "baseline_run": None, "summary": "no previous published run to compare with (first run)", "headline": [], "rules": []}
    same_id = previous.get("run_id") == current.get("run_id")
    base_label = f"{previous.get('run_id')} (its previous publication, {previous.get('finished_at', 'time unknown')})" if same_id else previous.get("run_id")
    ph = (previous.get("stages", {}).get("metrics", {}) or {}).get("headline", {}) or {}
    ch = current.get("headline", {}) or {}
    head = []
    for k in sorted(set(ph) | set(ch)):
        a, b = ph.get(k), ch.get(k)
        delta = round(b - a, 2) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None
        head.append({"metric": k, "previous": a, "current": b, "delta": delta})
    pr = (previous.get("stages", {}).get("validate", {}) or {})
    prs, prv = pr.get("rules", {}) or {}, pr.get("violations", {}) or {}
    crs, crv = current.get("rules", {}) or {}, current.get("violations", {}) or {}
    rules, worsened = [], []
    for rid in sorted(set(prs) | set(crs)):
        s0, s1 = prs.get(rid), crs.get(rid)
        v0, v1 = prv.get(rid), crv.get(rid)
        changed = (s0 != s1) or (v0 is not None and v1 is not None and v0 != v1)
        if changed:
            rules.append({"rule": rid, "previous_status": s0, "current_status": s1, "previous_violations": v0, "current_violations": v1})
        if s0 in ORDER and s1 in ORDER and ORDER[s1] > ORDER[s0]:
            worsened.append(rid)
    pf, cf = previous.get("fingerprints") or {}, current.get("fingerprints") or {}
    common = sorted(set(pf) & set(cf))
    changed = [k for k in common if pf[k] != cf[k]]
    fp = {"compared": len(common), "identical": len(common) - len(changed), "changed": changed,
          "only_in_previous": sorted(set(pf) - set(cf)), "only_in_current": sorted(set(cf) - set(pf))}
    kpi = next((h for h in head if h["metric"] == "late_delivery_rate_pct"), None)
    drift = kpi is not None and kpi["delta"] is not None and abs(kpi["delta"]) > drift_pp
    status = "WARN" if (drift or worsened) else "PASS"
    summary = (f"KPI moved {kpi['delta']:+.2f} pp vs {base_label}" if kpi and kpi["delta"] is not None else "KPI not comparable") + \
              (f"; rules worsened: {worsened}" if worsened else "; no rule got worse") + ("; DRIFT above threshold" if drift else "")
    if fp["compared"]:
        summary += f"; {fp['identical']}/{fp['compared']} deterministic outputs byte-identical"
    return {"status": status, "baseline_run": previous.get("run_id"), "summary": summary, "headline": head, "rules": rules,
            "drift_threshold_pp": drift_pp, "fingerprints": fp}


def comparison_to_markdown(cmp: dict) -> str:
    lines = ["# Run-over-run comparison", "", f"**Status: {cmp['status']}** — {cmp['summary']}", ""]
    if cmp.get("headline"):
        lines += ["| Metric | Previous | Current | Delta |", "|---|---:|---:|---:|"]
        lines += [f"| {h['metric']} | {h['previous']} | {h['current']} | {'' if h['delta'] is None else h['delta']} |" for h in cmp["headline"]]
    if cmp.get("rules"):
        lines += ["", "Rules whose status or violation count changed:", "", "| Rule | Previous | Current | Previous violations | Current violations |", "|---|---|---|---:|---:|"]
        lines += [f"| {r['rule']} | {r['previous_status']} | {r['current_status']} | {r['previous_violations']} | {r['current_violations']} |" for r in cmp["rules"]]
    elif cmp.get("baseline_run"):
        lines += ["", "No rule changed status or violation count."]
    fp = cmp.get("fingerprints") or {}
    if fp.get("compared"):
        tail = (f"; changed: {', '.join(fp['changed'][:15])}" if fp["changed"] else " (same inputs + same policy = same evidence).")
        lines += ["", f"**Reproducibility:** {fp['identical']} of {fp['compared']} deterministic outputs are byte-identical to the baseline run" + tail]
    return "\n".join(lines)

"""Validation gate (Class 6, Challenge 6): PASS / WARN / FAIL / UNKNOWN.

The deliverable of validation is not a clean dataframe - it is a decision:
*is this data safe enough for this decision, and what remains unresolved?*
"""
from __future__ import annotations

import pandas as pd

from .config import PipelineConfig
from .metrics import MetricsResult
from .rules import RuleResult

ORDER = {"PASS": 0, "UNKNOWN": 1, "WARN": 2, "FAIL": 3}


def _worst(statuses: list[str]) -> str:
    statuses = [s for s in statuses if s]
    return max(statuses, key=lambda s: ORDER.get(s, 0)) if statuses else "UNKNOWN"


def _rule(results: list[RuleResult], rid: str) -> RuleResult | None:
    return next((r for r in results if r.rule.id == rid), None)


def build_gate(ingestion: dict, results: list[RuleResult], metrics: MetricsResult, cfg: PipelineConfig) -> dict:
    checks: list[dict] = []

    # 1. retrieval completeness -----------------------------------------------------------
    api = ingestion.get("dispatch_api", {}) or {}
    api_status = "PASS" if api.get("complete") else ("UNKNOWN" if not api else "FAIL")
    if api.get("mode") == "snapshot" and api_status == "PASS":
        api_status = "WARN"
    files = ingestion.get("files", {}) or {}
    missing_files = [k for k, v in files.items() if v.get("status") == "missing" and not v.get("optional")]
    missing_optional = [k for k, v in files.items() if v.get("status") == "missing" and v.get("optional")]
    empty_files = [k for k, v in files.items() if v.get("empty")]
    sql = ingestion.get("sql", {}) or {}
    zero_sql = [e["name"] for e in sql.get("extracts", []) if e.get("rows", 0) == 0]
    retrieval = _worst([api_status, "FAIL" if missing_files else "PASS", "WARN" if empty_files else "PASS", "FAIL" if "orders_extract" in zero_sql else ("WARN" if zero_sql else "PASS")])
    checks.append({"check": "Retrieval completeness", "status": retrieval,
                   "evidence": f"API: {api.get('records_fetched')} records / expected {api.get('expected_total')} in {api.get('pages_fetched')} pages, retries={api.get('retries')}, mode={api.get('mode')}; "
                               f"missing files={missing_files or 'none'}; missing optional reference files={missing_optional or 'none'}; empty files={empty_files or 'none'}; zero-row SQL extracts={zero_sql or 'none'}",
                   "action": "raw pages + file copies + SQL extracts preserved under data/raw/<run_id>"})

    # 2. business grain ---------------------------------------------------------------------
    gr = _rule(results, "GR-01")
    checks.append({"check": "Business grain (one row per order)", "status": gr.status if gr else "UNKNOWN",
                   "evidence": gr.detail if gr else "rule not run", "action": "exact duplicates dropped; conflicting duplicates keep first row, conflict recorded in quarantine"})

    # 3. timestamp chronology --------------------------------------------------------------
    ts = [_rule(results, r) for r in ["TS-00", "TS-01", "TS-02", "TS-03", "TS-04", "TS-05"]]
    ts = [r for r in ts if r]
    checks.append({"check": "Timestamp chronology & completeness", "status": _worst([r.status for r in ts]),
                   "evidence": "; ".join(f"{r.rule.id}={r.violations}" for r in ts),
                   "action": "violating orders excluded from the KPI population (reject) and listed in the data-quality report; nothing deleted"})

    # 4. KPI definition ----------------------------------------------------------------------
    k = _rule(results, "KPI-01")
    checks.append({"check": "KPI definition ownership", "status": "UNKNOWN",
                   "evidence": (k.detail if k else "") + f" | pipeline publishes late = delay > {cfg.late_threshold_min:g} min and reports > {cfg.meaningful_late_threshold_min:g} min alongside",
                   "action": "VP Operations to sign off the definition; until then every output states the definition next to the number"})

    # 5. category semantics -------------------------------------------------------------------
    st = [r for r in results if r.rule.id.startswith("ST-")]
    sem = {r.rule.id: r.extra.get("semantic_candidates") for r in st if r.extra.get("semantic_candidates")}
    checks.append({"check": "Category semantics", "status": _worst([r.status for r in st]),
                   "evidence": "; ".join(f"{r.rule.id}: fixes={r.extra.get('representation_fixes', 0)}, unexpected={r.extra.get('unexpected', {})}" for r in st if r.status != "PASS") or "all vocabularies clean",
                   "action": f"representation normalised; semantic look-alikes NOT merged, owner decision required: {sem or 'none'}"})

    # 6. cross-source mapping ---------------------------------------------------------------
    ids = [r for r in results if r.rule.id.startswith("ID-") or r.rule.id.startswith("CX-")]
    cov = {r.rule.id: r.extra.get("coverage_pct", r.extra.get("orders_coverage_pct")) for r in ids if r.extra}
    map_status = _worst([r.status for r in ids])
    # Unmapped tickets/actions/events only weaken the *context* metrics (they are retained + flagged).
    # The workflow model itself collapses only if most orders have no Dispatch record.
    dispatch_cov = cov.get("ID-09")
    if dispatch_cov is not None and dispatch_cov < 50:
        map_status = "FAIL"
    checks.append({"check": "Cross-source mapping", "status": map_status,
                   "evidence": "coverage %: " + ", ".join(f"{k}={v}" for k, v in cov.items() if v is not None) + "; " + "; ".join(f"{r.rule.id}: {r.detail}" for r in ids if r.rule.id.startswith("CX-") and r.status != "PASS"),
                   "action": "unmapped records retained and flagged; Dispatch treated as authoritative for the final driver"})

    # 7. freshness -------------------------------------------------------------------------
    fr = _rule(results, "FR-01")
    checks.append({"check": "Freshness (restaurant status feed)", "status": fr.status if fr else "UNKNOWN", "evidence": fr.detail if fr else "rule not run",
                   "action": "restaurant status usable for weekly analytics only; not for live ETA or accountability"})

    # 8. metric sanity -----------------------------------------------------------------------
    ms = metrics.checks
    checks.append({"check": "Metric sanity & independent checks", "status": _worst([c["status"] for c in ms]),
                   "evidence": "; ".join(f"{c['status']}: {c['check']}" for c in ms if c["status"] != "PASS") or f"{len(ms)} checks passed",
                   "action": "see output/metric_checks.csv"})

    overall = _worst([c["status"] for c in checks])
    h = metrics.headline
    if overall == "FAIL":
        decision = "DO NOT PUBLISH - a blocking check failed (see checks). Fix retrieval/grain/mapping first."
    else:
        decision = (f"PUBLISH WITH CAVEATS: late delivery rate = {h.get('late_delivery_rate_pct')}% of {h.get('validated_population')} validated deliveries "
                    f"(historical definition: {h.get('historical_definition_pct')}%). State the definition, the excluded orders and the unresolved owner questions next to the number.")
    blocking = [c["check"] for c in checks if c["status"] == "FAIL"]
    unresolved = [c["check"] for c in checks if c["status"] in ("WARN", "UNKNOWN")]
    return {"overall_status": overall, "publish_decision": decision, "blocking": blocking, "unresolved": unresolved, "checks": checks,
            "leadership_claim": "Late Delivery Rate is 56%", "run_id": cfg.run_id}


def gate_to_markdown(gate: dict) -> str:
    df = pd.DataFrame(gate["checks"])
    lines = ["# Validation gate", "", f"**Overall: {gate['overall_status']}**  ", "", f"**Decision:** {gate['publish_decision']}", "",
             "| Check | Status | Evidence | Action |", "|---|---|---|---|"]
    for _, r in df.iterrows():
        lines.append(f"| {r['check']} | **{r['status']}** | {str(r['evidence']).replace('|', '/')} | {str(r['action']).replace('|', '/')} |")
    lines += ["", f"Blocking: {gate['blocking'] or 'none'}  ", f"Unresolved (caveats): {gate['unresolved'] or 'none'}"]
    return "\n".join(lines)

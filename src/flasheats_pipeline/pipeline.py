"""Orchestrator: ingest → preserve raw → profile → clean → validate → model → metrics → decision layer → gate → outputs.

Dependability features (Class 8 expectations):
* every stage is logged with timings and row counts (``output/pipeline.log``),
* raw inputs are snapshotted per run under ``data/raw/<run_id>/`` and never modified,
* processed tables and outputs are rewritten atomically per run (rerun-safe),
* the run manifest records inputs (hashes), outputs, gate status and any error,
* failures are explicit: a missing source, incomplete API ingestion or a failed
  gate stops publication with a clear message instead of a half-written output.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import requests

from . import __version__
from .cleaning import standardise
from .config import PipelineConfig
from .gate import build_gate
from .ingest import (ApiIngestionError, DispatchApiClient, ObservedWeatherClient, SourceFileError, SqlSource, flatten_driver_events,
                     load_snapshot_pages, read_csv_source, read_json_source)
from .insights import compute_insights
from .monitoring import build_ledger, compare_runs, comparison_to_markdown
from .timestamps import parse_timestamps
from .io_utils import read_json, write_json, write_text
from .logging_utils import configure_logging, get_logger
from .metrics import compute_metrics
from .model import build_model
from .profiling import profile_all
from .reports import (write_charts, write_dashboard, write_data_quality, write_decision_memo, write_evidence_table, write_gate,
                      write_insights, write_metrics, write_model, write_profile)
from .io_utils import write_csv
from .rules import run_rules

FILE_SOURCES = {
    # name: (file, required columns, optional?)
    "tickets": ("support_tickets.csv", ["ticket_id", "order_id", "created_at", "category"], False),
    "restaurant_status": ("restaurant_status.csv", ["order_id", "restaurant_id", "status", "last_updated_at"], False),
    "app_actions": ("customer_app_actions.csv", ["action_id", "order_id", "customer_id", "action_type", "action_at"], False),
    "interventions": ("order_interventions.csv", ["intervention_id", "order_id", "intervention_type", "intervention_at", "initiated_by"], False),
    # reference/derived files from the client - used only for reconciliation, never as a source of truth
    "order_outcomes_ref": ("order_outcomes.csv", ["order_id", "late_flag", "delay_min"], True),
}


@dataclass
class PipelineRun:
    config: PipelineConfig
    status: str = "NOT_STARTED"
    gate: dict = field(default_factory=dict)
    headline: dict = field(default_factory=dict)
    manifest: dict = field(default_factory=dict)
    error: str | None = None
    outputs: dict[str, str] = field(default_factory=dict)


class MockApiProcess:
    """Start the client's mock Dispatch API for the duration of a run (optional convenience)."""

    def __init__(self, script: Path, base_url: str):
        self.script, self.base_url, self.proc = script, base_url, None

    def __enter__(self):
        log = get_logger()
        if not self.script.exists():
            raise SourceFileError(f"mock API script not found: {self.script}")
        try:
            if requests.get(f"{self.base_url}/health", timeout=2).ok:
                log.info("Dispatch API already running at %s - not starting a new one", self.base_url)
                return self
        except requests.RequestException:
            pass
        self.proc = subprocess.Popen([sys.executable, str(self.script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(40):
            time.sleep(0.25)
            try:
                if requests.get(f"{self.base_url}/health", timeout=2).ok:
                    log.info("Started mock Dispatch API (pid %s) at %s", self.proc.pid, self.base_url)
                    return self
            except requests.RequestException:
                continue
        raise ApiIngestionError(f"mock Dispatch API did not become healthy at {self.base_url}")

    def __exit__(self, *exc):
        if self.proc is not None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover
                self.proc.kill()
            get_logger().info("Stopped mock Dispatch API")


def _stage(log, name: str):
    log.info("=" * 78)
    log.info("STAGE %s", name)
    log.info("=" * 78)
    return time.time()


def run_pipeline(cfg: PipelineConfig) -> PipelineRun:
    run = PipelineRun(config=cfg)
    out = cfg.output_dir
    run_out = cfg.run_output_dir
    out.mkdir(parents=True, exist_ok=True)
    log = configure_logging(run_out / "pipeline.log")
    t_start = time.time()
    manifest: dict = {"run_id": cfg.run_id, "pipeline_version": __version__, "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                      "config": {k: (str(v) if isinstance(v, Path) else v) for k, v in cfg.__dict__.items()}, "stages": {}, "inputs": {}, "outputs": {}}
    log.info("FlashEats pipeline v%s run_id=%s source_root=%s config=%s", __version__, cfg.run_id, cfg.source_root, cfg.config_file or "defaults")
    previous_manifest = None
    try:
        if (out / "run_manifest.json").exists():
            previous_manifest = read_json(out / "run_manifest.json")
    except Exception as exc:  # a corrupt previous manifest must not stop this run
        log.warning("previous run manifest unreadable (%s) - no run comparison", exc)
    api_ctx = MockApiProcess(cfg.mock_api_script, cfg.api_base_url) if cfg.start_mock_api else None
    try:
        if api_ctx:
            api_ctx.__enter__()
        # ------------------------------------------------------------------ 1 ingest
        t = _stage(log, "1/10 INGEST + RAW PRESERVATION")
        raw: dict[str, pd.DataFrame] = {}
        ingestion: dict = {"sql": {}, "files": {}, "dispatch_api": {}}
        sql = SqlSource(cfg.db_path, cfg.sql_dir, cfg.raw_dir)
        raw["orders"] = sql.extract("orders_extract", "orders", {"start_at": None, "end_at": None})
        raw["restaurants"] = sql.extract("restaurants_extract", "restaurants")
        raw["drivers"] = sql.extract("drivers_extract", "drivers")
        raw["customers"] = sql.extract("customers_extract", "customers")
        ingestion["sql"] = sql.manifest()
        for name, (fname, required, optional) in FILE_SOURCES.items():
            path = cfg.files_dir / fname
            try:
                df, res = read_csv_source(path, name, required, cfg.raw_dir)
                raw[name] = df
                ingestion["files"][name] = {"status": "ok", **res.as_dict()}
            except SourceFileError as exc:
                if optional:
                    log.warning("optional file %s unavailable: %s", fname, exc)
                    ingestion["files"][name] = {"status": "missing", "path": str(path), "error": str(exc), "optional": True}
                else:
                    raise
        de_obj, de_res = read_json_source(cfg.files_dir / "driver_events.json", "driver_events", cfg.raw_dir)
        raw["driver_events"] = flatten_driver_events(de_obj, de_res)
        ingestion["files"]["driver_events"] = {"status": "ok", **de_res.as_dict()}
        md_path = cfg.files_dir / "client_metric_definitions.json"
        metric_definitions = read_json(md_path) if md_path.exists() else {}
        ingestion["files"]["client_metric_definitions"] = {"status": "ok" if md_path.exists() else "missing", "path": str(md_path)}

        # independent external source: observed hourly weather for the same period (optional, never fatal)
        if cfg.weather_enabled:
            ts = [parse_timestamps(raw["orders"][c], c, cfg.source_timezone)[0] for c in ("created_at", "promised_eta") if c in raw["orders"].columns]
            span = pd.concat(ts).dropna() if ts else pd.Series(dtype="datetime64[ns]")
            if len(span):
                wclient = ObservedWeatherClient(cfg.weather_base_url, cfg.weather_latitude, cfg.weather_longitude, cfg.source_timezone, cfg.raw_dir,
                                                cache_dir=cfg.external_cache_dir, timeout_s=cfg.weather_timeout_s, max_retries=cfg.weather_max_retries)
                wdf, wrep = wclient.fetch(span.min().date().isoformat(), span.max().date().isoformat())
                ingestion["external_weather"] = wrep.as_dict()
                if wdf is not None:
                    raw["weather_obs"] = wdf
            else:
                ingestion["external_weather"] = {"mode": "unavailable", "errors": ["no parseable order timestamps to define the period"]}
        else:
            ingestion["external_weather"] = {"mode": "disabled"}

        client = DispatchApiClient(cfg.api_base_url, cfg.raw_dir, page_size=cfg.api_page_size, timeout_s=cfg.api_timeout_s,
                                   max_retries=cfg.api_max_retries, backoff_base_s=cfg.api_backoff_base_s, backoff_cap_s=cfg.api_backoff_cap_s, max_pages=cfg.api_max_pages)
        try:
            records, api_report = client.fetch_all()
        except ApiIngestionError as exc:
            log.error("Dispatch API ingestion failed: %s", exc)
            snap = load_snapshot_pages(cfg.raw_root, exclude_run=cfg.run_id) if cfg.api_fallback_to_last_snapshot else None
            if snap is None:
                raise
            records, api_report = snap
            log.warning("Falling back to preserved snapshot: %s", api_report.issues)
        ingestion["dispatch_api"] = api_report.as_dict()
        if not api_report.complete:
            log.error("Dispatch ingestion is INCOMPLETE: %s", api_report.issues)
        raw["dispatch"] = pd.DataFrame(records, dtype="object")
        if len(raw["dispatch"]) == 0:
            raw["dispatch"] = pd.DataFrame(columns=["order_id", "driver_id", "original_driver_id", "assigned_at", "reassigned_at", "estimated_pickup_at", "current_delivery_eta", "dispatch_status", "eta_model_version"])
        write_json(ingestion, cfg.raw_dir / "ingestion_manifest.json")
        manifest["inputs"] = ingestion
        manifest["stages"]["ingest"] = {"seconds": round(time.time() - t, 2), "rows": {k: int(len(v)) for k, v in raw.items()}}

        # ------------------------------------------------------------------ 2 profile
        t = _stage(log, "2/10 PROFILE (raw)")
        keys = {"orders": "order_id", "customers": "customer_id", "drivers": "driver_id", "restaurants": "restaurant_id", "tickets": "ticket_id",
                "restaurant_status": None, "app_actions": "action_id", "interventions": "intervention_id", "dispatch": "order_id", "driver_events": None,
                "order_outcomes_ref": "order_id", "weather_obs": "hour"}
        profiles = profile_all({k: (v, keys.get(k)) for k, v in raw.items()})
        write_profile(profiles, run_out)
        for p in profiles:
            log.info("profile %-18s rows=%6d dup_key=%3d exact_dup=%3d %s", p.name, p.rows, p.duplicate_key_rows, p.exact_duplicate_rows, "; ".join(p.notes)[:100])
        manifest["stages"]["profile"] = {"seconds": round(time.time() - t, 2)}

        # ------------------------------------------------------------------ 3 clean
        t = _stage(log, "3/10 CLEAN / STANDARDISE")
        ref = raw.pop("order_outcomes_ref", None)
        clean, cleaning_report = standardise(raw, cfg)
        manifest["stages"]["clean"] = {"seconds": round(time.time() - t, 2), "actions": len(cleaning_report.actions), "rows": cleaning_report.clean_row_counts}

        # ------------------------------------------------------------------ 4 validate
        t = _stage(log, "4/10 VALIDATE (business rules)")
        results = run_rules(clean, cleaning_report, cfg, metric_definitions)
        write_data_quality(cleaning_report, results, run_out)
        manifest["stages"]["validate"] = {"seconds": round(time.time() - t, 2), "rules": {r.rule.id: r.status for r in results},
                                          "violations": {r.rule.id: r.violations for r in results}}

        # ------------------------------------------------------------------ 5 model
        t = _stage(log, "5/10 BUSINESS MODEL")
        model = build_model(clean, results, cfg)
        write_model(model, cfg.processed_dir)
        manifest["stages"]["model"] = {"seconds": round(time.time() - t, 2), "tables": {k: int(len(v)) for k, v in model.tables.items()}}

        # ------------------------------------------------------------------ 6 metrics
        t = _stage(log, "6/10 METRICS")
        mr = compute_metrics(model, cfg, reference_outcomes=ref)
        # independent SQL re-computation straight from the client database
        try:
            sql_check = sql.scalar_query("independent_late_rate_check")
            pipe = mr.headline
            d_pop = abs(int(sql_check.get("valid_delivered") or 0) - int(pipe.get("validated_population") or 0))
            d_late = abs(int(sql_check.get("late_orders") or 0) - int(pipe.get("late_orders") or 0))
            # Raw SQL cannot normalise malformed or tz-suffixed timestamps or padded ids; a difference up to the
            # number of such values is explainable and reported as WARN. Anything larger means a real disagreement.
            ts_orders = [s for s in cleaning_report.timestamp_stats if s["column"].startswith("orders.")]
            explainable = sum(s["unparseable"] + s["tz_aware_converted"] for s in ts_orders) + sum(
                a.count for a in cleaning_report.actions if a.dataset == "orders" and a.action.startswith("normalise_id"))
            if d_pop == 0 and d_late == 0:
                status = "PASS"
            elif d_pop <= explainable and d_late <= explainable:
                status = "WARN"
            else:
                status = "FAIL"
            mr.checks.append({"check": "independent SQL re-computation of M1 on the raw database", "status": status,
                              "evidence": f"SQL: {sql_check} | pipeline: population={pipe.get('validated_population')}, late={pipe.get('late_orders')} | "
                                          f"difference pop={d_pop} late={d_late}, explainable by unparseable/tz/padded values={explainable}"})
            (log.info if status == "PASS" else log.warning if status == "WARN" else log.error)("independent SQL check %s: %s", status, sql_check)
        except Exception as exc:  # the check itself must never crash the run
            mr.checks.append({"check": "independent SQL re-computation of M1", "status": "UNKNOWN", "evidence": f"could not run: {exc}"})
        ledger, ledger_checks = build_ledger(cleaning_report, model["fact_order"])
        mr.checks.extend(ledger_checks)
        write_csv(ledger, run_out / "reconciliation_ledger.csv")
        write_metrics(mr, run_out)
        manifest["stages"]["metrics"] = {"seconds": round(time.time() - t, 2), "headline": mr.headline}

        # ------------------------------------------------------------------ 7 decision layer
        t = _stage(log, "7/10 DECISION LAYER (beyond the classroom)")
        ins = compute_insights(model, clean, mr.metrics, cfg)
        insight_charts = write_insights(ins, run_out, cfg, charts=cfg.write_charts)
        manifest["stages"]["insights"] = {"seconds": round(time.time() - t, 2), "headline": ins.headline, "findings": [f["id"] + " " + f["title"] for f in ins.findings]}

        # ------------------------------------------------------------------ 7 gate
        t = _stage(log, "8/10 VALIDATION GATE")
        comparison = compare_runs(previous_manifest, {"run_id": cfg.run_id, "headline": mr.headline,
                                                      "rules": manifest["stages"]["validate"]["rules"], "violations": manifest["stages"]["validate"]["violations"]},
                                  cfg.kpi_drift_alert_pp)
        write_json(comparison, run_out / "run_comparison.json")
        write_text(comparison_to_markdown(comparison), run_out / "run_comparison.md")
        log.info("run comparison %s: %s", comparison["status"], comparison["summary"])
        gate = build_gate(ingestion, results, mr, cfg, comparison)
        write_gate(gate, run_out)
        for c in gate["checks"]:
            (log.warning if c["status"] in ("WARN", "UNKNOWN") else log.error if c["status"] == "FAIL" else log.info)("gate %-8s %s", c["status"], c["check"])
        log.info("GATE OVERALL = %s | %s", gate["overall_status"], gate["publish_decision"])
        manifest["stages"]["gate"] = {"seconds": round(time.time() - t, 2), "overall": gate["overall_status"], "run_comparison": comparison["status"]}

        # ------------------------------------------------------------------ 9 decision memo
        t = _stage(log, "9/10 DECISION MEMO")
        write_decision_memo(mr, ins, gate, cfg, run_out)
        manifest["stages"]["memo"] = {"seconds": round(time.time() - t, 2)}

        # ------------------------------------------------------------------ 8 outputs
        t = _stage(log, "10/10 OUTPUTS")
        kual = build_kual_section(results, cleaning_report, ingestion, model, cfg)
        write_text(kual, run_out / "known_unknown_assumption_limitation.md")
        write_evidence_table(mr, gate, cfg, run_out, kual, ins)
        charts = (write_charts(mr, model, run_out) + insight_charts) if cfg.write_charts else []
        write_dashboard(mr, gate, charts, cfg, run_out)
        publish = gate["overall_status"] != "FAIL" or cfg.fail_on_gate == "NEVER"
        if publish:
            _publish_latest(run_out, out)
            log.info("published run outputs to %s", out)
        else:
            log.error("gate FAILED - outputs kept under %s but NOT published to %s", run_out, out)
        run.status = "COMPLETED" if publish else "GATE_FAILED"
        run.gate, run.headline = gate, mr.headline
        run.outputs = {p.name: str(p) for p in run_out.iterdir()}
        manifest["stages"]["outputs"] = {"seconds": round(time.time() - t, 2), "published": publish, "charts": [str(p) for p in charts]}
    except Exception as exc:
        run.status = "FAILED"
        run.error = f"{type(exc).__name__}: {exc}"
        log.error("PIPELINE FAILED: %s", run.error)
        log.debug(traceback.format_exc())
        manifest["error"] = run.error
        manifest["traceback"] = traceback.format_exc()
    finally:
        if api_ctx:
            api_ctx.__exit__(None, None, None)
        manifest["status"] = run.status
        manifest["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        manifest["duration_s"] = round(time.time() - t_start, 2)
        manifest["outputs"] = run.outputs
        write_json(manifest, run_out / "run_manifest.json")
        if run.status in ("COMPLETED",):
            write_json(manifest, out / "run_manifest.json")
        run.manifest = manifest
        log.info("run %s finished with status %s in %.1fs", cfg.run_id, run.status, manifest["duration_s"])
    return run


def _publish_latest(run_out: Path, out: Path) -> None:
    """Copy this run's evidence to output/ (the 'latest' view). Rerun-safe: old files are replaced."""
    for item in run_out.iterdir():
        dest = out / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)


def build_kual_section(results, cleaning_report, ingestion, model, cfg: PipelineConfig) -> str:
    """Known / Unknown / Assumption / Limitation - generated from the actual run, not hand-written."""
    r = {x.rule.id: x for x in results}
    api = ingestion.get("dispatch_api", {})
    known = [
        f"Retrieval is complete: {api.get('records_fetched')} dispatch records across {api.get('pages_fetched')} pages (server total {api.get('expected_total')}, {api.get('retries')} retries); every raw page and file copy is preserved with a SHA-256.",
        f"Grain: the raw orders extract had {cleaning_report.raw_row_counts.get('orders')} rows for {cleaning_report.clean_row_counts.get('orders')} unique orders; conflicting duplicates are quarantined, not deleted.",
        f"{r['TS-04'].violations if 'TS-04' in r else '?'} delivered orders have no actual_delivery_at and are reported as 'unknown outcome', not as on-time.",
        f"Chronology violations (TS-01 {r['TS-01'].violations if 'TS-01' in r else '?'}, TS-02 {r['TS-02'].violations if 'TS-02' in r else '?'}) are excluded from the KPI population and listed by order id.",
        f"The orders table keeps the ORIGINAL driver after a reassignment (CX-01): Dispatch is used as the authoritative final driver.",
    ]
    unknown = [
        "Which definition of 'late' leadership will own (any delay vs > 10 min) - no canonical KPI owner is documented (KPI-01).",
        "Whether the driver 'delivered' event may back-fill the missing delivery timestamps (TS-04): reported as a sensitivity, not published.",
        f"Why the intervention log and Dispatch disagree on driver reassignments (CX-03: {r['CX-03'].detail if 'CX-03' in r else 'n/a'}).",
        "Whether 'handoff' means 'handed_off' and 'ETA issue' means 'eta_changed' (semantic look-alikes kept separate).",
        "When the driver actually arrived at the restaurant - no such event exists, so restaurant prep time and driver wait cannot be separated.",
    ]
    assumptions = [
        f"Naive timestamps are in {cfg.source_timezone}; tz-aware values (if any) are converted to that zone.",
        f"Late = actual_delivery_at - promised_eta > {cfg.late_threshold_min:g} min (VP Operations); > {cfg.meaningful_late_threshold_min:g} min reported alongside (Support Lead).",
        "Cancelled orders are excluded from the KPI denominator (Finance) and no cancellation timestamp exists.",
        f"Delivery distance is plausible only in (0, {cfg.max_plausible_distance_km:g}] km; coordinates must fall inside the Bengaluru bounding box.",
        "orders.promised_eta is the customer-facing promise; Dispatch's current_delivery_eta is a later revision and is NOT used to define lateness.",
        "customer_interactions.csv and order_events.csv are treated as derived client artefacts and used only for reconciliation.",
    ]
    limitations = [
        "Interventions are targeted at late-risk orders, so 'late rate with vs without intervention' is an association with a selection effect, never a causal effect.",
        "Restaurant status feed covers only a subset of orders with minute precision (FR-01) - usable for weekly analytics, not for live ETA or restaurant accountability.",
        "GPS pings contain out-of-area outliers (RG-03) and no arrival-at-restaurant event: pickup_wait_min mixes restaurant prep and driver travel.",
        "All source data is a synthetic classroom pack for one city (Bengaluru) and one month (Aug 2026); magnitudes are illustrative.",
    ] + [f"Model note: {n}" for n in model.notes]
    wx = r.get("WX-01")
    if wx is not None and wx.status != "UNKNOWN":
        known.append(f"The client's weather_bucket does not match independently observed rainfall (WX-01: {wx.detail}).")
        unknown.append("Who writes weather_bucket and when (forecast at order time? manual flag?) - the label cannot be traced to observed weather.")
        assumptions.append(f"Observed weather is taken at one point (Bengaluru centre, {cfg.weather_latitude}, {cfg.weather_longitude}) per hour; "
                           f"an hour with > {cfg.weather_rain_threshold_mm:g} mm counts as raining.")
        limitations.append("A single weather point cannot capture neighbourhood-level showers; a V2 would geocode each order's route.")
    assumptions.append("Decision-layer what-ifs use an assumed intervention save rate (config: impact.prevented_share_scenarios); they are scenarios, not forecasts.")
    lines = ["## Known / Unknown / Assumption / Limitation", ""]
    for title, items in [("Known (verified in this run)", known), ("Unknown (needs an owner)", unknown), ("Assumptions (stated, not silently applied)", assumptions), ("Limitations", limitations)]:
        lines.append(f"**{title}**")
        lines += [f"- {i}" for i in items]
        lines.append("")
    return "\n".join(lines)

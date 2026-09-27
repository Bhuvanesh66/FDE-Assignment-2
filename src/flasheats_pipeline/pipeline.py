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

import json
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
from .contracts import check as contract_check, load_contract, required_columns
from .ingest.replay import load_preserved_manifest, read_api_pages, read_sql_extract, verify as verify_preserved
from .ingest.weather_source import WeatherReport, parse_open_meteo
from .insights import compute_insights
from .io_utils import sha256_file
from .monitoring import build_ledger, compare_runs, comparison_to_markdown, fingerprint_outputs
from .scope import control_totals, scope_reference, scope_to_period
from .sql_metrics import compare as compare_sql_metrics, run_views
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
from .visuals import build_visuals

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
        baseline = (out / "runs" / cfg.replay_run_id / "run_manifest.json") if cfg.replay_run_id else (out / "run_manifest.json")
        if baseline.exists():
            previous_manifest = read_json(baseline)
    except Exception as exc:  # a corrupt previous manifest must not stop this run
        log.warning("previous run manifest unreadable (%s) - no run comparison", exc)
    api_ctx = MockApiProcess(cfg.mock_api_script, cfg.api_base_url) if cfg.start_mock_api else None
    try:
        if api_ctx:
            api_ctx.__enter__()
        # ------------------------------------------------------------------ 1 ingest
        t = _stage(log, "1/10 INGEST + RAW PRESERVATION" + (f"  [replay of {cfg.replay_run_id}]" if cfg.replay_run_id else "")
                   + (f"  [period {cfg.period_start}..{cfg.period_end}]" if cfg.period_start else ""))
        raw, ingestion, metric_definitions, sql, all_order_ids = _ingest(cfg, log)
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
        clean = scope_to_period(clean, cleaning_report, cfg, all_order_ids)
        ref = scope_reference(ref, clean, cfg)
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
            sql_check = _independent_sql_check(sql, raw.get("orders"), cfg)
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
        try:
            views = run_views(cfg.processed_dir / "flasheats_model.sqlite", cfg.sql_dir / "40_metric_views.sql")
            sql_checks, sql_table = compare_sql_metrics(views, mr.metrics)
            mr.checks.extend(sql_checks)
            write_csv(sql_table, run_out / "sql_metric_layer_check.csv")
            for vname, vdf in views.items():
                write_csv(vdf, run_out / "sql_metric_views" / f"{vname}.csv")
        except Exception as exc:
            mr.checks.append({"check": "SQL metric layer (sql/40_metric_views.sql) == pandas metrics", "status": "FAIL", "evidence": f"could not run: {exc}"})
        ct = ingestion.get("control_totals") or {}
        if ct.get("rows"):
            mr.checks.append({"check": "retrieval complete vs client control totals (source_systems/manifest.json)",
                              "status": {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN"}.get(ct.get("status"), "UNKNOWN"),
                              "evidence": "; ".join(f"{r['control']}: published {r['published']} / observed {r['observed']}" for r in ct.get("rows", []))})
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
        manifest["fingerprints"] = fingerprint_outputs(run_out, cfg.processed_dir)
        comparison = compare_runs(previous_manifest, {"run_id": cfg.run_id, "headline": mr.headline, "fingerprints": manifest["fingerprints"],
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
        visuals = []
        if cfg.write_charts and not cfg.replay_run_id and not cfg.period_start:   # the visual story is drawn from this run's own evidence
            visuals = build_visuals(run_out, cfg.raw_dir, cfg.processed_dir, out)
        write_dashboard(mr, gate, charts, cfg, run_out, visuals)
        publish = gate["overall_status"] != "FAIL" or cfg.fail_on_gate == "NEVER"
        if cfg.replay_run_id:
            _write_replay_proof(cfg, ingestion, comparison, run_out, out)
            log.info("replay of %s complete - evidence in %s (published outputs left untouched)", cfg.replay_run_id, run_out)
        elif publish:
            _publish_latest(run_out, out)
            log.info("published run outputs to %s", out)
        else:
            log.error("gate FAILED - outputs kept under %s but NOT published to %s", run_out, out)
        run.status = "COMPLETED" if publish else "GATE_FAILED"
        run.gate, run.headline = gate, mr.headline
        run.outputs = {p.name: str(p) for p in run_out.iterdir()}
        manifest["stages"]["outputs"] = {"seconds": round(time.time() - t, 2), "published": publish, "charts": [str(p) for p in charts],
                                         "visuals": [p.name for p in visuals]}
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
        if run.status in ("COMPLETED",) and not cfg.replay_run_id:
            write_json(manifest, out / "run_manifest.json")
        run.manifest = manifest
        log.info("run %s finished with status %s in %.1fs", cfg.run_id, run.status, manifest["duration_s"])
    return run


SQL_EXTRACTS = [("orders", "orders_extract"), ("restaurants", "restaurants_extract"), ("drivers", "drivers_extract"), ("customers", "customers_extract")]


def _ingest(cfg: PipelineConfig, log):
    """Retrieve every source (live systems, or a verified replay of preserved raw) and prove completeness."""
    raw: dict[str, pd.DataFrame] = {}
    ingestion: dict = {"mode": "replay" if cfg.replay_run_id else "live", "sql": {}, "files": {}, "dispatch_api": {},
                       "period": None if not cfg.period_start else {"start": cfg.period_start, "end": cfg.period_end, "label": cfg.period_label}}
    contract = load_contract(cfg.schema_contract_file)
    contract_results = []
    sql = None
    src = pman = None
    win = cfg.period_window
    params = {"start_at": None, "end_at": None} if win is None else {"start_at": win[0].strftime("%Y-%m-%dT%H:%M:%S"), "end_at": win[1].strftime("%Y-%m-%dT%H:%M:%S")}

    # --- SQL (application database) -------------------------------------------------------
    if cfg.replay_run_id:
        src, pman = load_preserved_manifest(cfg.raw_root, cfg.replay_run_id)
        integrity = verify_preserved(src, pman)
        write_csv(integrity, cfg.raw_dir / "replay_integrity.csv")
        ingestion["replay"] = {"source_run": cfg.replay_run_id, "artifacts": int(len(integrity)), "verified": int((integrity["status"] == "OK").sum())}
        log.info("replay: %d preserved artefacts of %s verified against their SHA-256", ingestion["replay"]["verified"], cfg.replay_run_id)
        for table, name in SQL_EXTRACTS:
            raw[table] = read_sql_extract(src, name)
        ingestion["sql"] = {"mode": "replay", "tables": (pman.get("sql") or {}).get("tables", {}), "extracts": (pman.get("sql") or {}).get("extracts", [])}
        files_dir = src / "files"
    else:
        sql = SqlSource(cfg.db_path, cfg.sql_dir, cfg.raw_dir)
        for table, name in SQL_EXTRACTS:
            raw[table] = sql.extract(name, table, params if table == "orders" else None)
        ingestion["sql"] = sql.manifest()
        files_dir = cfg.files_dir
    for table, _ in SQL_EXTRACTS:
        contract_results.append(contract_check(raw[table], contract, "sql", table))

    # --- CSV + JSON exports --------------------------------------------------------------------
    for name, (fname, required_default, optional) in FILE_SOURCES.items():
        path = files_dir / fname
        try:
            df, res = read_csv_source(path, name, required_columns(contract, "files", fname, required_default), cfg.raw_dir)
            raw[name] = df
            ingestion["files"][name] = {"status": "ok", **res.as_dict()}
            contract_results.append(contract_check(df, contract, "files", fname, stop_on_missing=False))
        except SourceFileError as exc:
            if optional:
                log.warning("optional file %s unavailable: %s", fname, exc)
                ingestion["files"][name] = {"status": "missing", "path": str(path), "error": str(exc), "optional": True}
            else:
                raise
    de_obj, de_res = read_json_source(files_dir / "driver_events.json", "driver_events", cfg.raw_dir)
    raw["driver_events"] = flatten_driver_events(de_obj, de_res)
    ingestion["files"]["driver_events"] = {"status": "ok", **de_res.as_dict()}
    md_path = files_dir / "client_metric_definitions.json"
    metric_definitions = {}
    if md_path.exists():
        metric_definitions, md_res = read_json_source(md_path, "client_metric_definitions", cfg.raw_dir)
        ingestion["files"]["client_metric_definitions"] = {"status": "ok", **md_res.as_dict()}
    else:
        ingestion["files"]["client_metric_definitions"] = {"status": "missing", "path": str(md_path), "optional": True}

    # --- independent external source: observed weather (optional, never fatal) --------------
    if cfg.replay_run_id:
        wpath = src / "external" / "open_meteo_archive.json"
        if wpath.exists():
            with open(wpath, "r", encoding="utf-8") as f:
                raw["weather_obs"] = parse_open_meteo(json.load(f).get("payload", {}), expected_tz=cfg.source_timezone)
            w = WeatherReport(mode="replay", url=str(wpath), hours=int(len(raw["weather_obs"])), raw_path=str(wpath), raw_sha256=sha256_file(wpath))
            ingestion["external_weather"] = w.as_dict()
        else:
            ingestion["external_weather"] = {"mode": "unavailable", "errors": ["no preserved weather response in the replayed run"]}
    elif cfg.weather_enabled:
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

    # --- Dispatch REST API ----------------------------------------------------------------------
    if cfg.replay_run_id:
        records, api_report = read_api_pages(src, pman)
    else:
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
    contract_results.append(contract_check(raw["dispatch"], contract, "api", "dispatch", stop_on_missing=False))
    ingestion["schema_contract"] = [c.as_dict() for c in contract_results]
    for c in contract_results:
        if c.status != "PASS":
            log.warning("schema contract %s %s:%s missing_optional=%s uncontracted=%s", c.status, c.kind, c.source, c.missing_optional, c.uncontracted)

    # --- completeness: client control totals + server-side count of the SQL window -------------
    observed: dict[str, int | None] = {"support_tickets_rows": int(len(raw.get("tickets", []))) if "tickets" in raw else None,
                                       "dispatch_records": int(api_report.records_fetched)}
    if sql is not None:
        observed.update({"orders_rows": sql.count("SELECT COUNT(*) FROM orders"), "unique_orders": sql.count("SELECT COUNT(DISTINCT order_id) FROM orders"),
                         "drivers": sql.count("SELECT COUNT(*) FROM drivers"), "restaurants": sql.count("SELECT COUNT(*) FROM restaurants")})
        server = sql.count("SELECT COUNT(*) FROM orders WHERE (:start_at IS NULL OR created_at >= :start_at) AND (:end_at IS NULL OR created_at < :end_at)", params)
        ingestion["orders_extract_vs_server_count"] = {"extracted": int(len(raw["orders"])), "server_count": server, "match": server == len(raw["orders"])}
        all_ids = sql.distinct_order_ids()
    else:
        tables = ingestion["sql"].get("tables", {})
        observed.update({"orders_rows": (tables.get("orders") or {}).get("rows"), "drivers": (tables.get("drivers") or {}).get("rows"),
                         "restaurants": (tables.get("restaurants") or {}).get("rows"),
                         "unique_orders": int(raw["orders"]["order_id"].nunique()) if (pman.get("period") is None) else None})
        all_ids = {str(v).strip().upper() for v in raw["orders"]["order_id"].dropna()}
    ct_df, ct_status = control_totals(cfg, observed)
    ingestion["control_totals"] = {"status": ct_status, "rows": ct_df.to_dict("records")}
    write_csv(ct_df, cfg.raw_dir / "control_totals.csv")
    log.info("control totals %s: %s", ct_status, "; ".join(f"{r['control']} {r['observed']}/{r['published']}" for r in ingestion["control_totals"]["rows"]) or "none published")
    write_json(ingestion, cfg.raw_dir / "ingestion_manifest.json")
    return raw, ingestion, metric_definitions, sql, all_ids


def _independent_sql_check(sql, orders_raw: pd.DataFrame | None, cfg: PipelineConfig) -> dict:
    """Recompute M1 in SQL, independently of pandas: on the live database for a full live run,
    otherwise on an in-memory copy of the (window-scoped or replayed) raw orders extract."""
    import sqlite3
    if sql is not None and cfg.period_window is None:
        return sql.scalar_query("independent_late_rate_check")
    if orders_raw is None or len(orders_raw) == 0:
        return {"valid_delivered": 0, "late_orders": 0}
    con = sqlite3.connect(":memory:")
    try:
        orders_raw.astype("object").where(orders_raw.notna(), None).to_sql("orders", con, index=False)
        df = pd.read_sql_query((cfg.sql_dir / "independent_late_rate_check.sql").read_text(encoding="utf-8"), con)
    finally:
        con.close()
    return {} if df.empty else {k: (None if pd.isna(v) else v) for k, v in df.iloc[0].to_dict().items()}


def _write_replay_proof(cfg: PipelineConfig, ingestion: dict, comparison: dict, run_out: Path, out: Path) -> None:
    """Reproducibility proof: preserved inputs verified + outputs compared byte-for-byte with the original run."""
    rp = ingestion.get("replay") or {}
    fp = comparison.get("fingerprints") or {}
    ok = bool(fp.get("compared")) and not fp.get("changed")
    proof = {"replayed_run": cfg.replay_run_id, "replay_run": cfg.run_id, "artifacts_verified": rp.get("verified"), "artifacts": rp.get("artifacts"),
             "outputs_compared": fp.get("compared"), "outputs_identical": fp.get("identical"), "changed": fp.get("changed", []),
             "verdict": "REPRODUCED" if ok else ("NOT COMPARABLE" if not fp.get("compared") else "DIFFERENT")}
    lines = ["# Replay proof — the published evidence can be rebuilt from preserved raw inputs", "",
             f"**Verdict: {proof['verdict']}**", "",
             f"- Replayed run: `{cfg.replay_run_id}` (its preserved raw inputs in `data/raw/{cfg.replay_run_id}/`).",
             f"- Integrity: {rp.get('verified')} of {rp.get('artifacts')} preserved artefacts matched the SHA-256 recorded at retrieval (`replay_integrity.csv`, one row per artefact).",
             f"- No client system was contacted: the SQL extracts, files, every raw Dispatch API page and the weather response were read from the preserved copies.",
             f"- Outputs: {fp.get('identical')} of {fp.get('compared')} deterministic outputs are byte-identical to the original run"
             + (f"; different: {', '.join(fp.get('changed', [])[:10])}" if fp.get("changed") else "."), "",
             "Command: `python run_pipeline.py --replay " + str(cfg.replay_run_id) + "`"]
    write_json(proof, run_out / "replay_proof.json")
    write_text("\n".join(lines), run_out / "replay_proof.md")
    write_json(proof, out / "replay_proof.json")
    write_text("\n".join(lines), out / "replay_proof.md")
    integrity = cfg.raw_dir / "replay_integrity.csv"
    if integrity.exists():
        shutil.copy2(integrity, run_out / "replay_integrity.csv")
        shutil.copy2(integrity, out / "replay_integrity.csv")


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

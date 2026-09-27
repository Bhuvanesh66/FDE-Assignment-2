"""Tests 1, 8, 9, 10 - the full pipeline on clean data, messy data, failing sources and reruns."""
import json
import shutil

import pytest

from flasheats_pipeline.pipeline import run_pipeline
from tests.conftest import EXPECTED, build_pack


def test_normal_clean_data_passes_cleanly(clean_pack, api_server, make_config):
    cfg = make_config(clean_pack, api_server.url, run_id="run_clean")
    run = run_pipeline(cfg)
    assert run.status == "COMPLETED", run.error
    statuses = {c["check"]: c["status"] for c in run.gate["checks"]}
    assert statuses["Retrieval completeness"] == "PASS" and statuses["Business grain (one row per order)"] == "PASS"
    assert statuses["Timestamp chronology & completeness"] == "PASS"
    assert run.headline["validated_population"] == 4 and run.headline["late_orders"] == 2     # O00001,2,3,11 delivered; 2 and 3 late


def test_messy_pack_end_to_end_outputs_and_raw_preservation(messy_pack, api_server, make_config, tmp_path):
    cfg = make_config(messy_pack, api_server.url, run_id="run_messy", write_charts=True)
    run = run_pipeline(cfg)
    assert run.status == "COMPLETED", run.error
    assert run.gate["overall_status"] == "WARN"
    assert run.headline["late_delivery_rate_pct"] == EXPECTED["late_rate_pct"]
    out = cfg.output_dir
    for f in ["metrics.csv", "metrics.json", "evidence_table.md", "data_quality_report.md", "data_quality_report.json", "validation_gate.json",
              "validation_gate.md", "known_unknown_assumption_limitation.md", "run_manifest.json", "pipeline.log", "dashboard.html", "profile/profile.md",
              "quarantine/orders_duplicate_conflicts.csv", "charts/late_rate_by_traffic.png", "breakdowns/definition_comparison.csv",
              "decision_memo.md", "insights/insights.md", "insights/early_warning_backtest.csv", "reconciliation_ledger.csv",
              "run_comparison.md", "charts/early_warning_tradeoff.png", "charts/eta_padding_curve.png"]:
        assert (out / f).exists(), f
    raw = cfg.raw_dir
    assert (raw / "api" / "dispatch_page_001.json").exists() and (raw / "files" / "support_tickets.csv").exists() and (raw / "sql" / "orders_extract.csv").exists()
    assert (raw / "files" / "support_tickets.csv").read_bytes() == (messy_pack / "data" / "support_tickets.csv").read_bytes()   # raw untouched
    assert (cfg.processed_dir / "fact_order.csv").exists() and (cfg.processed_dir / "flasheats_model.sqlite").exists()
    manifest = json.loads((out / "run_manifest.json").read_text())
    assert manifest["status"] == "COMPLETED" and manifest["inputs"]["dispatch_api"]["complete"] is True
    assert set(manifest["stages"]) == {"ingest", "profile", "clean", "validate", "model", "metrics", "insights", "gate", "memo", "outputs"}
    log = (out / "pipeline.log").read_text(encoding="utf-8")
    assert "STAGE 1/10" in log and "STAGE 7/10 DECISION LAYER" in log and "GATE OVERALL = WARN" in log and "unexpected categories" in log
    # the visual story is drawn from this run's own evidence, even on a 16-row pack, and never breaks the run
    visuals = sorted(p.name for p in (out / "visuals").glob("*.png"))
    assert {"01_trustworthy_path.png", "02_source_map.png", "03_retrieval_proof.png", "04_kpi_funnel.png", "05_validation_gate.png",
            "07_order_lifecycle.png", "08_data_model.png", "09_metrics_board.png", "11_known_unknown.png", "12_pipeline_flow.png"} <= set(visuals), visuals
    assert manifest["stages"]["outputs"]["visuals"] == visuals
    assert "visuals/01_trustworthy_path.png" in (out / "dashboard.html").read_text(encoding="utf-8")


def test_rerun_is_idempotent_and_keeps_every_raw_snapshot(messy_pack, api_server, make_config):
    r1 = run_pipeline(make_config(messy_pack, api_server.url, run_id="run_A"))
    api_server.hits.clear()
    r2 = run_pipeline(make_config(messy_pack, api_server.url, run_id="run_B"))
    assert r1.status == r2.status == "COMPLETED" and r1.headline == r2.headline
    data = r1.config.data_dir
    assert (data / "raw" / "run_A").exists() and (data / "raw" / "run_B").exists()
    latest = json.loads((r2.config.output_dir / "run_manifest.json").read_text())
    assert latest["run_id"] == "run_B"


def test_api_down_fails_clearly_and_writes_manifest(messy_pack, make_config):
    cfg = make_config(messy_pack, "http://127.0.0.1:9", run_id="run_down", api_timeout_s=0.5, api_max_retries=1)
    run = run_pipeline(cfg)
    assert run.status == "FAILED" and ("connection_error" in run.error or "timeout" in run.error)
    manifest = json.loads((cfg.run_output_dir / "run_manifest.json").read_text())
    assert manifest["status"] == "FAILED" and manifest["error"] == run.error
    assert not (cfg.output_dir / "metrics.csv").exists()      # nothing half-published


def test_api_down_with_snapshot_fallback_degrades_to_warn(messy_pack, api_server, make_config, tmp_path):
    ok = run_pipeline(make_config(messy_pack, api_server.url, run_id="run_first"))
    assert ok.status == "COMPLETED"
    cfg = make_config(messy_pack, "http://127.0.0.1:9", run_id="run_fallback", api_timeout_s=0.5, api_max_retries=1, api_fallback_to_last_snapshot=True)
    run = run_pipeline(cfg)
    assert run.status == "COMPLETED", run.error
    assert run.manifest["inputs"]["dispatch_api"]["mode"] == "snapshot"
    assert {c["check"]: c["status"] for c in run.gate["checks"]}["Retrieval completeness"] == "WARN"


def test_incomplete_api_blocks_publication(messy_pack, api_server, make_config):
    api_server.mode = "wrong_total"
    cfg = make_config(messy_pack, api_server.url, run_id="run_incomplete")
    run = run_pipeline(cfg)
    assert run.status == "GATE_FAILED" and run.gate["overall_status"] == "FAIL"
    assert not (cfg.output_dir / "metrics.csv").exists() and (cfg.run_output_dir / "metrics.csv").exists()


def test_missing_required_file_names_the_file(tmp_path, api_server, make_config):
    pack = build_pack(tmp_path / "p", messy=True, omit_file="support_tickets.csv")
    run = run_pipeline(make_config(pack, api_server.url, run_id="run_nofile"))
    assert run.status == "FAILED" and "support_tickets.csv" in run.error and "not found" in run.error


def test_optional_reference_file_may_be_absent(tmp_path, api_server, make_config):
    pack = build_pack(tmp_path / "p", messy=True, with_outcomes_ref=False)
    run = run_pipeline(make_config(pack, api_server.url, run_id="run_noref"))
    assert run.status == "COMPLETED", run.error
    assert run.manifest["inputs"]["files"]["order_outcomes_ref"]["status"] == "missing"
    checks = (run.config.output_dir / "metric_checks.csv").read_text(encoding="utf-8")
    assert "order_outcomes.csv" not in checks                      # reconciliation simply not run
    assert {c["check"]: c["status"] for c in run.gate["checks"]}["Retrieval completeness"] == "PASS"


def test_missing_database_fails_clearly(tmp_path, api_server, make_config):
    pack = build_pack(tmp_path / "p", messy=True)
    (pack / "database" / "flasheats.db").unlink()
    run = run_pipeline(make_config(pack, api_server.url, run_id="run_nodb"))
    assert run.status == "FAILED" and "database not found" in run.error


def test_cli_entry_point(messy_pack, api_server, tmp_path):
    from flasheats_pipeline.cli import main
    code = main(["--source-root", str(messy_pack), "--api-url", api_server.url, "--data-dir", str(tmp_path / "d"), "--output-dir", str(tmp_path / "o"),
                 "--run-id", "run_cli", "--page-size", "5", "--no-charts", "--api-retries", "2", "--api-timeout", "1"])
    assert code == 0 and (tmp_path / "o" / "metrics.csv").exists()

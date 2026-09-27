"""Retrieval completeness beyond the API's own total: client control totals, server-side counts,
the schema contract, and the SQL metric layer agreeing with pandas."""
import json

import pandas as pd
import pytest

from flasheats_pipeline.contracts import check, load_contract
from flasheats_pipeline.ingest import SourceSchemaError
from flasheats_pipeline.pipeline import run_pipeline
from tests.conftest import MESSY_CONTROL_TOTALS, ROOT, build_pack, write_control_totals


def gate_row(run, name):
    return next(c for c in run.gate["checks"] if c["check"] == name)


def test_control_totals_match_passes(messy_pack, api_server, make_config):
    write_control_totals(messy_pack)
    run = run_pipeline(make_config(messy_pack, api_server.url, run_id="run_ct_ok"))
    assert run.status == "COMPLETED", run.error
    ct = run.manifest["inputs"]["control_totals"]
    assert ct["status"] == "PASS" and {r["control"] for r in ct["rows"]} == set(MESSY_CONTROL_TOTALS)
    assert run.manifest["inputs"]["orders_extract_vs_server_count"] == {"extracted": 16, "server_count": 16, "match": True}
    assert "client control totals PASS" in gate_row(run, "Retrieval completeness")["evidence"]


def test_control_total_mismatch_refuses_publication(messy_pack, api_server, make_config):
    write_control_totals(messy_pack, {**MESSY_CONTROL_TOTALS, "support_tickets_rows": 9})   # owner says 9 tickets exist, we got 6
    cfg = make_config(messy_pack, api_server.url, run_id="run_ct_bad")
    run = run_pipeline(cfg)
    assert run.status == "GATE_FAILED"
    assert gate_row(run, "Retrieval completeness")["status"] == "FAIL"
    assert not (cfg.output_dir / "metrics.csv").exists()                      # nothing published
    rows = {r["control"]: r for r in run.manifest["inputs"]["control_totals"]["rows"]}
    assert rows["support_tickets_rows"]["status"] == "MISMATCH" and rows["support_tickets_rows"]["observed"] == 6


def test_no_published_control_totals_is_reported_not_failed(messy_pack, api_server, make_config):
    run = run_pipeline(make_config(messy_pack, api_server.url, run_id="run_ct_none"))
    assert run.manifest["inputs"]["control_totals"]["status"] == "UNKNOWN"
    assert gate_row(run, "Retrieval completeness")["status"] == "PASS"


def test_schema_contract_rules():
    contract = load_contract(ROOT / "config" / "schema_contract.yaml")
    ok = pd.DataFrame(columns=["ticket_id", "order_id", "created_at", "category", "customer_message"])
    assert check(ok, contract, "files", "support_tickets.csv").status == "PASS"
    extra = pd.DataFrame(columns=["ticket_id", "order_id", "created_at", "category", "priority"])
    r = check(extra, contract, "files", "support_tickets.csv")
    assert r.status == "WARN" and r.uncontracted == ["priority"] and r.missing_optional == ["customer_message"]
    with pytest.raises(SourceSchemaError, match="schema drift.*category"):
        check(pd.DataFrame(columns=["ticket_id", "order_id", "created_at"]), contract, "files", "support_tickets.csv")
    assert check(pd.DataFrame(columns=["x"]), contract, "files", "unknown.csv").status == "WARN"


def test_contract_drives_required_columns_of_a_file(tmp_path, api_server, make_config):
    pack = build_pack(tmp_path / "p", messy=True)
    t = pd.read_csv(pack / "data" / "support_tickets.csv", dtype=str).drop(columns=["category"])
    t.to_csv(pack / "data" / "support_tickets.csv", index=False)
    run = run_pipeline(make_config(pack, api_server.url, run_id="run_drift"))
    assert run.status == "FAILED" and "category" in run.error


def test_uncontracted_api_field_only_warns(messy_pack, make_config):
    from tests.conftest import FakeDispatchServer, dispatch_records
    srv = FakeDispatchServer([{**r, "surge_multiplier": 1.2} for r in dispatch_records()]).start()
    try:
        run = run_pipeline(make_config(messy_pack, srv.url, run_id="run_api_extra"))
        assert run.status == "COMPLETED", run.error
        c = next(x for x in run.manifest["inputs"]["schema_contract"] if x["kind"] == "api")
        assert c["status"] == "WARN" and c["uncontracted"] == ["surge_multiplier"]
    finally:
        srv.stop()


def test_sql_metric_layer_agrees_with_pandas(messy_pack, api_server, make_config):
    cfg = make_config(messy_pack, api_server.url, run_id="run_sqlm")
    run = run_pipeline(cfg)
    checks = pd.read_csv(cfg.output_dir / "metric_checks.csv")
    row = checks[checks["check"].str.startswith("SQL metric layer")].iloc[0]
    assert row["status"] == "PASS"
    layer = pd.read_csv(cfg.output_dir / "sql_metric_layer_check.csv")
    assert layer["agrees"].all() and len(layer) == 6
    m1 = pd.read_csv(cfg.output_dir / "sql_metric_views" / "v_m1_late_rate.csv").iloc[0]
    assert m1["late_orders"] == 5 and m1["validated_population"] == 8

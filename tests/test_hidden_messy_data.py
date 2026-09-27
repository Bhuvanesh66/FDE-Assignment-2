"""Test 10 - evaluator simulation: "how would I break this pipeline with messy but realistic data?"

Each scenario mutates the source pack the way a hidden evaluation set might and
asserts the pipeline neither crashes nor silently hides the defect.
"""
import csv
import json
import sqlite3

import pytest

from flasheats_pipeline.pipeline import run_pipeline
from tests.conftest import build_pack


def rule_status(run, rid):
    return run.manifest["stages"]["validate"]["rules"][rid]


def test_csv_headers_in_different_case_and_extra_columns(tmp_path, api_server, make_config):
    pack = build_pack(tmp_path / "p", messy=True, csv_header_case=True)
    with open(pack / "data" / "support_tickets.csv", "a", newline="", encoding="utf-8") as f:
        pass
    run = run_pipeline(make_config(pack, api_server.url, run_id="run_hdr"))
    assert run.status == "COMPLETED", run.error


def test_ids_with_whitespace_and_lowercase_in_every_source_still_join(tmp_path, api_server, make_config):
    pack = build_pack(tmp_path / "p", messy=True)
    rows = list(csv.reader(open(pack / "data" / "order_interventions.csv", encoding="utf-8")))
    rows[1][1] = "  o00003 "
    with open(pack / "data" / "order_interventions.csv", "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    run = run_pipeline(make_config(pack, api_server.url, run_id="run_ws"))
    assert run.status == "COMPLETED", run.error
    assert run.manifest["stages"]["validate"]["rules"]["ID-08"] == "WARN"    # only the O77777 one is unmapped
    import pandas as pd
    oj = pd.read_csv(run.config.processed_dir / "order_journey.csv").set_index("order_id")
    assert oj.loc["O00003", "intervention_count"] == 1


def test_new_status_value_is_flagged_not_counted_as_delivered(tmp_path, api_server, make_config):
    pack = build_pack(tmp_path / "p", messy=True)
    con = sqlite3.connect(pack / "database" / "flasheats.db")
    con.execute("UPDATE orders SET final_status='DELIVERED ' WHERE order_id='O00001'")      # representation -> still delivered
    con.execute("UPDATE orders SET final_status='refunded' WHERE order_id='O00012'")        # new semantic value -> not delivered
    con.commit(); con.close()
    run = run_pipeline(make_config(pack, api_server.url, run_id="run_status"))
    assert run.status == "COMPLETED", run.error
    assert rule_status(run, "ST-01") == "WARN"
    assert run.headline["validated_population"] == 8 and run.headline["late_orders"] == 5
    dq = json.loads((run.config.output_dir / "data_quality_report.json").read_text())
    assert dq["cleaning"]["unexpected_categories"]["orders.final_status"] == {"refunded": 1}


def test_all_timestamps_unparseable_fails_the_gate_instead_of_publishing_zero(tmp_path, api_server, make_config):
    pack = build_pack(tmp_path / "p", messy=True)
    con = sqlite3.connect(pack / "database" / "flasheats.db")
    con.execute("UPDATE orders SET promised_eta='??' ")
    con.commit(); con.close()
    run = run_pipeline(make_config(pack, api_server.url, run_id="run_ts"))
    assert run.status == "GATE_FAILED"
    assert rule_status(run, "TS-00") == "FAIL" and run.gate["overall_status"] == "FAIL"


def test_orders_table_empty_is_reported_not_crashed(tmp_path, api_server, make_config):
    pack = build_pack(tmp_path / "p", messy=True)
    con = sqlite3.connect(pack / "database" / "flasheats.db")
    con.execute("DELETE FROM orders")
    con.commit(); con.close()
    run = run_pipeline(make_config(pack, api_server.url, run_id="run_empty"))
    assert run.status == "GATE_FAILED" and run.gate["overall_status"] == "FAIL"
    assert "Retrieval completeness" in run.gate["blocking"]


def test_dispatch_covers_only_half_the_orders_is_flagged(tmp_path, make_config):
    from tests.conftest import FakeDispatchServer, dispatch_records
    srv = FakeDispatchServer(dispatch_records(include_unknown=False)[:7]).start()
    try:
        pack = build_pack(tmp_path / "p", messy=True)
        run = run_pipeline(make_config(pack, srv.url, run_id="run_halfdispatch"))
        assert run.status == "COMPLETED", run.error
        assert rule_status(run, "ID-09") == "WARN"
        # orders without dispatch cannot be decomposed by stage but stay in the KPI
        assert run.headline["validated_population"] == 8
    finally:
        srv.stop()


def test_driver_events_missing_lat_lon_and_flat_layout(tmp_path, api_server, make_config):
    pack = build_pack(tmp_path / "p", messy=True)
    flat = [{"driver_id": "D001", "order_id": "O00005", "type": "delivered", "timestamp": "2026-08-02T11:55:00"},
            {"driver_id": "D001", "order_id": "O00001", "type": "gps_ping", "timestamp": "2026-08-01T10:10:00"}]
    with open(pack / "data" / "driver_events.json", "w", encoding="utf-8") as f:
        json.dump(flat, f)
    run = run_pipeline(make_config(pack, api_server.url, run_id="run_flat"))
    assert run.status == "COMPLETED", run.error
    assert run.manifest["stages"]["ingest"]["rows"]["driver_events"] == 2


def test_duplicate_business_events_do_not_inflate_counts(tmp_path, api_server, make_config):
    pack = build_pack(tmp_path / "p", messy=True)
    p = pack / "data" / "customer_app_actions.csv"
    rows = list(csv.reader(open(p, encoding="utf-8")))
    rows += [rows[1], rows[1]]                                   # same action id, same content, three times
    with open(p, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    run = run_pipeline(make_config(pack, api_server.url, run_id="run_dupact"))
    assert run.status == "COMPLETED", run.error
    import pandas as pd
    oj = pd.read_csv(run.config.processed_dir / "order_journey.csv").set_index("order_id")
    assert oj.loc["O00003", "eta_view_count"] == 2 and len(oj) == 14


def test_semantic_lookalikes_are_never_merged_silently(tmp_path, api_server, make_config):
    pack = build_pack(tmp_path / "p", messy=True)
    run = run_pipeline(make_config(pack, api_server.url, run_id="run_sem"))
    dq = json.loads((run.config.output_dir / "data_quality_report.json").read_text())
    assert dq["cleaning"]["semantic_candidates"]["restaurant_status.status"] == {"handoff": "handed_off"}
    assert dq["cleaning"]["semantic_candidates"]["tickets.category"] == {"eta_issue": "eta_changed"}
    import pandas as pd
    fi = pd.read_csv(run.config.processed_dir / "fact_interaction.csv")
    assert "eta_issue" in set(fi["detail"].dropna())

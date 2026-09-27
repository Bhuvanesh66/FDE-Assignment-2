"""Business correctness: model grain, aggregation without inflation, hand-checked metrics, zero denominators."""
import pandas as pd
import pytest

from flasheats_pipeline.cleaning import standardise
from flasheats_pipeline.gate import build_gate
from flasheats_pipeline.metrics import compute_metrics
from flasheats_pipeline.model import build_model
from flasheats_pipeline.rules import run_rules
from tests.conftest import EXPECTED
from tests.test_cleaning_rules import load_raw


@pytest.fixture
def modelled(messy_pack, tmp_path, make_config):
    cfg = make_config(messy_pack, "http://unused")
    raw = load_raw(messy_pack, tmp_path)
    clean, rep = standardise(raw, cfg)
    results = run_rules(clean, rep, cfg)
    model = build_model(clean, results, cfg)
    ref = pd.read_csv(messy_pack / "data" / "order_outcomes.csv", dtype="str")
    mr = compute_metrics(model, cfg, reference_outcomes=ref)
    return cfg, clean, rep, results, model, mr


def metric(mr, mid):
    return mr.metrics.set_index("metric_id").loc[mid]


def test_fact_order_grain_and_population(modelled):
    _, _, _, _, model, _ = modelled
    fo = model["fact_order"]
    assert fo["order_id"].is_unique and len(fo) == EXPECTED["unique_orders"]
    assert int(fo["kpi_population"].sum()) == EXPECTED["validated_population"]
    assert set(fo.loc[fo["kpi_exclusion_reason"] != "", "order_id"]) == {"O00005", "O00006", "O00007", "O00013"}
    buckets = fo["outcome_bucket"].value_counts().to_dict()
    assert buckets == {"delivered_late": 5, "delivered_on_time": 3, "cancelled": 1, "unknown_missing_timestamp": 2, "excluded_dq_rule": 2, "other_status": 1}
    assert all(c["row_count_preserved"] for c in model.join_checks)


def test_dispatch_is_authoritative_for_final_driver(modelled):
    _, _, _, _, model, _ = modelled
    fo = model["fact_order"].set_index("order_id")
    assert fo.loc["O00003", "recorded_driver_id"] == "D002" and fo.loc["O00003", "final_driver_id"] == "D001" and fo.loc["O00003", "driver_id"] == "D001"
    assert bool(fo.loc["O00003", "reassigned_flag"]) is True


def test_backfill_sensitivity_is_separate_from_published_kpi(modelled):
    _, _, _, _, model, mr = modelled
    fo = model["fact_order"].set_index("order_id")
    assert int(fo["backfilled_from_driver_event"].sum()) == EXPECTED["backfilled"]
    assert pd.isna(fo.loc["O00005", "actual_delivery_at"]) and fo.loc["O00005", "delay_min_backfilled"] == 15.0
    assert metric(mr, "M1c")["denominator"] == EXPECTED["validated_population"] + 1


def test_journey_aggregation_does_not_inflate_rows(modelled):
    _, _, _, _, model, _ = modelled
    oj = model["order_journey"].set_index("order_id")
    assert len(oj) == EXPECTED["unique_orders"]
    assert oj.loc["O00003", "eta_view_count"] == 2 and bool(oj.loc["O00003", "support_opened"]) and oj.loc["O00003", "ticket_count"] == 1
    assert oj.loc["O00003", "intervention_count"] == 1 and oj.loc["O00003", "intervention_types"] == "DRIVER_REASSIGNMENT"
    assert bool(oj.loc["O00009", "cancel_attempted"]) and bool(oj.loc["O00009", "support_contact"])   # ticket T00006
    assert bool(oj.loc["O00002", "frustrated_no_intervention"])                                       # ticket, no intervention
    assert oj.loc["O00001", "ticket_count"] == 0 and oj.loc["O00001", "intervention_count"] == 0


def test_event_log_is_ordered_and_multi_source(modelled):
    _, _, _, _, model, _ = modelled
    ev = model["fact_event"]
    o3 = ev[ev["order_id"] == "O00003"]
    assert o3["event_time"].is_monotonic_increasing
    assert {"ORDER_CREATED", "DRIVER_ASSIGNED", "DRIVER_REASSIGNED", "PICKED_UP", "DELIVERED", "APP_SUPPORT_OPENED", "SUPPORT_TICKET", "INTERVENTION_DRIVER_REASSIGNMENT", "RESTAURANT_HANDOFF"} <= set(o3["event_type"])
    assert set(o3["source_system"]) >= {"order_platform", "dispatch_api", "customer_app", "support_desk", "interventions_log", "restaurant_status_feed", "driver_app"}


def test_metrics_match_hand_computation(modelled):
    _, _, _, _, _, mr = modelled
    m1 = metric(mr, "M1")
    assert m1["value"] == EXPECTED["late_rate_pct"] and m1["numerator"] == EXPECTED["late_orders"] and m1["denominator"] == EXPECTED["validated_population"]
    m1a = metric(mr, "M1a")
    assert m1a["numerator"] == EXPECTED["historical_late"] and m1a["denominator"] == EXPECTED["historical_population"]
    assert metric(mr, "M1b")["numerator"] == 2                        # > 10 min: O00003 (+20), O00009 (+30); O00002 is exactly 10 -> not counted
    assert metric(mr, "M2")["value"] == EXPECTED["median_lateness_min"]
    assert metric(mr, "M2b")["value"] == 30.0
    m4 = metric(mr, "M4")
    assert m4["numerator"] == 3 and m4["denominator"] == 5             # late with support contact: O00002, O00003, O00009
    m5 = metric(mr, "M5")
    assert m5["numerator"] == 2 and m5["denominator"] == 8             # O00003, O00009 have interventions
    assert metric(mr, "M5a")["value"] == 100.0 and metric(mr, "M5b")["value"] == 50.0
    assert all(c["status"] == "PASS" for c in mr.checks), [c for c in mr.checks if c["status"] != "PASS"]


def test_stage_decomposition_identity_and_breakdowns(modelled):
    _, _, _, _, model, mr = modelled
    fo = model["fact_order"]
    pop = fo[fo["kpi_population"]]
    assert ((pop["pickup_overrun_min"] + pop["transit_overrun_min"]) - pop["delay_min"]).abs().max() < 0.05
    assert 0 <= metric(mr, "M3")["value"] <= 100
    tb = mr.breakdowns["late_rate_by_traffic"].set_index("traffic_bucket")
    assert tb.loc["gridlock", "orders"] == 1 and tb.loc["high", "orders"] == 2
    db = mr.breakdowns["late_rate_by_distance_band"]
    assert db["distance_band"].iloc[-1] == "invalid/unknown" and list(db["distance_band"])[:2] == ["0-3 km", "3-6 km"]
    cv = mr.breakdowns["customer_view_vs_system_view"].set_index("ticket_category")
    assert cv.loc["late_delivery", "tickets"] == 2 and "eta_issue" in cv.index      # 'Late Delivery' normalised into late_delivery; 'ETA issue' NOT merged


def test_gate_is_warn_not_fail_for_recoverable_defects(modelled):
    cfg, _, _, results, _, mr = modelled
    gate = build_gate({"dispatch_api": {"complete": True, "mode": "live", "records_fetched": 15, "expected_total": 15, "pages_fetched": 3, "retries": 0}, "files": {}, "sql": {}}, results, mr, cfg)
    assert gate["overall_status"] == "WARN" and gate["blocking"] == []
    assert {c["check"]: c["status"] for c in gate["checks"]}["KPI definition ownership"] == "UNKNOWN"
    assert "PUBLISH WITH CAVEATS" in gate["publish_decision"]


def test_gate_fails_when_ingestion_incomplete(modelled):
    cfg, _, _, results, _, mr = modelled
    gate = build_gate({"dispatch_api": {"complete": False, "mode": "live", "records_fetched": 10, "expected_total": 15}, "files": {"tickets": {"status": "missing"}}, "sql": {}}, results, mr, cfg)
    assert gate["overall_status"] == "FAIL" and "Retrieval completeness" in gate["blocking"] and "DO NOT PUBLISH" in gate["publish_decision"]


def test_zero_rows_gives_unknown_metrics_not_crash(messy_pack, tmp_path, make_config):
    cfg = make_config(messy_pack, "http://unused")
    raw = load_raw(messy_pack, tmp_path)
    raw["orders"] = raw["orders"].iloc[0:0]
    clean, rep = standardise(raw, cfg)
    results = run_rules(clean, rep, cfg)
    model = build_model(clean, results, cfg)
    mr = compute_metrics(model, cfg)
    assert len(model["fact_order"]) == 0
    assert metric(mr, "M1")["value"] is None or pd.isna(metric(mr, "M1")["value"])
    assert any(c["check"] == "KPI denominator > 0" and c["status"] == "FAIL" for c in mr.checks)
    gate = build_gate({"dispatch_api": {"complete": True, "mode": "live"}, "files": {}, "sql": {"extracts": [{"name": "orders_extract", "rows": 0}]}}, results, mr, cfg)
    assert gate["overall_status"] == "FAIL"

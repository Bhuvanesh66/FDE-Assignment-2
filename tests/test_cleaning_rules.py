"""Tests 2-7 - cleaning is representation-only and every business rule fires on the messy pack."""
import pandas as pd
import pytest

from flasheats_pipeline.cleaning import standardise
from flasheats_pipeline.ingest import SqlSource, flatten_driver_events, read_csv_source, read_json_source
from flasheats_pipeline.rules import kpi_exclusions, order_flags, run_rules
from tests.conftest import EXPECTED, ROOT, dispatch_records


def load_raw(pack, tmp_path):
    raw = {}
    src = SqlSource(pack / "database" / "flasheats.db", ROOT / "sql", tmp_path / "raw")
    raw["orders"] = src.extract("orders_extract", "orders", {"start_at": None, "end_at": None})
    raw["restaurants"] = src.extract("restaurants_extract", "restaurants")
    raw["drivers"] = src.extract("drivers_extract", "drivers")
    raw["customers"] = src.extract("customers_extract", "customers")
    raw["tickets"], _ = read_csv_source(pack / "data" / "support_tickets.csv", "tickets", ["ticket_id", "order_id", "created_at", "category"], tmp_path / "raw")
    raw["restaurant_status"], _ = read_csv_source(pack / "data" / "restaurant_status.csv", "restaurant_status", ["order_id", "restaurant_id", "status", "last_updated_at"], tmp_path / "raw")
    raw["app_actions"], _ = read_csv_source(pack / "data" / "customer_app_actions.csv", "app_actions", ["action_id", "order_id", "customer_id", "action_type", "action_at"], tmp_path / "raw")
    raw["interventions"], _ = read_csv_source(pack / "data" / "order_interventions.csv", "interventions", ["intervention_id", "order_id", "intervention_type", "intervention_at", "initiated_by"], tmp_path / "raw")
    obj, res = read_json_source(pack / "data" / "driver_events.json", "driver_events", tmp_path / "raw")
    raw["driver_events"] = flatten_driver_events(obj, res)
    raw["dispatch"] = pd.DataFrame(dispatch_records(include_unknown=True, duplicate_first=True), dtype="object")
    return raw


@pytest.fixture
def cleaned(messy_pack, tmp_path, make_config):
    cfg = make_config(messy_pack, "http://unused")
    raw = load_raw(messy_pack, tmp_path)
    clean, rep = standardise(raw, cfg)
    return raw, clean, rep, cfg


# ----------------------------------------------------------------------------- cleaning
def test_duplicates_exact_dropped_conflicting_kept_first_and_recorded(cleaned):
    raw, clean, rep, _ = cleaned
    assert len(raw["orders"]) == 16 and len(clean["orders"]) == EXPECTED["unique_orders"]
    assert clean["orders"]["order_id"].is_unique
    conflicts = rep.duplicate_conflicts["orders"]
    assert set(conflicts["order_id"]) == {"O00002"} and "traffic_bucket" in conflicts["conflicting_columns"].iloc[0]
    assert any(a.action == "drop_exact_duplicate_rows" and a.dataset == "orders" for a in rep.actions)
    assert clean["orders"].set_index("order_id").loc["O00002", "traffic_bucket"] == "medium"      # first row wins


def test_identifiers_are_trimmed_and_uppercased(cleaned):
    _, clean, rep, _ = cleaned
    assert "O00010" in set(clean["orders"]["order_id"]) and "o00010 " not in set(clean["orders"]["order_id"])
    assert any(a.action.startswith("normalise_id") and a.dataset == "orders" for a in rep.actions)


def test_categories_representation_fixed_semantics_kept(cleaned):
    _, clean, rep, _ = cleaned
    o = clean["orders"].set_index("order_id")
    assert o.loc["O00008", "final_status"] == "delivered" and o.loc["O00008", "traffic_bucket"] == "high"
    assert o.loc["O00009", "traffic_bucket"] == "gridlock"                       # unexpected value retained
    assert rep.unexpected_categories["orders.traffic_bucket"] == {"gridlock": 1}
    assert rep.unexpected_categories["orders.final_status"] == {"suspended": 1}
    t = clean["tickets"]
    assert "late_delivery" in set(t["category"]) and "Late Delivery" not in set(t["category"])
    assert "eta_issue" in set(t["category"])                                       # NOT merged into eta_changed
    assert rep.semantic_candidates["tickets.category"] == {"eta_issue": "eta_changed"}
    assert rep.semantic_candidates["restaurant_status.status"] == {"handoff": "handed_off"}


def test_timestamps_parsed_and_issues_counted(cleaned):
    _, clean, rep, _ = cleaned
    o = clean["orders"].set_index("order_id")
    assert str(o["actual_delivery_at"].dtype) == "datetime64[ns]"
    assert pd.isna(o.loc["O00013", "actual_delivery_at"])                          # 'not-a-date' -> NaT
    assert o.loc["O00014", "created_at"] == pd.Timestamp("2026-08-05 11:00:00")   # tz-aware normalised
    stats = {s["column"]: s for s in rep.timestamp_stats}
    assert stats["orders.actual_delivery_at"]["unparseable"] == 1
    assert stats["orders.created_at"]["tz_aware_converted"] == 1


def test_numeric_coercion_and_dispatch_dedup(cleaned):
    _, clean, rep, _ = cleaned
    assert clean["orders"]["distance_km_estimate"].dtype.kind == "f"
    assert clean["dispatch"]["order_id"].is_unique and len(clean["dispatch"]) == 15  # duplicate O00001 dropped


# ----------------------------------------------------------------------------- rules
def test_rules_fire_on_every_injected_defect(cleaned):
    _, clean, rep, cfg = cleaned
    res = {r.rule.id: r for r in run_rules(clean, rep, cfg, {"stakeholders": {"a": "b"}})}
    assert res["GR-01"].status == "WARN" and res["GR-01"].violations == 0        # corrected, reported
    assert set(res["ID-03"].violating_keys) == {"O00010"}                          # null restaurant
    assert set(res["ID-04"].violating_keys) == {"O00011"}                          # unknown driver D999
    assert res["ID-05"].violations == 2                                            # null + unknown order in tickets
    assert res["ID-06"].violations == 2                                            # foreign order + restaurant mismatch
    assert res["ID-08"].violations == 1                                            # intervention for unknown order
    assert res["ID-09"].extra["dispatch_unknown_orders"] == 1 and res["ID-09"].status == "WARN"
    assert res["ST-01"].extra["unexpected"] == {"suspended": 1} and res["ST-01"].extra["representation_fixes"] == 1
    assert res["ST-02"].extra["unexpected"] == {"gridlock": 1}
    assert res["ST-04"].extra["semantic_candidates"] == {"handoff": "handed_off"}
    assert res["TS-00"].violations == 1                                            # 'not-a-date'
    assert set(res["TS-01"].violating_keys) == {"O00006"}
    assert set(res["TS-02"].violating_keys) == {"O00007"}
    assert set(res["TS-04"].violating_keys) == {"O00005", "O00013"} and res["TS-04"].extra["recoverable_from_driver_events"] == 1
    assert res["TS-07"].violations == 1                                            # O00003 picked_up < assigned
    assert set(res["RG-01"].violating_keys) == {"O00009"}
    assert set(res["RG-02"].violating_keys) == {"R002"}
    assert res["RG-03"].violations == 1
    assert res["CX-01"].violations == 1                                            # O00003 reassigned
    assert res["CX-03"].extra["overlap"] == 1
    assert res["FR-01"].violations >= 1
    assert res["KPI-01"].status == "UNKNOWN"


def test_kpi_exclusions_only_use_reject_rules(cleaned):
    _, clean, rep, cfg = cleaned
    results = run_rules(clean, rep, cfg)
    excl = kpi_exclusions(results)
    assert set(excl) == {"O00006", "O00007", "O00005", "O00013"}
    assert excl["O00006"] == ["TS-01"] and excl["O00007"] == ["TS-02"]
    flags = order_flags(results)
    assert "RG-01" in flags["O00009"] and "ST-02" in flags["O00009"]
    assert "ID-03" in flags["O00010"] and "ID-04" in flags["O00011"]


def test_rules_are_unknown_when_a_source_is_absent(cleaned):
    _, clean, rep, cfg = cleaned
    partial = {k: v for k, v in clean.items() if k not in ("dispatch", "restaurant_status")}
    res = {r.rule.id: r for r in run_rules(partial, rep, cfg)}
    assert res["ID-09"].status == "UNKNOWN" and res["FR-01"].status == "UNKNOWN" and res["CX-01"].status == "UNKNOWN"

"""Record reconciliation ledger and run-over-run drift monitoring."""
import json

import pandas as pd

from flasheats_pipeline.cleaning import CleaningReport
from flasheats_pipeline.monitoring import build_ledger, compare_runs, comparison_to_markdown
from flasheats_pipeline.pipeline import run_pipeline


def test_ledger_balances_and_detects_a_silent_drop():
    rep = CleaningReport()
    rep.raw_row_counts = {"orders": 16, "tickets": 6}
    rep.clean_row_counts = {"orders": 14, "tickets": 5}
    rep.add("orders", "*", "drop_exact_duplicate_rows", 1)
    rep.add("orders", "order_id", "drop_conflicting_duplicate_key_rows (keep first)", 1)
    rep.add("tickets", "*", "drop_exact_duplicate_rows", 1)
    ledger, checks = build_ledger(rep)
    assert ledger["balanced"].all() and checks[0]["status"] == "PASS"
    rep.clean_row_counts["tickets"] = 4                     # one row vanished without an action
    ledger, checks = build_ledger(rep)
    assert not ledger.set_index("dataset").loc["tickets", "balanced"] and checks[0]["status"] == "FAIL"


def test_order_ledger_check():
    fo = pd.DataFrame({"outcome_bucket": ["delivered_late", "delivered_on_time", "cancelled"], "kpi_population": [True, True, False]})
    _, checks = build_ledger(CleaningReport(), fo)
    assert checks[1]["status"] == "PASS" and "3 orders" in checks[1]["evidence"]


def _manifest(run_id, rate, rules, violations):
    return {"run_id": run_id, "stages": {"metrics": {"headline": {"late_delivery_rate_pct": rate}}, "validate": {"rules": rules, "violations": violations}}}


def test_compare_runs_states():
    cur = {"run_id": "B", "headline": {"late_delivery_rate_pct": 56.0}, "rules": {"TS-01": "WARN"}, "violations": {"TS-01": 4}}
    assert compare_runs(None, cur, 2.0)["status"] == "UNKNOWN"
    stable = compare_runs(_manifest("A", 55.5, {"TS-01": "WARN"}, {"TS-01": 4}), cur, 2.0)
    assert stable["status"] == "PASS" and stable["baseline_run"] == "A" and stable["rules"] == []
    drift = compare_runs(_manifest("A", 50.0, {"TS-01": "WARN"}, {"TS-01": 4}), cur, 2.0)
    assert drift["status"] == "WARN" and "DRIFT" in drift["summary"]
    worse = compare_runs(_manifest("A", 56.0, {"TS-01": "PASS"}, {"TS-01": 0}), cur, 2.0)
    assert worse["status"] == "WARN" and "TS-01" in worse["summary"]
    assert "| TS-01 | PASS | WARN | 0 | 4 |" in comparison_to_markdown(worse)


def test_rerun_with_same_id_is_compared_with_its_previous_publication():
    cur = {"run_id": "A", "headline": {"late_delivery_rate_pct": 56.0}, "rules": {"TS-01": "WARN"}, "violations": {"TS-01": 4}}
    prev = _manifest("A", 56.0, {"TS-01": "WARN"}, {"TS-01": 4}) | {"finished_at": "2026-09-27T10:00:00"}
    res = compare_runs(prev, cur, 2.0)
    assert res["status"] == "PASS" and res["baseline_run"] == "A"
    assert "previous publication, 2026-09-27T10:00:00" in res["summary"] and "+0.00 pp" in res["summary"]


def test_pipeline_rerun_compares_with_previous_published_run(messy_pack, api_server, make_config):
    r1 = run_pipeline(make_config(messy_pack, api_server.url, run_id="run_1"))
    api_server.hits.clear()
    r2 = run_pipeline(make_config(messy_pack, api_server.url, run_id="run_2"))
    assert r1.status == r2.status == "COMPLETED"
    first = json.loads((r1.config.run_output_dir / "run_comparison.json").read_text())
    second = json.loads((r2.config.run_output_dir / "run_comparison.json").read_text())
    assert first["status"] == "UNKNOWN" and second["status"] == "PASS" and second["baseline_run"] == "run_1"
    ledger = pd.read_csv(r2.config.output_dir / "reconciliation_ledger.csv")
    assert ledger["balanced"].all() and ledger.set_index("dataset").loc["orders", "raw_rows"] == 16

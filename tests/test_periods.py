"""Partitioned runs: every order in exactly one period, periods add up to the full run, one scorecard."""
import json

import pandas as pd

from flasheats_pipeline.periods import run_periods, weekly_periods
from flasheats_pipeline.pipeline import run_pipeline
from tests.conftest import write_control_totals

PERIODS = [("2026-08-01", "2026-08-02"), ("2026-08-03", "2026-08-05")]
# the 14-order test pack is tiny: one bad order in a 6-order period is 16.7 %, above the default 15 % tolerance.
# These tests raise the tolerances to test the partitioning itself; test_default_policy_refuses_noisy_partitions
# proves the defaults refuse such a period instead of publishing it.
LOOSE = dict(max_missing_delivery_time_pct=50.0, max_unparseable_kpi_timestamp_pct=50.0, max_unexpected_status_pct=50.0)


def test_weekly_split_follows_the_data_span(messy_pack, make_config):
    assert weekly_periods(make_config(messy_pack, "http://unused")) == [("2026-08-01", "2026-08-05")]
    assert weekly_periods(make_config(messy_pack, "http://unused"), days=2) == [("2026-08-01", "2026-08-02"), ("2026-08-03", "2026-08-04"), ("2026-08-05", "2026-08-05")]


def test_periods_partition_the_orders_and_add_up(messy_pack, api_server, make_config):
    write_control_totals(messy_pack)
    full = run_pipeline(make_config(messy_pack, api_server.url, run_id="run_full", **LOOSE))
    assert full.status == "COMPLETED", full.error
    api_server.hits.clear()
    base = make_config(messy_pack, api_server.url, run_id="run_wk", write_charts=True, **LOOSE)
    result = run_periods(base, PERIODS)
    card = result["scorecard"].set_index("period")
    assert result["overall"] == "COMPLETE"
    # created 1-2 Aug: O00001-O00006; 3-5 Aug: O00007-O00014 (incl. the lower-case id and the tz-aware order)
    assert card.loc["2026-08-01_2026-08-02", "orders"] == 6 and card.loc["2026-08-03_2026-08-05", "orders"] == 8
    assert card.loc["2026-08-01_2026-08-02", "validated_population"] == 3 and card.loc["2026-08-01_2026-08-02", "late_orders"] == 2
    assert card.loc["2026-08-03_2026-08-05", "validated_population"] == 5 and card.loc["2026-08-03_2026-08-05", "late_orders"] == 3
    pc = result["partition_check"]
    assert pc["status"] == "PASS" and pc["orders_in_periods"] == 14 and pc["adds_up_to_full_run"] is True
    out = base.output_dir
    assert (out / "scorecard.md").exists() and (out / "charts" / "weekly_scorecard.png").exists()
    for p in card.index:
        assert (out / "periods" / p / "validation_gate.md").exists() and (out / "periods" / p / "decision_memo.md").exists()
        ledger = pd.read_csv(out / "periods" / p / "reconciliation_ledger.csv")
        assert ledger["balanced"].all()                                   # out-of-period records are counted, not lost
        assert (ledger["out_of_period"] > 0).any()
    # the published full-period evidence is untouched by the period runs
    assert json.loads((out / "run_manifest.json").read_text())["run_id"] == "run_full"


def test_unknown_order_references_survive_period_scoping(messy_pack, api_server, make_config):
    run = run_pipeline(make_config(messy_pack, api_server.url, run_id="run_p1", period_start="2026-08-01", period_end="2026-08-02", **LOOSE))
    assert run.status == "COMPLETED", run.error
    rules = run.manifest["stages"]["validate"]["violations"]
    assert rules["ID-08"] == 1          # intervention for O77777 (exists nowhere) is still flagged in the period run
    assert rules["ID-06"] >= 1          # restaurant status for the foreign order O88888 likewise


def test_default_policy_refuses_noisy_partitions(messy_pack, api_server, make_config):
    run = run_pipeline(make_config(messy_pack, api_server.url, run_id="run_p_default", period_start="2026-08-01", period_end="2026-08-02"))
    assert run.status == "GATE_FAILED"
    ts = next(c for c in run.gate["checks"] if c["check"].startswith("Timestamp"))
    assert ts["status"] == "FAIL" and "TS-04=1" in ts["evidence"]      # 1 of 6 delivered orders has no delivery time


def test_a_failing_period_does_not_block_the_others(messy_pack, api_server, make_config):
    write_control_totals(messy_pack, {"orders_rows": 99})                 # control total will not match
    result = run_periods(make_config(messy_pack, api_server.url, run_id="run_bad", **LOOSE), PERIODS)
    assert result["overall"] == "NONE_PUBLISHED"
    assert set(result["scorecard"]["status"]) == {"REFUSED"}
    assert (make_config(messy_pack, api_server.url).output_dir / "scorecard.md").exists()

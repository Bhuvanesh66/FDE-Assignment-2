"""Decision layer: every number hand-checked on the 14-order messy pack."""
import pandas as pd
import pytest

from flasheats_pipeline.cleaning import standardise
from flasheats_pipeline.insights import (compute_insights, early_warning_backtest, eta_calibration, fair_ranking, gps_arrival_feasibility,
                                         impact_whatif, weather_truth, wilson_interval)
from flasheats_pipeline.metrics import compute_metrics
from flasheats_pipeline.model import build_model
from flasheats_pipeline.rules import cohen_kappa, run_rules
from tests.conftest import RAIN_HOURS, weather_payload
from tests.test_cleaning_rules import load_raw


@pytest.fixture
def modelled(messy_pack, tmp_path, make_config):
    cfg = make_config(messy_pack, "http://unused")
    raw = load_raw(messy_pack, tmp_path)
    clean, rep = standardise(raw, cfg)
    results = run_rules(clean, rep, cfg)
    model = build_model(clean, results, cfg)
    mr = compute_metrics(model, cfg)
    return cfg, clean, model, mr


def test_wilson_interval_known_values():
    lo, hi = wilson_interval(5, 10, 0.95)
    assert round(lo, 4) == 0.2366 and round(hi, 4) == 0.7634
    assert all(pd.isna(x) for x in wilson_interval(0, 0))
    lo0, hi0 = wilson_interval(0, 20)
    assert lo0 == pytest.approx(0.0, abs=1e-12) and 0 < hi0 < 0.2


def test_cohen_kappa():
    a = pd.Series([True, True, False, False])
    assert cohen_kappa(a, a) == 1.0
    assert cohen_kappa(a, ~a) == -1.0
    assert cohen_kappa(pd.Series([], dtype=bool), pd.Series([], dtype=bool)) is None


def test_early_warning_backtest_hand_checked(modelled):
    cfg, _, model, _ = modelled
    grid, cmp, head = early_warning_backtest(model["fact_order"], model["fact_intervention"], cfg)
    allg = grid[grid["split"] == "all"].set_index("grace_min")
    # pickup overrun vs Dispatch estimate: O1 0, O2 +5 (late), O3 +15 (late), O8 +5 (late), O9 +20 (late), O10 0, O11 +5 (on time), O14 +5 (late)
    assert allg.loc[0, "alerts"] == 6 and allg.loc[0, "precision_pct"] == 83.3 and allg.loc[0, "recall_pct"] == 100.0
    assert allg.loc[5, "alerts"] == 2 and allg.loc[5, "precision_pct"] == 100.0 and allg.loc[5, "recall_pct"] == 40.0
    assert allg.loc[5, "median_lead_min"] == 20.0 and allg.loc[5, "alerts_before_promise_pct"] == 100.0
    assert allg.loc[15, "caught_late"] == 1
    # all orders fall on 1-5 Aug, so there is no hold-out week - the result says so instead of pretending
    assert head["holdout"] is False
    assert head["chosen_grace_min"] == 5                          # highest recall with precision >= 90 %
    caught = cmp.set_index("group").loc["late orders the trigger catches"]
    assert caught["orders"] == 2 and caught["with_any_intervention"] == 2      # O00003 and O00009 both had one


def test_eta_calibration_hand_checked(modelled):
    cfg, _, model, _ = modelled
    table, head = eta_calibration(model["fact_order"], cfg)
    allv = table[table["eta_model_version"] == "all versions"].set_index("padding_min")
    # delays: -5, +10, +20, +3, +30, -2, -1, +5
    assert allv.loc[0, "late_orders"] == 5 and allv.loc[5, "late_orders"] == 3 and allv.loc[30, "late_orders"] == 0
    assert list(allv["late_rate_pct"]) == sorted(allv["late_rate_pct"], reverse=True)      # monotone
    assert head["padding_needed_min"] == 20                      # 80 % on time needs at most 1 of 8 late
    assert head["late_rate_at_needed_padding_pct"] == 12.5


def test_fair_ranking_does_not_blame_small_samples(modelled):
    _, _, model, _ = modelled
    t, head = fair_ranking(model["fact_order"], "restaurant_id", min_orders=15, confidence=0.95)
    assert set(t["verdict"]) == {"too few orders to judge"} and head["significantly_worse"] == 0
    t1, head1 = fair_ranking(model["fact_order"], "restaurant_id", min_orders=1, confidence=0.95)
    r003 = t1.set_index("restaurant_id").loc["R003"]
    assert r003["late_rate_pct"] == 100.0 and r003["verdict"] == "not distinguishable from fleet"    # 3 of 3 is not proof
    assert "UNKNOWN" in set(t1["restaurant_id"])                  # the null-restaurant order is kept, not dropped


def test_weather_truth(modelled):
    cfg, _, model, _ = modelled
    from flasheats_pipeline.ingest import parse_open_meteo
    wx = parse_open_meteo(weather_payload(RAIN_HOURS))
    by_label, late_by, head = weather_truth(model["fact_order"], wx, cfg)
    assert head["orders_covered"] == 14
    assert head["kappa"] < 0 and head["agreement_pct"] == round(100 * 9 / 14, 1)
    lab = by_label.set_index("weather_bucket")
    assert lab.loc["heavy_rain", "observed_rain_share_pct"] == 0.0 and lab.loc["clear", "orders"] == 11
    assert lab.loc["clear", "observed_rain_share_pct"] == round(100 * 2 / 11, 1)       # the two rainy hours were labelled clear
    empty_a, empty_b, empty_h = weather_truth(model["fact_order"], None, cfg)
    assert empty_a.empty and empty_b.empty and empty_h == {}


def test_gps_feasibility_detects_converging_and_diverging_pings():
    fo = pd.DataFrame({"order_id": ["A", "B"], "restaurant_id": ["R1", "R1"], "pickup_at": pd.to_datetime(["2026-08-01 10:30", "2026-08-01 11:30"])})
    rest = pd.DataFrame({"restaurant_id": ["R1"], "lat": [12.95], "lon": [77.60], "coords_valid": [True]})

    def pings(converge: bool):
        lats = [12.99, 12.97, 12.951] if converge else [12.951, 12.97, 12.99]
        return [{"order_id": o, "type": "gps_ping", "timestamp": pd.Timestamp(f"2026-08-01 {h}:{m:02d}"), "lat": la, "lon": 77.60}
                for o, h in [("A", 10), ("B", 11)] for m, la in zip((0, 10, 20), lats)]
    t_ok, h_ok = gps_arrival_feasibility(pd.DataFrame(pings(True)), fo, rest)
    assert h_ok["approaching_pct"] == 100.0 and h_ok["verdict"].startswith("GPS could")
    t_bad, h_bad = gps_arrival_feasibility(pd.DataFrame(pings(False)), fo, rest)
    assert h_bad["approaching_pct"] == 0.0 and h_bad["verdict"].startswith("GPS cannot")


def test_impact_whatif_and_full_insights(modelled):
    cfg, clean, model, mr = modelled
    ins = compute_insights(model, clean, mr.metrics, cfg)
    ew = ins.headline["early_warning"]
    wi = impact_whatif(ew, mr.metrics, cfg)
    assert list(wi["assumed_share_of_caught_late_orders_saved"]) == [0.25, 0.5]
    assert wi.iloc[1]["late_orders_prevented"] == round(0.5 * ew["all_caught_late"])
    assert (wi["basis"].str.startswith("ASSUMPTION")).all()
    assert {f["id"] for f in ins.findings} >= {"D1", "D2", "D3"}
    assert "late_rate_heatmap_weekday_hour" in ins.tables
    assert impact_whatif({}, mr.metrics, cfg).empty


def test_insights_survive_empty_orders(messy_pack, tmp_path, make_config):
    cfg = make_config(messy_pack, "http://unused")
    raw = load_raw(messy_pack, tmp_path)
    raw["orders"] = raw["orders"].iloc[0:0]
    clean, rep = standardise(raw, cfg)
    model = build_model(clean, run_rules(clean, rep, cfg), cfg)
    ins = compute_insights(model, clean, compute_metrics(model, cfg).metrics, cfg)
    assert ins.findings == [] and ins.headline["early_warning"] == {}

"""The independent external source (Open-Meteo): validation, retries, fallback, and the WX-01 rule."""
import json

import pandas as pd
import pytest

from flasheats_pipeline.ingest import ObservedWeatherClient, WeatherSourceError, parse_open_meteo
from flasheats_pipeline.pipeline import run_pipeline
from tests.conftest import RAIN_HOURS, weather_payload


def client(srv, tmp_path, cache=True, **kw):
    return ObservedWeatherClient(srv.url, 12.97, 77.59, "Asia/Kolkata", tmp_path / "raw", cache_dir=(tmp_path / "cache") if cache else None,
                                 timeout_s=1.0, max_retries=2, backoff_s=0.0, sleep=lambda s: None, **kw)


def test_parse_validates_structure():
    df = parse_open_meteo(weather_payload(RAIN_HOURS), expected_tz="Asia/Kolkata")
    assert len(df) == 120 and df["precipitation_mm"].sum() == 4.0
    with pytest.raises(WeatherSourceError, match="no hourly"):
        parse_open_meteo({"latitude": 1})
    with pytest.raises(WeatherSourceError, match="empty"):
        parse_open_meteo({"hourly": {"time": [], "precipitation": []}})
    with pytest.raises(WeatherSourceError, match="equal length"):
        parse_open_meteo({"hourly": {"time": ["2026-08-01T00:00"], "precipitation": []}})
    with pytest.raises(WeatherSourceError, match="timezone"):
        parse_open_meteo({**weather_payload(), "timezone": "UTC"}, expected_tz="Asia/Kolkata")
    with pytest.raises(WeatherSourceError, match="reported an error"):
        parse_open_meteo({"error": True, "reason": "bad date"})


def test_live_fetch_preserves_raw_and_seeds_cache(weather_server, tmp_path):
    df, rep = client(weather_server, tmp_path).fetch("2026-08-01", "2026-08-05")
    assert rep.mode == "live" and rep.hours == 120 and df is not None
    assert (tmp_path / "raw" / "external" / "open_meteo_archive.json").exists()
    cached = list((tmp_path / "cache").glob("open_meteo_*.json"))
    assert len(cached) == 1


def test_transient_error_is_retried(weather_server, tmp_path):
    weather_server.mode = "flaky"
    df, rep = client(weather_server, tmp_path).fetch("2026-08-01", "2026-08-05")
    assert rep.mode == "live" and rep.retries == 1 and "503" in rep.errors[0]


@pytest.mark.parametrize("mode", ["always_500", "bad_request", "not_json", "no_hourly", "empty", "length_mismatch", "wrong_tz"])
def test_unusable_responses_fall_back_to_cache_then_unavailable(weather_server, tmp_path, mode):
    ok_df, _ = client(weather_server, tmp_path).fetch("2026-08-01", "2026-08-05")      # seed the reference copy
    weather_server.mode = mode
    df, rep = client(weather_server, tmp_path).fetch("2026-08-01", "2026-08-05")
    assert rep.mode == "cache" and df is not None and len(df) == len(ok_df) and rep.errors
    df2, rep2 = client(weather_server, tmp_path / "no_cache", cache=False).fetch("2026-08-01", "2026-08-05")
    assert df2 is None and rep2.mode == "unavailable"


def test_unreachable_api_without_cache_is_unavailable_not_a_crash(tmp_path):
    c = ObservedWeatherClient("http://127.0.0.1:9/v1/archive", 12.97, 77.59, "Asia/Kolkata", tmp_path / "raw", timeout_s=0.3, max_retries=1, sleep=lambda s: None)
    df, rep = c.fetch("2026-08-01", "2026-08-05")
    assert df is None and rep.mode == "unavailable" and len(rep.errors) == 2


def test_pipeline_weather_cross_check(messy_pack, api_server, weather_server, make_config):
    cfg = make_config(messy_pack, api_server.url, run_id="run_wx", weather_enabled=True, weather_base_url=weather_server.url, weather_max_retries=1)
    run = run_pipeline(cfg)
    assert run.status == "COMPLETED", run.error
    assert run.manifest["inputs"]["external_weather"]["mode"] == "live"
    assert run.manifest["stages"]["validate"]["rules"]["WX-01"] == "WARN"
    # labelled rain on O00003, O00009, O00011; observed rain at the hours of O00001 and O00002 -> 5 disagreements of 14
    assert run.manifest["stages"]["validate"]["violations"]["WX-01"] == 5
    assert (cfg.raw_dir / "external" / "open_meteo_archive.json").exists()
    gate = {c["check"]: c["status"] for c in run.gate["checks"]}
    assert gate["Independent cross-check (observed weather vs client label)"] == "WARN"
    ins = json.loads((cfg.output_dir / "insights" / "insights.json").read_text())
    assert ins["headline"]["weather"]["orders_covered"] == 14 and ins["headline"]["weather"]["kappa"] < 0.2
    assert any(f["id"] == "D4" for f in ins["findings"])


def test_pipeline_with_weather_disabled_marks_rule_unknown(messy_pack, api_server, make_config):
    run = run_pipeline(make_config(messy_pack, api_server.url, run_id="run_nowx"))
    assert run.status == "COMPLETED"
    assert run.manifest["inputs"]["external_weather"]["mode"] == "disabled"
    assert run.manifest["stages"]["validate"]["rules"]["WX-01"] == "UNKNOWN"


def test_weather_agreeing_with_label_passes(messy_pack, api_server, make_config, tmp_path):
    from tests.conftest import FakeWeatherServer
    # rain observed exactly at the hours of the three orders labelled rain / heavy_rain
    agree = FakeWeatherServer(weather_payload({"2026-08-01T12:00", "2026-08-03T12:00", "2026-08-04T11:00"})).start()
    try:
        run = run_pipeline(make_config(messy_pack, api_server.url, run_id="run_wx_ok", weather_enabled=True, weather_base_url=agree.url))
        assert run.manifest["stages"]["validate"]["rules"]["WX-01"] == "PASS"
        assert run.manifest["stages"]["validate"]["violations"]["WX-01"] == 0
    finally:
        agree.stop()

"""The stakeholder policy file: values flow into the run, typos fail loudly, CLI flags override."""
import json

import pytest

from flasheats_pipeline.config import ConfigError, PipelineConfig, load_config
from tests.conftest import ROOT


def test_repository_policy_file_loads_and_matches_defaults():
    cfg = load_config(ROOT / "config" / "pipeline.yaml")
    d = PipelineConfig()
    assert cfg.late_threshold_min == d.late_threshold_min == 0
    assert cfg.meaningful_late_threshold_min == 10
    assert cfg.lat_range == (12.5, 13.5) and cfg.ew_grace_minutes_grid == (0, 5, 10, 15, 20, 25, 30)
    assert cfg.config_file.endswith("pipeline.yaml")


def test_values_and_overrides(tmp_path):
    p = tmp_path / "policy.yaml"
    p.write_text("kpi:\n  late_threshold_min: 5\nearly_warning:\n  min_precision: 0.8\n", encoding="utf-8")
    cfg = load_config(p, run_id="run_x", late_threshold_min=None)
    assert cfg.late_threshold_min == 5 and cfg.ew_min_precision == 0.8 and cfg.run_id == "run_x"
    assert load_config(p, late_threshold_min=7).late_threshold_min == 7        # explicit override wins


@pytest.mark.parametrize("text,msg", [
    ("kpi:\n  late_treshold_min: 5\n", "unknown key 'kpi.late_treshold_min'"),
    ("kpis:\n  late_threshold_min: 5\n", "unknown section 'kpis'"),
    ("- a\n- b\n", "top level must be a mapping"),
    ("kpi: 5\n", "must be a mapping"),
])
def test_typos_fail_loudly(tmp_path, text, msg):
    p = tmp_path / "bad.yaml"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match=msg):
        load_config(p)


def test_missing_file_and_unknown_override(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")
    with pytest.raises(ConfigError, match="unknown config override"):
        load_config(None, not_a_setting=1)


def test_cli_applies_policy_file(messy_pack, api_server, tmp_path):
    from flasheats_pipeline.cli import main
    p = tmp_path / "policy.yaml"
    p.write_text("kpi:\n  late_threshold_min: 10\nexternal_weather:\n  enabled: false\n", encoding="utf-8")
    code = main(["--config", str(p), "--source-root", str(messy_pack), "--api-url", api_server.url, "--data-dir", str(tmp_path / "d"),
                 "--output-dir", str(tmp_path / "o"), "--run-id", "run_policy", "--page-size", "5", "--no-charts", "--api-timeout", "1"])
    assert code == 0
    manifest = json.loads((tmp_path / "o" / "run_manifest.json").read_text())
    assert manifest["config"]["late_threshold_min"] == 10 and manifest["config"]["config_file"].endswith("policy.yaml")
    # under "late = more than 10 min" only O00003 (+20) and O00009 (+30) are late
    assert manifest["stages"]["metrics"]["headline"]["late_orders"] == 2


def test_cli_rejects_bad_policy(tmp_path):
    from flasheats_pipeline.cli import main
    p = tmp_path / "bad.yaml"
    p.write_text("kpi:\n  typo: 1\n", encoding="utf-8")
    assert main(["--config", str(p), "--run-id", "x"]) == 1

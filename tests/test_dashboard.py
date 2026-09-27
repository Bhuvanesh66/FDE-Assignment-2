"""The Streamlit dashboard renders from real pipeline outputs and its simulators react to input."""
import os

import pytest

from flasheats_pipeline.pipeline import run_pipeline
from tests.conftest import ROOT

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def test_dashboard_renders_and_simulates(messy_pack, api_server, make_config, monkeypatch):
    cfg = make_config(messy_pack, api_server.url, run_id="run_dash", write_charts=True)
    assert run_pipeline(cfg).status == "COMPLETED"
    monkeypatch.setenv("FLASHEATS_OUTPUT_DIR", str(cfg.output_dir))
    monkeypatch.setenv("FLASHEATS_PROCESSED_DIR", str(cfg.processed_dir))
    at = AppTest.from_file(str(ROOT / "app" / "dashboard.py"), default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    labels = {m.label: m.value for m in at.metric}
    assert labels["M1 · Late delivery rate (validated population)"] == "62.5 %"
    at.slider[0].set_value(5).run()                              # early-warning grace minutes
    assert {m.label: m.value for m in at.metric}["precision"] == "100.0%"
    at.text_input[0].set_value("o00009").run()                   # order explorer tolerates lower case
    assert not at.exception and not at.error


def test_dashboard_without_runs_explains_what_to_do(tmp_path, monkeypatch):
    monkeypatch.setenv("FLASHEATS_OUTPUT_DIR", str(tmp_path / "empty"))
    at = AppTest.from_file(str(ROOT / "app" / "dashboard.py"), default_timeout=60).run()
    assert at.error and "run_pipeline.py" in at.error[0].value

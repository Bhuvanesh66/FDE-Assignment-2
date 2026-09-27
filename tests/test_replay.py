"""--replay: rebuild from preserved raw inputs, byte-identical, and refuse tampered evidence."""
import json

import pytest

from flasheats_pipeline.pipeline import run_pipeline


def test_evidence_is_written_with_lf_on_every_os(tmp_path):
    """Hashes are compared byte for byte, so a Windows run and a Linux replay must write identical bytes."""
    import pandas as pd
    from flasheats_pipeline.io_utils import write_csv, write_json, write_text
    files = [write_csv(pd.DataFrame({"a": [1, 2]}), tmp_path / "t.csv"), write_json({"a": [1, 2]}, tmp_path / "t.json"),
             write_text("line 1\nline 2\n", tmp_path / "t.md")]
    for f in files:
        data = f.read_bytes()
        assert b"\n" in data and b"\r" not in data, f.name


@pytest.fixture
def original(messy_pack, api_server, make_config):
    cfg = make_config(messy_pack, api_server.url, run_id="run_orig")
    run = run_pipeline(cfg)
    assert run.status == "COMPLETED", run.error
    return cfg, run


def test_replay_reproduces_every_output_byte_for_byte(original, make_config):
    cfg, run = original
    # the replay must not need the client systems at all: point it at a source root that does not exist
    rcfg = make_config(cfg.source_root.parent / "gone", "http://127.0.0.1:9", run_id="run_rep", replay_run_id="run_orig")
    rep = run_pipeline(rcfg)
    assert rep.status == "COMPLETED", rep.error
    proof = json.loads((rcfg.output_dir / "replay_proof.json").read_text())
    assert proof["verdict"] == "REPRODUCED" and proof["outputs_compared"] >= 30 and proof["changed"] == []
    assert proof["artifacts_verified"] == proof["artifacts"] >= 14          # 4 SQL extracts, 7 files, 3 API pages
    assert rep.headline == run.headline
    # the published evidence still belongs to the original run
    assert json.loads((rcfg.output_dir / "run_manifest.json").read_text())["run_id"] == "run_orig"
    assert (rcfg.output_dir / "replay_integrity.csv").exists()


def test_tampered_preserved_file_stops_the_replay(original, make_config):
    cfg, _ = original
    f = cfg.raw_root / "run_orig" / "files" / "support_tickets.csv"
    f.write_bytes(f.read_bytes() + b"T09999,O00001,2026-08-01T10:00:00,late_delivery,forged\n")
    rep = run_pipeline(make_config(cfg.source_root, "http://127.0.0.1:9", run_id="run_rep_bad", replay_run_id="run_orig"))
    assert rep.status == "FAILED" and "ReplayIntegrityError" in rep.error and "support_tickets.csv=MODIFIED" in rep.error


def test_deleted_api_page_stops_the_replay(original, make_config):
    cfg, _ = original
    (cfg.raw_root / "run_orig" / "api" / "dispatch_page_002.json").unlink()
    rep = run_pipeline(make_config(cfg.source_root, "http://127.0.0.1:9", run_id="run_rep_gone", replay_run_id="run_orig"))
    assert rep.status == "FAILED" and "dispatch_page_002.json=MISSING" in rep.error


def test_unknown_run_is_a_clear_error(messy_pack, make_config):
    rep = run_pipeline(make_config(messy_pack, "http://127.0.0.1:9", run_id="run_x", replay_run_id="run_never"))
    assert rep.status == "FAILED" and "no preserved run 'run_never'" in rep.error


def test_rerun_on_same_inputs_is_byte_identical(original, api_server, make_config):
    cfg, _ = original
    api_server.hits.clear()
    again = run_pipeline(make_config(cfg.source_root, api_server.url, run_id="run_again"))
    cmp = json.loads((again.config.run_output_dir / "run_comparison.json").read_text())
    assert cmp["baseline_run"] == "run_orig" and cmp["fingerprints"]["changed"] == [] and cmp["fingerprints"]["identical"] >= 30

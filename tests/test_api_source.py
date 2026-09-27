"""Test 9 - API failure modes: pagination, retries, timeouts, malformed bodies, incompleteness."""
import json

import pytest

from flasheats_pipeline.ingest import ApiIngestionError, DispatchApiClient, load_snapshot_pages
from tests.conftest import dispatch_records


def make_client(srv, tmp_path, **kw):
    base = dict(page_size=5, timeout_s=1.0, max_retries=3, backoff_base_s=0.01, backoff_cap_s=0.02, sleep=lambda s: None)
    base.update(kw)
    return DispatchApiClient(srv.url, tmp_path / "raw", **base)


def test_paginates_everything_and_preserves_raw_pages(api_server, tmp_path):
    recs, rep = make_client(api_server, tmp_path).fetch_all()
    assert rep.complete and rep.records_fetched == rep.expected_total == 15
    assert rep.pages_fetched == 3 and len(rep.raw_pages) == 3
    saved = json.loads((tmp_path / "raw" / "api" / "dispatch_page_001.json").read_text())
    assert saved["payload"]["page"] == 1 and len(saved["payload"]["data"]) == 5
    assert (tmp_path / "raw" / "api" / "ingestion_report.json").exists()


def test_retries_500_and_429_then_succeeds(api_server, tmp_path):
    api_server.mode = "flaky"
    sleeps = []
    recs, rep = make_client(api_server, tmp_path, sleep=sleeps.append).fetch_all()
    assert rep.complete and rep.records_fetched == 15
    assert rep.retries == 2 and {e.get("status") for e in rep.http_errors} == {429, 500}
    assert sleeps and sleeps[0] == 0.0                        # Retry-After: 0 honoured


def test_persistent_500_fails_clearly_after_retries(api_server, tmp_path):
    api_server.mode = "always_500"
    with pytest.raises(ApiIngestionError, match="HTTP 500 persisted"):
        make_client(api_server, tmp_path).fetch_all()


def test_404_is_not_retried(api_server, tmp_path):
    api_server.mode = "not_found"
    with pytest.raises(ApiIngestionError, match="non-retryable HTTP 404"):
        make_client(api_server, tmp_path).fetch_all()
    assert api_server.calls == 1


def test_timeout_is_retried_then_fails_clearly(api_server, tmp_path):
    api_server.mode = "timeout"
    with pytest.raises(ApiIngestionError, match="timeout"):
        make_client(api_server, tmp_path, timeout_s=0.3, max_retries=1).fetch_all()


def test_connection_refused_is_clear(tmp_path):
    client = DispatchApiClient("http://127.0.0.1:9", tmp_path / "raw", max_retries=1, backoff_base_s=0.01, sleep=lambda s: None, timeout_s=0.5)
    assert client.health() is False
    # Windows reports a connect timeout, Linux a refused connection - both must surface as a clear, retried failure
    with pytest.raises(ApiIngestionError, match="connection_error|timeout"):
        client.fetch_all()


def test_malformed_json_body_fails_clearly(api_server, tmp_path):
    api_server.mode = "malformed_json"
    with pytest.raises(ApiIngestionError, match="not valid JSON"):
        make_client(api_server, tmp_path).fetch_all()


def test_missing_data_key_fails_clearly(api_server, tmp_path):
    api_server.mode = "missing_data_key"
    with pytest.raises(ApiIngestionError, match="missing required keys"):
        make_client(api_server, tmp_path).fetch_all()


def test_missing_has_more_is_inferred_from_page_size(api_server, tmp_path):
    api_server.mode = "no_has_more"
    recs, rep = make_client(api_server, tmp_path).fetch_all()
    assert rep.records_fetched == 15 and rep.expected_total is None
    assert rep.complete and any("inferring pagination" in i for i in rep.issues)


def test_wrong_total_marks_incomplete(api_server, tmp_path):
    api_server.mode = "wrong_total"
    recs, rep = make_client(api_server, tmp_path).fetch_all()
    assert not rep.complete and any("incomplete ingestion" in i for i in rep.issues)


def test_overlapping_pages_are_detected(api_server, tmp_path):
    api_server.mode = "overlap"
    recs, rep = make_client(api_server, tmp_path).fetch_all()
    assert rep.records_fetched == 16 and rep.unique_order_ids == 15 and not rep.complete
    assert any("repeated across pages" in i for i in rep.issues)


def test_empty_result_is_incomplete_not_a_crash(api_server, tmp_path):
    api_server.mode = "empty"
    recs, rep = make_client(api_server, tmp_path).fetch_all()
    assert recs == [] and not rep.complete and any("zero records" in i for i in rep.issues)


def test_never_ending_pagination_is_capped(api_server, tmp_path):
    api_server.mode = "never_ends"
    recs, rep = make_client(api_server, tmp_path, max_pages=4).fetch_all()
    assert rep.pages_fetched <= 4 and any("0 records while has_more=true" in i or "max_pages" in i for i in rep.issues)


def test_missing_record_fields_are_counted(api_server, tmp_path):
    api_server.mode = "missing_fields"
    recs, rep = make_client(api_server, tmp_path).fetch_all()
    assert rep.records_missing_required_fields == 15 and rep.records_missing_expected_fields == 15
    assert any("required field" in i for i in rep.issues)


def test_snapshot_fallback_reads_newest_preserved_run(api_server, tmp_path):
    raw_root = tmp_path / "raw_root"
    c = DispatchApiClient(api_server.url, raw_root / "run_A", page_size=5, sleep=lambda s: None)
    c.fetch_all()
    snap = load_snapshot_pages(raw_root, exclude_run="run_B")
    assert snap is not None
    recs, rep = snap
    assert rep.mode == "snapshot" and len(recs) == 15 and rep.complete
    assert load_snapshot_pages(tmp_path / "does_not_exist") is None

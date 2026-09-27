"""Tests 2, 5, 8 - CSV / JSON ingestion: presence, structure, empty files, malformed rows, whitespace."""
import json

import pytest

from flasheats_pipeline.ingest import SourceFileError, SourceSchemaError, flatten_driver_events, read_csv_source, read_json_source


def test_missing_file_is_a_clear_error(tmp_path):
    with pytest.raises(SourceFileError, match="not found"):
        read_csv_source(tmp_path / "nope.csv", "tickets", ["ticket_id"], tmp_path / "raw")


def test_zero_byte_file_is_a_clear_error(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_bytes(b"")
    with pytest.raises(SourceFileError, match="empty"):
        read_csv_source(p, "tickets", ["ticket_id"], tmp_path / "raw")


def test_header_only_file_is_empty_table_not_crash(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("ticket_id,order_id,created_at,category\n", encoding="utf-8")
    df, res = read_csv_source(p, "tickets", ["ticket_id", "order_id"], tmp_path / "raw")
    assert len(df) == 0 and res.empty and "zero data rows" in "; ".join(res.notes)


def test_missing_required_column_names_the_column(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("ticket_id,category\nT1,late\n", encoding="utf-8")
    with pytest.raises(SourceSchemaError, match="order_id"):
        read_csv_source(p, "tickets", ["ticket_id", "order_id"], tmp_path / "raw")


def test_column_names_and_cells_are_normalised_and_raw_copy_preserved(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("﻿ Ticket_ID , Order_Id ,Category,Extra\n T1 , O00001 , late_delivery ,x\nT2,,eta_changed,\n", encoding="utf-8")
    df, res = read_csv_source(p, "tickets", ["ticket_id", "order_id", "category"], tmp_path / "raw")
    assert list(df.columns) == ["ticket_id", "order_id", "category", "extra"]
    assert df.loc[0, "ticket_id"] == "T1" and df.loc[0, "order_id"] == "O00001" and df.loc[0, "category"] == "late_delivery"
    assert df.loc[1, "order_id"] is None or df["order_id"].isna().iloc[1]
    assert res.extra_columns == ["extra"]
    assert (tmp_path / "raw" / "files" / "t.csv").read_bytes() == p.read_bytes()
    assert len(res.sha256) == 64


def test_malformed_rows_are_counted(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("a,b\n1,2\n3,4,5,6\n7,8\n", encoding="utf-8")
    df, res = read_csv_source(p, "x", ["a", "b"], tmp_path / "raw")
    assert len(df) == 2 and res.malformed_rows == 1


def test_numbers_are_kept_as_text_until_cleaning(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("order_id,distance\nO00001,007\n", encoding="utf-8")
    df, _ = read_csv_source(p, "x", ["order_id"], tmp_path / "raw")
    assert df.loc[0, "distance"] == "007"


def test_invalid_json_is_a_clear_error(tmp_path):
    p = tmp_path / "d.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(SourceFileError, match="invalid JSON"):
        read_json_source(p, "driver_events", tmp_path / "raw")


def test_flatten_driver_events_tolerates_shapes(tmp_path):
    nested = [{"driver_id": "D1", "events": [{"order_id": "O1", "type": "assigned", "timestamp": "2026-08-01T10:00:00"},
                                             {"order_id": "O1", "type": "gps_ping", "timestamp": "2026-08-01T10:05:00", "lat": 12.9, "lon": 77.6, "speed": 3}]},
              {"driver_id": "D2"},                 # no events key
              {"driver_id": "D3", "events": "oops"},  # events not a list
              "garbage",
              {"driver_id": "D4", "events": [42, {"order_id": " O2 ", "type": "delivered", "timestamp": "2026-08-01T11:00:00"}]}]
    p = tmp_path / "d.json"
    p.write_text(json.dumps(nested), encoding="utf-8")
    obj, res = read_json_source(p, "driver_events", tmp_path / "raw")
    df = flatten_driver_events(obj, res)
    assert list(df.columns)[:6] == ["driver_id", "order_id", "type", "timestamp", "lat", "lon"]
    assert len(df) == 3
    assert df.loc[2, "order_id"] == "O2"                     # whitespace stripped
    assert "speed" in df.columns and res.extra_columns == ["speed"]
    assert any("skipped" in n for n in res.notes)


def test_flatten_accepts_already_flat_list():
    df = flatten_driver_events([{"driver_id": "D1", "order_id": "O1", "type": "assigned", "timestamp": "2026-08-01T10:00:00"}])
    assert len(df) == 1 and df.loc[0, "driver_id"] == "D1"


def test_flatten_rejects_non_list():
    with pytest.raises(SourceSchemaError):
        flatten_driver_events({"driver_id": "D1"})

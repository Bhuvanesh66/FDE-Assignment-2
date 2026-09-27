"""Test 6 - invalid / inconsistent timestamps are parsed defensively and counted."""
import pandas as pd

from flasheats_pipeline.timestamps import minutes_between, parse_timestamps


def test_mixed_layouts_blanks_and_garbage_are_counted_not_raised():
    s = pd.Series(["2026-08-01T10:00:00", "2026-08-01T10:00:00.123456", "2026-08-01 10:00", "", "   ", None, "not-a-date", "31/02/2026"])
    parsed, stats = parse_timestamps(s, "col")
    assert str(parsed.dtype) == "datetime64[ns]"
    assert stats.total == 8
    assert stats.null_or_blank == 3
    assert stats.parsed == 3
    assert stats.unparseable == 2
    assert "not-a-date" in stats.unparseable_samples
    assert parsed.iloc[0] == pd.Timestamp("2026-08-01 10:00:00")


def test_tz_aware_values_are_converted_to_source_zone_and_made_naive():
    s = pd.Series(["2026-08-01T10:00:00+05:30", "2026-08-01T04:30:00Z", "2026-08-01T10:00:00"])
    parsed, stats = parse_timestamps(s, "col", source_tz="Asia/Kolkata")
    assert stats.tz_aware_converted == 2
    assert stats.unparseable == 0
    # +05:30 and Z (04:30 UTC) both mean 10:00 IST -> comparable with the naive third value
    assert parsed.iloc[0] == parsed.iloc[1] == parsed.iloc[2] == pd.Timestamp("2026-08-01 10:00:00")
    assert getattr(parsed.dtype, "tz", None) is None


def test_all_tz_aware_series():
    s = pd.Series(["2026-08-01T10:00:00+05:30", "2026-08-01T11:00:00+05:30"])
    parsed, stats = parse_timestamps(s, "col")
    assert stats.tz_aware_converted == 2
    assert parsed.iloc[1] - parsed.iloc[0] == pd.Timedelta(hours=1)


def test_empty_series():
    parsed, stats = parse_timestamps(pd.Series([], dtype="object"), "col")
    assert len(parsed) == 0 and stats.total == 0 and stats.parsed == 0


def test_minutes_between_handles_missing():
    a = pd.Series(pd.to_datetime(["2026-08-01T10:30:00", None]))
    b = pd.Series(pd.to_datetime(["2026-08-01T10:00:00", "2026-08-01T10:00:00"]))
    m = minutes_between(a, b)
    assert m.iloc[0] == 30.0 and pd.isna(m.iloc[1])

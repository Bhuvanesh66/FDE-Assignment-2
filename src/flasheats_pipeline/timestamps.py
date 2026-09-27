"""Timestamp parsing that never hides a problem.

Client exports mix ``YYYY-MM-DDTHH:MM:SS`` and ``...SS.ffffff``; hidden data may
add other formats, timezone suffixes, blanks or garbage.  ``parse_timestamps``
returns a naive datetime series **and** a statistics dict that the validation
report uses (how many values could not be parsed, how many carried a timezone,
which layouts were seen).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

_TZ_SUFFIX = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")


@dataclass
class TimestampParseStats:
    column: str
    total: int = 0
    null_or_blank: int = 0
    parsed: int = 0
    unparseable: int = 0
    tz_aware_converted: int = 0
    formats_seen: dict[str, int] = field(default_factory=dict)
    unparseable_samples: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "column": self.column,
            "total": self.total,
            "null_or_blank": self.null_or_blank,
            "parsed": self.parsed,
            "unparseable": self.unparseable,
            "tz_aware_converted": self.tz_aware_converted,
            "formats_seen": self.formats_seen,
            "unparseable_samples": self.unparseable_samples,
        }


def _layout(value: str) -> str:
    return re.sub(r"\d", "9", value)


def parse_timestamps(series: pd.Series, column: str | None = None, source_tz: str = "Asia/Kolkata") -> tuple[pd.Series, TimestampParseStats]:
    """Parse a string series into naive datetimes.

    * blanks / None -> NaT (counted as null_or_blank)
    * unparseable strings -> NaT (counted, sampled, never raised)
    * tz-aware strings -> converted to ``source_tz`` then made naive, so they
      are comparable with the naive timestamps the client systems normally emit.
    """
    name = column or (series.name if series.name is not None else "timestamp")
    stats = TimestampParseStats(column=str(name), total=int(len(series)))
    s = series.astype("object")
    stripped = s.map(lambda v: v.strip() if isinstance(v, str) else v)
    blank = stripped.isna() | stripped.map(lambda v: isinstance(v, str) and v == "")
    stats.null_or_blank = int(blank.sum())

    text = stripped.where(~blank, None)
    layouts = text.dropna().map(lambda v: _layout(str(v))).value_counts()
    stats.formats_seen = {k: int(v) for k, v in layouts.head(12).items()}

    # pandas refuses to parse a column that mixes tz-aware and naive strings
    # ("Mixed timezones detected"), so the two populations are parsed separately.
    is_tz = text.map(lambda v: isinstance(v, str) and bool(_TZ_SUFFIX.search(v)))
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    naive_mask = text.notna() & ~is_tz
    if naive_mask.any():
        naive = pd.to_datetime(text[naive_mask], format="mixed", errors="coerce")
        if getattr(naive.dtype, "tz", None) is not None:          # defensive: unexpected tz inference
            naive = naive.dt.tz_convert(source_tz).dt.tz_localize(None)
        parsed.loc[naive_mask] = naive.astype("datetime64[ns]")
    aware_mask = text.notna() & is_tz
    if aware_mask.any():
        aware = pd.to_datetime(text[aware_mask], format="mixed", errors="coerce", utc=True)
        aware = aware.dt.tz_convert(source_tz).dt.tz_localize(None)
        parsed.loc[aware_mask] = aware.astype("datetime64[ns]")
        stats.tz_aware_converted = int(aware.notna().sum())

    parsed = parsed.astype("datetime64[ns]")
    unparse_mask = parsed.isna() & text.notna()
    stats.unparseable = int(unparse_mask.sum())
    stats.parsed = int(parsed.notna().sum())
    stats.unparseable_samples = [str(v) for v in text[unparse_mask].head(5).tolist()]
    parsed.name = name
    return parsed, stats


def minutes_between(later: pd.Series, earlier: pd.Series) -> pd.Series:
    """(later - earlier) in minutes, NaN where either side is missing."""
    return (later - earlier).dt.total_seconds() / 60.0

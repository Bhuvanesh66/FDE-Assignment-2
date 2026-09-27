"""Independent external source: observed hourly weather from the public Open-Meteo archive.

Why it exists (beyond the classroom): the orders table carries a ``weather_bucket``
label and Operations blames weather for lateness. Nobody in class asked where that
label comes from. This client retrieves what the sky actually did over Bengaluru
for the same hours so the label can be *verified* instead of trusted.

Dependability:
* retries timeouts, connection errors, 429 and 5xx with back-off; no retry on 4xx;
* validates the body (``hourly.time`` / ``hourly.precipitation`` present, same
  length, non-empty, numeric, requested timezone) - an HTTP 200 is not proof;
* preserves the raw response under ``data/raw/<run>/external/``;
* if the public API is unreachable, falls back to the committed reference copy in
  ``data/external/`` (report mode = "cache"), and if that is missing too, returns
  ``None`` so the weather rule becomes UNKNOWN instead of crashing the run.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import requests

from ..io_utils import write_json
from ..logging_utils import get_logger

RETRYABLE = {408, 425, 429, 500, 502, 503, 504}


class WeatherSourceError(RuntimeError):
    """The weather API response cannot be used."""


@dataclass
class WeatherReport:
    source: str = "open_meteo_archive"
    mode: str = "unavailable"            # live | cache | unavailable
    url: str = ""
    params: dict = field(default_factory=dict)
    hours: int = 0
    first_hour: str | None = None
    last_hour: str | None = None
    retries: int = 0
    errors: list[str] = field(default_factory=list)
    raw_path: str | None = None

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def parse_open_meteo(payload: dict, expected_tz: str | None = None) -> pd.DataFrame:
    """Validate an Open-Meteo archive payload and return ``hour, precipitation_mm, rain_mm``."""
    if not isinstance(payload, dict):
        raise WeatherSourceError(f"payload is {type(payload).__name__}, expected an object")
    if payload.get("error"):
        raise WeatherSourceError(f"API reported an error: {payload.get('reason', payload)}")
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict) or "time" not in hourly or "precipitation" not in hourly:
        raise WeatherSourceError("payload has no hourly.time / hourly.precipitation arrays")
    times, precip = hourly["time"], hourly["precipitation"]
    if not isinstance(times, list) or not isinstance(precip, list) or len(times) != len(precip):
        raise WeatherSourceError("hourly.time and hourly.precipitation are not lists of equal length")
    if len(times) == 0:
        raise WeatherSourceError("hourly arrays are empty")
    if expected_tz and payload.get("timezone") not in (None, expected_tz):
        raise WeatherSourceError(f"timezone {payload.get('timezone')!r} differs from requested {expected_tz!r}")
    df = pd.DataFrame({"hour": pd.to_datetime(times, errors="coerce"),
                       "precipitation_mm": pd.to_numeric(pd.Series(precip), errors="coerce")})
    rain = hourly.get("rain")
    df["rain_mm"] = pd.to_numeric(pd.Series(rain), errors="coerce") if isinstance(rain, list) and len(rain) == len(times) else pd.NA
    bad = int(df["hour"].isna().sum())
    if bad == len(df):
        raise WeatherSourceError("no parseable hourly timestamps")
    df = df.dropna(subset=["hour"]).drop_duplicates("hour").sort_values("hour").reset_index(drop=True)
    return df


class ObservedWeatherClient:
    def __init__(self, base_url: str, latitude: float, longitude: float, timezone: str, raw_dir: Path,
                 cache_dir: Path | None = None, timeout_s: float = 20.0, max_retries: int = 3,
                 backoff_s: float = 1.0, session: requests.Session | None = None, sleep=time.sleep):
        self.base_url = base_url
        self.lat, self.lon, self.tz = latitude, longitude, timezone
        self.raw_dir = Path(raw_dir) / "external"
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.timeout_s, self.max_retries, self.backoff_s = timeout_s, max_retries, backoff_s
        self.session = session or requests.Session()
        self.sleep = sleep
        self.log = get_logger()

    def _cache_file(self, start: str, end: str) -> Path | None:
        if not self.cache_dir:
            return None
        return self.cache_dir / f"open_meteo_{self.lat:.4f}_{self.lon:.4f}_{start}_{end}.json"

    def fetch(self, start_date: str, end_date: str) -> tuple[pd.DataFrame | None, WeatherReport]:
        params = {"latitude": self.lat, "longitude": self.lon, "start_date": start_date, "end_date": end_date,
                  "hourly": "precipitation,rain", "timezone": self.tz}
        rep = WeatherReport(url=self.base_url, params=params)
        payload = None
        for attempt in range(1, self.max_retries + 2):
            try:
                r = self.session.get(self.base_url, params=params, timeout=self.timeout_s)
            except (requests.Timeout, requests.ConnectionError) as exc:
                rep.errors.append(f"attempt {attempt}: {type(exc).__name__}")
                if attempt > self.max_retries:
                    break
                rep.retries += 1
                self.sleep(self.backoff_s * attempt)
                continue
            if r.status_code in RETRYABLE:
                rep.errors.append(f"attempt {attempt}: HTTP {r.status_code}")
                if attempt > self.max_retries:
                    break
                rep.retries += 1
                self.sleep(self.backoff_s * attempt)
                continue
            if not r.ok:
                rep.errors.append(f"attempt {attempt}: non-retryable HTTP {r.status_code}")
                break
            try:
                payload = r.json()
            except ValueError:
                rep.errors.append(f"attempt {attempt}: body is not JSON")
                payload = None
                if attempt > self.max_retries:
                    break
                rep.retries += 1
                self.sleep(self.backoff_s * attempt)
                continue
            break

        df = None
        if payload is not None:
            try:
                df = parse_open_meteo(payload, expected_tz=self.tz)
                rep.mode = "live"
                self.raw_dir.mkdir(parents=True, exist_ok=True)
                raw_path = self.raw_dir / "open_meteo_archive.json"
                write_json({"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "request": {"url": self.base_url, "params": params}, "payload": payload}, raw_path)
                rep.raw_path = str(raw_path)
                cache = self._cache_file(start_date, end_date)
                if cache is not None and not cache.exists():          # seed the reference copy once; never overwrite it
                    write_json({"request": {"url": self.base_url, "params": params}, "payload": payload}, cache)
            except WeatherSourceError as exc:
                rep.errors.append(f"invalid payload: {exc}")
                df = None

        if df is None:
            cache = self._cache_file(start_date, end_date)
            if cache is not None and cache.exists():
                try:
                    with open(cache, "r", encoding="utf-8") as f:
                        df = parse_open_meteo(json.load(f).get("payload", {}), expected_tz=self.tz)
                    rep.mode = "cache"
                    rep.raw_path = str(cache)
                    self.log.warning("weather API unavailable (%s) - using reference copy %s", "; ".join(rep.errors[-2:]), cache.name)
                except (OSError, ValueError, WeatherSourceError) as exc:
                    rep.errors.append(f"cache unusable: {exc}")
                    df = None
        if df is None:
            rep.mode = "unavailable"
            self.log.warning("observed weather unavailable - weather cross-check will be UNKNOWN (%s)", "; ".join(rep.errors[-3:]))
            return None, rep
        rep.hours = int(len(df))
        rep.first_hour = df["hour"].min().isoformat()
        rep.last_hour = df["hour"].max().isoformat()
        self.log.info("weather %s: %d hourly observations %s -> %s, retries=%d", rep.mode, rep.hours, rep.first_hour, rep.last_hour, rep.retries)
        return df, rep

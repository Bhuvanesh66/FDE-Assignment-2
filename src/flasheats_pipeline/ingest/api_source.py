"""Dispatch REST API retrieval - "prove you retrieved everything".

An HTTP 200 on one page proves nothing.  This client:

* walks every page until the server says ``has_more == false`` (with a hard cap),
* retries transient failures (timeouts, connection errors, HTTP 429/5xx,
  malformed JSON) with exponential back-off and honours ``Retry-After``,
* refuses to retry non-transient client errors (400/401/403/404) - those are
  configuration bugs, not weather,
* validates the *content* of every page (expected keys, list of records,
  required record fields), not just the status code,
* preserves every successful raw page under ``data/raw/<run>/api/``,
* proves completeness: fetched == reported total, no duplicate order ids across
  pages, no empty page while ``has_more`` is still true,
* returns an ``IngestionReport`` the validation gate can turn into PASS/WARN/FAIL.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

from ..io_utils import write_json
from ..logging_utils import get_logger

PAYLOAD_REQUIRED_KEYS = {"data"}
PAYLOAD_EXPECTED_KEYS = {"data", "has_more", "page", "page_size", "total_records"}
RECORD_REQUIRED_FIELDS = ["order_id", "driver_id", "assigned_at", "dispatch_status"]
RECORD_EXPECTED_FIELDS = [
    "order_id", "driver_id", "original_driver_id", "assigned_at", "reassigned_at",
    "estimated_pickup_at", "current_delivery_eta", "dispatch_status", "eta_model_version",
]
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
NON_RETRYABLE_STATUS = {400, 401, 403, 404, 405, 410, 422}


class ApiIngestionError(RuntimeError):
    """Raised when the API cannot be ingested completely and safely."""


@dataclass
class IngestionReport:
    source: str = "dispatch_api"
    base_url: str = ""
    pages_fetched: int = 0
    records_fetched: int = 0
    unique_order_ids: int = 0
    expected_total: int | None = None
    retries: int = 0
    http_errors: list[dict] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    records_missing_required_fields: int = 0
    records_missing_expected_fields: int = 0
    complete: bool = False
    duration_s: float = 0.0
    raw_pages: list[str] = field(default_factory=list)
    mode: str = "live"                    # live | snapshot

    def as_dict(self) -> dict:
        return self.__dict__.copy()


class DispatchApiClient:
    def __init__(self, base_url: str, raw_dir: Path, page_size: int = 100, timeout_s: float = 10.0,
                 max_retries: int = 5, backoff_base_s: float = 0.5, backoff_cap_s: float = 4.0,
                 max_pages: int = 10_000, session: requests.Session | None = None, sleep=time.sleep):
        self.base_url = base_url.rstrip("/")
        self.raw_dir = Path(raw_dir) / "api"
        self.page_size = page_size
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self.backoff_cap_s = backoff_cap_s
        self.max_pages = max_pages
        self.session = session or requests.Session()
        self.sleep = sleep
        self.log = get_logger()

    # ---------------------------------------------------------------- helpers
    def _backoff(self, attempt: int, retry_after: float | None = None) -> float:
        if retry_after is not None:
            return max(0.0, min(retry_after, self.backoff_cap_s * 4))
        return min(self.backoff_base_s * (2 ** (attempt - 1)), self.backoff_cap_s)

    def health(self) -> bool:
        try:
            r = self.session.get(f"{self.base_url}/health", timeout=self.timeout_s)
            return r.ok
        except requests.RequestException:
            return False

    def _get_page(self, page: int, report: IngestionReport) -> dict:
        """One page with retries. Returns the parsed payload or raises ApiIngestionError."""
        url = f"{self.base_url}/dispatch/orders"
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self.session.get(url, params={"page": page, "page_size": self.page_size}, timeout=self.timeout_s)
            except (requests.Timeout, requests.ConnectionError) as exc:
                kind = "timeout" if isinstance(exc, requests.Timeout) else "connection_error"
                report.http_errors.append({"page": page, "attempt": attempt, "error": kind})
                if attempt > self.max_retries:
                    raise ApiIngestionError(f"page {page}: {kind} after {attempt - 1} retries ({exc})") from exc
                wait = self._backoff(attempt)
                self.log.warning("API page=%d attempt=%d %s - retrying in %.1fs", page, attempt, kind, wait)
                report.retries += 1
                self.sleep(wait)
                continue

            status = resp.status_code
            if status in RETRYABLE_STATUS:
                retry_after = None
                if resp.headers.get("Retry-After"):
                    try:
                        retry_after = float(resp.headers["Retry-After"])
                    except ValueError:
                        retry_after = None
                else:
                    try:
                        retry_after = float(resp.json().get("retry_after_seconds"))
                    except Exception:
                        retry_after = None
                report.http_errors.append({"page": page, "attempt": attempt, "status": status})
                if attempt > self.max_retries:
                    raise ApiIngestionError(f"page {page}: HTTP {status} persisted after {attempt - 1} retries")
                wait = self._backoff(attempt, retry_after)
                self.log.warning("API page=%d attempt=%d HTTP %d - retrying in %.1fs", page, attempt, status, wait)
                report.retries += 1
                self.sleep(wait)
                continue
            if status in NON_RETRYABLE_STATUS or not resp.ok:
                report.http_errors.append({"page": page, "attempt": attempt, "status": status})
                raise ApiIngestionError(f"page {page}: non-retryable HTTP {status}: {resp.text[:200]}")

            # 200 - but is the body usable?
            try:
                payload = resp.json()
            except ValueError as exc:
                report.http_errors.append({"page": page, "attempt": attempt, "error": "invalid_json"})
                if attempt > self.max_retries:
                    raise ApiIngestionError(f"page {page}: response is not valid JSON after retries") from exc
                self.log.warning("API page=%d attempt=%d invalid JSON body - retrying", page, attempt)
                report.retries += 1
                self.sleep(self._backoff(attempt))
                continue
            if not isinstance(payload, dict) or not PAYLOAD_REQUIRED_KEYS.issubset(payload):
                raise ApiIngestionError(f"page {page}: payload missing required keys {PAYLOAD_REQUIRED_KEYS}; got {type(payload).__name__} {list(payload)[:8] if isinstance(payload, dict) else ''}")
            if not isinstance(payload["data"], list):
                raise ApiIngestionError(f"page {page}: 'data' is {type(payload['data']).__name__}, expected list")
            missing_keys = PAYLOAD_EXPECTED_KEYS - set(payload)
            if missing_keys:
                msg = f"page {page}: payload missing optional keys {sorted(missing_keys)} - inferring pagination from page size"
                if msg not in report.issues:
                    report.issues.append(msg)
            return payload

    # ------------------------------------------------------------------- main
    def fetch_all(self) -> tuple[list[dict], IngestionReport]:
        report = IngestionReport(base_url=self.base_url)
        t0 = time.time()
        records: list[dict] = []
        seen_ids: set = set()
        duplicate_ids = 0
        page = 1
        self.raw_dir.mkdir(parents=True, exist_ok=True)

        while True:
            if page > self.max_pages:
                report.issues.append(f"stopped at max_pages={self.max_pages} while has_more was still true")
                break
            payload = self._get_page(page, report)
            data = payload["data"]
            raw_path = self.raw_dir / f"dispatch_page_{page:03d}.json"
            write_json({"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "request": {"page": page, "page_size": self.page_size}, "payload": payload}, raw_path)
            report.raw_pages.append(str(raw_path))
            report.pages_fetched += 1

            total = payload.get("total_records")
            if isinstance(total, int) and not isinstance(total, bool):
                if report.expected_total is None:
                    report.expected_total = total
                elif total != report.expected_total:
                    report.issues.append(f"total_records changed during pagination: {report.expected_total} -> {total} (page {page})")
            elif total is not None:
                report.issues.append(f"page {page}: total_records is not an integer ({total!r})")

            for rec in data:
                if not isinstance(rec, dict):
                    report.records_missing_required_fields += 1
                    continue
                if any(rec.get(f) in (None, "") for f in RECORD_REQUIRED_FIELDS):
                    report.records_missing_required_fields += 1
                if any(f not in rec for f in RECORD_EXPECTED_FIELDS):
                    report.records_missing_expected_fields += 1
                oid = rec.get("order_id")
                if oid in seen_ids:
                    duplicate_ids += 1
                seen_ids.add(oid)
                records.append(rec)

            has_more = payload.get("has_more")
            if not isinstance(has_more, bool):
                has_more = len(data) >= self.page_size          # inferred
            self.log.info("API page=%3d rows=%3d running_total=%5d has_more=%s", page, len(data), len(records), has_more)
            if len(data) == 0 and has_more:
                report.issues.append(f"page {page} returned 0 records while has_more=true - stopping to avoid an infinite loop")
                break
            if not has_more:
                break
            page += 1

        report.records_fetched = len(records)
        report.unique_order_ids = len({r.get("order_id") for r in records if isinstance(r, dict)})
        if duplicate_ids:
            report.issues.append(f"{duplicate_ids} records repeated across pages (pagination overlap or duplicate source rows)")
        if report.records_missing_required_fields:
            report.issues.append(f"{report.records_missing_required_fields} records lack a required field {RECORD_REQUIRED_FIELDS}")
        if report.records_missing_expected_fields:
            report.issues.append(f"{report.records_missing_expected_fields} records lack one of the expected fields (filled as null)")
        if report.expected_total is None:
            report.issues.append("server did not report total_records - completeness can only be inferred from pagination")
            report.complete = len(records) > 0 and duplicate_ids == 0
        else:
            report.complete = (report.records_fetched == report.expected_total) and duplicate_ids == 0
            if not report.complete:
                report.issues.append(f"incomplete ingestion: fetched {report.records_fetched}, server reports {report.expected_total}")
        if report.records_fetched == 0:
            report.issues.append("API returned zero records")
            report.complete = False
        report.duration_s = round(time.time() - t0, 3)
        write_json(report.as_dict(), self.raw_dir / "ingestion_report.json")
        self.log.info("API ingestion %s: pages=%d records=%d unique=%d expected=%s retries=%d",
                      "COMPLETE" if report.complete else "INCOMPLETE", report.pages_fetched, report.records_fetched,
                      report.unique_order_ids, report.expected_total, report.retries)
        return records, report


def load_snapshot_pages(raw_root: Path, exclude_run: str | None = None) -> tuple[list[dict], IngestionReport] | None:
    """Fallback: reload the newest previously preserved raw API pages.

    Used only when the live API is unreachable **and** the operator explicitly
    allowed it (``api_fallback_to_last_snapshot``).  The report is marked
    ``mode="snapshot"`` so the gate degrades the run to WARN.
    """
    raw_root = Path(raw_root)
    if not raw_root.exists():
        return None
    candidates = sorted([p for p in raw_root.iterdir() if p.is_dir() and (p / "api").exists() and p.name != exclude_run], reverse=True)
    for run_dir in candidates:
        pages = sorted((run_dir / "api").glob("dispatch_page_*.json"))
        if not pages:
            continue
        records: list[dict] = []
        for p in pages:
            with open(p, "r", encoding="utf-8") as f:
                payload = json.load(f).get("payload", {})
            records.extend([r for r in payload.get("data", []) if isinstance(r, dict)])
        rep = IngestionReport(mode="snapshot", base_url=str(run_dir / "api"), pages_fetched=len(pages), records_fetched=len(records),
                              unique_order_ids=len({r.get("order_id") for r in records}), raw_pages=[str(p) for p in pages])
        rep.issues.append(f"live API unavailable - reused snapshot from {run_dir.name}")
        rep.complete = len(records) > 0
        return records, rep
    return None

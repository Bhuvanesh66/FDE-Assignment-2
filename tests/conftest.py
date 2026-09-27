"""Shared fixtures: a hand-built messy source pack and a fault-injecting Dispatch API.

The synthetic pack is small enough to verify every metric by hand (see
``EXPECTED`` below) and deliberately contains the realistic defects an evaluator
could hide in the data: duplicates, casing, whitespace, malformed and tz-aware
timestamps, unknown identifiers, chronology violations, unexpected categories,
impossible ranges and foreign records.
"""
from __future__ import annotations

import json
import socket
import sqlite3
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from flasheats_pipeline.config import PipelineConfig  # noqa: E402

# --------------------------------------------------------------------------- synthetic data
# order_id, customer, restaurant, driver, created, promised, pickup, actual, status, distance, traffic, weather
ORDERS = [
    ("O00001", "C0001", "R001", "D001", "2026-08-01T10:00:00", "2026-08-01T10:40:00", "2026-08-01T10:15:00", "2026-08-01T10:35:00", "delivered", 5.0, "low", "clear"),        # on time (-5)
    ("O00002", "C0002", "R001", "D001", "2026-08-01T11:00:00", "2026-08-01T11:40:00", "2026-08-01T11:20:00", "2026-08-01T11:50:00", "delivered", 8.0, "medium", "clear"),     # late +10
    ("O00003", "C0003", "R003", "D002", "2026-08-01T12:00:00", "2026-08-01T12:40:00", "2026-08-01T12:30:00", "2026-08-01T13:00:00", "delivered", 12.0, "high", "rain"),      # late +20, intervention + ticket
    ("O00004", "C0001", "R001", "D001", "2026-08-02T10:00:00", "2026-08-02T10:40:00", "2026-08-02T10:20:00", None, "cancelled", 6.0, "low", "clear"),                          # cancelled
    ("O00005", "C0002", "R003", "D002", "2026-08-02T11:00:00", "2026-08-02T11:40:00", "2026-08-02T11:20:00", None, "delivered", 7.0, "medium", "clear"),                       # delivered, missing actual (recoverable)
    ("O00006", "C0003", "R001", "D001", "2026-08-02T12:00:00", "2026-08-02T11:50:00", "2026-08-02T12:20:00", "2026-08-02T12:45:00", "delivered", 9.0, "high", "clear"),      # TS-01 promised < created
    ("O00007", "C0004", "R003", "D002", "2026-08-03T10:00:00", "2026-08-03T10:40:00", "2026-08-03T10:30:00", "2026-08-03T10:25:00", "delivered", 4.0, "low", "clear"),       # TS-02 actual < pickup
    ("O00008", "C0004", "R001", "D001", "2026-08-03T11:00:00", "2026-08-03T11:40:00", "2026-08-03T11:20:00", "2026-08-03T11:43:00", "Delivered", 18.0, " HIGH ", "clear"),   # casing/whitespace, late +3
    ("O00009", "C0005", "R003", "D002", "2026-08-03T12:00:00", "2026-08-03T12:40:00", "2026-08-03T12:35:00", "2026-08-03T13:10:00", "delivered", 999.0, "gridlock", "heavy_rain"),  # bad range + unexpected category, late +30
    ("o00010 ", "C0005", None, "D001", "2026-08-04T10:00:00", "2026-08-04T10:40:00", "2026-08-04T10:15:00", "2026-08-04T10:38:00", "delivered", 3.0, "low", "clear"),        # lowercase/padded id, null restaurant, on time (-2)
    ("O00011", "C0001", "R001", "D999", "2026-08-04T11:00:00", "2026-08-04T11:40:00", "2026-08-04T11:20:00", "2026-08-04T11:39:00", "delivered", 5.0, "medium", "rain"),     # unknown driver, on time (-1)
    ("O00012", "C0002", "R003", "D002", "2026-08-04T12:00:00", "2026-08-04T12:40:00", "2026-08-04T12:20:00", "2026-08-04T12:50:00", "suspended", 5.0, "low", "clear"),      # unexpected status -> not delivered
    ("O00013", "C0003", "R001", "D001", "2026-08-05T10:00:00", "2026-08-05T10:40:00", "2026-08-05T10:20:00", "not-a-date", "delivered", 5.0, "low", "clear"),                # malformed timestamp
    ("O00014", "C0004", "R003", "D002", "2026-08-05T11:00:00+05:30", "2026-08-05T11:40:00+05:30", "2026-08-05T11:20:00+05:30", "2026-08-05T11:45:00+05:30", "delivered", 5.0, "medium", "clear"),  # tz-aware, late +5
]
DUPLICATE_ROWS = [
    ORDERS[0],                                                                                   # exact duplicate of O00001
    ("O00002", "C0002", "R001", "D001", "2026-08-01T11:00:00", "2026-08-01T11:40:00", "2026-08-01T11:20:00", "2026-08-01T11:50:00", "delivered", 8.0, "severe", "clear"),  # conflicting duplicate (traffic)
]
CUSTOMERS = [("C0001", 12.9, 77.6), ("C0002", 12.95, 77.55), ("C0003", 13.0, 77.6), ("C0004", 12.98, 77.62), ("C0005", 12.92, 77.58)]
RESTAURANTS = [("R001", "Restaurant 001", "Pizza", 12.95, 77.6, 1), ("R002", "Restaurant 002", "Cafe", 95.12, 77.6, 0), ("R003", "Restaurant 003", "Biryani", 12.97, 77.65, 0)]
DRIVERS = [("D001", 4.5, "bike", 20), ("D002", 4.1, "scooter", 5)]

# hand-computed expectations for the messy pack
EXPECTED = {
    "unique_orders": 14,
    "validated_population": 8,          # O00001,2,3,8,9,10,11,14
    "late_orders": 5,                   # O00002 (+10), O00003 (+20), O00008 (+3), O00009 (+30), O00014 (+5)
    "late_rate_pct": 62.5,
    "median_lateness_min": 10.0,
    "historical_population": 10,        # + O00006, O00007
    "historical_late": 6,               # + O00006 (+55)
    "cancelled": 1,
    "unknown_missing_timestamp": 2,     # O00005, O00013
    "excluded_dq_rule": 2,              # O00006, O00007
    "other_status": 1,                  # O00012
    "backfilled": 1,                    # O00005 via driver event
}


def dispatch_records(include_unknown: bool = True, duplicate_first: bool = False) -> list[dict]:
    recs = []
    for o in ORDERS:
        oid = o[0].strip().upper()
        created = o[4].replace("+05:30", "")
        base = created[:11]
        recs.append({
            "order_id": oid, "driver_id": "D001" if oid == "O00003" else (o[3] or "D001"), "original_driver_id": o[3] or "D001",
            "assigned_at": base + created[11:13] + ":03:00", "reassigned_at": base + created[11:13] + ":10:00" if oid == "O00003" else None,
            "estimated_pickup_at": base + created[11:13] + ":15:00", "current_delivery_eta": o[5].replace("+05:30", ""),
            "dispatch_status": "cancelled" if o[8] == "cancelled" else "completed", "eta_model_version": "eta-v3.2",
        })
    if include_unknown:
        recs.append({"order_id": "O09999", "driver_id": "D001", "original_driver_id": "D001", "assigned_at": "2026-08-09T10:03:00", "reassigned_at": None,
                     "estimated_pickup_at": "2026-08-09T10:15:00", "current_delivery_eta": "2026-08-09T10:40:00", "dispatch_status": "completed", "eta_model_version": "eta-v3.1"})
    if duplicate_first:
        recs.append(dict(recs[0]))
    return recs


def driver_events_nested() -> list[dict]:
    def ev(oid, typ, ts, **kw):
        return {"order_id": oid, "type": typ, "timestamp": ts, **kw}
    d001 = [ev("O00001", "assigned", "2026-08-01T10:03:00"), ev("O00001", "gps_ping", "2026-08-01T10:10:00", lat=12.93, lon=77.6),
            ev("O00001", "picked_up", "2026-08-01T10:15:00"), ev("O00001", "delivered", "2026-08-01T10:35:00"),
            ev("O00002", "assigned", "2026-08-01T11:03:00"), ev("O00002", "picked_up", "2026-08-01T11:20:00"), ev("O00002", "delivered", "2026-08-01T11:50:00"),
            ev("O00008", "assigned", "2026-08-03T11:03:00"), ev("O00008", "picked_up", "2026-08-03T11:20:00"), ev("O00008", "delivered", "2026-08-03T11:43:00"),
            ev("O00010", "assigned", "2026-08-04T10:03:00"), ev("O00010", "picked_up", "2026-08-04T10:15:00"), ev("O00010", "delivered", "2026-08-04T10:38:00")]
    d002 = [ev("O00003", "assigned", "2026-08-01T12:35:00"), ev("O00003", "picked_up", "2026-08-01T12:30:00"),      # picked_up before assigned (TS-07)
            ev("O00003", "gps_ping", "2026-08-01T12:40:00", lat=81.4, lon=171.5),                                    # GPS outlier (RG-03)
            ev("O00003", "delivered", "2026-08-01T13:00:00"),
            ev("O00005", "assigned", "2026-08-02T11:03:00"), ev("O00005", "picked_up", "2026-08-02T11:20:00"), ev("O00005", "delivered", "2026-08-02T11:55:00"),  # recoverable delivery
            ev("O00009", "assigned", "2026-08-03T12:03:00"), ev("O00009", "picked_up", "2026-08-03T12:35:00"), ev("O00009", "delivered", "2026-08-03T13:10:00"),
            ev("O00014", "assigned", "2026-08-05T11:03:00"), ev("O00014", "picked_up", "2026-08-05T11:20:00"), ev("O00014", "delivered", "2026-08-05T11:45:00")]
    return [{"driver_id": "D001", "events": d001}, {"driver_id": "D002", "events": d002}, {"driver_id": "D003"}]   # D003 has no events key


def build_pack(root: Path, messy: bool = True, with_outcomes_ref: bool = True, csv_header_case: bool = False, omit_file: str | None = None) -> Path:
    """Create a complete source pack under ``root`` (database/, data/, api/)."""
    (root / "database").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "api").mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(root / "database" / "flasheats.db")
    con.execute("CREATE TABLE orders (order_id TEXT, customer_id TEXT, restaurant_id TEXT, driver_id TEXT, city TEXT, created_at TEXT, promised_eta TEXT, pickup_at TEXT, actual_delivery_at TEXT, final_status TEXT, distance_km_estimate REAL, traffic_bucket TEXT, weather_bucket TEXT)")
    con.execute("CREATE TABLE customers (customer_id TEXT, name TEXT, email TEXT, lat REAL, lon REAL)")
    con.execute("CREATE TABLE restaurants (restaurant_id TEXT, restaurant_name TEXT, cuisine TEXT, lat REAL, lon REAL, manual_status_updates INTEGER)")
    con.execute("CREATE TABLE drivers (driver_id TEXT, rating REAL, vehicle_type TEXT, experience_months INTEGER)")
    rows = ORDERS + (DUPLICATE_ROWS if messy else [])
    if not messy:   # clean variant: only the well-formed, non-violating orders
        rows = [r for r in ORDERS if r[0] in ("O00001", "O00002", "O00003", "O00004", "O00011")]
        rows = [tuple(("D001" if (i == 3 and v == "D999") else v) for i, v in enumerate(r)) for r in rows]
    for r in rows:
        con.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (r[0], r[1], r[2], r[3], "Bengaluru", *r[4:]))
    for c in CUSTOMERS:
        con.execute("INSERT INTO customers VALUES (?,?,?,?,?)", (c[0], f"Customer {c[0]}", f"{c[0].lower()}@example.com", c[1], c[2]))
    for r in RESTAURANTS:
        con.execute("INSERT INTO restaurants VALUES (?,?,?,?,?,?)", r)
    for d in DRIVERS:
        con.execute("INSERT INTO drivers VALUES (?,?,?,?)", d)
    con.commit()
    con.close()

    def hdr(cols):
        return [c.upper() if csv_header_case else c for c in cols]

    present = {r[0].strip().upper() for r in rows}

    def write_csv(name, cols, data):
        if omit_file == name:
            return
        import csv
        if not messy and "order_id" in cols:          # a clean pack only references orders that exist
            data = [d for d in data if str(d[cols.index("order_id")]).strip().upper() in present]
        with open(root / "data" / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(hdr(cols))
            w.writerows(data)

    tickets = [("T00001", "O00002", "2026-08-01T11:45:00", "late_delivery", "past promised time"),
               ("T00002", "O00003", "2026-08-01T12:50:00", "Late Delivery", "still not here"),
               ("T00006", "O00009", "2026-08-03T12:50:00", "ETA issue", "eta keeps changing")]
    if messy:
        tickets += [("T00003", "", "2026-08-01T13:00:00", "eta_changed", "no order id"),
                    ("T00004", "O99999", "2026-08-01T13:00:00", "status_mismatch", "unknown order"),
                    ("T00001", "O00002", "2026-08-01T11:45:00", "late_delivery", "past promised time")]   # exact duplicate
    write_csv("support_tickets.csv", ["ticket_id", "order_id", "created_at", "category", "customer_message"], tickets)

    rstatus = [("O00002", "R001", "READY", "2026-08-01T11:18:00"), ("O00003", "R003", "handoff", "2026-08-01T12:31:00"), ("O00001", "R001", "ready ", "2026-08-01T10:12:00")]
    if messy:
        rstatus += [("O00001", "R001", "ready ", "2026-08-01T10:12:00"),          # exact duplicate
                    ("O88888", "R001", "preparing", "2026-08-01T10:12:00"),      # foreign order
                    ("O00002", "R003", "handed_off", "2026-08-01T12:30:00")]     # restaurant mismatch + stale (70 min after pickup)
    write_csv("restaurant_status.csv", ["order_id", "restaurant_id", "status", "last_updated_at"], rstatus)

    actions = [("ACT-00001", "O00003", "C0003", "ETA_VIEWED", "2026-08-01T12:20:00", "mobile_app"), ("ACT-00002", "O00003", "C0003", "ETA_VIEWED", "2026-08-01T12:41:00", "mobile_app"),
               ("ACT-00003", "O00003", "C0003", "SUPPORT_OPENED", "2026-08-01T12:48:00", "mobile_app"), ("ACT-00004", "O00002", "C0002", "ETA_VIEWED", "2026-08-01T11:30:00", "mobile_app"),
               ("ACT-00005", "O00009", "C0005", "CANCEL_ATTEMPTED", "2026-08-03T12:55:00", "mobile_app"), ("ACT-00006", "O00001", "C0001", "ETA_VIEWED", "2026-08-01T10:20:00", "mobile_app")]
    write_csv("customer_app_actions.csv", ["action_id", "order_id", "customer_id", "action_type", "action_at", "channel"], actions)

    interventions = [("INT-00001", "O00003", "DRIVER_REASSIGNMENT", "2026-08-01T12:10:00", "dispatch", "driver_unavailable"),
                     ("INT-00002", "O00009", "PRIORITY_DISPATCH", "2026-08-03T12:20:00", "operations", "late_risk")]
    if messy:
        interventions += [("INT-00003", "O77777", "RESTAURANT_CONTACT", "2026-08-03T12:20:00", "support", "status_stale")]
    write_csv("order_interventions.csv", ["intervention_id", "order_id", "intervention_type", "intervention_at", "initiated_by", "reason"], interventions)

    if with_outcomes_ref:
        # reference outcomes following the "historical" definition (delivered + non-null actual) for the messy pack
        ref = []
        for o in ORDERS:
            oid = o[0].strip().upper()
            status = o[8].strip().lower()
            if status == "delivered" and o[7] and o[7] != "not-a-date":
                from datetime import datetime
                a = datetime.fromisoformat(o[7].replace("+05:30", ""))
                p = datetime.fromisoformat(o[5].replace("+05:30", ""))
                delay = round((a - p).total_seconds() / 60, 2)
                ref.append((oid, "delivered", 1, 1 if delay > 0 else 0, delay, "delivered_late" if delay > 0 else "delivered_on_time"))
            elif status == "delivered":
                ref.append((oid, "delivered", 1, "", "", "unknown"))
            else:
                ref.append((oid, status, 0, "", "", status))
        write_csv("order_outcomes.csv", ["order_id", "final_status_norm", "delivered_flag", "late_flag", "delay_min", "outcome_bucket"], ref)

    with open(root / "data" / "driver_events.json", "w", encoding="utf-8") as f:
        json.dump(driver_events_nested(), f)
    with open(root / "data" / "client_metric_definitions.json", "w", encoding="utf-8") as f:
        json.dump({"metric_under_review": "Late Delivery Rate", "leadership_claim": "Late Delivery Rate is 56%",
                   "stakeholders": {"VP Operations": "Any delivered order after the promised ETA is late.", "Support Lead": "Only more than 10 minutes beyond ETA should count."},
                   "note": "No canonical KPI owner is formally documented."}, f)
    with open(root / "api" / "dispatch_data.json", "w", encoding="utf-8") as f:
        json.dump(dispatch_records(include_unknown=messy), f)
    return root


# --------------------------------------------------------------------------- fault-injecting API
class FakeDispatchServer:
    """A tiny HTTP server that mimics the client's Dispatch API with configurable faults."""

    def __init__(self, data: list[dict]):
        from flask import Flask, jsonify, request
        self.data = data
        self.mode = "normal"
        self.hits: dict[int, int] = {}
        self.calls = 0
        app = Flask("fake-dispatch")

        @app.get("/health")
        def health():
            return jsonify({"status": "ok"})

        @app.get("/dispatch/orders")
        def orders():
            self.calls += 1
            page = int(request.args.get("page", 1))
            size = int(request.args.get("page_size", 50))
            self.hits[page] = self.hits.get(page, 0) + 1
            first = self.hits[page] == 1
            m = self.mode
            if m == "flaky" and page == 2 and first:
                return jsonify({"error": "upstream"}), 500
            if m == "flaky" and page == 1 and first:
                return jsonify({"error": "rate limit"}), 429, {"Retry-After": "0"}
            if m == "always_500":
                return jsonify({"error": "down"}), 500
            if m == "not_found":
                return jsonify({"error": "no such route"}), 404
            if m == "malformed_json":
                return "{this is not json", 200, {"Content-Type": "application/json"}
            if m == "missing_data_key":
                return jsonify({"items": [], "has_more": False})
            if m == "timeout":
                time.sleep(3)
            start, end = (page - 1) * size, page * size
            items = self.data[start:end]
            payload = {"data": items, "page": page, "page_size": size, "has_more": end < len(self.data), "total_records": len(self.data)}
            if m == "wrong_total":
                payload["total_records"] = len(self.data) + 5
            if m == "no_has_more":
                payload.pop("has_more")
                payload.pop("total_records")
            if m == "empty":
                payload.update({"data": [], "has_more": False, "total_records": 0})
            if m == "overlap" and page == 2:
                payload["data"] = self.data[0:1] + items
            if m == "never_ends":
                payload["has_more"] = True
            if m == "missing_fields":
                payload["data"] = [{k: v for k, v in r.items() if k not in ("assigned_at", "eta_model_version")} for r in items]
            return jsonify(payload)

        self.app = app
        self.port = self._free_port()
        from werkzeug.serving import make_server
        self.server = make_server("127.0.0.1", self.port, app, threaded=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @staticmethod
    def _free_port() -> int:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.server.shutdown()


@pytest.fixture
def messy_pack(tmp_path: Path) -> Path:
    return build_pack(tmp_path / "pack", messy=True)


@pytest.fixture
def clean_pack(tmp_path: Path) -> Path:
    return build_pack(tmp_path / "clean_pack", messy=False)


@pytest.fixture
def api_server():
    srv = FakeDispatchServer(dispatch_records()).start()
    yield srv
    srv.stop()


@pytest.fixture
def make_config(tmp_path: Path):
    def _make(source_root: Path, api_url: str, **kw) -> PipelineConfig:
        base = dict(project_root=ROOT, source_root=source_root, data_dir=tmp_path / "data", output_dir=tmp_path / "output",
                    api_base_url=api_url, api_page_size=5, api_timeout_s=1.0, api_max_retries=3, api_backoff_base_s=0.01, api_backoff_cap_s=0.02,
                    write_charts=False, weather_enabled=False)
        base.update(kw)
        return PipelineConfig(**base)
    return _make


# --------------------------------------------------------------------------- fake Open-Meteo archive
def weather_payload(rain_hours: set[str] | None = None, tz: str = "Asia/Kolkata") -> dict:
    """Hourly payload for 2026-08-01 .. 2026-08-05; ``rain_hours`` are 'YYYY-MM-DDTHH:00' strings with 2.0 mm."""
    import datetime as _dt
    rain_hours = rain_hours or set()
    start = _dt.datetime(2026, 8, 1)
    times = [(start + _dt.timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(5 * 24)]
    precip = [2.0 if t in rain_hours else 0.0 for t in times]
    return {"latitude": 12.97, "longitude": 77.59, "timezone": tz, "hourly_units": {"time": "iso8601", "precipitation": "mm"},
            "hourly": {"time": times, "precipitation": precip, "rain": precip}}


class FakeWeatherServer:
    def __init__(self, payload: dict):
        from flask import Flask, jsonify
        self.payload, self.mode, self.calls = payload, "normal", 0
        app = Flask("fake-weather")

        @app.get("/v1/archive")
        def archive():
            self.calls += 1
            m = self.mode
            if m == "always_500":
                return jsonify({"error": True}), 500
            if m == "flaky" and self.calls == 1:
                return jsonify({"error": True}), 503
            if m == "bad_request":
                return jsonify({"error": True, "reason": "bad"}), 400
            if m == "not_json":
                return "<html>maintenance</html>", 200
            if m == "no_hourly":
                return jsonify({"latitude": 1})
            if m == "empty":
                return jsonify({**self.payload, "hourly": {"time": [], "precipitation": []}})
            if m == "length_mismatch":
                h = dict(self.payload["hourly"]); h["precipitation"] = h["precipitation"][:-1]
                return jsonify({**self.payload, "hourly": h})
            if m == "wrong_tz":
                return jsonify({**self.payload, "timezone": "UTC"})
            return jsonify(self.payload)

        from werkzeug.serving import make_server
        self.port = FakeDispatchServer._free_port()
        self.server = make_server("127.0.0.1", self.port, app, threaded=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1/archive"

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.server.shutdown()


# the synthetic orders were created at these hours; rain is observed at the first two only
RAIN_HOURS = {"2026-08-01T10:00", "2026-08-01T11:00"}


@pytest.fixture
def weather_server():
    srv = FakeWeatherServer(weather_payload(RAIN_HOURS)).start()
    yield srv
    srv.stop()

"""Build and execute the four classroom challenge notebooks plus the pipeline walkthrough.

    python notebooks/build_notebooks.py            # build + execute every notebook
    python notebooks/build_notebooks.py --no-exec  # build only

Challenges/ holds the instructor's four notebooks (Class 5 Starter, Class 5 Student,
Class 6 Student, Class 7 Challenge) **with every original cell kept in order** and
answer cells inserted after each challenge. Only these original cells are replaced,
and each replacement says so in its first line:
* the Colab / zip pack loaders and ``!pip install`` lines (the pack lives in source_systems/),
* the two skeleton cells that would create ``source_systems/student_output/`` (answers
  write to ``Challenges/output/`` instead, so the client snapshot is never modified),
* the API start-up cells, made to wait until the mock API is healthy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import nbformat as nbf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ORIG = HERE / "classroom_originals"
CHALLENGES = ROOT / "Challenges"


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip("\n"))


def code(text: str):
    return nbf.v4.new_code_cell(text.strip("\n"))


def answer(text: str):
    return md("> ✅ **Answer**\n\n" + text.strip("\n"))


SETUP = r'''
# [replaced classroom cell] The Colab/zip loader and `!pip install` are not needed here:
# the client pack lives in source_systems/ and dependencies come from requirements.txt.
import os, sys, json, time, sqlite3, subprocess, zipfile
from pathlib import Path
import pandas as pd
import requests
import matplotlib.pyplot as plt

ROOT = Path.cwd()
while not (ROOT / "source_systems").exists() and ROOT.parent != ROOT:
    ROOT = ROOT.parent
BASE = ROOT / "source_systems"                    # read-only client systems
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "Challenges" / "output"             # scratch outputs of the challenge notebooks
OUT.mkdir(parents=True, exist_ok=True)
pd.set_option("display.max_columns", 100); pd.set_option("display.width", 170); pd.set_option("display.max_colwidth", 90)
print("BASE:", BASE, "| database exists:", (BASE / "database" / "flasheats.db").exists())
'''

START_API = r'''
# [classroom cell, made robust] start the mock Dispatch API and wait until it is healthy (instead of a fixed sleep)
api_script = BASE / "api" / "mock_dispatch_api.py"
api_proc = subprocess.Popen([sys.executable, str(api_script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(60):
    try:
        if requests.get("http://127.0.0.1:8000/health", timeout=2).ok:
            break
    except requests.RequestException:
        time.sleep(0.25)
health = requests.get("http://127.0.0.1:8000/health", timeout=10)
print(health.status_code, health.json())
'''

FETCH_IMPL = r'''
# [classroom skeleton completed] reliable paginated ingestion
# Requirements from the skeleton: fetch every page, retry HTTP 500 / 429, preserve successful raw
# responses, fail clearly on unrecoverable errors, verify the final record count.
API_URL = "http://127.0.0.1:8000/dispatch/orders"
RAW_DIR = OUT / RAW_SUBDIR                           # NOT inside source_systems/ - the client snapshot stays untouched
RAW_DIR.mkdir(parents=True, exist_ok=True)

def fetch_all_dispatch_orders(page_size=100, max_retries=4, timeout=10):
    records, seen, page, expected_total, log = [], set(), 1, None, []
    while True:
        for attempt in range(1, max_retries + 1):
            try:
                r = requests.get(API_URL, params={"page": page, "page_size": page_size}, timeout=timeout)
            except (requests.Timeout, requests.ConnectionError) as exc:
                log.append((page, attempt, type(exc).__name__)); time.sleep(min(2 ** (attempt - 1), 4)); continue
            if r.status_code in (429, 500, 502, 503, 504):
                wait = float(r.json().get("retry_after_seconds", 0)) if r.status_code == 429 else min(2 ** (attempt - 1), 4)
                log.append((page, attempt, r.status_code)); time.sleep(wait); continue
            r.raise_for_status()                          # 4xx = configuration bug, never retried
            payload = r.json()
            break
        else:
            raise RuntimeError(f"page {page} failed after {max_retries} attempts: {log[-3:]}")
        if not isinstance(payload.get("data"), list):     # HTTP 200 is not proof: validate the body
            raise RuntimeError(f"page {page}: unexpected payload keys {list(payload)}")
        (RAW_DIR / f"dispatch_page_{page:03d}.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
        expected_total = payload.get("total_records", expected_total)
        for rec in payload["data"]:
            if rec["order_id"] in seen:
                raise RuntimeError(f"order {rec['order_id']} returned twice - pagination overlap")
            seen.add(rec["order_id"]); records.append(rec)
        if not payload.get("has_more"):
            break
        page += 1
    if expected_total is not None and len(records) != expected_total:
        raise RuntimeError(f"incomplete ingestion: got {len(records)}, server reports {expected_total}")
    return records, log

dispatch_records, retry_log = fetch_all_dispatch_orders()
dispatch_df = pd.DataFrame(dispatch_records)
print("pages saved:", len(list(RAW_DIR.glob("dispatch_page_*.json"))), "| retried:", retry_log)
print("records:", len(dispatch_df), "| unique orders:", dispatch_df["order_id"].nunique(), "| reassigned:", dispatch_df["reassigned_at"].notna().sum())
display(dispatch_df.head())
'''

CLEANUP = r'''
# cleanup: close the database and stop the mock API started above
try:
    con.close()
except Exception:
    pass
try:
    api_proc.terminate(); api_proc.wait(timeout=5)
except Exception:
    pass
print("cleanup complete")
'''


def weave(original: str, replace: dict[int, list], after: dict[int, list], append: list | None = None):
    nb = nbf.read(ORIG / f"{original}.ipynb", as_version=4)
    cells = []
    for i, c in enumerate(nb.cells):
        if i in replace:
            cells.extend(replace[i])
        else:
            c = nbf.v4.new_markdown_cell(c.source) if c.cell_type == "markdown" else nbf.v4.new_code_cell(c.source)
            cells.append(c)
        cells.extend(after.get(i, []))
    cells.extend(append or [])
    out = nbf.v4.new_notebook()
    out.cells = cells
    out.metadata = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}
    return out


# ============================================================================ Class 5 — Starter
def class5_starter():
    return weave("FlashEats_Class5_Starter", replace={
        1: [code(SETUP)],
        11: [code(START_API)],
        14: [code('RAW_SUBDIR = "raw_dispatch_starter"\n' + FETCH_IMPL)],
    }, after={
        2: [answer("""
Decided **before** querying:

| Decision | Choice | Why |
|---|---|---|
| Late means | `actual_delivery_at − promised_eta > 0 min` | the promise the customer saw is the yardstick |
| Denominator | delivered orders with both timestamps, **one row per order** | the raw table repeats 3 orders |
| Cancellations | excluded | nothing was delivered, so nothing can be late |
| Missing actual delivery time | excluded **and counted** (unknown outcome, not on time) | 37 orders; bounds the KPI |
| Grain | one row per `order_id` after de-duplication | `COUNT(*)` ≠ `COUNT(DISTINCT order_id)` |

This notebook answers the Starter challenges **in SQL first** (the Student notebook does them in pandas), to show that the same definitions give the same numbers in both tools.""")],
        4: [code(r'''
# Three SQL versions of the same KPI - each fixes one trap, so the difference is explainable, not mysterious
POP_SQL = """
WITH one_row AS (SELECT o.* FROM orders o JOIN (SELECT MIN(rowid) rid FROM orders GROUP BY order_id) f ON f.rid = o.rowid),
pop AS (SELECT *, (julianday(actual_delivery_at) - julianday(promised_eta)) * 1440 AS delay_min
        FROM one_row WHERE lower(trim(final_status)) = 'delivered' AND actual_delivery_at IS NOT NULL
          AND promised_eta >= created_at AND actual_delivery_at >= pickup_at)
"""   # the validated population, reused by the next challenges
naive = pd.read_sql("""
SELECT COUNT(*) AS delivered, SUM(julianday(actual_delivery_at) > julianday(promised_eta)) AS late
FROM orders WHERE final_status = 'delivered' AND actual_delivery_at IS NOT NULL""", con)

dedup = pd.read_sql("""
WITH one_row AS (SELECT o.* FROM orders o JOIN (SELECT MIN(rowid) rid FROM orders GROUP BY order_id) f ON f.rid = o.rowid)
SELECT COUNT(*) AS delivered, SUM(julianday(actual_delivery_at) > julianday(promised_eta)) AS late
FROM one_row WHERE lower(trim(final_status)) = 'delivered' AND actual_delivery_at IS NOT NULL""", con)

validated = pd.read_sql((ROOT / "sql" / "independent_late_rate_check.sql").read_text(encoding="utf-8"), con)   # + chronology rules

kpi = pd.DataFrame({
    "version": ["naive: status = 'delivered'", "+ one row per order, 'Delivered' = 'delivered'", "+ chronology rules (promise after creation, delivery after pickup)"],
    "delivered": [int(naive.delivered[0]), int(dedup.delivered[0]), int(validated.valid_delivered[0])],
    "late": [int(naive.late[0]), int(dedup.late[0]), int(validated.late_orders[0])]})
kpi["late_rate_%"] = (100 * kpi["late"] / kpi["delivered"]).round(2)
display(kpi)

print(pd.read_sql("SELECT COUNT(*) rows_, COUNT(DISTINCT order_id) orders_ FROM orders", con).to_string(index=False))
print(pd.read_sql("SELECT final_status, COUNT(*) n FROM orders GROUP BY final_status", con).to_string(index=False))
print("delivered but no actual_delivery_at:", pd.read_sql("SELECT COUNT(DISTINCT order_id) n FROM orders WHERE lower(final_status)='delivered' AND actual_delivery_at IS NULL", con).n[0])
'''), answer("""
- The **naive** query gives 1493 / 841: it misses the 5 `Delivered` rows (capital D) and double-counts the 3 duplicated orders.
- **One row per order** plus status normalisation gives **1495 / 843 = 56.39 %**. This matches the class answer and the leadership claim.
- Applying the **chronology rules** gives **1486 / 837 = 56.33 %**. Four promises were made before the order existed and five deliveries happened before pickup, so their lateness is meaningless. The pipeline publishes this figure.
- 37 delivered orders have no delivery time, so the true rate lies between 55.0 % (all on time) and 57.4 % (all late).

**Checkpoint:** when two teams disagree, the cause is almost always one of these three traps, not arithmetic.""")],
        7: [code(r'''
q = POP_SQL + """
SELECT {dim} AS bucket, COUNT(*) AS orders, ROUND(100.0 * AVG(delay_min > 0), 1) AS late_rate_pct, ROUND(AVG(delay_min), 1) AS avg_delay_min
FROM pop GROUP BY 1 ORDER BY 1"""
for name, dim in [("traffic", "lower(trim(traffic_bucket))"), ("weather", "weather_bucket"),
                  ("distance band", "CASE WHEN distance_km_estimate <= 6 THEN '0-6 km' WHEN distance_km_estimate <= 12 THEN '6-12 km' ELSE '12+ km' END"),
                  ("hour of day", "CAST(strftime('%H', created_at) AS INTEGER)")]:
    print(f"--- {name}"); display(pd.read_sql(q.format(dim=dim), con))
'''), answer("""
**Traffic is associated with lateness.** The late rate rises from 49 % in low traffic to 66 % in high or severe traffic. Distance shows only a weak gradient, from 51 % under 6 km to 57 % above 12 km, and the hour of day moves the rate between 43 % and 72 %.

**Why this is not proof:**
- The traffic bucket is a label attached to the order, not a measurement taken on the route.
- The evening peak raises traffic, kitchen load and driver scarcity at the same time.
- A later finding in `insights/` shows that almost all lateness builds up *before pickup*. The road is not where the time is lost, even when traffic is high.""")],
        9: [code(r'''
print("rows:", len(tickets), "| unique ticket ids:", tickets.ticket_id.nunique(), "| exact duplicate rows:", tickets.duplicated().sum(),
      "| tickets without order_id:", tickets.order_id.isna().sum())
print("raw categories:", sorted(tickets.category.unique()))
t = tickets.drop_duplicates().assign(category_norm=lambda d: d.category.str.strip().str.lower().str.replace(r"[\s-]+", "_", regex=True))
display(t.category_norm.value_counts().rename("tickets").to_frame())
# does the customer story match the operational story? (join tickets to the validated KPI population)
pop = pd.read_sql(POP_SQL + " SELECT order_id, delay_min FROM pop", con)
v = t.merge(pop, on="order_id", how="left")
display(v.groupby("category_norm").agg(tickets=("ticket_id", "size"), matched=("delay_min", "count"),
                                        late_share_pct=("delay_min", lambda s: round(100 * (s > 0).mean(), 1)), median_delay=("delay_min", "median")).round(1))
'''), answer("""
- **Customer view:** complaints are about lateness, the ETA changing and the restaurant. `ETA issue` is kept separate from `eta_changed`, because merging them is a meaning decision for the Support Lead.
- **System view:** 68–91 % of ticketed orders really were late, depending on the category, with median delays of 8–15 minutes. Customers are not crying wolf.
- **Ticket IDs are not unique.** One ticket appears twice as an exact duplicate, and three tickets have no order ID at all.
- **What tickets add:** the customer's belief about the cause and the moment they lost patience. No timestamp captures either.""")],
        16: [code(r'''
ev = pd.DataFrame([{"driver_id": d["driver_id"], **e} for d in driver_events for e in d["events"]])
ev["timestamp"] = pd.to_datetime(ev["timestamp"], format="mixed")
display(ev.type.value_counts())
print("explicit arrived-at-restaurant events:", (ev.type == "arrived_at_restaurant").sum())

# Beyond the class: can ARRIVAL be inferred from GPS (a geofence around the restaurant)?
import numpy as np
orders = pd.read_sql("SELECT DISTINCT order_id, restaurant_id, pickup_at FROM orders", con).drop_duplicates("order_id")
orders["pickup_at"] = pd.to_datetime(orders.pickup_at, format="mixed")
rest = pd.read_sql("SELECT restaurant_id, lat r_lat, lon r_lon FROM restaurants WHERE lat BETWEEN 12.5 AND 13.5 AND lon BETWEEN 77.2 AND 78", con)
p = ev[ev.type == "gps_ping"].merge(orders, on="order_id").merge(rest, on="restaurant_id")
p = p[p.timestamp <= p.pickup_at].sort_values("timestamp")
R = np.radians
p["km"] = 6371 * 2 * np.arcsin(np.sqrt(np.sin((R(p.lat) - R(p.r_lat)) / 2) ** 2 + np.cos(R(p.lat)) * np.cos(R(p.r_lat)) * np.sin((R(p.lon) - R(p.r_lon)) / 2) ** 2))
g = p.groupby("order_id").km.agg(first="first", last="last", n="size")
g = g[g.n >= 2]
print(f"orders with >=2 pre-pickup pings: {len(g)} | last ping closer to the restaurant than the first: {(g['last'] < g['first']).mean():.1%} "
      f"| FARTHER: {(g['last'] > g['first']).mean():.1%} | median last-ping distance: {g['last'].median():.1f} km")

# ...and do the pings look MEASURED or DRAWN? A real device track wiggles and has uneven gaps;
# an app that interpolates a straight line between two points does not.
allp = ev[ev.type == "gps_ping"].merge(orders, on="order_id")
print(f"pings before pickup: {(allp.timestamp <= allp.pickup_at).mean():.1%} of {len(allp)} (Session 6 expected pings only before pickup)")
def straightness(t):
    if len(t) < 3:
        return np.nan
    x = (t.timestamp - t.timestamp.iloc[0]).dt.total_seconds().to_numpy(float)
    return min(1.0 if np.ptp(t[c]) == 0 else np.corrcoef(x, t[c].to_numpy(float))[0, 1] ** 2 for c in ("lat", "lon"))
inside = ev[(ev.type == "gps_ping") & ev.lat.between(12.5, 13.5) & ev.lon.between(77.2, 78.0)].sort_values("timestamp")
shape = inside.groupby("order_id")[["timestamp", "lat", "lon"]].apply(straightness).dropna()
print(f"tracks with >=3 in-area pings: {len(shape)} | perfectly straight, constant-speed (R^2 >= 0.999): {(shape >= 0.999).mean():.1%}")
'''), answer("""
| Event / fact | Observed? | Source | Reliability concern |
|---|---|---|---|
| Driver assigned | **Observed** | driver app `assigned`, Dispatch `assigned_at` | 14 orders show `picked_up` *before* `assigned` |
| Driver at restaurant | **Not observed; not inferable either** | GPS pings | before pickup the pings move *away* from the restaurant in about 99 % of orders, and about 9 in 10 tracks are perfect straight constant-speed lines. The pings look drawn by the app, not measured, so a geofence would invent arrivals |
| Picked up | **Observed** | `orders.pickup_at`, driver app | agree to the second for 1527 orders |
| Delivered | **Observed** | `orders.actual_delivery_at`, driver app | 37 delivered orders lack the DB timestamp but have the driver event |

The class exercise names GPS as the signal from which arrival could be *inferred*. On this feed it cannot: the pings look interpolated. Session 6 also said pings stop at pickup; here about 30 % fall before pickup and the rest after it. The only fix is a new event, such as a driver-app tap on arrival, and a question to Fleet Ops: are these pings device readings?""")],
        17: [answer("""
**Problem size:** 56.3 % of validated deliveries are late (837 of 1486). The median late order is 8 minutes late, and one in four deliveries is more than 10 minutes late.

**Evidence:** lateness is associated with traffic, time of day and the weather label. The weather label turns out not to match observed weather (see Class 6 and `insights/`).

**Uncertainty:**
- 37 orders have an unknown outcome.
- 9 orders have contradictory timestamps.
- No arrival event exists.
- Four definitions of "late" compete, and none has an owner.

**Missing instrumentation:** an *arrived at restaurant* tap, a mandatory delivery timestamp, reassignment written back to the orders table, and a cancellation timestamp.

**Build the AI delay predictor now? No.** It would learn from promises that are sometimes made before the order exists, and it would lack the one event that separates kitchen delay from rider delay. First ship the rule-based pickup-overrun trigger from the pipeline's decision layer, which is 96 % precise on the held-out week. That trigger becomes the baseline any future model has to beat."""), code(CLEANUP)],
    })


# ============================================================================ Class 5 — Student
def class5_student():
    return weave("FlashEats_Class5_Student", replace={
        1: [code(SETUP)],
        2: [code('# [replaced classroom cell] pack already located by the setup cell above\nprint("BASE:", BASE)\nprint("Exists:", BASE.exists())')],
        13: [code(START_API)],
        15: [code('RAW_SUBDIR = "raw_dispatch_student"\n' + FETCH_IMPL)],
    }, after={
        3: [answer("""
| Information | Likely source | Authoritative? | Why |
|---|---|---|---|
| Promised delivery time | `orders.promised_eta` (SQLite) | **Yes**: the promise the customer saw | Dispatch's `current_delivery_eta` is a later revision |
| Actual delivery time | `orders.actual_delivery_at` | **Yes**, but 37 delivered orders have none | the driver-app `delivered` event could back-fill them; that needs the owner's sign-off |
| Driver assignment | Dispatch API (`assigned_at`, `reassigned_at`, `driver_id`) | **Yes** for the final driver | `orders.driver_id` keeps the *original* driver after a reassignment |
| Customer complaint | `support_tickets.csv` | yes for *what the customer said* | only contextual for what happened |
| Restaurant status | `restaurant_status.csv` | contextual | covers 31 % of orders, minute precision, mixed spellings |
| Driver movement | `driver_events.json` | yes for movement | no *arrived at restaurant* event |""")],
        6: [answer("""
- **Late** means `actual_delivery_at − promised_eta > 0`.
- **Denominator:** delivered orders with both timestamps, with one row per order.
- **Cancelled orders** are excluded.
- **Missing actual delivery time:** excluded and reported as unknown.
- **Grain:** one row per order after de-duplication."""), code(r'''
orders = pd.read_sql("SELECT * FROM orders;", con)
print("raw rows:", len(orders), "| unique orders:", orders.order_id.nunique(), "| extra duplicate rows:", len(orders) - orders.order_id.nunique())
display(orders[orders.order_id.duplicated(keep=False)].sort_values("order_id")[["order_id", "final_status", "traffic_bucket"]])  # they disagree!

oa = orders.drop_duplicates("order_id", keep="first").copy()
oa["final_status"] = oa.final_status.str.strip().str.lower()            # 'Delivered' is spelling, not a new status
oa["traffic_bucket"] = oa.traffic_bucket.str.strip().str.lower()          # 'HIGH' likewise
for c in ["created_at", "promised_eta", "pickup_at", "actual_delivery_at"]:
    oa[c] = pd.to_datetime(oa[c], format="mixed", errors="coerce")
valid = oa[(oa.final_status == "delivered") & oa.actual_delivery_at.notna() & oa.promised_eta.notna()].copy()
valid["delay_min"] = (valid.actual_delivery_at - valid.promised_eta).dt.total_seconds() / 60
late = valid[valid.delay_min > 0]
print(f"cancelled: {(oa.final_status == 'cancelled').sum()} | delivered without actual time: {((oa.final_status == 'delivered') & oa.actual_delivery_at.isna()).sum()}")
print(f"valid delivered: {len(valid)} | late: {len(late)} | late %: {100 * len(late) / len(valid):.2f} | median lateness: {late.delay_min.median():.1f} min")
display(late.sort_values("delay_min", ascending=False)[["order_id", "created_at", "promised_eta", "actual_delivery_at", "delay_min"]].head(6))
'''), answer("""
- **Result:** 843 of 1495 valid deliveries were late, **56.4 %**, with a median lateness of **8.0 min**.
- **Read the "worst delayed" list before believing it.** The four largest delays, +85 to +87 minutes on orders O00101–O00104, have a *promised ETA ten minutes before the order was created*. They are a data bug, not deliveries. The worst genuine delay is **O01081 at +50.3 min**. The pipeline therefore excludes chronology violations and publishes **56.33 %** on 1486 orders.
- **Data-quality issues that change the metric:**
  - 3 duplicated orders that disagree on traffic;
  - 68 cancellations;
  - 37 missing delivery times, which bound the KPI between 55.0 % and 57.4 %;
  - 9 chronology violations.""")],
        9: [code(r'''
def summarise(df, by):
    g = df.groupby(by, observed=True)["delay_min"].agg(count="count", median="median", mean="mean").round(1)
    g["late_rate_%"] = (df.assign(l=df.delay_min > 0).groupby(by, observed=True)["l"].mean() * 100).round(1)
    return g
for by, frame in [("traffic_bucket", valid), ("weather_bucket", valid),
                  ("distance_band", valid.assign(distance_band=pd.cut(valid.distance_km_estimate, [0, 3, 6, 10, 20, 50], include_lowest=True))),
                  ("hour", valid.assign(hour=valid.created_at.dt.hour))]:
    display(summarise(frame, by))
fig, ax = plt.subplots(1, 2, figsize=(11, 3.5))
summarise(valid, "traffic_bucket")["late_rate_%"].plot(kind="bar", ax=ax[0], title="Late rate by traffic bucket")
summarise(valid, "weather_bucket")["late_rate_%"].plot(kind="bar", ax=ax[1], title="Late rate by weather label", color="tab:orange")
plt.tight_layout(); plt.savefig(OUT / "class5_traffic_weather.png", dpi=110); plt.show()
'''), answer("""
**Hypothesis supported by the evidence:** lateness is associated with traffic and with the weather label.
- By traffic, the late rate rises from 49 % in low traffic to 66 % in severe traffic.
- By weather label, it rises from 53 % when clear to 74 % in heavy rain.
- Normalising the `HIGH` spelling first stops it from appearing as a fifth, misleading bucket.

**Alternative explanation that cannot be ruled out:** the evening peak raises traffic, kitchen load and driver scarcity at the same time. Distance shows no pattern.

**Beyond the class:** the pipeline checked the weather label against Open-Meteo's *observed* Bengaluru rainfall. The two agree about as often as chance (kappa ≈ 0). Orders labelled heavy rain saw no more rain than orders labelled clear, so the weather association is an association with a label, not with the sky.""")],
        11: [code(r'''
print("rows:", len(tickets), "| unique ids:", tickets.ticket_id.nunique(), "| exact duplicate rows:", tickets.duplicated().sum(), "| no order_id:", tickets.order_id.isna().sum())
t = tickets.drop_duplicates().assign(category_norm=lambda d: d.category.str.strip().str.lower().str.replace(r"[\s-]+", "_", regex=True))
tv = t.merge(valid[["order_id", "delay_min"]], on="order_id", how="left")      # LEFT: tickets are the base table
assert len(tv) == len(t), "join inflated the ticket count"
display(tv.groupby("category_norm").agg(tickets=("ticket_id", "size"), matched=("delay_min", "count"), median_delay=("delay_min", "median"),
                                          late_share_pct=("delay_min", lambda s: round(100 * (s > 0).mean(), 1))).round(1).sort_values("tickets", ascending=False))
'''), answer("""
| | Customer view (tickets) | System view (orders) |
|---|---|---|
| Most common complaint | `late_delivery` (39 after normalising and removing the duplicate), then `eta_changed` and `restaurant_delay` | 56 % of all deliveries are late, so a ticket is the exception, not the rule |
| Are the complaints justified? | yes | ticketed `late_delivery` orders have a median delay of **14.8 min** and 85 % of them were late; 90 % for `ready_but_waiting` and `status_mismatch` |
| `ready_but_waiting` / `status_mismatch` | the restaurant says ready, the app says picking up | 90 % late, and the gap between restaurant and rider is real but **unmeasured** (no arrival event) |
| Hygiene | 1 duplicated ticket ID, 3 tickets without an order, 3 spelling variants | the support system is not the event log |""")],
        17: [code(r'''
ev = driver_events_df.assign(ts=pd.to_datetime(driver_events_df.timestamp, format="mixed"))
piv = ev[ev.type.isin(["assigned", "picked_up", "delivered"])].groupby(["order_id", "type"]).ts.min().unstack()
pings = ev[ev.type == "gps_ping"].merge(piv, left_on="order_id", right_index=True)
print("explicit arrival events:", (ev.type == "arrived_at_restaurant").sum())
print("pings before pickup:", (pings.ts <= pings.picked_up).sum(), "| after pickup:", (pings.ts > pings.picked_up).sum(),
      "| out-of-area pings (lat>13.5 or lon>78):", ((pings.lat > 13.5) | (pings.lon > 78)).sum())
print("orders with picked_up before assigned:", (piv.picked_up < piv.assigned).sum())
missing = oa[(oa.final_status == "delivered") & oa.actual_delivery_at.isna()].order_id
print("delivered orders missing actual time that DO have a driver 'delivered' event:", missing.isin(piv[piv.delivered.notna()].index).sum(), "of", len(missing))
'''), answer("""
| Event / fact | Observed? | Source | Reliability concern |
|---|---|---|---|
| Driver assigned | **Observed** | Dispatch `assigned_at`; driver app `assigned` | 14 orders are picked up *before* they are assigned |
| Driver at restaurant | **Not observed** | none | GPS pings do not converge on the restaurant and look interpolated (see the Class 5 Starter), so the event cannot be inferred |
| Picked up | **Observed** | `orders.pickup_at`; driver app | agree for 1527 orders |
| Delivered | **Observed** | `orders.actual_delivery_at`; driver app | 37 DB gaps, all recoverable from the driver event, pending the owner's decision |""")],
        18: [answer("""
1. **Problem size.** 56.4 % of 1495 valid deliveries were late (56.3 % validated). The median late order was 8 minutes late and P90 is about 18 minutes.
2. **Evidence.** 99 % of the lateness minutes accrue **before pickup**. Dispatch's pickup estimate is short by a median 8 minutes. Traffic and hour of day are associated with lateness; distance is not. The weather label does not match observed weather.
3. **Trusted sources.** The orders table for the promise and delivery time, Dispatch for assignments, the driver app for movement, and tickets for customer perception only.
4. **Uncertainty.** 37 unknown outcomes, 9 chronology violations, no arrival event, a stale driver ID after reassignment, and no owner for the KPI definition.
5. **Instrumentation.** An arrival tap, a mandatory delivery timestamp, reassignment written back to the orders table, a cancellation timestamp, and an explanation of how `weather_bucket` is produced.
6. **Decision: no AI predictor yet.** Ship the pickup-overrun trigger now (96 % precision on the held-out week). A future model must beat it.""")],
    })


# ============================================================================ Class 6 — Student
def class6_student():
    return weave("FlashEats_Class6_Student", replace={1: [code(SETUP)]}, after={
        4: [answer("""
| Business assumption | Data expectation | How it is tested | Severity if false |
|---|---|---|---|
| One row = one business order | `order_id` unique | rows vs `nunique()`; do the duplicates disagree? | HIGH: the denominator inflates |
| Delivered orders have a completion time | delivered ⇒ `actual_delivery_at` not null | count nulls among delivered orders | HIGH: the population shrinks with unknown bias |
| Promised ETA is valid | parseable and `promised_eta ≥ created_at` | coerce, then compare | HIGH: lateness against an impossible promise is meaningless |
| Event chronology is valid | `created ≤ pickup ≤ delivered` | pairwise comparison | MEDIUM: stage metrics go negative |
| "Late" has an agreed definition | one owner, one formula | `client_metric_definitions.json` | HIGH: every team publishes a different number |""")],
        5: [code(r'''
customers = pd.read_sql("SELECT customer_id FROM customers", con)
a = orders.drop_duplicates("order_id", keep="first").copy()
a["final_status_norm"] = a.final_status.str.strip().str.lower()
for c in ["created_at", "promised_eta", "pickup_at", "actual_delivery_at"]:
    a[c] = pd.to_datetime(a[c], format="mixed", errors="coerce")
checks = pd.Series({
    "conflicting duplicate orders": orders[orders.order_id.duplicated(keep=False)].groupby("order_id").traffic_bucket.nunique().gt(1).sum(),
    "delivered without completion time": ((a.final_status_norm == "delivered") & a.actual_delivery_at.isna()).sum(),
    "promised_eta < created_at": (a.promised_eta < a.created_at).sum(),
    "actual_delivery_at < pickup_at": (a.actual_delivery_at < a.pickup_at).sum(),
    "pickup_at < created_at": (a.pickup_at < a.created_at).sum(),
    "null restaurant_id / driver_id": a.restaurant_id.isna().sum() + a.driver_id.isna().sum(),
}, name="violations")
display(checks)
bad = a[(a.promised_eta < a.created_at) | (a.actual_delivery_at < a.pickup_at)]
bad = bad.assign(promise_minus_created=(bad.promised_eta - bad.created_at).dt.total_seconds() / 60, delivered_minus_pickup=(bad.actual_delivery_at - bad.pickup_at).dt.total_seconds() / 60)
display(bad[["order_id", "created_at", "promised_eta", "pickup_at", "actual_delivery_at", "promise_minus_created", "delivered_minus_pickup"]])
'''), answer("""
**Questions that need a stakeholder, because the data cannot settle them:**
- **Data Team:** why do three orders exist twice with different traffic buckets? Are two systems writing to the table?
- **Fleet Ops:** may the driver-app `delivered` event back-fill the 37 missing delivery times?
- **ETA service:** every broken promise is off by exactly −10 minutes, and every early delivery by exactly −5 minutes. That looks like a writer bug, not noise.""")],
        7: [code(r'''
a["delay_min"] = (a.actual_delivery_at - a.promised_eta).dt.total_seconds() / 60
hist = a[(a.final_status_norm == "delivered") & a.actual_delivery_at.notna()]
validated = hist[(hist.promised_eta >= hist.created_at) & ~(hist.actual_delivery_at < hist.pickup_at)]
rows = [("VP Operations: any delay > 0 (historical population)", (hist.delay_min > 0).sum(), len(hist), "any missed promise counts"),
        ("Support Lead: delay > 10 min", (hist.delay_min > 10).sum(), len(hist), "'meaningfully late'"),
        ("Data Team: delivered with non-null actual time", (hist.delay_min > 0).sum(), len(hist), "the dashboard population"),
        ("Finance: cancelled / refunded excluded", (hist.delay_min > 0).sum(), len(hist), "already true in every row above"),
        ("Pipeline: validated population (chronology rules)", (validated.delay_min > 0).sum(), len(validated), "drops 9 contradictory orders")]
t = pd.DataFrame(rows, columns=["definition", "late", "population", "business meaning"])
t.insert(1, "late_rate_%", (100 * t.late / t.population).round(2))
display(t)
'''), answer("""
**Publish:** the VP Operations definition on the validated population, **56.3 %**, with the >10-minute rate (≈ 23 %) shown alongside as a severity measure.

**Owner:** VP Operations must sign the definition. Until then, the pipeline's gate marks KPI ownership as **UNKNOWN**, and every output prints the definition next to the number.""")],
        9: [code(r'''
def inspect(name, s):
    norm = s.astype(str).str.strip().str.lower().str.replace(r"[\s-]+", "_", regex=True)
    print(f"--- {name}: raw values {sorted(map(repr, s.dropna().unique()))}")
    display(pd.DataFrame({"raw": s.value_counts()}).join(pd.DataFrame({"after_representation_fix": norm.value_counts()}), how="outer").fillna(0).astype(int))
inspect("final_status", orders.final_status); inspect("traffic_bucket", orders.traffic_bucket)
inspect("restaurant status", restaurant_status.status); inspect("ticket category", tickets.category)
'''), answer("""
| Column | Safe to normalise (spelling) | Needs the owner (meaning) |
|---|---|---|
| `final_status` | `Delivered` → `delivered` | — |
| `traffic_bucket` | `HIGH` → `high` | a new value such as `gridlock` would be a new bucket, not `severe` |
| restaurant `status` | `READY`, `Ready`, `ready ` → `ready` | `handoff` vs `handed_off` (**Restaurant Ops**); `unknown` is a real value |
| ticket `category` | `Late Delivery`, `late_delivery ` → `late_delivery` | `ETA issue` vs `eta_changed` (**Support Lead**) |

The pipeline applies exactly this split. Representation fixes are logged in `output/data_quality_report.md`. Semantic look-alikes are reported and never merged, and the hidden-data tests check that.""")],
        11: [code(r'''
rel = [("orders.restaurant_id → restaurants", a.restaurant_id.isin(restaurants.restaurant_id).mean(), "3 NULL restaurant_id"),
       ("orders.driver_id → drivers", a.driver_id.isin(drivers.driver_id).mean(), "3 NULL driver_id; 95 stale after reassignment"),
       ("orders.customer_id → customers", a.customer_id.isin(customers.customer_id).mean(), ""),
       ("tickets.order_id → orders", tickets.order_id.isin(a.order_id).mean(), "3 tickets without order_id"),
       ("restaurant_status.order_id → orders", restaurant_status.order_id.isin(a.order_id).mean(), "only 500 of 1600 orders have a status row")]
cov = pd.DataFrame(rel, columns=["relationship", "coverage", "note"])
cov["coverage_%"] = (100 * cov.coverage).round(2)
cov["status"] = cov["coverage_%"].map(lambda v: "PASS" if v == 100 else ("WARN" if v >= 95 else "FAIL"))
display(cov[["relationship", "coverage_%", "status", "note"]])
# the check the class did not ask for: does orders.driver_id match Dispatch's FINAL driver?
pages = sorted(max((ROOT / "data" / "raw").glob("run_*/api"), key=lambda p: p.stat().st_mtime).glob("dispatch_page_*.json"))
dispatch = pd.DataFrame([r for p in pages for r in json.loads(p.read_text())["payload"]["data"]])
m = a.merge(dispatch[["order_id", "driver_id", "original_driver_id"]], on="order_id", suffixes=("", "_dispatch"))
print("orders.driver_id == Dispatch final driver:", (m.driver_id == m.driver_id_dispatch).sum(), "| == Dispatch ORIGINAL driver:", (m.driver_id == m.original_driver_id).sum(), "of", len(m))
'''), answer("""
**Is 1 % unmapped acceptable?** It depends on the decision.
- **For the late-delivery rate, yes.** The KPI needs only the order's own timestamps.
- **For restaurant or driver scorecards, no.** Those need every order mapped.

The bigger finding is a mapping that *looks* complete but is wrong: `orders.driver_id` equals Dispatch's **original** driver for 1597 orders. The orders table is never updated after a reassignment, so a driver scorecard built on it would blame the wrong person in 95 cases.""")],
        13: [code(r'''
rs = restaurant_status.drop_duplicates().assign(status_norm=lambda d: d.status.str.strip().str.lower(),
                                                  last_updated_at=lambda d: pd.to_datetime(d.last_updated_at, format="mixed"))
m = rs.merge(a[["order_id", "created_at", "pickup_at"]], on="order_id", how="left")
m["lag_vs_pickup_min"] = (m.last_updated_at - m.pickup_at).dt.total_seconds() / 60
print("orders covered:", m.order_id.nunique(), "of", len(a), "| precision: minutes only")
display(m.groupby("status_norm").lag_vs_pickup_min.describe().round(1))
print("ready/handed_off written > 15 min AFTER pickup:", (m.status_norm.isin(["ready", "handed_off"]) & (m.lag_vs_pickup_min > 15)).sum(),
      "| written BEFORE the order existed:", (m.last_updated_at < m.created_at).sum())
'''), answer("""
| Use case | Fresh enough? | Why |
|---|---|---|
| Weekly analytics | **WARN, usable** | covers 31 % of orders at minute precision; fine for aggregates if the coverage bias is stated |
| Live customer ETA | **FAIL** | some `ready` updates arrive after pickup, and some before the order exists |
| Restaurant accountability | **FAIL** | 38 % of restaurants update manually, so a late `ready` may be a late *update*, not a late *kitchen* |""")],
        15: [code(r'''
validation_report = {
    "business_grain":       ("WARN",    "1603 rows / 1600 orders; 3 conflicting duplicates kept-first and quarantined"),
    "timestamp_chronology": ("WARN",    "4 promises before creation (−10 min), 5 deliveries before pickup (−5 min), 37 missing delivery times"),
    "kpi_definition":       ("UNKNOWN", "4 stakeholder definitions, no documented owner"),
    "category_semantics":   ("WARN",    "spelling fixed; 'handoff' and 'ETA issue' kept separate for their owners"),
    "cross_source_mapping": ("WARN",    "99.8 % restaurant/driver, 98.5 % tickets; orders.driver_id stale after reassignment"),
    "freshness":            ("WARN",    "restaurant feed: 31 % coverage, minute precision, stale and pre-creation updates"),
    "weather_label":        ("WARN",    "beyond the class: client weather label vs observed Open-Meteo rainfall, kappa ≈ 0"),
    "publish_56_percent":   ("PUBLISH WITH CAVEATS", "56.3 % of 1486 validated deliveries (56.4 % on the dashboard definition)"),
}
display(pd.DataFrame(validation_report, index=["status", "evidence"]).T)
gate_file = ROOT / "output" / "validation_gate.json"
if gate_file.exists():
    g = json.loads(gate_file.read_text(encoding="utf-8"))
    print("pipeline gate of the last published run:", g["overall_status"], "->", g["publish_decision"])
'''), answer("""
**Should leadership publish "Late Delivery Rate = 56 %" today?** Yes, **with caveats**, never as a bare number:

> "56.3 % of validated August deliveries (837 of 1486) missed the promised ETA. 37 deliveries have an unknown outcome and 9 were excluded for contradictory timestamps. Definition owned by VP Operations (pending)."

**Before it can be published without caveats:**
1. VP Operations signs the definition.
2. Fleet Ops fixes or approves the back-fill of the missing delivery times.
3. The ETA service explains the fixed −10 / −5 minute offsets.""")],
    })


# ============================================================================ Class 7 — Challenge
def class7_challenge():
    return weave("FlashEats_Class7_Challenge", replace={1: [code(SETUP)]}, after={
        4: [code(r'''
# Build the timeline from EVERY source (not only the orders table) and sort by time
pages = sorted(max((ROOT / "data" / "raw").glob("run_*/api"), key=lambda p: p.stat().st_mtime).glob("dispatch_page_*.json"))
dispatch = pd.DataFrame([r for p in pages for r in json.loads(p.read_text())["payload"]["data"]])     # retrieved + preserved by the pipeline
with open(BASE / "data" / "driver_events.json") as f:
    dev = pd.DataFrame([{"driver_id": d["driver_id"], **e} for d in json.load(f) for e in d["events"]])
rstat = pd.read_csv(BASE / "data" / "restaurant_status.csv")
T = lambda s: pd.to_datetime(s, format="mixed", errors="coerce")

def build_order_timeline(order_id):
    ev = []
    o = base_orders[base_orders.order_id == order_id].iloc[0]
    for col, et in [("created_at", "ORDER_CREATED"), ("pickup_at", "PICKED_UP"), ("actual_delivery_at", "DELIVERED")]:
        ev.append((o[col], et, "customer" if et == "ORDER_CREATED" else "driver", "orders DB"))
    d = dispatch[dispatch.order_id == order_id]
    for _, r in d.iterrows():
        ev += [(r.assigned_at, "DRIVER_ASSIGNED " + str(r.original_driver_id), "dispatch", "Dispatch API"),
               (r.estimated_pickup_at, "PICKUP_ESTIMATED", "dispatch", "Dispatch API"), (r.reassigned_at, "DRIVER_REASSIGNED " + str(r.driver_id), "dispatch", "Dispatch API")]
    ev += [(r.timestamp, "DRIVER_APP_" + r.type.upper(), "driver " + r.driver_id, "driver app") for r in dev[dev.order_id == order_id].itertuples()]
    ev += [(r.last_updated_at, "RESTAURANT_" + r.status.strip().upper(), "restaurant", "restaurant feed") for r in rstat[rstat.order_id == order_id].itertuples()]
    ev += [(r.action_at, "APP_" + r.action_type, "customer", "customer app") for r in customer_actions[customer_actions.order_id == order_id].itertuples()]
    ev += [(r.created_at, "SUPPORT_TICKET " + r.category.strip(), "customer", "support desk") for r in tickets[tickets.order_id == order_id].itertuples()]
    ev += [(r.intervention_at, "INTERVENTION_" + r.intervention_type, r.initiated_by, "interventions log") for r in interventions[interventions.order_id == order_id].itertuples()]
    t = pd.DataFrame(ev, columns=["event_time", "event_type", "actor", "source_system"])
    t["event_time"] = T(t.event_time)
    return t.dropna(subset=["event_time"]).sort_values("event_time").reset_index(drop=True)

promised = base_orders.set_index("order_id").promised_eta
for label, oid in [("ON TIME", on_time_order), ("LATE", late_order), ("WITH INTERVENTION", intervention_order)]:
    print(f"=== {label}: {oid} | promised {promised[oid]}"); display(build_order_timeline(oid))
'''), answer("""
- **Where the time goes:** the gap between `DRIVER_ASSIGNED` and `PICKED_UP` is where the time is lost, and nothing records what happens inside it. There is no arrival event, so the time spent waiting at the restaurant and the ride there form one block.
- **Late order O00001:** the customer opened support at 14:20, before the 14:11 promise was broken, and the reassignment intervention came during the pre-pickup gap.
- **Two systems disagree on who delivered:** after a reassignment, the orders DB and Dispatch name different drivers.
- **Pipeline cross-check:** the pipeline builds the same lifecycle for all 1600 orders (`data/processed/fact_event.csv`, 21 518 events from 7 systems).""")],
        6: [answer("""
| Table (pipeline) | Grain: one row per… | Primary key | Foreign keys | Supports |
|---|---|---|---|---|
| `dim_customer` | customer | `customer_id` | — | customer → orders |
| `fact_order` | order | `order_id` | customer, restaurant, driver (**final, from Dispatch**) | order → outcome, stage durations, dq flags, KPI population |
| `fact_event` | lifecycle event | (order, time, type, source) | `order_id` | order → events and states |
| `fact_interaction` | app action or ticket | `interaction_id` | `order_id`, `customer_id` | order → customer and support interactions |
| `fact_intervention` | intervention | `intervention_id` | `order_id` | order → interventions |
| `order_journey` | order | `order_id` | as `fact_order` | interaction → intervention → outcome in one row |

**Why not mirror every source table?**
- The sources disagree on grain (1603 vs 1600 orders), on spelling, and even on the driver.
- The model is organised around the workflow the KPI lives in. One-to-many tables are aggregated *before* joining, so the order count cannot inflate.
- Every business question becomes one filter on `order_journey`.

Diagrams: `docs/data-model.md`.""")],
        8: [code(r'''
flags = customer_actions.groupby("order_id").agg(support_opened=("action_type", lambda s: (s == "SUPPORT_OPENED").any()),
                                                  cancel_attempted=("action_type", lambda s: (s == "CANCEL_ATTEMPTED").any()),
                                                  eta_views=("action_type", lambda s: int((s == "ETA_VIEWED").sum())))
tk = tickets.dropna(subset=["order_id"]).drop_duplicates().groupby("order_id").size().rename("tickets")
iv = interventions.groupby("order_id").agg(intervention_count=("intervention_id", "count"), intervention_types=("intervention_type", lambda s: ";".join(sorted(set(s)))))
journey = (base_orders[["order_id", "customer_id", "final_status"]]
           .merge(flags, on="order_id", how="left").merge(tk, on="order_id", how="left").merge(iv, on="order_id", how="left")
           .merge(outcomes[["order_id", "late_flag", "delay_min"]], on="order_id", how="left"))
assert len(journey) == base_orders.order_id.nunique(), "aggregate BEFORE joining - the order count must not change"
journey = journey.fillna({"support_opened": False, "cancel_attempted": False, "eta_views": 0, "tickets": 0, "intervention_count": 0, "intervention_types": ""})
journey["support_interaction"] = journey.support_opened.astype(bool) | (journey.tickets > 0)
display(journey.head())
late = journey[journey.late_flag == 1]
print("1. late orders with a support interaction:", int(late.support_interaction.sum()), "of", len(late))
print("2. orders that received an intervention:", int((journey.intervention_count > 0).sum()))
print("3. most common intervention:", interventions.intervention_type.value_counts().head(1).to_dict())
frus = journey[journey.support_interaction & (journey.intervention_count == 0)]
print("4. frustrated journeys with no intervention:", len(frus), "| of which late:", int((frus.late_flag == 1).sum()))
display(frus.sort_values("delay_min", ascending=False).head(5)[["order_id", "support_opened", "tickets", "delay_min"]])
oj = pd.read_csv(ROOT / "data" / "processed" / "order_journey.csv")
print("reconciliation with the pipeline's order_journey: rows", len(oj), "vs", len(journey),
      "| orders with intervention", int((oj.intervention_count > 0).sum()), "vs", int((journey.intervention_count > 0).sum()))
'''), answer("""
- **Late orders with a support interaction: 258 of 843.** This uses the client's `order_outcomes` file. The pipeline's validated population gives 257 of 837, and the small difference is the 9 chronology-rule orders.
- **Orders that received an intervention: 430.**
- **Most common intervention:** `DRIVER_REASSIGNMENT`, with 155.
- **Frustrated journeys with no intervention: 218**, most of them late. These are the ops team's clearest missed opportunities.
- **Reconciliation:** the notebook table and the pipeline's `order_journey` agree on both row count and intervention count.""")],
        10: [code(r'''
v = journey[journey.late_flag.notna()]
m = pd.DataFrame([
    ("M1 late delivery rate", "outcome", round(100 * v.late_flag.mean(), 2), "late / delivered-with-time"),
    ("M2 median lateness (late orders)", "outcome", round(v[v.late_flag == 1].delay_min.median(), 1), "min"),
    ("M4 support contact rate on late orders", "interaction", round(100 * v[v.late_flag == 1].support_interaction.mean(), 1), "% of late orders"),
    ("M4a support contact rate on on-time orders", "interaction", round(100 * v[v.late_flag == 0].support_interaction.mean(), 1), "baseline"),
    ("M5 intervention coverage", "intervention", round(100 * (v.intervention_count > 0).mean(), 1), "% of delivered orders"),
], columns=["metric", "type", "value", "unit"])
display(m)
display(pd.read_csv(ROOT / "output" / "metrics.csv")[["metric_id", "metric", "category", "value", "unit"]].head(18))
'''), answer("""
| # | Metric | Formula | Grain | Why it matters | Link to the KPI |
|---|---|---|---|---|---|
| M1 | Late delivery rate (**outcome**) | late / validated deliveries | order | the KPI itself | direct |
| M2 | Lateness severity (**outcome**) | median delay of late orders; P90 | order | many small misses or a few disasters? | severity |
| M3 | Share of lateness before pickup (**workflow**) | pre-pickup overrun / all stage overrun | order → stage | tells ops *where* to act | the driver of the KPI |
| M4 | Support contact rate on late orders (**interaction**) | late with ticket or SUPPORT_OPENED / late | order | the customer impact | consequence of the KPI |
| M5 | Intervention coverage and late rate with / without (**intervention**) | intervened / orders | order | does ops reach the right orders? | the lever |""")],
        12: [code(r'''
def rate(d): return round(100 * (d.late_flag == 1).mean(), 1) if len(d) else None
print("A. median delay with / without a support interaction:", v[v.support_interaction].delay_min.median(), "/", v[~v.support_interaction].delay_min.median(),
      "| late rate:", rate(v[v.support_interaction]), "/", rate(v[~v.support_interaction]))
print("B. late rate with / without an intervention:", rate(v[v.intervention_count > 0]), "/", rate(v[v.intervention_count == 0]))
c = interventions.merge(v[["order_id", "late_flag"]], on="order_id").groupby("intervention_type").late_flag.agg(orders="size", late_rate=lambda s: round(100 * s.mean(), 1))
print("C. late rate by intervention type:"); display(c.sort_values("late_rate"))
fr = pd.read_csv(ROOT / "output" / "insights" / "fair_ranking_restaurants.csv")
print("D. restaurants by late orders, with 95% Wilson intervals (beyond the class):")
display(fr.sort_values("late_orders", ascending=False).head(8)[["restaurant_id", "orders", "late_orders", "late_rate_pct", "ci_low_pct", "ci_high_pct", "verdict"]])
e = v[v.support_interaction & (v.intervention_count > 0) & (v.late_flag == 1)]
print("E. support + intervention + still late:", len(e)); display(e.sort_values("delay_min", ascending=False).head(5)[["order_id", "intervention_types", "delay_min"]])
'''), answer("""
- **A.** Orders with a support interaction are far more often late: 88 % against 49 %. *Tells:* complaints are a reliable lagging signal. *Does not prove:* that support contact causes delay; the delay causes the contact.
- **B.** The late rate is about 56 % with or without an intervention. *Tells:* interventions are not associated with a lower late rate. *Does not prove:* that they are useless. They target at-risk orders, a selection effect, and the interventions log does not reconcile with Dispatch.
- **C.** `PRIORITY_DISPATCH` has the lowest late rate, about 51 %, and `CUSTOMER_CREDIT` the highest, about 67 %. *Tells:* credits are handed out after a failure. *Does not prove:* which action works, because each type has a different trigger.
- **D.** The naive "most late orders" list names ten restaurants, but only **R024** is statistically worse than the fleet. *Tells:* lateness is systemic. *Does not prove:* kitchen fault, because preparation time is not observed.
- **E.** 67 journeys had a support interaction and an intervention and were still late (66 on the pipeline's validated population). *Tells:* the recovery loop acts too late or too weakly. *Does not prove:* that earlier action would have saved them. The pipeline's early-warning backtest tests exactly that timing question.""")],
        13: [answer("""
```
PROJECT KPI        reduce late delivery rate (M1)
  ↑ OUTCOMES       M1 late rate · M2 severity · M4 customer contact
  ↑ WORKFLOW       M3 pre-pickup overrun share · dispatch wait · assign→pickup · transit · Dispatch pickup-estimate bias
  ↑ INTERVENTIONS  M5 coverage and type · NEW: pickup-overrun trigger (alert at estimated pickup + k min)
  ↑ SOURCES/EVENTS orders DB · Dispatch API · driver app · restaurant feed · customer app · support desk · interventions log · Open-Meteo (external check)
```
1. **Controllable by operations:** dispatch wait, intervention coverage and timing (M5), which orders receive an intervention, and the pickup estimate behind the promise.
2. **Outcomes:** M1, M2 and M4.
3. **The missing event that limits the model most:** *driver arrived at restaurant*. It cannot be inferred from GPS either (see the Class 5 Starter).
4. **Instrument next:** an arrival tap, a mandatory delivery timestamp, reassignment written back to the orders table, a cancellation timestamp, and the provenance of `weather_bucket`.

**Beyond the class, what ops can do on Monday:** the pipeline backtested a transparent trigger, *"not picked up 10 minutes after Dispatch's own estimate"*. It was chosen on 1–21 August and proven on 22–28 August, where it reached **96 % precision and 72 % recall, about 45 minutes before the promise breaks**. Today, 446 of the late orders it would have caught received no intervention at all. See `output/decision_memo.md`.

**Modelling limitation:** the pre-pickup stage is a black box until the arrival event exists.""")],
    })


# ============================================================================ pipeline walkthrough
def walkthrough():
    cells = [md("""
# FlashEats pipeline — guided walkthrough

The same code as `python run_pipeline.py`, run **stage by stage** so each FDE decision is visible with its evidence:

`policy file → ingest (SQL · API · CSV · JSON · external weather) → raw preservation → profile → clean → business rules → workflow model → metrics → decision layer → gate`

It writes to `notebooks/walkthrough_run/` so it never overwrites the published evidence in `output/`.
"""), code(r'''
import sys, json, time
from pathlib import Path
import pandas as pd
ROOT = Path.cwd()
while not (ROOT / "source_systems").exists() and ROOT.parent != ROOT:
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
from flasheats_pipeline.config import load_config
from flasheats_pipeline.logging_utils import configure_logging
from flasheats_pipeline.ingest import SqlSource, DispatchApiClient, ObservedWeatherClient, read_csv_source, read_json_source, flatten_driver_events
from flasheats_pipeline.pipeline import FILE_SOURCES, MockApiProcess
from flasheats_pipeline.profiling import profile_all
from flasheats_pipeline.cleaning import standardise
from flasheats_pipeline.rules import run_rules, results_frame
from flasheats_pipeline.model import build_model
from flasheats_pipeline.metrics import compute_metrics
from flasheats_pipeline.insights import compute_insights
from flasheats_pipeline.monitoring import build_ledger
from flasheats_pipeline.gate import build_gate
pd.set_option("display.max_columns", 60); pd.set_option("display.width", 170); pd.set_option("display.max_colwidth", 80)
work = ROOT / "notebooks" / "walkthrough_run"
cfg = load_config(ROOT / "config" / "pipeline.yaml", run_id="walkthrough", data_dir=work / "data", output_dir=work / "output")
configure_logging(None)
print("policy file:", cfg.config_file)
print({k: getattr(cfg, k) for k in ["late_threshold_min", "meaningful_late_threshold_min", "status_freshness_sla_min", "ew_min_precision", "target_on_time_rate_pct"]})
'''), md("""
## 1 · Ingest — four client systems and one independent source
Each retrieval preserves its raw input under `walkthrough_run/data/raw/walkthrough/` with a SHA-256.
"""), code(r'''
raw, ingestion = {}, {}
sql = SqlSource(cfg.db_path, cfg.sql_dir, cfg.raw_dir)
for name, table in [("orders_extract", "orders"), ("restaurants_extract", "restaurants"), ("drivers_extract", "drivers"), ("customers_extract", "customers")]:
    raw[table] = sql.extract(name, table, {"start_at": None, "end_at": None} if table == "orders" else None)
for name, (fname, required, optional) in FILE_SOURCES.items():
    raw[name], _ = read_csv_source(cfg.files_dir / fname, name, required, cfg.raw_dir)
obj, res = read_json_source(cfg.files_dir / "driver_events.json", "driver_events", cfg.raw_dir)
raw["driver_events"] = flatten_driver_events(obj, res)
with MockApiProcess(cfg.mock_api_script, cfg.api_base_url):
    records, api_report = DispatchApiClient(cfg.api_base_url, cfg.raw_dir, page_size=cfg.api_page_size, backoff_base_s=0.2).fetch_all()
raw["dispatch"] = pd.DataFrame(records, dtype="object")
ingestion["dispatch_api"] = api_report.as_dict()
wx, wrep = ObservedWeatherClient(cfg.weather_base_url, cfg.weather_latitude, cfg.weather_longitude, cfg.source_timezone, cfg.raw_dir,
                                 cache_dir=ROOT / "data" / "external").fetch("2026-08-01", "2026-08-29")
ingestion["external_weather"] = wrep.as_dict()
if wx is not None:
    raw["weather_obs"] = wx
print(f"API complete={api_report.complete} records={api_report.records_fetched}/{api_report.expected_total} pages={api_report.pages_fetched} retries={api_report.retries}")
print(f"weather mode={wrep.mode} hours={wrep.hours}")
display(pd.DataFrame({k: [len(v)] for k, v in raw.items()}, index=["rows"]).T)
'''), md("## 2 · Profile before cleaning"), code(r'''
ref = raw.pop("order_outcomes_ref")
profiles = profile_all({k: (v, {"orders": "order_id", "tickets": "ticket_id", "dispatch": "order_id"}.get(k)) for k, v in raw.items()})
display(pd.DataFrame([{"dataset": p.name, "rows": p.rows, "duplicate_key_rows": p.duplicate_key_rows, "exact_duplicates": p.exact_duplicate_rows, "notes": "; ".join(p.notes)[:120]} for p in profiles]))
'''), md("## 3 · Clean — representation only, every change logged, nothing silently lost"), code(r'''
clean, rep = standardise(raw, cfg)
display(rep.actions_frame())
print("unexpected categories kept + flagged:", rep.unexpected_categories)
ledger, ledger_checks = build_ledger(rep)
display(ledger)
'''), md("## 4 · Business rules (validation contract)"), code(r'''
results = run_rules(clean, rep, cfg, json.loads((cfg.files_dir / "client_metric_definitions.json").read_text()))
rf = results_frame(results)
display(rf[rf.status != "PASS"][["rule_id", "rule", "status", "violations", "population", "action", "owner"]])
'''), md("## 5 · Workflow model and 6 · metrics"), code(r'''
model = build_model(clean, results, cfg)
display(pd.DataFrame(model.join_checks))
mr = compute_metrics(model, cfg, reference_outcomes=ref)
display(mr.metrics[["metric_id", "metric", "value", "unit", "numerator", "denominator"]])
display(mr.breakdowns["stage_durations_by_outcome"])
'''), md("## 7 · Decision layer — what the client can do now"), code(r'''
ins = compute_insights(model, clean, mr.metrics, cfg)
for f in ins.findings:
    print(f"{f['id']} {f['title']}\n   {f['finding']}\n   → {f['so_what']}  [{f['owner']}]\n")
display(ins.tables["early_warning_backtest"].query("split == 'test'"))
'''), code(r'''
import matplotlib.pyplot as plt
t = ins.tables["early_warning_backtest"].query("split == 'test'")
fig, ax = plt.subplots(1, 2, figsize=(12, 3.6))
ax[0].plot(t.grace_min, t.precision_pct, marker="o", label="precision"); ax[0].plot(t.grace_min, t.recall_pct, marker="o", label="recall")
ax[0].axvline(ins.headline["early_warning"]["chosen_grace_min"], ls=":", c="g"); ax[0].set_title("Early-warning trigger (held-out week)"); ax[0].legend()
e = ins.tables["eta_calibration"].query("eta_model_version == 'all versions'")
ax[1].plot(e.padding_min, e.late_rate_pct, marker="o"); ax[1].axhline(100 - cfg.target_on_time_rate_pct, ls=":", c="g"); ax[1].set_title("Late rate if every promise were padded")
plt.tight_layout(); plt.show()
'''), md("## 8 · The gate — publish or not?"), code(r'''
mr.checks.extend(ledger_checks)
gate = build_gate(ingestion, results, mr, cfg)
display(pd.DataFrame(gate["checks"])[["check", "status", "evidence"]])
print(gate["overall_status"], "->", gate["publish_decision"])
''')]
    nb = nbf.v4.new_notebook()
    nb.cells = cells
    nb.metadata = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}
    return nb


def _local_kernelspec() -> str:
    """Kernel spec for the current interpreter, kept inside the repository (no user-profile side effects)."""
    kdir = ROOT / ".jupyter" / "kernels" / "flasheats-local"
    kdir.mkdir(parents=True, exist_ok=True)
    (kdir / "kernel.json").write_text(json.dumps({"argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
                                                  "display_name": "Python (flasheats pipeline)", "language": "python"}, indent=1), encoding="utf-8")
    os.environ["JUPYTER_PATH"] = str(ROOT / ".jupyter") + os.pathsep + os.environ.get("JUPYTER_PATH", "")
    return "flasheats-local"


def build(exec_: bool, kernel: str | None, only: list[str] | None = None):
    kernel_name = kernel or (_local_kernelspec() if exec_ else "python3")
    CHALLENGES.mkdir(exist_ok=True)
    targets = [(CHALLENGES / "FlashEats_Class5_Starter.ipynb", class5_starter), (CHALLENGES / "FlashEats_Class5_Student.ipynb", class5_student),
               (CHALLENGES / "FlashEats_Class6_Student.ipynb", class6_student), (CHALLENGES / "FlashEats_Class7_Challenge.ipynb", class7_challenge),
               (HERE / "pipeline_walkthrough.ipynb", walkthrough)]
    for path, fn in targets:
        if only and path.stem not in only:
            continue
        nb = fn()
        if exec_:
            from nbclient import NotebookClient
            NotebookClient(nb, timeout=900, kernel_name=kernel_name, resources={"metadata": {"path": str(path.parent)}}, allow_errors=False).execute()
        nbf.write(nb, path)
        print(("executed" if exec_ else "wrote"), path.relative_to(ROOT), "cells:", len(nb.cells))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-exec", action="store_true")
    ap.add_argument("--kernel", default=None)
    ap.add_argument("--only", nargs="*", help="notebook stems to build, e.g. FlashEats_Class6_Student")
    a = ap.parse_args()
    build(not a.no_exec, a.kernel, a.only)

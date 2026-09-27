"""Generate and execute the Session 5 / 6 / 7 challenge notebooks.

    python notebooks/build_notebooks.py            # build + execute (needs the pipeline outputs, see README)
    python notebooks/build_notebooks.py --no-exec  # build only

The notebooks follow the instructor's challenge structure cell by cell, use the
same SQL/pandas idioms shown in class, and lean on ``flasheats_pipeline`` where
the logic already exists in the pipeline (so notebook and pipeline never drift).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import nbformat as nbf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

SETUP = '''# --- setup: locate the repository root and load the pipeline package -------------
import sys, json, sqlite3, subprocess, time
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path.cwd()
while not (ROOT / "source_systems").exists() and ROOT.parent != ROOT:
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
BASE = ROOT / "source_systems"            # the client systems snapshot (read-only)
NB_OUT = ROOT / "notebooks" / "output"      # scratch outputs of this notebook
NB_OUT.mkdir(parents=True, exist_ok=True)
pd.set_option("display.max_columns", 60); pd.set_option("display.width", 160); pd.set_option("display.max_colwidth", 90)
print("ROOT:", ROOT, "| pack exists:", (BASE / "database" / "flasheats.db").exists())
'''


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip("\n"))


def code(text: str):
    return nbf.v4.new_code_cell(text.strip("\n"))


# ============================================================================ SESSION 5
def session5():
    cells = [md("""
# FlashEats — Session 5 challenges: fetching data with SQL, APIs and files

**Client escalation:** *"Late deliveries are increasing and customers say our ETA is unreliable. Figure out what is happening before we invest in an AI delay-prediction system."*

Workflow: **define the question → retrieve evidence → validate completeness → reconcile sources → state what you know and what you still cannot know.**

Rules followed: no ML model; the definition of *late* is stated before it is calculated; raw API responses are preserved; failures are never silently dropped; when numbers differ, the definition and grain are investigated first.

This notebook reproduces every Class 5 challenge on the classroom pack. The same logic is productionised in `src/flasheats_pipeline/` (see `docs/session-5-challenges.md` for the mapping).
"""), code(SETUP), md("""
## Source map first — where would you look?

| Information | Likely source | Authoritative? | Why |
|---|---|---|---|
| Promised delivery time | `orders.promised_eta` (SQLite) | **Yes** — the promise the customer saw | Dispatch's `current_delivery_eta` is a later revision, not the promise |
| Actual delivery time | `orders.actual_delivery_at` (SQLite) | **Yes**, but 37 delivered orders have none | Driver app `delivered` event exists for those 37 → candidate back-fill, needs owner sign-off |
| Driver assignment / reassignment | Dispatch API (`assigned_at`, `reassigned_at`, `driver_id`, `original_driver_id`) | **Yes** for the final driver | `orders.driver_id` keeps the *original* driver after reassignment |
| Customer complaint | `support_tickets.csv` | Yes for *what the customer said* | Contextual for what actually happened |
| Restaurant status | `restaurant_status.csv` | Contextual | Covers ~31% of orders, minute precision, mixed spellings |
| Driver movement | `driver_events.json` (GPS pings, assigned / picked_up / delivered) | Yes for movement | No explicit *arrived at restaurant* event |
"""), code('''
# 3. BASIC SYNTAX — read every source (SQLite, CSV, nested JSON)
con = sqlite3.connect(f"file:{(BASE / 'database' / 'flasheats.db').as_posix()}?mode=ro", uri=True)   # read-only
tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;", con)
display(tables)
display(pd.read_sql("SELECT * FROM orders LIMIT 5;", con))

tickets = pd.read_csv(BASE / "data" / "support_tickets.csv")
restaurant_status = pd.read_csv(BASE / "data" / "restaurant_status.csv")
display(tickets.head())

with open(BASE / "data" / "driver_events.json", "r") as f:
    driver_events = json.load(f)
print("Driver objects:", len(driver_events), "| first driver:", driver_events[0]["driver_id"], "| events:", len(driver_events[0]["events"]))
'''), md("""
# Challenge 1 — How large is the late-delivery problem?

Decided **before** coding:

- **Late means:** `actual_delivery_at − promised_eta > 0 minutes` (the promise the customer saw is the yardstick; Dispatch's revised ETA is not).
- **Denominator:** orders that were actually delivered **and** have both timestamps (a delivered order without a delivery time has an *unknown* outcome, it is not on-time).
- **Cancelled orders:** excluded — there is no delivery to be late.
- **Missing actual delivery timestamp:** excluded from the denominator, counted and reported as a data-quality issue (37 orders); driver-app `delivered` events exist for them → back-fill is possible but is an owner decision, reported only as a sensitivity.
- **Row grain:** one row = one order **after** de-duplication (the raw table has 1603 rows for 1600 orders).
"""), code('''
# SQL first: retrieve only the rows/columns needed, and let SQL show the grain problem
q = """
SELECT order_id, created_at, promised_eta, pickup_at, actual_delivery_at, final_status, distance_km_estimate, traffic_bucket, weather_bucket
FROM orders
"""
orders = pd.read_sql(q, con)
print("Raw rows:", len(orders), "| unique orders:", orders["order_id"].nunique(), "| extra duplicate rows:", len(orders) - orders["order_id"].nunique())
print(pd.read_sql("SELECT final_status, COUNT(*) AS n FROM orders GROUP BY final_status", con).to_string(index=False))

# The 3 duplicated orders do not agree with themselves (traffic_bucket differs) — keep first, report the conflict
dups = orders[orders["order_id"].duplicated(keep=False)].sort_values("order_id")
display(dups[["order_id", "created_at", "final_status", "traffic_bucket"]])
'''), code('''
order_analysis = orders.drop_duplicates("order_id", keep="first").copy()
order_analysis["final_status"] = order_analysis["final_status"].str.strip().str.lower()      # 'Delivered' is representation, not a new status
order_analysis["traffic_bucket"] = order_analysis["traffic_bucket"].str.strip().str.lower()  # 'HIGH' likewise
for c in ["created_at", "promised_eta", "pickup_at", "actual_delivery_at"]:
    order_analysis[c] = pd.to_datetime(order_analysis[c], format="mixed", errors="coerce")

cancelled = (order_analysis["final_status"] == "cancelled").sum()
missing_actual = ((order_analysis["final_status"] == "delivered") & order_analysis["actual_delivery_at"].isna()).sum()
bad_promise = (order_analysis["promised_eta"] < order_analysis["created_at"]).sum()
bad_delivery = (order_analysis["actual_delivery_at"] < order_analysis["pickup_at"]).sum()

valid = order_analysis[(order_analysis["final_status"] == "delivered") & order_analysis["actual_delivery_at"].notna() & order_analysis["promised_eta"].notna()].copy()
valid["delay_min"] = (valid["actual_delivery_at"] - valid["promised_eta"]).dt.total_seconds() / 60
late = valid[valid["delay_min"] > 0]

print(f"Cancelled: {cancelled} | delivered with missing actual timestamp: {missing_actual} | promised<created: {bad_promise} | delivered<pickup: {bad_delivery}")
print(f"Valid delivered: {len(valid)} | late: {len(late)} | late %: {100*len(late)/len(valid):.1f} | median lateness (late only): {late['delay_min'].median():.1f} min")
print("Worst delayed orders:")
display(late.sort_values("delay_min", ascending=False)[["order_id", "promised_eta", "actual_delivery_at", "delay_min", "traffic_bucket", "weather_bucket"]].head(10))
'''), md("""
**Result (class definition):** 843 of 1495 valid delivered orders are late → **56.4 %**, median lateness among late orders **8.0 min** (the Class 5 solution printed 7.9 min on the pre-Class-6 pack; the injected anomalies moved nine orders).

**Look at the "worst delayed" list before believing it:** the four largest delays (+85 to +87 min, O00101–O00104) are exactly the four orders whose *promised ETA is 10 minutes before the order was created*. They are a data bug, not a delivery. The worst **genuine** delay is **O01081 at +50.3 min**. This is why the pipeline excludes chronology violators from the validated population.

**Data-quality issues that change the metric** (all surfaced, none silently fixed):
1. 3 duplicate order rows that *disagree on traffic_bucket* → grain fixed, conflict recorded;
2. 68 cancelled orders → excluded (no delivery to judge);
3. 37 delivered orders without `actual_delivery_at` → unknown outcome; if they were all late the rate would be 57.4 %, if all on time 55.0 % — the number is bounded, not exact;
4. 9 chronology violations (4 promises before creation, 5 deliveries before pickup) → the pipeline excludes them from the *validated* population (56.33 %, 837/1486); the class definition keeps them (56.39 %). Both are reported side by side.
"""), md("""
# Challenge 2 — Operations says "traffic is the problem"

Tested on four dimensions: traffic, weather, distance and hour of day. Association ≠ causation.
"""), code('''
def summarise(df, by):
    g = df.groupby(by, observed=True)["delay_min"].agg(count="count", median="median", mean="mean").round(1)
    g["late_rate_%"] = (df.assign(l=df["delay_min"] > 0).groupby(by, observed=True)["l"].mean() * 100).round(1)
    return g

traffic_summary = summarise(valid, "traffic_bucket")
weather_summary = summarise(valid, "weather_bucket")
distance_band = pd.cut(valid["distance_km_estimate"], bins=[0, 3, 6, 10, 20, 50], include_lowest=True)
distance_summary = summarise(valid.assign(distance_band=distance_band), "distance_band")
hour_summary = summarise(valid.assign(hour=valid["created_at"].dt.hour), "hour")
display(traffic_summary); display(weather_summary); display(distance_summary); display(hour_summary)

fig, axes = plt.subplots(1, 2, figsize=(11, 3.6))
traffic_summary["median"].plot(kind="bar", ax=axes[0], title="Median delay by traffic bucket", ylabel="minutes")
weather_summary["median"].plot(kind="bar", ax=axes[1], title="Median delay by weather", ylabel="minutes", color="tab:orange")
plt.tight_layout(); plt.savefig(NB_OUT / "s5_ch2_traffic_weather.png", dpi=110); plt.show()
'''), md("""
**Hypothesis supported by evidence:** lateness is associated with traffic (median delay −0.1 min at *low* vs +4.3 min at *severe*; late rate 49 % → 66 %) and with weather (clear +0.8 min vs heavy rain +6.6 min; late rate 53 % → 74 %). (The three `HIGH` rows were normalised into `high` before grouping — otherwise they show up as a fifth, misleading bucket.)

**Alternative explanation we cannot rule out:** traffic and weather are *buckets attached to the order*, not measured on the route; evening peaks (18:00–19:00 have the most orders and 62 % late) mean restaurant load and driver scarcity move together with traffic — the data cannot separate "roads were slow" from "the kitchen was slow". Distance shows **no** monotonic relationship (10–20 km orders have the same median delay as 6–10 km), so "long trips" is not the story either.
"""), md("""
# Challenge 3 — Customer Support disagrees

What are customers complaining about, are ticket ids unique, and does the customer story match the operational story?
"""), code('''
print("Ticket rows:", len(tickets), "| unique ticket ids:", tickets["ticket_id"].nunique(), "| duplicate ticket ids:", tickets["ticket_id"].duplicated().sum())
print("Tickets with no order id:", tickets["order_id"].isna().sum())
print("Raw categories (note casing/whitespace variants):", sorted(tickets["category"].unique()))
tickets_clean = tickets.drop_duplicates().copy()
tickets_clean["category_norm"] = tickets_clean["category"].str.strip().str.lower().str.replace(r"[\\s-]+", "_", regex=True)
display(tickets_clean["category_norm"].value_counts())

# LEFT merge: tickets are the base table; we want the operational facts for every complaint
tickets_with_delay = tickets_clean.merge(valid[["order_id", "delay_min", "traffic_bucket", "weather_bucket"]], on="order_id", how="left")
assert len(tickets_with_delay) == len(tickets_clean), "join inflated the ticket count"
view = tickets_with_delay.groupby("category_norm")["delay_min"].agg(tickets="size", matched="count", median_delay="median", mean_delay="mean").round(1)
view["late_share_%"] = (tickets_with_delay.assign(l=tickets_with_delay["delay_min"] > 0).groupby("category_norm")["l"].mean() * 100).round(1)
display(view.sort_values("tickets", ascending=False))
'''), md("""
**System view vs customer view**

| | Customer view (tickets) | System view (orders table) |
|---|---|---|
| Most common complaint | `late_delivery` (39) then `eta_changed` / `restaurant_delay` (37 each) | 56 % of *all* deliveries are late, so a complaint is the exception, not the rule |
| Are complaints justified? | — | Orders with a `late_delivery` ticket have a median delay of **14.8 min** vs 1.4 min overall; 87 % of them were in fact late |
| `ready_but_waiting` / `status_mismatch` | Customer sees the restaurant say *ready* while the app says *picking up* | 91–93 % of those orders were late: the driver-at-restaurant gap is real but **no arrival event exists** to measure it |
| Ticket hygiene | 1 duplicated ticket id, 3 tickets without an order id, 3 spelling variants of the category | The support system is not the canonical event log — it tells us *how the delay felt*, not *where it happened* |

**What tickets tell you that timestamps cannot:** the customer's perception of the cause (restaurant vs rider vs ETA logic) and the moment the customer lost patience — signals no operational timestamp carries.
"""), md("""
# Challenge 4 — Dispatch API: prove you retrieved everything

Start the mock API, inspect one response, retrieve **all** pages with retries, preserve every raw page and prove completeness. A 200 on one page proves nothing.
"""), code('''
import requests
from flasheats_pipeline.ingest.api_source import DispatchApiClient

API = "http://127.0.0.1:8000"
api_proc = None
try:
    requests.get(f"{API}/health", timeout=2).raise_for_status()
    print("API already running")
except Exception:
    api_proc = subprocess.Popen([sys.executable, str(BASE / "api" / "mock_dispatch_api.py")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        time.sleep(0.25)
        try:
            if requests.get(f"{API}/health", timeout=2).ok:
                break
        except Exception:
            pass
print("health:", requests.get(f"{API}/health", timeout=5).json())

# one response, inspected
r = requests.get(f"{API}/dispatch/orders", params={"page": 1, "page_size": 50}, timeout=10)
payload = r.json()
print("HTTP:", r.status_code, "| keys:", list(payload), "| records on page:", len(payload["data"]), "| has_more:", payload["has_more"], "| total:", payload["total_records"])
'''), code('''
# reliable paginated ingestion (the same client the pipeline uses): retries 429/500, honours Retry-After, saves every raw page
client = DispatchApiClient(API, NB_OUT / "raw_dispatch", page_size=100, max_retries=4, backoff_base_s=0.2)
records, report = client.fetch_all()
print(json.dumps({k: report.as_dict()[k] for k in ["pages_fetched", "records_fetched", "unique_order_ids", "expected_total", "retries", "http_errors", "complete", "issues"]}, indent=1))
assert report.complete, "refuse to claim success when ingestion is incomplete"

dispatch_df = pd.DataFrame(records)
print("Dispatch rows:", len(dispatch_df), "| unique orders:", dispatch_df["order_id"].nunique(), "| reassigned orders:", dispatch_df["reassigned_at"].notna().sum())
print("Raw pages preserved:", len(list((NB_OUT / "raw_dispatch" / "api").glob("dispatch_page_*.json"))))
display(dispatch_df.head())
'''), md("""
**Completeness proof:** 16 pages × 100 = **1600 records = server-reported `total_records`**, 1600 unique order ids, page 3 answered HTTP 500 and page 5 HTTP 429 on the first attempt — both were retried and the page re-fetched; every successful page is preserved as `notebooks/output/raw_dispatch/api/dispatch_page_NNN.json`. 95 orders carry a `reassigned_at`.

Cross-check with the orders table: `orders.driver_id` equals Dispatch's **original** driver for 1597 orders → the application database is **not updated after a reassignment**; Dispatch is authoritative for the final driver.
"""), md("""
# Challenge 5 — Can we attribute the delay?

Is there a reliable *driver arrived at restaurant* event? Observed = directly stored; inferred = estimated from another signal.
"""), code('''
flat_events = [{"driver_id": d["driver_id"], **e} for d in driver_events for e in d["events"]]
driver_events_df = pd.DataFrame(flat_events)
driver_events_df["timestamp"] = pd.to_datetime(driver_events_df["timestamp"], format="mixed", errors="coerce")
display(driver_events_df["type"].value_counts())
print("Explicit driver_arrived_at_restaurant events:", (driver_events_df["type"] == "arrived_at_restaurant").sum())

piv = driver_events_df[driver_events_df["type"].isin(["assigned", "picked_up", "delivered"])].groupby(["order_id", "type"])["timestamp"].min().unstack()
pings = driver_events_df[driver_events_df["type"] == "gps_ping"].merge(piv, left_on="order_id", right_index=True)
print("GPS pings before pickup:", (pings["timestamp"] <= pings["picked_up"]).sum(), "| after pickup:", (pings["timestamp"] > pings["picked_up"]).sum(),
      "| out-of-area pings (lat>13.5 or lon>78):", ((pings["lat"] > 13.5) | (pings["lon"] > 78)).sum())
print("Orders with picked_up before assigned:", (piv["picked_up"] < piv["assigned"]).sum())
print("Delivered orders in DB without actual_delivery_at that DO have a driver 'delivered' event:",
      order_analysis[(order_analysis["final_status"] == "delivered") & order_analysis["actual_delivery_at"].isna()]["order_id"].isin(piv[piv["delivered"].notna()].index).sum())
'''), md("""
| Event / fact | Observed? | Source | Reliability concern |
|---|---|---|---|
| Driver assigned | **Observed** | Dispatch API `assigned_at`; driver app `assigned` | Two sources agree; 14 orders show `picked_up` *before* `assigned` in the driver app |
| Driver at restaurant | **Not observed** — only *inferable* | GPS pings (≈1–5 per order, 189 out-of-area outliers) near the restaurant coordinates | No stored business event; two restaurants have impossible coordinates (lat 95, lon 190); geofencing would be an estimate, not a fact |
| Picked up | **Observed** | `orders.pickup_at`; driver app `picked_up` | Agree to the second for 1527 orders; 5 orders have delivery *before* pickup |
| Delivered | **Observed** | `orders.actual_delivery_at`; driver app `delivered` | 37 delivered orders lack the DB timestamp but have the driver event |

**Conclusion:** assignment, pickup and delivery are observed; **arrival at the restaurant is not**. Restaurant preparation time and the driver's wait cannot be separated, so "was it the kitchen or the rider?" cannot be answered with the current instrumentation.
"""), md("""
# Final FDE synthesis — one slide

1. **Problem size** — the data shows **56.4 % of 1 495 valid deliveries** arrive after the promised ETA (56.3 % on the validated population); median lateness 7.9 min, P90 delay ≈ 18 min, worst +50 min. The problem is real and large.
2. **Evidence** — lateness is associated with traffic and weather buckets and with evening peaks, not with distance. Almost all lateness accumulates **before pickup** (median pre-pickup overrun +14 min on late orders; transit is faster than planned).
3. **Trusted sources** — orders table for the promise and the delivery time; Dispatch for assignment/reassignment; driver app for movement; tickets for the customer's perception only.
4. **Uncertainty** — 37 unknown outcomes, 9 chronology violations, no restaurant-arrival event, `orders.driver_id` stale after reassignment, four competing definitions of "late" with no owner.
5. **Instrumentation recommendation** — capture *driver arrived at restaurant*, make the delivery timestamp mandatory on the `delivered` status transition, propagate reassignment into the orders table, and agree one written definition of *late* with an owner.
6. **Decision** — **do not build the AI delay predictor yet.** The model would learn from a promise that is sometimes made before the order exists, without the one event (arrival) that separates the two main causes. Fix instrumentation and the KPI definition first; the pipeline in this repository is the measurement baseline to judge any later model against.
"""), code('''
# cleanup
try:
    con.close()
except Exception:
    pass
if api_proc is not None:
    api_proc.terminate()
print("Session 5 notebook complete.")
''')]
    return cells


# ============================================================================ SESSION 6
def session6():
    cells = [md("""
# FlashEats — Session 6 challenges: data profiling and validation

Yesterday we proved we could **retrieve** the data. Today's question: **can we safely use it to make a business decision?**

Validation mindset: *business claim → assumptions → validation contract → targeted checks → stakeholder clarification → PASS / WARN / FAIL → publish decision.*

Leadership claim under review: **"Late Delivery Rate is 56 %."**
"""), code(SETUP), code('''
con = sqlite3.connect(f"file:{(BASE / 'database' / 'flasheats.db').as_posix()}?mode=ro", uri=True)
orders = pd.read_sql("SELECT * FROM orders", con)
restaurants = pd.read_sql("SELECT * FROM restaurants", con)
drivers = pd.read_sql("SELECT * FROM drivers", con)
customers = pd.read_sql("SELECT customer_id FROM customers", con)
tickets = pd.read_csv(BASE / "data" / "support_tickets.csv")
restaurant_status = pd.read_csv(BASE / "data" / "restaurant_status.csv")
with open(BASE / "data" / "client_metric_definitions.json") as f:
    metric_notes = json.load(f)
print("orders:", orders.shape, "| tickets:", tickets.shape, "| restaurant_status:", restaurant_status.shape)
print(json.dumps(metric_notes, indent=2))
'''), md("""
# Challenge 1 — Can we defend the "56 % late" claim?

Validation contract written **before** calculating anything:

| Business assumption | Data expectation | How it is tested | Severity if false |
|---|---|---|---|
| One row = one business order | `order_id` unique in `orders` | `len(orders)` vs `nunique()`; conflicting duplicates inspected | HIGH — denominator inflates |
| Delivered orders have a completion time | `final_status='delivered'` ⇒ `actual_delivery_at` not null | count nulls among delivered | HIGH — population silently shrinks, bias unknown |
| Promised ETA is valid | parseable and `promised_eta ≥ created_at` | `to_datetime(errors='coerce')`, chronology compare | HIGH — lateness against an invalid promise is meaningless |
| Event chronology is valid | `created ≤ pickup ≤ delivered` | pairwise compares | MEDIUM — stage metrics become negative |
| "Late" has an agreed definition | one owner, one formula | `client_metric_definitions.json` | HIGH — every team publishes a different number |
"""), code('''
o = orders.copy()
print("Rows:", len(o), "| unique orders:", o["order_id"].nunique(), "| conflicting duplicates:", o[o["order_id"].duplicated(keep=False)]["order_id"].nunique())
print(o["final_status"].value_counts(dropna=False).to_dict())
analysis = o.drop_duplicates("order_id", keep="first").copy()
analysis["final_status_norm"] = analysis["final_status"].str.strip().str.lower()
for c in ["created_at", "promised_eta", "pickup_at", "actual_delivery_at"]:
    analysis[c] = pd.to_datetime(analysis[c], format="mixed", errors="coerce")
checks = {
    "delivered without completion time": int(((analysis["final_status_norm"] == "delivered") & analysis["actual_delivery_at"].isna()).sum()),
    "promised_eta < created_at": int((analysis["promised_eta"] < analysis["created_at"]).sum()),
    "actual_delivery_at < pickup_at": int((analysis["actual_delivery_at"] < analysis["pickup_at"]).sum()),
    "pickup_at < created_at": int((analysis["pickup_at"] < analysis["created_at"]).sum()),
    "unparseable promised_eta": int((o.drop_duplicates("order_id")["promised_eta"].notna() & analysis["promised_eta"].isna()).sum()),
    "restaurant_id null": int(analysis["restaurant_id"].isna().sum()),
    "driver_id null": int(analysis["driver_id"].isna().sum()),
}
display(pd.Series(checks, name="violations"))
violators = analysis[(analysis["promised_eta"] < analysis["created_at"]) | (analysis["actual_delivery_at"] < analysis["pickup_at"])]
display(violators[["order_id", "created_at", "promised_eta", "pickup_at", "actual_delivery_at", "final_status"]])
'''), md("""
**Assumptions that need stakeholder clarification** (cannot be settled from the data):
- *Data Team:* why do 3 orders exist twice with different traffic buckets — two writers to the orders table?
- *Fleet Ops:* can the driver-app `delivered` event back-fill the 37 missing delivery timestamps?
- *ETA service owner:* the 4 promises made 10 minutes *before* order creation and the 5 deliveries exactly 5 minutes *before* pickup look like a systematic offset bug, not noise.
- *VP Operations:* is 'Delivered' (capitalised, 5 rows) the same status as 'delivered'? (Treated as representation.)
"""), md("""
# Challenge 2 — Stakeholders disagree on "late"

The metric under at least three definitions, plus the validated population the pipeline publishes.
"""), code('''
analysis["delay_min"] = (analysis["actual_delivery_at"] - analysis["promised_eta"]).dt.total_seconds() / 60
hist = analysis[(analysis["final_status_norm"] == "delivered") & analysis["actual_delivery_at"].notna()]
validated = hist[(hist["promised_eta"] >= hist["created_at"]) & ~(hist["actual_delivery_at"] < hist["pickup_at"])]
rows = [
    ("VP Operations — any delay > 0 min (historical population)", (hist["delay_min"] > 0).sum(), len(hist), "any missed promise counts; matches the leadership claim"),
    ("Support Lead — delay > 10 min", (hist["delay_min"] > 10).sum(), len(hist), "'meaningfully late'; hides small misses that still generate tickets"),
    ("Data Team — delivered with non-null actual time (dashboard)", (hist["delay_min"] > 0).sum(), len(hist), "population definition, same formula as VP Ops"),
    ("Finance — cancelled/refunded excluded", (hist["delay_min"] > 0).sum(), len(hist), "already true: cancelled orders never enter the population"),
    ("Pipeline — validated population (chronology rules applied)", (validated["delay_min"] > 0).sum(), len(validated), "excludes 9 orders whose timestamps contradict each other"),
]
table = pd.DataFrame(rows, columns=["definition", "late", "population", "business meaning"])
table.insert(1, "late_rate_%", (100 * table["late"] / table["population"]).round(2))
display(table)
'''), md("""
**Which one should leadership publish, and who must own it?** Publish the VP Operations definition (*any delivered order after the promised ETA*) on the **validated population — 56.3 %** — with the > 10 min rate (≈ 23 %) shown alongside as the severity view. It is the definition closest to the customer's experience and the one the historical dashboard already approximates (56.4 %), so nobody is surprised. **VP Operations must own it in writing**; `client_metric_definitions.json` says no canonical owner exists, so until that signature exists every publication carries the definition next to the number (gate status UNKNOWN, not PASS).
"""), md("""
# Challenge 3 — Validate categories without cleaning by instinct
"""), code('''
def inspect(name, s):
    raw = s.value_counts(dropna=False)
    norm = s.astype(str).str.strip().str.lower().str.replace(r"[\\s-]+", "_", regex=True)
    print(f"--- {name}: raw values {sorted(map(repr, s.dropna().unique()))}")
    display(pd.DataFrame({"raw_count": raw}).join(pd.DataFrame({"after_representation_fix": norm.value_counts()}), how="outer").fillna(0).astype(int))

inspect("orders.final_status", orders["final_status"])
inspect("orders.traffic_bucket", orders["traffic_bucket"])
inspect("restaurant_status.status", restaurant_status["status"])
inspect("support_tickets.category", tickets["category"])
'''), md("""
| Column | Representation differences (safe to normalise) | Semantic differences (owner confirmation) |
|---|---|---|
| `final_status` | `Delivered` → `delivered` (5 rows) | none |
| `traffic_bucket` | `HIGH` → `high` (3 rows) | none in the pack; `gridlock` in the class demo would be a new bucket — ask Operations, do not map to `severe` |
| restaurant `status` | `READY`, `Ready`, `ready ` → `ready` (4 rows) | `handoff` vs `handed_off` — *probably* the same, but may be a different system writing a different milestone → kept separate, flagged (**Restaurant Ops**); `unknown` is a legitimate value the feed emits |
| ticket `category` | `Late Delivery`, `late_delivery ` → `late_delivery` | `ETA issue` vs `eta_changed` — a free-text category; kept as `eta_issue`, flagged (**Support Lead**) |

The pipeline applies exactly this split: `cleaning.py` normalises representation and records every change; `SEMANTIC_CANDIDATES` are reported, never merged.
"""), md("""
# Challenge 4 — Cross-source integrity
"""), code('''
d = analysis
rel = [
    ("orders.restaurant_id → restaurants", d["restaurant_id"].isin(restaurants["restaurant_id"]).mean(), "3 orders have a NULL restaurant_id"),
    ("orders.driver_id → drivers", d["driver_id"].isin(drivers["driver_id"]).mean(), "3 orders have a NULL driver_id"),
    ("orders.customer_id → customers", d["customer_id"].isin(customers["customer_id"]).mean(), ""),
    ("tickets.order_id → orders", tickets["order_id"].isin(d["order_id"]).mean(), "3 tickets have no order_id"),
    ("restaurant_status.order_id → orders", restaurant_status["order_id"].isin(d["order_id"]).mean(), "only 500 of 1600 orders have any status row"),
]
cov = pd.DataFrame(rel, columns=["relationship", "coverage", "note"])
cov["coverage_%"] = (100 * cov["coverage"]).round(2)
cov["status"] = cov["coverage_%"].map(lambda v: "PASS" if v == 100 else ("WARN" if v >= 95 else "FAIL"))
cov["risk"] = ["restaurant attribution impossible for those orders", "driver attribution impossible; also orders keep the ORIGINAL driver after reassignment (95 orders)", "-", "complaint cannot be reconciled with the operational story", "restaurant-side timing only known for a third of orders"]
display(cov[["relationship", "coverage_%", "status", "risk", "note"]])
'''), md("""
**If 1 % is unmapped, is that acceptable?** It depends on which decision uses those records. For the **late-delivery rate** the answer is *yes*: the KPI needs only the order's own timestamps, so the 6 orders with a missing restaurant or driver id stay in the population (flagged). For **restaurant accountability** or **driver scorecards** the answer is *no*: those 6 orders must be excluded from the ranking and the source system fixed, and the 95 reassigned orders must use Dispatch's driver, not the stale one in the orders table.
"""), md("""
# Challenge 5 — Freshness is an SLA question
"""), code('''
rs = restaurant_status.drop_duplicates().copy()          # 2 exact duplicate rows
rs["status_norm"] = rs["status"].str.strip().str.lower()
rs["last_updated_at"] = pd.to_datetime(rs["last_updated_at"], format="mixed", errors="coerce")
m = rs.merge(analysis[["order_id", "created_at", "pickup_at", "actual_delivery_at"]], on="order_id", how="left")
m["lag_vs_pickup_min"] = (m["last_updated_at"] - m["pickup_at"]).dt.total_seconds() / 60      # + = status written AFTER pickup
m["lag_vs_created_min"] = (m["last_updated_at"] - m["created_at"]).dt.total_seconds() / 60
print("orders covered:", m["order_id"].nunique(), "of", len(analysis), "| timestamp precision: minutes (no seconds)")
display(m.groupby("status_norm")["lag_vs_pickup_min"].describe().round(1))
print("ready/handed_off written more than 15 min AFTER pickup:", int((m["status_norm"].isin(["ready", "handed_off"]) & (m["lag_vs_pickup_min"] > 15)).sum()))
print("status written BEFORE the order was created:", int((m["last_updated_at"] < m["created_at"]).sum()))
'''), md("""
| Use case | Fresh enough? | Why |
|---|---|---|
| Weekly analytics (prep-time trends per restaurant) | **WARN / usable** | 31 % coverage and minute precision are tolerable for aggregates, if the coverage bias is stated |
| Live customer ETA | **FAIL** | some `ready` statuses arrive after the driver already picked up, and 5 arrive before the order exists — a live ETA built on this feed would show wrong states |
| Restaurant accountability (penalising slow kitchens) | **FAIL** | with `manual_status_updates=1` for 38 % of restaurants, a late `ready` may be a late *update*, not a late *kitchen* |

The same record is acceptable for one decision and unsafe for another — freshness is decided per use case.
"""), md("""
# Challenge 6 — Build the validation gate

The pipeline computes this gate on every run (`output/validation_gate.md`). Reproduced here from the checks above.
"""), code('''
validation_report = {
    "business_grain":        ("WARN",    "1603 rows / 1600 orders; 3 conflicting duplicates corrected (keep first) and quarantined", "Data Team to explain the double writes"),
    "timestamp_chronology":  ("WARN",    "4 promises before creation, 5 deliveries before pickup, 37 delivered without a delivery time", "exclude the 9 from the validated population; ask ETA service + Fleet Ops"),
    "kpi_definition":        ("UNKNOWN", "4 stakeholder definitions, no documented owner", "VP Operations to sign off; publish the definition next to the number"),
    "category_semantics":    ("WARN",    "representation fixed (Delivered, HIGH, READY); 'handoff' and 'ETA issue' kept separate", "Restaurant Ops / Support Lead to confirm meaning"),
    "cross_source_mapping":  ("WARN",    "99.8 % restaurant/driver coverage, 98.5 % ticket coverage, 100 % dispatch coverage; orders.driver_id stale after reassignment", "use Dispatch for the final driver; fix nulls at source"),
    "freshness":             ("WARN",    "restaurant status: 31 % coverage, minute precision, 8 stale 'ready' rows, 5 rows before creation", "weekly analytics only"),
    "publish_56_percent":    ("PUBLISH WITH CAVEATS", "56.3 % of 1 486 validated deliveries (56.4 % under the dashboard definition)", "state definition, exclusions and open owner questions with the number"),
}
display(pd.DataFrame(validation_report, index=["status", "evidence", "action"]).T)

gate_file = ROOT / "output" / "validation_gate.json"
if gate_file.exists():
    gate = json.loads(gate_file.read_text(encoding="utf-8"))
    print("Pipeline gate for the last published run:", gate["overall_status"], "→", gate["publish_decision"])
'''), md("""
**Should leadership publish "Late Delivery Rate = 56 %" today?** Yes — *with caveats and not as a bare number*: "56.3 % of validated deliveries (837 of 1 486) were delivered after the promised ETA in August; 37 deliveries have an unknown outcome and 9 were excluded for contradictory timestamps; definition owned by VP Operations (pending)". Before the metric becomes publishable **without** caveats: (1) VP Operations signs the definition, (2) Fleet Ops fixes the missing delivery timestamps or approves the driver-event back-fill, (3) the ETA service explains the negative promise offsets.

**Final takeaway:** the job was not to make the data look clean; it was to decide whether this data is safe enough for this decision, and what remains unresolved.
""")]
    return cells


# ============================================================================ SESSION 7
def session7():
    cells = [md("""
# FlashEats — Session 7 challenge: modelling the business workflow with data

**Client question:** *"Show us where in the workflow delay accumulates, how customers react, what interventions we make, and which metrics we should use to improve the project KPI."*

Project KPI: **reduce late delivery rate**. Source discovery, retrieval and cleaning are not repeated here — the modelled tables produced by `run_pipeline.py` are used (`data/processed/`).
"""), code(SETUP), code('''
P = ROOT / "data" / "processed"
if not (P / "fact_order.csv").exists():
    raise FileNotFoundError("Run `python run_pipeline.py --start-api` first - this notebook reads the modelled tables from data/processed/")
dt_cols = ["created_at", "promised_eta", "pickup_at", "actual_delivery_at", "assigned_at", "reassigned_at", "estimated_pickup_at", "current_delivery_eta", "ev_delivered_at"]
fact_order = pd.read_csv(P / "fact_order.csv", parse_dates=[c for c in dt_cols])
fact_event = pd.read_csv(P / "fact_event.csv", parse_dates=["event_time"])
fact_interaction = pd.read_csv(P / "fact_interaction.csv", parse_dates=["interaction_at"])
fact_intervention = pd.read_csv(P / "fact_intervention.csv", parse_dates=["intervention_at"])
order_journey = pd.read_csv(P / "order_journey.csv", parse_dates=["created_at", "promised_eta", "actual_delivery_at", "first_intervention_at", "first_ticket_at", "first_app_action_at"])
dim_restaurant = pd.read_csv(P / "dim_restaurant.csv")
for name, df in [("fact_order", fact_order), ("fact_event", fact_event), ("fact_interaction", fact_interaction), ("fact_intervention", fact_intervention), ("order_journey", order_journey)]:
    print(f"{name:18s} {df.shape}")
'''), md("""
# Challenge 1 — Reconstruct the order lifecycle

Three orders — one on time, one late, one with an intervention — as `event_time | event_type | actor | source_system`, merged from every source and sorted by time.
"""), code('''
def build_order_timeline(order_id):
    t = fact_event[fact_event["order_id"] == order_id].sort_values("event_time")
    return t[["event_time", "event_type", "actor_type", "actor_id", "source_system", "detail"]].reset_index(drop=True)

on_time_order = fact_order[fact_order["outcome_bucket"] == "delivered_on_time"]["order_id"].iloc[0]
late_order = fact_order[(fact_order["outcome_bucket"] == "delivered_late") & (fact_order["delay_min"] > 20)]["order_id"].iloc[0]
intervention_order = order_journey[(order_journey["intervention_count"] > 0) & (order_journey["ticket_count"] > 0) & (order_journey["late_flag"] == 1)]["order_id"].iloc[0]
for label, oid in [("ON TIME", on_time_order), ("LATE", late_order), ("INTERVENTION + TICKET + STILL LATE", intervention_order)]:
    row = fact_order.set_index("order_id").loc[oid]
    print(f"=== {label}: {oid} | delay {row['delay_min']} min | promised {row['promised_eta']} | delivered {row['actual_delivery_at']}")
    display(build_order_timeline(oid))
'''), md("""
The timeline makes the gaps visible: between `DRIVER_ASSIGNED` and `PICKED_UP` there is no *arrived at restaurant* event, so the wait at the restaurant and the ride to it are one block; cancelled orders have no terminal event at all.

# Challenge 2 — Define the canonical project model

| Table | Grain (one row per…) | Primary key | Important foreign keys | Supports |
|---|---|---|---|---|
| `dim_customer` | customer | `customer_id` | — | customer → orders |
| `dim_restaurant` | restaurant | `restaurant_id` | — | restaurant attribution (with `coords_valid`) |
| `dim_driver` | driver | `driver_id` | — | driver attribution |
| `fact_order` | order | `order_id` | `customer_id`, `restaurant_id`, `driver_id` (final, from Dispatch), `original_driver_id` | order → outcome (`late_flag`, `delay_min`, `outcome_bucket`), stage durations, dq flags, KPI population |
| `fact_event` | lifecycle event | (`order_id`, `event_time`, `event_type`, `source_system`) | `order_id` | order → events/states |
| `fact_interaction` | customer interaction (app action or ticket) | `interaction_id` | `order_id`, `customer_id` | order → customer interactions, order → support interactions |
| `fact_intervention` | intervention | `intervention_id` | `order_id` | order → interventions |
| `order_journey` | order | `order_id` | as `fact_order` | interaction → intervention → outcome in one row |

Relationships: customer 1—n order; order 1—n event; order 1—n interaction; order 1—n intervention; order 1—1 outcome; restaurant 1—n order; driver 1—n order (with the reassignment kept as an event and as `original_driver_id`).

**Why this beats mirroring every source table:** the sources are organised by *system* (orders DB, dispatch, driver app, support desk, app analytics) and disagree on grain, spelling and even on who the driver is. The model is organised around the **workflow the KPI lives in**: every one-to-many table is aggregated to order grain *before* it touches the order, so the denominator cannot inflate, and every business question ("late orders with support contact and no intervention") is one filter on `order_journey` instead of a five-way join that nobody can audit.
"""), code('''
for name, df, key in [("fact_order", fact_order, "order_id"), ("fact_interaction", fact_interaction, "interaction_id"), ("fact_intervention", fact_intervention, "intervention_id"), ("order_journey", order_journey, "order_id")]:
    print(f"{name:18s} rows={len(df):6d} unique {key}={df[key].nunique():6d} -> grain OK: {df[key].is_unique}")
print("every order has exactly one journey row:", set(order_journey["order_id"]) == set(fact_order["order_id"]))
print(json.dumps(json.loads((P / "join_checks.json").read_text()), indent=1))
'''), md("""
# Challenge 3 — Build interaction → intervention → outcome

One order-level table: `order_id, customer_id, support_opened, cancel_attempted, intervention_count, intervention_types, final_status, late_flag, delay_min` (built by aggregating the one-to-many tables first).
"""), code('''
cols = ["order_id", "customer_id", "support_opened", "cancel_attempted", "ticket_count", "intervention_count", "intervention_types", "final_status", "late_flag", "delay_min", "outcome_bucket"]
display(order_journey[cols].head(8))
pop = order_journey[order_journey["kpi_population"]]
late = pop[pop["late_flag"] == 1]
print("1. Late orders with a support interaction (ticket or SUPPORT_OPENED):", int(late["support_contact"].sum()), "of", len(late), f"({100*late['support_contact'].mean():.1f}%)")
print("2. Orders that received an intervention:", int((order_journey["intervention_count"] > 0).sum()), "of", len(order_journey))
print("3. Most common intervention:", fact_intervention["intervention_type"].value_counts().head(1).to_dict())
frustrated_no_iv = order_journey[order_journey["frustrated_no_intervention"]]
print("4. Frustrated journeys (support contact) with NO intervention:", len(frustrated_no_iv), "| of which late:", int((frustrated_no_iv["late_flag"] == 1).sum()))
display(frustrated_no_iv[["order_id", "ticket_categories", "support_opened", "late_flag", "delay_min"]].sort_values("delay_min", ascending=False).head(8))
'''), md("""
# Challenge 4 — Select 3–5 business metrics

| # | Metric | Formula | Grain | Why it matters | Link to KPI |
|---|---|---|---|---|---|
| M1 | **Late delivery rate** (outcome) | late orders / validated delivered orders | order | the project KPI itself | direct |
| M2 | **Lateness severity** (outcome) | median delay among late orders; P90 delay over all deliveries | order | tells whether the problem is "many small misses" or "few disasters" | severity of the KPI |
| M3 | **Share of lateness accumulated before pickup** (workflow) | Σ max(pickup − estimated_pickup, 0) / Σ all positive stage overruns, late orders | order → stage | says *where* to intervene (kitchen/dispatch vs road) | the driver of the KPI |
| M4 | **Support contact rate on late orders** (interaction) | late orders with ticket or SUPPORT_OPENED / late orders | order | customer impact and early-warning signal | consequence of the KPI |
| M5 | **Intervention coverage & late rate with vs without intervention** (intervention) | orders with ≥1 intervention / orders; late rate per group and per type | order | does the ops team reach the orders that need help, and does it coincide with better outcomes | lever on the KPI |

All five (plus supporting variants) are computed by `metrics.py` and written to `output/metrics.csv`.
"""), code('''
metrics = pd.read_csv(ROOT / "output" / "metrics.csv")
for c in ["numerator", "denominator"]:      # show counts as integers, keep minute sums as they are
    metrics[c] = pd.to_numeric(metrics[c], errors="coerce").map(lambda v: int(v) if pd.notna(v) and float(v).is_integer() else v)
display(metrics[metrics["metric_id"].isin(["M1", "M1a", "M1b", "M2", "M2a", "M3", "M3a", "M3b", "M4", "M4a", "M5", "M5a", "M5b"])][["metric_id", "metric", "category", "value", "unit", "numerator", "denominator"]])
'''), md("""
# Challenge 5 — Investigate the workflow with joins and aggregations
"""), code('''
def late_rate(df):
    return round(100 * (df["late_flag"] == 1).mean(), 1) if len(df) else None

# A. Do orders with support interactions have higher delay?
a = pop.groupby("support_contact")["delay_min"].agg(orders="size", median_delay="median", mean_delay="mean").round(1)
a["late_rate_%"] = pop.groupby("support_contact").apply(late_rate, include_groups=False)
print("A. delay by support contact"); display(a)

# B. Late rate with vs without intervention
b = pop.groupby("has_intervention")["late_flag"].agg(orders="size", late=lambda s: int((s == 1).sum()))
b["late_rate_%"] = (100 * b["late"] / b["orders"]).round(1)
print("B. late rate with vs without intervention"); display(b)

# C. Which intervention type is associated with the lowest late rate?
c = fact_intervention.merge(pop[["order_id", "late_flag", "delay_min"]], on="order_id", how="inner")
c = c.groupby("intervention_type").agg(orders=("order_id", "nunique"), late_rate_pct=("late_flag", lambda s: round(100 * (s == 1).mean(), 1)), median_delay=("delay_min", "median"), before_promise_pct=("before_promised_eta", lambda s: round(100 * s.mean(), 1))).sort_values("late_rate_pct")
print("C. late rate by intervention type"); display(c)

# D. Which restaurants contribute the most late orders?
d = fact_order[fact_order["kpi_population"]].merge(dim_restaurant[["restaurant_id", "cuisine", "manual_status_updates"]], on="restaurant_id", how="left")
d = d.groupby(["restaurant_id", "cuisine"]).agg(orders=("order_id", "size"), late=("late_flag", "sum"), late_rate_pct=("late_flag", lambda s: round(100 * s.mean(), 1)), median_delay=("delay_min", "median")).reset_index()
d["share_of_all_late_%"] = (100 * d["late"] / d["late"].sum()).round(1)
print("D. top restaurants by late orders (share of all late orders)"); display(d.sort_values("late", ascending=False).head(10))

# E. Journeys with support interaction + intervention + still late
e = order_journey[order_journey["frustrated_intervened_still_late"]]
print("E. support contact + intervention + still late:", len(e)); display(e[["order_id", "ticket_categories", "intervention_types", "delay_min"]].sort_values("delay_min", ascending=False).head(8))
'''), md("""
**What each answer tells the business — and what it does NOT prove**

- **A.** Orders with a support contact have a median delay of ~12 min vs ~−0.3 min without, and a late rate of ~88 % vs ~49 %. *Tells:* complaints are a reliable lagging signal of real lateness. *Does not prove:* that contacting support changes the outcome — the customer contacts support *because* the order is late.
- **B.** Late rate is ~56 % with and ~56 % without an intervention. *Tells:* interventions are not associated with a lower late rate overall. *Does not prove:* that interventions are useless — they are targeted at late-risk orders (selection effect), so "no difference" may mean they pulled a 70 % risk down to 56 %.
- **C.** `PRIORITY_DISPATCH` and `RESTAURANT_CONTACT` show the lowest late rates (~51–52 %), `CUSTOMER_CREDIT` the highest (67 %). *Tells:* credits are issued *after* a bad outcome (0 % before the promised ETA), the other three act before it. *Does not prove:* which intervention causes better outcomes — no randomisation, different triggers per type.
- **D.** No single restaurant dominates: the top contributor has ~2.6 % of all late orders; a handful (e.g. R024, 80 % late) stand out on rate. *Tells:* lateness is systemic, not a "few bad kitchens" story. *Does not prove:* kitchen fault — restaurant prep time is not observed (no arrival event).
- **E.** 66 journeys had a support contact **and** an intervention **and** were still late. *Tells:* the recovery loop exists but is late or weak. *Does not prove:* that earlier intervention would have saved them.
"""), md("""
# Challenge 6 — Connect the model to the KPI

```
PROJECT KPI          reduce late delivery rate (M1)
   ↑
OUTCOME METRICS      M1 late rate · M2 severity (median / P90 delay)
   ↑
WORKFLOW METRICS     M3 pre-pickup overrun share · stage durations (dispatch wait, assign→pickup, transit) · ETA revision
   ↑                 M4 support contact rate (customer reaction)
INTERVENTIONS        M5 coverage · late rate by type (reassignment, restaurant contact, priority dispatch, credit)
   ↑
DATA SOURCES/EVENTS  orders DB (created, promised, pickup, delivered) · Dispatch API (assigned, estimated pickup, reassigned)
                     driver app (assigned, GPS, picked_up, delivered) · restaurant feed (preparing/ready/handed_off)
                     customer app (ETA_VIEWED, SUPPORT_OPENED, CANCEL_ATTEMPTED) · support desk (tickets) · interventions log
```

1. **Directly controllable by operations:** dispatch wait (assignment speed), intervention coverage and timing (M5), which orders get priority dispatch / restaurant contact, and the ETA promise itself (planned pickup and transit windows).
2. **Outcomes:** M1, M2, M4 — they move only when the controllable levers move.
3. **Missing event that limits the model most:** *driver arrived at restaurant*. Without it, M3's "pre-pickup overrun" cannot be split into kitchen time and rider time, so the biggest bucket of lateness (≈99 % of overrun minutes) cannot be assigned to an owner.
4. **What to instrument next:** the arrival event (geofence or a tap in the driver app), a mandatory delivery timestamp on the `delivered` transition, reassignment propagation into the orders table, and a cancellation timestamp.

**Final deliverable — the smallest useful model:** 3 dimensions, 4 facts, 1 order-grain journey table; key events created → assigned → (arrived?) → picked up → delivered plus interactions and interventions; 5 metrics linked to the KPI; one modelling limitation — the pre-pickup stage is a black box.
"""), code('''
print("Session 7 notebook complete.")
''')]
    return cells


def _local_kernelspec() -> str:
    """Register a kernel spec for the *current* interpreter inside the repository (no user-profile side effects).

    Jupyter looks for kernels under every directory in JUPYTER_PATH; pointing it at
    ``assignment-2/.jupyter`` keeps the spec next to the code and makes the executed
    notebooks reproducible with whatever interpreter runs this script.
    """
    import json
    import os
    kdir = ROOT / ".jupyter" / "kernels" / "flasheats-local"
    kdir.mkdir(parents=True, exist_ok=True)
    (kdir / "kernel.json").write_text(json.dumps({
        "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        "display_name": "Python (flasheats pipeline)", "language": "python",
    }, indent=1), encoding="utf-8")
    os.environ["JUPYTER_PATH"] = str(ROOT / ".jupyter") + os.pathsep + os.environ.get("JUPYTER_PATH", "")
    return "flasheats-local"


def build(exec_: bool, kernel: str | None):
    kernel_name = kernel or (_local_kernelspec() if exec_ else "python3")
    for name, fn in [("Session5_Challenges", session5), ("Session6_Challenges", session6), ("Session7_Challenges", session7)]:
        nb = nbf.v4.new_notebook()
        nb["cells"] = fn()
        nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}
        path = HERE / f"{name}.ipynb"
        if exec_:
            from nbclient import NotebookClient
            client = NotebookClient(nb, timeout=600, kernel_name=kernel_name, resources={"metadata": {"path": str(HERE)}}, allow_errors=False)
            client.execute()
        nbf.write(nb, path)
        print(("executed" if exec_ else "wrote"), path.name, "cells:", len(nb["cells"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-exec", action="store_true")
    ap.add_argument("--kernel", default=None, help="kernel name to execute with (default: a spec for the current interpreter, registered under .jupyter/)")
    a = ap.parse_args()
    build(not a.no_exec, a.kernel)

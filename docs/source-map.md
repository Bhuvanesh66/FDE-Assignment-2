# Source map — business questions → information → source systems

**Client:** FlashEats (food delivery, Bengaluru). **Business problem:** late deliveries hurt customer experience; leadership wants a dependable late-delivery KPI before investing in an AI delay-prediction system. **Project KPI:** reduce the late delivery rate.

## 1. Business questions → information needed

| # | Business question | Information required | Answered by |
|---|---|---|---|
| Q1 | How large is the late-delivery problem? | promised ETA, actual delivery time, final status, one row per order | M1, M2 |
| Q2 | Where in the workflow does delay accumulate? | order created, driver assigned, estimated pickup, actual pickup, delivered | M3 |
| Q3 | How do customers react? | ETA views, support opened, cancel attempts, support tickets | M4 |
| Q4 | What does the ops team do about it, and is it associated with better outcomes? | interventions (type, time, initiator), reassignments | M5 |
| Q5 | Which factors are associated with lateness? | traffic, weather, distance, hour, restaurant, driver | breakdowns |

## 2. Source systems

| Source system | Retrieval mode | Owner (assumed) | Grain | Refresh | Used for | Trust level |
|---|---|---|---|---|---|---|
| **Orders application DB** (`database/flasheats.db`, tables `orders`, `customers`, `drivers`, `restaurants`) | **SQL** (SQLite, read-only, `sql/*.sql`) | Data Team / Platform | `orders`: intended one row per order — actually 1603 rows for 1600 orders | batch export | promise, delivery time, status, KPI population, dimensions | **Authoritative** for the promise and the delivery time; **stale** for `driver_id` after reassignment |
| **Dispatch service** (mock REST API `/dispatch/orders`, paginated, transient 429/500) | **API** (`ingest/api_source.py`) | Dispatch | one record per order | live | assignment, reassignment, estimated pickup, revised ETA, final driver | **Authoritative** for assignment and the final driver |
| **Support ticketing export** (`data/support_tickets.csv`) | **CSV** | Support Lead | one row per ticket (202 rows, 201 ids, 3 without order) | export | customer view: complaint category and time | Contextual (what the customer said) |
| **Restaurant status feed** (`data/restaurant_status.csv`) | **CSV** | Restaurant Ops | one row per status update; covers 500 of 1600 orders; minute precision | feed | restaurant-side milestones (preparing / ready / handed_off) | Weak: partial coverage, manual updates for 38 % of restaurants |
| **Driver app telemetry** (`data/driver_events.json`, nested per driver) | **JSON** | Fleet Ops | one event per driver action / GPS ping (10 035 events) | stream export | assigned / picked_up / delivered events, GPS pings | Good for events; GPS has out-of-area outliers; **no arrival-at-restaurant event** |
| **Customer app analytics** (`data/customer_app_actions.csv`) | **CSV** | Product / App | one row per in-app action (2 365 rows, 1 100 orders) | export | ETA_VIEWED, SUPPORT_OPENED, CANCEL_ATTEMPTED | Good |
| **Interventions log** (`data/order_interventions.csv`) | **CSV** | Support / Dispatch / Operations | one row per intervention (430; at most one per order) | export | DRIVER_REASSIGNMENT, RESTAURANT_CONTACT, PRIORITY_DISPATCH, CUSTOMER_CREDIT | Does **not** reconcile with Dispatch reassignments (8 of 155 overlap) |
| `data/client_metric_definitions.json` | JSON | Leadership | — | — | four competing definitions of "late", no owner | Organisational input |
| `data/order_outcomes.csv`, `data/order_events.csv`, `data/customer_interactions.csv` | CSV | Data Team (derived) | order / event / interaction | — | **reconciliation only** — these are derived artefacts, not systems of record | Used as an independent cross-check (reference late count matches: 843) |

Retrieval modes used: **SQL + API + CSV + JSON** (the assignment requires at least two).

## 3. Important gaps found in the sources

| Gap | Consequence | Owner to ask |
|---|---|---|
| No *driver arrived at restaurant* event anywhere | restaurant prep time and driver waiting time cannot be separated → the largest bucket of lateness (pre-pickup) has no owner | Fleet Ops / Product |
| No cancellation timestamp | cancelled orders have no terminal event; cancellation lead time unknown | Platform |
| `orders.driver_id` is never updated after a Dispatch reassignment (95 orders) | driver scorecards blame the wrong driver unless Dispatch is used | Dispatch / Data Team |
| 37 delivered orders without `actual_delivery_at` (driver app has the `delivered` event) | KPI population is bounded, not exact (55.0 %–57.4 %) | Fleet Ops |
| 4 promises made before order creation, 5 deliveries before pickup | look like systematic offsets (exactly −10 min and −5 min) in a writer, not noise | ETA service / Platform |
| Interventions log vs Dispatch reassignments overlap on only 8 orders | one of the two logs is incomplete; intervention effectiveness cannot be trusted yet | Support Lead / Dispatch |
| Restaurant feed covers 31 % of orders, minute precision, mixed spellings, some updates before order creation | usable for weekly analytics, not for live ETA or accountability | Restaurant Ops |
| Four definitions of "late", no documented KPI owner | any published number is disputable | VP Operations |

## 4. Flow from systems to decision

```
 Orders DB (SQL) ─┐
 Dispatch API ────┤                                                     ┌─ M1 late delivery rate
 Tickets (CSV) ───┼─► ingest → raw snapshot → profile → validate/clean ─┼─ M2 severity
 Restaurant (CSV) ┤        (data/raw/<run>)     (rules, quarantine)     ├─ M3 stage of delay      ─► decision: which stage to fix,
 Driver app (JSON)┤                                   │                 ├─ M4 customer reaction       whether the AI predictor is justified
 App actions (CSV)┤                          business model             └─ M5 interventions
 Interventions ───┘               (fact_order, fact_event, order_journey)        + validation gate (PASS/WARN/FAIL/UNKNOWN)
```

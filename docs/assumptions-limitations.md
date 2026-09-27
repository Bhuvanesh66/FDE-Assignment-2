# Known / Unknown / Assumption / Limitation

The pipeline regenerates a version of this section from the actual run (`output/known_unknown_assumption_limitation.md`). This page is the curated, complete list with owners and the decision each item affects.

## Known (verified by the pipeline on the classroom pack)

| # | Fact | Evidence |
|---|---|---|
| K1 | Retrieval is complete: 1600 Dispatch records over 16 pages (server total 1600), 2 transient errors retried; every raw page, file copy and SQL extract is preserved with SHA-256 | `data/raw/<run_id>/`, `output/run_manifest.json` |
| K2 | The orders table has 1603 rows for 1600 orders; the 3 duplicates disagree on `traffic_bucket` | `output/quarantine/orders_duplicate_conflicts.csv` |
| K3 | 68 orders are cancelled; 37 delivered orders have no delivery timestamp; 4 promises predate the order; 5 deliveries predate pickup | rules TS-01/02/04 |
| K4 | Late delivery rate = **56.33 %** of 1486 validated deliveries (56.39 % of 1495 under the dashboard definition); median lateness 8.0 min; P90 17.9 min | `output/metrics.csv`, SQL cross-check, `order_outcomes.csv` reconciliation |
| K5 | 98.9 % of overrun minutes on late orders accrue **before pickup**; transit is faster than planned | M3, `stage_durations_by_outcome.csv` |
| K6 | `orders.driver_id` equals Dispatch's *original* driver for 1597 orders → not updated after reassignment | rule CX-01 |
| K7 | Late orders generate support contacts six times more often than on-time orders (30.7 % vs 5.2 %) | M4/M4a |
| K8 | The interventions log records 155 driver reassignments, Dispatch 95, overlap 8 | rule CX-03 |
| K9 | Two restaurants have impossible coordinates; 189 GPS pings are outside the service area | rules RG-02/03 |

## Unknown (needs an owner; the pipeline reports, it does not decide)

| # | Question | Owner | Decision affected |
|---|---|---|---|
| U1 | Which definition of "late" is canonical (any delay vs > 10 min) and who signs it | VP Operations | whether 56 % or 23 % is "the number" |
| U2 | May the driver-app `delivered` event back-fill the 37 missing delivery timestamps? | Fleet Ops | KPI 56.33 % vs 56.53 % |
| U3 | Are the −10 min promise offsets and −5 min delivery offsets a writer bug? | ETA service / Platform | whether the 9 excluded orders should be corrected instead of excluded |
| U4 | Why do the interventions log and Dispatch disagree on reassignments? | Support Lead / Dispatch | any intervention-effectiveness claim |
| U5 | Does `handoff` mean `handed_off`; does `ETA issue` mean `eta_changed`? | Restaurant Ops / Support Lead | category breakdowns (1 row each) |
| U6 | When does the driver arrive at the restaurant? (no event exists) | Fleet Ops / Product | splitting pre-pickup delay into kitchen vs rider |
| U7 | Why two writers to the orders table (duplicate rows with different traffic buckets)? | Data Team | grain guarantee |

## Assumptions (stated and configurable, never silently applied)

| # | Assumption | Where |
|---|---|---|
| A1 | Naive timestamps are `Asia/Kolkata`; tz-aware values are converted to it | `config.source_timezone` |
| A2 | Late = `actual_delivery_at − promised_eta > 0 min`; "meaningfully late" = > 10 min | `config.late_threshold_min`, `meaningful_late_threshold_min` |
| A3 | `orders.promised_eta` is the promise the customer saw; Dispatch's `current_delivery_eta` is a later revision and never defines lateness | `model.py` (`eta_revision_min` reported separately) |
| A4 | Cancelled orders are excluded from every denominator (Finance) | `kpi_population` |
| A5 | Delivered orders without a delivery timestamp are *unknown*, not on time | `outcome_bucket = unknown_missing_timestamp` |
| A6 | A plausible delivery distance is (0, 50] km; coordinates must lie in the Bengaluru bounding box (12.5–13.5, 77.2–78.0) | `config` |
| A7 | Representation differences (case, whitespace, spaces vs underscores) may be normalised; look-alike words may not | `cleaning.VOCAB`, `SEMANTIC_CANDIDATES` |
| A8 | When duplicate rows conflict, the first row is kept (as in class) and the conflict is quarantined | `cleaning.dedupe` |
| A9 | Dispatch is authoritative for the final driver; the orders table for the promise and delivery time; tickets only for the customer's perception | `model.build_fact_order` |
| A10 | `order_outcomes.csv`, `order_events.csv`, `customer_interactions.csv` are derived client artefacts used only for reconciliation | `pipeline.FILE_SOURCES` |
| A11 | Restaurant status is "fresh" if written within 15 min of pickup | `config.status_freshness_sla_min` |

## Limitations

| # | Limitation | Consequence |
|---|---|---|
| L1 | Interventions are targeted at late-risk orders (selection effect); no randomisation | M5a/M5b is an association, never an effect |
| L2 | No arrival-at-restaurant event | the biggest bucket of delay cannot be attributed to kitchen vs rider |
| L3 | Restaurant feed covers 31 % of orders at minute precision with manual updates | restaurant-side timing usable for weekly trends only |
| L4 | GPS pings are sparse (≈ 3–5 per order), have outliers, and **look interpolated**: 91.3 % of tracks are perfect straight constant-speed lines, and before pickup they move away from the restaurant in 99.2 % of orders | no route, arrival or GPS-based ETA inference; Fleet Ops to confirm whether pings are device readings |
| L5 | No cancellation timestamp | cancelled orders have no terminal event; cancellation lead time unknown |
| L6 | The classroom pack is synthetic, one city, one month | magnitudes illustrate the method; do not generalise |
| L7 | The independent SQL check cannot normalise malformed / tz-suffixed timestamps | on very messy data it reports WARN with the explainable difference instead of PASS |
| L8 | Traffic and weather are per-order buckets, not measured on the route | associations may be confounded by time-of-day load |

## Additions from the decision layer and the external source

| Type | Item |
|---|---|
| **Known** | The client's `weather_bucket` agrees with Open-Meteo's observed Bengaluru rainfall only at chance level (kappa 0.01). |
| **Known** | Dispatch's pickup estimate is optimistic by a median 8 minutes; a "not picked up 10 min after the estimate" rule would have caught 72 % of late orders with 96 % precision in the held-out week. |
| **Known** | GPS pings do not converge on the restaurant before pickup (they move away from it in 99.2 % of orders), and 91.3 % of tracks are perfect straight lines. Arrival cannot be inferred from them. |
| **Known** | The client's six published control totals all match what was retrieved; the preserved raw inputs reproduce every output byte for byte; the four weekly runs add up to the month. |
| **Unknown** | Whether GPS pings are device readings or drawn by the app between two points. Owner: Fleet Ops. |
| **Unknown** | Who writes `weather_bucket`, and when (a forecast at order time? a manual flag?). Owner: Operations / Data Team. |
| **Unknown** | The real save rate of an intervention triggered by the rule. Measure it with a switchback pilot (alternate days on and off). Owner: Operations. |
| **Assumption** | Observed weather comes from one point (Bengaluru centre) per hour; an hour with more than 0.1 mm counts as raining. |
| **Assumption** | The what-if save rates (25 % and 50 %) are scenarios from `config/pipeline.yaml`, not measurements. |
| **Assumption** | The trigger is chosen on 1–21 August and judged on 22–28 August; one hold-out week is a small sample. |
| **Limitation** | A single weather point cannot capture neighbourhood showers; a V2 would geocode each route. |
| **Limitation** | The backtest shows the trigger *detects* late orders early; it does not show that intervening will *save* them. That needs the pilot. |

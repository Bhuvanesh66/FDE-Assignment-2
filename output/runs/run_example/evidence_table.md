# Evidence table — FlashEats late-delivery KPI

Run `run_example` · gate: **WARN**

| # | Metric | Value | Numerator / Denominator | Population | Business question |
|---|---|---:|---|---|---|
| M1 | Late delivery rate (validated population) | **56.33 %** | 837 / 1486 | delivered orders with valid promised_eta + actual_delivery_at, passing chronology rules TS-01/02/03 | PROJECT KPI |
| M2 | Median lateness among late orders | **8.0 min** | — / 837 | late orders in the validated population | severity of the KPI |
| M3 | Share of lateness accumulated before pickup (vs in transit) | **98.91 %** | 13150.8 / 13296.1 | late orders with Dispatch estimated_pickup_at (837 orders) | WHERE delay accumulates -> which stage to fix first |
| M4 | Support contact rate on late orders | **30.7 %** | 257 / 837 | late orders (validated population) | customer impact of the KPI |
| M5 | Intervention coverage of delivered orders | **26.85 %** | 399 / 1486 | validated population | how much of the workflow the ops team touches |

Supporting metrics (M1a-c, M2a-b, M3a-b, M4a-c, M5a-c) and all breakdowns are in `metrics.md`.

## Definition comparison (why one number needs an owner)

| definition | late_rate_pct | late | population |
|---|---|---|---|
| VP Operations: any delivered order after promised ETA (validated population) | 56.33 | 837 | 1486 |
| Data Team: delivered orders with non-null actual delivery time (historical dashboard) | 56.39 | 843 | 1495 |
| Support Lead: only > 10 min beyond ETA | 23.15 | 344 | 1486 |
| Finance: cancelled/refunded excluded (already true in every definition above) | 56.33 | 837 | 1486 |
| Sensitivity: back-fill missing delivery time from driver telemetry | 56.53 | 861 | 1523 |

## Where delay accumulates

| stage_metric | late | on_time | late_minus_on_time |
|---|---|---|---|
| dispatch_wait_min | 2.30 | 2.30 | 0.00 |
| pickup_wait_min | 28.80 | 16.60 | 12.20 |
| transit_min | 49.00 | 45.30 | 3.70 |
| total_cycle_min | 81.80 | 65.10 | 16.70 |
| promised_window_min | 74.30 | 72.80 | 1.50 |
| pickup_overrun_min | 14.00 | 1.80 | 12.20 |
| transit_overrun_min | -5.90 | -7.90 | 2.00 |
| eta_revision_min | 10.00 | 4.60 | 5.40 |

## Interventions (association, not causation)

| intervention_type | orders | late_orders | median_delay_min | before_promised_eta_pct | late_rate_pct |
|---|---|---|---|---|---|
| CUSTOMER_CREDIT | 61 | 41 | 2.90 | 0.00 | 67.20 |
| DRIVER_REASSIGNMENT | 147 | 85 | 1.60 | 100.00 | 57.80 |
| (no intervention) | 1087 | 612 | 1.40 |  | 56.30 |
| RESTAURANT_CONTACT | 105 | 55 | 0.60 | 100.00 | 52.40 |
| PRIORITY_DISPATCH | 86 | 44 | 0.30 | 100.00 | 51.20 |

## Decision layer (beyond the classroom)

| # | Finding | So what | Owner |
|---|---|---|---|
| D1 A proactive trigger that works today, without AI | Alerting when an order is still not picked up 10 min after Dispatch's own estimated pickup catches 71.5% of late orders with 96.1% precision on the held-out week, a median 44.8 min before the promise breaks. | 446 late orders the trigger would have caught received no intervention at all; 169 interventions went to orders that were never at risk. | Operations |
| D2 The promise is optimistic before the food even leaves | Dispatch's pickup estimate is short by a median 8.0 min (planned 18.0 min vs actual 26.0 min from order to pickup). Reaching 80% on-time by padding alone needs +12 min on every promise. | Fix the pickup estimate (the input) rather than padding the promise (the output); padding trades lateness for longer quoted times, whose effect on conversion is unknown. | Product / ETA service |
| D3 Do not publish a restaurant or driver blame list | Only 1 of 59 judgeable restaurants (R024) and 1 of 91 drivers are statistically worse than the fleet; a naive top-10 list would name 10 restaurants, of which 1 survive the test. | Lateness is systemic; accountability conversations should start with the significant few, with the confidence interval shown. | Restaurant Ops / Fleet Ops |
| D4 The weather label does not match the weather | Against Open-Meteo's observed hourly rainfall, the client's weather_bucket agrees 52.6% of the time (Cohen's kappa 0.009, i.e. no better than chance). Orders labelled heavy rain saw 0.4 mm on average, orders labelled clear 0.46 mm. Observed rain: 58.5% late vs 54.5% when dry. | 'Weather causes delays' cannot be defended with this field; ask who writes weather_bucket and when, before any weather-aware ETA or staffing plan. | Operations / Data Team |
| D5 GPS cannot replace the missing arrival event | Before pickup, the last GPS ping is closer to the restaurant than the first in only 0.8% of orders; the median last ping is 4.35 km away. | A geofence built on this feed would invent arrivals. Instrument an explicit 'arrived at restaurant' tap instead. | Fleet Ops / Product |

Details: `insights/insights.md` · actions: `decision_memo.md`

## Known / Unknown / Assumption / Limitation

**Known (verified in this run)**
- Retrieval is complete: 1600 dispatch records across 16 pages (server total 1600, 2 retries); every raw page and file copy is preserved with a SHA-256.
- Grain: the raw orders extract had 1603 rows for 1600 unique orders; conflicting duplicates are quarantined, not deleted.
- 37 delivered orders have no actual_delivery_at and are reported as 'unknown outcome', not as on-time.
- Chronology violations (TS-01 4, TS-02 5) are excluded from the KPI population and listed by order id.
- The orders table keeps the ORIGINAL driver after a reassignment (CX-01): Dispatch is used as the authoritative final driver.
- The client's weather_bucket does not match independently observed rainfall (WX-01: hours covered=100.0%; agreement=52.6%; Cohen's kappa=0.009; mean observed mm by label={'clear': 0.46, 'heavy_rain': 0.4, 'rain': 0.6}).

**Unknown (needs an owner)**
- Which definition of 'late' leadership will own (any delay vs > 10 min) - no canonical KPI owner is documented (KPI-01).
- Whether the driver 'delivered' event may back-fill the missing delivery timestamps (TS-04): reported as a sensitivity, not published.
- Why the intervention log and Dispatch disagree on driver reassignments (CX-03: dispatch reassigned=95, intervention DRIVER_REASSIGNMENT=155, in both=8, only in interventions=147, only in dispatch=87).
- Whether 'handoff' means 'handed_off' and 'ETA issue' means 'eta_changed' (semantic look-alikes kept separate).
- When the driver actually arrived at the restaurant - no such event exists, so restaurant prep time and driver wait cannot be separated.
- Who writes weather_bucket and when (forecast at order time? manual flag?) - the label cannot be traced to observed weather.

**Assumptions (stated, not silently applied)**
- Naive timestamps are in Asia/Kolkata; tz-aware values (if any) are converted to that zone.
- Late = actual_delivery_at - promised_eta > 0 min (VP Operations); > 10 min reported alongside (Support Lead).
- Cancelled orders are excluded from the KPI denominator (Finance) and no cancellation timestamp exists.
- Delivery distance is plausible only in (0, 50] km; coordinates must fall inside the Bengaluru bounding box.
- orders.promised_eta is the customer-facing promise; Dispatch's current_delivery_eta is a later revision and is NOT used to define lateness.
- customer_interactions.csv and order_events.csv are treated as derived client artefacts and used only for reconciliation.
- Observed weather is taken at one point (Bengaluru centre, 12.9716, 77.5946) per hour; an hour with > 0.1 mm counts as raining.
- Decision-layer what-ifs use an assumed intervention save rate (config: impact.prevented_share_scenarios); they are scenarios, not forecasts.

**Limitations**
- Interventions are targeted at late-risk orders, so 'late rate with vs without intervention' is an association with a selection effect, never a causal effect.
- Restaurant status feed covers only a subset of orders with minute precision (FR-01) - usable for weekly analytics, not for live ETA or restaurant accountability.
- GPS pings contain out-of-area outliers (RG-03) and no arrival-at-restaurant event: pickup_wait_min mixes restaurant prep and driver travel.
- All source data is a synthetic classroom pack for one city (Bengaluru) and one month (Aug 2026); magnitudes are illustrative.
- Model note: No explicit 'driver arrived at restaurant' event exists in any source: restaurant prep time and driver wait cannot be separated (pickup_wait_min mixes both).
- Model note: No cancellation timestamp exists: cancelled orders have no terminal event in the event log.
- A single weather point cannot capture neighbourhood-level showers; a V2 would geocode each order's route.


## Validation gate

**Overall: WARN**  

**Decision:** PUBLISH WITH CAVEATS: late delivery rate = 56.33% of 1486 validated deliveries (historical definition: 56.39%). State the definition, the excluded orders and the unresolved owner questions next to the number.

| Check | Status | Evidence | Action |
|---|---|---|---|
| Retrieval completeness | **PASS** | API: 1600 records / expected 1600 in 16 pages, retries=2, mode=live; missing files=none; missing optional reference files=none; empty files=none; zero-row SQL extracts=none | raw pages + file copies + SQL extracts preserved under data/raw/<run_id> |
| Business grain (one row per order) | **WARN** | raw duplicate rows removed by cleaning: 3 (corrected; conflicting copies kept in quarantine) | exact duplicates dropped; conflicting duplicates keep first row, conflict recorded in quarantine |
| Timestamp chronology & completeness | **WARN** | TS-00=0; TS-01=4; TS-02=5; TS-03=0; TS-04=37; TS-05=0 | violating orders excluded from the KPI population (reject) and listed in the data-quality report; nothing deleted |
| KPI definition ownership | **UNKNOWN** | no canonical KPI owner documented; 4 stakeholder definitions found: VP Operations: Any delivered order after the promised ETA is late.; Support Lead: Only more than 10 minutes beyond ETA should count as meaningfully late.; Finance: Cancelled/refunded orders should not count in operational performance.; Data Team: Historical dashboard uses delivered orders with non-null actual delivery time. / pipeline publishes late = delay > 0 min and reports > 10 min alongside | VP Operations to sign off the definition; until then every output states the definition next to the number |
| Category semantics | **WARN** | ST-01: fixes=5, unexpected={}; ST-02: fixes=3, unexpected={}; ST-04: fixes=2, unexpected={'handoff': 1}; ST-05: fixes=2, unexpected={'eta_issue': 1} | representation normalised; semantic look-alikes NOT merged, owner decision required: {'ST-04': {'handoff': 'handed_off'}, 'ST-05': {'eta_issue': 'eta_changed'}} |
| Cross-source mapping | **WARN** | coverage %: ID-02=100.0, ID-03=99.81, ID-04=99.81, ID-05=98.51, ID-06=100.0, ID-07=100.0, ID-08=100.0, ID-09=100.0, ID-10=100.0; CX-01: orders.driver_id equals dispatch ORIGINAL driver for 1597 orders -> the orders table is not updated after reassignment; Dispatch is authoritative for the final driver; CX-02: compared 1532 orders; CX-03: dispatch reassigned=95, intervention DRIVER_REASSIGNMENT=155, in both=8, only in interventions=147, only in dispatch=87 | unmapped records retained and flagged; Dispatch treated as authoritative for the final driver |
| Freshness (restaurant status feed) | **WARN** | status rows joined=500 covering 500 of 1600 orders (31.2%); ready/handed_off written >15 min after pickup=8; updated before order creation=5; median lag vs pickup=-6.4 min; timestamps have minute precision only | restaurant status usable for weekly analytics only; not for live ETA or accountability |
| Metric sanity & independent checks | **PASS** | 13 checks passed | see output/metric_checks.csv |
| Independent cross-check (observed weather vs client label) | **WARN** | hours covered=100.0%; agreement=52.6%; Cohen's kappa=0.009; mean observed mm by label={'clear': 0.46, 'heavy_rain': 0.4, 'rain': 0.6}; source mode=live | weather_bucket is not used to explain lateness until Operations confirms how it is produced |
| Run-over-run stability (vs last published run) | **UNKNOWN** | no previous published run to compare with (first run) | see output/run_comparison.md |

Blocking: none  
Unresolved (caveats): ['Business grain (one row per order)', 'Timestamp chronology & completeness', 'KPI definition ownership', 'Category semantics', 'Cross-source mapping', 'Freshness (restaurant status feed)', 'Independent cross-check (observed weather vs client label)', 'Run-over-run stability (vs last published run)']
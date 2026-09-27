# Evidence table — FlashEats late-delivery KPI

Run `run_weekly_2026-08-01_2026-08-07` · gate: **WARN**

| # | Metric | Value | Numerator / Denominator | Population | Business question |
|---|---|---:|---|---|---|
| M1 | Late delivery rate (validated population) | **54.49 %** | 188 / 345 | delivered orders with valid promised_eta + actual_delivery_at, passing chronology rules TS-01/02/03 | PROJECT KPI |
| M2 | Median lateness among late orders | **8.0 min** | — / 188 | late orders in the validated population | severity of the KPI |
| M3 | Share of lateness accumulated before pickup (vs in transit) | **98.49 %** | 2836.5 / 2880.1 | late orders with Dispatch estimated_pickup_at (188 orders) | WHERE delay accumulates -> which stage to fix first |
| M4 | Support contact rate on late orders | **32.45 %** | 61 / 188 | late orders (validated population) | customer impact of the KPI |
| M5 | Intervention coverage of delivered orders | **24.93 %** | 86 / 345 | validated population | how much of the workflow the ops team touches |

Supporting metrics (M1a-c, M2a-b, M3a-b, M4a-c, M5a-c) and all breakdowns are in `metrics.md`.

## Definition comparison (why one number needs an owner)

| definition | late_rate_pct | late | population |
|---|---|---|---|
| VP Operations: any delivered order after promised ETA (validated population) | 54.49 | 188 | 345 |
| Data Team: delivered orders with non-null actual delivery time (historical dashboard) | 54.34 | 188 | 346 |
| Support Lead: only > 10 min beyond ETA | 21.74 | 75 | 345 |
| Finance: cancelled/refunded excluded (already true in every definition above) | 54.49 | 188 | 345 |
| Sensitivity: back-fill missing delivery time from driver telemetry | 54.90 | 196 | 357 |

## Where delay accumulates

| stage_metric | late | on_time | late_minus_on_time |
|---|---|---|---|
| dispatch_wait_min | 2.30 | 2.40 | -0.10 |
| pickup_wait_min | 28.40 | 16.40 | 12.00 |
| transit_min | 48.80 | 45.40 | 3.40 |
| total_cycle_min | 81.30 | 64.30 | 17.00 |
| promised_window_min | 74.00 | 72.80 | 1.20 |
| pickup_overrun_min | 13.80 | 1.20 | 12.60 |
| transit_overrun_min | -5.80 | -8.20 | 2.40 |
| eta_revision_min | 10.00 | 4.50 | 5.50 |

## Interventions (association, not causation)

| intervention_type | orders | late_orders | median_delay_min | before_promised_eta_pct | late_rate_pct |
|---|---|---|---|---|---|
| CUSTOMER_CREDIT | 17 | 11 | 2.70 | 0.00 | 64.70 |
| DRIVER_REASSIGNMENT | 32 | 19 | 1.90 | 100.00 | 59.40 |
| PRIORITY_DISPATCH | 14 | 8 | 3.40 | 100.00 | 57.10 |
| (no intervention) | 259 | 140 | 0.70 |  | 54.05 |
| RESTAURANT_CONTACT | 23 | 10 | -2.10 | 100.00 | 43.50 |

## Decision layer (beyond the classroom)

| # | Finding | So what | Owner |
|---|---|---|---|
| D1 A proactive trigger that works today, without AI | Alerting when an order is still not picked up 10 min after Dispatch's own estimated pickup catches 72.9% of late orders with 96.5% precision on the held-out week, a median 45.0 min before the promise breaks. | 104 late orders the trigger would have caught received no intervention at all; 36 interventions went to orders that were never at risk. | Operations |
| D2 The promise is optimistic before the food even leaves | Dispatch's pickup estimate is short by a median 7.7 min (planned 18.0 min vs actual 25.7 min from order to pickup). Reaching 80% on-time by padding alone needs +12 min on every promise. | Fix the pickup estimate (the input) rather than padding the promise (the output); padding trades lateness for longer quoted times, whose effect on conversion is unknown. | Product / ETA service |
| D3 Do not publish a restaurant or driver blame list | Only 0 of 0 judgeable restaurants (none) and 0 of 1 drivers are statistically worse than the fleet; a naive top-10 list would name 10 restaurants, of which 0 survive the test. | Lateness is systemic; accountability conversations should start with the significant few, with the confidence interval shown. | Restaurant Ops / Fleet Ops |
| D4 The weather label does not match the weather | Against Open-Meteo's observed hourly rainfall, the client's weather_bucket agrees 42.7% of the time (Cohen's kappa 0.019, i.e. no better than chance). Orders labelled heavy rain saw 0.96 mm on average, orders labelled clear 1.02 mm. Observed rain: 54.1% late vs 55.2% when dry. | 'Weather causes delays' cannot be defended with this field; ask who writes weather_bucket and when, before any weather-aware ETA or staffing plan. | Operations / Data Team |
| D5 GPS pings look drawn, not measured - they cannot show arrival at the restaurant | Before pickup, the last ping is FARTHER from the restaurant than the first in 98.8% of orders (closer in only 1.2%) - a rider cannot leave with the food before picking it up. 88.3% of tracks with 3+ pings are perfectly straight, constant-speed lines and 87.5% have perfectly even time gaps - real device tracks are never that clean. Class 6 found pings only before pickup; here 29.8% of pings fall before pickup and the rest after it (99.7% of post-pickup tracks close in on the customer). | Do not build a geofence or a live GPS ETA on this feed: it would invent arrivals. Ask Fleet Ops whether pings are device readings or app interpolation, and instrument an explicit 'arrived at restaurant' tap - the one event that splits kitchen delay from rider delay, which is where the lateness builds. | Fleet Ops / Product |

Details: `insights/insights.md` · actions: `decision_memo.md`

## Known / Unknown / Assumption / Limitation

**Known (verified in this run)**
- Retrieval is complete: 1600 dispatch records across 16 pages (server total 1600, 2 retries); every raw page and file copy is preserved with a SHA-256.
- Grain: the raw orders extract had 373 rows for 372 unique orders; conflicting duplicates are quarantined, not deleted.
- 12 delivered orders have no actual_delivery_at and are reported as 'unknown outcome', not as on-time.
- Chronology violations (TS-01 0, TS-02 1) are excluded from the KPI population and listed by order id.
- The orders table keeps the ORIGINAL driver after a reassignment (CX-01): Dispatch is used as the authoritative final driver.
- The client's weather_bucket does not match independently observed rainfall (WX-01: hours covered=100.0%; agreement=42.7%; Cohen's kappa=0.019; mean observed mm by label={'clear': 1.02, 'heavy_rain': 0.96, 'rain': 1.41}).

**Unknown (needs an owner)**
- Which definition of 'late' leadership will own (any delay vs > 10 min) - no canonical KPI owner is documented (KPI-01).
- Whether the driver 'delivered' event may back-fill the missing delivery timestamps (TS-04): reported as a sensitivity, not published.
- Why the intervention log and Dispatch disagree on driver reassignments (CX-03: dispatch reassigned=28, intervention DRIVER_REASSIGNMENT=32, in both=3, only in interventions=29, only in dispatch=25).
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

**Decision:** PUBLISH WITH CAVEATS: late delivery rate = 54.49% of 345 validated deliveries (historical definition: 54.34%). State the definition, the excluded orders and the unresolved owner questions next to the number.

| Check | Status | Evidence | Action |
|---|---|---|---|
| Retrieval completeness | **PASS** | API: 1600 records / expected 1600 in 16 pages, retries=2, mode=live; client control totals PASS (observed/published: orders_rows 1603/1603; unique_orders 1600/1600; support_tickets_rows 202/202; dispatch_records 1600/1600; drivers 120/120; restaurants 60/60); orders extract vs server COUNT(*): 373/373; schema-contract failures=none; missing files=none; missing optional reference files=none; empty files=none; zero-row SQL extracts=none | a count mismatch against the owner's control totals refuses publication; raw pages + file copies + SQL extracts preserved with SHA-256 under data/raw/<run_id> |
| Business grain (one row per order) | **WARN** | raw duplicate rows removed by cleaning: 1 (corrected; conflicting copies kept in quarantine) | exact duplicates dropped; conflicting duplicates keep first row, conflict recorded in quarantine |
| Timestamp chronology & completeness | **WARN** | TS-00=0; TS-01=0; TS-02=1; TS-03=0; TS-04=12; TS-05=0 | violating orders excluded from the KPI population (reject) and listed in the data-quality report; nothing deleted |
| KPI definition ownership | **UNKNOWN** | no canonical KPI owner documented; 4 stakeholder definitions found: VP Operations: Any delivered order after the promised ETA is late.; Support Lead: Only more than 10 minutes beyond ETA should count as meaningfully late.; Finance: Cancelled/refunded orders should not count in operational performance.; Data Team: Historical dashboard uses delivered orders with non-null actual delivery time. / pipeline publishes late = delay > 0 min and reports > 10 min alongside | VP Operations to sign off the definition; until then every output states the definition next to the number |
| Category semantics | **WARN** | ST-01: fixes=1, unexpected={}; ST-04: fixes=2, unexpected={}; ST-05: fixes=2, unexpected={'eta_issue': 1} | representation normalised; semantic look-alikes NOT merged, owner decision required: {'ST-04': {'handoff': 'handed_off'}, 'ST-05': {'eta_issue': 'eta_changed'}} |
| Cross-source mapping | **WARN** | coverage %: ID-02=100.0, ID-03=100.0, ID-04=99.46, ID-05=100.0, ID-06=100.0, ID-07=100.0, ID-08=100.0, ID-09=100.0, ID-10=100.0; CX-01: orders.driver_id equals dispatch ORIGINAL driver for 370 orders -> the orders table is not updated after reassignment; Dispatch is authoritative for the final driver; CX-02: compared 358 orders; CX-03: dispatch reassigned=28, intervention DRIVER_REASSIGNMENT=32, in both=3, only in interventions=29, only in dispatch=25 | unmapped records retained and flagged; Dispatch treated as authoritative for the final driver |
| Freshness (restaurant status feed) | **WARN** | status rows joined=131 covering 131 of 372 orders (35.2%); ready/handed_off written >15 min after pickup=1; updated before order creation=1; median lag vs pickup=-5.0 min; timestamps have minute precision only | restaurant status usable for weekly analytics only; not for live ETA or accountability |
| Metric sanity & independent checks | **PASS** | 15 checks passed | see output/metric_checks.csv |
| Independent cross-check (observed weather vs client label) | **WARN** | hours covered=100.0%; agreement=42.7%; Cohen's kappa=0.019; mean observed mm by label={'clear': 1.02, 'heavy_rain': 0.96, 'rain': 1.41}; source mode=live | weather_bucket is not used to explain lateness until Operations confirms how it is produced |
| Run-over-run stability (vs last published run) | **PASS** | KPI moved +0.00 pp vs run_weekly_2026-08-01_2026-08-07 (its previous publication, 2026-09-27T22:03:30); no rule got worse; 0/46 deterministic outputs byte-identical | see output/run_comparison.md |

Blocking: none  
Unresolved (caveats): ['Business grain (one row per order)', 'Timestamp chronology & completeness', 'KPI definition ownership', 'Category semantics', 'Cross-source mapping', 'Freshness (restaurant status feed)', 'Independent cross-check (observed weather vs client label)']
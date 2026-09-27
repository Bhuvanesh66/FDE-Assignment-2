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

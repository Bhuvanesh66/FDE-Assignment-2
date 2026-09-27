# Data-quality report

Flow: **understand → profile → detect → explain → fix → validate**. Nothing is deleted: corrected values are logged, unusable records are quarantined with a reason, and every business rule below records what it found and what the pipeline did.

## 1. Cleaning actions (representation only)

| dataset | column | action | count | detail |
|---|---|---|---|---|
| orders | final_status | normalise_category (trim, case, spaces->_) | 5 | 'Delivered'->'delivered' |
| orders | traffic_bucket | normalise_category (trim, case, spaces->_) | 3 | 'HIGH'->'high' |
| orders | order_id | drop_conflicting_duplicate_key_rows (keep first) | 3 | 3 keys duplicated; differing columns: ['traffic_bucket'] |
| tickets | category | normalise_category (trim, case, spaces->_) | 2 | 'ETA issue'->'eta_issue'; 'Late Delivery'->'late_delivery' |
| tickets | * | drop_exact_duplicate_rows | 1 |  |
| restaurant_status | status | normalise_category (trim, case, spaces->_) | 2 | 'READY'->'ready'; 'Ready'->'ready' |
| restaurant_status | * | drop_exact_duplicate_rows | 2 |  |

## 2. Timestamp parsing

| column | total | null_or_blank | parsed | unparseable | tz_aware_converted | formats_seen |
|---|---|---|---|---|---|---|
| orders.created_at | 1603 | 0 | 1603 | 0 | 0 | {'9999-99-99T99:99:99': 1603} |
| orders.promised_eta | 1603 | 0 | 1603 | 0 | 0 | {'9999-99-99T99:99:99': 813, '9999-99-99T99:99:99.999999': 790} |
| orders.pickup_at | 1603 | 0 | 1603 | 0 | 0 | {'9999-99-99T99:99:99.999999': 1603} |
| orders.actual_delivery_at | 1603 | 105 | 1498 | 0 | 0 | {'9999-99-99T99:99:99.999999': 1498} |
| tickets.created_at | 202 | 0 | 202 | 0 | 0 | {'9999-99-99T99:99:99': 202} |
| restaurant_status.last_updated_at | 502 | 0 | 502 | 0 | 0 | {'9999-99-99T99:99:99': 502} |
| app_actions.action_at | 2365 | 0 | 2365 | 0 | 0 | {'9999-99-99T99:99:99': 2292, '9999-99-99T99:99:99.999999': 73} |
| interventions.intervention_at | 430 | 0 | 430 | 0 | 0 | {'9999-99-99T99:99:99': 408, '9999-99-99T99:99:99.999999': 22} |
| driver_events.timestamp | 10035 | 0 | 10035 | 0 | 0 | {'9999-99-99T99:99:99.999999': 10035} |
| dispatch.assigned_at | 1600 | 0 | 1600 | 0 | 0 | {'9999-99-99T99:99:99.999999': 1600} |
| dispatch.reassigned_at | 1600 | 1505 | 95 | 0 | 0 | {'9999-99-99T99:99:99.999999': 95} |
| dispatch.estimated_pickup_at | 1600 | 0 | 1600 | 0 | 0 | {'9999-99-99T99:99:99': 1600} |
| dispatch.current_delivery_eta | 1600 | 0 | 1600 | 0 | 0 | {'9999-99-99T99:99:99.999999': 1230, '9999-99-99T99:99:99': 370} |

## 3. Unexpected category values (retained + flagged, owner decision needed)

- `tickets.category`: {'eta_issue': 1}  → semantic candidates: {'eta_issue': 'eta_changed'}
- `restaurant_status.status`: {'handoff': 1}  → semantic candidates: {'handoff': 'handed_off'}

## 4. Quarantine & duplicate conflicts

- quarantine/orders_duplicate_conflicts.csv: 6 rows (conflicting columns: ['traffic_bucket'])

## 5. Business rules (validation contract)

| Rule | Name | Dataset | Status | Violations | Population | Action | Owner | Business reason | Detection | Detail |
|---|---|---|---|---:|---:|---|---|---|---|---|
| GR-01 | One row per business order | orders | **WARN** | 0 | 1600 | correct | Data Team | Every KPI denominator counts orders; a repeated order would count twice. | order_id duplicated after cleaning (raw duplicates reported by the cleaning stage) | raw duplicate rows removed by cleaning: 3 (corrected; conflicting copies kept in quarantine) |
| ID-01 | order_id present and well-formed | orders | **PASS** | 0 | 1600 | flag | Data Team | An order without an identifier cannot be joined to any other system. | null order_id (quarantined) or layout not matching the O##### pattern | 0 rows quarantined for null order_id; 0 ids with a different layout (kept) |
| ID-02 | orders.customer_id maps to a known customer | orders | **PASS** | 0 | 1600 | flag | Data Team | Customer-level metrics and app-interaction joins need a real customer. | customer_id not in customers | null=0, unknown=0 |
| ID-03 | orders.restaurant_id maps to a known restaurant | orders | **WARN** | 3 | 1600 | flag | Restaurant Ops | Restaurant attribution of delay is impossible for an unknown restaurant. | restaurant_id null or not in restaurants | null=3, unknown=0 |
| ID-04 | orders.driver_id maps to a known driver | orders | **WARN** | 3 | 1600 | flag | Fleet Ops | Driver attribution and telemetry joins need a real driver. | driver_id null or not in drivers | null=3, unknown=0 |
| ID-05 | tickets.order_id maps to an order | tickets | **WARN** | 3 | 201 | flag | Support Lead | A complaint that cannot be tied to an order cannot be reconciled with the operational story. | order_id null or not in orders | null=3, unknown=0 |
| ID-06 | restaurant_status rows map to an order and agree on the restaurant | restaurant_status | **PASS** | 0 | 500 | flag | Restaurant Ops | Status events for a foreign order (another platform?) would corrupt restaurant metrics. | order_id not in orders OR restaurant_id differs from the order's restaurant | unknown order=0, restaurant mismatch=0 |
| ID-07 | app actions map to an order and its customer | app_actions | **PASS** | 0 | 2365 | flag | Product / App | Customer interaction counts must belong to the right order. | order_id not in orders OR customer_id differs from the order's customer | unknown order=0, customer mismatch=0 |
| ID-08 | interventions map to an order | interventions | **PASS** | 0 | 430 | flag | Support Lead | An intervention without an order cannot be linked to an outcome. | order_id not in orders |  |
| ID-09 | orders and Dispatch cover each other | orders | **PASS** | 0 | 1600 | flag | Dispatch | Assignment/reassignment context comes only from Dispatch; missing coverage hides reassignments. | order missing in dispatch, or dispatch record whose order is unknown | orders without dispatch record=0; dispatch records for unknown orders=0 |
| ID-10 | driver events map to an order | driver_events | **PASS** | 0 | 10035 | flag | Fleet Ops | Telemetry for unknown orders cannot be used for pickup/delivery inference. | order_id not in orders |  |
| ST-01 | final_status uses an agreed vocabulary | orders | **WARN** | 0 | 1600 | flag | VP Operations | The KPI counts 'delivered' orders only; a new status ('suspended', 'Delivered') would silently leave the population. | value not in {delivered, cancelled} after representation normalisation | representation fixes=5; unexpected values={}; semantic candidates (owner decision)={} |
| ST-02 | traffic_bucket uses an agreed vocabulary | orders | **WARN** | 0 | 1600 | flag | Operations | Traffic breakdowns need consistent buckets. | value not in {low, medium, high, severe} | representation fixes=3; unexpected values={}; semantic candidates (owner decision)={} |
| ST-03 | weather_bucket uses an agreed vocabulary | orders | **PASS** | 0 | 1600 | flag | Operations | Weather breakdowns need consistent buckets. | value not in {clear, rain, heavy_rain} | representation fixes=0; unexpected values={}; semantic candidates (owner decision)={} |
| ST-04 | restaurant status uses an agreed vocabulary | restaurant_status | **WARN** | 1 | 500 | flag | Restaurant Ops | 'handoff' vs 'handed_off' may be two systems or two meanings. | value not in {preparing, ready, handed_off, unknown} | representation fixes=2; unexpected values={'handoff': 1}; semantic candidates (owner decision)={'handoff': 'handed_off'} |
| ST-05 | ticket category uses an agreed vocabulary | tickets | **WARN** | 1 | 201 | flag | Support Lead | Complaint mix by category drives the customer-view comparison. | value not in the six support categories | representation fixes=2; unexpected values={'eta_issue': 1}; semantic candidates (owner decision)={'eta_issue': 'eta_changed'} |
| ST-06 | app action_type uses an agreed vocabulary | app_actions | **PASS** | 0 | 2365 | flag | Product / App | support_opened / cancel_attempted flags depend on it. | value not in {ETA_VIEWED, SUPPORT_OPENED, CANCEL_ATTEMPTED} | representation fixes=0; unexpected values={}; semantic candidates (owner decision)={} |
| ST-07 | intervention_type uses an agreed vocabulary | interventions | **PASS** | 0 | 430 | flag | Support Lead | Intervention metrics are grouped by type. | value not in the four intervention types | representation fixes=0; unexpected values={}; semantic candidates (owner decision)={} |
| ST-08 | dispatch_status uses an agreed vocabulary | dispatch | **PASS** | 0 | 1600 | flag | Dispatch | Cross-check of order status against Dispatch. | value not in {completed, cancelled} | representation fixes=0; unexpected values={}; semantic candidates (owner decision)={} |
| ST-09 | driver event type uses an agreed vocabulary | driver_events | **PASS** | 0 | 10035 | flag | Fleet Ops | Lifecycle reconstruction relies on assigned/picked_up/delivered. | value not in {assigned, gps_ping, picked_up, delivered} | representation fixes=0; unexpected values={}; semantic candidates (owner decision)={} |
| TS-00 | KPI timestamps are parseable | orders | **PASS** | 0 | 1600 | reject | Data Team | Unparseable promised_eta / actual_delivery_at silently shrink the KPI population. | value present but not parseable as a datetime | orders.created_at: unparseable=0, tz-aware=0; orders.promised_eta: unparseable=0, tz-aware=0; orders.pickup_at: unparseable=0, tz-aware=0; orders.actual_delivery_at: unparseable=0, tz-aware=0 |
| TS-01 | Promised ETA is after order creation | orders | **WARN** | 4 | 1600 | reject | Product / ETA service | A promise made before the order exists is not a promise; lateness against it is meaningless. | promised_eta < created_at | minutes early: [10.0] |
| TS-02 | Delivery happens after pickup | orders | **WARN** | 5 | 1600 | reject | Fleet Ops | A delivery timestamp earlier than pickup means one of the two clocks is wrong. | actual_delivery_at < pickup_at | minutes before pickup: [5.0] |
| TS-03 | Pickup happens after order creation | orders | **PASS** | 0 | 1600 | reject | Fleet Ops | Stage durations would be negative. | pickup_at < created_at |  |
| TS-04 | Delivered orders carry an actual delivery time | orders | **WARN** | 37 | 1600 | reject | Data Team / Fleet Ops | Without actual_delivery_at the order's lateness is unknown; excluding it biases the rate if the missing ones are not random. | final_status == delivered and actual_delivery_at is null | 37 delivered orders lack actual_delivery_at; 37 of them have a driver 'delivered' event that could back-fill it (owner decision) |
| TS-05 | Cancelled orders carry no delivery time | orders | **PASS** | 0 | 1600 | flag | Data Team | A cancelled order with a delivery time is a status bug. | final_status == cancelled and actual_delivery_at not null |  |
| TS-06 | Dispatch chronology (created <= assigned <= reassigned) | dispatch | **PASS** | 0 | 1600 | flag | Dispatch | Assignment timing feeds the dispatch-wait stage. | assigned_at < created_at OR reassigned_at < assigned_at |  |
| TS-07 | Driver-event chronology (assigned <= picked_up <= delivered) | driver_events | **WARN** | 14 | 1600 | flag | Fleet Ops | Telemetry used to recover missing delivery times must be internally consistent. | picked_up < assigned OR delivered < picked_up per order | picked_up<assigned=14, delivered<picked_up=0 |
| RG-01 | Delivery distance is plausible | orders | **PASS** | 0 | 1600 | flag | Operations | A 999 km 'estimate' would distort any distance analysis. | distance <= 0 or > max_plausible_distance_km or null | null=0, <=0=0, >50.0km=0 |
| RG-02 | Restaurant coordinates are inside the service area | restaurants | **WARN** | 2 | 60 | flag | Restaurant Ops | Geo-based prep/travel inference is impossible with lat=95. | lat/lon outside the Bengaluru bounding box | R007: (95.12, 77.694095); R019: (12.847954, 190.33) |
| RG-03 | GPS pings are inside the service area | driver_events | **WARN** | 189 | 5371 | flag | Fleet Ops | Outlier pings would corrupt any route/arrival inference. | lat/lon outside the Bengaluru bounding box |  |
| RG-04 | Driver attributes in range | drivers | **PASS** | 0 | 120 | flag | Fleet Ops | Sanity of the driver dimension. | rating outside 0-5 or experience_months < 0 |  |
| CX-01 | orders.driver_id agrees with Dispatch's final driver | orders | **WARN** | 95 | 1600 | retain | Dispatch / Data Team | If the orders table keeps the ORIGINAL driver after a reassignment, driver-level metrics blame the wrong person. | orders.driver_id != dispatch.driver_id | orders.driver_id equals dispatch ORIGINAL driver for 1597 orders -> the orders table is not updated after reassignment; Dispatch is authoritative for the final driver |
| CX-02 | orders.pickup_at agrees with the driver picked_up event | orders | **WARN** | 5 | 1532 | retain | Fleet Ops | Two systems, one fact - they should agree. | abs difference > 60 s | compared 1532 orders |
| CX-03 | Intervention log agrees with Dispatch reassignments | interventions | **WARN** | 234 | 242 | retain | Support Lead / Dispatch | If DRIVER_REASSIGNMENT interventions do not appear in Dispatch (or vice versa), one log is incomplete. | orders with a DRIVER_REASSIGNMENT intervention vs orders with dispatch.reassigned_at | dispatch reassigned=95, intervention DRIVER_REASSIGNMENT=155, in both=8, only in interventions=147, only in dispatch=87 |
| FR-01 | Restaurant status updates are fresh enough for the intended use | restaurant_status | **WARN** | 13 | 500 | flag | Restaurant Ops | 'ready' recorded after the driver already picked up is useless for live ETA and unfair for restaurant accountability. | status in {ready, handed_off} with last_updated_at later than the order's pickup_at (+ SLA) | status rows joined=500 covering 500 of 1600 orders (31.2%); ready/handed_off written >15 min after pickup=8; updated before order creation=5; median lag vs pickup=-6.4 min; timestamps have minute precision only |
| KPI-01 | 'Late' has one agreed definition and owner | orders | **UNKNOWN** | 0 | 0 | retain | VP Operations (proposed) | Four stakeholders define late differently; publishing one number without an owner invites disputes. | client_metric_definitions.json lists conflicting definitions and no canonical owner | no canonical KPI owner documented; 4 stakeholder definitions found: VP Operations: Any delivered order after the promised ETA is late.; Support Lead: Only more than 10 minutes beyond ETA should count as meaningfully late.; Finance: Cancelled/refunded orders should not count in operational performance.; Data Team: Historical dashboard uses delivered orders with non-null actual delivery time. |

## 6. Row counts

| dataset | raw_rows | clean_rows |
|---|---|---|
| orders | 1603 | 1600 |
| restaurants | 60 | 60 |
| drivers | 120 | 120 |
| customers | 900 | 900 |
| tickets | 202 | 201 |
| restaurant_status | 502 | 500 |
| app_actions | 2365 | 2365 |
| interventions | 430 | 430 |
| driver_events | 10035 | 10035 |
| dispatch | 1600 | 1600 |
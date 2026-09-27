# Metrics

| metric_id | metric | category | value | unit | numerator | denominator | population |
|---|---|---|---|---|---|---|---|
| M1 | Late delivery rate (validated population) | outcome | 59.84 | % | 228 | 381 | delivered orders with valid promised_eta + actual_delivery_at, passing chronology rules TS-01/02/03 |
| M1a | Late delivery rate (historical dashboard definition) | outcome | 60.16 | % | 231 | 384 | delivered orders with non-null actual delivery time (Data Team definition, no chronology rules) |
| M1b | Meaningfully late rate (> 10 min) | outcome | 25.98 | % | 99 | 381 | validated population |
| M1c | Late delivery rate (sensitivity: back-fill missing delivery time from driver telemetry) | outcome | 60.00 | % | 231 | 385 | validated population + delivered orders whose missing actual_delivery_at is back-filled from the driver 'delivered' event |
| M2 | Median lateness among late orders | outcome | 8.00 | min | — | 228 | late orders in the validated population |
| M2a | P90 delay across all validated deliveries | outcome | 20.30 | min | — | 381 | validated population |
| M2b | Worst single delay | outcome | 50.30 | min | — | 381 | validated population |
| M3 | Share of lateness accumulated before pickup (vs in transit) | workflow | 99.09 | % | 3748.5 | 3782.8 | late orders with Dispatch estimated_pickup_at (228 orders) |
| M3a | Median pre-pickup overrun on late orders | workflow | 14.10 | min | — | 228 | late orders with dispatch estimates |
| M3b | Median transit overrun on late orders | workflow | -6.00 | min | — | 228 | late orders with dispatch estimates |
| M4 | Support contact rate on late orders | interaction | 30.26 | % | 69 | 228 | late orders (validated population) |
| M4a | Support contact rate on on-time orders | interaction | 3.92 | % | 6 | 153 | on-time orders |
| M4b | Frustrated journeys with no intervention | interaction | 57 | orders | 57 | 75 | all orders with a support contact |
| M4c | Median ETA views per order (late vs on-time) | interaction | 1 vs 1 | views | — | — | validated population |
| M5 | Intervention coverage of delivered orders | intervention | 27.03 | % | 103 | 381 | validated population |
| M5a | Late rate WITH an intervention | intervention | 60.19 | % | 62 | 103 | validated orders with an intervention |
| M5b | Late rate WITHOUT an intervention | intervention | 59.71 | % | 166 | 278 | validated orders without an intervention |
| M5c | Most common intervention type | intervention | DRIVER_REASSIGNMENT (44) | type | 44 | 111 | all interventions |

## Definitions

- **M1 Late delivery rate (validated population)** — late = actual_delivery_at - promised_eta > 0 min. Population: delivered orders with valid promised_eta + actual_delivery_at, passing chronology rules TS-01/02/03. KPI link: PROJECT KPI. Notes: cancelled orders excluded (Finance); delivered orders without a delivery timestamp are 'unknown', not on-time
- **M1a Late delivery rate (historical dashboard definition)** — same formula as M1 on the historical population. Population: delivered orders with non-null actual delivery time (Data Team definition, no chronology rules). KPI link: PROJECT KPI (comparison). Notes: reproduces the leadership claim; differs from M1 only by the chronology-violating orders
- **M1b Meaningfully late rate (> 10 min)** — delay_min > 10. Population: validated population. KPI link: PROJECT KPI (Support Lead definition). 
- **M1c Late delivery rate (sensitivity: back-fill missing delivery time from driver telemetry)** — delay computed on the back-filled timestamp. Population: validated population + delivered orders whose missing actual_delivery_at is back-filled from the driver 'delivered' event. KPI link: PROJECT KPI (sensitivity). Notes: 4 orders back-filled; NOT the published number - needs Fleet Ops to confirm the driver event is authoritative
- **M2 Median lateness among late orders** — median(delay_min | late). Population: late orders in the validated population. KPI link: severity of the KPI. 
- **M2a P90 delay across all validated deliveries** — 90th percentile of delay_min (negative = early). Population: validated population. KPI link: severity of the KPI. 
- **M2b Worst single delay** — max(delay_min). Population: validated population. KPI link: severity of the KPI. 
- **M3 Share of lateness accumulated before pickup (vs in transit)** — delay = (pickup_at - estimated_pickup_at) + ((actual - pickup) - (promised - estimated_pickup)); share = sum(max(pre-pickup overrun,0)) / sum(all positive overruns). Population: late orders with Dispatch estimated_pickup_at (228 orders). KPI link: WHERE delay accumulates -> which stage to fix first. Notes: pre-pickup mixes restaurant prep and driver travel-to-restaurant: no 'arrived at restaurant' event exists to split them
- **M3a Median pre-pickup overrun on late orders** — median(pickup_at - estimated_pickup_at). Population: late orders with dispatch estimates. KPI link: stage diagnosis. 
- **M3b Median transit overrun on late orders** — median((actual - pickup) - (promised - estimated_pickup)). Population: late orders with dispatch estimates. KPI link: stage diagnosis. 
- **M4 Support contact rate on late orders** — order has a support ticket OR a SUPPORT_OPENED app action. Population: late orders (validated population). KPI link: customer impact of the KPI. Notes: on-time comparison: 3.92% of on-time orders had a support contact
- **M4a Support contact rate on on-time orders** — same definition as M4. Population: on-time orders. KPI link: baseline for M4. 
- **M4b Frustrated journeys with no intervention** — support contact AND intervention_count == 0. Population: all orders with a support contact. KPI link: missed opportunities for the ops team. 
- **M4c Median ETA views per order (late vs on-time)** — median(eta_view_count). Population: validated population. KPI link: early-warning signal candidate. Notes: association only
- **M5 Intervention coverage of delivered orders** — orders with >= 1 intervention / orders. Population: validated population. KPI link: how much of the workflow the ops team touches. 
- **M5a Late rate WITH an intervention** — late orders / orders (with intervention). Population: validated orders with an intervention. KPI link: does intervening coincide with better outcomes?. Notes: ASSOCIATION ONLY: interventions target late-risk orders (selection effect)
- **M5b Late rate WITHOUT an intervention** — late orders / orders (no intervention). Population: validated orders without an intervention. KPI link: baseline for M5a. 
- **M5c Most common intervention type** — mode(intervention_type). Population: all interventions. KPI link: what the ops team actually does. 

## Breakdowns

### stage_durations_by_outcome

| stage_metric | late | on_time | late_minus_on_time |
|---|---|---|---|
| dispatch_wait_min | 2.20 | 2.30 | -0.10 |
| pickup_wait_min | 29.60 | 16.20 | 13.40 |
| transit_min | 48.70 | 45.50 | 3.20 |
| total_cycle_min | 82.00 | 64.40 | 17.60 |
| promised_window_min | 73.30 | 72.80 | 0.50 |
| pickup_overrun_min | 14.10 | 1.60 | 12.50 |
| transit_overrun_min | -6.00 | -7.60 | 1.60 |
| eta_revision_min | 10.00 | 4.60 | 5.40 |

### late_orders_by_overrun_stage

| overrun_pattern | late_orders | share_pct |
|---|---|---|
| pre-pickup only | 211 | 92.50 |
| both stages overran | 17 | 7.50 |

### late_rate_by_intervention_type

| intervention_type | orders | late_orders | median_delay_min | before_promised_eta_pct | late_rate_pct |
|---|---|---|---|---|---|
| CUSTOMER_CREDIT | 16 | 10 | 6.20 | 0.00 | 62.50 |
| RESTAURANT_CONTACT | 23 | 14 | 1.80 | 100.00 | 60.90 |
| (no intervention) | 278 | 166 | 1.90 |  | 59.71 |
| DRIVER_REASSIGNMENT | 42 | 25 | 1.20 | 100.00 | 59.50 |
| PRIORITY_DISPATCH | 22 | 13 | 1.60 | 100.00 | 59.10 |

### definition_comparison

| definition | late_rate_pct | late | population |
|---|---|---|---|
| VP Operations: any delivered order after promised ETA (validated population) | 59.84 | 228 | 381 |
| Data Team: delivered orders with non-null actual delivery time (historical dashboard) | 60.16 | 231 | 384 |
| Support Lead: only > 10 min beyond ETA | 25.98 | 99 | 381 |
| Finance: cancelled/refunded excluded (already true in every definition above) | 59.84 | 228 | 381 |
| Sensitivity: back-fill missing delivery time from driver telemetry | 60.00 | 231 | 385 |

### outcome_distribution

| outcome_bucket | orders | share_pct |
|---|---|---|
| delivered_late | 228 | 55.70 |
| delivered_on_time | 153 | 37.40 |
| cancelled | 21 | 5.10 |
| unknown_missing_timestamp | 4 | 1.00 |
| excluded_dq_rule | 3 | 0.70 |

### late_rate_by_traffic

| traffic_bucket | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| high | 106 | 76 | 71.70 | 5.50 | 7.40 |
| low | 94 | 51 | 54.30 | 0.60 | 1.00 |
| medium | 151 | 85 | 56.30 | 1.50 | 3.30 |
| severe | 30 | 16 | 53.30 | 1.20 | 5.90 |

### late_rate_by_weather

| weather_bucket | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| clear | 303 | 167 | 55.10 | 0.90 | 2.90 |
| heavy_rain | 20 | 17 | 85.00 | 6.90 | 10.50 |
| rain | 58 | 44 | 75.90 | 6.70 | 7.80 |

### late_rate_by_distance_band

| distance_band | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| 0-3 km | 6 | 3 | 50.00 | 0.10 | -0.60 |
| 3-6 km | 20 | 12 | 60.00 | 1.00 | 2.90 |
| 6-10 km | 46 | 28 | 60.90 | 2.40 | 5.00 |
| 10-20 km | 309 | 185 | 59.90 | 2.10 | 4.10 |

### late_rate_by_hour

| hour_of_day | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| 11 | 28 | 17 | 60.70 | 2.20 | 4.40 |
| 12 | 38 | 21 | 55.30 | 1.10 | 1.90 |
| 13 | 21 | 14 | 66.70 | 0.70 | 4.80 |
| 14 | 21 | 11 | 52.40 | 0.60 | -0.20 |
| 15 | 15 | 11 | 73.30 | 4.30 | 7.40 |
| 16 | 20 | 12 | 60.00 | 1.90 | 4.50 |
| 17 | 31 | 18 | 58.10 | 5.10 | 6.00 |
| 18 | 60 | 40 | 66.70 | 3.60 | 5.90 |
| 19 | 50 | 31 | 62.00 | 4.20 | 6.50 |
| 20 | 34 | 17 | 50.00 | 0.10 | 1.00 |
| 21 | 29 | 14 | 48.30 | -0.10 | -0.20 |
| 22 | 22 | 10 | 45.50 | -0.10 | 1.70 |
| 23 | 12 | 12 | 100.00 | 5.60 | 10.20 |

### late_rate_by_day_of_week

| day_of_week | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| Friday | 56 | 37 | 66.10 | 2.30 | 4.00 |
| Monday | 56 | 33 | 58.90 | 1.80 | 4.50 |
| Saturday | 55 | 32 | 58.20 | 2.40 | 4.60 |
| Sunday | 60 | 34 | 56.70 | 1.60 | 3.60 |
| Thursday | 53 | 32 | 60.40 | 1.00 | 4.30 |
| Tuesday | 57 | 32 | 56.10 | 1.00 | 1.60 |
| Wednesday | 44 | 28 | 63.60 | 4.60 | 6.50 |

### late_rate_by_eta_model_version

| eta_model_version | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| eta-v3.1 | 176 | 101 | 57.40 | 1.20 | 3.20 |
| eta-v3.2 | 205 | 127 | 62.00 | 2.40 | 4.80 |

### late_rate_by_reassignment

| reassigned | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| not reassigned | 356 | 214 | 60.10 | 1.80 | 3.90 |
| reassigned | 25 | 14 | 56.00 | 2.00 | 6.30 |

### top_restaurants_by_late_orders

| restaurant_id | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min | share_of_all_late_pct |
|---|---|---|---|---|---|---|
| R025 | 10 | 9 | 90.00 | 3.40 | 4.90 | 3.90 |
| R050 | 9 | 8 | 88.90 | 6.20 | 7.90 | 3.50 |
| R030 | 8 | 7 | 87.50 | 5.00 | 4.30 | 3.10 |
| R051 | 8 | 7 | 87.50 | 8.90 | 11.40 | 3.10 |
| R026 | 14 | 7 | 50.00 | -0.20 | 2.90 | 3.10 |
| R001 | 6 | 6 | 100.00 | 10.70 | 9.40 | 2.60 |
| R002 | 7 | 6 | 85.70 | 0.90 | 10.90 | 2.60 |
| R009 | 7 | 6 | 85.70 | 7.80 | 9.20 | 2.60 |
| R012 | 8 | 6 | 75.00 | 5.30 | 5.60 | 2.60 |
| R023 | 9 | 6 | 66.70 | 4.80 | 5.20 | 2.60 |

### top_drivers_by_late_rate

| driver_id | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| D017 | 7 | 6 | 85.70 | 5.80 | 5.90 |
| D087 | 6 | 5 | 83.30 | 5.90 | 5.00 |
| D007 | 5 | 4 | 80.00 | 3.90 | 8.50 |
| D010 | 5 | 4 | 80.00 | 5.10 | 12.20 |
| D011 | 5 | 4 | 80.00 | 8.20 | 10.50 |
| D033 | 5 | 4 | 80.00 | 8.30 | 10.30 |
| D046 | 5 | 4 | 80.00 | 5.50 | 2.30 |
| D047 | 5 | 4 | 80.00 | 12.50 | 9.40 |
| D027 | 6 | 4 | 66.70 | 7.30 | 6.60 |
| D044 | 6 | 4 | 66.70 | 3.80 | 1.40 |

### worst_delays

| order_id | restaurant_id | driver_id | promised_eta | actual_delivery_at | delay_min | traffic_bucket | weather_bucket | distance_km_estimate | reassigned_flag | dq_flags |
|---|---|---|---|---|---|---|---|---|---|---|
| O01081 | R048 | D082 | 2026-08-13 18:15:46 | 2026-08-13 19:06:02 | 50.27 | high | clear | 9.42 | False |  |
| O00473 | R002 | D064 | 2026-08-14 20:17:48 | 2026-08-14 21:04:00 | 46.21 | high | clear | 18.00 | False |  |
| O01102 | R021 | D010 | 2026-08-12 19:31:12 | 2026-08-12 20:16:09 | 44.95 | medium | clear | 13.53 | False |  |
| O00194 | R020 | D018 | 2026-08-11 19:01:48 | 2026-08-11 19:40:08 | 38.34 | high | heavy_rain | 18.00 | False |  |
| O01312 | R027 | D056 | 2026-08-14 20:17:36 | 2026-08-14 20:54:36 | 37.01 | medium | clear | 18.00 | False |  |
| O00460 | R026 | D104 | 2026-08-12 17:52:24 | 2026-08-12 18:29:16 | 36.88 | severe | clear | 18.00 | False |  |
| O00064 | R002 | D032 | 2026-08-09 20:29:56 | 2026-08-09 21:05:34 | 35.63 | medium | clear | 14.36 | False |  |
| O00790 | R013 | D115 | 2026-08-09 00:44:42 | 2026-08-09 01:17:28 | 32.77 | severe | rain | 6.00 | False |  |
| O00497 | R032 | D016 | 2026-08-13 20:44:18 | 2026-08-13 21:16:04 | 31.78 | high | rain | 18.00 | True | CX-01;CX-03 |
| O01513 | R003 | D113 | 2026-08-08 20:09:48 | 2026-08-08 20:41:15 | 31.46 | high | clear | 18.00 | False |  |

### customer_view_vs_system_view

| ticket_category | tickets | orders_matched | late_share_pct | median_delay_min |
|---|---|---|---|---|
| late_delivery | 15 | 15 | 93.33 | 17.70 |
| ready_but_waiting | 12 | 12 | 91.67 | 12.00 |
| restaurant_delay | 9 | 9 | 100.00 | 12.10 |
| eta_changed | 7 | 7 | 71.43 | 2.00 |
| driver_not_moving | 5 | 5 | 60.00 | 5.10 |
| status_mismatch | 5 | 5 | 100.00 | 11.90 |

### journey_patterns

| pattern | orders |
|---|---|
| late orders | 228 |
| late + support contact | 69 |
| late + intervention | 62 |
| late + support contact + intervention (still late) | 16 |
| support contact + intervention + still > 15 min late (Class 7: the intervention did not work) | 8 |
| support contact + intervention (validated deliveries, the base for the line above) | 18 |
| support contact + NO intervention (any outcome) | 57 |
| cancel attempted in app | 1 |

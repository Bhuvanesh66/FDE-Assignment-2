# Metrics

| metric_id | metric | category | value | unit | numerator | denominator | population |
|---|---|---|---|---|---|---|---|
| M1 | Late delivery rate (validated population) | outcome | 56.33 | % | 837 | 1486 | delivered orders with valid promised_eta + actual_delivery_at, passing chronology rules TS-01/02/03 |
| M1a | Late delivery rate (historical dashboard definition) | outcome | 56.39 | % | 843 | 1495 | delivered orders with non-null actual delivery time (Data Team definition, no chronology rules) |
| M1b | Meaningfully late rate (> 10 min) | outcome | 23.15 | % | 344 | 1486 | validated population |
| M1c | Late delivery rate (sensitivity: back-fill missing delivery time from driver telemetry) | outcome | 56.53 | % | 861 | 1523 | validated population + delivered orders whose missing actual_delivery_at is back-filled from the driver 'delivered' event |
| M2 | Median lateness among late orders | outcome | 8.00 | min | — | 837 | late orders in the validated population |
| M2a | P90 delay across all validated deliveries | outcome | 17.90 | min | — | 1486 | validated population |
| M2b | Worst single delay | outcome | 50.30 | min | — | 1486 | validated population |
| M3 | Share of lateness accumulated before pickup (vs in transit) | workflow | 98.91 | % | 13150.8 | 13296.1 | late orders with Dispatch estimated_pickup_at (837 orders) |
| M3a | Median pre-pickup overrun on late orders | workflow | 13.90 | min | — | 837 | late orders with dispatch estimates |
| M3b | Median transit overrun on late orders | workflow | -5.90 | min | — | 837 | late orders with dispatch estimates |
| M4 | Support contact rate on late orders | interaction | 30.70 | % | 257 | 837 | late orders (validated population) |
| M4a | Support contact rate on on-time orders | interaction | 5.24 | % | 34 | 649 | on-time orders |
| M4b | Frustrated journeys with no intervention | interaction | 218 | orders | 218 | 293 | all orders with a support contact |
| M4c | Median ETA views per order (late vs on-time) | interaction | 1 vs 1 | views | — | — | validated population |
| M5 | Intervention coverage of delivered orders | intervention | 26.85 | % | 399 | 1486 | validated population |
| M5a | Late rate WITH an intervention | intervention | 56.39 | % | 225 | 399 | validated orders with an intervention |
| M5b | Late rate WITHOUT an intervention | intervention | 56.30 | % | 612 | 1087 | validated orders without an intervention |
| M5c | Most common intervention type | intervention | DRIVER_REASSIGNMENT (155) | type | 155 | 430 | all interventions |

## Definitions

- **M1 Late delivery rate (validated population)** — late = actual_delivery_at - promised_eta > 0 min. Population: delivered orders with valid promised_eta + actual_delivery_at, passing chronology rules TS-01/02/03. KPI link: PROJECT KPI. Notes: cancelled orders excluded (Finance); delivered orders without a delivery timestamp are 'unknown', not on-time
- **M1a Late delivery rate (historical dashboard definition)** — same formula as M1 on the historical population. Population: delivered orders with non-null actual delivery time (Data Team definition, no chronology rules). KPI link: PROJECT KPI (comparison). Notes: reproduces the leadership claim; differs from M1 only by the chronology-violating orders
- **M1b Meaningfully late rate (> 10 min)** — delay_min > 10. Population: validated population. KPI link: PROJECT KPI (Support Lead definition). 
- **M1c Late delivery rate (sensitivity: back-fill missing delivery time from driver telemetry)** — delay computed on the back-filled timestamp. Population: validated population + delivered orders whose missing actual_delivery_at is back-filled from the driver 'delivered' event. KPI link: PROJECT KPI (sensitivity). Notes: 37 orders back-filled; NOT the published number - needs Fleet Ops to confirm the driver event is authoritative
- **M2 Median lateness among late orders** — median(delay_min | late). Population: late orders in the validated population. KPI link: severity of the KPI. 
- **M2a P90 delay across all validated deliveries** — 90th percentile of delay_min (negative = early). Population: validated population. KPI link: severity of the KPI. 
- **M2b Worst single delay** — max(delay_min). Population: validated population. KPI link: severity of the KPI. 
- **M3 Share of lateness accumulated before pickup (vs in transit)** — delay = (pickup_at - estimated_pickup_at) + ((actual - pickup) - (promised - estimated_pickup)); share = sum(max(pre-pickup overrun,0)) / sum(all positive overruns). Population: late orders with Dispatch estimated_pickup_at (837 orders). KPI link: WHERE delay accumulates -> which stage to fix first. Notes: pre-pickup mixes restaurant prep and driver travel-to-restaurant: no 'arrived at restaurant' event exists to split them
- **M3a Median pre-pickup overrun on late orders** — median(pickup_at - estimated_pickup_at). Population: late orders with dispatch estimates. KPI link: stage diagnosis. 
- **M3b Median transit overrun on late orders** — median((actual - pickup) - (promised - estimated_pickup)). Population: late orders with dispatch estimates. KPI link: stage diagnosis. 
- **M4 Support contact rate on late orders** — order has a support ticket OR a SUPPORT_OPENED app action. Population: late orders (validated population). KPI link: customer impact of the KPI. Notes: on-time comparison: 5.24% of on-time orders had a support contact
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
| dispatch_wait_min | 2.30 | 2.30 | 0.00 |
| pickup_wait_min | 28.80 | 16.60 | 12.20 |
| transit_min | 49.00 | 45.30 | 3.70 |
| total_cycle_min | 81.80 | 65.10 | 16.70 |
| promised_window_min | 74.30 | 72.80 | 1.50 |
| pickup_overrun_min | 14.00 | 1.80 | 12.20 |
| transit_overrun_min | -5.90 | -7.90 | 2.00 |
| eta_revision_min | 10.00 | 4.60 | 5.40 |

### late_orders_by_overrun_stage

| overrun_pattern | late_orders | share_pct |
|---|---|---|
| pre-pickup only | 774 | 92.50 |
| both stages overran | 60 | 7.20 |
| transit only | 3 | 0.40 |

### late_rate_by_intervention_type

| intervention_type | orders | late_orders | median_delay_min | before_promised_eta_pct | late_rate_pct |
|---|---|---|---|---|---|
| CUSTOMER_CREDIT | 61 | 41 | 2.90 | 0.00 | 67.20 |
| DRIVER_REASSIGNMENT | 147 | 85 | 1.60 | 100.00 | 57.80 |
| (no intervention) | 1087 | 612 | 1.40 |  | 56.30 |
| RESTAURANT_CONTACT | 105 | 55 | 0.60 | 100.00 | 52.40 |
| PRIORITY_DISPATCH | 86 | 44 | 0.30 | 100.00 | 51.20 |

### definition_comparison

| definition | late_rate_pct | late | population |
|---|---|---|---|
| VP Operations: any delivered order after promised ETA (validated population) | 56.33 | 837 | 1486 |
| Data Team: delivered orders with non-null actual delivery time (historical dashboard) | 56.39 | 843 | 1495 |
| Support Lead: only > 10 min beyond ETA | 23.15 | 344 | 1486 |
| Finance: cancelled/refunded excluded (already true in every definition above) | 56.33 | 837 | 1486 |
| Sensitivity: back-fill missing delivery time from driver telemetry | 56.53 | 861 | 1523 |

### outcome_distribution

| outcome_bucket | orders | share_pct |
|---|---|---|
| delivered_late | 837 | 52.30 |
| delivered_on_time | 649 | 40.60 |
| cancelled | 68 | 4.20 |
| unknown_missing_timestamp | 37 | 2.30 |
| excluded_dq_rule | 9 | 0.60 |

### late_rate_by_traffic

| traffic_bucket | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| high | 421 | 280 | 66.50 | 4.00 | 5.20 |
| low | 358 | 177 | 49.40 | -0.10 | 0.90 |
| medium | 585 | 299 | 51.10 | 0.20 | 1.80 |
| severe | 122 | 81 | 66.40 | 4.30 | 6.40 |

### late_rate_by_weather

| weather_bucket | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| clear | 1185 | 631 | 53.20 | 0.80 | 2.00 |
| heavy_rain | 72 | 53 | 73.60 | 6.60 | 7.70 |
| rain | 229 | 153 | 66.80 | 4.20 | 6.10 |

### late_rate_by_distance_band

| distance_band | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| 0-3 km | 26 | 16 | 61.50 | 2.50 | 2.80 |
| 3-6 km | 70 | 33 | 47.10 | -0.60 | 0.40 |
| 6-10 km | 193 | 110 | 57.00 | 1.70 | 2.50 |
| 10-20 km | 1194 | 675 | 56.50 | 1.50 | 3.10 |
| 20-50 km | 3 | 3 | 100.00 | 26.30 | 25.10 |

### late_rate_by_hour

| hour_of_day | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| 11 | 94 | 56 | 59.60 | 1.90 | 3.20 |
| 12 | 123 | 68 | 55.30 | 1.00 | 2.50 |
| 13 | 93 | 50 | 53.80 | 0.70 | 2.20 |
| 14 | 73 | 40 | 54.80 | 0.90 | 2.20 |
| 15 | 56 | 38 | 67.90 | 4.00 | 4.70 |
| 16 | 75 | 45 | 60.00 | 2.40 | 4.10 |
| 17 | 127 | 73 | 57.50 | 3.00 | 4.20 |
| 18 | 222 | 138 | 62.20 | 3.20 | 4.60 |
| 19 | 204 | 109 | 53.40 | 0.80 | 3.00 |
| 20 | 171 | 91 | 53.20 | 0.50 | 1.60 |
| 21 | 100 | 43 | 43.00 | -1.50 | -0.10 |
| 22 | 90 | 44 | 48.90 | -0.10 | 0.70 |
| 23 | 58 | 42 | 72.40 | 4.60 | 5.10 |

### late_rate_by_day_of_week

| day_of_week | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| Friday | 207 | 120 | 58.00 | 1.00 | 2.90 |
| Monday | 215 | 124 | 57.70 | 2.00 | 3.20 |
| Saturday | 220 | 131 | 59.50 | 2.30 | 3.90 |
| Sunday | 213 | 112 | 52.60 | 1.00 | 2.30 |
| Thursday | 211 | 113 | 53.60 | 0.60 | 3.60 |
| Tuesday | 214 | 116 | 54.20 | 1.30 | 1.40 |
| Wednesday | 206 | 121 | 58.70 | 1.60 | 3.20 |

### late_rate_by_eta_model_version

| eta_model_version | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| eta-v3.1 | 737 | 406 | 55.10 | 1.20 | 2.70 |
| eta-v3.2 | 749 | 431 | 57.50 | 1.70 | 3.10 |

### late_rate_by_reassignment

| reassigned | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| not reassigned | 1395 | 785 | 56.30 | 1.40 | 2.80 |
| reassigned | 91 | 52 | 57.10 | 2.40 | 4.60 |

### top_restaurants_by_late_orders

| restaurant_id | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min | share_of_all_late_pct |
|---|---|---|---|---|---|---|
| R050 | 35 | 22 | 62.90 | 2.20 | 4.00 | 2.60 |
| R024 | 25 | 20 | 80.00 | 6.20 | 7.20 | 2.40 |
| R051 | 29 | 20 | 69.00 | 4.70 | 4.70 | 2.40 |
| R023 | 32 | 20 | 62.50 | 2.80 | 5.50 | 2.40 |
| R004 | 29 | 19 | 65.50 | 6.80 | 5.50 | 2.30 |
| R045 | 29 | 19 | 65.50 | 6.70 | 6.30 | 2.30 |
| R011 | 31 | 19 | 61.30 | 3.40 | 2.80 | 2.30 |
| R030 | 37 | 19 | 51.40 | 0.20 | -0.10 | 2.30 |
| R018 | 27 | 18 | 66.70 | 4.00 | 6.20 | 2.20 |
| R025 | 28 | 18 | 64.30 | 3.00 | 3.90 | 2.20 |

### top_drivers_by_late_rate

| driver_id | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| D065 | 10 | 9 | 90.00 | 3.80 | 7.70 |
| D023 | 7 | 6 | 85.70 | 7.20 | 7.90 |
| D011 | 12 | 10 | 83.30 | 10.40 | 11.50 |
| D031 | 12 | 10 | 83.30 | 9.40 | 9.10 |
| D054 | 18 | 14 | 77.80 | 6.70 | 6.80 |
| D118 | 9 | 7 | 77.80 | 14.30 | 12.60 |
| D018 | 12 | 9 | 75.00 | 6.90 | 8.30 |
| D040 | 12 | 9 | 75.00 | 2.80 | 5.60 |
| D096 | 8 | 6 | 75.00 | 4.90 | 6.70 |
| D087 | 15 | 11 | 73.30 | 6.30 | 5.30 |

### worst_delays

| order_id | restaurant_id | driver_id | promised_eta | actual_delivery_at | delay_min | traffic_bucket | weather_bucket | distance_km_estimate | reassigned_flag | dq_flags |
|---|---|---|---|---|---|---|---|---|---|---|
| O01081 | R048 | D082 | 2026-08-13 18:15:46 | 2026-08-13 19:06:02 | 50.27 | high | clear | 9.42 | False |  |
| O00473 | R002 | D064 | 2026-08-14 20:17:48 | 2026-08-14 21:04:00 | 46.21 | high | clear | 18.00 | False |  |
| O01102 | R021 | D010 | 2026-08-12 19:31:12 | 2026-08-12 20:16:09 | 44.95 | medium | clear | 13.53 | False |  |
| O00194 | R020 | D018 | 2026-08-11 19:01:48 | 2026-08-11 19:40:08 | 38.34 | high | heavy_rain | 18.00 | False |  |
| O01312 | R027 | D056 | 2026-08-14 20:17:36 | 2026-08-14 20:54:36 | 37.01 | medium | clear | 18.00 | False |  |
| O01403 | R014 | D099 | 2026-08-24 18:47:36 | 2026-08-24 19:24:32 | 36.93 | medium | heavy_rain | 18.00 | False |  |
| O00460 | R026 | D104 | 2026-08-12 17:52:24 | 2026-08-12 18:29:16 | 36.88 | severe | clear | 18.00 | False |  |
| O00737 | R027 | D048 | 2026-08-20 21:11:15 | 2026-08-20 21:47:32 | 36.28 | low | clear | 12.51 | False |  |
| O00064 | R002 | D032 | 2026-08-09 20:29:56 | 2026-08-09 21:05:34 | 35.63 | medium | clear | 14.36 | False |  |
| O00198 | R016 | D100 | 2026-08-19 18:57:33 | 2026-08-19 19:32:47 | 35.23 | medium | clear | 6.07 | False |  |

### customer_view_vs_system_view

| ticket_category | tickets | orders_matched | late_share_pct | median_delay_min |
|---|---|---|---|---|
| late_delivery | 39 | 38 | 86.84 | 14.80 |
| restaurant_delay | 37 | 37 | 75.68 | 10.40 |
| eta_changed | 37 | 36 | 80.00 | 7.60 |
| ready_but_waiting | 33 | 33 | 90.91 | 12.20 |
| status_mismatch | 29 | 28 | 92.86 | 12.70 |
| driver_not_moving | 25 | 25 | 68.00 | 10.40 |
| eta_issue | 1 | 1 | 100.00 | 5.40 |

### journey_patterns

| pattern | orders |
|---|---|
| late orders | 837 |
| late + support contact | 257 |
| late + intervention | 225 |
| late + support contact + intervention (still late) | 66 |
| support contact + intervention + still > 15 min late (Class 7: the intervention did not work) | 31 |
| support contact + intervention (validated deliveries, the base for the line above) | 74 |
| support contact + NO intervention (any outcome) | 218 |
| cancel attempted in app | 10 |

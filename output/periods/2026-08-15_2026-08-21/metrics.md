# Metrics

| metric_id | metric | category | value | unit | numerator | denominator | population |
|---|---|---|---|---|---|---|---|
| M1 | Late delivery rate (validated population) | outcome | 55.58 | % | 214 | 385 | delivered orders with valid promised_eta + actual_delivery_at, passing chronology rules TS-01/02/03 |
| M1a | Late delivery rate (historical dashboard definition) | outcome | 55.44 | % | 214 | 386 | delivered orders with non-null actual delivery time (Data Team definition, no chronology rules) |
| M1b | Meaningfully late rate (> 10 min) | outcome | 22.60 | % | 87 | 385 | validated population |
| M1c | Late delivery rate (sensitivity: back-fill missing delivery time from driver telemetry) | outcome | 56.12 | % | 220 | 392 | validated population + delivered orders whose missing actual_delivery_at is back-filled from the driver 'delivered' event |
| M2 | Median lateness among late orders | outcome | 8.30 | min | — | 214 | late orders in the validated population |
| M2a | P90 delay across all validated deliveries | outcome | 18.80 | min | — | 385 | validated population |
| M2b | Worst single delay | outcome | 36.30 | min | — | 385 | validated population |
| M3 | Share of lateness accumulated before pickup (vs in transit) | workflow | 99.53 | % | 3335.3 | 3351 | late orders with Dispatch estimated_pickup_at (214 orders) |
| M3a | Median pre-pickup overrun on late orders | workflow | 13.80 | min | — | 214 | late orders with dispatch estimates |
| M3b | Median transit overrun on late orders | workflow | -5.50 | min | — | 214 | late orders with dispatch estimates |
| M4 | Support contact rate on late orders | interaction | 29.91 | % | 64 | 214 | late orders (validated population) |
| M4a | Support contact rate on on-time orders | interaction | 5.26 | % | 9 | 171 | on-time orders |
| M4b | Frustrated journeys with no intervention | interaction | 54 | orders | 54 | 73 | all orders with a support contact |
| M4c | Median ETA views per order (late vs on-time) | interaction | 1 vs 1 | views | — | — | validated population |
| M5 | Intervention coverage of delivered orders | intervention | 28.31 | % | 109 | 385 | validated population |
| M5a | Late rate WITH an intervention | intervention | 59.63 | % | 65 | 109 | validated orders with an intervention |
| M5b | Late rate WITHOUT an intervention | intervention | 53.99 | % | 149 | 276 | validated orders without an intervention |
| M5c | Most common intervention type | intervention | DRIVER_REASSIGNMENT (36) | type | 36 | 117 | all interventions |

## Definitions

- **M1 Late delivery rate (validated population)** — late = actual_delivery_at - promised_eta > 0 min. Population: delivered orders with valid promised_eta + actual_delivery_at, passing chronology rules TS-01/02/03. KPI link: PROJECT KPI. Notes: cancelled orders excluded (Finance); delivered orders without a delivery timestamp are 'unknown', not on-time
- **M1a Late delivery rate (historical dashboard definition)** — same formula as M1 on the historical population. Population: delivered orders with non-null actual delivery time (Data Team definition, no chronology rules). KPI link: PROJECT KPI (comparison). Notes: reproduces the leadership claim; differs from M1 only by the chronology-violating orders
- **M1b Meaningfully late rate (> 10 min)** — delay_min > 10. Population: validated population. KPI link: PROJECT KPI (Support Lead definition). 
- **M1c Late delivery rate (sensitivity: back-fill missing delivery time from driver telemetry)** — delay computed on the back-filled timestamp. Population: validated population + delivered orders whose missing actual_delivery_at is back-filled from the driver 'delivered' event. KPI link: PROJECT KPI (sensitivity). Notes: 7 orders back-filled; NOT the published number - needs Fleet Ops to confirm the driver event is authoritative
- **M2 Median lateness among late orders** — median(delay_min | late). Population: late orders in the validated population. KPI link: severity of the KPI. 
- **M2a P90 delay across all validated deliveries** — 90th percentile of delay_min (negative = early). Population: validated population. KPI link: severity of the KPI. 
- **M2b Worst single delay** — max(delay_min). Population: validated population. KPI link: severity of the KPI. 
- **M3 Share of lateness accumulated before pickup (vs in transit)** — delay = (pickup_at - estimated_pickup_at) + ((actual - pickup) - (promised - estimated_pickup)); share = sum(max(pre-pickup overrun,0)) / sum(all positive overruns). Population: late orders with Dispatch estimated_pickup_at (214 orders). KPI link: WHERE delay accumulates -> which stage to fix first. Notes: pre-pickup mixes restaurant prep and driver travel-to-restaurant: no 'arrived at restaurant' event exists to split them
- **M3a Median pre-pickup overrun on late orders** — median(pickup_at - estimated_pickup_at). Population: late orders with dispatch estimates. KPI link: stage diagnosis. 
- **M3b Median transit overrun on late orders** — median((actual - pickup) - (promised - estimated_pickup)). Population: late orders with dispatch estimates. KPI link: stage diagnosis. 
- **M4 Support contact rate on late orders** — order has a support ticket OR a SUPPORT_OPENED app action. Population: late orders (validated population). KPI link: customer impact of the KPI. Notes: on-time comparison: 5.26% of on-time orders had a support contact
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
| dispatch_wait_min | 2.30 | 2.20 | 0.10 |
| pickup_wait_min | 28.30 | 16.40 | 11.90 |
| transit_min | 49.80 | 44.20 | 5.60 |
| total_cycle_min | 81.80 | 64.60 | 17.20 |
| promised_window_min | 75.00 | 72.80 | 2.20 |
| pickup_overrun_min | 13.80 | 2.20 | 11.60 |
| transit_overrun_min | -5.50 | -8.30 | 2.80 |
| eta_revision_min | 10.00 | 4.30 | 5.70 |

### late_orders_by_overrun_stage

| overrun_pattern | late_orders | share_pct |
|---|---|---|
| pre-pickup only | 204 | 95.30 |
| both stages overran | 10 | 4.70 |

### late_rate_by_intervention_type

| intervention_type | orders | late_orders | median_delay_min | before_promised_eta_pct | late_rate_pct |
|---|---|---|---|---|---|
| CUSTOMER_CREDIT | 14 | 12 | 6.40 | 0.00 | 85.70 |
| DRIVER_REASSIGNMENT | 35 | 22 | 3.30 | 100.00 | 62.90 |
| RESTAURANT_CONTACT | 28 | 16 | 1.40 | 100.00 | 57.10 |
| (no intervention) | 276 | 149 | 1.10 |  | 53.99 |
| PRIORITY_DISPATCH | 32 | 15 | -1.00 | 100.00 | 46.90 |

### definition_comparison

| definition | late_rate_pct | late | population |
|---|---|---|---|
| VP Operations: any delivered order after promised ETA (validated population) | 55.58 | 214 | 385 |
| Data Team: delivered orders with non-null actual delivery time (historical dashboard) | 55.44 | 214 | 386 |
| Support Lead: only > 10 min beyond ETA | 22.60 | 87 | 385 |
| Finance: cancelled/refunded excluded (already true in every definition above) | 55.58 | 214 | 385 |
| Sensitivity: back-fill missing delivery time from driver telemetry | 56.12 | 220 | 392 |

### outcome_distribution

| outcome_bucket | orders | share_pct |
|---|---|---|
| delivered_late | 214 | 51.90 |
| delivered_on_time | 171 | 41.50 |
| cancelled | 19 | 4.60 |
| unknown_missing_timestamp | 7 | 1.70 |
| excluded_dq_rule | 1 | 0.20 |

### late_rate_by_traffic

| traffic_bucket | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| high | 106 | 72 | 67.90 | 4.10 | 5.50 |
| low | 95 | 41 | 43.20 | -1.30 | -0.50 |
| medium | 150 | 75 | 50.00 | 0.00 | 1.80 |
| severe | 34 | 26 | 76.50 | 4.60 | 7.50 |

### late_rate_by_weather

| weather_bucket | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| clear | 309 | 161 | 52.10 | 0.60 | 1.80 |
| heavy_rain | 15 | 7 | 46.70 | -0.30 | 2.00 |
| rain | 61 | 46 | 75.40 | 4.60 | 7.60 |

### late_rate_by_distance_band

| distance_band | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| 0-3 km | 4 | 3 | 75.00 | 4.20 | 3.50 |
| 3-6 km | 21 | 8 | 38.10 | -1.30 | -2.40 |
| 6-10 km | 46 | 24 | 52.20 | 0.50 | 0.60 |
| 10-20 km | 311 | 176 | 56.60 | 1.40 | 3.20 |
| 20-50 km | 3 | 3 | 100.00 | 26.30 | 25.10 |

### late_rate_by_hour

| hour_of_day | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| 11 | 17 | 10 | 58.80 | 1.20 | 3.40 |
| 12 | 31 | 16 | 51.60 | 0.50 | 2.30 |
| 13 | 24 | 10 | 41.70 | -0.80 | -1.30 |
| 14 | 20 | 10 | 50.00 | 1.80 | 3.20 |
| 15 | 11 | 8 | 72.70 | 4.60 | 1.50 |
| 16 | 22 | 14 | 63.60 | 2.60 | 4.00 |
| 17 | 39 | 23 | 59.00 | 3.60 | 4.70 |
| 18 | 64 | 40 | 62.50 | 1.50 | 4.80 |
| 19 | 50 | 26 | 52.00 | 0.70 | 1.80 |
| 20 | 52 | 28 | 53.80 | 0.90 | 2.30 |
| 21 | 22 | 7 | 31.80 | -1.60 | 0.20 |
| 22 | 18 | 10 | 55.60 | 1.80 | 0.20 |
| 23 | 15 | 12 | 80.00 | 3.80 | 5.20 |

### late_rate_by_day_of_week

| day_of_week | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| Friday | 56 | 36 | 64.30 | 1.50 | 2.70 |
| Monday | 53 | 26 | 49.10 | -0.10 | 2.80 |
| Saturday | 57 | 36 | 63.20 | 2.40 | 3.50 |
| Sunday | 59 | 27 | 45.80 | -0.40 | 1.60 |
| Thursday | 59 | 33 | 55.90 | 1.20 | 4.20 |
| Tuesday | 51 | 24 | 47.10 | -1.50 | -0.20 |
| Wednesday | 50 | 32 | 64.00 | 2.20 | 4.50 |

### late_rate_by_eta_model_version

| eta_model_version | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| eta-v3.1 | 193 | 109 | 56.50 | 1.80 | 2.80 |
| eta-v3.2 | 192 | 105 | 54.70 | 1.00 | 2.70 |

### late_rate_by_reassignment

| reassigned | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| not reassigned | 363 | 202 | 55.60 | 1.20 | 2.70 |
| reassigned | 22 | 12 | 54.50 | 3.60 | 4.10 |

### top_restaurants_by_late_orders

| restaurant_id | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min | share_of_all_late_pct |
|---|---|---|---|---|---|---|
| R050 | 13 | 8 | 61.50 | 1.20 | 4.50 | 3.70 |
| R031 | 7 | 7 | 100.00 | 4.00 | 5.50 | 3.30 |
| R018 | 8 | 7 | 87.50 | 10.80 | 9.60 | 3.30 |
| R024 | 8 | 7 | 87.50 | 9.00 | 7.60 | 3.30 |
| R011 | 11 | 7 | 63.60 | 4.00 | 2.60 | 3.30 |
| R039 | 6 | 6 | 100.00 | 10.90 | 14.30 | 2.80 |
| R033 | 7 | 6 | 85.70 | 4.60 | 7.20 | 2.80 |
| R046 | 7 | 6 | 85.70 | 4.10 | 5.00 | 2.80 |
| R058 | 8 | 6 | 75.00 | 9.30 | 10.20 | 2.80 |
| R029 | 9 | 6 | 66.70 | 14.30 | 8.90 | 2.80 |

### top_drivers_by_late_rate

| driver_id | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| D054 | 5 | 5 | 100.00 | 19.20 | 13.10 |
| D001 | 8 | 7 | 87.50 | 4.20 | 3.70 |
| D063 | 5 | 4 | 80.00 | 2.60 | 7.30 |
| D076 | 5 | 4 | 80.00 | 5.00 | 7.70 |
| D117 | 5 | 4 | 80.00 | 7.60 | 6.60 |
| D017 | 6 | 4 | 66.70 | 5.40 | 3.70 |
| D018 | 6 | 4 | 66.70 | 2.70 | 2.30 |
| D067 | 6 | 4 | 66.70 | 1.50 | 0.70 |
| D015 | 5 | 3 | 60.00 | 4.30 | 3.30 |
| D041 | 5 | 3 | 60.00 | 3.00 | 1.60 |

### worst_delays

| order_id | restaurant_id | driver_id | promised_eta | actual_delivery_at | delay_min | traffic_bucket | weather_bucket | distance_km_estimate | reassigned_flag | dq_flags |
|---|---|---|---|---|---|---|---|---|---|---|
| O00737 | R027 | D048 | 2026-08-20 21:11:15 | 2026-08-20 21:47:32 | 36.28 | low | clear | 12.51 | False |  |
| O00198 | R016 | D100 | 2026-08-19 18:57:33 | 2026-08-19 19:32:47 | 35.23 | medium | clear | 6.07 | False |  |
| O00303 | R039 | D038 | 2026-08-19 21:33:34 | 2026-08-19 22:06:43 | 33.16 | severe | clear | 45.00 | False |  |
| O01197 | R034 | D118 | 2026-08-17 17:56:18 | 2026-08-17 18:27:54 | 31.61 | high | rain | 18.00 | False |  |
| O00930 | R022 | D120 | 2026-08-15 19:50:13 | 2026-08-15 20:19:42 | 29.48 | high | clear | 10.58 | False |  |
| O00171 | R008 | D076 | 2026-08-17 19:46:24 | 2026-08-17 20:14:45 | 28.35 | severe | clear | 18.00 | True | CX-01 |
| O01470 | R050 | D030 | 2026-08-19 18:23:02 | 2026-08-19 18:50:50 | 27.80 | medium | clear | 10.12 | False |  |
| O00607 | R058 | D060 | 2026-08-15 18:44:06 | 2026-08-15 19:11:44 | 27.64 | medium | rain | 18.00 | False |  |
| O00409 | R018 | D047 | 2026-08-15 18:13:54 | 2026-08-15 18:41:17 | 27.39 | severe | rain | 18.00 | False | CX-03 |
| O00077 | R053 | D108 | 2026-08-16 00:35:21 | 2026-08-16 01:01:54 | 26.54 | high | rain | 9.93 | False |  |

### customer_view_vs_system_view

| ticket_category | tickets | orders_matched | late_share_pct | median_delay_min |
|---|---|---|---|---|
| eta_changed | 11 | 11 | 81.82 | 9.80 |
| status_mismatch | 10 | 10 | 90.00 | 12.10 |
| late_delivery | 9 | 9 | 88.89 | 14.10 |
| restaurant_delay | 8 | 8 | 75.00 | 12.30 |
| driver_not_moving | 6 | 6 | 50.00 | 1.30 |
| ready_but_waiting | 4 | 4 | 100.00 | 14.00 |

### journey_patterns

| pattern | orders |
|---|---|
| late orders | 214 |
| late + support contact | 64 |
| late + intervention | 65 |
| late + support contact + intervention (still late) | 17 |
| support contact + intervention + still > 15 min late (Class 7: the intervention did not work) | 12 |
| support contact + intervention (validated deliveries, the base for the line above) | 19 |
| support contact + NO intervention (any outcome) | 54 |
| cancel attempted in app | 2 |

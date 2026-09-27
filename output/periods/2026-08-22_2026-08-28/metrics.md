# Metrics

| metric_id | metric | category | value | unit | numerator | denominator | population |
|---|---|---|---|---|---|---|---|
| M1 | Late delivery rate (validated population) | outcome | 55.20 | % | 207 | 375 | delivered orders with valid promised_eta + actual_delivery_at, passing chronology rules TS-01/02/03 |
| M1a | Late delivery rate (historical dashboard definition) | outcome | 55.41 | % | 210 | 379 | delivered orders with non-null actual delivery time (Data Team definition, no chronology rules) |
| M1b | Meaningfully late rate (> 10 min) | outcome | 22.13 | % | 83 | 375 | validated population |
| M1c | Late delivery rate (sensitivity: back-fill missing delivery time from driver telemetry) | outcome | 55.01 | % | 214 | 389 | validated population + delivered orders whose missing actual_delivery_at is back-filled from the driver 'delivered' event |
| M2 | Median lateness among late orders | outcome | 7.60 | min | — | 207 | late orders in the validated population |
| M2a | P90 delay across all validated deliveries | outcome | 16.80 | min | — | 375 | validated population |
| M2b | Worst single delay | outcome | 36.90 | min | — | 375 | validated population |
| M3 | Share of lateness accumulated before pickup (vs in transit) | workflow | 98.43 | % | 3230.5 | 3282.2 | late orders with Dispatch estimated_pickup_at (207 orders) |
| M3a | Median pre-pickup overrun on late orders | workflow | 14.40 | min | — | 207 | late orders with dispatch estimates |
| M3b | Median transit overrun on late orders | workflow | -6.10 | min | — | 207 | late orders with dispatch estimates |
| M4 | Support contact rate on late orders | interaction | 30.43 | % | 63 | 207 | late orders (validated population) |
| M4a | Support contact rate on on-time orders | interaction | 7.74 | % | 13 | 168 | on-time orders |
| M4b | Frustrated journeys with no intervention | interaction | 61 | orders | 61 | 78 | all orders with a support contact |
| M4c | Median ETA views per order (late vs on-time) | interaction | 1 vs 1 | views | — | — | validated population |
| M5 | Intervention coverage of delivered orders | intervention | 26.93 | % | 101 | 375 | validated population |
| M5a | Late rate WITH an intervention | intervention | 49.50 | % | 50 | 101 | validated orders with an intervention |
| M5b | Late rate WITHOUT an intervention | intervention | 57.30 | % | 157 | 274 | validated orders without an intervention |
| M5c | Most common intervention type | intervention | DRIVER_REASSIGNMENT (43) | type | 43 | 113 | all interventions |

## Definitions

- **M1 Late delivery rate (validated population)** — late = actual_delivery_at - promised_eta > 0 min. Population: delivered orders with valid promised_eta + actual_delivery_at, passing chronology rules TS-01/02/03. KPI link: PROJECT KPI. Notes: cancelled orders excluded (Finance); delivered orders without a delivery timestamp are 'unknown', not on-time
- **M1a Late delivery rate (historical dashboard definition)** — same formula as M1 on the historical population. Population: delivered orders with non-null actual delivery time (Data Team definition, no chronology rules). KPI link: PROJECT KPI (comparison). Notes: reproduces the leadership claim; differs from M1 only by the chronology-violating orders
- **M1b Meaningfully late rate (> 10 min)** — delay_min > 10. Population: validated population. KPI link: PROJECT KPI (Support Lead definition). 
- **M1c Late delivery rate (sensitivity: back-fill missing delivery time from driver telemetry)** — delay computed on the back-filled timestamp. Population: validated population + delivered orders whose missing actual_delivery_at is back-filled from the driver 'delivered' event. KPI link: PROJECT KPI (sensitivity). Notes: 14 orders back-filled; NOT the published number - needs Fleet Ops to confirm the driver event is authoritative
- **M2 Median lateness among late orders** — median(delay_min | late). Population: late orders in the validated population. KPI link: severity of the KPI. 
- **M2a P90 delay across all validated deliveries** — 90th percentile of delay_min (negative = early). Population: validated population. KPI link: severity of the KPI. 
- **M2b Worst single delay** — max(delay_min). Population: validated population. KPI link: severity of the KPI. 
- **M3 Share of lateness accumulated before pickup (vs in transit)** — delay = (pickup_at - estimated_pickup_at) + ((actual - pickup) - (promised - estimated_pickup)); share = sum(max(pre-pickup overrun,0)) / sum(all positive overruns). Population: late orders with Dispatch estimated_pickup_at (207 orders). KPI link: WHERE delay accumulates -> which stage to fix first. Notes: pre-pickup mixes restaurant prep and driver travel-to-restaurant: no 'arrived at restaurant' event exists to split them
- **M3a Median pre-pickup overrun on late orders** — median(pickup_at - estimated_pickup_at). Population: late orders with dispatch estimates. KPI link: stage diagnosis. 
- **M3b Median transit overrun on late orders** — median((actual - pickup) - (promised - estimated_pickup)). Population: late orders with dispatch estimates. KPI link: stage diagnosis. 
- **M4 Support contact rate on late orders** — order has a support ticket OR a SUPPORT_OPENED app action. Population: late orders (validated population). KPI link: customer impact of the KPI. Notes: on-time comparison: 7.74% of on-time orders had a support contact
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
| dispatch_wait_min | 2.40 | 2.30 | 0.10 |
| pickup_wait_min | 28.40 | 16.90 | 11.50 |
| transit_min | 49.00 | 46.00 | 3.00 |
| total_cycle_min | 81.80 | 66.20 | 15.60 |
| promised_window_min | 75.00 | 72.80 | 2.20 |
| pickup_overrun_min | 14.40 | 2.00 | 12.40 |
| transit_overrun_min | -6.10 | -7.80 | 1.70 |
| eta_revision_min | 10.00 | 4.80 | 5.20 |

### late_orders_by_overrun_stage

| overrun_pattern | late_orders | share_pct |
|---|---|---|
| pre-pickup only | 189 | 91.30 |
| both stages overran | 17 | 8.20 |
| transit only | 1 | 0.50 |

### late_rate_by_intervention_type

| intervention_type | orders | late_orders | median_delay_min | before_promised_eta_pct | late_rate_pct |
|---|---|---|---|---|---|
| (no intervention) | 274 | 157 | 2.20 |  | 57.30 |
| CUSTOMER_CREDIT | 14 | 8 | 0.40 | 0.00 | 57.10 |
| DRIVER_REASSIGNMENT | 38 | 19 | 0.20 | 100.00 | 50.00 |
| RESTAURANT_CONTACT | 31 | 15 | -0.50 | 100.00 | 48.40 |
| PRIORITY_DISPATCH | 18 | 8 | -2.10 | 100.00 | 44.40 |

### definition_comparison

| definition | late_rate_pct | late | population |
|---|---|---|---|
| VP Operations: any delivered order after promised ETA (validated population) | 55.20 | 207 | 375 |
| Data Team: delivered orders with non-null actual delivery time (historical dashboard) | 55.41 | 210 | 379 |
| Support Lead: only > 10 min beyond ETA | 22.13 | 83 | 375 |
| Finance: cancelled/refunded excluded (already true in every definition above) | 55.20 | 207 | 375 |
| Sensitivity: back-fill missing delivery time from driver telemetry | 55.01 | 214 | 389 |

### outcome_distribution

| outcome_bucket | orders | share_pct |
|---|---|---|
| delivered_late | 207 | 50.90 |
| delivered_on_time | 168 | 41.30 |
| cancelled | 14 | 3.40 |
| unknown_missing_timestamp | 14 | 3.40 |
| excluded_dq_rule | 4 | 1.00 |

### late_rate_by_traffic

| traffic_bucket | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| high | 109 | 70 | 64.20 | 3.50 | 4.40 |
| low | 88 | 44 | 50.00 | 0.20 | 2.10 |
| medium | 142 | 70 | 49.30 | -0.50 | 0.70 |
| severe | 36 | 23 | 63.90 | 1.90 | 5.10 |

### late_rate_by_weather

| weather_bucket | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| clear | 297 | 157 | 52.90 | 0.80 | 1.70 |
| heavy_rain | 21 | 15 | 71.40 | 6.80 | 7.50 |
| rain | 57 | 35 | 61.40 | 2.40 | 5.30 |

### late_rate_by_distance_band

| distance_band | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| 0-3 km | 7 | 3 | 42.90 | -2.30 | 0.50 |
| 3-6 km | 11 | 4 | 36.40 | -7.00 | 0.20 |
| 6-10 km | 49 | 28 | 57.10 | 2.30 | 2.60 |
| 10-20 km | 308 | 172 | 55.80 | 1.60 | 2.70 |

### late_rate_by_hour

| hour_of_day | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| 11 | 20 | 12 | 60.00 | 1.60 | 2.70 |
| 12 | 29 | 18 | 62.10 | 2.00 | 4.10 |
| 13 | 26 | 14 | 53.80 | 1.40 | 3.60 |
| 14 | 16 | 10 | 62.50 | 3.10 | 3.30 |
| 15 | 13 | 9 | 69.20 | 1.80 | 5.80 |
| 16 | 16 | 9 | 56.20 | 1.60 | 2.60 |
| 17 | 37 | 21 | 56.80 | 3.50 | 3.70 |
| 18 | 50 | 29 | 58.00 | 3.80 | 3.00 |
| 19 | 56 | 28 | 50.00 | 0.10 | 1.70 |
| 20 | 40 | 23 | 57.50 | 0.80 | 1.90 |
| 21 | 24 | 10 | 41.70 | -4.10 | 0.20 |
| 22 | 33 | 15 | 45.50 | -1.90 | 0.10 |
| 23 | 15 | 9 | 60.00 | 3.80 | 3.50 |

### late_rate_by_day_of_week

| day_of_week | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| Friday | 52 | 25 | 48.10 | -0.80 | 2.20 |
| Monday | 51 | 33 | 64.70 | 2.10 | 2.80 |
| Saturday | 59 | 38 | 64.40 | 3.70 | 5.60 |
| Sunday | 54 | 29 | 53.70 | 1.50 | 2.10 |
| Thursday | 52 | 26 | 50.00 | -0.30 | 3.10 |
| Tuesday | 45 | 23 | 51.10 | 0.40 | 0.90 |
| Wednesday | 62 | 33 | 53.20 | 1.10 | 0.90 |

### late_rate_by_eta_model_version

| eta_model_version | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| eta-v3.1 | 197 | 110 | 55.80 | 1.20 | 3.00 |
| eta-v3.2 | 178 | 97 | 54.50 | 1.70 | 2.10 |

### late_rate_by_reassignment

| reassigned | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| not reassigned | 357 | 198 | 55.50 | 1.50 | 2.60 |
| reassigned | 18 | 9 | 50.00 | -0.10 | 0.80 |

### top_restaurants_by_late_orders

| restaurant_id | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min | share_of_all_late_pct |
|---|---|---|---|---|---|---|
| R020 | 14 | 8 | 57.10 | 0.60 | 5.80 | 3.90 |
| R055 | 10 | 7 | 70.00 | 8.30 | 9.70 | 3.40 |
| R002 | 11 | 7 | 63.60 | 6.20 | 5.00 | 3.40 |
| R041 | 7 | 6 | 85.70 | 10.70 | 9.40 | 2.90 |
| R051 | 7 | 6 | 85.70 | 6.80 | 8.50 | 2.90 |
| R011 | 8 | 6 | 75.00 | 3.80 | 5.10 | 2.90 |
| R042 | 8 | 6 | 75.00 | 4.50 | 5.20 | 2.90 |
| R052 | 8 | 6 | 75.00 | 5.90 | 4.80 | 2.90 |
| R017 | 9 | 6 | 66.70 | 6.50 | 2.60 | 2.90 |
| R023 | 6 | 5 | 83.30 | 2.20 | 8.20 | 2.40 |

### top_drivers_by_late_rate

| driver_id | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| D046 | 5 | 5 | 100.00 | 9.00 | 10.20 |
| D076 | 7 | 6 | 85.70 | 11.80 | 9.50 |
| D043 | 6 | 5 | 83.30 | 8.80 | 5.80 |
| D087 | 6 | 5 | 83.30 | 9.30 | 9.30 |
| D015 | 5 | 4 | 80.00 | 1.50 | 8.70 |
| D016 | 5 | 4 | 80.00 | 20.70 | 15.00 |
| D031 | 5 | 4 | 80.00 | 10.70 | 10.80 |
| D116 | 5 | 4 | 80.00 | 8.30 | 7.50 |
| D054 | 7 | 5 | 71.40 | 4.20 | 4.80 |
| D088 | 6 | 4 | 66.70 | 7.60 | 4.20 |

### worst_delays

| order_id | restaurant_id | driver_id | promised_eta | actual_delivery_at | delay_min | traffic_bucket | weather_bucket | distance_km_estimate | reassigned_flag | dq_flags |
|---|---|---|---|---|---|---|---|---|---|---|
| O01403 | R014 | D099 | 2026-08-24 18:47:36 | 2026-08-24 19:24:32 | 36.93 | medium | heavy_rain | 18.00 | False |  |
| O00211 | R016 | D051 | 2026-08-22 20:24:31 | 2026-08-22 20:56:54 | 32.38 | low | clear | 8.34 | False |  |
| O01235 | R032 | D098 | 2026-08-28 14:36:17 | 2026-08-28 15:08:17 | 32.00 | medium | heavy_rain | 17.85 | False |  |
| O00977 | R051 | D016 | 2026-08-27 13:33:32 | 2026-08-27 14:05:27 | 31.92 | high | clear | 15.02 | False |  |
| O00995 | R020 | D040 | 2026-08-22 18:45:48 | 2026-08-22 19:17:31 | 31.72 | low | clear | 18.00 | False |  |
| O00012 | R008 | D094 | 2026-08-22 13:25:02 | 2026-08-22 13:55:10 | 30.13 | high | clear | 5.26 | False |  |
| O01144 | R055 | D017 | 2026-08-26 23:21:18 | 2026-08-26 23:51:26 | 30.13 | high | rain | 18.00 | False |  |
| O00706 | R035 | D020 | 2026-08-22 18:49:47 | 2026-08-22 19:19:23 | 29.59 | severe | rain | 12.71 | False |  |
| O00169 | R055 | D064 | 2026-08-22 16:35:43 | 2026-08-22 17:04:40 | 28.95 | high | rain | 8.20 | False |  |
| O00047 | R011 | D111 | 2026-08-22 16:45:39 | 2026-08-22 17:13:46 | 28.11 | high | rain | 17.70 | False |  |

### customer_view_vs_system_view

| ticket_category | tickets | orders_matched | late_share_pct | median_delay_min |
|---|---|---|---|---|
| restaurant_delay | 12 | 12 | 58.33 | 7.50 |
| eta_changed | 10 | 9 | 75.00 | 10.50 |
| ready_but_waiting | 10 | 10 | 80.00 | 7.80 |
| driver_not_moving | 9 | 9 | 77.78 | 25.00 |
| late_delivery | 7 | 6 | 66.67 | 9.90 |
| status_mismatch | 7 | 6 | 100.00 | 13.50 |

### journey_patterns

| pattern | orders |
|---|---|
| late orders | 207 |
| late + support contact | 63 |
| late + intervention | 50 |
| late + support contact + intervention (still late) | 13 |
| support contact + intervention + still > 15 min late (Class 7: the intervention did not work) | 5 |
| support contact + intervention (validated deliveries, the base for the line above) | 16 |
| support contact + NO intervention (any outcome) | 61 |
| cancel attempted in app | 2 |

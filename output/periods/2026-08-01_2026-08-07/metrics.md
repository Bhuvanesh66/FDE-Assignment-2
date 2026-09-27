# Metrics

| metric_id | metric | category | value | unit | numerator | denominator | population |
|---|---|---|---|---|---|---|---|
| M1 | Late delivery rate (validated population) | outcome | 54.49 | % | 188 | 345 | delivered orders with valid promised_eta + actual_delivery_at, passing chronology rules TS-01/02/03 |
| M1a | Late delivery rate (historical dashboard definition) | outcome | 54.34 | % | 188 | 346 | delivered orders with non-null actual delivery time (Data Team definition, no chronology rules) |
| M1b | Meaningfully late rate (> 10 min) | outcome | 21.74 | % | 75 | 345 | validated population |
| M1c | Late delivery rate (sensitivity: back-fill missing delivery time from driver telemetry) | outcome | 54.90 | % | 196 | 357 | validated population + delivered orders whose missing actual_delivery_at is back-filled from the driver 'delivered' event |
| M2 | Median lateness among late orders | outcome | 8.00 | min | — | 188 | late orders in the validated population |
| M2a | P90 delay across all validated deliveries | outcome | 17.20 | min | — | 345 | validated population |
| M2b | Worst single delay | outcome | 29.80 | min | — | 345 | validated population |
| M3 | Share of lateness accumulated before pickup (vs in transit) | workflow | 98.49 | % | 2836.5 | 2880.1 | late orders with Dispatch estimated_pickup_at (188 orders) |
| M3a | Median pre-pickup overrun on late orders | workflow | 13.80 | min | — | 188 | late orders with dispatch estimates |
| M3b | Median transit overrun on late orders | workflow | -5.80 | min | — | 188 | late orders with dispatch estimates |
| M4 | Support contact rate on late orders | interaction | 32.45 | % | 61 | 188 | late orders (validated population) |
| M4a | Support contact rate on on-time orders | interaction | 3.82 | % | 6 | 157 | on-time orders |
| M4b | Frustrated journeys with no intervention | interaction | 46 | orders | 46 | 67 | all orders with a support contact |
| M4c | Median ETA views per order (late vs on-time) | interaction | 2 vs 2 | views | — | — | validated population |
| M5 | Intervention coverage of delivered orders | intervention | 24.93 | % | 86 | 345 | validated population |
| M5a | Late rate WITH an intervention | intervention | 55.81 | % | 48 | 86 | validated orders with an intervention |
| M5b | Late rate WITHOUT an intervention | intervention | 54.05 | % | 140 | 259 | validated orders without an intervention |
| M5c | Most common intervention type | intervention | DRIVER_REASSIGNMENT (32) | type | 32 | 89 | all interventions |

## Definitions

- **M1 Late delivery rate (validated population)** — late = actual_delivery_at - promised_eta > 0 min. Population: delivered orders with valid promised_eta + actual_delivery_at, passing chronology rules TS-01/02/03. KPI link: PROJECT KPI. Notes: cancelled orders excluded (Finance); delivered orders without a delivery timestamp are 'unknown', not on-time
- **M1a Late delivery rate (historical dashboard definition)** — same formula as M1 on the historical population. Population: delivered orders with non-null actual delivery time (Data Team definition, no chronology rules). KPI link: PROJECT KPI (comparison). Notes: reproduces the leadership claim; differs from M1 only by the chronology-violating orders
- **M1b Meaningfully late rate (> 10 min)** — delay_min > 10. Population: validated population. KPI link: PROJECT KPI (Support Lead definition). 
- **M1c Late delivery rate (sensitivity: back-fill missing delivery time from driver telemetry)** — delay computed on the back-filled timestamp. Population: validated population + delivered orders whose missing actual_delivery_at is back-filled from the driver 'delivered' event. KPI link: PROJECT KPI (sensitivity). Notes: 12 orders back-filled; NOT the published number - needs Fleet Ops to confirm the driver event is authoritative
- **M2 Median lateness among late orders** — median(delay_min | late). Population: late orders in the validated population. KPI link: severity of the KPI. 
- **M2a P90 delay across all validated deliveries** — 90th percentile of delay_min (negative = early). Population: validated population. KPI link: severity of the KPI. 
- **M2b Worst single delay** — max(delay_min). Population: validated population. KPI link: severity of the KPI. 
- **M3 Share of lateness accumulated before pickup (vs in transit)** — delay = (pickup_at - estimated_pickup_at) + ((actual - pickup) - (promised - estimated_pickup)); share = sum(max(pre-pickup overrun,0)) / sum(all positive overruns). Population: late orders with Dispatch estimated_pickup_at (188 orders). KPI link: WHERE delay accumulates -> which stage to fix first. Notes: pre-pickup mixes restaurant prep and driver travel-to-restaurant: no 'arrived at restaurant' event exists to split them
- **M3a Median pre-pickup overrun on late orders** — median(pickup_at - estimated_pickup_at). Population: late orders with dispatch estimates. KPI link: stage diagnosis. 
- **M3b Median transit overrun on late orders** — median((actual - pickup) - (promised - estimated_pickup)). Population: late orders with dispatch estimates. KPI link: stage diagnosis. 
- **M4 Support contact rate on late orders** — order has a support ticket OR a SUPPORT_OPENED app action. Population: late orders (validated population). KPI link: customer impact of the KPI. Notes: on-time comparison: 3.82% of on-time orders had a support contact
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
| dispatch_wait_min | 2.30 | 2.40 | -0.10 |
| pickup_wait_min | 28.40 | 16.40 | 12.00 |
| transit_min | 48.80 | 45.40 | 3.40 |
| total_cycle_min | 81.30 | 64.30 | 17.00 |
| promised_window_min | 74.00 | 72.80 | 1.20 |
| pickup_overrun_min | 13.80 | 1.20 | 12.60 |
| transit_overrun_min | -5.80 | -8.20 | 2.40 |
| eta_revision_min | 10.00 | 4.50 | 5.50 |

### late_orders_by_overrun_stage

| overrun_pattern | late_orders | share_pct |
|---|---|---|
| pre-pickup only | 170 | 90.40 |
| both stages overran | 16 | 8.50 |
| transit only | 2 | 1.10 |

### late_rate_by_intervention_type

| intervention_type | orders | late_orders | median_delay_min | before_promised_eta_pct | late_rate_pct |
|---|---|---|---|---|---|
| CUSTOMER_CREDIT | 17 | 11 | 2.70 | 0.00 | 64.70 |
| DRIVER_REASSIGNMENT | 32 | 19 | 1.90 | 100.00 | 59.40 |
| PRIORITY_DISPATCH | 14 | 8 | 3.40 | 100.00 | 57.10 |
| (no intervention) | 259 | 140 | 0.70 |  | 54.05 |
| RESTAURANT_CONTACT | 23 | 10 | -2.10 | 100.00 | 43.50 |

### definition_comparison

| definition | late_rate_pct | late | population |
|---|---|---|---|
| VP Operations: any delivered order after promised ETA (validated population) | 54.49 | 188 | 345 |
| Data Team: delivered orders with non-null actual delivery time (historical dashboard) | 54.34 | 188 | 346 |
| Support Lead: only > 10 min beyond ETA | 21.74 | 75 | 345 |
| Finance: cancelled/refunded excluded (already true in every definition above) | 54.49 | 188 | 345 |
| Sensitivity: back-fill missing delivery time from driver telemetry | 54.90 | 196 | 357 |

### outcome_distribution

| outcome_bucket | orders | share_pct |
|---|---|---|
| delivered_late | 188 | 50.50 |
| delivered_on_time | 157 | 42.20 |
| cancelled | 14 | 3.80 |
| unknown_missing_timestamp | 12 | 3.20 |
| excluded_dq_rule | 1 | 0.30 |

### late_rate_by_traffic

| traffic_bucket | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| high | 100 | 62 | 62.00 | 2.40 | 3.40 |
| low | 81 | 41 | 50.60 | 0.30 | 1.30 |
| medium | 142 | 69 | 48.60 | -0.40 | 1.30 |
| severe | 22 | 16 | 72.70 | 6.40 | 7.80 |

### late_rate_by_weather

| weather_bucket | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| clear | 276 | 146 | 52.90 | 0.70 | 1.70 |
| heavy_rain | 16 | 14 | 87.50 | 9.10 | 10.00 |
| rain | 53 | 28 | 52.80 | 0.50 | 3.20 |

### late_rate_by_distance_band

| distance_band | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| 0-3 km | 9 | 7 | 77.80 | 6.10 | 6.50 |
| 3-6 km | 18 | 9 | 50.00 | -0.50 | 1.00 |
| 6-10 km | 52 | 30 | 57.70 | 1.10 | 1.70 |
| 10-20 km | 266 | 142 | 53.40 | 1.20 | 2.40 |

### late_rate_by_hour

| hour_of_day | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| 11 | 29 | 17 | 58.60 | 4.30 | 2.20 |
| 12 | 25 | 13 | 52.00 | 0.10 | 1.60 |
| 13 | 22 | 12 | 54.50 | 1.80 | 2.00 |
| 14 | 16 | 9 | 56.20 | 1.10 | 2.70 |
| 15 | 17 | 10 | 58.80 | 6.30 | 3.50 |
| 16 | 17 | 10 | 58.80 | 0.70 | 5.30 |
| 17 | 20 | 11 | 55.00 | 1.00 | 1.10 |
| 18 | 48 | 29 | 60.40 | 4.00 | 4.40 |
| 19 | 48 | 24 | 50.00 | -0.00 | 2.40 |
| 20 | 45 | 23 | 51.10 | 0.20 | 1.10 |
| 21 | 25 | 12 | 48.00 | -1.80 | -0.30 |
| 22 | 17 | 9 | 52.90 | 1.40 | 1.30 |
| 23 | 16 | 9 | 56.20 | 4.00 | 2.50 |

### late_rate_by_day_of_week

| day_of_week | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| Friday | 43 | 22 | 51.20 | 0.20 | 2.80 |
| Monday | 55 | 32 | 58.20 | 2.80 | 2.60 |
| Saturday | 49 | 25 | 51.00 | 0.20 | 1.80 |
| Sunday | 40 | 22 | 55.00 | 1.10 | 1.50 |
| Thursday | 47 | 22 | 46.80 | -0.40 | 2.70 |
| Tuesday | 61 | 37 | 60.70 | 3.50 | 2.70 |
| Wednesday | 50 | 28 | 56.00 | 1.10 | 1.70 |

### late_rate_by_eta_model_version

| eta_model_version | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| eta-v3.1 | 171 | 86 | 50.30 | 0.30 | 1.70 |
| eta-v3.2 | 174 | 102 | 58.60 | 2.10 | 2.80 |

### late_rate_by_reassignment

| reassigned | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| not reassigned | 319 | 171 | 53.60 | 1.00 | 2.00 |
| reassigned | 26 | 17 | 65.40 | 5.00 | 6.10 |

### top_restaurants_by_late_orders

| restaurant_id | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min | share_of_all_late_pct |
|---|---|---|---|---|---|---|
| R004 | 10 | 7 | 70.00 | 5.40 | 7.10 | 3.70 |
| R054 | 7 | 6 | 85.70 | 10.60 | 7.30 | 3.20 |
| R057 | 9 | 6 | 66.70 | 1.00 | 3.70 | 3.20 |
| R034 | 10 | 6 | 60.00 | 1.70 | 2.30 | 3.20 |
| R044 | 6 | 5 | 83.30 | 5.80 | 8.00 | 2.70 |
| R047 | 6 | 5 | 83.30 | 9.00 | 9.60 | 2.70 |
| R058 | 6 | 5 | 83.30 | 10.00 | 8.30 | 2.70 |
| R007 | 7 | 5 | 71.40 | 1.40 | 0.80 | 2.70 |
| R018 | 7 | 5 | 71.40 | 4.00 | 6.70 | 2.70 |
| R045 | 7 | 5 | 71.40 | 15.50 | 11.40 | 2.70 |

### top_drivers_by_late_rate

| driver_id | orders | late_orders | late_rate_pct | median_delay_min | mean_delay_min |
|---|---|---|---|---|---|
| D031 | 5 | 5 | 100.00 | 8.00 | 9.50 |
| D117 | 5 | 4 | 80.00 | 5.10 | 5.90 |
| D073 | 7 | 5 | 71.40 | 0.50 | 6.10 |
| D003 | 6 | 4 | 66.70 | 7.40 | 5.90 |
| D008 | 6 | 4 | 66.70 | 6.80 | 7.10 |
| D063 | 6 | 4 | 66.70 | 3.90 | 2.90 |
| D017 | 5 | 3 | 60.00 | 1.00 | -2.50 |
| D068 | 5 | 3 | 60.00 | 3.30 | -2.70 |
| D081 | 5 | 3 | 60.00 | 8.70 | 4.60 |
| D083 | 5 | 3 | 60.00 | 4.00 | 3.70 |

### worst_delays

| order_id | restaurant_id | driver_id | promised_eta | actual_delivery_at | delay_min | traffic_bucket | weather_bucket | distance_km_estimate | reassigned_flag | dq_flags |
|---|---|---|---|---|---|---|---|---|---|---|
| O01268 | R045 | D010 | 2026-08-06 20:11:36 | 2026-08-06 20:41:25 | 29.82 | medium | heavy_rain | 18.00 | False |  |
| O00808 | R032 | D071 | 2026-08-01 18:08:48 | 2026-08-01 18:37:12 | 28.40 | low | clear | 18.00 | False |  |
| O00874 | R018 | D008 | 2026-08-06 20:51:29 | 2026-08-06 21:19:29 | 28.01 | medium | clear | 17.47 | False |  |
| O00613 | R023 | D065 | 2026-08-01 20:09:11 | 2026-08-01 20:36:22 | 27.18 | high | rain | 10.81 | False |  |
| O00730 | R036 | D052 | 2026-08-04 13:03:24 | 2026-08-04 13:30:31 | 27.12 | severe | clear | 18.00 | False |  |
| O00565 | R023 | D073 | 2026-08-07 17:27:24 | 2026-08-07 17:53:38 | 26.24 | severe | clear | 18.00 | False |  |
| O00992 | R053 | D022 | 2026-08-04 13:54:16 | 2026-08-04 14:19:38 | 25.37 | high | clear | 4.42 | False |  |
| O00393 | R054 | D109 | 2026-08-08 00:46:06 | 2026-08-08 01:10:59 | 24.90 | medium | rain | 18.00 | False |  |
| O01307 | R047 | D097 | 2026-08-07 21:08:04 | 2026-08-07 21:31:40 | 23.60 | medium | clear | 7.75 | False |  |
| O01233 | R012 | D096 | 2026-08-05 19:49:47 | 2026-08-05 20:13:10 | 23.39 | high | clear | 4.18 | True | CX-01;CX-03 |

### customer_view_vs_system_view

| ticket_category | tickets | orders_matched | late_share_pct | median_delay_min |
|---|---|---|---|---|
| eta_changed | 9 | 9 | 88.89 | 7.60 |
| restaurant_delay | 8 | 8 | 75.00 | 11.30 |
| late_delivery | 8 | 8 | 87.50 | 12.80 |
| ready_but_waiting | 7 | 7 | 100.00 | 12.20 |
| status_mismatch | 7 | 7 | 85.71 | 13.00 |
| driver_not_moving | 5 | 5 | 80.00 | 14.80 |
| eta_issue | 1 | 1 | 100.00 | 5.40 |

### journey_patterns

| pattern | orders |
|---|---|
| late orders | 188 |
| late + support contact | 61 |
| late + intervention | 48 |
| late + support contact + intervention (still late) | 20 |
| support contact + intervention + still > 15 min late (Class 7: the intervention did not work) | 6 |
| support contact + intervention (validated deliveries, the base for the line above) | 21 |
| support contact + NO intervention (any outcome) | 46 |
| cancel attempted in app | 5 |

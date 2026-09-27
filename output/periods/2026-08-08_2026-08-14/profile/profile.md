# Data profile (raw, before any cleaning)

| dataset | rows | columns | key | duplicate_key_rows | exact_duplicate_rows | notes |
|---|---|---|---|---|---|---|
| orders | 410 | 13 | order_id | 1 | 0 | 1 rows share an existing order_id (grain is not one row per order_id) |
| restaurants | 60 | 6 | restaurant_id | 0 | 0 | - |
| drivers | 120 | 4 | driver_id | 0 | 0 | - |
| customers | 900 | 3 | customer_id | 0 | 0 | - |
| tickets | 202 | 5 | ticket_id | 1 | 1 | 1 rows share an existing ticket_id (grain is not one row per ticket_id); 1 rows are exact duplicates |
| restaurant_status | 502 | 4 |  | 0 | 2 | 2 rows are exact duplicates |
| app_actions | 2365 | 6 | action_id | 0 | 0 | - |
| interventions | 430 | 6 | intervention_id | 0 | 0 | - |
| order_outcomes_ref | 1600 | 6 | order_id | 0 | 0 | - |
| driver_events | 10035 | 6 |  | 0 | 0 | - |
| weather_obs | 192 | 3 | hour | 0 | 0 | - |
| dispatch | 1600 | 9 | order_id | 0 | 0 | - |

## orders  (410 rows)

| column | kind | non_null | null_% | distinct | padded | detail |
|---|---|---|---|---|---|---|
| order_id | id | 410 | 0.00 | 409 | 0 | layouts={'a99999': 410} |
| customer_id | id | 410 | 0.00 | 329 | 0 | layouts={'a9999': 410} |
| restaurant_id | id | 410 | 0.00 | 60 | 0 | layouts={'a999': 410} |
| driver_id | id | 410 | 0.00 | 115 | 0 | layouts={'a999': 410} |
| city | category | 410 | 0.00 | 1 | 0 | Bengaluru=410 |
| created_at | timestamp | 410 | 0.00 | 386 | 0 | 2026-08-08T11:06:00 → 2026-08-14T23:46:00; unparseable=0; layouts={'9999-99-99a99:99:99': 410} |
| promised_eta | timestamp | 410 | 0.00 | 407 | 0 | 2026-08-08T12:14:29.392287 → 2026-08-15T01:08:18; unparseable=0; layouts={'9999-99-99a99:99:99': 221, '9999-99-99a99:99:99.999999': 189} |
| pickup_at | timestamp | 410 | 0.00 | 409 | 0 | 2026-08-08T11:17:22.235428 → 2026-08-15T00:10:22.794975; unparseable=0; layouts={'9999-99-99a99:99:99.999999': 410} |
| actual_delivery_at | timestamp | 385 | 6.10 | 384 | 0 | 2026-08-08T12:03:14.031896 → 2026-08-15T01:13:05.140527; unparseable=0; layouts={'9999-99-99a99:99:99.999999': 385} |
| final_status | category | 410 | 0.00 | 3 | 0 | delivered=387, cancelled=21, Delivered=2 |
| distance_km_estimate | numeric | 410 | 0.00 | 185 | 0 | min=0.5 p50=18.0 max=18.0 |
| traffic_bucket | category | 410 | 0.00 | 5 | 0 | medium=164, high=111, low=100, severe=34, HIGH=1 |
| weather_bucket | category | 410 | 0.00 | 3 | 0 | clear=325, rain=62, heavy_rain=23 |

## restaurants  (60 rows)

| column | kind | non_null | null_% | distinct | padded | detail |
|---|---|---|---|---|---|---|
| restaurant_id | id | 60 | 0.00 | 60 | 0 | layouts={'a999': 60} |
| restaurant_name | text | 60 | 0.00 | 60 | 0 | Restaurant 001=1, Restaurant 002=1, Restaurant 003=1, Restaurant 004=1, Restaurant 005=1, Restaurant 006=1, Restaurant 007=1, Restaurant 008=1 |
| cuisine | category | 60 | 0.00 | 8 | 0 | South Indian=10, Cafe=10, North Indian=8, Biryani=8, Burgers=7, Chinese=7, Pizza=6, Desserts=4 |
| lat | numeric | 60 | 0.00 | 60 | 0 | min=12.739 p50=12.9572 max=95.12 |
| lon | numeric | 60 | 0.00 | 60 | 0 | min=77.3858 p50=77.596 max=190.33 |
| manual_status_updates | numeric | 60 | 0.00 | 2 | 0 | min=0.0 p50=0.0 max=1.0 |

## drivers  (120 rows)

| column | kind | non_null | null_% | distinct | padded | detail |
|---|---|---|---|---|---|---|
| driver_id | id | 120 | 0.00 | 120 | 0 | layouts={'a999': 120} |
| rating | numeric | 120 | 0.00 | 64 | 0 | min=3.76 p50=4.53 max=5.0 |
| vehicle_type | category | 120 | 0.00 | 3 | 0 | bike=69, scooter=40, ebike=11 |
| experience_months | numeric | 120 | 0.00 | 43 | 0 | min=1.0 p50=19.0 max=83.0 |

## customers  (900 rows)

| column | kind | non_null | null_% | distinct | padded | detail |
|---|---|---|---|---|---|---|
| customer_id | id | 900 | 0.00 | 900 | 0 | layouts={'a9999': 900} |
| lat | numeric | 900 | 0.00 | 897 | 0 | min=12.6796 p50=12.9763 max=13.249 |
| lon | numeric | 900 | 0.00 | 899 | 0 | min=77.3245 p50=77.5986 max=77.9508 |

## tickets  (202 rows)

| column | kind | non_null | null_% | distinct | padded | detail |
|---|---|---|---|---|---|---|
| ticket_id | id | 202 | 0.00 | 201 | 0 | layouts={'a99999': 202} |
| order_id | id | 199 | 1.49 | 198 | 0 | layouts={'a99999': 199} |
| created_at | timestamp | 202 | 0.00 | 200 | 0 | 2026-08-01T11:39:00 → 2026-08-28T20:43:00; unparseable=0; layouts={'9999-99-99a99:99:99': 202} |
| category | category | 202 | 0.00 | 8 | 0 | late_delivery=39, eta_changed=37, restaurant_delay=37, ready_but_waiting=33, status_mismatch=29, driver_not_moving=25, Late Delivery=1, ETA issue=1 |
| customer_message | category | 202 | 0.00 | 6 | 0 | My order is already past the promised time.=39, The ETA keeps changing and the food is still not here.=37, Restaurant says they are still preparing my order.=37, Restaurant says food is ready but no rider has picked it up.=33, The app says picking up but the restaurant says it is ready.=29, The rider has not moved for 15 minutes.=27 |

## restaurant_status  (502 rows)

| column | kind | non_null | null_% | distinct | padded | detail |
|---|---|---|---|---|---|---|
| order_id | id | 502 | 0.00 | 500 | 0 | layouts={'a99999': 502} |
| restaurant_id | id | 502 | 0.00 | 60 | 0 | layouts={'a999': 502} |
| status | category | 502 | 0.00 | 7 | 0 | preparing=171, handed_off=168, ready=159, READY=1, Ready=1, handoff=1, unknown=1 |
| last_updated_at | timestamp | 502 | 0.00 | 492 | 0 | 2026-08-01T11:22:00 → 2026-08-28T23:43:00; unparseable=0; layouts={'9999-99-99a99:99:99': 502} |

## app_actions  (2365 rows)

| column | kind | non_null | null_% | distinct | padded | detail |
|---|---|---|---|---|---|---|
| action_id | id | 2365 | 0.00 | 2365 | 0 | layouts={'aaa-99999': 2365} |
| order_id | id | 2365 | 0.00 | 1100 | 0 | layouts={'a99999': 2365} |
| customer_id | id | 2365 | 0.00 | 608 | 0 | layouts={'a9999': 2365} |
| action_type | category | 2365 | 0.00 | 3 | 0 | ETA_VIEWED=2217, SUPPORT_OPENED=138, CANCEL_ATTEMPTED=10 |
| action_at | timestamp | 2365 | 0.00 | 2177 | 0 | 2026-08-01T11:07:00 → 2026-08-28T23:56:00; unparseable=0; layouts={'9999-99-99a99:99:99': 2292, '9999-99-99a99:99:99.999999': 73} |
| channel | category | 2365 | 0.00 | 1 | 0 | mobile_app=2365 |

## interventions  (430 rows)

| column | kind | non_null | null_% | distinct | padded | detail |
|---|---|---|---|---|---|---|
| intervention_id | id | 430 | 0.00 | 430 | 0 | layouts={'aaa-99999': 430} |
| order_id | id | 430 | 0.00 | 430 | 0 | layouts={'a99999': 430} |
| intervention_type | category | 430 | 0.00 | 4 | 0 | DRIVER_REASSIGNMENT=155, RESTAURANT_CONTACT=116, PRIORITY_DISPATCH=95, CUSTOMER_CREDIT=64 |
| intervention_at | timestamp | 430 | 0.00 | 425 | 0 | 2026-08-01T11:39:00 → 2026-08-28T23:33:48; unparseable=0; layouts={'9999-99-99a99:99:99': 408, '9999-99-99a99:99:99.999999': 22} |
| initiated_by | category | 430 | 0.00 | 3 | 0 | support=180, dispatch=155, operations=95 |
| reason | category | 430 | 0.00 | 12 | 0 | slow_progress=58, driver_unavailable=51, capacity_rebalance=46, customer_escalation=40, status_stale=38, prep_delay=38, late_risk=36, vip_customer=33 |

## order_outcomes_ref  (1600 rows)

| column | kind | non_null | null_% | distinct | padded | detail |
|---|---|---|---|---|---|---|
| order_id | id | 1600 | 0.00 | 1600 | 0 | layouts={'a99999': 1600} |
| final_status_norm | category | 1600 | 0.00 | 2 | 0 | delivered=1532, cancelled=68 |
| delivered_flag | numeric | 1600 | 0.00 | 2 | 0 | min=0.0 p50=1.0 max=1.0 |
| late_flag | numeric | 1495 | 6.56 | 2 | 0 | min=0.0 p50=1.0 max=1.0 |
| delay_min | numeric | 1495 | 6.56 | 1224 | 0 | min=-22.15 p50=1.41 max=87.35 |
| outcome_bucket | category | 1600 | 0.00 | 4 | 0 | delivered_late=843, delivered_on_time=652, cancelled=68, unknown=37 |

## driver_events  (10035 rows)

| column | kind | non_null | null_% | distinct | padded | detail |
|---|---|---|---|---|---|---|
| driver_id | id | 10035 | 0.00 | 120 | 0 | layouts={'a999': 10035} |
| order_id | id | 10035 | 0.00 | 1600 | 0 | layouts={'a99999': 10035} |
| type | category | 10035 | 0.00 | 4 | 0 | gps_ping=5371, assigned=1600, picked_up=1532, delivered=1532 |
| timestamp | timestamp | 10035 | 0.00 | 10035 | 0 | 2026-08-01T11:03:07.731329 → 2026-08-29T00:50:53.383274; unparseable=0; layouts={'9999-99-99a99:99:99.999999': 10035} |
| lat | numeric | 5371 | 46.48 | 5288 | 0 | min=12.7441 p50=12.97 max=81.4469 |
| lon | numeric | 5371 | 46.48 | 5293 | 0 | min=77.3665 p50=77.602 max=171.5392 |

## weather_obs  (192 rows)

| column | kind | non_null | null_% | distinct | padded | detail |
|---|---|---|---|---|---|---|
| hour | text | 192 | 0.00 | 192 | 0 | 2026-08-08 00:00:00=1, 2026-08-08 01:00:00=1, 2026-08-08 02:00:00=1, 2026-08-08 03:00:00=1, 2026-08-08 04:00:00=1, 2026-08-08 05:00:00=1, 2026-08-08 06:00:00=1, 2026-08-08 07:00:00=1 |
| precipitation_mm | numeric | 192 | 0.00 | 14 | 0 | min=0.0 p50=0.0 max=3.2 |
| rain_mm | numeric | 192 | 0.00 | 14 | 0 | min=0.0 p50=0.0 max=3.2 |

## dispatch  (1600 rows)

| column | kind | non_null | null_% | distinct | padded | detail |
|---|---|---|---|---|---|---|
| assigned_at | timestamp | 1600 | 0.00 | 1600 | 0 | 2026-08-01T11:03:07.731329 → 2026-08-28T23:34:06.081673; unparseable=0; layouts={'9999-99-99a99:99:99.999999': 1600} |
| current_delivery_eta | timestamp | 1600 | 0.00 | 1600 | 0 | 2026-08-01T12:17:48 → 2026-08-29T00:53:27.108992; unparseable=0; layouts={'9999-99-99a99:99:99.999999': 1230, '9999-99-99a99:99:99': 370} |
| dispatch_status | category | 1600 | 0.00 | 2 | 0 | completed=1532, cancelled=68 |
| driver_id | id | 1600 | 0.00 | 120 | 0 | layouts={'a999': 1600} |
| estimated_pickup_at | timestamp | 1600 | 0.00 | 1527 | 0 | 2026-08-01T11:20:00 → 2026-08-28T23:51:00; unparseable=0; layouts={'9999-99-99a99:99:99': 1600} |
| eta_model_version | category | 1600 | 0.00 | 2 | 0 | eta-v3.2=800, eta-v3.1=800 |
| order_id | id | 1600 | 0.00 | 1600 | 0 | layouts={'a99999': 1600} |
| original_driver_id | id | 1600 | 0.00 | 120 | 0 | layouts={'a999': 1600} |
| reassigned_at | timestamp | 95 | 94.06 | 95 | 0 | 2026-08-01T11:35:17.515941 → 2026-08-28T17:32:01.398186; unparseable=0; layouts={'9999-99-99a99:99:99.999999': 95} |

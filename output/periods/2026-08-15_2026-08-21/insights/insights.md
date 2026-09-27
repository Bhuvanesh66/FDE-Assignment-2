# Decision layer — beyond the classroom

Transparent, non-ML analyses that turn the model into actions the client can take now. Every number is recomputed on each run.

## D1 · A proactive trigger that works today, without AI

**Finding.** Alerting when an order is still not picked up 10 min after Dispatch's own estimated pickup catches 71.5% of late orders with 96.8% precision on the held-out week, a median 45.3 min before the promise breaks.

**So what.** 105 late orders the trigger would have caught received no intervention at all; 42 interventions went to orders that were never at risk.

**Owner.** Operations

## D2 · The promise is optimistic before the food even leaves

**Finding.** Dispatch's pickup estimate is short by a median 8.2 min (planned 18.0 min vs actual 26.2 min from order to pickup). Reaching 80% on-time by padding alone needs +12 min on every promise.

**So what.** Fix the pickup estimate (the input) rather than padding the promise (the output); padding trades lateness for longer quoted times, whose effect on conversion is unknown.

**Owner.** Product / ETA service

## D3 · Do not publish a restaurant or driver blame list

**Finding.** Only 0 of 0 judgeable restaurants (none) and 0 of 1 drivers are statistically worse than the fleet; a naive top-10 list would name 10 restaurants, of which 0 survive the test.

**So what.** Lateness is systemic; accountability conversations should start with the significant few, with the confidence interval shown.

**Owner.** Restaurant Ops / Fleet Ops

## D4 · The weather label does not match the weather

**Finding.** Against Open-Meteo's observed hourly rainfall, the client's weather_bucket agrees 61.2% of the time (Cohen's kappa 0.002, i.e. no better than chance). Orders labelled heavy rain saw 0.14 mm on average, orders labelled clear 0.16 mm. Observed rain: 63.4% late vs 51.9% when dry.

**So what.** 'Weather causes delays' cannot be defended with this field; ask who writes weather_bucket and when, before any weather-aware ETA or staffing plan.

**Owner.** Operations / Data Team

## D5 · GPS pings look drawn, not measured - they cannot show arrival at the restaurant

**Finding.** Before pickup, the last ping is FARTHER from the restaurant than the first in 100.0% of orders (closer in only 0.0%) - a rider cannot leave with the food before picking it up. 92.2% of tracks with 3+ pings are perfectly straight, constant-speed lines and 90.7% have perfectly even time gaps - real device tracks are never that clean. Class 6 found pings only before pickup; here 31.3% of pings fall before pickup and the rest after it (99.7% of post-pickup tracks close in on the customer).

**So what.** Do not build a geofence or a live GPS ETA on this feed: it would invent arrivals. Ask Fleet Ops whether pings are device readings or app interpolation, and instrument an explicit 'arrived at restaurant' tap - the one event that splits kitchen delay from rider delay, which is where the lateness builds.

**Owner.** Fleet Ops / Product

### early_warning_backtest

| split | grace_min | orders | alerts | alert_rate_pct | late_orders | caught_late | false_alerts | precision_pct | recall_pct | median_lead_min | alerts_before_promise_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 0 | 385 | 330 | 85.70 | 214 | 214 | 116 | 64.80 | 100.00 | 57.00 | 100.00 |
| train | 5 | 385 | 252 | 65.50 | 214 | 201 | 51 | 79.80 | 93.90 | 50.30 | 100.00 |
| train | 10 | 385 | 158 | 41.00 | 214 | 153 | 5 | 96.80 | 71.50 | 45.30 | 100.00 |
| train | 15 | 385 | 93 | 24.20 | 214 | 93 | 0 | 100.00 | 43.50 | 42.60 | 100.00 |
| train | 20 | 385 | 57 | 14.80 | 214 | 57 | 0 | 100.00 | 26.60 | 37.60 | 100.00 |
| train | 25 | 385 | 34 | 8.80 | 214 | 34 | 0 | 100.00 | 15.90 | 31.40 | 100.00 |
| train | 30 | 385 | 12 | 3.10 | 214 | 12 | 0 | 100.00 | 5.60 | 21.80 | 100.00 |
| test | 0 | 385 | 330 | 85.70 | 214 | 214 | 116 | 64.80 | 100.00 | 57.00 | 100.00 |
| test | 5 | 385 | 252 | 65.50 | 214 | 201 | 51 | 79.80 | 93.90 | 50.30 | 100.00 |
| test | 10 | 385 | 158 | 41.00 | 214 | 153 | 5 | 96.80 | 71.50 | 45.30 | 100.00 |
| test | 15 | 385 | 93 | 24.20 | 214 | 93 | 0 | 100.00 | 43.50 | 42.60 | 100.00 |
| test | 20 | 385 | 57 | 14.80 | 214 | 57 | 0 | 100.00 | 26.60 | 37.60 | 100.00 |
| test | 25 | 385 | 34 | 8.80 | 214 | 34 | 0 | 100.00 | 15.90 | 31.40 | 100.00 |
| test | 30 | 385 | 12 | 3.10 | 214 | 12 | 0 | 100.00 | 5.60 | 21.80 | 100.00 |
| all | 0 | 385 | 330 | 85.70 | 214 | 214 | 116 | 64.80 | 100.00 | 57.00 | 100.00 |
| all | 5 | 385 | 252 | 65.50 | 214 | 201 | 51 | 79.80 | 93.90 | 50.30 | 100.00 |
| all | 10 | 385 | 158 | 41.00 | 214 | 153 | 5 | 96.80 | 71.50 | 45.30 | 100.00 |
| all | 15 | 385 | 93 | 24.20 | 214 | 93 | 0 | 100.00 | 43.50 | 42.60 | 100.00 |
| all | 20 | 385 | 57 | 14.80 | 214 | 57 | 0 | 100.00 | 26.60 | 37.60 | 100.00 |
| all | 25 | 385 | 34 | 8.80 | 214 | 34 | 0 | 100.00 | 15.90 | 31.40 | 100.00 |
| … 1 more rows … | | | | | | | | | | | |

### early_warning_vs_interventions

| group | orders | with_any_intervention | intervention_before_pickup | intervention_coverage_pct |
|---|---|---|---|---|
| late orders the trigger catches | 153 | 48 | 38 | 31.40 |
| late orders the trigger misses | 61 | 17 | 10 | 27.90 |
| on-time orders the trigger flags (false alerts) | 5 | 2 | 2 | 40.00 |
| on-time orders not flagged | 166 | 42 | 16 | 25.30 |

### eta_calibration

| eta_model_version | padding_min | orders | late_orders | late_rate_pct | on_time_rate_pct |
|---|---|---|---|---|---|
| all versions | 0 | 385 | 214 | 55.60 | 44.40 |
| all versions | 5 | 385 | 133 | 34.50 | 65.50 |
| all versions | 10 | 385 | 87 | 22.60 | 77.40 |
| all versions | 15 | 385 | 58 | 15.10 | 84.90 |
| all versions | 20 | 385 | 28 | 7.30 | 92.70 |
| all versions | 25 | 385 | 11 | 2.90 | 97.10 |
| all versions | 30 | 385 | 4 | 1.00 | 99.00 |
| eta-v3.1 | 0 | 193 | 109 | 56.50 | 43.50 |
| eta-v3.1 | 5 | 193 | 70 | 36.30 | 63.70 |
| eta-v3.1 | 10 | 193 | 43 | 22.30 | 77.70 |
| eta-v3.1 | 15 | 193 | 29 | 15.00 | 85.00 |
| eta-v3.1 | 20 | 193 | 14 | 7.30 | 92.70 |
| eta-v3.1 | 25 | 193 | 7 | 3.60 | 96.40 |
| eta-v3.1 | 30 | 193 | 2 | 1.00 | 99.00 |
| eta-v3.2 | 0 | 192 | 105 | 54.70 | 45.30 |
| eta-v3.2 | 5 | 192 | 63 | 32.80 | 67.20 |
| eta-v3.2 | 10 | 192 | 44 | 22.90 | 77.10 |
| eta-v3.2 | 15 | 192 | 29 | 15.10 | 84.90 |
| eta-v3.2 | 20 | 192 | 14 | 7.30 | 92.70 |
| eta-v3.2 | 25 | 192 | 4 | 2.10 | 97.90 |
| … 1 more rows … | | | | | |

### fair_ranking_restaurants

| restaurant_id | orders | late_orders | late_rate_pct | ci_low_pct | ci_high_pct | verdict | in_naive_top10 |
|---|---|---|---|---|---|---|---|
| R031 | 7 | 7 | 100.00 | 64.60 | 100.00 | too few orders to judge | True |
| R039 | 6 | 6 | 100.00 | 61.00 | 100.00 | too few orders to judge | True |
| R016 | 5 | 5 | 100.00 | 56.60 | 100.00 | too few orders to judge | False |
| R018 | 8 | 7 | 87.50 | 52.90 | 97.80 | too few orders to judge | True |
| R024 | 8 | 7 | 87.50 | 52.90 | 97.80 | too few orders to judge | True |
| R003 | 4 | 4 | 100.00 | 51.00 | 100.00 | too few orders to judge | False |
| R033 | 7 | 6 | 85.70 | 48.70 | 97.40 | too few orders to judge | True |
| R046 | 7 | 6 | 85.70 | 48.70 | 97.40 | too few orders to judge | True |
| R021 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| R026 | 6 | 5 | 83.30 | 43.60 | 97.00 | too few orders to judge | False |
| R058 | 8 | 6 | 75.00 | 40.90 | 92.90 | too few orders to judge | True |
| R004 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | False |
| R006 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | False |
| R038 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | False |
| R056 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | False |
| R035 | 7 | 5 | 71.40 | 35.90 | 91.80 | too few orders to judge | False |
| R036 | 7 | 5 | 71.40 | 35.90 | 91.80 | too few orders to judge | False |
| R045 | 7 | 5 | 71.40 | 35.90 | 91.80 | too few orders to judge | False |
| R050 | 13 | 8 | 61.50 | 35.50 | 82.30 | too few orders to judge | True |
| R011 | 11 | 7 | 63.60 | 35.40 | 84.80 | too few orders to judge | True |
| … 41 more rows … | | | | | | | |

### fair_ranking_drivers

| driver_id | orders | late_orders | late_rate_pct | ci_low_pct | ci_high_pct | verdict | in_naive_top10 |
|---|---|---|---|---|---|---|---|
| D024 | 10 | 2 | 20.00 | 5.70 | 51.00 | better than fleet (significant) | False |
| D054 | 5 | 5 | 100.00 | 56.60 | 100.00 | too few orders to judge | True |
| D001 | 8 | 7 | 87.50 | 52.90 | 97.80 | too few orders to judge | True |
| D040 | 4 | 4 | 100.00 | 51.00 | 100.00 | too few orders to judge | True |
| D065 | 4 | 4 | 100.00 | 51.00 | 100.00 | too few orders to judge | True |
| D013 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| D023 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| D037 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| D104 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| D118 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| D063 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | True |
| D076 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | True |
| D117 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | True |
| D007 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D011 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D021 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D045 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D050 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D061 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D062 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| … 95 more rows … | | | | | | | |

### weather_label_vs_observed

| weather_bucket | orders | observed_rain_share_pct | mean_observed_mm |
|---|---|---|---|
| clear | 330 | 31.50 | 0.16 |
| heavy_rain | 18 | 16.70 | 0.14 |
| rain | 64 | 35.90 | 0.23 |

### late_rate_label_vs_observed_weather

| signal | orders | late_rate_pct |
|---|---|---|
| client label: clear | 309 | 52.10 |
| client label: heavy_rain | 15 | 46.70 |
| client label: rain | 61 | 75.40 |
| observed: dry | 262 | 51.90 |
| observed: raining | 123 | 63.40 |

### gps_arrival_feasibility

| check | value |
|---|---|
| orders with pre-pickup GPS pings | 312.00 |
| orders with >= 2 pre-pickup pings | 90.00 |
| of those, last ping closer to the restaurant than the first (%) | 0.00 |
| orders with any pre-pickup ping within 1 km of the restaurant (%) | 5.10 |
| median distance of the last pre-pickup ping to the restaurant (km) | 4.30 |
| of orders with >= 2 pre-pickup pings, last ping FARTHER from the restaurant than the first (%) | 100.00 |
| GPS pings recorded before pickup (%) - Class 6 expected pings only before pickup | 31.30 |
| orders with >= 3 in-area pings | 281.00 |
| of those, perfectly straight constant-speed track, R^2 >= 0.999 (%) | 92.20 |
| of those, perfectly even time gaps between pings, CV < 0.05 (%) | 90.70 |
| delivered orders with GPS pings between pickup and delivery (%) | 99.00 |
| of those with >= 2 pings, last ping closer to the customer than the first (%) | 99.70 |

### late_rate_heatmap_weekday_hour

| weekday | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Monday | 0.00 | 60.00 | 20.00 | 0.00 | 100.00 | 60.00 | 75.00 | 67.00 | 67.00 | 14.00 | 0.00 | 80.00 |  |
| Tuesday | 100.00 | 50.00 | 50.00 | 33.00 |  | 50.00 | 20.00 | 50.00 | 56.00 | 20.00 | 60.00 | 50.00 | 67.00 |
| Wednesday | 67.00 | 50.00 | 100.00 | 100.00 | 0.00 | 100.00 | 57.00 | 64.00 | 67.00 | 82.00 | 0.00 | 100.00 | 100.00 |
| Thursday | 50.00 | 100.00 | 12.00 | 20.00 | 100.00 | 50.00 | 100.00 | 85.00 | 30.00 | 75.00 | 25.00 | 100.00 | 100.00 |
| Friday | 100.00 | 100.00 | 100.00 | 100.00 | 50.00 | 25.00 | 56.00 | 70.00 | 40.00 | 88.00 | 0.00 | 33.00 | 0.00 |
| Saturday | 50.00 | 50.00 | 67.00 | 100.00 | 100.00 | 100.00 | 83.00 | 67.00 | 40.00 | 10.00 | 100.00 | 0.00 | 100.00 |
| Sunday | 50.00 | 14.00 | 50.00 | 50.00 | 50.00 | 50.00 | 25.00 | 25.00 | 67.00 | 86.00 | 0.00 | 33.00 | 67.00 |

### impact_whatif

| assumed_share_of_caught_late_orders_saved | late_orders_prevented | late_rate_after_pct | kpi_change_pp | support_contacts_avoided | alerts_ops_must_handle | basis |
|---|---|---|---|---|---|---|
| 0.25 | 38 | 45.70 | -9.90 | 9 | 158 | ASSUMPTION - save rate not measured; contact rates from M4/M4a |
| 0.50 | 76 | 35.80 | -19.70 | 19 | 158 | ASSUMPTION - save rate not measured; contact rates from M4/M4a |

# Decision layer — beyond the classroom

Transparent, non-ML analyses that turn the model into actions the client can take now. Every number is recomputed on each run.

## D1 · A proactive trigger that works today, without AI

**Finding.** Alerting when an order is still not picked up 10 min after Dispatch's own estimated pickup catches 71.9% of late orders with 98.2% precision on the held-out week, a median 44.8 min before the promise breaks.

**So what.** 122 late orders the trigger would have caught received no intervention at all; 41 interventions went to orders that were never at risk.

**Owner.** Operations

## D2 · The promise is optimistic before the food even leaves

**Finding.** Dispatch's pickup estimate is short by a median 8.3 min (planned 18.0 min vs actual 26.3 min from order to pickup). Reaching 80% on-time by padding alone needs +13 min on every promise.

**So what.** Fix the pickup estimate (the input) rather than padding the promise (the output); padding trades lateness for longer quoted times, whose effect on conversion is unknown.

**Owner.** Product / ETA service

## D3 · Do not publish a restaurant or driver blame list

**Finding.** Only 0 of 0 judgeable restaurants (none) and 0 of 0 drivers are statistically worse than the fleet; a naive top-10 list would name 10 restaurants, of which 0 survive the test.

**So what.** Lateness is systemic; accountability conversations should start with the significant few, with the confidence interval shown.

**Owner.** Restaurant Ops / Fleet Ops

## D4 · The weather label does not match the weather

**Finding.** Against Open-Meteo's observed hourly rainfall, the client's weather_bucket agrees 51.6% of the time (Cohen's kappa 0.016, i.e. no better than chance). Orders labelled heavy rain saw 0.28 mm on average, orders labelled clear 0.26 mm. Observed rain: 59.1% late vs 60.5% when dry.

**So what.** 'Weather causes delays' cannot be defended with this field; ask who writes weather_bucket and when, before any weather-aware ETA or staffing plan.

**Owner.** Operations / Data Team

## D5 · GPS pings look drawn, not measured - they cannot show arrival at the restaurant

**Finding.** Before pickup, the last ping is FARTHER from the restaurant than the first in 99.0% of orders (closer in only 1.0%) - a rider cannot leave with the food before picking it up. 93.5% of tracks with 3+ pings are perfectly straight, constant-speed lines and 93.9% have perfectly even time gaps - real device tracks are never that clean. Class 6 found pings only before pickup; here 31.1% of pings fall before pickup and the rest after it (99.1% of post-pickup tracks close in on the customer).

**So what.** Do not build a geofence or a live GPS ETA on this feed: it would invent arrivals. Ask Fleet Ops whether pings are device readings or app interpolation, and instrument an explicit 'arrived at restaurant' tap - the one event that splits kitchen delay from rider delay, which is where the lateness builds.

**Owner.** Fleet Ops / Product

### early_warning_backtest

| split | grace_min | orders | alerts | alert_rate_pct | late_orders | caught_late | false_alerts | precision_pct | recall_pct | median_lead_min | alerts_before_promise_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 0 | 381 | 325 | 85.30 | 228 | 228 | 97 | 70.20 | 100.00 | 55.30 | 100.00 |
| train | 5 | 381 | 246 | 64.60 | 228 | 212 | 34 | 86.20 | 93.00 | 50.20 | 100.00 |
| train | 10 | 381 | 167 | 43.80 | 228 | 164 | 3 | 98.20 | 71.90 | 44.80 | 100.00 |
| train | 15 | 381 | 108 | 28.30 | 228 | 108 | 0 | 100.00 | 47.40 | 40.20 | 100.00 |
| train | 20 | 381 | 69 | 18.10 | 228 | 69 | 0 | 100.00 | 30.30 | 37.30 | 100.00 |
| train | 25 | 381 | 41 | 10.80 | 228 | 41 | 0 | 100.00 | 18.00 | 32.30 | 100.00 |
| train | 30 | 381 | 20 | 5.20 | 228 | 20 | 0 | 100.00 | 8.80 | 27.60 | 100.00 |
| test | 0 | 381 | 325 | 85.30 | 228 | 228 | 97 | 70.20 | 100.00 | 55.30 | 100.00 |
| test | 5 | 381 | 246 | 64.60 | 228 | 212 | 34 | 86.20 | 93.00 | 50.20 | 100.00 |
| test | 10 | 381 | 167 | 43.80 | 228 | 164 | 3 | 98.20 | 71.90 | 44.80 | 100.00 |
| test | 15 | 381 | 108 | 28.30 | 228 | 108 | 0 | 100.00 | 47.40 | 40.20 | 100.00 |
| test | 20 | 381 | 69 | 18.10 | 228 | 69 | 0 | 100.00 | 30.30 | 37.30 | 100.00 |
| test | 25 | 381 | 41 | 10.80 | 228 | 41 | 0 | 100.00 | 18.00 | 32.30 | 100.00 |
| test | 30 | 381 | 20 | 5.20 | 228 | 20 | 0 | 100.00 | 8.80 | 27.60 | 100.00 |
| all | 0 | 381 | 325 | 85.30 | 228 | 228 | 97 | 70.20 | 100.00 | 55.30 | 100.00 |
| all | 5 | 381 | 246 | 64.60 | 228 | 212 | 34 | 86.20 | 93.00 | 50.20 | 100.00 |
| all | 10 | 381 | 167 | 43.80 | 228 | 164 | 3 | 98.20 | 71.90 | 44.80 | 100.00 |
| all | 15 | 381 | 108 | 28.30 | 228 | 108 | 0 | 100.00 | 47.40 | 40.20 | 100.00 |
| all | 20 | 381 | 69 | 18.10 | 228 | 69 | 0 | 100.00 | 30.30 | 37.30 | 100.00 |
| all | 25 | 381 | 41 | 10.80 | 228 | 41 | 0 | 100.00 | 18.00 | 32.30 | 100.00 |
| … 1 more rows … | | | | | | | | | | | |

### early_warning_vs_interventions

| group | orders | with_any_intervention | intervention_before_pickup | intervention_coverage_pct |
|---|---|---|---|---|
| late orders the trigger catches | 164 | 42 | 34 | 25.60 |
| late orders the trigger misses | 64 | 20 | 12 | 31.20 |
| on-time orders the trigger flags (false alerts) | 3 | 0 | 0 | 0.00 |
| on-time orders not flagged | 150 | 41 | 15 | 27.30 |

### eta_calibration

| eta_model_version | padding_min | orders | late_orders | late_rate_pct | on_time_rate_pct |
|---|---|---|---|---|---|
| all versions | 0 | 381 | 228 | 59.80 | 40.20 |
| all versions | 5 | 381 | 154 | 40.40 | 59.60 |
| all versions | 10 | 381 | 99 | 26.00 | 74.00 |
| all versions | 15 | 381 | 56 | 14.70 | 85.30 |
| all versions | 20 | 381 | 41 | 10.80 | 89.20 |
| all versions | 25 | 381 | 18 | 4.70 | 95.30 |
| all versions | 30 | 381 | 12 | 3.10 | 96.90 |
| eta-v3.1 | 0 | 176 | 101 | 57.40 | 42.60 |
| eta-v3.1 | 5 | 176 | 65 | 36.90 | 63.10 |
| eta-v3.1 | 10 | 176 | 39 | 22.20 | 77.80 |
| eta-v3.1 | 15 | 176 | 25 | 14.20 | 85.80 |
| eta-v3.1 | 20 | 176 | 18 | 10.20 | 89.80 |
| eta-v3.1 | 25 | 176 | 7 | 4.00 | 96.00 |
| eta-v3.1 | 30 | 176 | 4 | 2.30 | 97.70 |
| eta-v3.2 | 0 | 205 | 127 | 62.00 | 38.00 |
| eta-v3.2 | 5 | 205 | 89 | 43.40 | 56.60 |
| eta-v3.2 | 10 | 205 | 60 | 29.30 | 70.70 |
| eta-v3.2 | 15 | 205 | 31 | 15.10 | 84.90 |
| eta-v3.2 | 20 | 205 | 23 | 11.20 | 88.80 |
| eta-v3.2 | 25 | 205 | 11 | 5.40 | 94.60 |
| … 1 more rows … | | | | | |

### fair_ranking_restaurants

| restaurant_id | orders | late_orders | late_rate_pct | ci_low_pct | ci_high_pct | verdict | in_naive_top10 |
|---|---|---|---|---|---|---|---|
| R001 | 6 | 6 | 100.00 | 61.00 | 100.00 | too few orders to judge | True |
| R025 | 10 | 9 | 90.00 | 59.60 | 98.20 | too few orders to judge | True |
| R050 | 9 | 8 | 88.90 | 56.50 | 98.00 | too few orders to judge | True |
| R030 | 8 | 7 | 87.50 | 52.90 | 97.80 | too few orders to judge | True |
| R051 | 8 | 7 | 87.50 | 52.90 | 97.80 | too few orders to judge | True |
| R002 | 7 | 6 | 85.70 | 48.70 | 97.40 | too few orders to judge | True |
| R009 | 7 | 6 | 85.70 | 48.70 | 97.40 | too few orders to judge | True |
| R006 | 6 | 5 | 83.30 | 43.60 | 97.00 | too few orders to judge | False |
| R054 | 6 | 5 | 83.30 | 43.60 | 97.00 | too few orders to judge | False |
| R057 | 6 | 5 | 83.30 | 43.60 | 97.00 | too few orders to judge | False |
| R012 | 8 | 6 | 75.00 | 40.90 | 92.90 | too few orders to judge | True |
| R020 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | False |
| R039 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | False |
| R005 | 7 | 5 | 71.40 | 35.90 | 91.80 | too few orders to judge | False |
| R021 | 7 | 5 | 71.40 | 35.90 | 91.80 | too few orders to judge | False |
| R024 | 7 | 5 | 71.40 | 35.90 | 91.80 | too few orders to judge | False |
| R023 | 9 | 6 | 66.70 | 35.40 | 87.90 | too few orders to judge | True |
| R060 | 10 | 6 | 60.00 | 31.30 | 83.20 | too few orders to judge | False |
| R049 | 8 | 5 | 62.50 | 30.60 | 86.30 | too few orders to judge | False |
| R033 | 4 | 3 | 75.00 | 30.10 | 95.40 | too few orders to judge | False |
| … 40 more rows … | | | | | | | |

### fair_ranking_drivers

| driver_id | orders | late_orders | late_rate_pct | ci_low_pct | ci_high_pct | verdict | in_naive_top10 |
|---|---|---|---|---|---|---|---|
| D018 | 4 | 4 | 100.00 | 51.00 | 100.00 | too few orders to judge | True |
| D022 | 4 | 4 | 100.00 | 51.00 | 100.00 | too few orders to judge | True |
| D025 | 4 | 4 | 100.00 | 51.00 | 100.00 | too few orders to judge | True |
| D094 | 4 | 4 | 100.00 | 51.00 | 100.00 | too few orders to judge | True |
| D017 | 7 | 6 | 85.70 | 48.70 | 97.40 | too few orders to judge | True |
| D020 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| D029 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| D042 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| D078 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| D092 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| D095 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| D103 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| D087 | 6 | 5 | 83.30 | 43.60 | 97.00 | too few orders to judge | True |
| D007 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | True |
| D010 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | True |
| D011 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | True |
| D033 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | True |
| D046 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | False |
| D047 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | False |
| D008 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| … 92 more rows … | | | | | | | |

### weather_label_vs_observed

| weather_bucket | orders | observed_rain_share_pct | mean_observed_mm |
|---|---|---|---|
| clear | 324 | 48.10 | 0.26 |
| heavy_rain | 23 | 52.20 | 0.28 |
| rain | 62 | 50.00 | 0.28 |

### late_rate_label_vs_observed_weather

| signal | orders | late_rate_pct |
|---|---|---|
| client label: clear | 303 | 55.10 |
| client label: heavy_rain | 20 | 85.00 |
| client label: rain | 58 | 75.90 |
| observed: dry | 195 | 60.50 |
| observed: raining | 186 | 59.10 |

### gps_arrival_feasibility

| check | value |
|---|---|
| orders with pre-pickup GPS pings | 292.00 |
| orders with >= 2 pre-pickup pings | 98.00 |
| of those, last ping closer to the restaurant than the first (%) | 1.00 |
| orders with any pre-pickup ping within 1 km of the restaurant (%) | 7.20 |
| median distance of the last pre-pickup ping to the restaurant (km) | 4.43 |
| of orders with >= 2 pre-pickup pings, last ping FARTHER from the restaurant than the first (%) | 99.00 |
| GPS pings recorded before pickup (%) - Class 6 expected pings only before pickup | 31.10 |
| orders with >= 3 in-area pings | 277.00 |
| of those, perfectly straight constant-speed track, R^2 >= 0.999 (%) | 93.50 |
| of those, perfectly even time gaps between pings, CV < 0.05 (%) | 93.90 |
| delivered orders with GPS pings between pickup and delivery (%) | 99.50 |
| of those with >= 2 pings, last ping closer to the customer than the first (%) | 99.10 |

### late_rate_heatmap_weekday_hour

| weekday | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Monday | 40.00 | 67.00 | 100.00 | 0.00 | 80.00 | 50.00 | 40.00 | 43.00 | 50.00 | 75.00 | 60.00 | 75.00 | 100.00 |
| Tuesday | 80.00 | 75.00 | 0.00 | 75.00 | 0.00 | 0.00 | 50.00 | 43.00 | 60.00 | 33.00 | 78.00 | 0.00 |  |
| Wednesday | 67.00 | 0.00 | 100.00 |  | 33.00 | 67.00 | 60.00 | 89.00 | 75.00 | 50.00 | 100.00 | 40.00 | 100.00 |
| Thursday | 0.00 | 57.00 | 33.00 | 100.00 | 100.00 | 67.00 | 83.00 | 50.00 | 75.00 | 50.00 | 0.00 | 40.00 | 100.00 |
| Friday | 60.00 | 64.00 | 100.00 | 33.00 | 100.00 | 67.00 | 50.00 | 70.00 | 80.00 | 33.00 | 50.00 | 67.00 | 100.00 |
| Saturday | 33.00 | 100.00 | 40.00 | 40.00 | 100.00 | 67.00 | 50.00 | 91.00 | 42.00 | 50.00 | 0.00 |  | 100.00 |
| Sunday | 83.00 | 0.00 | 100.00 | 0.00 | 100.00 | 50.00 | 67.00 | 60.00 | 70.00 | 57.00 | 17.00 | 25.00 | 100.00 |

### impact_whatif

| assumed_share_of_caught_late_orders_saved | late_orders_prevented | late_rate_after_pct | kpi_change_pp | support_contacts_avoided | alerts_ops_must_handle | basis |
|---|---|---|---|---|---|---|
| 0.25 | 41 | 49.10 | -10.80 | 11 | 167 | ASSUMPTION - save rate not measured; contact rates from M4/M4a |
| 0.50 | 82 | 38.30 | -21.50 | 22 | 167 | ASSUMPTION - save rate not measured; contact rates from M4/M4a |

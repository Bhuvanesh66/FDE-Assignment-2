# Decision layer — beyond the classroom

Transparent, non-ML analyses that turn the model into actions the client can take now. Every number is recomputed on each run.

## D1 · A proactive trigger that works today, without AI

**Finding.** Alerting when an order is still not picked up 10 min after Dispatch's own estimated pickup catches 72.9% of late orders with 96.5% precision on the held-out week, a median 45.0 min before the promise breaks.

**So what.** 104 late orders the trigger would have caught received no intervention at all; 36 interventions went to orders that were never at risk.

**Owner.** Operations

## D2 · The promise is optimistic before the food even leaves

**Finding.** Dispatch's pickup estimate is short by a median 7.7 min (planned 18.0 min vs actual 25.7 min from order to pickup). Reaching 80% on-time by padding alone needs +12 min on every promise.

**So what.** Fix the pickup estimate (the input) rather than padding the promise (the output); padding trades lateness for longer quoted times, whose effect on conversion is unknown.

**Owner.** Product / ETA service

## D3 · Do not publish a restaurant or driver blame list

**Finding.** Only 0 of 0 judgeable restaurants (none) and 0 of 1 drivers are statistically worse than the fleet; a naive top-10 list would name 10 restaurants, of which 0 survive the test.

**So what.** Lateness is systemic; accountability conversations should start with the significant few, with the confidence interval shown.

**Owner.** Restaurant Ops / Fleet Ops

## D4 · The weather label does not match the weather

**Finding.** Against Open-Meteo's observed hourly rainfall, the client's weather_bucket agrees 42.7% of the time (Cohen's kappa 0.019, i.e. no better than chance). Orders labelled heavy rain saw 0.96 mm on average, orders labelled clear 1.02 mm. Observed rain: 54.1% late vs 55.2% when dry.

**So what.** 'Weather causes delays' cannot be defended with this field; ask who writes weather_bucket and when, before any weather-aware ETA or staffing plan.

**Owner.** Operations / Data Team

## D5 · GPS pings look drawn, not measured - they cannot show arrival at the restaurant

**Finding.** Before pickup, the last ping is FARTHER from the restaurant than the first in 98.8% of orders (closer in only 1.2%) - a rider cannot leave with the food before picking it up. 88.3% of tracks with 3+ pings are perfectly straight, constant-speed lines and 87.5% have perfectly even time gaps - real device tracks are never that clean. Class 6 found pings only before pickup; here 29.8% of pings fall before pickup and the rest after it (99.7% of post-pickup tracks close in on the customer).

**So what.** Do not build a geofence or a live GPS ETA on this feed: it would invent arrivals. Ask Fleet Ops whether pings are device readings or app interpolation, and instrument an explicit 'arrived at restaurant' tap - the one event that splits kitchen delay from rider delay, which is where the lateness builds.

**Owner.** Fleet Ops / Product

### early_warning_backtest

| split | grace_min | orders | alerts | alert_rate_pct | late_orders | caught_late | false_alerts | precision_pct | recall_pct | median_lead_min | alerts_before_promise_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 0 | 345 | 281 | 81.40 | 188 | 186 | 95 | 66.20 | 98.90 | 56.00 | 100.00 |
| train | 5 | 345 | 213 | 61.70 | 188 | 174 | 39 | 81.70 | 92.60 | 50.00 | 100.00 |
| train | 10 | 345 | 142 | 41.20 | 188 | 137 | 5 | 96.50 | 72.90 | 45.00 | 100.00 |
| train | 15 | 345 | 83 | 24.10 | 188 | 83 | 0 | 100.00 | 44.10 | 40.30 | 100.00 |
| train | 20 | 345 | 51 | 14.80 | 188 | 51 | 0 | 100.00 | 27.10 | 34.80 | 98.00 |
| train | 25 | 345 | 26 | 7.50 | 188 | 26 | 0 | 100.00 | 13.80 | 29.80 | 96.20 |
| train | 30 | 345 | 5 | 1.40 | 188 | 5 | 0 | 100.00 | 2.70 | 24.80 | 80.00 |
| test | 0 | 345 | 281 | 81.40 | 188 | 186 | 95 | 66.20 | 98.90 | 56.00 | 100.00 |
| test | 5 | 345 | 213 | 61.70 | 188 | 174 | 39 | 81.70 | 92.60 | 50.00 | 100.00 |
| test | 10 | 345 | 142 | 41.20 | 188 | 137 | 5 | 96.50 | 72.90 | 45.00 | 100.00 |
| test | 15 | 345 | 83 | 24.10 | 188 | 83 | 0 | 100.00 | 44.10 | 40.30 | 100.00 |
| test | 20 | 345 | 51 | 14.80 | 188 | 51 | 0 | 100.00 | 27.10 | 34.80 | 98.00 |
| test | 25 | 345 | 26 | 7.50 | 188 | 26 | 0 | 100.00 | 13.80 | 29.80 | 96.20 |
| test | 30 | 345 | 5 | 1.40 | 188 | 5 | 0 | 100.00 | 2.70 | 24.80 | 80.00 |
| all | 0 | 345 | 281 | 81.40 | 188 | 186 | 95 | 66.20 | 98.90 | 56.00 | 100.00 |
| all | 5 | 345 | 213 | 61.70 | 188 | 174 | 39 | 81.70 | 92.60 | 50.00 | 100.00 |
| all | 10 | 345 | 142 | 41.20 | 188 | 137 | 5 | 96.50 | 72.90 | 45.00 | 100.00 |
| all | 15 | 345 | 83 | 24.10 | 188 | 83 | 0 | 100.00 | 44.10 | 40.30 | 100.00 |
| all | 20 | 345 | 51 | 14.80 | 188 | 51 | 0 | 100.00 | 27.10 | 34.80 | 98.00 |
| all | 25 | 345 | 26 | 7.50 | 188 | 26 | 0 | 100.00 | 13.80 | 29.80 | 96.20 |
| … 1 more rows … | | | | | | | | | | | |

### early_warning_vs_interventions

| group | orders | with_any_intervention | intervention_before_pickup | intervention_coverage_pct |
|---|---|---|---|---|
| late orders the trigger catches | 137 | 33 | 27 | 24.10 |
| late orders the trigger misses | 51 | 15 | 8 | 29.40 |
| on-time orders the trigger flags (false alerts) | 5 | 2 | 2 | 40.00 |
| on-time orders not flagged | 152 | 36 | 11 | 23.70 |

### eta_calibration

| eta_model_version | padding_min | orders | late_orders | late_rate_pct | on_time_rate_pct |
|---|---|---|---|---|---|
| all versions | 0 | 345 | 188 | 54.50 | 45.50 |
| all versions | 5 | 345 | 128 | 37.10 | 62.90 |
| all versions | 10 | 345 | 75 | 21.70 | 78.30 |
| all versions | 15 | 345 | 43 | 12.50 | 87.50 |
| all versions | 20 | 345 | 21 | 6.10 | 93.90 |
| all versions | 25 | 345 | 7 | 2.00 | 98.00 |
| all versions | 30 | 345 | 0 | 0.00 | 100.00 |
| eta-v3.1 | 0 | 171 | 86 | 50.30 | 49.70 |
| eta-v3.1 | 5 | 171 | 58 | 33.90 | 66.10 |
| eta-v3.1 | 10 | 171 | 33 | 19.30 | 80.70 |
| eta-v3.1 | 15 | 171 | 19 | 11.10 | 88.90 |
| eta-v3.1 | 20 | 171 | 12 | 7.00 | 93.00 |
| eta-v3.1 | 25 | 171 | 4 | 2.30 | 97.70 |
| eta-v3.1 | 30 | 171 | 0 | 0.00 | 100.00 |
| eta-v3.2 | 0 | 174 | 102 | 58.60 | 41.40 |
| eta-v3.2 | 5 | 174 | 70 | 40.20 | 59.80 |
| eta-v3.2 | 10 | 174 | 42 | 24.10 | 75.90 |
| eta-v3.2 | 15 | 174 | 24 | 13.80 | 86.20 |
| eta-v3.2 | 20 | 174 | 9 | 5.20 | 94.80 |
| eta-v3.2 | 25 | 174 | 3 | 1.70 | 98.30 |
| … 1 more rows … | | | | | |

### fair_ranking_restaurants

| restaurant_id | orders | late_orders | late_rate_pct | ci_low_pct | ci_high_pct | verdict | in_naive_top10 |
|---|---|---|---|---|---|---|---|
| R032 | 4 | 4 | 100.00 | 51.00 | 100.00 | too few orders to judge | False |
| R054 | 7 | 6 | 85.70 | 48.70 | 97.40 | too few orders to judge | True |
| R044 | 6 | 5 | 83.30 | 43.60 | 97.00 | too few orders to judge | True |
| R047 | 6 | 5 | 83.30 | 43.60 | 97.00 | too few orders to judge | True |
| R058 | 6 | 5 | 83.30 | 43.60 | 97.00 | too few orders to judge | True |
| R004 | 10 | 7 | 70.00 | 39.70 | 89.20 | too few orders to judge | True |
| R022 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | False |
| R024 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | False |
| R043 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | False |
| R007 | 7 | 5 | 71.40 | 35.90 | 91.80 | too few orders to judge | True |
| R018 | 7 | 5 | 71.40 | 35.90 | 91.80 | too few orders to judge | True |
| R045 | 7 | 5 | 71.40 | 35.90 | 91.80 | too few orders to judge | True |
| R057 | 9 | 6 | 66.70 | 35.40 | 87.90 | too few orders to judge | True |
| R001 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| R038 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| R034 | 10 | 6 | 60.00 | 31.30 | 83.20 | too few orders to judge | True |
| R041 | 8 | 5 | 62.50 | 30.60 | 86.30 | too few orders to judge | False |
| R036 | 4 | 3 | 75.00 | 30.10 | 95.40 | too few orders to judge | False |
| R008 | 6 | 4 | 66.70 | 30.00 | 90.30 | too few orders to judge | False |
| R014 | 6 | 4 | 66.70 | 30.00 | 90.30 | too few orders to judge | False |
| … 40 more rows … | | | | | | | |

### fair_ranking_drivers

| driver_id | orders | late_orders | late_rate_pct | ci_low_pct | ci_high_pct | verdict | in_naive_top10 |
|---|---|---|---|---|---|---|---|
| D010 | 11 | 6 | 54.50 | 28.00 | 78.70 | not distinguishable from fleet | True |
| D031 | 5 | 5 | 100.00 | 56.60 | 100.00 | too few orders to judge | True |
| D036 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | True |
| D071 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | True |
| D075 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | True |
| D113 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| D117 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | True |
| D073 | 7 | 5 | 71.40 | 35.90 | 91.80 | too few orders to judge | True |
| D011 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D025 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D027 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D051 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D054 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D060 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D097 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D100 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D103 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D107 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D116 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D009 | 4 | 3 | 75.00 | 30.10 | 95.40 | too few orders to judge | False |
| … 93 more rows … | | | | | | | |

### weather_label_vs_observed

| weather_bucket | orders | observed_rain_share_pct | mean_observed_mm |
|---|---|---|---|
| clear | 297 | 63.30 | 1.02 |
| heavy_rain | 16 | 81.20 | 0.96 |
| rain | 59 | 62.70 | 1.41 |

### late_rate_label_vs_observed_weather

| signal | orders | late_rate_pct |
|---|---|---|
| client label: clear | 276 | 52.90 |
| client label: heavy_rain | 16 | 87.50 |
| client label: rain | 53 | 52.80 |
| observed: dry | 125 | 55.20 |
| observed: raining | 220 | 54.10 |

### gps_arrival_feasibility

| check | value |
|---|---|
| orders with pre-pickup GPS pings | 272.00 |
| orders with >= 2 pre-pickup pings | 86.00 |
| of those, last ping closer to the restaurant than the first (%) | 1.20 |
| orders with any pre-pickup ping within 1 km of the restaurant (%) | 6.60 |
| median distance of the last pre-pickup ping to the restaurant (km) | 4.26 |
| of orders with >= 2 pre-pickup pings, last ping FARTHER from the restaurant than the first (%) | 98.80 |
| GPS pings recorded before pickup (%) - Class 6 expected pings only before pickup | 29.80 |
| orders with >= 3 in-area pings | 265.00 |
| of those, perfectly straight constant-speed track, R^2 >= 0.999 (%) | 88.30 |
| of those, perfectly even time gaps between pings, CV < 0.05 (%) | 87.50 |
| delivered orders with GPS pings between pickup and delivery (%) | 98.60 |
| of those with >= 2 pings, last ping closer to the customer than the first (%) | 99.70 |

### late_rate_heatmap_weekday_hour

| weekday | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Monday | 50.00 | 50.00 | 33.00 | 100.00 | 67.00 | 50.00 | 80.00 | 50.00 | 80.00 | 67.00 | 67.00 | 25.00 | 67.00 |
| Tuesday | 62.00 | 80.00 | 80.00 | 0.00 | 67.00 | 25.00 | 50.00 | 82.00 | 50.00 | 38.00 | 75.00 |  | 50.00 |
| Wednesday | 0.00 | 100.00 | 33.00 | 80.00 | 100.00 | 67.00 | 50.00 | 100.00 | 25.00 | 42.00 | 33.00 | 75.00 | 100.00 |
| Thursday | 100.00 | 50.00 | 75.00 | 50.00 | 50.00 | 100.00 | 0.00 | 44.00 | 33.00 | 38.00 | 33.00 |  | 60.00 |
| Friday | 0.00 | 25.00 | 0.00 | 0.00 | 67.00 | 75.00 | 33.00 | 100.00 | 50.00 | 88.00 | 25.00 | 50.00 | 33.00 |
| Saturday | 67.00 | 0.00 | 100.00 | 0.00 | 0.00 | 67.00 | 100.00 | 50.00 | 50.00 | 100.00 | 33.00 | 50.00 |  |
| Sunday | 67.00 | 50.00 | 40.00 | 100.00 | 50.00 |  |  | 50.00 | 57.00 | 40.00 | 100.00 | 100.00 | 50.00 |

### impact_whatif

| assumed_share_of_caught_late_orders_saved | late_orders_prevented | late_rate_after_pct | kpi_change_pp | support_contacts_avoided | alerts_ops_must_handle | basis |
|---|---|---|---|---|---|---|
| 0.25 | 34 | 44.60 | -9.90 | 10 | 142 | ASSUMPTION - save rate not measured; contact rates from M4/M4a |
| 0.50 | 68 | 34.80 | -19.70 | 19 | 142 | ASSUMPTION - save rate not measured; contact rates from M4/M4a |

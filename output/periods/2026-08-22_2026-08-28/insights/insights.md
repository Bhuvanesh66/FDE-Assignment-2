# Decision layer — beyond the classroom

Transparent, non-ML analyses that turn the model into actions the client can take now. Every number is recomputed on each run.

## D1 · A proactive trigger that works today, without AI

**Finding.** Alerting when an order is still not picked up 10 min after Dispatch's own estimated pickup catches 71.5% of late orders with 96.1% precision on the held-out week, a median 44.8 min before the promise breaks.

**So what.** 115 late orders the trigger would have caught received no intervention at all; 50 interventions went to orders that were never at risk.

**Owner.** Operations

## D2 · The promise is optimistic before the food even leaves

**Finding.** Dispatch's pickup estimate is short by a median 8.0 min (planned 18.0 min vs actual 25.9 min from order to pickup). Reaching 80% on-time by padding alone needs +12 min on every promise.

**So what.** Fix the pickup estimate (the input) rather than padding the promise (the output); padding trades lateness for longer quoted times, whose effect on conversion is unknown.

**Owner.** Product / ETA service

## D3 · Do not publish a restaurant or driver blame list

**Finding.** Only 0 of 0 judgeable restaurants (none) and 0 of 0 drivers are statistically worse than the fleet; a naive top-10 list would name 10 restaurants, of which 0 survive the test.

**So what.** Lateness is systemic; accountability conversations should start with the significant few, with the confidence interval shown.

**Owner.** Restaurant Ops / Fleet Ops

## D4 · The weather label does not match the weather

**Finding.** Against Open-Meteo's observed hourly rainfall, the client's weather_bucket agrees 54.1% of the time (Cohen's kappa -0.004, i.e. no better than chance). Orders labelled heavy rain saw 0.34 mm on average, orders labelled clear 0.45 mm. Observed rain: 60.0% late vs 51.6% when dry.

**So what.** 'Weather causes delays' cannot be defended with this field; ask who writes weather_bucket and when, before any weather-aware ETA or staffing plan.

**Owner.** Operations / Data Team

## D5 · GPS pings look drawn, not measured - they cannot show arrival at the restaurant

**Finding.** Before pickup, the last ping is FARTHER from the restaurant than the first in 99.0% of orders (closer in only 1.0%) - a rider cannot leave with the food before picking it up. 91.0% of tracks with 3+ pings are perfectly straight, constant-speed lines and 90.6% have perfectly even time gaps - real device tracks are never that clean. Class 6 found pings only before pickup; here 31.0% of pings fall before pickup and the rest after it (99.1% of post-pickup tracks close in on the customer).

**So what.** Do not build a geofence or a live GPS ETA on this feed: it would invent arrivals. Ask Fleet Ops whether pings are device readings or app interpolation, and instrument an explicit 'arrived at restaurant' tap - the one event that splits kitchen delay from rider delay, which is where the lateness builds.

**Owner.** Fleet Ops / Product

### early_warning_backtest

| split | grace_min | orders | alerts | alert_rate_pct | late_orders | caught_late | false_alerts | precision_pct | recall_pct | median_lead_min | alerts_before_promise_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 0 | 375 | 307 | 81.90 | 207 | 206 | 101 | 67.10 | 99.50 | 56.90 | 100.00 |
| train | 5 | 375 | 234 | 62.40 | 207 | 195 | 39 | 83.30 | 94.20 | 50.50 | 100.00 |
| train | 10 | 375 | 154 | 41.10 | 207 | 148 | 6 | 96.10 | 71.50 | 44.80 | 100.00 |
| train | 15 | 375 | 96 | 25.60 | 207 | 96 | 0 | 100.00 | 46.40 | 41.90 | 100.00 |
| train | 20 | 375 | 52 | 13.90 | 207 | 52 | 0 | 100.00 | 25.10 | 34.80 | 100.00 |
| train | 25 | 375 | 32 | 8.50 | 207 | 32 | 0 | 100.00 | 15.50 | 29.80 | 96.90 |
| train | 30 | 375 | 16 | 4.30 | 207 | 16 | 0 | 100.00 | 7.70 | 25.20 | 100.00 |
| test | 0 | 375 | 307 | 81.90 | 207 | 206 | 101 | 67.10 | 99.50 | 56.90 | 100.00 |
| test | 5 | 375 | 234 | 62.40 | 207 | 195 | 39 | 83.30 | 94.20 | 50.50 | 100.00 |
| test | 10 | 375 | 154 | 41.10 | 207 | 148 | 6 | 96.10 | 71.50 | 44.80 | 100.00 |
| test | 15 | 375 | 96 | 25.60 | 207 | 96 | 0 | 100.00 | 46.40 | 41.90 | 100.00 |
| test | 20 | 375 | 52 | 13.90 | 207 | 52 | 0 | 100.00 | 25.10 | 34.80 | 100.00 |
| test | 25 | 375 | 32 | 8.50 | 207 | 32 | 0 | 100.00 | 15.50 | 29.80 | 96.90 |
| test | 30 | 375 | 16 | 4.30 | 207 | 16 | 0 | 100.00 | 7.70 | 25.20 | 100.00 |
| all | 0 | 375 | 307 | 81.90 | 207 | 206 | 101 | 67.10 | 99.50 | 56.90 | 100.00 |
| all | 5 | 375 | 234 | 62.40 | 207 | 195 | 39 | 83.30 | 94.20 | 50.50 | 100.00 |
| all | 10 | 375 | 154 | 41.10 | 207 | 148 | 6 | 96.10 | 71.50 | 44.80 | 100.00 |
| all | 15 | 375 | 96 | 25.60 | 207 | 96 | 0 | 100.00 | 46.40 | 41.90 | 100.00 |
| all | 20 | 375 | 52 | 13.90 | 207 | 52 | 0 | 100.00 | 25.10 | 34.80 | 100.00 |
| all | 25 | 375 | 32 | 8.50 | 207 | 32 | 0 | 100.00 | 15.50 | 29.80 | 96.90 |
| … 1 more rows … | | | | | | | | | | | |

### early_warning_vs_interventions

| group | orders | with_any_intervention | intervention_before_pickup | intervention_coverage_pct |
|---|---|---|---|---|
| late orders the trigger catches | 148 | 33 | 26 | 22.30 |
| late orders the trigger misses | 59 | 17 | 9 | 28.80 |
| on-time orders the trigger flags (false alerts) | 6 | 1 | 0 | 16.70 |
| on-time orders not flagged | 162 | 50 | 19 | 30.90 |

### eta_calibration

| eta_model_version | padding_min | orders | late_orders | late_rate_pct | on_time_rate_pct |
|---|---|---|---|---|---|
| all versions | 0 | 375 | 207 | 55.20 | 44.80 |
| all versions | 5 | 375 | 140 | 37.30 | 62.70 |
| all versions | 10 | 375 | 83 | 22.10 | 77.90 |
| all versions | 15 | 375 | 45 | 12.00 | 88.00 |
| all versions | 20 | 375 | 28 | 7.50 | 92.50 |
| all versions | 25 | 375 | 14 | 3.70 | 96.30 |
| all versions | 30 | 375 | 7 | 1.90 | 98.10 |
| eta-v3.1 | 0 | 197 | 110 | 55.80 | 44.20 |
| eta-v3.1 | 5 | 197 | 77 | 39.10 | 60.90 |
| eta-v3.1 | 10 | 197 | 46 | 23.40 | 76.60 |
| eta-v3.1 | 15 | 197 | 22 | 11.20 | 88.80 |
| eta-v3.1 | 20 | 197 | 17 | 8.60 | 91.40 |
| eta-v3.1 | 25 | 197 | 11 | 5.60 | 94.40 |
| eta-v3.1 | 30 | 197 | 6 | 3.00 | 97.00 |
| eta-v3.2 | 0 | 178 | 97 | 54.50 | 45.50 |
| eta-v3.2 | 5 | 178 | 63 | 35.40 | 64.60 |
| eta-v3.2 | 10 | 178 | 37 | 20.80 | 79.20 |
| eta-v3.2 | 15 | 178 | 23 | 12.90 | 87.10 |
| eta-v3.2 | 20 | 178 | 11 | 6.20 | 93.80 |
| eta-v3.2 | 25 | 178 | 3 | 1.70 | 98.30 |
| … 1 more rows … | | | | | |

### fair_ranking_restaurants

| restaurant_id | orders | late_orders | late_rate_pct | ci_low_pct | ci_high_pct | verdict | in_naive_top10 |
|---|---|---|---|---|---|---|---|
| R029 | 4 | 4 | 100.00 | 51.00 | 100.00 | too few orders to judge | False |
| R041 | 7 | 6 | 85.70 | 48.70 | 97.40 | too few orders to judge | True |
| R051 | 7 | 6 | 85.70 | 48.70 | 97.40 | too few orders to judge | True |
| R044 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| R023 | 6 | 5 | 83.30 | 43.60 | 97.00 | too few orders to judge | True |
| R011 | 8 | 6 | 75.00 | 40.90 | 92.90 | too few orders to judge | True |
| R042 | 8 | 6 | 75.00 | 40.90 | 92.90 | too few orders to judge | True |
| R052 | 8 | 6 | 75.00 | 40.90 | 92.90 | too few orders to judge | True |
| R055 | 10 | 7 | 70.00 | 39.70 | 89.20 | too few orders to judge | True |
| R024 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | False |
| R060 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | False |
| R031 | 7 | 5 | 71.40 | 35.90 | 91.80 | too few orders to judge | False |
| R002 | 11 | 7 | 63.60 | 35.40 | 84.80 | too few orders to judge | True |
| R017 | 9 | 6 | 66.70 | 35.40 | 87.90 | too few orders to judge | True |
| R020 | 14 | 8 | 57.10 | 32.60 | 78.60 | too few orders to judge | True |
| R004 | 8 | 5 | 62.50 | 30.60 | 86.30 | too few orders to judge | False |
| R014 | 8 | 5 | 62.50 | 30.60 | 86.30 | too few orders to judge | False |
| R015 | 8 | 5 | 62.50 | 30.60 | 86.30 | too few orders to judge | False |
| R037 | 8 | 5 | 62.50 | 30.60 | 86.30 | too few orders to judge | False |
| R021 | 4 | 3 | 75.00 | 30.10 | 95.40 | too few orders to judge | False |
| … 41 more rows … | | | | | | | |

### fair_ranking_drivers

| driver_id | orders | late_orders | late_rate_pct | ci_low_pct | ci_high_pct | verdict | in_naive_top10 |
|---|---|---|---|---|---|---|---|
| D046 | 5 | 5 | 100.00 | 56.60 | 100.00 | too few orders to judge | True |
| D039 | 4 | 4 | 100.00 | 51.00 | 100.00 | too few orders to judge | True |
| D076 | 7 | 6 | 85.70 | 48.70 | 97.40 | too few orders to judge | True |
| D094 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| D102 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| D111 | 3 | 3 | 100.00 | 43.90 | 100.00 | too few orders to judge | False |
| D043 | 6 | 5 | 83.30 | 43.60 | 97.00 | too few orders to judge | True |
| D087 | 6 | 5 | 83.30 | 43.60 | 97.00 | too few orders to judge | True |
| D015 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | True |
| D016 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | True |
| D031 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | True |
| D116 | 5 | 4 | 80.00 | 37.60 | 96.40 | too few orders to judge | True |
| D054 | 7 | 5 | 71.40 | 35.90 | 91.80 | too few orders to judge | True |
| D001 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D020 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D024 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D065 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D114 | 2 | 2 | 100.00 | 34.20 | 100.00 | too few orders to judge | False |
| D008 | 4 | 3 | 75.00 | 30.10 | 95.40 | too few orders to judge | False |
| D017 | 4 | 3 | 75.00 | 30.10 | 95.40 | too few orders to judge | False |
| … 97 more rows … | | | | | | | |

### weather_label_vs_observed

| weather_bucket | orders | observed_rain_share_pct | mean_observed_mm |
|---|---|---|---|
| clear | 322 | 42.90 | 0.45 |
| heavy_rain | 21 | 38.10 | 0.34 |
| rain | 64 | 43.80 | 0.55 |

### late_rate_label_vs_observed_weather

| signal | orders | late_rate_pct |
|---|---|---|
| client label: clear | 297 | 52.90 |
| client label: heavy_rain | 21 | 71.40 |
| client label: rain | 57 | 61.40 |
| observed: dry | 215 | 51.60 |
| observed: raining | 160 | 60.00 |

### gps_arrival_feasibility

| check | value |
|---|---|
| orders with pre-pickup GPS pings | 290.00 |
| orders with >= 2 pre-pickup pings | 100.00 |
| of those, last ping closer to the restaurant than the first (%) | 1.00 |
| orders with any pre-pickup ping within 1 km of the restaurant (%) | 4.80 |
| median distance of the last pre-pickup ping to the restaurant (km) | 4.47 |
| of orders with >= 2 pre-pickup pings, last ping FARTHER from the restaurant than the first (%) | 99.00 |
| GPS pings recorded before pickup (%) - Class 6 expected pings only before pickup | 31.00 |
| orders with >= 3 in-area pings | 288.00 |
| of those, perfectly straight constant-speed track, R^2 >= 0.999 (%) | 91.00 |
| of those, perfectly even time gaps between pings, CV < 0.05 (%) | 90.60 |
| delivered orders with GPS pings between pickup and delivery (%) | 99.20 |
| of those with >= 2 pings, last ping closer to the customer than the first (%) | 99.10 |

### late_rate_heatmap_weekday_hour

| weekday | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Monday | 67.00 | 50.00 | 100.00 | 75.00 | 100.00 | 100.00 | 100.00 | 67.00 | 58.00 | 33.00 | 0.00 | 43.00 | 100.00 |
| Tuesday |  | 67.00 | 67.00 | 67.00 |  | 0.00 | 30.00 | 75.00 | 25.00 | 75.00 | 50.00 | 67.00 | 100.00 |
| Wednesday | 50.00 | 86.00 | 40.00 | 100.00 | 100.00 | 33.00 | 67.00 | 60.00 | 60.00 | 44.00 | 75.00 | 0.00 | 33.00 |
| Thursday | 78.00 | 80.00 | 100.00 | 0.00 | 50.00 | 67.00 | 33.00 | 29.00 | 25.00 | 50.00 | 25.00 | 43.00 | 50.00 |
| Friday | 40.00 | 25.00 | 62.00 | 0.00 | 33.00 |  | 67.00 | 40.00 | 50.00 | 78.00 | 0.00 | 0.00 | 50.00 |
| Saturday |  | 50.00 | 0.00 | 50.00 | 100.00 | 100.00 | 62.00 | 67.00 | 60.00 | 67.00 | 71.00 | 67.00 | 100.00 |
| Sunday | 0.00 | 50.00 | 25.00 | 100.00 | 0.00 | 50.00 | 75.00 | 64.00 | 50.00 | 40.00 | 0.00 | 75.00 | 100.00 |

### impact_whatif

| assumed_share_of_caught_late_orders_saved | late_orders_prevented | late_rate_after_pct | kpi_change_pp | support_contacts_avoided | alerts_ops_must_handle | basis |
|---|---|---|---|---|---|---|
| 0.25 | 37 | 45.30 | -9.90 | 8 | 154 | ASSUMPTION - save rate not measured; contact rates from M4/M4a |
| 0.50 | 74 | 35.50 | -19.70 | 17 | 154 | ASSUMPTION - save rate not measured; contact rates from M4/M4a |

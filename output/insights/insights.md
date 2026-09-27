# Decision layer — beyond the classroom

Transparent, non-ML analyses that turn the model into actions the client can take now. Every number is recomputed on each run.

## D1 · A proactive trigger that works today, without AI

**Finding.** Alerting when an order is still not picked up 10 min after Dispatch's own estimated pickup catches 71.5% of late orders with 96.1% precision on the held-out week, a median 44.8 min before the promise breaks.

**So what.** 446 late orders the trigger would have caught received no intervention at all; 169 interventions went to orders that were never at risk.

**Owner.** Operations

## D2 · The promise is optimistic before the food even leaves

**Finding.** Dispatch's pickup estimate is short by a median 8.0 min (planned 18.0 min vs actual 26.0 min from order to pickup). Reaching 80% on-time by padding alone needs +12 min on every promise.

**So what.** Fix the pickup estimate (the input) rather than padding the promise (the output); padding trades lateness for longer quoted times, whose effect on conversion is unknown.

**Owner.** Product / ETA service

## D3 · Do not publish a restaurant or driver blame list

**Finding.** Only 1 of 59 judgeable restaurants (R024) and 1 of 91 drivers are statistically worse than the fleet; a naive top-10 list would name 10 restaurants, of which 1 survive the test.

**So what.** Lateness is systemic; accountability conversations should start with the significant few, with the confidence interval shown.

**Owner.** Restaurant Ops / Fleet Ops

## D4 · The weather label does not match the weather

**Finding.** Against Open-Meteo's observed hourly rainfall, the client's weather_bucket agrees 52.6% of the time (Cohen's kappa 0.009, i.e. no better than chance). Orders labelled heavy rain saw 0.4 mm on average, orders labelled clear 0.46 mm. Observed rain: 58.5% late vs 54.5% when dry.

**So what.** 'Weather causes delays' cannot be defended with this field; ask who writes weather_bucket and when, before any weather-aware ETA or staffing plan.

**Owner.** Operations / Data Team

## D5 · GPS pings look drawn, not measured - they cannot show arrival at the restaurant

**Finding.** Before pickup, the last ping is FARTHER from the restaurant than the first in 99.2% of orders (closer in only 0.8%) - a rider cannot leave with the food before picking it up. 91.3% of tracks with 3+ pings are perfectly straight, constant-speed lines and 90.7% have perfectly even time gaps - real device tracks are never that clean. Class 6 found pings only before pickup; here 30.8% of pings fall before pickup and the rest after it (99.4% of post-pickup tracks close in on the customer).

**So what.** Do not build a geofence or a live GPS ETA on this feed: it would invent arrivals. Ask Fleet Ops whether pings are device readings or app interpolation, and instrument an explicit 'arrived at restaurant' tap - the one event that splits kitchen delay from rider delay, which is where the lateness builds.

**Owner.** Fleet Ops / Product

### early_warning_backtest

| split | grace_min | orders | alerts | alert_rate_pct | late_orders | caught_late | false_alerts | precision_pct | recall_pct | median_lead_min | alerts_before_promise_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 0 | 1111 | 936 | 84.20 | 630 | 628 | 308 | 67.10 | 99.70 | 55.90 | 100.00 |
| train | 5 | 1111 | 711 | 64.00 | 630 | 587 | 124 | 82.60 | 93.20 | 50.10 | 100.00 |
| train | 10 | 1111 | 467 | 42.00 | 630 | 454 | 13 | 97.20 | 72.10 | 44.80 | 100.00 |
| train | 15 | 1111 | 284 | 25.60 | 630 | 284 | 0 | 100.00 | 45.10 | 41.30 | 100.00 |
| train | 20 | 1111 | 177 | 15.90 | 630 | 177 | 0 | 100.00 | 28.10 | 37.30 | 99.40 |
| train | 25 | 1111 | 101 | 9.10 | 630 | 101 | 0 | 100.00 | 16.00 | 30.80 | 99.00 |
| train | 30 | 1111 | 37 | 3.30 | 630 | 37 | 0 | 100.00 | 5.90 | 27.30 | 97.30 |
| test | 0 | 375 | 307 | 81.90 | 207 | 206 | 101 | 67.10 | 99.50 | 56.90 | 100.00 |
| test | 5 | 375 | 234 | 62.40 | 207 | 195 | 39 | 83.30 | 94.20 | 50.50 | 100.00 |
| test | 10 | 375 | 154 | 41.10 | 207 | 148 | 6 | 96.10 | 71.50 | 44.80 | 100.00 |
| test | 15 | 375 | 96 | 25.60 | 207 | 96 | 0 | 100.00 | 46.40 | 41.90 | 100.00 |
| test | 20 | 375 | 52 | 13.90 | 207 | 52 | 0 | 100.00 | 25.10 | 34.80 | 100.00 |
| test | 25 | 375 | 32 | 8.50 | 207 | 32 | 0 | 100.00 | 15.50 | 29.80 | 96.90 |
| test | 30 | 375 | 16 | 4.30 | 207 | 16 | 0 | 100.00 | 7.70 | 25.20 | 100.00 |
| all | 0 | 1486 | 1243 | 83.60 | 837 | 834 | 409 | 67.10 | 99.60 | 56.10 | 100.00 |
| all | 5 | 1486 | 945 | 63.60 | 837 | 782 | 163 | 82.80 | 93.40 | 50.30 | 100.00 |
| all | 10 | 1486 | 621 | 41.80 | 837 | 602 | 19 | 96.90 | 71.90 | 44.80 | 100.00 |
| all | 15 | 1486 | 380 | 25.60 | 837 | 380 | 0 | 100.00 | 45.40 | 41.40 | 100.00 |
| all | 20 | 1486 | 229 | 15.40 | 837 | 229 | 0 | 100.00 | 27.40 | 36.00 | 99.60 |
| all | 25 | 1486 | 133 | 9.00 | 837 | 133 | 0 | 100.00 | 15.90 | 30.30 | 98.50 |
| … 1 more rows … | | | | | | | | | | | |

### early_warning_vs_interventions

| group | orders | with_any_intervention | intervention_before_pickup | intervention_coverage_pct |
|---|---|---|---|---|
| late orders the trigger catches | 602 | 156 | 125 | 25.90 |
| late orders the trigger misses | 235 | 69 | 39 | 29.40 |
| on-time orders the trigger flags (false alerts) | 19 | 5 | 4 | 26.30 |
| on-time orders not flagged | 630 | 169 | 61 | 26.80 |

### eta_calibration

| eta_model_version | padding_min | orders | late_orders | late_rate_pct | on_time_rate_pct |
|---|---|---|---|---|---|
| all versions | 0 | 1486 | 837 | 56.30 | 43.70 |
| all versions | 5 | 1486 | 555 | 37.30 | 62.70 |
| all versions | 10 | 1486 | 344 | 23.10 | 76.90 |
| all versions | 15 | 1486 | 202 | 13.60 | 86.40 |
| all versions | 20 | 1486 | 118 | 7.90 | 92.10 |
| all versions | 25 | 1486 | 50 | 3.40 | 96.60 |
| all versions | 30 | 1486 | 23 | 1.50 | 98.50 |
| eta-v3.1 | 0 | 737 | 406 | 55.10 | 44.90 |
| eta-v3.1 | 5 | 737 | 270 | 36.60 | 63.40 |
| eta-v3.1 | 10 | 737 | 161 | 21.80 | 78.20 |
| eta-v3.1 | 15 | 737 | 95 | 12.90 | 87.10 |
| eta-v3.1 | 20 | 737 | 61 | 8.30 | 91.70 |
| eta-v3.1 | 25 | 737 | 29 | 3.90 | 96.10 |
| eta-v3.1 | 30 | 737 | 12 | 1.60 | 98.40 |
| eta-v3.2 | 0 | 749 | 431 | 57.50 | 42.50 |
| eta-v3.2 | 5 | 749 | 285 | 38.10 | 61.90 |
| eta-v3.2 | 10 | 749 | 183 | 24.40 | 75.60 |
| eta-v3.2 | 15 | 749 | 107 | 14.30 | 85.70 |
| eta-v3.2 | 20 | 749 | 57 | 7.60 | 92.40 |
| eta-v3.2 | 25 | 749 | 21 | 2.80 | 97.20 |
| … 1 more rows … | | | | | |

### fair_ranking_restaurants

| restaurant_id | orders | late_orders | late_rate_pct | ci_low_pct | ci_high_pct | verdict | in_naive_top10 |
|---|---|---|---|---|---|---|---|
| R031 | 22 | 16 | 72.70 | 51.80 | 86.80 | not distinguishable from fleet | False |
| R029 | 24 | 17 | 70.80 | 50.80 | 85.10 | not distinguishable from fleet | False |
| R051 | 29 | 20 | 69.00 | 50.80 | 82.70 | not distinguishable from fleet | True |
| R054 | 20 | 14 | 70.00 | 48.10 | 85.50 | not distinguishable from fleet | False |
| R018 | 27 | 18 | 66.70 | 47.80 | 81.40 | not distinguishable from fleet | True |
| R004 | 29 | 19 | 65.50 | 47.30 | 80.10 | not distinguishable from fleet | True |
| R044 | 22 | 15 | 68.20 | 47.30 | 83.60 | not distinguishable from fleet | False |
| R045 | 29 | 19 | 65.50 | 47.30 | 80.10 | not distinguishable from fleet | True |
| R050 | 35 | 22 | 62.90 | 46.30 | 76.80 | not distinguishable from fleet | True |
| R021 | 19 | 13 | 68.40 | 46.00 | 84.60 | not distinguishable from fleet | False |
| R025 | 28 | 18 | 64.30 | 45.80 | 79.30 | not distinguishable from fleet | True |
| R023 | 32 | 20 | 62.50 | 45.30 | 77.10 | not distinguishable from fleet | True |
| R057 | 25 | 16 | 64.00 | 44.50 | 79.80 | not distinguishable from fleet | False |
| R033 | 29 | 18 | 62.10 | 44.00 | 77.30 | not distinguishable from fleet | False |
| R060 | 29 | 18 | 62.10 | 44.00 | 77.30 | not distinguishable from fleet | False |
| R011 | 31 | 19 | 61.30 | 43.80 | 76.30 | not distinguishable from fleet | True |
| R003 | 20 | 13 | 65.00 | 43.30 | 81.90 | not distinguishable from fleet | False |
| R026 | 27 | 16 | 59.30 | 40.70 | 75.50 | not distinguishable from fleet | False |
| R041 | 32 | 18 | 56.20 | 39.30 | 71.80 | not distinguishable from fleet | False |
| R002 | 28 | 16 | 57.10 | 39.10 | 73.50 | not distinguishable from fleet | False |
| … 41 more rows … | | | | | | | |

### fair_ranking_drivers

| driver_id | orders | late_orders | late_rate_pct | ci_low_pct | ci_high_pct | verdict | in_naive_top10 |
|---|---|---|---|---|---|---|---|
| D080 | 14 | 4 | 28.60 | 11.70 | 54.60 | better than fleet (significant) | False |
| D038 | 15 | 4 | 26.70 | 10.90 | 52.00 | better than fleet (significant) | False |
| D119 | 15 | 3 | 20.00 | 7.00 | 45.20 | better than fleet (significant) | False |
| D011 | 12 | 10 | 83.30 | 55.20 | 95.30 | not distinguishable from fleet | False |
| D031 | 12 | 10 | 83.30 | 55.20 | 95.30 | not distinguishable from fleet | False |
| D054 | 18 | 14 | 77.80 | 54.80 | 91.00 | not distinguishable from fleet | True |
| D017 | 22 | 16 | 72.70 | 51.80 | 86.80 | not distinguishable from fleet | True |
| D046 | 18 | 13 | 72.20 | 49.10 | 87.50 | not distinguishable from fleet | True |
| D001 | 20 | 14 | 70.00 | 48.10 | 85.50 | not distinguishable from fleet | True |
| D087 | 15 | 11 | 73.30 | 48.00 | 89.10 | not distinguishable from fleet | True |
| D063 | 17 | 12 | 70.60 | 46.90 | 86.70 | not distinguishable from fleet | True |
| D094 | 17 | 12 | 70.60 | 46.90 | 86.70 | not distinguishable from fleet | True |
| D018 | 12 | 9 | 75.00 | 46.80 | 91.10 | not distinguishable from fleet | False |
| D040 | 12 | 9 | 75.00 | 46.80 | 91.10 | not distinguishable from fleet | False |
| D076 | 19 | 13 | 68.40 | 46.00 | 84.60 | not distinguishable from fleet | True |
| D008 | 14 | 10 | 71.40 | 45.40 | 88.30 | not distinguishable from fleet | False |
| D022 | 16 | 11 | 68.80 | 44.40 | 85.80 | not distinguishable from fleet | True |
| D025 | 11 | 8 | 72.70 | 43.40 | 90.30 | not distinguishable from fleet | False |
| D010 | 26 | 16 | 61.50 | 42.50 | 77.60 | not distinguishable from fleet | True |
| D088 | 13 | 9 | 69.20 | 42.40 | 87.30 | not distinguishable from fleet | False |
| … 100 more rows … | | | | | | | |

### weather_label_vs_observed

| weather_bucket | orders | observed_rain_share_pct | mean_observed_mm |
|---|---|---|---|
| clear | 1273 | 46.00 | 0.46 |
| heavy_rain | 78 | 46.20 | 0.40 |
| rain | 249 | 47.80 | 0.60 |

### late_rate_label_vs_observed_weather

| signal | orders | late_rate_pct |
|---|---|---|
| client label: clear | 1185 | 53.20 |
| client label: heavy_rain | 72 | 73.60 |
| client label: rain | 229 | 66.80 |
| observed: dry | 797 | 54.50 |
| observed: raining | 689 | 58.50 |

### gps_arrival_feasibility

| check | value |
|---|---|
| orders with pre-pickup GPS pings | 1,166.00 |
| orders with >= 2 pre-pickup pings | 374.00 |
| of those, last ping closer to the restaurant than the first (%) | 0.80 |
| orders with any pre-pickup ping within 1 km of the restaurant (%) | 5.90 |
| median distance of the last pre-pickup ping to the restaurant (km) | 4.35 |
| of orders with >= 2 pre-pickup pings, last ping FARTHER from the restaurant than the first (%) | 99.20 |
| GPS pings recorded before pickup (%) - Class 6 expected pings only before pickup | 30.80 |
| orders with >= 3 in-area pings | 1,111.00 |
| of those, perfectly straight constant-speed track, R^2 >= 0.999 (%) | 91.30 |
| of those, perfectly even time gaps between pings, CV < 0.05 (%) | 90.70 |
| delivered orders with GPS pings between pickup and delivery (%) | 99.10 |
| of those with >= 2 pings, last ping closer to the customer than the first (%) | 99.40 |

### late_rate_heatmap_weekday_hour

| weekday | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Monday | 41.00 | 58.00 | 54.00 | 50.00 | 82.00 | 64.00 | 71.00 | 56.00 | 62.00 | 41.00 | 50.00 | 55.00 | 86.00 |
| Tuesday | 71.00 | 71.00 | 58.00 | 60.00 | 50.00 | 25.00 | 37.00 | 62.00 | 46.00 | 39.00 | 70.00 | 55.00 | 67.00 |
| Wednesday | 56.00 | 65.00 | 58.00 | 86.00 | 57.00 | 64.00 | 58.00 | 75.00 | 57.00 | 56.00 | 40.00 | 40.00 | 56.00 |
| Thursday | 69.00 | 69.00 | 38.00 | 42.00 | 71.00 | 67.00 | 67.00 | 57.00 | 43.00 | 50.00 | 25.00 | 46.00 | 73.00 |
| Friday | 60.00 | 55.00 | 71.00 | 38.00 | 60.00 | 55.00 | 55.00 | 65.00 | 55.00 | 79.00 | 23.00 | 45.00 | 56.00 |
| Saturday | 57.00 | 50.00 | 45.00 | 50.00 | 88.00 | 80.00 | 72.00 | 72.00 | 49.00 | 37.00 | 56.00 | 50.00 | 100.00 |
| Sunday | 67.00 | 24.00 | 53.00 | 67.00 | 56.00 | 50.00 | 55.00 | 51.00 | 62.00 | 58.00 | 21.00 | 50.00 | 75.00 |

### impact_whatif

| assumed_share_of_caught_late_orders_saved | late_orders_prevented | late_rate_after_pct | kpi_change_pp | support_contacts_avoided | alerts_ops_must_handle | basis |
|---|---|---|---|---|---|---|
| 0.25 | 150 | 46.20 | -10.10 | 38 | 621 | ASSUMPTION - save rate not measured; contact rates from M4/M4a |
| 0.50 | 301 | 36.10 | -20.30 | 77 | 621 | ASSUMPTION - save rate not measured; contact rates from M4/M4a |

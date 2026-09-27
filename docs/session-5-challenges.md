# Session 5 challenges — fetching data using SQL, APIs and files

Source: `session-5/` lecture transcript, `FlashEats_Class5_Solution.pdf`, `FlashEats_Class_solution.txt` (instructor notebook) and the classroom pack's `FlashEats_Class5_Student.ipynb` (copied to `notebooks/classroom_originals/`).
Completed notebooks, with the instructor's original cells kept in order and answers inserted and executed:
- **`Challenges/FlashEats_Class5_Starter.ipynb`** answers the Starter challenges **in SQL**.
- **`Challenges/FlashEats_Class5_Student.ipynb`** answers the Student challenges in pandas.

The logic is productionised in the pipeline as listed below.

| Challenge (as set by the instructor) | What was required | Where it is done | Evidence |
|---|---|---|---|
| **Source map first** — predict where each fact lives; which source is authoritative vs contextual | table of information → source → why | `docs/source-map.md`; notebook §"Source map first" | table with trust levels and gaps |
| **Challenge 1 — How large is the late-delivery problem?** define *late*, denominator, cancelled policy, missing-timestamp policy, row grain; then valid delivered, late count/%, median lateness, worst orders, DQ issues that change the metric | SQL retrieval + pandas analysis | notebook Ch1; pipeline `sql/orders_extract.sql`, `cleaning.py` (dedupe), `rules.py` TS-01/02/04, `metrics.py` M1/M1a/M2/M2b, breakdown `worst_delays` | 1603 rows → 1600 orders; 68 cancelled; 37 missing; **843/1495 = 56.4 %** (class definition), **837/1486 = 56.33 %** (validated); median 8.0 min; worst genuine delay O01081 +50.3 min; the 4 largest "delays" are the promise-before-creation bugs |
| **Checkpoint** — if counts differ, investigate duplicates, cancellations, missing timestamps, definition, grain | definition comparison | `output/breakdowns/definition_comparison.csv`; notebook Ch1 markdown | five definitions side by side |
| **Challenge 2 — "Traffic is the problem"** test on ≥ 3 dimensions; 2–3 comparisons, one chart, one supported hypothesis, one alternative explanation; association ≠ causation | groupby + chart | notebook Ch2 (traffic, weather, distance, hour + chart `Challenges/output/class5_traffic_weather.png`); pipeline breakdowns `late_rate_by_traffic/weather/distance_band/hour` + `output/charts/*.png` | hypothesis: traffic and weather associated (49 % → 66 %, 53 % → 74 %); alternative: evening peak load confounds; distance not associated |
| **Challenge 3 — Customer Support disagrees** categories, most common, unique ticket ids, customer story vs operational story, what tickets tell that timestamps cannot; output: system view vs customer view | CSV read, value_counts, LEFT merge on `order_id` | notebook Ch3; pipeline `fact_interaction`, breakdown `customer_view_vs_system_view` | 202 rows / 201 ids / 1 duplicate / 3 without order; `late_delivery` most common; tickets' median delay 14.8 min vs 1.4 overall; comparison table |
| **Challenge 4 — Dispatch API: prove you retrieved everything** start API, inspect one response, retrieve all, pagination, retry 429/500, save every raw page, prove completeness | `while` loop with retries; raw preservation | notebook Ch4 (uses `DispatchApiClient`); pipeline `ingest/api_source.py` + `data/raw/<run>/api/dispatch_page_*.json` + `ingestion_report.json` | 16 pages × 100 = 1600 = `total_records`, 1600 unique ids, page 3 (500) and page 5 (429) retried; `assert report.complete` |
| **Challenge 5 — Can we attribute the delay?** flatten nested JSON; observed vs inferred; is there a reliable *driver arrived at restaurant* event? | flatten + event counts + table | notebook Ch5; pipeline `ingest/file_source.flatten_driver_events`, rules TS-07 / RG-03, model note | 0 arrival events; assigned 1600 / picked_up 1532 / delivered 1532 / gps 5371; 189 outlier pings; 14 orders with pickup before assignment; 37 recoverable delivery timestamps |
| **Final FDE synthesis (one slide)** problem size, evidence, trusted sources, uncertainty, instrumentation recommendation, decision on the AI delay predictor | one-slide markdown | notebook final section; `docs/demo-script.md` | decision: **do not build the predictor yet** — fix instrumentation and KPI ownership first |

## Lecture concepts → implementation

| Concept taught | Implementation |
|---|---|
| retrieve only the rows/columns you need; keep SQL reviewable | `sql/*.sql` files, `customers_extract.sql` deliberately drops name/email |
| `pd.read_sql`, `pd.read_csv`, `json.load` + flatten | `ingest/sql_source.py`, `ingest/file_source.py` |
| `nunique()` vs `len()` — deduplication before anything else | `cleaning.dedupe` (exact vs conflicting duplicates) |
| `pd.to_datetime(format="mixed", errors="coerce")` | `timestamps.parse_timestamps` (plus tz handling and statistics) |
| valid population = delivered ∧ actual not null ∧ promised not null | `model.build_fact_order` → `kpi_population` |
| `groupby(...).agg(count, median, mean)` | `metrics._rate_table` |
| LEFT merge with tickets as base table | `metrics` customer-view breakdown; `order_journey` aggregation-before-join |
| pagination loop, retry on 429/500 with back-off, raw page per file, `len(records) != expected_total` ⇒ error | `DispatchApiClient.fetch_all` |
| "preserve raw API responses; do not silently drop failures" | `data/raw/<run_id>/` + `IngestionReport.issues` + gate |

## Class 5 Starter notebook (the fourth classroom notebook)

The Starter is a shorter version of the same five challenges, with an empty `-- YOUR SQL HERE` cell and an empty `fetch_all_dispatch_orders()`. It is answered differently on purpose:

| Starter challenge | How it is answered | Result |
|---|---|---|
| 1 Late-delivery size | **Three SQL queries**, each fixing one trap: naive, then one row per order with normalised status, then chronology rules | 1493/841, then **1495/843 = 56.39 %**, then **1486/837 = 56.33 %**; every difference is explained |
| 2 Traffic claim | one parameterised SQL query grouped by traffic, weather, distance band and hour | association only; distance shows a weak gradient |
| 3 Support tickets | uniqueness, normalisation and a join to the validated population | 1 duplicated ticket, 3 without an order; 68–91 % of ticketed orders were late |
| 4 Dispatch API | the skeleton's `fetch_all_dispatch_orders()` implemented **by hand**: retries 429/500 honouring `retry_after_seconds`, validates the body, saves raw pages, detects overlap and checks the total | 16 pages, 1600 records, pages 3 and 5 retried |
| 5 Driver events | observed vs inferred, **plus an actual geofence attempt and a track-shape test** | before pickup, pings head for the restaurant in < 1 % of orders, and 91 % of tracks are perfect straight lines (they look interpolated), so arrival cannot be inferred |
| Final recommendation | a one-slide answer | no AI yet; ship the pickup-overrun trigger as the baseline |

The skeleton cells wrote to `source_systems/student_output/`. They were redirected to `Challenges/output/`, so the client snapshot is never modified.

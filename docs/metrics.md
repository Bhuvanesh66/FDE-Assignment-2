# Metrics — definitions, formulas and interpretation

Computed by `src/flasheats_pipeline/metrics.py`; values for the last run in `output/metrics.csv` / `output/metrics.md`; all breakdowns in `output/breakdowns/`. Every metric is computed on **`fact_order` / `order_journey` at order grain**, so no join can inflate a count (see `data/processed/join_checks.json`).

| # | Metric (category) | Business question | Formula | Source tables & joins | Filters / population | Edge cases handled | Value (last run) |
|---|---|---|---|---|---|---|---|
| **M1** | Late delivery rate (outcome, **project KPI**) | How large is the problem? | late / validated delivered | `fact_order` | `kpi_population`: delivered, both timestamps, TS-01/02/03 pass | zero denominator → value `None`, gate FAIL; cancelled excluded; unknown outcomes excluded and counted | **56.33 %** (837 / 1486) |
| M1a | … historical dashboard definition | Does it reproduce the leadership claim? | same, on delivered with non-null actual | `fact_order` | no chronology rules | — | 56.39 % (843 / 1495) = leadership's "56 %" |
| M1b | Meaningfully late rate | Support Lead's definition | delay > 10 min / validated | `fact_order` | as M1 | threshold configurable | 23.15 % |
| M1c | Sensitivity: back-fill from driver telemetry | What if the driver `delivered` event is trusted? | as M1 on back-filled timestamps | `fact_order` ⟕ driver events (aggregated) | adds the 37 recovered orders | reported, **not published** | 56.53 % (861 / 1523) |
| **M2** | Median lateness among late orders (outcome) | How late is late? | median(delay_min \| late) | `fact_order` | late orders | none late → `None` | **8.0 min** |
| M2a/b | P90 delay / worst delay | tail severity | quantile 0.9 / max | `fact_order` | validated | — | 17.9 min / 50.3 min |
| **M3** | Share of lateness accumulated before pickup (workflow) | *Where* does delay build up? | Σ max(pickup − est. pickup, 0) / Σ all positive stage overruns, late orders | `fact_order` (orders ⟕ Dispatch) | late orders with `estimated_pickup_at` | identity `pre-pickup + transit = delay` asserted each run (max residual 0.01 min) | **98.9 %** |
| M3a/b | Median pre-pickup / transit overrun on late orders | how big is each stage's overrun | median | `fact_order` | late orders | — | +13.9 min / −5.9 min |
| **M4** | Support contact rate on late orders (interaction) | How often does a late order become a customer contact? | late orders with ticket ∨ SUPPORT_OPENED / late orders | `order_journey` (fact_order ⟕ aggregated app actions ⟕ aggregated tickets) | late orders | tickets without order id cannot count | **30.7 %** (vs 5.2 % on-time, M4a) |
| M4b | Frustrated journeys without intervention | missed opportunities | support contact ∧ no intervention | `order_journey` | all orders | — | 218 (191 of them late) |
| **M5** | Intervention coverage (intervention) | How much of the workflow does ops touch? | orders with ≥ 1 intervention / validated orders | `order_journey` ⟕ aggregated interventions | validated | at most one intervention per order in this pack | **26.9 %** |
| M5a/b | Late rate with / without intervention | are interventions associated with better outcomes? | late / orders per group | `order_journey` | validated | **selection effect**: interventions target late-risk orders | 56.4 % / 56.3 % |
| M5c | Most common intervention type | what ops actually does | mode | `fact_intervention` | all | — | DRIVER_REASSIGNMENT (155) |

## Interpretation for the business

1. **The problem is real and large:** more than half of validated deliveries miss the promise; half of the late orders are late by 8 minutes or more; one in four deliveries is more than 10 minutes late.
2. **Delay is not built on the road.** Late orders reach the driver's hands a median 14 minutes after Dispatch's estimated pickup time, then travel *faster* than planned (−6 min). 92.5 % of late orders overran **only** before pickup. The lever is the dispatch→pickup stage (kitchen, driver-to-restaurant, waiting), not routing. Because no "arrived at restaurant" event exists, the data cannot yet say which of kitchen or rider owns it.
3. **Customers notice:** a late order is six times more likely to generate a support contact than an on-time one; 218 frustrated journeys received no intervention at all.
4. **Interventions do not (yet) move the KPI in the data,** but this is an association with a strong selection effect and an interventions log that does not reconcile with Dispatch — the honest statement is "we cannot evaluate intervention effectiveness until the logs agree".
5. **Descriptive associations** (breakdowns): late rate rises with traffic (49 % low → 66 % severe) and weather (53 % clear → 74 % heavy rain) and peaks 18:00–19:00 and after 23:00; distance is *not* associated; no restaurant contributes more than 2.6 % of late orders (systemic, not a few kitchens).

## Independent validation performed on every run

| Check | Method | Result |
|---|---|---|
| M1 recomputed straight from the raw SQLite with SQL (`sql/independent_late_rate_check.sql`) | dedup by rowid, same rules in SQL | 1486 / 837 — identical |
| Reconciliation with the client's derived `order_outcomes.csv` | per-order late flag and delay diff | 843 = 843, max delay diff 0.000 min |
| Join cardinality | every merge preserves the left row count | 5/5 preserved |
| Outcome buckets sum to unique orders; late + on-time = population | arithmetic | pass |
| Stage identity | pre-pickup + transit overrun = delay | max residual 0.010 min |
| Denominator > 0 | guard | pass |

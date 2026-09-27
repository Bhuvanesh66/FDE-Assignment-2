# Session 7 challenges — modelling the business workflow with data

Source: `session-7/` lecture transcript, `data/class7_model_brief.json` (project KPI: *reduce late delivery rate*; question: *where in the order lifecycle do delays accumulate, and which interventions are associated with better outcomes?*) and `FlashEats_Class7_Challenge.ipynb` (six challenges; copied to `notebooks/classroom_originals/`).
Completed notebook: **`notebooks/Session7_Challenges.ipynb`** (executed on the modelled tables). Productionised in `model.py` and `metrics.py`.

| Challenge | Required output | Where it is done | Evidence |
|---|---|---|---|
| **1 — Reconstruct the order lifecycle** timelines (`event_time | event_type | actor | source_system`) for one on-time, one late and one intervened order, from every source, sorted by time | `build_order_timeline(order_id)` | notebook Ch1; pipeline `model.build_fact_event` → `data/processed/fact_event.csv` (21 518 events, 7 source systems) | three timelines printed; the assign→pickup gap has no arrival event; cancelled orders have no terminal event |
| **2 — Define the canonical project model** customer → orders, order → customer interactions, order → support interactions, order → interventions, order → outcome; PK / FK / grain per table; why better than mirroring source tables | model documentation | `docs/data-model.md` (ER + workflow diagrams); notebook Ch2; `model.py` docstring; `data/processed/join_checks.json` | 3 dims, 4 facts, `order_journey`; every table asserted unique on its key; all merges preserve row counts |
| **3 — Build interaction → intervention → outcome** one order-level table with `order_id, customer_id, support_opened, cancel_attempted, intervention_count, intervention_types, final_status, late_flag, delay_min`; answer: late orders with support interaction, orders with intervention, most common intervention, frustrated journeys with no intervention | aggregate one-to-many tables *before* joining | `model.build_order_journey` → `data/processed/order_journey.csv`; notebook Ch3; metrics M4, M4b, M5, M5c; breakdown `journey_patterns.csv` | 257 of 837 late orders had a support interaction (30.7 %); 430 orders received an intervention; DRIVER_REASSIGNMENT (155) most common; 218 frustrated journeys without intervention (191 late) |
| **4 — Select 3–5 business metrics** name, formula, grain, why it matters, KPI relationship; at least one outcome, one interaction, one intervention metric | metric documentation | `docs/metrics.md`; `output/metrics.csv`; notebook Ch4 | M1 outcome, M2 outcome, M3 workflow, M4 interaction, M5 intervention |
| **5 — Investigate the workflow with joins and aggregations** ≥ 3 of: A delay with vs without support interaction; B late rate with vs without intervention; C intervention type with lowest late rate; D restaurants contributing most late orders; E support + intervention + still late — each with "what it tells / what it does NOT prove" | joins/groupby + one sentence each | notebook Ch5 (all five); pipeline breakdowns `late_rate_by_intervention_type`, `top_restaurants_by_late_orders`, `journey_patterns`, M5a/M5b | A 88 % vs 49 % late; B 56.4 % vs 56.3 %; C PRIORITY_DISPATCH lowest (51 %), CUSTOMER_CREDIT highest (67 %, issued after the fact); D top restaurant = 2.6 % of late orders; E 66 journeys |
| **6 — Connect the model to the KPI** one-page view `PROJECT KPI → OUTCOME METRIC → WORKFLOW/DRIVER METRICS → INTERVENTIONS → DATA SOURCES/EVENTS`; which metrics are controllable, which are outcomes, which missing event limits the model most, what to instrument next | one-page view + answers | notebook Ch6; `README.md` (KPI tree); `docs/assumptions-limitations.md` | missing event: *driver arrived at restaurant*; instrument next: arrival event, mandatory delivery timestamp, reassignment propagation, cancellation timestamp |
| **Final reflection** — the smallest useful model that explains the workflow and supports the KPI | — | notebook final cell; `docs/data-model.md` §5 | — |

Lecture concepts applied:

| Concept taught | Implementation |
|---|---|
| entity / event / state distinction; one order has many events, interactions, interventions; one outcome | `docs/data-model.md` §2; facts vs `order_journey` |
| "aggregate the one-to-many tables back to the order grain" (`groupby(order_id).count`) then LEFT merge onto outcomes | `build_order_journey` with `_checked_merge` |
| cardinality check of the new sources (100 % mapping ⇒ dependable) | rules ID-07, ID-08 |
| ETA viewed many times as a possible early-warning signal — not deterministic | M4c (median ETA views late vs on-time) reported as *association only* |
| interventions targeted at late-risk orders ⇒ evaluation needs care | M5a/M5b labelled "selection effect", CX-03 finding that logs do not reconcile |
| outcomes table = late_flag / delay_min / outcome bucket derived from the orders table | rebuilt from primary sources and reconciled with the client's `order_outcomes.csv` (843 = 843) |
| the instructor's `order_events.csv` / `customer_interactions.csv` are derived artefacts | treated as reference-only sources (see `docs/source-map.md`) |

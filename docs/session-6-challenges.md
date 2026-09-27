# Session 6 challenges — data profiling and validation

Source: `session-6/` lecture transcript and `FlashEats_Class6_Student.ipynb` (six challenges; copied to `notebooks/classroom_originals/`). The instructor's framing: *validation is decision-dependent; turn assumptions into contracts; separate technical / semantic / organisational validation; never silently fix ambiguity; output a validation gate.*
Completed notebook: **`notebooks/Session6_Challenges.ipynb`** (executed). Productionised in `profiling.py`, `cleaning.py`, `rules.py`, `gate.py`.

| Challenge | Required output | Where it is done | Evidence |
|---|---|---|---|
| **1 — Can we defend the "56 % late" claim?** validation contract (assumption → expectation → test → severity) *before* calculating; establish grain, delivered-without-completion, `promised_eta ≥ created_at`, `pickup_at ≤ actual_delivery_at`, list assumptions needing stakeholder clarification | contract table + checks | notebook Ch1; pipeline rules GR-01, TS-01…05, `output/data_quality_report.md` §5 | 1603/1600; 37; 4; 5; 0; 3 null restaurant, 3 null driver; four owner questions listed |
| **2 — Stakeholders disagree on "late"** metric under ≥ 3 definitions (any > 0, > 10 min, historical population); which to publish and who owns it | definition table + answer | notebook Ch2; pipeline `metrics` M1/M1a/M1b/M1c, `breakdowns/definition_comparison.csv`, rule KPI-01, gate check "KPI definition ownership" (UNKNOWN) | 56.39 % / 23.3 % / 56.39 % / 56.33 % validated; recommendation: VP Ops definition on validated population, owner signature pending |
| **3 — Validate categories without cleaning by instinct** for `final_status`, `traffic_bucket`, restaurant `status`, ticket `category`: observed values, representation vs semantics, safe to normalise vs owner confirmation | table | notebook Ch3; pipeline `cleaning.VOCAB` / `SEMANTIC_CANDIDATES`, rules ST-01…09, `output/data_quality_report.md` §1 and §3 | `Delivered`, `HIGH`, `READY/Ready/ready `, `Late Delivery`, `late_delivery ` normalised and logged; `handoff` and `ETA issue` kept + flagged |
| **4 — Cross-source integrity** coverage % for `orders.restaurant_id → restaurants`, `orders.driver_id → drivers`, `tickets.order_id → orders`, `restaurant_status.order_id → orders`; is 1 % unmapped acceptable? | coverage table + discussion | notebook Ch4; pipeline rules ID-02…ID-10, CX-01…03, gate check "Cross-source mapping" | 99.81 / 99.81 / 98.51 / 100 %; plus the finding that `orders.driver_id` is stale after reassignment (CX-01) and the interventions log does not reconcile with Dispatch (CX-03); answer: acceptable for the KPI, not for scorecards |
| **5 — Freshness is an SLA question** join `restaurant_status` to order timestamps; fresh enough for weekly analytics / live ETA / accountability? | timing analysis + verdict per use case | notebook Ch5; pipeline rule FR-01 (`status_freshness_sla_min`), gate check "Freshness" | 500 of 1600 orders, minute precision, 8 `ready/handed_off` > 15 min after pickup, 5 updates before creation → weekly WARN/usable, live FAIL, accountability FAIL |
| **6 — Build the validation gate** PASS / WARN / FAIL / UNKNOWN for grain, chronology, KPI definition, category semantics, cross-source mapping, freshness; should leadership publish 56 % today; what must happen first | gate table + decision | notebook Ch6; pipeline `gate.build_gate` → `output/validation_gate.md` / `.json` (adds retrieval completeness and metric sanity) | overall **WARN → publish with caveats**; three preconditions for an uncaveated number |

Also implemented from the lecture (concept walkthrough, not numbered challenges):

| Lecture point | Implementation |
|---|---|
| inspect column types, numeric ranges, category distributions, suspicious values before using data | `profiling.py` → `output/profile/profile.md` (+ `.json`) |
| distance > 50 km or ≤ 0 is suspicious; do not just drop outliers — take them to the stakeholder | rule RG-01 (flag, retain) |
| unexpected categories such as `gridlock`: is it a new category or an anomaly? ask, do not map | `SEMANTIC_CANDIDATES` reported, never merged; tested with `gridlock` / `refunded` / `suspended` |
| timestamp inconsistencies (`promised_eta < created_at`, `actual < pickup`) as business rules whose violators are listed by order id | TS-01/TS-02 (reject from KPI population, listed in report) |
| identifier mismatch across four datasets; "an order that is not yours" | ID-05…ID-10 with coverage % |
| restaurant `manual_status_updates` and `unknown` status make the feed unreliable | FR-01 detail; `dim_restaurant.manual_status_updates` kept for the accountability caveat |
| GPS pings after pickup are needed for driver-behaviour investigation | notebook Ch5 (Session 5) counts pings before/after pickup: 1632 / 3739 in this pack version |
| the `client_metric_definitions.json` file was added for Class 6 | ingested; feeds rule KPI-01 and the gate |

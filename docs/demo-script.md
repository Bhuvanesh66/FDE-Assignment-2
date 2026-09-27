# Demo script (3–5 minutes) and the FDE judgement call

## 0:00 — The problem and the KPI (30 s)
"FlashEats says late deliveries are rising and wants an AI delay predictor. Leadership quotes a 56 % late rate. Before anyone builds a model, we need a number we can trust and we need to know *where* the delay comes from. Project KPI: reduce the late delivery rate."

## 0:30 — Run it (45 s)
```
python run_pipeline.py --start-api
```
Show the log scrolling through the eight stages: SQL extracts, CSV/JSON reads, 16 API pages with page 3 and page 5 retried, the profile, the cleaning actions (`Delivered → delivered`, 3 conflicting duplicates quarantined), the rules, the model, the metrics, the gate. Point at `data/raw/<run_id>/` — every raw page and file is preserved with a hash.

## 1:15 — The evidence table (60 s)
Open `output/evidence_table.md` (or `dashboard.html`):
- **M1 56.33 % of 1486 validated deliveries** are late — and the dashboard definition gives 56.39 %, so leadership's "56 %" is right *for its definition*.
- **M3 98.9 % of lateness accumulates before pickup** — the road is not the problem, the dispatch → pickup stage is.
- **M4 30.7 %** of late orders turn into a support contact (vs 5 % on time).
- **M5** interventions touch 27 % of orders with no visible association to a lower late rate — and the interventions log does not reconcile with Dispatch.
- The gate says **WARN → publish with caveats**, and lists exactly which owner has to answer which question.

## 2:15 — The judgement call (75 s)
**"37 delivered orders have no delivery timestamp — but the driver app has a `delivered` event for every one of them. Do I back-fill?"**

Options:
1. *Back-fill silently* → cleaner number (56.53 %), but I would be inventing the client's system-of-record value from a secondary source that itself has 14 impossible sequences (`picked_up` before `assigned`).
2. *Drop them silently* → the class number (56.39 %), but the KPI would be biased if the missing timestamps are not random (e.g. a crash on very late deliveries).
3. **What I did:** exclude them from the published population, report them as *unknown outcome*, compute the back-filled rate **as a sensitivity** (56.5 %), bound the KPI (55.0 %–57.4 %), and route the decision to Fleet Ops through the gate. The number stays defensible, the uncertainty stays visible, and the owner gets a concrete question.

The same principle runs through the rest: chronology violations are excluded and listed (not fixed), `handoff` is not merged into `handed_off`, `gridlock` would not be mapped to `severe`, and the orders table's stale `driver_id` is replaced by Dispatch's only because the evidence (1597 of 1600 equal the *original* driver) says so.

## 3:30 — Decision and next step (30 s)
"Do not build the delay predictor yet. Instrument *driver arrived at restaurant*, make the delivery timestamp mandatory, propagate reassignments, and sign off the definition of late. This pipeline is the baseline any future model will be judged against — and it reruns in 15 seconds."

## Backup slides / questions
- "Why 1486 and not 1495?" → `output/breakdowns/definition_comparison.csv`
- "Prove the API retrieval is complete" → `data/raw/<run_id>/api/ingestion_report.json`
- "What breaks if the data is messier?" → `python -m pytest` (73 tests: tz-mixed timestamps, `gridlock`, 999 km, duplicate events, half-covered Dispatch, API 429/500/timeout/malformed…)
- "Show me the SQL" → `sql/`, `sql/independent_late_rate_check.sql`

# FlashEats — a dependable late-delivery KPI pipeline

**FDE Data Foundations Assignment (Classes 4–8) · Track A (FlashEats-style) · Bhuvanesh M S**

> *"Late deliveries are increasing and customers say our ETA is unreliable. Figure out what is happening before we invest in an AI delay-prediction system."* — leadership also claims **"Late Delivery Rate is 56 %"**.

This repository turns FlashEats' fragmented client systems (SQLite application DB, a paginated Dispatch API, CSV exports and nested JSON telemetry) into a **small, explainable, repeatable pipeline** that produces trustworthy business metrics, states what they cannot prove, and supports one decision: *where to intervene first, and whether the AI predictor is justified yet.*

## 1. Problem, stakeholders, KPI

| | |
|---|---|
| **Problem** | More than half of deliveries miss the promised ETA; nobody agrees on the number, and nobody knows *where* in the workflow the delay is created. |
| **Users / stakeholders** | VP Operations (KPI owner, proposed) · Support Lead · Finance · Data Team · Dispatch · Fleet Ops · Restaurant Ops · Product / App |
| **Project KPI** | **Reduce the late delivery rate** — share of validated deliveries with `actual_delivery_at − promised_eta > 0 min` |
| **Decision the output supports** | Which lifecycle stage to fix first (dispatch → pickup vs transit), whether interventions can be evaluated yet, and whether to fund the AI delay predictor now. |

## 2. Headline evidence (run `run_example`, gate **WARN → publish with caveats**)

| # | Metric | Value | What it answers |
|---|---|---|---|
| **M1** | Late delivery rate (validated population) | **56.33 %** (837 / 1 486) — 56.39 % under the historical dashboard definition, so leadership's "56 %" holds for its definition | How large is the problem? |
| **M2** | Median lateness among late orders · P90 delay | **8.0 min** · 17.9 min | How late is late? |
| **M3** | Share of lateness accumulated **before pickup** | **98.9 %** (late orders pick up 14 min after Dispatch's estimate, then travel 6 min *faster* than planned) | Where does delay build up? |
| **M4** | Support contact rate on late orders | **30.7 %** (vs 5.2 % on-time) · 218 frustrated journeys received no intervention | How do customers react? |
| **M5** | Intervention coverage · late rate with / without | **26.9 %** · 56.4 % / 56.3 % (association only; the interventions log does not reconcile with Dispatch) | Do interventions reach the right orders? |

Full table with numerators, definitions and Known/Unknown/Assumption/Limitation: [`output/evidence_table.md`](output/evidence_table.md) · dashboard: [`output/dashboard.html`](output/dashboard.html) · gate: [`output/validation_gate.md`](output/validation_gate.md).

**FDE judgement call:** 37 delivered orders have no delivery timestamp although the driver app recorded a `delivered` event for each. They are **not** back-filled and **not** dropped silently: they are reported as *unknown outcome*, the KPI is bounded (55.0–57.4 %), the back-filled rate (56.5 %) is shown as a sensitivity, and Fleet Ops gets the decision. See [`docs/demo-script.md`](docs/demo-script.md).

## 3. From client systems to a decision

```
 SOURCE SYSTEMS                 PIPELINE (python run_pipeline.py)                          OUTPUT
 ┌ Orders DB  (SQL) ─────┐   1 ingest      raw snapshot per run (hashes, raw API pages)   metrics.csv / evidence_table.md
 │ Dispatch API (REST) ──┤   2 profile     rows, nulls, layouts, ranges, duplicates        data_quality_report.md (+ quarantine)
 │ Tickets (CSV) ────────┼─► 3 clean       representation only, everything logged      ─► validation_gate.md  PASS/WARN/FAIL/UNKNOWN
 │ Restaurant feed (CSV) │   4 validate    37 business rules → KPI population              breakdowns/*.csv, charts/*.png, dashboard.html
 │ Driver app (JSON) ────┤   5 model       dims + facts + order_journey (order grain)       known_unknown_assumption_limitation.md
 │ App actions (CSV) ────┤   6 metrics     M1–M5 + independent SQL / reference checks     run_manifest.json, pipeline.log
 └ Interventions (CSV) ──┘   7 gate  8 publish                                            data/processed/*.csv + flasheats_model.sqlite
```

Source map (ownership, grain, gaps): [`docs/source-map.md`](docs/source-map.md) · workflow + data model diagrams: [`docs/data-model.md`](docs/data-model.md).

## 4. What the workflow model looks like

```
customer ──places──► ORDER ──assigned──► driver ──(arrived at restaurant? NOT RECORDED)──► picked up ──► delivered | cancelled
                        │                                                                        ▲
                        ├── interactions: ETA_VIEWED · SUPPORT_OPENED · CANCEL_ATTEMPTED · SUPPORT_TICKET
                        └── interventions: DRIVER_REASSIGNMENT · RESTAURANT_CONTACT · PRIORITY_DISPATCH · CUSTOMER_CREDIT
   outcome per order: late_flag · delay_min · outcome_bucket (delivered_late / on_time / cancelled / unknown / excluded_dq_rule)
```

Tables at explicit grain: `dim_customer`, `dim_restaurant`, `dim_driver`, `fact_order`, `fact_event` (21 518 events from 7 systems), `fact_interaction`, `fact_intervention`, `order_journey` (interaction → intervention → outcome, one row per order). Every one-to-many table is aggregated to order grain **before** joining; every merge is cardinality-checked.

**KPI tree:** reduce late rate (M1) ← severity (M2) ← *where* the delay accrues (M3: dispatch→pickup stage) ← customer reaction (M4) ← interventions (M5) ← events from the seven source systems. The missing *driver-arrived-at-restaurant* event is the single biggest limitation: it prevents splitting the pre-pickup stage into kitchen time and rider time.

## 5. What the data-quality work found (nothing silently fixed)

| Finding | Action |
|---|---|
| 1 603 rows for 1 600 orders; the 3 duplicates disagree on `traffic_bucket` | keep first, quarantine the conflict, report |
| `Delivered`, `HIGH`, `READY / Ready / ready `, `Late Delivery`, `late_delivery ` | representation normalised, every change logged |
| `handoff` vs `handed_off`, `ETA issue` vs `eta_changed` | **kept separate**, flagged for the owner (semantics, not spelling) |
| 37 delivered orders without delivery time · 4 promises before order creation · 5 deliveries before pickup | excluded from the validated population with the rule id, listed by order id |
| `orders.driver_id` = Dispatch's *original* driver for 1 597 orders | Dispatch used as the final driver (95 reassignments) |
| interventions log: 155 reassignments vs Dispatch: 95, overlap 8 | reported; intervention effectiveness declared not evaluable |
| 2 restaurants with impossible coordinates, 189 out-of-area GPS pings | flagged; no geo inference |
| restaurant feed: 31 % coverage, minute precision, updates before order creation | usable for weekly analytics only |
| four definitions of "late", no owner | all computed side by side; gate = UNKNOWN until VP Operations signs |

Rules with business reason / detection / action / owner: [`docs/data-quality-rules.md`](docs/data-quality-rules.md) · run results: [`output/data_quality_report.md`](output/data_quality_report.md).

## 6. Setup and run

```bash
cd assignment-2
python -m venv .venv && .venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

python run_pipeline.py --start-api                       # full run (~15 s); starts the mock Dispatch API for the run
python run_pipeline.py --start-api --run-id run_example  # reproduce the committed outputs
python -m pytest                                         # 73 tests, incl. messy-data and API-failure scenarios
python notebooks/build_notebooks.py                      # optional: re-execute the Session 5/6/7 challenge notebooks
```

Useful options: `--api-url` (an already running API), `--fallback-snapshot` (API down → reuse last raw pages, gate WARN), `--late-threshold 10` (recompute under the Support Lead definition), `--source-root <dir>` (point at a different client pack — the hidden-data behaviour is described in [`docs/data-quality-rules.md`](docs/data-quality-rules.md#hidden-data-behaviour-tested-in-tests)).
Exit codes: `0` completed · `1` failed (source missing, API unrecoverable) · `2` gate failed (outputs kept in `output/runs/<run_id>/`, not published).

## 7. Repository map

| Path | Content |
|---|---|
| `source_systems/` | the client systems as received (SQLite DB, CSV/JSON exports, mock Dispatch API) — read-only inputs |
| `sql/` | retrieval queries (only needed columns; customers without PII) and the independent SQL KPI check |
| `src/flasheats_pipeline/` | `ingest/` (SQL, files, API) · `profiling` · `cleaning` · `rules` · `model` · `metrics` · `gate` · `reports` · `pipeline` · `cli` |
| `run_pipeline.py` | runnable entry point reproducing every output from raw inputs |
| `data/raw/<run_id>/` | preserved raw inputs per run (SQL extracts + SQL text, byte copies of files with SHA-256, every raw API page, ingestion report) |
| `data/processed/` | modelled tables (CSV + `flasheats_model.sqlite`) and join checks |
| `output/` | evidence: metrics, breakdowns, charts, dashboard, data-quality report, quarantine, profile, gate, K/U/A/L, manifest, log |
| `tests/` | 73 pytest tests with a hand-checkable messy pack and a fault-injecting Dispatch API |
| `notebooks/` | executed `Session5/6/7_Challenges.ipynb` (+ generator and the classroom originals) |
| `docs/` | source map · data model · data-quality rules · metrics · session 5/6/7 challenge mapping · assumptions & limitations · testing · pipeline dependability · demo script · requirement traceability |

## 8. Known / Unknown / Assumption / Limitation (short)

- **Known:** retrieval complete and preserved; 56.33 % late on 1 486 validated deliveries; delay accrues before pickup; the orders table is stale on drivers after reassignment.
- **Unknown (owner needed):** canonical definition of *late* (VP Ops); back-fill of 37 delivery times (Fleet Ops); the −10 / −5 min timestamp offsets (ETA service); why the intervention log and Dispatch disagree (Support / Dispatch); when drivers arrive at restaurants (nobody records it).
- **Assumptions:** naive timestamps are IST; late = any delay > 0 (10 min reported alongside); cancelled excluded; representation may be normalised, semantics may not; Dispatch is authoritative for the final driver.
- **Limitations:** intervention effects are associations with a selection effect; the pre-pickup stage cannot be split; restaurant feed is partial; synthetic single-city data.

Full list with owners and affected decisions: [`docs/assumptions-limitations.md`](docs/assumptions-limitations.md) · requirement → implementation → test → evidence: [`docs/requirement-traceability.md`](docs/requirement-traceability.md).

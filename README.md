# FlashEats: a trustworthy path from client systems to a business decision

**FDE Data Foundations Assignment 2 (Sessions 4–8) · Track A, FlashEats-style · Bhuvanesh M S**

🎥 **Demo video:** _add the Loom link here after recording_ · video script with the picture to show at each moment: [`docs/demo-script.md`](docs/demo-script.md)

> **Client:** *"Late deliveries are increasing and customers say our ETA is unreliable. Figure out what is happening before we invest in an AI delay predictor."*
> **Leadership:** *"Late Delivery Rate is 56 %."*

| | |
|---|---|
| **Problem** | More than half of deliveries miss the promised ETA. Teams disagree on the number, and nobody knows *where* in the order workflow the delay is created or which intervention helps. |
| **Users / stakeholders** | VP Operations (proposed KPI owner) · Support Lead · Dispatch · Fleet Ops · Restaurant Ops · Product / ETA service · Data Team · Finance |
| **Project KPI** | **Reduce the late-delivery rate**: the share of trusted deliveries with `actual_delivery_at − promised_eta > 0 min` (the > 10 min rate is reported alongside) |
| **Source overview** | Orders DB (SQL) · Dispatch REST API (paginated) · driver-app events (nested JSON) · restaurant status feed, customer app actions, support tickets, interventions log (CSV) · the client's KPI definitions and outcome file · Open-Meteo observed weather as an outside check. See the [source map](#1--source-reasoning-where-does-the-truth-live-20-) |
| **Decisions the output supports** | ① Which lifecycle stage to fix first. ② Which orders ops should act on, and when. ③ Whether the ETA or the operation is wrong. ④ Who, if anyone, to hold accountable. ⑤ Whether to fund the AI predictor now. |

![A trustworthy path from client systems to a business decision](output/visuals/01_trustworthy_path.png)

**The answer in four lines** (run `run_example`, data gate **WARN → publish with caveats**):

1. **56.33 %** of 1,486 trusted deliveries were late (837 orders). Leadership's "56 %" is right for the dashboard's own definition (56.39 %).
2. **98.9 %** of the lost minutes build up **before pickup**, not on the road.
3. **Decision:** switch on a simple rule today. It alerts ops when an order is still not picked up 10 min after Dispatch's own estimate. On a held-out week it was **96 % precise, caught 72 % of late orders, ~45 min before the promise broke**.
4. **Not yet:** the AI predictor. The rule is the baseline any model must beat, and the data cannot yet say whether the kitchen or the rider owns the pre-pickup delay.

Every picture on this page is **drawn by the pipeline from that run's own evidence files** ([`src/flasheats_pipeline/visuals.py`](src/flasheats_pipeline/visuals.py)). A picture cannot disagree with the numbers.

---

## 1 · Source reasoning: where does the truth live? (20 %)

![Source map](output/visuals/02_source_map.png)

- **Five business questions** are mapped to the information they need and to the **eight sources** that hold it. There are seven client systems plus one outside check (observed weather).
- Every source has an **owner**, a **grain** (what one row means) and a **trust level**.
- **The gap that shapes every conclusion:** no source records *"driver arrived at the restaurant"*. The time before pickup cannot be split into kitchen delay and rider delay.
- Details: [`docs/source-map.md`](docs/source-map.md).

## 2 · Retrieval: did we get all of it? (20 %)

![Retrieval proof](output/visuals/03_retrieval_proof.png)

- **Four retrieval modes:** SQL (read-only SQLite), a paginated REST API, CSV and nested JSON, plus the public Open-Meteo API.
- **Complete, not assumed:** 1,600 / 1,600 Dispatch records across 16 pages. Page 3 (HTTP 500) and page 5 (HTTP 429) were retried. **6 / 6 control totals** published by the client match, and the orders extract equals the server's own `COUNT(*)`.
- **Evidence kept:** all 28 raw artefacts are preserved with a SHA-256 in [`data/raw/run_example/`](data/raw/run_example/). `--replay` rebuilds the whole run from them.
- **Schema contract:** a missing required column stops the run and names the column ([`config/schema_contract.yaml`](config/schema_contract.yaml)).

## 3 · Validation: can we trust it for THIS decision? (20 %)

![From 1,603 raw rows to a number you can defend](output/visuals/04_kpi_funnel.png)

![Validation gate](output/visuals/05_validation_gate.png)

| What the data-quality work found | What the pipeline did (nothing is silently fixed) |
|---|---|
| 1,603 rows for 1,600 orders, and the 3 duplicates disagree on traffic | kept the first row and quarantined the conflict ([`output/quarantine/`](output/quarantine/)) |
| `Delivered` / `delivered`, `HIGH` / `high`, `READY` / `ready ` | fixed the spelling and logged every change |
| `handoff` vs `handed_off`, `ETA issue` vs `eta_changed` | **kept apart**: the meaning belongs to the owner, not to the pipeline |
| 37 delivered orders with no delivery time | outcome **UNKNOWN**, never guessed. Worst and best case: 837/1,523 = 55.0 % to 874/1,523 = 57.4 % |
| 4 promises before the order, 5 deliveries before the pickup | excluded from the KPI by rule id and listed by order |
| the orders table keeps the **old** driver after a reassignment | Dispatch is used for the final driver |
| the client's weather label vs real rainfall: kappa 0.009 | weather is **not** used to explain delays |
| restaurant feed covers 31 % of orders, and some "ready" updates arrive after pickup | fine for weekly analytics, not for live ETAs |

- **38 business rules**, each with a reason, an action, an owner and a tolerance. The tolerances live in the stakeholder-owned policy file [`config/pipeline.yaml`](config/pipeline.yaml).
- **Proof that nothing was lost:** [`output/reconciliation_ledger.csv`](output/reconciliation_ledger.csv) shows raw = clean + duplicates + quarantined + out of period, for every dataset.
- Rules: [`docs/data-quality-rules.md`](docs/data-quality-rules.md) · run results: [`output/data_quality_report.md`](output/data_quality_report.md).

## 4 · Workflow + metrics: where is time lost, and what helps? (20 %)

**Start with one order, not an ER diagram.** This is one real late order, as seven systems saw it:

![One order across seven systems](output/visuals/06_one_order_journey.png)

**Then generalise it into the workflow** of entities, events, states, interactions, interventions and outcomes:

![Order workflow](output/visuals/07_order_lifecycle.png)

**Then model it around the order.** The many-side tables are aggregated to one row per order *before* the join, so counts cannot inflate:

![Data model](output/visuals/08_data_model.png)

**Five metrics, each tied to the KPI** "reduce the late-delivery rate". They are computed twice, in pandas and in SQL views ([`sql/40_metric_views.sql`](sql/40_metric_views.sql)), and the two agree:

![Metrics board](output/visuals/09_metrics_board.png)

| # | Metric | Value | Question it answers |
|---|---|---|---|
| **M1** | Late delivery rate | **56.33 %** (837 / 1,486) | How big is the problem? |
| **M2** | Median lateness of late orders | **8.0 min** (P90 of all deliveries 17.9) | How late is late? |
| **M3** | Share of the lateness built up before pickup | **98.9 %** | Where is time lost? |
| **M4** | Support contact rate on late orders | **30.7 %** vs 5.2 % on time | How do customers react? |
| **M5** | Intervention coverage | **26.9 %** of deliveries, with a late rate of 56.4 % with and 56.3 % without an intervention (association, not effect) | Does ops reach the right orders? |

![Where the time is lost](output/visuals/10_where_delay_builds.png)

- **Session 7 pattern:** of 74 validated orders with a support contact **and** an intervention, 66 were still late and **31 were still more than 15 min late**, meaning the intervention did not work.
- Evidence table with every numerator and population: [`output/evidence_table.md`](output/evidence_table.md) · metric definitions: [`docs/metrics.md`](docs/metrics.md).

## 5 · Pipeline dependability: does it re-run, and does it stop itself? (20 %)

![Dependable pipeline](output/visuals/12_pipeline_flow.png)

![Reproducibility](output/visuals/13_reproducibility.png)

| What happens if… | Behaviour | Proven by |
|---|---|---|
| an API page returns HTTP 500 or 429 | retried with back-off; the retry is logged | `test_retries_500_and_429_then_succeeds` |
| the API never recovers or is unreachable | the run fails with a clear message and still writes its manifest | `test_api_down_fails_clearly_and_writes_manifest` |
| the API is down but an earlier snapshot exists | `--fallback-snapshot` uses it and the gate shows WARN | `test_api_down_with_snapshot_fallback_degrades_to_warn` |
| we get fewer records than the server says exist | publication is refused | `test_incomplete_api_blocks_publication` |
| a count differs from the client's control totals | publication is refused | `test_control_total_mismatch_refuses_publication` |
| a required file or column disappears | the run stops and names it | `test_missing_required_file_names_the_file`, `test_missing_required_column_names_the_column` |
| a new, unknown status value appears | flagged, never counted as delivered | `test_new_status_value_is_flagged_not_counted_as_delivered` |
| every timestamp is unparseable | the gate FAILS instead of publishing 0 % | `test_all_timestamps_unparseable_fails_the_gate_instead_of_publishing_zero` |
| a 1:N table is joined onto orders | duplicate keys are dropped and counted, and rows never multiply | `test_checked_merge_never_multiplies_rows` |
| someone edits or deletes preserved raw evidence | the replay stops and names the file | `test_tampered_preserved_file_stops_the_replay`, `test_deleted_api_page_stops_the_replay` |
| the same inputs are run again | byte-identical outputs, and the run-over-run check passes | `test_rerun_on_same_inputs_is_byte_identical`, `test_rerun_with_same_id_is_compared_with_its_previous_publication` |
| one week's data is broken | that week is refused and the other weeks still publish | `test_a_failing_period_does_not_block_the_others` |

**Three ways to run the same code**, each verified on the real client pack:

| Mode | Command | Result |
|---|---|---|
| Live | `python run_pipeline.py --start-api` | gate WARN → publish with caveats. The re-run is 0.00 pp vs the last publication, with 46/46 outputs byte-identical |
| Replay | `python run_pipeline.py --replay run_example` | **REPRODUCED**: 28/28 preserved artefacts hash-verified, 46/46 outputs byte-identical, no client system contacted |
| Weekly | `python run_pipeline.py --start-api --weekly` | 4 gated weeks, all published. They add up to the month (1,486 deliveries, 837 late). Two week-on-week moves above 2 pp were flagged |

Details: [`docs/pipeline-dependability.md`](docs/pipeline-dependability.md) · tests: [`docs/testing.md`](docs/testing.md).

## The FDE judgement call

![The judgement call](output/visuals/14_judgement_call.png)

The class question was *"should we build the AI delay predictor now?"*. The evidence says the delay is created **before pickup**, and Dispatch's **own** pickup estimate already tells us when an order is in trouble.

**The call:** ship a transparent rule now. It alerts when an order is not picked up 10 min after Dispatch's estimate. The threshold was chosen on 1–21 August and **proven on the held-out week of 22–28 August**:

- 96.1 % of its alerts were right;
- it caught 71.5 % of late orders;
- it fired ~45 min before the promise broke.

Today, **446 late orders that it would have caught got no intervention at all**, and 169 interventions went to orders that were never at risk. The rule is cheap, explainable and can start this week. It becomes the **baseline any AI model must beat**.

## Known · Unknown · Assumption · Limitation

![Known Unknown Assumption Limitation](output/visuals/11_known_unknown.png)

Generated from the run: [`output/known_unknown_assumption_limitation.md`](output/known_unknown_assumption_limitation.md) · with owners: [`docs/assumptions-limitations.md`](docs/assumptions-limitations.md).

## What makes this different from the class work

![Where the class stopped and what an FDE adds](output/visuals/15_what_is_different.png)

1. **Act, don't just diagnose.** A proactive trigger proven on a week it never saw, instead of stopping at "don't build the AI yet".
2. **Re-test class insights on the client's own data.** Session 6 said GPS has pings before pickup and none after. Here, 30.8 % of pings fall before pickup and the rest after it. Before pickup, the pings move **away** from the restaurant in 99.2 % of orders, and 91.3 % of the tracks are perfect straight lines. The pings look drawn, not measured, so no geofence or GPS ETA should be built on them.
3. **Check the client's labels against the outside world.** The weather label agrees with real rainfall only by chance (kappa 0.009).
4. **Measure the promise, not just the outcome.** Dispatch's pickup estimate is 8 min short. Padding the promise instead would cost +12 min on every order.
5. **Fair ranking before blame.** A raw top-10 would name 10 restaurants, but only R024 is statistically worse than the fleet.
6. **Make trust re-runnable:**
   - the client's control totals;
   - a byte-identical replay with tamper detection;
   - weekly runs that add up to the month;
   - a drift alert;
   - a policy file owned by stakeholders;
   - CI tests.

Full rationale: [`docs/beyond-the-classroom.md`](docs/beyond-the-classroom.md).

---

## Setup and run

```bash
cd assignment-2
python -m venv .venv && .venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

python run_pipeline.py --start-api                       # live run from raw client systems -> output/ (evidence, dashboard, 15 visuals)
python run_pipeline.py --replay run_example --run-id run_replay_check   # rebuild from preserved raw, prove byte-identical
python run_pipeline.py --start-api --weekly              # 4 gated weekly runs + scorecard + partition check
python make_visuals.py                                   # redraw output/visuals/ after --replay / --weekly
streamlit run app/dashboard.py                           # dashboard: visual story, simulators, data quality, run history
python -m pytest                                         # the full test suite (also runs in CI: .github/workflows/tests.yml)
python notebooks/build_notebooks.py                      # re-execute the 4 challenge notebooks + the walkthrough
```

- **No Python on the viewing machine?** Open `output/dashboard.html` in any browser. It is a static, self-contained page generated by the pipeline, with the metric tiles, the visual story, the charts and the gate. It is the only HTML in the project, and none of it is hand-written.
- **Try a policy change:** set `kpi.late_threshold_min: 10` in [`config/pipeline.yaml`](config/pipeline.yaml) and rerun. Every metric, the gate, the memo and the pictures follow, and `output/run_comparison.md` shows what moved.
- **Flags:**
  - `--period 2026-08-01..2026-08-07` runs one period;
  - `--fallback-snapshot` survives an API outage;
  - `--no-weather` skips the outside check;
  - `--source-root <dir>` runs on another client pack.
- **Exit codes:** `0` means completed; `1` means failed (for example a missing source or an unrecoverable API); `2` means the gate failed, so outputs are kept in `output/runs/<run_id>/` and not published.

## Repository map

| Path | Content |
|---|---|
| `output/visuals/` | **the 15 pictures on this page**, redrawn from every run's evidence |
| `Challenges/` | the **four instructor notebooks** (Class 5 Starter, Class 5 Student, Class 6 Student, Class 7 Challenge), answered and executed |
| `notebooks/pipeline_walkthrough.ipynb` | the production pipeline run stage by stage, with evidence inline |
| `source_systems/` | the client systems as received (read-only) |
| `config/` | `pipeline.yaml` (stakeholder-owned thresholds, each with an owner) · `schema_contract.yaml` (required columns per source) |
| `sql/` | retrieval queries (customers without PII), the independent SQL KPI check, the SQL metric views |
| `src/flasheats_pipeline/` | `ingest/` (SQL, files, Dispatch API, weather API, replay) · `contracts` · `scope` · `profiling` · `cleaning` · `rules` · `model` · `metrics` · `sql_metrics` · `insights` · `monitoring` · `gate` · `reports` · **`visuals`** · `periods` · `pipeline` · `cli` |
| `app/dashboard.py` | Streamlit dashboard, whose first tab is the visual story |
| `data/raw/run_example/` | preserved raw inputs with SHA-256: SQL extracts, file copies, every raw API page, the weather response |
| `data/processed/` | modelled tables (CSV + SQLite) and join checks |
| `output/` | evidence: metrics, insights, decision memo, gate, data-quality report, ledger, run comparison, replay proof, weekly scorecard, charts, visuals, dashboard.html, manifest, log |
| `tests/` | pytest suite with a hand-checkable messy pack and fault-injecting Dispatch and weather APIs |
| `docs/` | rubric map · beyond the classroom · source map · data model · rules · metrics · sessions 5/6/7 · assumptions · testing · dependability · demo script · traceability |

**Where each grading area and submission item is evidenced:** [`docs/rubric-map.md`](docs/rubric-map.md) · requirement by requirement: [`docs/requirement-traceability.md`](docs/requirement-traceability.md).

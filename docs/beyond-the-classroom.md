# Beyond the classroom — what this project adds on top of Classes 4–8

The class used FlashEats to teach **retrieval (C5), validation (C6) and workflow modelling (C7)**, and stopped at the conclusion *"do not build the AI predictor yet"*. The challenges are completed in `Challenges/`, but the class answers are the *starting point* here, not the deliverable.

An FDE is paid for the step after the diagnosis: **what can the client do on Monday, and how will they know it worked?** This page lists every addition and the view it opens up. The table notes where a reference repository inspired an idea; each idea was rebuilt for this problem.

![Where the class stopped, and what an FDE adds on top](../output/visuals/15_what_is_different.png)

## The six points to take forward

1. **Act, don't just diagnose.** Session 5 ends with "should we build the AI predictor now?". This project ships a rule ops can switch on today, proven on a week it never saw, and makes it the baseline any AI must beat.
2. **Re-test class insights on the client's own data.** Session 6 said GPS has pings before pickup and none after. Here the pings fall on both sides of pickup, but they look *drawn, not measured*. No geofence or GPS ETA should be built on them.
3. **Check the client's labels against the outside world.** Real rainfall shows the weather label is chance-level.
4. **Measure the promise, not only the outcome.** The pickup estimate is 8 min short. Fix the input rather than padding the output.
5. **Fair ranking before blame.** Only one restaurant is really worse than the fleet.
6. **Make trust re-runnable.** Three things make this work:
   - client control totals and a schema contract;
   - a byte-identical replay with tamper detection;
   - weekly runs that add up to the month, drift alerts, and CI.

## Summary

| # | Addition | What the class did | What this project adds | Result on the classroom data | Where |
|---|---|---|---|---|---|
| 1 | **Early-warning trigger** (decision layer) | Session 5 synthesis: decide "whether to build the AI predictor now" | A transparent rule ops can switch on today: *alert when an order is not picked up k minutes after Dispatch's own estimate*. `k` is chosen on 1–21 Aug and **proven on the held-out week 22–28 Aug** (no peeking) | **k = 10 min: 96 % precision, 72 % recall, fires ~45 min before the promise breaks.** 446 late orders the trigger would have caught got **no intervention**; 169 interventions went to orders that were never at risk | `insights.py` · `output/insights/early_warning_*.csv` · chart `early_warning_tradeoff.png` · dashboard simulator |
| 2 | **ETA calibration** | "ETAs are unreliable" (stated, not measured) | Measures *where* the promise is wrong: Dispatch's pickup estimate vs reality, and what padding would be needed for a target on-time rate, with a guardrail | Dispatch's pickup estimate is short by a **median 8 min** (plans 18 min, reality 26). Padding to reach 80 % on-time would need **+12 min on every order**; fixing the pickup estimate is the better lever | `eta_calibration` · `eta_padding_curve.png` · dashboard slider |
| 3 | **Fair ranking** of restaurants and drivers | "Which restaurants contribute the most late orders?" (raw counts) | Wilson 95 % intervals, a minimum sample size and a funnel plot, so nobody is penalised for noise | A naive top-10 blames 10 restaurants; **only R024 is statistically worse** than the fleet (1 of 59), and 1 of 91 drivers | `fair_ranking_*.csv` · `restaurant_funnel_plot.png` |
| 4 | **Independent external source**: observed weather (Open-Meteo archive, Bengaluru, hourly) | Took `weather_bucket` at face value: heavy rain goes with a 6.6 min median delay | Verifies the client's label against **what actually fell from the sky**, as rule **WX-01** in the gate | The label agrees with observed rain **53 % of the time, Cohen's kappa 0.01 (chance level)**. Orders labelled *heavy rain* saw no more rain than *clear* ones, so the weather story cannot be defended with this field | `ingest/weather_source.py` · rule WX-01 · `weather_label_vs_observed.png` |
| 5 | **GPS feasibility and track-shape test** | Session 6: "GPS has pings between assignment and pickup, none between pickup and delivery". The Class 5 notebook lists GPS as the signal from which arrival could be *inferred* | Tests both claims on this client's data: when the pings fall, whether they head for the restaurant, and whether the tracks look measured or drawn | **30.8 %** of pings fall before pickup and the rest after it, so the class claim does not hold here. Before pickup, the pings move **away** from the restaurant in **99.2 %** of orders. **91.3 %** of tracks are perfect straight constant-speed lines, and 90.7 % are perfectly evenly spaced. The pings look interpolated, not measured: no geofence or GPS ETA should be built on them. Ask Fleet Ops, and instrument an "arrived" tap | `gps_arrival_feasibility`, `gps_track_shape` · `output/insights/gps_arrival_feasibility.csv` · Class 5 Starter notebook |
| 6 | **What-if impact** (assumption-labelled) | none | KPI and support-contact effect of acting on the trigger, under a stated save-rate assumption (25 % / 50 %) | at 25 % save rate: late rate −10 pp, ~38 fewer support contacts a month; the memo says to measure the save rate with a switchback pilot | `impact_whatif.csv` · decision memo |
| 7 | **Decision memo** generated every run | a one-slide synthesis written by hand | Situation → Complication → Resolution (Session 2–3 structure) with **owned, measurable actions** and conditions to revisit the AI predictor ("the trigger is the baseline any model must beat") | `output/decision_memo.md` | `reports.write_decision_memo` |
| 8 | **Stakeholder-owned policy file** *(idea from the NYC-TLC reference repo's config.yaml)* | thresholds typed into notebook cells | `config/pipeline.yaml`: every business number with its **owner**; typos fail loudly; the values used are recorded in each run manifest | change `kpi.late_threshold_min` to 10 and rerun: every output, the gate and the memo follow | `config.py` · `tests/test_config.py` |
| 9 | **Record reconciliation ledger** *(idea from the Olist reference repo's "clean + anomalies = raw" check)* | "don't silently drop data" (principle) | Proves it per dataset: `raw = clean + dropped duplicates + quarantined`, and every order lands in exactly one outcome bucket | 11 datasets balanced; 1600 orders = 837 + 649 + 68 + 37 + 9 | `monitoring.build_ledger` · `output/reconciliation_ledger.csv` |
| 10 | **Run-over-run drift monitoring** | a monthly pipeline was mentioned for Class 8 | Each run compares its KPI and every rule's status and violations with the last published run; the gate WARNs on drift | a rerun shows **+0.00 pp, no rule worse**; a 2-pp move or a newly failing rule would flag | `monitoring.compare_runs` · `output/run_comparison.md` |
| 11 | **Interactive decision dashboard** *(idea from the Olist reference repo's Streamlit app)* | static tables and one chart | 9 tabs, including **live simulators** for the trigger (`k`) and ETA padding, fair ranking, the weather check, data quality, an order explorer and run history | `streamlit run app/dashboard.py` | `app/dashboard.py` · `tests/test_dashboard.py` |
| 12 | **Guided walkthrough notebook** *(idea from the NYC-TLC reference repo)* | challenge notebooks per class | the production code run stage by stage, with the evidence of each FDE decision inline | — | `notebooks/pipeline_walkthrough.ipynb` |
| 13 | **Completeness against the client's own numbers** *(control totals and schema contract: idea from the rajasurya reference repo)* | "prove retrieval is complete" by counting API pages | also checks every count against the totals the client publishes (`source_systems/manifest.json`) and the orders extract against the server's own `COUNT(*)`. A schema contract names any missing required column | **6/6 control totals match**; extract 1,603 = `COUNT(*)` 1,603; a one-row mismatch refuses publication (tested) | `scope.control_totals` · `contracts.py` · `config/schema_contract.yaml` |
| 14 | **Replay with tamper detection** *(offline replay idea from the rajasurya reference repo)* | notebooks re-read the live sources | `--replay <run_id>` rebuilds everything from the preserved raw files after verifying every SHA-256. One edited byte stops it and names the file | **REPRODUCED: 28/28 artefacts verified, 46/46 outputs byte-identical** | `ingest/replay.py` · `output/replay_proof.md` |
| 15 | **Weekly partitions** *(monthly-partition idea from the rajasurya reference repo, applied to weeks)* | one monthly number | `--weekly`: one gated run per week, a scorecard, a drift flag, and a partition check that the weeks add up to the month | 4/4 weeks published; 1,600 orders each in exactly one week; the weeks sum to 1,486 deliveries and 837 late; two moves above 2 pp flagged | `periods.py` · `output/scorecard.md` · `weekly_scorecard.png` |
| 16 | **SQL metric layer** *(SQL metric views: idea from the rajasurya reference repo)* | metrics computed once, in pandas | the same metrics as SQL views over the modelled tables (aggregate in a CTE, then join), compared with pandas on every run | 6/6 SQL values = pandas | `sql/40_metric_views.sql` · `sql_metrics.py` |
| 17 | **Visual story drawn from the evidence** *(instructor feedback: "more images, pipelines and graphical representation")* | text answers and a few charts | 15 pictures (source map, retrieval proof, KPI funnel, gate, one-order swimlane, workflow, data model, metrics, K/U/A/L, pipeline, reproducibility, judgement call) redrawn by every run from its own files, so a picture cannot disagree with the numbers | `output/visuals/` · README · the dashboard's first tab | `visuals.py` · `make_visuals.py` |
| 18 | **Continuous integration** *(idea from the rajasurya reference repo)* | tests run by hand | the whole suite runs on every push | 132 tests | `.github/workflows/tests.yml` |

## Why these, and not something bigger

- **Every addition answers a business question the class left open.** It never adds technology for its own sake. There is no machine-learning model, because the data cannot support one yet, and the trigger is the honest baseline for when it can.
- **Everything is judged the way a client would judge it:**
  - the trigger is tested on a held-out week;
  - rankings carry confidence intervals;
  - the weather label is checked against an independent source;
  - what-ifs are labelled as assumptions.
- **Everything reruns.** Each addition is part of `python run_pipeline.py`, covered by tests and visible in the gate, the memo and the dashboard.

## The one judgement call to explain in the demo

The class's natural next step was *"find more signals and build the predictor"*. The data says something more useful:
- the delay is created before pickup;
- Dispatch already knows its own pickup estimate;
- a trivial rule on that estimate already catches most late orders 45 minutes early.

**Recommending the rule instead of the model** is the FDE judgement. It is cheaper and explainable, it can start this week, and it becomes the baseline any future model must beat. Alongside it sit two honest negatives: the weather label is not trustworthy, and the GPS pings look drawn rather than measured, so they cannot fill the arrival gap. Together they stop the client from investing in the wrong things.

![The judgement call](../output/visuals/14_judgement_call.png)

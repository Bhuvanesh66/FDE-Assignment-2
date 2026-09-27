# Loom demo script (about 9 minutes, with a 5-minute cut)

The assignment asks for a 3–5 minute demo. This script runs about 9 minutes. Sections marked **[5-min cut: skip]** can be dropped to land near 5 minutes. Every number below matches the committed outputs.

## Before you record

1. Open the repository on GitHub in the browser. Open these tabs: the README, `docs/source-map.md`, `docs/data-model.md`, `output/decision_memo.md`, and the `Challenges/` folder.
2. In VS Code, open `assignment-2`, zoom to about 150 %, and activate the environment: `.venv\Scripts\activate`.
3. Start the dashboard in a second terminal **before** recording: `streamlit run app/dashboard.py`. Keep its browser tab open.
4. Make sure port 8000 is free, then do one practice run: `python run_pipeline.py --start-api`.
5. After recording, restore the committed evidence: `git restore output data`.

---

## 0:00–0:35 · The problem (screen: GitHub README, top)

> "Hi, I'm Bhuvanesh. This is Assignment 2, Track A, FlashEats. The client says late deliveries are rising, the ETA is unreliable, and they want to buy an AI delay predictor. Leadership quotes a 56 % late rate.
>
> As the FDE I had to answer three things: is 56 % real, where in the order workflow is the time lost, and what should FlashEats actually do, this week and not in six months. The project KPI is reducing the late delivery rate."

## 0:35–1:00 · The class work is done, and it is the starting point (screen: the `Challenges/` folder on GitHub)

> "All four classroom notebooks are in `Challenges/`: the Class 5 Starter, the Class 5 Student, Class 6 and Class 7. I kept every one of sir's cells and inserted my answers after each challenge. The Starter is answered in SQL and the Student in pandas, so the same definitions are checked in both tools. But the class stops at 'don't build the AI yet', and I wanted to go one step further. That is what this demo is about."

## 1:00–1:50 · Class 4: understand the sources (screen: `docs/source-map.md`) **[5-min cut: keep the first two sentences]**

> "Class 4 was about mapping business questions to the information they need and to the system that owns it. I mapped seven client systems: the orders database, the Dispatch API, tickets, the restaurant feed, driver-app events, app actions and the interventions log, each with its owner, grain and trust level.
>
> One thing the class never asked: where does the `weather_bucket` label come from? Operations blames weather. So I added an eighth, independent source, the Open-Meteo archive of real hourly rainfall in Bengaluru, to check that label. I'll come back to what it found.
>
> The most important gap: no system records when the driver arrives at the restaurant."

## 1:50–3:00 · Class 5: retrieve and preserve (screen: terminal, type `python run_pipeline.py --start-api`)

> "One command runs everything in about 15 seconds. Class 5 was about retrieving from several modes and proving the retrieval is complete. This pipeline uses SQL on SQLite, two REST APIs, CSV and nested JSON."

*Point at the API lines.*

> "The Dispatch API failed on purpose: page 3 returned a 500 and page 5 a 429. Both were retried, and ingestion only counts as complete because 16 pages gave 1600 records, matching the server's `total_records`, with no duplicate IDs. An HTTP 200 on one page proves nothing."

*Open `data/raw/run_example/` in the file explorer.*

> "Every raw input is preserved per run: the SQL extracts with their query, byte copies of every file with a hash, every raw API page, and the weather response. If the public weather API is down, the pipeline uses a committed reference copy and says so. It never crashes."

## 3:00–4:20 · Class 6: profile and validate (screen: `output/data_quality_report.md`, then `output/validation_gate.md`)

> "Class 6 taught: profile before cleaning, fix spelling but never meaning, and turn assumptions into a gate. I wrote 38 business rules, each with a reason, an action and an owner.
>
> The orders table has 1603 rows for 1600 orders, and the three duplicates disagree with each other on traffic, so I quarantine the conflict. 'Delivered' with a capital D is spelling, so it is normalised. 'handoff' versus 'handed_off' might mean something different, so it is flagged for Restaurant Ops, not merged.
>
> Here is one trap. The four worst 'delays' in the data, 85 minutes and more, are orders whose promise was made ten minutes *before the order existed*. They are a system bug, not deliveries. So I publish 56.33 % on 1486 validated deliveries. The dashboard definition gives 56.39 %, which means leadership's 56 % is right for its definition."

*Open `output/charts/weather_label_vs_observed.png`.* **[5-min cut: skip this paragraph]**

> "And the weather label: against real rainfall it agrees at chance level, a kappa of 0.01. Orders labelled heavy rain got no more rain than orders labelled clear. So 'weather causes delays' can't be defended with this field, and that is now rule WX-01 in the gate."

> "The gate says WARN, publish with caveats. KPI ownership is UNKNOWN, because four stakeholders define 'late' differently."

## 4:20–5:20 · Class 7: model the workflow (screen: `docs/data-model.md` on GitHub, then the dashboard's Executive tab)

> "Class 7: reorganise the data around the order lifecycle instead of the source systems. An order is created, assigned, picked up and delivered, while the customer interacts and ops intervenes. Every one-to-many table is aggregated to one row per order before joining, and every join is checked so the count can never inflate."

*Dashboard, Executive tab: point at the five tiles and the stage chart.*

> "Five metrics. M1, the KPI, is 56.3 %. M2, the median late order, is 8 minutes late. M3 is the key one: 99 % of lateness builds up *before pickup*. Late orders travel faster than planned, so the road is not the problem. M4: late orders trigger support contacts six times more often. M5: interventions touch 27 % of orders with no visible effect."

## 5:20–6:50 · Beyond the class: from diagnosis to action (screen: dashboard, Early-warning tab)

> "This is where I go past the classroom. If the delay is created before pickup, Dispatch already knows its *own* estimated pickup time. So here is a rule with no AI: if an order is still not picked up k minutes after Dispatch's estimate, alert ops."

*Drag the slider from 0 to 10.*

> "I chose k using only 1 to 21 August and tested it on the last week, which the rule never saw. At 10 minutes it is right 96 % of the time, catches 72 % of late orders, and fires about 45 minutes before the promise breaks, which is enough time to act. And today, 446 of the late orders this rule would have caught received no intervention at all."

*ETA tab, drag the padding slider.* **[5-min cut: skip]**

> "The ETA: Dispatch's pickup estimate is short by a median 8 minutes. Padding every promise by 12 minutes would reach 80 % on time, but that hides the problem, so the recommendation is to fix the estimate."

*Fair ranking tab: funnel plot.* **[5-min cut: skip]**

> "And before anyone blames a restaurant: a naive top-10 list names ten, but with confidence intervals only one, R024, is really worse than the fleet."

## 6:50–7:40 · The FDE judgement call (screen: `output/decision_memo.md`, the recommendations table)

> "The judgement call I want to highlight: the obvious next step was to find more signals and build the AI predictor. I recommended the opposite. Ship this simple rule now, because it is explainable, starts this week, and becomes the **baseline any future model must beat**.
>
> I also closed two doors with evidence. The weather label isn't real weather, and I tested whether GPS could stand in for the missing arrival event: pings move towards the restaurant in under 1 % of orders, so it can't. The instrumentation request is now backed by data, not opinion."

## 7:40–8:30 · Class 8: a dependable pipeline (screen: `config/pipeline.yaml`, then terminal) **[5-min cut: first sentence only]**

> "Class 8 is about repeatability. Every business threshold lives in this policy file with its owner. If VP Operations decides 'late' means more than 10 minutes, they change one line and rerun, and every output, the gate and the memo follow."

*Terminal: `python -m pytest tests/test_hidden_messy_data.py -q`*

> "There are 111 tests, including messy data an evaluator might hide: mixed timezones, new status values, IDs with spaces, duplicate events, the API or the weather service going down. Every run proves no rows vanished with a reconciliation ledger, and compares itself with the last published run to catch drift. If retrieval is incomplete, the gate fails and nothing is published."

## 8:30–9:00 · Close (screen: the decision memo, "Decision on the AI delay predictor")

> "So: the late-delivery problem is real, about 56 %, and it is created before pickup. The recommendation is to switch on the pickup-overrun trigger with ops, fix Dispatch's pickup estimate, instrument the arrival tap, and have VP Operations sign off the definition of late. The AI predictor can wait until it can beat this baseline. Thanks."

---

## 5-minute version

Keep: problem (0:35) → Challenges folder (0:25) → first two sentences of Class 4 → the retrieval run (1:10) → the Class 6 trap and 56.33 % (0:50) → the five metrics (0:50) → the early-warning slider (1:00) → the judgement call (0:40) → close (0:20). That is about 5:00.

## Likely questions

- "Why 1486 and not 1495?" → `output/breakdowns/definition_comparison.csv`
- "Is the trigger overfitted?" → chosen on 1–21 Aug, judged on 22–28 Aug; see `output/insights/early_warning_backtest.csv` (the train and test rows are nearly identical)
- "Prove retrieval is complete" → `data/raw/run_example/api/ingestion_report.json`
- "What if the data is messier?" → `python -m pytest` (111 tests)
- "Where are the class answers?" → `Challenges/` and `docs/session-5/6/7-challenges.md`

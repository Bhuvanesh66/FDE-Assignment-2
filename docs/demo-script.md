# Demo video script: the FlashEats case, session by session (5 minutes)

The video follows the class's own flow: **define the question → retrieve the evidence → check it's complete → reconcile the sources → say what you know and what you can't know → make it a pipeline.**

Every block has four parts:

- **Class:** what the session asked or found, shortened from the class notes;
- **Grading area:** which 20 % the block covers;
- **Show:** exactly what is on screen;
- **Say:** the words, kept simple so the picture does the explaining.

The brief asks for **a 3–5 minute demo using the GitHub project, explaining one important FDE judgement call**. This runs **5:00**. Every number matches the committed run `run_example`.

## Before you record

1. **Tab 1:** the GitHub README. The pictures appear top to bottom in the order of this script.
2. **Tab 2:** `notebooks/pipeline_walkthrough.ipynb` on GitHub.
3. **Tab 3:** the `data/raw/run_example/api/` folder on GitHub.
4. **VS Code terminal** in `assignment-2` with `.venv\Scripts\activate`, zoomed to about 150 %. Type this and **do not press Enter yet**:
   `python run_pipeline.py --replay run_example --run-id run_replay_check`
5. **Browser zoom** about 110 %, so the text inside the pictures is readable.
6. **After recording:** `git restore output data`.

## The plan

| Time | Block | Grading area | On screen |
|---|---|---|---|
| 0:00–0:25 | The case | opening | README table · picture 01 |
| 0:25–1:05 | Session 5, part 1: where does the truth live? | **Source reasoning** | picture 02 · `docs/source-map.md` |
| 1:05–1:50 | Session 5, part 2: can we get all of it? | **Retrieval** | picture 03 · `data/raw/run_example/api/` · notebook §1 |
| 1:50–2:40 | Session 6: can we trust it for this decision? | **Validation** | pictures 04, 05 |
| 2:40–3:30 | Session 7: where is time lost, and do interventions help? | **Workflow + metrics** | pictures 06, 08 · notebook §5–6 · pictures 09, 10, 11 |
| 3:30–4:15 | The assignment: a dependable pipeline | **Pipeline dependability** | terminal replay · pictures 12, 13 |
| 4:15–4:52 | The FDE judgement call | the required judgement call | picture 14 |
| 4:52–5:00 | Close | beyond the class | picture 15 |

---

## 0:00–0:25 · The case

**Class:** *"Late deliveries are increasing and our ETAs are unreliable, so figure out what's happening before we invest in an AI delay predictor."*

**Show:**

- The README's top table: problem, stakeholders, KPI, sources, decision.
- Scroll to **picture 01**. Move the mouse along the six boxes, left to right, then along the red STOP boxes under them.

**Say:**
> "Hi, I'm Bhuvanesh. This is my FDE Assignment 2, Track A: FlashEats, the same case as Sessions 5, 6 and 7. The client wants an AI delay predictor. My job was to build a trustworthy path from their systems to a business decision. This picture is that path: six steps, and under each one, the check that stops it if trust breaks."

---

## 0:25–1:05 · Session 5, part 1: where does the truth live? (Source reasoning, 20 %)

**Class:** the source-map exercise. *"Promised ETA and actual delivery time are in orders. Driver assignment is in driver_events. Complaints are in support_tickets."*

**Show:**

- **Picture 02, the source map.** Point at the left column, the right column, then the red GAP box.
- For 2 seconds, open `docs/source-map.md` to show the full table with owners and grain.

**Say:**
> "Session 5 asked: where does the truth live? I mapped five business questions to eight sources, and each box says who owns it and what one row means. The promise and the delivery time live in the orders database. The final driver is in the Dispatch API, and complaints are in support tickets. I added one outside source, real weather, to check the client's weather label. And the red box is the gap the class found too: nobody records when the driver reaches the restaurant."

---

## 1:05–1:50 · Session 5, part 2: can we get all of it? (Retrieval, 20 %)

**Class:** *"Dispatch API: prove you retrieved everything. Loop through the pages and retry on HTTP 500 and 429."* *"Keep the raw API responses, and never drop failures silently."*

**Show:**

1. **Picture 03.** Point at the two orange bars, then the green ✓ column.
2. The `data/raw/run_example/api/` folder on GitHub (2 s).
3. The walkthrough notebook, section **"1 · Ingest"** (2 s).

**Say:**
> "Then: can we get all of it? Four retrieval modes: SQL, a REST API, CSV and JSON. Just like in class, page 3 failed with a 500 and page 5 with a 429, and both were retried. We got 1,600 records, exactly the server's total. I went one step further. The client publishes its own control totals, and all six match. Every raw file and API page is saved here with a fingerprint, so nothing is lost and nothing can be quietly changed."

---

## 1:50–2:40 · Session 6: can we trust this data enough to make a business decision? (Validation, 20 %)

**Class:**

- *"1603 raw rows, 1600 unique. Remove 68 cancelled and 37 with no delivery timestamp: 1495 valid, 843 late, 56.4 %."*
- *"Fix how a value is written, never what it means."*
- *"Should leadership publish 56 % today?"*

**Show:**

1. **Picture 04, the funnel.** Go down the bars from top to bottom.
2. **Picture 05, the gate.** Point at one green, one orange, the grey, and the OVERALL box.

**Say:**
> "Session 6: can we trust it enough for this decision? This funnel starts where the class did.
>
> - 1,603 rows, of which 3 are duplicates.
> - 68 cancelled.
> - 37 have no delivery time. I mark those unknown. I never guess.
>
> That gives the class's 1,495, and 843 late: 56.4 %. I also removed 9 orders with impossible times, like a promise made before the order existed. So the trusted number is 56.33 % of 1,486. Every removal has a rule and an owner, and nothing disappears silently.
>
> Then the gate answers the class question. Yes, publish 56 %, with the definition and the caveats written next to it."

---

## 2:40–3:30 · Session 7: where in the order lifecycle is time lost, and do interventions help? (Workflow + metrics, 20 %)

**Class:**

- *"Start with one order, not an ER diagram."*
- *"Joining a 1:N table directly multiplies the rows, so aggregate first, then left-merge: the order journey."*
- *"If a ticket was raised and an intervention made, but the order was still more than 15 minutes late, the intervention didn't work."*

**Show:**

1. **Picture 06, one order across seven systems.** Point at the priority dispatch, the support ticket, and the red "26 min late" line.
2. **Picture 08, the data model.** Point at the green arrow, "aggregate, then 1 : 1".
3. The walkthrough notebook, section **"5 · Workflow model and 6 · metrics"** (2 s).
4. **Picture 09, the five metric tiles.**
5. **Picture 10**, where the delay builds (2 s).
6. **Picture 11, Known / Unknown / Assumption / Limitation** (3 s).

**Say:**
> "Session 7: where is the time lost? As the class said, start with one order. This one touched seven systems. Ops gave it priority dispatch, the customer still raised a ticket, and it arrived 26 minutes late. So the intervention did not work.
>
> Then I built the model around the order. Every many-rows table is summed per order before the join, so nothing is double counted. Five metrics, computed in pandas and again in SQL, and both agree.
>
> The big one: 99 % of the lateness builds up before pickup, not on the road. And this is what I know, what I don't know, what I assumed, and what this data can't do."

---

## 3:30–4:15 · The assignment: a small, explainable, dependable pipeline (Pipeline dependability, 20 %)

**Class:** *"Assignment 2: turn messy data into a small, explainable, dependable pipeline."* The brief asks for ingest → validate → transform/model → metric output, with logging, reruns and failure handling.

**Show:**

1. Press **Enter** on the prepared replay command. It takes about 17 seconds.
2. While it runs, show **picture 12** and point at the red STOP badges.
3. Back in the terminal, point at `COMPLETED` and the replay-proof line.
4. **Picture 13.** Point at **REPRODUCED 46/46** and the four weekly bars.

**Say:**
> "Finally, the assignment: make it a dependable pipeline. One command runs all ten stages, from the raw systems to every picture you've seen. The red badges are stop points. If a count is wrong, a rule breaks, or two methods disagree, nothing is published.
>
> Right now I'm replaying the whole run from the saved raw files, without touching the client's systems. All 28 fingerprints match, and all 46 outputs are byte-identical. GitHub repeats this on Linux on every push. It also runs week by week: four gated weeks that add up exactly to the month."

---

## 4:15–4:52 · The FDE judgement call

**Class:** the Session 5 synthesis asks *"whether to build the AI predictor now"*.

**Show:** **picture 14.**

- Top half: move along the one-order timeline, from ALERT to the promised ETA.
- Bottom half: point at the green line at k = 10.

**Say:**
> "My judgement call answers the class's last question: should FlashEats build the AI predictor now? Not yet, but act today.
>
> The delay builds before pickup, and Dispatch already estimates the pickup time. So if an order still isn't picked up 10 minutes after that estimate, alert ops. I picked 10 minutes on three weeks and tested it on a fourth week it never saw:
>
> - 96 % of alerts were right;
> - it caught 72 % of late orders;
> - it fired 45 minutes before the promise broke.
>
> This rule is the baseline any AI must beat."

---

## 4:52–5:00 · Close

**Show:** **picture 15**, scrolled once.

**Say:**
> "Beyond the class, I re-tested the GPS insight, checked the weather label against real rain, and measured the ETA itself. Thank you."

---

## Class idea → where it is in the project (for questions)

| Class idea | Where to point |
|---|---|
| Define "late" before you calculate it | `config/pipeline.yaml` (`kpi.late_threshold_min`, owner VP Operations) · the four definitions in `output/breakdowns/definition_comparison.csv` |
| Keep the raw API responses; never drop failures silently | `data/raw/run_example/api/` (16 pages, SHA-256) · `output/reconciliation_ledger.csv` |
| Check the definition and the grain first | picture 04 (1,486 vs 1,495) · `docs/source-map.md` (grain per source) |
| Profiling tells you where to investigate, not what to delete | `output/profile/profile.md` · `output/quarantine/` |
| Spelling vs meaning (`Delivered` vs `delivered`, `handoff` vs `handed_off`) | `docs/data-quality-rules.md` (ST rules) · picture 05, "Category semantics" |
| PASS / WARN / FAIL / UNKNOWN gate | picture 05 · `output/validation_gate.md` |
| GPS pings only before pickup (Session 6 key insight) | re-tested: picture 15, second row · `output/insights/gps_arrival_feasibility.csv` |
| Start with one order, not an ER diagram | picture 06 |
| Aggregate first, then left-merge (order journey) | picture 08 · `test_checked_merge_never_multiplies_rows` · `data/processed/order_journey.csv` |
| Ticket + intervention + still > 15 min late = didn't work | `output/breakdowns/journey_patterns.csv`: 31 orders |
| Whether to build the AI predictor now | picture 14 · `output/decision_memo.md` |

## If you are asked

- **"Why 1,486 and not 1,495?"** The 1,495 includes 9 orders with impossible timestamps. Both numbers are in picture 04 and `output/breakdowns/definition_comparison.csv`.
- **"Is the rule overfitted?"** The threshold was chosen on 1–21 Aug and judged on 22–28 Aug. See `output/insights/early_warning_backtest.csv`.
- **"Prove the pipeline reproduces the output from raw inputs."** See `output/replay_proof.md`: REPRODUCED, 28/28 hashes, 46/46 outputs. CI repeats it on Linux.
- **"What if the data is messier?"** Run `python -m pytest tests/test_hidden_messy_data.py -q`.
- **"Where are the class notebooks?"** In `Challenges/`, with the answers mapped in `docs/session-5-challenges.md`, `docs/session-6-challenges.md` and `docs/session-7-challenges.md`.

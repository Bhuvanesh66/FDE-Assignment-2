# Demo video script: 5 minutes, picture first

The brief asks for **a 3–5 minute demo using the GitHub project, explaining one important FDE judgement call**. This script runs **5:00**:

- **5 equal blocks** for the five grading areas (20 % each);
- **1 block** for the judgement call;
- a short opening and close.

Every block says **what to show** and **what to say**. The words are simple on purpose: let the picture do the explaining. Every number matches the committed outputs of run `run_example`.

> An optional longer cut (about 8 minutes) is at the end. Submit the 5-minute version unless your instructor allows longer.

## Before you record (5 minutes of setup)

1. **Browser tab 1:** the GitHub repository README. It shows all the pictures, top to bottom in the order of this script.
2. **Browser tab 2:** `notebooks/pipeline_walkthrough.ipynb` on GitHub, which shows the code and its outputs.
3. **Browser tab 3:** the `data/raw/run_example/api/` folder on GitHub.
4. **VS Code terminal** in `assignment-2`, with the environment active (`.venv\Scripts\activate`), zoomed to about 150 %.
   - Type the replay command without pressing Enter: `python run_pipeline.py --replay run_example --run-id run_replay_check`
5. **Browser zoom:** about 110 %, so the text in the pictures is readable on the recording.
6. **After recording:** if you ran anything, restore the committed evidence with `git restore output data`.

## Where each required item appears in the video

| Required by the brief | Shown at | What is on screen |
|---|---|---|
| Source map | 0:20 | picture 02 · `docs/source-map.md` |
| Workflow / data model diagram | 2:35 | pictures 06, 07 and 08 |
| Code / notebook: retrieval, validation, modelling, joins, metrics | 1:05, 2:35 | `notebooks/pipeline_walkthrough.ipynb` on GitHub |
| Runnable pipeline that reproduces the output from raw inputs | 3:25 | terminal: the replay runs live and prints REPRODUCED |
| Evidence table / dashboard with 3–5 metrics | 2:35 | picture 09 (M1–M5) |
| Known / Unknown / Assumption / Limitation | 3:15 | picture 11 |
| One important FDE judgement call | 4:10 | picture 14 |

---

## 0:00–0:20 · Opening (20 s)

**SHOW:** README top, then scroll to **picture 01: "A trustworthy path from client systems to a business decision"**. Move the mouse slowly along the six boxes from left to right, then along the red STOP boxes under them.

**SAY:**
> "Hi, I'm Bhuvanesh. This is FDE Assignment 2, Track A: FlashEats. The client says deliveries are late and wants to buy an AI predictor. My goal was not to analyse a dataset. It was to build a trustworthy path from their systems to a business decision. This picture is that path, and under every step is the check that stops it when trust breaks."

---

## 0:20–1:05 · ① Source reasoning (45 s, 20 %)

**SHOW:** **picture 02, the source map.** Point at the left column, then the right column, then the red GAP box. For 2 seconds, click `docs/source-map.md` to show the full table with owners and grain.

**SAY:**
> "First: where does the truth live? On the left are five business questions. On the right are the eight sources that answer them: the orders database, the Dispatch API, driver-app events, the restaurant feed, app actions, support tickets, the interventions log, and one outside source, real weather. Each box says who owns it and what one row means. Green I trust. Orange I use with care.
>
> The red box is the most important finding here: no system records when the driver reaches the restaurant. That gap shapes every conclusion later."

---

## 1:05–1:50 · ② Retrieval (45 s, 20 %)

**SHOW:**
1. **Picture 03, the retrieval proof.** Point at the two orange bars, then the green ✓ column.
2. The GitHub folder `data/raw/run_example/api/`, with its 16 saved pages (2 s).
3. The walkthrough notebook, section **"1 · Ingest"** (2 s).

**SAY:**
> "Second: did we get all of it? I used four retrieval modes: SQL, a REST API, CSV and JSON. The Dispatch API failed on purpose. Page 3 returned an error 500, page 5 an error 429, and both were retried. I don't trust a success message. I count. We got 1,600 records, exactly the server's total. The client also publishes its own totals, and all six match.
>
> Every raw file and API page is saved here with a fingerprint, so I can rebuild everything later without touching their systems again."

---

## 1:50–2:35 · ③ Validation (45 s, 20 %)

**SHOW:** **picture 04, the funnel from 1,603 rows.** Go down the bars. Then **picture 05, the validation gate.** Point at one green, one orange, the grey, and the OVERALL box.

**SAY:**
> "Third: can we trust it for this decision? This funnel shows every row I removed, and why.
>
> - 1,603 rows, of which 3 are duplicates.
> - 68 cancelled.
> - 37 have no delivery time. I mark them unknown. I never guess.
> - 9 have impossible times, like a promise made before the order existed.
>
> That leaves 1,486 trusted deliveries, and 837 of them were late: 56.33 %. Nothing disappears silently, and a ledger proves it.
>
> Then the gate. Green passes, orange is a warning, grey means an owner must decide, and any red would stop publication. Today it says: publish, with the caveats written next to the number."

---

## 2:35–3:25 · ④ Workflow + metrics (50 s, 20 %)

**SHOW:**
1. **Picture 06, one order across seven systems** (8 s). Point at the priority dispatch, the support ticket, and the red "26 min late" line.
2. **Picture 08, the data model.** Point at the green arrow, "aggregate, then 1:1".
3. The walkthrough notebook, section **"5 · Workflow model and 6 · metrics"** (2 s).
4. **Picture 09, the five metric tiles.**
5. **Picture 11, the K/U/A/L quadrants** (3 s).

**SAY:**
> "Fourth: the workflow. I started with one real order, as seven systems saw it. It was created and assigned, ops gave it priority dispatch, the customer still raised a ticket, and it arrived 26 minutes late. So the intervention did not work.
>
> Then I modelled everything around the order. Every many-rows table is summed to one row per order before the join, so nothing is double counted.
>
> Five metrics, computed in pandas and again in SQL, and both agree. The key one is M3: 99 % of the lateness builds up before pickup, not on the road. And here is what I know, what I don't know, what I assumed, and what this data can't do."

---

## 3:25–4:10 · ⑤ Pipeline dependability (45 s, 20 %)

**SHOW:**
1. Press **Enter** in the terminal on the prepared replay command, and let it run (about 17 s).
2. While it runs, show **picture 12, the pipeline flow.** Point at the STOP badges.
3. Back to the terminal: point at `COMPLETED` and the replay-proof line. Then open **picture 13** and point at **REPRODUCED 46/46** and the four weekly bars.

**SAY:**
> "Fifth: can it run again, and does it stop itself? One command runs all ten stages, from the raw client systems to every file and picture you have seen. The red badges are stop points. If a count doesn't match, a rule breaks its tolerance, or two methods disagree, nothing is published.
>
> Right now I'm replaying the whole run from the saved raw files. No client system is touched. All 28 fingerprints match, and all 46 outputs come out byte-identical. It also runs week by week: four gated weeks that add up exactly to the month. And 133 automated tests break it on purpose: API down, missing files, strange values."

---

## 4:10–4:50 · The FDE judgement call (40 s)

**SHOW:** **picture 14, the judgement call.**
1. Top half: move along the one-order timeline from "ALERT" to "promised ETA", the orange warning window.
2. Bottom half: point at the green line at k = 10.

**SAY:**
> "My most important judgement call. The class question was: should FlashEats build the AI predictor now? My answer: not yet, but act today.
>
> Because the delay builds before pickup, I used Dispatch's own estimate. If an order still isn't picked up 10 minutes after it, alert ops. I chose 10 minutes on the first three weeks and tested it on a week it had never seen:
>
> - 96 % of alerts were right;
> - it caught 72 % of late orders;
> - it fired 45 minutes before the promise broke.
>
> Today, 446 of those orders got no help at all. The rule is cheap and explainable, and it becomes the baseline any AI must beat."

---

## 4:50–5:00 · Close (10 s)

**SHOW:** **picture 15, "where the class stopped".** Scroll it once.

**SAY:**
> "I also re-tested the class's GPS claim on this data, checked the weather label against real rain, and measured the ETA itself. It's all in the repository. Thank you."

---

## Say it simply: the five sentences to remember

1. **Sources:** "Five questions, eight sources, one gap: nobody records arrival at the restaurant."
2. **Retrieval:** "I don't trust a 200. I count: 1,600 of 1,600, and 6 of 6 client totals."
3. **Validation:** "Nothing disappears silently. 1,603 rows become 1,486 trusted deliveries, and every removal has a reason."
4. **Workflow + metrics:** "One row per order, five metrics, and 99 % of the lateness happens before pickup."
5. **Dependability:** "Same inputs, same outputs, byte for byte, and it stops itself when trust breaks."

## Optional longer cut (about 8 minutes)

Add these after the 5-minute blocks, only if longer videos are allowed:

| Add after | Show | Say (one or two lines) |
|---|---|---|
| Opening | the `Challenges/` folder on GitHub | "All four class notebooks are answered here, with sir's cells kept. This project starts where they stop." |
| ① Sources | picture 02, the Q5 → Open-Meteo arrow | "I added an outside source to test the weather label, because Operations blames the weather." |
| ③ Validation | `config/pipeline.yaml` | "Every threshold has an owner. If VP Operations changes the definition of late, it's one line and a rerun." |
| ④ Metrics | picture 07, the order workflow | "Customer reactions and ops interventions sit next to the lifecycle. The orders table alone only says 'delivered'." |
| ④ Metrics | picture 10, where the delay builds | "Late orders lose 12 extra minutes before pickup, and only about 4 extra in transit." |
| Judgement call | dashboard (`streamlit run app/dashboard.py`), Early-warning tab slider | "Ops can try their own k here. It recomputes live from the modelled orders." |
| Close | picture 15, the GPS row | "Session 6 said GPS has pings before pickup and none after. Here the pings look drawn, not measured: 91 % are perfect straight lines. So no geofence should be built on them." |

## Likely questions, and where the answer is

- **"Why 1,486 and not 1,495?"** The 1,495 is the dashboard's own definition. See `output/breakdowns/definition_comparison.csv` and picture 04.
- **"Is the trigger overfitted?"** The threshold was chosen on 1–21 Aug and judged on 22–28 Aug. See `output/insights/early_warning_backtest.csv`.
- **"Prove retrieval is complete."** See `data/raw/run_example/ingestion_manifest.json` (pages, retries, control totals) and picture 03.
- **"Prove the pipeline reproduces the output."** See `output/replay_proof.md`: REPRODUCED, 28/28 hashes, 46/46 outputs.
- **"What if the data is messier?"** Run `python -m pytest tests/test_hidden_messy_data.py -q`.
- **"Where are the class answers?"** See `Challenges/` and `docs/session-5-challenges.md`, `docs/session-6-challenges.md`, `docs/session-7-challenges.md`.

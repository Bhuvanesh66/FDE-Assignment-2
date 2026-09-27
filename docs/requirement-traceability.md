# Requirement traceability

Every requirement → source → implementation → test → evidence. Paths are relative to `assignment-2/`.

## A. Assignment 2 (`FDE_Assignment2.pdf`)

| Requirement | Source | Implementation | Test | Evidence / output |
|---|---|---|---|---|
| Choose a track; realistic operational problem, messy sources, explainable dependable pipeline | Assignment p.1 | Track A (FlashEats-style) on the classroom pack under `source_systems/` | — | `README.md` §1 |
| **Class 4 — Understand sources:** business questions → information → source systems; ownership, grain, gaps | Assignment table row 4 | `docs/source-map.md` | — | source map with 9 sources, 8 gaps |
| **Class 5 — Retrieve data:** ≥ 2 retrieval modes (SQL, API, JSON/CSV); show retrieval is complete; preserve raw inputs | row 5 | `sql/*.sql` + `ingest/sql_source.py`; `ingest/api_source.py`; `ingest/file_source.py` (CSV + nested JSON); raw snapshot per run | `test_sql_source.py`, `test_api_source.py` (15), `test_file_source.py` (11) | `data/raw/run_example/`, `api/ingestion_report.json` (complete=true), `ingestion_manifest.json` with SHA-256 |
| **Class 6 — Profile & validate:** profile, meaningful quality issues, business-oriented validation rules, assumptions/limitations recorded instead of silently fixed | row 6 | `profiling.py`; `cleaning.py` (representation only + quarantine); `rules.py` (37 rules); `gate.py` | `test_cleaning_rules.py`, `test_hidden_messy_data.py` | `output/profile/profile.md`, `output/data_quality_report.md`, `output/quarantine/`, `output/validation_gate.md`, `docs/data-quality-rules.md`, `docs/assumptions-limitations.md` |
| **Class 7 — Model workflow:** entities, events/states, interactions/interventions/outcomes; simple relational/event model; 3–5 metrics linked to the KPI | row 7 | `model.py` (3 dims, 4 facts, `order_journey`); `metrics.py` (M1–M5) | `test_model_metrics.py` | `docs/data-model.md`, `data/processed/*.csv`, `output/metrics.csv` |
| **Class 8 — Dependable pipeline:** ingest → validate → transform/model → metric output; logging/checks, rerun behaviour, failure handling | row 8 | `pipeline.py`, `cli.py`, `run_pipeline.py`, `logging_utils.py` | `test_pipeline_e2e.py` (10), `test_hidden_messy_data.py` (9) | `output/pipeline.log`, `output/run_manifest.json`, `docs/pipeline-dependability.md` |
| README: problem, users/stakeholders, project KPI, source overview, setup/run, decision supported | Submission package | `README.md` | — | — |
| Source map + workflow/data model diagram in the repo | Submission package | `docs/source-map.md`, `docs/data-model.md` (mermaid) | — | — |
| Code/notebooks showing retrieval, validation, modelling, joins/aggregations, metrics + runnable script reproducing the output from raw inputs | Submission package | `src/flasheats_pipeline/`, `notebooks/Session{5,6,7}_Challenges.ipynb`, `run_pipeline.py` | full suite | executed notebooks with outputs |
| Final evidence table/dashboard with 3–5 metrics + Known/Unknown/Assumption/Limitation | Submission package | `reports.py` | e2e test asserts files exist | `output/evidence_table.md`, `output/dashboard.html`, `output/known_unknown_assumption_limitation.md` |
| 3–5 minute demo explaining one FDE judgement call | Submission package | `docs/demo-script.md` | — | — |
| Challenge notebooks submitted in the repo (instructor, Class 7 lecture) | `session-7` transcript | `notebooks/` | executed by `build_notebooks.py` | outputs embedded |
| Grading: source reasoning / retrieval / validation / workflow + metrics / dependability (20 % each) | Assignment p.2 | mapped above | — | — |

## B. Session 5 concepts and challenges → see `docs/session-5-challenges.md`

| Item | Implementation | Test | Evidence |
|---|---|---|---|
| Ch1 define late, denominator, cancelled, missing timestamps, grain; counts; median; worst; DQ issues | `metrics.py` M1/M1a/M2/M2b, `rules.py` TS-*, `cleaning.dedupe` | `test_metrics_match_hand_computation`, `test_fact_order_grain_and_population` | `output/metrics.md`, `breakdowns/worst_delays.csv`, notebook §Ch1 |
| Ch2 traffic claim on ≥ 3 dimensions with chart | `metrics._rate_table`, `reports.write_charts` | `test_stage_decomposition_identity_and_breakdowns` | `output/charts/`, `breakdowns/late_rate_by_*.csv`, notebook §Ch2 |
| Ch3 tickets: categories, unique ids, LEFT join, system vs customer view | `fact_interaction`, `customer_view_vs_system_view` | `test_event_log_is_ordered_and_multi_source`, breakdown assertions | notebook §Ch3 |
| Ch4 API pagination, retry, raw pages, completeness | `DispatchApiClient` | `test_api_source.py` | `data/raw/run_example/api/`, notebook §Ch4 |
| Ch5 driver events observed vs inferred; no arrival event | `flatten_driver_events`, TS-07, RG-03, model notes | `test_flatten_driver_events_tolerates_shapes` | notebook §Ch5 |
| Final synthesis slide | notebook final section, `docs/demo-script.md` | — | — |

## C. Session 6 concepts and challenges → see `docs/session-6-challenges.md`

| Item | Implementation | Test | Evidence |
|---|---|---|---|
| Ch1 validation contract; grain; completion; chronology; owner questions | `rules.py` GR-01, TS-01…05 | `test_rules_fire_on_every_injected_defect` | `output/data_quality_report.md` §5 |
| Ch2 late rate under ≥ 3 definitions; owner | M1/M1a/M1b/M1c, KPI-01, gate | `test_metrics_match_hand_computation` | `breakdowns/definition_comparison.csv` |
| Ch3 categories: representation vs semantics | `cleaning.VOCAB/SEMANTIC_CANDIDATES`, ST-01…09 | `test_categories_representation_fixed_semantics_kept`, `test_semantic_lookalikes_are_never_merged_silently` | report §1, §3 |
| Ch4 cross-source coverage; is 1 % acceptable | ID-02…10, CX-01…03 | `test_rules_fire_on_every_injected_defect` | report §5, gate "Cross-source mapping" |
| Ch5 freshness per use case | FR-01 | rule test | gate "Freshness" |
| Ch6 validation gate + publish decision | `gate.py` | `test_gate_is_warn_not_fail_for_recoverable_defects`, `test_gate_fails_when_ingestion_incomplete` | `output/validation_gate.md` |
| Profiling before cleaning; ranges; suspicious values; identifier mismatch | `profiling.py`, RG-01…04 | `test_zero_rows…`, rules test | `output/profile/profile.md` |

## D. Session 7 concepts and challenges → see `docs/session-7-challenges.md`

| Item | Implementation | Test | Evidence |
|---|---|---|---|
| Ch1 order timelines from all sources | `build_fact_event` | `test_event_log_is_ordered_and_multi_source` | notebook §Ch1, `data/processed/fact_event.csv` |
| Ch2 canonical model (PK/FK/grain) | `model.py`, `docs/data-model.md` | grain assertions | `join_checks.json` |
| Ch3 interaction → intervention → outcome table + 4 answers | `build_order_journey`, M4/M4b/M5/M5c | `test_journey_aggregation_does_not_inflate_rows` | `data/processed/order_journey.csv`, `breakdowns/journey_patterns.csv` |
| Ch4 3–5 metrics (outcome, interaction, intervention) | `metrics.py` | `test_metrics_match_hand_computation` | `docs/metrics.md`, `output/metrics.csv` |
| Ch5 joins/aggregations A–E with "tells / does not prove" | breakdowns + notebook | breakdown assertions | notebook §Ch5 |
| Ch6 KPI linkage; controllable vs outcome; missing event; instrument next | README KPI tree, notebook §Ch6 | — | — |

## E. FDE principles from Sessions 1–3 applied

| Principle | Where visible |
|---|---|
| A client request is a hypothesis, not a specification ("56 % late") | definition comparison, gate UNKNOWN on KPI ownership |
| Facts / assumptions / unknowns kept separate | `docs/assumptions-limitations.md`, generated K/U/A/L section |
| Evidence > assumptions; ask for reality (walk through one order) | order timelines (Session 7 Ch1) |
| SMART problem framing with one KPI, supporting metrics and guardrails | M1 KPI, M2–M5 supporting, cancelled-order guardrail (Finance), definition guardrail |
| Issue tree → hypotheses → quickest analysis | stage decomposition (M3) answers "kitchen/dispatch vs road" before any model is built |
| Pyramid-principle communication (few words, tables, diagrams) | README, evidence table, demo script |
| Don't build the AI yet — prove the problem and the measurement first | decision in the synthesis slide |

## F. Robustness requirements (brief Phases 11–14, 17, 23)

| Requirement | Implementation | Test |
|---|---|---|
| nulls / missing columns / blanks | `read_csv_source` required-column check, blank → None, quarantine of missing keys | `test_file_source.py`, `test_pipeline_e2e.py::test_missing_*` |
| duplicates (rows, events, API pages) | `cleaning.dedupe`, aggregation before join, API overlap detection | `test_duplicates_*`, `test_duplicate_business_events_*`, `test_overlapping_pages_*` |
| categories (unexpected, case, whitespace, spelling) | `normalise_category` + vocab + semantic candidates | `test_categories_*`, `test_new_status_value_*` |
| dates (formats, malformed, tz) | `parse_timestamps` | `test_timestamps.py`, `test_all_timestamps_unparseable_*` |
| ids (whitespace, case, unknown references) | `normalise_ids`, ID-* rules | `test_identifiers_*`, `test_ids_with_whitespace_*` |
| SQL zero rows / missing tables / join duplication | `SqlSource`, `_checked_merge` | `test_sql_source.py`, join-check assertions |
| API timeout / HTTP error / malformed JSON / missing fields / empty / pagination / partial | `DispatchApiClient` | `test_api_source.py` |
| independent metric validation | SQL recomputation, reference reconciliation, identities | `metric_checks.csv` |

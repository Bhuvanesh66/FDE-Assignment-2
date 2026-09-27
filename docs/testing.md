# Testing and validation

```
python -m pytest            # 111 tests, ~2 minutes (starts fault-injecting Dispatch and weather APIs on free ports)
```

The fixtures (`tests/conftest.py`) build a **14-order synthetic pack** whose every metric is hand-checkable (`EXPECTED`), plus `FakeDispatchServer`, an HTTP server that can be switched into failure modes (`flaky`, `always_500`, `not_found`, `timeout`, `malformed_json`, `missing_data_key`, `no_has_more`, `wrong_total`, `overlap`, `empty`, `never_ends`, `missing_fields`).

## Required test matrix

| # | Scenario (assignment brief) | Test(s) | What is asserted |
|---|---|---|---|
| 1 | Normal / clean data | `test_pipeline_e2e.py::test_normal_clean_data_passes_cleanly` | grain, chronology and retrieval checks PASS; 2 of 4 late |
| 2 | Missing values (nulls, blanks, missing columns, missing files) | `test_file_source.py` (header-only, missing column names the column, blanks → None), `test_cleaning_rules.py` (null restaurant/driver/order ids), `test_pipeline_e2e.py::test_missing_required_file_names_the_file`, `::test_optional_reference_file_may_be_absent`, `::test_missing_database_fails_clearly` | clear errors naming the file/column; optional file absence is not a failure |
| 3 | Duplicate records / events | `test_cleaning_rules.py::test_duplicates_exact_dropped_conflicting_kept_first_and_recorded`, `test_hidden_messy_data.py::test_duplicate_business_events_do_not_inflate_counts`, `test_api_source.py::test_overlapping_pages_are_detected` | exact dups dropped and counted, conflicting dups quarantined, per-order counts never inflate, API overlap flagged |
| 4 | Invalid categories | `test_cleaning_rules.py::test_categories_representation_fixed_semantics_kept`, `test_hidden_messy_data.py::test_new_status_value_is_flagged_not_counted_as_delivered`, `::test_semantic_lookalikes_are_never_merged_silently` | `gridlock`/`suspended`/`refunded` retained + flagged; look-alikes never merged |
| 5 | Formatting inconsistencies (case, whitespace, headers) | `test_file_source.py::test_column_names_and_cells_are_normalised_and_raw_copy_preserved`, `test_cleaning_rules.py::test_identifiers_are_trimmed_and_uppercased`, `test_hidden_messy_data.py::test_csv_headers_in_different_case_and_extra_columns`, `::test_ids_with_whitespace_and_lowercase_in_every_source_still_join` | ` o00003 ` still joins; `Order_ID` header works; raw file untouched |
| 6 | Invalid dates / timestamps | `test_timestamps.py` (mixed layouts, garbage, tz-aware, mixed tz/naive, empty), `test_cleaning_rules.py::test_timestamps_parsed_and_issues_counted`, `test_hidden_messy_data.py::test_all_timestamps_unparseable_fails_the_gate_instead_of_publishing_zero` | `not-a-date` → NaT counted; `+05:30` normalised; 100 % unparseable ⇒ gate FAIL, nothing published |
| 7 | Identifier mismatch (unknown references) | `test_cleaning_rules.py::test_rules_fire_on_every_injected_defect` (ID-03…ID-09), `test_hidden_messy_data.py::test_dispatch_covers_only_half_the_orders_is_flagged` | coverage % reported; unknown driver `D999`, foreign order `O88888`, unknown dispatch order flagged |
| 8 | Empty input / zero rows | `test_sql_source.py::test_extract_preserves_raw_and_reports_zero_rows`, `test_model_metrics.py::test_zero_rows_gives_unknown_metrics_not_crash`, `test_hidden_messy_data.py::test_orders_table_empty_is_reported_not_crashed`, `test_api_source.py::test_empty_result_is_incomplete_not_a_crash` | metrics `None`, denominator check FAIL, gate FAIL, no crash |
| 9 | API failure (timeout, 4xx/5xx, malformed JSON, missing fields, pagination) | `test_api_source.py` (15 tests), `test_pipeline_e2e.py::test_api_down_fails_clearly_and_writes_manifest`, `::test_api_down_with_snapshot_fallback_degrades_to_warn`, `::test_incomplete_api_blocks_publication` | retries with back-off and `Retry-After`; 404 not retried; incompleteness blocks publication; snapshot fallback degrades to WARN |
| 10 | Hidden-data simulation (evaluator scenarios) | `test_hidden_messy_data.py` (9 scenarios), `test_pipeline_e2e.py::test_messy_pack_end_to_end_outputs_and_raw_preservation` | full pipeline on the messy pack: **62.5 % = 5/8** exactly as hand-computed, all evidence files written, raw preserved byte-for-byte |

Business-correctness tests (not just "it runs"): `test_model_metrics.py` checks the KPI population, outcome buckets, Dispatch-as-final-driver, back-fill sensitivity separation, journey aggregation counts, event ordering, every metric against hand computation, the stage identity, breakdown ordering, and the gate decisions (WARN for recoverable defects, FAIL for incomplete ingestion).

## Validation performed on the real classroom pack

| Check | Result |
|---|---|
| Independent SQL recomputation of M1 from the raw database | 1486 / 837 — identical to pandas |
| Reconciliation with the client's `order_outcomes.csv` | late 843 = 843; max delay difference 0.000 min over 1495 orders |
| Reference figures from the Class 5 solution (1603/1600/3, 68, 37, 1495, 843, 56.4 %, 1600 dispatch, 95 reassigned, 1 duplicate ticket, 0 arrival events) | all reproduced |
| Join cardinality (5 merges) | all preserve the left row count |
| Stage identity | max residual 0.010 min |
| Rerun | identical headline on rerun; every run keeps its own raw snapshot |

## Tests for the additions beyond the class (38 tests)

| File | What it proves |
|---|---|
| `test_config.py` (9) | the repository policy file loads; values and overrides flow into the run; **typos in business thresholds fail loudly** (unknown key, section or shape); the CLI applies a policy file (late = more than 10 min gives 2 late orders on the pack) |
| `test_weather_source.py` (14) | payload validation (missing arrays, empty, unequal lengths, wrong timezone, API error body); retry on 503; **7 unusable-response modes fall back to the reference copy, or to UNKNOWN without one**; an unreachable API is never fatal; the pipeline's WX-01 counts exactly 5 disagreements on the pack, PASSes when the label agrees and is UNKNOWN when disabled |
| `test_insights.py` (9) | Wilson interval known values; Cohen's kappa; **early-warning backtest hand-checked** (alerts, precision, recall, lead time, chosen *k*, and an explicit "no hold-out" flag on data without a late-August week); ETA padding hand-checked (+20 min for 80 % on the pack) and monotone; fair ranking refuses to judge small samples and keeps the unknown restaurant; the GPS test tells converging from diverging pings; what-ifs are labelled as assumptions; empty data yields no findings instead of a crash |
| `test_monitoring.py` (4) | the ledger balances and **detects a silently dropped row**; run comparison states (no baseline, stable, KPI drift, rule got worse); a rerun compares with the previous published run |
| `test_dashboard.py` (2) | the Streamlit app renders from real pipeline outputs, the trigger slider recomputes precision, the order explorer accepts lower-case ids, and with no runs it tells the user what to run |

The four classroom notebooks and the walkthrough are also **executed end to end** by `python notebooks/build_notebooks.py` (`allow_errors=False`), so a broken answer cell fails the build.

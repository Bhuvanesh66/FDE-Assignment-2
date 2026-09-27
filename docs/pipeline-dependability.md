# Pipeline dependability (Class 8 expectations)

`ingest → validate → transform/model → metric output`, with logging/checks, rerun behaviour and failure handling.

## Stages and the checks between them

| # | Stage | Module | Checks that gate the next stage | Written artefacts |
|---|---|---|---|---|
| 1 | Ingest + raw preservation | `ingest/*` | DB/table/file exist and are non-empty; required columns present; JSON valid; API pagination complete (records = `total_records`, unique ids, no empty page with `has_more`) | `data/raw/<run_id>/sql/*.csv+.sql`, `files/*` (byte copies + SHA-256), `api/dispatch_page_*.json`, `ingestion_report.json`, `ingestion_manifest.json` |
| 2 | Profile | `profiling.py` | none (read-only) | `output/profile/profile.{md,json}` |
| 3 | Clean / standardise | `cleaning.py` | every change counted; quarantine for unusable rows | `output/data_quality_report.*` §1–4, `output/quarantine/*.csv` |
| 4 | Validate | `rules.py` | 37 business rules → PASS/WARN/FAIL/UNKNOWN; reject rules define the KPI population | `output/data_quality_rules.csv`, report §5 |
| 5 | Model | `model.py` | every merge preserves the left row count (`validate=`); `fact_order` / `order_journey` unique on `order_id` | `data/processed/*.csv`, `flasheats_model.sqlite`, `join_checks.json` |
| 6 | Metrics | `metrics.py` + `sql/independent_late_rate_check.sql` | denominator > 0; late + on-time = population; buckets sum to orders; stage identity; reconciliation with reference file; independent SQL recomputation | `output/metrics.{csv,json,md}`, `metric_checks.csv`, `breakdowns/*.csv` |
| 7 | Gate | `gate.py` | 8 checks → overall status and publish decision | `output/validation_gate.{md,json}` |
| 8 | Outputs | `reports.py` | publication only if the gate is not FAIL | `evidence_table.md`, `known_unknown_assumption_limitation.md`, `charts/*.png`, `dashboard.html`, `run_manifest.json`, `pipeline.log` |

## Logging
One log per run (`output/runs/<run_id>/pipeline.log`, copied to `output/pipeline.log` on publication): stage banners, row counts in and out of every stage, every cleaning action with counts, every rule with status and violations, every merge with cardinality, every metric with numerator/denominator, every check and gate decision. WARN/ERROR levels are used so `grep WARNING pipeline.log` is a summary of what needs an owner.

## Rerun behaviour
- Every run has a `run_id` (timestamp or `--run-id`). Raw snapshots are **never overwritten**: `data/raw/<run_id>/` accumulates (older ones may be pruned; `.gitignore` keeps only `run_example`).
- `data/processed/` and `output/` are the *latest published* view and are rewritten atomically per run; the per-run copy lives in `output/runs/<run_id>/`.
- Re-running on the same inputs produces the same numbers (tested); `run_manifest.json` records inputs (hashes), config, stage timings, rule statuses and outputs, so any two runs can be diffed.
- If the API is down, `--fallback-snapshot` reuses the newest preserved raw pages and the gate degrades retrieval to **WARN** (explicit, never silent).

## Failure handling
| Situation | Behaviour |
|---|---|
| database / required file missing, empty, unreadable, required column absent | run **FAILED** with a message naming the object; manifest written with the error; nothing published |
| API timeout / connection error / 429 / 5xx / malformed JSON | retried with exponential back-off (honours `Retry-After`), then **FAILED** with the page and cause |
| API 4xx configuration errors | not retried; **FAILED** immediately |
| API incomplete (count mismatch, overlap, zero records) | run continues so the evidence is visible, but the gate **FAILS** and outputs stay in `output/runs/<run_id>/` only |
| > 10 % KPI timestamps unparseable, > 15 % delivered without delivery time, empty orders table, Dispatch covering < 50 % | gate **FAIL** (not published) |
| any unexpected exception in a stage | caught at the orchestrator, logged with traceback into the manifest, status FAILED, exit code 1 |
| exit codes | 0 completed, 1 failed, 2 gate failed |

## Reproducing the submitted outputs
```
python -m venv .venv && .venv\Scripts\activate      # or source .venv/bin/activate
pip install -r requirements.txt
python run_pipeline.py --start-api --run-id run_example
python -m pytest
python notebooks/build_notebooks.py                 # optional: re-execute the challenge notebooks
```

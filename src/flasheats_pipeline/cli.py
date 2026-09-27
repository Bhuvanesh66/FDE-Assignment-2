"""Command-line entry point: ``python run_pipeline.py [options]``."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import PipelineConfig
from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="FlashEats late-delivery KPI pipeline (ingest → validate → model → metrics).")
    p.add_argument("--source-root", type=Path, default=None, help="folder holding database/, data/ and api/ (default: ./source_systems)")
    p.add_argument("--data-dir", type=Path, default=None, help="where raw snapshots and processed tables go (default: ./data)")
    p.add_argument("--output-dir", type=Path, default=None, help="where evidence outputs go (default: ./output)")
    p.add_argument("--run-id", default=None, help="explicit run id (default: timestamp)")
    p.add_argument("--api-url", default="http://127.0.0.1:8000", help="Dispatch API base URL")
    p.add_argument("--start-api", action="store_true", help="start the mock Dispatch API from source_systems/api for this run")
    p.add_argument("--page-size", type=int, default=100)
    p.add_argument("--api-timeout", type=float, default=10.0)
    p.add_argument("--api-retries", type=int, default=5)
    p.add_argument("--fallback-snapshot", action="store_true", help="if the API is down, reuse the newest preserved raw snapshot (run degrades to WARN)")
    p.add_argument("--late-threshold", type=float, default=0.0, help="minutes beyond promised ETA that count as late (KPI definition)")
    p.add_argument("--meaningful-late-threshold", type=float, default=10.0)
    p.add_argument("--no-charts", action="store_true")
    p.add_argument("--publish-even-if-gate-fails", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    kwargs = dict(api_base_url=args.api_url, api_page_size=args.page_size, api_timeout_s=args.api_timeout, api_max_retries=args.api_retries,
                  start_mock_api=args.start_api, api_fallback_to_last_snapshot=args.fallback_snapshot, late_threshold_min=args.late_threshold,
                  meaningful_late_threshold_min=args.meaningful_late_threshold, write_charts=not args.no_charts,
                  fail_on_gate="NEVER" if args.publish_even_if_gate_fails else "FAIL")
    for k in ("source_root", "data_dir", "output_dir", "run_id"):
        if getattr(args, k) is not None:
            kwargs[k] = getattr(args, k)
    cfg = PipelineConfig(**kwargs)
    run = run_pipeline(cfg)
    print(f"\nrun {cfg.run_id}: {run.status}")
    if run.error:
        print(f"error: {run.error}")
        return 1
    print(f"gate: {run.gate.get('overall_status')} — {run.gate.get('publish_decision')}")
    print(f"headline: {run.headline}")
    print(f"outputs: {cfg.output_dir}")
    return 0 if run.status == "COMPLETED" else 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

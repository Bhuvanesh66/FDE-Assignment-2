"""Command-line entry point: ``python run_pipeline.py [options]``.

Values come from ``config/pipeline.yaml`` (stakeholder-owned policy); any flag given
on the command line overrides the file for that run only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .pipeline import run_pipeline

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "pipeline.yaml"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="FlashEats late-delivery KPI pipeline (ingest → validate → model → metrics → decision layer).")
    p.add_argument("--config", type=Path, default=None, help=f"policy file (default: {DEFAULT_CONFIG.name} if present)")
    p.add_argument("--no-config", action="store_true", help="ignore the policy file and use built-in defaults")
    p.add_argument("--source-root", type=Path, default=None, help="folder holding database/, data/ and api/ (default: ./source_systems)")
    p.add_argument("--data-dir", type=Path, default=None, help="where raw snapshots and processed tables go (default: ./data)")
    p.add_argument("--output-dir", type=Path, default=None, help="where evidence outputs go (default: ./output)")
    p.add_argument("--run-id", default=None, help="explicit run id (default: timestamp)")
    p.add_argument("--api-url", default=None, help="Dispatch API base URL")
    p.add_argument("--start-api", action="store_true", help="start the mock Dispatch API from source_systems/api for this run")
    p.add_argument("--page-size", type=int, default=None)
    p.add_argument("--api-timeout", type=float, default=None)
    p.add_argument("--api-retries", type=int, default=None)
    p.add_argument("--fallback-snapshot", action="store_true", help="if the API is down, reuse the newest preserved raw snapshot (run degrades to WARN)")
    p.add_argument("--no-weather", action="store_true", help="skip the external observed-weather cross-check")
    p.add_argument("--late-threshold", type=float, default=None, help="minutes beyond promised ETA that count as late (KPI definition)")
    p.add_argument("--meaningful-late-threshold", type=float, default=None)
    p.add_argument("--no-charts", action="store_true")
    p.add_argument("--publish-even-if-gate-fails", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = None if args.no_config else (args.config or (DEFAULT_CONFIG if DEFAULT_CONFIG.exists() else None))
    overrides = dict(source_root=args.source_root, data_dir=args.data_dir, output_dir=args.output_dir, run_id=args.run_id,
                     api_base_url=args.api_url, api_page_size=args.page_size, api_timeout_s=args.api_timeout, api_max_retries=args.api_retries,
                     late_threshold_min=args.late_threshold, meaningful_late_threshold_min=args.meaningful_late_threshold)
    if args.start_api:
        overrides["start_mock_api"] = True
    if args.fallback_snapshot:
        overrides["api_fallback_to_last_snapshot"] = True
    if args.no_weather:
        overrides["weather_enabled"] = False
    if args.no_charts:
        overrides["write_charts"] = False
    if args.publish_even_if_gate_fails:
        overrides["fail_on_gate"] = "NEVER"
    try:
        cfg = load_config(config_path, **overrides)
    except ConfigError as exc:
        print(f"config error: {exc}")
        return 1
    run = run_pipeline(cfg)
    print(f"\nrun {cfg.run_id}: {run.status}  (policy: {cfg.config_file or 'built-in defaults'})")
    if run.error:
        print(f"error: {run.error}")
        return 1
    print(f"gate: {run.gate.get('overall_status')} — {run.gate.get('publish_decision')}")
    print(f"headline: {run.headline}")
    print(f"outputs: {cfg.output_dir}  ·  decision memo: {cfg.output_dir / 'decision_memo.md'}")
    return 0 if run.status == "COMPLETED" else 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

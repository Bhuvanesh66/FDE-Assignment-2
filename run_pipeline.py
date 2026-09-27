"""Runnable entry point - reproduces every output from the raw client sources.

    python run_pipeline.py --start-api

See README.md for options.  The heavy lifting lives in src/flasheats_pipeline/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from flasheats_pipeline.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

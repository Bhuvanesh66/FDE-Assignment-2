"""Redraw the visual story (output/visuals/*.png) from the published evidence.

The pipeline already draws these on every full run. Run this after `--replay` or `--weekly`,
so the reproducibility and weekly panels include those results too:

    python make_visuals.py
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from flasheats_pipeline.logging_utils import configure_logging  # noqa: E402
from flasheats_pipeline.visuals import build_visuals  # noqa: E402


def main() -> int:
    out = ROOT / "output"
    manifest = out / "run_manifest.json"
    if not manifest.exists():
        print("no published run in output/ - run `python run_pipeline.py --start-api` first")
        return 1
    run_id = json.loads(manifest.read_text(encoding="utf-8"))["run_id"]
    configure_logging(None)
    made = build_visuals(out, ROOT / "data" / "raw" / run_id, ROOT / "data" / "processed", out)
    run_dir = out / "runs" / run_id
    if run_dir.exists():                        # keep the run folder's copy in step with the published one
        if (run_dir / "visuals").exists():
            shutil.rmtree(run_dir / "visuals")
        shutil.copytree(out / "visuals", run_dir / "visuals")
    print(f"{len(made)} figures written to {out / 'visuals'}")
    for p in made:
        print("  ", p.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())

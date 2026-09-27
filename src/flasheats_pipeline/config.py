"""Pipeline configuration.

Every threshold that encodes a *business* decision lives here with a comment
saying who should own it.  Nothing in the code base hard-codes these numbers.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path


def new_run_id() -> str:
    return "run_" + dt.datetime.now().strftime("%Y%m%dT%H%M%S")


@dataclass
class PipelineConfig:
    # ------------------------------------------------------------------ paths
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])
    source_root: Path | None = None          # client systems snapshot (default: <root>/source_systems)
    data_dir: Path | None = None             # <root>/data
    output_dir: Path | None = None           # <root>/output
    run_id: str = field(default_factory=new_run_id)

    # ------------------------------------------------------------- Dispatch API
    api_base_url: str = "http://127.0.0.1:8000"
    api_page_size: int = 100                 # mock API caps page_size at 200
    api_timeout_s: float = 10.0
    api_max_retries: int = 5
    api_backoff_base_s: float = 0.5          # exponential back-off: 0.5, 1, 2, 4 ... capped
    api_backoff_cap_s: float = 4.0
    api_max_pages: int = 10_000              # hard stop against a server that never says has_more=False
    start_mock_api: bool = False             # launch source_systems/api/mock_dispatch_api.py for the run
    api_fallback_to_last_snapshot: bool = False  # if the API is down, reuse the newest raw snapshot (WARN)

    # ------------------------------------------------------ business thresholds
    # KPI definition. Owner: VP Operations (see client_metric_definitions.json).
    late_threshold_min: float = 0.0
    # "Meaningfully late" supporting definition. Owner: Support Lead.
    meaningful_late_threshold_min: float = 10.0
    # Plausible delivery distance for a single-city (Bengaluru) operation. Owner: Operations.
    max_plausible_distance_km: float = 50.0
    # Bounding box used to flag impossible coordinates (Bengaluru metro).  Owner: Operations / GIS.
    lat_range: tuple[float, float] = (12.5, 13.5)
    lon_range: tuple[float, float] = (77.2, 78.0)
    # Source timezone assumed for naive timestamps.  Owner: Data Team.
    source_timezone: str = "Asia/Kolkata"
    # Restaurant status freshness SLA used in the freshness check (minutes). Owner: Restaurant Ops.
    status_freshness_sla_min: float = 15.0

    # -------------------------------------------------------------- behaviour
    fail_on_gate: str = "FAIL"               # "FAIL" -> abort publishing when any check FAILs; "NEVER" to always write
    write_charts: bool = True

    # ------------------------------------------------------------------ helpers
    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root)
        self.source_root = Path(self.source_root) if self.source_root else self.project_root / "source_systems"
        self.data_dir = Path(self.data_dir) if self.data_dir else self.project_root / "data"
        self.output_dir = Path(self.output_dir) if self.output_dir else self.project_root / "output"

    # source-system locations -------------------------------------------------
    @property
    def db_path(self) -> Path:
        return self.source_root / "database" / "flasheats.db"

    @property
    def files_dir(self) -> Path:
        return self.source_root / "data"

    @property
    def mock_api_script(self) -> Path:
        return self.source_root / "api" / "mock_dispatch_api.py"

    @property
    def sql_dir(self) -> Path:
        return self.project_root / "sql"

    # pipeline locations ------------------------------------------------------
    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw" / self.run_id

    @property
    def raw_root(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def run_output_dir(self) -> Path:
        return self.output_dir / "runs" / self.run_id

"""Pipeline configuration.

Business thresholds live in ``config/pipeline.yaml`` with the name of the
stakeholder who owns each value (inspired by the idea that the engineer owns
the rule and the business owns the number). ``PipelineConfig`` holds safe
defaults so the package also works without the YAML file (tests, notebooks).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any


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
    config_file: str | None = None           # YAML the values came from (recorded in the manifest)

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

    # ------------------------------------------------------ external weather API
    weather_enabled: bool = True
    weather_base_url: str = "https://archive-api.open-meteo.com/v1/archive"
    weather_latitude: float = 12.9716
    weather_longitude: float = 77.5946
    weather_rain_threshold_mm: float = 0.1
    weather_timeout_s: float = 20.0
    weather_max_retries: int = 3

    # ------------------------------------------------------ business thresholds
    late_threshold_min: float = 0.0                  # owner: VP Operations
    meaningful_late_threshold_min: float = 10.0      # owner: Support Lead
    target_on_time_rate_pct: float = 80.0            # owner: VP Operations (proposed)
    max_plausible_distance_km: float = 50.0          # owner: Operations
    lat_range: tuple[float, float] = (12.5, 13.5)    # owner: Operations / GIS
    lon_range: tuple[float, float] = (77.2, 78.0)
    source_timezone: str = "Asia/Kolkata"            # owner: Data Team
    status_freshness_sla_min: float = 15.0           # owner: Restaurant Ops

    # ------------------------------------------------------ decision layer
    ew_grace_minutes_grid: tuple[int, ...] = (0, 5, 10, 15, 20, 25, 30)
    ew_min_precision: float = 0.90
    ew_train_until_day: int = 21
    eta_padding_grid_min: tuple[int, ...] = (0, 5, 10, 15, 20, 25, 30)
    fair_min_orders_restaurant: int = 15
    fair_min_orders_driver: int = 10
    fair_confidence: float = 0.95
    impact_prevented_share_scenarios: tuple[float, ...] = (0.25, 0.50)
    kpi_drift_alert_pp: float = 2.0

    # -------------------------------------------------------------- behaviour
    fail_on_gate: str = "FAIL"               # "FAIL" -> abort publishing when any check FAILs; "NEVER" to always write
    write_charts: bool = True

    # ------------------------------------------------------------------ helpers
    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root)
        self.source_root = Path(self.source_root) if self.source_root else self.project_root / "source_systems"
        self.data_dir = Path(self.data_dir) if self.data_dir else self.project_root / "data"
        self.output_dir = Path(self.output_dir) if self.output_dir else self.project_root / "output"
        self.lat_range = tuple(self.lat_range)
        self.lon_range = tuple(self.lon_range)
        self.ew_grace_minutes_grid = tuple(int(x) for x in self.ew_grace_minutes_grid)
        self.eta_padding_grid_min = tuple(int(x) for x in self.eta_padding_grid_min)
        self.impact_prevented_share_scenarios = tuple(float(x) for x in self.impact_prevented_share_scenarios)

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
    def external_cache_dir(self) -> Path:
        """Reference copy of the external weather response, used when the public API is unreachable."""
        return self.data_dir / "external"

    @property
    def run_output_dir(self) -> Path:
        return self.output_dir / "runs" / self.run_id


# YAML section.key -> PipelineConfig attribute
YAML_MAP: dict[tuple[str, str], str] = {
    ("kpi", "late_threshold_min"): "late_threshold_min",
    ("kpi", "meaningful_late_threshold_min"): "meaningful_late_threshold_min",
    ("kpi", "target_on_time_rate_pct"): "target_on_time_rate_pct",
    ("data_quality", "source_timezone"): "source_timezone",
    ("data_quality", "max_plausible_distance_km"): "max_plausible_distance_km",
    ("data_quality", "lat_range"): "lat_range",
    ("data_quality", "lon_range"): "lon_range",
    ("data_quality", "status_freshness_sla_min"): "status_freshness_sla_min",
    ("dispatch_api", "base_url"): "api_base_url",
    ("dispatch_api", "page_size"): "api_page_size",
    ("dispatch_api", "timeout_s"): "api_timeout_s",
    ("dispatch_api", "max_retries"): "api_max_retries",
    ("dispatch_api", "backoff_base_s"): "api_backoff_base_s",
    ("dispatch_api", "backoff_cap_s"): "api_backoff_cap_s",
    ("external_weather", "enabled"): "weather_enabled",
    ("external_weather", "base_url"): "weather_base_url",
    ("external_weather", "latitude"): "weather_latitude",
    ("external_weather", "longitude"): "weather_longitude",
    ("external_weather", "rain_threshold_mm"): "weather_rain_threshold_mm",
    ("external_weather", "timeout_s"): "weather_timeout_s",
    ("external_weather", "max_retries"): "weather_max_retries",
    ("early_warning", "grace_minutes_grid"): "ew_grace_minutes_grid",
    ("early_warning", "min_precision"): "ew_min_precision",
    ("early_warning", "train_until_day"): "ew_train_until_day",
    ("eta_calibration", "padding_grid_min"): "eta_padding_grid_min",
    ("fairness", "min_orders_restaurant"): "fair_min_orders_restaurant",
    ("fairness", "min_orders_driver"): "fair_min_orders_driver",
    ("fairness", "confidence"): "fair_confidence",
    ("impact", "prevented_share_scenarios"): "impact_prevented_share_scenarios",
    ("monitoring", "kpi_drift_alert_pp"): "kpi_drift_alert_pp",
}


class ConfigError(ValueError):
    """The policy file is malformed or contains an unknown key."""


def load_config(path: Path | str | None = None, **overrides: Any) -> PipelineConfig:
    """Build a PipelineConfig from ``config/pipeline.yaml`` (if given) plus explicit overrides.

    Unknown sections/keys are rejected loudly: a typo in a business threshold must
    never silently fall back to a default.
    """
    values: dict[str, Any] = {}
    if path is not None:
        import yaml
        p = Path(path)
        if not p.exists():
            raise ConfigError(f"config file not found: {p}")
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ConfigError(f"{p}: top level must be a mapping of sections")
        known_sections = {s for s, _ in YAML_MAP}
        for section, body in raw.items():
            if section not in known_sections:
                raise ConfigError(f"{p}: unknown section '{section}' (known: {sorted(known_sections)})")
            if not isinstance(body, dict):
                raise ConfigError(f"{p}: section '{section}' must be a mapping")
            for key, value in body.items():
                attr = YAML_MAP.get((section, key))
                if attr is None:
                    raise ConfigError(f"{p}: unknown key '{section}.{key}'")
                values[attr] = value
        values["config_file"] = str(p)
    valid = {f.name for f in fields(PipelineConfig)}
    for k, v in overrides.items():
        if k not in valid:
            raise ConfigError(f"unknown config override '{k}'")
        if v is not None:
            values[k] = v
    return PipelineConfig(**values)

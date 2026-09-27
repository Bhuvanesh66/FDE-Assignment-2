"""Schema contract: required columns stop the run, optional ones warn, unknown ones are recorded."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .ingest.file_source import SourceSchemaError

DEFAULT_CONTRACT = {
    "sql": {
        "orders": {"required": ["order_id", "customer_id", "restaurant_id", "driver_id", "created_at", "promised_eta", "pickup_at", "actual_delivery_at", "final_status"],
                   "optional": ["city", "distance_km_estimate", "traffic_bucket", "weather_bucket"]},
        "restaurants": {"required": ["restaurant_id"], "optional": ["restaurant_name", "cuisine", "lat", "lon", "manual_status_updates"]},
        "drivers": {"required": ["driver_id"], "optional": ["rating", "vehicle_type", "experience_months"]},
        "customers": {"required": ["customer_id"], "optional": ["lat", "lon"]},
    },
    "files": {
        "support_tickets.csv": {"required": ["ticket_id", "order_id", "created_at", "category"], "optional": ["customer_message"]},
        "restaurant_status.csv": {"required": ["order_id", "restaurant_id", "status", "last_updated_at"], "optional": []},
        "customer_app_actions.csv": {"required": ["action_id", "order_id", "customer_id", "action_type", "action_at"], "optional": ["channel"]},
        "order_interventions.csv": {"required": ["intervention_id", "order_id", "intervention_type", "intervention_at", "initiated_by"], "optional": ["reason"]},
        "order_outcomes.csv": {"required": ["order_id", "late_flag", "delay_min"], "optional": ["final_status_norm", "delivered_flag", "outcome_bucket"]},
    },
    "api": {"dispatch": {"required": ["order_id", "driver_id", "assigned_at", "dispatch_status"],
                         "optional": ["original_driver_id", "reassigned_at", "estimated_pickup_at", "current_delivery_eta", "eta_model_version"]}},
}


@dataclass
class ContractResult:
    source: str
    kind: str
    status: str = "PASS"                 # PASS | WARN | FAIL
    missing_required: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)
    uncontracted: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def load_contract(path: Path | None) -> dict:
    if path is None or not Path(path).exists():
        return DEFAULT_CONTRACT
    import yaml
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    merged = {k: dict(v) for k, v in DEFAULT_CONTRACT.items()}
    for kind, body in data.items():
        merged.setdefault(kind, {}).update(body or {})
    return merged


def required_columns(contract: dict, kind: str, source: str, fallback: list[str]) -> list[str]:
    return list(contract.get(kind, {}).get(source, {}).get("required", fallback))


def check(df: pd.DataFrame, contract: dict, kind: str, source: str, stop_on_missing: bool = True) -> ContractResult:
    spec = contract.get(kind, {}).get(source)
    res = ContractResult(source=source, kind=kind)
    if spec is None:
        res.status = "WARN"
        res.uncontracted = [str(c) for c in df.columns]
        return res
    cols = {str(c).strip().lower() for c in df.columns}
    req, opt = spec.get("required", []), spec.get("optional", [])
    res.missing_required = [c for c in req if c not in cols]
    res.missing_optional = [c for c in opt if c not in cols]
    res.uncontracted = sorted(cols - set(req) - set(opt))
    if res.missing_required:
        res.status = "FAIL"
        if stop_on_missing:
            raise SourceSchemaError(f"[{kind}:{source}] schema drift - required columns missing: {res.missing_required}")
    elif res.missing_optional or res.uncontracted:
        res.status = "WARN"
    return res

"""Run the SQL metric layer on the modelled warehouse and prove it agrees with the pandas metrics."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

VIEWS = ["v_m1_late_rate", "v_m3_pre_pickup_share", "v_m4_support_contact", "v_m5_intervention", "v_late_rate_by_restaurant"]


def run_views(db_path: Path, sql_file: Path) -> dict[str, pd.DataFrame]:
    con = sqlite3.connect(db_path)
    try:
        con.executescript(Path(sql_file).read_text(encoding="utf-8"))
        return {v: pd.read_sql_query(f"SELECT * FROM {v}", con) for v in VIEWS}
    finally:
        con.close()


def compare(views: dict[str, pd.DataFrame], metrics: pd.DataFrame) -> tuple[list[dict], pd.DataFrame]:
    m = metrics.set_index("metric_id")

    def num(mid, col):
        try:
            v = m.loc[mid, col]
            return None if pd.isna(v) else float(v)
        except KeyError:
            return None
    v1 = views["v_m1_late_rate"].iloc[0]
    v3 = views["v_m3_pre_pickup_share"].iloc[0]
    v4 = views["v_m4_support_contact"].set_index("outcome")
    v5 = views["v_m5_intervention"].set_index("grp")
    rows = [
        ("M1 late orders", num("M1", "numerator"), float(v1["late_orders"] or 0)),
        ("M1 validated population", num("M1", "denominator"), float(v1["validated_population"] or 0)),
        ("M3 share before pickup %", num("M3", "value"), None if pd.isna(v3["share_before_pickup_pct"]) else float(v3["share_before_pickup_pct"])),
        ("M4 late orders with support contact", num("M4", "numerator"), float(v4.loc["late", "orders_with_support_contact"]) if "late" in v4.index else 0.0),
        ("M4 late orders", num("M4", "denominator"), float(v4.loc["late", "orders"]) if "late" in v4.index else 0.0),
        ("M5 orders with intervention", num("M5", "numerator"), float(v5.loc["with_intervention", "orders"]) if "with_intervention" in v5.index else 0.0),
    ]
    table = pd.DataFrame(rows, columns=["quantity", "pandas", "sql"])
    table["agrees"] = [(a is None and b is None) or (a is not None and b is not None and abs(a - b) < 0.011) or (a is None and b == 0.0)
                       for a, b in zip(table["pandas"], table["sql"])]
    status = "PASS" if table["agrees"].all() else "FAIL"
    check = {"check": "SQL metric layer (sql/40_metric_views.sql) == pandas metrics", "status": status,
             "evidence": "; ".join(f"{r.quantity}: pandas={r.pandas} sql={r.sql}" for r in table.itertuples() if not r.agrees) or f"{len(table)} quantities agree"}
    return [check], table

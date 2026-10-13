"""IPPU-specific completeness, acquisition and historical-coverage products."""
from __future__ import annotations

import os

from pkinv.paths import DATA
from pkinv.sectors.ippu import schemas
from pkinv.assets import asset_path


def matrix(data_dir=DATA):
    path = asset_path(data_dir, "activity", "ippu", "master_data_gap_matrix.csv")
    return schemas.validate_completeness(schemas.read_csv(path))


def request_rows(data_dir=DATA):
    rows = []
    for row in matrix(data_dir):
        if row["notation_key_2024"] != "NE":
            continue
        rows.append({
            "ipcc_code": row["ipcc_code"], "category": row["category"],
            "materiality": row["materiality"], "request_recipient": row["request_recipient"],
            "requested_information": row["next_action"],
            "current_public_evidence": row["public_source"],
        })
    return rows


def historical_coverage(activity_rows, first_year=1990, last_year=2024):
    output = []
    for year in range(first_year, last_year + 1):
        rows = [r for r in activity_rows if int(r["period_end_year"]) == year]
        output.append({
            "year": year, "activity_control_count": len(rows),
            "model_ready_estimate_count": sum(r["status"] == "estimate" for r in rows),
            "source_tiers": ";".join(sorted({r["data_tier"] for r in rows})),
            "coverage_status": ("activity controls present" if rows else
                                "no public activity loaded; no silent interpolation"),
        })
    return output

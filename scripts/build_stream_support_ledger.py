#!/usr/bin/env python3
"""THE ATOMIC STREAM-TO-SUPPORT LEDGER (rc47 Wave 7) - the audit's named deliverable.

One product at grain (period_id, source_stream_id): every stream-year's MASS and its
SPATIAL SUPPORT in one row, rectangular over the registered stream x core-period panel with a
typed absence key - the three files a reader used to join by hand (atomic mass, weight
registry, fallback ledger) joined once, here, with the join's completeness pinned by test.

Columns beyond the join:
  located_share     1 - the stream-year's province-scope fallback share: the measured
                    fraction of the year's mass on the stream's own support (post-Waves
                    2-5 this is honest for every construction - the renormalisers and
                    silent re-seats all price their remainders now)
  fallback_Mt       mass the year placed on a fallback surface, from the priced events
  adm1_retained_Mt  mass retained at ADM1 (the unallocated ledger's stream-years)
  monthly_support   the reference has a published GHG monthly raster and ADM tables;
                    other periods have monthly administrative allocations and annual
                    rasters, with their temporal/spatial evidence carried separately.
                    This GHG ledger does not describe the separate four-configuration
                    air annual/monthly cube family.

Usage:  python3 scripts/build_stream_support_ledger.py [--check]
Writes: outputs/pakemis_stream_support_ledger.csv
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.core.io import read_rows, write_or_check  # noqa: E402
from pkinv.paths import OUTPUTS  # noqa: E402

OUT = asset_path(OUTPUTS, "pakemis_stream_support_ledger.csv")
REFERENCE = "FY2023-24"
MONTHLY_ADMINISTRATIVE = ("monthly_administrative_allocation; "
                          "no_published_ghg_monthly_raster")
FIELDS = ("period_id", "source_stream_id", "module", "gas", "status",
          "emissions_Gg", "co2e_Mt_AR5",
          "geometry_id", "surface", "district_panel", "spatial_view",
          "within_province_placement", "spatial_time_basis", "weight_period",
          "substituted_share", "located_share", "fallback_Mt", "adm1_retained_Mt",
          "evidence_grade", "pattern_hash", "temporal_operator", "evidence_role",
          "validation_ids", "monthly_support", "basis")


def _f(x):
    return float(x) if x not in ("", None) else 0.0


def build():
    weights = read_rows(asset_path(OUTPUTS, "pakemis_spatial_weights_by_year.csv"))
    surfaces = {(r["period_id"], r["source_stream_id"]): r for r in read_rows(
        asset_path(OUTPUTS, "pakemis_grid_stream_surfaces_by_year.csv"))}
    mass = defaultdict(lambda: [0.0, 0.0])
    for r in read_rows(asset_path(OUTPUTS, "pakemis_atomic_annual.csv")):
        m = mass[(r["period_id"], r["source_stream_id"])]
        m[0] += _f(r.get("emission_native_mass"))
        m[1] += _f(r.get("co2e_Mt_AR5"))
    fallback = defaultdict(float)
    for r in read_rows(asset_path(OUTPUTS, "pakemis_grid_fallbacks_by_year.csv")):
        if r["scope"] == "province":
            fallback[(r["period_id"], r["source_stream_id"])] += _f(r["affected_Mt_AR5"])
    retained = defaultdict(float)
    for r in read_rows(asset_path(OUTPUTS, "pakemis_spatial_unallocated_by_year.csv")):
        retained[(r["period_id"], r["source_stream_id"])] += _f(r["co2e_Mt_AR5"])
    fb_share = defaultdict(float)
    for r in read_rows(asset_path(OUTPUTS, "pakemis_grid_fallbacks_by_year.csv")):
        if r["scope"] == "province":
            fb_share[(r["period_id"], r["source_stream_id"])] += _f(r["weight_share"])

    rows = []
    for w in weights:
        key = (w["period_id"], w["source_stream_id"])
        surf = surfaces.get(key, {})
        present = w["spatial_time_basis"] != "not_present"
        m_gg, m_mt = mass.get(key, (0.0, 0.0))
        share_fb = min(1.0, fb_share.get(key, 0.0))
        rows.append({
            "period_id": w["period_id"], "source_stream_id": w["source_stream_id"],
            "module": w["module"], "gas": w["gas"],
            "status": "present" if present else "not_present",
            "emissions_Gg": "%.6f" % m_gg if present else "",
            "co2e_Mt_AR5": "%.8f" % m_mt if present else "",
            "geometry_id": surf.get("geometry_id", ""),
            "surface": w["surface"], "district_panel": w["district_panel"],
            "spatial_view": w["spatial_view"],
            "within_province_placement": surf.get("within_province_placement", ""),
            "spatial_time_basis": w["spatial_time_basis"],
            "weight_period": w["weight_period"],
            "substituted_share": w["substituted_share"],
            "located_share": ("%.6f" % (1.0 - share_fb)) if present and
                             w["spatial_time_basis"] != "unallocated" else "",
            "fallback_Mt": "%.8f" % fallback.get(key, 0.0) if present else "",
            "adm1_retained_Mt": "%.8f" % retained.get(key, 0.0) if present else "",
            "evidence_grade": w["evidence_grade"],
            "pattern_hash": w["pattern_hash"],
            "temporal_operator": w["temporal_operator"],
            "evidence_role": w["evidence_role"],
            "validation_ids": w["validation_ids"],
            "monthly_support": ("gridded_monthly" if w["period_id"] == REFERENCE
                                else MONTHLY_ADMINISTRATIVE) if present else "",
            "basis": w["basis"],
        })
    rows.sort(key=lambda r: (r["period_id"], r["source_stream_id"]))
    banner = [
        "THE ATOMIC STREAM-TO-SUPPORT LEDGER (rc47 Wave 7). One row per (period,",
        "stream): the mass, the support that placed it, the measured located share,",
        "the priced fallback and ADM1-retained masses, and actual GHG monthly support",
        "stated per row. Rectangular over the full stream x period panel; a stream-year",
        "with nothing to place carries status=not_present rather than silence.",
        "Sources: pakemis_atomic_annual + pakemis_spatial_weights_by_year +",
        "pakemis_grid_stream_surfaces_by_year + the fallback and unallocated ledgers.",
        "This is the S_TAN GHG stream ledger. All core periods have monthly administrative",
        "allocations; only the detailed reference has a published GHG monthly raster.",
        "Separate air annual/monthly cubes carry all four configurations and their own",
        "source/process coverage and allocation evidence, not the GHG stream coverage.",
    ]
    check = "--check" in sys.argv
    write_or_check(OUT, list(FIELDS), rows, check=check, banner=banner,
                   lineterminator="\n")
    n_present = sum(1 for r in rows if r["status"] == "present")
    print("stream-support ledger: %d rows (%d present, %d not_present)"
          % (len(rows), n_present, len(rows) - n_present))


if __name__ == "__main__":
    build()

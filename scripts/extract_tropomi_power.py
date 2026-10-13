#!/usr/bin/env python3
"""Extract TROPOMI NO2 and SO2 enhancements over Pakistan's power plants.

THE CHANNEL THIS OPENS. Every validation the power sector carries - the CRT, EDGAR,
Climate TRACE, the heat-rate channels - ultimately passes through somebody's reporting
chain. Sentinel-5P does not: it measures trace-gas columns from orbit, daily, and NO2's
hours-scale lifetime keeps the signal near its source. This script turns the TROPOMI
archive on the external SSD into a small committed extraction that the diagnostic module,
the tests and CI can use WITHOUT the SSD.

THE ARCHIVE. /Volumes/Extreme SSD/grid/pakistan/tropomi holds a daily 0.1-degree feature
grid for Pakistan, 2020-01-01 onward: per cell, per species, the median column with a
QA-pass fraction (upstream QA 0.75, from GEE's COPERNICUS/S5P/OFFL/L3 daily composites).
It is the product of the user's own Estimation pipeline; provenance and the collection
names live in that pipeline's download_tropomi.py.

THE METHOD, chosen for honesty over sophistication. Per source, per day:

    enhancement = mean(cells within 0.15 deg) - median(annulus 0.3-0.7 deg)

The same-day annulus median removes the regional background including its weather; what
it cannot do is follow the plume, so wind smears signal INTO the annulus and biases
enhancements LOW - conservative for every detection claim built on them. Complexes closer
than the grid can separate are extracted as one source and labelled mixed-attribution:
the four Thar mine-mouth plants, the Hub site (Hubco RFO + China Power Hub coal), and the
Port Qasim area (Port Qasim EPC + Lucky + K-Electric's Bin Qasim - additionally inside
Karachi's plume, so only within-source time contrasts are meaningful there).

THE DATA TRAP THIS SCRIPT EXISTS TO FILTER. Some archive days carry spatially-clustered
EXACT-ZERO fills with perfect QA (n_pixels 9, qa_pass_fraction 1.0) that no flag column
identifies - 2.6 percent of cells on affected days. A zero column through a power plant
is not a measurement. Cells with median == 0.0 exactly are dropped, and the filter is
part of this script's contract, documented here and pinned by the tests.

Usage:  python3 scripts/extract_tropomi_power.py
Needs:  the external SSD mounted at /Volumes/Extreme SSD (fails loudly otherwise)
Writes: data/activity/power/tropomi_no2_plants.csv   (committed, ~2.5 MB)
        outputs/power_tropomi_extraction_manifest.json
"""

from pkinv.assets import asset_path
import csv
import hashlib
import json
import os
import sys
from datetime import date

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRID = "/Volumes/Extreme SSD/grid/pakistan/tropomi"
OUT_CSV = asset_path(ROOT, "data", "activity", "power", "tropomi_no2_plants.csv")
OUT_MANIFEST = asset_path(ROOT, "outputs", "power_tropomi_extraction_manifest.json")

R_SRC = 0.15          # degrees: source disk (6-8 cells at 0.1 deg)
R_IN, R_OUT = 0.3, 0.7  # degrees: background annulus (~125 cells)
QA_MIN = 0.5          # cell-level qa_pass_fraction floor (upstream already applied 0.75)
SPECIES = ("no2", "so2")

# Coordinates from sources/Power Plants/climatetrace_power_assets_PAK.csv; complexes the
# 0.1-degree grid cannot separate are one source each, attribution stated.
SOURCES = {
    "sahiwal":            (30.7142, 73.2380, "Huaneng Shandong Ruyi (Sahiwal), isolated"),
    "thar_cluster":       (24.7700, 70.3500, "Engro + Thar Coal Block-I + Thar Energy + "
                                             "ThalNova, mine-mouth cluster, mixed"),
    "hub_complex":        (24.9147, 66.6888, "Hubco RFO + China Power Hub coal, mixed"),
    "port_qasim_complex": (24.8000, 67.3200, "Port Qasim EPC + Lucky + Bin Qasim (K-E), "
                                             "mixed AND Karachi-confounded"),
    "uch":                (28.5827, 68.1762, "Uch + Uch-II, isolated gas"),
    "guddu":              (28.4249, 69.7009, "TPS Guddu blocks, isolated gas"),
    "balloki":            (31.0370, 73.9267, "NPPMCL Balloki, RLNG"),
    "bhikki":             (31.6037, 73.9046, "QATPL Bhikki, RLNG"),
    "hbs":                (31.1262, 72.1913, "NPPMCL Haveli Bahadur Shah, RLNG"),
}


def main():
    if not os.path.isdir(GRID):
        sys.exit("SSD not mounted: %s absent. Mount the Extreme SSD and rerun." % GRID)
    days = sorted(d for d in os.listdir(GRID) if d.startswith("date="))
    if len(days) < 2200:
        sys.exit("only %d date dirs under %s - archive incomplete, refusing to extract"
                 % (len(days), GRID))

    cols = ["lat", "lon"] + ["%s_%s" % (sp, f) for sp in SPECIES
                             for f in ("median", "qa_pass_fraction")]

    first = pd.read_parquet(asset_path(GRID, days[0], "part-000.parquet"),
                            columns=["lat", "lon"])
    lat0 = first["lat"].to_numpy()
    lon0 = first["lon"].to_numpy()
    grid_checksum = float(lat0.sum() + lon0.sum())

    masks = {}
    for name, (plat, plon, _note) in SOURCES.items():
        d = np.sqrt((lat0 - plat) ** 2 + (lon0 - plon) ** 2)
        masks[name] = (d <= R_SRC, (d >= R_IN) & (d <= R_OUT))

    rows = []
    for dd in days:
        day = dd.split("=", 1)[1]
        df = pd.read_parquet(asset_path(GRID, dd, "part-000.parquet"), columns=cols)
        if abs(float(df["lat"].sum() + df["lon"].sum()) - grid_checksum) > 1e-6:
            sys.exit("grid layout changed on %s - masks invalid, re-audit" % day)
        for name in SOURCES:
            src_m, bkg_m = masks[name]
            row = {"source": name, "date": day}
            for sp in SPECIES:
                v = df["%s_median" % sp].to_numpy()
                q = df["%s_qa_pass_fraction" % sp].to_numpy()
                # THE ZERO-FILL FILTER: exact zeros are fills, not measurements.
                ok = np.isfinite(v) & (v != 0.0) & np.isfinite(q) & (q >= QA_MIN)
                sv, bv = v[src_m & ok], v[bkg_m & ok]
                row["%s_src_mean" % sp] = float(sv.mean()) if len(sv) else ""
                row["%s_src_cells" % sp] = len(sv)
                row["%s_bkg_median" % sp] = float(np.median(bv)) if len(bv) else ""
                row["%s_bkg_cells" % sp] = len(bv)
                row["%s_enhancement" % sp] = (float(sv.mean() - np.median(bv))
                                              if len(sv) and len(bv) else "")
                row["%s_src_qa_mean" % sp] = (float(q[src_m & ok].mean())
                                              if (src_m & ok).any() else "")
            rows.append(row)

    fields = ["source", "date"]
    for sp in SPECIES:
        fields += ["%s_src_mean" % sp, "%s_src_cells" % sp, "%s_bkg_median" % sp,
                   "%s_bkg_cells" % sp, "%s_enhancement" % sp, "%s_src_qa_mean" % sp]
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            for k, v in list(r.items()):
                if isinstance(v, float):
                    r[k] = "%.6g" % v
            w.writerow(r)

    h = hashlib.sha256(open(OUT_CSV, "rb").read()).hexdigest()
    manifest = {
        "generated": date.today().isoformat(),
        "archive": GRID, "days": len(days),
        "first_day": days[0].split("=")[1], "last_day": days[-1].split("=")[1],
        "species": list(SPECIES),
        "method": {"r_src_deg": R_SRC, "annulus_deg": [R_IN, R_OUT],
                   "qa_min": QA_MIN, "zero_fill_filtered": True,
                   "source_stat": "mean", "background_stat": "median"},
        "sources": {k: {"lat": v[0], "lon": v[1], "note": v[2]}
                    for k, v in SOURCES.items()},
        "provenance": "GEE COPERNICUS/S5P/OFFL/L3 daily composites, 0.1 deg feature grid "
                      "built by the user's Estimation pipeline (qa 0.75 upstream)",
        "csv_rows": len(rows), "csv_sha256": h,
    }
    os.makedirs(os.path.dirname(OUT_MANIFEST), exist_ok=True)
    json.dump(manifest, open(OUT_MANIFEST, "w"), indent=2)
    print("wrote %s (%d rows, sha256 %s...)" % (os.path.relpath(OUT_CSV, ROOT),
                                                len(rows), h[:16]))
    print("wrote %s" % os.path.relpath(OUT_MANIFEST, ROOT))


if __name__ == "__main__":
    main()

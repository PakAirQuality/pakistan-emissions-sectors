"""The rice geography crosscheck: the declared surface measured against an own-year one.

WHY (Wave 5). The rice proxy contract was fulfilled this wave - MapSPAM 2020 physical
area landed as data/gis/manual/spam_rice.tif and the cropland fallback class was
deleted fail-closed - but SPAM is a 2020-vintage 5-arc-min model surface, and the
repository's own period-matching principle (rc13, rc24) says a vintage mismatch is a
measurable property, not a footnote. The instrument is held: GCD-Rice, a 30 m
classified paddy extent for Pakistan's OWN reporting-period year
(data/gis/manual/gcd_rice_2023.tif; ScienceDB doi:10.57760/sciencedb.21665, ~88.9%
overall accuracy on 258k validation samples). This module aggregates the 30 m binary
to the inventory grid and publishes, per ADM2 unit, the WITHIN-PROVINCE share each
surface would allocate - the operative quantity, because province marginals are
controlled and only below-province placement is the proxy's to decide.

WHAT IT IS NOT. Not a surface switch: the declared proxy stays SPAM, and the
disagreement measured here is priced separately as the ADM2 bracket alternative
(pakemis_spatial_brackets_adm2.csv, agriculture_rice_gcd2023_adm2), so a reader can
see what the own-year 30 m product would move before anyone moves it. Geography
only, never magnitude - the same licence GCD-Rice carries in the companion
repository that built it.

Usage:  python3 -m pkinv.report.rice_geography_crosscheck
Writes: outputs/pakemis_rice_geography_crosscheck.csv
"""
from __future__ import annotations

from pkinv.assets import asset_path

import os

import numpy as np

from pkinv.paths import OUTPUTS
from pkinv.core.io import write_table

OUT = asset_path(OUTPUTS, "pakemis_rice_geography_crosscheck.csv")
GCD_TIF = asset_path("data", "gis", "manual", "gcd_rice_2023.tif")

# A unit "disagrees" when the two surfaces differ by more than this many percentage
# points of its own province's rice mass - a declared reading threshold, stated on
# every row that uses it.
DISAGREE_PP = 2.0

# NAMES BESIDE THE INDICES. The first version shipped only the raster indices, so the
# reader of a validation table meant for an external reviewer got "province_id 2" where
# the answer is "Khyber Pakhtunkhwa". The indices stay, because they are what the rasters
# key on and a join needs them; the names are added, because a published table is read by
# people.
FIELDS = ("shape_id", "district", "province_id", "province",
          "spam_share_pct", "gcd_share_pct",
          "cropland_share_pct", "spam_gcd_gap_pp", "verdict", "note")


def gcd_fraction(grid):
    """The 30 m paddy band aggregated to the inventory grid, read through the
    proxy cache (data/gis/proxy_gcd_rice_267x340.npy; the raster only on a cache
    miss - rc41, so a tree that holds the cached grid but not the 30 MB raster
    still runs the crosscheck). The aggregation lives in
    core.gis.proxies.build_gcd_rice_proxy."""
    from pkinv.core.gis.proxies import get_proxy
    return get_proxy("gcd_rice", grid)[0]


def _province_name(pid):
    """The inventory province an index names. PROVINCES is the order the raster is built on."""
    from pkinv.core.geography import PROVINCES
    return PROVINCES[pid] if 0 <= pid < len(PROVINCES) else ""


def _district_name(grid, sid):
    """The ADM2 unit a district index names, or "" where the grid carries no name for it."""
    return grid.districts[sid] if 0 <= sid < len(grid.districts) else ""


def _within_province_shares(surface, grid):
    """{(province_id, shape_id): share of the province's surface mass}."""
    out = {}
    prov_tot = {}
    for pid in np.unique(grid.province_id):
        if pid < 0:
            continue
        prov_tot[int(pid)] = float(surface[grid.province_id == pid].sum())
    for sid in np.unique(grid.district_id):
        if sid < 0:
            continue
        mask = grid.district_id == sid
        pid = int(grid.province_id[mask][0])
        tot = prov_tot.get(pid, 0.0)
        val = float(surface[mask].sum())
        out[(pid, int(sid))] = val / tot if tot > 0 else 0.0
    return out


def build(grid=None):
    from pkinv.core.gis.grid import build_grid
    from pkinv.core.gis.proxies import build_manual_proxy, get_proxy
    grid = grid or build_grid()

    spam = build_manual_proxy(grid, "spam_rice.tif")
    if spam is None:
        raise SystemExit("spam_rice.tif absent - the crosscheck has nothing to "
                         "check; the fallback allow-list no longer permits "
                         "building without it")
    spam = spam[0]
    try:
        gcd = gcd_fraction(grid)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc))
    crop, _ = get_proxy("cropland", grid)

    s_spam = _within_province_shares(spam, grid)
    s_gcd = _within_province_shares(gcd, grid)
    s_crop = _within_province_shares(crop, grid)

    rows = []
    for (pid, sid) in sorted(s_spam):
        a = s_spam[(pid, sid)] * 100.0
        b = s_gcd.get((pid, sid), 0.0) * 100.0
        c = s_crop.get((pid, sid), 0.0) * 100.0
        gap = a - b
        rows.append({
            "shape_id": sid, "district": _district_name(grid, sid),
            "province_id": pid, "province": _province_name(pid),
            "spam_share_pct": round(a, 4), "gcd_share_pct": round(b, 4),
            "cropland_share_pct": round(c, 4),
            "spam_gcd_gap_pp": round(gap, 4),
            "verdict": ("agree" if abs(gap) <= DISAGREE_PP else "disagree"),
            "note": ("threshold %.1f pp of the unit's own province rice mass "
                     "(declared reading line)" % DISAGREE_PP)})
    l1 = {}
    for (pid, sid), v in s_spam.items():
        l1[pid] = l1.get(pid, 0.0) + abs(v - s_gcd.get((pid, sid), 0.0))
    for pid in sorted(l1):
        rows.append({
            "shape_id": "PROVINCE_L1", "district": "",
            "province_id": pid, "province": _province_name(pid),
            "spam_share_pct": "", "gcd_share_pct": "", "cropland_share_pct": "",
            "spam_gcd_gap_pp": round(l1[pid] * 100.0 / 2.0, 4),
            "verdict": "summary",
            "note": "half the L1 distance between the two surfaces' "
                    "within-province ADM2 shares - the fraction of this "
                    "province's rice mass the own-year 30 m product would "
                    "place in different districts"})
    return rows


def main():
    rows = build()
    write_table(OUT, list(FIELDS), rows, banner=('# The rice surface measured against the own-year instrument: MapSPAM 2020 V2r2', '# (the declared proxy) vs GCD-Rice 2023 (30 m classified paddy, doi:10.57760/sciencedb.21665,', '# ~88.9% accuracy), as WITHIN-PROVINCE ADM2 shares - the operative allocation quantity.', '# Geography only, never magnitude. See rice_geography_crosscheck.py.',), lineterminator="\n")
    units = [r for r in rows if r["verdict"] != "summary"]
    disagree = sum(1 for r in units if r["verdict"] == "disagree")
    print("rice geography crosscheck -> %s" % OUT)
    print("  %d ADM2 units: %d within %.1f pp, %d disagree; province L1/2: %s"
          % (len(units), len(units) - disagree, DISAGREE_PP, disagree,
             ", ".join("%s %.1f%%" % (r["province_id"], r["spam_gcd_gap_pp"])
                       for r in rows if r["verdict"] == "summary")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

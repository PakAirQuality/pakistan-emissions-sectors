"""GLW vs PBS at DISTRICT grain: the raw-proxy validation the tree never had (rc32).

The livestock validation on file is province-rank-only and says so; both panels
needed for the district comparison have been held all along
(data/activity/livestock_district_2024.csv - the PBS 2024 census; the GLW-4
EF-weighted raster) and the missing piece was an honest way to sum a raster by
district, which the fractional intersection table now provides.

WHAT THIS VALIDATES, EXACTLY. The census is the ALLOCATOR for the livestock
streams (district shares come from it, GLW is the fallback for 15 unmatched
districts), so census-vs-GLW here is NOT a check of the shipped allocation - it
is a check of the GLW PROXY itself, the surface that (a) fills those fallback
districts and (b) carries the within-district placement everywhere. A district
where the two disagree badly is a district where the fallback would be wrong
and the within-district placement is least trustworthy.

Usage:  python3 scripts/validate_glw_districts.py
Writes: outputs/eval/validation/livestock_district_validation.csv
"""

from pkinv.assets import asset_path
import csv
import os

import numpy as np

from pkinv.core.gis import cube as cube_core
from pkinv.core.gis.grid import build_grid
from pkinv.paths import DATA, OUTPUTS, ROOT

OUT = asset_path(OUTPUTS, "eval", "validation",
                   "livestock_district_validation.csv")


def main():
    grid = build_grid()
    glw = np.load(asset_path(DATA, "gis", "proxy_glw_livestock_267x340.npy"))
    packed = cube_core._fraction_matrix(grid)
    flat = glw.ravel()
    glw_by_idx = {i: float((flat[ix] * fr).sum())
                  for i, (ix, fr) in packed.items() if i != -1}
    glw_by_name = {grid.districts[i]: v for i, v in glw_by_idx.items()}
    glw_total = sum(glw_by_name.values())

    census = {}
    with open(asset_path(DATA, "activity", "livestock_district_2024.csv"),
              newline="", encoding="utf-8") as f:
        for r in csv.DictReader(line for line in f if not line.startswith("#")):
            name = (r.get("district") or r.get("adm2_name") or "")
            # the census suffixes " District"; the grid's shapeNames do not
            name = name.removesuffix(" District").strip()
            heads = sum(float(r[c] or 0) for c in r
                        if c and c not in ("district", "adm2_name", "province")
                        and (r[c] or "").replace(".", "").isdigit())
            census[name] = census.get(name, 0.0) + heads
    census_total = sum(census.values())

    rows, both = [], []
    for name in sorted(set(glw_by_name) | set(census)):
        g = glw_by_name.get(name)
        c = census.get(name)
        g_share = g / glw_total if g is not None else None
        c_share = c / census_total if c is not None else None
        rows.append({
            "district": name,
            "glw_ef_weighted_share": ("%.6f" % g_share) if g_share is not None else "",
            "census_heads_share": ("%.6f" % c_share) if c_share is not None else "",
            "share_gap_pp": ("%.4f" % ((g_share - c_share) * 100)
                             if g_share is not None and c_share is not None else ""),
            "status": ("both" if g_share is not None and c_share is not None
                       else "glw_only" if g_share is not None else "census_only"),
        })
        if g_share is not None and c_share is not None:
            both.append((g_share, c_share))
    # Spearman by hand: ranks over the matched set
    def ranks(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        out = [0] * len(vals)
        for rank, i in enumerate(order):
            out[i] = rank
        return out
    if both:
        rg = ranks([b[0] for b in both])
        rc = ranks([b[1] for b in both])
        n = len(both)
        d2 = sum((a - b) ** 2 for a, b in zip(rg, rc))
        rho = 1 - 6 * d2 / (n * (n ** 2 - 1))
    else:
        rho = float("nan")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        f.write("# GLW-4 (EF-weighted) vs PBS 2024 census at DISTRICT grain, shares of\n"
                "# each panel's own total; the GLW side summed through the fractional\n"
                "# intersection table. Validates the PROXY (the fallback and the\n"
                "# within-district placement), never the shipped allocation, whose\n"
                "# district masses come from the census itself. Matched Spearman rho\n"
                "# %.4f over %d districts.\n" % (rho, len(both)))
        w = csv.DictWriter(f, fieldnames=["district", "glw_ef_weighted_share",
                                          "census_heads_share", "share_gap_pp",
                                          "status"])
        w.writeheader()
        w.writerows(rows)
    print("district livestock validation -> %s (%d rows; %d matched; "
          "Spearman rho %.4f)" % (OUT, len(rows), len(both), rho))


if __name__ == "__main__":
    main()

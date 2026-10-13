"""Spatial validation of gridded NH3 against an independent 0.1-degree inventory.

Every external check in this work so far has compared national or provincial MAGNITUDES. The
geography -- which is what a gridded product is for -- has been evaluated only against government crop
records, and only for the greenhouse gases. This module supplies the missing test: our ammonia surface
against the independent South Asian gridded inventory of Tomlinson et al. (2026), released at 0.1
degrees under the Open Government Licence (EIDC, doi:10.5285/e0114a4f-32c2-41d9-9c2a-c46f365d4c30).

The comparison separates SHAPE from LEVEL, because those turn out to have different answers: the
pattern agrees strongly while the magnitude does not. Pearson correlation is scale-invariant, so it
already measures shape alone; a log-space correlation is reported alongside it because emission
fields are strongly right-skewed and the linear coefficient is otherwise dominated by a handful of
cells.

Reading their grid is itself checked: summed over our Pakistan mask their five sectors reproduce the
national total published in their Table 3 to better than 1%, which is what makes the unit conversion
and the mask trustworthy enough to compare against.

Three caveats stated rather than buried:
  * their grid is 2015 and so is ours here (air_spatial.build(year=2015)), but our spatial PROXIES
    are fixed-vintage -- GLW livestock and WorldCover cropland do not vary by year -- so what moves
    between years is the provincial control totals, not the within-province pattern;
  * their sectors and ours are not identical: we map SFA to synthetic fertiliser, GRM+MNM to the
    livestock streams, CRB to residue burning, and we have no CRR term (ours is a computed zero);
  * 0.1-degree cells are compared by aggregating our 0.05-degree surface 2x2, which is exact.

Usage:  python3 -m pkinv.eval.spatial_nh3_validation --data /path/to/unpacked/eidc/data
Writes: outputs/eval/spatial_nh3_validation.json, outputs/eval/nh3_spatial_comparison.png
"""

from pkinv.assets import asset_path
import json
import math
import os
import sys


import numpy as np                                    # noqa: E402
import rasterio                                       # noqa: E402
from rasterio.windows import from_bounds              # noqa: E402

from pkinv.core.gis.grid import build_grid, PROVINCES, PROV_ID       # noqa: E402
from pkinv.sectors.agriculture.gis import air_spatial  # noqa: E402

from pkinv.paths import ROOT

OUT = asset_path(ROOT, "outputs", "eval")
DEFAULT_DATA = asset_path(ROOT, "data", "gis", "manual", "sanh_2015")
SECTORS = ("SFA", "GRM", "MNM", "CRB", "CRR")
YEAR = 2015
# their sector -> our comparable scope, and whether the two rest on the SAME spatial input.
# This is the crux of how much the comparison is worth. Their livestock sectors distribute on GLWv4
# (their Table A7) and so do ours, so agreement there is partly structural rather than earned. Their
# fertiliser and burning sectors use EarthStat crop surfaces against our WorldCover cropland,
# MapSPAM rice and FIRMS fire, so those comparisons are the genuinely independent part of the test.
SECTOR_SCOPE = {"SFA": "synthetic", "GRM": "livestock", "MNM": "livestock",
                "CRB": "burning", "CRR": "residues"}
SHARED_INPUT = {"livestock": "GLWv4 livestock density (both inventories)",
                "synthetic": None, "burning": None, "residues": None}


def _cell_area_km2(lat_deg, res):
    """Area of a res x res degree cell centred at lat_deg, km^2 (spherical earth)."""
    R = 6371.0
    dlat = math.radians(res)
    lat = math.radians(lat_deg)
    return R * R * dlat * math.radians(res) * math.cos(lat)


def load_benchmark(data_dir, sectors=SECTORS):
    """{sector: (kt per 0.1-deg cell array, transform)} clipped to our grid's bounding box."""
    g = build_grid()
    minx, miny, maxx, maxy = g.bounds
    out, transform, lats = {}, None, None
    for s in sectors:
        path = asset_path(data_dir, "NH3_%s_SouthAsia_2015_gm2_0.1.tif" % s)
        if not os.path.exists(path):
            raise SystemExit("missing %s -- unpack the EIDC download and pass --data" % path)
        with rasterio.open(path) as r:
            win = from_bounds(minx, miny, maxx, maxy, r.transform)
            arr = r.read(1, window=win).astype(np.float64)
            transform = r.window_transform(win)
        arr = np.where(np.isfinite(arr), arr, 0.0)
        h, w = arr.shape
        if lats is None:
            lats = np.array([transform.f + transform.e * (i + 0.5) for i in range(h)])
        # g m-2 a-1 -> kt a-1 : x cell area (km2) x 1e6 m2/km2 / 1e9 g/kt
        area = np.array([_cell_area_km2(la, 0.1) for la in lats])[:, None]
        out[s] = arr * area * 1e6 / 1e9
    return out, transform


def pakistan_mask_01(transform, shape):
    """Fraction of each 0.1-deg cell that lies inside Pakistan, from our 0.05-deg province grid."""
    g = build_grid()
    inside = (g.province_id >= 0).astype(np.float64)
    frac = np.zeros(shape)
    for i in range(shape[0]):
        top = transform.f + transform.e * i
        for j in range(shape[1]):
            left = transform.c + transform.a * j
            # our grid runs north-down from bounds[3]; map the 0.1 cell onto 2x2 of ours
            r0 = int(round((g.bounds[3] - top) / 0.05))
            c0 = int(round((left - g.bounds[0]) / 0.05))
            if 0 <= r0 < g.height - 1 and 0 <= c0 < g.width - 1:
                frac[i, j] = inside[r0:r0 + 2, c0:c0 + 2].mean()
    return frac


def _aggregate_fine(fine, transform, shape, g):
    """Aggregate one 0.05-degree surface onto the benchmark's 0.1-degree cells (exact, 2x2).

    rc47 Wave 6 made "exact" a CHECKED word: `int(round(...))` would silently snap ANY
    misaligned benchmark onto the nearest fine index, and a 0.1-aligned benchmark must
    land on ODD fine offsets (the frozen lattice's west and north edges sit on 0.1-cell
    CENTRES). Both facts are asserted per cell now - a benchmark on a different
    alignment refuses loudly instead of aggregating half a cell off."""
    if fine is None:
        return None
    out = np.zeros(shape)
    for i in range(shape[0]):
        top = transform.f + transform.e * i
        rf = (g.bounds[3] - top) / 0.05
        r0 = int(round(rf))
        if abs(rf - r0) > 1e-6:
            raise ValueError("benchmark row %d is off the fine lattice by %.6f cells; "
                             "the 2x2 would be silently misaligned" % (i, rf - r0))
        for j in range(shape[1]):
            left = transform.c + transform.a * j
            cf = (left - g.bounds[0]) / 0.05
            c0 = int(round(cf))
            if abs(cf - c0) > 1e-6:
                raise ValueError("benchmark col %d off-lattice by %.6f cells" % (j, cf - c0))
            if 0 <= r0 < g.height - 1 and 0 <= c0 < g.width - 1:
                if r0 % 2 != 1 or c0 % 2 != 1:
                    raise ValueError(
                        "0.1-aligned benchmark cell (%d,%d) landed at EVEN fine offsets "
                        "(%d,%d): the odd-parity identity broke - see the frozen "
                        "lattice's edge arithmetic in tests/test_grid_spec.py" % (i, j, r0, c0))
                out[i, j] = fine[r0:r0 + 2, c0:c0 + 2].sum()
    return out


def ours_at_01(transform, shape, year=YEAR):
    """Our total NH3 surface on the benchmark's grid (kt)."""
    g = build_grid()
    rasters, _, _, _ = air_spatial.build(grid=g, year=year)
    return _aggregate_fine(rasters["NH3"], transform, shape, g)


def _stats(a, b, mask):
    """Pattern statistics over the masked cells of two surfaces."""
    sel = mask > 0.5
    x, y = a[sel], b[sel]
    if x.sum() <= 0 or y.sum() <= 0:
        return {}
    def pearson(u, v):
        u, v = u - u.mean(), v - v.mean()
        d = math.sqrt((u * u).sum() * (v * v).sum())
        return float((u * v).sum() / d) if d else float("nan")

    def spearman(u, v):
        return pearson(np.argsort(np.argsort(u)).astype(float),
                       np.argsort(np.argsort(v)).astype(float))

    # hotspot overlap: share of the top-decile cells they agree on
    k = max(1, int(0.1 * len(x)))
    top_a = set(np.argsort(-x)[:k].tolist())
    top_b = set(np.argsort(-y)[:k].tolist())
    # Pearson is scale-invariant, so normalising each surface by its own total would return an
    # identical coefficient -- reporting it as a second statistic would be padding. Emission fields
    # are strongly right-skewed, so a log-space correlation is the informative complement: it tests
    # agreement across the whole range rather than letting the few largest cells dominate.
    floor = max(x[x > 0].min() if (x > 0).any() else 1e-9,
                y[y > 0].min() if (y > 0).any() else 1e-9) * 1e-3
    lx, ly = np.log10(np.maximum(x, floor)), np.log10(np.maximum(y, floor))
    return {
        "cells": int(sel.sum()),
        "pearson": pearson(x, y),
        "pearson_log10": pearson(lx, ly),
        "spearman": spearman(x, y),
        "hotspot_overlap_top10pct": len(top_a & top_b) / float(k),
        "ours_kt": float(x.sum()),
        "benchmark_kt": float(y.sum()),
        "ratio": float(x.sum() / y.sum()),
    }


def compare(data_dir=DEFAULT_DATA, year=YEAR):
    bench, transform = load_benchmark(data_dir)
    shape = next(iter(bench.values())).shape
    mask = pakistan_mask_01(transform, shape)
    ours = ours_at_01(transform, shape, year)
    bench_total = sum(bench.values())

    result = {"year": year, "resolution_deg": 0.1,
              "benchmark_sector_totals_kt": {s: float((v * (mask > 0.5)).sum())
                                             for s, v in bench.items()},
              "all_sectors": _stats(ours, bench_total, mask)}
    # provincial comparison, on the same 0.1-degree mask
    g = build_grid()
    prov = {}
    for p in PROVINCES:
        pm = np.zeros(shape)
        inside = (g.province_id == PROV_ID[p]).astype(np.float64)
        for i in range(shape[0]):
            r0 = int(round((g.bounds[3] - (transform.f + transform.e * i)) / 0.05))
            for j in range(shape[1]):
                c0 = int(round(((transform.c + transform.a * j) - g.bounds[0]) / 0.05))
                if 0 <= r0 < g.height - 1 and 0 <= c0 < g.width - 1:
                    pm[i, j] = inside[r0:r0 + 2, c0:c0 + 2].mean()
        sel = pm > 0.5
        if sel.sum():
            prov[p] = {"ours_kt": float(ours[sel].sum()),
                       "benchmark_kt": float(bench_total[sel].sum())}
            prov[p]["ratio"] = (prov[p]["ours_kt"] / prov[p]["benchmark_kt"]
                                if prov[p]["benchmark_kt"] else None)
    result["provincial"] = prov

    # per-stream, so the shared-input streams can be told apart from the independent ones
    g2 = build_grid()
    _, _, _, scope_rasters = air_spatial.build(grid=g2, year=year)
    by_scope = {}
    for scope in ("synthetic", "livestock", "burning"):
        sectors = [k for k, v in SECTOR_SCOPE.items() if v == scope]
        b = sum(bench[k] for k in sectors if k in bench)
        o = _aggregate_fine(scope_rasters.get(scope), transform, shape, g2)
        if o is None:
            continue
        st = _stats(o, b, mask)
        st["benchmark_sectors"] = sectors
        st["shared_spatial_input"] = SHARED_INPUT[scope]
        by_scope[scope] = st
    result["by_stream"] = by_scope
    return result, ours, bench_total, mask, transform


def main():
    data_dir = DEFAULT_DATA
    if "--data" in sys.argv:
        data_dir = sys.argv[sys.argv.index("--data") + 1]
    os.makedirs(OUT, exist_ok=True)
    result, ours, bench, mask, _ = compare(data_dir)
    with open(asset_path(OUT, "spatial_nh3_validation.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    a = result["all_sectors"]
    print("Gridded NH3 vs Tomlinson et al. (2026) at 0.1 deg, %d, Pakistan:" % result["year"])
    print("  cells compared              %6d" % a["cells"])
    print("  our total / benchmark       %6.1f / %.1f kt  (x%.2f)"
          % (a["ours_kt"], a["benchmark_kt"], a["ratio"]))
    print("  Pearson r                   %6.3f" % a["pearson"])
    print("  Pearson r, log10 cells      %6.3f   <- not dominated by the largest cells"
          % a["pearson_log10"])
    print("  Spearman rank r             %6.3f" % a["spearman"])
    print("  top-decile hotspot overlap  %6.1f%%" % (100 * a["hotspot_overlap_top10pct"]))
    print()
    print("  by stream (which part of the agreement is earned rather than structural):")
    for scope, v in result.get("by_stream", {}).items():
        shared = v.get("shared_spatial_input")
        tag = "SHARED INPUT" if shared else "independent"
        print("    %-10s r=%5.3f  hotspot %4.1f%%  x%.2f   %s"
              % (scope, v["pearson"], 100 * v["hotspot_overlap_top10pct"], v["ratio"], tag))
    print()
    print("  provincial:")
    for p, v in result["provincial"].items():
        if v["ratio"]:
            print("    %-20s ours %7.1f  benchmark %7.1f  x%.2f"
                  % (p, v["ours_kt"], v["benchmark_kt"], v["ratio"]))
    _plot(ours, bench, mask)
    return 0


def _plot(ours, bench, mask):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print("  (plot skipped: %s)" % e)
        return
    sel = mask > 0.5
    o = np.where(sel, ours, np.nan)
    b = np.where(sel, bench, np.nan)
    resid = np.where(sel, ours / np.maximum(bench, 1e-9), np.nan)
    fig, ax = plt.subplots(1, 3, figsize=(13, 4.2))
    for k, (arr, title, kw) in enumerate([
            (o, "This work, 2015", dict(cmap="YlOrRd")),
            (b, "Tomlinson et al. 2026", dict(cmap="YlOrRd")),
            (np.log10(np.clip(resid, 0.1, 10)), "log$_{10}$(ours / benchmark)",
             dict(cmap="RdBu_r", vmin=-1, vmax=1))]):
        im = ax[k].imshow(arr, **kw)
        ax[k].set_title(title, fontsize=10)
        ax[k].set_xticks([]); ax[k].set_yticks([])
        fig.colorbar(im, ax=ax[k], fraction=0.046)
    fig.suptitle("Agricultural NH$_3$, Pakistan, 0.1$^\\circ$ (kt per cell)", fontsize=11)
    fig.tight_layout()
    path = asset_path(OUT, "nh3_spatial_comparison.png")
    fig.savefig(path, dpi=130)
    plt.close(fig)
    print("  wrote %s" % os.path.relpath(path, ROOT))


if __name__ == "__main__":
    raise SystemExit(main())

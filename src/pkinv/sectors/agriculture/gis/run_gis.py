"""Phase 4 - build gridded agricultural emission surfaces for Pakistan.

Allocates Phase-3 provincial control totals to a 0.05-degree national grid using
**category-specific proxies** (see CATEGORY_PROXY): GLW 4 livestock density for enteric +
manure, MapSPAM rice area for rice, NASA FIRMS/VIIRS fire for residue burning, and ESA
WorldCover cropland for managed soils + urea (also the universal fallback). MapSPAM and FIRMS
are optional drop-ins (data/gis/manual/); absent them, rice/burning fall back to cropland.
Every surface reconciles exactly to province/national control totals.

Usage:  python3 -m pkinv.sectors.agriculture.gis.run_gis
Writes: outputs/gis/*.tif, hotspot PNGs, grid_emissions_2024.csv, gis_report.md
"""

from pkinv.assets import asset_path
import collections
import csv
import os
import sys

import numpy as np


from pkinv.core.gis.grid import build_grid, cell_lonlat, PROVINCES, PROV_ID  # noqa: E402
from pkinv.core.gis.proxies import get_proxy, build_manual_proxy, build_firms_fire_proxy  # noqa: E402
from pkinv.core.gis.allocate import allocate, category_totals  # noqa: E402
from pkinv.core.gis.proxy_map import GIS_PROXY_FOR, gis_proxy  # noqa: E402
from pkinv.sectors.agriculture.downscale import provincial_matrix, provincial_rows, CATEGORIES  # noqa: E402
from pkinv.core.gis import render  # noqa: E402

from pkinv.paths import ROOT

OUT = asset_path(ROOT, "outputs", "gis")


def fire_title():
    """The fire figure's in-image title, derived from the fetched FIRMS artifact's
    own sidecar rather than a literal: the ninth review found the graphic still
    naming a season the data no longer covered, because a hardcoded title cannot
    notice a re-fetch. Falls back to the fetcher's default season key when the
    sidecar is absent (the figure is only drawn when the layer is present, so in
    practice the sidecar is there too). Since the Wave-3 backfetch the sidecar
    records per-fiscal-year windows rather than one season key, so the title
    names the span the record actually covers."""
    import json
    from pkinv.sectors.agriculture.gis import fetch_firms
    try:
        with open(fetch_firms.SIDECAR, encoding="utf-8") as handle:
            years = sorted({int(w[0][2:])
                            for w in json.load(handle)["windows_fetched"]})
        season = "FY%d-%02d to FY%d-%02d" % (years[0], (years[0] + 1) % 100,
                                             years[-1], (years[-1] + 1) % 100)
    except (OSError, KeyError, ValueError, IndexError):
        season = "FY2023-24"
    return ("Pakistan crop-residue fire occurrence (VIIRS, %s burning seasons)"
            % season)
TIF = {"Enteric fermentation": "enteric_ch4_2024.tif",
       "Manure management": "manure_2024.tif",
       "Rice cultivation": "rice_ch4_2024.tif",
       "Managed soils": "managed_soils_2024.tif",
       "Field burning of residues": "residue_burning_2024.tif",
       "Urea application": "liming_urea_2024.tif"}
# Category -> DEFAULT proxy, and the set resolve_proxies must build. Actual allocation is finer:
# allocate_by_stream() grids each subitem on the raster matching its own province proxy, so managed
# soils is not forced onto one surface. This table sets the fallback and the categories' base raster.
# A user-supplied data/gis/manual/spam_rice.tif overrides rice at runtime (see resolve_proxies).
CATEGORY_PROXY = {"Enteric fermentation": "glw_livestock",
                  "Manure management": "glw_livestock",
                  "Rice cultivation": "cropland",
                  "Managed soils": "cropland",
                  "Field burning of residues": "cropland",
                  "Urea application": "cropland"}
TOL = 1e-3  # Mt; reconciliation tolerance


def allocate_by_stream(grid, proxies, cat_proxy):
    """Allocate each province x SUBITEM stream on its own raster, then sum into category surfaces.

    A category is not spatially homogeneous. Managed soils carries synthetic fertiliser, applied
    manure, pasture deposition and crop residues, and roughly three-fifths of its nitrogen is
    livestock-derived -- so gridding the whole category on cropland, as a single category-wide proxy
    forces, put the bulk of it on the wrong geography. Each stream now follows the raster matching
    the province proxy it was allocated with.

    Shares core.gis.proxy_map's province-proxy -> raster translation with the
    air-pollutant layer so the two cannot drift apart.

    Returns ({category: (H,W) Mt}, fallbacks, {category: [raster names used]}).
    """
    groups = collections.defaultdict(list)
    for r in provincial_rows():
        groups[(r["category"], gis_proxy(r["proxy"], r["category"], proxies))].append(r)

    allocated = {c: np.zeros((grid.height, grid.width), dtype=np.float64) for c in CATEGORIES}
    fallbacks, used = [], collections.defaultdict(set)
    for (category, gproxy), rows in sorted(groups.items()):
        sub = {p: {c: 0.0 for c in CATEGORIES} for p in PROVINCES}
        for r in rows:
            sub[r["province"]][r["category"]] += r["co2e_Mt_AR5"]
        group_cat_proxy = dict(cat_proxy)
        group_cat_proxy[category] = gproxy
        part, fb = allocate(grid, proxies, sub, group_cat_proxy)
        allocated[category] += part[category]
        fallbacks += [f for f in fb if f[1] == category]
        used[category].add(gproxy)
    return allocated, fallbacks, {c: sorted(v) for c, v in used.items()}


def main():
    os.makedirs(OUT, exist_ok=True)
    grid = build_grid()
    matrix = provincial_matrix()

    proxies, cat_proxy, descs = resolve_proxies(grid)
    allocated, fallbacks, stream_proxies = allocate_by_stream(grid, proxies, cat_proxy)

    _check_reconciliation(grid, allocated, matrix)

    total = sum(allocated.values())
    for cat, arr in allocated.items():
        render.write_geotiff(asset_path(OUT, TIF[cat]), arr, grid)
    render.write_geotiff(asset_path(OUT, "total_co2e_2024.tif"), total, grid)
    render.plot_total(asset_path(OUT, "hotspot_total.png"), total, grid,
                      "Pakistan agricultural GHG emissions 2024 (Mt CO2e, provisional)")
    render.plot_by_category(asset_path(OUT, "hotspot_by_category.png"), allocated, grid)
    if "firms_fire" in proxies:                       # VIIRS burn-occurrence map
        render.plot_total(asset_path(OUT, "fire_occurrence.png"), proxies["firms_fire"], grid,
                          fire_title(),
                          cbar_label="VIIRS fire density, FRP-weighted (log scale)")
    _write_cells_csv(grid, allocated, total)
    _write_report(grid, matrix, allocated, total, stream_proxies, descs, fallbacks)

    print("Phase 4 gridded surfaces written (per-stream proxies):")
    for cat in CATEGORIES:
        print("  %-28s <- %s" % (cat, ", ".join(stream_proxies.get(cat, [cat_proxy[cat]]))))
    if fallbacks:
        provs = sorted({p for p, _ in fallbacks})
        print("  uniform fallback (empty proxy) for: %s" % ", ".join(provs))
    print("  national total (gridded): %.1f Mt CO2e  (control %.1f)"
          % (total.sum(), sum(sum(matrix[p].values()) for p in PROVINCES)))


def resolve_proxies(grid):
    """Build the proxy set the categories need, with manual-drop overrides and fallbacks.

    Returns (proxies{name:array}, category_proxy{cat:name}, descs{name:desc}).
    """
    proxies, descs = {}, {}
    cat_proxy = dict(CATEGORY_PROXY)

    # optional user-supplied rice proxy (MapSPAM) overrides rice
    manual_rice = build_manual_proxy(grid, "spam_rice.tif")
    if manual_rice is not None and manual_rice[0].sum() > 0:
        proxies["spam_rice"], descs["spam_rice"] = manual_rice
        cat_proxy["Rice cultivation"] = "spam_rice"

    # optional FIRMS fire proxy (VIIRS) overrides residue burning.
    # THE REFERENCE PERIOD, NAMED RATHER THAN DEFAULTED. This module is a hand-run sector
    # diagnostic - it is in neither run_all's PHASES nor the Makefile - and it has no period
    # of its own, so build_firms_fire_proxy's default was already the reference year. Saying
    # so costs nothing and stops the call reading like the cube's, which IS period-keyed and
    # would be wrong to leave defaulted.
    from pkinv.report.grid_cube import period_keys
    fire = build_firms_fire_proxy(grid, period_keys())
    if fire is not None and fire[0].sum() > 0:
        proxies["firms_fire"], descs["firms_fire"] = fire
        cat_proxy["Field burning of residues"] = "firms_fire"

    # Build every raster reachable from a province proxy, not just the category defaults:
    # allocate_by_stream() resolves per subitem, so e.g. manure_applied is needed even though no
    # whole category defaults to it.
    for name in set(cat_proxy.values()) | set(GIS_PROXY_FOR.values()):
        if name in proxies:
            continue
        try:
            arr, desc = get_proxy(name, grid)
        except Exception as e:
            print("  proxy '%s' unavailable (%s) -> cropland fallback" % (name, e))
            arr, desc = None, None
        if arr is None or arr.sum() <= 0:
            arr, desc = get_proxy("cropland", grid)   # reliable fallback
            desc = "cropland fallback (%s empty/unavailable)" % name
        proxies[name], descs[name] = arr, desc
    return proxies, cat_proxy, descs


def _check_reconciliation(grid, allocated, matrix):
    # national per-category
    for cat in CATEGORIES:
        nat = sum(matrix[p][cat] for p in PROVINCES)
        got = float(allocated[cat].sum())
        assert abs(nat - got) < TOL, "category %s: %.4f vs %.4f" % (cat, nat, got)
    # per province
    for prov in PROVINCES:
        mask = grid.province_mask(prov)
        ctrl = sum(matrix[prov].values())
        got = float(sum(allocated[c][mask].sum() for c in CATEGORIES))
        assert abs(ctrl - got) < TOL, "province %s: %.4f vs %.4f" % (prov, ctrl, got)


def _write_cells_csv(grid, allocated, total):
    lon, lat = cell_lonlat(grid)
    id_to_prov = {v: k for k, v in PROV_ID.items()}
    path = asset_path(OUT, "grid_emissions_2024.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["lon", "lat", "province"]
                   + [c.replace(" ", "_") for c in CATEGORIES] + ["total_Mt_co2e"])
        H, W = grid.height, grid.width
        for i in range(H):
            for j in range(W):
                pid = grid.province_id[i, j]
                if pid < 0 or total[i, j] <= 0:
                    continue
                w.writerow([round(float(lon[i, j]), 4), round(float(lat[i, j]), 4),
                            id_to_prov[pid]]
                           + [round(float(allocated[c][i, j]), 6) for c in CATEGORIES]
                           + [round(float(total[i, j]), 6)])


def _write_report(grid, matrix, allocated, total, cat_proxy, descs, fallbacks):
    cattot = category_totals(allocated)
    lines = ["# Pakistan Agricultural GHG - Gridded Surfaces (2024, provisional)\n",
             "National emissions allocated to a 0.05-degree (~5 km) grid by dasymetric "
             "distribution of the Phase-3 provincial control totals, using **category-specific "
             "proxies**, reconciled exactly to province and national totals.\n",
             "## Configuration",
             "- Grid: %dx%d cells at 0.05 deg, EPSG:4326, bounds %s"
             % (grid.width, grid.height, tuple(round(float(b), 2) for b in grid.bounds)),
             "",
             "## Proxies used per category\n",
             "Allocation is per emission *stream*, not per category: a category whose subitems ride "
             "different nitrogen sources is gridded on several rasters and summed. Managed soils is "
             "the clear case -- most of its nitrogen is livestock-derived, so gridding it wholly on "
             "cropland would misplace the majority of it.\n",
             "| Category | Proxies | Sources |", "|---|---|---|"]
    for c in CATEGORIES:
        names = cat_proxy[c] if isinstance(cat_proxy[c], list) else [cat_proxy[c]]
        lines.append("| %s | %s | %s |"
                     % (c, ", ".join("`%s`" % n for n in names),
                        "; ".join(descs.get(n, n) for n in names)))
    if fallbacks:
        provs = ", ".join(sorted({p for p, _ in fallbacks}))
        lines.append("\n- Province-uniform fallback (empty proxy) applied in: %s" % provs)
    lines += ["",
              "## Category totals (gridded == control)\n",
              "| Category | Mt CO2e |", "|---|---:|"]
    for c in CATEGORIES:
        lines.append("| %s | %.1f |" % (c, cattot[c]))
    lines.append("| **Total** | **%.1f** |" % total.sum())
    lines += ["",
              "## Outputs",
              "- Per-category + total GeoTIFFs (float32, Mt CO2e/cell), "
              "`hotspot_total.png`, `hotspot_by_category.png`, `grid_emissions_2024.csv`",
              "",
              "## Data provenance & caveats",
              "- **Enteric & manure** now use **GLW 4 (2020) emission-weighted livestock "
              "density** (FAO, open) - herds land on real locations (canal belt, rangeland, "
              "peri-urban), not just cropland.",
              "- **Rice, soils, burning, urea** use ESA WorldCover 2021 cropland fraction. A "
              "user-supplied `data/gis/manual/spam_rice.tif` (MapSPAM) overrides rice automatically.",
              "- **MapSPAM crop area and NASA FIRMS fire** are user-supplied drop-ins "
              "(see `docs/DATA_ACQUISITION.md`); absent -> cropland fallback.",
              "- These are **allocated** surfaces, not measurements; category totals are exact "
              "control totals. GLW ref-year 2020 / WorldCover 2021 vs 2024 activity - stable but flagged.",
              ""]
    with open(asset_path(OUT, "gis_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()

"""Gridded (0.05 deg) and ADM2-district allocation of the air-pollutant layer.

Same dasymetric rule as the GHG layer (allocate.py Eq: e_i = E_p * w_i / sum_j w_j), so each pollutant
reconciles province-by-province and nationally by construction. Two differences from the GHG gridding,
both deliberate:

  * Sub-item proxies. The GHG grid maps a whole CATEGORY to one raster (run_gis.CATEGORY_PROXY), but the
    air layer resolves each nitrogen stream separately -- NH3 from manure rides gridded livestock while
    NH3 from fertiliser rides cropland -- matching the per-stream province split already published. The
    air grid is therefore finer than the GHG grid for managed soils.
  * Units are kt of the pollutant per cell (the GHG rasters are Mt CO2e per cell).

The province-share proxy vocabulary (livestock_total, fertilizer_N, ...) differs from the GIS raster
vocabulary (glw_livestock, cropland, ...), so GIS_PROXY_FOR translates between them; burning streams
resolve to the FIRMS fire raster where available. All raster fallbacks (missing GLW/MapSPAM/FIRMS ->
cropland) are inherited unchanged from run_gis.resolve_proxies.

Usage:  python3 -m pkinv.sectors.agriculture.gis.air_spatial
Writes: outputs/gis/air/<pollutant>_2024.tif, outputs/air_pollutants_district_2024.csv,
        outputs/gis/air/nh3_map.png
"""

from pkinv.assets import asset_path
import collections
import csv
import os
import sys


import numpy as np                                      # noqa: E402
from pkinv.core.gis.grid import build_grid, PROVINCES                  # noqa: E402
from pkinv.core.gis.allocate import allocate                           # noqa: E402
from pkinv.sectors.agriculture.gis.run_gis import resolve_proxies, CATEGORIES        # noqa: E402
from pkinv.sectors.agriculture.gis import district_downscale as DD  # noqa: E402
from pkinv.core.gis import render  # noqa: E402
from pkinv.sectors.agriculture import air_pollutants as ap  # noqa: E402

from pkinv.paths import ROOT

OUT_GIS = asset_path(ROOT, "outputs", "gis", "air")
OUT_DIST = asset_path(ROOT, "outputs", "air_pollutants_district_2024.csv")
RTOL = 1e-6          # relative: the GHG TOL is absolute in Mt and meaningless for kt

# province-share proxy -> GIS raster. Defined in core because the greenhouse-gas grid
# layer needs the same translation; re-exported here since this module's name for it is
# already load-bearing.
from pkinv.core.gis.proxy_map import GIS_PROXY_FOR, gis_proxy as _gis_proxy  # noqa: E402,F401


# Which external benchmark sector each of our NH3 streams corresponds to. Used only by the spatial
# comparison, which must be reported per stream: our livestock streams and the benchmark's both
# distribute on GLW livestock, so their spatial agreement is partly structural, while the fertiliser
# and burning streams rest on genuinely different surfaces.
# PREFIX map since the air spatial Wave A disaggregation: the atoms carry product,
# species-stage and crop detail in a parenthetical suffix ("NH3 - housing (buffalo)",
# "Residue burning NH3 (wheat)"), and the benchmark scope is a property of the GROUP.
NH3_SCOPE = {
    "NH3 - synthetic fertiliser": "synthetic",
    "NH3 - pasture deposition (cattle-type)": "livestock",
    "NH3 - pasture deposition (sheep/goat/other)": "livestock",
    "NH3 - housing": "livestock",
    "NH3 - yard": "livestock",
    "NH3 - storage": "livestock",
    "NH3 - manure applied to soils": "livestock",
    "NH3 - crop residues left in field": "residues",
    "Residue burning NH3": "burning",
}


def nh3_scope(subitem):
    for prefix, scope in NH3_SCOPE.items():
        if subitem.startswith(prefix):
            return scope
    return None


def _province_matrix(rows_for_group):
    """{province: {category: kt}} zero-filled over the 6 GHG categories allocate() iterates."""
    m = {p: {c: 0.0 for c in CATEGORIES} for p in PROVINCES}
    for r in rows_for_group:
        m[r["province"]][r["category"]] += r["emissions_kt"]
    return m


def build(grid=None, proxies=None, cat_proxy=None, year=None):
    """Return ({pollutant: array}, district_rows, {pollutant: {province: kt}}, {NH3 scope: array}).

    `year` builds the surface on a historical year's activity instead of the census anchor, which
    the spatial validation needs in order to compare against a benchmark published for 2015. The
    spatial PROXIES are fixed-vintage either way (GLW livestock, WorldCover cropland), so only the
    provincial control totals move with the year -- a limitation to state, not to hide.
    """
    if grid is None:
        grid = build_grid()
    if proxies is None:
        proxies, cat_proxy, _ = resolve_proxies(grid)

    rows = ap.compute() if year is None else ap.engine_rows_for_year(year)
    if rows is None:
        raise ValueError("no engine rows for year %r" % year)
    prov_rows = ap._provincial(rows)
    # group by (pollutant, category, gis raster) so each stream keeps its own proxy
    groups = collections.defaultdict(list)
    for r in prov_rows:
        groups[(r["pollutant"], r["category"],
                _gis_proxy(r["proxy"], r["category"], proxies))].append(r)
    # separately, group the NH3 rows by benchmark-comparable scope for the spatial comparison
    scope_groups = collections.defaultdict(list)
    for r in prov_rows:
        sc = nh3_scope(r["subitem"]) if r["pollutant"] == "NH3" else None
        if sc:
            scope_groups[(sc, r["category"],
                          _gis_proxy(r["proxy"], r["category"], proxies))].append(r)

    rasters = collections.defaultdict(
        lambda: np.zeros((grid.height, grid.width), dtype=np.float64))
    scope_rasters = collections.defaultdict(
        lambda: np.zeros((grid.height, grid.width), dtype=np.float64))
    prov_totals = collections.defaultdict(lambda: collections.defaultdict(float))
    district_rows = []
    share_cache = {}          # (category, gis proxy) -> {district_idx: share}

    for (scope, category, gproxy), rows in sorted(scope_groups.items()):
        m = _province_matrix(rows)
        gcp = dict(cat_proxy)
        gcp[category] = gproxy
        alloc, _ = allocate(grid, proxies, m, gcp)
        scope_rasters[scope] += alloc[category]

    for (poll, category, gproxy), rows in sorted(groups.items()):
        matrix = _province_matrix(rows)
        group_cat_proxy = dict(cat_proxy)
        group_cat_proxy[category] = gproxy
        allocated, _ = allocate(grid, proxies, matrix, group_cat_proxy)
        rasters[poll] += allocated[category]
        for p in PROVINCES:
            prov_totals[poll][p] += matrix[p][category]

        # districts: same shares the GHG layer uses for this proxy (incl. the PBS-2024 census
        # override, which fires whenever the resolved raster is glw_livestock)
        if (category, gproxy) not in share_cache:
            share_cache[(category, gproxy)] = DD.district_shares(
                grid, proxies, group_cat_proxy)[category]
        shares = share_cache[(category, gproxy)]
        for prov in DD.NAMED:
            for d in grid.districts_in(prov):
                v = matrix[prov][category] * shares.get(d, 0.0)
                if v > 0:
                    district_rows.append({"district": grid.districts[d], "province": prov,
                                          "category": category, "proxy": gproxy,
                                          "pollutant": poll, "emissions_kt": v})
            # rc42 (S-2): the census units with no polygon (Cholistan Area, Larkana District)
            # carry their own share as named rows, as the GHG district panel does; without
            # them the livestock pollutants summed to 99.6 percent of the province control
            if gproxy == "glw_livestock":
                for unit, share in DD.NO_SHAPE.get(prov, {}).items():
                    v = matrix[prov][category] * share
                    if v > 0:
                        district_rows.append({"district": unit, "province": prov,
                                              "category": category, "proxy": gproxy,
                                              "pollutant": poll, "emissions_kt": v})
        if matrix[DD.OTHER][category] > 0:
            district_rows.append({"district": "Other (GB/AJK/ICT residual)", "province": DD.OTHER,
                                  "category": category, "proxy": gproxy, "pollutant": poll,
                                  "emissions_kt": matrix[DD.OTHER][category]})
    return (dict(rasters), district_rows, {p: dict(v) for p, v in prov_totals.items()},
            dict(scope_rasters))


def check(rasters, district_rows, prov_totals):
    """Per pollutant: sum(cells) == sum(districts) == sum(provinces) == national (relative tol)."""
    worst = 0.0
    dist = collections.defaultdict(float)
    for r in district_rows:
        dist[r["pollutant"]] += r["emissions_kt"]
    for poll, arr in rasters.items():
        nat = sum(prov_totals[poll].values())
        if nat <= 0:
            continue
        for got, what in ((float(arr.sum()), "grid"), (dist[poll], "districts")):
            rel = abs(got - nat) / nat
            assert rel < RTOL, "%s %s: %.6f vs national %.6f" % (poll, what, got, nat)
            worst = max(worst, rel)
    return worst


def main():
    grid = build_grid()
    if grid.district_id is None:
        print("No PAK_ADM2.geojson - run `make fetch-adm2` first.")
        return 1
    os.makedirs(OUT_GIS, exist_ok=True)
    proxies, cat_proxy, _ = resolve_proxies(grid)
    rasters, district_rows, prov_totals, _ = build(grid, proxies, cat_proxy)
    worst = check(rasters, district_rows, prov_totals)

    for poll, arr in sorted(rasters.items()):
        render.write_geotiff(asset_path(OUT_GIS, "%s_2024.tif" % poll.replace(".", "").lower()),
                             arr, grid)
    render.plot_total(asset_path(OUT_GIS, "nh3_map.png"), rasters["NH3"], grid,
                      "Pakistan agricultural NH3 (2024, kt per cell; province controls preserved)",
                      cbar_label="kt NH3 per 0.05 deg cell (log scale)")

    with open(OUT_DIST, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["district", "province", "category", "proxy", "pollutant", "emissions_kt"])
        for r in sorted(district_rows, key=lambda r: (r["pollutant"], -r["emissions_kt"])):
            w.writerow([r["district"], r["province"], r["category"], r["proxy"],
                        r["pollutant"], round(r["emissions_kt"], 5)])

    ndist = len({r["district"] for r in district_rows})
    print("Air-pollutant spatial allocation: %d pollutants -> gis/air/*.tif + district CSV"
          % len(rasters))
    print("  reconciliation: worst relative residual %.2e (grid and districts, per pollutant)" % worst)
    top = collections.defaultdict(float)
    for r in district_rows:
        if r["pollutant"] == "NH3" and r["province"] != DD.OTHER:
            top[r["district"]] += r["emissions_kt"]
    lead = sorted(top.items(), key=lambda kv: -kv[1])[:5]
    print("  %d districts; top NH3 (kt): " % ndist
          + ", ".join("%s %.0f" % (d.split(" District")[0], v) for d, v in lead))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

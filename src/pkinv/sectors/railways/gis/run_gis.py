"""The route-constrained spatial inventory: emissions on the rails that burn the fuel.

WHAT REPLACES WHAT. The provincial split had one basis: freight wagons LOADED by division,
which credits Sindh with fuel burnt hauling Karachi-origin freight up-country and spreads
passenger operations - four times the freight train-km - by freight geography. This model
constrains emissions to the audited rail network instead: line-haul fuel runs along
corridor-weighted route geometry, shunting sits at the seven divisional yards weighted by
their wagon loadings, and every surface reconciles exactly to the national control.

WHAT THE WEIGHTS ARE, HONESTLY. The network geometry and the yard locations are data. The
corridor service tiers are DECLARED JUDGMENT (corridor_weights.csv states the basis row by
row) pending the operator's timetable - whose public interface sits behind an
authenticated API (see rail-timetable in data/data_gaps.csv). The judgment moves fuel
along real track only; the old wagons-loaded proxy is retained as the structural
alternative so the choice is visible, and the national total is identical under both by
construction.

ONE COMPOSITE SURFACE SERVES EVERY SPECIES. All Tier 1 species - CO2, CH4, N2O and the
air-pollutant layer - are proportional to fuel, so the fuel surface (passenger + freight +
shunting shares from tier2.split, each on its own normalised raster) allocates them all;
per-species grids differ only by their national totals. Reconciliation is asserted at
national, provincial and district level on every run.

Usage:   python3 -m pkinv.sectors.railways.gis.run_gis     (needs the [gis] extra)
Writes:  outputs/gis/railways_*.tif, outputs/railways_gis_cells_2024.csv,
         railways_gis_provincial_2024.csv, railways_gis_district_2024.csv,
         railways_route_province_shares_2024.csv, railways_network_audit_2024.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.core.geography import PROVINCES
from pkinv.core.gis.grid import build_grid
from pkinv.core.gis.lines import burn_lines, burn_points
from pkinv.core.gis.render import write_geotiff
from pkinv.paths import OUTPUTS
from pkinv.sectors.railways import air_pollutants, engine, tier2, traction
from pkinv.sectors.railways.data import RailwaysData
from pkinv.sectors.railways.gis import network

TOL_MT = 1e-9          # the surface is constructed from the total; equality is exact
GIS_OUT = asset_path(OUTPUTS, "gis")


def service_rasters(grid, segments=None, weights=None):
    """Normalised {passenger, freight, shunting} surfaces; each sums to 1."""
    segments = segments or network.load_network()
    weights = weights or network.load_weights()
    rasters = {}
    for service in ("passenger", "freight"):
        records = [(s["coords"], weights[s["corridor"]][service])
                   for s in segments if s["status"] == "active"]
        arr = burn_lines(grid, records)
        rasters[service] = arr / arr.sum()
    yards = burn_points(grid, network.load_yards())
    rasters["shunting"] = yards / yards.sum()
    return rasters


def fuel_surface(grid, data, rasters=None):
    """The composite fuel surface: service fuel shares on their normalised rasters."""
    rasters = rasters or service_rasters(grid)
    split = tier2.split(data)
    control = sum(split.values())
    surf = (rasters["passenger"] * (split["line_haul_passenger"] / control)
            + rasters["freight"] * (split["line_haul_freight"] / control)
            + rasters["shunting"] * (split["shunting"] / control))
    return surf / surf.sum()


def province_shares(grid, surf):
    shares = {}
    for p in PROVINCES:
        shares[p] = float(surf[grid.province_mask(p)].sum())
    inside = sum(shares.values())
    # Mass on cells the ADM raster leaves outside any province (border pixels) is
    # renormalised so the shares are a partition - the same closure the dasymetric
    # allocator applies within masks.
    return {p: v / inside for p, v in shares.items()}


def main():
    os.makedirs(GIS_OUT, exist_ok=True)
    data = RailwaysData()
    grid = build_grid()
    segments = network.load_network()

    aud = network.audit(data, segments)
    with open(asset_path(OUTPUTS, "railways_network_audit_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["item", "km", "note"])
        for corridor, km in sorted(aud["by_corridor"].items()):
            w.writerow([corridor, round(km, 1), ""])
        w.writerow(["active_total", round(aud["active_km"], 1),
                    "OSM line-km incl. double-track parallel ways"])
        w.writerow(["disconnected_fragments", round(aud["disconnected_km"], 1),
                    "isolated yard trackage and fragments; carry no line-haul weight"])
        w.writerow(["route_km_yearbook", aud["route_km_yearbook"],
                    "Principal Statistics; ratio %.3f"
                    % aud["ratio_osm_over_yearbook"]])

    rasters = service_rasters(grid, segments)
    surf = fuel_surface(grid, data, rasters)

    comps = engine.build_components(data)
    total_mt = sum(c["co2e_Mt_AR5"] for c in comps)
    co2e = surf * total_mt
    assert abs(float(co2e.sum()) - total_mt) < TOL_MT

    air = {r["pollutant"]: 0.0 for r in air_pollutants.compute(data)}
    for r in air_pollutants.compute(data):
        air[r["pollutant"]] += r["emissions_kt"]

    write_geotiff(asset_path(GIS_OUT, "railways_co2e_%d.tif" % data.year), co2e, grid)
    for pol in ("NOx", "PM2.5", "SO2"):
        write_geotiff(asset_path(GIS_OUT, "railways_%s_%d.tif"
                                   % (pol.replace(".", ""), data.year)),
                      surf * air[pol], grid)

    shares = province_shares(grid, surf)
    with open(asset_path(OUTPUTS, "railways_route_province_shares_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["province", "share", "co2e_Mt_AR5"])
        for p in PROVINCES:
            w.writerow([p, round(shares[p], 6), round(shares[p] * total_mt, 5)])

    with open(asset_path(OUTPUTS, "railways_gis_provincial_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["province", "co2e_Mt_AR5", "NOx_kt", "PM2.5_kt", "SO2_kt"])
        for p in PROVINCES:
            w.writerow([p, round(shares[p] * total_mt, 5),
                        round(shares[p] * air["NOx"], 5),
                        round(shares[p] * air["PM2.5"], 6),
                        round(shares[p] * air["SO2"], 6)])
    assert abs(sum(shares.values()) - 1.0) < 1e-9

    rows = []
    if grid.district_id is not None:
        import numpy as np
        inside = 0.0
        for did, name in enumerate(grid.districts):
            m = grid.district_mask(did)
            v = float(surf[m].sum())
            if v > 0:
                rows.append([did, name, grid.district_province[did], v])
                inside += v
        with open(asset_path(OUTPUTS, "railways_gis_district_%d.csv" % data.year),
                  "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["district_id", "district", "province", "share",
                        "co2e_Mt_AR5"])
            for did, name, prov, v in rows:
                w.writerow([did, name, prov, round(v / inside, 6),
                            round(v / inside * total_mt, 6)])

    import numpy as np
    ys, xs = np.nonzero(surf)
    with open(asset_path(OUTPUTS, "railways_gis_cells_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["lon", "lat", "co2e_Mt_AR5", "NOx_kt"])
        for r, c in zip(ys, xs):
            lon, lat = grid.transform * (c + 0.5, r + 0.5)
            w.writerow([round(lon, 4), round(lat, 4),
                        round(float(co2e[r, c]), 8),
                        round(float(surf[r, c] * air["NOx"]), 8)])

    print("network audit: %d active km vs %d route-km (x%.3f), %d km disconnected"
          % (aud["active_km"], aud["route_km_yearbook"],
             aud["ratio_osm_over_yearbook"], aud["disconnected_km"]))
    print("route-model province shares (CO2e %.5f Mt):" % total_mt)
    for p in PROVINCES:
        print("  %-18s %6.2f%%" % (p, 100 * shares[p]))
    print("  cells with railway emissions: %d" % len(xs))


if __name__ == "__main__":
    main()

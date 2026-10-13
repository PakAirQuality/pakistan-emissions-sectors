"""FROZEN SINCE THE REPOSITORY SPLIT (rc36 note): this driver reads outputs/nowcast/,
which lives in the companion research repository, so it cannot run here. Its five
products under outputs/districts/ are kept as the Tier-3 research set (docs/
spatial_products_contract.md) because the agriculture paper and its supplement include
district_totals.png; regenerating them means running this in the companion checkout.

District downscaling orchestrator: per-district controls, downscaled nowcasts, and a choropleth.

Writes outputs/district_totals_2024.csv (annual by category), outputs/districts/*_by_district.csv (the
module nowcasts split to districts by their proxy shares), and outputs/districts/district_totals.png
(a district choropleth). Everything reconciles: Σ districts == province control (and the module
time series Σ over districts == the province series).

Usage:  python3 -m pkinv.sectors.agriculture.gis.run_districts
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os
import sys


from pkinv.sectors.agriculture.gis import district_downscale as DD  # noqa: E402
from pkinv.core.gis.grid import build_grid       # noqa: E402
from pkinv.sectors.agriculture.gis.run_gis import resolve_proxies  # noqa: E402

from pkinv.paths import ROOT

NC = asset_path(ROOT, "outputs", "nowcast")
OUTD = asset_path(ROOT, "outputs", "districts")
# module CSV -> (time key, category whose proxy drives the district split)
MODULES = [
    ("rice_ch4_weekly.csv", "week_start", "Rice cultivation", "rice"),
    ("soil_n2o_daily.csv", "date", "Managed soils", "soil_n2o"),
    ("livestock_monthly.csv", "month", "Enteric fermentation", "livestock"),
    ("fire_emissions_daily.csv", "date", "Field burning of residues", "fire"),
]


def _province_series(path, tkey):
    """{province: {time_key: co2e_Mt}} from a module's per-province time series."""
    ser = {}
    for r in _activity_rows(path, comments=False):
        ser.setdefault(r["province"], {})[r[tkey]] = ser.get(r["province"], {}).get(r[tkey], 0.0) \
            + float(r["co2e_Mt"])
    return ser


def _choropleth(grid, rows):
    import numpy as np
    from pkinv.core.gis import render
    tot = {}
    for r in rows:
        tot[r["district"]] = tot.get(r["district"], 0.0) + r["co2e_Mt_AR5"]
    name_to_id = {n: i for i, n in enumerate(grid.districts)}
    arr = np.zeros((grid.height, grid.width), dtype=np.float64)
    for dname, v in tot.items():
        did = name_to_id.get(dname)
        if did is None:
            continue
        m = grid.district_mask(did)
        if int(m.sum()) > 0:
            arr[m] = v                     # flat choropleth: each district painted by its TOTAL
    render.plot_total(asset_path(OUTD, "district_totals.png"), arr, grid,
                      "Pakistan agricultural GHG by district (2024; province controls preserved)",
                      cbar_label="District total (Mt CO2e, AR5; log scale)")


def main():
    os.makedirs(OUTD, exist_ok=True)
    grid = build_grid()
    if grid.district_id is None:
        print("No PAK_ADM2.geojson - run `make fetch-adm2` first.")
        return 1
    proxies, cat_proxy, _ = resolve_proxies(grid)
    rows, shares, matrix = DD.district_controls(grid, proxies, cat_proxy)
    worst, nat_gap, nat = DD.check(rows, matrix)

    os.makedirs(os.path.dirname(DD.OUT_CSV), exist_ok=True)
    with open(DD.OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["district", "province", "category", "co2e_Mt_AR5"])
        for r in rows:
            w.writerow([r["district"], r["province"], r["category"], round(r["co2e_Mt_AR5"], 5)])

    # per-district TEMPORAL driver weights (fire day, rice week, soil-N2O pulse, manure season); each
    # module falls back to the static within-province shape where its district input is absent.
    try:
        from pkinv.sectors.agriculture.gis import district_timeseries as DT
        weights = DT.all_weights(grid)
    except Exception as e:      # noqa: BLE001
        print("  district-timing weights unavailable (%s) -> static shape" % str(e)[:60])
        weights = {}

    # downscale each module's province-week/day/month series to districts
    n_series, n_timed = 0, 0
    for fname, tkey, cat, stub in MODULES:
        p = asset_path(NC, fname)
        if not os.path.exists(p):
            continue
        ser = _province_series(p, tkey)
        dser = DD.downscale_series(ser, cat, grid, shares, weights=weights)
        if cat in weights:
            n_timed += 1
        rowsout = [(d, k, v) for d, s in dser.items() for k, v in s.items()]
        with open(asset_path(OUTD, "%s_by_district.csv" % stub), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["district", tkey, "co2e_Mt"])
            for d, k, v in sorted(rowsout):
                w.writerow([d, k, round(v, 6)])
        n_series += 1

    try:
        _choropleth(grid, rows)
        fig = " + choropleth"
    except Exception as e:      # noqa: BLE001
        fig = " (choropleth skipped: %s)" % str(e)[:40]
    n_dist = sum(len(grid.districts_in(p)) for p in DD.NAMED)
    print("District downscaling: %d districts + Other residual | %d module series (%d with per-district "
          "timing)%s" % (n_dist, n_series, n_timed, fig))
    print("  reconciliation: worst per-province residual %.2e Mt | national %.1f (gap %.2e)"
          % (worst, nat, nat_gap))
    return 0


if __name__ == "__main__":
    sys.exit(main())

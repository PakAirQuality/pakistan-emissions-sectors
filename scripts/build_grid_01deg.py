#!/usr/bin/env python3
"""The EDGAR-aligned 0.1-degree derived grid (rc47 Wave 6).

The twenty-first review: "the current 0.05 degree grid is not exactly aligned 2x2 with
EDGAR's 0.1 degree lattice." Verified PARTLY true, and the arithmetic is now shipped
rather than argued: three of the frozen lattice's four edges sit on EDGAR cell CENTRES
(odd multiples of 0.05), so a naive even-index 2x2 is offset by one fine cell on both
axes - but the ODD-index 2x2 tiles EDGAR exactly, the interior 266x338 fine cells
covering 133x169 EDGAR cells with zero error. The three half-cell strips (row 0 against
latitude 37.05, column 0 against longitude 60.85, column 339 against 77.85) belong to
EDGAR cells this domain only half-covers; they are aggregated into those cells with
`coverage_fraction` saying so, and the SUM is conserved exactly - every fine cell lands
in exactly one coarse cell.

The frozen 0.05 lattice does not move (its receipts, goldens and every product stay
keyed to it); this file is a DERIVED aggregation for benchmark use, and a test asserts
the conservation identity per (period, view, gas).

Usage:  python3 scripts/build_grid_01deg.py
Writes: outputs/pakemis_grid_0p1_edgar_aligned.nc
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

import netCDF4 as nc  # noqa: E402
import numpy as np  # noqa: E402

from pkinv.paths import OUTPUTS  # noqa: E402

SRC = asset_path(OUTPUTS, "pakemis_grid_0p05_annual_ref_fy2015_16_fy2024_25.nc")
OUT = asset_path(OUTPUTS, "pakemis_grid_0p1_edgar_aligned.nc")
GASES = ("co2", "ch4", "n2o")

# The coarse frame: lon edges 60.8..77.9 (172 edges, 171 cells: col 0 and col 170 are
# the half-covered boundary cells), lat edges 23.7..37.1 (135 edges, 134 cells: row 0
# under 37.1 is half-covered; 23.7 is itself a multiple of 0.1 so the south closes).
LON_W, LON_E = 60.8, 77.9
LAT_S, LAT_N = 23.7, 37.1
NLON = round((LON_E - LON_W) / 0.1)   # 171
NLAT = round((LAT_N - LAT_S) / 0.1)   # 134


def build():
    src = nc.Dataset(SRC)
    fine_lon = src.variables["lon"][:]
    fine_lat = src.variables["lat"][:]
    # each fine cell's coarse indices, from its CENTRE - exact by construction
    ci = np.floor((fine_lon - LON_W) / 0.1).astype(int)      # (340,)
    ri = np.floor((LAT_N - fine_lat) / 0.1).astype(int)      # (267,) row 0 = north
    assert ci.min() >= 0 and ci.max() == NLON - 1, (ci.min(), ci.max())
    assert ri.min() >= 0 and ri.max() == NLAT - 1, (ri.min(), ri.max())

    def coarsen(a2d):
        out = np.zeros((NLAT, NLON), dtype=np.float64)
        np.add.at(out, (ri[:, None], ci[None, :]), a2d)
        return out

    ds = nc.Dataset(OUT, "w")
    ds.createDimension("time", len(src.dimensions["time"]))
    ds.createDimension("spatial_view", len(src.dimensions["spatial_view"]))
    ds.createDimension("lat", NLAT)
    ds.createDimension("lon", NLON)
    for name in ("time", "period_id", "spatial_view"):
        v = src.variables[name]
        ov = ds.createVariable(name, v.dtype, v.dimensions)
        ov[:] = v[:]
        ov.setncatts({k: v.getncattr(k) for k in v.ncattrs()})
    lat = ds.createVariable("lat", "f8", ("lat",))
    lat[:] = LAT_N - 0.05 - 0.1 * np.arange(NLAT)
    lat.units, lat.standard_name = "degrees_north", "latitude"
    lon = ds.createVariable("lon", "f8", ("lon",))
    lon[:] = LON_W + 0.05 + 0.1 * np.arange(NLON)
    lon.units, lon.standard_name = "degrees_east", "longitude"
    frac = ds.createVariable("coverage_fraction", "f8", ("lat", "lon"))
    cover = coarsen(np.ones((len(fine_lat), len(fine_lon))))
    frac[:] = cover / 4.0
    frac.long_name = ("share of the 0.1-degree cell covered by the fine domain: 1.0 "
                      "for the 133x169 interior, 0.5 on the three half-covered "
                      "boundary strips, 0.25 at their two corners")
    checks = []
    for gas in GASES:
        v = src.variables["%s_emissions" % gas]
        ov = ds.createVariable("%s_emissions" % gas, "f8",
                               ("time", "spatial_view", "lat", "lon"), zlib=True)
        for t in range(v.shape[0]):
            for k in range(v.shape[1]):
                fine = np.nan_to_num(np.asarray(v[t, k], dtype=np.float64))
                coarse = coarsen(fine)
                ov[t, k] = coarse
                checks.append(abs(coarse.sum() - fine.sum()))
        ov.units = v.units if "units" in v.ncattrs() else ""
        ov.long_name = ("aggregated 2x2 at the ODD parity that tiles EDGAR exactly; "
                        "see coverage_fraction for the boundary strips")
    ds.alignment = ("EDGAR-aligned: every cell edge is a multiple of 0.1 degrees. The "
                    "0.05 lattice's west/east/north edges sit on EDGAR cell centres, "
                    "so the interior tiles at odd fine indices and three half-cell "
                    "strips are aggregated into their half-covered coarse cells.")
    ds.source_lattice = "pk_0p05_epsg4326_v1 (frozen; this file is a derived aggregation)"
    worst = max(checks)
    ds.conservation_worst_abs = worst
    ds.close()
    src.close()
    # The source layers are float32; two summation orders over 90,780 f4 values
    # differ at ~1e-7 absolute on layers of 1e2..1e4 Gg. The identity being asserted
    # is exact in exact arithmetic (every fine cell lands in exactly one coarse
    # cell); the bound prices f4 summation noise and nothing else.
    assert worst < 1e-5, worst
    print("0.1-degree EDGAR-aligned grid: %dx%d, conservation worst |delta| %.2e"
          % (NLAT, NLON, worst))


if __name__ == "__main__":
    build()

"""Annual 0.05-degree emissions grids streamed over registered fiscal periods.

The current core spans July 2015 through June 2025: ten fiscal years. Each layer
carries its fiscal identifier and evidence records distinguishing own-period activity,
modelled or reused geography, substitution and unallocated mass. A grid resolution is
not an observation of source activity at that resolution.

The writer is a sink for spatial_by_year: one period's accumulators are resident at a
time. The annual, monthly administrative and detailed reference products therefore
consume the same physical allocation rather than independently deriving geography.

CF intervals run from 1 July to the following 1 July (exclusive). The source register
stores inclusive period-end dates, converted here by adding one day. Complete calendar
years could be assembled only for CY2016 through CY2024 at compatible source and
allocation boundaries; the fiscal layers themselves remain July-to-June intervals.
"""

from pkinv.assets import asset_path
import datetime as _dt
import os

import numpy as np

import pkinv
from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows

GASES = ("CO2", "CH4", "N2O")
VIEWS = ("physical", "origin", "accounting")
FILL = -9999.0
EPOCH = _dt.date(1970, 1, 1)
CORE = asset_path(OUTPUTS, "pakemis_grid_0p05_annual_ref_fy2015_16_fy2024_25.nc")


def period_bounds():
    """[(period_id, start_days, end_days_exclusive, mid_days)] over the registered fiscal core."""
    out = []
    for row in read_rows(asset_path(DATA, "periods.csv")):
        start = _dt.date.fromisoformat(row["period_start"])
        # periods.csv records the LAST DAY of the period; CF bounds are half-open.
        end = _dt.date.fromisoformat(row["period_end"]) + _dt.timedelta(days=1)
        a, b = (start - EPOCH).days, (end - EPOCH).days
        out.append((row["period_id"], a, b, (a + b) / 2.0))
    return out


def write_frame(ds, grid, periods, view_names=None):
    """The shared georeference of the annual cube family: time axis with fiscal
    bounds, period_id, lat/lon with bounds, CRS (with the WKT GDAL actually reads),
    cell_area and pakistan_fraction - written identically for the greenhouse-gas cube
    and the air-pollutant cubes so the two families cannot drift by construction.

    `view_names` keeps the greenhouse-gas file's spatial_view axis in its original
    creation position; the air family passes None and gets no view axis at all (its
    files declare why in their own attributes)."""
    from pkinv.core.gis.grid import GRID_SPEC, cell_area_km2, pakistan_fraction
    periods = list(periods)
    ds.createDimension("time", len(periods))
    if view_names is not None:
        ds.createDimension("spatial_view", len(view_names))
    ds.createDimension("lat", grid.height)
    ds.createDimension("lon", grid.width)
    ds.createDimension("nv", 2)

    time = ds.createVariable("time", "f8", ("time",))
    time.units = "days since 1970-01-01 00:00:00"
    time.calendar = "proleptic_gregorian"
    time.standard_name = "time"
    time.long_name = "midpoint of the Pakistani fiscal year"
    time.bounds = "time_bnds"
    time[:] = [p[3] for p in periods]
    bnds = ds.createVariable("time_bnds", "f8", ("time", "nv"))
    bnds[:, 0] = [p[1] for p in periods]
    bnds[:, 1] = [p[2] for p in periods]

    pid = ds.createVariable("period_id", str, ("time",))
    pid.long_name = ("fiscal period identifier; these are July-to-June intervals and "
                     "NOT calendar years - a calendar-year product could be made directly "
                     "only for CY2016-CY2024")
    for i, p in enumerate(periods):
        pid[i] = p[0]

    if view_names is not None:
        view = ds.createVariable("spatial_view", str, ("spatial_view",))
        view.long_name = ("where a layer places mass: physical (where the emission "
                          "happens), origin (where the generating activity originates) "
                          "or accounting (where the statistic is booked). Summing "
                          "across views is a choice.")
        for i, name in enumerate(view_names):
            view[i] = name

    west, north, res = GRID_SPEC["west"], GRID_SPEC["north"], GRID_SPEC["resolution_deg"]
    lat = ds.createVariable("lat", "f8", ("lat",))
    lat.units, lat.standard_name, lat.axis = "degrees_north", "latitude", "Y"
    lat.bounds = "lat_bnds"
    lat[:] = [north - (i + 0.5) * res for i in range(grid.height)]
    lat_b = ds.createVariable("lat_bnds", "f8", ("lat", "nv"))
    lat_b[:, 0] = [north - (i + 1) * res for i in range(grid.height)]
    lat_b[:, 1] = [north - i * res for i in range(grid.height)]
    lon = ds.createVariable("lon", "f8", ("lon",))
    lon.units, lon.standard_name, lon.axis = "degrees_east", "longitude", "X"
    lon.bounds = "lon_bnds"
    lon[:] = [west + (j + 0.5) * res for j in range(grid.width)]
    lon_b = ds.createVariable("lon_bnds", "f8", ("lon", "nv"))
    lon_b[:, 0] = [west + j * res for j in range(grid.width)]
    lon_b[:, 1] = [west + (j + 1) * res for j in range(grid.width)]

    crs = ds.createVariable("crs", "i4")
    crs.grid_mapping_name = "latitude_longitude"
    crs.longitude_of_prime_meridian = 0.0
    crs.semi_major_axis = 6378137.0
    crs.inverse_flattening = 298.257223563
    crs.epsg_code = GRID_SPEC["crs"]
    # crs_wkt IS WHAT GDAL AND rasterio ACTUALLY READ. The parameter attributes above are
    # correct CF and are not, on their own, enough: without a WKT the file opens as a
    # georeferenced grid with no declared datum, and a reader is left to assume WGS84 from
    # the axis units. Assuming is what this column exists to prevent.
    crs.crs_wkt = (
        'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,'
        'AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],'
        'PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],'
        'UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],'
        'AUTHORITY["EPSG","4326"]]')
    crs.spatial_ref = crs.crs_wkt

    area = ds.createVariable("cell_area", "f8", ("lat", "lon"))
    area.units, area.long_name = "km2", "geodesic area of the cell"
    area.comment = ("a 0.05-degree cell is not a fixed area: 28.298 km2 at the southern "
                    "edge against 24.678 at the northern. Emissions here are cell TOTALS "
                    "in Gg; divide by this for a flux per square kilometre.")
    area[:] = cell_area_km2(grid)

    land = ds.createVariable("pakistan_fraction", "f8", ("lat", "lon"))
    land.units, land.long_name = "1", "share of the cell inside a Pakistani district"
    land.comment = ("from exact cell-district intersections. Summed against cell_area it "
                    "gives 877,057 km2 against a country of about 881,913; the boolean "
                    "label mask gives 900,261 because it is rasterised all_touched.")
    land[:] = pakistan_fraction(grid)


class AnnualGridWriter:
    """Opened once, fed one period at a time, closed once."""

    def __init__(self, path, grid, periods, configuration_id=None):
        from netCDF4 import Dataset
        from pkinv.core.gis.grid import GRID_SPEC
        self.path = path
        self.grid = grid
        self.periods = list(periods)
        self.index = {p[0]: i for i, p in enumerate(self.periods)}
        self.ds = Dataset(path, "w", format="NETCDF4")
        ds = self.ds
        write_frame(ds, grid, self.periods, view_names=VIEWS)

        self.gas = {}
        for name in GASES:
            var = ds.createVariable(
                name.lower() + "_emissions", "f4",
                ("time", "spatial_view", "lat", "lon"),
                zlib=True, complevel=4, shuffle=True, fletcher32=True,
                chunksizes=(1, 1, 128, 128), fill_value=FILL)
            var.units = "Gg"
            var.long_name = "%s emitted in the cell over the fiscal period" % name
            var.cell_methods = "time: sum area: sum"
            var.cell_measures = "area: cell_area"
            var.grid_mapping = "crs"
            var.comment = ("an interval-integrated cell MASS, so the unit is Gg and not Gg/yr. "
                           "Cells outside every district are _FillValue; an in-country zero is "
                           "a measurement and is stored as 0.")
            self.gas[name] = var

        self.outside = grid.province_id < 0
        ds.Conventions = "CF-1.8"
        from pkinv.core import configurations as conf
        configuration_id = conf.canonical(configuration_id or conf.REFERENCE)
        ds.title = "PakEmis annual native greenhouse-gas emissions, " + self.periods[0][0] + " to " + self.periods[-1][0]
        ds.release_version = pkinv.__version__
        ds.grid_spec_id = GRID_SPEC["grid_spec_id"]
        ds.configuration_id = configuration_id
        ds.institution = "Pakistan Air Quality Initiative"
        ds.licence = "See LICENSE-data and per-product provenance; upstream licences retained"
        ds.geographic_licence_basis = "independent_primary_geography; ODbL alternatives excluded"
        ds.time_basis = ("Pakistani fiscal years, 1 July to 30 June. NOT calendar years, "
                         "and not relabelled as any: period_id travels with every slice.")
        ds.configurations = ("This file contains one structural configuration: " + configuration_id +
                             "; household dung=" + conf.dung_basis(configuration_id) +
                             "; nitrogen method=" + conf.nitrogen_method(configuration_id))
        ds.monthly_grain = ("monthly cells exist for FY2023-24 only "
                            "(pakemis_grid_0p05_monthly.nc). A historical month has no "
                            "seasonal geography evidence and none is invented here.")
        ds.conservation = ("per period, gas and view, the cells sum to the national total less "
                           "the mass in pakemis_spatial_unallocated_by_year.csv, which is "
                           "published per period for exactly this check.")
        ds.evidence = ("what each layer's spatial pattern rests on, per stream and period, is "
                       "in pakemis_spatial_weights_by_year.csv - including whether the pattern "
                       "is the period's own evidence or the reference year's, carried back.")
        ds.configuration_allocation = (
            "All configurations use the same process-specific geographic allocation within each "
            "period. Changing dung fate or nitrogen method changes process mass; it does not "
            "supply new observations of locations. Differences between configuration maps are "
            "conditional on this fixed allocation, including reference/proxy patterns.")

    def write(self, time_index, period_id, result):
        """One period, straight from the accumulator the loop already holds."""
        if self.index.get(period_id) != time_index:
            raise ValueError("period %s is index %r, not %r"
                             % (period_id, self.index.get(period_id), time_index))
        for gas in GASES:
            for view_index, view in enumerate(VIEWS):
                # float64 throughout, cast at the write
                annual = np.sum(result["view_gas_month"][(view, gas)], axis=0,
                                dtype=np.float64)
                annual = np.where(self.outside, FILL, annual)
                self.gas[gas][time_index, view_index, :, :] = annual.astype(np.float32)

    def close(self):
        self.ds.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

"""The nine-period annual 0.05-degree AIR-POLLUTANT grids, one file per configuration.

SAME LATTICE, SAME PERIODS, SAME DISCIPLINE as the greenhouse-gas annual cube
(annual_grid.py), because it is the same allocation: every pollutant layer is its
anchor stream's own cell weight vector - the vector the greenhouse-gas cube placed
that stream on for that period - multiplied by the air panel's mass. The frame
(time/lat/lon coordinates, bounds, CRS, cell_area, pakistan_fraction) is written by
annual_grid.write_frame so the two families cannot drift.

NO spatial_view DIMENSION, DELIBERATELY. The air family does not resolve the
physical/origin/accounting question: each pollutant mass rides its anchor's single
declared placement (physical for most sectors, accounting for road-fuel transport,
origin for waste), and the global attribute says so rather than a dimension
pretending the three views were separately estimated for air.

TWO FILES, TWO CONFIGURATIONS. REF_2023_24 (survey-anchored dung) and the ledger series L_HERD1624
differ in the residential dung layers alone; S is a separate file, never a sum.

coverage_scope=covered_sources_only: the grid holds the covered series, not a
national air total. WHICH sectors that is, is read from the atoms the grid sums and
written into the file's own attribute (covered_sectors below) - it was a hand-written
list here and in the attribute, and both went on naming seven sectors, with power and
industry absent, after the grid held ten.
"""

from pkinv.assets import asset_path
import os

import numpy as np

import pkinv
from pkinv.paths import OUTPUTS
from pkinv.core.gis.grid import GRID_SPEC

FILL = -9999.0
POLLUTANTS = ("BC", "CO", "NH3", "NMVOC", "NOx", "PM2.5", "SO2")
VAR_OF = {"BC": "bc_emissions", "CO": "co_emissions", "NH3": "nh3_emissions",
          "NMVOC": "nmvoc_emissions", "NOx": "nox_emissions",
          "PM2.5": "pm25_emissions", "SO2": "so2_emissions"}
REF_PATH = asset_path(OUTPUTS, "pakemis_air_grid_0p05_annual_fy2015_16_fy2023_24.nc")
SURVEY_PATH = asset_path(
    OUTPUTS, "pakemis_air_grid_0p05_annual_ledger_fy2015_16_fy2023_24.nc")


def covered_sectors():
    """The sectors whose atoms this grid is the sum of, and the species each one carries -
    from the atoms file itself (the core seven species; the panel's extra strata are not
    gridded). {sector_id: sorted species}."""
    from pkinv.activity.store import read_rows
    out = {}
    for r in read_rows(asset_path(OUTPUTS, "pakemis_air_atomic_annual.csv")):
        if r["core7"] == "yes" and float(r["emissions_Gg"]) != 0.0:
            out.setdefault(r["sector_id"], set()).add(r["pollutant"])
    return {sector: sorted(species) for sector, species in sorted(out.items())}


def coverage_scope_text(sectors):
    """The file's coverage_scope attribute, from covered_sectors(). A sector that carries
    only some of the species is said to (grid power is in the panel for the species its
    admission register prices and for no other)."""
    whole = [s for s, species in sectors.items() if len(species) == len(POLLUTANTS)]
    part = ["%s (%s only)" % (s, ", ".join(species)) for s, species in sectors.items()
            if len(species) != len(POLLUTANTS)]
    return ("covered_sources_only: the %d sectors with an air-pollutant layer over the "
            "nine-year window (%s). A sector listed with species carries those alone; what "
            "is screened and not estimated travels beside the panel as a scenario pair and "
            "is ABSENT here - this is the covered series, not a national air total; "
            "outputs/pakemis_air_coverage_matrix.csv is the cell-by-cell record."
            % (len(sectors), ", ".join(whole + part)))


class AirAnnualGridWriter:
    """Opened once per configuration, fed one period's pollutant rasters at a time."""

    def __init__(self, path, grid, periods, configuration_id):
        from netCDF4 import Dataset
        from pkinv.report.annual_grid import write_frame
        self.path = path
        self.grid = grid
        self.periods = list(periods)
        self.index = {p[0]: i for i, p in enumerate(self.periods)}
        self.ds = Dataset(path, "w", format="NETCDF4")
        write_frame(self.ds, grid, self.periods)
        self.vars = {}
        for name in POLLUTANTS:
            var = self.ds.createVariable(
                VAR_OF[name], "f4", ("time", "lat", "lon"),
                zlib=True, complevel=4, shuffle=True, fletcher32=True,
                chunksizes=(1, 128, 128), fill_value=FILL)
            var.units = "Gg"
            var.long_name = ("%s emitted in the cell over the fiscal period, "
                             "covered sources only" % name)
            var.cell_methods = "time: sum area: sum"
            var.cell_measures = "area: cell_area"
            var.grid_mapping = "crs"
            var.comment = ("an interval-integrated cell MASS in Gg, native pollutant "
                           "mass (NOx as NO2, SO2 as SO2, PM2.5 and BC as particulate "
                           "mass), never CO2e and never summable across species - the "
                           "particulate strata contain one another. Cells outside "
                           "every district are _FillValue; an in-country zero is a "
                           "measurement and is stored as 0.")
            self.vars[name] = var
        self.outside = grid.province_id < 0
        ds = self.ds
        ds.Conventions = "CF-1.8"
        ds.title = ("PakEmis 0.05 degree annual air-pollutant emissions, "
                    "FY2015-16 to FY2023-24, %s configuration, covered sources only"
                    % ("reference" if configuration_id == "REF_2023_24"
                       else "ledger (L_HERD1624)"))
        ds.release_version = pkinv.__version__
        ds.grid_spec_id = GRID_SPEC["grid_spec_id"]
        ds.configuration_id = configuration_id
        ds.institution = "Pakistan Air Quality Initiative"
        ds.licence = "CC-BY-4.0"
        ds.coverage_scope = coverage_scope_text(covered_sectors())
        ds.spatial_view = (
            "no view dimension, deliberately: each pollutant layer rides its anchor "
            "greenhouse-gas stream's single declared placement - physical for most "
            "sectors, accounting (point of sale) for road-fuel transport, origin for "
            "waste. The three views are the greenhouse-gas cube's resolution "
            "(pakemis_grid_0p05_annual_ref_fy2015_16_fy2023_24.nc); the air family "
            "inherits one placement per source and does not claim the others.")
        ds.time_basis = ("nine Pakistani fiscal years, 1 July to 30 June. NOT "
                         "calendar years, and not relabelled as any: period_id "
                         "travels with every slice.")
        ds.configurations = (
            "REF_2023_24 and L_HERD1624 are separate files, never summed. The "
            "reference burns in households the dung the two HIES rounds observe "
            "(2018-19 and 2024-25 per-household anchors, interpolated). L_HERD1624 "
            "burns all the dung agriculture diverts in each year and differs in the "
            "residential dung-cake layers alone; every other layer is bit-identical "
            "to the reference. outputs/residential_configurations_by_year.csv is the "
            "activity record of both.")
        ds.conservation = ("per period, configuration and pollutant, the cells sum "
                           "to the national covered panel less the mass in "
                           "outputs/pakemis_air_unallocated_by_year.csv (the "
                           "aviation cruise class), published for exactly this "
                           "check.")
        ds.evidence = ("what each anchor stream's spatial pattern rests on, per "
                       "period - measured for the year or the reference year's "
                       "pattern rescaled - is in "
                       "outputs/pakemis_spatial_weights_by_year.csv, joined per "
                       "pollutant mass in "
                       "outputs/pakemis_air_spatial_support_by_year.csv.")

    def write_period(self, period_id, rasters):
        """One period's {pollutant: (lat, lon) float64 Gg} for this configuration."""
        t = self.index[period_id]
        for name in POLLUTANTS:
            annual = rasters.get(name)
            if annual is None:
                annual = np.zeros((self.grid.height, self.grid.width))
            annual = np.where(self.outside, FILL, annual)
            self.vars[name][t, :, :] = annual.astype(np.float32)

    def close(self):
        self.ds.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

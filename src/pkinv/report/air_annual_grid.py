"""Annual 0.05-degree native air cell masses, one file per configuration.

The streamed spatial build supplies each emitting-process vector and its period's
mass. Facility subsets and kiln types carry explicit spatial overrides; processes
without supported geography remain in the unallocated ledger. A nominal grid is
an allocation lattice, not observed activity at that resolution. Fiscal intervals,
configuration, coverage, placement boundaries and evidence are retained in the
file and associated records. Grid mass plus unallocated mass closes to the covered
panel separately for each period, configuration and pollutant.
"""

from pkinv.assets import asset_path
import os

import numpy as np

import pkinv
from pkinv.paths import OUTPUTS
from pkinv.core.gis.grid import GRID_SPEC
from pkinv.core import configurations as conf
from pkinv.core.reporting_window import CORE_SUFFIX

FILL = -9999.0
POLLUTANTS = ("BC", "CO", "NH3", "NMVOC", "NOx", "PM2.5", "SO2")
VAR_OF = {"BC": "bc_emissions", "CO": "co_emissions", "NH3": "nh3_emissions",
          "NMVOC": "nmvoc_emissions", "NOx": "nox_emissions",
          "PM2.5": "pm25_emissions", "SO2": "so2_emissions"}
def path_for(configuration):
    """One explicit configuration per file; the filename describes its contents."""
    return asset_path(OUTPUTS, "pakemis_air_grid_0p05_annual_%s_%s.nc" %
                      (conf.canonical(configuration).lower(), CORE_SUFFIX))


REF_PATH = path_for(conf.REFERENCE)
SURVEY_PATH = path_for(conf.LEDGER)


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
            "reported fiscal window (%s). A sector listed with species carries those alone; what "
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
                chunksizes=(1, min(128, grid.height), min(128, grid.width)), fill_value=FILL)
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
                           "every district are _FillValue; zero is a calculated zero "
                           "for the admitted sources, not evidence of complete coverage.")
            self.vars[name] = var
        self.outside = grid.province_id < 0
        ds = self.ds
        ds.Conventions = "CF-1.8"
        ds.title = ("PakEmis 0.05 degree annual air-pollutant emissions, %s to %s, "
                    "%s configuration, covered sources only" %
                    (self.periods[0][0], self.periods[-1][0], configuration_id))
        ds.release_version = pkinv.__version__
        ds.grid_spec_id = GRID_SPEC["grid_spec_id"]
        ds.configuration_id = configuration_id
        ds.institution = "Pakistan Air Quality Initiative"
        ds.licence = "See release product-level licensing and source attribution records"
        ds.geographic_licence_basis = "independent_primary_geography; ODbL alternatives excluded"
        ds.coverage_scope = coverage_scope_text(covered_sectors())
        ds.spatial_view = (
            "no view dimension, deliberately: each pollutant layer rides its anchor "
            "greenhouse-gas stream's single declared placement - physical for most "
            "sectors, accounting (point of sale) for road-fuel transport, origin for "
            "waste. The three views are the greenhouse-gas cube's resolution "
            "(pakemis_grid_0p05_annual_ref_fy2015_16_fy2024_25.nc); the air family "
            "inherits one placement per source and does not claim the others.")
        ds.time_basis = ("%d Pakistani fiscal years, 1 July to 30 June; "
                         "period_id and time bounds identify the exact intervals" % len(self.periods))
        ds.configurations = (
            "S_TAN, L_TAN, S_IPCC and L_IPCC are separate configurations, never summed. "
            "S uses survey-anchored household dung; L assumes all diverted dung is burned "
            "in households. TAN and IPCC identify the conserved nitrogen formulations. "
            "These structural choices carry no probabilities.")
        ds.release_boundary = ("residential gross appliance emissions, outdoor escape not "
                               "estimated; waste burning allocated at generation origin; "
                               "vertical injection and atmospheric chemical speciation unresolved")
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

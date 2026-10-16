"""Monthly air grids written from the same per-process spatial allocation as annual.

The AirSink supplies process-month masses while its source weight vector is
resident. This writer never redistributes an annual national map by one national
monthly profile. Files contain cell mass, not atmospheric concentration or flux.
"""
import datetime
import os
import numpy as np

from pkinv.assets import asset_path
from pkinv.core import monthly
from pkinv.core.reporting_window import CORE_SUFFIX
from pkinv.paths import OUTPUTS
from pkinv.report.air_annual_grid import AirAnnualGridWriter


def path_for(configuration):
    return asset_path(OUTPUTS, "pakemis_air_grid_0p05_monthly_%s_%s.nc" % (configuration.lower(), CORE_SUFFIX))


def month_bounds(periods):
    epoch = datetime.date(1970, 1, 1)
    result = []
    for period, _a, _b, _mid in periods:
        start = 2000 + int(period[-2:]) - 1
        for month in monthly.months_for(start):
            year, number = int(month[:4]), int(month[4:])
            first = datetime.date(year, number, 1)
            last = datetime.date(year + (number == 12), number % 12 + 1, 1)
            a, b = (first - epoch).days, (last - epoch).days
            result.append((month, a, b, (a + b) / 2))
    return result


class AirMonthlyGridWriter(AirAnnualGridWriter):
    def __init__(self, grid, periods, configuration):
        periods = list(periods)
        self.final_path = path_for(configuration)
        super().__init__(self.final_path + ".partial", grid, month_bounds(periods), configuration)
        self.ds.title = "PakEmis monthly air-pollutant allocation, %s, %s to %s" % (configuration, periods[0][0], periods[-1][0])
        self.ds.time_basis = "calendar months within the reported fiscal core; monthly support differs by emitting process"
        self.ds.variables["time"].long_name = "midpoint of calendar month"
        self.ds.variables["period_id"].long_name = "YYYYMM; no annual fiscal interval implied"
        for variable in self.vars.values():
            variable.long_name = variable.long_name.replace("fiscal period", "calendar month")
        self.ds.temporal_support = "pakemis_air_monthly.csv and pakemis_air_temporal_support.csv"
        self.ds.spatial_time_support = "source-process annual spatial weight held within each fiscal year; monthly source geography not observed"
        self.ds.conservation = "per month/configuration/pollutant: placed cell mass plus below_adm1 mass in pakemis_air_monthly_unallocated.csv equals national covered mass in pakemis_air_monthly.csv"
        self.ds.fitness_for_use = "allocated emissions; vertical injection, chemical speciation and household outdoor escape unresolved; no ambient concentrations"

    def close(self):
        if self.ds.isopen():
            super().close()
            os.replace(self.final_path + ".partial", self.final_path)

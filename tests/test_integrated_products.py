"""Cross-product closure of all released configurations and fiscal periods."""
import collections
import csv
import unittest

import netCDF4
import numpy as np
from pkinv.assets import asset_path
from pkinv.paths import OUTPUTS
from pkinv.core import configurations as conf
from pkinv.core.reporting_window import CORE_PERIOD_IDS
from pkinv.report.annual_grid import CORE
from pkinv.report.spatial_by_year import configuration_grid_path


def rows(name):
    with open(asset_path(OUTPUTS, name), newline="") as handle:
        yield from csv.DictReader(line for line in handle if not line.startswith("#"))


def totals(name, value):
    result = collections.defaultdict(float)
    for row in rows(name):
        if row[value] != "":
            result[(row["configuration_id"], row["period_id"], row["gas"]) ] += float(row[value])
    return result


class IntegratedProducts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.annual = totals("pakemis_ghg_configuration_atoms.csv", "emission_native_mass")

    def assert_closed(self, found, control, relative=1e-9, absolute=1e-5):
        self.assertEqual(set(found), set(control))
        for key, value in control.items():
            self.assertLessEqual(abs(found[key] - value), max(absolute, relative * abs(value)),
                                 (key, found[key], value))

    def test_all_configurations_have_exact_core_period_and_native_gases(self):
        self.assertEqual(set(self.annual), {(cfg, period, gas) for cfg in conf.ALL
                         for period in CORE_PERIOD_IDS for gas in ("CO2", "CH4", "N2O")})

    def test_months_and_provinces_close_to_own_configuration_annual_mass(self):
        self.assert_closed(totals("pakemis_ghg_configuration_monthly.csv", "emission_native_mass"), self.annual)
        self.assert_closed(totals("pakemis_ghg_configuration_adm1.csv", "emissions_Gg"), self.annual)
        self.assert_closed(totals("pakemis_ghg_configuration_adm1_monthly.csv", "emissions_Gg"), self.annual)

    def test_all_four_grids_plus_unallocated_mass_close_to_native_totals(self):
        found = totals("pakemis_ghg_configuration_unallocated.csv", "emissions_Gg")
        for cfg in conf.ALL:
            path = CORE if cfg == conf.REFERENCE else configuration_grid_path(cfg)
            with netCDF4.Dataset(path) as ds:
                self.assertEqual(cfg, ds.configuration_id)
                self.assertIn("ODbL alternatives excluded", ds.geographic_licence_basis)
                periods = [str(p) for p in ds.variables["period_id"][:]]
                self.assertEqual(list(CORE_PERIOD_IDS), periods)
                for index, period in enumerate(periods):
                    for gas in ("CO2", "CH4", "N2O"):
                        variable = ds.variables[gas.lower() + "_emissions"]
                        self.assertEqual("Gg", variable.units)
                        found[(cfg, period, gas)] += float(np.ma.sum(variable[index].astype("f8")))
        # NetCDF stores float32 cell mass; sum using float64 and allow its encoding error.
        self.assert_closed(found, self.annual, relative=2e-7, absolute=2e-5)

    def test_conditional_native_centres_match_annual_product(self):
        values = {}
        for row in rows("pakemis_ghg_conditional_uncertainty.csv"):
            if row["sector_id"] != "national_covered" or row["species_or_metric"] not in ("CO2", "CH4", "N2O"):
                continue
            key = (row["configuration_id"], row["period_id"], row["species_or_metric"])
            values[key] = float(row["deterministic_quantity"])
            self.assertEqual("Gg", row["unit"])
            self.assertEqual(10000, int(row["draws"]))
            self.assertLessEqual(float(row["P2_5_quantity"]), float(row["P97_5_quantity"]))
        self.assert_closed(values, self.annual, relative=1e-8, absolute=1e-4)


if __name__ == "__main__":
    unittest.main()

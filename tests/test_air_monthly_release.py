"""Release-level air checks across actual monthly exports, native grids and draws."""
import collections
import unittest

import numpy as np
from netCDF4 import Dataset

from pkinv.core import configurations as conf
from pkinv.core.io import read_rows
from pkinv.core.reporting_window import CORE_FY_ENDS, CORE_PERIOD_IDS
from pkinv.paths import OUTPUTS
from pkinv.report.air_annual import ROLLUP_OUT
from pkinv.report.air_annual_grid import VAR_OF
from pkinv.report.air_monthly import OUT
from pkinv.report.air_monthly_grid import path_for
from pkinv.report.air_spatial_by_year import MONTHLY_UNALLOC_OUT


class MonthlyRelease(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.annual, cls.monthly, cls.unallocated = (collections.defaultdict(float) for _ in range(3))
        cls.proxy_classes = collections.defaultdict(set)
        for row in read_rows(ROLLUP_OUT):
            cls.annual[row["period_id"], row["configuration_id"], row["pollutant"]] += float(row["emissions_Gg"])
        for row in read_rows(OUT):
            cls.monthly[row["month"], row["configuration_id"], row["pollutant"]] += float(row["emissions_Gg"])
            if row["sector_id"] == "aviation" or row["source_class_id"] == "fug_petrol_distribution_refuelling":
                key = row["period_id"], row["configuration_id"], row["sector_id"]
                cls.proxy_classes[key].add(row["temporal_evidence_class"])
        for row in read_rows(MONTHLY_UNALLOC_OUT):
            if row["level"] in ("below_adm1", "below_national"):
                cls.unallocated[row["month"], row["configuration_id"], row["pollutant"]] += float(row["emissions_Gg"])

    def test_exported_customer_profiles_do_not_become_observed_flight_or_distribution_activity(self):
        expected = {(pid, cfg, sector) for pid in CORE_PERIOD_IDS for cfg in conf.AIR_ALL
                    for sector in ("aviation", "fugitives")}
        self.assertEqual(set(self.proxy_classes), expected)
        for key, classes in self.proxy_classes.items():
            self.assertTrue(classes <= {"TE3", "TE4"}, (key, classes))
        ghg = collections.defaultdict(set)
        for row in read_rows(OUTPUTS + "/pakemis_ghg_configuration_monthly.csv"):
            if row["sector_id"] == "aviation":
                ghg[row["period_id"], row["configuration_id"]].add(row["temporal_evidence_class"])
        self.assertEqual(set(ghg), {(pid, cfg) for pid in CORE_PERIOD_IDS for cfg in conf.ALL})
        for key, classes in ghg.items():
            self.assertTrue(classes <= {"TE3", "TE4"}, (key, classes))

    def test_exported_months_close_to_the_current_annual_configurations(self):
        totals = collections.defaultdict(float)
        for (month, cfg, pol), value in self.monthly.items():
            year = int(month[:4]) - (int(month[4:]) <= 6)
            totals["FY%d-%02d" % (year, (year + 1) % 100), cfg, pol] += value
        self.assertEqual(set(totals), set(self.annual))
        self.assertEqual(len(totals), len(CORE_FY_ENDS) * len(conf.AIR_ALL) * 7)
        # Rollup decimal formatting accumulates at source/category grain.
        for key, value in self.annual.items():
            self.assertAlmostEqual(value, totals[key], delta=max(1e-5, abs(value) * 1e-7), msg=str(key))

    def test_actual_monthly_grids_plus_unallocated_close_for_every_species(self):
        for cfg in conf.AIR_ALL:
            with Dataset(path_for(cfg)) as dataset:
                months = list(map(str, dataset["period_id"][:]))
                self.assertEqual(len(months), 120)
                self.assertEqual(months[0], "201507")
                self.assertEqual(months[-1], "202506")
                for pol, name in VAR_OF.items():
                    self.assertEqual(dataset[name].units, "Gg")
                    self.assertIn("calendar month", dataset[name].long_name)
                    self.assertEqual(dataset[name].cell_methods, "time: sum area: sum")
                    values = np.ma.filled(dataset[name][:], 0).sum(axis=(1, 2), dtype=np.float64)
                    for month, placed in zip(months, values):
                        expected = self.monthly[month, cfg, pol]
                        actual = placed + self.unallocated[month, cfg, pol]
                        self.assertAlmostEqual(actual, expected,
                            delta=max(2e-6, expected * 2e-6), msg=str((month, cfg, pol)))


class ConditionalRelease(unittest.TestCase):
    def test_final_intervals_and_paired_changes_keep_configuration_and_draw_count(self):
        levels = read_rows(OUTPUTS + "/pakemis_air_conditional_uncertainty.csv")
        changes = read_rows(OUTPUTS + "/pakemis_air_trend_uncertainty.csv")
        controls = {}
        for row in levels:
            self.assertEqual(int(row["draws"]), 10000)
            self.assertEqual(row["interval_kind"], "conditional_parameter_percentiles")
            self.assertLessEqual(float(row["P2_5_Gg"]), float(row["P50_Gg"]))
            self.assertLessEqual(float(row["P50_Gg"]), float(row["P97_5_Gg"]))
            self.assertLess(float(row["max_nitrogen_closure_residual_kgN"]), 1e-4)
            controls[row["period_id"], row["configuration_id"], row["pollutant"],
                     row["sector_id"], row["dependence_case"]] = float(row["deterministic_Gg"])
        self.assertEqual({r["configuration_id"] for r in levels}, set(conf.AIR_ALL))
        for row in changes:
            key = tuple(row[k] for k in ("configuration_id", "pollutant", "sector_id", "dependence_case"))
            expected = controls[(row["end_period"],) + key] - controls[(row["start_period"],) + key]
            self.assertAlmostEqual(float(row["deterministic_change_Gg"]), expected, delta=1e-8)
            self.assertEqual(row["interval_kind"], "paired_change_parameter_percentiles")


if __name__ == "__main__":
    unittest.main()

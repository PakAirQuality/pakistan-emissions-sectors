"""The household HFC equipment bank: a band per year, a floor, from the HIES stock indicator."""
import csv
import os
import unittest

from pkinv.paths import OUTPUTS

OUT = os.path.join(OUTPUTS, "pakemis_hfc_bank_series.csv")
YEARS = ["%d-%02d" % (y, (y + 1) % 100) for y in range(2015, 2024)]


def rows():
    with open(OUT, encoding="utf-8") as h:
        return list(csv.DictReader(l for l in h if not l.startswith("#")))


class HfcBankSeries(unittest.TestCase):
    def test_nine_years_three_applications_and_a_floor_total(self):
        r = rows()
        totals = [x for x in r if x["application"].startswith("household bank total")]
        self.assertEqual([x["fiscal_year"] for x in totals], YEARS)
        for fy in YEARS:
            apps = {x["application"] for x in r if x["fiscal_year"] == fy}
            self.assertEqual(len(apps), 4, fy)

    def test_bands_are_bands_and_the_floor_is_the_sum(self):
        r = rows()
        for fy in YEARS:
            parts = [x for x in r if x["fiscal_year"] == fy and not x["application"].startswith("household")]
            total = next(x for x in r if x["fiscal_year"] == fy and x["application"].startswith("household"))
            for x in parts:
                self.assertLess(float(x["emissions_mt_co2e_low"]), float(x["emissions_mt_co2e_high"]))
            self.assertAlmostEqual(sum(float(x["emissions_mt_co2e_low"]) for x in parts), float(total["emissions_mt_co2e_low"]), places=4)
            self.assertAlmostEqual(sum(float(x["emissions_mt_co2e_high"]) for x in parts), float(total["emissions_mt_co2e_high"]), places=4)
            self.assertIn("FLOOR", total["status"])

    def test_extrapolation_is_flagged_and_the_stock_rises(self):
        r = rows()
        ref = {x["fiscal_year"]: x for x in r if x["application"] == "domestic refrigeration"}
        for fy in ("2015-16", "2016-17", "2017-18"):
            self.assertIn("EXTRAPOLATED", ref[fy]["stock_basis"])
        self.assertIn("interpolated", ref["2020-21"]["stock_basis"])
        self.assertLess(float(ref["2018-19"]["stock_units"]), float(ref["2023-24"]["stock_units"]))

    def test_the_household_floor_sits_far_below_the_supply_lanes(self):
        total = next(x for x in rows() if x["fiscal_year"] == "2023-24" and x["application"].startswith("household"))
        self.assertLess(float(total["emissions_mt_co2e_high"]), 4.42)      # the consumption-based bounded bank
        self.assertIn("cannot absorb", total["note"])


if __name__ == "__main__":
    unittest.main()

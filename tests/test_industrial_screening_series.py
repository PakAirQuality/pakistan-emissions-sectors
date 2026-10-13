"""The remaining industrial categories as nine-year screening series: typed, outside every total."""
import csv
import os
import unittest

from pkinv.paths import OUTPUTS

OUT = os.path.join(OUTPUTS, "pakemis_industrial_screening_series.csv")
SCREENING = os.path.join(OUTPUTS, "ippu_chemicals_screening_2024.csv")
YEARS = ["%d-%02d" % (y, (y + 1) % 100) for y in range(2015, 2024)]


def rows():
    with open(OUT, encoding="utf-8") as h:
        return list(csv.DictReader(l for l in h if not l.startswith("#")))


class IndustrialScreeningSeries(unittest.TestCase):
    def test_every_category_carries_all_nine_years(self):
        by = {}
        for x in rows():
            by.setdefault(x["category"], []).append(x["fiscal_year"])
        self.assertEqual(set(by), {"Soda ash production", "Iron and steel production", "Lubricant use",
                                   "Industrial wastewater - Sugar refining", "Industrial wastewater - Pulp and paper (combined)"})
        for cat, years in by.items():
            self.assertEqual(years, YEARS, cat)

    def test_soda_ash_is_na_in_ippu_with_no_number(self):
        for x in rows():
            if x["ipcc_code"] == "2.B.7":
                self.assertEqual((x["central_mt_co2e"], x["low_mt_co2e"], x["high_mt_co2e"]), ("", "", ""))
                self.assertIn("Solvay", x["method"])
                self.assertTrue(x["band_kind"].startswith("NA"))

    def test_steel_reference_year_matches_the_chemicals_screening(self):
        steel = next(float(x["central_mt_co2e"]) for x in rows() if x["ipcc_code"] == "2.C.1" and x["fiscal_year"] == "2023-24")
        with open(SCREENING, encoding="utf-8") as h:
            scr = next(r for r in csv.DictReader(l for l in h if not l.startswith("#")) if "steel" in r.get("stream", "").lower())
        self.assertAlmostEqual(steel, float(scr["bracket_high_Mt"]), places=4)

    def test_lubricants_are_tier_1_points_on_ocac_sales(self):
        for x in rows():
            if x["ipcc_code"] == "2.D.1":
                self.assertEqual(x["central_mt_co2e"], x["low_mt_co2e"])
                self.assertIn("OCAC", x["activity_source"])
                self.assertGreater(float(x["central_mt_co2e"]), 0.03)
                self.assertLess(float(x["central_mt_co2e"]), 0.12)

    def test_wastewater_is_a_band_with_no_central_coded_waste(self):
        for x in rows():
            if x["ipcc_code"] == "4.D.2":
                self.assertEqual(x["central_mt_co2e"], "")
                self.assertLess(float(x["low_mt_co2e"]), float(x["high_mt_co2e"]))
                self.assertEqual(x["sector_code"], "waste")
                self.assertIn("economic view only", x["status"])


if __name__ == "__main__":
    unittest.main()

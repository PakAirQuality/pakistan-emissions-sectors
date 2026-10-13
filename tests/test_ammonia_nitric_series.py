"""Ammonia and nitric acid as nine-year series: the back-cast the boundary rule demands; outside the reference."""
import csv
import os
import unittest

from pkinv.paths import OUTPUTS

OUT = os.path.join(OUTPUTS, "pakemis_ammonia_nitric_series.csv")
TOTALS = os.path.join(OUTPUTS, "ippu_totals_2024.csv")


def rows():
    with open(OUT, encoding="utf-8") as h:
        return list(csv.DictReader(l for l in h if not l.startswith("#")))


class AmmoniaNitricSeries(unittest.TestCase):
    def test_nine_periods_plus_the_labelled_extra_year(self):
        r = rows()
        for code in ("2.B.1", "2.B.2"):
            years = [x["fiscal_year"] for x in r if x["ipcc_code"] == code]
            self.assertEqual(years[:9], ["%d-%02d" % (y, (y + 1) % 100) for y in range(2015, 2024)])
            self.assertEqual([x["in_reference_window"] for x in r if x["ipcc_code"] == code][9:], ["no (extra year)"])

    def test_the_reference_year_reproduces_the_reference_component(self):
        # rc52: ammonia is a reference component; the series and the engine ride the same
        # NFDC production, factor and recovery, so they must agree to the rounding of the table
        with open(TOTALS, encoding="utf-8") as h:
            ref = next(float(r["co2e_Mt_AR5"]) for r in csv.DictReader(l for l in h if not l.startswith("#")) if r["category"] == "Ammonia production")
        central = next(float(x["central_mt_co2e"]) for x in rows() if x["ipcc_code"] == "2.B.1" and x["fiscal_year"] == "2023-24")
        self.assertAlmostEqual(central, ref, places=4)

    def test_ammonia_envelope_is_a_method_envelope_around_the_central(self):
        for x in rows():
            if x["ipcc_code"] != "2.B.1":
                continue
            lo, c, hi = float(x["envelope_low_mt"]), float(x["central_mt_co2e"]), float(x["envelope_high_mt"])
            self.assertLess(lo, c); self.assertLess(c, hi)
            self.assertIn("not a confidence interval", x["envelope_kind"])
            self.assertIn("reference component since rc52", x["status"])

    def test_nitric_is_a_pair_with_no_central_and_sits_above_the_plant(self):
        for x in rows():
            if x["ipcc_code"] != "2.B.2":
                continue
            self.assertEqual(x["central_mt_co2e"], "")
            self.assertLess(float(x["abated_mt_co2e"]), float(x["unabated_mt_co2e"]))
            self.assertIn("DERIVED", x["activity_unit"])
            if x["fiscal_year"] == "2021-22":
                self.assertIn("consistent", x["plant_check"])


if __name__ == "__main__":
    unittest.main()

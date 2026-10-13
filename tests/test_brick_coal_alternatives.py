"""Brick-kiln coal alternatives: bounded, labelled, no manufactured central; HDIP's footnote carried."""
import csv
import os
import unittest

from pkinv.paths import OUTPUTS

OUT = os.path.join(OUTPUTS, "pakemis_brick_coal_alternatives.csv")


def rows():
    with open(OUT, encoding="utf-8") as h:
        return list(csv.DictReader(l for l in h if not l.startswith("#")))


class BrickAlternatives(unittest.TestCase):
    def test_nine_years_no_preferred_estimate(self):
        r = rows()
        self.assertEqual([x["fiscal_year"] for x in r], ["%d-%02d" % (y, (y + 1) % 100) for y in range(2015, 2024)])
        for x in r:
            self.assertEqual(x["preferred_estimate"], "", x["fiscal_year"])
            self.assertTrue(x["decision_rule_row"].startswith("3"))

    def test_the_official_value_is_named_a_residual_by_hdip_itself(self):
        for x in rows():
            self.assertIn("Estimated by deducting other uses of indigenous coal from the total production", x["what_the_official_value_is"])

    def test_the_intensity_sensitivity_is_read_at_constant_output(self):
        by = {x["fiscal_year"]: x for x in rows()}
        # official kt x 1e9 g / 82.5e9 bricks
        self.assertAlmostEqual(float(by["2023-24"]["implied_g_per_brick_at_2018_output"]), 1129 * 1e9 / 82.5e9, places=1)
        self.assertIn("far below", by["2023-24"]["intensity_reading"])
        for x in by.values():
            self.assertEqual((x["constant_output_low_kt"], x["constant_output_high_kt"]), ("12771", "15180"))

    def test_the_intensity_band_is_measured_and_pakistani(self):
        """rc53 Wave D: the 70-100 g/brick pair carried here until rc52 appears in NO held document -
        the CCAC fact sheet prints only aggregate tonnes. It is replaced by 155 g (zig-zag) and 184 g
        (FCBTK), measured on 60 kilns in Faisalabad in 2023."""
        text = open(os.path.join(OUTPUTS, "pakemis_brick_coal_alternatives.csv"), encoding="utf-8").read()
        self.assertNotIn("70-100 g", text)
        for x in rows():
            self.assertIn("155-184 g/brick", x["intensity_reading"])

    def test_the_reading_names_its_own_denominator_bias(self):
        """The brick count is the disputed quantity, so a low implied intensity is evidence about the
        PAIR (tonnage, brick count) and must not be read as evidence about the tonnage alone."""
        for x in rows():
            if "far below" in x["intensity_reading"]:
                self.assertIn("on any reading of the pair", x["intensity_reading"])
            else:
                self.assertIn("biased low", x["intensity_reading"])
            self.assertIn("sensitivity", x["note"])

    def test_the_band_exists_only_where_a_nepra_lane_does(self):
        by = {x["fiscal_year"]: x for x in rows()}
        for fy in ("2015-16", "2016-17", "2017-18", "2018-19"):
            self.assertEqual(by[fy]["band_low_kt"], "")
        for fy in ("2019-20", "2020-21", "2021-22", "2022-23", "2023-24"):
            self.assertLessEqual(float(by[fy]["band_low_kt"]), float(by[fy]["band_high_kt"]))


if __name__ == "__main__":
    unittest.main()

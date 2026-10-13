"""The nine-year crop district panel: closure, concordance and the exclusion that must fire.

WHY THIS FILE EXISTS. The panel is the first per-year district crop evidence in the
inventory, and it arrived from a dashboard whose ids are not unique, whose names carry a
typo and a division-grain row, and whose rice payloads hold two cells that are corrupt by
the source's own arithmetic. Every one of those facts is a RULE in the builder; this file
holds the rules to their outcomes.
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

from pkinv.paths import DATA

PANEL = asset_path(DATA, "activity", "agriculture", "crop_district_panel.csv")
ES = asset_path(DATA, "activity", "agriculture", "es_fiscal_series.csv")


def _rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(l for l in handle if not l.startswith("#")))


@unittest.skipUnless(os.path.exists(PANEL), "the crop district panel has not been built")
class TestThePanelClosesAndItsRulesFired(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = _rows(PANEL)
        cls.es = {(r["fiscal_label"], r["item"]): float(r["value"]) for r in _rows(ES)}

    def test_nine_periods_five_crops(self):
        periods = {r["period_id"] for r in self.rows}
        crops = {r["crop"] for r in self.rows}
        self.assertEqual(len(periods), 9)
        self.assertEqual(crops, {"maize", "rice", "sugarcane", "wheat", "cotton"})

    def test_the_district_sums_reproduce_the_economic_survey_controls(self):
        """The API's own national closure, now held per panel year rather than spot-checked.

        The included rows (excluded_corrupt left OUT) must reproduce the Economic Survey
        area control within 1.5 percent for every crop-year the survey covers - rice's two
        corrupt-cell years close BECAUSE the exclusion fired, which is the point. Wheat
        2023-24 is the one known vintage gap (the survey printed the provisional 9,632
        against the dashboard's revised 9,734) and carries its own wider bound.
        """
        from collections import defaultdict
        sums = defaultdict(float)
        for r in self.rows:
            if r["qa_flag"] == "excluded_corrupt":
                continue
            sums[(r["period_id"], r["crop"])] += float(r["area_kha"])
        checked = 0
        for (period, crop), got in sorted(sums.items()):
            key = ("FY" + period[2:] if not period.startswith("FY") else period,
                   crop + "_area_ha")
            key = (period, crop + "_area_ha")
            if key not in self.es:
                continue
            control = self.es[key] / 1000.0
            bound = 0.015 if not (crop == "wheat" and period == "FY2023-24") else 0.02
            self.assertLess(abs(got - control) / control, bound,
                            "%s %s: panel %.1f vs ES %.1f" % (period, crop, got, control))
            checked += 1
        self.assertGreaterEqual(checked, 40, "the ES join stopped matching")

    def test_the_exclusion_fired_in_all_seven_corrupt_years(self):
        """A three-year spot check first found two corrupt years; this panel's own closure
        test forced the full enumeration and found SEVEN - every year Sujawal's rice row
        appears, it equals the payload's whole excess over the national control. The two
        clean years have no Sujawal rice row, so exactly seven exclusions must fire."""
        excluded = {(r["period_id"], r["crop"]) for r in self.rows
                    if r["qa_flag"] == "excluded_corrupt"}
        self.assertEqual(excluded, {("FY%s" % y, "rice") for y in
                                    ("2015-16", "2016-17", "2017-18", "2018-19",
                                     "2019-20", "2020-21", "2021-22")})

    def test_every_adm2_id_is_canonical(self):
        canon = {r["adm2_id"] for r in _rows(asset_path(DATA, "adm2_canonical.csv"))}
        for r in self.rows:
            if r["adm2_id"]:
                self.assertIn(r["adm2_id"], canon, r["source_row"])

    def test_pooled_rows_declare_their_split(self):
        for r in self.rows:
            if "pooled_parent" in r["qa_flag"]:
                # rc47 Wave 1: the old string asserted a provenance that never executed
                # (the split was always the uniform fallback behind a broken key).
                # The rule is now uniform BY DECLARATION and the value must prove it.
                self.assertIn("uniform within-pool split", r["split_rule"], r["source_row"])
                import re as _re
                frac = float(_re.search(r"([\d.]+)", r["split_rule"]).group(1))
                self.assertAlmostEqual(
                    frac * round(1.0 / frac), 1.0, places=3,
                    msg="a pooled split that is not 1/n contradicts the declared rule")


if __name__ == "__main__":
    unittest.main()

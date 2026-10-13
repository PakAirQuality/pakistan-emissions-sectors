"""The OGRA gas-class series: eight classes x ten fiscal years, spot-pinned to the
reports' own printed numbers, the scanned edition a typed gap and the 2022-23
vocabulary drift preserved (Domestic / Industry / Fertilizer FEED) - the class
semantics are the point of the product."""

from pkinv.assets import asset_path
import csv
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "outputs", "ogra_gas_class_series.csv")


def rows():
    with open(OUT, encoding="utf-8") as h:
        return list(csv.DictReader(l for l in h if not l.startswith("#")))


class OgraGasClasses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows()

    def test_the_grid_is_complete(self):
        self.assertEqual(len(self.rows), 80)   # 8 classes x 10 fiscal years
        self.assertEqual(len({r["period_id"] for r in self.rows}), 10)
        self.assertEqual(
            {r["status"] for r in self.rows},
            {"extracted", "extracted_drifted_vocabulary",
             "typed_gap_scanned_edition", "not_reported_separately"})

    def test_printed_numbers_are_pinned(self):
        """The transcription register's rule: pin what the source itself prints."""
        pins = {("FY2023-24", "general_industry"): "291",
                ("FY2023-24", "captive_power"): "287",
                ("FY2023-24", "fertilizer"): "756",
                ("FY2015-16", "captive_power"): "389",
                ("FY2015-16", "general_industry"): "320",
                ("FY2022-23", "fertilizer"): "629"}
        got = {(r["period_id"], r["gas_class"]): r["mmcfd_total"] for r in self.rows}
        for key, want in pins.items():
            self.assertEqual(got[key], want, key)

    def test_the_scanned_edition_is_a_typed_gap(self):
        fy21 = [r for r in self.rows if r["period_id"] == "FY2020-21"]
        self.assertEqual(len(fy21), 8)
        for r in fy21:
            self.assertEqual(r["status"], "typed_gap_scanned_edition")
            self.assertEqual(r["mmcfd_total"], "")

    def test_the_2022_23_drift_is_recorded(self):
        drift = {r["gas_class"]: r for r in self.rows if r["period_id"] == "FY2022-23"}
        self.assertIn("Fertilizer Feed", drift["fertilizer"]["note"])
        self.assertIn("Domestic", drift["residential"]["note"])
        self.assertEqual(drift["cement"]["status"], "not_reported_separately")
        self.assertEqual(drift["fertilizer"]["class_comparable"], "no")

    def test_systems_sum_to_the_country_total(self):
        for r in self.rows:
            if r["status"] != "extracted":
                continue
            parts = sum(float(r[c]) for c in ("mmcfd_sngpl", "mmcfd_ssgcl", "mmcfd_independent"))
            self.assertAlmostEqual(parts, float(r["mmcfd_total"]), delta=2.5,
                                   msg="%s %s" % (r["period_id"], r["gas_class"]))


class TheExtractionValidatesTheHeldIngests(unittest.TestCase):
    """The OCAC rule applied again: a re-extraction of already-ingested tables is
    only worth shipping as a CHECK. Where the class series and the held ingests
    (gas_consumption.csv, captive_gas.csv) both carry a class-comparable cell,
    they must agree to 1 MMCFD (rounding sources differ by one for FY2023-24
    captive); the FY2022-23 reclassified edition is class_comparable=no and the
    scanned FY2020-21 is a gap the ingests cover by OCR."""

    @classmethod
    def setUpClass(cls):
        cls.mine = {(r["period_id"], r["gas_class"]): r for r in rows()}
        root = os.path.dirname(HERE)
        with open(asset_path(root, "data", "activity", "industry", "gas_consumption.csv"), encoding="utf-8") as h:
            cls.industry = list(csv.DictReader(h))
        with open(asset_path(root, "data", "activity", "power", "captive_gas.csv"), encoding="utf-8") as h:
            cls.captive = list(csv.DictReader(h))

    @staticmethod
    def fy(end):
        return "FY%d-%s" % (int(end) - 1, str(int(end))[2:])

    def check(self, period, cls_key, ingest_total):
        mine = self.mine[(period, cls_key)]
        if mine["class_comparable"] != "yes":
            return  # drifted or gap cells are exempt by declaration, not silence
        self.assertAlmostEqual(float(mine["mmcfd_total"]), float(ingest_total), delta=1.0,
                               msg="%s %s" % (period, cls_key))

    def test_general_industry_and_cement_agree(self):
        for r in self.industry:
            key = "general_industry" if r["stream"] == "General Industry" else "cement"
            self.check(self.fy(r["fiscal_year"]), key, r["total_mmcfd"])

    def test_captive_agrees(self):
        for r in self.captive:
            self.check(self.fy(r["fiscal_year"]), "captive_power", r["total_mmcfd"])

    def test_the_drifted_year_is_declared_not_silent(self):
        drifted = [r for r in rows() if r["period_id"] == "FY2022-23" and r["status"].startswith("extracted")]
        self.assertTrue(drifted)
        for r in drifted:
            self.assertEqual(r["class_comparable"], "no", r["gas_class"])


if __name__ == "__main__":
    unittest.main()

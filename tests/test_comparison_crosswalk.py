"""The comparison crosswalk declares the terms of every external comparison."""
import csv
import io
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs", "pakemis_comparison_crosswalk.csv")
BTR = os.path.join(ROOT, "outputs", "pakemis_btr_comparison.csv")


def rows(path):
    with io.open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheCrosswalk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows(OUT)

    def test_every_btr_row_is_crosswalked_and_year_matched(self):
        """The BTR's inventory year 2020-21 is a Pakistani fiscal year by its own statement,
        and the comparison uses the inventory's own FY2020-21: same basis, no blend."""
        btr = {"btr:%s" % r["pakemis_codes"] for r in rows(BTR)}
        here = {r["comparison_id"] for r in self.rows if r["kind"] == "BTR category row"}
        self.assertEqual(btr, here)
        for r in self.rows:
            if r["kind"] == "BTR category row":
                self.assertEqual(r["comparator_year_basis"], "FY2020-21")
                self.assertIn("FY2020-21", r["pakemis_year_basis"])
                self.assertEqual(r["year_match"], "same fiscal year")

    def test_every_row_states_metric_units_boundary_and_independence(self):
        for r in self.rows:
            for col in ("source", "gas_metric", "units", "category_boundary",
                        "independence_class", "year_match"):
                self.assertTrue(r[col].strip(), (r["comparison_id"], col))
        self.assertTrue(any(r["year_match"] == "same basis" for r in self.rows))
        self.assertTrue(any("fiscal vs calendar" in r["year_match"] for r in self.rows))

    def test_it_regenerates_identically(self):
        before = open(OUT, "rb").read()
        run = subprocess.run([sys.executable, "-m", "pkinv.report.comparison_crosswalk"],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        self.assertEqual(before, open(OUT, "rb").read())


if __name__ == "__main__":
    unittest.main()

"""The mass-weighted spatial evidence taxonomy: closed vocabulary, complete cells, and
shares that sum to the period they describe."""
import csv
import io
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLASSES = os.path.join(ROOT, "outputs", "pakemis_spatial_basis_classes.csv")
SHARES = os.path.join(ROOT, "outputs", "pakemis_spatial_basis_shares.csv")
SECTOR = os.path.join(ROOT, "outputs", "pakemis_spatial_basis_shares_by_sector.csv")
SOURCE = os.path.join(ROOT, "outputs", "semantic", "fact_spatial_basis_year.csv")
ADM1 = os.path.join(ROOT, "outputs", "semantic", "fact_adm1_year.csv")


def rows(path):
    with io.open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheTaxonomy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classes = rows(CLASSES)
        cls.shares = rows(SHARES)
        cls.sector = rows(SECTOR)
        cls.source = rows(SOURCE)

    def test_the_vocabulary_is_closed_in_both_directions(self):
        declared = {r["spatial_time_basis"] for r in self.classes}
        used = {r["spatial_time_basis"] for r in self.source}
        self.assertEqual(used - declared, set(), "the registry uses an undefined class")
        self.assertEqual(declared - {r["spatial_time_basis"] for r in self.shares}, set())
        for r in self.classes:
            for col in ("plain_name", "definition", "what_it_supports", "what_it_does_not_support"):
                self.assertTrue(r[col].strip(), (r["spatial_time_basis"], col))

    def test_every_period_times_class_cell_is_printed_and_sums_to_one(self):
        periods = sorted({r["period_id"] for r in self.source})
        n_classes = len(self.classes)
        for p in periods:
            cells = [r for r in self.shares if r["period_id"] == p]
            self.assertEqual(len(cells), n_classes, p)
            self.assertAlmostEqual(sum(float(r["share_of_period"]) for r in cells), 1.0, places=5)
            self.assertAlmostEqual(sum(float(r["co2e_Mt_AR5"]) for r in cells),
                                   float(cells[0]["period_total_Mt"]), places=4)

    def test_the_period_total_is_the_province_table_total(self):
        adm1 = {}
        for r in rows(ADM1):
            if (r.get("co2e_Mt_AR5") or "").strip():
                adm1[r["period_id"]] = adm1.get(r["period_id"], 0.0) + float(r["co2e_Mt_AR5"])
        for r in self.shares:
            self.assertAlmostEqual(float(r["period_total_Mt"]), adm1[r["period_id"]], places=3,
                                   msg=r["period_id"])

    def test_the_sector_table_sums_to_the_national_one(self):
        for p in sorted({r["period_id"] for r in self.shares}):
            for c in {r["spatial_time_basis"] for r in self.classes}:
                nat = next(float(r["co2e_Mt_AR5"]) for r in self.shares
                           if r["period_id"] == p and r["spatial_time_basis"] == c)
                sec = sum(float(r["co2e_Mt_AR5"]) for r in self.sector
                          if r["period_id"] == p and r["spatial_time_basis"] == c)
                self.assertAlmostEqual(nat, sec, places=5, msg=(p, c))

    def test_the_backcast_class_is_a_real_cell_not_a_label(self):
        """Transport and industry ride the reference shape before FY2021-22 and their own
        provincial sales after; a zero printed for the later years is a fact, not a hole."""
        bc = {r["period_id"]: float(r["co2e_Mt_AR5"]) for r in self.shares
              if r["spatial_time_basis"] == "reference_shape_backcast"}
        self.assertGreater(bc["FY2015-16"], 1.0)
        self.assertEqual(bc["FY2023-24"], 0.0)

    def test_it_regenerates_identically(self):
        before = tuple(open(p, "rb").read() for p in (CLASSES, SHARES, SECTOR))
        run = subprocess.run([sys.executable, "-m", "pkinv.report.spatial_basis_taxonomy"],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        self.assertEqual(before, tuple(open(p, "rb").read() for p in (CLASSES, SHARES, SECTOR)))


if __name__ == "__main__":
    unittest.main()

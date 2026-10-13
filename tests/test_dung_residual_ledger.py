"""The unresolved dung residual's nitrogen and volatile solids close on the engine's chain."""
import csv
import io
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs", "pakemis_dung_residual_ledger.csv")
LEDGER = os.path.join(ROOT, "outputs", "residential_dung_ledger_2024.csv")


def rows(path):
    with io.open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheResidualLedger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows(OUT)
        cls.ledger = {(r["configuration"], r["claimant"][:9]): float(r["Mt_air_dry"])
                      for r in rows(LEDGER)}

    def test_the_species_rows_sum_to_the_all_row(self):
        species = [r for r in self.rows if r["species"] != "ALL"]
        total = next(r for r in self.rows if r["species"] == "ALL")
        for col in ("diverted_N_kt", "diverted_VS_kt", "unresolved_N_kt", "unresolved_VS_kt",
                    "diverted_air_dry_Mt", "unresolved_air_dry_Mt"):
            self.assertAlmostEqual(sum(float(r[col]) for r in species), float(total[col]),
                                   places=2, msg=col)

    def test_it_closes_on_the_residential_ledger(self):
        total = next(r for r in self.rows if r["species"] == "ALL")
        self.assertAlmostEqual(float(total["diverted_air_dry_Mt"]),
                               self.ledger[("both", "Diverted ")], places=3)
        self.assertAlmostEqual(float(total["unresolved_air_dry_Mt"]),
                               self.ledger[("S", "UNRESOLVE")], places=3)

    def test_nitrogen_is_not_cake_and_the_chain_says_so(self):
        """N -> VS -> dry solids -> air-dry; the ratio VS/N differs by species, so a
        reader who multiplied N by one factor would be wrong, and the chain column names
        the species' own rates."""
        ratios = {r["species"]: float(r["diverted_VS_kt"]) / float(r["diverted_N_kt"])
                  for r in self.rows if r["species"] != "ALL"}
        self.assertGreater(max(ratios.values()) / min(ratios.values()), 1.2)
        for r in self.rows:
            if r["species"] != "ALL":
                self.assertIn("vs_rate_%s" % r["species"], r["chain"])
                self.assertIn("assumed", r["note"])

    def test_it_regenerates_identically(self):
        before = open(OUT, "rb").read()
        run = subprocess.run([sys.executable, "-m", "pkinv.report.dung_residual_ledger"],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        self.assertEqual(before, open(OUT, "rb").read())


if __name__ == "__main__":
    unittest.main()

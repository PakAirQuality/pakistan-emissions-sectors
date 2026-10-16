"""The enteric bridge to the BTR: a declared transcription that sums to the printed total,
compared species by species with the inventory's own FY2020-21 estimate."""
import csv
import io
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs", "pakemis_enteric_btr_bridge.csv")
BTR = os.path.join(ROOT, "outputs", "pakemis_btr_comparison.csv")


def rows(path):
    with io.open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows(OUT)
        cls.total = next(r for r in cls.rows if r["species"] == "TOTAL")

    def test_the_transcription_sums_to_the_btr_comparison_pair(self):
        pair = next(r for r in rows(BTR) if r["subject"] == "Enteric fermentation")
        self.assertAlmostEqual(float(self.total["btr_Mt_co2e"]), float(pair["btr_Mt_co2e"]), places=2)
        self.assertAlmostEqual(float(self.total["pakemis_Mt_co2e_AR5"]), float(pair["pakemis_Mt_co2e"]), places=2)

    def test_species_rows_sum_to_the_total(self):
        species = [r for r in self.rows if r["species"] != "TOTAL"]
        ours = sum(float(r["pakemis_Mt_co2e_AR5"]) for r in species if r["pakemis_Mt_co2e_AR5"] != "NE")
        btr = sum(float(r["btr_Mt_co2e"]) for r in species)
        self.assertAlmostEqual(ours, float(self.total["pakemis_Mt_co2e_AR5"]), places=2)
        self.assertAlmostEqual(btr, float(self.total["btr_Mt_co2e"]), places=2)

    def test_each_species_verdict_follows_its_matched_native_difference(self):
        from pkinv.report import enteric_btr_bridge as bridge
        for r in self.rows:
            if r["species"] in ("TOTAL", "mules_and_asses", "horses"):
                continue
            difference = float(r["pakemis_Mt_co2e_AR5"]) - float(r["btr_Mt_co2e"])
            self.assertAlmostEqual(float(r["difference_Mt"]), difference, delta=.001)
            expected = ("agree to the printed precision" if abs(difference) <= bridge.AGREE_MT
                        else "inventory higher" if difference > 0 else "inventory lower")
            self.assertEqual(r["verdict"], expected, r["species"])
        for r in self.rows:
            if r["species"] in ("mules_and_asses", "horses"):
                self.assertEqual(r["pakemis_Mt_co2e_AR5"], "NE")

    def test_it_regenerates_identically(self):
        from pkinv.report import enteric_btr_bridge as bridge
        self.assertEqual(bridge.build(), self.rows)


if __name__ == "__main__":
    unittest.main()

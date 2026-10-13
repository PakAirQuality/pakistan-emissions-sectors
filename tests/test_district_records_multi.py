"""District validation beyond rice: structure, valid rank stats, and honest gap reporting."""
import json
import os
import unittest
from _support import ROOT

OUT = os.path.join(ROOT, "outputs", "eval", "validation", "district_records_multi.json")


class TestDistrictRecordsMulti(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(OUT), "multi-record validation not run")
    def test_structure_and_stats(self):
        d = json.load(open(OUT))
        self.assertIn("checks", d)
        self.assertIn("no_independent_record", d)
        # every scored check has a valid Spearman rho and a positive matched count
        scored = [c for c in d["checks"] if "spearman_rho" in c and c["spearman_rho"] is not None]
        self.assertGreaterEqual(len(scored), 2, "expected rice + at least one more scored category")
        for c in scored:
            self.assertTrue(-1.0 <= c["spearman_rho"] <= 1.0)
            self.assertGreater(c["n_matched"], 5)

    @unittest.skipUnless(os.path.exists(OUT), "multi-record validation not run")
    def test_managed_soils_wheat_check_present(self):
        d = json.load(open(OUT))
        soils = [c for c in d["checks"] if c["category"] == "Managed soils" and "spearman_rho" in c]
        self.assertTrue(soils, "managed-soils vs wheat check missing")
        self.assertGreater(soils[0]["spearman_rho"], 0.3, "wheat proxy should track soils geography")

    @unittest.skipUnless(os.path.exists(OUT), "multi-record validation not run")
    def test_livestock_gap_is_stated_not_faked(self):
        """Livestock must appear as an explicit no-independent-record gap, never as a fake validation."""
        d = json.load(open(OUT))
        gap_cats = {g["category"] for g in d["no_independent_record"]}
        self.assertIn("Enteric fermentation", gap_cats)
        self.assertIn("Manure management", gap_cats)
        scored_cats = {c["category"] for c in d["checks"] if "spearman_rho" in c}
        self.assertNotIn("Enteric fermentation", scored_cats)


if __name__ == "__main__":
    unittest.main()

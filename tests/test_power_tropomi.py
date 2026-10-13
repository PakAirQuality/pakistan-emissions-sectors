"""The TROPOMI cross-check - the invariants that make a satellite claim citable.

Three layers, as with the CRT and heat-rate channels: the committed extraction is the
audited artefact (hash-pinned; the SSD is never touched here); a few extraction cells
are reproduced against values read during the study; and the findings themselves - the
Thar ramp, the Hub decline, the Sahiwal arbitration, the rank agreement - are
regression-pinned so a re-extraction that moved them fails loudly instead of quietly
rewriting the paper's claims.

Run:  python3 -m unittest discover tests -p "test_power_tropomi.py"
"""
import csv
import hashlib
import os
import unittest

from pkinv.sectors.power import tropomi_crosscheck as T

# Pinned from the committed extraction (scripts/extract_tropomi_power.py, run against
# the 2,275-day archive). A mismatch is a re-audit instruction: every finding below was
# computed from THIS file.
EXPECTED_SHA256 = "d56b4a8e1c58a63b"
EXPECTED_ROWS = 20475


class TestPayload(unittest.TestCase):
    def test_the_extraction_is_the_audited_one(self):
        h = hashlib.sha256(open(T.CSV, "rb").read()).hexdigest()
        self.assertEqual(h[:16], EXPECTED_SHA256)

    def test_row_count_and_shape(self):
        rows = T._rows()
        self.assertEqual(len(rows), EXPECTED_ROWS)
        self.assertEqual(sorted({r["source"] for r in rows}),
                         sorted(T.LEDGER_PLANTS))

    def test_no_exact_zero_survived_the_filter(self):
        """The archive's zero-fill artifact: a source mean of exactly zero would mean
        the filter regressed."""
        for r in T._rows():
            for sp in ("no2", "so2"):
                if r["%s_src_mean" % sp] != "":
                    self.assertNotEqual(float(r["%s_src_mean" % sp]), 0.0,
                                        msg="%s %s" % (r["source"], r["date"]))


class TestAggregation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.no2 = T.fy_enhancements("no2")

    def test_fy2019_is_excluded_by_the_half_year_rule(self):
        """The archive starts 2020-01-01, so FY2019-20 has only Jan-Jun months; the
        both-halves rule must drop it rather than report a seasonally-biased year."""
        self.assertFalse([k for k in self.no2 if k[1] == 2019])

    def test_coverage_is_deep(self):
        """300+ valid days behind most FY means - the reason annual contrasts are tight."""
        deep = [v for v in self.no2.values() if v["n_days"] >= 280]
        self.assertGreater(len(deep), 30)

    def test_every_full_fy_reports_for_the_big_sources(self):
        for src in ("sahiwal", "thar_cluster", "hub_complex", "uch"):
            years = {y for s, y in self.no2 if s == src}
            self.assertTrue({2020, 2021, 2022, 2023}.issubset(years), msg=src)


class TestFindings(unittest.TestCase):
    """The paper's claims, pinned."""

    @classmethod
    def setUpClass(cls):
        cls.v = T.verdicts()
        cls.sp = T.spearman()

    def test_h1_hub_decline(self):
        """The ledger retires the Hub site's fuel; the satellite sees the site fade."""
        self.assertTrue(self.v["h1_hub_decline_confirmed"])
        self.assertAlmostEqual(self.v["h1_hub_ratio_fy2023_over_fy2020"], 0.53,
                               delta=0.05)

    def test_h2_thar_ramp(self):
        """One plant to four, 3.6 to 13.2 Mt of coal - and the column rises with it,
        SO2 (the lignite sulfur signature) hardest of all."""
        self.assertTrue(self.v["h2_thar_ramp_confirmed"])
        self.assertAlmostEqual(self.v["h2_thar_no2_ratio"], 2.23, delta=0.1)
        self.assertGreater(self.v["h2_thar_so2_ratio"], 7.0)

    def test_h3_the_sahiwal_arbitration(self):
        """The cross-module payoff: the implied-CV channel flagged Sahiwal's FY2021 mass
        cell; the satellite, which cannot read NEPRA's tables, sides with generation."""
        self.assertTrue(self.v["h3_satellite_sides_with_generation"])
        self.assertAlmostEqual(self.v["h3_sahiwal_enh_ratio_fy2021_over_fy2020"], 1.02,
                               delta=0.05)
        self.assertLess(abs(self.v["h3_sahiwal_enh_ratio_fy2021_over_fy2020"]
                            - self.v["h3_generation_ratio"]), 0.1)
        self.assertGreater(abs(self.v["h3_sahiwal_enh_ratio_fy2021_over_fy2020"]
                               - self.v["h3_suspect_mass_ratio"]), 0.4)

    def test_h4_uch_is_flat_and_guddu_is_honestly_reclassified(self):
        """Uch (steady field gas) is the null control and holds. Guddu was drafted as a
        second null and the data rejected the premise - its fuel really moves - so its
        verdict lives in the covariation statistics, not here."""
        self.assertTrue(self.v["h4_uch_flat_confirmed"])
        self.assertLess(self.v["h4_uch_cv"], 0.2)
        self.assertGreater(self.v["h4_guddu_cv"], 0.3)

    def test_rank_agreement(self):
        """Within-source ranks pooled: does the satellite order each source's years the
        way the ledger's generation does? rho 0.58, p 2e-4 over 36 source-years."""
        self.assertAlmostEqual(self.sp["within_rho"], 0.58, delta=0.05)
        self.assertLess(self.sp["within_p"], 0.01)
        self.assertGreater(self.sp["pooled_rho"], 0.3)
        self.assertEqual(self.sp["per_source"]["thar_cluster"]["rho"], 1.0)

    def test_the_emissions_path_never_reads_the_satellite(self):
        import inspect

        from pkinv.sectors.power import combustion, engine
        for mod in (combustion, engine):
            src = inspect.getsource(mod)
            self.assertNotIn("tropomi", src)


class TestNoSSDNeeded(unittest.TestCase):
    def test_everything_runs_from_the_committed_csv(self):
        """The module must never reach for the external drive: CI has no SSD, and a
        detached-drive failure would otherwise be silent on this Mac (the Desktop path
        is a symlink into the volume)."""
        import inspect
        src = inspect.getsource(T)
        self.assertNotIn("/Volumes", src)
        self.assertTrue(os.path.exists(T.CSV))


if __name__ == "__main__":
    unittest.main()

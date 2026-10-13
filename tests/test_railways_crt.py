"""The CRT extraction and the official-benchmark comparison, held to the filing's own cells.

The central pin is the finding itself: the current CRT's implied N2O factor for railways is
the ROAD table's 3.9 kg/TJ, not the rail table's 28.6. If a future CRT submission corrects
the category, test_the_filing_used_the_road_factors FAILS - which is the desired behaviour,
because the paper's claim about the filing must then be rewritten, not left standing.

Run:  python3 -m unittest discover tests -p "test_railways_crt.py"
"""
import unittest

from pkinv.sectors.railways import official_reporting as official
from pkinv.sectors.railways.data import RailwaysData

# The committed archive. A substituted file must fail loudly: every number this module
# reports is only as good as the bytes it was read from.
CRT_SHA256 = "afba70d10be0694aea6b2ba2cec311e149473346daa206319138185c190e8f38"


class TestExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = official.extract()
        cls.data = RailwaysData()

    def test_the_archive_is_the_committed_one(self):
        self.assertEqual(official.payload_sha256(), CRT_SHA256)

    def test_rows_are_found_by_label_not_position(self):
        self.assertTrue(self.rows["category"]["label"].startswith("1.A.3.c"))
        self.assertTrue(self.rows["liquid"]["label"].startswith("Liquid fuels"))
        for name in ("category", "liquid"):
            self.assertIn("cells", self.rows[name])

    def test_the_filings_arithmetic_reproduces_from_its_own_cells(self):
        self.assertEqual(official.arithmetic_check(self.rows), [])

    def test_the_filing_used_the_road_factors(self):
        """CH4 and N2O IEFs both ~3.9 kg/TJ - Table 3.2.2 (road) - where Table 3.4.1
        (rail) says 4.15 and 28.6. CO2 at 74.1 t/TJ is common to both tables, which is
        exactly why the substitution is silent in every check run on CO2 alone."""
        ief = self.rows["liquid"]
        self.assertAlmostEqual(ief["ief_ch4_kg_per_TJ"], 3.9, places=1)
        self.assertAlmostEqual(ief["ief_n2o_kg_per_TJ"], 3.9, places=1)
        self.assertAlmostEqual(ief["ief_co2_t_per_TJ"], 74.1, places=1)
        rail_n2o = self.data.efv("railway_traction_n2o", "Gas/Diesel Oil")
        self.assertGreater(rail_n2o, 5 * ief["ief_n2o_kg_per_TJ"])

    def test_the_filings_activity_dwarfs_the_metered_fuel(self):
        """56,609 TJ is ~1,316 kt of diesel; the operator's account never exceeds 136 kt in
        any held year. The order-of-magnitude divergence is in the current filing, not just
        the old BUR."""
        implied = official.implied_activity(self.data, self.rows)["implied_diesel_kt"]
        heaviest = max(self.data.quantity("Gas/Diesel Oil", y) * 1000.0
                       * self.data.p("hsd_density_kg_per_l") / 1e6
                       for y in self.data.years())
        self.assertGreater(implied, 1200)
        self.assertLess(heaviest, 140)
        self.assertGreater(implied / heaviest, 9)


class TestComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.comp = {r["benchmark_id"]: r
                    for r in official.comparison(RailwaysData())}

    def test_bur1_is_matched_year(self):
        r = self.comp["bur1"]
        self.assertIn("matched fiscal year", r["match_basis"])
        self.assertAlmostEqual(r["official_Mt_co2e"], 4.06)
        self.assertTrue(8.0 < r["ratio_official_over_own"] < 10.0,
                        r["ratio_official_over_own"])

    def test_crt_ratio_and_basis_are_stated(self):
        r = self.comp["crt2022"]
        self.assertIn("straddles", r["match_basis"])
        self.assertTrue(10.0 < r["ratio_official_over_own"] < 14.0,
                        r["ratio_official_over_own"])
        self.assertGreater(r["implied_over_metered"], 10.0)

    def test_every_register_row_documents_itself(self):
        for b in official.register():
            self.assertTrue(b["source_note"].strip(), b["benchmark_id"])
            self.assertTrue(b["source"].strip(), b["benchmark_id"])

    def test_the_inc_era_figure_was_sane(self):
        """The table's arc: INC FY1993-94 (derived from its stated 3 percent share) sits
        within 15 percent of the quinquennial history reconstruction. The
        order-of-magnitude error entered the record with BUR-1, not at the start."""
        r = self.comp["inc1994"]
        self.assertTrue(0.7 < r["ratio_official_over_own"] < 1.2,
                        r["ratio_official_over_own"])
        self.assertIn("quinquennial", r["match_basis"])

    def test_the_silent_documents_say_so(self):
        """The TNC and the BTR-1 narrative report 1.A.3 as one line; their comparison
        rows must state the non-reporting rather than fabricate a railway value."""
        for b in ("tnc2021", "btr2024"):
            r = self.comp[b]
            self.assertEqual(r["official_Mt_co2e"], "")
            self.assertIn("not separately reported", r["match_basis"])


if __name__ == "__main__":
    unittest.main()

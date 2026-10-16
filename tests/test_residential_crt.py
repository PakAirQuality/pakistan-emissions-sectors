"""The residential CRT extraction, benchmark register and CCAC bridge, held to the
filing's own cells.

The central pin is the headline finding: the current CRT reports every Biomass cell in
the 1.A.4.b block as NE - the country's two largest household fuels are absent from its
own filing. If a future submission estimates them, test_the_filings_biomass_is_ne FAILS,
which is the desired behaviour: the paper's claim about the filing must then be
rewritten, not left standing.

Run:  python3 -m unittest discover tests -p "test_residential_crt.py"
"""
import csv
import os
import unittest

from pkinv.paths import OUTPUTS
from pkinv.sectors.residential import combustion, engine
from pkinv.sectors.residential import official_reporting as official
from pkinv.sectors.residential.data import ResidentialData

# The committed archive - same zip the railways, power and fugitives extractions pin.
CRT_SHA256 = "afba70d10be0694aea6b2ba2cec311e149473346daa206319138185c190e8f38"


class TestExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = official.extract()
        cls.data = ResidentialData()

    def test_the_archive_is_the_committed_one(self):
        self.assertEqual(official.payload_sha256(), CRT_SHA256)

    def test_rows_are_found_by_label_not_position(self):
        self.assertTrue(self.rows["category"]["label"].startswith("1.A.4.b"))
        for name in ("liquid", "solid", "gaseous", "biomass"):
            self.assertTrue(self.rows[name]["label"].startswith(name.capitalize()))
            self.assertIn("cells", self.rows[name])

    def test_the_filings_arithmetic_reproduces_from_its_own_cells(self):
        self.assertEqual(official.arithmetic_check(self.rows), [])

    def test_the_filings_biomass_is_ne(self):
        """The headline. Dung and firewood - 487,701 TJ in this inventory, more than
        one and a half times the filing's whole residential activity - carry the
        notation key NE in Pakistan's own submission.

        Through rc66 the figure was 1,041,627 TJ and "more than three times": that was
        the whole diverted dung supply burned in households. At rc67 the reference dung
        became the household survey series, and the three-times statement belongs to
        configuration L, where it is still held."""
        self.assertTrue(official.biomass_is_ne(self.rows))
        filing_tj = self.rows["category"]["activity_TJ"]
        own_biomass_tj = sum(combustion.fuel_TJ(self.data)[s]
                             for s in ("Dung cake", "Firewood"))
        from pkinv.sectors.residential import hies, timeseries
        expected_tj = (hies.firewood_air_dry_kg()
                       / 1e6 * self.data.efv("residential_ncv", "Wood/Wood Waste")
                       + timeseries.dung_survey_air_dry_kg(self.data.year) / 1e6
                       * self.data.efv("residential_ncv", "Other Primary Solid Biomass"))
        self.assertAlmostEqual(own_biomass_tj, expected_tj, places=5)
        self.assertGreater(own_biomass_tj, 1.5 * filing_tj)
        self.assertLess(own_biomass_tj, 3 * filing_tj)
        ledger_biomass_tj = sum(
            combustion.fuel_TJ(self.data, dung_basis="ledger")[s]
            for s in ("Dung cake", "Firewood"))
        self.assertGreater(ledger_biomass_tj, 3 * filing_tj)

    def test_the_gaseous_rows_corroborate_within_two_percent(self):
        """Two independent derivations of the same metered gas - the filing's and
        OGRA's domestic table - across a one-to-two-year vintage gap."""
        g = official.gaseous_corroboration(self.data, self.rows)
        self.assertLess(abs(1.0 - g["ratio_own_over_crt"]), 0.02)

    def test_the_gaseous_iefs_are_table_2_5(self):
        r = self.rows["gaseous"]
        self.assertAlmostEqual(r["ief_co2_t_per_TJ"], 56.1, places=1)
        self.assertAlmostEqual(r["ief_ch4_kg_per_TJ"], 5.0, places=6)
        self.assertAlmostEqual(r["ief_n2o_kg_per_TJ"], 0.1, places=6)

    def test_the_liquid_ief_is_an_lpg_kerosene_blend(self):
        """64.37 t/TJ sits between LPG (63.1) and kerosene (71.9) - the RIGHT factor
        family for the category, unlike the road-table substitution the railway block
        carries. The implied kerosene share is a diagnostic, not a finding of error."""
        share = official.liquid_blend_implied_kerosene_share(self.data, self.rows)
        self.assertGreater(share, 0.0)
        self.assertLess(share, 0.5)

    def test_the_solid_row_is_the_lignite_factor_set(self):
        """29.5 TJ booked at 101/300/1.5 - Table 2.5's lignite row, where this
        inventory carries household coal as other-bituminous. Both negligible; the
        divergence is recorded, and this pin breaks if a resubmission rebooks it."""
        r = self.rows["solid"]
        self.assertAlmostEqual(r["ief_co2_t_per_TJ"], 101.0, places=1)
        self.assertAlmostEqual(r["ief_ch4_kg_per_TJ"], 300.0, places=1)
        self.assertLess(r["activity_TJ"], combustion.fuel_TJ(self.data)["Coal"])

    def test_fossil_scope_comparison_is_within_ten_percent(self):
        """On the filing's own scope (fossil only, its GWPs) the two inventories agree
        within ten percent across the vintage gap - the corroboration that makes the
        biomass NE finding a scope statement rather than a magnitude dispute."""
        official_mt = official.crt_co2e_Mt(self.rows)
        own_mt = official.own_fossil_scope_Mt(self.data)
        self.assertLess(abs(1.0 - official_mt / own_mt), 0.10)
        # The full scope against the filing. 1.66 through rc66, when the reference
        # burned all the diverted dung in households; 1.37 since rc67 on the survey
        # series. The old bound of 1.5 is now a statement about configuration L.
        full = sum(c["co2e_Mt_AR5"] for c in engine.build_components(self.data))
        self.assertAlmostEqual(full / official_mt, 1.366, places=3)
        ledger = sum(c["co2e_Mt_AR5"] for c in
                     engine.build_components(self.data, dung_basis="ledger"))
        self.assertGreater(ledger / official_mt, 1.5)


class TestRegisterAndOutputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.register = official.register()
        cls.comparison = official.comparison(cls.data)

    def test_every_register_row_reaches_the_comparison(self):
        self.assertEqual({b["benchmark_id"] for b in self.register},
                         {c["benchmark_id"] for c in self.comparison})

    def test_every_ratio_row_states_its_match_basis(self):
        """Since the time-series phase, comparisons are matched-year - and each must
        say exactly what was matched and what was held, never a bare ratio."""
        for c in self.comparison:
            if c["ratio_official_over_own"]:
                self.assertIn("MATCHED", c["match_basis"], c["benchmark_id"])
                self.assertIn("held", c["match_basis"], c["benchmark_id"])

    def test_the_crt_row_compares_on_the_filings_scope_and_year(self):
        row = next(c for c in self.comparison if c["benchmark_id"] == "crt2022")
        self.assertIn("MATCHED SCOPE AND STRADDLE-MEAN YEAR", row["match_basis"])
        self.assertAlmostEqual(row["own_Mt_co2e"],
                               round(official.own_fossil_scope_cy(self.data, 2022), 3))
        self.assertLess(abs(1.0 - row["official_Mt_co2e"] / row["own_Mt_co2e"]), 0.10)

    def test_the_narrative_absence_rows_say_so(self):
        for bid in ("tnc2021", "btr2024"):
            row = next(c for c in self.comparison if c["benchmark_id"] == bid)
            self.assertEqual(row["official_Mt_co2e"], "")
            self.assertIn("not separately reported", row["match_basis"])

    def test_the_ccac_row_defers_to_the_bridge(self):
        row = next(c for c in self.comparison if c["benchmark_id"] == "ccac2021")
        self.assertIn("bridge", row["match_basis"])
        self.assertEqual(row["official_Mt_co2e"], "")


class TestCcacBridge(unittest.TestCase):
    """rc67 (2026-10-13). Through rc66 the bridge started from configuration L (631.9 kt)
    and its largest step was "WEDGE: dung configuration L to S", 314.6 kt, a candidate
    alignment. The reference is now the survey series, so endpoint A is 282.7 kt, the
    configuration wedge is gone, and configuration L follows endpoint B as a memo row
    that is not a step. The tests below find rows by label because the last row is no
    longer endpoint B."""

    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.bridge = official.ccac_bridge(cls.data)

    def _row(self, prefix):
        hits = [r for r in self.bridge if r["item"].startswith(prefix)]
        self.assertEqual(len(hits), 1, prefix)
        return hits[0]

    def _steps(self):
        """The rows strictly between the two endpoints: the wedges and the residual."""
        items = [r["item"] for r in self.bridge]
        a = items.index(self._row("ENDPOINT A")["item"])
        b = items.index(self._row("ENDPOINT B")["item"])
        return self.bridge[a + 1:b]

    def test_the_endpoints_bracket_the_bridge(self):
        """Endpoint A opens the table and endpoint B closes the BRIDGE; the only row
        after it is the configuration-L memo."""
        self.assertIn("ENDPOINT A", self.bridge[0]["item"])
        self.assertIn("(reference)", self.bridge[0]["item"])
        self.assertIn("ENDPOINT B", self.bridge[-2]["item"])
        self.assertTrue(self.bridge[-1]["item"].startswith("MEMO"))
        self.assertGreater(self.bridge[0]["pm25_kt"], self.bridge[-2]["pm25_kt"])

    def test_the_bridge_closes_exactly_through_a_signed_residual(self):
        """Endpoint A minus every wedge minus the residual must equal endpoint B by
        construction - and the residual must EXIST, be signed, and be labelled
        unexplained. A bridge without one would mean a leftover had been silently
        booked as an explanation; a bridge that doesn't close is arithmetic error.

        The memo row sits outside the identity: with it in the sum the bridge would be
        590.7 kt from closing, which is how the pre-rc67 form of this test failed."""
        a = self._row("ENDPOINT A")["pm25_kt"]
        b = self._row("ENDPOINT B")["pm25_kt"]
        middle = sum(r["pm25_kt"] for r in self._steps())
        self.assertAlmostEqual(a - middle, b, delta=0.3)
        year = self._row("WEDGE: inventory year")["pm25_kt"]
        fuel_set = self._row("WEDGE: fuel set")["pm25_kt"]
        residual = next(r for r in self.bridge if "RESIDUAL" in r["item"])
        self.assertAlmostEqual(a - year - fuel_set - residual["pm25_kt"], b, delta=0.3)
        self.assertNotEqual(residual["pm25_kt"], 0.0)
        self.assertIn("never redistributed", residual["note"])
        self.assertLess(abs(residual["pm25_kt"]) / b, 0.25)

    def test_the_bridge_is_the_shipped_one(self):
        """Compare the published final bridge with current source/method reconstruction."""
        from pkinv.core.io import read_rows
        shipped = read_rows(os.path.join(OUTPUTS, "residential_ccac_bridge_2024.csv"))
        self.assertEqual([r["item"] for r in self.bridge], [r["item"] for r in shipped])
        for expected, actual in zip(self.bridge, shipped):
            self.assertAlmostEqual(expected["pm25_kt"], float(actual["pm25_kt"]), places=1)

    def test_the_year_wedge_is_quantified_by_the_time_series(self):
        from pkinv.sectors.residential import timeseries
        year_wedge = next(r for r in self.bridge
                          if r["item"].startswith("WEDGE") and "year" in r["item"])
        matched = timeseries.matched_cy(2021, self.data)["pm25_kt"]
        self.assertAlmostEqual(year_wedge["pm25_kt"],
                               self.bridge[0]["pm25_kt"] - matched, delta=0.2)

    def test_there_is_no_configuration_wedge(self):
        """Through rc66 the bridge's largest wedge had to be the L-to-S configuration
        move. The reference is the survey reading now, so no wedge may name a
        configuration: the two that remain are the year and the fuel set, the larger is
        the fuel set, and its candidate-alignment status must be stated, not implied."""
        wedges = [r for r in self.bridge if r["item"].startswith("WEDGE")]
        self.assertEqual([r["item"] for r in wedges],
                         ["WEDGE: inventory year", "WEDGE: fuel set (crop residues)"])
        for r in self._steps():
            self.assertNotIn("configuration", r["item"])
        largest = max(wedges, key=lambda r: r["pm25_kt"])
        self.assertIn("fuel set", largest["item"])
        self.assertIn("CANDIDATE", largest["note"])

    def test_configuration_l_is_a_memo_and_not_a_step(self):
        """The memo row is the matched-2021 total on the ledger dung series, taken here
        from the time series directly (the bridge builds it by swapping the dung
        stream). It must say it is not a step, and it sits far above both endpoints."""
        from pkinv.sectors.residential import timeseries
        memo = self._row("MEMO")
        self.assertIn("configuration L", memo["item"])
        self.assertIn("NOT A STEP OF THE BRIDGE", memo["note"])
        ledger = timeseries.matched_cy(
            2021, self.data,
            series=timeseries.fuel_TJ_series(self.data, dung_basis="ledger"))["pm25_kt"]
        self.assertAlmostEqual(memo["pm25_kt"], ledger, delta=0.06)
        self.assertGreater(memo["pm25_kt"], 2 * self._row("ENDPOINT A")["pm25_kt"])

    def test_the_implied_ccac_figure_is_the_stated_arithmetic(self):
        self.assertAlmostEqual(self._row("ENDPOINT B")["pm25_kt"],
                               round(official.CCAC_NATIONAL_PM25_KT_2021
                                     * official.CCAC_RESIDENTIAL_SHARE, 1))

    def test_the_shipped_file_is_this_bridge(self):
        """outputs/residential_ccac_bridge_2024.csv row for row, so a stale file with
        the retired configuration wedge cannot sit beside a corrected function."""
        path = os.path.join(OUTPUTS, "residential_ccac_bridge_2024.csv")
        with open(path, newline="", encoding="utf-8") as f:
            shipped = list(csv.DictReader(f))
        self.assertEqual([(r["item"], float(r["pm25_kt"]), r["note"]) for r in shipped],
                         [(r["item"], r["pm25_kt"], r["note"]) for r in self.bridge])


class TestOutputsExist(unittest.TestCase):
    def test_the_three_outputs_are_written_and_readable(self):
        official.main()
        for name in ("residential_unfccc_crt_cell_audit_2024.csv",
                     "residential_official_comparison_2024.csv",
                     "residential_ccac_bridge_2024.csv"):
            path = os.path.join(OUTPUTS, name)
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertTrue(rows, name)


if __name__ == "__main__":
    unittest.main()

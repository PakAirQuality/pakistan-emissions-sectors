"""Clinker trade: is the year observed, or is the silence being read as a zero?

The single failure this module guards is small to write and expensive to make: UN Comtrade
returns no record for a month with no trade AND for a month it has not processed, so reading
silence as zero would turn one observed fiscal year into a nine-year panel that looks
complete and is not. It would also bias in one direction - Pakistan exports far more clinker
than it imports, and a missing export month read as zero lowers inferred domestic production.

So the tests below are mostly about what does NOT happen: no zero appears where a number is
unknown, no benchmark leaks into a published total, and no absent year acquires a value from
its neighbours.

Run:  python3 -m unittest discover tests -p "test_trade_evidence.py"
"""
import csv
import os
import unittest

from _support import require_documents  # noqa: E402  (rc42: the documents gate)

from pkinv.paths import OUTPUTS
from pkinv.sectors.ippu import cement, trade_evidence as te
from pkinv.sectors.ippu.data import IppuData
from pkinv.core.io import read_rows
from pkinv.core.reporting_window import CORE_FY_ENDS, CORE_PERIOD_IDS
from pkinv.core.configurations import REFERENCE


def _rows(name):
    return read_rows(os.path.join(OUTPUTS, name), comments=False)


class TestSilenceIsNotZero(unittest.TestCase):
    """The synthetic cases, so the rule is tested rather than the shipped data's shape."""

    RECORDS = {("2019-%02d" % m, "export"): 1000.0 for m in range(1, 12)}

    def test_a_month_with_no_record_and_no_control_is_absent(self):
        state = te.month_state("2019-12", "export", records=self.RECORDS, reconciled=set())
        self.assertEqual(state, te.ABSENT)

    def test_a_control_that_the_months_reach_proves_the_rest_zero(self):
        """Eleven months of 1,000 t and an annual total of 11,000 t: the source itself says
        December held nothing."""
        controls = {("2019", "export"): 11000.0}
        reconciled = te.reconciled_years(self.RECORDS, controls)
        self.assertIn(("2019", "export"), reconciled)
        self.assertEqual(te.month_state("2019-12", "export", self.RECORDS, reconciled),
                         te.OBSERVED_ZERO)

    def test_a_control_the_months_do_not_reach_proves_nothing(self):
        """12,000 t against 11,000 t of records: a thousand tonnes moved in some month, and
        which month is exactly what is unknown. This is the case that must NOT resolve."""
        controls = {("2019", "export"): 12000.0}
        reconciled = te.reconciled_years(self.RECORDS, controls)
        self.assertNotIn(("2019", "export"), reconciled)
        self.assertEqual(te.month_state("2019-12", "export", self.RECORDS, reconciled),
                         te.ABSENT)

    def test_observed_zero_and_absent_are_never_the_same_state(self):
        self.assertNotEqual(te.OBSERVED_ZERO, te.ABSENT)
        self.assertIn(te.OBSERVED_ZERO, te.STATES)
        self.assertIn(te.BOUNDED, te.STATES)

    def test_no_year_is_bounded_yet_and_that_is_deliberate(self):
        """The state exists so a future bounded estimate arrives carrying its evidence and
        uncertainty, not as a silent central value. None are populated today."""
        self.assertNotIn(te.BOUNDED, {row["status"] for row in te.table()})


class TestTheShippedPanel(unittest.TestCase):
    def test_the_reference_year_is_observed_and_unmoved(self):
        verdict = te.require(2024)
        self.assertEqual(verdict["status"], te.OBSERVED)
        self.assertAlmostEqual(verdict["import_kt"], 26.131, places=3)
        self.assertAlmostEqual(verdict["export_kt"], 3792.074, places=3)
        self.assertEqual(verdict["missing_months"], 0)

    def test_every_year_of_the_series_has_an_observed_trade_term(self):
        """What the acquisition bought. The panel ran July 2023 to June 2024 and now runs
        July 2014 to June 2024, so the gap that named unobtained trade for eight years is
        closed by evidence rather than by assumption."""
        for row in te.table():
            self.assertIn(row["status"], (te.OBSERVED, te.OBSERVED_ZERO),
                          row["fiscal_end_year"])
            self.assertEqual(row["missing_months"], 0, row["fiscal_end_year"])
            self.assertIsNotNone(row["import_kt"])
            self.assertIsNotNone(row["export_kt"])

    def test_some_years_stand_partly_on_proved_zeros(self):
        """And that is the point of the annual control: four of the nine years contain
        months Comtrade is silent about, and they are covered because the source's own
        annual total leaves nothing for those months to hold - not because silence was read
        as zero."""
        proved = {r["fiscal_end_year"]: r["proved_zero_months"] for r in te.table()}
        self.assertTrue(any(n > 0 for n in proved.values()))
        self.assertEqual(proved[2024], 0)      # the reference year needs no such argument

    def test_a_year_outside_the_panel_raises_instead_of_returning_zero(self):
        """The whole design in one assertion, tested where the panel genuinely ends. Every
        arithmetic path downstream would consume a 0.0 without complaint."""
        verdict = te.resolve(2014)
        self.assertEqual(verdict["status"], te.ABSENT)
        with self.assertRaises(te.TradeNotObserved):
            te.require(2014)


class TestTheGateGovernsTheBalance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = IppuData()

    def test_the_reference_balance_is_unchanged_by_the_gate(self):
        balance = cement.clinker_balance(self.data)
        self.assertAlmostEqual(balance["clinker_production_kt"], 33440.443, places=3)
        self.assertEqual(balance["trade_status"], te.OBSERVED)
        self.assertEqual(balance["configuration_status"], "valid")

    def test_only_years_holding_BOTH_halves_produce_a_balance(self):
        """The composed property, which is stronger than testing either half alone: a
        balance exists for exactly the years with observed activity AND an observed trade
        term, and every other year fails loudly rather than dropping a term.

        Which half fails first is not fixed and should not be asserted - activity is looked
        up before the gate, so a year missing both reports the activity. What matters is
        that no year produces a number with a term missing.
        """
        built = set()
        for year in range(2014, 2025):
            try:
                balance = cement.clinker_balance(
                    self.data, year=year,
                    activity_source=self.data.cement_activity_source(year))
            except (te.TradeNotObserved, KeyError):
                continue
            built.add(year)
            self.assertTrue(balance["trade_included"])
            self.assertEqual(balance["configuration_status"], "valid")
        self.assertEqual(built, set(range(2016, 2025)))

    def test_every_built_year_carries_an_observed_trade_term(self):
        """Every built year. A built cement year with trade_status anything but observed
        would be the failure this module exists for."""
        for year in CORE_FY_ENDS:
            balance = cement.clinker_balance(self.data, year=year,
                                             activity_source=self.data
                                             .cement_activity_source(year))
            self.assertIn(balance["trade_status"], (te.OBSERVED, te.OBSERVED_ZERO), year)
            self.assertEqual(balance["configuration_status"], "valid", year)
            self.assertGreater(balance["clinker_exports_kt"], 0.0, year)

    def test_omitting_trade_yields_a_screening_calculation_not_a_configuration(self):
        balance = cement.clinker_balance(self.data, year=2022,
                                         activity_source="sbp_stat_supplement_fy2024",
                                         include_trade=False)
        self.assertEqual(balance["configuration_status"], "screening_only")
        self.assertEqual(balance["trade_status"], te.ABSENT)
        self.assertFalse(balance["trade_included"])

    def test_a_year_with_no_activity_is_NE_and_says_so(self):
        """The message still has to be the right one where activity really is missing.

        FY2018-19 used to be that year and is not any more, so this asks about a year
        outside the series entirely: the resolver must name the year as NE rather than
        raise a bare KeyError from a dictionary three layers down.
        """
        with self.assertRaises(KeyError) as caught:
            self.data.cement_activity_source(2010)
        self.assertIn("NE, not zero", str(caught.exception))

    def test_every_series_year_resolves_to_exactly_one_activity_source(self):
        """Nine years, three publications, and no year ambiguous between two of them - the
        FY2019-20 overlap is carried as a comparison row precisely so that it informs the
        join without becoming a second candidate."""
        sources = {y: self.data.cement_activity_source(y) for y in range(2016, 2025)}
        self.assertEqual(len(sources), 9)
        self.assertEqual(sources[2020], "sbp_stat_supplement_fy2024")
        self.assertEqual(sources[2016], "psyb_2020_table_13_2")


class TestTheBenchmarksStayOutOfEveryTotal(unittest.TestCase):
    """A screening calculation that reaches a published total is worse than no benchmark."""

    def setUp(self):
        self.benchmarks = _rows("ippu_cement_method_benchmarks_2024.csv")

    def test_they_are_all_screening_only(self):
        self.assertTrue(self.benchmarks)
        self.assertEqual({r["status"] for r in self.benchmarks}, {"screening_only"})
        self.assertIn("cement_no_trade_method_benchmark",
                      {r["benchmark_id"] for r in self.benchmarks})
        self.assertEqual({r["trade_included"] for r in self.benchmarks}, {"False"})

    def test_no_benchmark_value_appears_in_any_additive_product(self):
        values = {round(float(r["co2e_Mt_AR5"]), 5) for r in self.benchmarks}
        products = ("national_all_sectors.csv", "national_all_sectors_ledger.csv",
                    "pakemis_national_series.csv", "pakemis_atomic_annual.csv",
                    "pakemis_annual_fy2015_16_fy2024_25.csv")
        for name in products:
            for row in _rows(name):
                raw = row.get("co2e_Mt_AR5") or ""
                if not raw or raw == "absent":
                    continue
                self.assertNotIn(round(float(raw), 5), values,
                                 "a screening-only benchmark value surfaced in %s" % name)

    def test_the_valid_structural_range_excludes_them(self):
        ladder = _rows("ippu_cement_method_ladder_2024.csv")
        valid = [r for r in ladder if r["model_class"] == "valid structural"]
        self.assertTrue(valid)
        # rc30: the census reference observes production directly, so it carries
        # no trade term BY CONSTRUCTION; every model member still must
        self.assertEqual(
            {r["trade_included"] for r in valid},
            {"True", "not applicable: production observed directly"})
        census = [r for r in valid
                  if r["trade_included"].startswith("not applicable")]
        self.assertEqual(len(census), 1)
        for row in ladder:
            if row["model_class"] != "valid structural":
                self.assertEqual(row["status"], "screening_only")


class TestTheCoverageMatrixSaysNE(unittest.TestCase):
    def setUp(self):
        self.cells = [r for r in _rows("pakemis_coverage_matrix.csv")
                      if r["ipcc_code"] == "2.A.1"
                      and r["configuration_id"] == REFERENCE]

    def test_cement_is_estimated_in_every_year_now(self):
        """Both halves are held in all nine years, so there is no split left to show.

        This asserted a five-and-four split for one release. The four NE years closed when
        Pakistan Statistical Year Book 2020 Table 13.2 was read - a document that had been
        under sources/ the whole time - and the test is kept, pointed at the completed
        state, because the property that matters is unchanged: a cement year is estimated
        only where activity AND an observed trade term are both held, and now they always
        are.
        """
        by_year = {r["period_label"]: r["state"] for r in self.cells}
        self.assertEqual(set(by_year), set(CORE_PERIOD_IDS))
        self.assertEqual({s for s in by_year.values()}, {"estimated"})

    def test_every_NE_year_names_the_gap_that_would_close_it(self):
        for cell in self.cells:
            if cell["state"] == "NE":
                self.assertTrue(cell["gap_id"].strip(), cell["period_label"])
                self.assertTrue(cell["evidence"].strip(), cell["period_label"])

    def test_the_gap_is_registered_rather_than_asserted_in_prose(self):
        from pkinv.report import completeness
        registered = {g["gap_id"] for g in completeness.load_data_gaps()}
        self.assertIn("clinker-trade-history", registered)


class TestTheSourcesAreBridgedRatherThanJoined(unittest.TestCase):
    """Two publications carry the nine-year cement activity, and they meet in one year."""

    def setUp(self):
        self.rows = _rows("pakemis_cement_activity_sources.csv")

    def test_the_overlap_exists_and_is_small(self):
        """A join between two sources with NO overlapping year is a declared break; this one
        has an overlap, and it is what licenses carrying the earlier years on the yearbook
        without declaring a step in the series."""
        overlaps = [r for r in self.rows if r["overlap_with"]]
        self.assertTrue(overlaps, "no overlapping year: the join is unbounded")
        self.assertEqual({r["period_id"] for r in overlaps}, {"FY2019-20"})
        for row in overlaps:
            self.assertLess(abs(float(row["difference_pct"])), 0.01,
                            "%s: the two sources differ by %s%%"
                            % (row["period_id"], row["difference_pct"]))

    def test_every_series_year_has_exactly_one_activity_row(self):
        """The comparison row must not read as a second activity value for its year."""
        import collections
        activity = collections.Counter(r["period_id"] for r in self.rows
                                       if not r["overlap_with"])
        overlap_periods = {r["period_id"] for r in self.rows if r["overlap_with"]}
        self.assertEqual(set(activity) | overlap_periods, set(CORE_PERIOD_IDS))
        self.assertEqual(set(activity.values()), {1})

    def test_the_committed_activity_matches_the_document(self):
        """The yearbook rows are read back out of the archive rather than trusted.

        Skipped where pdftotext is absent, because the check is about the document and not
        about this machine.
        """
        import shutil
        import subprocess
        import sys
        if not shutil.which("pdftotext"):
            self.skipTest("pdftotext not installed")
        require_documents("sources/Provincial Statistics/National-20260803T134231Z-1-001.zip")
        script = os.path.join(os.path.dirname(__file__), "..", "scripts",
                              "extract_psyb_cement.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         "the committed cement rows disagree with the yearbook:\n%s"
                         % result.stdout)


class TestTheScannedTableIsReadNotTyped(unittest.TestCase):
    def test_the_ocr_read_reproduces_and_self_checks(self):
        """The FY2020-21 industry gas row came off an image scan, so the guarantee cannot be
        "someone read it carefully" - it has to be that the read repeats and that the table's
        own arithmetic accepts it. Skipped without the rendering and OCR tools."""
        import shutil
        import subprocess
        import sys
        # The document first (rc69): without the layers this must skip with the pinned
        # "restricted layers absent:" reason whatever tools the machine has. The public CI
        # runner has no tesseract, skipped here for that reason, and the pinned set failed.
        require_documents("sources/OGRA/ogra_state_of_industry_2020-21.pdf")
        for tool in ("pdftoppm", "tesseract"):
            if not shutil.which(tool):
                self.skipTest("%s not installed" % tool)
        script = os.path.join(os.path.dirname(__file__), "..", "scripts",
                              "ocr_ogra_2020_21.py")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         "the committed rows disagree with the scan:\n%s" % result.stdout)
        self.assertIn("all three identities hold", result.stdout)


if __name__ == "__main__":
    unittest.main()

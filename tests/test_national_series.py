"""The national series: nine fiscal years that may not move the one that is published.

THE INVARIANT THIS FILE EXISTS TO HOLD. Wiring a sector for history may not move its
published FY2023-24 figure by one digit. 447.71688 Mt (L) is anchored in roughly seventy
places and the manuscript is frozen, so every year-parameterisation below is required to be
a proven no-op at the reference year - not approximately, exactly. The rollup identity test
here was written BEFORE any wiring landed and ran green against the unmodified engines;
every subsequent step had to keep it green.

THE TRANSPORT BRIDGE IS EXACT, NOT CLOSE. The road control's static factor rows are the
OCAC FY2023-24 cells to the digit: MS 7,104,484 t + HOBC 104,926 t = 7,209,410 t = the
7209.410 kt factor row, and HSD 5,551,442 t likewise. IEEE division by 1000 is correctly
rounded, so `(ms + hobc) / 1000.0 == efv(...)` holds as float equality. That is what makes
the repoint provably digit-preserving rather than tolerably so, and the bridge test asserts
`==` for exactly that reason - a tolerance here would license the drift the static rows and
the OCAC panel must never develop between them.
"""
import csv
import os
import sys
import unittest


from pkinv.core import registry                            # noqa: E402
from pkinv.report import national_rollup                   # noqa: E402
from pkinv.core.io import read_rows
from _support import OUT, ROOT



def _rows(name):
    return read_rows(os.path.join(OUT, name))


def _sector(name):
    return next(s for s in registry.all_sectors() if s.NAME == name)


class TestTheReferenceYearCannotMove(unittest.TestCase):
    """Written before the wiring; green before, required green after every step."""

    def test_the_rollup_recomputed_equals_the_shipped_rollup(self):
        """The executable form of 'the wiring may not move a digit'.

        Recompute the rollup through the live engines and compare against
        outputs/national_all_sectors.csv cell-for-cell at the rounding _write_rollup
        applies. Any wiring change that leaks into the no-year path fails here first.
        """
        shipped = {r["sector"]: r for r in _rows("national_all_sectors.csv")}
        fresh = national_rollup.rollup()
        self.assertEqual(len(fresh), len(shipped))
        for row in fresh:
            disk = shipped[row["sector"]]
            # round(x, 5) exactly as _write_rollup applies it, compared as floats: the CSV
            # cell is repr(round(x, 5)), so "0.3012" on disk IS round(0.30120, 5).
            self.assertEqual(round(row["co2e_Mt_AR5"], 5), float(disk["co2e_Mt_AR5"]),
                             "%s AR5 moved" % row["sector"])
            self.assertEqual(round(row["co2e_Mt_AR6"], 5), float(disk["co2e_Mt_AR6"]),
                             "%s AR6 moved" % row["sector"])

    def test_the_transport_bridge_is_exact(self):
        """static factor row == OCAC cells / 1000, as float equality.

        The static rows stay after the repoint - they carry the declared uncertainty and
        the provenance note - and this is what stops the row and the panel becoming twin
        vintages of one number.
        """
        from pkinv.sectors.transport.data import TransportData
        data = TransportData()
        self.assertEqual(
            (data.ocac_t("Road", "MS", 2024) + data.ocac_t("Road", "HOBC", 2024)) / 1000.0,
            data.efv("transport_fuel_supply", "Motor Gasoline"))
        self.assertEqual(
            data.ocac_t("Road", "HSD", 2024) / 1000.0,
            data.efv("transport_fuel_supply", "Gas/Diesel Oil"))


class TestTransportIsNoLongerYearPinned(unittest.TestCase):
    """The successor to test_transports_magnitude_is_known_to_be_year_pinned.

    That test asserted the magnitude did NOT move with the year, called itself "a reminder
    with a deadline", and said in its own docstring to delete it when the control was
    repointed at the OCAC year rows. The repoint landed; these are the two assertions that
    replace it: the magnitude now varies (the pin is gone), and the reference year did not
    move by a digit while it went (the pin was removed without disturbing what it held).
    """

    def test_the_magnitude_varies_and_the_reference_is_exact(self):
        sector = _sector("transport")
        data = sector.load_data()
        totals = {y: sum(c["co2e_Mt_AR5"] for c in sector.build_components(data, y))
                  for y in (2022, 2023, 2024)}
        self.assertGreater(max(totals.values()) - min(totals.values()), 0.5,
                           "the transport magnitude no longer moves with the year - the "
                           "control has been re-pinned")
        reference = sum(c["co2e_Mt_AR5"] for c in sector.build_components(data))
        self.assertEqual(reference, totals[2024],
                         "the explicit reference year and the no-argument build disagree")

    def test_the_composition_rule_applies_to_every_requested_year(self):
        """The trap the repoint re-opened, and closed again.

        Passing year=2024 explicitly used to ride the partial 271-cell registration panel
        while the default rode the complete 2023 one - two class splits for the same twelve
        months, 1.2 Mt of diesel walking between 1A3b and 1A4c depending on how the caller
        spelled the reference year. fleet_year() now disciplines every request.
        """
        from pkinv.sectors.transport.data import TransportData
        data = TransportData()
        self.assertEqual(data.fleet_year(2024), data.fleet_year(),
                         "an explicit reference year bypasses the completeness rule")
        self.assertLess(data.fleet_year(2017), 2020,
                        "early years should borrow the earliest complete panel")


class TestTheSeriesProduct(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.series = _rows("pakemis_national_series.csv")
        cls.national = {r["sector"]: r for r in _rows("national_all_sectors.csv")}

    def test_the_reference_column_equals_the_rollup_exactly(self):
        """The whole design in one assertion: nine years of history, and the tenth digit of
        the published year untouched. String equality on the rounded cells - both files
        round to 5 places, so this is exact, not tolerant."""
        anchor = [r for r in self.series
                  if r["period_label"] == "FY2023-24" and r["sector"] != "COVERED_TOTAL"]
        self.assertEqual(len(anchor), 10)
        for row in anchor:
            self.assertEqual(float(row["co2e_Mt_AR5"]),
                             float(self.national[row["sector"]]["co2e_Mt_AR5"]),
                             "%s moved at the reference year" % row["sector"])
            self.assertEqual(float(row["co2e_Mt_AR6"]),
                             float(self.national[row["sector"]]["co2e_Mt_AR6"]),
                             "%s AR6 moved at the reference year" % row["sector"])

    def test_covered_totals_conserve(self):
        """A COVERED_TOTAL is the sum of its own year's non-absent rows, nothing else."""
        for fy in {r["fiscal_end_year"] for r in self.series}:
            year_rows = [r for r in self.series if r["fiscal_end_year"] == fy]
            total = next(r for r in year_rows if r["sector"] == "COVERED_TOTAL")
            covered = [r for r in year_rows if r["sector"] != "COVERED_TOTAL"
                       and r["activity_basis"] != "absent"]
            self.assertAlmostEqual(float(total["co2e_Mt_AR5"]),
                                   sum(float(r["co2e_Mt_AR5"]) for r in covered), places=4)

    def test_absent_rows_carry_no_number_and_name_their_gap(self):
        """An absent sector-year must be unmistakably absent: the numeric cells carry the
        literal string 'absent' so nothing can silently sum them, and the note names the
        specific missing edition or panel - a gap with no name never gets closed.

        ZERO, and the count's history is the discipline: it was a floor ("more than
        five"), then an exact two when only industry and transport FY2015-16 remained,
        both blocked on the same OCAC edition. That edition turned out to be public
        (the Pakistan Oil Report 2015-2016 flipbook, recovered and identity-gated at
        rc20 - which document closed it, per this test's own failure message), so the
        panel is a complete 90-sector-year rectangle. The exact-zero bound keeps the
        teeth: a NEW absence must be declared in national_series.GAPS with its reason,
        and will fail here until this count is updated deliberately."""
        absent = [r for r in self.series if r["activity_basis"] == "absent"]
        self.assertEqual(len(absent), 0,
                         "the absent set changed: %s. Either a new gap opened (declare "
                         "it in national_series.GAPS, update this, and say so in the "
                         "paper) or an absence is being papered over"
                         % sorted((r["sector"], r["period_label"]) for r in absent))

    def test_no_cell_is_blank(self):
        for row in self.series:
            for field, value in row.items():
                self.assertTrue(str(value).strip(),
                                "blank %s on %s %s" % (field, row["sector"],
                                                       row["period_label"]))

    def test_every_year_has_every_sector_exactly_once(self):
        from pkinv.core import registry as reg
        names = {s.NAME for s in reg.all_sectors()}
        for fy in {r["fiscal_end_year"] for r in self.series}:
            sectors = [r["sector"] for r in self.series
                       if r["fiscal_end_year"] == fy and r["sector"] != "COVERED_TOTAL"]
            self.assertEqual(sorted(sectors), sorted(names),
                             "year %s does not carry all ten sectors" % fy)

    def test_the_splice_diagnostic_matches_its_own_claim(self):
        """The agriculture basis change is priced, and the price printed must be the
        difference the two bases actually show at the anchor."""
        splice = _rows("pakemis_series_splice_agriculture.csv")
        self.assertGreater(len(splice), 4)
        for row in splice:
            self.assertAlmostEqual(float(row["splice_difference_Mt"]),
                                   float(row["engine_Mt_AR5"])
                                   - float(row["faostat_basis_Mt_AR5"]), places=4)
        total_gap = sum(float(r["splice_difference_Mt"]) for r in splice)
        # The floor here was >1.0 Mt, priced against a committed timeseries that predated
        # the fertiliser-anchor move - staleness, not a basis difference. At the anchor the
        # timeseries rides the census-based engine by construction, so with fresh inputs
        # the gap IS rounding, and anything above a tenth of a megatonne now means the
        # timeseries was built from different activity data than the engine - the exact
        # defect the old floor was accidentally certifying as a method property.
        self.assertLess(abs(total_gap), 0.1,
                        "the anchor splice reopened (%.4f Mt) - the timeseries and the "
                        "engine no longer share their activity anchor; rerun "
                        "pkinv.sectors.agriculture.timeseries before reading this as a "
                        "basis change" % total_gap)

    def test_the_series_is_deterministic(self):
        from pkinv.report import national_series
        first = national_series.build()[0]
        second = national_series.build()[0]
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()


class TestThePublishedSeriesIsCutWithSequentialSums(unittest.TestCase):
    """rc42 (the twentieth review's reproduction finding). CPython 3.12 changed float `sum()`
    to compensated summation; the agriculture FY2022-23 AR5 category rows sum to an exact
    five-decimal tie (208.5645650...) that rounds up under 3.11's sequential sum and down
    under 3.12's. The writers accumulate sequentially by name (pkinv.core.io.seq_sum), so
    the published cell is the same bytes on every interpreter the lock or a reviewer runs."""

    ROWS_FY2023_AR5 = [143.249211, 20.163445, 13.5408, 26.456801, 0.557902, 4.596406]

    def test_the_tie_rounds_the_published_way(self):
        from pkinv.core.io import seq_sum
        self.assertEqual("%.5f" % seq_sum(self.ROWS_FY2023_AR5), "208.56457")

    def test_the_series_writer_uses_the_sequential_sum(self):
        from pkinv.report import national_series
        import inspect
        source = inspect.getsource(national_series._sum)
        self.assertIn("seq_sum", source)
        self.assertNotIn("(sum(", source)

    def test_the_published_cell_is_the_sequential_one(self):
        from pkinv.core.io import seq_sum
        from pkinv.sectors.agriculture import engine
        components = engine.components_for_fiscal_year(2023)
        expected = "%.5f" % seq_sum(row["co2e_Mt_AR5"] for row in components)
        row = next(r for r in _rows("pakemis_national_series.csv")
                   if r["row_kind"] == "sector" and r["sector"] == "agriculture"
                   and r["fiscal_end_year"] == "2023")
        self.assertEqual(row["co2e_Mt_AR5"], expected)

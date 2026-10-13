"""PBS's plant-month generation: the parse proves itself, and the fuel labels are not guessed.

This series is the largest single repair the monthly product has had - grid power was twelve
percent of the inventory carried on a flat line, and PBS had published the plant-month record
all along. Reading it is a parse of a fifteen-layout PDF, which is exactly the kind of thing
that looks right and is quietly wrong, so almost every test here is a PROOF the document
itself supplies rather than a number this project decided:

  * the plant rows must reconstruct the printed monthly Grand Total, month by month. That is
    also what licenses reading a blank cell as nil - the source's own arithmetic says so.
  * a row that carries its own annual total must meet it, which is what places its figures on
    the right months when its name has wrapped and its last figure has spilled onto the line
    below.
  * the unit scale is derived from a bracket the physics of the grid supplies - total
    generation is more than fossil generation and nowhere near three times it - and one
    scale can satisfy it, never two.
  * a fuel is read from the Fuel column or carried back from the same publication. It is
    never read from a plant's name, and a plant the ledger gives several fuels gets none.

Run:  python3 -m unittest discover tests -p "test_pbs_generation.py"
"""

from pkinv.assets import asset_path
import collections
import csv
import os
import sys
import unittest

from _support import ROOT, scripts_on_path
scripts_on_path()

import ingest_pbs_generation as ingest  # noqa: E402
from pkinv.sectors.power import pbs_generation  # noqa: E402
from pkinv.core.io import read_rows

YEARS = range(ingest.FIRST_FY_START, ingest.LAST_FY_START + 1)


def _csv(path):
    return read_rows(path, comments=False)


class TestTheParseProvesItself(unittest.TestCase):
    """Nothing here trusts the reader; every year is checked against the printed page."""

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(ingest.PDF):
            raise unittest.SkipTest("the PBS publication is not present")
        cls.blocks = ingest.blocks()
        cls.parsed = {year: ingest.parse_year(cls.blocks[year])
                      for year in YEARS if year in cls.blocks}

    def test_every_year_in_the_window_is_in_the_document(self):
        self.assertEqual(sorted(self.parsed), sorted(YEARS))

    def test_the_plant_rows_reconstruct_the_printed_grand_total(self):
        """The headline proof. Whitespace tokenising missed this by up to sixteen percent in
        four of the six years, and the shortfall was blank cells and wrapped rows, not a
        publication that does not add up."""
        for year, (plants, totals, _dropped) in self.parsed.items():
            self.assertIsNotNone(totals, "FY%d prints no Grand Total row" % year)
            for index in range(12):
                summed = sum(p["months"][index] for p in plants)
                self.assertAlmostEqual(
                    summed / totals[index], 1.0, places=2,
                    msg="FY%d month %d: plants %.0f vs printed %.0f"
                        % (year, index + 1, summed, totals[index]))

    def test_a_blank_cell_is_read_as_nil_and_a_missing_plant_is_not(self):
        """Blank is nil BECAUSE the totals close, not by assumption. A plant with no row at
        all is a different thing and never becomes a zero - which is visible as the plant
        counts differing between years rather than every year carrying every plant."""
        counts = {year: len(plants) for year, (plants, _t, _d) in self.parsed.items()}
        self.assertGreater(len(set(counts.values())), 1,
                           "every year has the same number of plants, which would mean "
                           "absent plants are being filled in from somewhere")
        blanks = [p for _y, (plants, _t, _d) in self.parsed.items() for p in plants
                  if any(m == 0.0 for m in p["months"]) and sum(p["months"]) > 0]
        self.assertTrue(blanks, "no plant anywhere has a nil month, which a fleet with "
                                "seasonal reserve plant certainly does")

    def test_no_subtotal_row_is_counted_as_a_plant(self):
        """`TOTAL JAMSHORO` and `tps guddu (1-4)` aggregate rows printed just above them.
        Counting both would double the largest thermal stations in the file."""
        for year, (plants, _t, _d) in self.parsed.items():
            for plant in plants:
                self.assertNotRegex(plant["plant"].lower(), r"(^|\s)total(\s|$)",
                                    "FY%d counts a subtotal row" % year)

    def test_the_serial_number_is_not_part_of_the_plant_name(self):
        """The same station is 54 one year and 48 the next; leaving the number in the name
        is enough on its own to stop a fuel label carrying back between years."""
        for year, (plants, _t, _d) in self.parsed.items():
            for plant in plants:
                self.assertFalse(plant["plant"][:4].strip()[:1].isdigit(),
                                 "FY%d: %r" % (year, plant["plant"]))


class TestTheUnitScaleIsDerivedAndUnique(unittest.TestCase):
    """The tables are headed GWH, MW and GWh and the magnitudes are none of those."""

    def test_one_scale_and_only_one_satisfies_the_bracket(self):
        for year in YEARS:
            controls = ingest.control_by_fuel()[year]
            fossil = sum(controls.get(f, 0.0) for f in ingest.FOSSIL)
            # the printed national total for that year, in the document's own units
            total = fossil * 1.5 * 1000
            self.assertEqual(ingest.unit_scale(total, fossil), [1000])

    def test_a_total_that_fits_no_scale_returns_nothing_rather_than_the_nearest(self):
        """A near miss must not be rounded into a decision; the caller raises on this."""
        self.assertEqual(ingest.unit_scale(4.4e6, 1e5), [])

    def test_the_scale_actually_used_is_MWh_for_every_year(self):
        """Per LANE: the PBS PDF prints MWh under a GWh heading and the scale is derived;
        the SIR listing sheets state GWh and mean it. The two vocabularies are closed and
        keyed on the row's own source_file, so a third basis - or a lane wearing the other
        lane's unit story - fails here."""
        rows = _csv(asset_path(ROOT, "data", "activity", "power", "generation_monthly.csv"))
        by_lane = {}
        for row in rows:
            lane = "sir" if "sir_detail" in row["source_file"] else "pbs"
            by_lane.setdefault(lane, set()).add(row["unit_basis"])
        self.assertEqual(by_lane["pbs"], {"MWh in the document, written here as GWh"})
        self.assertEqual(by_lane["sir"], {"GWh as printed"})


class TestNoFuelIsGuessedFromAName(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _csv(asset_path(ROOT, "data", "activity", "power", "generation_monthly.csv"))

    def test_a_plant_the_ledger_gives_several_fuels_gets_none(self):
        """Fifteen of the ledger's fifty-two plants burn more than one fuel. Taking the first
        row would have labelled Jamshoro gas and KAPCO whichever of RLNG, furnace oil and
        diesel happened to be read first."""
        fuels = ingest.ledger_fuels()
        for ambiguous in ("kapco", "jamshoro", "binqasimtpsi"):
            self.assertFalse([k for k in fuels if ambiguous in k],
                             "%s is multi-fuel and must not carry a single label"
                             % ambiguous)

    def test_the_ledger_names_are_cleaned_before_matching(self):
        """Three ledger rows begin `(Rs. Million)`, carried in from a column heading. Left
        alone they match nothing, silently."""
        self.assertEqual(ingest._ledger_name("(Rs. Million) GTPS Faisalabad"),
                         "GTPS Faisalabad")
        self.assertEqual(ingest._ledger_name("TPS Muzaffargarh (GENCO-III)"),
                         "TPS Muzaffargarh")

    def test_a_plant_whose_name_contains_a_fuel_word_is_not_thereby_labelled(self):
        """`Coal Fire/Huaneng Shandong Ruyi` is Sahiwal, and it is a coal plant - but the
        NAME must not be the reason anyone believes that. Since Pass 2 the station IS
        labelled - by the same year's SIR listing sheet through a declared, magnitude-
        gated alias - so the assertion is on the PROVENANCE: the label may come from the
        sheet lane or be absent, and never from PBS's fuel column, where only the name
        could have put it."""
        named = [r for r in self.rows if r["plant"].lower().startswith("coal fire")]
        self.assertTrue(named, "the Coal Fire rows have gone")
        for row in named:
            self.assertIn(row["fuel_source"], ("unassigned", "sir_sheet_label"),
                          "%s: %s" % (row["plant"], row["fuel_source"]))
            self.assertNotIn("pbs_fuel_column", row["fuel_source"], row["plant"])

    def test_names_are_matched_exactly_and_never_by_containment(self):
        """A tested negative, kept because it looks like an easy win and is not.

        Sahiwal is unassigned, and a normalised containment join against the ledger is the
        obvious way to recover it. Measured, that join does not find Sahiwal at all - the two
        names share no containing substring - and of the four matches it does make, one binds
        HUBCO Narowal to `hub`, which is a different power station. The rule stays exact.
        """
        fuels = ingest.ledger_fuels()
        hub = [key for key in fuels if key == "hub"]
        self.assertTrue(hub, "the ledger no longer has the short name this guards against")
        self.assertNotIn("hubconorwal", fuels,
                         "HUBCO Narowal has acquired a label by name containment")

    def test_every_row_says_where_its_fuel_came_from(self):
        for row in self.rows:
            self.assertTrue(row["fuel_source"].strip())
            if row["fuel_source"] == "unassigned":
                self.assertEqual(row["fuel"], "")
                self.assertIn("excluded from the fuel-specific", row["note"])
            else:
                self.assertTrue(row["fuel"])


class TestCoverageDecidesTheShapeRatherThanTheYear(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _csv(asset_path(ROOT, "data", "activity", "power", "generation_monthly_coverage.csv"))

    def test_the_grade_follows_the_measured_coverage(self):
        for row in self.rows:
            share = float(row["coverage"])
            if share > ingest.COVERAGE_IMPOSSIBLE:
                expected = "TE4"
            elif share >= ingest.COVERAGE_STRONG:
                expected = "TE2"
            elif share >= ingest.COVERAGE_WEAK:
                expected = "TE3"
            else:
                expected = "TE4"
            self.assertEqual(row["temporal_class"], expected,
                             "%s %s at %.3f" % (row["fiscal_year"], row["subitem"], share))

    def test_generation_beyond_the_control_refuses_the_shape(self):
        """Carrying a fuel label back assumes the plant burned then what it burned later, and
        Pakistan's RLNG conversions make that false in places: read per PBS fuel word,
        FY2016-17 comes to 580 percent of an RLNG control that had barely opened.

        Grouping RLNG with pipeline gas absorbs that particular case, because both land on
        one component - so no published row trips this check today, and it is driven here
        rather than asserted against the data. A check whose test needs the defect to still
        be present is a check that gets deleted the day it works.
        """
        plants = [{"fuel": "Coal", "months": [1000.0] * 12}]
        rows = ingest.coverage_rows(plants, {"Coal": 5.0}, 1000, "FYtest")
        coal = [r for r in rows if r["subitem"] == "Coal"][0]
        self.assertGreater(float(coal["coverage"]), ingest.COVERAGE_IMPOSSIBLE)
        self.assertEqual(coal["temporal_class"], "TE4")
        self.assertIn("exceeds the annual control", coal["decision"])

    def test_a_thin_year_is_declared_rather_than_shaped(self):
        """FY2016-17 and FY2017-18 label barely a third of gas generation, because PBS never
        names the fuel of Guddu, Jamshoro, Muzaffargarh or K-Electric and the ledger starts
        in FY2019-20. Those years keep their flat profile and say so."""
        thin = [r for r in self.rows
                if r["fiscal_year"] in ("FY2016-17", "FY2017-18") and r["subitem"] == "Gas"]
        self.assertEqual(len(thin), 2)
        for row in thin:
            self.assertEqual(row["temporal_class"], "TE4")
            self.assertIn("flat", row["decision"])


class TestTheShapeIsAppliedWithoutMovingAnyMass(unittest.TestCase):
    def test_every_shape_sums_to_one(self):
        """E(f,m) = E(f,FY) x G(f,m) / SUM G(f,m). The annual control does not move."""
        for year in YEARS:
            for subitem, (shares, _method, _basis) in pbs_generation.shapes(year).items():
                self.assertEqual(len(shares), 12, "%d %s" % (year, subitem))
                self.assertAlmostEqual(sum(shares.values()), 1.0, places=9,
                                       msg="%d %s" % (year, subitem))
                self.assertTrue(all(v >= 0 for v in shares.values()))

    def test_a_subitem_the_ingest_graded_TE4_gets_no_shape(self):
        for year in YEARS:
            available = pbs_generation.shapes(year)
            for row in pbs_generation.coverage(year):
                if row["temporal_class"] == "TE4":
                    self.assertNotIn(row["subitem"], available,
                                     "%s %s" % (row["fiscal_year"], row["subitem"]))

    def test_captive_generation_never_takes_the_grid_shape(self):
        """An industrial plant burning its own gas behind the meter does not follow national
        dispatch, and the grid's shape applied to it would be a borrowed profile wearing an
        observed profile's grade."""
        available = pbs_generation.shapes(2018)
        self.assertIn("Gas", available, "the fixture year no longer carries a gas shape")
        captive = {"category": pbs_generation.CAPTIVE_CATEGORY,
                   "subitem": "Captive natural gas CO2"}
        self.assertIsNone(pbs_generation.shape_for(captive, available))
        grid = {"category": "Electricity and heat production", "subitem": "Gas CO2"}
        self.assertIsNotNone(pbs_generation.shape_for(grid, available))

    def test_the_sir_years_carry_coal_and_gas_and_nothing_else(self):
        """PBS stops at FY2020-21; the SIR listing lane carries the three years after it
        (rc21). What it offers is deliberate: Coal in all three years (TE2 -> T2), Gas
        where the annual-control bound can force the RLNG/HSD group (TE3 -> T3, FY2022-23
        and FY2023-24; FY2021-22 misses the 95 percent rule and is refused), and NEVER the
        liquid fuels - those stay on the OCAC panel, which carries T1/T2 months a TE3
        generation shape must not displace."""
        expected = {2021: {"Coal": "T2"},
                    2022: {"Coal": "T2", "Gas": "T3"},
                    2023: {"Coal": "T2", "Gas": "T3"}}
        for year, fuels in expected.items():
            available = pbs_generation.shapes(year)
            self.assertEqual({s: m for s, (_sh, m, _b) in available.items()}, fuels)
            for _shares, _method, basis in available.values():
                self.assertIn("Detail of Generation listings", basis)
                self.assertNotIn("PBS", basis)

    def test_a_graded_subitem_with_no_generation_behind_it_raises(self):
        """Silence here would publish a flat line under an observed grade."""
        original = pbs_generation._generation
        pbs_generation._generation = lambda _fy: {}
        try:
            with self.assertRaises(ValueError):
                pbs_generation.shapes(2018)
        finally:
            pbs_generation._generation = original


if __name__ == "__main__":
    unittest.main()


class TestTheNepraPanelAndItsAliases(unittest.TestCase):
    """The panel says how much of each station's year came from each fuel, so no label is
    carried across a year it was not observed in - and no alias is believed on its name."""

    @classmethod
    def setUpClass(cls):
        import ingest_nepra_plant_fuel
        cls.nepra = ingest_nepra_plant_fuel
        cls.panel = _csv(asset_path(ROOT, "data", "activity", "power", "plant_fuel_generation.csv"))
        cls.series = _csv(asset_path(ROOT, "data", "activity", "power", "generation_monthly.csv"))

    def test_no_subitem_year_exceeds_the_national_control(self):
        """Partial coverage is the expected state. More generation from one fuel than the
        country produced is double counting."""
        rows = [{"fiscal_year": r["fiscal_year"], "fuel": r["fuel"],
                 "generation_gwh": float(r["generation_gwh"]) if r["generation_gwh"] else 0.0}
                for r in self.panel]
        for _year, _subitem, _total, _control, share, verdict in self.nepra.reconcile(rows):
            self.assertEqual(verdict, "OK")
            self.assertLessEqual(share, self.nepra.CEILING)

    def test_not_published_is_empty_and_carries_its_reason(self):
        for row in self.panel:
            if not row["generation_gwh"]:
                self.assertIn("not published", row["note"])

    def test_every_alias_is_corroborated_by_magnitude(self):
        """THE TEST THAT MAKES A HAND-WRITTEN ALIAS SAFE.

        Each pairing is a human judgement about two strings, and a wrong one would relabel a
        station's fuel with complete confidence. So every alias must also make the two
        sources' own annual generation agree for the same year. The band allows for PBS
        reporting generation GROSS where NEPRA's table is net of auxiliary consumption, which
        runs to about a tenth at the old thermal stations - TPS Muzaffargarh sits at 1.10 for
        exactly that reason. It does not allow for the alias being wrong: PBS's
        `TPS GUDDU(5-13)` was proposed as NEPRA's Units 5-10 plus 11-13, read 1.46 and then
        2.36 against them, and was removed. Guddu's unit ranges do not reconcile between the
        two publications and the station stays unassigned in those years.
        """
        pbs = collections.defaultdict(float)
        for row in self.series:
            pbs[(ingest._normalise(row["plant"]), row["fiscal_year"])] += float(row["gwh"])
        panel = ingest.panel_totals()
        checked = 0
        for name, targets in ingest.aliases().items():
            for start in range(ingest.FIRST_FY_START, ingest.LAST_FY_START + 1):
                label = "FY%d-%02d" % (start, (start + 1) % 100)
                theirs = sum(sum(panel.get((t, label), {}).values()) for t in targets)
                ours = pbs.get((name, label), 0.0)
                if not (theirs and ours):
                    continue
                checked += 1
                self.assertGreater(ours / theirs, 0.85, "%s %s" % (name, label))
                self.assertLess(ours / theirs, 1.20, "%s %s" % (name, label))
        self.assertGreater(checked, 10, "the alias table has stopped being corroborated")

    def test_a_mixed_plant_year_is_never_labelled(self):
        """TPS Jamshoro is 74 percent gas in FY2015-16 and 30 percent in FY2019-20. A station
        that genuinely burned a mixture must not have that mixture spread over the months by
        assertion - Pakistani plant swings to furnace oil at the summer peak, so a constant
        within-year mix is wrong in exactly the direction this product is measuring."""
        panel = ingest.panel_totals()
        mixed = 0
        for (plant, label) in panel:
            found = ingest.dominant_fuel(panel, [plant], label)
            if found and found[1] < ingest.DOMINANT:
                mixed += 1
                labelled = [r for r in self.series
                            if ingest._normalise(r["plant"]) == plant
                            and r["fiscal_year"] == label
                            and r["fuel_source"].startswith("nepra_panel")]
                self.assertFalse(labelled, "%s %s is %.0f%% one fuel and was labelled anyway"
                                 % (plant, label, 100 * found[1]))
        self.assertGreater(mixed, 0, "no station burns a mixture, which cannot be right")

    def test_a_panel_label_records_the_share_it_rested_on(self):
        for row in self.series:
            if row["fuel_source"].startswith("nepra_panel"):
                share = int(row["fuel_source"].rsplit("_", 1)[1].rstrip("%"))
                self.assertGreaterEqual(share, int(100 * ingest.DOMINANT))

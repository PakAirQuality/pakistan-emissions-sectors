"""The cube's period is a parameter, and the registries are what define it.

WHY THIS EXISTS. grid_cube.py used to name FY2023-24 in nine spellings - a month tuple, a
`year == "2023"` filter on the population panel, a `fiscal_year != "2023"` filter on the plant
ledger, a NetCDF time origin written out as a date. Keying one of them to the wrong year while
the rest stayed right would not have failed: it would have placed one year's mass on another
year's surface and closed every conservation identity while doing it. The spellings now come
from one object read from data/periods.csv and data/months.csv, and these tests hold the two
properties that makes the object worth having: it agrees with the literal it replaced, and it
works for the eight years the cube has never been built for.

WHAT IS NOT CLAIMED HERE. The cube still BUILDS one period. Making the year a parameter is not
the same as reading nine years of activity, and the test that the reference year is still the
only buildable one is written below as a fact about this increment, not as a limit anyone
should preserve - it is the next increment's job to retire it.
"""

from pkinv.assets import asset_path
import unittest

from pkinv.report import grid_cube

from _support import cached_build


class TestPeriodKeys(unittest.TestCase):

    def test_the_reference_months_are_the_literal_they_replaced(self):
        """The byte-identity anchor: the retired tuple, spelled out one last time."""
        retired = tuple("2023%02d" % m for m in range(7, 13)) \
            + tuple("2024%02d" % m for m in range(1, 7))
        self.assertEqual(grid_cube.MONTHS, retired)
        self.assertEqual(grid_cube.REFERENCE.months, retired)
        self.assertEqual(grid_cube.REFERENCE.period_id, "FY2023-24")

    def test_every_registered_period_resolves_to_twelve_consecutive_months(self):
        import csv
        import os
        from pkinv.paths import DATA
        with open(asset_path(DATA, "periods.csv"), newline="", encoding="utf-8") as handle:
            periods = [r["period_id"] for r in csv.DictReader(handle)]
        self.assertEqual(len(periods), 9, "the period registry should hold nine fiscal years")
        for period_id in periods:
            keys = grid_cube.period_keys(period_id)
            self.assertEqual(len(keys.months), 12, period_id)
            # July to June, in order, with no month borrowed from a neighbouring year
            self.assertEqual(keys.months[0], "%s07" % keys.fiscal_start_year, period_id)
            self.assertEqual(keys.months[-1], "%s06" % keys.file_token, period_id)
            self.assertEqual(sorted(keys.months), list(keys.months), period_id)
            self.assertIn(keys.days, (365, 366), period_id)

    def test_the_spellings_cannot_disagree_with_each_other(self):
        """fiscal_start_year and the first month are one fact, not two."""
        for period_id in ("FY2015-16", "FY2019-20", "FY2023-24"):
            keys = grid_cube.period_keys(period_id)
            self.assertEqual(keys.months[0][:4], keys.fiscal_start_year, period_id)
            self.assertEqual(keys.label, keys.period_id, period_id)

    def test_population_is_read_at_the_fiscal_MIDPOINT_and_not_the_opening_year(self):
        """This test used to assert census_year == fiscal_start_year, on the reading that the
        two were "one fact, not three". They are not one fact. fiscal_start_year is a label
        for an interval; the population that interval integrates is a STOCK, and reading the
        year the interval opens in takes it six months before the midpoint - neither the mean
        over the period nor the middle of it.

        A fiscal year runs July to June, so its midpoint is 1 January, exactly halfway between
        two mid-year estimates. Every period therefore reads two vintages at equal weight,
        including the reference: FY2023-24 is mean(2023, 2024), and the panel holds 2000-2024
        so no period has to borrow a neighbour's."""
        for period_id, expected in (("FY2015-16", (("2015", 0.5), ("2016", 0.5))),
                                    ("FY2019-20", (("2019", 0.5), ("2020", 0.5))),
                                    ("FY2023-24", (("2023", 0.5), ("2024", 0.5)))):
            keys = grid_cube.period_keys(period_id)
            self.assertEqual(keys.population_years, expected, period_id)
            self.assertAlmostEqual(sum(w for _y, w in keys.population_years), 1.0, places=12)
            # the opening year alone is what this replaced, and it is no longer the answer
            self.assertNotEqual(keys.population_years, ((keys.fiscal_start_year, 1.0),))

    def test_an_unregistered_period_raises_and_names_what_is_held(self):
        with self.assertRaises(ValueError) as caught:
            grid_cube.period_keys("FY2029-30")
        self.assertIn("FY2029-30", str(caught.exception))
        self.assertIn("FY2023-24", str(caught.exception))

    def test_the_year_filtered_ledgers_take_the_period_and_read_a_different_year(self):
        """The point of the parameter: a different period selects different rows.

        The plant fuel ledger spans FY2019-20..FY2023-24 and the airport movement panel starts
        in 2006, so both genuinely answer for a year that is not the reference - which is the
        property that would have been silently absent if the filters had stayed literals."""
        reference = grid_cube.airport_points()
        earlier = grid_cube.airport_points(grid_cube.period_keys("FY2015-16"))
        self.assertTrue(reference and earlier)
        self.assertNotEqual(sorted(reference), sorted(earlier),
                            "a different period returned the reference year's airports")


class TestTheCubeBuildsEveryRegisteredPeriod(unittest.TestCase):
    """Nine cubes, built once and shared, because the property under test is the whole set.

    THE CLOSURE IDENTITY IS THE POINT. A cube that ran for an earlier year and placed the
    wrong mass would raise nothing: conservation is a property of weights summing to one, not
    of the weights being the right year's. So the test is not "it ran" but "the mass that
    reached the grid, plus the mass explicitly not placed below ADM1, is the mass the national
    panel says that year had" - per year and per gas.
    """

    @classmethod
    def setUpClass(cls):
        import collections
        import csv
        import os

        from pkinv.paths import DATA, OUTPUTS
        with open(asset_path(DATA, "periods.csv"), newline="", encoding="utf-8") as handle:
            cls.periods = [r["period_id"] for r in csv.DictReader(handle)]
        cls.national = collections.defaultdict(lambda: collections.defaultdict(float))
        panel = os.path.join(OUTPUTS, grid_cube.PANEL)
        with open(panel, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(l for l in handle if not l.startswith("#")):
                cls.national[row["period_id"]][row["gas"]] += \
                    float(row["emission_native_mass"])
        # cached_build, not build: test_spatial_by_year performs the IDENTICAL nine-period
        # sweep, so these nine cubes were built twice per suite run. Same arguments, same
        # object, one computation - see _support.cached_build for why the memo is not in
        # grid_cube itself.
        cls.built = {p: cached_build(period=grid_cube.period_keys(p), ledger=False)
                     for p in cls.periods}

    def test_every_period_closes_against_its_own_national_total(self):
        import collections
        for period_id, result in self.built.items():
            unallocated = collections.defaultdict(float)
            for row in result["unallocated"]:
                unallocated[row["gas"]] += row["emissions_Gg"]
            for gas in grid_cube.GASES:
                placed = float(result["gas_month"][gas].sum()) + unallocated[gas]
                want = self.national[period_id][gas]
                # The reference year is controlled by the stream ledger and every other year by
                # the panel, and the two agree only to the ledger's eight printed decimals -
                # which is the whole of this tolerance. See monthly_layer's docstring.
                self.assertAlmostEqual(placed / want, 1.0, places=6,
                                       msg="%s %s: %.6f placed against %.6f"
                                           % (period_id, gas, placed, want))

    def test_a_year_carries_the_streams_it_has_and_no_others(self):
        """Not every stream exists in every year, and the absences are structural: cement gas
        in the FY2020-21 curtailment year, bagasse power before FY2019-20, railway furnace oil
        before FY2021-22. A year with fewer streams is correct, not broken."""
        counts = {p: len(r["streams"]) for p, r in self.built.items()}
        # +6 everywhere at rc46 Wave 2: brick and cement coal x three gases exist in every
        # year of the window (the HDIP series has no gap years for either consumer).
        # +3 everywhere at rc47 Wave 3: the aviation LTO/cruise split turns three
        # domestic streams into six, in every year the category exists (the same
        # fuel account split by stage, so no year gains or loses a category).
        self.assertEqual(counts["FY2023-24"], 202)   # rc52: + ammonia, steel, lubricating oil, grease
        self.assertEqual(counts["FY2015-16"], 197)   # rc52: + ammonia, steel, oil, grease in every year
        self.assertEqual(counts["FY2020-21"], 196)
        for period_id, count in counts.items():
            self.assertLessEqual(count, 202, period_id)
            self.assertGreaterEqual(count, 192, period_id)

    def test_no_year_places_another_year_s_months(self):
        for period_id, result in self.built.items():
            months = {m for s in result["streams"] for m in s["monthly_share"]}
            self.assertEqual(months, set(grid_cube.period_keys(period_id).months), period_id)

    def test_the_years_are_not_all_the_same_cube(self):
        """The trap this guards: build() ignoring its period argument would close every
        identity above, because each year would be checked against its own panel total only if
        the mass actually differed. It has to be asserted that it does."""
        totals = {p: round(float(r["gas_month"]["CO2"].sum()), 3)
                  for p, r in self.built.items()}
        self.assertEqual(len(set(totals.values())), len(totals),
                         "two periods produced identical grids: %s" % totals)


class TestTheReferenceYearIsNotRebased(unittest.TestCase):

    def test_the_panel_and_the_reference_file_carry_the_same_numbers(self):
        """load_streams reads the reference year from national_monthly_2024.csv and every
        other year from the nine-year panel. That split is a PRECISION decision - the file
        prints eight decimals, the panel twelve - so it is only honest while the two agree."""
        import csv
        import os

        from pkinv.paths import OUTPUTS
        from pkinv.report.source_streams import stream_id

        def read(name, keys):
            out = {}
            with open(os.path.join(OUTPUTS, name), newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(l for l in handle if not l.startswith("#")):
                    if "period_id" in row and row["period_id"] != "FY2023-24":
                        continue
                    sid = stream_id(*(row[k] for k in keys))
                    out[(sid, row["month"])] = float(row["share"])
            return out

        one = read("national_monthly_2024.csv", ("sector", "category", "subitem", "gas"))
        two = read(grid_cube.PANEL, ("sector_id", "category", "subitem", "gas"))
        self.assertEqual(set(one), set(two))
        # 2340 since rc46 Wave 2 (+72: the two solid-fuel streams x three gases x
        # twelve months); 2376 since rc47 Wave 3 (+36: the aviation LTO/cruise split,
        # three streams becoming six) - present in both monthly sources or in neither,
        # which is the identity this test holds.
        self.assertEqual(len(one), 2424)   # rc52: 202 components x twelve months
        worst = max(abs(one[k] - two[k]) for k in one)
        self.assertLess(worst, 1e-8, "the two monthly sources have diverged: %.3e" % worst)


class TestWhatThisIncrementDoesNotYetDo(unittest.TestCase):
    """Facts about the current state, written down so the next increment retires them
    deliberately rather than discovering them."""

    def test_configuration_l_is_refused_for_any_period_but_the_reference(self):
        """L_2023_24 needs a monthly layer that exists for one year; the writers say so
        rather than being right by accident because a module constant happened to hold.

        rc67: the second configuration these writers serve was S (the survey reading)
        through rc66 and is L (the ledger) now; the refusal is the same refusal."""
        acc = {"period": grid_cube.period_keys("FY2015-16")}
        for writer in (grid_cube.write_adm1_ledger, grid_cube.write_adm2_ledger):
            with self.assertRaises(ValueError) as caught:
                writer(acc, "/dev/null")
            self.assertIn("FY2015-16", str(caught.exception))

    def test_the_monthly_grain_remains_the_reference_year_alone(self):
        """Retired and replaced, rather than deleted, at the annual-grid increment.

        This used to read "the SHIPPED products are still the reference year's alone" and
        assert the same constant. That sentence stopped being true when
        pakemis_grid_0p05_annual_ref_fy2015_16_fy2023_24.nc shipped nine periods, so the claim
        is narrowed to the one that survived: the MONTHLY grain is still the reference year's.
        Eight historical years have annual cells and no monthly ones, because a historical
        month's seasonal geography is not evidenced - and the annual cube's own tests
        (tests/test_annual_grid.py) now hold the nine-period side of this.
        """
        import os
        from pkinv.paths import OUTPUTS
        self.assertEqual(grid_cube.REFERENCE.file_token, "2024")
        self.assertTrue(os.path.exists(os.path.join(
            OUTPUTS, "pakemis_grid_0p05_annual_ref_fy2015_16_fy2023_24.nc")),
            "the annual cube is gone: this test's premise, that history moved to the annual "
            "grain, no longer holds and the monthly claim must be re-examined")


if __name__ == "__main__":
    unittest.main()

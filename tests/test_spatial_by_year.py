"""The nine-year ADM1 and ADM2 products: every year closes, and the reference year agrees
with the product that already shipped.

THE TEST THAT MATTERS MOST is the last one. A new annual ADM2 table could close every identity
in this file and still be a SECOND VINTAGE of the same geography - built on the raw district
binning rather than the canonical fractional partition the monthly view uses, disagreeing only
at shared boundary cells, where nobody would look. So the reference year's rows in the new
product are compared, cell for cell, against outputs/pakemis_adm2_monthly.csv summed over its
twelve months. If those two ever part company, one of them is wrong and the failure names which
pair diverged.
"""

from pkinv.assets import asset_path
import collections
import csv
import os
import unittest

from pkinv.paths import DATA, OUTPUTS
from _support import cached_build

REFERENCE = "FY2023-24"


def rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(l for l in handle if not l.startswith("#")))


class TestNineYearSpatialProducts(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.adm1 = rows(os.path.join(OUTPUTS, "pakemis_adm1_by_year.csv"))
        cls.adm2 = rows(os.path.join(OUTPUTS, "pakemis_adm2_by_year.csv"))
        cls.fallbacks = rows(os.path.join(OUTPUTS,
                                          "pakemis_grid_fallbacks_by_year.csv"))
        cls.periods = [r["period_id"] for r in rows(asset_path(DATA, "periods.csv"))]
        cls.national = collections.defaultdict(lambda: collections.defaultdict(float))
        for row in rows(os.path.join(OUTPUTS,
                                     "pakemis_monthly_fy2015_16_fy2024_25.csv")):
            cls.national[row["period_id"]][row["gas"]] += float(row["emission_native_mass"])

    def test_both_products_carry_every_registered_period(self):
        self.assertEqual(set(self.periods), {r["period_id"] for r in self.adm1})
        for table, name in ((self.adm1, "adm1"), (self.adm2, "adm2"),
                            (self.fallbacks, "fallbacks")):
            self.assertEqual({r["period_id"] for r in table}, set(self.periods), name)

    def test_adm1_reproduces_each_year_s_national_total(self):
        got = collections.defaultdict(lambda: collections.defaultdict(float))
        for row in self.adm1:
            got[row["period_id"]][row["gas"]] += float(row["emissions_Gg"])
        for period_id in self.periods:
            for gas in ("CO2", "CH4", "N2O"):
                self.assertAlmostEqual(
                    got[period_id][gas] / self.national[period_id][gas], 1.0, places=6,
                    msg="%s %s" % (period_id, gas))

    def test_adm2_plus_unallocated_reproduces_adm1(self):
        """The closure identity with two terms: mass below ADM1, and mass explicitly not
        placed below it. A stream cannot quietly appear in neither."""
        unallocated = collections.defaultdict(lambda: collections.defaultdict(float))
        for row in rows(os.path.join(OUTPUTS, "pakemis_spatial_unallocated.csv")):
            unallocated[REFERENCE][row["gas"]] += float(row["emissions_Gg"])
        adm1 = collections.defaultdict(lambda: collections.defaultdict(float))
        for row in self.adm1:
            adm1[row["period_id"]][row["gas"]] += float(row["emissions_Gg"])
        # EVERY view, not one: the view axis PARTITIONS the mass - each stream belongs to a
        # single view - so filtering to `physical` would silently drop the streams booked to
        # origin and accounting, about a quarter of the CO2.
        adm2 = collections.defaultdict(lambda: collections.defaultdict(float))
        for row in self.adm2:
            if row["emissions_Gg"]:
                adm2[row["period_id"]][row["gas"]] += float(row["emissions_Gg"])
        for gas in ("CO2", "CH4", "N2O"):
            placed = adm2[REFERENCE][gas] + unallocated[REFERENCE][gas]
            self.assertAlmostEqual(placed / adm1[REFERENCE][gas], 1.0, places=6, msg=gas)

    def test_every_year_closes_adm1_to_adm2_plus_what_is_not_placed(self):
        """The reference year has a published unallocated table; the other eight do not yet,
        so their unplaced mass is taken from the build itself - the 24 industry streams the
        cube declines to place below ADM1 - and the identity is asserted for all nine."""
        from pkinv.report import grid_cube
        adm1 = collections.defaultdict(lambda: collections.defaultdict(float))
        for row in self.adm1:
            adm1[row["period_id"]][row["gas"]] += float(row["emissions_Gg"])
        adm2 = collections.defaultdict(lambda: collections.defaultdict(float))
        for row in self.adm2:
            if row["emissions_Gg"]:
                adm2[row["period_id"]][row["gas"]] += float(row["emissions_Gg"])
        for period_id in self.periods:
            # cached_build: these are the same nine cubes test_grid_cube_period builds.
            result = cached_build(period=grid_cube.period_keys(period_id), ledger=False)
            unplaced = collections.defaultdict(float)
            for row in result["unallocated"]:
                unplaced[row["gas"]] += row["emissions_Gg"]
            for gas in ("CO2", "CH4", "N2O"):
                placed = adm2[period_id][gas] + unplaced[gas]
                self.assertAlmostEqual(placed / adm1[period_id][gas], 1.0, places=6,
                                       msg="%s %s" % (period_id, gas))

    def test_a_declared_absence_stays_non_numeric(self):
        """A unit with no drawable polygon carries a typed reason and an EMPTY number, so a
        downstream sum cannot absorb it and a downstream reader cannot miss it."""
        absences = [r for r in self.adm2 if r["absence_reason"]]
        self.assertTrue(absences)
        for row in absences:
            self.assertEqual(row["emissions_Gg"], "", row["adm2_ids"])

    def test_the_reference_year_agrees_with_the_shipped_monthly_view(self):
        """The second-vintage guard. Same partition or the two views disagree at boundary
        cells - see grid_cube.adm2_view_rows and the rc32/rc40 comments it carries."""
        monthly = collections.defaultdict(float)
        for row in rows(os.path.join(OUTPUTS, "pakemis_adm2_monthly.csv")):
            if row["emissions_Gg"]:
                monthly[(row["shape_id"], row["gas"], row["spatial_view"])] += \
                    float(row["emissions_Gg"])
        annual = {(r["shape_id"], r["gas"], r["spatial_view"]): float(r["emissions_Gg"])
                  for r in self.adm2
                  if r["period_id"] == REFERENCE and r["emissions_Gg"]}
        self.assertEqual(set(annual), set(monthly),
                         "the annual and monthly ADM2 views cover different cells")
        worst, where = 0.0, None
        for key, value in annual.items():
            want = monthly[key]
            diff = abs(value - want) / want if want else abs(value)
            if diff > worst:
                worst, where = diff, key
        self.assertLess(worst, 1e-9,
                        "annual and monthly ADM2 disagree at %s by %.3e" % (where, worst))


class TestTheMonthsBelowTheNation(unittest.TestCase):
    """The 108-month product at ADM2. It is the SAME view the annual table is built from -
    summed rather than re-derived - so the two cannot disagree, and the reference year's rows
    must still be the file that already shipped."""

    @classmethod
    def setUpClass(cls):
        cls.monthly = rows(os.path.join(OUTPUTS, "pakemis_adm2_monthly_by_year.csv"))
        cls.annual = rows(os.path.join(OUTPUTS, "pakemis_adm2_by_year.csv"))

    def test_the_product_carries_twelve_months_per_registered_period(self):
        months = {r["month"] for r in self.monthly} - {"all"}
        from pkinv.report.annual_grid import period_bounds
        periods = {p[0] for p in period_bounds()}
        self.assertEqual(len(months), 12 * len(periods))
        self.assertEqual({r["period_id"] for r in self.monthly}, periods)

    def test_the_reference_year_is_the_file_that_already_shipped(self):
        """Byte-for-byte, not approximately: a second monthly ADM2 table that differed from
        the shipped one would be a second vintage of the same geography."""
        shipped = rows(os.path.join(OUTPUTS, "pakemis_adm2_monthly.csv"))
        key = lambda r: (r["shape_id"], r["adm2_ids"], r["province"], r["gas"], r["month"],
                         r["spatial_view"])
        mine = {key(r): r["emissions_Gg"] for r in self.monthly
                if r["period_id"] == "FY2023-24"}
        theirs = {key(r): r["emissions_Gg"] for r in shipped}
        self.assertEqual(mine, theirs)

    def test_the_annual_table_is_this_one_summed(self):
        import collections
        key = lambda r: (r["period_id"], r["shape_id"], r["adm2_ids"], r["province"],
                         r["gas"], r["spatial_view"])
        summed = collections.defaultdict(float)
        for row in self.monthly:
            if row["emissions_Gg"]:
                summed[key(row)] += float(row["emissions_Gg"])
        checked = 0
        for row in self.annual:
            if not row["emissions_Gg"]:
                continue
            want, got = summed[key(row)], float(row["emissions_Gg"])
            if want == 0.0:
                # A cell whose twelve months are all zero: the annual must be zero too, and a
                # ratio would say nothing. Asserted rather than skipped.
                self.assertEqual(got, 0.0, str(key(row)))
            else:
                self.assertAlmostEqual(got / want, 1.0, places=9, msg=str(key(row)))
            checked += 1
        self.assertGreater(checked, 10000)


class TestTheFrameIsFixedAndSaysSo(unittest.TestCase):
    """One frame for nine years is a choice, not a fact about Pakistan, so it is printed on
    the products and held here rather than assumed."""

    def test_the_contract_declares_the_frame_and_what_a_past_year_s_row_means(self):
        """The declaration lives in the contract document and not in a CSV banner, because
        claim pointers read these products with comments=False on purpose - a banner must not
        be able to change a count."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "docs", "spatial_products_contract.md"),
                  encoding="utf-8") as handle:
            contract = handle.read()
        self.assertIn("geoBoundaries-gbOpen-PAK-ADM2-2019", contract)
        self.assertIn("abs-adm2-frame-vintage", contract)
        for phrase in ("one fixed frame", "carved_from", "legacy_aggregate"):
            self.assertIn(phrase, contract)

    def test_no_by_year_product_carries_a_comment_banner(self):
        """The rule the banner broke, now held: these products are read by claim pointers
        with comments=False, so a leading '#' block would be parsed as data."""
        for name in ("pakemis_adm1_by_year.csv", "pakemis_adm2_by_year.csv",
                     "pakemis_adm2_monthly_by_year.csv",
                     "pakemis_grid_fallbacks_by_year.csv"):
            with open(os.path.join(OUTPUTS, name), encoding="utf-8") as handle:
                self.assertFalse(handle.readline().startswith("#"), name)

    def test_the_frame_is_one_geometry_version_for_every_unit(self):
        """If the canonical frame ever carried two vintages the header's claim would quietly
        stop being true, and no closure test would notice."""
        frame = rows(asset_path(DATA, "adm2_canonical.csv"))
        self.assertEqual({r["geometry_version"] for r in frame},
                         {"geoBoundaries-gbOpen-PAK-ADM2-2019"})
        self.assertEqual(len(frame), 152)

    def test_the_missing_creation_dates_are_a_declared_absence_not_a_silence(self):
        """Not in monthly_data_requests.csv: that registry is keyed to the monthly
        DECOMPOSITION's components, and a district-frame gap is not one of them - the
        generator rejected it, correctly. The validation catalog's declared_absence lane is
        the mechanism built for exactly this."""
        catalog = rows(asset_path(DATA, "validation_catalog.csv"))
        row = next((r for r in catalog if r["validation_id"] == "abs-adm2-frame-vintage"),
                   None)
        self.assertIsNotNone(row, "the district-frame gap must be a declared absence")
        self.assertEqual(row["wired"], "declared_absence")
        self.assertIn("effective_date", row["source"])
        self.assertIn("today's boundary", row["interpretation_limit"].lower())

    def test_the_frame_carries_labels_where_dates_would_be(self):
        """The reason the request exists, asserted so nobody later mistakes the column for
        dates and writes a filter against it."""
        frame = rows(asset_path(DATA, "adm2_canonical.csv"))
        values = {r["effective_date"] for r in frame}
        self.assertEqual(values, {"census_2023", "boundary_2019", "pre_subdivision",
                                  "ag_census_2024", "n/a"})


class TestTheSubstitutionRecordIsPublishedPerYear(unittest.TestCase):
    """The record existed and nothing read it. These hold the fact that made it worth
    publishing: the earlier years are not marginally more substituted, they are categorically
    more substituted, because the evidence those years would need does not exist."""

    @classmethod
    def setUpClass(cls):
        cls.fallbacks = rows(os.path.join(OUTPUTS, "pakemis_grid_fallbacks_by_year.csv"))
        cls.allowed = {(r["scope"], r["declared"], r["used"])
                       for r in rows(asset_path(DATA, "allowed_grid_fallbacks.csv"))}

    def test_every_substitution_in_every_year_is_allow_listed(self):
        """The fail-closed gate over every supported core period."""
        for row in self.fallbacks:
            self.assertIn((row["scope"], row["declared"], row["used"]), self.allowed,
                          "%s %s" % (row["period_id"], row["source_stream_id"]))
            if (row["scope"], row["declared"], row["used"]) == \
                    ("raster", "firms_fire", "cropland"):
                self.assertEqual(row["period_id"], "FY2024-25",
                                 "a held-period FIRMS layer was lost, rather than extended")

    def test_the_grid_fleet_substitution_stays_small_in_every_year(self):
        """Rewritten at rc46 Wave 1, which retired the premise of its predecessor.

        The old guard held two absences an order of magnitude apart: before FY2019-20 there
        was no plant fuel ledger and the WHOLE fleet rode built-up (42-53 Mt a year); from
        FY2019-20 about half the gas fuel sat on unlocated plants (10-15 Mt). Wave 1 removed
        both causes - the early years draw a per-station pool from the generation panel
        through the name crosswalk, and seventeen gas/RFO stations acquired coordinates - so
        the measured fallback collapsed to 0.09-0.96 Mt (panel years) and 1.2-5.4 Mt (ledger
        years, the typed skip list: a GOGPT source defect, the JDW-III identity conflict,
        Nooriabad approximate-only).

        Rewritten AGAIN at rc47 Wave 2, because the rc46 numbers this docstring used to
        quote (0.09-0.96 Mt for the panel years) were an artefact of the defect the
        twenty-first review found: located_activity_share returned None for a panel
        year, grid_weight read None as 1.0, and the 24-38%% of generation that was
        blank-fuel or unlocated was silently renormalised onto the located stations -
        the fallback ledger UNDERSTATED by construction. The share is measured now
        (labelled-and-located over everything, blank rows in the denominator), so the
        three low-coverage years price 13-18 Mt of genuinely unplaceable fuel and
        FY2018-19 - the year the panel's labelling is nearly complete - stays small
        honestly.

        What this asserts now: the fallback never reads zero (that would mean the
        events stopped being priced), the three low-coverage panel years stay in the
        measured regime rather than sliding back to the flattering one, and FY2018-19
        stays small because its coverage is real.
        """
        import collections
        mass = collections.defaultdict(float)
        for row in self.fallbacks:
            if row["declared"] == "grid station points":
                mass[row["period_id"]] += float(row["affected_Mt_AR5"])
        for period_id in ("FY2015-16", "FY2016-17", "FY2017-18"):
            self.assertGreater(mass[period_id], 5.0,
                               "%s: a low-coverage panel year below 5 Mt means the "
                               "blank-fuel mass stopped being priced - the rc46 "
                               "understatement returning" % period_id)
            self.assertLess(mass[period_id], 25.0,
                            "%s: above 25 Mt the panel pool stopped resolving its "
                            "fleet at all" % period_id)
        self.assertGreater(mass["FY2018-19"], 0.01, "FY2018-19")
        self.assertLess(mass["FY2018-19"], 2.0,
                        "FY2018-19: near-complete labelling (97.9%%) should keep this "
                        "year in the small regime")
        for period_id in ("FY2019-20", "FY2020-21", "FY2021-22", "FY2022-23", "FY2023-24"):
            self.assertGreater(mass[period_id], 0.5, period_id)
            self.assertLess(mass[period_id], 7.0,
                            "%s: a ledger year above 7 Mt means an rc46 coordinate was "
                            "lost or the pooling defect returned" % period_id)

    def test_the_reference_year_matches_the_cube_s_own_fallback_file(self):
        """One record, two views of it - the by-year file must not drift from the file the
        cube writes for the reference year."""
        shipped = rows(os.path.join(OUTPUTS, "pakemis_grid_fallbacks.csv"))
        mine = [r for r in self.fallbacks if r["period_id"] == "FY2023-24"]
        self.assertEqual(len(mine), len(shipped))
        key = lambda r: (r["source_stream_id"], r["scope"], r["province"], r["shape"],
                         r["reason"], r["affected_Gg"])
        self.assertEqual(sorted(map(key, mine)), sorted(map(key, shipped)))


class TestTheExactStreamPricedCo2e(unittest.TestCase):
    """The sector ADM2 tables carry an EXACT co2e column, priced per stream at
    accumulation (each stream's own CH4 origin) - the column that retired the
    [x28, x30] interval the module grain used to force. The identity per row: a
    single-gas mass admits its gas's factor band, and only CH4 has a band at all
    (mixed-origin modules land strictly inside it; single-origin ones at an end)."""

    FACTORS = {"CO2": (1.0, 1.0), "CH4": (28.0, 30.0), "N2O": (265.0, 265.0)}

    def test_every_priced_row_sits_in_its_gas_s_factor_band(self):
        path = os.path.join(OUTPUTS, "pakemis_adm2_sector_by_year.csv")
        checked = 0
        with open(path, newline="", encoding="utf-8") as handle:
            for r in csv.DictReader(l for l in handle if not l.startswith("#")):
                if r["emissions_Gg"] in ("", "0") or float(r["emissions_Gg"]) <= 0:
                    continue
                mass, co2e = float(r["emissions_Gg"]), float(r["co2e_Mt_AR5"])
                lo, hi = self.FACTORS[r["gas"]]
                # ABSOLUTE bound: the two columns are rounded independently (mass at
                # 8 dp Gg, co2e at 12 dp Mt) and the ANNUAL row is a sum of twelve
                # such roundings, so the honest slack is n x half-ulp of each column,
                # priced - a ratio check would explode on small masses instead
                eps = 12 * (0.5e-8 * hi / 1000.0 + 0.5e-12) + 1e-9 * (1.0 + co2e)
                self.assertTrue(mass * lo / 1000.0 - eps <= co2e <= mass * hi / 1000.0 + eps,
                                "%s %s %s %s: co2e %.12f outside [%s, %s] x mass"
                                % (r["period_id"], r["module"], r["gas"], r["shape_id"],
                                   co2e, lo, hi))
                checked += 1
        self.assertGreater(checked, 20000, "the identity must actually bite")

    def test_the_mixed_modules_price_strictly_inside_the_band_somewhere(self):
        """If every CH4 row of power and residential sat AT 28 or AT 30, the pricing
        would not be doing the one thing it exists for: mixing the origins a module
        actually burns. At least one row of each must be strictly interior."""
        path = os.path.join(OUTPUTS, "pakemis_adm2_sector_by_year.csv")
        interior = set()
        with open(path, newline="", encoding="utf-8") as handle:
            for r in csv.DictReader(l for l in handle if not l.startswith("#")):
                if r["gas"] != "CH4" or r["module"] not in ("power", "residential"):
                    continue
                if r["emissions_Gg"] in ("", "0") or float(r["emissions_Gg"]) <= 0:
                    continue
                implied = float(r["co2e_Mt_AR5"]) * 1000.0 / float(r["emissions_Gg"])
                if 28.001 < implied < 29.999:
                    interior.add(r["module"])
        self.assertEqual(interior, {"power", "residential"})


class TestTheLocatedShareDoesNotDependOnTheHashSeed(unittest.TestCase):
    """rc69: located_activity_share summed a set of plant names, so its last digits followed
    PYTHONHASHSEED and the fallback register moved between two runs of the same tree. The
    seed is not pinned anywhere in the build, so every run is a different seed; this asks
    two seeds for the same values."""

    PROBE = ("from pkinv.report import grid_cube as g\n"
             "for profile, period in (('power_gas', 'FY2015-16'), ('power_coal', 'FY2019-20'),"
             " ('power_rfo', 'FY2017-18'), ('power_hsd', 'FY2018-19')):\n"
             "    print(repr(g.located_activity_share(profile, g.period_keys(period))))\n")

    def test_two_seeds_give_the_same_shares(self):
        import subprocess
        import sys
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        seen = set()
        for seed in ("1", "3"):
            env = dict(os.environ, PYTHONHASHSEED=seed,
                       PYTHONPATH=os.path.join(root, "src"))
            seen.add(subprocess.check_output([sys.executable, "-c", self.PROBE], cwd=root,
                                             env=env, text=True))
        self.assertEqual(len(seen), 1, seen)


if __name__ == "__main__":
    unittest.main()

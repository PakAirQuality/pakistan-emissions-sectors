"""The nine-year ensemble: it describes the published inventory, and its correlation is real.

WHY THESE TESTS AND NOT OTHERS. An uncertainty product is unusually easy to ship broken,
because a wrong band looks exactly like a right one. Three things can go wrong here and each
has a test rather than a paragraph.

1. THE ENSEMBLE COULD DISPERSE AROUND THE WRONG NUMBER. A band on a central estimate that is
   not the published one is worse than no band. Closure is asserted before any draw.

2. THE CORRELATION COULD BE WIRED BACKWARDS AND NOBODY WOULD SEE IT. Sharing a draw across
   years must NARROW a difference and must leave a LEVEL alone. Both directions are asserted,
   because a scenario that changed the levels would mean the streams are not common random
   numbers at all - which is the defect uncertainty_all found in the fossil-carbon scenarios
   and which cost a release before it was caught.

3. `_mc_key` CARRIES A CONTRACT THAT LIVED IN ONE DOCSTRING. core.parameters.original_category
   reads its first field to recover the engine category through uncertainty_all's by-sector
   relabelling. This module's first draft led the key with the sector name instead, and every
   category-scoped dependency group stopped binding. It failed loudly, which is the only
   reason it cost an hour rather than a release; it is asserted here now.

Run:  python3 -m unittest discover tests -p "test_longitudinal_uncertainty.py"
"""
import collections
import csv
import os
import re
import unittest

from pkinv.core import montecarlo as mc
from pkinv.paths import OUTPUTS
from pkinv.report import longitudinal_uncertainty as lu
from pkinv.core.io import read_rows

# Small enough to run in a test, large enough that the comparisons below are not noise.
N_ITER = 4000

# Measured when this guard was written (rc27): about eight percent of national variance sat in
# parameters shared across years, four fifths was unexplained residual. rc39 named the
# agriculture factors and the residual fell to a few percent; rc42 (T-2) made the shares
# covariance-aware (a group's members add before squaring) and the reference year reads about
# 77 / 21 / 2. These are ratchets in the honest direction - the residual share may FALL as
# parameters are attributed, and if it rises someone has widened the unexplained part of this
# inventory and should say so; the resampling floor is the one the rc41 sum-of-squares
# arithmetic (10.67) cannot pass.
RESIDUAL_SHARE_CEILING_PCT = 10.0
PERSISTS_SHARE_FLOOR_PCT = 60.0
RESAMPLES_SHARE_FLOOR_PCT = 15.0


def _rows(name):
    return read_rows(os.path.join(OUTPUTS, name))


class TestItDescribesThePublishedInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_year = lu.components_by_year()

    def test_every_sector_year_closes_to_the_series_before_any_draw(self):
        """The gate that comes first. assert_closure raises, so reaching the count is the
        assertion; the count itself is checked so a silently emptied dict cannot pass."""
        checked = lu.assert_closure(self.by_year)
        self.assertEqual(checked, 90, "the ensemble covers %d sector-years, not the 90 the "
                                      "series publishes (the full rectangle since rc20's "
                                      "FY2015-16 recovery)" % checked)

    def test_no_sector_year_is_silently_missing_its_components(self):
        published = {(r["sector"], int(r["fiscal_end_year"]))
                     for r in lu.ns_rows() if r["co2e_Mt_AR5"] != "absent"}
        built = {(name, fy) for fy, sectors in self.by_year.items() for name in sectors}
        self.assertEqual(built, published)

    def test_the_reference_year_total_is_the_published_national_total(self):
        total = sum(c["co2e_Mt_AR5"]
                    for rows in self.by_year[lu.REFERENCE_YEAR].values() for c in rows)
        # rc39 A1 re-base: the reference herd became the census's exact enumeration, so the pins moved for the first time since rc30 (L 452.14350 -> 452.33432, S 447.01683 -> 447.20153; agriculture +0.184699 and residential +0.006121 through the dung handoff)
        # rc39 A2: FracGASF is one global factor, so re-weighting it onto the fiscal year's own product mix lifts managed soils in EVERY year by ~0.0021-0.0023 Mt
        self.assertAlmostEqual(total, 444.95542, places=4)  # rc67 reference re-base (was 451.85782)


class TestTheStreamKeyContract(unittest.TestCase):
    """The defect that made the parameter graph stop binding."""

    def test_every_key_leads_with_the_engine_category(self):
        from pkinv.core import parameters as param_core
        by_year = lu.components_by_year()
        for scenario in lu.SCENARIOS:
            for component in lu._keyed(by_year[2020]["power"], "power", 2020, scenario):
                self.assertEqual(component["_mc_key"].split("|", 1)[0],
                                 component["category"], scenario)
                self.assertEqual(param_core.original_category(component),
                                 component["category"], scenario)

    def test_the_typed_scenario_keeps_its_key_free_of_the_year_and_the_value(self):
        """`_mc_key` anchors a dependency group's representative member. Writing the value
        into it re-seeds every shared parameter, and the typed scenario silently collapses
        onto full independence - which is exactly what happened before this test existed."""
        by_year = lu.components_by_year()

        def keyed(fy_end):
            return {lu._identity(c): c["_mc_key"]
                    for c in lu._keyed(by_year[fy_end]["power"], "power", fy_end,
                                       "parameter_typed")}

        early, late = keyed(2018), keyed(2022)
        # Intersect deliberately. Power's component LIST differs between years - bagasse
        # co-generation rows exist in FY2021-22 and not FY2017-18 - and that is the inventory
        # changing, not a key defect. What must hold is that a component present in both
        # years carries the same key in both.
        shared = set(early) & set(late)
        self.assertGreater(len(shared), 10)
        for identity in sorted(shared):
            self.assertEqual(early[identity], late[identity],
                             "%s: the typed scenario's stream key differs between years, so "
                             "its shared parameters are not shared" % identity)


class TestTheCorrelationIsRealAndPointsTheRightWay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_year = lu.components_by_year()
        cls.levels, cls.draws = lu.levels(cls.by_year, n_iter=N_ITER)
        cls.trend = lu.differences(cls.by_year, cls.draws, n_iter=N_ITER)

    def _pair(self, scenario, early, late):
        return next(r for r in self.trend if r["scenario"] == scenario
                    and r["from_period"] == early and r["to_period"] == late)

    def test_sharing_draws_across_years_narrows_a_difference(self):
        """The direction that matters. If this ever inverts, the streams are not shared."""
        for early, late in (("FY2020-21", "FY2021-22"), ("FY2021-22", "FY2022-23")):
            correlated = self._pair("time_correlated", early, late)["half_width_Mt"]
            independent = self._pair("time_independent", early, late)["half_width_Mt"]
            self.assertLess(correlated, independent,
                            "%s->%s: correlated %.3f is not narrower than independent %.3f"
                            % (early, late, correlated, independent))

    def test_the_typed_scenario_sits_inside_the_bracket(self):
        for early, late in (("FY2020-21", "FY2021-22"), ("FY2021-22", "FY2022-23")):
            widths = {s: self._pair(s, early, late)["half_width_Mt"]
                      for s in lu.SCENARIOS}
            self.assertLessEqual(widths["time_correlated"], widths["parameter_typed"])
            self.assertLessEqual(widths["parameter_typed"], widths["time_independent"])

    def test_a_level_barely_moves_between_scenarios(self):
        """Time correlation is a statement about how years relate, not about how wide a
        single year is - for the two scenarios that draw the same distribution.

        time_correlated and time_independent re-KEY the shared streams (same sigmas,
        different realizations), so between THEM a level width moves only by sampling
        noise. parameter_typed is not the same distribution: it draws through the parameter
        graph, so a row whose marginal is DERIVED from its parameters (the audited
        stale_row_sigma rows) is wider there than under its declared width in the other
        two. That gap was small enough to hide inside the noise bound until rc40 G3b
        scoped the herd and crop draws to the thirteen manure and soils N2O rows and
        twelve of them derived (101-114 -> 107-124 percent): at 20,000 draws the typed
        level is now 0.67-0.95 points wider than time_correlated in every year, while
        time_correlated and time_independent stay within 0.38 of each other. So this test
        asserts the two things that are true: the same-distribution pair agree to noise,
        and the typed excess is bounded and in the direction the graph implies. The
        noise bound is empirical at N_ITER draws (the rc19 delivered-gas group already
        moved a single year by 1.67 at 20k under the old structure). Distribution
        equality for the same-distribution pair is what the deterministic-invariance test
        below asserts exactly."""
        by_key = {(r["scenario"], r["fiscal_end_year"]): r for r in self.levels}
        for fy_end in sorted(self.by_year):
            corr = by_key[("time_correlated", fy_end)]["rel_up_pct_95"]
            indep = by_key[("time_independent", fy_end)]["rel_up_pct_95"]
            typed = by_key[("parameter_typed", fy_end)]["rel_up_pct_95"]
            self.assertLess(abs(corr - indep), 2.0,
                            "FY ending %d: time_correlated %.3f and time_independent %.3f draw the "
                            "same distribution and differ by more than Monte Carlo noise"
                            % (fy_end, corr, indep))
            self.assertGreater(typed - corr, -1.0,
                               "FY ending %d: the typed level %.3f is NARROWER than time_correlated "
                               "%.3f; the graph-derived rows can only widen it" % (fy_end, typed, corr))
            self.assertLess(typed - corr, 3.0,
                            "FY ending %d: the typed level %.3f exceeds time_correlated %.3f by more "
                            "than the derived rows explain (0.67-0.95 at 20k draws, plus noise)"
                            % (fy_end, typed, corr))

    def test_the_deterministic_total_is_scenario_invariant(self):
        by_year_totals = {}
        for row in self.levels:
            key = row["fiscal_end_year"]
            by_year_totals.setdefault(key, set()).add(row["covered_total_Mt"])
        for fy_end, totals in by_year_totals.items():
            self.assertEqual(len(totals), 1, "FY ending %d" % fy_end)

    def test_significance_is_stated_per_scenario(self):
        for row in self.trend:
            self.assertIn(row["significant_at_95"], ("yes", "no"))
        # The window change is the one every scenario resolves; if it ever stopped being
        # significant under the NARROWEST scenario, the ensemble would be saying that eight
        # years of Pakistani growth are indistinguishable from nothing.
        window = self._pair("time_correlated", "FY2015-16", "FY2023-24")
        self.assertEqual(window["significant_at_95"], "yes")


class TestTheDiagnosticThatExplainsTheAnswer(unittest.TestCase):
    """The trend band is wide because the variance is mostly unexplained, and that is a
    measurement rather than an excuse. These hold it to the honest direction."""

    @classmethod
    def setUpClass(cls):
        by_year = lu.components_by_year()
        comps = []
        for sector, rows in sorted(by_year[lu.REFERENCE_YEAR].items()):
            comps += lu._keyed(rows, sector, lu.REFERENCE_YEAR, "parameter_typed")
        cls.shares = lu.variance_shares([c for c in comps if c["co2e_Mt_AR5"] > 0])

    def test_the_shares_are_a_partition(self):
        self.assertAlmostEqual(sum(self.shares.values()), 100.0, places=6)

    def test_the_unexplained_share_does_not_grow(self):
        self.assertLessEqual(
            self.shares["residual"], RESIDUAL_SHARE_CEILING_PCT,
            "the share of national variance the parameter graph cannot name rose to %.2f%%. "
            "That is the quantity that keeps the trend band wide, and it should fall as "
            "parameters are attributed, never rise." % self.shares["residual"])

    def test_shared_parameters_still_carry_a_measurable_share(self):
        self.assertGreaterEqual(
            self.shares["persists"], PERSISTS_SHARE_FLOOR_PCT,
            "parameters shared across years fell to %.2f%% of variance; below this the typed "
            "scenario is not typing anything and should not be published as a scenario"
            % self.shares["persists"])

    def test_the_resampling_share_counts_its_covariance(self):
        self.assertGreaterEqual(
            self.shares["resamples"], RESAMPLES_SHARE_FLOOR_PCT,
            "the year-resampling share reads %.2f%%; the rc41 arithmetic that dropped every "
            "within-group covariance printed 10.67, and this floor is what it cannot pass"
            % self.shares["resamples"])

    def test_a_groups_members_add_before_they_are_squared(self):
        """Synthetic control for the rc42 arithmetic: two members of one persisting group,
        value 1 and sigma 0.1 each, are ONE factor drawn once - the group's variance term is
        (0.1 + 0.1)^2 = 0.04, not 0.01 + 0.01. Against a residual of 0.04 the persisting
        share is 50 percent covariance-aware and one third under the sum of squares."""
        group = next(g for g, (kind, _reason) in lu.GROUP_TYPE.items() if kind == "persists")
        decomposed = [({"co2e_Mt_AR5": 1.0}, {group: 0.1}, 0.0, None),
                      ({"co2e_Mt_AR5": 1.0}, {group: 0.1}, 0.2, None)]
        shares = lu._variance_shares_from(decomposed)
        self.assertAlmostEqual(shares["persists"], 50.0, places=6)
        self.assertAlmostEqual(shares["residual"], 50.0, places=6)
        self.assertAlmostEqual(shares["resamples"], 0.0, places=6)

    def test_every_dependency_group_is_typed(self):
        """Fail-closed. An untyped group raises inside group_type; this reaches every group
        the decomposition actually resolves so a new one is caught at test time."""
        from pkinv.core import parameters as param_core
        by_year = lu.components_by_year()
        comps = []
        for sector, rows in sorted(by_year[lu.REFERENCE_YEAR].items()):
            comps += lu._keyed(rows, sector, lu.REFERENCE_YEAR, "parameter_typed")
        groups = {g for _c, shared, _r, _o in
                  param_core.decompose([c for c in comps if c["co2e_Mt_AR5"] > 0])
                  for g in shared}
        self.assertGreater(len(groups), 50)
        for group in sorted(groups):
            kind, reason = lu.group_type(group)
            self.assertIn(kind, ("persists", "resamples"), group)
            self.assertGreater(len(reason), 15, "%s is typed without a reason" % group)


class TestTheCoreHookIsNeutralByDefault(unittest.TestCase):
    """`group_qualifier` and `residual_qualifier` were added to core.montecarlo for this
    module. Every existing caller passes neither, and this proves that costs them nothing."""

    def _components(self):
        from pkinv.core import registry
        comps, _cats, _sector_of = registry.build_all()
        return [c for c in comps if c["co2e_Mt_AR5"] > 0]

    def test_a_none_qualifier_is_bit_identical_to_omitting_it(self):
        comps = self._components()
        cats = sorted({c["category"] for c in comps})
        _s1, a, _d1 = mc.run(comps, cats, n_iter=600, stream="parameter",
                             return_samples=True)
        _s2, b, _d2 = mc.run(comps, cats, n_iter=600, stream="parameter",
                             return_samples=True,
                             group_qualifier=None, residual_qualifier=None)
        self.assertEqual(a, b)

    def test_a_qualifier_returning_none_changes_nothing(self):
        """Not the same test: this exercises the branch, and asserts the branch is neutral
        when the callable declines to qualify."""
        comps = self._components()
        cats = sorted({c["category"] for c in comps})
        _s1, a, _d1 = mc.run(comps, cats, n_iter=600, stream="parameter",
                             return_samples=True)
        _s2, b, _d2 = mc.run(comps, cats, n_iter=600, stream="parameter",
                             return_samples=True,
                             group_qualifier=lambda _g: None,
                             residual_qualifier=lambda _c: None)
        self.assertEqual(a, b)

    def test_the_qualifiers_are_refused_on_other_streams(self):
        comps = self._components()
        cats = sorted({c["category"] for c in comps})
        with self.assertRaises(ValueError):
            mc.run(comps, cats, n_iter=100, stream="per_component",
                   group_qualifier=lambda _g: "x")


class TestTheShippedProductsAgreeWithTheModule(unittest.TestCase):
    def test_the_levels_file_carries_every_year_and_scenario(self):
        rows = _rows("pakemis_longitudinal_uncertainty.csv")
        years = {r["fiscal_end_year"] for r in rows}
        scenarios = {r["scenario"] for r in rows}
        self.assertEqual(len(years), 9)
        self.assertEqual(scenarios, set(lu.SCENARIOS))
        self.assertEqual(len(rows), 9 * len(lu.SCENARIOS))

    def test_the_trend_file_carries_both_windows_and_every_step(self):
        rows = _rows("pakemis_trend_uncertainty.csv")
        kinds = {r["pair_kind"] for r in rows}
        # ONE window since rc20: common_start is derived, and with FY2015-16
        # complete it coincides with the panel's first year, so the separate
        # common-scope pair is skipped by the same code that used to add it.
        self.assertEqual(kinds, {"consecutive", "window_full_panel"})
        consecutive = {(r["from_period"], r["to_period"]) for r in rows
                       if r["pair_kind"] == "consecutive"}
        self.assertEqual(len(consecutive), 8)

    def test_every_difference_is_the_sum_over_the_sectors_it_claims(self):
        """THE GUARD THAT WAS MISSING, and its absence cost the headline number.

        The predecessor of this test asserted that `comparable_sectors` READ "8" on the first
        step. It never asked whether the difference beside it had been computed over eight
        sectors, and it had not: the arithmetic subtracted every sector present in each year,
        so the step published 77.92 Mt where the comparable-scope change is 16.83, and the
        nine-year window published 131.27 where it is 80.28 - thirty-nine per cent of the
        headline was transport and industry entering the record.

        A label is not a restriction. This recomputes each published difference from the
        atomic annual table over exactly the sectors the row names, so the column can no
        longer describe something the arithmetic did not do.
        """
        by_period = collections.defaultdict(lambda: collections.defaultdict(float))
        for row in _rows("pakemis_atomic_annual.csv"):
            if row["co2e_Mt_AR5"]:
                by_period[row["period_id"]][row["sector_id"]] += float(row["co2e_Mt_AR5"])
        for row in _rows("pakemis_trend_uncertainty.csv"):
            early, late = by_period[row["from_period"]], by_period[row["to_period"]]
            shared = set(early) & set(late)
            self.assertEqual(len(shared), int(row["comparable_sectors"]),
                             "%s->%s names %s comparable sectors and the products share %d"
                             % (row["from_period"], row["to_period"],
                                row["comparable_sectors"], len(shared)))
            expected = sum(late[s] for s in shared) - sum(early[s] for s in shared)
            self.assertAlmostEqual(
                expected, float(row["difference_Mt"]), places=3,
                msg="%s->%s publishes %s over a claimed %s sectors, but those sectors give "
                    "%.5f" % (row["from_period"], row["to_period"], row["difference_Mt"],
                              row["comparable_sectors"], expected))

    def test_restricting_to_the_same_sectors_changes_nothing(self):
        """WHAT LICENSES THE RESTRICTION, checked rather than assumed.

        Comparable-scope pairs are produced by re-running a year over a subset of its sectors.
        That is only sound if a component's draws depend on its own stream key and not on how
        many components sit beside it - otherwise dropping a sector would silently re-roll the
        ones that remain, and every restricted pair would be comparing two different random
        worlds while looking perfectly well behaved.

        So: restricting to the FULL set must be bit-identical, and dropping a sector must move
        the total by that sector alone.
        """
        from pkinv.report import longitudinal_uncertainty as lu
        by_year = lu.components_by_year()
        year = max(y for y in by_year if len(by_year[y]) == 10)
        full = lu._run_year(by_year, year, "parameter_typed", 2000, lu.SEED)
        same = lu._run_year({year: dict(by_year[year])}, year, "parameter_typed", 2000,
                            lu.SEED)
        self.assertEqual(full, same,
                         "re-running a year over its own full sector set changed the draws, "
                         "so the draws depend on the component LIST and every restricted "
                         "pair is comparing two different random worlds")
        dropped = "aviation"
        without = lu._run_year(
            {year: {s: r for s, r in by_year[year].items() if s != dropped}},
            year, "parameter_typed", 2000, lu.SEED)
        moved = sum(full) / len(full) - sum(without) / len(without)
        mass = sum(c["co2e_Mt_AR5"] for c in by_year[year][dropped])
        self.assertAlmostEqual(mass, moved, places=1,
                               msg="dropping %s moved the total by %.3f Mt against its own "
                                   "%.3f Mt" % (dropped, moved, mass))

    def test_the_dropped_sectors_are_named_not_just_counted(self):
        for row in _rows("pakemis_trend_uncertainty.csv"):
            if row["scope_note"].startswith("restricted"):
                self.assertNotEqual("none", row["sectors_dropped"])
            else:
                self.assertEqual("none", row["sectors_dropped"])

    def test_the_published_intervals_bracket_their_own_point_estimate(self):
        for row in _rows("pakemis_longitudinal_uncertainty.csv"):
            self.assertLess(float(row["P2.5_Mt"]), float(row["P50_Mt"]))
            self.assertLess(float(row["P50_Mt"]), float(row["P97.5_Mt"]))


if __name__ == "__main__":
    unittest.main()


class TestTheStreamKeysCarryNoFloat(unittest.TestCase):
    """rc41, the nineteenth review's T-2. Every seed input the ensemble derives from a
    component - the time_independent `_mc_key`, the resampling groups' fingerprints, the
    residual qualifier - used to write `repr(co2e)` into the key. A float's repr is the same
    on every platform, but the VALUE it prints is computed in-process, and a libm-sensitive
    path landing one ulp apart re-seeded the stream. The keys now carry the component's
    identity and its PIN YEAR (the first year holding its exact value) and no float."""

    FLOAT = re.compile(r"\d+\.\d+")

    @classmethod
    def setUpClass(cls):
        cls.by_year = lu.components_by_year()
        cls.pins = lu.pin_years(cls.by_year)

    def test_no_key_contains_a_decimal_number(self):
        for scenario in lu.SCENARIOS:
            for fy_end, sectors in self.by_year.items():
                for sector, comps in sectors.items():
                    for c in lu._keyed(comps, sector, fy_end, scenario, self.pins):
                        self.assertIsNone(self.FLOAT.search(c["_mc_key"]),
                                          (scenario, fy_end, c["_mc_key"]))

    def test_a_held_component_shares_its_pin_year_and_a_moved_one_does_not(self):
        """The semantics the value string expressed, kept: two years holding a component at
        one number share a key; a year whose value moved gets its own."""
        held = moved = 0
        for (sector, identity, value), first in self.pins.items():
            years = [fy for fy in self.by_year
                     if any(lu._identity(c) == identity and c["co2e_Mt_AR5"] == value
                            for c in self.by_year[fy].get(sector, []))]
            self.assertEqual(min(years), first)
            if len(years) > 1:
                held += 1
            else:
                moved += 1
        self.assertGreater(held, 0, "no component is held across years - pinned_share "
                                    "says otherwise")
        self.assertGreater(moved, held, "more components held than moved; the panel is "
                                        "not the one the series describes")
        fy = max(self.by_year)
        for sector, comps in self.by_year[fy].items():
            for c in lu._keyed(comps, sector, fy, "time_independent", self.pins):
                pin = self.pins[(sector, lu._identity(c), c["co2e_Mt_AR5"])]
                self.assertTrue(c["_mc_key"].endswith("|pin|%d" % pin), c["_mc_key"])

    def test_the_fingerprint_moves_only_when_a_member_value_moves(self):
        early, late = sorted(self.by_year)[-2:]
        def prints(fy):
            comps = []
            for sector, rows in sorted(self.by_year[fy].items()):
                comps += lu._keyed(rows, sector, fy, "parameter_typed", self.pins)
            return lu._group_fingerprints([c for c in comps if c["co2e_Mt_AR5"] > 0])
        a, b = prints(early), prints(late)
        shared = set(a) & set(b)
        self.assertGreater(len(shared), 20)
        same = [g for g in shared if a[g] == b[g]]
        # persists-typed groups' fingerprints are never consulted; among resampling groups
        # some are held (waste's partition, the factor tables) and most move with the year
        self.assertGreater(len(same), 0)
        self.assertGreater(len(shared) - len(same), 0)


class TestTheShippedPrefixIsReproducible(unittest.TestCase):
    """draw d is draw d, and the shipped prefix is what a rerun produces (rc41, T-2)."""

    PREFIX = os.path.join(OUTPUTS, "pakemis_longitudinal_prefix.csv")

    @classmethod
    def setUpClass(cls):
        cls.by_year = lu.components_by_year()
        cls.pins = lu.pin_years(cls.by_year)
        cls.shipped = {}
        for r in read_rows(cls.PREFIX):
            cls.shipped.setdefault((r["scenario"], int(r["fiscal_end_year"])), []).append(
                float(r["covered_total_Mt"]))

    def test_the_file_carries_every_stream_at_the_declared_length(self):
        keys = {(s, fy) for s in lu.SCENARIOS for fy in self.by_year}
        self.assertEqual(set(self.shipped), keys)
        for key, values in self.shipped.items():
            self.assertEqual(len(values), lu.PREFIX_N_ITER, key)

    def test_a_short_run_is_a_prefix_of_a_longer_one(self):
        fy = max(self.by_year)
        for scenario in lu.SCENARIOS:
            short = lu._run_year(self.by_year, fy, scenario, lu.PREFIX_N_ITER, lu.SEED,
                                 self.pins)
            longer = lu._run_year(self.by_year, fy, scenario, 5 * lu.PREFIX_N_ITER, lu.SEED,
                                  self.pins)
            self.assertEqual(short, longer[:lu.PREFIX_N_ITER], scenario)

    def test_a_rerun_reproduces_the_shipped_prefix(self):
        """Bit-identical on the platform that produced the shipped file; to 1e-12 relative
        elsewhere (summation order and libm), which no re-seeding could pass. The
        validation package's container run exercises the second branch."""
        exact = True
        for (scenario, fy), shipped in sorted(self.shipped.items()):
            rerun = lu._run_year(self.by_year, fy, scenario, lu.PREFIX_N_ITER, lu.SEED,
                                 self.pins)
            if rerun == shipped:
                continue
            exact = False
            worst = max(abs(a - b) / max(abs(a), 1e-12) for a, b in zip(shipped, rerun))
            self.assertLess(worst, 1e-12, "%s FY%d: the rerun differs from the shipped "
                            "prefix by %.3e relative - the draws are not the same draws"
                            % (scenario, fy, worst))
        if not exact:
            print("  longitudinal prefix identical to 1e-12 relative, not bit for bit: a "
                  "cross-platform rerun")

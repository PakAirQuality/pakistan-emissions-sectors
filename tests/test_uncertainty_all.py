"""Cross-sector Monte-Carlo uncertainty (IPCC Approach 2).

The invariant that matters most here is negative: adding a national Monte Carlo must not
disturb agriculture's own run, whose RNG stream core/montecarlo.py documents as fragile.

Run:  python3 -m unittest discover tests -p "test_uncertainty_all.py"
"""
import math
import unittest

from pkinv.core import montecarlo as mc_core
from pkinv.core import registry
from pkinv.report import uncertainty_all

# Building all seven sectors costs about ten seconds, so build once and share. The
# iteration count is low deliberately: none of these assertions needs published precision,
# and 10,000 iterations x two scenarios x two labellings x several tests does not pay for
# itself in a suite that runs on every commit.
N = 400
_POOLED = {}


def setUpModule():
    _POOLED[False] = uncertainty_all.pooled(correlate_fossil=False)
    _POOLED[True] = uncertainty_all.pooled(correlate_fossil=True)


class TestPooling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.components, cls.categories, cls.sector_of = _POOLED[False]

    def test_every_sector_contributes_components(self):
        sectors = {c["_sector"] for c in self.components}
        self.assertEqual(sectors, {s.NAME for s in registry.all_sectors()})

    def test_every_declared_category_is_present(self):
        self.assertEqual(set(self.categories),
                         {cat for s in registry.all_sectors() for cat in s.CATEGORIES})

    def test_categories_are_unique_across_sectors(self):
        """The registry contract guarantees this; the pooled run depends on it, because
        two sectors sharing a category name would silently merge in the output."""
        self.assertEqual(len(self.categories), len(set(self.categories)))

    def test_pooling_does_not_mutate_a_sector(self):
        """pooled() copies each row before adding _sector or a correlation group."""
        sector = registry.get("transport")
        original = sector.build_components(sector.load_data())
        self.assertFalse(any("_sector" in c for c in original))
        uncertainty_all.pooled(correlate_fossil=True)
        again = sector.build_components(sector.load_data())
        self.assertFalse(any("_sector" in c for c in again))
        self.assertEqual([c.get("corr_group") for c in original],
                         [c.get("corr_group") for c in again])


class TestTheRunLeaksNoState(unittest.TestCase):
    """core/montecarlo.py warns that the count and order of gauss() calls determine every
    draw, so anything that shares generator state across invocations changes results
    invisibly. This used to be checked by running AGRICULTURE's own Monte Carlo either side
    of the national one; that module now lives in the companion repository, so the property
    is asserted directly instead - and more strongly, because it pins the national run
    itself rather than a neighbour of it.

    Two identical invocations must agree exactly, and an intervening run at a different seed
    must not disturb them."""

    def test_the_same_seed_twice_gives_the_same_answer(self):
        first = uncertainty_all.run(n_iter=N, seed=7, prebuilt=_POOLED[False])[0]["TOTAL"]
        uncertainty_all.run(n_iter=N, seed=99, prebuilt=_POOLED[False])
        again = uncertainty_all.run(n_iter=N, seed=7, prebuilt=_POOLED[False])[0]["TOTAL"]
        self.assertEqual(first, again)


class TestScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ind_cat, cls.ind_sec, _ = uncertainty_all.run(n_iter=N, prebuilt=_POOLED[False])
        cls.cor_cat, cls.cor_sec, _ = uncertainty_all.run(n_iter=N, prebuilt=_POOLED[True])

    def test_the_two_labellings_agree_on_the_total(self):
        """By-category and by-sector are two passes over the same components drawing the
        same stream - the same realisation viewed two ways. That used to hold because the
        two passes visited the list in the same order; it now holds because each component
        carries an _mc_key pinning its stream, which survives the second pass relabelling
        the category column. Not bit-equal: the passes accumulate into 12 buckets and 7
        respectively, and
        floating-point addition is not associative. Twelve significant figures is the
        honest form of the claim, and is still far tighter than any sampling difference."""
        for key in ("mean", "p025", "p50", "p975", "rel_pct"):
            a, b = self.ind_cat["TOTAL"][key], self.ind_sec["TOTAL"][key]
            self.assertAlmostEqual(a, b, delta=abs(a) * 1e-12, msg=key)

    def test_correlating_shared_factors_widens_the_sector_that_shares_them(self):
        """Asserted where the shared factor actually dominates, not nationally.

        Under the superseded single-group scheme every fuel-burning CO2 row drew together, so
        correlation widened the NATIONAL band by about a fifth. Grouped per physical factor -
        which is the defensible treatment - the eight factor groups are independent of one
        another and their variances add in quadrature, so the national effect is close to
        nil while the effect inside a single-fuel-dominated sector stays large. Transport is
        that sector: its petrol classes share one carbon content and its diesel classes
        another."""
        self.assertGreater(self.cor_sec["transport"]["rel_pct"],
                           self.ind_sec["transport"]["rel_pct"] * 1.2)

    def test_correlation_does_not_move_the_central_estimate(self):
        """Correlation changes the spread, not the mean. A shifted mean would mean the
        draws stopped being mean-preserving."""
        self.assertAlmostEqual(self.cor_cat["TOTAL"]["mean"], self.ind_cat["TOTAL"]["mean"],
                               delta=0.03 * self.ind_cat["TOTAL"]["mean"])

    def test_the_mean_estimates_the_deterministic_total(self):
        deterministic = sum(c["co2e_Mt_AR5"] for c in _POOLED[False][0])
        self.assertAlmostEqual(self.ind_cat["TOTAL"]["mean"], deterministic,
                               delta=0.05 * deterministic)

    def test_approach_2_is_close_to_approach_1(self):
        """Two independent routes to the same band. A large divergence means one of them
        is mishandling the correlation groups."""
        t = self.ind_cat["TOTAL"]
        self.assertAlmostEqual(t["rel_pct"], t["approach1_pct"], delta=4.0)

    def test_the_national_band_is_narrower_than_its_widest_sector(self):
        """Aggregation reduces relative uncertainty when errors are independent. If the
        national band exceeded every sector's, the pooling would be wrong."""
        widest = max(self.ind_sec[s.NAME]["rel_pct"] for s in registry.all_sectors())
        self.assertLess(self.ind_cat["TOTAL"]["rel_pct"], widest)

    def test_a_sector_band_is_reported_for_every_sector(self):
        for s in registry.all_sectors():
            self.assertGreater(self.ind_sec[s.NAME]["rel_pct"], 0.0, msg=s.NAME)


class TestFuelSectors(unittest.TestCase):
    def test_the_correlated_group_covers_only_fuel_combustion_co2(self):
        components, _c, _s = _POOLED[True]
        grouped = [c for c in components
                   if (c.get("corr_group") or "").startswith(
                       uncertainty_all.SHARED_FOSSIL_GROUP)]
        self.assertTrue(grouped)
        for c in grouped:
            self.assertEqual(c["gas"], "CO2")
            self.assertIn(c["_sector"], uncertainty_all.FUEL_SECTORS)

    def test_the_declared_membership_equals_the_derived_membership(self):
        """The test that would have caught industry.

        FUEL_SECTORS was a hand-written literal, and when industrial fuel combustion landed
        nothing compared it against the inventory - so a whole fossil-burning module sat
        outside the correlation group through a release, and the paper's headline
        correlation finding understated the band. The membership is now derived from the
        components' IPCC codes and the declaration has to match.
        """
        self.assertEqual(set(uncertainty_all.FUEL_SECTORS),
                         uncertainty_all.fuel_combustion_sectors(_POOLED[False][0]))

    def test_the_derivation_is_not_trivially_everything(self):
        """A derivation that returned every sector would pass the test above while making
        the correlation meaningless."""
        derived = uncertainty_all.fuel_combustion_sectors(_POOLED[False][0])
        for outside in ("agriculture", "waste", "ippu", "fugitives"):
            self.assertNotIn(outside, derived)

    def test_every_fuel_sector_actually_contributes_a_grouped_component(self):
        """The group name is now a PREFIX plus the physical factor, not one literal - see
        core.factors for why a single group spanning diesel, gas and coal was not a defensible
        claim."""
        components, _c, _s = _POOLED[True]
        grouped = {c["_sector"] for c in components
                   if (c.get("corr_group") or "").startswith(
                       uncertainty_all.SHARED_FOSSIL_GROUP)}
        self.assertEqual(grouped, set(uncertainty_all.FUEL_SECTORS))

    def test_each_correlation_group_is_one_physical_factor(self):
        """The property the regrouping exists for: a group may span sectors and categories -
        road, rail, off-road and industrial diesel are one carbon content - but it may never
        span two fuels."""
        from pkinv.core import factors
        components, _c, _s = _POOLED[True]
        by_group = {}
        for c in components:
            g = c.get("corr_group") or ""
            if g.startswith(uncertainty_all.SHARED_FOSSIL_GROUP):
                by_group.setdefault(g, set()).add(factors.factor_id(c))
        self.assertTrue(by_group)
        for g, fuels in by_group.items():
            self.assertEqual(len(fuels), 1, "%s mixes %s" % (g, fuels))

    def test_the_factor_table_covers_every_fossil_co2_row(self):
        """No fossil-fuel CO2 row without a declared factor identity. A sector that gains a
        fuel fails here rather than silently dropping out of the correlated scenario."""
        from pkinv.core import factors
        components, _c, _s = _POOLED[False]
        uncovered = [(c["_sector"], c["subitem"]) for c in components
                     if c["gas"] == "CO2" and c["_sector"] in uncertainty_all.FUEL_SECTORS
                     and factors.factor_id(c) is None]
        self.assertFalse(uncovered, "fossil CO2 rows with no factor identity: %s" % uncovered)

    def test_agriculture_co2_is_not_in_the_group(self):
        """Agriculture's CO2 is urea and liming, from a different IPCC chapter and a
        different argument, so it does not share the fuel-carbon factors."""
        self.assertNotIn("agriculture", uncertainty_all.FUEL_SECTORS)
        components, _c, _s = _POOLED[True]
        for c in components:
            if c["_sector"] == "agriculture":
                self.assertNotEqual(c.get("corr_group"), uncertainty_all.SHARED_FOSSIL_GROUP)


class TestDeterminism(unittest.TestCase):
    def test_the_same_seed_gives_the_same_answer(self):
        a, _s, _t = uncertainty_all.run(n_iter=N, seed=11, prebuilt=_POOLED[False])
        b, _s2, _t2 = uncertainty_all.run(n_iter=N, seed=11, prebuilt=_POOLED[False])
        self.assertEqual(a["TOTAL"], b["TOTAL"])

    def test_a_different_seed_gives_a_different_answer(self):
        a, _s, _t = uncertainty_all.run(n_iter=N, seed=11, prebuilt=_POOLED[False])
        b, _s2, _t2 = uncertainty_all.run(n_iter=N, seed=12, prebuilt=_POOLED[False])
        self.assertNotEqual(a["TOTAL"]["p50"], b["TOTAL"]["p50"])

    def test_sigma_log_is_the_shared_core_implementation(self):
        self.assertIs(uncertainty_all.mc_core.sigma_log, mc_core.sigma_log)


class TestTheSimulationReproducesTheDeterministicTotal(unittest.TestCase):
    """The draws are mean-preserving, so the simulated mean must estimate the deterministic
    total. If a pooled path ever ran on a stale component list, this is where it would show.

    The tolerance is DERIVED, not chosen: five standard errors of the simulated mean, where
    the standard error is the sample standard deviation over the square root of the iteration
    count. A fixed percentage would either be loose enough to hide a missing sector or tight
    enough to fail on sampling noise, and it would not scale with n_iter.
    """

    def _check(self, correlate):
        components, categories, sector_of = _POOLED[correlate]
        by_category, _by_sector, samples = uncertainty_all.run(
            n_iter=N, prebuilt=(components, categories, sector_of))
        deterministic = sum(c["co2e_Mt_AR5"] for c in components)
        mean = by_category["TOTAL"]["mean"]
        var = sum((x - mean) ** 2 for x in samples) / (len(samples) - 1)
        stderr = math.sqrt(var / len(samples))
        self.assertLess(
            abs(mean - deterministic), 5 * stderr,
            "simulated mean %.3f is %.3f Mt from the deterministic %.3f, which is more than "
            "five standard errors (%.3f) - a component set is out of date somewhere"
            % (mean, abs(mean - deterministic), deterministic, stderr))

    def test_the_independent_scenario_reproduces_the_total(self):
        self._check(False)

    def test_the_correlated_scenario_reproduces_the_total(self):
        """Correlation changes the spread, not the mean, so this must hold under both."""
        self._check(True)


class TestOneSectorDoesNotMoveAnother(unittest.TestCase):
    """The reason the national run uses per-component RNG streams.

    Under the shared sequential stream this file used to run, adding eighteen
    industrial-fuel components moved the WASTE sector's published disposal median from
    8.26 to 8.31 Mt - and waste had not changed. Every downstream draw shifts when the
    count or order of gauss() calls changes, so a released band was only stable for as
    long as no sector grew. This inventory intends to gain components every release.
    """

    @classmethod
    def setUpClass(cls):
        components, categories, sector_of = _POOLED[False]
        cls.full = uncertainty_all.run(
            n_iter=N, prebuilt=(components, categories, sector_of))[1]
        kept = [c for c in components if c["_sector"] != "industry"]
        cls.without = uncertainty_all.run(
            n_iter=N, prebuilt=(kept, sorted({c["category"] for c in kept}), sector_of))[1]

    def test_removing_a_whole_sector_leaves_the_others_bit_identical(self):
        for name in ("agriculture", "waste", "power", "transport", "residential",
                     "fugitives", "ippu", "railways", "aviation"):
            self.assertEqual(self.full[name], self.without[name], name)

    def test_the_removed_sector_is_gone_rather_than_merely_unchanged(self):
        """Guards the trivial way to pass the test above."""
        self.assertEqual(self.without["industry"]["p50"], 0.0)
        self.assertGreater(self.full["industry"]["p50"], 0.0)

    def test_a_components_stream_follows_its_identity_not_its_position(self):
        components, categories, sector_of = _POOLED[False]
        shuffled = list(reversed(components))
        a = uncertainty_all.run(n_iter=N, prebuilt=(components, categories, sector_of))[0]
        b = uncertainty_all.run(n_iter=N, prebuilt=(shuffled, categories, sector_of))[0]
        self.assertAlmostEqual(a["TOTAL"]["p50"], b["TOTAL"]["p50"], places=9)

    def test_the_seed_derivation_does_not_depend_on_pythons_salted_hash(self):
        """hash() on a str is salted per process, so a stream built on it would differ
        between runs and every percentile would be irreproducible across machines."""
        self.assertEqual(mc_core.stream_seed(42, "a|b|CO2"),
                         mc_core.stream_seed(42, "a|b|CO2"))
        self.assertNotEqual(mc_core.stream_seed(42, "a|b|CO2"),
                            mc_core.stream_seed(43, "a|b|CO2"))
        self.assertEqual(mc_core.stream_seed(42, "a|b|CO2"), 10486715988415057114)


class TestSectorRunsKeepTheOriginalStream(unittest.TestCase):
    def test_sequential_is_still_the_default(self):
        """Sector-scoped runs must not move: their percentiles are published and pinned.
        Only the national run opts into per-component streams."""
        import inspect
        self.assertEqual(
            inspect.signature(mc_core.run).parameters["stream"].default, "sequential")

    def test_an_unknown_discipline_raises(self):
        components, categories, _s = _POOLED[False]
        with self.assertRaises(ValueError):
            mc_core.run(components, categories, n_iter=10, stream="whatever")


class TestCorrelationNeverNarrowsABand(unittest.TestCase):
    """Adding positive correlation to a sum of positive terms cannot shrink its spread.

    This is the invariant that caught a real defect twice over. pooled() used to assign the
    fossil-carbon group UNCONDITIONALLY, which silently overwrote correlation the sector had
    already declared - power groups its four grid CO2 rows under one TOE-to-terajoule
    conversion - and the correlated scenario came out NARROWER than the independent baseline,
    9.94 against 7.87 percent. A scenario that reduces uncertainty by adding a shared error is
    not a scenario, it is a bug, and nothing in the suite was asking.

    A small negative tolerance is allowed and is not slack: a grouped component that is not
    its group's representative necessarily draws a different stream than it does in the
    independent run, so its realisation moves. That residual is bounded here; the defect it
    is distinguished from was an order of magnitude larger.

    THE BOUND IS NOW MEASURED RATHER THAN CHOSEN. It used to be a hand-set floor - half a
    point, or five percent of the band, whichever was larger - and a reviewer reasonably asked
    how anyone knew the residual movements were noise. They were asserted to be. The published
    run reports a batch-means standard error for every half-width, so the admissible residual
    is three standard errors of the statistic itself, and the paper's claim is checkable
    instead of stated. At the published 100,000 draws only two rows still move down at all,
    both inside that bound; the power defect was 2.07 points on a 9.94 band, roughly forty
    standard errors, and no bound of this shape admits it.

    The invariant itself is also restated. "Correlation cannot reduce the spread of a sum" is
    too absolute - negative dependence reduces it routinely. The claim here is narrower and
    true: POSITIVE shared-factor dependence should not reduce the variance of the affected
    non-negative sum relative to otherwise identical independent draws.
    """

    SE_MULTIPLE = 3.0
    # A floor for rows too small for a stable batch-means estimate.
    MIN_FLOOR_REL = 0.02

    def _floor(self, stats):
        se = stats.get("rel_se_pp")
        by_se = self.SE_MULTIPLE * se if se else 0.0
        return max(by_se, self.MIN_FLOOR_REL * stats["rel_pct"])

    # THE SHIPPED PAIR, NOT THE SUPERSEDED ONE. The rc2 version of this class ran the
    # retired correlate_fossil pooling under the per_component default, so the invariant
    # guarded a scenario pair the paper no longer publishes while the published
    # within_sector/cross_sector parameter pair ran unguarded -- a check reporting passing
    # while testing the wrong thing. The stream and the scenario axis are read from
    # uncertainty_all's own constants so this cannot silently diverge from what ships.
    @classmethod
    def setUpClass(cls):
        cls.ind_cat, cls.ind_sec, _ = uncertainty_all.run(
            n_iter=4000, prebuilt=_POOLED[False],
            stream=uncertainty_all.NATIONAL_STREAM, cross_sector=False)
        cls.cor_cat, cls.cor_sec, _ = uncertainty_all.run(
            n_iter=4000, prebuilt=_POOLED[False],
            stream=uncertainty_all.NATIONAL_STREAM, cross_sector=True)

    def test_no_sector_band_narrows_materially(self):
        narrowed = []
        for name in (s.NAME for s in registry.all_sectors()):
            delta = self.cor_sec[name]["rel_pct"] - self.ind_sec[name]["rel_pct"]
            floor = self._floor(self.ind_sec[name])
            if delta < -floor:
                narrowed.append("%s %.2f -> %.2f (%.3f, floor %.3f)"
                                % (name, self.ind_sec[name]["rel_pct"],
                                   self.cor_sec[name]["rel_pct"], delta, floor))
        self.assertFalse(narrowed, "correlation narrowed a band:\n  " + "\n  ".join(narrowed))

    def test_the_national_band_does_not_narrow(self):
        base = self.ind_cat["TOTAL"]["rel_pct"]
        self.assertGreater(self.cor_cat["TOTAL"]["rel_pct"],
                           base - self._floor(self.ind_cat["TOTAL"]))

    def test_a_sector_declared_group_survives_the_scenario(self):
        """The specific overwrite. Power's grid rows must still carry their own group in the
        correlated pooling, and must therefore be reported as outside the fuel scenario."""
        components, _c, _s = _POOLED[True]
        power_grid = [c for c in components
                      if c["_sector"] == "power" and c["subitem"].endswith("CO2")
                      and c.get("corr_group") == "1a1a_toe_activity"]
        # Coal now uses physical station mass and rank NCVs, while gas/oil/
        # diesel retain their shared published energy conversion group.
        self.assertEqual(len(power_grid), 3)
        self.assertFalse(any(c["subitem"].startswith("Coal") for c in power_grid))
        excluded = {(s, sub) for s, sub, _g in
                    uncertainty_all.excluded_from_fossil_scenario(components)}
        for c in power_grid:
            self.assertIn((c["_sector"], c["subitem"]), excluded)

    def test_the_exclusion_is_reported_rather_than_silent(self):
        """A scenario that omits four of the power sector's five CO2 rows must say so."""
        self.assertTrue(uncertainty_all.excluded_from_fossil_scenario())


if __name__ == "__main__":
    unittest.main()


class TestTheReportedNoiseFloor(unittest.TestCase):
    """The published run must report the Monte Carlo error of what it publishes.

    Six bands came out slightly narrower under correlation than under independence, and the
    paper said correlation cannot narrow a sum. Both statements cannot be right, and the
    resolution - that the residual is a re-drawn realisation rather than a variance reduction -
    was asserted rather than demonstrated. A standard error makes it demonstrable.
    """

    def test_every_published_row_carries_a_standard_error(self):
        import csv as _csv
        import os as _os
        from pkinv.paths import OUTPUTS
        path = _os.path.join(OUTPUTS, "national_uncertainty_montecarlo.csv")
        with open(path, newline="", encoding="utf-8") as handle:
            rows = list(_csv.DictReader(handle))
        self.assertGreater(len(rows), 20)
        for r in rows:
            self.assertTrue((r.get("rel_uncert_se_pp") or "").strip(),
                            "%s/%s publishes a half-width with no standard error"
                            % (r["scenario"], r["name"]))
            self.assertEqual(int(r["n_iter"]), uncertainty_all.NATIONAL_N_ITER)

    def test_the_standard_error_is_small_against_what_it_qualifies(self):
        """A standard error the size of the number is a warning, not a footnote."""
        import csv as _csv
        import os as _os
        from pkinv.paths import OUTPUTS
        with open(_os.path.join(OUTPUTS, "national_uncertainty_montecarlo.csv"),
                  newline="", encoding="utf-8") as handle:
            for r in _csv.DictReader(handle):
                band, se = float(r["rel_uncert_pct_MC_95"]), float(r["rel_uncert_se_pp"])
                self.assertLess(se, 0.05 * band,
                                "%s/%s: SE %.3f on a band of %.2f - the published figure is "
                                "not stable at this iteration count"
                                % (r["scenario"], r["name"], se, band))

    def test_batch_means_falls_with_more_draws(self):
        """The estimator must behave like a standard error: roughly 1/sqrt(n)."""
        from pkinv.core import montecarlo as mc
        import random as _random
        rng = _random.Random(4)
        draws = [rng.lognormvariate(0.0, 0.3) for _ in range(40000)]
        coarse = mc.batch_standard_error(draws[:10000])
        fine = mc.batch_standard_error(draws)
        self.assertIsNotNone(coarse)
        self.assertLess(fine, coarse)

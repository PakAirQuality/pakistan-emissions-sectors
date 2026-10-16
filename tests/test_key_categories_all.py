"""National Key Category Analysis (IPCC Vol 1 Ch 4, Approach 1) across all sectors.

Run:  python3 -m unittest discover tests -p "test_key_categories_all.py"
"""

from pkinv.assets import asset_path
import unittest

from pkinv.core import registry
from pkinv.report import key_categories_all as kca

_PREBUILT = []


def setUpModule():
    _PREBUILT.append(registry.build_all())


class TestApproach1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level, cls.variance, cls.by_category = kca.compute(prebuilt=_PREBUILT[0])

    def test_level_shares_sum_to_one(self):
        self.assertAlmostEqual(sum(s for _n, s, _c, _k in self.level), 1.0, places=9)

    def test_variance_shares_sum_to_one(self):
        self.assertAlmostEqual(sum(s for _n, s, _c, _k in self.variance), 1.0, places=9)

    def test_rows_are_sorted_descending(self):
        shares = [s for _n, s, _c, _k in self.level]
        self.assertEqual(shares, sorted(shares, reverse=True))

    def test_cumulative_is_monotone_and_reaches_one(self):
        cums = [c for _n, _s, c, _k in self.level]
        self.assertEqual(cums, sorted(cums))
        self.assertAlmostEqual(cums[-1], 1.0, places=9)

    def test_the_crossing_row_is_key_and_later_rows_are_not(self):
        """IPCC's convention: the category that takes the cumulative sum past 95% is itself
        key. Getting this off by one drops or adds a category at the boundary."""
        keys = [k for _n, _s, _c, k in self.level]
        first_false = keys.index(False)
        self.assertTrue(all(keys[:first_false]))
        self.assertFalse(any(keys[first_false:]))
        crossing = self.level[first_false - 1]
        self.assertGreaterEqual(crossing[2], kca.THRESHOLD)
        self.assertLess(self.level[first_false - 2][2], kca.THRESHOLD)

    def test_every_registered_category_is_screened(self):
        """The screen ranks IPCC CATEGORIES now, not the engine's own, so the identity is
        "every engine category appears as a source stream beneath exactly one screened code",
        not "the two name sets are equal". The old equality is what let the screen report 19
        rows while the category table reported 18."""
        declared = {cat for s in registry.all_sectors() for cat in s.CATEGORIES}
        streamed = {}
        for label, row in self.by_category.items():
            for entry in row["source_streams"].split("; "):
                streamed.setdefault(entry.rsplit(" ", 1)[0], []).append(label)
        self.assertEqual(set(streamed), declared,
                         "an engine category is screened under no IPCC code, or vice versa")
        # AN ENGINE CATEGORY MAY NOW SPAN TWO IPCC CATEGORIES, and two do. Under IPCC 2006
        # manure management's indirect N2O is 3.C.6 while its CH4 and direct N2O are 3.A.2,
        # and managed soils divides into 3.C.4 and 3.C.5, so "appears beneath exactly one
        # screened code" stopped being the invariant on 2026-10-06. What still must not happen
        # is a category spanning codes it is not DECLARED to span - that would be double
        # counting rather than disaggregation - so the split pairs are named and anything else
        # appearing twice is still a defect.
        split = {"Manure management", "Managed soils"}
        doubled = {k: v for k, v in streamed.items() if len(v) > 1 and k not in split}
        self.assertFalse(doubled, "a category is screened twice: %s" % doubled)
        for category in split:
            self.assertEqual(
                len(streamed.get(category, [])), 2,
                "%s is a declared split and must be screened under exactly its two IPCC "
                "categories, not %s" % (category, streamed.get(category)))


class TestTheFinding(unittest.TestCase):
    """The reason this module exists: against the national total rather than the
    agriculture total, two energy categories are key and had never been screened."""

    @classmethod
    def setUpClass(cls):
        cls.level, cls.variance, cls.by_category = kca.compute(prebuilt=_PREBUILT[0])
        cls.keys = {n for n, _s, _c, k in cls.level if k}

    def test_road_transport_and_power_are_key(self):
        self.assertIn("Road transportation", self.keys)
        self.assertIn("Public electricity and heat production", self.keys)

    def test_they_outrank_every_agriculture_category_but_enteric(self):
        order = [n for n, _s, _c, _k in self.level]
        self.assertEqual(order[0], "Enteric fermentation")
        self.assertIn(order[1], ("Road transportation",
                         "Public electricity and heat production"))
        self.assertIn(order[2], ("Road transportation",
                         "Public electricity and heat production"))

    def test_the_denominator_is_national_not_agricultural(self):
        """If this ever screened against the agriculture total, the energy sectors would
        take shares above 100% and the whole analysis would be nonsense."""
        total = sum(v["level_Mt"] for v in self.by_category.values())
        agriculture = sum(v["level_Mt"] for v in self.by_category.values()
                          if v["sector"] == "agriculture")
        self.assertGreater(total, agriculture * 1.5)

    def test_some_categories_are_not_key(self):
        """A screen that flags everything has no discriminating power."""
        self.assertLess(len(self.keys), len(self.level))
        self.assertGreater(len(self.keys), 2)


class TestVarianceRanking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level, cls.variance, cls.by_category = kca.compute(prebuilt=_PREBUILT[0])

    def test_variance_ranking_differs_from_level_ranking(self):
        """The point of reporting both. If they were the same ordering, the variance
        column would be decoration - size would already tell you where to spend effort."""
        self.assertNotEqual([n for n, _s, _c, _k in self.level],
                            [n for n, _s, _c, _k in self.variance])

    def test_a_large_category_can_be_a_small_share_of_variance(self):
        """Road transport is a top-three category by size and a minor one by variance,
        because its fuel control total is well measured. That contrast is the finding."""
        level = dict((n, s) for n, s, _c, _k in self.level)
        var = dict((n, s) for n, s, _c, _k in self.variance)
        self.assertLess(var["Road transportation"], level["Road transportation"])

    def test_variance_matches_the_approach_1_quadrature(self):
        """Same arithmetic as core.uncertainty.combine_sum, so the variance shares and the
        published national band cannot disagree about which category dominates."""
        from pkinv.core.uncertainty import combine_sum
        from pkinv.report import category_ledger
        components, _categories, _s = _PREBUILT[0]
        codes = category_ledger.category_codes()
        by_code = {}
        for c in components:
            by_code.setdefault(
                category_ledger.component_code(c["category"], c.get("subitem"), c["gas"]),
                []).append(c)
        for code, rows in by_code.items():
            category = category_ledger.IPCC_CATEGORY_NAMES[code]
            members = [(c["co2e_Mt_AR5"], c["uncert_pct"], c.get("corr_group"))
                       for c in rows]
            value, pct = combine_sum(members)
            expected_abs = abs(value) * pct / 100.0
            raw = dict((n, s) for n, s, _c, _k in self.variance)
            total_var = sum(
                (abs(sum(c["co2e_Mt_AR5"] for c in other))
                 * combine_sum([(c["co2e_Mt_AR5"], c["uncert_pct"], c.get("corr_group"))
                                for c in other])[1] / 100.0) ** 2
                for other in by_code.values())
            self.assertAlmostEqual(raw[category], expected_abs ** 2 / total_var, places=6,
                                   msg=category)


class TestScopeIsDeclared(unittest.TestCase):
    def test_level_only_is_stated_in_the_docstring(self):
        """A missing trend assessment that nobody mentions reads as an oversight."""
        self.assertIn("LEVEL ONLY", kca.__doc__)
        self.assertIn("trend", kca.__doc__.lower())

    # The companion assertion - that the agriculture module still runs its own trend
    # assessment on its own base year - moved with that module to the agriculture repository.

class TestBenchmarkCoverage(unittest.TestCase):
    """data/benchmarks.csv was agriculture-only until the EDGAR booklet was read for every
    sector. These pin that the comparison stays honest about scope."""

    @classmethod
    def setUpClass(cls):
        import csv
        import os
        from pkinv.paths import DATA
        with open(asset_path(DATA, "benchmarks.csv"), encoding="utf-8") as f:
            cls.rows = list(csv.DictReader(f))

    def test_the_energy_sectors_have_a_benchmark(self):
        """Resolution is by category where EDGAR's scope is a category, and by SECTOR where
        it is not. EDGAR "Waste" spans disposal, burning and wastewater, and EDGAR
        "Transport" spans every mode - pointing those at a single category made the waste
        row resolve against open burning alone and print 0.14x."""
        cats = {r["engine_category"] for r in self.rows}
        for expected in ("Electricity and heat production", "Residential fuel combustion",
                         "Fugitive emissions from oil and gas", "Cement production"):
            self.assertIn(expected, cats, msg="category-scoped benchmark missing")
        for expected in ("waste", "transport"):
            self.assertIn(expected, cats, msg="sector-scoped benchmark missing")

    def test_every_row_declares_its_scope(self):
        """EDGAR's sectors are not this inventory's categories. A row without a scope note
        invites a reader to read a real scope difference as an error."""
        for r in self.rows:
            self.assertTrue(r["scope_detail"].strip(), msg=r["engine_category"])

    def test_the_largest_gap_stays_visible_and_says_it_is_partial(self):
        """The 44 Mt of industrial combustion must stay in the comparison, and must not be
        mistaken for something the engine now covers.

        This used to assert a "(not estimated)" sentinel row, then a captive-gas-only row.
        Both were superseded by the thing they were guarding against: as more of 1A2 became
        estimated, a benchmark pointed at one part of it understated coverage and the ratio
        drifted further from meaning anything. It now resolves against every 1A2 stream the
        inventory estimates, in whichever sector computes it, at about a third of EDGAR's
        figure - so the row must still say it is PARTIAL and the ratio must still be
        understood as coverage rather than a discrepancy. Fugitives and IPPU made the same
        transition earlier and are checked here for the same reason."""
        by_cat = {r["engine_category"]: r for r in self.rows}
        self.assertIn("1A2 (all estimated)", by_cat)
        row = by_cat["1A2 (all estimated)"]
        self.assertIn("industrial combustion", row["scope_detail"].lower())
        self.assertIn("PARTIAL", row["scope_detail"].upper())
        self.assertIn("COVERAGE", row["note"].upper())
        self.assertNotIn("NOT ESTIMATED HERE",
                         by_cat["Fugitive emissions from oil and gas"]["scope_detail"])
        self.assertNotIn("NOT ESTIMATED HERE", by_cat["Cement production"]["scope_detail"])

    def test_the_1A2_benchmark_covers_every_1A2_category(self):
        """The failure mode this key exists to prevent: a new 1A2 stream lands in some
        sector, the benchmark keeps pointing at the old subset, and the coverage ratio
        silently understates itself. Anything named (1A2) must be inside the key."""
        from pkinv.report import national_rollup
        components, categories, _sector_of = national_rollup.registry.build_all()
        parts = [c for c in categories if c.endswith("(1A2)")]
        self.assertGreater(len(parts), 1, "expected 1A2 to span more than one category")
        want = sum(c["co2e_Mt_AR5"] for c in components if c["category"] in parts)
        # Indexed by NAME rather than position: the row gained five boundary columns in the
        # audit round and five protocol columns (gwp, engine_period, gas_scope, bunker,
        # biogenic) in rc10, and a positional index would have started reading the wrong one.
        header = ["source", "engine_category", "scope_detail", "year", "gwp",
                  "engine_period", "benchmark_period",
                  "engine_boundary", "benchmark_boundary", "boundary_match",
                  "gas_scope", "bunker_treatment", "biogenic_treatment",
                  "comparison_role", "benchmark_Mt_co2e", "engine_Mt_co2e",
                  "ratio_engine_over_benchmark", "within_0.5_2.0x", "note"]
        resolved = {r[1]: dict(zip(header, r))
                    for r in national_rollup.benchmark_comparison()}
        self.assertAlmostEqual(resolved["1A2 (all estimated)"]["engine_Mt_co2e"], want,
                               places=2)

    def test_mismatched_scopes_say_which_way_they_run(self):
        """Two rows are known not to be like-for-like in opposite directions - transport
        (engine higher, all-modes EDGAR) and buildings (engine lower, households only).
        Both must say so, because the ratio alone would mislead.

        Transport now carries TWO EDGAR rows - since the rc5 period rebuild put the
        sector on FY2023-24, the 2024 row is the year-matched one and the 2022 row
        is superseded history - so the direction claim is asserted on the 2024 row,
        and the 2022 row must say it is superseded rather than posing as current.
        The engine sits BELOW EDGAR, and the note must say so and say why (bulk
        claimants are their own customer-class rows, excluded from the road control
        by construction, and EDGAR books the captive share under Industrial
        Combustion)."""
        by_cat = {r["engine_category"]: r for r in self.rows}
        transport = [r for r in self.rows
                     if r["engine_category"] == "transport" and r["source"] == "EDGAR"]
        self.assertEqual(len(transport), 2)
        matched = next(r for r in transport if r["year"] == "2024")
        superseded = next(r for r in transport if r["year"] == "2022")
        self.assertIn("below EDGAR", matched["note"])
        self.assertIn("YEAR-MATCHED", matched["note"])
        self.assertIn("by construction", matched["note"])
        self.assertIn("SUPERSEDED", superseded["note"])
        self.assertEqual(superseded["comparison_role"], "superseded")
        self.assertIn("households only", by_cat["Residential fuel combustion"]["note"])

if __name__ == "__main__":
    unittest.main()

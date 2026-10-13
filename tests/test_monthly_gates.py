"""The gates an external reviewer set for the 108-month product, as executable checks.

WHY A SEPARATE FILE. The monthly product already has tests, and they check that it builds and
closes. These check the things a REVIEWER would refuse it for, which is a different list: that
a month is never invented, that a relabelling never passes for an observation, and that a
global model's monthly profile never becomes this inventory's allocator and then also its
validation.

THE RELABELLING BANS ARE THE POINT OF THE FILE. Every one of them is a real way to make the
evidence grade look better without acquiring anything:

  dispatch is not production      a plant's monthly generation is not its monthly fuel
  cement is not clinker           calcination emissions follow clinker, not despatched bags
  urea is not ammonia             urea output is not gross ammonia and is not emitted CO2
  refinery output is not road     what a refinery made is not what a road burned
  upstream gas is not distribution a field's monthly production cannot time a leak in a city

Each is a case where a monthly series genuinely exists for the left-hand quantity, so the
temptation is to use it for the right-hand one and record the strong class it came with.

Run:  python3 -m unittest discover tests -p "test_monthly_gates.py"
"""
import collections
import csv
import os
import unittest

from pkinv.paths import OUTPUTS
from pkinv.report import temporal_profiles
from pkinv.core.io import read_rows

MONTHLY = "pakemis_monthly_fy2015_16_fy2023_24.csv"
PROFILES = "pakemis_temporal_profiles.csv"
ANNUAL = "pakemis_annual_fy2015_16_fy2023_24.csv"

# The window this product declares, in months. Not a tolerance: a 108-month product with 107
# months is a different product.
EXPECTED_MONTHS = 108

# Global inventories and reanalysis-derived profile products. They are legitimate VALIDATION
# and must never become the allocator: EDGAR's monthly values are themselves computed from
# temporal profiles, so using them to time this inventory and then citing them as agreement
# would be this release validating itself through a third party.
COMPARATOR_ONLY = ("edgar", "cams", "odiac", "ceds", "gfed")


def _rows(name):
    return read_rows(os.path.join(OUTPUTS, name))


class TestTheWindowIsExactlyWhatItClaims(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.monthly = _rows(MONTHLY)
        cls.profiles = _rows(PROFILES)

    def test_exactly_108_distinct_months(self):
        months = {r["month"] for r in self.monthly}
        self.assertEqual(len(months), EXPECTED_MONTHS)
        self.assertEqual(min(months), "201507")
        self.assertEqual(max(months), "202406")

    def test_no_duplicate_component_month_configuration(self):
        seen = collections.Counter(
            (r["component_id"], r["month"], r.get("configuration_id", ""))
            for r in self.monthly)
        duplicated = [k for k, n in seen.items() if n > 1]
        self.assertFalse(duplicated[:10], "%d duplicated component-months" % len(duplicated))

    def test_every_profile_year_carries_twelve_months(self):
        counted = collections.Counter(
            (r["component_id"], r["fiscal_year"], r["profile_variant"])
            for r in self.profiles)
        wrong = {k: n for k, n in counted.items() if n != 12}
        self.assertFalse(dict(list(wrong.items())[:5]),
                         "%d component-years do not carry twelve months" % len(wrong))


class TestTheWeightsCanOnlyDecideWhen(unittest.TestCase):
    """The registry's whole contract: it may move mass between months and may never create
    or destroy any. Everything else in the monthly product depends on this holding."""

    @classmethod
    def setUpClass(cls):
        cls.profiles = _rows(PROFILES)

    def test_every_weight_is_non_negative(self):
        negative = [r for r in self.profiles if float(r["weight"]) < 0]
        self.assertFalse(negative[:5], "%d negative monthly weights" % len(negative))

    def test_every_component_year_sums_to_one(self):
        totals = collections.defaultdict(float)
        for row in self.profiles:
            totals[(row["component_id"], row["fiscal_year"],
                    row["profile_variant"])] += float(row["weight"])
        for key, total in totals.items():
            self.assertAlmostEqual(total, 1.0, places=9, msg=str(key))

    def test_a_flat_profile_is_days_weighted_and_leap_years_are_right(self):
        """Equal twelfths is wrong by up to 10.7 per cent between February and July, and
        claims nothing in exchange. A leap year must show 29 days in February."""
        from pkinv.core import monthly as core_monthly
        for fy_start in (2015, 2019, 2023):
            weights = core_monthly.days_weighted_profile(fy_start)
            self.assertAlmostEqual(sum(weights.values()), 1.0, places=12)
            distinct = {round(w, 9) for w in weights.values()}
            self.assertGreater(len(distinct), 1,
                               "FY%d's flat profile is equal twelfths, not days-weighted"
                               % fy_start)
        leap = core_monthly.days_weighted_profile(2019)      # Feb 2020 has 29 days
        february = min(leap.values())
        self.assertAlmostEqual(february, 29.0 / 366.0, places=9)


class TestTheMonthsCloseToTheYear(unittest.TestCase):
    """No temporal allocation may alter an annual number. This is the invariant the whole
    programme rests on, and it is asserted here against the ANNUAL PRODUCT rather than
    against another monthly file."""

    def test_every_twelve_month_sequence_equals_its_annual_row(self):
        monthly = collections.defaultdict(float)
        for row in _rows(MONTHLY):
            key = (row["period_id"], row["sector_id"], row["category"], row["gas"])
            monthly[key] += float(row["co2e_Mt_AR5"] or 0.0)
        annual = collections.defaultdict(float)
        for row in _rows(ANNUAL):
            if row["grain"] != "category_gas":
                continue
            if row["configuration_id"] != "REF_2023_24":
                continue     # rc31: the S rows close in their own file, not here
            key = (row["period_label"], row["sector"], row["category"], row["gas"])
            annual[key] += float(row["co2e_Mt_AR5"] or 0.0)
        shared = set(monthly) & set(annual)
        self.assertGreater(len(shared), 200, "the two products barely overlap; the join key "
                                             "is wrong and this test is checking nothing")
        for key in sorted(shared):
            self.assertAlmostEqual(monthly[key], annual[key], places=4, msg=str(key))


class TestMissingIsNeverZero(unittest.TestCase):
    def test_no_month_is_silently_absent(self):
        """A component present in a year must be present in all twelve of its months. Twelve
        rows summing to the year is not the same as twelve rows existing, and a dropped month
        would pass the closure test above by inflating its neighbours."""
        per_year = collections.defaultdict(set)
        for row in _rows(MONTHLY):
            per_year[(row["component_id"], row["period_id"])].add(row["month"])
        short = {k: sorted(v) for k, v in per_year.items() if len(v) != 12}
        self.assertFalse(dict(list(short.items())[:5]),
                         "%d component-years do not carry twelve months" % len(short))

    def test_an_absent_sector_year_carries_no_monthly_rows_at_all(self):
        """NE means no estimate: a product that quietly wrote twelve zeros for an NE
        sector-year would be asserting zero emissions. The annual product has carried
        no NE sector-year since rc20 closed FY2015-16, so the invariant is vacuous
        today - it stays because the next partial year re-arms it automatically, and
        the panel-completeness assertion beside it is what keeps "no NE rows" a
        checked claim rather than a silence."""
        absent = {(r["period_label"], r["sector"]) for r in _rows(ANNUAL)
                  if r["completeness_state"] == "NE"}
        present = {(r["period_id"], r["sector_id"]) for r in _rows(MONTHLY)}
        for key in absent:
            self.assertNotIn(key, present,
                             "%s is declared NE in the annual product and carries monthly "
                             "rows anyway" % (key,))
        # the completeness claim, asserted from the product rather than assumed:
        # every published sector-year carries months
        annual_years = {(r["period_label"], r["sector"]) for r in _rows(ANNUAL)
                        if r["completeness_state"] == "E" and r["co2e_Mt_AR5"]}
        for key in sorted(annual_years):
            self.assertIn(key, present,
                          "%s/%s is estimated annually but carries no months" % key)


class TestTheRelabellingBans(unittest.TestCase):
    """Each of these is a monthly series that exists for one quantity and is tempting for a
    different one. The registry records what a profile is evidence OF; these check that the
    record and the use agree."""

    @classmethod
    def setUpClass(cls):
        cls.profiles = _rows(PROFILES)

    def _sources(self, predicate):
        return [r for r in self.profiles if predicate(r["source_id"].lower()
                                                      + " " + r["basis"].lower())]

    def test_a_production_series_never_times_a_process_it_does_not_measure(self):
        """timing_target is the mechanism, and it must not claim the emitting process where
        the source measures output or despatch."""
        for row in self.profiles:
            text = (row["source_id"] + " " + row["basis"]).lower()
            if "qim" in text or "despatch" in text or "production" in text:
                self.assertNotEqual(
                    row["timing_target"], "emitting_process",
                    "%s times a production series and claims the emitting process; cement "
                    "output is not clinker calcination and urea output is not ammonia"
                    % row["component_id"])

    def test_a_fuel_sale_series_never_claims_the_emitting_process(self):
        for row in self.profiles:
            if row["timing_target"] != "fuel_sale":
                continue
            self.assertNotIn("emitting", row["basis"].lower(),
                             "%s is a sales series describing itself as the emitting process"
                             % row["component_id"])

    def test_an_upstream_gas_profile_never_reaches_distribution_or_post_meter(self):
        """A field's monthly production cannot time a leak in a city's distribution network,
        and the physics table says so in as many words."""
        for row in self.profiles:
            if row["sector"] != "fugitives":
                continue
            downstream = any(word in row["subitem"].lower()
                             for word in ("distribution", "post-meter", "post meter"))
            if not downstream:
                continue
            text = (row["source_id"] + " " + row["basis"]).lower()
            self.assertNotIn("production", text,
                             "%s times a downstream leak on an upstream production series"
                             % row["component_id"])

    def test_a_borrowed_profile_declares_the_year_it_was_borrowed_from(self):
        for row in self.profiles:
            if row["temporal_evidence_class"] == "TE4":
                continue
            if "borrow" in row["basis"].lower() or "month-of-year" in row["basis"].lower():
                self.assertTrue(row["borrowed_from_year"],
                                "%s uses a borrowed shape and does not say from when"
                                % row["component_id"])

    def test_observed_month_count_is_zero_where_the_class_is_flat(self):
        """A days-weighted fallback that claimed observed months would be claiming evidence
        it does not have."""
        for row in self.profiles:
            if row["temporal_evidence_class"] == "TE4" and row["profile_id"] == "days_weighted":
                self.assertEqual(row["observed_month_count"], "0", row["component_id"])


class TestGlobalComparatorsStayOutOfTheAllocator(unittest.TestCase):
    """EDGAR's monthly values are themselves built from temporal profiles. Using them to time
    this inventory and then citing their agreement would be self-validation with an extra
    step."""

    def test_no_profile_is_sourced_from_a_global_comparator(self):
        for row in _rows(PROFILES):
            text = (row["source_id"] + " " + row["basis"] + " " + row["profile_id"]).lower()
            for comparator in COMPARATOR_ONLY:
                self.assertNotIn(
                    comparator, text,
                    "%s takes its monthly shape from %s, which is a comparator and must not "
                    "be the allocator" % (row["component_id"], comparator))


class TestTheThirdAxisIsDeclaredAndDerived(unittest.TestCase):
    """temporal_behavior says what the PROCESS does in time. It is derived from the physics
    table that already owns that judgement, so the two cannot disagree - which they would
    have, because the first version of it was a second table written from scratch."""

    @classmethod
    def setUpClass(cls):
        cls.profiles = _rows(PROFILES)

    def test_every_row_carries_a_behaviour_from_the_vocabulary(self):
        for row in self.profiles:
            self.assertIn(row["temporal_behavior"], temporal_profiles.BEHAVIORS,
                          row["component_id"])
            # PHYSICS uses a cross-reference idiom for siblings that share a driver -
            # "as gas production", "as distribution" - which is short and informative
            # precisely because it points at the entry that carries the argument. Demanding
            # prose there would push someone to paste a paragraph rather than cite one.
            basis = row["behavior_basis"]
            self.assertTrue(len(basis) > 20 or basis.startswith("as "),
                            "%s carries a behaviour with no usable reason: %r"
                            % (row["component_id"], basis))

    def test_the_behaviour_agrees_with_the_physics_table_that_owns_it(self):
        from pkinv.report import temporal_decomposition as decomposition
        for row in self.profiles[:400]:
            grain = decomposition.grain_of({"sector_id": row["sector"],
                                            "category": row["category"],
                                            "subitem": row["subitem"]})
            physics, _driver, _basis = decomposition._classify(row["sector"], grain)
            if physics == decomposition.CONTINUOUS:
                self.assertEqual(row["temporal_behavior"], temporal_profiles.CONTINUOUS,
                                 row["component_id"])
            elif physics == decomposition.STOCK:
                self.assertEqual(row["temporal_behavior"], temporal_profiles.STOCK_DRIVEN,
                                 row["component_id"])
            else:
                self.assertIn(row["temporal_behavior"],
                              (temporal_profiles.SEASONAL, temporal_profiles.EVENT_DRIVEN),
                              row["component_id"])

    def test_a_seasonal_process_is_never_counted_as_physically_flat(self):
        """The one that stops this becoming a scoring device. A seasonal or event-driven
        process has a shape whether or not this inventory observes it, so its flat profile is
        ignorance and must count against the weakly-timed share."""
        self.assertNotIn(temporal_profiles.SEASONAL, temporal_profiles.PHYSICALLY_FLAT)
        self.assertNotIn(temporal_profiles.EVENT_DRIVEN, temporal_profiles.PHYSICALLY_FLAT)
        self.assertNotIn(temporal_profiles.UNKNOWN, temporal_profiles.PHYSICALLY_FLAT)

    def test_the_three_published_shares_partition_the_product(self):
        facts = {r["fact_id"]: r["value"] for r in _rows("pakemis_product_facts.csv")}
        total = (float(facts["monthly_observed_share_pct"])
                 + float(facts["monthly_physical_share_pct"])
                 + float(facts["monthly_weakly_timed_share_pct"]))
        self.assertAlmostEqual(total, 100.0, delta=0.3,
                               msg="X + Y + Z = %.2f; the three published shares do not "
                                   "partition the monthly product" % total)


if __name__ == "__main__":
    unittest.main()


class TheLivestockClassificationIsPinned(unittest.TestCase):
    """Wave 3's livestock item, delivered as verification: the sixteenth review asked
    for day-weighted stock exposure formally classified physically-continuous, and
    that is the SHIPPED state - enteric and manure are continuous_by_process in the
    physics table, days-weighted flat in the layer, guarded to twelve decimals by
    the enumeration test. This pin makes the classification itself an assertion, so
    a future edit cannot quietly demote it to time_variable (which would put 1,344
    Mt into the unobserved-gap metric) or promote it to an invented curve."""

    def test_enteric_and_manure_are_continuous_by_process(self):
        from pkinv.report import temporal_decomposition as td
        for category in ("Enteric fermentation", "Manure management"):
            physics, _driver, basis = td._classify("agriculture", category)
            self.assertEqual(td.CONTINUOUS, physics, category)
            self.assertTrue(basis.strip(), category)

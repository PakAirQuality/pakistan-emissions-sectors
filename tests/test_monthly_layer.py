"""The monthly layer as a national product: every module, closing, and classified.

tests/test_monthly.py pins the contract itself and the two modules that carried it first.
This file pins the properties that only exist once all ten modules have a layer - that none
is missing, that the concatenation closes against the same annual components every other
national output is built from, that a census stock is never given a season, and that the
annual temporal_method a component declares is the one its own layer actually used.

Building every sector and every layer takes several seconds, so it is done once for the class.
"""
import csv
import os
import unittest

from pkinv.core import evidence, monthly, registry
from pkinv.paths import OUTPUTS
from pkinv.report import monthly_all, monthly_crosschecks

FY_START = 2023


class TestNationalMonthlyLayer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.layer_components = monthly_all.build()
        cls.annual, _categories, _sector_of = registry.build_all()
        cls.by_key = {(c["category"], c["subitem"], c["gas"]): c for c in cls.annual}

    def test_every_registered_module_has_a_layer(self):
        """A module cannot ship without one: the registry names the layer, and a sector
        whose layer is missing raises here rather than quietly contributing nothing to the
        national monthly product."""
        for sector in registry.all_sectors():
            module = registry.monthly_layer(sector.NAME)
            self.assertTrue(hasattr(module, "rows"),
                            "%s's monthly layer exposes no rows()" % sector.NAME)
        self.assertEqual(set(registry.MONTHLY_LAYERS),
                         {s.NAME for s in registry.all_sectors()})

    def test_the_twelve_months_close_to_the_annual_inventory(self):
        """Component by component, against registry.build_all() - not against whatever
        each layer handed back, which would let a layer close against its own variant."""
        monthly.check_closure(self.rows, self.annual)
        self.assertAlmostEqual(sum(r["co2e_Mt_AR5"] for r in self.rows),
                               sum(c["co2e_Mt_AR5"] for c in self.annual), places=9)

    def test_every_stream_has_exactly_twelve_fiscal_months(self):
        months = set(monthly.months_for(FY_START))
        seen = {}
        for r in self.rows:
            seen.setdefault((r["category"], r["subitem"], r["gas"]), set()).add(r["month"])
        for key, got in seen.items():
            self.assertEqual(got, months, key)

    def test_every_row_is_classified_and_says_what_on(self):
        for r in self.rows:
            self.assertIn(r["temporal_method"], evidence.TEMPORAL,
                          "%s/%s" % (r["category"], r["subitem"]))
            self.assertTrue(r["basis"].strip(),
                            "%s/%s carries no basis" % (r["category"], r["subitem"]))

    def test_no_enumeration_row_carries_a_non_flat_profile(self):
        """The reason activity_period_kind exists. A livestock census counts a stock once;
        it has no month, and a seasonal profile applied to it would be an invention with no
        activity data behind it at all. Unshaped and T4, or the run stops.

        UNSHAPED IS NOT EQUAL-TWELFTHS. A census stock is a stock EXPOSED, emitting at some
        rate per day for as long as the animals are alive, so its year divides by time and
        time is not in equal twelfths. This asserted 1/12 exactly, which quietly required
        February to emit as much as July. Days-weighting is still T4: it removes an
        arithmetic error, it does not add evidence about the source.
        """
        days = monthly.days_weighted_profile(monthly_all.FY_START)
        enumerated = 0
        for r in self.rows:
            annual = self.by_key[(r["category"], r["subitem"], r["gas"])]
            if annual.get("activity_period_kind") != "enumeration":
                continue
            enumerated += 1
            self.assertAlmostEqual(r["share"], days[r["month"]], places=12,
                                   msg="%s/%s is an enumeration with a shaped profile"
                                       % (r["category"], r["subitem"]))
            self.assertEqual(r["temporal_method"], "T4",
                             "%s/%s" % (r["category"], r["subitem"]))
        self.assertGreater(enumerated, 0,
                           "no enumeration rows reached the monthly layer - the livestock "
                           "census rows have stopped declaring themselves a stock")

    def test_the_declared_class_is_the_one_the_layer_used(self):
        """8a's temporal_method was a claim about evidence made before there was a layer to
        check it against. This is that check: the class a component declares must be the
        class covering most of its year in the layer built from that evidence."""
        modal = monthly.modal_class(self.rows)
        for key, cls in modal.items():
            self.assertEqual(self.by_key[key].get("temporal_method"), cls,
                             "%s declares %s and its layer is %s"
                             % (key[1], self.by_key[key].get("temporal_method"), cls))

    def test_a_shaped_profile_never_claims_more_than_its_evidence(self):
        """T4 means UNSHAPED here, and unshaped means T4. A shaped profile labelled T4
        would be an undeclared seasonal model; an unshaped one labelled T1 or T2 would
        claim an observation that produced no shape.

        Unshaped now means one of the two calendar-only profiles - equal twelfths, or each
        month weighted by its own length. Neither carries information about the source,
        which is what the class is about; the difference between them is whether the
        calendar was divided correctly.
        """
        flat = monthly.flat_profile(monthly_all.FY_START)
        days = monthly.days_weighted_profile(monthly_all.FY_START)
        for key, cls in monthly.modal_class(self.rows).items():
            shares = {r["month"]: r["share"] for r in self.rows
                      if (r["category"], r["subitem"], r["gas"]) == key}
            unshaped = (all(abs(s - flat[m]) < 1e-12 for m, s in shares.items())
                        or all(abs(s - days[m]) < 1e-12 for m, s in shares.items()))
            self.assertEqual(cls == "T4", unshaped,
                             "%s is class %s and %s unshaped"
                             % (key[1], cls, "is" if unshaped else "is not"))

    def test_the_class_distribution_is_reported_and_adds_up(self):
        by_class = monthly_all.by_class(self.rows)
        self.assertEqual(set(by_class) - set(evidence.TEMPORAL), set())
        self.assertAlmostEqual(sum(by_class.values()),
                               sum(c["co2e_Mt_AR5"] for c in self.annual), places=9)

    def test_most_of_the_inventory_is_flat_and_the_paper_says_so(self):
        """Not a target - a fact this release should not be able to overstate by accident.
        If a future round earns a lower T4 share, this test is the one that notices the
        manuscript needs rewriting."""
        by_class = monthly_all.by_class(self.rows)
        total = sum(by_class.values())
        self.assertGreater(by_class["T4"] / total, 0.5)
        self.assertLess(by_class.get("T1", 0.0) / total, 0.05)


class TestCrossChecks(unittest.TestCase):
    def test_the_agronomic_calendar_is_a_profile_in_its_own_right(self):
        profile = monthly_crosschecks.agronomic_profile(FY_START)
        self.assertEqual(len(profile), 12)
        self.assertAlmostEqual(sum(profile.values()), 1.0, places=12)

    def test_offtake_and_agronomy_disagree_and_the_disagreement_is_published(self):
        """They are not the same thing - one is when urea left the depot and the other is
        when the crop needs it - and a version of this repo that quietly reported them as
        agreeing would be hiding the width of its own monthly claim."""
        rows = monthly_crosschecks.fertiliser_check(FY_START)
        worst, total = monthly_crosschecks.summarise(rows)["fertiliser"]
        self.assertGreater(total, 0.10)
        self.assertLess(worst, 0.50)

    def test_the_direct_editions_reassemble_into_the_annual_edition(self):
        """FY2021-22 is the year with twelve separately published monthly editions, so
        summing them against the annual edition tests the ingest and OCAC's own internal
        consistency rather than an identity."""
        rows = [r for r in monthly_crosschecks.vintage_check()
                if r["check"].startswith("vintage:FY2021-22")]
        self.assertTrue(rows)
        for r in rows:
            self.assertLess(abs(r["difference"]), 0.01, r["check"])


class TestWrittenNationalFile(unittest.TestCase):
    def test_the_published_csv_carries_the_sector_and_the_class(self):
        path = os.path.join(OUTPUTS, "national_monthly_2024.csv")
        if not os.path.exists(path):
            self.skipTest("run python3 -m pkinv.report.monthly_all first")
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        self.assertTrue(rows)
        sectors = {r["sector"] for r in rows}
        self.assertEqual(sectors, {s.NAME for s in registry.all_sectors()})
        for r in rows:
            self.assertIn(r["temporal_method"], evidence.TEMPORAL)
        self.assertEqual(len(rows) % 12, 0)


if __name__ == "__main__":
    unittest.main()

"""The gap, priced: complete against the decomposition, and quoting no number of its own.

A request table assembled by attention omits whatever nobody thought about, and a document
that quotes a gap once goes on quoting it after the gap has closed. Both failures are silent
and both are what these tests are for:

  * every component whose unobserved mass exceeds one percent of the monthly product must be
    somebody's request. Completeness is asserted from the DECOMPOSITION's side, so the table
    cannot be complete merely because it looks tidy.
  * every figure in the generated document is read from the decomposition at generation time.
    The test regenerates and compares, so a hand edit to the document fails.
  * the requested shares must sum to the gap itself. A component counted under two requests
    would inflate the programme's apparent worth, and this is what notices.

Run:  python3 -m unittest discover tests -p "test_monthly_data_requests.py"
"""
import collections
import csv
import os
import unittest

from pkinv.paths import OUTPUTS, ROOT
from pkinv.report import monthly_data_requests as requests
from pkinv.core.io import read_rows


def _rows(name, base=OUTPUTS):
    return read_rows(os.path.join(base, name), comments=False)


class TestTheProgrammeIsCompleteAgainstTheGap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows("pakemis_monthly_data_requests.csv")
        cls.gap = requests.decomposition()

    def test_every_material_component_has_a_request(self):
        """Asserted from the decomposition's side, which is the only direction that catches
        an omission. A component big enough to matter and quiet enough to forget is exactly
        what a table like this loses."""
        asked = {(r["sector_id"], r["component"]) for r in self.rows}
        missing = sorted(set(requests.material_components()) - asked)
        self.assertFalse(missing, "these carry more than %.0f%% of the monthly product's mass, "
                                  "are carried flat, and nobody is being asked for them: %s"
                         % (requests.MATERIAL, missing))

    # rc20 opened the lane kind; the Wave-2 remainder added the four annual-scope
    # packets (HDIP fuel ledger, CMI industry-by-fuel, NFDC plant separation, IPPU
    # facility operating data) - each pays into a scope-registry activation gate,
    # not the timing gap, so each claims nothing from it.
    NON_TIMING = ("REQ-NOU-01", "MON-NHA-01", "REQ-HDIP-01", "REQ-CMI-01",
                  "REQ-NFDC-02", "REQ-IPPU-01")

    def test_non_timing_lanes_carry_no_weight(self):
        """rc20 added request lanes whose payoff is module or spatial evidence
        rather than monthly resolution. They ride the register so every drafted
        request lives in one place, and the contract is that they claim NOTHING
        from the timing gap: empty component, empty share."""
        rows = [r for r in self.rows if r["request_id"] in self.NON_TIMING]
        self.assertEqual({r["request_id"] for r in rows}, set(self.NON_TIMING))
        for r in rows:
            self.assertEqual((r["sector_id"], r["component"]), ("", ""))
            self.assertEqual(r["share_of_national_pct"], "")

    def test_every_request_names_a_component_that_exists(self):
        for row in self.rows:
            if row["request_id"] in self.NON_TIMING:
                continue
            self.assertIn((row["sector_id"], row["component"]), self.gap,
                          "%s names a component the decomposition does not have"
                          % row["request_id"])

    def test_no_component_is_counted_under_two_requests(self):
        """Otherwise the programme's headline worth is inflated by whatever was double-asked."""
        counted = collections.Counter((r["sector_id"], r["component"])
                                      for r in self.rows
                                      if r["request_id"] not in self.NON_TIMING)
        self.assertFalse([k for k, n in counted.items() if n > 1],
                         "components asked for twice: %s"
                         % [k for k, n in counted.items() if n > 1])

    def test_the_requested_share_equals_the_gap(self):
        total = sum(float(r["co2e_Mt_AR5"]) for r in self.gap.values())
        unobserved = sum(float(r["unobserved_Mt_AR5"]) for r in self.gap.values())
        asked = sum(float(r["share_of_national_pct"]) for r in self.rows
                    if r["share_of_national_pct"] != "")
        self.assertAlmostEqual(asked, 100.0 * unobserved / total, places=2)

    def test_every_request_says_what_to_send_and_on_what_boundary(self):
        for row in self.rows:
            for field in ("recipient", "period_requested", "requested_fields",
                          "definitions_and_boundary", "preferred_format", "purpose",
                          "status", "contact_or_reference"):
                self.assertTrue(row[field].strip(),
                                "%s has no %s" % (row["request_id"], field))


class TestTheDocumentQuotesNothingOfItsOwn(unittest.TestCase):
    def test_it_regenerates_identically(self):
        """The numbers live in the decomposition. A hand edit here is a number that will go
        stale where nothing can see it."""
        with open(os.path.join(ROOT, "docs", "monthly_data_requests.md"),
                  encoding="utf-8") as handle:
            shipped = handle.read()
        self.assertEqual(shipped, requests.document(),
                         "docs/monthly_data_requests.md is stale or hand-edited; run "
                         "python3 -m pkinv.report.monthly_data_requests")

    def test_a_request_for_a_component_that_vanished_raises(self):
        """Fails closed. A request left pointing at a component the decomposition no longer
        has would otherwise be published with an empty price."""
        original = requests.decomposition
        requests.decomposition = lambda: {}
        try:
            with self.assertRaises(KeyError):
                requests.build()
        finally:
            requests.decomposition = original


class TestThePowerProfileVariantIsPricedAndNotApplied(unittest.TestCase):
    """The constant within-year fuel mix: shown, so that refusing it is a decision."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(OUTPUTS, "pakemis_power_profile_variant.csv")
        if not os.path.exists(path):
            raise unittest.SkipTest("the variant has not been generated")
        cls.rows = _rows("pakemis_power_profile_variant.csv")

    def test_the_shares_sum_to_one_under_both_readings(self):
        for column in ("reference_share", "variant_share"):
            totals = collections.defaultdict(float)
            for row in self.rows:
                if row[column]:
                    totals[(row["fiscal_year"], row["subitem"])] += float(row[column])
            for key, total in totals.items():
                self.assertAlmostEqual(total, 1.0, places=4, msg="%s %s" % (column, key))

    def test_the_variant_never_covers_less_than_the_reference(self):
        """It can only add labelled generation, so a fall would mean it lost some."""
        for row in self.rows:
            self.assertGreaterEqual(float(row["variant_coverage"]),
                                    float(row["reference_coverage"]) - 1e-9,
                                    "%s %s" % (row["fiscal_year"], row["subitem"]))

    def test_it_carries_its_assumption_on_every_row(self):
        for row in self.rows:
            self.assertIn("constant within the year", row["assumption"])

    def test_no_variant_reaches_the_published_product_or_the_registry(self):
        """The whole point. The baseline registry is one variant deep and the monthly product
        knows nothing about this file."""
        from pkinv.report import temporal_profiles
        names = {r["profile_variant"] for r in _rows("pakemis_temporal_profiles.csv")}
        self.assertEqual(names, {temporal_profiles.REFERENCE_VARIANT})
        variant = {r["profile_variant"] for r in self.rows}
        self.assertNotIn(temporal_profiles.REFERENCE_VARIANT, variant)

    def test_something_would_change_under_the_assumption(self):
        """If the variant moved nothing it would price nothing, and its absence from the
        baseline would be a claim with no content behind it."""
        self.assertTrue([r for r in self.rows if r["newly_shaped"] == "yes"],
                        "the variant earns no subitem-year a shape, so refusing it costs "
                        "nothing and this table asserts something it cannot show")


if __name__ == "__main__":
    unittest.main()

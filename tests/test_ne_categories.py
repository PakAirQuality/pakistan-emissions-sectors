"""rc39 A4: a category declared Not Estimated must not publish a number, least of all a zero.

THE DEFECT THIS CLOSES. completeness.py declared 3.G Liming as NE - not estimated, pending
national lime-use activity data - while the engine published a "Liming CO2" row of exactly
0.000000 Gg inside the shared category "Liming & urea (CO2)". Both shipped in the same release.

They are not the same claim. NE says the inventory did not estimate this source. A published
zero says it did, and found nothing - the stronger statement, and the one a reader summing the
category ledger actually receives. Nobody measured Pakistan's agricultural lime use; the zero
came from two activity parameters set to 0 with the note "~0 pending data".

The completeness table is where an inventory states what it does and does not cover, so it is
the authority here, and this module holds the engine to it: for every category the table calls
NE or NO, the atomic annual product must carry no numeric row. Enforcing it in the product
rather than in the engine is deliberate - the engine is one of several writers, and what a
reader can verify is what was published.
"""
import collections
import csv
import os
import unittest

from _support import OUTPUTS, read_rows


def _completeness():
    return read_rows(os.path.join(OUTPUTS, "completeness.csv"))


def _atomic():
    return read_rows(os.path.join(OUTPUTS, "pakemis_atomic_annual.csv"))


class TestNotEstimatedMeansNoNumber(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.completeness = _completeness()
        cls.atomic = _atomic()

    def test_the_sweep_sees_both_products(self):
        """A closure test over an empty read passes; this is what stops that."""
        self.assertGreater(len(self.completeness), 20)
        self.assertGreater(len(self.atomic), 100)

    def test_no_ne_or_no_row_names_an_engine_category_that_carries_numbers(self):
        """Keyed on engine_category, NOT on the IPCC code.

        A code legitimately carries both statuses at once: 3.D is E for managed soils and NE
        for the N released by SOC mineralisation, a sub-source of the same code that this
        inventory does not estimate. Eleven such rows exist and every one of them names NO
        engine category - which is precisely how an honest NE looks. 3.G was the exception: it
        declared NE and named a category that published 4.8 Mt, so the notation key and the
        product disagreed about the same words. That is the defect, and it is a defect of the
        MAPPING, so the mapping is what this asserts."""
        by_category = collections.defaultdict(float)
        counts = collections.Counter()
        for row in self.atomic:
            value = row.get("co2e_Mt_AR5", "")
            if value in ("", None):
                continue
            by_category[(row.get("category") or "").strip()] += float(value)
            counts[(row.get("category") or "").strip()] += 1
        offenders = []
        for row in self.completeness:
            status = (row.get("notation_key") or "").strip()
            engine_category = (row.get("engine_category") or "").strip()
            if status not in ("NE", "NO") or not engine_category:
                continue
            if engine_category in by_category:
                offenders.append(
                    "%s (%s) is declared %s but names engine category %r, which publishes "
                    "%d atom(s) totalling %.6f Mt"
                    % ((row.get("code") or "").strip(), row.get("category", ""), status,
                       engine_category, counts[engine_category], by_category[engine_category]))
        self.assertFalse(offenders, "a row the completeness table calls NE or NO points at a "
                                    "category that publishes numbers:\n  "
                                    + "\n  ".join(offenders))

    def test_an_ne_row_without_an_engine_category_is_not_flagged(self):
        """The negative control for the rule above: the eleven honest NE sub-source rows must
        NOT trip it, or the guard would push people to delete true declarations."""
        honest = [r for r in self.completeness
                  if (r.get("notation_key") or "").strip() in ("NE", "NO")
                  and not (r.get("engine_category") or "").strip()]
        self.assertGreater(len(honest), 5, "the honest NE rows have vanished")

    def test_liming_is_declared_ne_and_maps_to_no_engine_category(self):
        """The specific case, pinned by name: 3.G must stay NE AND stop sharing a category
        with 3.H, because sharing one is how the zero got published under an NE heading."""
        liming = [r for r in self.completeness
                  if (r.get("code") or "").strip() == "3.C.2"]
        self.assertEqual(len(liming), 1)
        row = liming[0]
        self.assertEqual((row.get("notation_key") or "").strip(), "NE")
        engine_category = (row.get("engine_category") or "").strip()
        self.assertEqual(engine_category, "",
                         "3.G is NE but still names an engine category (%r), which is how a "
                         "numeric row reaches an NE declaration" % engine_category)

    def test_urea_is_estimated_and_named_for_what_it_is(self):
        urea = [r for r in self.completeness
                if (r.get("code") or "").strip() == "3.C.3"]
        self.assertEqual(len(urea), 1)
        self.assertEqual((urea[0].get("notation_key") or "").strip(), "E")
        self.assertEqual((urea[0].get("engine_category") or "").strip(), "Urea application")


class TestTheCombinedCategoryIsGone(unittest.TestCase):
    """The old name must not survive anywhere that feeds a reader: it asserted that liming
    and urea were estimated together, which was only ever true of the urea half."""

    def test_no_published_product_still_names_it(self):
        import glob
        from pkinv.paths import ROOT
        hits = []
        for path in glob.glob(os.path.join(ROOT, "outputs", "*.csv")):
            with open(path, encoding="utf-8", errors="replace") as handle:
                if "Liming & urea" in handle.read():
                    hits.append(os.path.basename(path))
        self.assertFalse(hits, "the combined category survives in: %s" % sorted(hits))

    def test_the_engine_emits_no_liming_row(self):
        from pkinv.sectors.agriculture import liming_urea
        from pkinv.sectors.agriculture.ef_library import InventoryData
        subitems = [c["subitem"] for c in liming_urea.compute(InventoryData())]
        self.assertEqual(subitems, ["Urea application CO2"])


if __name__ == "__main__":
    unittest.main()

"""The declared classification scheme, held to being complete in both directions.

WHY THIS EXISTS. Until 2026-10-06 the shipped `ipcc_code` column mixed two classifications -
UNFCCC CRT in sector 3, IPCC 2006 in sector 4 - and nothing in the suite asserted a scheme at
all. An external reviewer found it in a printed table and was right that the mix makes
automated comparison and aggregation unsafe. Declaring IPCC 2006 canonical is only worth
anything if something holds the declaration to the data, which is what this file does.

THE TWO DIRECTIONS. A registry can rot in either: a live component that no rule covers would
silently keep whatever code it had, and a rule matching nothing would sit here looking like
coverage long after the category it names was retired. Both are asserted. The pattern is the
one data/shared/parameters/parameter_scope.csv already uses for shared parameters.
"""
import collections
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from _support import OUTPUTS, read_rows                                  # noqa: E402
from pkinv.report import category_crosswalk as X                         # noqa: E402

SECTOR_3_PREFIXES = ("3.",)


def _atoms():
    return [r for r in read_rows(os.path.join(OUTPUTS, "pakemis_atomic_annual.csv"))
            if r["period_id"] == "FY2023-24"]


class TestTheSchemeIsDeclared(unittest.TestCase):
    def test_one_scheme_version_governs_every_rule(self):
        self.assertEqual(X.scheme_declared(), "ipcc2006/v1")

    def test_the_rules_were_read(self):
        """A closure test over an empty registry passes; this is what stops that."""
        self.assertGreater(len(X.rules()), 20)
        self.assertGreater(len([r for r in X.rules() if r["applies_to"] == "component"]), 5)

    def test_every_tier_is_from_the_vocabulary(self):
        allowed = {"exact", "split", "reclassified", "precursor", "unmapped",
                   "needs_separation"}
        for r in X.rules():
            self.assertIn(r["tier"], allowed, r["ipcc2006_code"] or r["crt_code"])

    def test_an_unmapped_rule_states_no_ipcc_code(self):
        """The instruction was not to invent a mapping. A row that claims tier=unmapped and
        then names a code would be exactly that, written down."""
        for r in X.rules():
            if r["tier"] == "unmapped":
                self.assertEqual(r["ipcc2006_code"], "",
                                 "%s is unmapped but names an IPCC 2006 code" % r["crt_code"])
                self.assertTrue(r["crt_code"], "an unmapped row must say what it came from")


class TestBothDirections(unittest.TestCase):
    """The registry covers the data, and the data covers the registry."""

    @classmethod
    def setUpClass(cls):
        cls.atoms = _atoms()
        if not cls.atoms:
            raise unittest.SkipTest("the atomic product has not been built here")

    def test_every_live_component_resolves(self):
        unresolved = []
        for a in self.atoms:
            try:
                X.resolve(a["category"], a["subitem"], a["gas"])
            except KeyError:
                # energy and IPPU resolve from the completeness matrix, which is the
                # declared fallback for the sectors whose codes are identical in both
                # schemes; only a sector-3 miss is a defect here
                if any(a["ipcc_code"].startswith(p) for p in SECTOR_3_PREFIXES):
                    unresolved.append((a["category"], a["subitem"], a["gas"]))
        self.assertFalse(unresolved,
                         "live components no crosswalk rule covers: %s" % unresolved)

    def test_every_component_rule_matches_a_live_component(self):
        used = set()
        for a in self.atoms:
            try:
                _, rule = X.resolve(a["category"], a["subitem"], a["gas"])
            except KeyError:
                continue
            used.add((rule["engine_category"], rule["subitem_prefix"], rule["gas"]))
        stale = [(r["engine_category"], r["subitem_prefix"], r["gas"])
                 for r in X.rules() if r["applies_to"] == "component"
                 and (r["engine_category"], r["subitem_prefix"], r["gas"]) not in used
                 # LULUCF is estimated but books outside every total, so its components do
                 # not appear in the atomic product; its rules are exercised by the
                 # completeness matrix instead and are named here rather than silently
                 # exempted
                 and not r["engine_category"].startswith("LULUCF")]
        self.assertFalse(stale, "crosswalk rules matching no live component: %s" % stale)

    def test_the_shipped_codes_are_what_the_crosswalk_resolves(self):
        """The product must carry the code the registry says, not one it kept."""
        wrong = []
        for a in self.atoms:
            try:
                code, _ = X.resolve(a["category"], a["subitem"], a["gas"])
            except KeyError:
                continue
            if code != a["ipcc_code"]:
                wrong.append((a["component_id"], a["ipcc_code"], code))
        self.assertFalse(wrong, "shipped code disagrees with the crosswalk: %s" % wrong[:5])


class TestTheSplitsAreReal(unittest.TestCase):
    """The two categories that split are the reason the code is a property of the component."""

    def test_exactly_the_declared_categories_split(self):
        self.assertEqual(X.split_categories(), {"Manure management", "Managed soils"})

    def test_each_split_reaches_the_product(self):
        atoms = _atoms()
        if not atoms:
            self.skipTest("the atomic product has not been built here")
        by_cat = collections.defaultdict(set)
        for a in atoms:
            by_cat[a["category"]].add(a["ipcc_code"])
        self.assertEqual(by_cat["Manure management"], {"3.A.2", "3.C.6"})
        self.assertEqual(by_cat["Managed soils"], {"3.C.4", "3.C.5"})

    def test_no_code_string_survives_from_the_retired_scheme(self):
        """3.A, 3.B, 3.C, 3.D and 3.F all exist in BOTH schemes with different meanings, so a
        leftover would look valid. The retired sector-3 leaves are the ones to check for."""
        atoms = _atoms()
        if not atoms:
            self.skipTest("the atomic product has not been built here")
        retired = {"3.E", "3.F", "3.G", "3.H", "3.I", "3.J", "LU"}
        live = {a["ipcc_code"] for a in atoms}
        self.assertFalse(live & retired,
                         "codes from the retired scheme are still shipped: %s"
                         % sorted(live & retired))


class TestNoProductKeepsARetiredCode(unittest.TestCase):
    """The sweep that found the miss the conservation check could not.

    Re-coding is verified two ways and they see different things. The conservation check
    aggregates by period x gas x configuration x geography, which is CODE-INDEPENDENT by
    construction - so it passed with the whole monthly lane still carrying 3.F and 3.H,
    because no mass had moved. Only a sweep of the code columns themselves finds a lane that
    was never rebuilt. A migration needs both: one says nothing moved, the other says
    everything moved.
    """

    # the sector-3 LEAVES that IPCC 2006 does not define. 3.A, 3.B, 3.C and 3.D are deliberately
    # absent: they are valid IPCC 2006 PARENTS, so their presence proves nothing either way.
    RETIRED = {"3.E", "3.F", "3.G", "3.H", "3.I", "3.J", "LU"}
    CODE_COLUMNS = ("ipcc_code", "code", "parent_code", "pakemis_codes")
    # The one file that keeps them, on purpose: it exists to be read against Pakistan's own
    # reporting, whose codes these are. Rewriting it would destroy what it is for.
    DELIBERATELY_CRT = {"crt_AFOLU_table.csv"}

    def test_the_sweep_sees_products(self):
        """A sweep over an empty glob passes; this is what stops that."""
        self.assertGreater(len(self._scan()[1]), 30,
                           "the code-column sweep has stopped matching products")

    def _scan(self):
        import csv as _csv
        import glob
        import io as _io
        found, scanned = [], []
        for path in sorted(glob.glob(os.path.join(OUTPUTS, "**", "*.csv"), recursive=True)):
            try:
                body = "".join(l for l in open(path, encoding="utf-8", errors="replace")
                               if not l.startswith("#"))
                rows = list(_csv.DictReader(_io.StringIO(body)))
            except Exception:
                continue
            if not rows:
                continue
            columns = [c for c in rows[0] if c in self.CODE_COLUMNS]
            if not columns:
                continue
            scanned.append(os.path.basename(path))
            if os.path.basename(path) in self.DELIBERATELY_CRT:
                continue
            for column in columns:
                for value in {(r.get(column) or "").strip() for r in rows}:
                    for part in value.replace("+", " ").replace(";", " ").split():
                        if part in self.RETIRED:
                            found.append("%s[%s]=%s" % (os.path.basename(path), column, part))
        return sorted(set(found)), scanned

    def test_no_product_ships_a_retired_sector_3_code(self):
        found, _ = self._scan()
        self.assertFalse(
            found,
            "products still carrying codes from the retired scheme - a lane that was not "
            "rebuilt, which the conservation check cannot see because it aggregates at a "
            "grain no code appears in:\n  " + "\n  ".join(found))

    def test_the_crt_exemption_is_not_a_hiding_place(self):
        """An exemption that stopped matching would silently widen."""
        import csv as _csv
        import io as _io
        for name in self.DELIBERATELY_CRT:
            path = os.path.join(OUTPUTS, name)
            if not os.path.exists(path):
                continue
            body = "".join(l for l in open(path, encoding="utf-8", errors="replace")
                           if not l.startswith("#"))
            rows = list(_csv.DictReader(_io.StringIO(body)))
            codes = {(r.get("code") or "").strip() for r in rows}
            self.assertTrue(codes & self.RETIRED,
                            "%s is exempted as deliberately CRT but carries no CRT-only code, "
                            "so the exemption is doing nothing" % name)


if __name__ == "__main__":
    unittest.main()


class TestEveryShippedCodeIsAuthoredInCompleteness(unittest.TestCase):
    """The positive half of the sweep (v3, the 23rd review's A4).

    TestNoProductKeepsARetiredCode proves no RETIRED code survives; it says nothing about a
    code that was never in either scheme (a typo, a sector-numbering slip like Pakistan's
    own BTR urea-at-3.C.2). This asserts that every code in a code column of every shipped
    product - the semantic tables and pakemis_btr_comparison.csv included, because the glob
    is recursive - is a code completeness.py::ROWS authors, a parent of one, or a sub-leaf below one. The CRT
    file keeps Pakistan's codes on purpose and is exempt here as there.
    """

    def test_every_product_code_is_a_row_or_a_parent_of_one(self):
        from pkinv.report.completeness import ROWS
        authored = {row[0] for row in ROWS}
        parents = set()
        for code in authored:
            parts = code.split(".")
            for n in range(1, len(parts)):
                parents.add(".".join(parts[:n]))
        allowed = authored | parents
        sweep = TestNoProductKeepsARetiredCode()
        strange = []
        import csv as _csv
        import glob
        import io as _io
        scanned = 0
        for path in sorted(glob.glob(os.path.join(OUTPUTS, "**", "*.csv"), recursive=True)):
            if os.path.basename(path) in sweep.DELIBERATELY_CRT:
                continue
            try:
                body = "".join(l for l in open(path, encoding="utf-8", errors="replace")
                               if not l.startswith("#"))
                rows = list(_csv.DictReader(_io.StringIO(body)))
            except Exception:
                continue
            if not rows:
                continue
            columns = [c for c in rows[0] if c in sweep.CODE_COLUMNS]
            if not columns:
                continue
            scanned += 1
            for column in columns:
                for value in {(r.get(column) or "").strip() for r in rows}:
                    for part in value.replace("+", " ").replace(";", " ").replace(",", " ").split():
                        if not part or not part[0].isdigit() or part in allowed:
                            continue
                        # a sub-leaf below the ROWS grain (1.B.2.a.i under 1.B.2.a) is an
                        # IPCC 2006 code ROWS aggregates, not a stranger
                        if any(part.startswith(code + ".") for code in authored):
                            continue
                        strange.append("%s[%s]=%s" % (os.path.basename(path), column, part))
        self.assertGreater(scanned, 30, "the sweep has stopped matching products")
        self.assertFalse(sorted(set(strange)),
                         "codes that completeness.py::ROWS does not author:\n  "
                         + "\n  ".join(sorted(set(strange))))

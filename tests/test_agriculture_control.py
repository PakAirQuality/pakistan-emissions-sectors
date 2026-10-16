"""Preserve the historical agriculture control without freezing current methods.

The rc39 external calculation describes the rc67 input vintage and IPCC nitrogen
configuration. Its exact values remain checked against the immutable release baseline.
Current source revisions and TAN/IPCC configurations are checked separately against
native components, so a historical model calculation cannot silently become an
observation that forbids a documented scientific change.
"""

from pkinv.assets import asset_path
import collections
import csv
import os
import unittest

from _support import OUTPUTS, read_rows

# The external audit's expected values, FY2023-24, Mt CO2e on AR5.
#
# THESE KEYS ARE THE AUDITOR'S CODES, AND THEY ARE UNFCCC CRT. They are left exactly as the
# audit supplied them, because the point of this file is a comparison against a figure computed
# outside the repository; rewriting the control's own codes to match ours would make it one
# step less external. What changed on 2026-10-06 is OUR side: the inventory adopted IPCC 2006
# as canonical, under which the auditor's 3.B splits into 3.A.2 and 3.C.6 and its 3.D into
# 3.C.4 and 3.C.5. The product is therefore folded back to the control's scheme through
# data/shared/lookups/category_crosswalk.csv before comparing - which is what a crosswalk is
# for, and which exercises it in the CRT direction. NO VALUE MOVED: the two split pairs sum to
# the auditor's figures to six decimal places, and the test below asserts that.
CONTROL = {
    "3.A": ("Enteric fermentation", 151.657650),
    "3.B": ("Manure management", 21.228487),
    "3.C": ("Rice cultivation", 16.548350),
    "3.D": ("Managed soils", 28.525954),
    "3.F": ("Field burning of residues", 0.669549),
    "3.H": ("Urea application", 4.824481),
}
CONTROL_TOTAL = 223.454471


def _agriculture_by_code(path=None):
    agg = collections.defaultdict(float)
    if path is None:
        from pkinv.paths import DATA
        path = os.path.join(DATA, "baselines", "rc67_integrated_campaign", "outputs", "pakemis_atomic_annual.csv")
    for row in read_rows(path):
        if row["period_id"] != "FY2023-24" or row["sector_id"] != "agriculture":
            continue
        value = row["co2e_Mt_AR5"]
        if value in ("", None):
            continue
        agg[row["ipcc_code"]] += float(value)
    return dict(agg)


def _folded_to_control_scheme():
    """Our IPCC 2006 codes, folded back to the auditor's CRT codes via the crosswalk."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "src"))
    from pkinv.report import category_crosswalk
    crt = {}
    for rule in category_crosswalk.rules():
        if rule["ipcc2006_code"] and rule["crt_code"]:
            crt.setdefault(rule["ipcc2006_code"], rule["crt_code"])
    folded = collections.defaultdict(float)
    for code, value in _agriculture_by_code().items():
        if code not in crt:
            raise AssertionError(
                "%s has no CRT counterpart in the crosswalk, so the external control cannot "
                "be compared against it" % code)
        folded[crt[code]] += value
    return dict(folded)


class TestHistoricalReleaseRetainsExternalControl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_code = _folded_to_control_scheme()
        cls.native = _agriculture_by_code()

    def test_the_sweep_found_the_sector(self):
        """A closure test over an empty read passes; this is what stops that."""
        self.assertTrue(self.by_code, "no agriculture atoms in the annual product")

    def test_every_category_matches_the_audit(self):
        for code, (name, expected) in sorted(CONTROL.items()):
            self.assertIn(code, self.by_code, "%s (%s) is absent from the product" % (code, name))
            self.assertAlmostEqual(
                self.by_code[code], expected, places=6,
                msg="%s %s: %.6f against the audit's %.6f. If this move is intended it is a "
                    "RE-BASE and belongs in a commit that says so."
                    % (code, name, self.by_code[code], expected))

    def test_the_sector_total_matches_the_audit(self):
        self.assertAlmostEqual(sum(self.by_code.values()), CONTROL_TOTAL, places=6)

    def test_the_sector_carries_no_category_the_control_does_not_name(self):
        """A new agriculture category would pass the six checks above and still break the
        total, so the vocabulary is closed here too. 3.G is absent BY DESIGN - it is Not
        Estimated and publishes no row (rc39 A4)."""
        self.assertEqual(sorted(self.by_code), sorted(CONTROL))
        self.assertNotIn("3.G", self.by_code)

    def test_the_split_categories_sum_to_the_controls_own(self):
        """The migration re-coded; it must not have re-estimated. The auditor reported one
        figure where IPCC 2006 reports two, so the pair has to add back to it exactly."""
        for crt_code, parts in (("3.B", ("3.A.2", "3.C.6")), ("3.D", ("3.C.4", "3.C.5"))):
            for part in parts:
                self.assertIn(part, self.native,
                              "%s is absent: the split did not reach the product" % part)
            self.assertAlmostEqual(
                sum(self.native[p] for p in parts), CONTROL[crt_code][1], places=5,
                msg="%s splits into %s, which must sum to the audit's %.6f"
                    % (crt_code, " + ".join(parts), CONTROL[crt_code][1]))


class TestCurrentReferenceHasExplicitMethodAndSourceRevision(unittest.TestCase):
    def test_current_native_categories_match_the_adopted_reference(self):
        from pkinv.sectors.agriculture import engine
        from pkinv.core import configurations as conf
        from pkinv.report.category_ledger import component_code
        expected = collections.defaultdict(float)
        for row in engine.components_for_fiscal_year(2024, nitrogen_method=conf.nitrogen_method(conf.REFERENCE)):
            expected[component_code(row["category"], row["subitem"], row["gas"])] += row["co2e_Mt_AR5"]
        current = _agriculture_by_code(os.path.join(OUTPUTS, "pakemis_atomic_annual.csv"))
        self.assertEqual(set(current), set(expected))
        for code in expected:
            self.assertAlmostEqual(current[code], expected[code], delta=5e-8)
        self.assertNotEqual(round(sum(current.values()), 6), CONTROL_TOTAL,
                            "the documented source/nitrogen revision unexpectedly disappeared")


class TestTheControlIsNotSelfReferential(unittest.TestCase):
    """The check that this file is worth having: the numbers above must not be reachable
    from the engine, or the comparison is the engine against itself."""

    def test_the_expected_values_appear_in_no_input(self):
        import subprocess
        from pkinv.paths import ROOT
        needles = ["151.657650", "21.228487", "16.548350",
                   "28.525954", "0.669549", "4.824481", "223.454471"]
        # The files ripgrep searched: CSV and JSON under data/ that git does not ignore, none
        # under a baselines/ folder. In Python since rc69, because the public CI runner has no
        # rg and the test errored there instead of checking anything.
        data = asset_path(ROOT, "data")
        try:
            listed = subprocess.run(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--",
                 os.path.relpath(data, ROOT)], cwd=ROOT, capture_output=True, check=True
            ).stdout.decode("utf-8").split("\0")
        except (OSError, subprocess.CalledProcessError):
            listed = [os.path.relpath(os.path.join(d, n), ROOT)
                      for d, _, names in os.walk(data) for n in names]
        hits = collections.defaultdict(list)
        for rel in sorted(p for p in listed if p.endswith((".csv", ".json"))):
            if "/baselines/" in "/" + rel or not os.path.isfile(os.path.join(ROOT, rel)):
                continue
            with open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            for needle in needles:
                if needle in text:
                    hits[needle].append(rel)
        self.assertFalse(dict(hits),
                         "a historical audit control appears in active model inputs: %s"
                         % dict(hits))


if __name__ == "__main__":
    unittest.main()

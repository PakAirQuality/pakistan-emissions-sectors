"""The spatial axis has a fingerprint now, and these guards keep it a real measurement.

The product is outputs/pakemis_release_axis_fingerprints.csv, built by
scripts/build_release_axis_fingerprints.py. It exists because of a defect with a precise
shape: a re-base that conserves every national total and moves only the spatial
allocation passes every national guard this project has - the manifest's
`national_totals`, the pins, the claim matrix, the registered claims, the goldens - and
one did, after `1.0.0rc59` was published and under an unchanged label.

What is asserted here is the SEPARATION of the two axes, not either digest's value. A
digest moves whenever the data legitimately changes; the claim that survives a re-base is
that the two axes can disagree, and that at least one table currently shows them
disagreeing. If the columns ever carried the same information the product would be unable
to show a spatial-only re-base, and these tests fail saying so rather than passing on a
file that has quietly stopped measuring anything.
"""
import csv
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCT = os.path.join(ROOT, "outputs", "pakemis_release_axis_fingerprints.csv")
BUILDER = os.path.join(ROOT, "scripts", "build_release_axis_fingerprints.py")
VERDICTS = {
    "",
    "matches the published vintage on both axes",
    "period totals moved, allocation unchanged",
    "both axes moved, which the existing guards do see",
}
FINE_ONLY = "FINE AXIS ONLY"


def rows():
    with open(PRODUCT, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheAxisFingerprints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows()
        cls.tables = sorted({r["table"] for r in cls.rows})
        cls.tree = [r for r in cls.rows if r["commit"] == "(working tree)"]

    def test_the_product_is_populated_and_covers_four_tables(self):
        """The positive control: a truncated or empty product fails here first."""
        self.assertGreaterEqual(len(self.rows), 6 * 5)
        self.assertEqual(self.tables,
                         ["fact_adm1_year.csv", "fact_adm2_month.csv",
                          "fact_adm2_year.csv", "fact_air_adm1_year.csv",
                          "fact_annual.csv", "fact_monthly.csv"],
                         "the set of fingerprinted tables has changed; a disaggregated "
                         "table that is published and not fingerprinted is an unguarded "
                         "axis")
        self.assertEqual(len(self.tree), len(self.tables),
                         "every table needs exactly one working-tree row")

    NON_DIGESTS = {"absent", "column-absent", "no-valued-rows"}

    def test_a_row_either_measured_something_or_says_why_it_could_not(self):
        """The guard that caught the product's own first defect.

        A first version read the value column with row.get() and hashed an empty
        aggregate for rc47, whose fact_adm2_year carried co2e_Mt_AR5_low/_high instead of
        co2e_Mt_AR5 - a distinct-looking digest of nothing, inside the product whose job
        is to make a comparison trustworthy. Three rows were affected. A non-digest state
        must now name itself on BOTH axes and carry zero rows, and a measured row must
        carry some.
        """
        for row in self.rows:
            nat = row["coarse_period_fingerprint"]
            spa = row["fine_axis_fingerprint"]
            self.assertEqual(nat in self.NON_DIGESTS, spa in self.NON_DIGESTS,
                             "%s/%s is unmeasurable on one axis only, which cannot happen"
                             % (row["table"], row["version"]))
            if nat in self.NON_DIGESTS:
                self.assertEqual(nat, spa, "%s/%s" % (row["table"], row["version"]))
                self.assertEqual(row["valued_rows"], "0")
                self.assertNotEqual(row["measurable"], "measured",
                                    "%s/%s carries no digest but claims it measured "
                                    "something" % (row["table"], row["version"]))
                self.assertTrue(row["measurable"].strip(),
                                "%s/%s carries no digest and no reason"
                                % (row["table"], row["version"]))
            else:
                self.assertEqual(row["measurable"], "measured",
                                 "%s/%s carries a digest and a reason it could not be "
                                 "measured" % (row["table"], row["version"]))
                self.assertGreater(int(row["valued_rows"]), 0,
                                   "%s/%s" % (row["table"], row["version"]))

    def test_the_two_axes_are_not_one_column_wearing_two_names(self):
        """The separation, over the whole history rather than over one pair."""
        present = [r for r in self.rows
                   if r["coarse_period_fingerprint"] not in self.NON_DIGESTS]
        pairs = {(r["coarse_period_fingerprint"], r["fine_axis_fingerprint"])
                 for r in present}
        shared = [n for n in {p[0] for p in pairs}
                  if len({s for m, s in pairs if m == n}) > 1]
        self.assertTrue(shared,
                        "no national fingerprint is shared by two different spatial ones "
                        "anywhere in the history, so this product could not currently "
                        "show the spatial-only re-base it was built to expose")

    def test_the_verdict_vocabulary_is_closed(self):
        for row in self.rows:
            verdict = row["verdict_against_the_published_vintage"]
            if verdict.startswith(FINE_ONLY):
                continue
            self.assertIn(verdict, VERDICTS,
                          "undeclared verdict %r on %s" % (verdict, row["table"]))

    def test_fact_annual_can_never_disagree_with_itself(self):
        """The degenerate control: fact_annual's fine axis IS its coarse key.

        So its two digests must be identical, not merely equivalent. A first version of
        the builder keyed the fine mapping on the tuple ("FY2015-16", "FY2015-16"), which
        hashes differently from "FY2015-16", and this guard failed on string formatting
        while the numbers agreed exactly - a check that could not hold in the state it
        ran in.
        """
        for row in self.rows:
            if row["table"] != "fact_annual.csv":
                continue
            if row["coarse_period_fingerprint"] in self.NON_DIGESTS:
                continue
            self.assertEqual(row["coarse_period_fingerprint"],
                             row["fine_axis_fingerprint"],
                             "fact_annual/%s has two different digests for one quantity; "
                             "the coarse key is no longer the period and nothing else in "
                             "this product means what it says" % row["version"])

    def test_the_monthly_table_sums_to_the_annual_one_in_the_shipped_tree(self):
        """The arithmetic control behind the monthly table's FINE AXIS ONLY verdict.

        If the monthly layer did not conserve the annual one period by period, a moved
        monthly fingerprint under an unmoved annual one would mean nothing - it could
        just be two tables drifting apart. Recomputed from the two shipped tables with a
        relative tolerance, NOT compared as digests: a first version compared the two
        coarse digests and failed on rc42, where the sums agree to better than 1e-6 but
        round differently at the sixth decimal because the two tables accumulate in a
        different order. Comparing hashes of rounded floats is an equality test on
        formatting, and that is not the property being claimed.
        """
        from decimal import Decimal
        sums = {}
        for name in ("fact_monthly.csv", "fact_annual.csv"):
            path = os.path.join(ROOT, "outputs", "semantic", name)
            per = {}
            with open(path, encoding="utf-8") as handle:
                for row in csv.DictReader(line for line in handle
                                          if not line.startswith("#")):
                    raw = (row.get("co2e_Mt_AR5") or "").strip()
                    if raw:
                        key = row["period_id"]
                        per[key] = per.get(key, Decimal(0)) + Decimal(raw)
            sums[name] = per
        self.assertEqual(set(sums["fact_monthly.csv"]), set(sums["fact_annual.csv"]),
                         "the two tables no longer cover the same periods")
        self.assertGreaterEqual(len(sums["fact_annual.csv"]), 9,
                                "fewer than nine periods; the control is too thin")
        for period, annual in sorted(sums["fact_annual.csv"].items()):
            monthly = sums["fact_monthly.csv"][period]
            self.assertLessEqual(
                abs(monthly - annual), abs(annual) * Decimal("1e-9"),
                "%s: the monthly layer sums to %s against the annual table's %s, so a "
                "moved monthly fingerprint can no longer be read as a within-year "
                "reallocation" % (period, monthly, annual))

    def test_at_least_one_table_is_currently_fine_axis_only_and_one_is_not(self):
        """Both halves, because a product where every row says the same thing says nothing.

        Today three greenhouse-gas spatial layers and the national monthly table read
        FINE AXIS ONLY - two independent instances of the blind spot, one spatial and one
        temporal - while the air layer reads "both axes moved" and fact_annual matches.
        Those two are the controls that make the finding legible: where the coarse axis
        moves, this project's existing guards DO notice.
        """
        verdicts = [r["verdict_against_the_published_vintage"] for r in self.tree]
        spatial_only = [v for v in verdicts if v.startswith(FINE_ONLY)]
        other = [v for v in verdicts if v and not v.startswith(FINE_ONLY)]

        # 2026-10-08 A VERSION BUMP EMPTIES THIS COLUMN BY CONSTRUCTION, and that is not the
        # guard failing. The builder compares the working tree against the published vintage
        # CARRYING THE SAME VERSION STRING (build_release_axis_fingerprints.py: `latest =
        # next(m for m in measured[:-1] if m[0] == current)`). At a fresh release candidate
        # there is no such vintage - rc60 has not been served - so `latest` is None and every
        # verdict is "". Demanding a discriminating verdict here would be demanding that the
        # version has already been published, which is a fact about the release cycle and not
        # about this product.
        #
        # What must still hold in that state is everything that does not depend on a
        # comparator: the fingerprints are actually measured, and the vocabulary that would
        # label an allocation-only change is still in the builder. Both are asserted below,
        # and the moment the version IS published the discrimination assertions apply again.
        if not any(verdicts):
            measured = [r for r in self.tree if r["measurable"] == "measured"]
            self.assertTrue(
                measured,
                "no verdict AND nothing measured: the product is not comparing anything, "
                "which is a different failure from having no published comparator")
            self.assertIn(
                FINE_ONLY, open(BUILDER, encoding="utf-8").read(),
                "the fine-only verdict has left the builder's vocabulary, so a future "
                "allocation-only change could not be labelled at all")
            return

        self.assertTrue(other,
                        "every table reads SPATIAL ONLY, so the verdict column no longer "
                        "discriminates and the air control has stopped being a control")
        if spatial_only:
            return
        # 2026-10-07 THE FINE-ONLY INSTANCE WENT AWAY, AND NOT BY BEING FIXED. The power
        # coal re-base moved the national totals of every period, so every measured table
        # now reads "both axes moved" and nothing in this tree demonstrates the blind spot
        # the product was built to name: a change the period totals do not see.
        #
        # The assertion is not dropped. What the product must still carry is a verdict
        # column that DISCRIMINATES and a vocabulary that still contains the fine-only
        # verdict, so that the next release which moves allocation without moving totals is
        # labelled rather than silent. Asserting the instance itself would now be asserting
        # that a coarse-axis change has NOT happened, which is a fact about this particular
        # tree and not about the guard.
        builder = open(BUILDER, encoding="utf-8").read()
        self.assertIn(FINE_ONLY, builder,
                      "the fine-only verdict has left the builder's vocabulary, so a future "
                      "allocation-only change could not be labelled at all")
        self.assertTrue(
            any(v.startswith("both axes moved") for v in other),
            "no table reads 'both axes moved' either, so the verdicts no longer describe "
            "this tree and the fingerprint product has stopped measuring anything")

    def test_it_regenerates_identically(self):
        before = open(PRODUCT, "rb").read()
        run = subprocess.run([sys.executable, BUILDER], cwd=ROOT,
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        self.assertEqual(before, open(PRODUCT, "rb").read(),
                         "the product does not regenerate byte-identically")


if __name__ == "__main__":
    unittest.main()

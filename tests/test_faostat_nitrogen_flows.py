"""The flows agree, so the manuscript may not attribute the gap to the flows.

WHY THIS TEST EXISTS. Section 10 explained managed soils at 0.49 of FAOSTAT by saying
FAOSTAT "applies a synthetic-fertiliser default to a national nitrogen supply that this
inventory tracks through an explicit ledger". The sentence pointed at the fertiliser, and the
fertiliser is the one thing the two compilations agree on - to 0.9 per cent. So did the
livestock, to 0.9 per cent, with this inventory counting MORE sheep, goats and camels, which
is the wrong direction for the headline.

This holds the facts the corrected sentence rests on: the two activity flows agree, the pools
map one-to-one so none of the gap is scope, the EF1 vintage accounts for a stated fraction,
and - since FAOSTAT's four items were acquired on 2026-09-30 - the remainder is localised to
pasture deposition rather than left as a residual. One pool runs the other way, which is the
only place the two compilations disagree about where the nitrogen goes rather than what
happens to it, and the paragraph says so.

A guard on an agreement is unusual and deliberate. The risk here is not that the numbers
drift - it is that a later round reads the 0.49 ratio, reaches for the nearest explanation
and writes the wrong one again. If the flows ever stop agreeing that is a real finding and
this test should fail loudly, because the whole paragraph then needs rewriting.
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import read_rows                                      # noqa: E402

OUT = os.path.join(ROOT, "outputs", "pakemis_faostat_nitrogen_flows.csv")

# How close "agree" is. Two compilations built independently from the same national
# statistics should land inside this; outside it, the activity is a live difference and the
# attribution in Section 10 no longer holds.
AGREE_PCT = 3.0


class TestTheNitrogenAgreesAndTheFactorsDoNot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(OUT):
            raise unittest.SkipTest("the nitrogen-flow comparison has not been built here")
        cls.rows = read_rows(OUT, comments=True)
        cls.by = {r["flow"]: r for r in cls.rows}

    def _ratio(self, flow):
        return float(self.by[flow]["pakemis_over_faostat"])

    def test_synthetic_fertiliser_nitrogen_agrees(self):
        r = self._ratio("synthetic fertiliser nitrogen")
        self.assertLess(
            abs(100 * (r - 1)), AGREE_PCT,
            "synthetic fertiliser nitrogen no longer agrees (ratio %.3f). Section 10 says it "
            "agrees to under a per cent and uses that to rule the fertiliser out as the "
            "source of the managed-soils gap; if this has moved, that paragraph is wrong."
            % r)

    def test_the_shared_livestock_species_agree_in_total(self):
        r = self._ratio("livestock head: all six species")
        self.assertLess(
            abs(100 * (r - 1)), AGREE_PCT,
            "the six shared livestock species no longer agree in total (ratio %.3f)" % r)

    def test_this_inventory_still_counts_more_small_ruminants(self):
        """The direction matters: more animals is more excreted nitrogen, not less.

        If this reversed, 'the residual runs the wrong way for the headline' would stop being
        true and the argument would need a different leg.
        """
        for sp in ("sheep", "goats", "camels"):
            r = self._ratio("livestock head: %s" % sp)
            self.assertGreater(
                r, 1.0,
                "PakEmis no longer counts more %s than FAOSTAT (ratio %.3f); Section 10's "
                "'wrong way for the headline' clause depends on it" % (sp, r))

    def test_every_pool_maps_onto_a_faostat_item(self):
        pools = [r for r in self.rows if r["row_kind"] == "pool"]
        self.assertTrue(pools, "no pool rows: the scope check is the first thing to do")
        unmapped = sorted(r["flow"] for r in pools if "(unmapped)" in r["basis"])
        self.assertFalse(
            unmapped,
            "these managed-soils pools map onto no FAOSTAT item, so part of the gap IS "
            "scope and Section 10's claim that none of it is would be false: %s" % unmapped)

    def test_the_ef_vintage_accounts_for_a_stated_share_and_no_more(self):
        main = float(self.by["managed soils, as reported"]["pakemis"])
        fao = float(self.by["managed soils, as reported"]["faostat"])
        ef = float(self.by["managed soils, at FAOSTAT's EF1 vintage"]["pakemis"])
        rest = float(self.by["unexplained after activity and EF1 vintage"]["pakemis"])
        self.assertGreater(ef, main, "FAOSTAT's EF1 vintage should raise this inventory")
        self.assertLess(ef, fao,
                        "the EF vintage alone should NOT reach FAOSTAT; if it does, the "
                        "unexplained remainder has gone and the paragraph needs rewriting")
        self.assertAlmostEqual(
            rest, fao - ef, places=2,
            msg="the declared remainder (%.2f) is not the gap left after the EF vintage "
                "(%.2f); the attribution no longer adds up" % (rest, fao - ef))

    def test_the_remainder_is_localised_and_names_its_pool(self):
        """This assertion was the opposite one until the items were acquired.

        It used to require the verdict to read NOT LOCALISABLE, which was true while only
        the SUM of FAOSTAT's four items was held. The acquisition made it false, and a
        product still claiming a residual cannot be located after it has been is exactly
        the stale-absence defect this repository keeps finding in itself.
        """
        v = self.by["unexplained after activity and EF1 vintage"]["verdict"]
        self.assertIn("LOCALISED", v,
                      "the remainder is no longer reported as localised: %r" % v[:120])
        self.assertIn("pasture", v,
                      "the verdict must name the pool that carries it: %r" % v[:120])

    def test_the_acquired_extract_validates_against_what_was_already_held(self):
        """The four items must sum to the benchmark the register already carried.

        This is the only check that the acquired extract is the right file at all: the
        benchmark row's 58.5 Mt came from this source before the items were acquired, so
        the items summing to it is independent confirmation rather than a tautology.
        """
        pools = [r for r in self.rows if r["row_kind"] == "pool"]
        self.assertEqual(len(pools), 4, "expected FAOSTAT's four managed-soils items")
        total = sum(float(r["faostat"]) for r in pools)
        reported = float(self.by["managed soils, as reported"]["faostat"])
        self.assertAlmostEqual(
            total, reported, places=2,
            msg="the acquired items sum to %.3f Mt but the benchmark register carries "
                "%.3f; either the extract is the wrong file or the register moved"
                % (total, reported))

    def test_the_residual_is_localised_to_pasture_deposition(self):
        """The finding the acquisition bought, and the one Section 10 now states."""
        pools = {r["flow"]: r for r in self.rows if r["row_kind"] == "pool"}
        gaps = {k: float(v["faostat"]) - float(v["pakemis"]) for k, v in pools.items()}
        biggest = max(gaps, key=gaps.get)
        self.assertEqual(
            biggest, "manure on pasture",
            "the largest pool gap is no longer pasture deposition but %r; Section 10 says "
            "two-thirds of the gap is pasture and that sentence would be wrong" % biggest)
        share = 100 * gaps[biggest] / sum(gaps.values())
        self.assertGreater(
            share, 50.0,
            "pasture deposition is now only %.1f per cent of the gap; 'two-thirds' in "
            "Section 10 needs restating" % share)

    def test_manure_applied_still_runs_the_other_way(self):
        """The one pool the factor vintage cannot explain, and the paragraph says so."""
        r = next(x for x in self.rows
                 if x["row_kind"] == "pool" and x["flow"] == "manure applied to soils")
        ratio = float(r["pakemis_over_faostat"])
        self.assertGreater(
            ratio, 1.0,
            "PakEmis is no longer HIGHER than FAOSTAT on manure applied to soils (%.3f). "
            "Section 10 uses that to separate a partition disagreement from a factor one."
            % ratio)

    def test_both_direct_factor_vintages_account_for_most_of_the_gap(self):
        """The result the pasture scenario bought, and Section 10's strongest claim."""
        main = float(self.by["managed soils, as reported"]["pakemis"])
        fao = float(self.by["managed soils, as reported"]["faostat"])
        both = float(self.by["managed soils, at BOTH of FAOSTAT's 2006 direct "
                             "factors"]["pakemis"])
        share = 100 * (both - main) / (fao - main)
        self.assertGreater(
            share, 80.0,
            "the two 2006 direct factors now account for only %.0f per cent of the gap; "
            "Section 10 says 87 and that sentence needs restating" % share)
        self.assertLess(
            both, fao,
            "the two direct vintages now reach or exceed FAOSTAT (%.2f against %.2f), so "
            "there is no remainder left for the indirect factors and the partition - which "
            "Section 10 claims there is" % (both, fao))

    def test_the_two_factor_scenarios_are_disjoint(self):
        """Section 10 says no subitem belongs to both sets, and adds their effects.

        If they ever overlapped, the combined figure would double-count and the 87 per cent
        would be an overstatement rather than an addition.
        """
        from pkinv.eval import sensitivity_table as st
        overlap = sorted(set(st.EF1_SUBITEMS) & set(st.EF3PRP_DEFAULT))
        self.assertFalse(
            overlap,
            "these subitems are scaled by BOTH the EF1 and EF3PRP scenarios, so the "
            "combined case double-counts them: %s" % overlap)

    def test_the_shipped_file_matches_a_fresh_build(self):
        r = subprocess.run(
            [sys.executable, "-m", "pkinv.sectors.agriculture.faostat_nitrogen_flows",
             "--check"],
            capture_output=True, text=True, cwd=ROOT,
            env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src")))
        self.assertEqual(r.returncode, 0,
                         "the nitrogen-flow comparison is stale; rebuild it.\n%s%s"
                         % (r.stdout, r.stderr))


if __name__ == "__main__":
    unittest.main()

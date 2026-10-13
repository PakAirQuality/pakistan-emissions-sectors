"""The two Lahore SO2 diagnosis tables (rc60).

The attribution CLOSES: its booked effect rows sum to the published nine-year change exactly, and
the two row kinds that are not part of that sum - a counterfactual and a band - stay out of it.
The EDGAR comparison COMPARES AND DOES NOT FIT: every register is byte-identical across a run of
it, its national self-check reproduces EDGAR's own published country total, and the fiscal years
EDGAR does not reach are typed not-compared rather than borrowed.

These are the guarantees that make a diagnosis readable. A decomposition whose parts do not sum to
the whole is a set of assertions; a comparison that writes back into a register is a calibration
wearing a comparison's name.
"""

from pkinv.assets import asset_path
import hashlib
import os
import subprocess
import sys
import unittest
from collections import defaultdict

from pkinv.core.io import read_rows
from pkinv.paths import DATA, OUTPUTS

ROOT = os.path.join(os.path.dirname(__file__), "..")
ATTRIBUTION = os.path.join(OUTPUTS, "pakemis_air_lahore_so2_attribution.csv")
COMPARISON = os.path.join(OUTPUTS, "pakemis_air_lahore_external_comparison.csv")
LAHORE_VIEW = os.path.join(OUTPUTS, "pakemis_air_lahore_by_year.csv")
REGISTERS = (
    asset_path(DATA, "air_emission_factors.csv"),
    asset_path(DATA, "air_source_classes.csv"),
    asset_path(DATA, "activity", "industry", "fuel_sulfur_evidence.csv"),
    asset_path(DATA, "industry_params.csv"),
    asset_path(DATA, "physical_sources.csv"),
)
KINDS = {"booked", "counterfactual", "bound", "note"}
START, END = "FY2015-16", "FY2023-24"


def _digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def published_change():
    """The nine-year change in Lahore District SO2, read from the shipped district view."""
    total = defaultdict(float)
    for r in read_rows(LAHORE_VIEW):
        if (r["pollutant"] == "SO2" and r["configuration_id"] == "REF_2023_24"
                and r["row_kind"] == "district"):
            total[r["period_id"]] += float(r["emissions_Gg"])
    return total[END] - total[START], total


class TestAttributionCloses(unittest.TestCase):
    def setUp(self):
        self.rows = read_rows(ATTRIBUTION)

    def test_the_booked_effects_sum_to_the_published_change(self):
        change, _ = published_change()
        effects = sum(float(r["effect_on_change_Gg"]) for r in self.rows
                      if r["kind"] == "booked" and r["effect_on_change_Gg"]
                      and r["stream"] != "ALL STREAMS")
        self.assertAlmostEqual(effects, change, places=5,
                               msg="the decomposition must account for the whole change")

    def test_the_total_row_carries_the_published_endpoints(self):
        _, total = published_change()
        row = [r for r in self.rows if r["stream"] == "ALL STREAMS" and r["kind"] == "booked"]
        self.assertEqual(len(row), 1)
        self.assertAlmostEqual(float(row[0]["start_Gg"]), total[START], places=5)
        self.assertAlmostEqual(float(row[0]["end_Gg"]), total[END], places=5)

    def test_counterfactuals_and_bounds_are_never_added(self):
        for r in self.rows:
            if r["kind"] in ("counterfactual", "bound", "note"):
                self.assertEqual(r["effect_on_change_Gg"], "",
                                 "%s row %s must carry no effect" % (r["kind"], r["stream"]))

    def test_every_row_declares_a_kind_and_a_reading(self):
        for r in self.rows:
            self.assertIn(r["kind"], KINDS, r)
            self.assertTrue(r["reading"].strip(), r)
            self.assertTrue(r["channel"].strip(), r)

    def test_the_declared_sulfur_channel_names_its_register(self):
        rows = [r for r in self.rows
                if r["channel"] == "declared sulfur regime" and r["kind"] == "booked"]
        self.assertTrue(rows, "the 2017 fuel-specification step must appear as its own channel")
        for r in rows:
            self.assertTrue("fuel_sulfur" in r["evidence"] or "air_source_classes" in r["evidence"],
                            r)

    def test_the_withdrawn_trend_range_stays_on_the_record(self):
        """It varied ONE endpoint against an unchanged denominator. The row says so rather than
        vanishing, and no bound row claims a trend."""
        note = [r for r in self.rows if r["stream"] == "ALL STREAMS" and r["kind"] == "note"]
        self.assertEqual(len(note), 1)
        self.assertIn("WITHDRAWN", note[0]["reading"])
        for r in self.rows:
            if r["kind"] == "bound":
                self.assertNotIn("decline of", r["reading"])

    def test_the_brick_band_says_what_it_bounds(self):
        """The band uses the NEPRA metered power burn; the central uses HDIP's power column. They
        are not the same calculation, so a value outside the band is a seam, not an error."""
        for r in self.rows:
            if r["kind"] == "bound" and "brick" in r["stream"]:
                self.assertIn("NEPRA", r["reading"])
                self.assertIn("not an uncertainty interval", r["reading"])

    def test_a_declared_sulfur_step_is_not_called_activity(self):
        """The whole point: a fuel specification changing is not a fuel quantity changing."""
        diesel = [r for r in self.rows
                  if "diesel" in r["stream"] and r["kind"] == "booked"
                  and r["channel"] == "declared sulfur regime"]
        self.assertTrue(diesel)
        self.assertLess(sum(float(r["effect_on_change_Gg"]) for r in diesel), -1.0,
                        "the declared step should carry well over a kilotonne of the decline")


class TestComparisonDoesNotFit(unittest.TestCase):
    def setUp(self):
        self.rows = read_rows(COMPARISON)

    def test_the_registers_are_byte_identical_across_a_run(self):
        before = {p: _digest(p) for p in REGISTERS}
        subprocess.run([sys.executable,
                        os.path.join(ROOT, "scripts", "build_air_lahore_external_comparison.py")],
                       check=True, capture_output=True)
        after = {p: _digest(p) for p in REGISTERS}
        self.assertEqual(before, after)

    def test_the_national_self_check_reproduces_edgars_own_total(self):
        """Single-category checks must land on 1. The grouped ones and the boundary rows have
        their own tolerances and are asserted in the crosswalk test below."""
        checks = [r for r in self.rows
                  if r["row_kind"] == "self_check" and r["ratio_engine_over_edgar"]
                  and r["edgar_stream"] in ("IND", "NMM")]
        self.assertGreaterEqual(len(checks), 16)
        for r in checks:
            self.assertAlmostEqual(float(r["ratio_engine_over_edgar"]), 1.0, places=2,
                                   msg="a polygon summation that cannot reproduce EDGAR's own "
                                       "country total says nothing about a district: %s" % r)

    def test_years_beyond_edgar_are_not_compared(self):
        for r in self.rows:
            if r["row_kind"] != "comparison":
                continue
            if r["period_id"] in ("FY2022-23", "FY2023-24"):
                self.assertEqual(r["edgar_Gg"], "", r)
                self.assertEqual(r["ratio_engine_over_edgar"], "", r)
                self.assertIn("not compared", r["reading"])

    def test_the_inventories_it_cannot_use_are_rows_not_silence(self):
        named = {r["edgar_stream"] for r in self.rows if r["row_kind"] == "not_compared"}
        for name in ("CEDS", "CAMS-GLOB-ANT", "HTAP v3"):
            self.assertIn(name, named,
                          "an inventory that cannot answer the question is a typed row, not a gap")
        for r in self.rows:
            if r["row_kind"] == "not_compared":
                self.assertTrue(len(r["reading"]) > 40, r)

    def test_the_sector_disagreements_are_stated(self):
        findings = [r for r in self.rows if r["row_kind"] == "finding"]
        self.assertGreaterEqual(len(findings), 5)
        streams = {r["edgar_stream"] for r in findings}
        for expected in ("IND", "ENE", "TRO", "RCO", "NMM"):
            self.assertIn(expected, streams)

    def test_the_crosswalk_is_proved_by_arithmetic_not_by_labels(self):
        """The defect this product shipped with: NMM (2.A.1, mineral PROCESS) was used as the
        counterpart for kiln FUEL, which is 1.A.2 and therefore the IND grid. The guard is not a
        comment - it is that each gridded category reproduces EDGAR's own published country total
        for the IPCC code the crosswalk pairs it with."""
        pairs = defaultdict(list)
        for r in self.rows:
            if r["row_kind"] == "self_check" and r["ratio_engine_over_edgar"]:
                pairs[r["edgar_stream"]].append(float(r["ratio_engine_over_edgar"]))
        for single in ("IND", "NMM"):
            self.assertIn(single, pairs, "the crosswalk check for %s is missing" % single)
            for ratio in pairs[single]:
                self.assertAlmostEqual(ratio, 1.0, places=2,
                                       msg="%s does not reproduce its own published category" % single)
        # multi-stream categories are looser: the workbook's code may not be exactly the union
        for grouped in ("CHE", "IRO+NFE"):
            self.assertIn(grouped, pairs)
            for ratio in pairs[grouped]:
                self.assertLess(abs(ratio - 1.0), 0.10, grouped)

    def test_every_sector_is_fetched_so_none_is_read_by_leftover(self):
        whole = [r for r in self.rows
                 if r["row_kind"] == "self_check" and r["edgar_stream"] == "ALL SECTORS"]
        self.assertGreaterEqual(len(whole), 8)
        for r in whole:
            self.assertAlmostEqual(float(r["ratio_engine_over_edgar"]), 1.0, places=3,
                                   msg="the sector grids must reconstruct TOTALS: %s" % r)

    def test_a_ratio_is_formed_only_where_the_crosswalk_declares_a_counterpart(self):
        for r in self.rows:
            if r["row_kind"] != "comparison" or not r["ratio_engine_over_edgar"]:
                continue
            self.assertTrue(r["engine_Gg"], r)
            self.assertNotIn("no counterpart declared", r["engine_basis"], r)
            self.assertNotIn("typed NE", r["engine_basis"],
                             "a typed absence is not a zero and cannot carry a ratio: %s" % r)

    def test_the_exact_fiscal_year_is_computed_where_monthly_is_held(self):
        """Eight calendar years are not eight July-June years, and the product must measure the
        approximation rather than assert it is small."""
        exact = [r for r in self.rows if r["row_kind"] == "comparison_exact_fy"]
        self.assertTrue(exact, "the monthly grids give exact fiscal years; use them")
        for r in exact:
            self.assertIn("July", r["calendar_basis"])
            self.assertIn("exact", r["reading"])

    def test_the_withdrawn_finding_stays_on_the_record(self):
        """A correction that deletes the wrong claim leaves no trace of having been wrong."""
        nmm = [r for r in self.rows if r["row_kind"] == "finding" and r["edgar_stream"] == "NMM"]
        self.assertEqual(len(nmm), 1)
        self.assertIn("WITHDRAWN", nmm[0]["reading"])
        self.assertIn("2.A.1", nmm[0]["reading"])


    def test_a_plant_derived_row_may_not_describe_itself_as_a_borrowed_share(self):
        """THE CONTRADICTION THAT MISLED A REVIEWER, made machine-checkable.

        Lahore's power SO2 stopped being a share of a national pattern at rc61, when the admitted
        fleet began declaring its own provincial marginal and placing each station on its own
        coordinate. Four shipped artefacts went on saying otherwise for three releases - a banner
        asserting the release published nothing, a docstring citing superseded values, an
        attribution note reading "it has never been in this curve in any year", and this panel's
        own per-row note calling it "the district's share of a national or provincial pattern, not
        a measurement". A reviewer read them and concluded the number was borrowed. Every one of
        those was checkable against the class register, and nothing checked them.

        The rule: if a class declares a `power_admission:*` spatial override, no row carrying its
        mass may describe itself as a share of a national or provincial pattern."""
        overrides = {r["source_class_id"]: r["spatial_override"]
                     for r in read_rows(asset_path(DATA, "air_source_classes.csv"))}
        declaring = {c for c, o in overrides.items() if o.startswith("power_admission:")}
        self.assertTrue(declaring, "no class declares a power_admission override any more; if the "
                                   "admission was withdrawn this test should go with it")
        # MATCH THE CLAIM, NOT ITS WORDS. The first version of this test searched for the phrase
        # "share of a national" and failed on the corrected note, which opens "NOT a share of a
        # national pattern" - a guard that cannot tell an assertion from its denial. The generic
        # allocation sentence has a distinctive opening that no correction of it reproduces, so
        # the test is whether the row carries THAT sentence.
        generic_opening = "the release's ADM2 allocation for the sector's anchor streams"
        offending = []
        for row in read_rows(LAHORE_VIEW):
            if row["sector_id"] != "power" or row["pollutant"].upper() != "SO2":
                continue
            if generic_opening in row["note"]:
                offending.append((row["period_id"], row["note"][:60]))
        self.assertFalse(offending,
                         "the Lahore power SO2 row describes itself as a borrowed share while its "
                         "classes declare their own placement: %s" % offending[:3])


if __name__ == "__main__":
    unittest.main()

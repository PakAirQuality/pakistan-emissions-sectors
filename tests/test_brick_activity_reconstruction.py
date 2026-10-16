"""Brick-kiln coal from a kiln count and a measured fuel rate: independent of HDIP, and bounded.

The guard that matters is the anti-circularity one. HDIP's brick column is a residual of domestic
coal production by the publisher's own footnote, so an estimate built from that balance cannot test
it. Every input here must come from somewhere else, and the product must refuse to name a central
while two independent sources disagree about the scale by a factor of three.
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

from _support import OUTPUTS, ROOT
from _support import readable  # noqa: E402

OUT = os.path.join(OUTPUTS, "pakemis_brick_activity_reconstruction.csv")
EVIDENCE = asset_path(ROOT, "data", "activity", "industry", "brick_kiln_activity_evidence.csv")
PERIODS = ["%d-%02d" % (y, (y + 1) % 100) for y in range(2015, 2024)]


def rows(path):
    with open(path, encoding="utf-8") as h:
        return list(csv.DictReader(l for l in h if not l.startswith("#")))


class Evidence(unittest.TestCase):
    def test_every_row_cites_a_held_document_and_a_page(self):
        for r in rows(EVIDENCE):
            self.assertTrue(os.path.exists(asset_path(ROOT, r["source_file"]))
                            or not readable(r["source_file"]), r["evidence_id"])
            self.assertTrue(r["page"].strip(), r["evidence_id"])

    def test_nothing_derived_from_hdip_enters_the_evidence(self):
        """The circularity trap: a study that takes its coal from the Economic Survey is not
        independent evidence about the Economic Survey."""
        for r in rows(EVIDENCE):
            self.assertEqual(r["hdip_derived"], "no", r["evidence_id"])

    def test_every_row_says_what_it_does_not_measure(self):
        for r in rows(EVIDENCE):
            self.assertTrue(r["what_it_does_not_measure"].strip(), r["evidence_id"])

    def test_a_detected_kiln_is_not_claimed_to_be_an_operating_one(self):
        r = {x["evidence_id"]: x for x in rows(EVIDENCE)}["hamdani_kilns_2023"]
        self.assertEqual(r["quantity_kind"], "detected_kilns")
        self.assertIn("OPERATING STATUS", r["what_it_does_not_measure"])

    def test_the_comparative_specific_energies_name_their_country(self):
        for r in rows(EVIDENCE):
            if r["quantity_kind"].startswith("specific_energy"):
                self.assertIn("COMPARATIVE", r["geography"])
                self.assertNotIn("Pakistan", r["geography"])


class Reconstruction(unittest.TestCase):
    def setUp(self):
        self.rows = {r["fiscal_year"]: r for r in rows(OUT)}

    def test_nine_years_and_no_central(self):
        self.assertEqual(sorted(self.rows), PERIODS)
        for fy, r in self.rows.items():
            self.assertEqual(r["independent_level_central_kt"], "", fy)
            self.assertIn("NO CENTRAL", r["note"])

    def test_the_independent_level_is_the_sources_own_national_figure(self):
        """rc54 correction. rc53 scaled the paper's Punjab total up on this release's kiln frame
        and called the result the independent national level, without reading the national figure
        the same page prints. The scale-out survives as a cross-check that disagrees."""
        r = self.rows["2023-24"]
        self.assertEqual(float(r["independent_level_low_kt"]), 6500.0)
        kilns, per_kiln = float(r["punjab_kilns"]), float(r["coal_per_kiln_t"])
        share = float(r["punjab_share_of_national_kilns"])
        self.assertEqual((kilns, per_kiln), (10394.0, 328.2))
        self.assertAlmostEqual(float(r["kiln_frame_scale_out_kt"]), kilns * per_kiln / 1000.0 / share, places=0)
        self.assertIn("percent", r["scale_out_vs_source_national"])

    def test_the_scale_out_disagrees_with_the_source_and_says_so(self):
        for fy, r in self.rows.items():
            ratio = float(r["kiln_frame_scale_out_kt"]) / float(r["independent_level_low_kt"])
            self.assertLess(ratio, 0.7, fy)
            self.assertIn("the kiln frame puts", r["scale_out_vs_source_national"])

    def test_the_measured_intensity_is_pakistani_and_replaces_the_unsourced_band(self):
        """184 g/brick (FCBTK) and 155 g (zig-zag), measured on 60 kilns in Faisalabad - not the
        70-100 g band that was carried with no page behind it."""
        r = self.rows["2023-24"]
        self.assertEqual((r["intensity_g_per_brick_measured_low"],
                          r["intensity_g_per_brick_measured_high"]), ("155", "184"))

    def test_the_official_series_swings_around_a_stable_fleet(self):
        """The finding: one counted, surveyed fleet against an official column that moves by a
        factor of seven across the window."""
        ratios = {fy: float(r["official_over_independent"]) for fy, r in self.rows.items()}
        self.assertGreater(max(ratios.values()) / min(ratios.values()), 5.0)
        self.assertGreater(ratios["2020-21"], 1.3)
        self.assertLess(ratios["2023-24"], 0.2)
        self.assertIn("BELOW HALF", self.rows["2023-24"]["reading"])

    def test_the_scale_disagreement_is_carried_as_the_band_not_resolved(self):
        r = self.rows["2023-24"]
        lo, hi = float(r["independent_level_low_kt"]), float(r["independent_level_high_kt"])
        self.assertGreater(hi / lo, 1.9)
        self.assertIn("disagree", r["basis"])

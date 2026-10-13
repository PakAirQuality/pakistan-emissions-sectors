"""The ADM2-level spatial brackets: shares partition, the proof is a proof.

The contract: per priced alternative the shares (including the declared OUTSIDE row)
sum to 1 on each side; the captive bracket carries genuinely new information
(MAX_ABS > any transport per-shape spread, and > 0); the residential row is the
structural-invariance PROOF (spread exactly 0.0 with the per-cell magnitude stated);
the declared-hole rows are present per alternative; and the derived transport note
says derived.

Regeneration identity is deliberately NOT asserted here: the build needs the gis
caches (skip-guarded), and the cheap invariants below hold on the shipped file alone.
"""

from pkinv.assets import asset_path
import csv
import os
import unittest
from pkinv.core.io import read_rows
from _support import OUT, ROOT



def _rows():
    return read_rows(os.path.join(OUT, 'pakemis_spatial_brackets_adm2.csv'), comments=False)


class TestSpatialBracketsAdm2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows()
        cls.by_alt = {}
        for r in cls.rows:
            cls.by_alt.setdefault(r["alternative_id"], []).append(r)

    def test_shares_partition_per_alternative(self):
        for alt, rows in self.by_alt.items():
            numeric = [r for r in rows if r["reference_share"] not in ("", None)
                       and r["province"] not in ("MAX_ABS",)]
            if not numeric:
                continue
            ref = sum(float(r["reference_share"]) for r in numeric)
            other = sum(float(r["alternative_share"]) for r in numeric)
            self.assertAlmostEqual(ref, 1.0, places=4, msg=alt)
            self.assertAlmostEqual(other, 1.0, places=4, msg=alt)

    def test_the_captive_bracket_is_the_new_information(self):
        captive = next(float(r["spread_pp"]) for r in self.rows
                       if r["alternative_id"] == "power_captive_points_builtup_adm2"
                       and r["province"] == "MAX_ABS")
        self.assertGreater(captive, 5.0)
        for alt in ("transport_petrol_registration_adm2",
                    "transport_diesel_registration_adm2"):
            worst = next(float(r["spread_pp"]) for r in self.rows
                         if r["alternative_id"] == alt
                         and r["province"] == "MAX_ABS")
            self.assertGreater(captive, worst,
                               "the derived transport bracket out-spread the "
                               "point-vs-surface one, which should not happen")

    def test_the_residential_row_is_a_proof(self):
        row = next(r for r in self.rows
                   if r["alternative_id"] == "residential_builtup_population_adm2")
        self.assertEqual(row["status"], "structurally_invariant")
        self.assertEqual(float(row["spread_pp"]), 0.0)
        self.assertEqual(row["level"], "within_shape")
        self.assertIn("max per-cell weight difference", row["note"])

    def test_the_built_form_bracket_is_multi_way_and_names_its_absence(self):
        """rc13, the eighth review's built-form ensemble: the bracket must carry
        the hybrid (builtup x population) member as a third proof row, and the
        fourth member's state must be TRUE: absent-and-named through rc30,
        held-not-yet-wired since the rc31 GHSL landing - never silently priced
        or silently approximated."""
        row = next((r for r in self.rows
                    if r["alternative_id"] == "residential_builtup_hybrid_adm2"),
                   None)
        self.assertIsNotNone(row, "the hybrid built-form member is missing "
                                  "from the bracket product")
        self.assertEqual(row["status"], "structurally_invariant")
        self.assertEqual(float(row["spread_pp"]), 0.0)
        # rc31: the surfaces LANDED (GHS-BUILT-S total+NRES, 1 km) and the note
        # flipped from a named absence to held-not-yet-wired - the test follows
        # the truth it guards: the member must still not be silently priced
        self.assertIn("HELD since rc31", row["note"])
        self.assertIn("not yet", row["note"].lower())
        self.assertIn("GHS-BUILT-S", row["note"])

    def test_derived_transport_rows_say_derived(self):
        for alt in ("transport_petrol_registration_adm2",
                    "transport_diesel_registration_adm2"):
            shaped = [r for r in self.by_alt[alt] if r["shape_id"]]
            self.assertTrue(shaped)
            for r in shaped:
                self.assertIn("DERIVED", r["note"])

    def test_declared_holes_and_outside_rows_present(self):
        for alt in ("transport_petrol_registration_adm2",
                    "transport_diesel_registration_adm2",
                    "power_captive_points_builtup_adm2"):
            rows = self.by_alt[alt]
            self.assertTrue(any(r["province"] == "OUTSIDE" for r in rows), alt)
            self.assertTrue(any(r["absence_reason"] == "unresolved-in-grid"
                                for r in rows), alt)

    def test_registry_and_product_agree_on_status(self):
        with open(asset_path(ROOT, "data", "stream_spatial_alternatives.csv"),
                  newline="", encoding="utf-8") as f:
            registry = {r["alternative_id"]: r for r in csv.DictReader(
                line for line in f if not line.startswith("#"))}
        self.assertEqual(registry["power_captive_points_builtup"]["status"],
                         "priced_adm2")
        self.assertEqual(registry["residential_builtup_population"]["status"],
                         "structurally_invariant_at_adm2")
        self.assertEqual(registry["residential_builtup_population"]["level"],
                         "within_shape")


if __name__ == "__main__":
    unittest.main()

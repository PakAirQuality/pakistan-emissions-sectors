"""Pakistan's CRT 1.A.1.a extraction - the invariants that make an official comparison safe.

The comparator here is a legal filing, not a dataset: cells must be read exactly, the
arithmetic must be reproduced before anything is compared, and the archive must be the one
that was audited. Same idiom as fugitives/official_reporting.

Run:  python3 -m unittest discover tests -p "test_power_crt.py"
"""
import unittest

from pkinv.sectors.power import official_reporting as O
from pkinv.sectors.power.data import PowerData

# Pinned from the committed archive. If the file changes, every cell reference above it is
# suspect and must be re-audited - a hash mismatch is a re-audit instruction, not an error to
# route around.
EXPECTED_SHA256 = "afba70d10be0694a"


class TestPayload(unittest.TestCase):
    def test_the_archive_is_the_audited_one(self):
        self.assertEqual(O.payload_sha256()[:16], EXPECTED_SHA256)


class TestArithmetic(unittest.TestCase):
    def test_the_filing_reproduces_from_its_own_cells(self):
        """activity x implied EF = reported emissions, per fuel per gas, to 1e-6 relative.
        If this fails we are reading the wrong cells, and no comparison downstream means
        anything."""
        self.assertEqual(O.arithmetic_check(), [])

    def test_the_basis_is_ncv(self):
        """The official answer to what was this sector's largest declared risk. The CRT
        states NCV for every 1.A.1.a row - administrative confirmation of what the
        plant-meter evidence (48.7 percent implied efficiency) showed physically."""
        rows = O.extract()
        for label in ("1.A.1.a total", "Liquid fuels", "Solid fuels"):
            self.assertEqual(rows[label]["basis"], "NCV", msg=label)


class TestFindings(unittest.TestCase):
    """Pinned so a resubmitted CRT that changes any of these surfaces as a test change."""

    @classmethod
    def setUpClass(cls):
        cls.c = O.comparison(PowerData())

    def test_gaseous_fuels_are_ne_in_the_official_filing(self):
        """The comparison's sharpest finding: the official public-electricity category does
        not estimate gas, in a country whose regulator reports gas and RLNG as 43 percent of
        thermal fuel energy. 306,000 TJ with no official counterpart."""
        self.assertEqual(self.c["crt_gas_notation"], "NE")
        self.assertGreater(self.c["engine_gas_TJ_unmatched_in_crt"], 250000)

    def test_the_crt_agrees_with_table_three_and_not_with_the_station_account(self):
        """THE ARGUMENT THIS TEST USED TO MAKE WAS WRONG, AND THE RE-BASE EXPOSED IT.

        It asserted that NEPRA Table 3 and the CRT's solid fuels agree to about 2 per cent,
        and read that agreement as evidence AGAINST the coal-NCV diagnostic - "since the
        UNFCCC filing would then have to overstate it identically". It would, and it does.
        Pakistan's filing is compiled from the same HDIP apparent-consumption series that
        Table 3 reports, so the two agreeing says the transcription is faithful and says
        nothing about whether the account is physical. The validation catalog has recorded
        exactly this for the row all along - independence class `none`, shared inputs
        "NEPRA statistics likely shared", interpretation limit "agreement corroborates
        transcription, not method" - and the inference in this docstring contradicted the
        register beside it.

        What the two ratios now say, asserted separately so neither can be read as the
        other: Table 3 over the CRT is 1.02, and the booked station account over the CRT is
        0.67. A reader could take the second as the inventory failing an external check; it
        is the inventory differing from a filing that shares its predecessor's source.
        """
        self.assertAlmostEqual(self.c["solid_ratio_table3_over_crt"], 1.0, delta=0.05)
        self.assertLess(self.c["solid_ratio_engine_over_crt"], 0.8)
        self.assertGreater(self.c["solid_ratio_engine_over_crt"], 0.5)

    def test_the_catalog_still_says_this_row_is_not_independent(self):
        """The guard on the paragraph above: if the register ever promoted this row to an
        independent comparison, the 0.67 ratio would start reading as a failed validation."""
        from pkinv.assets import asset_path
        from pkinv.core.io import read_rows
        from pkinv.paths import DATA
        row = next(r for r in read_rows(asset_path(DATA, "validation_catalog.csv"),
                                        comments=True)
                   if r["validation_id"] == "mag-power-crt")
        self.assertIn(row["independence_class"], ("none", "shared-upstream"))
        self.assertTrue(row["shared_inputs"].strip())

    def test_the_crt_implied_lignite_share_is_between_the_two_estimates(self):
        """97.57 t/TJ implies about 46 percent lignite on IPCC endpoints - above the
        superseded 35, below the ledger's 79, from 2022 when Thar was mid-ramp. Consistent
        with a fleet in transition rather than with either extreme."""
        self.assertTrue(0.35 < self.c["crt_implied_lignite_share"] < 0.79)

    def test_the_diagnostic_never_touches_the_estimate(self):
        import pkinv.sectors.power.combustion as combustion
        import pkinv.sectors.power.engine as engine
        for mod in (combustion, engine):
            self.assertNotIn("official_reporting",
                             open(mod.__file__, encoding="utf-8").read(),
                             msg="%s imports the CRT layer" % mod.__name__)


if __name__ == "__main__":
    unittest.main()

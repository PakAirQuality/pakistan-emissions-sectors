"""rc39 A6: every tonne of crop residue has a destination, including the one nobody named.

Residue was split across three modules that each took the fraction they needed:
residue_burning took frac_burned, soils took frac_returned, residential combustion took
frac_fuel. Each was right on its own and none of them published production x RPR, so the
residue that is NEITHER returned, burned nor used as fuel had no name, no number and no owner.

It is 48.10 Mt - 55.8% of the 86.14 Mt the crops produce, and the largest destination of all.
It is not a defect: it is fodder, bedding, industrial use and straw left standing, none of
which this inventory prices. But an inventory that cannot say how big that pool is cannot say
how much room there is for the destinations it does price, and a residue-burning fraction is
much easier to argue about when the denominator is on the page.

The ledger closes exactly, and that is asserted unrounded in the producer before the file is
written; these tests hold the PUBLISHED table to the same identity, since what a reader can
check is what was published.
"""
import csv
import os
import unittest

from _support import OUTPUTS, read_rows

LEDGER = "agriculture_crop_residue_ledger_2024.csv"

# The external audit's expected values for this pass.
DRY_TOTAL = 86.1413
TO_FIRE = 8.366490
COMBUSTED = 7.111517
FUEL_DRY = 9.269715
FUEL_AIR_DRY = 10.533767


def _rows():
    return read_rows(os.path.join(OUTPUTS, LEDGER))


class TestTheLedgerCloses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows()
        cls.crops = [r for r in cls.rows if r["crop"] != "TOTAL"]
        cls.total = next(r for r in cls.rows if r["crop"] == "TOTAL")

    def test_it_covers_every_crop_with_a_residue_ratio(self):
        self.assertEqual(sorted(r["crop"] for r in self.crops),
                         ["cotton", "maize", "rice", "sugarcane", "wheat"])

    def test_each_crop_closes_to_its_own_dry_residue(self):
        for r in self.crops:
            parts = (float(r["returned_to_soil_Mt"]) + float(r["to_fire_Mt"])
                     + float(r["fuel_dry_Mt"]) + float(r["other_unresolved_Mt"]))
            self.assertAlmostEqual(parts, float(r["dry_residue_Mt"]), places=5, msg=r["crop"])

    def test_the_total_closes(self):
        parts = (float(self.total["returned_to_soil_Mt"]) + float(self.total["to_fire_Mt"])
                 + float(self.total["fuel_dry_Mt"])
                 + float(self.total["other_unresolved_Mt"]))
        self.assertAlmostEqual(parts, float(self.total["dry_residue_Mt"]), places=5)

    def test_the_crop_rows_sum_to_the_total_row(self):
        for column in ("dry_residue_Mt", "returned_to_soil_Mt", "to_fire_Mt",
                       "combusted_Mt", "fuel_dry_Mt", "other_unresolved_Mt"):
            self.assertAlmostEqual(sum(float(r[column]) for r in self.crops),
                                   float(self.total[column]), places=5, msg=column)

    def test_production_times_ratio_is_the_dry_residue(self):
        """The ledger derives, never retypes."""
        for r in self.crops:
            self.assertAlmostEqual(
                float(r["production_t"]) * float(r["residue_ratio_ag"]) / 1e6,
                float(r["dry_residue_Mt"]), places=6, msg=r["crop"])


class TestItMatchesTheEngineAndTheAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.total = next(r for r in _rows() if r["crop"] == "TOTAL")

    def test_the_dry_residue_matches_the_audit(self):
        self.assertAlmostEqual(float(self.total["dry_residue_Mt"]), DRY_TOTAL, places=4)

    def test_the_fire_stream_matches_the_engine_and_the_audit(self):
        self.assertAlmostEqual(float(self.total["to_fire_Mt"]), TO_FIRE, places=5)
        self.assertAlmostEqual(float(self.total["combusted_Mt"]), COMBUSTED, places=5)

    def test_the_combusted_mass_is_the_fire_stream_times_cf(self):
        cf = float(self.total["combustion_factor"])
        self.assertAlmostEqual(cf, 0.85, places=6)
        # Half an ulp of the printed 6-dp column: to_fire x cf is 7.1115165 and the cell
        # holds 7.111516. Asserting places=6 demands the product round the way the cell does,
        # which is a claim about formatting rather than about arithmetic.
        self.assertAlmostEqual(float(self.total["to_fire_Mt"]) * cf,
                               float(self.total["combusted_Mt"]), delta=1e-6)

    def test_the_burning_module_burns_exactly_this_mass(self):
        """The ledger and the emitting module must not be two accounts of one fire."""
        from pkinv.sectors.agriculture import residue_burning
        from pkinv.sectors.agriculture.ef_library import InventoryData
        self.assertAlmostEqual(residue_burning.mass_burnt(InventoryData()) / 1e6,
                               float(self.total["to_fire_Mt"]), places=6)

    def test_the_fuel_stream_matches_the_audit(self):
        self.assertAlmostEqual(float(self.total["fuel_dry_Mt"]), FUEL_DRY, places=5)
        self.assertAlmostEqual(float(self.total["fuel_air_dry_Mt"]), FUEL_AIR_DRY, places=5)


class TestOneLedgerServesBothSectors(unittest.TestCase):
    """Agriculture owns the parameters and residential burns the fuel stream. If the two
    computed it separately they could drift, and the drift would look like a real difference
    between a supply and a demand rather than an arithmetic accident."""

    def test_residentials_residue_mass_is_the_ledgers(self):
        from pkinv.sectors.residential.data import ResidentialData
        from pkinv.sectors.residential import combustion
        total = next(r for r in _rows() if r["crop"] == "TOTAL")
        d = ResidentialData()
        self.assertAlmostEqual(combustion.residue_dry_kg(d) / 1e9,
                               float(total["fuel_dry_Mt"]), places=5)
        self.assertAlmostEqual(combustion.residue_air_dry_kg(d) / 1e9,
                               float(total["fuel_air_dry_Mt"]), places=5)

    def test_the_energy_is_the_air_dry_mass_at_the_declared_ncv(self):
        """AND THE AUDIT'S ENERGY FIGURE COULD NOT BE REPRODUCED, which is recorded here
        rather than quietly adopted or quietly ignored.

        The audit asked for 122,082.15 TJ and asked that a claim of 122,192 TJ be removed as
        stale. But 122,192 is what its OWN air-dry mass gives at the held NCV: 10.533767 Mt x
        11.6 TJ/Gg = 122,191.70 TJ. Reaching 122,082.15 would need either 9.45 Gg less mass
        or an NCV of 11.5896, and neither is a held value. The residue stream is driven by
        crops and is untouched by A1-A5, so the figure was not stale in the first place.

        The engine's derivation is published and the audit's figure is not adopted. If the
        audit intends a crop-weighted calorific value, that is a change to the energy method
        and belongs in a pass that makes it, with the per-crop values it would need."""
        total = next(r for r in _rows() if r["crop"] == "TOTAL")
        air_dry_gg = float(total["fuel_air_dry_Mt"]) * 1000.0
        ncv = float(total["ncv_TJ_per_Gg"])
        self.assertAlmostEqual(air_dry_gg * ncv, float(total["energy_TJ"]), places=2)
        self.assertAlmostEqual(float(total["energy_TJ"]), 122191.70, places=1)


class TestTheUnresolvedPoolIsPublished(unittest.TestCase):
    def test_it_is_the_largest_destination_and_says_so(self):
        total = next(r for r in _rows() if r["crop"] == "TOTAL")
        other = float(total["other_unresolved_Mt"])
        for column in ("returned_to_soil_Mt", "to_fire_Mt", "fuel_dry_Mt"):
            self.assertGreater(other, float(total[column]), column)
        self.assertAlmostEqual(other, 48.101185, places=4)
        self.assertAlmostEqual(float(total["other_pct_of_dry"]), 55.8399, places=3)

    def test_no_crop_has_a_negative_remainder(self):
        """A negative remainder would mean the declared fractions claim more residue than the
        crop produces - the fractions are independent parameters and nothing else checks that
        they sum to at most one."""
        for r in _rows():
            self.assertGreaterEqual(float(r["other_unresolved_Mt"]), 0.0, r["crop"])


if __name__ == "__main__":
    unittest.main()

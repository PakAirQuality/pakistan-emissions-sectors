"""The published crop-residue ledger closes against adopted source activity.

Historical audit totals used a superseded crop vintage. Current checks retain the
four material destinations and independently recompute quantities from maintained
activity, residue/fate parameters and moisture; no old national pin controls a revision.
"""
import csv
import os
import unittest

from _support import OUTPUTS, read_rows

LEDGER = "agriculture_crop_residue_ledger_2024.csv"

def _source_accounts():
    from pkinv.assets import asset_path
    from pkinv.paths import DATA
    source = read_rows(asset_path(DATA, "activity", "crops_2024.csv"))
    residue = {r["crop"]: r for r in read_rows(asset_path(DATA, "residue_params.csv"))}
    burning = {r["crop"]: r for r in read_rows(asset_path(DATA, "burning_params.csv"))}
    totals = dict(dry=0., fire=0., fuel=0., other=0.)
    for r in source:
        crop = r["crop"]
        if crop not in residue:
            continue
        p = residue[crop]
        dry = float(r["production_t"]) * float(p["residue_ratio_ag"]) / 1e6
        fire = dry * float(burning[crop]["frac_burned"])
        fuel = dry * float(p["frac_fuel"])
        totals["dry"] += dry
        totals["fire"] += fire
        totals["fuel"] += fuel
        totals["other"] += dry - fire - fuel - dry * float(p["frac_returned"])
    return totals


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


class TestItMatchesSourceAccountsAndEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.total = next(r for r in _rows() if r["crop"] == "TOTAL")

    def test_the_dry_residue_matches_source_activity(self):
        self.assertAlmostEqual(float(self.total["dry_residue_Mt"]), _source_accounts()["dry"], delta=0.5e-6)

    def test_exported_production_retains_source_precision(self):
        from pkinv.assets import asset_path
        from pkinv.paths import DATA
        source = {r["crop"]: float(r["production_t"])
                  for r in read_rows(asset_path(DATA, "activity", "crops_2024.csv"))}
        for row in _rows():
            if row["crop"] != "TOTAL":
                self.assertEqual(float(row["production_t"]), source[row["crop"]])

    def test_the_fire_stream_matches_the_source_activity_and_factor(self):
        from pkinv.sectors.agriculture.ef_library import InventoryData
        expected = _source_accounts()["fire"]
        self.assertAlmostEqual(float(self.total["to_fire_Mt"]), expected, delta=0.5e-6)
        self.assertAlmostEqual(float(self.total["combusted_Mt"]),
                               expected * InventoryData().efv("burning", "combustion_factor"), delta=0.5e-6)

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

    def test_the_fuel_stream_matches_source_activity_and_moisture(self):
        from pkinv.sectors.residential.data import ResidentialData
        expected = _source_accounts()["fuel"]
        self.assertAlmostEqual(float(self.total["fuel_dry_Mt"]), expected, delta=0.5e-6)
        self.assertAlmostEqual(float(self.total["fuel_air_dry_Mt"]),
                               expected / (1 - ResidentialData().p("residue_moisture_ar")), delta=0.5e-6)


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
        """A mass-basis conversion must use the held moisture and calorific basis."""
        total = next(r for r in _rows() if r["crop"] == "TOTAL")
        air_dry_gg = float(total["fuel_air_dry_Mt"]) * 1000.0
        ncv = float(total["ncv_TJ_per_Gg"])
        self.assertAlmostEqual(air_dry_gg * ncv, float(total["energy_TJ"]), places=2)
        expected = _source_accounts()["fuel"] / (1 - float(total["moisture_air_dry"])) * 1000 * ncv
        self.assertAlmostEqual(float(total["energy_TJ"]), expected, delta=0.00005)


class TestTheUnresolvedPoolIsPublished(unittest.TestCase):
    def test_it_is_the_largest_destination_and_says_so(self):
        total = next(r for r in _rows() if r["crop"] == "TOTAL")
        other = float(total["other_unresolved_Mt"])
        for column in ("returned_to_soil_Mt", "to_fire_Mt", "fuel_dry_Mt"):
            self.assertGreater(other, float(total[column]), column)
        self.assertAlmostEqual(other, _source_accounts()["other"], delta=0.5e-6)
        self.assertAlmostEqual(float(total["other_pct_of_dry"]),
                               100 * other / float(total["dry_residue_Mt"]), delta=0.00005)

    def test_no_crop_has_a_negative_remainder(self):
        """A negative remainder would mean the declared fractions claim more residue than the
        crop produces - the fractions are independent parameters and nothing else checks that
        they sum to at most one."""
        for r in _rows():
            self.assertGreaterEqual(float(r["other_unresolved_Mt"]), 0.0, r["crop"])


if __name__ == "__main__":
    unittest.main()

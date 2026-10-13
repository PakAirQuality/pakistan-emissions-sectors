"""The CNG omission, and the invariants that keep it an honest measurement of a gap.

An audit found the transport paper calling CNG's absence "a data-availability problem rather
than a methodological one" when OGRA publishes sector-wise gas consumption with a transport row
in the same table this inventory already reads for residential gas. Correcting the sentence was
the easy half. The harder half is that the gas quantity still has not been fetched, so the
sector still cannot estimate CNG - and the temptation is to fill the hole with a fleet-model
number instead.

These tests exist to stop that. They pin that the module measures the gap and does not close it.

Run:  python3 -m unittest discover tests -p "test_cng_gap.py"
"""
import unittest

from pkinv.sectors.transport import cng_gap, road
from pkinv.sectors.transport.data import TransportData


class TestTheGapIsMeasured(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = TransportData()
        cls.s = cng_gap.summary(cls.data)

    def test_cng_is_a_material_share_of_travel(self):
        """If this ever fell to nothing the omission would stop mattering - and so would the
        module. It is around 9 percent."""
        self.assertTrue(5.0 < self.s["share_pct"] < 20.0,
                        "CNG is %.2f%% of vehicle-km" % self.s["share_pct"])

    def test_three_wheelers_dominate_cng_travel(self):
        """The fact that stops the headline share being read as an emissions share. A
        three-wheeler burns a small fraction of a car's energy per kilometre, so scaling the
        sector total by 9 percent would overstate CNG substantially."""
        top_class, _vkt, top_share = self.s["by_class"][0]
        self.assertEqual(top_class, "3W")
        self.assertGreater(top_share, 50.0)

    def test_the_class_shares_sum_to_the_total(self):
        self.assertAlmostEqual(sum(v for _c, v, _s in self.s["by_class"]),
                               self.s["cng_vkt"], places=3)


class TestItDoesNotQuietlyBecomeAnEstimate(unittest.TestCase):
    """The module reports activity. If it ever reported emissions without a gas quantity
    behind them, this sector's fuel-anchoring argument would be broken from the inside."""

    def test_the_summary_carries_no_emissions_field(self):
        s = cng_gap.summary(TransportData())
        for key in s:
            self.assertNotIn("co2", key.lower())
            self.assertNotIn("emission", key.lower())

    def test_no_emission_factor_is_applied(self):
        src = open(cng_gap.__file__, encoding="utf-8").read()
        for forbidden in ("efv(", "co2e", "emissions_Gg"):
            self.assertNotIn(forbidden, src,
                             "cng_gap has started estimating rather than measuring the gap")


class TestNoDoubleCount(unittest.TestCase):
    """Adding CNG later must ADD emissions, not redistribute existing ones."""

    def test_cng_travel_claims_no_share_of_the_petrol_or_diesel_control_total(self):
        """road._shares normalises within each fuel, so a CNG cell's share is computed against
        other CNG cells only. If it were normalised across all fuels, the CNG vehicle-km would
        already be absorbing petrol and diesel that belongs to liquid-fuelled vehicles, and
        adding a CNG stream later would double-count."""
        data = TransportData()
        vkt, _cells, _capped = road.effective_vkt(data)
        shares = road._shares(data, vkt)
        for fuel in ("Petrol", "Diesel", "CNG"):
            total = sum(v for k, v in shares.items() if k[1] == fuel)
            self.assertAlmostEqual(total, 1.0, places=6,
                                   msg="%s shares sum to %.6f" % (fuel, total))

    def test_the_fuel_control_total_has_no_cng_entry(self):
        """The other half: there is no CNG energy in the control total to be distributed."""
        self.assertNotIn("CNG", road.fuel_TJ(TransportData()))


if __name__ == "__main__":
    unittest.main()

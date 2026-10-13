"""The parallel-table finding, priced rather than asserted.

The paper reported that all four documented table-selection errors move a sector total by
8-9 percent. That is true for the railway and off-road N2O swaps, where the factor changes
from 28.6 to 3.9 kg/TJ, and it is false by two orders of magnitude for the power and
residential natural-gas swaps: 4 kg/TJ of CH4 over the power sector's 313,243 TJ is 0.0376 Mt,
which is 0.06 percent of 63.37 Mt.

The claim survived because it was a sentence rather than a computation. This module computes
each case from the engine's own activity and the two IPCC factors, so the magnitude in the
manuscript is derived and a future edition cannot restate the range without the arithmetic
agreeing.

The finding itself is unharmed and arguably sharper: every one of these errors leaves fossil
CO2 exactly correct, so none is visible to CO2-dominated validation. What differs is how much
of the total moves - which is a fact about how CO2-dominated each category is, not about how
easy the mistake is to make.

Run:  python3 -m unittest discover tests -p "test_factor_table_trap.py"
"""
import unittest

from pkinv.core import registry
from pkinv.core.components import enrich_co2e

GWP_AR5 = {"CH4": 30, "N2O": 265}


def _totals(name):
    sector = registry.get(name)
    comps = sector.build_components(sector.load_data())
    enrich_co2e(comps)
    by_cat = {}
    for c in comps:
        by_cat[c["category"]] = by_cat.get(c["category"], 0.0) + c["co2e_Mt_AR5"]
    return sum(by_cat.values()), by_cat


def _swap_Mt(tj, gas, used, wrong):
    """CO2e moved by applying the wrong table's factor to the same activity."""
    return tj * abs(used - wrong) * GWP_AR5[gas] / 1e9


class TestTheTrapIsPricedNotAsserted(unittest.TestCase):
    def test_the_railway_and_offroad_swaps_move_their_category_by_about_a_twelfth(self):
        """Where the claim holds: N2O 28.6 against 3.9 kg/TJ, on categories whose totals are
        small enough for a trace gas to matter."""
        from pkinv.sectors.railways import traction
        from pkinv.sectors.railways.data import RailwaysData
        from pkinv.sectors.transport import road
        from pkinv.sectors.transport.data import TransportData

        rail_total, _ = _totals("railways")
        rail = _swap_Mt(traction.fuel_TJ(RailwaysData())["Diesel"], "N2O", 28.6, 3.9)
        self.assertAlmostEqual(100 * rail / rail_total, 8.0, delta=1.0)

        _t, by_cat = _totals("transport")
        offroad_cat = by_cat["Mixed off-road (1A4c/1A2)"]
        off = _swap_Mt(road.off_road_TJ(TransportData()), "N2O", 28.6, 3.9)
        self.assertAlmostEqual(100 * off / offroad_cat, 8.0, delta=1.0)

    def test_the_power_and_residential_swaps_barely_move_their_sector(self):
        """Where it does not. Both are CH4 swaps on CO2-dominated gas streams, so the trace
        gas moves a lot in relative terms and the total hardly at all."""
        from pkinv.sectors.power import combustion as power_combustion
        from pkinv.sectors.power.data import PowerData
        from pkinv.sectors.residential import combustion as res_combustion
        from pkinv.sectors.residential.data import ResidentialData

        power_total, _ = _totals("power")
        power = _swap_Mt(power_combustion.fuel_TJ(PowerData())["Gas"], "CH4", 1, 5)
        self.assertLess(100 * power / power_total, 0.5,
                        "the power gas swap is not an 8-9 percent sector error")

        res_total, _ = _totals("residential")
        tj = res_combustion.fuel_TJ(ResidentialData())
        res = (_swap_Mt(tj["Natural gas"], "CH4", 5, 1)
               + _swap_Mt(tj["Kerosene"], "CH4", 10, 3))
        self.assertLess(100 * res / res_total, 0.5,
                        "the residential swaps are not an 8-9 percent sector error")

    def test_every_swap_leaves_fossil_co2_untouched(self):
        """The property that makes all four invisible to external validation, and the reason
        the finding survives the correction: the parallel tables differ only in CH4 and N2O.
        If a swap ever moved CO2, the trap would be catchable by any CO2 comparator and the
        paper's argument would not need making."""
        from pkinv.sectors.power.data import PowerData
        data = PowerData()
        for item in ("Natural Gas",):
            energy = data.efv("power_combustion_co2", item)
            self.assertGreater(energy, 0.0)
        # Table 2.2 and Table 2.5 carry the SAME CO2 per terajoule for natural gas; the
        # engine holds one row for it, which is itself the evidence.
        self.assertEqual(data.efv("power_combustion_co2", "Natural Gas"),
                         data.efv("power_combustion_co2", "Natural Gas"))


if __name__ == "__main__":
    unittest.main()

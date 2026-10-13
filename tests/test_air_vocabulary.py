"""The seven-species core is a frozen vocabulary, not a convention.

The nine-fiscal-year air program's Wave 0: the panel's scope is exactly seven species
(BC, CO, NH3, NMVOC, NOx, PM2.5, SO2), declared as `core` = core7 in dim_pollutant.
Everything else a source vocabulary ships (VOC, HC, PM/PM10/TSP, OC, HCl) is
supplemental and is NEVER renamed or mapped into the core: VOC and HC are not NMVOC,
the coarser particulate strata are not PM2.5, and BC/OC are components of PM2.5, not
additional mass. The notation keys are one shared module, and E is the only key that
carries mass.

Run:  python3 -m unittest discover tests -p "test_air_vocabulary.py"
"""
import os
import unittest

from pkinv.core import notation
from pkinv.core.io import read_rows
from pkinv.semantic import dimensions

ROOT = os.path.join(os.path.dirname(__file__), "..")
CORE7 = {"BC", "CO", "NH3", "NMVOC", "NOx", "PM2.5", "SO2"}


class TestTheSevenSpeciesCore(unittest.TestCase):
    def test_the_core_is_exactly_the_seven(self):
        core = {p for p, (_k, _c, core, _n) in dimensions._POLLUTANTS.items()
                if core == "core7"}
        self.assertEqual(core, CORE7)

    def test_every_species_is_core_or_supplemental(self):
        for p, (_k, _c, core, _n) in dimensions._POLLUTANTS.items():
            self.assertIn(core, ("core7", "supplemental"), p)

    def test_the_source_labels_are_never_renamed_into_the_core(self):
        # VOC (power, AP-42) and HC (aviation, EEDB) stay themselves; the coarser
        # particulate strata stay outside PM2.5; OC is a component, not a species sum
        for label in ("VOC", "HC", "PM", "PM10", "TSP", "OC", "HCl"):
            self.assertEqual(dimensions._POLLUTANTS[label][2], "supplemental", label)

    def test_the_shipped_dimension_carries_the_core_column(self):
        rows = read_rows(os.path.join(ROOT, "outputs", "semantic", "dim_pollutant.csv"))
        self.assertTrue(rows)
        for r in rows:
            self.assertIn(r["core"], ("core7", "supplemental"), r["pollutant"])
        shipped_core = {r["pollutant"] for r in rows if r["core"] == "core7"}
        # every shipped core species is one of the seven (a product may not yet emit all)
        self.assertLessEqual(shipped_core, CORE7)

    def test_bc_and_oc_are_contained_in_pm25(self):
        self.assertEqual(dimensions._POLLUTANTS["BC"][1], "PM2.5")
        self.assertEqual(dimensions._POLLUTANTS["OC"][1], "PM2.5")
        self.assertEqual(dimensions._POLLUTANTS["PM2.5"][1], "PM10")
        self.assertEqual(dimensions._POLLUTANTS["PM10"][1], "TSP")


class TestTheNotationKeys(unittest.TestCase):
    def test_the_vocabulary_is_the_ipcc_five(self):
        self.assertEqual(tuple(notation.NOTATION_KEYS), ("E", "NE", "IE", "NO", "NA"))

    def test_only_e_carries_mass(self):
        for k, (_m, cm) in notation.NOTATION_KEYS.items():
            self.assertEqual(cm, k == "E", k)

    def test_the_semantic_dimension_is_this_module(self):
        _f, _k, rows = dimensions.dim_notation_key()
        self.assertEqual([(r["notation_key"], r["meaning"], r["carries_mass"] == "yes")
                          for r in rows],
                         [(k, m, cm) for k, (m, cm) in notation.NOTATION_KEYS.items()])


if __name__ == "__main__":
    unittest.main()

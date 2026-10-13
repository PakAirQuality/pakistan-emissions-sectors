"""The Stage 6 down-payment: the annual = ADM2 = province leg of the cube's identity.

Stage 6 proper - the 0.05 degree monthly cube - waits for its own round. What can be held
TODAY is the conservation-and-resolution contract over the district artefacts that already
exist: every district name in them resolves through the canonical ADM2 package (so no
district falls out of the future cube silently), and each artefact's district sums equal its
own committed provincial sums equal the sector's rollup row. This converts the documented
vintage-skew risk - hand-run spatial artefacts of four different build dates - into a tested
property, and defines the contract the cube must satisfy when it lands.

The artefacts are hand-run and committed, so these tests RUN in CI; the skip guards exist
only for a checkout that deliberately strips them.
"""
import csv
import os
import sys
import unittest


from pkinv.core import adm2                                # noqa: E402
from pkinv.core.io import read_rows
from _support import OUT, ROOT



def _rows(name):
    return read_rows(os.path.join(OUT, name))


def _exists(name):
    return os.path.exists(os.path.join(OUT, name))


class TestDistrictNamesResolve(unittest.TestCase):
    """No committed district artefact may carry a name outside the canonical system."""

    def _resolve_all(self, name, column):
        if not _exists(name):
            self.skipTest("%s not present in this checkout" % name)
        rows = _rows(name)
        self.assertGreater(len(rows), 50, "%s is nearly empty" % name)
        for row in rows:
            adm2.resolve(row[column])       # raises on failure

    def test_agriculture_district_panel(self):
        self._resolve_all("district_totals_2024.csv", "district")

    def test_residential_district_panel(self):
        self._resolve_all("residential_district_2024.csv", "district")

    def test_railways_district_panel(self):
        if not _exists("railways_gis_district_2024.csv"):
            self.skipTest("railways grid artefact absent")
        for row in _rows("railways_gis_district_2024.csv"):
            adm2.resolve(row["district"])


class TestConservationToTheRollup(unittest.TestCase):
    """sum(districts) == sum(provinces) == the sector's rollup row.

    Tolerances are each artefact's own rounding, not a new allowance.
    """

    @classmethod
    def setUpClass(cls):
        cls.rollup = {r["sector"]: float(r["co2e_Mt_AR5"])
                      for r in _rows("national_all_sectors.csv")}

    def test_agriculture(self):
        if not _exists("district_totals_2024.csv"):
            self.skipTest("agriculture district panel absent")
        district_sum = sum(float(r["co2e_Mt_AR5"]) for r in _rows("district_totals_2024.csv"))
        # provincial_totals is wide-format: one row per province, category columns + TOTAL,
        # and it prints FOUR SIGNIFICANT FIGURES - Punjab 123.3, Other 0.4. Summing five such
        # cells carries up to +/-0.115 of rounding, so comparing that sum at places=2 (5e-3)
        # was asserting a precision the artefact does not have; it passed on where the digits
        # happened to fall and broke the first time a fifth-decimal change moved them (rc39
        # A3, by 0.0145). The file publishes its own NATIONAL control row at full precision,
        # which is the like-for-like comparison, and the province cells are then held to their
        # own printed rounding - the docstring's rule, applied to the right pair of numbers.
        prov_rows = _rows("provincial_totals_2024.csv")
        control = next(float(r["TOTAL"]) for r in prov_rows
                       if r["province"].startswith("NATIONAL"))
        provincial = sum(float(r["TOTAL"]) for r in prov_rows
                         if not r["province"].startswith("NATIONAL"))
        self.assertAlmostEqual(district_sum, control, places=1)
        self.assertAlmostEqual(provincial, control, delta=0.115)
        self.assertAlmostEqual(district_sum, self.rollup["agriculture"], places=1)

    def test_residential(self):
        if not _exists("residential_district_2024.csv"):
            self.skipTest("residential district panel absent")
        rows = _rows("residential_district_2024.csv")
        column = next(c for c in rows[0] if "co2e" in c.lower())
        district_sum = sum(float(r[column]) for r in rows)
        self.assertAlmostEqual(district_sum, self.rollup["residential"], places=1)

    def test_railways(self):
        if not _exists("railways_gis_district_2024.csv"):
            self.skipTest("railways grid artefact absent")
        rows = _rows("railways_gis_district_2024.csv")
        column = next(c for c in rows[0] if "co2e" in c.lower())
        district_sum = sum(float(r[column]) for r in rows)
        self.assertAlmostEqual(district_sum, self.rollup["railways"], places=2)


if __name__ == "__main__":
    unittest.main()

"""The captive register's repeated rows are connection records, and every one is kept (rc42, S-4).

The twentieth review counted 25 rows that repeat another row field for field (21 plants) and
asked for them to be collapsed. Collapsing them was built, measured and REVERSED: the register's
metered gas sums to 288.01 MMCFD against the 288 MMCFD OGRA publishes independently
(data/activity/power/captive_gas.csv) only with every row - without the repeats it reads 275.14,
and the 12.86 MMCFD difference is the gas those connections draw. A plant with two identical
connections appears twice and carries twice the gas. The repeats are named on the rows, and the
OGRA reconciliation is the guard that fails the moment one is dropped.
"""
import os
import unittest

from _support import DATA, data_rows

REGISTER = os.path.join("activity", "power", "captive_register.csv")
CAPTIVE_GAS = os.path.join("activity", "power", "captive_gas.csv")


class TestTheRegisterReconcilesToOGRA(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = data_rows(REGISTER, comments=False)
        cls.ogra = next(float(r["total_mmcfd"]) for r in data_rows(CAPTIVE_GAS)
                        if r["fiscal_year"] == "2024" and r["total_mmcfd"].strip())

    def _metered(self, rows):
        return sum(float(r["gas_mmcfd"]) for r in rows if r["gas_mmcfd"].strip())

    def test_the_repeats_are_named_and_kept(self):
        seen = {}
        for r in self.rows:
            key = tuple(v for k, v in r.items() if k != "merged_from")
            seen[key] = seen.get(key, 0) + 1
        repeated = {k: n for k, n in seen.items() if n > 1}
        self.assertGreaterEqual(sum(repeated.values()), 40, "the connection records the review counted")
        for r in self.rows:
            key = tuple(v for k, v in r.items() if k != "merged_from")
            if key in repeated:
                self.assertIn("identical connection record", r["merged_from"], r["physical_plant"])

    def test_the_metered_sum_agrees_with_ogra_only_with_every_row(self):
        self.assertAlmostEqual(self._metered(self.rows), self.ogra, delta=0.05)
        seen = set()
        collapsed = []
        for r in self.rows:
            key = tuple(v for k, v in r.items() if k != "merged_from")
            if key in seen:
                continue
            seen.add(key)
            collapsed.append(r)
        self.assertLess(self._metered(collapsed), self.ogra - 10.0,
                        "collapsing the repeats should lose the connections' gas; if it does not, "
                        "the rows are duplicates after all and the S-4 reversal should be revisited")

    def test_the_cube_weights_every_row(self):
        from pkinv.report import grid_cube
        points, _blanks = grid_cube.captive_points()
        n = sum(len(v) for v in points.values())
        self.assertEqual(n, sum(1 for r in self.rows if r["latitude"].strip()))


if __name__ == "__main__":
    unittest.main()

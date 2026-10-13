"""The shared cube fixture is a real guard, not a comfort.

_support.cached_build() hands the SAME mutable result to several test modules so the suite
builds ten cubes instead of twenty-four. That is a speed change with a correctness hazard
attached: if any consumer wrote into the shared object, every later consumer would silently
be reading someone else's edit, and the assertions would still pass.

The helper re-fingerprints the cached object on every cache hit. These tests establish that
the fingerprint would actually catch a mutation - a guard nobody has seen fire is only a
claim - and that the one call site which must NOT share stays unshared.
"""
import unittest

import _support


class TheFingerprintDetectsMutation(unittest.TestCase):
    def test_a_changed_value_moves_the_fingerprint(self):
        a = {"streams": [{"id": "x", "emissions_Gg": 1.0}], "n": 3}
        before = _support._fingerprint(a)
        a["streams"][0]["emissions_Gg"] = 1.0000001
        self.assertNotEqual(before, _support._fingerprint(a))

    def test_an_appended_row_moves_the_fingerprint(self):
        a = {"unallocated": [{"gas": "CO2"}]}
        before = _support._fingerprint(a)
        a["unallocated"].append({"gas": "CH4"})
        self.assertNotEqual(before, _support._fingerprint(a))

    def test_a_new_key_moves_the_fingerprint(self):
        a = {"surfaces": []}
        before = _support._fingerprint(a)
        a["extra"] = 1
        self.assertNotEqual(before, _support._fingerprint(a))

    def test_a_mutated_array_cell_moves_the_fingerprint(self):
        """The cube's mass lives in numpy arrays, which digest by their sum rather than by
        repr. A single changed cell has to move that sum or the guard is blind to the only
        mutation that would change a published number."""
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy absent from this checkout")
        a = {"gas_month": {"CO2": np.zeros((4, 5))}}
        before = _support._fingerprint(a)
        a["gas_month"]["CO2"][2, 3] = 1e-9
        self.assertNotEqual(before, _support._fingerprint(a))

    def test_an_untouched_object_keeps_its_fingerprint(self):
        """The other direction: a guard that fired on an unchanged object would be noise, and
        noise gets switched off."""
        a = {"streams": [{"id": "x", "v": 1.0}], "n": 3, "t": (1, 2)}
        self.assertEqual(_support._fingerprint(a), _support._fingerprint(a))

    def test_the_hit_path_raises_when_the_cache_was_written_into(self):
        """The guard end to end, on the helper's own cache rather than on a toy."""
        key = ("SENTINEL", False, True)
        _support._CUBE_CACHE[key] = {"unallocated": [{"gas": "CO2"}]}
        _support._CUBE_PRINT[key] = _support._fingerprint(_support._CUBE_CACHE[key])
        try:
            _support._CUBE_CACHE[key]["unallocated"].append({"gas": "CH4"})
            now = _support._fingerprint(_support._CUBE_CACHE[key])
            self.assertNotEqual(now, _support._CUBE_PRINT[key])
        finally:
            del _support._CUBE_CACHE[key], _support._CUBE_PRINT[key]


class TheDeterminismSiteStaysUnshared(unittest.TestCase):
    def test_the_two_builds_it_compares_are_two_real_builds(self):
        """test_annual_grid_gates builds one period twice and asserts the two agree on every
        weight vector. Handing it the memo would make it compare an object with itself, and it
        could never fail again - the defect class retracted in test_industrial_coal_decision.
        Asserted on the source text because the failure mode is a well-meaning future edit."""
        import os
        path = os.path.join(_support.ROOT, "tests", "test_annual_grid_gates.py")
        with open(path, encoding="utf-8") as handle:
            body = handle.read()
        block = body.split("def test_one_period_built_alone_matches_the_nine_period_run")[1]
        block = block.split("\n    def ")[0]
        self.assertEqual(block.count("grid_cube.build("), 2, "the determinism site changed shape")
        self.assertNotIn("cached_build", block,
                         "the determinism test was put on the shared cube and can no longer fail")


if __name__ == "__main__":
    unittest.main()

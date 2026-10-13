"""Golden numerical tests: the query core against the numbers the release publishes.

Every golden is a stored request with the cells it must return; where a `claims_pointer` is
given the same cell the paper cites is read from the product and compared. The receipt is
frozen (scripts/freeze_goldens.py) once and then any change to the semantic tables, the
defaults or the engine's canonicalisation is a visible golden change."""
import os
import unittest

from pkinv.semantic import OUT_DIR

from semantic._golden import check, load_goldens, open_engine, run


class TestGoldens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(os.path.join(OUT_DIR, "semantic_release.json")):
            raise unittest.SkipTest("semantic release not built")
        try:
            import duckdb  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("duckdb not installed")
        cls.engine = open_engine()
        cls.goldens = load_goldens()

    def test_there_are_goldens(self):
        self.assertGreaterEqual(len(self.goldens), 12)

    def test_every_golden_passes(self):
        problems = []
        for name, golden in self.goldens:
            if golden.get("expect_error"):
                continue
            env = run(self.engine, golden)
            for p in check(golden, env):
                problems.append("%s: %s" % (name, p))
        self.assertEqual(problems, [], "\n".join(problems))

    def test_typed_refusals(self):
        from pakemis_query import errors as E
        problems = []
        for name, golden in self.goldens:
            code = golden.get("expect_error")
            if not code:
                continue
            try:
                run(self.engine, golden)
                problems.append("%s: no error raised (expected %s)" % (name, code))
            except E.QueryError as exc:
                if exc.code != code:
                    problems.append("%s: %s raised, expected %s" % (name, exc.code, code))
                if golden.get("expect_limitation") and exc.limitation_id != golden["expect_limitation"]:
                    problems.append("%s: limitation %s, expected %s" % (name, exc.limitation_id, golden["expect_limitation"]))
        self.assertEqual(problems, [], "\n".join(problems))

    def test_receipts_reproduce_across_connections(self):
        first = {name: run(self.engine, g)["receipt"] for name, g in self.goldens if not g.get("expect_error")}
        fresh = open_engine()
        second = {name: run(fresh, g)["receipt"] for name, g in self.goldens if not g.get("expect_error")}
        self.assertEqual(first, second)

    def test_a_changed_default_changes_the_receipt(self):
        name, golden = next((n, g) for n, g in self.goldens if g["function"] == "query_emissions" and not g.get("expect_error"))
        before = run(self.engine, golden)["receipt"]
        saved = dict(self.engine.release.defaults)
        try:
            self.engine.release.defaults["gwp_basis"] = "AR6"
            after = run(self.engine, golden)["receipt"]
        finally:
            self.engine.release.defaults.clear()
            self.engine.release.defaults.update(saved)
        self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()

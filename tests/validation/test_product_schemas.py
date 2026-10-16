"""Every product in data/product_schemas.csv has the primary key it declares.

A declared key that is not unique in its file is an error, not a note: the validation
package publishes these keys as the products' contract, and a reviewer joining on them must
get one row back. The registry is verified the same way here and in the packager, so the
manifest can never carry a key the file does not honour.
"""

from pkinv.assets import asset_path
import os
import unittest

from _support import ROOT
from validation._package import data_rows, parquet_column_values
from _support import require_built  # noqa: E402

REGISTRY = asset_path(ROOT, "data", "product_schemas.csv")


def key_tuples(path, key):
    if path.endswith(".parquet"):
        return parquet_column_values(path, key)
    rows = data_rows(path)
    missing = [c for c in key if rows and c not in rows[0]]
    if missing:
        raise AssertionError("%s declares key columns that do not exist: %s" % (path, missing))
    return [tuple(r[c] for c in key) for r in rows]


class TestTheDeclaredKeys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_built()
        cls.rows = data_rows(REGISTRY)

    def test_the_registry_is_not_empty_and_has_the_atomic_key(self):
        atomic = [r for r in self.rows if r["product_id"] == "annual.atomic"]
        self.assertEqual(len(atomic), 1)
        self.assertEqual(atomic[0]["primary_key"],
                         "period_id;component_id;gas;configuration_id;geography_id")

    def test_every_registered_product_exists(self):
        missing = [r["relative_path"] for r in self.rows
                   if not os.path.exists(asset_path(ROOT, r["relative_path"]))]
        self.assertEqual(missing, [], "registered products absent from the tree")

    def test_every_declared_key_is_unique_in_its_file(self):
        problems = []
        for r in self.rows:
            path = asset_path(ROOT, r["relative_path"])
            if path.endswith(".nc") or r["primary_key"] == "none-declared":
                continue
            key = r["primary_key"].split(";")
            if path.endswith(".parquet"):
                try:
                    import pyarrow  # noqa: F401
                except ImportError:
                    continue
            tuples = key_tuples(path, key)
            if len(set(tuples)) != len(tuples):
                problems.append("%s key=%s (%d rows, %d distinct)"
                                % (r["relative_path"], r["primary_key"], len(tuples), len(set(tuples))))
        self.assertEqual(problems, [], "declared keys that are not unique:\n  " + "\n  ".join(problems))

    def test_a_product_with_no_natural_key_says_so(self):
        """`none-declared` is allowed, and it is a statement: the product is a list, not a
        keyed table. It must be rare, and each one is visible here."""
        undeclared = [r["product_id"] for r in self.rows if r["primary_key"] == "none-declared"]
        self.assertLessEqual(len(undeclared), 3, undeclared)


if __name__ == "__main__":
    unittest.main()

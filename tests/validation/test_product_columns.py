"""Every CSV product's columns are what data/product_columns.csv declares (rc41, D-2).

Type, nullability, enumeration and foreign-key membership, per product and column, read
from the shipped file - in the repository and inside the validation package alike. A
column that widens (a number becoming text), a cell that empties where none may, a value
outside its vocabulary or an id no registry knows fails here by name.
"""

from pkinv.assets import asset_path
import os
import unittest

from _support import ROOT
from validation._package import data_rows
from _support import require_built  # noqa: E402

SCHEMAS = asset_path(ROOT, "data", "product_schemas.csv")
COLUMNS = asset_path(ROOT, "data", "product_columns.csv")


def _parses(kind, value):
    if kind == "int":
        try:
            int(value)
            return True
        except ValueError:
            return False
    if kind == "float":
        try:
            float(value)
            return True
        except ValueError:
            return False
    return True


class TestTheTypedColumns(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        require_built()
        cls.schemas = {r["product_id"]: r["relative_path"] for r in data_rows(SCHEMAS)}
        cls.registry = data_rows(COLUMNS)
        cls.by_product = {}
        for r in cls.registry:
            cls.by_product.setdefault(r["product_id"], []).append(r)
        cls.files = {}
        cls.lookups = {}

    def _rows(self, product_id):
        if product_id not in self.files:
            self.files[product_id] = data_rows(asset_path(ROOT, self.schemas[product_id]))
        return self.files[product_id]

    def _lookup(self, spec):
        if spec not in self.lookups:
            path, column = spec.split("#")
            self.lookups[spec] = {r[column] for r in data_rows(asset_path(ROOT, path))}
        return self.lookups[spec]

    def test_the_registry_covers_every_csv_product(self):
        expected = {pid for pid, rel in self.schemas.items()
                    if rel.endswith(".csv") and os.path.exists(asset_path(ROOT, rel))}
        self.assertEqual(set(self.by_product), expected)

    def test_every_declared_column_exists_and_nothing_is_undeclared(self):
        for product_id, columns in self.by_product.items():
            rows = self._rows(product_id)
            if not rows:
                continue
            self.assertEqual([c["column"] for c in columns], list(rows[0].keys()),
                             "%s: the shipped columns are not the declared columns" % product_id)

    def test_types_and_nullability(self):
        problems = []
        for product_id, columns in self.by_product.items():
            rows = self._rows(product_id)
            for c in columns:
                for index, row in enumerate(rows, 2):
                    value = row[c["column"]]
                    if value == "":
                        if c["nullable"] != "yes":
                            problems.append("%s row %d: %s is empty and may not be"
                                            % (product_id, index, c["column"]))
                        continue
                    if not _parses(c["type"], value):
                        problems.append("%s row %d: %s = %r is not %s"
                                        % (product_id, index, c["column"], value[:40], c["type"]))
        self.assertEqual(problems[:20], [], "%d typed-column violations" % len(problems))

    def test_enumerations_and_foreign_keys(self):
        problems = []
        for product_id, columns in self.by_product.items():
            rows = self._rows(product_id)
            for c in columns:
                if not c["constraint"]:
                    continue
                kind, spec = c["constraint"].split(":", 1)
                allowed = set(spec.split("|")) if kind == "enum" else self._lookup(spec)
                for index, row in enumerate(rows, 2):
                    value = row[c["column"]]
                    if value == "":
                        continue
                    values = value.split(";") if kind == "fk-list" else [value]
                    for v in values:
                        if v not in allowed:
                            problems.append("%s row %d: %s = %r is outside %s"
                                            % (product_id, index, c["column"], v[:40], kind))
        self.assertEqual(problems[:20], [], "%d vocabulary/foreign-key violations" % len(problems))


if __name__ == "__main__":
    unittest.main()

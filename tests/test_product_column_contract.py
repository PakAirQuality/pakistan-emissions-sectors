"""Unestimated numeric bounds retain a numeric, nullable product contract."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from _support import scripts_on_path
scripts_on_path()
import build_product_columns as builder


class DeclaredProductColumns(unittest.TestCase):
    def test_absent_completeness_bounds_are_numeric_nulls(self):
        with tempfile.TemporaryDirectory(prefix="pakemis-column-contract-") as directory:
            path = Path(directory) / "bounds.csv"
            path.write_text("completeness_bound_Mt\n\"\"\n", encoding="utf-8")
            schemas = [{"product_id": product, "relative_path": str(path)}
                       for product in ("uncertainty.joint", "semantic.fact_uncertainty")]
            with patch.object(builder, "read_rows", return_value=schemas), \
                 patch.object(builder, "asset_path", side_effect=lambda root, rel: rel):
                columns = builder.build()
        self.assertEqual(len(columns), 2)
        self.assertTrue(all(row["type"] == "float" and row["nullable"] == "yes"
                            for row in columns))

    def test_legacy_parameter_graph_is_an_explicit_closed_model_basis(self):
        expected = "enum:legacy_parameter_graph_sensitivity_not_native_material_flow"
        for product in ("uncertainty.longitudinal", "uncertainty.longitudinal_prefix",
                        "uncertainty.trend"):
            self.assertEqual(builder.OVERRIDES[(product, "model_basis")][0], expected)


if __name__ == "__main__":
    unittest.main()

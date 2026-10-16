"""The analytical legacy sensitivity must not masquerade as native uncertainty."""
import unittest
from pathlib import Path

from pkinv.core.io import read_rows
from pkinv.paths import OUTPUTS

OUTPUT_DIR = Path(OUTPUTS)


class UncertaintyProductScope(unittest.TestCase):
    def test_legacy_tables_and_catalogue_state_their_limited_basis(self):
        basis = "legacy_parameter_graph_sensitivity_not_native_material_flow"
        for name in ("pakemis_longitudinal_uncertainty.csv",
                     "pakemis_trend_uncertainty.csv",
                     "pakemis_longitudinal_prefix.csv"):
            rows = read_rows(str(OUTPUT_DIR / name))
            self.assertTrue(rows, name)
            self.assertEqual({row["model_basis"] for row in rows}, {basis}, name)

        catalog = {row["product_id"]: row for row in
                   read_rows(str(OUTPUT_DIR / "pakemis_product_catalog.csv"))}
        for name in ("uncertainty.longitudinal", "uncertainty.trend"):
            self.assertEqual(catalog[name]["release_tier"], "supporting")
            self.assertEqual(catalog[name]["artifact_kind"], "sensitivity")
            self.assertEqual(catalog[name]["status"], "legacy analytical sensitivity")
            self.assertIn("not", catalog[name]["what_it_is_and_is_not"])
        self.assertEqual(catalog["uncertainty.ghg_native"]["release_tier"], "core")


if __name__ == "__main__":
    unittest.main()

"""Maintained observations reproduce existing source views without duplicate values."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from pkinv.activity import compatibility_views as views
from pkinv.assets import resolve
from pkinv.paths import ROOT


class CompatibilityViewsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in views.INPUTS:
            relative = "data/activity/" + name + ".csv"
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(Path(resolve(str(Path(ROOT) / relative))).read_bytes())
        target = self.root / views.FORMATS
        target.write_bytes(Path(resolve(str(Path(ROOT) / views.FORMATS))).read_bytes())

    def rows(self, name):
        return views._read(name, self.root)

    def change(self, name, update):
        rows = self.rows(name)
        update(rows)
        with (self.root / "data/activity" / (name + ".csv")).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def test_all_eight_views_reproduce_existing_bytes_without_reading_views(self):
        rendered = views.render(self.root)
        self.assertEqual(len(rendered), 8)
        for name, payload in rendered.items():
            expected = Path(resolve(str(Path(ROOT) / "data/activity" / (name + ".csv"))))
            self.assertEqual(payload, expected.read_bytes(), name)
        self.assertEqual(len(views.build(self.root)), 8)
        self.assertEqual(views.build(self.root, check=True), [])

    def test_shared_company_value_changes_all_three_views(self):
        def update(rows):
            next(row for row in rows if row["observation_id"] == "company-period-001"
                 and row["measure"] == "clinker_production")["value"] = "1234567"
        self.change("ippu/company_production", update)
        for name, rows in views.view_rows(self.root).items():
            if name.startswith("ippu/"):
                selected = next(row for row in rows if row["company"] == "Attock Cement Pakistan Limited"
                                and row["period_end_year"] == "2024")
                self.assertEqual(selected["clinker_production_t"], "1234567", name)

    def test_current_and_historical_gas_share_one_quantity_keep_annotations(self):
        before = views.view_rows(self.root)
        def update(rows):
            next(row for row in rows if row["fiscal_year"] == "2024"
                 and row["fuel"] == "Natural Gas")["quantity"] = "822"
        self.change("residential/fuel_supply_observations", update)
        after = views.view_rows(self.root)
        for name in ("residential/fuel_supply", "residential/fuel_supply_history"):
            old = next(row for row in before[name] if row["fuel"] == "Natural Gas" and row["fiscal_year"] == "2024")
            new = next(row for row in after[name] if row["fuel"] == "Natural Gas" and row["fiscal_year"] == "2024")
            self.assertEqual(new["quantity"], "822")
            self.assertEqual(new["source"], old["source"])
            self.assertEqual(new["note"], old["note"])
        self.assertEqual(len(after["residential/fuel_supply"]), 3)

    def test_company_not_in_series_is_retained_and_unprinted_cells_stay_missing(self):
        rows = views.view_rows(self.root)
        current = rows["ippu/company_clinker_2023_24"]
        census = rows["ippu/cement_producer_census_2023_24"]
        self.assertEqual(len(current), 16)
        self.assertEqual({r["company"] for r in current}, {r["company"] for r in census})
        self.assertIn("Cherat Cement Company Limited", {r["company"] for r in current})
        missing = next(r for r in rows["ippu/company_clinker_series"] if
                       r["company"] == "Dandot Cement Company Limited" and r["period_end_year"] == "2023")
        self.assertEqual(missing["status"], "not_printed")
        self.assertNotIn("clinker_production_t", missing)
        self.assertTrue(all("opening_clinker_stock_t" not in r for r in current))

    def test_duplicate_company_fact_fails_before_any_write(self):
        self.change("ippu/company_production", lambda rows: rows.append(dict(rows[0])))
        with self.assertRaisesRegex(ValueError, "duplicate maintained observation"):
            views.build(self.root)
        self.assertFalse((self.root / "data/activity/aviation/fuel_controls_2023_24.csv").exists())

    def test_catalog_can_relocate_sources_and_views(self):
        paths = list(views.INPUTS) + list(views.render(self.root))
        entries = []
        for i, name in enumerate(paths):
            old = "data/activity/" + name + ".csv"
            new = "data/sector-layout/asset-%d.csv" % i
            source, target = self.root / old, self.root / new
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.exists():
                source.replace(target)
            entries.append({"asset_id": str(i), "legacy_path": old, "path": new, "canonical_path": ""})
        catalog = self.root / "data/catalog/assets.csv"
        catalog.parent.mkdir(parents=True)
        with catalog.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, list(entries[0])); writer.writeheader(); writer.writerows(entries)
        self.assertEqual(len(views.build(self.root)), 8)
        self.assertEqual(views.build(self.root, check=True), [])


if __name__ == "__main__":
    unittest.main()

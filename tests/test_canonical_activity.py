"""Canonical input integrity, lossless field translation, and model adapter parity."""
import csv
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from pkinv.activity import build, store
from pkinv.core.io import read_rows as staging_rows
from pkinv.paths import ROOT


class CanonicalFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "data/activity").mkdir(parents=True)
        self.source = self.root / "data/activity/example.csv"
        self.source.write_text('species,quantity,note\ncattle,0,"a, b"\npoultry,,"line one\nline two"\n', encoding="utf-8")
        (self.root / "data/canonical_tables.csv").write_text(
            'table_id,source_path,path,title,role\n'
            'activity.example,data/activity/example.csv,data/canonical/activity/example.csv,Example,input\n')
        (self.root / "data/canonical_columns.csv").write_text(
            'table_id,field_id,name\nactivity.example,species,Animal\n'
            'activity.example,quantity,Quantity\nactivity.example,note,Note\n')

    def test_lossless_roundtrip_and_readable_download_rows(self):
        build.build(self.root)
        inputs = store.ActivityStore(self.root)
        self.assertEqual(inputs.legacy_rows("data/activity/example.csv"), staging_rows(self.source))
        rows = inputs.rows("activity.example")
        self.assertEqual(rows[0]["Quantity"], "0")
        self.assertEqual(rows[1]["Quantity"], "")
        self.assertEqual(rows[1]["Note"], "line one\nline two")
        self.assertEqual(rows[1]["Source row"], "2")
        rows[0]["Quantity"] = "changed by caller"
        self.assertEqual(inputs.rows("activity.example")[0]["Quantity"], "0")

    def test_noop_preserves_mtimes_and_check_never_writes(self):
        build.build(self.root)
        paths = list((self.root / "data/canonical").rglob("*"))
        before = {str(path): path.stat().st_mtime_ns for path in paths}
        self.assertEqual(build.build(self.root), [])
        self.assertEqual(build.build(self.root, check=True), [])
        self.assertEqual(before, {str(path): path.stat().st_mtime_ns for path in paths})
        self.source.write_text(self.source.read_text().replace("cattle,0", "cattle,1"))
        self.assertTrue(build.build(self.root, check=True))
        self.assertEqual(before, {str(path): path.stat().st_mtime_ns for path in paths})

    def test_runtime_refuses_missing_stale_and_corrupted_inputs(self):
        with self.assertRaises(store.CanonicalInputError):
            store.read_rows(self.source, root=self.root)
        build.build(self.root)
        inputs = store.ActivityStore(self.root)
        inputs.rows("activity.example")
        self.source.write_text(self.source.read_text().replace("cattle,0", "cattle,9"))
        with self.assertRaisesRegex(store.CanonicalInputError, "changed since"):
            inputs.rows("activity.example")
        build.build(self.root)
        inputs.rows("activity.example")
        target = self.root / "data/canonical/activity/example.csv"
        target.write_text(target.read_text().replace("cattle,9", "cattle,8"))
        with self.assertRaisesRegex(store.CanonicalInputError, "differs"):
            inputs.rows("activity.example")

    def test_canonical_only_runtime_does_not_require_staging(self):
        build.build(self.root)
        expected = staging_rows(self.source)
        self.source.unlink()
        self.assertTrue(store.input_exists(self.source, root=self.root))
        self.assertEqual(store.read_rows(self.source, root=self.root), expected)
        (self.root / "data/canonical/activity/example.csv").unlink()
        with self.assertRaises(store.CanonicalInputError):
            store.input_exists(self.source, root=self.root)

    def test_ingestion_boundary_is_explicit_and_scoped(self):
        with store.staging_inputs():
            self.assertEqual(store.read_rows(self.source, root=self.root), staging_rows(self.source))
        with self.assertRaises(store.CanonicalInputError):
            store.read_rows(self.source, root=self.root)

    def test_audited_reads_identify_only_the_consumed_table(self):
        build.build(self.root)
        with mock.patch("pkinv.activity.store.sys.audit") as audit:
            store.ActivityStore(self.root).rows("activity.example")
        audit.assert_called_once_with("pkinv.canonical.read", "activity.example",
                                      "data/canonical/activity/example.csv")

    def test_new_columns_and_new_activity_tables_require_declaration(self):
        self.source.write_text("species,quantity,note,unknown\ncattle,1,,x\n")
        with self.assertRaisesRegex(ValueError, "header changed"):
            build.build(self.root)
        (self.root / "data/activity/new.csv").write_text("value\n1\n")
        with self.assertRaisesRegex(ValueError, "no canonical table"):
            build.build(self.root)


class RepositoryAdapters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build.build(ROOT)

    def test_every_registered_value_and_row_survives(self):
        inputs = store.ActivityStore(ROOT)
        for table in inputs.tables:
            with self.subTest(table=table["table_id"]):
                self.assertEqual(inputs.legacy_rows(table["source_path"]),
                                 staging_rows(Path(ROOT) / table["source_path"]))
                self.assertFalse(table["source_path"].startswith("outputs/"))

    def test_all_ten_sector_data_interfaces_match_verified_staging(self):
        classes = (
            ("agriculture.ef_library", "InventoryData"), ("aviation.data", "AviationData"),
            ("fugitives.data", "FugitivesData"), ("industry.data", "IndustryData"),
            ("ippu.data", "IppuData"), ("power.data", "PowerData"),
            ("railways.data", "RailwaysData"), ("residential.data", "ResidentialData"),
            ("transport.data", "TransportData"), ("waste.data", "WasteData"),
        )
        for module, name in classes:
            with self.subTest(sector=module):
                constructor = getattr(importlib.import_module("pkinv.sectors." + module), name)
                with mock.patch("pkinv.activity.store.sys.audit") as audit:
                    canonical = vars(constructor())
                self.assertTrue(any(call.args[0] == "pkinv.canonical.read"
                                    for call in audit.call_args_list),
                                "%s bypassed the canonical input store" % module)
                with store.staging_inputs():
                    verified = vars(constructor())
                self.assertEqual(canonical, verified)

    def test_existing_activity_publication_preserves_values_and_legacy_ids(self):
        from pkinv.activity import present, publish
        canonical = publish.build_rows()
        with store.staging_inputs():
            verified = publish.build_rows()
        self.assertEqual(canonical, verified)
        registers = present.Registers()
        for name, rows in canonical.items():
            if rows:
                self.assertEqual(present.render(rows[0], registers.collections[name], registers)["Record ID"],
                                 present.render(verified[name][0], registers.collections[name], registers)["Record ID"])


if __name__ == "__main__":
    unittest.main()

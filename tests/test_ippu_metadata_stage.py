"""IPPU workflow registers do not participate in numerical input loading."""
import csv
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from pkinv.assets import legacy_path
from pkinv.sectors.ippu import schemas
from pkinv.sectors.ippu.data import IppuData, IppuMetadata
from pkinv.sectors.ippu.metadata import combined_checks, metadata_checks, validate_numerical_outputs


class IppuMetadataStageTest(unittest.TestCase):
    def test_numerical_constructor_does_not_read_descriptive_registers(self):
        forbidden = {"master_data_gap_matrix.csv", "evidence_maturity.csv",
                     "hfc_inventory_import_contract.csv", "data_request_packets.csv",
                     "source_manifest.csv"}
        original = schemas.read_csv
        reads = []
        def record(path):
            name = Path(legacy_path(path)).name
            self.assertNotIn(name, forbidden)
            reads.append(name)
            return original(path)
        with mock.patch.object(schemas, "read_csv", side_effect=record):
            data = IppuData()
        self.assertIn("company_boundary_audit.csv", reads)
        self.assertIn("chemical_plant_activity.csv", reads)
        self.assertIn("nitric_acid_monitoring_detail.csv", reads)
        self.assertEqual(len(data.company_clinker()), 16)

    def test_compatibility_metadata_properties_load_once_on_demand(self):
        data = IppuMetadata()
        with mock.patch.object(data, "_metadata_rows", return_value=[{"source_id": "fixture"}]) as read:
            self.assertEqual(read.call_count, 0)
            self.assertEqual(data.source_manifest_rows, [{"source_id": "fixture"}])
            self.assertIs(data.source_manifest_rows, data.source_manifest_rows)
            read.assert_called_once_with("source_manifest.csv")

    def test_metadata_stage_restores_original_qa_positions(self):
        descriptive = metadata_checks(IppuMetadata())
        checks = [{"check": name, "passed": True, "actual": "", "expected": "", "note": "fixture"}
                  for name in ("company_clinker_subset", "company_boundary_audit", "nitric_monitoring_detail")]
        context = {"checks": checks, "declared": ["numerical.csv", "descriptive.csv"]}
        with tempfile.TemporaryDirectory() as temporary:
            for name in context["declared"]:
                Path(temporary, name).touch()
            result = combined_checks(context, descriptive, temporary)
            names = [row["check"] for row in result]
            self.assertEqual(names[:4], ["company_clinker_subset", "company_boundary_audit",
                                        "evidence_maturity", "nitric_monitoring_detail"])
            self.assertEqual(names[4:-1], ["completeness_2." + family for family in "ABCDEFG"])
            self.assertTrue(all(row["passed"] for row in result))
            self.assertEqual(result[-1]["actual"], 2)
            Path(temporary, "numerical.csv").unlink()
            failed = combined_checks(context, descriptive, temporary)
            self.assertFalse(failed[-1]["passed"])
            self.assertIn("numerical.csv", failed[-1]["note"])
        self.assertEqual(context["checks"], checks)

    def test_metadata_rejects_changed_or_missing_numerical_outputs(self):
        payload = b"category,emissions\nfixture,1\n"
        context = {"numerical_outputs": {"outputs/numerical.csv": hashlib.sha256(payload).hexdigest()}}
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary, "outputs/numerical.csv")
            target.parent.mkdir()
            with self.assertRaisesRegex(ValueError, "changed or missing"):
                validate_numerical_outputs(context, temporary)
            target.write_bytes(payload)
            validate_numerical_outputs(context, temporary)
            target.write_bytes(payload.replace(b",1", b",2"))
            with self.assertRaisesRegex(ValueError, "changed or missing"):
                validate_numerical_outputs(context, temporary)


if __name__ == "__main__":
    unittest.main()

"""CSV extraction must retain the distinctions workbook consumers rely on."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pkinv.core import source_extracts


class SourceExtractRoundTrip(unittest.TestCase):
    def round_trip(self, value):
        tree, payloads = source_extracts.serialize("example", value)
        with tempfile.TemporaryDirectory() as folder:
            for name, payload in payloads.items():
                (Path(folder) / name).write_bytes(payload)
            actual = source_extracts.deserialize(tree, folder)
        self.assertEqual(actual, value)
        return actual

    def test_numbers_notation_blank_none_and_missing_remain_distinct(self):
        value = [{"value": 0, "raw": "0", "notation": "NE", "blank": "", "null": None},
                 {"value": 1.2345678901234567, "raw": "1.2345678901234567",
                  "notation": "", "blank": "", "boolean": False}]
        actual = self.round_trip(value)
        self.assertIs(type(actual[0]["value"]), int)
        self.assertIs(type(actual[1]["value"]), float)
        self.assertNotIn("null", actual[1])
        self.assertIsNone(actual[0]["null"])

    def test_nested_cell_provenance_and_category_order_survive(self):
        value = {"category": {"value": 0.0, "cells": {"value": "C10"}, "raw": {"value": "0"}},
                 "gaseous": {"value": None, "cells": {"value": "C11"}, "raw": {"value": "NE"}}}
        actual = self.round_trip(value)
        self.assertEqual(list(actual), list(value))

    def test_category_identity_is_visible_in_csv_and_retains_its_type(self):
        value = {"Liquid fuels": {"value": 1.5}, 2022: {"value": 0}}
        tree, payloads = source_extracts.serialize("example", value)
        self.assertIn(b"source_key,value\nLiquid fuels,1.5\n2022,0\n", payloads["example.csv"])
        self.assertNotIn("keys", tree)
        self.assertEqual(self.round_trip(value), value)

    def test_fugitive_summary_and_rows_remain_a_tuple(self):
        actual = self.round_trip(({"year": 2022, "total": 3.5}, [{"category": "1.B.2", "value": 0}]))
        self.assertIsInstance(actual, tuple)

    def test_altered_csv_is_rejected(self):
        tree, payloads = source_extracts.serialize("example", [{"value": 1}])
        with tempfile.TemporaryDirectory() as folder:
            for name, payload in payloads.items():
                (Path(folder) / name).write_bytes(payload.replace(b"1", b"9"))
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                source_extracts.deserialize(tree, folder)

    def test_changed_parser_requires_explicit_reingestion(self):
        from pkinv.sectors.power import official_reporting
        with patch.object(source_extracts, "producer_fingerprint", return_value="changed"):
            with self.assertRaisesRegex(ValueError, "source parser changed"):
                official_reporting.extract()

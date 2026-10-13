"""Repeated provenance checks can share hashes without concealing edited documents."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pkinv.core import documents


class DocumentDigestCache(unittest.TestCase):
    def test_reuses_unchanged_file_but_detects_same_size_edit_with_restored_mtime(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.pdf"
            path.write_bytes(b"first")
            documents._cached_sha256.cache_clear()
            with patch("builtins.open", wraps=open) as reader:
                self.assertEqual(documents.sha256(path), hashlib.sha256(b"first").hexdigest())
                self.assertEqual(documents.sha256(path), hashlib.sha256(b"first").hexdigest())
                self.assertEqual(reader.call_count, 1)
            original = path.stat()
            path.write_bytes(b"other")
            os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
            self.assertEqual(documents.sha256(path), hashlib.sha256(b"other").hexdigest())

"""Shared accessors for the validation-package tests.

ROOT is whatever pkinv.paths resolved: the repository when the suite runs there, the package
when validate.sh runs it with PKINV_ROOT set. IN_PACKAGE is the one fact the tests branch on.
"""
import csv
import hashlib
import json
import os

from _support import ROOT

MANIFEST = os.path.join(ROOT, "VALIDATION_MANIFEST.json")
INVENTORY = os.path.join(ROOT, "FILE_INVENTORY.csv")
SUMS = os.path.join(ROOT, "SHA256SUMS")
KNOWN = os.path.join(ROOT, "KNOWN_EXCEPTIONS.json")
IN_PACKAGE = os.path.exists(MANIFEST) and os.path.exists(INVENTORY)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def data_rows(path):
    """Rows of a CSV that may carry `#` comment lines; strict about the field count
    (rc41): a row with more or fewer fields than the header raises rather than being
    silently truncated or padded."""
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(line for line in handle if not line.startswith("#"))
        rows = []
        for index, row in enumerate(reader, 2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError("%s row %d: field count differs from the %d-column header"
                                 % (path, index, len(reader.fieldnames or [])))
            rows.append(row)
        return rows


def manifest():
    with open(MANIFEST, encoding="utf-8") as handle:
        return json.load(handle)


def inventory():
    return data_rows(INVENTORY)


def parquet_column_values(path, columns):
    import pyarrow.parquet as pq
    table = pq.read_table(path, columns=columns)
    return list(zip(*[table.column(c).to_pylist() for c in columns]))

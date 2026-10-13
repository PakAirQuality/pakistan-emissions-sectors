"""The cross-sector ledger pointer grammar, in src so the semantic phase and the package tests
share one resolver (lifted from tests/validation/test_cross_sector_ledger.py)."""

from pkinv.assets import asset_path
import os

from pkinv.core.io import read_rows
from pkinv.paths import ROOT


def parse_key(text):
    return dict(part.split("=", 1) for part in text.split(";"))


def resolve(row, root=ROOT, sources=None):
    """The source rows a ledger-map row points at (exactly one when the map is well-formed)."""
    rows = (sources.rows(row["source_file"]) if sources is not None else
            read_rows(asset_path(root, row["source_file"])))
    key = parse_key(row["row_key"])
    return [r for r in rows if all(r.get(c) == v for c, v in key.items())]

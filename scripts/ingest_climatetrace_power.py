#!/usr/bin/env python3
"""Consumed derivative of the Climate TRACE power-asset extract (rc41).

Reads:  sources/Power Plants/climatetrace_power_assets_PAK.csv (registered, not shipped)
Writes: data/activity/power/climatetrace_power_assets_pak.csv

The power benchmark diagnostic (pkinv.sectors.power.benchmarks_plants) read the document
directly; the validation package registers the document without shipping it, so the
engine now reads THIS table - the document's 72 rows, every column, under a provenance
banner - and this script proves the table against the document wherever it is held.
Deterministic; --check re-derives and diffs (write_or_check discipline); exit 3 when the
document is not held.

Usage:  python3 scripts/ingest_climatetrace_power.py [--check]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pkinv.core import documents  # noqa: E402
from pkinv.core.io import read_rows, write_or_check  # noqa: E402
from pkinv.sectors.power.benchmarks_plants import TRACE_CSV, TRACE_SOURCE  # noqa: E402


def main(check=False):
    if not os.path.exists(TRACE_SOURCE):
        print("document not held: %s" % documents.relative(TRACE_SOURCE))
        return 3
    rows = read_rows(TRACE_SOURCE, comments=False)
    with open(TRACE_SOURCE, newline="", encoding="utf-8") as handle:
        header = handle.readline().rstrip("\r\n").split(",")
    banner = [
        "CONSUMED DERIVATIVE (rc41): every row and column of %s" % documents.relative(TRACE_SOURCE),
        "sha256 of the document: %s (data/raw_manifest.csv; data/consumed_derivatives.csv)"
        % documents.digest(TRACE_SOURCE, quiet=True),
        "written by scripts/ingest_climatetrace_power.py; --check re-derives it wherever the document is held",
        "read by pkinv.sectors.power.benchmarks_plants (Climate TRACE v7 power assets, Pakistan)",
    ]
    return write_or_check(TRACE_CSV, header, rows, check=check, banner=banner,
                          lineterminator="\n")


if __name__ == "__main__":
    from pkinv.activity.store import staging_inputs
    with staging_inputs():
        raise SystemExit(main(check="--check" in sys.argv))

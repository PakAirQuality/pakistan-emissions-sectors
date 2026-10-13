#!/usr/bin/env python3
"""Consumed derivative of the Climate TRACE waste-source extract for Pakistan (rc41).

Reads:  sources/ClimateTRACE/climatetrace_waste_PAK_sources.json (registered, not shipped)
Writes: data/activity/waste/climatetrace_waste_sites_pak.csv

The waste release-candidate table (pkinv.sectors.waste.gis.release_candidates) read the
JSON directly and added one candidate row per modelled source; the validation package
registers the document without shipping it, so the rebuild in the package produced 27
fewer candidates and the artifact inventory that records the table could not reproduce.
The engine now reads THIS table - the 27 sources with exactly the fields the candidate row
is built from, the quality string as the engine formatted it - and this script proves the
table against the document wherever it is held. Deterministic; --check re-derives and
diffs (write_or_check discipline); exit 3 when the document is not held.

Usage:  python3 scripts/ingest_climatetrace_waste.py [--check]
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pkinv.core import documents  # noqa: E402
from pkinv.core.io import write_or_check  # noqa: E402
from pkinv.sectors.waste.gis.release_candidates import CLIMATETRACE, CLIMATETRACE_TABLE  # noqa: E402

FIELDS = ("source_id", "subsector", "name", "quality", "latitude", "longitude")


def main(check=False):
    if not os.path.exists(CLIMATETRACE):
        print("document not held: %s" % documents.relative(CLIMATETRACE))
        return 3
    rows = []
    for s in json.load(open(CLIMATETRACE, encoding="utf-8")):
        c = s.get("centroid") or {}
        rows.append({
            "source_id": s["id"],
            "subsector": s.get("subsector") or "",
            "name": s.get("name") or "",
            # exactly the string the candidate row carried when the engine read the JSON
            "quality": "climatetrace_%s" % (s.get("confidence") or "na"),
            "latitude": c.get("latitude", ""),
            "longitude": c.get("longitude", ""),
        })
    banner = [
        "CONSUMED DERIVATIVE (rc41): the %d Climate TRACE v7 waste sources for Pakistan in"
        % len(rows),
        "%s, with the fields the release-candidate row is built from"
        % documents.relative(CLIMATETRACE),
        "sha256 of the document: %s (data/raw_manifest.csv; data/consumed_derivatives.csv)"
        % documents.digest(CLIMATETRACE, quiet=True),
        "written by scripts/ingest_climatetrace_waste.py; --check re-derives it wherever the document is held",
        "read by pkinv.sectors.waste.gis.release_candidates (comparator/candidate rows only)",
    ]
    return write_or_check(CLIMATETRACE_TABLE, list(FIELDS), rows, check=check, banner=banner,
                          lineterminator="\n")


if __name__ == "__main__":
    from pkinv.activity.store import staging_inputs
    with staging_inputs():
        raise SystemExit(main(check="--check" in sys.argv))

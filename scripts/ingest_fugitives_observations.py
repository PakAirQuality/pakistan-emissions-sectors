#!/usr/bin/env python3
"""Consumed derivatives of the two fugitives observation documents (rc41).

Reads:  sources/Fugitives/world_bank_flare_sites_2012_2025.xlsx (registered, not shipped)
        sources/Fugitives/unep_mars_plumes.zip (registered, not shipped; CC BY-NC-SA)
Writes: data/activity/fugitives/flare_sites_pak.csv
        data/activity/fugitives/mars_plumes_pak.csv
        data/activity/fugitives/mars_sources_pak.csv

pkinv.sectors.fugitives.observations opened both documents live (openpyxl, zipfile) for
the flare time series, the MARS event evaluation and the provincial comparison; the
validation package registers the documents without shipping them, so the engine now
reads THESE tables - the Pakistan rows, every column, exactly as the document carries
them - and this script proves each table against its document wherever it is held.
Deterministic; --check re-derives and diffs; exit 3 when a document is not held.

Usage:  python3 scripts/ingest_fugitives_observations.py [--check]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pkinv.core import documents  # noqa: E402
from pkinv.core.io import write_or_check  # noqa: E402
from pkinv.sectors.fugitives import observations as obs  # noqa: E402


def _banner(source, script_note, read_by):
    return [
        "CONSUMED DERIVATIVE (rc41): %s" % script_note,
        "document: %s, sha256 %s (data/raw_manifest.csv; data/consumed_derivatives.csv)"
        % (documents.relative(source), documents.digest(source, quiet=True)),
        "written by scripts/ingest_fugitives_observations.py; --check re-derives it wherever the document is held",
        "read by %s" % read_by,
    ]


def main(check=False):
    for source in (obs.FLARE_SOURCE, obs.MARS_SOURCE):
        if not os.path.exists(source):
            print("document not held: %s" % documents.relative(source))
            return 3
    codes = []
    header, rows = obs.extract_flare_sites()
    codes.append(write_or_check(
        obs.FLARE_TABLE, header, rows, check=check, lineterminator="\n",
        banner=_banner(obs.FLARE_SOURCE,
                       "the Pakistan rows of the World Bank GGFR flare-site list, every column "
                       "(annual flared volume, bcm, 2012-2025)",
                       "pkinv.sectors.fugitives.observations (flare_timeseries, geolocated_flare_sites)")))
    for member, table in sorted(obs.MARS_TABLES.items()):
        header, rows = obs.extract_mars_rows(member)
        codes.append(write_or_check(
            table, header, rows, check=check, lineterminator="\n",
            banner=_banner(obs.MARS_SOURCE,
                           "the Pakistan oil-and-gas rows of %s (UNEP IMEO MARS), every column; "
                           "the archive's LICENSE-CC-BY-NC-SA.txt governs the rows" % member,
                           "pkinv.sectors.fugitives.observations (mars_summary, geolocated_mars_sources, "
                           "mars_flare_matches)")))
    return max(codes)


if __name__ == "__main__":
    from pkinv.activity.store import staging_inputs
    with staging_inputs():
        raise SystemExit(main(check="--check" in sys.argv))

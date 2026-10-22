#!/usr/bin/env python3
"""Which FAOSTAT release each held bulk is, against FAOSTAT's own bulk-download catalogue.

WHY. A FAOSTAT domain is revised in place: the bulk at a fixed address is replaced at each release, and a
comparison read from a held bulk is only reproducible against that release. The second contribution-
evidence brief (22 October 2026) asked for each download's catalogue entry to be kept beside it. FAOSTAT
publishes the catalogue (datasets_E.json: file address, size, rows, date of update per domain), and a copy
was kept on 2026-10-22. This table joins it to every FAOSTAT bulk held in data/raw/faostat and its
retrieval record, so a reader can see which held bulks predate the current release.

The comparison column is a test on what is printed, not a proof of identity: the catalogue gives a size in
KB and a date, not a hash. 'same-size' means the held bytes, rounded UP to whole KB as FAOSTAT's
catalogue rounds them (checked on the EMN, GT and FBS bulks), equal the catalogue's KB; 'predates-update'
means the held copy was retrieved before the catalogue's DateUpdate, so the published file may since have
changed.

Reads:  data/raw/faostat/faostat_bulk_catalogue_datasets_E.json, data/raw/faostat/RETRIEVALS.csv, the held
        bulks (restricted layer)
Writes: data/sectors/agriculture/evidence/faostat_versions.csv
Usage:  PYTHONPATH=src python3 scripts/ingest_faostat_versions.py [--check]
"""
import argparse
import csv
import hashlib
import json
import os
import sys

from pkinv.assets import asset_path
from pkinv.core.io import write_or_check
from pkinv.paths import DATA

RAW = asset_path(DATA, "raw", "faostat")
CATALOGUE = os.path.join(RAW, "faostat_bulk_catalogue_datasets_E.json")
RETRIEVALS = os.path.join(RAW, "RETRIEVALS.csv")
OUT = asset_path(DATA, "sectors", "agriculture", "evidence", "faostat_versions.csv")
FIELDS = ("dataset_code", "dataset_name", "catalogue_date_update", "catalogue_file_size", "catalogue_file_rows",
          "held_file", "held_bytes", "held_sha256", "held_retrieved_utc", "size_vs_catalogue", "date_vs_catalogue")


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def rows():
    if not os.path.exists(CATALOGUE):
        raise SystemExit("%s is not mounted: this ingest reads the restricted layer "
                         "(scripts/overlay.py link)" % CATALOGUE)
    with open(CATALOGUE, encoding="utf-8") as handle:
        datasets = json.load(handle)["Datasets"]["Dataset"]
    with open(RETRIEVALS, encoding="utf-8", newline="") as handle:
        retrieved = {r["file"]: r for r in csv.DictReader(handle)}
    out = []
    for d in datasets:
        held = "faostat_" + d["FileLocation"].rsplit("/", 1)[-1]
        path = os.path.join(RAW, held)
        if not os.path.exists(path):
            continue
        if held not in retrieved:
            raise SystemExit("%s is held but has no RETRIEVALS.csv row" % held)
        size = os.path.getsize(path)
        sha = _sha256(path)
        if sha != retrieved[held]["sha256"]:
            raise SystemExit("%s does not hash to its RETRIEVALS.csv row" % held)
        kb = int(d["FileSize"].rstrip("KB"))
        when = retrieved[held]["retrieved_utc"]
        out.append({"dataset_code": d["DatasetCode"], "dataset_name": d["DatasetName"],
                    "catalogue_date_update": d["DateUpdate"], "catalogue_file_size": d["FileSize"],
                    "catalogue_file_rows": d["FileRows"], "held_file": "data/raw/faostat/" + held,
                    "held_bytes": size, "held_sha256": sha, "held_retrieved_utc": when,
                    "size_vs_catalogue": "same-size" if -(-size // 1024) == kb else "differs",
                    "date_vs_catalogue": "predates-update" if when[:10] < d["DateUpdate"][:10] else "after-update"})
    out.sort(key=lambda r: r["dataset_code"])
    return out


def banner():
    return ("FAOSTAT RELEASES OF THE HELD BULKS, AGAINST FAOSTAT'S BULK-DOWNLOAD CATALOGUE.",
            "Catalogue: https://bulks-faostat.fao.org/production/datasets_E.json, kept 2026-10-22 as "
            "data/raw/faostat/faostat_bulk_catalogue_datasets_E.json (sha256 %s)." % _sha256(CATALOGUE),
            "The catalogue prints a size in KB and a date, not a hash: same-size and predates-update are tests on "
            "what it prints, not proof that the held bytes are or are not the current release.",
            "Written by scripts/ingest_faostat_versions.py.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="re-derive and report a difference; write nothing")
    args = ap.parse_args(argv)
    result = rows()
    code = write_or_check(OUT, FIELDS, result, check=args.check, banner=banner(), lineterminator="\n")
    if not args.check:
        print("wrote %s (%d rows)" % (os.path.relpath(OUT, os.path.dirname(DATA)), len(result)))
    return code


if __name__ == "__main__":
    sys.exit(main())

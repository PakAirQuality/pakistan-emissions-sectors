"""Every raw byte this inventory was built from: where it is, what it hashes to, who owns it.

WHY, GIVEN THAT GIT NOW TRACKS ALL OF IT. Because git tracking is not a backup. Committing a
file puts a second copy in .git on the SAME disk, and this project's disk is 89 percent full
with no cloud copy anywhere. What protects irreplaceable government scans is a second physical
location, and what makes a second location trustworthy is a list of what should be in it and
what each file should hash to. That list is this file.

It also covers the raw tree that is licensed separately. data/cache/aviation/adsblol/ is
9.76 GB of ADS-B under ODbL, and this repository ships MIT plus CC-BY-4.0 for data; folding
share-alike data into a CC-BY core would relicense it by inclusion. It IS tracked (LFS - the
raw-data round chose one uncopied disk over an ignore rule) but is recorded here as
`package=odbl-external` so the licence separation survives publication: external means
separately licensed, never unchecked. (Until rc36 this paragraph said git did not hold it;
the rc36 presence audit found all six tars in LFS, hashed and verified.) Since rc36 data/gis/
- the rasters and boundaries the allocation reads - is a tree here too; it had been in
neither hash manifest.

WHAT `tracked` MEANS on a row:
  git       an ordinary git object, in this repository's history
  lfs       a Git LFS object; the file exceeds GitHub's 100 MB limit
  external  held on disk, hashed here, deliberately outside git for licence reasons

HASHING 12 GB TAKES A WHILE. The manifest stores size and mtime beside the digest and reuses a
previous digest when both are unchanged, so a re-run after adding one file costs one hash
rather than four hundred. `--rehash` forces the full pass, which is what you want before
trusting a mirror.

Usage:  python3 scripts/raw_data_manifest.py [--rehash]
Writes: data/raw_manifest.csv
"""
import argparse
import csv
import hashlib
import os
import sys
from pkinv.core.io import read_rows
from pkinv.assets import catalog as asset_catalog, resolve, legacy_path
from pkinv.core import layers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = resolve(os.path.join(ROOT, "data", "raw_manifest.csv"), root=ROOT)

FIELDS = ("path", "bytes", "sha256", "mtime", "tracked", "package", "licence", "origin",
          "note")

# Trees that hold RAW inputs - documents and payloads this project did not produce. Generated
# outputs live in outputs/ and are covered by the release manifest instead.
# rc36: data/raw/ joins the manifest. The .gitignore essay said this file "records every
# raw file" while it held not one data/raw/ row; the 4,764-document NEPRA corpus and every
# other acquisition under data/raw/ were hashed by nothing.
TREES = ("sources", os.path.join("data", "cache"), os.path.join("data", "raw"),
         os.path.join("data", "gis"),
         # rc37: the transcription directories hold their source documents beside the
         # CSVs (census workbooks, MNFSR/CRS booklets, GLEAM reference PDFs, GMW workbooks,
         # NFDC reviews); nothing hashed them
         os.path.join("data", "pbs_census"), os.path.join("data", "district_records"),
         os.path.join("data", "gleam"), os.path.join("data", "gmw"), os.path.join("data", "nfdc"))

# Licence and package by tree prefix. Anything not matched is the repository default, which is
# what an unrecognised new directory should inherit until someone says otherwise.
LICENCE_RULES = (
    (os.path.join("data", "cache", "aviation", "adsblol"),
     "ODbL-1.0", "odbl-external",
     "https://samples.adsb.lol/",
     "raw ADS-B; share-alike, kept out of the CC-BY core so inclusion does not relicense it"),
    (os.path.join("sources", "OSM"),
     "ODbL-1.0", "odbl-external-in-tree",
     "https://download.geofabrik.de/asia/pakistan.html",
     "OpenStreetMap extract; ODbL, tracked here but licensed separately from the CC-BY core"),
    (os.path.join("sources", "HIES"),
     "PBS microdata terms", "restricted-microdata",
     "https://www.pbs.gov.pk/",
     "household survey microdata; redistribution terms are the publisher's, not CC-BY"),
    (os.path.join("data", "cache"),
     "upstream terms", "cache-external", "", "retrieved payloads, not authored here"),
    (os.path.join("data", "gis"),
     "mixed open licences (per-directory *_SOURCES.json)", "gis-inputs", "",
     "the rasters and boundaries the spatial allocation reads (WorldPop, geoBoundaries, SPAM, "
     "GLW, GHSL, ESA WorldCover, the OSM-derived surfaces); 229 MB that had been in neither "
     "hash manifest until rc36 - provenance in the *_SOURCES.json sidecars"),
    (os.path.join("data", "raw", "pbs", "hies"),
     "PBS microdata terms", "restricted-microdata",
     "https://www.pbs.gov.pk/",
     "household survey microdata; redistribution terms are the publisher's, not CC-BY"),
    (os.path.join("data", "raw", "nepra"),
     "source-document terms", "archive",
     "https://nepra.org.pk/",
     "the regulator's SIR daily reports and FCA determinations, fetched by "
     "scripts/download_sir_archive.py and scripts/fetch_fca_corpus.py; public, terms not stated"),
    (os.path.join("data", "raw"),
     "source-document terms", "archive",
     "", "held acquisitions; the curated provenance rows are data/manifests/source_manifest.csv"),
    # rc37: the transcription directories - documents beside the CSVs typed from them
    (os.path.join("data", "pbs_census"),
     "source-document terms", "archive", "https://www.pbs.gov.pk/",
     "PBS 7th Agricultural Census 2024 Table 4/6 workbooks and PDFs, with the transcriptions"),
    (os.path.join("data", "district_records"),
     "source-document terms", "archive", "",
     "MNFSR and Punjab Crop Reporting Service district-wise booklets, with the transcriptions"),
    (os.path.join("data", "gleam"),
     "FAO terms", "archive", "https://www.fao.org/gleam/",
     "FAO GLEAM 3.0 model description and reference documentation, with the transcription"),
    (os.path.join("data", "gmw"),
     "CC-BY-4.0", "archive", "https://www.globalmangrovewatch.org/",
     "Global Mangrove Watch country statistics workbooks, with the transcription"),
    (os.path.join("data", "nfdc"),
     "source-document terms", "archive", "https://www.nfdc.gov.pk/",
     "NFDC fertilizer reviews (PDF + pdftotext) beside the annex extractions"),
    ("sources", "source-document terms", "archive",
     "", "government and institutional documents; see data/source_documents.csv"),
)

SKIP_NAMES = {".DS_Store"}
# Derived caches that live beside raw inputs and are gitignored ON PURPOSE: they are rebuilt
# by a producer from files this manifest already lists, so a row for them would call a
# reproducible intermediate "external" (the word for a licence-separated raw holding).
# Keyed on the LEGACY identity, which is what the asset catalog matches on below. The
# .gitignore entry that makes the word "gitignored" true now names the current location,
# /data/shared/gis/adm2_intersections_267x340.csv - the sector layout relocated the file
# out from under the retired `data/gis/*` block, so the exclusion was re-expressed there.
SKIP_PATHS = {
    "data/gis/adm2_intersections_267x340.csv",       # scripts/build_adm2_intersections.py
    "data/gis/adm2_intersections_267x340.csv.txt",   # its provenance sidecar
}


def _rules_for(relative):
    relative = legacy_path(relative, root=ROOT)
    for prefix, licence, package, origin, note in LICENCE_RULES:
        if relative == prefix or relative.startswith(prefix + os.sep):
            return licence, package, origin, note
    return "undetermined", "unclassified", "", "no licence rule matched this path"


def _lfs_paths():
    """LFS paths from whichever repository owns each one (src/pkinv/core/layers.py): from
    rc69 the documents are tracked by the private checkout mounted beside a public clone."""
    return layers.lfs_files(root=ROOT)


def _git_paths():
    return set(layers.ls_files(root=ROOT))


def _previous():
    if not os.path.exists(OUT):
        return {}
    return {os.path.relpath(resolve(os.path.join(ROOT, row["path"]), root=ROOT), ROOT): row
            for row in read_rows(OUT, comments=False)}


def sha256(path, chunk=1 << 20):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def walk():
    seen = set()
    for asset in asset_catalog(root=ROOT):
        logical = asset["legacy_path"]
        if (any(logical.startswith(tree.rstrip("/") + "/") for tree in TREES)
                and logical not in SKIP_PATHS and os.path.basename(logical) not in SKIP_NAMES):
            relative = asset["path"]
            full = os.path.join(ROOT, relative)
            if os.path.isfile(full):
                seen.add(relative)
                yield relative, full
    for tree in TREES:
        base = os.path.join(ROOT, tree)
        if not os.path.isdir(base):
            continue
        for folder, _dirs, names in os.walk(base):
            for name in sorted(names):
                if name in SKIP_NAMES:
                    continue
                full = os.path.join(folder, name)
                relative = os.path.relpath(full, ROOT).replace(os.sep, "/")
                if relative in SKIP_PATHS or relative in seen:
                    continue
                yield relative, full


def build(rehash=False):
    previous = _previous()
    lfs, tracked = _lfs_paths(), _git_paths()
    rows, hashed, reused = [], 0, 0
    for relative, full in walk():
        stat = os.stat(full)
        old = previous.get(relative)
        if (not rehash and old and old["bytes"] == str(stat.st_size)
                and old["mtime"] == str(int(stat.st_mtime)) and old["sha256"]):
            digest, reused = old["sha256"], reused + 1
        else:
            digest, hashed = sha256(full), hashed + 1
        # The mtime is a cache key for the digest, not a property of the document. A fresh
        # clone (rc69: development moved to the public repository) stamps every tracked file
        # with the moment of checkout; unchanged content keeps the time it was recorded with,
        # so the manifest regenerates byte for byte in any checkout.
        mtime = int(stat.st_mtime)
        if old and old["sha256"] == digest and old["bytes"] == str(stat.st_size) and old["mtime"]:
            mtime = int(old["mtime"])
        licence, package, origin, note = _rules_for(relative.replace("/", os.sep))
        rows.append({
            "path": relative,
            "bytes": stat.st_size,
            "sha256": digest,
            "mtime": mtime,
            "tracked": ("lfs" if relative in lfs else
                        "git" if relative in tracked else "external"),
            "package": package,
            "licence": licence,
            "origin": origin,
            "note": note,
        })
    rows.sort(key=lambda r: r["path"])
    return rows, hashed, reused


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rehash", action="store_true",
                        help="re-hash every file rather than reusing unchanged digests")
    args = parser.parse_args(argv)
    if not layers.present(ROOT):
        raise SystemExit("the restricted layers are not mounted here (mode %s), so this "
                         "manifest would list none of the documents it exists to hold. "
                         "Run python3 scripts/overlay.py link PATH first." % layers.mode(ROOT))

    rows, hashed, reused = build(args.rehash)
    # THE MANIFEST MAY NOT FORGET A DOCUMENT. This script rebuilds its list from the disk,
    # so until October 2026 a deleted document simply stopped being listed and the one test
    # that had noticed went quiet. data/catalog/document_retention.csv is the list that only
    # grows (scripts/retain_document.py); a path it holds that the disk no longer does is a
    # deletion, and a deletion is refused here, by name, before anything is written.
    ledger = os.path.join(ROOT, "data", "catalog", "document_retention.csv")
    if os.path.exists(ledger):
        with open(ledger, encoding="utf-8", newline="") as handle:
            retained = {r["path"] for r in csv.DictReader(handle)}
        lost = sorted(retained - {r["path"] for r in rows})
        if lost:
            print("REFUSED: %d held documents are in the retention ledger and no longer on "
                  "disk. Nothing was written. Restore them (git checkout, the mirror); a held "
                  "document is never deleted:" % len(lost))
            for path in lost[:40]:
                print("  %s" % path)
            return 1
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    total = sum(r["bytes"] for r in rows)
    print("raw data manifest -> %s" % os.path.relpath(OUT, ROOT))
    print("  %d files, %.2f GB (%d hashed now, %d digests reused)"
          % (len(rows), total / 1024 ** 3, hashed, reused))
    by_tracked = {}
    for row in rows:
        entry = by_tracked.setdefault(row["tracked"], [0, 0])
        entry[0] += 1
        entry[1] += row["bytes"]
    for state in ("git", "lfs", "external"):
        if state in by_tracked:
            count, size = by_tracked[state]
            print("    %-9s %4d files  %8.2f GB" % (state, count, size / 1024 ** 3))
    unclassified = [r["path"] for r in rows if r["package"] == "unclassified"]
    if unclassified:
        print("  %d files matched no licence rule - classify them before publication:"
              % len(unclassified))
        for path in unclassified[:5]:
            print("    %s" % path)
    print("  git holds a second copy on the SAME disk; scripts/mirror_raw_data.sh is what "
          "puts one somewhere else")
    return 0


if __name__ == "__main__":
    sys.exit(main())

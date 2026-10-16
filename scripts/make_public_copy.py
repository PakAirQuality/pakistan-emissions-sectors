#!/usr/bin/env python3
"""Assemble the public copy of a release: the tracked tree without other people's documents.

WHY THIS EXISTS. The working repository keeps every document the inventory was built from,
because several are no longer published anywhere. Those are third-party publications, and one
family of them (the PBS household survey microdata) may not be redistributed at all. The
repository is therefore private, and through rc67 every manuscript pointed its readers at it.
The public repository is a COPY of each release that leaves the documents out. The first copy
was assembled by hand on 13 October 2026; the list of what to leave out belongs in code, so
the next one cannot leave out less.

WHAT IS LEFT OUT, and it is a rule about WHOSE WORK a file is, not about its size:

  sources/, data/raw/              primary documents and comparator datasets
  data/cache/                      downloaded archives a pilot study read
  five older document folders      third-party documents kept under pre-layout paths
  thirteen rasters                 SPAM, GCD-Rice, WorldPop, GHSL: obtain from the publisher
  campaign/, .claude/              working notes and tool settings

Everything else tracked is this project's own code, tables, products and prose. The tables
under data/sectors/ and data/shared/ are what the project DERIVED from the documents, each
row with its citation, and they ship. Every document left out stays listed with its SHA-256
in data/catalog/raw_manifest.csv and data/catalog/document_retention.csv.

NOT A HISTORY. The copy is a directory of files. Committing and pushing it is a separate,
deliberate act; this script never touches a remote.

Usage:  python3 scripts/make_public_copy.py OUT_DIR        (OUT_DIR must be empty or absent)
        python3 scripts/make_public_copy.py --list         (print what would be left out)
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv import __version__, release  # noqa: E402

NOTE_NAME = "PUBLIC_MIRROR.md"

# (prefix, what it is). A prefix ends with "/" and matches everything under it.
LEFT_OUT_TREES = (
    ("sources/", "primary documents (frozen legacy tree)"),
    ("data/raw/", "primary documents and comparator datasets"),
    ("data/cache/", "downloaded aircraft-position archives used by one pilot study"),
    ("data/nfdc/", "third-party documents under an older path"),
    ("data/gleam/", "third-party documents under an older path"),
    ("data/gmw/", "third-party documents under an older path"),
    ("data/pbs_census/", "third-party documents under an older path"),
    ("data/district_records/", "third-party documents under an older path"),
    ("campaign/", "working notes"),
    (".claude/", "tool settings"),
)
# Third-party rasters, named one by one: the folders they sit in also hold this project's own
# provenance notes (*SOURCES*.json), which ship.
LEFT_OUT_FILES = (
    "data/shared/gis/worldpop_pak_2020_1km.tif",
    "data/sectors/agriculture/gis/manual/gcd_rice_2023.tif",
    "data/sectors/agriculture/gis/manual/spam2020_V2r2_global_A_RICE_I.tif",
    "data/sectors/agriculture/gis/manual/spam2020_V2r2_global_A_RICE_R.tif",
    "data/sectors/agriculture/gis/manual/spam_rice.tif",
)
LEFT_OUT_PATTERNS = (
    # every GHSL tile, and no other file of that folder
    ("data/shared/gis/manual/ghsl_built_1km/", ".tif"),
)
# Record-level survey files must never ship, wherever a future layout puts them.
FORBIDDEN_SUFFIXES = (".sav", ".dta", ".por", ".zsav")
# GitHub refuses a file over 100 MiB. The products above this size are this project's own
# (the monthly configuration panels and grids, rc68) and ship in the deposit; the copy lists
# them in PUBLIC_MIRROR.md instead of failing the push.
SIZE_LIMIT_BYTES = 95 * 1024 * 1024


def tracked():
    out = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode()
    return [p for p in out.split("\0") if p]


def left_out(path):
    """The reason a tracked path stays out of the public copy, or None if it ships."""
    for prefix, reason in LEFT_OUT_TREES:
        if path.startswith(prefix):
            return reason
    if path in LEFT_OUT_FILES:
        return "third-party raster"
    for prefix, suffix in LEFT_OUT_PATTERNS:
        if path.startswith(prefix) and path.endswith(suffix):
            return "third-party raster"
    if path.lower().endswith(FORBIDDEN_SUFFIXES):
        return "record-level survey file"
    full = os.path.join(ROOT, path)
    if (os.path.isfile(full) and not os.path.islink(full)
            and os.path.getsize(full) > SIZE_LIMIT_BYTES):
        return "own product too large for GitHub (in the deposit)"
    return None


def partition(paths=None):
    paths = tracked() if paths is None else paths
    keep, drop = [], []
    for path in paths:
        (drop if left_out(path) else keep).append(path)
    return keep, drop


def note(commit, n_keep, n_drop, n_documents, large=()):
    return """# This repository is the public copy of {product} {version}

It holds the code, the verified data tables, the released products, the manuscripts and the
tests of release {version}. It was made from commit `{commit}` of the project's working
repository, which is private. `outputs/release_manifest.json` names commits of that
repository; they do not exist here, because this copy carries no history of it.

## What is not here, and why

The working repository also keeps every document the inventory was built from. Those are
other people's publications and data, and this project cannot grant a licence for them, so
they are left out ({n_drop} files; {n_keep} are here):

| Left out | What it is |
|---|---|
| `sources/`, `data/raw/` | {n_documents} primary documents: government reports and scans, company reports, statistical yearbooks, IPCC chapters, comparator datasets. The household survey microdata (PBS, HIES) is among them; PBS forbids redistribution of the record-level files. |
| `data/cache/` | Downloaded aircraft-position archives used by one pilot study. |
| `data/nfdc/`, `data/gleam/`, `data/gmw/`, `data/pbs_census/`, `data/district_records/` | Further third-party documents kept under older paths. |
| Thirteen raster files under `data/sectors/agriculture/gis/manual/` and `data/shared/gis/` | SPAM 2020 rice area (three files), GCD-Rice 2023, WorldPop 2020 and eight GHSL built-up tiles. Obtain them from their publishers; the `*SOURCES*` notes kept beside them give the addresses and versions. |
| `campaign/`, `.claude/` | Working notes and tool settings. |
| {too_large} | This project's own products, each over GitHub's 100 MB file limit: {large_list}. They are in the deposit, with their checksums in `outputs/SHA256SUMS`. |

Every document left out is listed with its SHA-256 in `data/catalog/raw_manifest.csv` and
`data/catalog/document_retention.csv`, and `data/catalog/cited_documents.csv` says which data
table cites which document. A reader who obtains a document can check it is the one used.

What IS here from those documents is what the project derived from them: the transcribed and
verified tables under `data/sectors/` and `data/shared/`, each row with its source citation.

## What this means for rebuilding

The sector engines and the national build read the verified tables, not the documents, and
run from this copy. A small number of build phases, checks and tests read the documents or
the rasters directly and will fail or skip here; `docs/deposit_rebuild_limits.md` lists them.
The published test record (`outputs/pakemis_test_run.json`) was taken on the full working
tree, not on this copy. Continuous integration is switched off on this repository for the
same reason.

## Where else to look

- The release itself, its checksums and its citation: `README.md`, `CITATION.cff`,
  `outputs/SHA256SUMS`, `outputs/release_manifest.json`.
- What changed in each release: `CHANGELOG.md`.
- An interactive explorer of the dataset is at {explorer}, a website of the
  {initiative} ({initiative_url}). It is deployed separately and can serve an earlier
  release than this one; check the release it names before comparing its totals with the
  ones in this repository.

Code is under the MIT licence (`LICENSE`); data and text under CC BY 4.0 (`LICENSE-data`).
""".format(product=release.PRODUCT, version=__version__, commit=commit, n_keep=n_keep,
           n_drop=n_drop, n_documents=n_documents, explorer=release.EXPLORER_URL,
           initiative=release.INITIATIVE, initiative_url=release.INITIATIVE_URL,
           too_large="%d large products" % len(large),
           large_list=", ".join("`%s`" % p for p in large) or "none")


def main(argv):
    keep, drop = partition()
    if "--list" in argv:
        for path in drop:
            print("%s\t%s" % (path, left_out(path)))
        print("%d tracked, %d ship, %d left out" % (len(keep) + len(drop), len(keep), len(drop)),
              file=sys.stderr)
        return 0
    if len(argv) != 1:
        raise SystemExit(__doc__)
    out = os.path.abspath(argv[0])
    if os.path.exists(out) and os.listdir(out):
        raise SystemExit("%s is not empty; a public copy is assembled into a fresh directory, "
                         "so a file left out this time cannot survive from last time" % out)
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).decode().strip()
    if dirty:
        raise SystemExit("the working tree is not clean; the copy must be of a commit:\n%s"
                         % dirty[:600])
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    os.makedirs(out, exist_ok=True)
    for path in keep:
        source, target = os.path.join(ROOT, path), os.path.join(out, path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.islink(source):
            os.symlink(os.readlink(source), target)
        else:
            shutil.copy2(source, target)
    n_documents = sum(1 for p in drop if p.startswith(("sources/", "data/raw/")))
    large = [p for p in drop if left_out(p).startswith("own product too large")]
    with open(os.path.join(out, NOTE_NAME), "w", encoding="utf-8") as handle:
        handle.write(note(commit, len(keep), len(drop), n_documents, large))
    print("public copy of %s (%s) -> %s: %d files, %d left out, plus %s"
          % (__version__, commit[:12], out, len(keep), len(drop), NOTE_NAME))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

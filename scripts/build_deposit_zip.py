#!/usr/bin/env python3
"""The three archive deposits of a release, prepared in dist/ (v1.0.0 program; user-only upload).

    python3 scripts/build_deposit_zip.py [--data] [--documentation] [--software] [--out DIR]

- data          pakemis-<version>-data.zip: every deposit-manifest row of kind product, input,
                provenance or documentation EXCEPT a product whose release tier is `build`,
                laid out per docs/product_catalog_design.md (pakemis-core/ by release tier
                core, pakemis-support/ for supporting + research + inputs, pakemis-audit/ for
                audit) with SHA256SUMS. Refuses any file that is not a deposit-manifest row,
                and any manifest row whose digest no longer matches disk.

                THAT EXCEPTION USED TO BE UNSTATED, and it is not a detail. This docstring said
                "every product row" while data_layout() skipped build-tier products under rule
                7, and the two selections share no criterion - deposit_manifest.py picks
                products from release_manifest.PRODUCT_PATTERNS and never consults role or
                tier. Thirteen hashed products fell in the gap, essentially the whole
                air-pollutant family, and the test named for a partition held one inclusion
                only, so nothing noticed. Every remaining exclusion is now declared in
                tests/test_dev_snapshot.py::DepositZips.DECLARED_UNPLACED with its reason.
- documentation pakemis-<version>-documentation.zip: the manuscript rows (papers/pdf) with the
                paper-hash sidecar, the release cover and the licences.
- software      pakemis-<version>-software.zip: `git archive HEAD` (the tracked tree at the
                commit; sources/ is untracked and data/raw is excluded by .gitattributes rules).

Nothing here mints or uploads anything. The zips are deterministic for a given tree
(fixed entry times, sorted entries)."""
import csv
import hashlib
import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path
import pkinv  # noqa: E402
from pkinv.core.io import read_rows  # noqa: E402

VERSION = pkinv.__version__
DEPOSIT = asset_path(ROOT, "outputs", "pakemis_deposit_manifest.csv")
INVENTORY = asset_path(ROOT, "outputs", "pakemis_artifact_inventory.csv")
STAMP = (2026, 1, 1, 0, 0, 0)
TIER_DIR = {"core": "pakemis-core", "supporting": "pakemis-support", "research": "pakemis-support",
            "audit": "pakemis-audit"}
DATA_KINDS = ("product", "input", "provenance", "documentation")
ROOT_DOCS = ("LICENSE", "LICENSE-data", "CITATION.cff", ".zenodo.json", "README.md", "CHANGELOG.md")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def deposit_rows():
    rows = read_rows(DEPOSIT)
    for row in rows:
        path = asset_path(ROOT, row["path"])
        if not os.path.exists(path):
            raise RuntimeError("deposit-manifest row missing on disk: %s" % row["path"])
        if row["sha256"] and sha256(path) != row["sha256"]:
            raise RuntimeError("deposit-manifest digest stale: %s (regenerate the manifest)" % row["path"])
    return rows


def tiers():
    return {row["artifact"]: row["release_tier"] for row in read_rows(INVENTORY)}


def data_layout(rows):
    """[(archive path, repo-relative path)] for the data deposit."""
    tier = tiers()
    out = []
    for row in rows:
        rel, kind = row["path"], row["kind"]
        if kind not in DATA_KINDS or rel.startswith("papers/"):
            continue
        if kind == "product":
            name = rel[len("outputs/"):] if rel.startswith("outputs/") else rel
            t = tier.get(name, "")
            if t == "build":
                continue                                    # rule 7: no build artifact in a deposit
            folder = TIER_DIR.get(t, "pakemis-support")
            out.append(("%s/%s" % (folder, name), rel))
        elif kind == "input":
            out.append(("pakemis-support/inputs/%s" % rel[len("data/"):] if rel.startswith("data/") else
                        "pakemis-support/inputs/%s" % rel, rel))
        elif kind == "provenance":
            out.append(("pakemis-core/provenance/%s" % os.path.basename(rel), rel))
        else:                                               # documentation
            if rel in ROOT_DOCS:
                out.append((rel, rel))
            else:
                out.append(("pakemis-core/docs/%s" % rel.replace("docs/", "", 1), rel))
    out.append(("pakemis-core/provenance/pakemis_deposit_manifest.csv", "outputs/pakemis_deposit_manifest.csv"))
    seen = {}
    for arc, rel in out:
        if arc in seen and seen[arc] != rel:
            raise RuntimeError("two files map to %s: %s and %s" % (arc, seen[arc], rel))
        seen[arc] = rel
    return sorted(seen.items())


def documentation_layout(rows):
    out = [(rel, rel) for rel in ("outputs/pakemis_paper_hashes.csv", "paper_common/release_cover.tex",
                                  "LICENSE-data", "CITATION.cff")]
    for row in rows:
        if row["kind"] == "manuscript":
            out.append((row["path"], row["path"]))
    return sorted(set(out))


def write_zip(zip_path, entries, sums_name="SHA256SUMS"):
    lines = []
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for arc, rel in entries:
            path = asset_path(ROOT, rel)
            info = zipfile.ZipInfo(arc, date_time=STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(path, "rb") as handle:
                data = handle.read()
            z.writestr(info, data)
            lines.append("%s  %s" % (hashlib.sha256(data).hexdigest(), arc))
        info = zipfile.ZipInfo(sums_name, date_time=STAMP)
        info.external_attr = 0o644 << 16
        z.writestr(info, "\n".join(lines) + "\n")
    return zip_path


# What a software record is, beside what it is not. The build stamps and the licence travel
# with the code because a reader cannot run it otherwise; the raw document trees do not,
# because they are not software and the data record carries what of them is redistributable.
SOFTWARE_EXTRA = ("Makefile", "README.md", "LICENSE", "CITATION.cff", ".zenodo.json",
                  "pyproject.toml", "requirements.txt", "reproduce.sh")


def software_zip(zip_path, rows=None):
    """The code, at HEAD, as the deposit manifest itself defines code.

    THIS SHIPPED THE WHOLE TREE UNTIL 2026-10-08. It was `git archive HEAD` with no
    pathspec, which archives everything tracked - and this repository tracks its raw
    document trees, 3.8 GB under sources/ and 3.6 GB under data/raw/. The software archive
    came out at 16.7 GB: a full repository snapshot wearing the label "software", against
    10.8 MB for the 928 files the deposit manifest calls code.

    An honest note on what this is NOT. A first reading of mine was that shipping those
    documents contradicted the manifest's licensing, and the evidence does not support it:
    the manifest does not cover sources/ at all, every outbound licence in it is own-work,
    own-work-compilation or public-licence, and nothing in it declines redistribution. The
    documents are tracked in a public repository already, so archiving them creates no new
    exposure. The defect is that a 16.7 GB software record is unusable and mislabelled, not
    that it is impermissible.

    THE SELECTION COMES FROM THE MANIFEST, not from a second list kept here. kind == "code"
    is already the repository's own answer to "what is software", and a pathspec written
    beside it would drift from it the first time a directory moved - which is the same
    mistake as the glob that sat beside the literals it subsumed. Files are read from HEAD
    rather than from the working tree, so the archive describes the committed release.
    """
    paths = sorted({r["path"] for r in (rows or deposit_rows()) if r["kind"] == "code"})
    assert paths, "the deposit manifest lists no code; refusing to write an empty archive"
    for extra in SOFTWARE_EXTRA:
        if os.path.exists(asset_path(ROOT, extra)):
            paths.append(extra)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        lines = []
        for rel in paths:
            blob = subprocess.run(["git", "-C", ROOT, "show", "HEAD:%s" % rel],
                                  capture_output=True, check=True).stdout
            arc = "pakemis-%s/%s" % (VERSION, rel)
            info = zipfile.ZipInfo(arc, date_time=STAMP)
            info.external_attr = 0o644 << 16
            z.writestr(info, blob)
            lines.append("%s  %s" % (hashlib.sha256(blob).hexdigest(), rel))
        info = zipfile.ZipInfo("pakemis-%s/SHA256SUMS" % VERSION, date_time=STAMP)
        info.external_attr = 0o644 << 16
        z.writestr(info, "\n".join(lines) + "\n")
    return zip_path


def main(argv):
    out_dir = os.path.abspath(argv[argv.index("--out") + 1]) if "--out" in argv else asset_path(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    wanted = [a for a in ("--data", "--documentation", "--software") if a in argv] or \
        ["--data", "--documentation", "--software"]
    rows = deposit_rows()
    built = []
    if "--data" in wanted:
        built.append(write_zip(asset_path(out_dir, "pakemis-%s-data.zip" % VERSION), data_layout(rows)))
    if "--documentation" in wanted:
        built.append(write_zip(asset_path(out_dir, "pakemis-%s-documentation.zip" % VERSION),
                               documentation_layout(rows)))
    if "--software" in wanted:
        built.append(software_zip(asset_path(out_dir, "pakemis-%s-software.zip" % VERSION),
                                  rows))
    with open(asset_path(out_dir, "pakemis-%s-deposits.SHA256SUMS" % VERSION), "w", encoding="utf-8") as handle:
        for path in built:
            handle.write("%s  %s\n" % (sha256(path), os.path.basename(path)))
            print("%s  %s  (%.1f MB)" % (sha256(path), path, os.path.getsize(path) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

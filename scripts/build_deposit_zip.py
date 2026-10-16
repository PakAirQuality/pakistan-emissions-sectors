#!/usr/bin/env python3
"""Prepare a local review collection with primary data, ODbL companion, documentation
and manifest-verified software/dependencies. Every archive has SHA256SUMS; one
outer release archive contains all records and their checksums. No upload or DOI
is performed. Raw publications are excluded unless separately admitted.

Usage: python3 scripts/build_deposit_zip.py [--data] [--documentation] [--software] [--out DIR]
"""
import csv
import hashlib
import json
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
ROOT_DOCS = ("LICENSE", "LICENSE-data", "LICENSE-ODbL", "CITATION.cff", ".zenodo.json", "README.md", "CHANGELOG.md")


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


def data_layout(rows, package_group="primary"):
    """[(archive path, repo-relative path)] for the data deposit."""
    tier = tiers()
    out = []
    for row in rows:
        rel, kind = row["path"], row["kind"]
        if row.get("package_group", "primary") != package_group:
            continue
        if kind not in DATA_KINDS or rel.startswith("papers/"):
            continue
        if kind == "product":
            name = rel[len("outputs/"):] if rel.startswith("outputs/") else rel
            t = tier.get(name, "")
            if t == "build":
                # Compiled-table reproduction needs registered downstream inputs.
                # Preserve these in support/reproduction, separate from core records.
                out.append(("pakemis-support/reproduction/%s" % name, rel))
                continue
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
            elif rel.startswith("campaign/"):
                out.append(("pakemis-core/review-evidence/%s" % rel, rel))
            else:
                out.append(("pakemis-core/docs/%s" % rel.replace("docs/", "", 1), rel))
    out.append(("pakemis-core/provenance/pakemis_deposit_manifest.csv", "outputs/pakemis_deposit_manifest.csv"))
    seen = {}
    for arc, rel in out:
        if arc in seen and seen[arc] != rel:
            raise RuntimeError("two files map to %s: %s and %s" % (arc, seen[arc], rel))
        seen[arc] = rel
    return sorted(seen.items())


def companion_layout(rows):
    entries = data_layout(rows, "odbl-companion")
    entries.extend((rel, rel) for rel in ("LICENSE-data", "LICENSE-ODbL", "docs/deposit_rebuild_limits.md"))
    return sorted(set(entries))


def documentation_layout(rows):
    out = [(rel, rel) for rel in ("outputs/pakemis_paper_hashes.csv", "paper_common/release_cover.tex",
                                  "LICENSE-data", "LICENSE-ODbL", "CITATION.cff")]
    for row in rows:
        if row["kind"] in ("manuscript", "manuscript_source"):
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
                  "pyproject.toml", "requirements.txt", "requirements.lock", "reproduce.sh", "LICENSE-data", "LICENSE-ODbL")


def software_zip(zip_path, rows=None):
    """Code and dependency records from the manifest-verified release snapshot.

    THIS SHIPPED THE WHOLE TREE UNTIL 2026-10-08. It was `git archive HEAD` with no
    pathspec, which archives everything tracked - and this repository tracks its raw
    document trees, 3.8 GB under sources/ and 3.6 GB under data/raw/. The software archive
    came out at 16.7 GB: a full repository snapshot wearing the label "software", against
    10.8 MB for the 928 files the deposit manifest calls code.

    Public availability does not establish redistribution permission. Raw publications
    and survey microdata are excluded; only the declared code and dependency closure
    enter this record.

    THE SELECTION COMES FROM THE MANIFEST, not from a second list kept here. kind == "code"
    is already the repository's own answer to "what is software", and a pathspec written
    beside it would drift from it the first time a directory moved. Bytes are read from
    the verified snapshot, including authorized new files. HEAD alone would silently
    package obsolete code while products describe an uncommitted corrected release.
    The revision and dirty status are recorded, never described as a clean commit.
    """
    paths = sorted({r["path"] for r in (rows or deposit_rows()) if r["kind"] in ("code", "build")})
    assert paths, "the deposit manifest lists no code; refusing to write an empty archive"
    for extra in SOFTWARE_EXTRA:
        if os.path.exists(asset_path(ROOT, extra)):
            paths.append(extra)
    paths = sorted(set(paths))
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        lines = []
        for rel in paths:
            with open(asset_path(ROOT, rel), "rb") as handle:
                blob = handle.read()
            arc = "pakemis-%s/%s" % (VERSION, rel)
            info = zipfile.ZipInfo(arc, date_time=STAMP)
            info.external_attr = 0o644 << 16
            z.writestr(info, blob)
            lines.append("%s  %s" % (hashlib.sha256(blob).hexdigest(), rel))
        revision = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True, text=True, check=True).stdout != ""
        metadata = json.dumps({"release_version": VERSION, "git_head": revision,
            "working_tree_modified": dirty, "software_content_sha256": hashlib.sha256("\n".join(lines).encode()).hexdigest(),
            "reproduction_basis": "manifest-verified compiled inputs; primary-source re-extraction separate"}, sort_keys=True, indent=2).encode() + b"\n"
        arc = "pakemis-%s/RELEASE_SNAPSHOT.json" % VERSION
        info = zipfile.ZipInfo(arc, date_time=STAMP)
        info.external_attr = 0o644 << 16
        z.writestr(info, metadata)
        lines.append("%s  RELEASE_SNAPSHOT.json" % hashlib.sha256(metadata).hexdigest())
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
        built.append(write_zip(asset_path(out_dir, "pakemis-%s-odbl-companion.zip" % VERSION), companion_layout(rows)))
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
    # One immutable review collection includes all constituent archives and their
    # actual checksums. Building it is local; no deposit or DOI is minted here.
    sums = asset_path(out_dir, "pakemis-%s-deposits.SHA256SUMS" % VERSION)
    release_path = asset_path(out_dir, "pakemis-%s-release.zip" % VERSION)
    with zipfile.ZipFile(release_path, "w", zipfile.ZIP_STORED) as archive:
        for path in sorted(built + [sums]):
            info = zipfile.ZipInfo(os.path.basename(path), date_time=STAMP)
            info.external_attr = 0o644 << 16
            with open(path, "rb") as handle:
                archive.writestr(info, handle.read())
    print("%s  %s" % (sha256(release_path), release_path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

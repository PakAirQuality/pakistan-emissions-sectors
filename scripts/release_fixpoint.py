"""The release dance, as one command that refuses to run on the wrong tree.

The manifest's git block names the commit that was HEAD when it was GENERATED -- by
construction the parent of the commit that carries it -- and its tree_dirty flag records
whether anything uncommitted was present at that moment. The rc3 release shipped every PDF
with "Commit feb9fac (working tree modified)" in its provenance box, because the manifest
was regenerated mid-work and committed as-is: the printed commit did not identify the tree
that built the papers, which an external reviewer correctly called a release-integrity
failure.

The fixpoint: commit ALL content first (engine, prose, outputs), so the tree is clean;
then this script regenerates the manifest (tree_dirty=False, describes_commit=HEAD), the
cover, and every PDF; then a second, artifacts-only commit carries them. Regenerating
after that second commit changes only the VOLATILE git block, which every check excludes,
so the fixpoint is stable. This script enforces the precondition: if anything OTHER than
the regenerable artifacts is modified, it stops and says commit your content first.

Usage:  python3 scripts/release_fixpoint.py     (or: make release-fixpoint)
"""
import csv
import hashlib
import os
import re
import subprocess
import sys

from pkinv.assets import resolve
from pkinv.core.io import read_rows

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ARTIFACT_PATTERNS = (
    r"^outputs/release_manifest\.json$",
    # Both are written BY this script, after the checks below, so a tree carrying only
    # their previous run's output is clean content as far as the freeze is concerned.
    r"^outputs/pakemis_paper_hashes\.csv$",
    r"^outputs/pakemis_test_run\.json$",
    r"^outputs/SHA256SUMS$",
    r"^paper_common/release_cover\.tex$",
    r"^papers/pdf/",
    # NESTED: the national paper's PDFs and bibliographies moved into
    # paper_national/versions/<v>/, and [^/]+ would no longer match them - the fixpoint
    # would have stopped recognising the article's own output as a release artefact.
    r"^paper_national/versions/[^/]+/[^/]+\.(pdf|bbl)$",
    r"^papers/[^/]+/(paper|supplement)\.(pdf|bbl)$",
)


def _run(cmd):
    print("-> %s" % " ".join(cmd))
    subprocess.check_call(cmd)


def _porcelain():
    out = subprocess.check_output(["git", "status", "--porcelain"]).decode()
    return [line[3:].strip() for line in out.splitlines() if line.strip()]


def _read_csv(path):
    return read_rows(path)


def check_spatial_inputs():
    """The fail-closed half of the declared-fallback design (sixth review): a release
    may ship only fallback CLASSES listed in data/allowed_grid_fallbacks.csv, and the
    committed proxy caches must match the digests published in PROXY_SOURCES.md. A
    new fallback class means a spatial input went missing or was renamed - that is a
    build defect, not a substitution to declare after the fact."""
    problems = []
    allowed = {(r["scope"], r["declared"], r["used"])
               for r in _read_csv(os.path.join(ROOT, "data",
                                               "allowed_grid_fallbacks.csv"))}
    for row in _read_csv(os.path.join(ROOT, "outputs",
                                      "pakemis_grid_fallbacks.csv")):
        key = (row["scope"], row["declared"], row["used"])
        if key not in allowed:
            problems.append("fallback class not in the allow-list: %r (stream %s)"
                            % (key, row["source_stream_id"]))

    # The closure identity's second term must ship WITH the cube. A grid that is 2% short of
    # the national total and a missing sidecar is indistinguishable from a grid that lost
    # mass, so a release cannot have one without the other.
    unallocated_path = os.path.join(ROOT, "outputs", "pakemis_spatial_unallocated.csv")
    if not os.path.exists(unallocated_path):
        problems.append("the cube ships without its unallocated table: "
                        "outputs/pakemis_spatial_unallocated.csv")
    else:
        published = {}
        for row in _read_csv(unallocated_path):
            published[row["gas"]] = published.get(row["gas"], 0.0) + float(
                row["emissions_Gg"])
        declared = {}
        for row in _read_csv(os.path.join(ROOT, "outputs",
                                          "pakemis_source_streams.csv")):
            if row["geometry_id"] == "S4:no-native-geometry":
                declared[row["gas"]] = (declared.get(row["gas"], 0.0)
                                        + float(row["emissions_native"]))
        for gas, total in sorted(declared.items()):
            got = published.get(gas, 0.0)
            if abs(got - total) > max(1e-6 * total, 1e-6):
                problems.append("unallocated %s is %.8f Gg and the ledger declares %.8f"
                                % (gas, got, total))
        for gas in sorted(set(published) - set(declared)):
            problems.append("unallocated table carries %s, which no stream declares "
                            "unplaceable" % gas)

    # A PUBLISHED OUTPUT MAY NOT BE OLDER THAN THE DATA IT IS BUILT FROM. This is the
    # general form of the defect that shipped a wrong number in the IPPU manuscript:
    # `make national` builds the cross-sector layer only, so a sector's own products can lag
    # its inputs indefinitely while the roll-up moves on. outputs/ippu_facility_registry.csv
    # lagged data/activity/ippu/facility_geocoding_overrides.csv through four releases,
    # reporting eight geocoded facilities against nineteen held, and the manuscript's claim
    # was anchored to it. Nothing in the release path noticed, because nothing compared a
    # product's age with its source's.
    #
    # Declared pairs rather than a dependency graph: the graph does not exist here, and
    # inventing one would be a second build definition to keep in step with the three that
    # already exist. A pair added is a pair someone decided mattered.
    for product, source in (
            (os.path.join("outputs", "ippu_facility_registry.csv"),
             os.path.join("data", "activity", "ippu", "facility_geocoding_overrides.csv")),
            (os.path.join("outputs", "pakemis_facility_registry.csv"),
             os.path.join("data", "facility_registry.csv")),
    ):
        # The pairs are declared by their published identities; resolve() maps a source
        # to wherever the sector layout keeps it.
        product_path, source_path = resolve(os.path.join(ROOT, product)), resolve(
            os.path.join(ROOT, source))
        if not (os.path.exists(product_path) and os.path.exists(source_path)):
            problems.append("declared freshness pair is missing a file: %s <- %s"
                            % (product, source))
            continue
        if os.path.getmtime(product_path) < os.path.getmtime(source_path):
            problems.append("%s is older than %s; the runner that writes it is not in "
                            "`make national`, so run its sector target before releasing"
                            % (product, source))

    # The published identities stay `data/gis/...`; resolve() finds where they now live.
    sources_md = open(resolve(os.path.join(ROOT, "data", "gis", "PROXY_SOURCES.md")),
                      encoding="utf-8").read()
    for match in re.finditer(r"\| `(proxy_[a-z_0-9]+\.npy)` \| `([0-9a-f]{64})` \|",
                             sources_md):
        name, digest = match.group(1), match.group(2)
        path = resolve(os.path.join(ROOT, "data", "gis", name))
        if not os.path.exists(path):
            problems.append("proxy cache missing: data/gis/%s" % name)
            continue
        actual = hashlib.sha256(open(path, "rb").read()).hexdigest()
        if actual != digest:
            problems.append("proxy cache data/gis/%s does not match the digest "
                            "published in PROXY_SOURCES.md" % name)
    return problems


# EVERY VERSION'S PDFs BY GLOB (2026-10-07). This list used to name the MAIN version's two
# filenames literally - paper_national.pdf and supplement.pdf - so v2, the version going to
# the journal, whose files are paper.pdf, submission.pdf and technical_supplement.pdf, was
# hashed nowhere in the release record. The review's item 1 asked for a hash-locked archive
# and named the supplement; measured, it was all three files.
#
# THE TWO LITERALS ARE GONE, not kept beside the glob. Keeping both duplicated v1's two
# rows - 23 rows carrying 21 distinct paths - and `path` is a declared unique key, so
# validation/test_product_schemas caught it. A glob that subsumes a literal must replace
# it; adding one beside the other means every file matched by both is written twice.
PAPER_GLOBS = ("papers/pdf/*.pdf",
               "paper_national/versions/*/*.pdf")
PAPER_HASHES = "outputs/pakemis_paper_hashes.csv"


def _write_paper_hashes():
    """Hash the shipped papers AFTER they are built, in a file they do not quote.

    The release manifest cannot carry these. It is quoted by the release cover, the cover
    is inputted by every paper, so a manifest containing PDF hashes would change the
    cover, which changes the PDFs, which changes their hashes - no fixpoint. Writing them
    here, one step after `make papers`, is the only ordering that closes.

    These hashes are NOT a rebuild target. LaTeX stamps /CreationDate into every file, so
    two builds of identical sources differ byte for byte; the digest identifies the
    artifact a reader downloaded, and that is all it can honestly do.
    """
    import glob
    rows = []
    for pattern in PAPER_GLOBS:
        for path in sorted(glob.glob(os.path.join(ROOT, pattern))):
            with open(path, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            rows.append((os.path.relpath(path, ROOT), digest,
                         os.path.getsize(path)))
    out = os.path.join(ROOT, PAPER_HASHES)
    with open(out, "w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(["path", "sha256", "bytes", "byte_stable", "note"])
        for path, digest, size in rows:
            w.writerow([path, digest, size, "false",
                        "LaTeX stamps a build date, so this identifies the distributed "
                        "artifact and is not a reproducible target"])
    print("-> %s (%d papers)" % (PAPER_HASHES, len(rows)))


SHA256SUMS = "outputs/SHA256SUMS"


def _write_sha256sums():
    """The flat checksum file a downloader verifies with `shasum -a 256 -c` (rc29,
    a FAIR fix): every file in outputs/, one line each, EXCEPT itself and the
    files written after it in the release dance (the paper-hash sidecar and the
    test-run record are written later by design; the rebuild log describes a run
    that compares the manifest). The release manifest remains the structured
    record; this is the same facts in the one format every platform's tooling
    already reads."""
    import glob
    skip = {SHA256SUMS, PAPER_HASHES, "outputs/pakemis_test_run.json"}
    lines = []
    for path in sorted(glob.glob(os.path.join(ROOT, "outputs", "**", "*"),
                                 recursive=True)):
        rel = os.path.relpath(path, ROOT)
        if not os.path.isfile(path) or rel in skip:
            continue
        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        # sha256sum -c format: digest, two spaces, path relative to the repo root
        lines.append("%s  %s" % (digest, rel))
    out = os.path.join(ROOT, SHA256SUMS)
    with open(out, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print("-> %s (%d files)" % (SHA256SUMS, len(lines)))


def main():
    spatial = check_spatial_inputs()
    if spatial:
        print("REFUSING: the spatial inputs are not release-clean -- a missing or "
              "substituted input must be resolved (or its class deliberately added "
              "to data/allowed_grid_fallbacks.csv), never shipped silently.")
        for p in spatial[:20]:
            print("  %s" % p)
        return 1

    dirty = _porcelain()
    non_artifact = [p for p in dirty
                    if not any(re.match(pat, p) for pat in ARTIFACT_PATTERNS)]
    if non_artifact:
        print("REFUSING: the tree carries uncommitted CONTENT, so the regenerated "
              "manifest would say tree_dirty and the cover would ship '(working tree "
              "modified)' -- the exact defect this script exists to prevent.")
        print("Commit these first:")
        for p in non_artifact[:20]:
            print("  %s" % p)
        return 1

    _run([sys.executable, "-m", "pkinv.report.release_manifest"])
    _write_sha256sums()
    _run([sys.executable, "scripts/make_release_cover.py"])
    _run([sys.executable, "scripts/make_availability.py"])
    _run(["make", "papers"])
    _write_paper_hashes()

    print()
    print("Artifacts regenerated on a clean content tree. Finish with the artifacts-only")
    print("commit so the shipped cover names the content commit:")
    print("  git add -A && git commit -m "
          "'Release manifest, cover and PDFs: regenerate against the clean tree'")
    print()
    print("THEN, and not before, record what the released tree's suite does:")
    print("  python3 scripts/record_test_run.py && git add outputs/pakemis_test_run.json "
          "&& git commit -m 'Record the release run'")
    print("Two release-integrity tests cannot pass until that artifacts commit exists - the")
    print("manifest at HEAD does not describe HEAD until HEAD is the artifacts commit - so a")
    print("record taken here would ship a FAILED outcome that says nothing about the release.")
    print("The manifest does not hash the record, so writing it afterwards reopens nothing.")
    print()
    print("LAST, once the record is committed, check the three commits are in that order:")
    print("  make release-sequence")
    print("Nothing in the suite can check it: the record is produced BY the suite, so while")
    print("it runs the committed record is necessarily the previous release's. A record")
    print("left in the working tree and swept into the next content commit by `git add -A`")
    print("describes a tree two commits old and every test stays green.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

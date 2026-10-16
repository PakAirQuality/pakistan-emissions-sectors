#!/usr/bin/env python3
"""Mint a PakEmis release candidate: the parameterised form of the mint_rc46..mint_rc61 family.

    python3 scripts/mint_release.py OLD NEW [--dry-run]      e.g. 1.0.0rc61 1.0.0rc62

Idempotent: a site already carrying NEW is reported, not refused. The CHANGELOG section for
NEW is written beforehand and is not patched here. The four GENERATED version sites follow the
build (outputs/release_manifest.json, paper_common/release_cover.tex, the two generated
availability fragments). After this script: the FULL build, then the release fixpoint.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = sys.argv[1], sys.argv[2]
DRY = "--dry-run" in sys.argv[3:]

done, applied, missing = [], [], []


def patch(path, pairs, count=None):
    full = os.path.join(R, path)
    with open(full, encoding="utf-8") as handle:
        s = original = handle.read()
    for old, new in pairs:
        n = s.count(old)
        if n == 0:
            # Already applied, or genuinely absent. Those are different, and the difference
            # is whether the NEW form is there instead.
            (done if s.count(new) else missing).append("%s: %r" % (path, old[:60]))
            continue
        if count is not None and n != count:
            raise SystemExit("%s: expected %d of %r, found %d" % (path, count, old[:60], n))
        s = s.replace(old, new)
        applied.append("%s: %d site(s) of %r" % (path, n, old[:60]))
    if s == original:
        return
    if DRY:
        print("would patch %s" % path)
    else:
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(s)
        print("patched %s" % path)


patch("src/pkinv/__init__.py", [('__version__ = "%s"' % OLD, '__version__ = "%s"' % NEW)])
patch("CITATION.cff", [("version: %s" % OLD, "version: %s" % NEW)])
# DERIVED from OLD/NEW, not typed. CITATION.cff carries the version in two spellings
# and the dashed one was a literal pair copied from mint to mint - so this script
# inherited rc59->rc60 while its own OLD/NEW said rc60->rc61, and reported the site
# "already applied" when it had not been touched at all.
DASHED = lambda v: "v" + v.replace("rc", "-rc")
patch("CITATION.cff", [(DASHED(OLD), DASHED(NEW))])
patch(".zenodo.json", [('"version": "%s"' % OLD, '"version": "%s"' % NEW)])
# THE v1 PAPER MOVED under paper_national/versions/ after rc59, so the paths the previous
# mint used no longer exist. The four GENERATED sites are deliberately not here and follow
# the build: outputs/release_manifest.json, paper_common/release_cover.tex,
# paper_common/generated_availability_tn.tex and versions/v1/generated/availability.tex.
# rc69: the v1 report's main file and abstract, and the v3 article, no longer name the version
# in their own text - it reaches them through the generated availability fragments and the
# release cover - so those three sites were dropped. The v1 short summary is still written
# by hand and still names it.
patch("paper_national/versions/v1/short_summary.txt", [(OLD, NEW)])
patch("README.md", [(OLD, NEW)])
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)])
patch("paper_common/references.bib", [(OLD, NEW)])
# RESOLVED THROUGH THE ASSET CATALOG, not hardcoded: the 2026-09 layout migration moved
# this under data/catalog/, and the previous mint's literal path no longer exists. The shim
# exists for exactly this, and a bare path is what it cannot see.
sys.path.insert(0, os.path.join(R, "src"))
from pkinv.assets import asset_path                                   # noqa: E402
from pkinv.paths import DATA                                          # noqa: E402

patch(os.path.relpath(asset_path(DATA, "claims_registry.csv"), R),
      [(",%s," % OLD, ",%s," % NEW)])

print("\n%d site group(s) patched now, %d already applied, %d not found"
      % (len(applied), len(done), len(missing)))
for line in applied:
    print("  applied  %s" % line)
for line in done:
    print("  already  %s" % line)
for line in missing:
    print("  MISSING  %s" % line)
if missing:
    raise SystemExit(
        "\n%d site(s) carry neither the old nor the new version. That is not an "
        "already-applied mint; a site has moved or been renamed, and leaving it would ship a "
        "release that names two versions of itself." % len(missing))
print("\nThe CHANGELOG section for %s was written before this script; it is not patched here."
      % NEW)
print("Next: the FULL build (the version-stamped products), then the release fixpoint.")

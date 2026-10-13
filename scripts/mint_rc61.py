#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc61 from the rc60 tree.

    python3 scripts/mint_rc61.py [--dry-run]

Same shape as scripts/mint_rc60.py, and idempotent for the same reason: it reports a site
that is already patched instead of refusing to run, so a mint interrupted halfway can be
finished by running it again.

rc61 MOVES NO NUMBER AT ALL. It is the remainder of the 23rd review's item 6 - the four
deferred source questions written up as named open items ranked by what each would move, and
the wastewater sludge term restated as the DEFAULT ZERO it is rather than as a demonstration
- plus the deposit archives rebuilt against this tree. The pins stay at L 451.85782 and
S 446.72502 Mt CO2e AR5.

WHY A NEW VERSION FOR PROSE. rc60's test record is committed and describes a specific tree.
Changing that tree under the same label is exactly the state
data/catalog/published_release_vintages.csv calls "diverged-under-the-same-label", and its own
instruction is that the next mint bumps rather than republishes. A label that does not
identify its content is worth less than no label.

THIS FAMILY SHOULD BE ONE SCRIPT. mint_rc46 through mint_rc61 differ only in OLD, NEW and a
changelog body; the next round should collapse them into one parameterised producer that
reads its release notes from CHANGELOG.md, rather than adding a seventeenth near-copy.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc60", "1.0.0rc61"
DRY = "--dry-run" in sys.argv

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
patch("paper_national/versions/v1/paper_national.tex", [(OLD, NEW)])
patch("paper_national/versions/v1/sections/00_abstract.tex", [(OLD, NEW)])
patch("README.md", [(OLD, NEW)])
# THE v2 AVAILABILITY STATEMENT. Patched by hand at rc60 and therefore missed at
# rc61 until tests/test_v2_documents.py's version guard caught it - which is what
# that guard is for, and also the argument for naming the site here rather than
# relying on the next person to remember it.
patch("paper_national/versions/v2/paper.tex", [(OLD, NEW)])
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

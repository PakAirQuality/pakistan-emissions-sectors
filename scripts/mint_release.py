#!/usr/bin/env python3
"""Mint a PakEmis release candidate: the parameterised form of the mint_rc46..mint_rc61 family.

    python3 scripts/mint_release.py OLD NEW [--dry-run]      e.g. 1.0.0rc61 1.0.0rc62

Idempotent: a site already carrying NEW is reported, not refused. The CHANGELOG section for
NEW is written beforehand and is not patched here. The GENERATED version site
(outputs/release_manifest.json) follows the build. After this script: the FULL build, then the
release fixpoint.
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
# rc69: the record titles carry the version too ("PakEmis 1.0.0rc68: ..."), and the rc69 mint
# left both at the old one.
patch("CITATION.cff", [('title: "PakEmis %s:' % OLD, 'title: "PakEmis %s:' % NEW)])
patch(".zenodo.json", [('"title": "PakEmis %s:' % OLD, '"title": "PakEmis %s:' % NEW)])
patch("docs/reproducibility.md", [("dist/pakemis-%s-" % OLD, "dist/pakemis-%s-" % NEW)])
patch("docs/zenodo_data_record.md", [("PakEmis %s:" % OLD, "PakEmis %s:" % NEW)])
patch("README.md", [(OLD, NEW)])
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)])

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

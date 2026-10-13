#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc54 from the rc53 tree.

    python3 scripts/mint_rc54.py [--dry-run]

Identical in shape to scripts/mint_rc52.py: a release candidate carries no DOIs; regenerated
sites are left to the build; only data/claims_registry.csv is bumped among the stamped
registries. No push, no tag, no upload.

rc53 MOVES NO NATIONAL NUMBER. It is a diagnosis release: the industrial decline is taken apart
into the channel that produced it, the boundary the bar is drawn on is corrected in the reporting
axis, and the decision record adopts nothing.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc53", "1.0.0rc54"
DRY = "--dry-run" in sys.argv


def patch(path, pairs, count=None):
    full = os.path.join(R, path)
    s = open(full, encoding="utf-8").read()
    for old, new in pairs:
        n = s.count(old)
        if n == 0:
            raise SystemExit("%s: not found: %r" % (path, old[:80]))
        if count is not None and n != count:
            raise SystemExit("%s: expected %d of %r, found %d" % (path, count, old[:60], n))
        s = s.replace(old, new)
    if DRY:
        print("would patch %-42s (%d site(s))" % (path, sum(1 for _ in pairs)))
    else:
        open(full, "w", encoding="utf-8").write(s)
        print("patched %s" % path)


patch("src/pkinv/__init__.py", [('__version__ = "%s"' % OLD, '__version__ = "%s"' % NEW)], 1)
patch("CITATION.cff", [("version: %s" % OLD, "version: %s" % NEW)], 1)
patch(".zenodo.json", [('"version": "%s"' % OLD, '"version": "%s"' % NEW)], 1)
patch("paper_national/paper_national.tex",
      [("release \\texttt{%s}" % OLD, "release \\texttt{%s}" % NEW)], 1)
patch("paper_national/sections/00_abstract.tex",
      [("under release \\texttt{%s}." % OLD, "under release \\texttt{%s}." % NEW)], 1)
patch("CITATION.cff", [("v1.0.0-rc53", "v1.0.0-rc54")], 1)
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)], 1)
patch("paper_common/references.bib", [(OLD, NEW)], 6)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
patch("CHANGELOG.md", [("\n\n## [%s] — September 2026" % OLD, """

## [%s] — September 2026

**One meaning of "industry" across the product, and an acceptance policy that can tell an absence
from a contradiction. NO NATIONAL NUMBER MOVES.** rc53 filed captive self-generation where IPCC 2006
reports it and then left two things wrong: the correction reached one page, and the decision record
that accompanied it scored missing evidence as though the candidate had been tested and failed.

- **The district layer answers the reporting axis.** rc53 refused it at district grain on the ground
  that the district tables were module-resolved, and that ground was wrong: the cube computes each
  stream's district vector for every period and folded it into a module key two lines later. The
  accumulator now keys on (module, reporting_sector), so a module's district mass is partitioned by
  where the Guidelines report it - exactly, from the same per-stream vectors, with the module total
  recoverable by summing over the pair. Industry and power read 28.13 and 57.82 at national,
  provincial AND district grain, which is the consistency the axis existed for and did not deliver.
  The 5.54 Mt that moves is captive generation's own measured district vector - a point allocation
  over 1,060 geocoded plants - never a proportional share of the power module's districts, and the
  release already quantifies that a surface-based substitute would differ by more than 5 points.
- **The per-stream district vector, for all nine periods.** pakemis_adm2_stream_by_year.csv, 223,774
  rows. The reference year's has shipped since rc47; the other eight were computed in the same loop
  and dropped. Same generator as the reference-year file, which a test holds row-for-row, and the
  same closure: a stream's district rows sum, with its OUTSIDE row, to its provincial mass at 1e-9.
- **The acceptance policy, rewritten before any new evidence meets it.** Every test RESULT now
  carries a kind: `constraint` (a bound, and THE OFFICIAL SERIES IS SCORED ON IT TOO), `validation`
  (two estimates, neither the truth), `untested` (the input is not held, and it NEVER favours either
  side). The same evidence re-scores as 11 constraints, 19 validations and 33 untested - and the
  three violated constraints belong to the OFFICIAL series, conditionally, not to the candidates.
  rc53's verdicts ship beside them under policy_version.
- **A pinned verdict, retracted.** tests/test_industrial_coal_decision.py asserted
  `decision.startswith("OFFICIAL STAYS BOOKED")` on every row - the only place in the tree where a
  scientific conclusion was pinned rather than a number, so a build in which the evidence had
  changed its mind would have failed the suite. The test now asserts the record's SHAPE: that an
  absence is never phrased as a failure, and that the objection blocking adoption is the defensible
  one (a single cross-section does not establish a TREND) and not the indefensible one (no
  reconstruction without an annual survey - IPCC 2006 Vol 1 Ch 5 permits a single-year surrogate).
- **A shipped number of ours was wrong, and is repaired.** ICIMOD prints a NATIONAL brick-coal
  figure of 6.5 Mt/yr on page 27. rc53 ignored it and scaled the paper's Punjab total up on this
  release's kiln frame to 3.94 Mt - 39 percent below the source's own national number. The
  independent level is now the source's figure and the scale-out is a cross-check that disagrees
  with it by a factor of 1.65; the official column reads 0.17x to 1.34x that level. Two further
  discrepancies are recorded rather than smoothed: the paper prints 3.1 Mt on the same page where
  its own arithmetic gives 3.41, and its national pair implies Punjab is 52 percent of national
  brick coal where the kiln frame says 87.

## [%s] — September 2026""" % (NEW, OLD))], 1)
print("done; regenerate (strict build), then the gate WITH --after-mint")

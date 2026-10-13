#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc57 from the rc56 tree.

    python3 scripts/mint_rc57.py [--dry-run]

Identical in shape to scripts/mint_rc56.py: a release candidate carries no DOIs; regenerated
sites are left to the build; only data/claims_registry.csv is bumped among the stamped
registries. No push, no tag, no upload.

rc57 MOVES NO NATIONAL NUMBER. The seventeen activity tables take a reader's shape - readable
headers, expanded labels, explicit units, unambiguous periods - and their technical fields move,
verbatim, to one companion table joined on Record ID.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc56", "1.0.0rc57"
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
patch("CITATION.cff", [("v1.0.0-rc56", "v1.0.0-rc57")], 1)
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)], 1)
patch("paper_common/references.bib", [(OLD, NEW)], 6)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
patch("CHANGELOG.md", [("\n\n## [%s] — September 2026" % OLD, """

## [%s] — September 2026

**The activity tables in a reader's shape. NO NATIONAL NUMBER MOVES.** The seventeen `fact_activity_*`
tables published in rc55 and rc56 answered the six questions in a machine's vocabulary - `head_count`,
`kha`, `province_by_locality`, a period `2014` whose meaning depended on the sector. They now read
`Period · Location · Measure · Animal type · Value · Unit · Period type · Location level · Evidence ·
Source series · Use note · Source reference · Record ID`, following the reshaping the user did by
hand and checked row for row. All 101,808 rows and every value are unchanged; a test joins each
readable row to its technical row and asserts it.

- **One companion table, `fact_activity_source_details`**: the twenty technical fields of every row,
  verbatim, under the same Record ID. The readable table is a view; this is the record.
- **One data dictionary, `dim_activity_columns`**: what every column of every readable table means.
- **The labels are registers, not code.** `data/activity_measures.csv` (what a variable is called),
  `activity_units.csv` (units spelt out, never rescaled), `activity_labels.csv` (the labels the
  mechanical default gets wrong: HSD, 2W, SNGPL), `activity_collections.csv` (each table's public
  shape), `activity_use_notes.csv` (the conditional caveats), and a `label` column on the evidence
  vocabulary. A value with no register entry fails the build naming it.
- **Every fiscal period is now spelt one way.** A bare year meant two different things in the tree -
  a railway `2014` is FY2013-14 and an airport `2006` is FY2006-07 - and the sector engines had
  always declared which. `fiscal_convention` carries that into the publication, so every fiscal
  period reads FYyyyy-yy, every month yyyy-mm, and a vehicle stock counted at 30 June carries the
  date it was counted. A bare year the publisher cannot resolve fails the build.
- **Six defects in the rc56 export, found by the user's review and fixed upstream rather than
  mirrored.** Three were one bug: the melt's own labels overwrote a declared category column, which
  is how 5,445 aviation rows lost their airport and 235 lost their airline. The airport is now the
  place it always was, at airport level. OCAC's per-row additivity flag is published on every area
  row (12,500 rows are not additive; the rule used to name the flag and withhold its value). NFDC's
  monthly plant gas carried a month with no year while the file had a year column. The livestock
  following-year projections sat under the base year. HIES waste-service provinces sat in the
  subcategory while the location said Pakistan - and the same national-marker rule that fixed them
  fixed 7,700 OCAC PAKISTAN rows levelled as a province. The provenance of a plant-month's fuel label
  was welded into the fuel itself; it is provenance, and it travels as such.
- **Crop districts are named, not coded.** `kp_bannu` is Khyber Pakhtunkhwa · Bannu District, from
  the canonical district registry; every district row carries its province.""" % NEW)], 1)

print("\nrc57 patched. Now: make national (or the regeneration tail), then the release fixpoint.")

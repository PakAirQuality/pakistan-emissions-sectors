#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc55 from the rc54 tree.

    python3 scripts/mint_rc55.py [--dry-run]

Identical in shape to scripts/mint_rc54.py: a release candidate carries no DOIs; regenerated
sites are left to the build; only data/claims_registry.csv is bumped among the stamped
registries. No push, no tag, no upload.

rc55 MOVES NO NATIONAL NUMBER. It adds products: the activity data behind the estimates,
published so it can be used without running PakEmis or studying emissions.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc54", "1.0.0rc55"
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
patch("CITATION.cff", [("v1.0.0-rc54", "v1.0.0-rc55")], 1)
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)], 1)
patch("paper_common/references.bib", [(OLD, NEW)], 6)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
patch("CHANGELOG.md", [("\n\n## [%s] — September 2026" % OLD, """

## [%s] — September 2026

**The activity data behind the estimates, published so it can be used on its own. NO NATIONAL
NUMBER MOVES.** Someone who wants Pakistan's livestock counts, fuel sales, fertiliser offtake or
plant-level generation should not have to run an emissions engine to get them, or be studying
emissions at all. Six collections leave the ingest tree as eight tables, 79,676 rows, under one
declared vocabulary.

- **Eight new semantic tables.** `fact_activity_fuel_sales_national` and `..._area` (OCAC's
  customer-class and monthly area pages, kept apart because OCAC never prints their joint
  breakdown), `..._livestock`, `..._crops`, `..._fertiliser`, `..._power_plants`,
  `..._power_monthly` and `..._household_fuel`. Each carries its aggregation rule and, in
  `closure`, the sentence a reader needs before adding two rows together.
- **Every row answers six questions on its own**: what the quantity is, where and when it applies,
  what kind of evidence it is, where it came from, what this project changed, and whether it may be
  combined. The ingest tree could answer none of them uniformly - 167 files, 937 distinct column
  names, 705 of them appearing exactly once, units baked into column names and status spread over
  more than sixty columns.
- **The judgements are five registers, not a melt function.** `data/activity_files.csv`,
  `activity_columns.csv`, `activity_evidence_classes.csv`, `activity_evidence_map.csv` and
  `activity_item_map.csv`. Every mapping from a source status to an evidence class carries its
  reason, because a judgement buried in code is one nobody can review.
- **An unmapped status fails the build.** Nothing falls back to `reported`: falling back is how
  `verified` - a statement about this project's TRANSCRIPTION, not about what the publisher offered
  - would come to be published as `observed`. The source's own word survives beside the class.
- **The separations that make the tables safe to reuse.** Tonnes of fertiliser product are never
  tonnes of nitrogen (an earlier draft of the register published all five of the 2024 nutrients as
  `t N`, which would have restated 996,000 t of phosphate and 6,579,000 t of urea product as
  nitrogen). Monthly power is GENERATION - the source never measured fuel monthly. A pooled
  district split by a declared rule is an ALLOCATION, and 1,562 crop rows say so rather than
  posing as observed district production. A projection is never summed with a count. An empty cell
  is typed `not_printed` and stays empty: an absence is not a zero.
- **Two ambiguities left visible.** PBS prints two rows under the truncated plant name "Sapphire
  electric company U" with the same month and different generation, 24 times; neither summing them
  (inventing a total nobody printed) nor dropping them (losing real generation) is honest, so both
  ship and `source_row` tells them apart. Seven crop rows carry real figures against a district
  that could not be identified; they are withheld, with the reason in the register, rather than
  published against a blank place.
- **Prose corrected against the generated catalogue.** README.md and docs/uncertainty_contract.md
  said 20 structural axes and 19 named configurations; `pakemis_product_facts.csv` says 22 and 27,
  and the files on disk agree with the facts.

Licensing is unchanged and was checked before a byte was published: 195 of 196 register rows carry
`derived_file_in_deposit = yes`, the documents themselves still ship nowhere, and the HIES rule -
microdata never redistributed, design-weighted aggregates always - is asserted by a test that walks
every published row back to its register entry.""" % NEW)], 1)

print("\nrc55 patched. Now: make national (or the regeneration tail), then the release fixpoint.")

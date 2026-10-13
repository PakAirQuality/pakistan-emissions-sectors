#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc56 from the rc55 tree.

    python3 scripts/mint_rc56.py [--dry-run]

Identical in shape to scripts/mint_rc55.py: a release candidate carries no DOIs; regenerated
sites are left to the build; only data/claims_registry.csv is bumped among the stamped
registries. No push, no tag, no upload.

rc56 MOVES NO NATIONAL NUMBER. It finishes the activity publication rc55 began: the three
collections left pending, and the sector datasets that belong beside them.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc55", "1.0.0rc56"
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
patch("CITATION.cff", [("v1.0.0-rc55", "v1.0.0-rc56")], 1)
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)], 1)
patch("paper_common/references.bib", [(OLD, NEW)], 6)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
patch("CHANGELOG.md", [("\n\n## [%s] — September 2026" % OLD, """

## [%s] — September 2026

**The activity publication finished: all nine collections, and the sector data beside them. NO
NATIONAL NUMBER MOVES.** rc55 published six collections; this adds the three it left pending -
industrial fuel and production, the gas tables, waste services and waste flows - and the three
datasets that belong in their sectors without a card of their own: railway fuel and traffic, airport
movements and passengers, and registered vehicles by district. Seventeen tables, 101,808 rows.

- **Nine new tables.** `fact_activity_industry_fuel`, `..._industry_production`, `..._gas_supply`,
  `..._gas_network`, `..._waste_services`, `..._waste_flows`, `..._railways`, `..._aviation`,
  `..._vehicles`.
- **A seventh evidence class, `modelled`**, and it is the first row in this collection that is not
  something a publisher printed. The waste flow ledger is a per-capita rate over an interpolated
  population panel and a fate partition; typing it `reported` would have been the most damaging
  label in the release, and the household survey published beside it reads a different split.
- **The separations this wave had to carry.** Printed TOTAL rows are withheld rather than published
  beside their own members, which is what a declared row filter is for. Unaccounted-for gas carries
  its source's own words - NOT AN EMISSION FIGURE AND MUST NEVER BE USED AS ONE - onto every
  published row. Registered vehicles are cumulative stock as at 30 June, not observed traffic and
  not an active fleet. The HIES `collected` and `uncollected` rows are sums of routes 1-3 and 4-7
  and are typed `derived`, not published as an eighth and ninth category beside their own parts.
  Company clinker is company-reported and is never allocated to plants, because nothing in this
  release allocates it. Aviation counts its fiscal year from the START, the opposite of the railway,
  waste and transport tables in the same collection, and the period basis says so on every row.
- **The feedstock/fuel split, which exists nowhere else.** Gas a fertiliser plant turns into ammonia
  is not gas it burns; NFDC prints them separately and this is the first release to publish the
  distinction.
- **What is deliberately NOT published.** Ten IPPU and industry working files - source manifests, a
  gap matrix, a readiness diagnostic, geocoding overrides, a plant register, a self-declared
  screening table and a third-party emissions series - are measurements of nothing. The PBS minerals
  panel is withheld because the file carries no unit anywhere and its mineral labels are uncleaned
  OCR, including one cell holding an entire unparsed table row. The QIM panel is filtered to the
  four mapped items on quantity rows: its index rows are index points on a 100 base, and 108 of them
  carry a one-column shift from the extraction.
- **UNEP MARS stays out.** The plume and source tables carry `LICENSE-CC-BY-NC-SA.txt` in their own
  banners - non-commercial and share-alike, incompatible with this release's CC-BY-4.0 either way -
  and the manifest already records them as rights-undetermined, evaluation-only.""" % NEW)], 1)

print("\nrc56 patched. Now: make national (or the regeneration tail), then the release fixpoint.")

#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc46 from the rc45 tree.

    python3 scripts/mint_rc46.py [--dry-run]

Modelled on scripts/mint_rc45.py and identical in shape: a release candidate carries no
DOIs, so the DOI sites the v1.0.0 script rewrites are left alone; regenerated sites - the
release cover, the manifest, the README banner, the .bbl - are left to the build. Only
data/claims_registry.csv is bumped among the stamped registries, because its stamp means
"the release this claim was checked against" and the mint re-checks it. No push, no tag,
no upload.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc45", "1.0.0rc46"
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
# The three sites test_release_identity found at rc44 and which stay covered here.
patch("CITATION.cff", [("v1.0.0-rc45", "v1.0.0-rc46")], 1)
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)], 1)
patch("paper_common/references.bib", [(OLD, NEW)], 6)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
patch("CHANGELOG.md", [("\n\n## [%s] — September 2026" % OLD, """

## [%s] — September 2026

**The revision release: activity controls from open data.** The twentieth review asked for
the inventory's remaining borrowed geography and modelled activity to be replaced with the
public series that carry them, and this release is that program: six gated waves, ONE
deliberate re-base, and every delta named. The national pins move for the first time since
rc39: **L 452.34662 -> 465.91851, S 447.21383 -> 460.78572 (+13.57189 Mt both)**, the entire
delta the industrial solid-fuel activation and its per-stream ledger sums exactly.

- **Industrial solid fuels enter the reference total** through the written
  `industrial_solid_fuels_1a2` activation gate: brick-kiln coal (+2.77584 Mt) and cement kiln
  coal (+10.79604 Mt) on the Finance Division Statistical Supplement 2024-25 Table 14.1(4)
  coal-by-consumer series (25 years, 118 cells checker-verified). Supply and consumption
  close to ~0.5 kt in eight of nine years, so the brick residual column absorbs all
  non-power/cement/household coal and the old 7.0 Mt typed refusal closes by identity. The
  one year that does not close (FY2015-16, by exactly the 204 kt brick vintage delta) adopts
  the balance-consistent PEY value, typed. The rc13 kiln screening (7.35 Mt) retires as the
  claimant; the measured reference year is a trough (1,129 kt brick coal vs 8,678 in
  FY2020-21).
- **Power on point support.** 17 more stations located (GEM GOGPT + bioenergy trackers, all
  TRACE-corroborated <=5 km); a 547-spelling plant-name crosswalk; the four pre-FY2019-20
  grid-coal years draw per-station pools from the generation panel instead of 100%%
  substitution; gas located share 0.50 -> 0.9658 and the letter follows the measurement
  (S2 -> S1). Two source defects typed rather than adjudicated: GOGPT's "Halmore" pinned on
  Habibullah's Quetta site, and JDW-III's three-way identity conflict.
- **Eight years of crop geography stop borrowing the reference year's map.** The PBS
  crop-by-district API yields district panels for all nine years and five crops; the
  agriculture allocation reads each period's own panel, controlled to the unchanged fiscal
  series so no national number moves. Agricultural `reference_shape_backcast` stream-years
  fall 256 -> 120 (livestock and fertilizer legitimately remain), verified by pattern hash.
  Sujawal's rice cell is corrupt at source in seven of nine years - excluded by pinned
  value, with an assertion that fires when PBS repairs it.
- **The F-gas bank goes species-resolved and stays outside the total.** Fourteen species
  from the UNDP RAC inventory (108 transcription checks) drive a bank-and-retirement model
  priced at blend-component GWPs: 5.854 Mt CO2e for the reference year, inside the old
  one-stratum bracket [2.3, 6.2]. 2.F's activation is an explicit rc47 review; the lanes
  (CRT / bank / Art.7 / EDGAR) remain contractually unblended.
- **The geography the registers always held.** The 130 World Bank flare sites (per-site
  annual volumes 2012-2025) become the allocation basis for the five field-sited fugitive
  segments, year-keyed; the two LNG FSRUs are located and the "0 of 2 located" refusal
  retired; the mapped disposal sites (56 OSM landfill polygons + 2 ClimateTRACE points)
  concentrate covered districts' waste within-district under the kiln coverage-mask
  pattern. Pure-uniform fugitive rows fall 171 -> 36. Every promoted letter was forced by
  the derived-class guard, not declared. Three defects that no closure test could see were
  caught by a provincial-marginal diff and killed before the gate: a flare cache key
  missing the stream's profile (gas segments briefly rode oil's provincial split), a waste
  surface built beside the district panel instead of from it, and an `or True` admitting 25
  wastewater plants into the disposal-site register.

Named and not closed: 2.F activation and the HIES disposal-route promotion (the same rc47
review); the livestock second census anchor; fertilizer province-month backfill; the
SPAM -> GCD rice allocator; transmission and distribution line geometry; the road raster.

## [%s] — September 2026""" % (NEW, OLD))], 1)
print("done; regenerate (strict build), then the gate WITHOUT the manifest checkout")

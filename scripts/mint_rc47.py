#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc47 from the rc46 tree.

    python3 scripts/mint_rc47.py [--dry-run]

Modelled on scripts/mint_rc46.py and identical in shape: a release candidate carries no
DOIs; regenerated sites are left to the build; only data/claims_registry.csv is bumped
among the stamped registries. No push, no tag, no upload.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc46", "1.0.0rc47"
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
patch("CITATION.cff", [("v1.0.0-rc46", "v1.0.0-rc47")], 1)
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)], 1)
patch("paper_common/references.bib", [(OLD, NEW)], 6)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
patch("CHANGELOG.md", [("\n\n## [%s] — September 2026" % OLD, """

## [%s] — September 2026

**The stabilization release.** The twenty-first review audited rc46 and returned ten
findings; three verification passes confirmed every one against the tree, several worse
than stated. This release fixes all ten under FROZEN national pins - not one reference
total moves - which makes its headline unusual: the scorecard gets WORSE where the old
numbers were flattering, and that is the point. Measurement, not regression.

- **The configuration double count is dead.** Three scope configurations kept adding
  their full screening estimates to a reference that already booked the measured coal:
  brick (+7.35) and captive (+1.31) are retired, cement re-priced as the model's net
  excess (+2.60), and a ratchet test now forbids any configuration from pricing mass the
  reference contains. The completeness ledger's negative unclaimed remainder - the
  arithmetic signature, shipped in plain sight - is gone.
- **The crop geography is real.** The pooled-district split that claimed a reference-year
  provenance had NEVER executed (a name-vs-id key mismatch made every split silently
  uniform); it is now uniform by declaration and allocation-inert. Twenty dropped
  mainland districts (~5.5%% of crop area) re-enter through canonical naming; the
  reference year reads the PBS panel instead of the MapSPAM proxy, with the disagreement
  shipped measured; field burning declines both panels and rides its own year's FIRMS
  raster.
- **Historical power is graded by measurement.** The four panel years' located share is
  computed (labelled-and-located over everything, blank rows in the denominator) instead
  of a None read as 1.0: FY2015-16..FY2017-18 regrade S1 to S2 wholesale, FY2018-19
  keeps its S1 because 0.97-0.98 earns it, and 13-18 Mt a year of genuinely unplaceable
  fuel is priced as events instead of renormalised onto located stations.
- **Mass rides its own evidence.** Fugitive segments pool only their own Field Type's
  flare sites (3.6 Mt was on the wrong field type); the waste coverage reports its
  measured located share (0.287 SWDS / 0.050 wastewater) instead of a silent 1.0;
  wastewater's served share sits at the 25 HydroWASTE plants, fractionally; and domestic
  aviation splits LTO from cruise the rail-recode way - the 16.5%% that burns at
  airports stays S1 there, the cruise remainder is booked at uplift provinces and NOT
  placed below them, because corridor weights without an OD matrix would be invented
  physics. 195 of 198 streams are gridded; the three cruise streams are the entire
  unallocated set (0.05%%).
- **Industry has geography at last.** All 22.58 Mt leaves S4: brick coal on the 11,272
  surveyed kiln points, cement coal on the geocoded clinker register, gas and liquids on
  built-up within their provincial shares - registers the repository held all along.
- **Transport reads its own years.** FY2021-22 and FY2022-23 get their measured OCAC
  provincial shapes (twelve direct monthly editions each, held and unread until now);
  the road-density raster is promoted from priced bracket to the petrol/diesel basis
  with built-up as the priced comparator; CNG stays urban on built-up.
- **The frames are settled.** The OCHA COD-AB 2022 vintage is landed and crosswalked
  (`pakemis_adm2_frame_2022.csv`: twelve of fourteen collision groups plus Larkana and
  Tor Ghar resolve) with the one re-rasterisation declared as v1.1's migration; the
  0.05-degree lattice's exact odd-parity 2x2 relationship to EDGAR ships as
  `pakemis_grid_0p1_edgar_aligned.nc` with its conservation identity asserted.
- **`pakemis_stream_support_ledger.csv`** is the audit's deliverable: one row per
  (period, stream) - mass, support, measured located share, priced remainders and the
  per-row monthly refusal - rectangular over the full panel with typed absence.

Named and not closed: the v1.1 ADM2 re-rasterisation (prepared, tested, deliberately not
performed in a release candidate); 2.F activation and the HIES disposal routes (the
standing review items); the livestock second census anchor; Keamari and Surab polygons.

## [%s] — September 2026""" % (NEW, OLD))], 1)
print("done; regenerate (strict build), then the gate WITHOUT the manifest checkout")

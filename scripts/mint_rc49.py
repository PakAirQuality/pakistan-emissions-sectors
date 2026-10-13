#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc49 from the rc48 tree.

    python3 scripts/mint_rc49.py [--dry-run]

Modelled on scripts/mint_rc48.py and identical in shape: a release candidate carries no
DOIs; regenerated sites are left to the build; only data/claims_registry.csv is bumped
among the stamped registries. No push, no tag, no upload.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc48", "1.0.0rc49"
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
patch("CITATION.cff", [("v1.0.0-rc48", "v1.0.0-rc49")], 1)
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)], 1)
patch("paper_common/references.bib", [(OLD, NEW)], 6)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
patch("CHANGELOG.md", [("\n\n## [%s] — September 2026" % OLD, """

## [%s] — September 2026

**The nine-year air spatial family.** The covered-sources air panel leaves the national
grain: nine fiscal years x seven species on the frozen 0.05-degree lattice, through the
greenhouse-gas cube's own dispatch - every pollutant mass rides the cell vector its
anchor stream was placed on for that period, so the grid, the ADM2 table and the ADM1
table are three marginals of ONE allocation and the identity
panel = grid = ADM1 = ADM2 + outside + unallocated_below_adm1 is asserted for all 126
(pollutant, period, configuration) cells, not a sample. National greenhouse-gas pins
are UNTOUCHED.

- **The supports were corrected before anything was gridded.** The railway air layer
  splits per traction stream (54 furnace-oil atoms had anchored a stream marked
  not_present for six of the nine periods; they now ride the non-traction yards stream
  that exists all nine - every pollutant total conserved to the bit, the FY2016
  traction furnace-oil rows ABSENT, not zero). Agriculture's 14 rows became 76 on the
  surfaces each mass actually leaves from: fertiliser NH3 per product, livestock NH3
  per (species, stage) - housing/storage on the volatilisation stream, application on
  organic manure, grazing on the two pasture streams - soil NOx as three N pools
  riding their own surfaces (the single row had put manure-N and residue-N on the
  fertiliser surface), residue burning per crop. A regrouping, byte-stable at every
  national total. A guard now refuses any (period, anchor) whose stream has no mass in
  the period's own atomic table: the registry join may never inherit dead geometry.
- **Uncertainty is invariant under the regrouping, and now provably.** The per-row
  independent Monte-Carlo draw would have silently HALVED the NH3 interval
  (+/-23.6%% to +/-12%%) by sqrt-N cancellation across sub-rows that share one factor
  family. The MC and its Approach-1 cross-check now draw per POOL (the key-category
  grouping, with the three soil-NOx pools folded onto their one shared emission
  fraction): five of seven pollutants reproduce the pre-split file bit-for-bit.
- **A second configuration for the nine years.** `S_HIES1925` joins the closed
  vocabulary: the survey-anchored dung series (HIES 2018-19 and 2024-25 per-household
  anchors, interpolated, flat before 2019, each year's basis labelled in
  `residential_configurations_by_year.csv`); the air panel, the fact table, `query_air`
  and the spatial family carry it at every grain, as separate files and slices, never
  summed; the greenhouse-gas engine refuses the new id everywhere.
- **The products.** Two physical-only NetCDFs on the shared frame
  (`pakemis_air_grid_0p05_annual_fy2015_16_fy2023_24.nc` and `..._survey_...`;
  `annual_grid.write_frame` is now one function for both families so the frames cannot
  drift - the greenhouse-gas cube reproduced byte-identically through the refactor),
  anchor-grain `pakemis_air_adm1_by_year.csv`, canonical-frame
  `pakemis_air_adm2_by_year.csv`, typed `pakemis_air_unallocated_by_year.csv` (the
  aviation cruise class, never zeros). The by-year tables carry the (period, stream)
  join key and NO evidence badge of their own - the badge is the weight registry's to
  derive from what the build DID - and the join ships:
  `pakemis_air_spatial_support_by_year.csv` (basis, proxy year, operator, pattern
  hash, grade as separate columns) and `pakemis_air_uncertainty_split_by_year.csv`
  (the activity/factor and spatial halves side by side, never combined).
- **Release mechanics live in the tree now.** `scripts/release_finish.sh` (receipts
  deposit-last -> fixpoint -> record -> package -> split, the ordering's WHY in
  comments) and `scripts/build_release_split.py` (fail-closed on the package's own
  exit codes; a per-release RELEASE_NOTES entry is REQUIRED - a version without notes
  refuses to split).

Named and not closed: semantic/query and explorer wiring of the by-year air family;
and beside this lane the standing acquisitions - the dung inter-round reconciliation,
the power/industry plant-unit-year control-equipment record, road-fuel sulfur
supply-weighting from the OGRA import shares, the HIES waste-route burn split - each
a gap-register row or coverage-matrix absence, none a silent omission.

## [%s] — September 2026""" % (NEW, OLD))], 1)
print("done; regenerate (strict build), then the gate WITHOUT the manifest checkout")

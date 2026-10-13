#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc59 from the rc58 tree.

    python3 scripts/mint_rc59.py [--dry-run]

Identical in shape to scripts/mint_rc58.py: a release candidate carries no DOIs; regenerated
sites are left to the build; only data/claims_registry.csv is bumped among the stamped
registries. No push, no tag, no upload.

rc59 MOVES NO NATIONAL GREENHOUSE-GAS NUMBER. The AIR panel's totals move: IPPU process pollutants
and fugitive NMVOC with flaring enter the covered air panel as provisional estimates from the same
source-class register industry rides; the kiln-frame spatial override is honoured; the seventeen
readable activity tables lose their redundant result_row_id.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc58", "1.0.0rc59"
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
patch("CITATION.cff", [("v1.0.0-rc58", "v1.0.0-rc59")], 1)
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)], 1)
patch("paper_common/references.bib", [(OLD, NEW)], 6)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
patch("CHANGELOG.md", [("\n\n## [%s] — September 2026" % OLD, """

## [%s] — September 2026

**The four things rc58 declared and did not build, in one mint. NO NATIONAL GREENHOUSE-GAS NUMBER
MOVES; the air panel's totals do.** IPPU process pollutants and fugitive NMVOC with flaring enter the
covered air panel as provisional estimates from the same source-class register industrial combustion
rides; the brick classes ride their own kiln-type frames in the spatial sink; the seventeen readable
activity tables carry one id, not two. The air PM2.5 pins move by exactly the two layers' particulate
(771.482 -> 771.873 Gg REF; 429.845 -> 430.235 S; the residential-only difference 341.637 is
unchanged); the covered NOx headline FY2022-23 moves 814.03 -> 819.81 kt.

- **The register is cross-module** (`data/air_source_classes.csv`, moved from
  `data/activity/industry/`; 40 classes over 19 physical sources): `computing_module` and
  `reporting_sector` now span industry, ippu and fugitives; the executor learns `ippu.nh3_kt`,
  `ippu.billets_kt`, `ippu.qim_tonnes:<item>`, `fugitives.activity:<anchor>`, `fugitives.flare_bcm`
  (the satellite calendar volumes blended half-and-half to the fiscal year, basis `calendar_blend`) and
  `transport.ocac_tonnes:MS:TOTAL_INTERNAL`; the factor loader learns per-product, per-gas-volume and
  per-oil-volume units. Whole-activity classes may coexist as DISTINCT PROCESSES on one quantity
  (refinery process species and refinery flaring both ride the feed); partitions still sum to one.
- **Acquired** (public, `data/raw/emep/`, `data/raw/epa_ap42/`, every attempt logged): EMEP/EEA 2023
  2.B (consolidated: 2.B.1, 2.B.2, 2.B.10.a), 2.B.7, 2.C.1, 1.B.2.a.i+b, 1.B.2.a.iv, 1.B.2.a.v,
  1.B.2.c; AP-42 13.5 (the 1995 reformat - the 2018 address 404s). AP-42 8.2 (urea) could not be
  fetched: every epa.gov address returned 403, logged. 52 factor rows added (163 total), each with page
  and digest; the inadmissible ones (2.B.10.a sector ratio for urea; 2.C.1 Tier 1 for the electric
  route; AP-42 13.5 heat-basis rows) are HELD, NOT CITED, with the reason on the row.
- **IPPU** (FY2023-24 NOx 5.1 kt, CO 15.9, NH3 0.75, PM2.5 0.10): ammonia synthesis on the NFDC
  tonnes behind the greenhouse-gas ammonia stream (2.B.1 Tier 1); electric-route steel on the QIM
  billets behind the steel stream (2.C.1 Tier 2 electric-arc rows, 200 percent declared on the
  particulate so the band reaches the uncontrolled Tier 1 held beside); Solvay soda ash on the QIM item
  read by name (2.B.7; no greenhouse-gas stream exists, the general-industry gas vector is a DECLARED
  geography proxy). Urea finishing, nitric acid, lime and glass are typed absent with their activity
  beside them; cement process particulate is an explicit IE pointer into the integrated kiln (gap
  air-ippu-cement closed).
- **Fugitives** (FY2023-24 NMVOC 80.3 kt, SO2 3.6, CO 1.2, NOx 1.2, PM2.5 0.29, BC 0.06): NMVOC per
  segment on the module's own volumes - gas exploration/production/processing on gross production
  (one summed factor, applied once), transmission and distribution on transmission throughput (one
  summed factor), domestic crude at the chapter's 1.16 m3/t, refining and storage on the module's
  refinery-feed proxy (the other-regions row; NOx, CO, SO2 and particulate from process units beside
  it), petrol depot, delivery and refuelling on OCAC's motor-spirit total (uncontrolled, the chapter's
  instruction for countries without Stage I/II; vehicle-side evaporation stays in transport). Field
  flaring on the satellite volumes at 1.B.2.c Tier 1 (density 0.85 kg/m3; SO2 at the chapter's 6.4 ppm
  because no flare-gas sulfur evidence is held; BC 24 percent of PM2.5 with its own wide range);
  refinery flaring per m3 of feed. Venting, post-meter NMVOC and LNG terminals are typed absent (gaps
  air-fugitives-venting, -composition, -segments; air-fugitives-flaring closed).
- **The kiln-frame override is honoured** (`pkinv.report.kiln_frame_vectors`,
  `pakemis_kiln_frame_adm2_by_type.csv`): the FCBK and zig-zag classes ride their own kiln-type frames
  (FCBK 9,959 kilns, hash d833193a0ff77be5; ZZ 1,329 incl. Balochistan's 16 pooled kilns, declared,
  hash 2589e78ae487f7fd), province marginal equal to the brick stream's shares by construction so ADM1
  does not move; the coal outside the surveyed frame is placed at ADM1 and typed unallocated below it
  (a second typed below-ADM1 class beside aviation cruise, 90 rows). The support ledger gains
  `spatial_frame` with each frame's own hash.
- **`result_row_id`**: the seventeen readable activity tables declare `id_column: Record ID`
  (`semantic_release.json` records it; the build asserts uniqueness) and carry one id.
- **EDGAR** (`pakemis_industry_air_edgar_comparison.csv`, two new column sets; catalogue rows
  mag-ippu-air-edgar, mag-fugitives-air-edgar): FY2021-22 fugitives NMVOC 1.46x EDGAR's 1.B.2, CO 0.98x;
  ippu NOx 1.26x EDGAR's 2.B+2.C; the flare sulfur and particulate and the ippu CO compare an estimate
  with EDGAR's near-absence (ratios in the tens to hundreds) and rank neither. Compared, never fitted;
  the registers are byte-identical across it.
- **Coverage**: ippu E for all seven core species; fugitives E for six (NH3 typed absent, the chapters
  decline it); nine new gap rows, two closed; the completeness ledger, supplement, limitations, release
  limitation texts, the query engine's air sectors and the assurance figure follow, held together by
  `tests/test_air_prose_drift.py`.
- **Renamed**: `industry_air_pollutants_fy2015_16_fy2023_24.csv` ->
  `pakemis_air_source_classes_fy2015_16_fy2023_24.csv` (+ `sector_id`),
  `pakemis_air_industry_uncertainty_by_year.csv` -> `pakemis_air_source_class_uncertainty_by_year.csv`,
  semantic `fact_air_industry` -> `fact_air_source_classes`.""" % NEW)], 1)

print("\nrc59 patched. Now: make national (FULL - the version-stamped products), then goldens, receipts, the release fixpoint.")

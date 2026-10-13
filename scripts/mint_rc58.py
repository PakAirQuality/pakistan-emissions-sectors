#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc58 from the rc57 tree.

    python3 scripts/mint_rc58.py [--dry-run]

Identical in shape to scripts/mint_rc57.py: a release candidate carries no DOIs; regenerated
sites are left to the build; only data/claims_registry.csv is bumped among the stamped
registries. No push, no tag, no upload.

rc58 MOVES NO NATIONAL GREENHOUSE-GAS NUMBER. The AIR panel's totals move: industrial combustion
enters the covered air panel as a provisional estimate (industry atoms in every period), captive
self-generation is reported once, under industry, and leaves the power screening.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc57", "1.0.0rc58"
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
patch("CITATION.cff", [("v1.0.0-rc57", "v1.0.0-rc58")], 1)
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)], 1)
patch("paper_common/references.bib", [(OLD, NEW)], 6)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
patch("CHANGELOG.md", [("\n\n## [%s] — September 2026" % OLD, """

## [%s] — September 2026

**Industrial combustion enters the covered air panel. NO NATIONAL GREENHOUSE-GAS NUMBER MOVES; the air
panel's totals do.** Through rc57 the air panel covered six sectors and typed industry, IPPU and fugitives
NE, so "the largest source" of PM2.5 meant the largest of six. The assistant said it bare. The user's
admission rule - a defensible activity basis, an applicable factor for the actual source class, an explicit
process boundary and documented assumptions, with uncertainty - is now met source class by source class,
and the result is inside the panel as a provisional estimate: FY2023-24 industry NOx 143 kt, SO2 138 kt,
CO 99 kt, PM2.5 13.3 kt, NMVOC 11.7 kt, BC 5.5 kt, uncertainties 47-70 percent. The air PM2.5 pins move
by exactly that (758.219 -> 771.482 Gg REF; 416.582 -> 429.845 S; the residential-only difference 341.637
is unchanged).

- **Every factor chapter the earlier screening called "not held" was public and is now held**
  (`data/raw/emep/`, `data/raw/epa_ap42/`, `data/raw/edgar/`; every attempt logged in
  `data/raw/ACQUISITION_LOG_industrial_air.csv` - the first-guess addresses all 404'd). EMEP/EEA 2023
  1.A.2, 2.A.1, 2.A.2, 2.A.3, 2.A.5.c, 2.A.6; AP-42 1.3, 1.4, 3.2, 3.3, 3.4, 11.3, 11.6, 11.17; EDGAR v8.1
  SO2, CO, NMVOC, NH3, BC.
- **`data/air_emission_factors.csv`**: 111 factor rows as their sources print them - unit, activity basis,
  equipment, control state, particulate basis, sulfur/ash scaling, rating, document, table, page and
  digest. A held row without a page fails the build; an absent row is a typed NE a class may cite.
- **`data/activity/industry/industrial_air_sources.csv`**: 22 source classes over six physical sources
  (`data/physical_sources.csv`), each burning the ENGINE's own quantity - OGRA gas, OCAC liquids, HDIP coal,
  the cement engine's clinker, the power module's captive gas. Shares of one activity sum to one (tested);
  declared shares say so and name the acquisition that would replace them. Control posture: source-class
  typical (cement kilns carry the particulate collection inherent to clinker production; boilers, engines
  and brick kilns are uncontrolled).
- **SO2 is a sulfur balance on DATED evidence** (`data/activity/industry/fuel_sulfur_evidence.csv`): the
  HSFO grade mix, the diesel regime by year, Punjab coalfield ranges for brick coal. Thar lignite - the
  rc57 screening's proxy for every fuel - is inadmissible for brick and cement coal by register. A class
  whose evidence is not valid for a year gets a typed absence for SO2, never a zero.
- **Double counting refused by construction**: cement gas and HDIP's cement-coal column are IE into the
  clinker-based integrated kiln (a kiln is never also a boiler); captive oil is IE into the OCAC liquids;
  captive gas is priced once, under industry (IPCC 1.A.2), and the power screening is grid-only; the three
  brick classes (FCBK, zig-zag, outside the surveyed frame) partition HDIP's brick coal exactly.
- **Typed absences with their activity beside them**: NH3 for every fuel (EMEP lists it not estimated),
  other-industry coal inside HDIP's cement column, captive solids, industrial bagasse - five new gap rows.
- **The coverage matrix's absences are data** (`data/air_coverage_absences.csv`); a cell nobody types fails
  the build. Six descriptions of the layer that disagreed (matrix, ledger, axis, power table, supplement,
  limitations) are held to each other by `tests/test_air_prose_drift.py`, written to fail on rc57.
- **Three views**: Lahore District by sector beside the national unplaced remainder
  (`pakemis_air_lahore_by_year.csv`), calendar 2023 composed from two fiscal years on the monthly cube's
  own shares (`pakemis_air_industry_cy2023.csv`), and EDGAR v8.1 at matched years - a comparison, never a
  fit; the registers are held byte-identical across it (`pakemis_industry_air_edgar_comparison.csv`:
  FY2021-22 NOx 1.14x, PM2.5 0.65x, SO2 2.35x, CO 0.19x EDGAR's fossil 1.A.2).
- **Retired**: `industry_air_screening_fy2015_16_fy2023_24.csv` and its module; superseded by the estimate.
- **Declared, not yet built**: the kiln-frame spatial override (FCBK/ZZ typing of the kiln-point pattern;
  the unmapped remainder typed unallocated below the province) - rc59, with IPPU process pollutants;
  fugitive NMVOC and flaring - rc60.""" % NEW)], 1)

print("\nrc58 patched. Now: make national (or the regeneration tail), then the release fixpoint.")

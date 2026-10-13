#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc48 from the rc47 tree.

    python3 scripts/mint_rc48.py [--dry-run]

Modelled on scripts/mint_rc47.py and identical in shape: a release candidate carries no
DOIs; regenerated sites are left to the build; only data/claims_registry.csv is bumped
among the stamped registries. No push, no tag, no upload.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc47", "1.0.0rc48"
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
patch("CITATION.cff", [("v1.0.0-rc47", "v1.0.0-rc48")], 1)
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)], 1)
patch("paper_common/references.bib", [(OLD, NEW)], 6)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
patch("CHANGELOG.md", [("\n\n## [%s] — September 2026" % OLD, """

## [%s] — September 2026

**The air-pollutant panel release.** The seven air species (BC, CO, NH3, NMVOC, NOx as
NO2, PM2.5, SO2) leave their single reference year: a nine-fiscal-year covered-sources
panel (FY2015-16..FY2023-24), built the way the greenhouse-gas national series is built
- each sector's own air engine per year under its own fiscal convention, never a
national total distributed downward. National greenhouse-gas pins are UNTOUCHED.

- **The atomic ledger** (`pakemis_air_atomic_annual.csv`): 2,790 atoms at period x
  sector x category x process x species in Gg, each carrying its activity basis, its
  factor source and its own source-stream anchor, fail-closed through the air join.
  The rollup (`pakemis_air_annual_fy2015_16_fy2023_24.csv`) declares
  `coverage_scope=covered_sources_only` on every row: this is NOT a complete national
  seven-species inventory and does not claim to be.
- **Coverage as a product** (`pakemis_air_coverage_matrix.csv`): all 630 period x
  module x species cells typed under the closed IPCC notation keys - 360 estimated,
  270 typed absences each carrying its reason and gap row. A missing estimate is its
  key, never a zero. Power runs the same nine years as the UNCONTROLLED screening
  scenario it declares itself to be, shipped BESIDE the panel
  (`power_air_screening_fy2015_16_fy2023_24.csv`), never inside it.
- **Road transport re-based on cited factors.** The exploratory Punjab-workbook
  diagnostic (uncited g/km, one anchor per fuel, no BC, exhaust only) is replaced by
  the EMEP/EEA guidebook 2023 Tier 1 chapters - held under sources/EMEP, 204
  transcribed cells verified against the chapters' own text - with fuel reconciled to
  the OCAC Road control by construction and four processes as separate atoms (exhaust,
  evaporative NMVOC, tyre-and-brake and road-surface wear). BC exists for the first
  time; SO2 is sulfur stoichiometry under a declared per-year regime with the cited
  Euro-II (Jan 2017) and Euro-V (Jan 2021) import-mandate boundaries; every row anchors
  its own vehicle class's stream. FY2023-24 totals move as a declared re-base (NOx
  172.1 kt was 112.7; CO 1430.4 was 3588.2; PM2.5 8.2 was 21.6), the old-vs-new
  comparison printed in the paper with the superseded column frozen in the registries,
  and the residential-to-road particulate ratio re-based to 109 (L) / 50 (S) on the
  exhaust definition with Tier 1's own uncontrolled-to-modern spans as its honest width.
- **The engines honour the year they are asked about.** Power's air layer takes the
  same three-regime lignite share the CO2 side burns (no Thar lignite before the fleet
  existed), passes bagasse its year and captive the fiscal-END year the OGRA panel is
  keyed on; railways SO2 burns each year's own declared diesel sulfur (0.5 percent
  before the January 2017 Euro-II import mandate - FY2015-16 is 1.23 kt against the
  0.12 a flat modern spec would claim); residential's series slice generalises from
  PM2.5 alone to every species, absent - never zero - where the reference emits none.
- **The panel is servable.** `fact_air_panel` enters the semantic layer on real fiscal
  period ids (plain foreign keys - the CY2024 column escapes are single-year-layer
  only), and `query_air` answers fiscal-period questions with the covered-sources
  limitation verbatim on every envelope and three typed refusals (periods below
  national grain; years and periods together, which are two time bases; a period
  grouping without periods). Two goldens freeze the first answers, the SO2 series'
  Euro-II step among them.
- **A dead column came back to life.** `pakemis_stream_support_ledger.csv` shipped
  `emissions_Gg=0.000000` on every one of its 1,753 present rows - the builder read a
  column name the atomic table does not have, and the closure test checked only the
  co2e column beside it. The builder now reads `emission_native_mass` and a closure
  test refuses a dead mass column outright.
- **Beside this release's own lane**, the external verification bundle became the
  whole package (its own commits): per-sector archives plus a `_common.zip` carrying
  every outputs file, a four-stage derivation chain per sector, and a withheld-files
  register so nothing this project may not republish ships by accident.

Named and not closed: the air spatial-by-year and NetCDF family, monthly pollutants,
air engines for industry, IPPU and non-flare fugitives, the flare submodule, controlled
power (`air-power-controlled`), the livestock fiscal enumeration, and the residential
LPG/kerosene/coal archive transcription - each a typed absence in the coverage matrix
or a gap-register row, none a silent omission.

## [%s] — September 2026""" % (NEW, OLD))], 1)
print("done; regenerate (strict build), then the gate WITHOUT the manifest checkout")

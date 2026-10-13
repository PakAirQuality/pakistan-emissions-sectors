#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc51 from the rc50 tree.

    python3 scripts/mint_rc51.py [--dry-run]

Modelled on scripts/mint_rc50.py and identical in shape: a release candidate carries no
DOIs; regenerated sites are left to the build; only data/claims_registry.csv is bumped
among the stamped registries. No push, no tag, no upload.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc50", "1.0.0rc51"
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
patch("CITATION.cff", [("v1.0.0-rc50", "v1.0.0-rc51")], 1)
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)], 1)
patch("paper_common/references.bib", [(OLD, NEW)], 6)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
patch("CHANGELOG.md", [("\n\n## [%s] — September 2026" % OLD, """

## [%s] — September 2026

**The industrial boundary, Wave A: what the Industry bar is, said plainly; the same atoms
regrouped by what they are; two repairs.** No reference number moves and the pins are
untouched. The Analyze waterfall's Industry bar is the industry MODULE - IPCC 1.A.2 direct
industrial fuels (the official HDIP coal allocation, OGRA's industrial gas, OCAC's industry
liquids) - and it was labelled as if it were Pakistan's industrial sector. Captive generation
(1.A.2, computed by the power module) and cement process CO2 (2.A.1) were never inside it.

- **The contract's limitation text.** `industry_reported_fuel_series` now leads with the
  reading the bar deserves: "Covered industrial-combustion emissions fell, reflecting lower
  recorded fuel use. This does not mean Pakistan's total industrial emissions declined;
  several industrial sources are reported elsewhere or remain outside the inventory." - then
  the reported-fuel caveat as before. The Explorer labels the module "Industrial fuel use -
  covered sources" (short form "Industrial fuel use" mid-sentence and on an axis).
- **The economic-sector view.** `group_by: ["economic_sector"]` is a derived group key of the
  query core (`pakemis_query.engine.ECONOMIC_SECTOR_SQL`): the same fact_annual atoms grouped
  by what the IPCC code says the activity IS - 'industrial' = 1.A.2 exactly or its children
  (so the captive generation the power module computes is inside, and railways' unresolved
  '1.A.2/1.A.4.c' is not) plus every 2.x process category; every other sector keeps its
  module. Additive with the IPCC view every period, and its industrial aggregate reproduces
  the boundary ledger's priced total to the ledger's own rounding (59.54 Mt in FY2015-16,
  49.95 in FY2023-24: -9.60). A new limitation, `economic_sector_view`, says what that
  aggregate does NOT contain - ammonia and nitric acid process emissions, HFCs and SF6, iron
  and steel, lime, glass, lubricants and industrial wastewater are screened or absent, and each
  enters only as a full FY2015-16..FY2023-24 series, never in the reference year alone
  (adding them to FY2023-24 alone would manufacture about +12 Mt of "growth"). The view is
  labelled "covered direct industrial sources" until that back-cast is complete. No fact
  column was added: the rule lives in one place and is held to the ledger by test.
- **A repair to the rc50 bridge.** `pakemis_industrial_coal_bridge.csv` read the "official"
  2.A.1 emissions from the atom table, which after the re-base already carried the re-based
  value, and then added the delta a second time (FY2015-16 printed official 17.779 and
  reconstructed 21.743 Mt; correct 13.815 and 17.779). Both ends are now computed from the
  clinker quantities and the reconstructed end is held equal to the reference atom by test;
  the builder is invariant to build order. National numbers were never affected.
- **The nine-year EDGAR diagnostic.** EDGAR's Pakistani Industrial Combustion and Processes
  rows (every gas, 2015-2024) are extracted from the held 2025 booklet to
  `data/activity/industry/edgar_pak_industry_series.csv`, and
  `pakemis_industry_edgar_divergence.csv` sets the engine's 1.A.2 (industry + captive) and
  its covered industrial aggregate against EDGAR at the fiscal blend for all nine years. At
  the blend the two 1.A.2 series differ by -4.6..+6.6 Mt with alternating sign from FY2015-16
  through FY2021-22, then the engine falls 17.9 and 17.5 Mt below EDGAR in FY2022-23 and
  FY2023-24 - the two years HDIP's power allocation sits above NEPRA's metered burn. The
  boundary ledger carries one diagnostic row per period from it. EDGAR is IEA-balance-derived
  and HDIP-fed upstream and its 2023-2024 columns are preliminary: a diagnostic of where the
  compilations part, never an independent verification, never a residual. The reference-year
  EDGAR benchmark note, which still described the engine as "gas and liquid fuels only" four
  releases after coal entered, is rewritten to the rc50 boundary.

## [%s] — September 2026""" % (NEW, OLD))], 1)
print("done; regenerate (strict build), then the gate WITH --after-mint")

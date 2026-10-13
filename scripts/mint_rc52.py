#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc52 from the rc51 tree.

    python3 scripts/mint_rc52.py [--dry-run]

Modelled on scripts/mint_rc51.py and identical in shape: a release candidate carries no
DOIs; regenerated sites are left to the build; only data/claims_registry.csv is bumped
among the stamped registries. No push, no tag, no upload.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc51", "1.0.0rc52"
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
patch("CITATION.cff", [("v1.0.0-rc51", "v1.0.0-rc52")], 1)
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)], 1)
patch("paper_common/references.bib", [(OLD, NEW)], 6)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
patch("CHANGELOG.md", [("\n\n## [%s] — September 2026" % OLD, """

## [%s] — September 2026

**The industrial boundary, Wave B and C: the evidence products, and THREE CATEGORIES ENTER THE
REFERENCE.** The second deliberate re-base of the boundary program. Ammonia (2.B.1), iron and steel
(2.C.1) and lubricant use (2.D.1) enter the reference as full FY2015-16..FY2023-24 series, each
through its gate (data/scope_registry.csv): the national totals move in every year (the ledger is
in the commit message and scripts/check_pins.py), by +3.72 Mt in FY2023-24 (469.64 from 465.92).

- **Ammonia, Tier 1 calibrated.** NFDC production by product and fiscal year (a new ingest,
  data/nfdc/nfdc_production_by_product_series.csv, every year closing on its printed total and
  identical across editions) x the NH3 embodied per product x the Pakistan-calibrated 1.815 t
  CO2/t NH3, net of the CO2 recovered into urea (44/60). 2.73 Mt in FY2015-16, 3.24 in FY2023-24;
  the method envelope (1.694..2.104) stays beside it in pakemis_ammonia_nitric_series.csv and the
  four-pathway reconciliation stays diagnostic. The `ammonia_feedstock_in_scope` configuration is
  retired - the mass is in the reference. Plant-level output and recovered CO2 for every plant
  is the Tier 2 step, named.
- **Iron and steel, Tier 1 EAF.** QIM billets and ingots (the year's own twelve months) x IPCC
  Table 4.1's 0.08 t CO2/t; pig iron is zero from FY2016-17, so the electric route is the only one
  operating. 0.25 Mt in FY2015-16, 0.39 in FY2023-24; the scrap/DRI split is named in the
  uncertainty.
- **Lubricant use, Tier 1 ODU.** OCAC's sectoral sales of non-energy products (a new ingest,
  data/activity/industry/ocac_non_energy_sectoral.csv, 2,846 cells FY2015-16..FY2024-25) - LUBES
  and GREASES grand totals x NCV 40.2 x 20.0 t C/TJ x ODU 0.2/0.05 x 44/12. 0.05..0.10 Mt.
- **What stays outside, and why.** Nitric acid: a PAIR per year (unabated/abated) on a
  nitrate-derived activity - abatement operation after 2022 is undocumented, so no central. Soda
  ash: NA in IPPU for a Solvay country (IPCC Vol 3 s3.8.3.1 allocates the emissions to the coke) -
  the earlier natural-process ceiling was the wrong method. HFCs: the first STOCK-based band, from
  HIES 2018-19 and 2024-25 ownership (data/activity/ippu/hies_appliance_ownership.csv) x IPCC
  Table 7.9 ranges - the household bank's operating losses reach a few tenths of a Mt against
  Annex F consumption of 7-10 Mt CO2e a year, so the supply cannot be absorbed by household
  equipment (commercial and industrial banks are unsurveyed). Industrial wastewater: a band over
  IPCC's own W, COD and MCF ranges (sugar, paper), coded Waste.
- **The brick question, narrowed by HDIP's own footnote.** The PBS Compendium on Environment
  Statistics reprints HDIP's coal-by-sector table with its footnote: the brick-kiln column is
  "Estimated by deducting other uses of indigenous coal from the total production" - a RESIDUAL of
  domestic production by construction. The new by-province ingest (PBS minerals, every table
  closing to the tonne; Sindh 1.49 -> 14.67 Mt on the Thar ramp) gives the coal balance a third
  test: in FY2019-20 and FY2020-21 the official brick residual EXCEEDS all coal mined outside the
  Thar plants' burn by 3.5 and 3.1 Mt - not domestic coal under HDIP's own definition. Read at
  CCAC's one held brick output (82.5 billion, 2018), the official tonnage implies 14 g of coal
  per brick in FY2023-24 against 70-100 g by kiln type. pakemis_brick_coal_alternatives.csv
  carries the alternatives with no central; the official series stays booked.
- **Also.** UNSD per-period rows beside EDGAR's in the boundary ledger; the OGRA class extension
  is a typed negative (no captive-textile class, feed/fuel only in the tariff section); IPCC 2006
  Vol 3 Ch 3/4/5/7 and Vol 5 Ch 6 acquired; the monthly minerals ingest's COAL rows are found to
  mis-attribute other minerals' rows in several editions (registered; no shipped number reads them). BUILD-ORDER DEBT, named: the validation catalogue's freshness gate (2-hour slack against the national totals sentinel) runs BEFORE the boundary-program phases that it grades, so a build more than two hours after their last run fails on them until they are regenerated by hand - the gate should follow those phases or grade them by their own phase; not fixed this release.

## [%s] — September 2026""" % (NEW, OLD))], 1)
print("done; regenerate (strict build), then the gate WITH --after-mint")

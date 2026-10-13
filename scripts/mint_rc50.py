#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc50 from the rc49 tree.

    python3 scripts/mint_rc50.py [--dry-run]

Modelled on scripts/mint_rc49.py and identical in shape: a release candidate carries no
DOIs; regenerated sites are left to the build; only data/claims_registry.csv is bumped
among the stamped registries. No push, no tag, no upload.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc49", "1.0.0rc50"
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
patch("CITATION.cff", [("v1.0.0-rc49", "v1.0.0-rc50")], 1)
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)], 1)
patch("paper_common/references.bib", [(OLD, NEW)], 6)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
patch("CHANGELOG.md", [("\n\n## [%s] — September 2026" % OLD, """

## [%s] — September 2026

**The industrial-coal reconstruction, and the clinker re-base.** The Analyze waterfall's
Industry (1.A.2) bar read -11.69 Mt over FY2015-16 -> FY2023-24 on HDIP's coal-by-consumer
allocation - an '** Estimated' series the engine reproduces exactly. Matching the official
table closes the transcription question and not the inventory-quality one, so this release
holds that diagnosis OPEN with held evidence and moves only what the evidence supports. ONE
deliberate re-base, and it is not the coal: the national pins are UNTOUCHED (FY2023-24's
cement is the audited census already); the eight historical 2.A.1 values move.

- **The clinker basis is promoted (decision-rule row 2).** The 16-company producer census
  implies a clinker-in-cement fraction of 0.965 (derived from the census balance, never
  typed; GEM's 30-of-32 plants at 0-5 percent substitution corroborate; IPCC's all-portland
  0.95 brackets it). Applied to the eight earlier years in place of the IPCC blended-cement
  default 0.75 it removes the +9,027 kt FY2022-23 -> FY2023-24 method break the splice had
  manufactured (to +109 kt) and raises 2.A.1 by +3.96..+5.57 Mt a year, +37.1 Mt in total.
  One clinker series now serves process CO2 and the cement kiln-fuel activity. The fraction
  is one held quantity, typed `persists` and scoped - but NOT yet bound as a shared draw: a
  scope rule binds by stream, not by year, and the census year does not multiply the
  fraction, so binding it would over-declare FY2023-24's width. Its 2.5 percent therefore
  still sits in the per-year residual this release; a year-conditional scope binding is
  named debt, not closed.
- **Brick, cement and other industrial coal stay on the official series - bounded (row 3).**
  Production evidence exists; fuel evidence does not. Cement kiln coal is reconstructed as a
  band (K x H x s / NCV; H, s and NCV transferred - zero of sixteen held company reports
  prints coal tonnage or kiln heat); the HDIP "Cement" column - printed "Cement/Others" by
  the Economic Survey and "Cement/Other Industry" by the PEY - sits ABOVE that band by
  1.4-6.4 Mt of other-industry coal in FY2016-19 and FY2021-22 and inside it in FY2023-24.
  Brick has no held production or intensity. The power seam (NEPRA's metered burn against
  HDIP's estimate) flips sign across the window and would lower the FY21 peak and raise the
  FY24 trough, but "production minus Thar burned" cannot separate non-Thar brick coal from
  Thar stockpile without by-field production, and FY2023-24 supply is publisher-flagged
  partial. Every band is published beside the official value; no central is manufactured;
  the label "Industry: reported-fuel estimate" and its caveat stay.
- **The evidence products.** `coal_supply.csv` (two production lanes, the partial-period
  footnotes per row), `unsd_coal_supply_control.csv` (the one independent supply control),
  `pakemis_coal_source_reconciliation.csv`, `pakemis_coal_balance.csv` (H1/H2 tested per
  year: the supply-origin allocation matches in four of ten years and breaks in five),
  `pakemis_cement_kiln_coal_reconstruction.csv`, and `pakemis_industrial_coal_bridge.csv`
  (official -> activity -> fuel-quality -> boundary -> reconstructed, with the identity
  dE_new = dE_official + dE_end - dE_start as a band).
- **Acquired.** Economic Survey 2025-26 ch.14 Energy and ch.3 Manufacturing (Table 3.11 -
  the document the fugitives ingests cited but did not hold). The Statistical Supplement
  2025-26 is unpublished; the FY2024-25 brick figure cannot yet be verified.

Named and not closed: by-field coal production (the one acquisition that separates
non-Thar brick coal from Thar stockpile); fired-brick production and coal-per-brick by kiln
technology (PBS Compendium on Environment Statistics 2020); plant kiln heat and coal share
(the extended IPPU-CEM-01 request); the FY2023-24 monthly import series for the coverage
audit; the Supplement 2025-26.

## [%s] — September 2026""" % (NEW, OLD))], 1)
print("done; regenerate (strict build), then the gate WITH --after-mint")

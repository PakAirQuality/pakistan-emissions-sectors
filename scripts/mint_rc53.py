#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc53 from the rc52 tree.

    python3 scripts/mint_rc53.py [--dry-run]

Identical in shape to scripts/mint_rc52.py: a release candidate carries no DOIs; regenerated
sites are left to the build; only data/claims_registry.csv is bumped among the stamped
registries. No push, no tag, no upload.

rc53 MOVES NO NATIONAL NUMBER. It is a diagnosis release: the industrial decline is taken apart
into the channel that produced it, the boundary the bar is drawn on is corrected in the reporting
axis, and the decision record adopts nothing.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc52", "1.0.0rc53"
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
patch("CITATION.cff", [("v1.0.0-rc52", "v1.0.0-rc53")], 1)
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)], 1)
patch("paper_common/references.bib", [(OLD, NEW)], 6)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
patch("CHANGELOG.md", [("\n\n## [%s] — September 2026" % OLD, """

## [%s] — September 2026

**The industrial boundary, the diagnosis release: WHY the series falls, and what is not established.
NO NATIONAL NUMBER MOVES.** rc52 expanded what the inventory calculates. rc53 asks the prior
question - is the fall in reported industrial fuel physical, a reporting change, incomplete
coverage, or a combination - and answers it per channel, per stream and per year, without
correcting a single value until something earns it. Nothing does.

- **The source-vintage ledger.** HDIP's coal-by-sector allocation is published more than once per
  reference year and the prints differ, so every published print is now a row
  (data/activity/industry/coal_by_sector_vintages.csv, 303 prints across nine editions) with
  reference year, publication year and REPORTING-PERIOD LENGTH as separate columns - a nine-month
  July-March figure can never be differenced against a full year.
  pakemis_coal_vintage_ledger.csv pairs consecutive prints and classifies what moved. TWO
  REALLOCATIONS are in the record: July-March FY2023-24 moves 1,500 kt from brick kilns to
  cement/others between two Economic Survey editions with power and the total unchanged, and
  full-year FY2024-25 moves 133 kt back. Neither is a change in consumption, neither touches a
  booked endpoint, and brick + cement/others is INVARIANT across both - so reversing one would
  redistribute between subsectors and repair no industrial total. Also found: the Supplement folds
  the Pak Steel column into "Cement" (FY2013-14 and FY2014-15, to the tonne; the column is zero
  from FY2015-16, so no reported year carries it, but "Cement" has never meant cement alone).
- **The booking policy is now declared data.** data/coal_booking_policy.csv names the estimate the
  engine books for each year and consumer, with its reason, replacing a rule inside
  sectors/industry/solid_fuels.py plus one hard-coded override. It refuses July-March prints and
  reproduces rc52's booked values to the gram. It also makes a method transition visible: the brick
  series is NOT single-vintage - FY2015-16 books the older print because the Supplement's revision
  breaks the supply balance - a transition IPCC 2006 Vol 1 Ch 5 (acquired this release) requires be
  documented and tested rather than hidden. It is worth 0.50 Mt on the measured decline.
- **Where the decline comes from.** pakemis_industrial_change_attribution.csv splits the FY2015-16
  to FY2023-24 change in every priced 1.A.2 stream into the channel that produced it, with only the
  booked rows summing to the published change and counterfactuals never added to it. THE HEADLINE
  IS UNCOMFORTABLE AND STANDS: the industry MODULE falls 11.69 Mt while IPCC 1.A.2 - including the
  captive self-generation the power module computes - falls 13.63. Correcting the boundary makes
  the decline LARGER, not smaller, because captive generation fell too.
- **The reporting-sector axis.** A stream is now filed where IPCC 2006 reports it, beside the
  module that computes it: data/stream_reporting_sector.csv declares `reporting_sector` per stream
  and the column rides source_streams -> atoms -> months -> ADM1 -> fact_annual/fact_monthly/
  dim_stream. One row differs - captive gas self-generation reports under industry - and the axis
  is ADDITIVE with sector_id in every period, so the power bar loses exactly what the industry bar
  gains and no mass moves. The economic-sector view is re-expressed on top of it, so "industrial"
  is the industry and ippu reporting sectors by construction rather than by a second code rule.
  The district tables are module-resolved upstream and so do NOT carry the column: the axis is
  REFUSED at ADM2 rather than answered with the module, because answering would return the industry
  module alone and silently drop the captive generation the axis exists to include.
- **The coal account closes; the division does not.** The national coal balance now writes the
  identity out with its residual RETAINED as a column (exports and stock change typed, never
  zeroed), carries the power lane as a BAND from NEPRA's metered burn to HDIP's allocation so
  industry is not made to absorb the seam, and adds an origin-resolved energy account. Per year:
  FY2019-20 and FY2020-21 read MISDIVIDED between users - the tonnage closes while the brick column
  exceeds all domestic coal mined outside the Thar plants' burn - and the other metered years
  CLOSE. Two honesty guards ride with it: the tonnage closure is labelled a TRANSCRIPTION CHECK
  because the two published tables balance by construction, and the energy residual is reported as
  a WIDTH (44-71 percent of supply energy) because two of its three calorific values are IPCC
  defaults and the test cannot fail.
- **Brick kilns, from a counted fleet instead of a residual.** Six documents acquired.
  pakemis_brick_activity_reconstruction.csv estimates this stream for the first time without
  reading HDIP's own column: an association kiln census (10,394 operating in Punjab, November 2020)
  times a 440-kiln baseline survey (328.2 t per kiln-year) gives 3.41 Mt for Punjab, 3.94 Mt
  scaled nationally. THE OFFICIAL COLUMN RUNS FROM 0.29x THAT LEVEL IN FY2023-24 TO 2.21x IN
  FY2020-21 - a factor of 7.7 - while the counted fleet does not move. The 70-100 g of coal per
  brick carried here until rc52 APPEARS IN NO HELD DOCUMENT and is retired, replaced by measured
  Pakistani values: 184 g per brick for fixed-chimney kilns and 155 for zig-zag, 60 kilns in
  Faisalabad, 2023. Two independent sources agree on that intensity and disagree on SCALE by a
  factor of three, so the level is a band with no central, and the implied-intensity reading now
  names its own denominator bias.
- **Cement, tested against the producers' own books.** Sixteen held annual reports yield a
  company clinker series and a TYPED NEGATIVE: none of them discloses kiln thermal energy under
  about 35 patterns, so the reconstruction's heat term stays transferred rather than measured.
  Two tests became possible anyway. Fourteen companies print both FY2022-23 and FY2023-24, and
  their matched clinker agrees with this release's census-derived back-cast to 1.46 percent - the
  first independent test that basis has had. And HDIP's FY2023-24 cement column, at a 100 percent
  coal share, implies 2.70 GJ per tonne of clinker, BELOW the 2.85 GJ/t design floor of the most
  efficient line any held source names: in the reference year that column cannot cover cement's
  own kiln fuel, so it holds no other industry and is short.
- **The decision record adopts nothing.** pakemis_industrial_coal_decision.csv scores every
  candidate against four tests in every year. None beats the official series on all of them, so
  every official value stays booked and the pins do not move: L 469.63822 / S 464.50543, unchanged
  from rc52. The brick candidate beats the official column as a LEVEL and is refused as a SERIES,
  because one surveyed cross-section is not a nine-year path and imposing a flat one would
  manufacture the central the decision rule forbids. The cement candidate is refused because its
  own heat term is assumed. What changed is what the series MEANS, not what it holds.
- **The build-order debt named in rc52 is closed.** The validation catalogue's freshness gate
  compares each cited product's mtime to the build sentinel, but the catalogue phase ran BEFORE
  a dozen of the products it grades, so those still carried the previous build's mtime and any
  build more than two hours after their last hand-run failed STALE on them. The catalogue now runs
  after every phase it grades and still before the three phases that read its outputs (the product
  catalogue, the artifact inventory and the deposit manifest), in all three build definitions.
- **Also.** A completeness row corrected: captive-generation diesel AND furnace oil bought in bulk
  are inside the estimated 1.A.2 industrial liquids (the transport fuel ledger excludes that
  customer class from the road control by construction), and only retail-pump diesel remains inside
  1.A.3.b - the previous row claimed the whole of it sat in Road and omitted furnace oil. The
  FY2023-24 and FY2024-25 Economic Survey energy chapters and IPCC 2006 Vol 1 Ch 5 acquired.

## [%s] — September 2026""" % (NEW, OLD))], 1)
print("done; regenerate (strict build), then the gate WITH --after-mint")

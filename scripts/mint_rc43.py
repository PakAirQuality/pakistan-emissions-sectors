#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc43 from the rc42 tree.

    python3 scripts/mint_rc43.py [--dry-run]

Modelled on scripts/mint_1_0_0.py and deliberately NARROWER: a release candidate carries no
DOIs, so the DOI sites that script rewrites (release_manifest.py, CITATION.cff identifiers,
.zenodo.json related_identifiers, references.bib, the abstract's DOI parenthesis) are left
alone. Regenerated sites - the release cover, the manifest, the README banner, the .bbl - are
left to the build, as they are there.

The data registries that carry a release stamp are treated as that script treats them: only
data/claims_registry.csv is bumped, because its stamp means "the release this claim was
checked against" and the mint re-checks it. data/held_products.csv and
data/temporal_driver_registry.csv keep rc42, which is the release those rows were assessed in
and remains true. No push, no tag, no upload.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc42", "1.0.0rc43"
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
# THREE SITES THE v1.0.0 SCRIPT DOES NOT COVER, found by test_release_identity rather than by
# reading: CITATION.cff carries a HYPHENATED "v1.0.0-rc42" in its commented DOI block beside the
# unhyphenated `version:` field; docs/reproducibility.md prints the version in a table; and
# references.bib names it six times. The identity guard exists because a release that is called
# two different things in two artefacts is a release nobody can cite, and it earned its keep here.
patch("CITATION.cff", [("v1.0.0-rc42", "v1.0.0-rc43")], 1)
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)], 1)
patch("paper_common/references.bib", [(OLD, NEW)], 6)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
patch("CHANGELOG.md", [("\n\n## [%s] — August 2026" % OLD, '''

## [%s] — August 2026

**The nine-year spatial reconstruction.** The inventory had a nine-year national ledger
attached to a one-year spatial renderer; this release places the other eight years and says,
per stream-year, on what evidence.

- **Territorial membership.** An "Other" share is now placed only where its own source put it:
  every row of `data/province_shares.csv` carries a machine-read `other_membership`, and
  transport's 0.80 Mt of CO2e leaves Islamabad District, whose OCAC area pages never reported
  it. No national pin and no ADM1 marginal moves.
- **The period is a parameter.** `report/grid_cube.py` named FY2023-24 in nine spellings; one
  `PeriodKeys` object now carries them all, read from `data/periods.csv` and
  `data/months.csv`. Two silent borrowings were found by measuring rather than reading: the
  grid plant fleet and the FIRMS fire raster were both keyed to the reference year for every
  period, and neither raised anything.
- **Nine years published**: `pakemis_adm1_by_year.csv`, `pakemis_adm2_by_year.csv`,
  `pakemis_adm2_monthly_by_year.csv` (all 108 months at district grain),
  `pakemis_adm2_sector_by_year.csv` and `pakemis_grid_fallbacks_by_year.csv`. Each period
  closes: national == ADM1, and ADM1 == ADM2 + the mass unallocated below it, to 1e-12 for the
  eight panel-controlled years.
- **Provenance per stream-year.** `pakemis_spatial_weights_by_year.csv` types all 1,701
  stream-periods on two axes - was the geography measured for THIS year, and how much of the
  placement was substituted. 299 of 1,672 live stream-years were measured in their own year;
  1,102 carry the reference year's pattern rescaled.
- **The substitution record, per year.** Grid power's plant ledger begins FY2019-20, so the
  four years before it place 42.6-53.3 Mt CO2e a year on a built-up substitute - two orders of
  magnitude more than the reference year's 0.34 Mt, and previously invisible.
- **The query surface serves it**: `fact_adm2_year` beside `fact_adm2_month`, with the engine
  routing historical district requests to the annual table and refusing monthly ones for a
  reason that is true.
- **A receipt no longer depends on the tree it was built in.** `result_sha256` digested the
  release manifest's git hash, so every commit invalidated every frozen golden receipt,
  whatever the data did. It had already gone unnoticed through rc42.

Named and not closed: the district frame is fixed at the 2019 boundary set for all nine
periods (`abs-adm2-frame-vintage`), the historical periods are annual at ADM2 module grain,
and a plant-name crosswalk between the generation panel and the coordinate tables would turn
power's four backcast years into per-object activity.

## [%s] — August 2026''' % (NEW, OLD))], 1)
print("done; regenerate (strict build), then the gate WITHOUT the manifest checkout")

#!/usr/bin/env python3
"""Mint PakEmis 1.0.0rc45 from the rc44 tree.

    python3 scripts/mint_rc45.py [--dry-run]

Modelled on scripts/mint_rc44.py and deliberately NARROWER: a release candidate carries no
DOIs, so the DOI sites that script rewrites (release_manifest.py, CITATION.cff identifiers,
.zenodo.json related_identifiers, references.bib, the abstract's DOI parenthesis) are left
alone. Regenerated sites - the release cover, the manifest, the README banner, the .bbl - are
left to the build, as they are there.

The data registries that carry a release stamp are treated as that script treats them: only
data/claims_registry.csv is bumped, because its stamp means "the release this claim was
checked against" and the mint re-checks it. data/held_products.csv and
data/temporal_driver_registry.csv keep their own stamp, which is the release those rows were assessed in
and remains true. No push, no tag, no upload.
"""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc44", "1.0.0rc45"
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
# The three sites test_release_identity found at rc44 and which stay covered here.
patch("CITATION.cff", [("v1.0.0-rc44", "v1.0.0-rc45")], 1)
patch("docs/reproducibility.md", [("**%s**" % OLD, "**%s**" % NEW)], 1)
patch("paper_common/references.bib", [(OLD, NEW)], 6)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
patch("CHANGELOG.md", [("\n\n## [%s] — August 2026" % OLD, """

## [%s] — September 2026

**The nine-period annual grid.** rc44 shipped nine fiscal years of district products and,
deliberately, no historical raster: nine cubes were declined because for two thirds of
stream-years they would carry the reference year's within-province pattern multiplied into 3.4
million cells a year. That objection was right and this release answers it rather than
overriding it - the pattern's provenance now ships beside the pattern, and is measured rather
than asserted.

- **`pakemis_grid_0p05_annual_ref_fy2015_16_fy2023_24.nc`**: nine fiscal periods x three
  spatial views x three gases on the frozen `pk_0p05_epsg4326_v1` lattice, 9.0 MB. Every period
  is generated from its own atomic streams, not by rescaling the reference map, and a test
  compares NORMALISED layers so a rescaled cube could not pass it. Cells plus
  `pakemis_spatial_unallocated_by_year.csv` reproduce each period's national control to a worst
  relative 2.2e-7. The three views PARTITION the placed mass and must not be added to one
  another's totals.
- **The pattern, hashed.** `pattern_hash` digests the normalised weight vector where the
  allocator uses it, so "borrowed" stops being a claim about the build. All 918 stream-years
  labelled a backcast do carry the reference year's pattern; of the 351 labelled as resting on
  their own year's evidence, none does. The grading and the thing it grades now have
  independent sources and they agree.
- **The registry was reading the reference year for all nine periods.**
  `pakemis_grid_stream_surfaces.csv` is the reference year's file and the join used
  `source_stream_id` alone, so the surface and placement reported against FY2015-16 were
  FY2023-24's. Now joined on (period, stream) via the new
  `pakemis_grid_stream_surfaces_by_year.csv`; 29 rows change, all of them streams carrying no
  mass in that period.
- **The grid query stops answering wrongly.** `get_grid_cell` was declared in the contract with
  no caller and no test. It resolved months by subtracting a hardcoded `date(2023, 7, 1)`;
  `argmin` snapped any point on earth to a Pakistani edge cell; and a masked cell - outside the
  country - was returned as a number. The epoch is now read from the file, the domain is
  checked, and the mask is a refusal.
- **`cell_area` and `pakistan_fraction` ship as variables**, because a 0.05 degree cell is 28.3
  square kilometres in Sindh and 24.7 in the north and that gradient otherwise reads as a real
  north-south signal. `crs_wkt` and `spatial_ref` are declared, which is what GDAL actually
  reads.
- **Nine release gates**, including the annual FY2023-24 layer against the twelve monthly cells
  cell by cell, and a period-isolation gate for a leak that every closure test would survive.

Named and not closed: no historical monthly grain and no historical configuration S, neither
being evidenced; the by-module and by-category cube groups; a CF checker is neither installed
nor pinned, so the CF check covers the conventions the file relies on rather than certifying
conformance.

## [%s] — August 2026""" % (NEW, OLD))], 1)
print("done; regenerate (strict build), then the gate WITHOUT the manifest checkout")

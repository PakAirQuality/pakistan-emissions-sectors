#!/usr/bin/env python3
"""Mint PakEmis 1.0.0 from the rc42-frozen tree with three reserved Zenodo DOIs (route A).

    python3 scripts/mint_1_0_0.py --doi-data 10.5281/zenodo.A --doi-software 10.5281/zenodo.B --doi-docs 10.5281/zenodo.C [--dry-run]

Rewrites every site that carries the version or a DOI; regenerated sites (release cover,
manifest, README banner, .bbl) are left to the build. No push, no tag, no upload."""
import datetime
import os
import re
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD, NEW = "1.0.0rc42", "1.0.0"
DOI_RE = re.compile(r"^10\.\d{4,9}/zenodo\.\d+$")


def arg(flag):
    if flag not in sys.argv:
        raise SystemExit("missing %s" % flag)
    value = sys.argv[sys.argv.index(flag) + 1]
    if not DOI_RE.match(value):
        raise SystemExit("%s is not a Zenodo DOI: %s" % (flag, value))
    return value


DATA, SOFTWARE, DOCS = arg("--doi-data"), arg("--doi-software"), arg("--doi-docs")
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
        print("would patch", path)
    else:
        open(full, "w", encoding="utf-8").write(s)
        print("patched", path)


patch("src/pkinv/__init__.py", [('__version__ = "%s"' % OLD, '__version__ = "%s"' % NEW)], 1)
patch("src/pkinv/report/release_manifest.py",
      [('DOI = {"software": "", "data": "", "documentation": ""}',
        'DOI = {"software": "%s", "data": "%s", "documentation": "%s"}' % (SOFTWARE, DATA, DOCS))], 1)
patch("CITATION.cff", [("version: %s" % OLD, "version: %s" % NEW)], 1)
# CITATION.cff: replace the commented identifiers block with the real one
cff = open(os.path.join(R, "CITATION.cff"), encoding="utf-8").read()
head, sep, _tail = cff.partition("\n# DOIs are minted at archival")
if not sep:
    raise SystemExit("CITATION.cff: the DOI comment block anchor was not found; inspect the foot of the file")
ident = '''
identifiers:
  - type: doi
    value: %s
    description: "Zenodo DOI of the software record for v%s"
  - type: doi
    value: %s
    description: "Zenodo DOI of the data record for v%s"
  - type: doi
    value: %s
    description: "Zenodo DOI of the documentation record for v%s"
''' % (SOFTWARE, NEW, DATA, NEW, DOCS, NEW)
if not DRY:
    open(os.path.join(R, "CITATION.cff"), "w", encoding="utf-8").write(head.rstrip("\n") + "\n" + ident)
print("CITATION.cff identifiers written" if not DRY else "would write CITATION.cff identifiers")

patch(".zenodo.json", [('"version": "%s"' % OLD,
                        '"version": "%s",\n  "related_identifiers": [\n'
                        '    {"identifier": "%s", "relation": "isSupplementTo", "scheme": "doi"},\n'
                        '    {"identifier": "%s", "relation": "isDocumentedBy", "scheme": "doi"}\n  ]'
                        % (NEW, DATA, DOCS))], 1)
patch("paper_common/references.bib",
      [("release %s; DOI to be assigned" % OLD, "release %s; \\url{https://doi.org/%s}" % (NEW, DOCS))])
patch("paper_national/versions/v1/paper_national.tex", [("release \\texttt{%s}" % OLD, "release \\texttt{%s}" % NEW)], 1)
patch("paper_national/versions/v1/sections/00_abstract.tex",
      [("under release \\texttt{%s}." % OLD,
        "under release \\texttt{%s} (data: \\url{https://doi.org/%s}; software: \\url{https://doi.org/%s})."
        % (NEW, DATA, SOFTWARE))], 1)
patch("data/claims_registry.csv", [(",%s," % OLD, ",%s," % NEW)])
month = datetime.date.today().strftime("%B %Y")
patch("CHANGELOG.md", [("\n\n## [%s] — August 2026" % OLD, '''

## [1.0.0] — %s

**A publication cut, not a science change.** 1.0.0 freezes the rc42 tree — the previous
release candidate answered the twentieth review with every gate green — and adds the single
numerical truth layer the programme now rests on:

- `outputs/semantic/`: 22 fact and dimension tables as canonical CSV (hashed in the release
  manifest) with all-string Parquet twins, described by `semantic_release.json`
  (`pkinv.semantic_release/v1`); the only arithmetic in the phase is Decimal (ADM1 shares,
  the S module sums). Closures held: ADM1 to national, S composed to 447.21383.
- `src/pakemis_query/`: the typed query core every consumer runs — one basis, configuration
  and GWP per request, typed refusals (mixed basis/configuration/GWP, not-estimated,
  unknown value, grain unavailable), DECIMAL(38,18) sums, envelopes with receipts, sixteen
  golden queries with frozen receipts.
- The identity guard at a final version: RELEASE_CLAIM catches a full version introduced by
  a release word; every printed DOI must equal the manifest's; the product name
  "PakEmis v1.0" is accepted only while the release is 1.0.x.
- Three Zenodo DOIs reserved before the mint and carried by the tag: data %s,
  software %s, documentation %s.
- `scripts/build_dev_snapshot.py` (deterministic development snapshot) and
  `scripts/build_deposit_zip.py` (the three deposits, from the deposit manifest).
- The national manuscript is re-targeted as an ESSD data-description article
  (`docs/essd_outline.md`); the sector papers are Sector Technical Notes TN01–TN10.

Deferred, named in README "Not in 1.0.0": exact ADM2 CO2e for the two mixed-origin modules,
configuration S beyond the residential substitution, a calendar basis outside agriculture,
TN08's text and the ESSD prose rewrite.

## [%s] — August 2026''' % (month, DATA, SOFTWARE, DOCS, OLD))], 1)
print("done; regenerate (strict build), then the gate WITHOUT the manifest checkout")

# Reproducibility and release

PakEmis **1.0.0rc70** covers **July 2015–June 2025**, ten fiscal years. FY2023–24
remains the detailed reference year; FY2025–26 is a separate provisional source
extension. The maintained article, longer report and sector notes describe this
release. `outputs/release_manifest.json` records its exact version, code identity,
reference totals, core period and product hashes.

The native gases are CO2, CH4 and N2O, with separate AR5 and AR6 aggregates. The
core air panel is primary PM2.5, BC, NOx, SO2, CO, NMVOC and NH3. Additional species
retain narrower coverage. Four configurations (`S_TAN`, `L_TAN`, `S_IPCC`,
`L_IPCC`) combine household fuel and nitrogen-method alternatives. They are
separate estimates, not additive parts or probability-weighted scenarios.

| Item | Location | Note |
|---|---|---|
| Code repository | `https://github.com/PakAirQuality/pakistan-emissions-sectors` | a public copy of each release without the third-party source documents; the `git` block of the release manifest names commits of the private working repository |
| Interactive explorer | `https://emissions.hawanama.org` | deployed separately; it can serve an earlier release than this one |

## Inputs and source custody

The source workflow is:

```
retained primary documents -> verified extracted activity tables
                          -> canonical inputs -> source calculations
                          -> annual/monthly/spatial/uncertainty products
                          -> semantic query tables and publication assets
```

`data/catalog/document_retention.csv` and the acquisition registers retain source
locations and hashes. `outputs/pakemis_source_register.csv` identifies source
custody; it does not grant redistribution rights. `outputs/pakemis_deposit_manifest.csv`
identifies the actual package files, licence terms and checksums.

Code is MIT licensed. Project-owned primary products and text use CC BY 4.0;
third-party inputs retain their terms. ODbL-derived databases and potentially
affected legacy spatial products are separated into a companion. Primary
geographic products exclude OSM coordinates and weights. The per-product audit
and `LICENSE-data` explain this separation. Extracting facts from a document does
not remove obligations inherited from a licensed source database.

## Build from a clone of this repository

The third-party documents are not in this repository (`docs/restricted_layers.md`). A
plain clone therefore rebuilds from the verified tables. The fifteen phases that read
documents or the private release history reuse their published products:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python scripts/build_adm2_intersections.py
.venv/bin/python -m pkinv.activity.build
.venv/bin/python -m pkinv.build --group deposit --strict --quick
PKINV_RELEASE_CHECKS=0 .venv/bin/python scripts/run_tests.py -j 4
```

In that clone the tests that need a document skip with the reason `restricted layers
absent:`. The runner fails if the skipped set differs from
`data/catalog/restricted_gated_tests.txt`. `PKINV_RELEASE_CHECKS=0` skips, and counts,
the few tests that hold only at a release commit.

With the restricted layers mounted, the maintainer's full build includes the
document-reading phases:

```sh
.venv/bin/python scripts/overlay.py link /path/to/private/checkout
.venv/bin/python -m pkinv.build --group full --strict --quick \
  --ledger logs/pakemis_full_run.json
.venv/bin/python scripts/retain_document.py --verify
```

`--quick` excludes network acquisition; it does not imply a statistical sample
of the build. The full repository lane includes local primary-source extraction
phases when their documents are retained. `make dev` is the incremental development
lane; `make build-plan` explains selected tasks. Release verification bypasses
cached successes. Inspect the entire phase ledger for failures and missing
outputs, not only the last console line.

Focused source checks include the PBS final exported-panel controls, NEPRA
station/fuel/bagasse replay, official extension-table replay and transcription
register. A passing compiled-input build must not be described as a complete
re-extraction of all held publications.

## Clean reconstruction and the deposit

The local collection contains primary data, the ODbL companion, software and
documentation. `scripts/unpack_deposit.py` verifies all archive checksums and
restores the original paths into an empty directory. The compiled-input lane is:

```sh
python3 scripts/unpack_deposit.py dist/pakemis-1.0.0rc70-release.zip /tmp/pakemis-review
cd /tmp/pakemis-review
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pkinv.activity.build
.venv/bin/python -m pkinv.build --group deposit --strict --quick
```

The fresh-directory verification harness is `scripts/clean_rebuild.py`. It starts
from manifest-listed code, inputs and dependencies in an isolated pinned
environment. Explicitly held or source-extracted products have named reasons and
verified hashes. The result distinguishes build status, product comparison and
source re-extraction. See [the exact reproduction levels](deposit_rebuild_limits.md).
The recorded runs are in [docs/reproduction/](reproduction/). For rc69
([docs/reproduction/rc69](reproduction/rc69/README.md)):
- the clean rebuild compared 470 files with 0 differences;
- the reader's unpack-and-build compared 400 files with 0 differences, and its 110
  not-rebuilt files were checked byte-identical.

rc68's runs ([docs/reproduction/rc68](reproduction/rc68/README.md)) compared 465 and 395
files, also with 0 differences.

A successful level is claimed only after its actual result is recorded.

CSV comparison preserves text, missingness and numerical tolerances. NetCDF
comparison includes dimensions, variables, masks, labels, scientific metadata and
arrays. Different container bytes alone are not evidence of different emissions;
changed values cannot be dismissed as a timestamp.

## Tests and publication assets

The canonical test command is run from the repository root:

```sh
PYTHONPATH=src:tests python3 -m unittest discover -s tests
```

`outputs/pakemis_test_run.json` records the actual run, skips and failures. Test
counts are not maintained as literals in prose. Focused tests check source
transcription, shared balances, native units, non-additivity, all four
configurations, annual/monthly/spatial closure and query/product identity.

`make papers` builds the current national article, submission copy, technical
supplement and maintained sector notes. Figure data are retained beside each
plot. Quantitative macros are checked independently against released emission
and uncertainty tables; a common commit header alone is not a consistency check.
The final release sequence commits content before regenerating provenance covers,
PDFs and checksums. A dirty snapshot must identify itself as dirty.

The inspected comparison release is rc67 commit
`3db0d658294dae1e6c760844df167daf7938fd65`; the reviewed PDF commit
`1876f398f85c` was an investigation lead, not a substitute for inspecting the
current tree. Matched numerical revisions, PBS timing-only consequences and
remaining scientific limitations are recorded in the campaign repair register
and concise change report.

No external publication, journal submission, DOI or review-access link is claimed.
A completed local package still needs an authorized public review deposit before
journal submission.

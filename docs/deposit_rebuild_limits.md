# Reproduction from the local review package

The current package is one local release collection containing primary data,
software, manuscript sources and an ODbL companion. Each constituent archive has
SHA256SUMS; the outer collection includes checksums for all four archives. The
software snapshot records its release version, HEAD, dirty status and content
hash. A dirty snapshot is not described as an exact clean commit.

Assemble it into an empty directory with the included helper:

```sh
python3 scripts/unpack_deposit.py dist/pakemis-1.0.0rc68-release.zip /tmp/pakemis-review
cd /tmp/pakemis-review
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pkinv.activity.build
.venv/bin/python -m pkinv.build --group deposit --full --strict
```

The helper validates every archive entry before assembling the original paths;
it refuses conflicting files, escaping paths and a non-empty destination. Both
primary and companion inputs are restored for declared schemas and provenance.
Primary calculation filters exclude ODbL coordinates and weights before placing
mass; presence of a companion input does not permit its use in a CC BY product.
The geographical audit records supported primary scopes and retained alternatives.

The package includes the native annual/monthly emissions, administrative products,
registered downstream compiled inputs, required SPAM rice water-regime rasters,
WorldPop/GHSL inputs, full TeX/figure sources and software dependency lock. Upstream
licences and attribution remain attached. GCD-Rice source redistribution has not
been established: its original raster is excluded; held evaluation tables are
provided. A recalculation of that independent raster crosscheck requires public
reacquisition and checksum matching, rather than an undocumented substitution.

Reproduction levels must be reported separately. A build from compiled activity
tables verifies equations, configurations, uncertainty and allocation. Full
re-extraction additionally requires original NEPRA/OGRA/PBS/OCAC/NFDC and other
source publications, public reacquisition and hash checks, Poppler, and the
source-ingestion commands. HIES record-level microdata are excluded; the published
survey aggregates are the compiled input. Public availability does not establish
redistribution rights for the original publications.

The deposit build group excludes fifteen phases and uses their verified compiled
outputs: thirteen primary-source phases and two that read release history from git:

- Power plant workbooks
- OGRA gas-class series
- Fiscal extension source tables
- Residential own-year degree-days
- HTAP air comparison
- Power air-control evidence
- UNSD industrial-combustion control
- UNSD coal supply control
- Forest flux adjudication (FAOSTAT land-use forests bulk archive)
- F-gas leak-rate adjudication (UNFCCC CRT tables)
- Lahore SO2 vs EDGAR gridmaps (EDGAR v8.1 air-pollutant gridmap archives)
- Provincial SO2 vs EDGAR gridmaps (the same archives)
- FAOSTAT nitrogen flows (FAOSTAT bulk emissions archives)
- Published release vintages (each published release manifest, read from git history)
- Release axis fingerprints (each published release's products, read from git history)

Each seed is identified by producer, reason and SHA256. These
source-extraction phases are not reported as regenerated. The last five read
retained raw archives under `data/raw/`, which the deposit carries by digest only.
The two history phases need a git checkout holding the published commits; the deposit
carries the tree, not its history.

The held products (`data/catalog/held_products.csv`: hand-run, network-bound or
legacy research-lane files that no build phase writes) travel in the package, legacy
spatial ones in the ODbL companion. A deposit build seeds them; until rc68 the clean
rebuild seeded them from the maintainer's checkout while 66 were missing from the archives.

A phase that declares a `prior:` read consumes the previous build's copy of a
file a later phase rewrites. A fresh tree has no previous build, so the harness
seeds the released copy of each such file, records it in the seeded-product
receipt as rewritable, and the later phase must rewrite it to the same bytes.

The fresh-directory harness is `python3 scripts/clean_rebuild.py --work DIR`.
It copies only manifest-listed code, dependencies, inputs, documentation and
manuscript assets into a new tree, creates an isolated pinned environment, starts
the production outputs directory empty apart from explicitly held/seeded inputs,
and runs the strict compiled-input deposit group. The resulting `result.json`,
`comparison.csv`, input snapshot, seeded-product receipt and build log retain the
actual outcome. CSV values and NetCDF arrays, masks and metadata are compared;
contextual hashes and stamps are distinguished from physical data. An already
installed isolated lockfile environment can be supplied with `--venv DIR`.

Some evaluation/release-bookkeeping phases additionally require excluded raw
acquisitions, GCD-Rice, a Git checkout or contextual paper hashes.
Success at one level does not establish success at the others. Use the current
verification record for the exact tested command, dependencies, phase list,
failures and numerical/byte comparison. This document does not assert a successful
full clean rebuild before that record exists. For rc68 it exists:
[docs/reproduction/rc68](reproduction/rc68/README.md) publishes the clean
rebuild (level `compiled_inputs`, 15 seeded phases, 0 differences in 465
files) and the reader's unpack-and-build (0 differences in 395 files). Neither
re-extracted a primary document.

Earlier rc62 deposit failure measurements remain in
campaign/v3_readiness/all_phases_from_deposit.json and deposit_failure_classes.json.
They describe that historical package, not the current corrected release.

An external review deposit and DOI remain pending. Nothing in this packaging
workflow uploads files or submits the manuscript.

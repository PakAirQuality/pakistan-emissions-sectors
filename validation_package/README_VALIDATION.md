# PakEmis {{version}} — national validation package

One release, one commit, one tree. Everything here was produced from commit `{{commit}}`
of the PakEmis repository (`{{generated}}`), whose working tree was clean. The release is
three commits by construction: the content commit `{{content_commit}}` (which
`outputs/release_manifest.json` describes, as the fixpoint requires), the artifacts commit that
carries the regenerated manifest, cover and PDFs, and the record commit `{{commit}}` that
carries the suite's result on that tree; only those artifact files differ between the first
and the last. Nothing was repaired while packaging; what failed is recorded, not removed.

Reference-year national total, configuration L (the inventory reference): **{{L}} Mt CO₂e
(AR5)**; configuration S: {{S}} Mt. Both are read from `outputs/release_manifest.json` and
asserted against the products by the suite.

## What was run before this package was hashed

| gate | command | result on the packaging machine |
|---|---|---|
| reproduction | `./reproduce.sh` (run FIRST, so the ledger tests below have a ledger) | **{{reproduce}}** — `logs/reproduction.log`, `logs/reproduction_report.csv`, `logs/reproduction_ledger.json` |
| quick validation | `./validate.sh --quick` | **{{quick}}** — `logs/quick_validation.log` |
| full validation | `./validate.sh --full` (self-contained) | **{{full}}** — `logs/full_validation.log`, `logs/test_summary.json` |
| Linux container | `docker run --network=none … ./validate.sh` | **{{docker}}** — `logs/linux_validation.log`, `logs/linux/` |
| documents | `./validate.sh --documents DIR` (needs the maintainer's source vault) | **{{documents}}** — `logs/documents_validation.log` |

Packaging machine: {{platform}}, CPython {{python}}. The package's records
(`KNOWN_EXCEPTIONS.json`, `EXPECTED_RESULTS.json`, `FILE_INVENTORY.csv`,
`VALIDATION_MANIFEST.json`, `SHA256SUMS`) are written BEFORE the validations run, so the
package-only tests know they are inside a package, and written again after; the finished tree
is then re-tested by the package's own tests (`logs/records_gate.log`) before it is zipped.
Every step's exit code is in `logs/exit_codes.txt` and `logs/command_timings.csv`. A test
that failed in the packaged run is listed by name in `KNOWN_EXCEPTIONS.json`
(`tests_failing_in_the_packaged_run`); none was excluded to make a gate green. Tests that
need a source document the package registers and does not carry SKIP by name
(`document vault not mounted: …`, counted in `logs/test_summary.json`) and run only under
the documents gate.

## The two layers of this tree

**The runnable tree.** The package root is shaped like the repository — `src/`, `scripts/`,
`data/`, `outputs/`, `tests/`, `docs/`, `paper_national/`, `papers/`, `paper_common/`,
`Makefile`, `pyproject.toml`, `run_all.py` — because the engine, the test suite and the
manuscripts resolve every path from one root (`src/pkinv/paths.py`; `PKINV_ROOT`). The two
shipped scripts set that root to this folder and run the release suite **unmodified**.

The compact data deposit stores source extracts, field schemas and the canonical
catalog without duplicate generated input CSVs. Both scripts first materialize
those CSVs offline with `python3 -m pkinv.activity.build`; the validation packager
does the same before running its engine checks and records their provenance.
For a direct model command in an extracted archive, run
`PYTHONPATH=src python3 -m pkinv.activity.build` first. No raw workbook, PDF or
network request is needed for this step; readable labels and source/category
keys reproduce with the retained catalog hashes.

**The reading index.** The folders the validation specification names by role —
`registries/`, `outputs/{annual,monthly,spatial,uncertainty,configurations,cross_sector,
completeness,validation}/`, `data/{parameters,emission_factors,source_documents,
source_extracts,transcription_registers,acquisition_records,boundaries,crosswalks,
restricted_sources}/`, `manuscripts/`, `code/`, `environment/` — sit on top of that tree.
Every file in them is one of:

- a **presentation copy**: a byte copy of a canonical file under the specification's name.
  `FILE_INVENTORY.csv` records the source path; `tests/validation/test_presentation_identity.py`
  hashes every copy against its source on every run, so the two layers cannot diverge;
- a **view**: a mechanical projection of canonical products (a GROUP BY, a filter, a join),
  written by `src/pkinv/report/validation_views.py` with a banner naming its inputs. A view is
  not a product of the release; regenerate it from the files it names;
- a **record** written by the packager (`VALIDATION_MANIFEST.json`, `FILE_INVENTORY.csv`,
  `SHA256SUMS`, `KNOWN_EXCEPTIONS.json`, `EXPECTED_RESULTS.json`, `data/SOURCE_MANIFEST.csv`).

Counts for this build: {{n_copied}} files copied from the release, {{n_views}} views,
{{n_registered}} files registered without bytes (below), {{n_sources}} rows in
`data/SOURCE_MANIFEST.csv`, {{n_restricted}} of them restricted.

A slot in the specification that no shipped product honestly fills is listed in
`VALIDATION_MANIFEST.json → omitted_artifacts` with the nearest artifact. Nothing was
invented to fill a slot.

## What is not in the package, and how to get it

Third-party documents are **not redistributed**: the 3.8 GB of source PDFs and workbooks
under `sources/`, the raw publisher files under `data/raw/`, the ODbL flight archive under
`data/cache/`, PBS microdata. The repository's tested position
(`tests/test_deposit_licensing.py`) is that *not-established* is the correct answer for a
government document with no stated terms, and a package is a publication. Each such file
has a row in `data/SOURCE_MANIFEST.csv` (SHA-256, size, publisher, URL, retrieval date) and,
where the document itself is absent, in `data/restricted_sources/restricted_source_registry.csv`
with the pages or cells consumed and the extraction tables that carry its facts. Every fact
transcribed from those documents is in `data/` and re-extracted cell by cell by
`data/transcription_registers/transcription_checks.csv` (`scripts/check_transcriptions.py`,
which needs `pdftotext` and the documents).

Two registers make a build possible without those documents (rc41). `data/public_documents.csv`
names the documents under `sources/` the package DOES ship, on the publisher's recorded
terms (the UNFCCC CRT tables six `official_reporting` modules open). `data/consumed_derivatives.csv`
names the tables under `data/activity/` that `scripts/ingest_*.py` extracted from documents
the package does not ship — the Climate TRACE power assets, the World Bank flare sites and
UNEP MARS rows, the OCAC aviation cells, the OECD, Climate TRACE and ERA5 aviation series —
with exactly the rows and columns the engine reads; the engine reads the table, and each
script's `--check` re-derives it wherever the document is held
(`tests/test_data_rederivation.py` skips those by name here, and says so). A run manifest
that hashes a document the tree does not hold carries the digest from `data/raw_manifest.csv`
and prints that it did (`src/pkinv/core/documents.py`).

The consumed geospatial inputs ship as the national 267×340 grids the engine actually reads
(`data/gis/proxy_*_267x340.npy`, WorldPop 1 km, ADM1/ADM2 geoBoundaries) and the MapSPAM,
GHSL and FIRMS files under `data/gis/manual/` whose sidecars declare an open licence. Global
archives were never held; `data/gis/PROXY_SOURCES.md` records each source, vintage, licence
and hash.

## Running it

```
./validate.sh --quick            # integrity, identity, schemas and keys, arithmetic closure (minutes)
./validate.sh --full             # the complete release suite, self-contained (document tests skip by name)
./validate.sh --documents DIR    # the document tests over a mounted source vault (DIR/sources, DIR/data/raw, DIR/data/cache)
./reproduce.sh [--papers] [--sources DIR]   # rebuild every canonical output from an EMPTY outputs/ and compare
```

`reproduce.sh` copies the runnable tree **without `outputs/`** into a temporary directory,
seeds only the products `data/held_products.csv` declares (hand-run products whose inputs
are outside the build, the hand-run validation results the catalog declares, the release-run
records, and the two tables of the one network phase that `--quick` skips; each verified
against its release digest and recorded as `seeded`),
then runs `run_all.py --quick --strict` — every phase must exit 0, and the run stops at the
first that cannot, naming it — with a **ledger** (`logs/reproduction_ledger.json`) of what
each phase wrote. `logs/reproduction_report.csv` then counts a product as
`rebuilt_identical` only if a phase logged OK and wrote it in that run; anything else is
`seeded`, `not_rebuilt`, `missing_in_rebuild` or `difference`, and the gate passes only when
nothing is in the last three. The rc40 package's reproduction had copied `outputs/` in first
and reported 82 of 83 products identical while 59 phases had never run; this is the rule
that makes that impossible.

Requirements: Python ≥ 3.10 and nothing else for the engine and most of the suite. The
gridded, parquet and common-draw tests need `environment/requirements.lock`
(`python3 -m venv .venv && .venv/bin/pip install -r environment/requirements.lock`,
then `PYTHON=.venv/bin/python ./validate.sh --full`); without it those tests **skip** and
the skips are counted in `logs/test_summary.json`. `environment/container/Dockerfile` is the
fully provisioned Linux environment; run it with `--network=none`. Both scripts export an
unroutable proxy, so any network attempt fails loudly. Both preserve the packaged
outputs. Validation writes logs and reconstructs `data/canonical/` when needed;
reproduction writes its rebuilt inputs and outputs in the temporary copy.

Verify the files with `sha256sum -c SHA256SUMS` (Linux) or `shasum -a 256 -c SHA256SUMS`
(macOS), or with the shipped stdlib checker `python3 tests/validation/check_sha256sums.py .`
(`--strict` to hold the `logs/` entries too, which is what the plain tools do). Every listed
file, logs included, verifies on a fresh package; three files the packager writes after
`SHA256SUMS` exists are deliberately not listed (`logs/build_tail.log`,
`logs/sha256_check_at_packaging.log`, `logs/records_gate.log`). Files under `logs/` are
rewritten by every run you make; after that their recorded digests describe the packaging
run and the default checker reports them separately.

`VALIDATION_MANIFEST.json` is byte-identical to the standalone
`pakemis_{{version}}_validation_manifest.json` beside the zip. Its `sha256sums_sha256` is the
digest of `SHA256SUMS` with the manifest's own line removed — a file cannot carry the hash
of a file that carries its hash — and `tests/validation/test_manifest_dimensions.py` re-derives
every count in `expected_dimensions` from the packaged files.

## Reading conventions

- Many `data/*.csv` registries carry a `#` comment banner before the header; read them with
  `comment='#'`.
- Primary keys of every product are declared in `registries/product_schemas.csv` and verified
  by `tests/validation/test_product_schemas.py`. The atomic key is
  `period_id, component_id, gas, configuration_id, geography_id`. Every CSV product's columns
  are typed in `registries/product_columns.csv` (type, nullability, enumeration or foreign
  key) and verified by `tests/validation/test_product_columns.py`; every CSV in the tree is
  rectangular and header-first (`tests/validation/test_csv_rectangular.py`), and the engine's
  own reader (`pkinv.core.io.read_rows`) refuses a row whose field count differs from the
  header's (rc41).
- The cross-sector ledgers are projected into one schema by pointers
  (`registries/cross_sector_ledger_map.csv` → `outputs/cross_sector/cross_sector_closure_registry.csv`);
  every value is read from the sector ledger it names, and the closure report is computed
  per ledger and configuration.
- `tests/` stays flat because `unittest discover` and `tests/_support.py` resolve modules
  from there; `tests/test_catalogue.csv` assigns each module to the specification's themes.

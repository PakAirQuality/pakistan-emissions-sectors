# Reproducibility and release

This page is the release record: what version this is, what it is built from, how to
rebuild it, and what changed since the previous state. The authoritative machine-readable
form is `outputs/release_manifest.json`, written by `python3 -m pkinv.report.release_manifest`
on every full run. Where this page and that file disagree, the file is right — it is
generated and this one is not.

## Release identifiers

| Item | Location | Value |
|---|---|---|
| Version | `src/pkinv/__init__.py` (`pyproject.toml` derives it) | **1.0.0rc67** |
| Code repository | `https://github.com/RehanAhmad13/pakistan-emissions-sectors` | see `git` block of the release manifest |
| Release manifest | `outputs/release_manifest.json` | version, commit, per-sector totals and years, completeness counts, source hashes |
| Archived software release | Zenodo | *not yet minted — see "Minting the DOIs" below* |
| Archived data release | Zenodo | *as above* |
| Code licence | `LICENSE` | MIT |
| Data, figures and manuscript text licence | `LICENSE-data` | CC-BY-4.0 |
| Citation metadata | `CITATION.cff`, `.zenodo.json` | kept in step with the version above |
| Python | `pyproject.toml` | 3.10+; standard library plus `openpyxl`; `gis` extra for gridded products |

## What the deposit contains, and what it deliberately does not

**The archive deposit ships products, not the source documents.** `sources/` holds 3.8 GB of
third-party publications — OGRA, NEPRA, PBS, NFDC and PCAA reports, and PBS household survey
microdata — and for most of them the publisher states no redistribution terms at all. That is
the ordinary condition of a government statistical publication, not a defect in the record.
But a deposit is a publication, and this project cannot license what it does not own:
depositing the repository whole would have offered several thousand third-party files under the
CC-BY-4.0 grant in `LICENSE-data`, which it has no right to make.

So the deposit is assembled from an explicit allowlist and every file in it carries a licence
this project can actually grant. Two generated products describe it:

| product | what it answers |
|---|---|
| `outputs/pakemis_deposit_manifest.csv` | every deposited file, its licence, its reason, its sha256 |
| `outputs/pakemis_source_register.csv` | every source **not** deposited, its publisher, its hash, and how to obtain it |

The register keeps two questions apart that one column used to conflate — whether a document
may be **read and derived from** (`inbound_use`) is not whether it may be **republished**
(`outbound_redistribution`), and only the second is at issue. Facts are not copyrightable, so
the derived activity tables and every product built from them are this project's to license
and are deposited in full.

**The cost, stated plainly:** a reader rebuilding from nothing must re-acquire those
publications themselves. The hashes are what make that a procedure rather than a guess —
obtain the document, compare the digest, and you know you are reading what this release read.
`tests/test_deposit_licensing.py` holds all of this absolutely: nothing enters the deposit
without a grantable licence, and no excluded source may be silently absent from the register.

## The national validation package

`python3 scripts/build_validation_package.py [--docker]` builds, from a clean release
checkout whose manifest describes HEAD, the two files an external validator receives:

    dist/pakemis_<version>_full_validation.zip
    dist/pakemis_<version>_validation_manifest.json    (byte-identical to the copy inside)

The package root is a repo-shaped tree filtered by the deposit manifest - a file is copied
iff `outputs/pakemis_deposit_manifest.csv` lists it with a depositable outbound licence, or
it is this project's own code, product or prose; documents are registered with their hashes
in `data/SOURCE_MANIFEST.csv` and never copied. On top of that tree the validator's folders
(`registries/`, `outputs/annual/` ... `manuscripts/`, `code/`, `environment/`) hold byte
copies of canonical files under the names the specification uses, or views computed by
`pkinv.report.validation_views`, and `tests/validation/test_presentation_identity.py`
hashes every copy against its source. Before the tree is hashed the packager writes the package's records first (so the
package-only tests know they are inside a package), runs `./reproduce.sh` FIRST and then
`./validate.sh --quick` and `./validate.sh --full` against the reproduction's own ledger
(and, with `--docker`, both validations in the shipped container with `--network=none`,
the ledger copied in); the logs and exit codes ship in `logs/`, a failing test is named in
`KNOWN_EXCEPTIONS.json` rather than excluded, and tests that need the source documents the
package does not carry run only under `./validate.sh --documents DIR` (rc42) - they are a
separate gate, reported `not_executed` when no vault is mounted, never a hidden failure. `tests/test_validation_package.py` holds the builder and its templates to
these commitments without building the package.

## Minting the DOIs

Every DOI field is empty until a real identifier exists: an invented identifier that resolves
to nothing is worse than a missing one, and an empty `value` would make `CITATION.cff` fail its
own schema. Three records are deposited — **data** (the products), **software** (the tree at
the tag) and **documentation** (the PDFs with their hash sidecar) — and the route is
**reserve first, then mint**, so that the tag, the manifest, the citation files and the
manuscripts all carry the identifiers they will resolve to. Every step needs the GitHub and
Zenodo accounts that own the repository, so every step is user-only; the engine's side is
`scripts/mint_1_0_0.py` and the builders named below.

1. **Reserve three DOIs on Zenodo** (New upload → "Get a DOI now" on each of three draft
   records: data, software, documentation; do not publish yet). Each reserved DOI is of the
   form `zenodo.<record number>` (three distinct records).
2. **Mint the release** on the clean fixpoint tree:
   `python3 scripts/mint_1_0_0.py --doi-data <data DOI> --doi-software <software DOI> --doi-docs <documentation DOI>`
   writes the version and the three identifiers into every site that carries them
   (`src/pkinv/__init__.py`, `CITATION.cff`, `.zenodo.json`, `pkinv.report.release_manifest.DOI`,
   the bibliography notes, the manuscripts' release lines, the claims registry, the
   CHANGELOG), then the gate runs (`scripts/gate_chain.sh`, **without** the wave-gate
   manifest checkout), the fixpoint (`scripts/release_fixpoint.py`) and the test-run record
   (`scripts/record_test_run.py`) commit as usual. The identity suite proves every printed
   DOI equals the manifest's.
3. **Push with the LFS objects** (`git lfs push --all origin pakemis-pass2-2026-08 && git push
   origin pakemis-pass2-2026-08`); no remote holds the 19 git-lfs objects (~3 GB) until then.
4. **Tag the record commit**: `git tag -a v<version> -m "PakEmis <version>" && git push origin v<version>`.
5. **Build the deposits** from the tagged tree: `python3 scripts/build_validation_package.py
   --docker` (the reviewer artefact), `python3 scripts/build_deposit_zip.py` (writes
   `dist/pakemis-<version>-data.zip`, `-software.zip` from `git archive`, `-documentation.zip`,
   each with `SHA256SUMS`), `python3 scripts/build_dev_snapshot.py` (the collaborator's
   development snapshot; not a deposit).
6. **Publish the three Zenodo records** with those zips (`docs/zenodo_data_record.md` is the
   data record's prepared metadata; the ODbL carve-outs are stated there and in
   `LICENSE-data`). Link them with related identifiers — data *isSupplementTo* software,
   documentation *isDocumentedBy*/*documents* data — so each resolves to the others.
7. **GitHub Release** from `v<version>` with the validation package attached; merging
   `pakemis-pass2-2026-08` into `main` is a separate decision taken afterwards.

**Checklist** — every item user-only:

- [ ] three DOIs reserved (data, software, documentation)
- [ ] `scripts/mint_1_0_0.py` run with them; gate, fixpoint and record committed
- [ ] branch pushed **with LFS objects**
- [ ] `v<version>` tagged on the record commit and pushed
- [ ] validation package, three deposit zips and the development snapshot built from the tag
- [ ] the three Zenodo records published and cross-linked
- [ ] GitHub Release published; merge to `main` decided

Nothing in this repository can complete these; what it guarantees is that the moment they are
done every printed identifier already resolves to the right record.

## The baseline configuration, and why a total needs one

Residential dung admits two readings of the same evidence, a factor of 4.9 apart on the
2024-25 survey round as measured. The reference is the household survey; configuration L is a destination assumption retained
beside it:

| Configuration | Dung basis | Residential | **National (AR5)** |
|---|---|---:|---:|
| **S — the declared baseline** | HIES reported cake (household demand) | 24.22 Mt | **444.96 Mt** |
| L | agriculture nitrogen ledger (all diverted supply) | 29.47 Mt | **450.20 Mt** |

S is the baseline because the residential row measures what households burn, and the survey
observes that. Under it the rest of the dung agriculture diverts has no observed destination
and is outside the total; `outputs/pakemis_dung_fate_by_year.csv` prices each candidate
destination. L, which burns all the diverted dung in households, was the baseline of every
release through rc66. Both are computed through the same code path and written to
`outputs/national_all_sectors.csv` and `outputs/national_all_sectors_ledger.csv`. **A national
figure quoted without its configuration is ambiguous**, and every generated output now carries
the configuration in a column rather than leaving it to prose.

### Which product is the fact table, and which are views

`outputs/pakemis_atomic_annual.csv` is the **atomic fact table**: one row per emission stream
per period, keyed on `period_id × component_id × gas × configuration_id × geography_id`, and
holding no aggregate of any kind. Its aggregates are derived into
`pakemis_atomic_annual_aggregates.csv` with the level of each one named.

`national_all_sectors.csv`, `national_all_sectors_ledger.csv` and
`pakemis_national_series.csv` are **typed aggregate views kept for compatibility**. Each holds
its total in the same column as the parts that make it — a `TOTAL` row on the rollups, a
`COVERED_TOTAL` row per year on the series — because roughly a hundred and sixty call sites
read them that way and moving the row would move no number while breaking all of them. Read
the typed `row_kind` column (`sector` / `national_total`; `sector` / `covered_total`) rather
than matching on the row's name, and do not sum a column of these files without filtering it.
The atomic table is the one to build new work on; see the deferred source-of-truth inversion
in [ROADMAP_STATE.md](ROADMAP_STATE.md).

## One reporting period

All ten sectors report the same twelve months: **FY2023-24, 1 July 2023 to 30 June 2024**,
declared as explicit dates rather than as an integer year. Every generated output carries
`period_start`, `period_end` and `period_label`, so a reader meeting a CSV without this page
can see which twelve months a row describes.

This is the property that changed most since the first release, and this page described the
old state for three rounds after it stopped being true. The earlier releases were a
latest-supported-year nowcast — transport on FY2021-22, waste and power and aviation on 2023,
the rest on 2024 — and the national total was a sum across reference years. It is not any
more. Where a sector's activity data are genuinely older than the reporting period, the gap
is carried as a declared structural axis in `data/scenarios.csv` rather than as a different
year in the total.

The inventory is also resolved into those twelve months one at a time: see
`outputs/national_monthly_2024.csv`, which closes to the annual figure exactly for every
source stream, and `outputs/temporal_profile.csv`, which reports how well the timing of each
module is known. Most of it is not: **54.65 percent** of the national total sits on a flat
profile that is a declared assumption rather than a finding.

## One-command reproduction

**Nothing is user-supplied.** The two geospatial inputs a reader might expect to fetch
are settled: the NASA FIRMS VIIRS extraction is COMMITTED and hash-pinned
(`data/sectors/agriculture/gis/manual/`, sha256 in `FIRMS_SOURCES.json`) so no access key is needed to
reproduce, and MapSPAM 2020 is HELD and hash-pinned (`RICE_SOURCES.json`), with its
former cropland-fallback class deleted from the allow-list so a checkout missing the
raster refuses the build. Re-fetching FIRMS or swapping the rice surface changes the
surfaces and is an **upgrade, not a reproduction**: it
creates a new configuration and a new manifest, and its outputs are not the ones this
release reports.

```
pip install -e .
make all        # every sector, the national layer, the release manifest, figures, dashboard
make test       # the full suite, including the cross-document consistency guards
make papers     # the national manuscript, nine sector technical reports and their supplements
```

`make quick` skips the phases that need network access. Individual stages:

```
make sectors    # the ten sector runners
make air        # the air-pollutant layers
make national   # rollup, key categories, uncertainty, completeness, the category ledger,
                # the parameter decomposition and the uncertainty drivers, the monthly layer
                # and its cross-checks, the CRT crosswalk, EDGAR and the release manifest
```

## Two reproduction levels

A reader can reproduce this release at two levels, and the registry
`data/catalog/held_products.csv` is what separates them.

1. **Compiled-inputs rebuild.** From the deposit's `pakemis-<version>-software.zip` and
   `-data.zip`, 156 of the 195 registered phases run as shipped, every sector engine except
   Agriculture among them; a sector rebuilds at runner level (`python3 -m pkinv.activity.build`,
   then the sector runner). `make full` from the deposit does not run end to end: Agriculture
   needs gitignored GIS rasters the deposit does not carry, the national chain downstream of it
   reads build-tier intermediates the deposit excludes by rule, three phases read primary
   documents under `sources/`, and four comparison phases read `data/raw` acquisitions. The
   measured list, phase by phase and by cause, is `docs/deposit_rebuild_limits.md`. The 96
   products the registry lists as *held* are the ones no phase writes; the deposit ships them,
   and `tests/test_held_products.py` holds each to the SHA-256 recorded at release.
2. **Primary-evidence re-derivation.** Each held product names its producer script, what it
   needs and why it is not a phase: 74 are hand-run scripts over inputs that ship (rerunnable,
   not scheduled), 5 are reproducible from the package as it stands, 15 need an input the
   package does not carry (the Geofabrik OSM extract, WorldPop rasters, the ERA5 and NASA
   POWER pulls), one is rewritten by the release fixpoint and one needs the network. The
   verified ingests themselves cite the page or table of the source document in
   `data/catalog/source_documents.csv`; re-deriving an ingest from its document is the level
   the acquisition log (`data/raw/ACQUISITION_LOG_*.csv`) records per document, with the
   status of every document that could not be obtained.

   **Which documents are held (rc65).** `data/catalog/cited_documents.csv` answers per
   document: one row for each document a data file cites, the file that holds it, and how
   that was established. Of the 213 registered data files, 149 cite only documents that are
   held, 52 are derived inside the repository, and 12 cite at least one document that is not
   held as cited; `data/catalog/not_retained_register.csv` names those documents, the reason
   and, where one exists, the held reprint that prints the same figures. A document fetched
   after its table was compiled is labelled a later edition or an archive copy and compared
   with the table by the fetcher's `--check`. Until rc65 the register answered per file and
   usually named a directory, which is how twenty sources were listed as not kept while
   three of them were on disk, and how eight files were marked archived at a directory that
   did not contain what they cite.

   **A held document is never deleted.** `data/catalog/document_retention.csv` lists every
   file under `sources/` and `data/raw/` with its digest and only grows
   (`scripts/retain_document.py`); `tests/test_document_retention.py` fails on a missing or
   changed document, on a held document the ledger does not list, and on any earlier
   committed version of the ledger that listed more. `scripts/raw_data_manifest.py` refuses
   to write a manifest that has lost a listed path. A fetcher writes the bytes it received to
   `data/raw/` before it parses them (`src/pkinv/core/retention.py`), so a table cannot be
   produced without its source being kept.

   **Hand-run validations.** Six of the eight hand-run validation products now re-derive
   and compare without overwriting (`--check`, through `src/pkinv/core/checkmode.py`). Two
   do not, and the registry says why: the livestock validation's input model card is in no
   commit, and the IPPU coordinate agreement's producer is not idempotent.

What is NOT reproducible from the deposit at either level is stated in the registry's
`reproducible_in_package` column, row by row, rather than summarised here.

## What the build asserts about itself

These run in the test suite - in CI for every pushed commit, and in the release gate that
every content commit passes before it exists - and fail the build rather than reporting a
warning:

- **Generated artefacts match their generators.** `docs/completeness.md`, the README's
  numeric blocks and the sector papers' generated appendices are compared against a fresh
  regeneration with `git diff --exit-code`.
- **Manuscripts match the engine.** Every headline number in every manuscript is anchored by
  regex to the output CSV it came from; a lost anchor is a failure, not a skip.
- **Shipped outputs match a fresh build.** Each sector's committed totals are rebuilt
  in-process and compared, so a partial re-run cannot ship.
- **Cross-sector transfers close.** The dung transfer, the road/rail fuel boundary, the waste
  stream partition and the road/off-road diesel split are asserted, not described.
- **Coverage claims match the registry.** Prose asserting a category is not estimated must
  correspond to a real row in `outputs/completeness.csv`.
- **The twelve months close to the year.** Every source stream's monthly rows sum to its
  annual component exactly, nationally and per module, and every month row carries the
  evidence class of its own timing. A module that ships without a monthly layer fails.
- **The build has one executable task registry.** Make and CI select groups from the
  same registry used by `run_all.py`; reproduction bypasses the developer cache.
  Dependencies, command identity, source membership and output digests govern reuse.
- **Nothing in `outputs/` is an orphan.** Every committed output has something in the tree
  that writes it, and no superseded year-variant sits beside a current one.
- **A phase cannot claim an artefact it did not produce.** `run_all.py` checks that each
  phase wrote the output it declares, during that run.

## Known limits of this release

Stated here rather than discovered by a reader:

- **Coverage.** Roughly 29 Mt of industrial fuel combustion (1A2) and 11.5 Mt of F-gases are
  not estimated; `outputs/completeness.csv` and `data/data_gaps.csv` name every gap. The 1A2
  figure is an upper bound on what is absent rather than a measurement of it — reading a held
  table has narrowed it twice.
- **The monthly layer is mostly declared, not observed.** 54.65 percent of the inventory
  carries a flat profile. Some of that is unavoidable (a livestock census counts a stock once
  and has no month); the rest — road CNG, sugar-mill bagasse, crop-residue burning, waste and
  fugitives throughout — is an acquisition gap, and none of it moves the annual total.
- **Uncertainty is parametric and conditional.** The published interval is a Monte Carlo over
  parameters within one named structural configuration, `REF_2023_24`. Three single
  structural alternatives move the total further than the interval itself;
  `outputs/national_structural_bridge.csv` prices each.
- **LULUCF is excluded** from all totals and carried as an exploratory module.
- **Agriculture parameter provenance.** 25 rows carry working pointers and 21 are declared
  judgements rather than citations; each is now labelled with a `provenance_class` column and
  registered as `agriculture-parameter-provenance`. Resolution was attempted and not
  completed — see the agriculture supplement for why choosing a plausible match would
  fabricate provenance rather than establish it.
- **Transport air-pollutant factors** carry no located primary citation
  (`transport-air-factor-provenance`); that layer is an exploratory diagnostic.
- **Air-pollutant coverage is uneven** across sectors and is not a finished product; the power
  figures in particular are uncontrolled upper bounds, not what the fleet emits.

## Change log

Release-cycle history lives in [CHANGELOG.md](../CHANGELOG.md) at the repository root -
the manuscripts and this page describe the current method only. Historical totals are
history there, never claims here.

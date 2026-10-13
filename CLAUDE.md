# PakEmis — repo instructions for Claude

## Where data lives — check ALL FOUR places before acquiring or extracting anything

This repo holds source data in **four** layers, and every one of them must be
searched before downloading a document or re-parsing a table. On 2026-09-10 a
sweep re-downloaded nine OGRA reports and re-extracted a gas table because only
one layer was checked; the same mistake had already happened once with OCAC.

1. **`sources/`** — the PRIMARY raw-document tree (government scans, company
   reports, statistical yearbooks; several are no longer published anywhere).
   Organized by topic (`sources/OGRA/`, `sources/IPPU/company/`, …).
2. **`data/raw/<source>/`** — the second raw tree (bulk acquisitions: OCAC
   editions, PBS tables, NFDC reviews, …).
3. **`data/sectors/<sector>/activity/`** and **`data/shared/activity/`** —
   hand-verified INGESTS: transcribed tables with per-row source citations,
   statuses (`verified`, `verified-ocr`, `restated`) and notes. If a table is
   here, it has already been read, verified, and often corrected (restatements
   from later editions' comparison columns; OCR of scanned editions). A sector
   also holds its `parameters/`, `lookups/`, `gis/`, `evidence/`, `requests/`
   and generated `canonical/` folders; `data/README.md` is the reviewer index.
4. **The registries** that map it all, all under `data/catalog/`:
   `source_documents.csv` (which ingest came from which document),
   `raw_manifest.csv`, `assets.csv` (every asset, with the `legacy_path` each
   one keeps as its published identity) and `migrations.csv` (the old→new map),
   plus `outputs/pakemis_source_register.csv`.

Historical `data/...` paths still WORK: `src/pkinv/assets.py` resolves every one
through `data/catalog/assets.csv`, and the central readers call it. Two things it
cannot do — and both have already caused defects. It does not resolve a legacy
DIRECTORY that fanned out (`data/activity` spans eleven sectors), so a walk or a
glob over one finds nothing; use `assets.members("data/activity/")`. And it never
sees a bare `open()`; `tests/test_asset_path_discipline.py` fails on that.

**The check, before any acquisition or extraction — ONE command:**

```
python3 scripts/holdings.py <keyword> [<keyword> ...]
```

It searches all four layers in one pass (both raw trees, the verified ingests by
filename AND by source-column content, and the three registries) and exits
non-zero only when nothing is held — so an acquisition script can gate on it.
Run it first, every time. Its ingest layer is enumerated from the asset catalog,
not by walking a directory: it used to walk `data/activity/`, and when the sector
layout emptied that tree the layer reported `0 table(s)` for every keyword while
the exit code stayed 0. A dead layer leaves the gate looking healthy, so
`tests/test_holdings_discipline.py` now asserts every layer can still find
something.

**New documents go to `data/raw/<source>/` only.** `sources/` is the FROZEN
legacy tree — its file list is pinned in `data/catalog/sources_freeze.txt` and a
guard (`tests/test_holdings_discipline.py`) fails on any addition. The two trees
are a known redundancy (23 documents already live byte-identical in both, listed
in `data/catalog/cross_tree_duplicates_baseline.csv`); a second guard fails on any NEW
cross-tree duplicate, so the OGRA/OCAC re-acquisition cannot recur. Physically
merging the trees is a declared v1.0.0-boundary event (it re-hashes the release
manifest's document section) — do it there, not mid-release.

If the document is held: use the held copy. If the table is already ingested:
do NOT ship a parallel extraction — a re-extraction is only ever a CROSS-CHECK
that validates the ingest (the OCAC precedent, and now the OGRA one:
`outputs/ogra_gas_class_series.csv` validates
`data/sectors/industry/activity/gas_consumption.csv` +
`data/sectors/power/activity/captive_gas.csv` on their overlapping cells and
adds only the classes they never held).

**Every document read is kept, and no held document is ever deleted.** A fetcher writes
the bytes it received to `data/raw/<source>/` through `pkinv.core.retention.keep()` BEFORE
it parses them, and parses the kept file. Until 2026-10-12 several parsed a response in
memory and let it go (UN Comtrade, the World Bank API, NASA POWER, HydroWASTE, the GEM
workbooks, FIRMS), and pages were read live with no snapshot; twenty sources ended in the
not-retained register that way and the manuscript had to say so. Nothing under `sources/`
or `data/raw/` is deleted or edited: not a duplicate, not a superseded edition, not a file
"nothing reads" (the August cleanup that removed 103 Climate TRACE responses on that ground
is the precedent NOT to follow). `data/catalog/document_retention.csv` is the append-only
ledger (`scripts/retain_document.py`, run after `scripts/raw_data_manifest.py`);
`tests/test_document_retention.py` fails on a missing or changed document, and the manifest
builder refuses to drop a listed path. Holding is not redistributing: everything under
`data/raw/` is hash-only in the deposit, so copyright is never a reason not to keep a copy.

**Which document, not which directory.** `data/catalog/cited_documents.csv` has one row per
document a data file cites, with the file that holds it. A data file is `archived` in
`data/catalog/source_documents.csv` only if EVERY document it cites is held as cited; a
reprint that prints the same figures is a `held-witness` and does not make the original
held. A saved web page is not the cited fact: several sites build the page in the browser,
so `scripts/fetch_cited_documents.py --verify` checks that the held bytes carry the cited
content and reports a page that does not as `empty-of-it`. A copy fetched later than the
table was compiled is labelled (`held-later-edition`, `held-archive-copy`) and compared by
the fetcher's `--check`; it is never passed off as the bytes read.

Every acquisition attempt gets a log row — hits, negatives and blocked sources
alike (`data/raw/ACQUISITION_LOG_*.csv`); a "site is down" is usually a wrong
address, so search for the real URL before logging a negative.

## Standing invariants that repeatedly bite

- **Tests**: `python3 -m unittest discover -s tests` from the repo root only.
  A green run is exit code 0; for build chains, scan the whole log for `[FAIL]`
  lines — never just the tail. That invocation stays CANONICAL: it is what
  `scripts/record_test_run.py` shells and publishes. For iteration,
  `python3 scripts/run_tests.py` (`make test-fast`) runs the same tests one
  process per module — 180 s against 610 s on ten cores, same failures.
  `tests/test_parallel_runner.py` holds it to dispatching exactly what
  discovery finds; only three modules are exclusive, each with its reason in
  the file. `scripts/gate_chain.sh` uses it for its suite step too, and greps
  `[FAIL]` and `[ERROR]` out of its output — those two markers are a CONTRACT
  (the exclusion list may only ever apply to failures), guarded by applying the
  gate's own grep to the runner's own output.
- **Rebuilding less**: `make dev` (`python3 -m pkinv.build --group dev`) is the
  everyday build — it reuses a task whose inputs, command, code, environment and
  complete recorded outputs still match. `make build-plan` explains the selection
  without executing anything, and `BUILD_ARGS="--target 'LABEL'"` narrows it,
  prerequisites included. `python3 -m pkinv.run_all --only "LABEL"` / `--changed`
  forward to the same scheduler. DEVELOPMENT ONLY — refused under `--strict`, the
  phases whose `reads` is None never skip, and reuse is recorded as `CACHED` or
  `SKIP (current)` so a run that skipped cannot be read as one that executed.
  Release paths are untouched; nothing in the mint sequence passes either flag.
  `make release-check` is the strict path and ignores cached successes. The cache
  is `logs/build_cache.json` + `logs/file_digests.json` (both gitignored); delete
  them to force a full build. `make data-check` proves the data contract:
  requests, asset catalog and reviewer guides, compatibility views, canonical
  inputs. See `docs/data_pipeline.md` and `docs/development_builds.md`.
- **Manifests read git**: new files under `data/` must be `git add`ed BEFORE
  regenerating `data/catalog/raw_manifest.csv` (`scripts/raw_data_manifest.py`)
  or the builders will not see them. Regenerated too early, that script silently
  relabels every untracked row `tracked=external` — which in its own vocabulary
  is a claim about redistribution and backup, and no test rejects the value.
- **Product registration**: a new output that is not named `pakemis_*.csv`
  needs a LITERAL entry in `PRODUCT_PATTERNS`
  (`src/pkinv/report/release_manifest.py`), a row in
  `data/catalog/artifact_roles.csv`, the filename in `tests/test_csv_terminators.py`,
  a `Phase` in `src/pkinv/run_all.py`, and a Makefile line — then regenerate
  `pkinv.report.artifact_inventory` and `pkinv.report.product_facts`. The
  canonical-uncited ratchet in `tests/test_artifact_inventory.py` is raised
  only WITH a written reason.
- **Pakistani PDFs**: `pdftotext` renders the "ti" ligature as control byte
  `\x19` in some documents and drops it in others ("Cap ve"/"Capve" for
  Captive) — normalize by stripping `[\s\x00-\x1f]` before matching. Serial
  row numbers ("7. Power …") pollute numeric columns. Table vocabularies DRIFT
  between editions (FY2022-23 OGRA reclassifies its gas table) — record the
  printed label beside the mapped class and mark non-comparable cells.
- **Classification**: **IPCC 2006 is canonical**, authored in exactly one place
  (`src/pkinv/report/completeness.py::ROWS`), declared in
  `data/shared/lookups/category_crosswalk.csv` and resolved by
  `pkinv.report.category_ledger.component_code(category, subitem, gas)` — never by keying a
  dict on the engine category, because two categories SPLIT: manure management is 3.A.2 for
  CH4 and direct N2O but **3.C.6** for indirect N2O, and managed soils is **3.C.4** direct /
  **3.C.5** indirect. The UNFCCC CRT is a published crosswalk
  (`outputs/pakemis_category_crosswalk.csv`), never a second set of codes in the engines.
  The move is **not injective on code text** — 3.A, 3.B, 3.C and 3.D all exist on both sides
  meaning different things, and Waste is **4** in IPCC 2006 and **5** in the CRT — so migrate
  on `component_id`, never on the code string. Pakistan's own BTR uses a shifted numbering
  (urea at 3.C.2, which the Guidelines use for liming), so `build_btr_comparison.py`
  crosswalks rather than joins. Retired leaves (`3.F`, `3.H`, the `LU` sentinel) must not
  reappear: `tests/test_category_crosswalk.py` guards both directions AND sweeps the code
  columns, because the conservation check aggregates at a grain no code appears in and is
  blind to a stale code that moved no mass. Sectors 1 and 2 carry no rule — the two schemes
  agree code for code there, which is the all-sector audit's finding, not an omission.
  See `docs/classification_scheme.md`.
- **Numbers discipline**: an absence is typed (`NE`, empty cell, a status
  word), never a zero; screenings and scenario ends live BESIDE totals, never
  inside them; a diagnostic gap (e.g. EDGAR 1.A.2) is never inserted as a
  residual; new categories must back-cast to FY2015-16 before entering any
  comparable aggregate.
- **Releases**: pins never move mid-session without a declared re-base; the
  paper and release manifest are frozen at the released rc — post-release prose
  edits wait for the next mint. No tags/pushes: v1.0.0 waits on the user's
  reserved Zenodo DOIs (`scripts/release_1_0_0.sh`).

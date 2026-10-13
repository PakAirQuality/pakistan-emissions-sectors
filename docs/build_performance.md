# Build and data migration validation

The sector-folder migration below was checked on 21 September 2026 with Python
3.11.10. The earlier pipeline measurements are retained separately as evidence
from the 20 September snapshot. They do not describe a fresh full build of the
current folder layout. Existing staged scientific changes were preserved; release
pins and scientific expectations were not changed to make these checks pass.

## Current sector-folder validation

The current registry contains **393 assets**, including **221 canonical tables
and 194,306 canonical rows**. Thirteen metadata/request tables were removed from
the initial 228-table model-input catalog and six maintained fact/evidence tables
were added. Canonical CSV format remains v1; existing table and record identities
survive relocation. The source register has 211 rows: its original 205 rows are
unchanged, and six explicitly derived consolidations have been added.

An isolated integration fixture ran the real IPPU numerical and metadata tasks
against materialized upstream inputs. A request contact-note edit reran only
metadata publication; the numerical task stayed cached. Exact restoration left
all **58 IPPU CSVs byte-identical** to the fixture's successful initial run.

| Two-task IPPU fixture | Producers executed | Wall time |
|---|---:|---:|
| Empty task cache, existing inputs and warm digest index | 2 | 1.971 s |
| First unchanged run | 0 | 0.142 s |
| Request-note edit | 1, metadata only | 0.551 s |
| Exact input restoration | 1, metadata only | 0.627 s |
| Unchanged after restoration | 0 | 0.150 s |

These are two-task integration measurements, not full repository build timings.
The evidence is `logs/sector_layout_ippu_invalidation.json`. The cache uses a new
layout version and intentionally discards receipts containing the old physical
paths. The scheduler records the learned input scope after its first successful
execution, so narrowing the initial conservative scope does not itself force a
second execution.

The current focused build, package and reconstruction suite ran 164 tests with
one skip and no failures.
It covers relocated file/directory declarations, native GIS companions, scoped
asset metadata, full-catalog consumers, one-time cache invalidation, missing
declared bundle members, unstaged modules in the explicit code allowlist,
offline reconstruction of every canonical CSV, and
existing cache corruption/concurrent-edit protections. The compact package still
omits generated canonical copies and reconstructs them from deposited source
tables and registries; their Git tracking does not cause duplicate archive copies.

## Full-suite totals and downstream parity from the current layout

That validation is now finished, on 22 September 2026 with Python 3.11.10. Three things
were measured: the suite, a cold build from an empty task cache, and the bytes of every
output against the tree the migration inherited.

**The suite.** `python3 scripts/run_tests.py` runs 263 modules. Its first run against the
relocated tree failed 10 tests and errored 15; it now passes, and so does the canonical
`python3 -m unittest discover -s tests` from the repository root - **3,321 executed, 3,306
passed, 15 skipped, 0 failed**, recorded in `outputs/pakemis_test_run.json`. At that commit the published
count of defined test functions was 3,331; it is not a live figure here, and the three
sites that do state it live are held to the suite by the claims registry.

Those 25 failures were nine distinct defects that the focused 164-test run had not found,
every one a consequence of relocating data without a reader noticing, and all nine are
fixed. The classes are worth naming, because they are the ones a future relocation will
reproduce:

- **The shim resolves a FILE, and eight readers built their path some other way.** A bare
  `open(os.path.join(DATA, "waste_params.csv"))` never reaches
  `pkinv.assets.resolve`, so it names a file that moved. Routed through the shim.
- **The shim also does not resolve a DIRECTORY that fanned out.** `data/activity` spans
  eleven sectors, so `asset_path()` returns it unchanged; `data/gis/kilns` moved as a whole
  subtree, so it can be resolved and now is. The distinction is in `assets._directories`,
  which translates a historical directory only when every registered file beneath it kept
  its relative position under one destination.
- **`scripts/holdings.py` walked `data/activity/` and reported `0 table(s)` for every
  keyword** while the registry layers kept the exit code at 0. That is the gate CLAUDE.md
  requires before any acquisition, and a false negative there is how a document gets
  downloaded twice. Its ingest layer is now a catalog query, and
  `tests/test_holdings_discipline.py` asserts that no layer comes back silent.
- **`scripts/release_fixpoint.py` raw-opened `data/gis/PROXY_SOURCES.md`** - the
  `make release-check` spatial gate, dead with a FileNotFoundError.
- **`scripts/ingest_nfdc_production_series.py` read an absent input and would have written
  a second vintage of its table** beside the raw PDFs while every reader used the catalog's
  copy. It had no `--check` and no row in `tests/test_data_rederivation.py`, so nothing ran
  it; it now has both.
- **`tests/semantic/test_asset_catalog.py` read `assets.REGISTRY`, which does not exist.**
  Pointed at `pkinv.assets.CATALOG`, the constant the production code consumes.

`tests/test_asset_path_discipline.py` now fails on a raw file operation naming a relocated
path, and on a walk over a legacy directory the shim cannot resolve - the three shapes
above, checked instead of remembered.

**The cold build.** `make dev` from a deleted task cache. It found three further defects
that no test covered, because each needed a producer to actually run:

- `pkinv/report/air_annual.py` took `os.path.dirname(ABSENCES)` and joined `data_gaps.csv`
  onto it. The two siblings went to different purpose folders, so the build stopped at task
  101. Resolved by its own identity.
- `pkinv.core.documents.digests` globbed `asset_path(ROOT, pattern)`, and a pattern is not
  a registered file, so `data/activity/transport/*.csv` matched nothing. **The transport run
  manifest silently dropped fourteen of its eighty-nine hashed sources** - the whole
  activity layer behind the sector's numbers - and still looked well formed. The helper now
  matches patterns against each asset's legacy identity, the way
  `core.manifest.sha256_sources` already did, which repairs every caller at once;
  `tests/test_asset_path_discipline.py` fails on a declared pattern that matches nothing.
- `run_all` declared "Semantic release" before "Validation catalog + scorecard" and
  "Deposit manifest", and `pkinv.semantic.assets` hashes four of their outputs. The build's
  forward-edge check raised it. It is a genuine cycle - the catalog probes fifteen products
  written between the two, and two of those read `outputs/semantic/` - so the four reads are
  declared `prior:`, the vocabulary the runner already carries for the previous release's
  artefact. `tests/test_held_products.py` now holds a `prior:` read to naming a later
  phase's output, rather than accepting a held-product row that would be untrue.

A tenth finding belongs to the staged science rather than the layout:
`scripts/ingest_brick_kiln_fleet_observations.py` did not reproduce its own committed
table. The reviewed wording of Bahawalnagar's `printed_value_if_corrected` - which opens
with the PRINTED 450 the row does not use - had been corrected in the CSV and never in the
script, and the first cold build put the old wording back. The script now re-derives the
table byte-identically.

**Downstream parity, which is the claim this migration actually makes.** Against the 885
output files the migration inherited, the completed cold build reproduced **880 byte for
byte**. Of the 229 files that carry an emissions quantity, **226 are byte-identical and the
other three contain no changed numeric cell** - a prose note in the completeness register
(the rc63 sulfur round's "as-fired kiln coal analyses" replacing "Punjab coalfield ranges"),
rendered into `fact_completeness.csv` and its Parquet twin. Every annual, monthly, ADM1,
ADM2, grid, air and Monte-Carlo product is unchanged, and so are all 54 semantic fact
tables but that one. The two remaining differences are the ones the 20 September run also
expected: `pakemis_data_provenance.csv` and `outputs/semantic/semantic_release.json`. In the
latter, 54 `derived_from` lists changed and one `sha256_csv`: the lineage is now per-table
rather than release-wide, so `fact_activity_crops` cites the one source it derives from
instead of all 72 the semantic build reads. That is the per-table dependency tracking
`docs/data_pipeline.md` describes, and it is a provenance improvement, not a loss.

Five further reader-facing artifacts moved afterwards for deliberate reasons, none of them
numeric: the claim matrix and the source register, deposit manifest, paper-artefact hashes
and monthly-request register that follow from correcting stale paths in prose a reader is
meant to follow. `docs/DATA_ACQUISITION.md` was the worst of those - it told a contributor
to drop `spam_rice.tif` into `data/gis/manual/`, where the shim would resolve the registered
name elsewhere and the dropped file would be ignored in silence.

**Timings.** The cold build executed 152 producers. Held at that state, an unchanged rebuild
reports **0 producers executed, 151 cached, 2.22 s**. `make data-check` passes on all four
contracts: 393 assets with no reviewer index differing, 0 compatibility views changed, 0
canonical differences, 221 canonical tables and 194,306 rows. Git records the relocation as
**351 renames**, all R100, so no blob is rewritten; the five deliberately excluded spatial
files (41 MB, including the 28 MB COD-AB archive) were re-expressed in `.gitignore` at their
new paths before anything was staged, because the retired `data/gis/*` block had been
keeping them out by omission and the relocation would have swept them into plain git.

## Initial pipeline measurements (20 September snapshot)

The original full, offline strict pipeline completed 164 phases in approximately
1,199 seconds (1,195.1 seconds summed across producers). This includes release
reporting that the new developer command intentionally excludes. Cold runs also
overlapped other validation work, so their total times are not a controlled
before/after speed comparison.

The new developer build completed all 154 tasks (149 producers and five checks
of products already written by their sector runner) in 850.90 seconds. This is
the cold developer path, with the full scientific calculations and draw counts.
That run preceded the final guard against inputs changing during execution; the
guard was subsequently checked with focused regressions and actual producers.

After populating the cache and holding code and inputs fixed, the unchanged
developer build completed in **2.226 seconds wall time**, with **zero producers
executed, 149 cached, and five existing-product checks**. Cache format and code
changes made during implementation required one-time refreshes; those runs are
not included in this unchanged-build measurement.

With a real transport fuel-share edit, the dry-run invalidated transport and the
residential runner's transport comparison, while eight unrelated primary sectors
remained cached. Conservative source boundaries still invalidated 115 tasks in
total, including cross-sector reports. Further narrowing those boundaries requires
auditing their complete inputs. An actual selected build after a harmless edit to
the transport province-shape module executed exactly one producer in 1.093 seconds.
Restoring that code also executed one producer; the subsequent unchanged full
developer build took 1.761 seconds. All 660 output CSVs remained byte-identical to
the successful cold snapshot after these probes.

Two measured changes remove repeated calculations while retaining output bytes:

| Producer | Original observed time | New observed time | Change |
|---|---:|---:|---|
| Monthly layer, nine years | 72.400 s | 0.352 s | Read the already materialized temporal profiles |
| Waste uncertainty summary | 36.590 s | 0.673 s | Summarize the same prefix of verified persisted Monte Carlo draws |

These are individual phase observations from the initial comparison run, not
isolated microbenchmarks. Detailed execution and cache ledgers are written under
`logs/architecture_*.json`. Run `make dev` twice with a fixed interpreter and
environment to measure an unchanged rebuild on another machine; use
`BUILD_ARGS='--explain --ledger logs/local-build.json'` to retain its evidence.

## Initial pipeline parity (20 September snapshot)

The following counts belong to the earlier 228-table snapshot, before sector
folders, metadata separation and the four fact consolidations:

- All ten sector data adapters preserve their complete normalized values.
- The canonical contract contains 228 tables and 194,345 rows. Source values,
  order, missing values, and existing public activity record IDs are preserved.
- All eleven newly materialized workbook interfaces match their original
  parsers exactly, including Python value types and order, with workbook parsing
  prohibited during the runtime comparison.
- All ten sector adapters and eleven workbook interfaces also match in an
  isolated tree with every managed staging CSV removed and no raw source
  directory. The check forbids reads of the original workspace's input files.
- The completed output comparison found 586 output files byte-for-byte identical
  to the original full pipeline: 543 CSVs, six NetCDF files, seven Parquet files,
  six PNGs, thirteen JSON files, and eleven Markdown files. The only differences
  were the intended provenance CSV and semantic release metadata.
- All 54 semantic CSVs, containing 550,109 rows, retain identical bytes.
- Explorer reconstructs all 228 canonical downloads from source bytes and schema
  with exact output hashes. The three dictionary-shaped workbook extracts expose
  their source category labels directly in the CSVs.
- Explorer passed 474 API tests using fixtures from its exact pinned release,
  423 frontend tests, and a production build. Comparing current working-tree
  scientific goldens with the older pinned release is deliberately not a parity
  test for this migration.

## Initial release-state checks (20 September snapshot)

The full inventory test run covered 257 modules and ran 3,270 tests, with nine
skips and no errors. It found two integration failures, subsequently fixed and
retested in a 130-test followup: an obsolete held-product declaration and
redundant canonical CSV copies pushing the compact archive over its existing
size limit. The archive
now retains the complete source/schema recipe and catalog; its bootstrap
reconstructs the same canonical input bytes before running models.

Five assertions still concern release state: two comparisons of existing grid
products against Git HEAD, two checks of the unfinalized release manifest, and
the manuscript's frozen test-count claim. These are not new scientific golden
values. Release finalization remains separate from this development migration.

Focused tests additionally exercise corrupted/deleted outputs, parser changes,
source changes, cache identity, Parquet corruption, canonical-only reads,
packaged-input reconstruction, and existing-release API compatibility. The
final build/cache followup passed 99 tests, including source/code edits and new
input or product files appearing during a task. The strict reproduction path
bypasses developer cache successes.

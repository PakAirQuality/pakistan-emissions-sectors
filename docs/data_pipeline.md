# Canonical inputs and incremental builds

The data path is:

```text
held source documents → verified extracts → canonical domain CSVs
                                             ├─ model adapters → sector calculations
                                             └─ activity downloads
sector calculations → semantic emissions tables → query API → graphs and result downloads
```

## Editing and building

Use `make dev` for everyday work. The first run populates the task cache; later runs
verify the input, code, environment and output identities before reusing a result.
`make build-plan` prints the selected tasks and rebuild reasons without producing files.
For a particular product, use `make dev BUILD_ARGS="--target 'Semantic release'"`;
prerequisites are included. `--jobs` controls the bounded worker pool. Tasks whose
ownership has not been audited stay in the serial lane.

`make release-check` runs every release task in strict mode and bypasses cached task
successes. `make all` retains the full build entry point. Papers, packaging and release
finalization stay outside the everyday build. Existing release pins are not changed by
development builds.

Verified extracts under `data/sectors/<sector>/activity/` and `data/shared/activity/`
remain the auditable staging layer. Use the
source's existing ingest script when a document changes, then rebuild canonical inputs.
`make ingest` materializes the six sectors' UNFCCC CRT workbook extracts under each
sector's `evidence/unfccc/` folder; `python3 scripts/ingest_official_reporting.py --check` proves those extracts without
rewriting them. It acquires no documents. Ordinary sector calculations do not parse
those workbooks. Other existing ingestion commands remain available for their sources.

The developer cache and execution ledgers live under `logs/`. Cache entries are written
only after successful execution and complete output checks. Changed arguments, code,
environment, input membership, or modified/deleted outputs invalidate reuse. Cache
records never substitute for a strict reproduction ledger.

## One input contract

`data/catalog/canonical_tables.csv` declares each domain table and its source, role and
period convention; `data/catalog/canonical_columns.csv` declares readable headings and
stable field IDs. `python3 -m pkinv.activity.build` writes each owner's generated
`canonical/` CSVs and `data/catalog/canonical.json`; `--check` verifies them without
writing. Those CSVs are versioned reviewer artifacts - only the retired `data/canonical/`
tree stays gitignored. Header drift, duplicate
declarations, malformed rows and unregistered activity tables fail explicitly.

The transformation retains every row, field, numeric string, blank and notation key.
It preserves source row order and does not merge independent dimensions, select one
source edition, infer missing values, convert units, or calculate emissions. Storage is
text so exact decimals and mixed notation columns survive; sector adapters apply the
same numeric parsing used before the migration. Explicit units and fiscal start/end
conventions travel with the schema.

`ActivityStore` returns the canonical rows through stable field IDs. Scientific code
does not dispatch on display labels. Returned records are isolated from caller mutation;
the store verifies canonical checksums and detects changed staging inputs when present.
A missing managed canonical table fails with a rebuild instruction. Ingestion is an
explicit staging context, rather than a fallback in calculations.

Canonical record identity is table identity plus source ordinal. It is deliberately not
a claim that every source has a natural key: reordering a source changes those IDs.
Existing readable activity exports retain their own existing record IDs and are
compatibility projections of canonical values. Their legacy source-details joins remain
available. Modelled waste flows remain downstream results, not source observations.

## Downloads and serving

The semantic release carries the canonical input catalog and ordered download metadata.
Explorer uses it for collection descriptions, schemas, product membership and file
selection. CSV downloads contain the canonical input bytes; existing emission-table
Parquet files represent the same CSV rows and exact values. The API, graphs and
"download this view" continue to use the shared query envelopes and receipt rules.

The canonical CSVs are versioned under each owner's `canonical/` folder, so a reviewer
reads the same bytes the model does. The DEPOSIT still omits them, to avoid archiving the
same source values twice, and Explorer reconstructs an input CSV it was not served from
the pinned commit's verified extracts and schema, then checks the source checksum,
canonical checksum and row count against the release contract. A mismatch refuses the
fetch. It never substitutes files from an uncommitted working tree.

Semantic builders retain per-table dependencies, memoize immutable source reads and
preserve unchanged CSV and Parquet files. Startup verifies the representation actually
served, including Parquet when a CSV twin exists, and shares that verification with
the query engine. Old pinned releases retain their legacy download catalog behavior.

## Compatibility and validation

This migration changes data plumbing rather than scientific assumptions. Keep exact
source quantities, uncertainties, periods, missing-value semantics, category admission,
random seeds, accumulation order and published rounding unchanged. New numerical
findings require separate scientific review, not updates to parity-test expectations.

The contract checks compare staging-to-canonical rows, sector components, semantic CSV
bytes, query envelopes, downloadable payloads and Parquet representations. Build tests
cover invalidation, missing outputs, interrupted execution, ownership and targeted
prerequisites. Full release and manuscript checks remain distinct from developer cache
tests.

See [the migration measurements and validation record](build_performance.md) for
observed timings, data parity, and the remaining release-state assertions.

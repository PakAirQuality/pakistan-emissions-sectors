# Canonical model inputs

`python -m pkinv.activity.build` prepares the readable CSVs under each owner's
`canonical/` folder - `data/sectors/<sector>/canonical/` and
`data/shared/canonical/`. These are the input tables used by sector calculations and
offered in Downloads. `--check` proves they reproduce without changing files.
A no-op build preserves file modification times.

Archive deposits retain the verified source CSVs, field/table registries, typed
extraction receipts and `data/catalog/canonical.json`. They omit the generated
canonical CSV copies to avoid storing the same source values twice. From an
extracted runnable archive, materialize them offline before a direct model or
query command:

```sh
PYTHONPATH=src python3 -m pkinv.activity.build
PYTHONPATH=src python3 -m pkinv.activity.build --check
```

This needs only the Python standard library and deposited files, without the
original PDFs, spreadsheets or network access. The regenerated CSV bytes,
readable labels, source/category keys and record IDs must match the retained
catalog. `make dev`, the validation-package scripts and the validation packager
perform this bootstrap before running calculations. Explorer reconstructs the
same files from the pinned source/schema inputs for Downloads. The runtime and
download contract remains the canonical CSVs.

The flow is:

```
held documents -> explicit ingest scripts -> verified staging CSVs
              -> canonical readable CSVs -> sector calculations
                                        -> Downloads
```

`data/catalog/canonical_tables.csv` declares each table, source, output, role, and
known period convention. `data/catalog/canonical_columns.csv` maps stable field IDs
to readable headings. Every staging field and row survives, including blank
quantities, uncertainty, evidence status, source qualifiers, and provenance.
Numeric text is preserved exactly; the adapters retain each sector's existing
numeric conversions. The catalog declares string storage and units only where
the existing activity contract supplies them. It does not infer missing units
or treat missing values as zero.

`data/catalog/canonical.json` records field mappings, the `Record ID` primary
key, row counts, source hashes, and canonical CSV hashes. A record ID identifies
a table and its original row ordinal. Reordering a staging source changes these
identities, so source order is deliberately retained. The `Source row` column
joins to the legacy activity source-details table through its `source_id` and
`source_row`; the existing public activity projections and their IDs are unchanged.

Runtime code reads through `pkinv.activity.store.read_rows`. For registered
inputs it obtains values exclusively from canonical CSVs and maps readable
headings back to field IDs. `ActivityStore.rows(table_id)` returns the readable
rows directly. Returned rows are independent copies. Missing, corrupted, or
stale canonical inputs fail with a rebuild instruction. Cached rows and source
verification invalidate when their files change. A deployment containing the
canonical bundle does not need the original staging files; if staging files
are present, their hashes must agree with the catalog.

Ingest scripts use `pkinv.core.io.read_rows` to read staging. The few upstream
producers that call shared model helpers explicitly enter `staging_inputs()`;
this is a scoped ingestion operation, never a runtime fallback. The pipeline
runs those producers before canonical materialization. Raw workbook extraction
and its `--check` audits remain explicit ingest tasks.

The legacy seventeen activity collections remain curated views of this broader
input library. Modelled waste flows remain downstream model results and cannot
become an input dependency. Geographic rasters and other non-tabular assets
retain their existing contracts.

`data/catalog/canonical_consumers.csv` declares conservative sector input scopes.
Runtime canonical reads also emit `pkinv.canonical.read` audit events so build
receipts can record exactly which input tables a task consumed. Source edits
invalidate dependent calculations; readable-heading changes remain distinct
from the scientific field IDs used in calculations.

Run `python -m unittest discover -s tests -p test_canonical_activity.py` for
lossless roundtrips, all ten sector adapter comparisons, publication identity,
source freshness, corruption, and reproducible-build checks.

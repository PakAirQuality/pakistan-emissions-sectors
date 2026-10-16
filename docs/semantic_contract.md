# The PakEmis semantic contract

**One numerical truth layer.** `outputs/semantic/` is the release's numbers at their published
grains, as typed fact and dimension tables, with `outputs/semantic/semantic_release.json`
declaring the release identity, the dimensions and their allowed values, the defaults, the
rounding rules, the aggregation rule of every fact, the source products with their digests and
the known limitations. The paper's tables and figures, PakEmis Explorer, the downloads and
Ask PakEmis consume the release through this layer by release id and hash; nothing numerical is
computed outside `pakemis_query`, and every number a consumer prints is a `display` field of an
envelope that carries the exact value, the unit, the context bar, the provenance and a receipt.

## What the layer is, and is not

- **Derived, not new.** Every value is the source product's string copied byte for byte. The
  only arithmetic is exact decimal arithmetic on two shipped numbers, in two places, each held
  to a closure the release already publishes: `fact_adm1_month` (a stream's monthly mass times
  its month-invariant declared province share from `pakemis_grid_provincial_check.csv`) and the
  configuration-S rows of `fact_adm2_month` (the survey product's stream rows summed to the
  module grain the reference product carries). ADM2 CO2e is the native mass times the engine's
  own GWP factor: exact where a module's methane has one origin, an interval `[x28, x30]` where
  it mixes fossil and biogenic (`co2e_exactness`), never a midpoint.
- **Identity is the CSV.** Each table is written once as canonical text - header first, no
  `#` preamble, LF, UTF-8, rows sorted by the declared primary key - and `sha256_csv` in the
  contract is the digest of that text; the release manifest records the same digest. The
  `.parquet` beside it is an all-string representation of the same text (the rule
  `pkinv.report.parquet_twins` already states: pyarrow's footer pins a library build, so a
  Parquet is never the identity); a holder of the Parquet re-serialises it and compares.
- **Every row has an id.** `result_row_id = sha256("pkinv.rowid/v1" ␟ table ␟ key values)[:24]`,
  independent of the release, so a row keeps its id across releases while its value may change.
  A table whose rows already carry a content-derived id declares it (`aggregation.id_column`) and
  ships that one column instead - the seventeen readable activity tables' `Record ID`, minted from
  the technical row's key and equal to `fact_activity_source_details`' `result_row_id`.
- **Byte-stable.** No commit stamp, no timestamp; `python3 -m pkinv.semantic.build --check`
  re-derives everything and fails on one byte.

## The tables

Dimensions: `dim_period.csv` (nine fiscal periods and the calendar years the agriculture
reconstruction publishes; `basis` is a column), `dim_month.csv` (108), `dim_configuration.csv`
(`REF_2023_24`, `L_2023_24` and the structural alternatives; L is a residential-module
substitution and the row says at which grains it exists; `S_2023_24` was retired at rc67,
when the survey reading became the reference), `dim_gwp.csv` (AR5 and AR6 factors),
`dim_gas.csv`, `dim_category.csv` (IPCC code hierarchy with the notation keys per gas),
`dim_geography.csv` (PK, five ADM1 units, every canonical ADM2 unit including the two without a
polygon), `dim_stream.csv` (the 189 source streams), `dim_evidence_class.csv` (E, TE and S
grades), `dim_notation_key.csv`.

Facts: `fact_annual.csv` (the annual atoms; configuration L at category x gas),
`fact_annual_calendar.csv` (agriculture, calendar years), `fact_monthly.csv` (the 108-month
atoms; L residential), `fact_adm1_month.csv`, `fact_adm2_month.csv`, `fact_unallocated.csv`,
`fact_uncertainty.csv` (the joint envelope; `envelope_not_quadrature`),
`fact_uncertainty_series.csv` (annual levels, trend pairs, the reference-year parametric
intervals), `fact_completeness.csv`, `fact_completeness_mass.csv`, `fact_transfer.csv` (the
cross-sector ledgers resolved to their values), `fact_evidence.csv` (one lineage row per
stream). The grid stays in the NetCDF products, registered by hash in the release manifest; `pakemis_query` reads a
cell from the file and map tiles are visual only.

## Defaults and refusals

Defaults: configuration `REF_2023_24`, GWP AR5, basis fiscal, period FY2023-24, geography PK,
`spatial_view = all` (the three views - physical, origin, accounting - are disjoint and additive,
so a district total sums them and the envelope reports each). A request names one basis, one
configuration and one GWP basis; `"2024"` is refused with `FY2023-24` and `CY2024 (agriculture
only)` named; `basis=calendar` outside agriculture, AR6 at ADM2 and configuration L outside
FY2023-24 are typed refusals (`NotEstimated`, `GrainUnavailable`), never computed.

## Where it is enforced

`tests/semantic/test_semantic_release.py` (identity, manifest agreement, registered columns,
defaults, closures, byte stability); `data/catalog/schemas/semantic_release.schema.json`;
`data/product_schemas.csv` rows `semantic.*` with `fk:` constraints into the dimensions.

## The claim matrix

The national manuscript's headline claims are the rows of `data/claim_matrix.csv` (the
sentence as printed, its `claim:` / `fact:` / `registry:` / `table:` references into the
claims machinery, the source pointer in the registry grammar, the stored query and its
parameters, the configuration, unit, rounding, evidence class, limitation label, technical
notes and artefact). `scripts/make_claim_matrix.py` resolves every row against this layer -
through `pakemis_query` where a stored query exists, else through the shared pointer resolver
`pkinv.report.claims` - and writes `outputs/pakemis_claim_matrix.csv` (the registry columns
plus `resolved_value`, `printed_value`, `agrees`, `query_hash`, `receipt`,
`semantic_release_id`), the readable `outputs/pakemis_claim_matrix.md` grouped by ESSD
section, and Supplement S5 as `paper_national/generated/claim_matrix.tex`. The renderer
repairs nothing; `tests/paper_numbers/test_claim_matrix.py` holds the printed value to the
resolved one and the matrix to the headline rule in both directions.

## Stored queries: the national manuscript's tables and figures

The national paper's tables and figures are stored queries against this release, registered in
`paper_national/queries/paper_artefacts.csv` (artefact id, kind, query function, canonical
params, output, renderer, ESSD section, what the artefact shows, the hand-registry entry it
retires). `scripts/make_paper_artefacts.py` opens the release with its identity verified, runs
every row through `pakemis_query`, and writes the table bodies
(`paper_national/sections/gen_tab_categorygas.tex`, `gen_tab_completeness.tex` - every number a
`display` string of an envelope, the first line naming the query, the params and result digests,
the release and the receipt), the cells each figure query draws
(`outputs/paper_figure_data/<id>.csv`; canonical CSV, hashed by the release manifest), the
figures themselves (`outputs/paper_figures/`, PNG and PDF with deterministic bytes) and the sidecar
`outputs/pakemis_paper_artefact_hashes.csv` (per artefact: params and result digests, receipt,
output and image hashes). Rows of kind `static` are the tables and figures the contract cannot
answer yet; the registry names what blocks each, and the sidecar hashes their inline source.
Since rc68 every registered artefact is `static` (the v3 integrated figures and tables), so no
figure-data file is written; the four rc67 query figures (`fig_trend`, `fig_sectors`,
`fig_months`, `fig_uncertainty`) were retired with their data, because no manuscript drew them
and their cells were rc67's nine-year values. Their bytes stay in git history and their hashes
in `data/baselines/rc67_integrated_campaign/outputs/release_manifest.json`.
`tests/paper_numbers/test_paper_artefacts.py` replays every query and holds the bytes; the
generated sections are exempt from the every-digit rule by reading the registry.

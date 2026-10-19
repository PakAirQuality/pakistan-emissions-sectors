# The PakEmis semantic contract

**One numerical truth layer.** `outputs/semantic/` is the release's numbers at their published
grains, as typed fact and dimension tables, with `outputs/semantic/semantic_release.json`
declaring the release identity, the dimensions and their allowed values, the defaults, the
rounding rules, the aggregation rule of every fact, the source products with their digests and
the known limitations. PakEmis Explorer, the downloads and Ask PakEmis
consume the release through this layer by release id and hash; nothing numerical is
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

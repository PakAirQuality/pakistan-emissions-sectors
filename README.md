# PakEmis — Pakistan National Greenhouse Gas Inventory

<!-- BEGIN GENERATED: headline -->
A reproducible ten-sector national emissions inventory for Pakistan: **444.96 Mt CO2e (AR5) +/- 10.9%** under the reference, which burns in households the dung the household survey observes, or **450.20 Mt** under configuration L, which burns all the dung agriculture diverts. Under the reference most of the diverted dung has no observed destination and is outside the total (each candidate priced in outputs/national_dung_variants.csv) -- built from Pakistani national statistics under the IPCC Guidelines.
<!-- END GENERATED: headline -->

<!-- BEGIN GENERATED: release -->
**Release** `1.0.0rc67` | reporting period **FY2023-24** (2023-07-01 to 2024-06-30) | **444.96 Mt CO2e** (AR5, reference) / **450.20 Mt** (configuration L) | 23 structural axes, 28 named configurations | completeness 54 E / 71 NE / 8 IE / 4 NO | code MIT, data and text CC-BY-4.0. Commit and manifest digest: `paper_common/release_cover.tex` and `outputs/release_manifest.json`.
<!-- END GENERATED: release -->

This repository holds the inventory engine, the manuscripts that document it, the activity
data they read, and the government source documents everything was digitized from. Each
sector is a software module satisfying a common contract, and the properties that span
sectors — the fuel a country burns being allocated once, nitrogen leaving one balance and
arriving in another — are executable assertions rather than statements in a methods document.

Nine of the ten sector modules are documented by self-contained technical reports in
`papers/`, alongside the cross-sector paper in `paper_national/`; industrial
combustion (1A2, 22.58 Mt since the rc46 solid-fuel activation) is the module still awaiting its own report, documented for
now by its fuel ledger and the national paper. The companion repository
`pakistan-emissions-nowcast` holds a different question: satellite **nowcasting** of
agricultural emissions *between* census years, and the machine-learned activity weights behind
it. It depends on this one. The line is what each answers — this repository, what emissions
were in the reference year; the companion, what they are now.

## What this release ships

Four product families. Every one is listed here because the table is generated from
`outputs/pakemis_product_catalog.csv`, so a product cannot ship and be missing from this page.

<!-- BEGIN GENERATED: products -->
| Family | Product | Entry point | Status |
|---|---|---|---|
| Annual | `annual.reference_year` | `outputs/national_all_sectors.csv` | mature |
| Annual | `annual.panel` | `outputs/pakemis_annual_fy2015_16_fy2023_24.csv` | mature |
| Annual | `annual.pass2_scorecard` | `outputs/pakemis_pass2_scorecard.csv` | new |
| Annual | `annual.completeness_mass` | `outputs/pakemis_completeness_mass.csv` | new |
| Annual | `annual.atomic` | `outputs/pakemis_atomic_annual.csv` | mature |
| Monthly | `monthly.panel` | `outputs/pakemis_monthly_fy2015_16_fy2023_24.csv` | allocation, not observation |
| Monthly | `monthly.coverage` | `outputs/pakemis_monthly_coverage_summary.csv` | complete |
| Spatial | `spatial.rice_geography_crosscheck` | `outputs/pakemis_rice_geography_crosscheck.csv` | new |
| Spatial | `spatial.stream_support_ledger` | `outputs/pakemis_stream_support_ledger.csv` | new |
| Spatial | `spatial.adm2_frame_2022` | `outputs/pakemis_adm2_frame_2022.csv` | new |
| Spatial | `spatial.grid_0p1_edgar_aligned` | `outputs/pakemis_grid_0p1_edgar_aligned.nc` | new |
| Spatial | `spatial.agri_reference_panel_divergence` | `outputs/agri_reference_panel_divergence.csv` | new |
| Spatial | `spatial.cube` | `outputs/pakemis_grid_0p05_monthly.nc` | allocation, partly observed |
| Spatial | `spatial.cube_annual` | `outputs/pakemis_grid_0p05_annual_ref_fy2015_16_fy2023_24.nc` | allocation, evidence-graded per stream and period |
| Spatial | `spatial.by_year` | `outputs/pakemis_adm1_by_year.csv` | allocation, geography borrowed outside the reference year |
| Spatial | `spatial.unallocated` | `outputs/pakemis_spatial_unallocated.csv` | declared, not gridded |
| Uncertainty | `uncertainty.reference_year` | `outputs/national_uncertainty_montecarlo.csv` | mature |
| Uncertainty | `uncertainty.common_ensemble` | `outputs/pakemis_ensemble_summary.csv` | joinable, reference year |
| Uncertainty | `uncertainty.longitudinal` | `outputs/pakemis_longitudinal_uncertainty.csv` | published, and negative |
| Uncertainty | `uncertainty.trend` | `outputs/pakemis_trend_uncertainty.csv` | published, and negative |
| Semantic layer | `semantic.release` | `outputs/semantic/semantic_release.json` | mature |
| Semantic layer | `semantic.facts` | `outputs/semantic/fact_annual.csv` | mature |
| Semantic layer | `semantic.dimensions` | `outputs/semantic/dim_period.csv` | mature |
<!-- END GENERATED: products -->

**Quickstart.** `make dev` prepares the canonical inputs and incrementally rebuilds the
inventory and Explorer data. `make build-plan` explains the selected tasks without executing
them. `make release-check` runs the full strict build without reusing the developer cache;
`python3 -m unittest discover tests` runs the full suite from the repository root.
See [the data and build architecture](docs/data_pipeline.md) for source ingestion, shared
download schemas, targeted builds, and compatibility. `make release-fixpoint` remains the
separate manifest, cover and PDF finalization command for a clean release tree.

**Two manifests, and they answer different questions.**
`outputs/pakemis_source_register.csv` names every third-party document this inventory READ,
with its publisher and sha256, so a reader can confirm they hold the same file. It is not a
distribution: those documents carry no established redistribution terms and are deliberately
not shipped. `data/catalog/cited_documents.csv` says, document by document, which file in
this repository holds it, and `data/catalog/document_retention.csv` is the list of held
documents that only grows. `outputs/pakemis_deposit_manifest.csv` is what the archive deposit CONTAINS —
this project's own code, derived products and manuscripts — with the licence each is offered
under. Reading a number back to its source uses the first; redistributing anything uses the
second.

**Licences.** Code MIT; data, figures and manuscript text CC-BY-4.0; the geometry inputs carry
their publishers' own terms (geoBoundaries public domain, OpenStreetMap ODbL, WorldPop and ESA
WorldCover CC-BY-4.0), recorded per file in the deposit manifest. No third-party source
document is redistributed under any of them.

**Known limitations, stated here rather than found later.** The inventory excludes LULUCF by
construction. Roughly three-quarters of the nine-year monthly mass sits on a declared-flat
profile — it is an evidence-graded allocation, not an observed monthly record. Thirty
industrial-combustion streams have no defensible placement below ADM1 and are retained in a
spatially unallocated ledger rather than spread onto the grid. Historical spatial products do
not exist; the cube is the reference year. And under the reported correlation scenario no
year-on-year change in the nine-year panel is resolved at 95 per cent; the multi-year
decadal window now is (the FY2015-16 to FY2023-24 change resolves at 38.96-114.11 Mt under
every published correlation reading) — the panel supports a decadal trend statement and
still cannot resolve an annual one.

**Status.** No manuscript here has been submitted to a journal, and none should be cited as
submitted, in review or in press. No DOI has been minted; when one is, it will appear in the
release block above.

## The inventory

<!-- BEGIN GENERATED: sectors -->
| Sector | IPCC | Year | Mt CO2e (AR5) | +/- % |
|---|---|---|---:|---:|
| Agriculture | 3.A-3.H | 2024 | 223.45 | 19.1 |
| Electricity + captive generation (family power_grid_control: grid 38.45 / 40.04 / 44.05 / 57.82 within the module figure) | 1A1a + 1A2 | 2023 | 45.59 | 9.7 |
| Road transport + mixed off-road | 1A3b + 1A4c/1A2 | 2024 | 41.93 | 11.4 |
| Waste | 4A, 4C2, 4D1 | 2024 | 37.45 | 51.1 |
| Cement (process CO2) | 2A1 | 2024 | 25.54 | 8.1 |
| Residential fuel | 1A4b | 2024 | 24.22 | 23.2 |
| Oil & gas fugitives | 1B2 | 2024 | 23.50 | 37.7 |
| Industrial gas combustion | 1A2 | 2024 | 22.58 | 18.7 |
| Railways | 1A3c + 1A2/1A4c | 2024 | 0.39 | 14.6 |
| Domestic aviation | 1A3a ii | 2023 | 0.30 | 58.8 |
| **Total (configuration S, the reference)** | | FY2023-24 | **444.96** | **10.9** |
| **Total (configuration L)** | | FY2023-24 | **450.20** | **11.0** |
<!-- END GENERATED: sectors -->

Every sector reports the **same twelve months**, 1 July 2023 to 30 June 2024. The integer in
the Year column is each sector's own label for that period — some name a fiscal year by its
start and some by its end — so read the reporting period, not the year. The release manifest
records both, and the convention each sector uses.

<!-- BEGIN GENERATED: coverage -->
Against EDGAR's Pakistani sectors summed (514.33 Mt), this inventory reports 87%. The shortfall is not spread thinly: roughly 16 Mt of industrial combustion (1A2) is still absent and F-gases (2F, 11.54 Mt) entirely so. `outputs/completeness.csv` carries an IPCC notation key and a justification for all 138 category-gas combinations — 54 estimated, 71 not, 8 included elsewhere, 4 not occurring.
<!-- END GENERATED: coverage -->

## Manuscripts

| Directory | What it is |
|---|---|
| `paper_national/` | The national manuscript, **versioned**: `versions/v1/` is the ESSD article that the release builds and hashes (`CURRENT` points at it), `versions/v3/` is the compact editorial rewrite built beside it, with its eight figures (`figures/f01_…f08_*.pdf`), `versions/v2/` is that rewrite as release 1.0.0rc62 shipped it, with its seven figures, frozen by digest in `versions/FROZEN.csv`, and `figures/` and `queries/` are shared by all three. Which version ships is said in `PAPER_NATIONAL_CURRENT` (`src/pkinv/paths.py`) and `NATIONAL_VERSION` (Makefile), held to agreement by `tests/test_paper_versions.py`. Contents: the sector contract, four enforced accounting closures, the IPCC parallel-table trap, parameter-level uncertainty, key categories by level *and* variance, completeness, benchmarks |
| `papers/<sector>/` | Nine sector technical reports — data, method, validation, results and limitations for each — maintained as versioned documentation of the release rather than as separate submissions; collected as PDFs in `papers/pdf/` |
| `paper_common/` | Shared LaTeX preamble and bibliography for every document here |

Every number printed in a manuscript is checked against the CSV it came from by
`tests/paper_numbers/`, and every figure must byte-match the output it plots. Both are
build failures, not warnings. The rules the uncertainty intervals follow - and why an
interval is never a validation - are stated in
[docs/uncertainty_contract.md](docs/uncertainty_contract.md).

## Layout

```
src/pkinv/       core/     registry, GWP, uncertainty, provincial downscale
                 sectors/  the ten sector modules
                 report/   rollup, uncertainty, key categories, completeness, figures
data/            activity data, emission factors, parameters, benchmarks
outputs/         generated CSVs and figures - regenerable, tracked so a diff is visible
tests/           the 28-invariant sector contract, per-sector arithmetic, manuscript checks
sources/         the government documents everything was digitized from
```

## Data products

The release's principal machine-readable products, all under `outputs/` and all
regenerated by the build (schemas and contracts in the linked documents):

| Product | What it is |
|---|---|
| `pakemis_atomic_annual.csv` (+ `_aggregates`) | **the atomic fact table**: one row per stream per period, keyed `period_id × component_id × gas × configuration_id × geography_id`, and nothing aggregated. Aggregates are derived beside it with their level named |
| `national_all_sectors.csv` (+ `_survey`) | the ten-sector annual rollup under configurations L and S — **a typed aggregate view: it carries its `TOTAL` beside its parts, so read `row_kind` (`sector` / `national_total`) and never sum the column blind** |
| `pakemis_national_series.csv` (+ coverage) | a nine-fiscal-year panel: all ten sector modules report in every year — the last two absent sector-years closed at rc20 — **the same shape: read `row_kind` (`sector` / `covered_total`)** |
| `pakemis_unallocated_activity_controls.csv` | the FY2015-16 Road and Total Industry controls that recorded the absence for four releases and now **gate the recovery**: the recovered edition's totals must equal them exactly (the two-document gate in `sectors/transport/ocac_image_edition.py`) |
| `pakemis_bridge_configurations.csv` | the modelled years this release **declines to publish**: `FY2015_16_FULL_SCOPE_BRIDGE` stays declared and permanently unpopulated — the observed split recovered at rc20 made every modelled alternative moot, and the validator ships for the next partial year |
| `pakemis_monthly_fy2015_16_fy2023_24.csv` (+ `pakemis_temporal_profiles.csv`, `pakemis_monthly_evidence.csv`) | **the 108-month layer**: every supported annual row resolved into its twelve months, closing to the annual row in native gas mass. The profile registry beside it carries each month's weight, its TE1–TE4 timing-evidence class, and what that timing is evidence *of* (`timing_target`) |
| `pakemis_source_streams.csv` | the 190-stream source ledger (evidence, spatial and temporal classes per stream) — [docs/source_stream_ledger.md](docs/source_stream_ledger.md) |
| `pakemis_grid_0p05_monthly.nc` | the 0.05° monthly gas-mass cube — [docs/spatial_products_contract.md](docs/spatial_products_contract.md) |
| `pakemis_adm2_monthly*.csv`, district panels | ADM2 views (frames declared in the spatial contract; crosswalk: `pakemis_adm2_crosswalk.csv`) |
| `national_configurations.csv`, `national_axis_register.csv` | the 22 structural axes, named configurations, families and pricing status |
| `national_uncertainty_montecarlo.csv` (+ sources, convergence, draw files) | the 100k-draw national Monte Carlo with published seeds and per-quantile standard errors |
| `national_gas_closure.csv`, `completeness.csv`, `release_manifest.json` | the commodity ledger, the E/NE/IE/NO register, and the release identity every headline resolves to |

Uncertainty ships per product: Approach-1 half-widths on every sector row, the
asymmetric national Monte Carlo (−10.4/+16.0 about the median), and structural
alternatives priced as named configurations — never folded into one number.

## The four products, and where each actually stands

PakEmis is promised as four linked products. Three of them are partial today, and this
table is the honest state rather than the intention — every figure is read from the file
named beside it.

| Product | Shipped today | What is missing before v1.0 |
|---|---|---|
| **Annual** `pakemis_annual_fy2015_16_fy2023_24.csv` | a complete nine-fiscal-year, ten-module rectangle — every sector-year estimated since rc20 recovered the FY2015-16 product splits from the public record (complete over modules, not over sources — see the completeness register) | no configuration axis; no F-gases |
| **Monthly** `pakemis_monthly_fy2015_16_fy2023_24.csv`, `national_monthly_2024.csv` | **108 months across nine fiscal years** (the full panel, closing to each annual row in native gas mass) — an evidence-graded ALLOCATION, not an observed monthly record: 87.3% of mass rides a TE4 profile, 12.6% of sector-months are strictly observed | observed monthly evidence for the declared-flat share (the OCAC panel covers FY2019-20 onward; six earlier years have no monthly petroleum series at all); no configuration axis |
| **Spatial** `pakemis_grid_0p05_monthly.nc`, `pakemis_adm2_monthly*.csv` | FY2023-24 cube at 0.05°, ADM2 panels; one historical district panel (`outputs/districts/district_totals_by_year.csv`, agriculture only, 1990–2024) | historical grid and ADM2 for every other sector; one canonical district geography (four unit counts are live — see the gap register) |
| **Uncertainty** `national_uncertainty_montecarlo.csv`, `outputs/mc_draws/` | 100,000 draws, reference year, 23 axes / 28 named configurations; a 10,000-draw common ensemble (`pakemis_ensemble_*.parquet`) joins annual, monthly and spatial draws on one draw_id | annual draws are single-year (the 20,000-draw longitudinal ensemble is its own product); ~13% of variance is unnamed residual since agriculture's factors were named, led by waste |

## What 1.0.0 is

**1.0.0 is a publication cut, not a science change**: it freezes the tree that shipped as the
last release candidate (1.0.0rc42, every one of the twentieth review's gates green) and adds
the one thing that tree lacked — a single numerical truth layer. `outputs/semantic/` holds the
release's facts and dimensions as canonical CSV (hashed in the release manifest) with Parquet
twins, described by `outputs/semantic/semantic_release.json`; `src/pakemis_query/` is the only
arithmetic any consumer runs over them, and every answer it returns carries a receipt. The
national manuscript, the sector technical notes, the downloads and the PakEmis Explorer are
different views of that one layer. What 1.0.0 contains, as products: one mature FY2023-24
reference-year inventory in two declared configurations (L and S); the nine-year annual
product; the 108-month product; the ADM1, ADM2 and 0.05° allocations with their unallocated
remainder; the joint and longitudinal uncertainty products; the completeness matrix and the
comparator-bounded absences. `paper_national/CURRENT/supplement.tex` states the contract each shipped
product satisfies, and its product table is generated from the release's own catalogue.

## Not in 1.0.0 (deferred, named)

- ADM2 CO₂e is **bounded, not exact**, for the two mixed-CH₄-origin modules (power,
  residential): the semantic layer reports the [×28, ×30] interval and never a midpoint.
  Exact stream-grain ADM2 is a 1.1 product.
- Configuration L is a **residential-module substitution** (L = REF − residential(REF) +
  residential(L)); its sub-annual and gridded products exist only for FY2023-24. The survey
  reading that was "configuration S" through rc66 is the reference since rc67, in all nine
  years.
- The calendar-year basis exists for agriculture only (the FAOSTAT reconstruction); every
  other sector is fiscal-year only and a calendar request is refused as not estimated.
- Sector Technical Note TN08 (industrial combustion) is numbered and reserved; its text is
  written in the next pass. The ESSD data-description prose of the national article is
  likewise the next pass; 1.0.0 ships the skeleton, the outline and the claim matrix.
- Nothing here is an official national inventory: the totals are those of the estimated
  PakEmis scope under a named reference configuration.

## Citing this work

See [CITATION.cff](CITATION.cff). DOIs are minted at archival and are deliberately
absent until then — nothing here prints an identifier that resolves to nothing. Cite
the release version and commit from the generated release block above;
`paper_common/release_cover.tex` and `outputs/release_manifest.json` carry the
commit and manifest digest.

**Manuscript status: in preparation.** The national paper and the nine sector reports are
in preparation and none has been submitted to a journal; no manuscript here should be
cited as submitted, in review or in press.

**Expected checksums.** `outputs/release_manifest.json` records a SHA-256 for every
activity file (191) and every archived source document (116), together with the commit
that generated it and whether the tree was clean. `scripts/make_release_cover.py` prints
the manifest's own digest into each technical report's provenance box, so a reader can
check that a shipped PDF and a checkout describe the same release. Verify with
`python3 -m pkinv.report.release_manifest` and compare — the file is written without a
timestamp precisely so it is byte-comparable. The shipped PDFs are **not** byte-stable:
LaTeX embeds a build date, so their recorded hashes identify the distributed artifact
rather than a reproducible target.

## Running it

```bash
pip install -e '.[gis,build,semantic]'
make dev                                    # canonical inputs and changed products
make build-plan                             # explain planned work without running it
make release-check                          # full strict reproduction
python3 -m pkinv.report.national_rollup     # the headline table above
python3 -m unittest discover tests
make papers                                 # compile the national paper and nine sector papers
```

The core inventory runs on the standard library alone. `pip install -e '.[gis,build]'` adds the
plotting extras that `pkinv.report.figures` needs and the two packages the build itself
imports (`openap` for the aviation fallback study, `jsonschema` for the packager);
`requirements.lock` pins the exact versions the shipped outputs were built with, those
included. One system dependency is not pip-installable:
**poppler-utils** (`pdftotext`), used only by the source-ingestion scripts under
`scripts/` — the inventory build itself never needs it. For a from-outside
reproduction, `bash scripts/clean_rebuild.sh` clones the repository into a temp
directory, installs the lockfile into a fresh venv, runs the offline build and
verifies the committed outputs reproduce byte-for-byte on the locked interpreter
(CPython 3.11; 3.12 changed the built-in float `sum()`, which the writers no longer use).

### Flight-stage aviation anchor year

The aggregate aviation inventory remains dependency-free. The FY2023-24 source-neutral
pipeline can run immediately as a provisional PCAA/OCAC-constrained annual-route
reconstruction; permissioned OpenSky records later replace its input adapter:

```bash
pip install -e '.[aviation,gis]'
make aviation-fallback      # official controls + Tier C/D reconstruction + OpenAP M0-M3
make aviation-study         # nine-year fuel account, official/external comparisons, and QA/QC
make aviation-opensky       # requires OPENSKY_TRINO_USER/PASSWORD
make aviation-adsblol-pilot # optional four-day public ODbL coverage pilot (multi-GiB cache)
make aviation-era5          # optional small CDS weather-sensitivity subset
make aviation-ledger        # canonical private Parquet ledger + query manifest
make aviation-anchor        # PCAA coverage, OpenAP fuel, OCAC closure, spatial products
```

Tier C rows are weighted annual route strata and never receive invented dates; unsupported
airport/operator activity remains Tier D `UNALLOCATED`. OpenSky rows are written only below
`data/private/aviation/`, which is gitignored. Exact
queries, source versions, coverage reports, and aggregate products are publishable. A
canonical CSV/Parquet ledger can replace OpenSky with future PCAA operational records
without changing the accounting engine. `run_anchor_year --coverage-only` audits a partial
extract before aircraft and performance enrichment is complete.

`make aviation-study` is the complete public-data analysis used by the focused
reconciliation paper. It extracts nine final annual OCAC reports and four years of public
monthly reports, closes every fuel row across six accounting destinations, compares five
complete fiscal years with matched OECD components, extracts Pakistan's UNFCCC CRT, evaluates
Climate TRACE airport ordering, incorporates aggregate ADSB.lol and ERA5 pilots, calibrates
carrier-specific bridge scenarios, bounds the reconstructed route matrix, separates
common-support model resolution from coverage completion, constrains payload with PCAA
passengers/cargo/mail, and runs a 20,000-draw completed-M2 Monte Carlo for every route-graph and
coverage-completion configuration. The ADSB.lol negative-coverage result carries synthetic and
same-archive positive controls; the CRT extraction carries a 21-cell hash-pinned audit. All
intervals, structural envelopes, contribution screens, manifests and QA reports are written to
`outputs/`. The representative-engine airport-pollutant layer remains a supplementary screening
module rather than part of the central reconciliation claim.

### IPPU evidence-gated platform

The registered FY2023--24 IPPU estimate is presently limited to cement-process CO₂. A
source-period audit found that the former 48.011 Mt cement control belongs to FY2021--22;
PBS QIM and the SBP Statistical Supplement agree on 39.566 Mt for FY2023--24. Correcting that
activity for all twelve months of observed HS 252310 trade gives 17.389 Mt at a 0.75 clinker
fraction. Trade is mandatory in both valid Tier-1 configurations; the no-trade calculation is
retained only as a method benchmark. Twelve producer filings disclose 32.831 Mt of clinker,
98.2% of the reference Tier-1 inference, without scaling the remaining producers. The same
runner writes the complete 2.A--2.G evidence matrix, producer census, facility registry,
ammonia/nitric-acid activation audit, HFC import contract, uncertainty register, and a
cell-audited extraction of Pakistan's 2022 CRT. Unsupported activity controls remain behind
evidence gates rather than being converted into proxy emissions.

```bash
python3 -m pkinv.sectors.ippu.run_ippu
python3 -m unittest discover tests -p 'test_ippu.py'
```

## Sources

`sources/` holds the government documents behind the activity data — NEPRA State of Industry
Reports, OGRA petroleum tables, Pakistan Railways Year Books, Civil Aviation Authority
movement statistics, provincial Development Statistics yearbooks, and the workbooks digitized
from them.

The provincial ZIP archives (~1.4 GB) are **gitignored** and must be backed up separately;
they are original sources, not regenerable outputs. Anything digitized out of them belongs in
`data/` as a versioned CSV.

## Conventions

Greenhouse gases use **AR5** GWP-100, the UNFCCC reporting standard, with AR6 carried
alongside at every level of aggregation. Air pollutants are reported as mass and never
converted to CO₂e. Most Pakistani sources are fiscal-year (July–June) — check before combining
with calendar-year data.

**Units.** `emissions_Gg` is gigagrams of the native gas (not CO₂e). `co2e_Mt_AR5` and
`co2e_Mt_AR6` are megatonnes CO₂-equivalent. `uncert_pct` is a 95% half-width in percent.
Monthly `share` is a fraction of the fiscal year and sums to 1 per stream. Spatial cube
variables are gas mass in Gg per cell-month.

**Evidence grades.** Every row declares three independent axes, defined in
`src/pkinv/core/evidence.py`:

- **E1–E4** — how the estimate itself is evidenced: E1 measured, E2 observed national
  statistic, E3 extrapolated from an observed anchor, E4 modelled or borrowed.
- **T1–T4** — how it is resolved in time: T1 observed monthly activity, T2 an observed
  correlated monthly control, T3 an evidence-supported seasonal profile, T4 flat or
  declared synthetic. Nationally: T1 0.94%, T2 12.46%, T3 14.97%, **T4 71.62%** of mass.
- **S1–S4** — how it is allocated in space: S1 native geometry, S2 facility or network
  proxy, S3 administrative statistic, S4 no native geometry. Nationally: S1 0.09%,
  S2 17.27%, **S3 82.65%**.

A high T or S share is an allocation, not an observation. Read the class before reading
the map.

**Summing rows correctly.** Sum `co2e_Mt_AR5` over `sector × category × gas` for one
`period_label` and one configuration — never across configurations, which are alternative
readings of the same emissions rather than additive parts. Monthly rows sum to their
annual row within 5×10⁻⁶ Mt (asserted by the build). Do not add the `COVERED_TOTAL` rows
of `pakemis_national_series.csv` to sector rows; they are the sum, not a member. Filter on
the typed `row_kind` column rather than on the row's name: the two rollups and the series
are compatibility views that keep their totals inline, and `row_kind` is what says which is
which. `pakemis_atomic_annual.csv` needs no such filter — it holds parts only, and has no
`row_kind` column precisely so that it cannot acquire a total.

**Reading a month.** `share` is the fraction of the component's annual mass placed in that
month, and the twelve shares sum to one — so the monthly layer can only say *when*, never how
much. `temporal_evidence_class` grades how well that timing is evidenced (TE1 direct monthly
activity → TE4 weak, borrowed, flat or days-weighted) and `timing_target` says what it is
evidence **of**: a TE2 fertiliser profile times urea *leaving a depot*, not nitrogen reaching a
field. A declared-unshaped stream is weighted by its month's own length, not by an equal
twelfth. Nationally 87.3% of mass is TE4 — the six fiscal years before the OCAC monthly panel
begins have no monthly petroleum series at all, and none was borrowed to cover them.

**Configuration policy.** Every headline is conditional on a named configuration.
`REF_2023_24` is the reference: household dung is what the household survey observes.
Configuration L (`L_2023_24`), in which households burn all the dung agriculture diverts, is
a retained alternative. `national_axis_register.csv` lists the 23 axes and
`national_configurations.csv` the 28 named configurations, each with its own total and, for
families, the kind of alternative it is. Pick one, name it beside any number you quote, and
do not average them or quote a range across kinds.

## What would move the inventory most

Two things, in order:

<!-- BEGIN GENERATED: movers -->
1. **Resolve gas-system practice and facility activity.** The 2019 segment inventory makes
   fugitives 5.3% of national emissions and 3.3% of national Approach-1 variance. Pipeline
   length and utility throughput are now included; material, pressure, LDAR, compressor,
   processing-plant and well records are the binding evidence.
<!-- END GENERATED: movers -->
2. **Finish industrial solid fuels.** 1A2 was the largest single gap and halved at rc46:
   captive gas, industrial process gas, the OCAC liquid customer class and the newly
   activated brick-kiln and cement-sector coal (HDIP's coal-by-consumer series, via the
   Finance Division Statistical Supplement) now cover 28.1 Mt of it and roughly 16 Mt
   remains — petcoke on its trade-screen lane, the gas/liquids floor, and whatever the
   EDGAR comparator counts that Pakistan's statistics do not. The paywalled HDIP *Pakistan
   Energy Yearbook* (`eyb@hdip.gov.pk`) would still settle the power sector's
   gross-versus-net TOE question and close the aviation JP-1 reconciliation.

Two sectors remain blocked on data rather than on work. Industrial combustion (1A2) has
establishment *counts* only for the solid fuels that remain — an allocation proxy, not activity
data. Water-borne navigation
(1A3d) has no marine fuel figure at any tier; do **not** build it on OGRA's "Overseas/Export"
furnace-oil line, which is exported cargo rather than bunkers.

## Licence

Code MIT (`LICENSE`); data and documentation CC BY 4.0 (`LICENSE-data`) — except the
OpenStreetMap-derived geometry tables and rasters (landfill polygons, rail network and
yards, road-density and building-fraction rasters, and the 71 OSM-sourced facility
rows), which are **derivative databases under ODbL 1.0** (© OpenStreetMap
contributors, share-alike); `LICENSE-data` lists every file. Rendered maps and figures
built from them are produced works and need only attribution; the extracted tables
themselves stay ODbL.

## Reading the deposit in five lines

```python
import pandas as pd
annual = pd.read_csv("pakemis-core/semantic/fact_annual.csv", comment="#")      # period x category x gas
ref = annual[(annual.configuration_id == "REF_2023_24") & (annual.period_id == "FY2023-24")]
print(ref.groupby("gas").co2e_Mt_AR5.sum())                                      # 444.96 Mt CO2e in all
adm2 = pd.read_csv("pakemis-core/semantic/fact_adm2_year.csv", comment="#")    # district x year
```

Every table carries a `#` banner naming its producer and its meaning; `pakemis_artifact_inventory.csv`
lists every file with its role, and `SHA256SUMS` verifies the archive.

## Writing in the national paper

Read `paper_national/writing/sub.md` before editing any prose or caption in `paper_national/`: it is the house practice (what belongs in the paper and what belongs in release notes, the voice, the vocabulary, the period rule, number registration, figure and caption rules, and what an agent may not write).

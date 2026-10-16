# PakEmis: greenhouse gases and air pollutants in Pakistan

<!-- BEGIN GENERATED: headline -->
A shared activity and material-flow inventory for Pakistan covering ten fiscal years, **July 2015–June 2025**. The latest covered-source estimates are **457.24 Mt CO2e (AR5)**, **422.7 Gg primary PM2.5**, **833.1 Gg NOx as NO2** and **2690.1 Gg NH3**, under configuration S_TAN. Native CO2, CH4 and N2O are supplied separately from warming-potential aggregates. Other core air species are BC, SO2, CO and NMVOC. These totals exclude unestimated sources and LULUCF.
<!-- END GENERATED: headline -->

<!-- BEGIN GENERATED: release -->
**Release** `1.0.0rc68` | reporting period **July 2015--June 2025 (ten fiscal years)** (2015-07-01 to 2025-06-30) | reference FY2023–24: **444.61 Mt CO2e** (AR5, S_TAN) / **449.85 Mt** (L_TAN) | 23 structural axes, 28 named configurations | completeness 54 E / 70 NE / 9 IE / 4 NO | code MIT; CC-BY-4.0 for project-owned primary products and text; per-file upstream terms retained. ODbL-derived components are packaged separately. Commit and manifest digest: `paper_common/release_cover.tex` and `outputs/release_manifest.json`.
<!-- END GENERATED: release -->

**Explore the data:** <https://emissions.hawanama.org> is an interactive explorer of this
inventory, a website of the [Pakistan Air Quality Initiative](https://pakairquality.com). It
is deployed separately and can serve an earlier release than the one in this repository.
**Public repository:** <https://github.com/PakAirQuality/pakistan-emissions-sectors>, a copy
of each release without the third-party source documents (`PUBLIC_MIRROR.md` there says what
is left out and where its checksums are).

The common account reconciles Pakistani fuel consumption, physical production, household fuel,
biomass and nitrogen flows before applying source-specific emissions methods. It distinguishes
activity, factor, control, coverage and allocation assumptions. The maintained main article is
[the integrated national manuscript](paper_national/versions/v3/paper.tex); the longer report
and sector technical notes supply detailed methods. This is a research inventory, not an
official national submission.

## Products and configurations

<!-- BEGIN GENERATED: products -->
| Family | Product | Entry point | Status |
|---|---|---|---|
| Annual | `annual.reference_year` | `outputs/national_all_sectors.csv` | mature |
| Annual | `annual.panel` | `outputs/pakemis_annual_fy2015_16_fy2024_25.csv` | mature |
| Annual | `annual.completeness_mass` | `outputs/pakemis_completeness_mass.csv` | new |
| Annual | `annual.atomic` | `outputs/pakemis_atomic_annual.csv` | mature |
| Annual | `annual.configurations` | `outputs/pakemis_ghg_configuration_atoms.csv` | current |
| Annual | `annual.air` | `outputs/pakemis_air_annual_fy2015_16_fy2024_25.csv` | current |
| Annual | `annual.extension_provisional` | `outputs/pakemis_fy2025_26_provisional_emissions.csv` | current |
| Monthly | `monthly.panel` | `outputs/pakemis_monthly_fy2015_16_fy2024_25.csv` | allocation, not observation |
| Monthly | `monthly.coverage` | `outputs/pakemis_monthly_coverage_summary.csv` | complete |
| Monthly | `monthly.configurations` | `outputs/pakemis_ghg_configuration_monthly.csv` | current |
| Monthly | `monthly.air` | `outputs/pakemis_air_monthly.csv` | current |
| Spatial | `spatial.rice_geography_crosscheck` | `outputs/pakemis_rice_geography_crosscheck.csv` | new |
| Spatial | `spatial.stream_support_ledger` | `outputs/pakemis_stream_support_ledger.csv` | new |
| Spatial | `spatial.adm2_frame_2022` | `outputs/pakemis_adm2_frame_2022.csv` | new |
| Spatial | `spatial.grid_0p1_edgar_aligned` | `outputs/pakemis_grid_0p1_edgar_aligned.nc` | new |
| Spatial | `spatial.agri_reference_panel_divergence` | `outputs/agri_reference_panel_divergence.csv` | new |
| Spatial | `spatial.cube` | `outputs/pakemis_grid_0p05_monthly.nc` | allocation, partly observed |
| Spatial | `spatial.cube_annual` | `outputs/pakemis_grid_0p05_annual_ref_fy2015_16_fy2024_25.nc` | allocation, evidence-graded per stream and period |
| Spatial | `spatial.by_year` | `outputs/pakemis_adm1_by_year.csv` | allocation, source-specific temporal evidence |
| Spatial | `spatial.unallocated` | `outputs/pakemis_spatial_unallocated.csv` | declared, not gridded |
| Spatial | `spatial.configurations` | `outputs/pakemis_ghg_configuration_adm2.csv` | current |
| Uncertainty | `uncertainty.reference_year` | `outputs/national_uncertainty_montecarlo.csv` | legacy, reference year |
| Uncertainty | `uncertainty.common_ensemble` | `outputs/pakemis_ensemble_summary.csv` | joinable, reference year |
| Uncertainty | `uncertainty.ghg_native` | `outputs/pakemis_ghg_conditional_uncertainty.csv` | current |
| Uncertainty | `uncertainty.air` | `outputs/pakemis_air_conditional_uncertainty.csv` | current |
| Semantic layer | `semantic.release` | `outputs/semantic/semantic_release.json` | mature |
| Semantic layer | `semantic.facts` | `outputs/semantic/fact_annual.csv` | mature |
| Semantic layer | `semantic.dimensions` | `outputs/semantic/dim_period.csv` | mature |
<!-- END GENERATED: products -->

The core includes ten fiscal years and 120 months. FY2023–24 remains the detailed reference
year. Annual national, ADM1, ADM2 and gridded records and supported monthly allocations retain
period, configuration, species, provenance and unallocated mass. A separate FY2025–26 provisional
source extension never forms a common-scope national total. Calendar 2026 is incomplete at the
14 October 2026 source audit.

Four configurations combine household survey fuel (S) or combustion of all diverted dung (L)
with TAN or IPCC nitrogen volatilisation methods: `S_TAN`, `L_TAN`, `S_IPCC`, `L_IPCC`.
Under S, the destinations of diverted dung remain unresolved; its surveyed household
combustion does not imply that the remainder is burned elsewhere.
Alternatives are not added or probability-weighted. Conditional parameter intervals and paired
trend draws are separate from structural cases, missing categories and allocation uncertainty.
BC and OC are components of particulate mass; nested species must not be summed.

## Reproduction

`make dev` materialises canonical inputs and incrementally rebuilds products. `make build-plan`
shows dependencies. `make release-check` runs the strict pipeline and verifies retained source
hashes. Run `PYTHONPATH=src:tests python3 -m unittest discover -s tests` from the repository root.
The dependency lock and [local-package reproduction instructions](docs/deposit_rebuild_limits.md)
distinguish regeneration from compiled activity tables from primary-document re-extraction.

The public query and download layers use the same period, configuration and species vocabulary.
`outputs/semantic/semantic_release.json` records verified table identities. Unsupported requests
receive typed refusals; a source-only extension or absent category cannot become a zero national total.

## Reference-year GHG results

The table gives FY2023–24 module totals. The displayed symmetric percentages are the existing
Approach-1 diagnostics; the native conditional-ensemble products carry the separately published
percentile intervals. Captive power's calculation module and IPCC reporting category differ.

<!-- BEGIN GENERATED: sectors -->
| Sector | IPCC | Year | Mt CO2e (AR5) | +/- % |
|---|---|---|---:|---:|
| Agriculture | 3.A-3.H | 2024 | 223.04 | 19.1 |
| Electricity + captive generation (family power_grid_control: grid 38.51 / 40.11 / 44.12 / 57.95 within the module figure) | 1A1a + 1A2 | 2023 | 45.66 | 26.8 |
| Road transport + mixed off-road | 1A3b + 1A4c/1A2 | 2024 | 41.93 | 11.4 |
| Waste | 4A, 4C2, 4D1 | 2024 | 37.45 | 51.1 |
| Industrial processes | 2A1 | 2024 | 25.54 | 8.1 |
| Residential fuel | 1A4b | 2024 | 24.22 | 23.2 |
| Oil & gas fugitives | 1B2 | 2024 | 23.50 | 37.7 |
| Industrial combustion | 1A2 | 2024 | 22.58 | 18.7 |
| Railways | 1A3c + 1A2/1A4c | 2024 | 0.39 | 14.6 |
| Domestic aviation | 1A3a ii | 2023 | 0.30 | 58.8 |
| **Total (configuration S, the reference)** | | FY2023-24 | **444.61** | **11.2** |
| **Total (configuration L)** | | FY2023-24 | **449.85** | **11.3** |
<!-- END GENERATED: sectors -->

## Coverage and fitness for use

<!-- BEGIN GENERATED: coverage -->
The GHG completeness register contains 138 category–gas records: 54 estimated, 70 not estimated, 9 included elsewhere, 4 not occurring and 1 not applicable. The separate air coverage matrix reports source/process × species × year. Missing estimates are notation statuses, not zero. Differences from EDGAR or another inventory are matched-boundary comparisons; their residuals are not automatically estimates of missing PakEmis emissions.
<!-- END GENERATED: coverage -->

LULUCF, unestimated F-gases, coal-mining fugitives and unresolved industrial categories remain
outside estimated totals. Admitted power oil/diesel SO2 is separated from unresolved coal
control cases. Road exhaust, evaporation and wear exclude resuspended dust. Household estimates
are gross appliance emissions, not measured outdoor releases. Grid spacing is not observed
activity resolution; fixed or substituted geography and temporal proxies are explicitly labelled.
Per-cell mass requires area and duration conversion before use as a flux.

## Source custody and licences

`outputs/pakemis_source_register.csv` identifies held source documents and checksums;
`outputs/pakemis_deposit_manifest.csv` identifies distributable package files and their terms.
Holding a public document does not grant redistribution rights. Code is MIT licensed.
Project-owned primary data, figures and text use CC BY 4.0 with per-file upstream terms.
ODbL-derived databases and affected legacy spatial products form a separate companion.
Primary geographic products are rebuilt without OpenStreetMap geometry or weights; the
product-specific audit accompanies the package. See [LICENSE-data](LICENSE-data) and
[LICENSE-ODbL](LICENSE-ODbL).

## Release review

The [repair register](campaign/v3_readiness/repair_register.csv) and
[work log](campaign/v3_readiness/INTEGRATED_WORK_LOG.md) link verified defects to repairs and tests.
`outputs/pakemis_release_change_summary.csv` records matched before/after numerical changes;
previous release controls remain preserved under `data/baselines/rc67_integrated_campaign`.

<!-- BEGIN GENERATED: movers -->
1. **Resolve gas-system practice and facility activity.** The 2019 segment inventory makes
   fugitives 5.3% of national emissions and 3.1% of national Approach-1 variance. Pipeline
   length and utility throughput are now included; material, pressure, LDAR, compressor,
   processing-plant and well records are the binding evidence.
<!-- END GENERATED: movers -->

No external deposit or journal submission is claimed. The local review package contains
products, code, manuscript sources/PDFs, plotted data, metadata, checksums and reproduction
evidence. A public review deposit and persistent identifiers remain subsequent actions.
See [CITATION.cff](CITATION.cff) for the current title, version and attribution.

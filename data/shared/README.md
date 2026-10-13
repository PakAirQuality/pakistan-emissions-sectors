# Shared data data

Start with the readable CSV links below. Each asset has one owner; shared inputs are linked rather than copied.

`canonical/` contains generated, Git-versioned runtime/download CSVs. Edit the maintained source listed in the catalog, then run `make dev`; do not edit canonical copies independently.

Source identities remain stable even where the old identity looks like a former file path. See the [asset catalog](<../catalog/assets.csv>) for physical locations, producers, consumers and source references.

## Activity

Observed source quantities and verified extracts; generated compatibility views are identified separately.

| Asset | Authoring | Representation |
|---|---|---|
| [APCMA monthly cement dispatches](<canonical/activity/monthly/apcma_month_region_dispatch.csv>) | Generated | Readable canonical CSV |
| [Afr2025 offtake by product](<canonical/activity/nfdc/afr2025_offtake_by_product.csv>) | Generated | Readable canonical CSV |
| [Afr2025 production by manufacturer](<canonical/activity/nfdc/afr2025_production_by_manufacturer.csv>) | Generated | Readable canonical CSV |
| [Annex5 national month product](<canonical/activity/nfdc/annex5_national_month_product.csv>) | Maintained | Readable canonical CSV |
| [Annex7 province month product 2023-24](<canonical/activity/nfdc/annex7_province_month_product_2023-24.csv>) | Generated | Readable canonical CSV |
| [Livestock by district 2024](<activity/pbs_census/livestock_by_district_2024.csv>) | Maintained | table |
| [Livestock province 2024](<activity/pbs_census/livestock_province_2024.csv>) | Maintained | table |
| [NFDC monthly plant gas use](<canonical/activity/nfdc/afr2025_fertilizer_gas_monthly.csv>) | Generated | Readable canonical CSV |
| [NFDC monthly product offtake](<canonical/activity/monthly/nfdc_month_product_offtake.csv>) | Generated | Readable canonical CSV |
| [NFDC plant gas use](<canonical/activity/nfdc/afr2025_fertilizer_gas_by_plant.csv>) | Generated | Readable canonical CSV |
| [Nfdc production by product series](<canonical/activity/nfdc/nfdc_production_by_product_series.csv>) | Generated | Readable canonical CSV |
| [PBS monthly industrial production](<canonical/activity/monthly/pbs_qim_month_item.csv>) | Generated | Readable canonical CSV |
| [Pbs minerals month province](<canonical/activity/monthly/pbs_minerals_month_province.csv>) | Generated | Readable canonical CSV |

## Parameters

Emission factors, scientific assumptions, scenarios and applicability rules.

| Asset | Authoring | Representation |
|---|---|---|
| [Air emission factors](<canonical/parameters/air_emission_factors.csv>) | Maintained | Readable canonical CSV |
| [Coal booking policy](<canonical/parameters/coal_booking_policy.csv>) | Generated | Readable canonical CSV |
| [Emission factors](<canonical/parameters/emission_factors.csv>) | Generated | Readable canonical CSV |
| [Method registry](<parameters/method_registry.csv>) | Maintained | table |
| [Parameter scope](<parameters/parameter_scope.csv>) | Generated | table |
| [Parameter scope exclusions](<parameters/parameter_scope_exclusions.csv>) | Maintained | table |
| [Scenario variants](<parameters/scenario_variants.csv>) | Maintained | table |
| [Scenarios](<parameters/scenarios.csv>) | Generated | table |
| [Scope registry](<parameters/scope_registry.csv>) | Maintained | table |
| [Temporal driver registry](<parameters/temporal_driver_registry.csv>) | Generated | table |
| [Temporal profiles](<parameters/temporal_profiles.csv>) | Maintained | table |
| [Uncertainty reconciliation](<parameters/uncertainty_reconciliation.csv>) | Generated | table |

## Lookups

Names, identifiers, classifications and mappings used to interpret the observations.

| Asset | Authoring | Representation |
|---|---|---|
| [Category crosswalk](<lookups/category_crosswalk.csv>) | Maintained | table |
| [Facility registry](<canonical/lookups/facility_registry.csv>) | Generated | Readable canonical CSV |
| [Months](<lookups/months.csv>) | Generated | table |
| [Periods](<lookups/periods.csv>) | Generated | table |
| [Physical sources](<lookups/physical_sources.csv>) | Maintained | table |
| [Province shares](<canonical/lookups/province_shares.csv>) | Generated | Readable canonical CSV |
| [Stream reporting sector](<lookups/stream_reporting_sector.csv>) | Maintained | table |

## Gis

Spatial inputs. Keep geometry, CRS, provenance and licensing companion files together.

| Asset | Authoring | Representation |
|---|---|---|
| [Adm2 canonical](<canonical/gis/adm2_canonical.csv>) | Generated | Readable canonical CSV |
| [Adm2 crosswalk](<canonical/gis/adm2_crosswalk.csv>) | Generated | Readable canonical CSV |
| [Adm2 intersections 267x340](<gis/adm2_intersections_267x340.csv>) | Generated | table |
| [Adm2 intersections 267x340.csv](<gis/adm2_intersections_267x340.csv.txt>) | Maintained | gis |
| [Allowed grid fallbacks](<gis/allowed_grid_fallbacks.csv>) | Generated | table |
| [Boundary sources](<gis/BOUNDARY_SOURCES.json>) | Maintained | gis |
| [Cod ab sources](<gis/cod_ab/COD_AB_SOURCES.json>) | Maintained | gis |
| [Geometry sets](<gis/geometry_sets.csv>) | Maintained | table |
| [Ghs built s e2020 globe r2023a 54009 1000 v1 0 r6 c25](<gis/manual/ghsl_built_1km/GHS_BUILT_S_E2020_GLOBE_R2023A_54009_1000_V1_0_R6_C25.tif>) | Maintained | gis |
| [Ghs built s e2020 globe r2023a 54009 1000 v1 0 r6 c26](<gis/manual/ghsl_built_1km/GHS_BUILT_S_E2020_GLOBE_R2023A_54009_1000_V1_0_R6_C26.tif>) | Maintained | gis |
| [Ghs built s e2020 globe r2023a 54009 1000 v1 0 r7 c25](<gis/manual/ghsl_built_1km/GHS_BUILT_S_E2020_GLOBE_R2023A_54009_1000_V1_0_R7_C25.tif>) | Maintained | gis |
| [Ghs built s e2020 globe r2023a 54009 1000 v1 0 r7 c26](<gis/manual/ghsl_built_1km/GHS_BUILT_S_E2020_GLOBE_R2023A_54009_1000_V1_0_R7_C26.tif>) | Maintained | gis |
| [Ghs built s nres e2020 globe r2023a 54009 1000 v1 0 r6 c25](<gis/manual/ghsl_built_1km/GHS_BUILT_S_NRES_E2020_GLOBE_R2023A_54009_1000_V1_0_R6_C25.tif>) | Maintained | gis |
| [Ghs built s nres e2020 globe r2023a 54009 1000 v1 0 r6 c26](<gis/manual/ghsl_built_1km/GHS_BUILT_S_NRES_E2020_GLOBE_R2023A_54009_1000_V1_0_R6_C26.tif>) | Maintained | gis |
| [Ghs built s nres e2020 globe r2023a 54009 1000 v1 0 r7 c25](<gis/manual/ghsl_built_1km/GHS_BUILT_S_NRES_E2020_GLOBE_R2023A_54009_1000_V1_0_R7_C25.tif>) | Maintained | gis |
| [Ghs built s nres e2020 globe r2023a 54009 1000 v1 0 r7 c26](<gis/manual/ghsl_built_1km/GHS_BUILT_S_NRES_E2020_GLOBE_R2023A_54009_1000_V1_0_R7_C26.tif>) | Maintained | gis |
| [Ghsl sources](<gis/manual/ghsl_built_1km/GHSL_SOURCES.json>) | Maintained | gis |
| [Grid proxy semantics](<canonical/gis/grid_proxy_semantics.csv>) | Maintained | Readable canonical CSV |
| [Osm building fraction 267x340](<gis/osm_building_fraction_267x340.npy>) | Generated | gis |
| [Osm building fraction 267x340.npy](<gis/osm_building_fraction_267x340.npy.txt>) | Maintained | gis |
| [Pak adm1](<gis/PAK_ADM1.geojson>) | Generated | gis |
| [Pak adm2](<gis/PAK_ADM2.geojson>) | Generated | gis |
| [Pak admin boundaries.geojson](<gis/cod_ab/pak_admin_boundaries.geojson.zip>) | Maintained | gis |
| [Pak admin2](<gis/cod_ab/pak_admin2.geojson>) | Maintained | gis |
| [Proxy builtup 267x340](<gis/proxy_builtup_267x340.npy>) | Generated | gis |
| [Proxy builtup 267x340.npy](<gis/proxy_builtup_267x340.npy.txt>) | Maintained | gis |
| [Proxy population 267x340](<gis/proxy_population_267x340.npy>) | Generated | gis |
| [Proxy population 267x340.npy](<gis/proxy_population_267x340.npy.txt>) | Maintained | gis |
| [Proxy sources](<gis/PROXY_SOURCES.md>) | Maintained | gis |
| [Release heights](<gis/release_heights.csv>) | Maintained | table |
| [Stream geometry](<gis/stream_geometry.csv>) | Maintained | table |
| [Stream grid proxy](<canonical/gis/stream_grid_proxy.csv>) | Maintained | Readable canonical CSV |
| [Stream spatial alternatives](<gis/stream_spatial_alternatives.csv>) | Maintained | table |
| [Worldpop pak 2020 1km](<gis/worldpop_pak_2020_1km.tif>) | Maintained | gis |

## Evidence

Independent comparisons, diagnostics, source extracts and evidence supporting interpretation.

| Asset | Authoring | Representation |
|---|---|---|
| [Benchmark tasks](<evidence/benchmark_tasks.csv>) | Generated | table |
| [Benchmarks](<canonical/evidence/benchmarks.csv>) | Maintained | Readable canonical CSV |
| [Benchmarks air](<canonical/evidence/benchmarks_air.csv>) | Maintained | Readable canonical CSV |
| [Brick kilns pk](<evidence/ml/brick_kilns_pk.csv>) | Maintained | table |
| [Claim matrix](<evidence/claim_matrix.csv>) | Maintained | table |
| [Claims registry](<evidence/claims_registry.csv>) | Maintained | table |
| [Livestock validation](<evidence/validation/livestock_validation.csv>) | Generated | table |
| [Pakistan BTR1 national inventory 2020-21](<canonical/evidence/btr1_national_inventory.csv>) | Maintained | Readable canonical CSV |
| [Spatial kiln allocation](<evidence/benchmark_splits/spatial_kiln_allocation.csv>) | Generated | table |
| [Spatial rice mnfsr](<evidence/benchmark_splits/spatial_rice_mnfsr.csv>) | Generated | table |
| [Spatial rice punjabcrs](<evidence/benchmark_splits/spatial_rice_punjabcrs.csv>) | Generated | table |
| [Spatial road transport](<evidence/benchmark_splits/spatial_road_transport.csv>) | Generated | table |
| [Spatial wheat mnfsr](<evidence/benchmark_splits/spatial_wheat_mnfsr.csv>) | Generated | table |
| [Temporal origins](<evidence/benchmark_splits/temporal_origins.csv>) | Generated | table |
| [Transcription checks](<evidence/transcription_checks.csv>) | Maintained | table |
| [Validation catalog](<evidence/validation_catalog.csv>) | Generated | table |

## Metadata

Coverage descriptions, source inventories and schema documentation.

| Asset | Authoring | Representation |
|---|---|---|
| [Air coverage absences](<metadata/air_coverage_absences.csv>) | Maintained | table |
| [Air source classes](<metadata/air_source_classes.csv>) | Maintained | table |
| [Availability matrix](<metadata/availability_matrix.csv>) | Maintained | table |
| [Bridge configurations](<metadata/bridge_configurations.csv>) | Maintained | table |
| [Cross sector ledger map](<metadata/cross_sector_ledger_map.csv>) | Maintained | table |
| [Dependency group rules](<metadata/dependency_group_rules.csv>) | Maintained | table |
| [Edgar domain map](<metadata/edgar_domain_map.csv>) | Maintained | table |
| [Member bindings](<metadata/member_bindings.csv>) | Maintained | table |
| [Residual classes](<metadata/residual_classes.csv>) | Maintained | table |

## Requests

Outstanding data requests, letters and prospective templates. Templates are not observations.

| Asset | Authoring | Representation |
|---|---|---|
| [Data gaps](<requests/data_gaps.csv>) | Maintained | table |
| [Monthly data request register](<requests/monthly_request_register.csv>) | Maintained | table |
| [Monthly request compatibility view](<requests/views/monthly_data_requests.csv>) | Generated compatibility view | table |
| [Monthly request sector components](<requests/monthly_request_components.csv>) | Maintained | table |


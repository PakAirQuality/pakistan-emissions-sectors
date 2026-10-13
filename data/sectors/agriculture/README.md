# Agriculture data

Start with the readable CSV links below. Each asset has one owner; shared inputs are linked rather than copied.

`canonical/` contains generated, Git-versioned runtime/download CSVs. Edit the maintained source listed in the catalog, then run `make dev`; do not edit canonical copies independently.

Source identities remain stable even where the old identity looks like a former file path. See the [asset catalog](<../../catalog/assets.csv>) for physical locations, producers, consumers and source references.

## Activity

Observed source quantities and verified extracts; generated compatibility views are identified separately.

| Asset | Authoring | Representation |
|---|---|---|
| [District crop series](<canonical/activity/crop_district_panel.csv>) | Generated | Readable canonical CSV |
| [District livestock census](<canonical/activity/livestock_district_2024.csv>) | Maintained | Readable canonical CSV |
| [Fao harvest sessions](<canonical/activity/fao_harvest_sessions.csv>) | Generated | Readable canonical CSV |
| [Faostat emissions](<canonical/activity/historical/faostat_emissions.csv>) | Generated | Readable canonical CSV |
| [Historical crop series](<canonical/activity/historical/crops.csv>) | Generated | Readable canonical CSV |
| [Historical livestock stocks](<canonical/activity/historical/livestock_stocks.csv>) | Generated | Readable canonical CSV |
| [Historical nitrogen fertiliser](<canonical/activity/historical/fertilizer_n.csv>) | Generated | Readable canonical CSV |
| [National fertiliser nutrients, 2023-24](<canonical/activity/fertilizer_2024.csv>) | Maintained | Readable canonical CSV |
| [National livestock census and projections](<canonical/activity/livestock_2024.csv>) | Maintained | Readable canonical CSV |
| [Pakistan Economic Survey annual series](<canonical/activity/es_fiscal_series.csv>) | Maintained | Readable canonical CSV |
| [Pakistan Economic Survey crops, 2023-24](<canonical/activity/crops_2024.csv>) | Maintained | Readable canonical CSV |
| [Provincial livestock census](<canonical/activity/livestock_province_2024.csv>) | Maintained | Readable canonical CSV |

## Parameters

Emission factors, scientific assumptions, scenarios and applicability rules.

| Asset | Authoring | Representation |
|---|---|---|
| [Burning params](<canonical/parameters/burning_params.csv>) | Maintained | Readable canonical CSV |
| [Cui2021 pak ef](<parameters/cui2021_pak_ef.csv>) | Maintained | table |
| [Fertilizer calendar](<parameters/fertilizer_calendar.csv>) | Maintained | table |
| [Gleam mms](<canonical/parameters/gleam_mms.csv>) | Maintained | Readable canonical CSV |
| [Mms shares](<canonical/parameters/mms_shares.csv>) | Maintained | Readable canonical CSV |
| [Nfdc offtake](<parameters/nfdc_offtake.csv>) | Maintained | table |
| [Nowcast params](<parameters/nowcast_params.csv>) | Maintained | table |
| [Parameters](<canonical/parameters/parameters.csv>) | Generated | Readable canonical CSV |
| [Residue params](<canonical/parameters/residue_params.csv>) | Maintained | Readable canonical CSV |
| [Rice calendar](<canonical/parameters/rice_calendar.csv>) | Maintained | Readable canonical CSV |
| [Rice temperature climatology](<parameters/rice_temperature_climatology.csv>) | Maintained | table |

## Gis

Spatial inputs. Keep geometry, CRS, provenance and licensing companion files together.

| Asset | Authoring | Representation |
|---|---|---|
| [Firms fire](<gis/manual/firms_fire.csv>) | Maintained | table |
| [Firms sources](<gis/manual/FIRMS_SOURCES.json>) | Maintained | gis |
| [Gcd rice 2023](<gis/manual/gcd_rice_2023.tif>) | Maintained | gis |
| [Proxy cropland 267x340](<gis/proxy_cropland_267x340.npy>) | Generated | gis |
| [Proxy cropland 267x340.npy](<gis/proxy_cropland_267x340.npy.txt>) | Maintained | gis |
| [Proxy gcd rice 267x340](<gis/proxy_gcd_rice_267x340.npy>) | Generated | gis |
| [Proxy gcd rice 267x340.npy](<gis/proxy_gcd_rice_267x340.npy.txt>) | Maintained | gis |
| [Proxy glw livestock 267x340](<gis/proxy_glw_livestock_267x340.npy>) | Generated | gis |
| [Proxy glw livestock 267x340.npy](<gis/proxy_glw_livestock_267x340.npy.txt>) | Maintained | gis |
| [Proxy manure applied 267x340](<gis/proxy_manure_applied_267x340.npy>) | Generated | gis |
| [Proxy manure applied 267x340.npy](<gis/proxy_manure_applied_267x340.npy.txt>) | Maintained | gis |
| [Rice sources](<gis/manual/RICE_SOURCES.json>) | Maintained | gis |
| [Spam rice](<gis/manual/spam_rice.tif>) | Maintained | gis |
| [Spam2020 v2r2 global a rice i](<gis/manual/spam2020_V2r2_global_A_RICE_I.tif>) | Maintained | gis |
| [Spam2020 v2r2 global a rice r](<gis/manual/spam2020_V2r2_global_A_RICE_R.tif>) | Maintained | gis |

## Evidence

Independent comparisons, diagnostics, source extracts and evidence supporting interpretation.

| Asset | Authoring | Representation |
|---|---|---|
| [District rice area mnfsr 2022-23](<evidence/district_records/district_rice_area_MNFSR_2022-23.csv>) | Maintained | table |
| [District rice area punjabcrs 2022-25](<evidence/district_records/district_rice_area_PunjabCRS_2022-25.csv>) | Maintained | table |
| [District wheat area mnfsr 2022-23](<evidence/district_records/district_wheat_area_MNFSR_2022-23.csv>) | Maintained | table |
| [Gleam mms south asia](<evidence/gleam/gleam_mms_south_asia.csv>) | Maintained | table |

## Shared inputs

| Asset | Purpose |
|---|---|
| [NFDC monthly product offtake](<../../shared/canonical/activity/monthly/nfdc_month_product_offtake.csv>) | activity |
| [NFDC plant gas use](<../../shared/canonical/activity/nfdc/afr2025_fertilizer_gas_by_plant.csv>) | activity |
| [NFDC monthly plant gas use](<../../shared/canonical/activity/nfdc/afr2025_fertilizer_gas_monthly.csv>) | activity |
| [Afr2025 offtake by product](<../../shared/canonical/activity/nfdc/afr2025_offtake_by_product.csv>) | activity |
| [Afr2025 production by manufacturer](<../../shared/canonical/activity/nfdc/afr2025_production_by_manufacturer.csv>) | activity |
| [Annex5 national month product](<../../shared/canonical/activity/nfdc/annex5_national_month_product.csv>) | activity |
| [Annex7 province month product 2023-24](<../../shared/canonical/activity/nfdc/annex7_province_month_product_2023-24.csv>) | activity |
| [Nfdc production by product series](<../../shared/canonical/activity/nfdc/nfdc_production_by_product_series.csv>) | activity |
| [Adm2 canonical](<../../shared/canonical/gis/adm2_canonical.csv>) | gis |
| [Adm2 crosswalk](<../../shared/canonical/gis/adm2_crosswalk.csv>) | gis |
| [Benchmarks air](<../../shared/canonical/evidence/benchmarks_air.csv>) | evidence |
| [Emission factors](<../../shared/canonical/parameters/emission_factors.csv>) | parameters |
| [Facility registry](<../../shared/canonical/lookups/facility_registry.csv>) | lookups |
| [Grid proxy semantics](<../../shared/canonical/gis/grid_proxy_semantics.csv>) | gis |
| [Province shares](<../../shared/canonical/lookups/province_shares.csv>) | lookups |
| [Monthly request sector components](<../../shared/requests/monthly_request_components.csv>) | requests |
| [Monthly data request register](<../../shared/requests/monthly_request_register.csv>) | requests |


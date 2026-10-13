# Industry data

Start with the readable CSV links below. Each asset has one owner; shared inputs are linked rather than copied.

`canonical/` contains generated, Git-versioned runtime/download CSVs. Edit the maintained source listed in the catalog, then run `make dev`; do not edit canonical copies independently.

Source identities remain stable even where the old identity looks like a former file path. See the [asset catalog](<../../catalog/assets.csv>) for physical locations, producers, consumers and source references.

## Activity

Observed source quantities and verified extracts; generated compatibility views are identified separately.

| Asset | Authoring | Representation |
|---|---|---|
| [Brick kiln fleet observations](<canonical/activity/brick_kiln_fleet_observations.csv>) | Generated | Readable canonical CSV |
| [Brick-kiln coal use and energy](<canonical/activity/brick_kiln_coal.csv>) | Maintained | Readable canonical CSV |
| [Coal use by consumer](<canonical/activity/coal_by_consumer.csv>) | Maintained | Readable canonical CSV |
| [Coal use by sector and publication edition](<canonical/activity/coal_by_sector_vintages.csv>) | Generated | Readable canonical CSV |
| [Coal use by sector, energy yearbook compendium](<canonical/activity/coal_by_sector_pey_compendium.csv>) | Generated | Readable canonical CSV |
| [Edgar pak industry ap series](<canonical/activity/edgar_pak_industry_ap_series.csv>) | Generated | Readable canonical CSV |
| [Edgar pak industry series](<canonical/activity/edgar_pak_industry_series.csv>) | Generated | Readable canonical CSV |
| [Fuel sulfur observations](<canonical/activity/fuel_sulfur_observations.csv>) | Generated | Readable canonical CSV |
| [Furnace oil grade mix](<canonical/activity/furnace_oil_grade_mix.csv>) | Generated | Readable canonical CSV |
| [Gas consumption by sector](<canonical/activity/gas_consumption.csv>) | Generated | Readable canonical CSV |
| [Gem cement pak](<canonical/activity/gem_cement_pak.csv>) | Generated | Readable canonical CSV |
| [National coal supply](<canonical/activity/coal_supply.csv>) | Maintained | Readable canonical CSV |
| [OCAC detailed customer-group sales](<canonical/activity/ocac_non_energy_sectoral.csv>) | Generated | Readable canonical CSV |
| [Provincial coal production](<canonical/activity/coal_production_by_province.csv>) | Generated | Readable canonical CSV |

## Parameters

Emission factors, scientific assumptions, scenarios and applicability rules.

| Asset | Authoring | Representation |
|---|---|---|
| [Industry params](<canonical/parameters/industry_params.csv>) | Maintained | Readable canonical CSV |

## Gis

Spatial inputs. Keep geometry, CRS, provenance and licensing companion files together.

| Asset | Authoring | Representation |
|---|---|---|
| [Brick kiln sources](<gis/BRICK_KILN_SOURCES.json>) | Generated | gis |
| [Pak brick kiln assets](<gis/pak_brick_kiln_assets.csv>) | Generated | table |
| [Pak brick kiln coverage](<gis/pak_brick_kiln_coverage.csv>) | Generated | table |

## Evidence

Independent comparisons, diagnostics, source extracts and evidence supporting interpretation.

| Asset | Authoring | Representation |
|---|---|---|
| [Brick kiln activity evidence](<canonical/evidence/brick_kiln_activity_evidence.csv>) | Maintained | Readable canonical CSV |
| [Fuel sulfur evidence](<canonical/evidence/fuel_sulfur_evidence.csv>) | Maintained | Readable canonical CSV |

## Shared inputs

| Asset | Purpose |
|---|---|
| [PBS monthly industrial production](<../../shared/canonical/activity/monthly/pbs_qim_month_item.csv>) | activity |
| [Air emission factors](<../../shared/canonical/parameters/air_emission_factors.csv>) | parameters |
| [Air source classes](<../../shared/metadata/air_source_classes.csv>) | metadata |
| [Benchmarks](<../../shared/canonical/evidence/benchmarks.csv>) | evidence |
| [Coal booking policy](<../../shared/canonical/parameters/coal_booking_policy.csv>) | parameters |
| [Emission factors](<../../shared/canonical/parameters/emission_factors.csv>) | parameters |
| [Province shares](<../../shared/canonical/lookups/province_shares.csv>) | lookups |
| [Monthly request sector components](<../../shared/requests/monthly_request_components.csv>) | requests |
| [Monthly data request register](<../../shared/requests/monthly_request_register.csv>) | requests |


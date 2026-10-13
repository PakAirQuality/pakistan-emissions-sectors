# Aviation data

Start with the readable CSV links below. Each asset has one owner; shared inputs are linked rather than copied.

`canonical/` contains generated, Git-versioned runtime/download CSVs. Edit the maintained source listed in the catalog, then run `make dev`; do not edit canonical copies independently.

Source identities remain stable even where the old identity looks like a former file path. See the [asset catalog](<../../catalog/assets.csv>) for physical locations, producers, consumers and source references.

## Activity

Observed source quantities and verified extracts; generated compatibility views are identified separately.

| Asset | Authoring | Representation |
|---|---|---|
| [Adsblol pilot fy2023 24](<activity/adsblol_pilot_fy2023_24.json>) | Generated | document |
| [Aircraft family shares 2023 24](<canonical/activity/aircraft_family_shares_2023_24.csv>) | Maintained | Readable canonical CSV |
| [Airport controls 2023 24](<canonical/activity/airport_controls_2023_24.csv>) | Maintained | Readable canonical CSV |
| [Airports](<canonical/activity/airports.csv>) | Maintained | Readable canonical CSV |
| [Climatetrace airport monthly extract](<canonical/activity/climatetrace_airport_monthly_extract.csv>) | Generated | Readable canonical CSV |
| [Climatetrace national monthly extract](<canonical/activity/climatetrace_national_monthly_extract.csv>) | Generated | Readable canonical CSV |
| [Era5 route weather extract](<canonical/activity/era5_route_weather_extract.csv>) | Generated | Readable canonical CSV |
| [Fuel controls 2023 24](<canonical/activity/fuel_controls_2023_24.csv>) | Generated compatibility view | Readable canonical CSV |
| [Fuel sales](<canonical/activity/fuel_sales.csv>) | Generated | Readable canonical CSV |
| [International airports](<canonical/activity/international_airports.csv>) | Maintained | Readable canonical CSV |
| [OCAC aviation fuel sales](<canonical/activity/ocac_annual_extract.csv>) | Generated | Readable canonical CSV |
| [Ocac annual sources](<canonical/activity/ocac_annual_sources.csv>) | Maintained | Readable canonical CSV |
| [Ocac cumulative sources](<canonical/activity/ocac_cumulative_sources.csv>) | Maintained | Readable canonical CSV |
| [Ocac monthly extract](<canonical/activity/ocac_monthly_extract.csv>) | Generated | Readable canonical CSV |
| [Oecd monthly extract](<canonical/activity/oecd_monthly_extract.csv>) | Generated | Readable canonical CSV |
| [PCAA airline traffic, 2023-24](<canonical/activity/airline_controls_2023_24.csv>) | Maintained | Readable canonical CSV |
| [PCAA airport traffic](<canonical/activity/movements_airport.csv>) | Generated | Readable canonical CSV |
| [Unfccc inventory controls](<canonical/activity/unfccc_inventory_controls.csv>) | Maintained | Readable canonical CSV |

## Parameters

Emission factors, scientific assumptions, scenarios and applicability rules.

| Asset | Authoring | Representation |
|---|---|---|
| [Aviation engine map](<canonical/parameters/aviation_engine_map.csv>) | Maintained | Readable canonical CSV |
| [Aviation fleet mix](<canonical/parameters/aviation_fleet_mix.csv>) | Maintained | Readable canonical CSV |
| [Aviation params](<canonical/parameters/aviation_params.csv>) | Maintained | Readable canonical CSV |

## Lookups

Names, identifiers, classifications and mappings used to interpret the observations.

| Asset | Authoring | Representation |
|---|---|---|
| [Aircraft aliases](<canonical/lookups/aircraft_aliases.csv>) | Maintained | Readable canonical CSV |
| [Airport aliases](<canonical/lookups/airport_aliases.csv>) | Generated | Readable canonical CSV |
| [Airport coordinate overrides](<canonical/lookups/airport_coordinate_overrides.csv>) | Generated | Readable canonical CSV |
| [Operator groups](<canonical/lookups/operator_groups.csv>) | Maintained | Readable canonical CSV |

## Evidence

Independent comparisons, diagnostics, source extracts and evidence supporting interpretation.

| Asset | Authoring | Representation |
|---|---|---|
| [Aviation extract crt](<evidence/unfccc/aviation_extract_crt.json>) | Generated | document |
| [Aviation extract crt audit](<evidence/unfccc/aviation_extract_crt_audit.json>) | Generated | document |
| [Benchmarks](<canonical/evidence/benchmarks.csv>) | Maintained | Readable canonical CSV |
| [Control reconciliation 2023 24](<canonical/evidence/control_reconciliation_2023_24.csv>) | Maintained | Readable canonical CSV |
| [Route evidence 2023 24](<canonical/evidence/route_evidence_2023_24.csv>) | Maintained | Readable canonical CSV |
| [UNFCCC aviation extract crt](<canonical/evidence/unfccc/aviation_extract_crt.csv>) | Generated | Readable canonical CSV |
| [UNFCCC aviation extract crt audit](<canonical/evidence/unfccc/aviation_extract_crt_audit.csv>) | Generated | Readable canonical CSV |

## Metadata

Coverage descriptions, source inventories and schema documentation.

| Asset | Authoring | Representation |
|---|---|---|
| [Source manifest](<metadata/source_manifest.csv>) | Generated | table |

## Shared inputs

| Asset | Purpose |
|---|---|
| [Benchmarks](<../../shared/canonical/evidence/benchmarks.csv>) | evidence |
| [Emission factors](<../../shared/canonical/parameters/emission_factors.csv>) | parameters |
| [Facility registry](<../../shared/canonical/lookups/facility_registry.csv>) | lookups |
| [Grid proxy semantics](<../../shared/canonical/gis/grid_proxy_semantics.csv>) | gis |
| [Province shares](<../../shared/canonical/lookups/province_shares.csv>) | lookups |
| [Monthly request sector components](<../../shared/requests/monthly_request_components.csv>) | requests |
| [Monthly data request register](<../../shared/requests/monthly_request_register.csv>) | requests |


# Residential data

Start with the readable CSV links below. Each asset has one owner; shared inputs are linked rather than copied.

`canonical/` contains generated, Git-versioned runtime/download CSVs. Edit the maintained source listed in the catalog, then run `make dev`; do not edit canonical copies independently.

Source identities remain stable even where the old identity looks like a former file path. See the [asset catalog](<../../catalog/assets.csv>) for physical locations, producers, consumers and source references.

## Activity

Observed source quantities and verified extracts; generated compatibility views are identified separately.

| Asset | Authoring | Representation |
|---|---|---|
| [Fuel supply](<canonical/activity/fuel_supply.csv>) | Generated compatibility view | Readable canonical CSV |
| [Fuel supply annotations](<canonical/activity/fuel_supply_annotations.csv>) | Maintained | Readable canonical CSV |
| [Fuel supply history](<canonical/activity/fuel_supply_history.csv>) | Generated compatibility view | Readable canonical CSV |
| [Fuel supply observations](<canonical/activity/fuel_supply_observations.csv>) | Maintained | Readable canonical CSV |
| [HIES national fuel estimates](<canonical/activity/hies/hies_national_totals.csv>) | Generated | Readable canonical CSV |
| [HIES provincial fuel estimates](<canonical/activity/hies/hies_fuel_quantities.csv>) | Generated | Readable canonical CSV |
| [Monthly degree days](<canonical/activity/monthly_degree_days.csv>) | Generated | Readable canonical CSV |
| [Stove mix mtf](<canonical/activity/stove_mix_mtf.csv>) | Maintained | Readable canonical CSV |
| [Woodfuel](<canonical/activity/woodfuel.csv>) | Maintained | Readable canonical CSV |

## Parameters

Emission factors, scientific assumptions, scenarios and applicability rules.

| Asset | Authoring | Representation |
|---|---|---|
| [Residential params](<canonical/parameters/residential_params.csv>) | Maintained | Readable canonical CSV |

## Evidence

Independent comparisons, diagnostics, source extracts and evidence supporting interpretation.

| Asset | Authoring | Representation |
|---|---|---|
| [Hies diagnostics](<canonical/evidence/hies/hies_diagnostics.csv>) | Generated | Readable canonical CSV |
| [Official benchmarks](<canonical/evidence/official_benchmarks.csv>) | Maintained | Readable canonical CSV |
| [Residential extract](<evidence/unfccc/residential_extract.json>) | Generated | document |
| [UNFCCC residential extract](<canonical/evidence/unfccc/residential_extract.csv>) | Generated | Readable canonical CSV |

## Shared inputs

| Asset | Purpose |
|---|---|
| [Adm2 canonical](<../../shared/canonical/gis/adm2_canonical.csv>) | gis |
| [Adm2 crosswalk](<../../shared/canonical/gis/adm2_crosswalk.csv>) | gis |
| [Emission factors](<../../shared/canonical/parameters/emission_factors.csv>) | parameters |
| [Facility registry](<../../shared/canonical/lookups/facility_registry.csv>) | lookups |
| [Grid proxy semantics](<../../shared/canonical/gis/grid_proxy_semantics.csv>) | gis |
| [Province shares](<../../shared/canonical/lookups/province_shares.csv>) | lookups |
| [Monthly request sector components](<../../shared/requests/monthly_request_components.csv>) | requests |
| [Monthly data request register](<../../shared/requests/monthly_request_register.csv>) | requests |


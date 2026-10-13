# Railways data

Start with the readable CSV links below. Each asset has one owner; shared inputs are linked rather than copied.

`canonical/` contains generated, Git-versioned runtime/download CSVs. Edit the maintained source listed in the catalog, then run `make dev`; do not edit canonical copies independently.

Source identities remain stable even where the old identity looks like a former file path. See the [asset catalog](<../../catalog/assets.csv>) for physical locations, producers, consumers and source references.

## Activity

Observed source quantities and verified extracts; generated compatibility views are identified separately.

| Asset | Authoring | Representation |
|---|---|---|
| [Corridor weights](<canonical/activity/corridor_weights.csv>) | Maintained | Readable canonical CSV |
| [Diesel sulfur regime](<canonical/activity/diesel_sulfur_regime.csv>) | Maintained | Readable canonical CSV |
| [Elk rail pak 2019](<canonical/activity/elk_rail_pak_2019.csv>) | Generated | Readable canonical CSV |
| [Fuel detail](<canonical/activity/fuel_detail.csv>) | Maintained | Readable canonical CSV |
| [Fuel history quinquennial](<canonical/activity/fuel_history_quinquennial.csv>) | Maintained | Readable canonical CSV |
| [Pakistan Railways fuel use](<canonical/activity/fuel_consumption.csv>) | Maintained | Readable canonical CSV |
| [Pakistan Railways service statistics](<canonical/activity/service_statistics.csv>) | Maintained | Readable canonical CSV |
| [Pakistan Railways traffic](<canonical/activity/traffic.csv>) | Maintained | Readable canonical CSV |
| [Wdi rail](<canonical/activity/wdi_rail.csv>) | Generated | Readable canonical CSV |

## Parameters

Emission factors, scientific assumptions, scenarios and applicability rules.

| Asset | Authoring | Representation |
|---|---|---|
| [Railways params](<canonical/parameters/railways_params.csv>) | Maintained | Readable canonical CSV |

## Gis

Spatial inputs. Keep geometry, CRS, provenance and licensing companion files together.

| Asset | Authoring | Representation |
|---|---|---|
| [Corridors](<gis/corridors.csv>) | Maintained | table |
| [Pak rail network](<gis/pak_rail_network.geojson>) | Generated | gis |
| [Rail sources](<gis/RAIL_SOURCES.json>) | Generated | gis |
| [Yards](<gis/yards.csv>) | Maintained | table |

## Evidence

Independent comparisons, diagnostics, source extracts and evidence supporting interpretation.

| Asset | Authoring | Representation |
|---|---|---|
| [Agp evidence](<canonical/evidence/agp_evidence.csv>) | Maintained | Readable canonical CSV |
| [Official benchmarks](<canonical/evidence/official_benchmarks.csv>) | Maintained | Readable canonical CSV |
| [Railways extract](<evidence/unfccc/railways_extract.json>) | Generated | document |
| [UNFCCC railways extract](<canonical/evidence/unfccc/railways_extract.csv>) | Generated | Readable canonical CSV |

## Shared inputs

| Asset | Purpose |
|---|---|
| [Emission factors](<../../shared/canonical/parameters/emission_factors.csv>) | parameters |
| [Facility registry](<../../shared/canonical/lookups/facility_registry.csv>) | lookups |
| [Grid proxy semantics](<../../shared/canonical/gis/grid_proxy_semantics.csv>) | gis |
| [Province shares](<../../shared/canonical/lookups/province_shares.csv>) | lookups |
| [Monthly request sector components](<../../shared/requests/monthly_request_components.csv>) | requests |
| [Monthly data request register](<../../shared/requests/monthly_request_register.csv>) | requests |


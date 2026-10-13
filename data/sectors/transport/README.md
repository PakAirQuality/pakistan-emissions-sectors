# Transport data

Start with the readable CSV links below. Each asset has one owner; shared inputs are linked rather than copied.

`canonical/` contains generated, Git-versioned runtime/download CSVs. Edit the maintained source listed in the catalog, then run `make dev`; do not edit canonical copies independently.

Source identities remain stable even where the old identity looks like a former file path. See the [asset catalog](<../../catalog/assets.csv>) for physical locations, producers, consumers and source references.

## Activity

Observed source quantities and verified extracts; generated compatibility views are identified separately.

| Asset | Authoring | Representation |
|---|---|---|
| [Edgar pak transport categories](<canonical/activity/edgar_pak_transport_categories.csv>) | Generated | Readable canonical CSV |
| [Edgar pak transport series](<canonical/activity/edgar_pak_transport_series.csv>) | Generated | Readable canonical CSV |
| [Emep class map](<canonical/activity/emep_class_map.csv>) | Maintained | Readable canonical CSV |
| [Emep tier1 road air](<canonical/activity/emep_tier1_road_air.csv>) | Maintained | Readable canonical CSV |
| [Emission factors gkm](<canonical/activity/emission_factors_gkm.csv>) | Maintained | Readable canonical CSV |
| [Fuel sulfur by year](<canonical/activity/fuel_sulfur_by_year.csv>) | Maintained | Readable canonical CSV |
| [National CNG consumption](<canonical/activity/cng_gas.csv>) | Maintained | Readable canonical CSV |
| [OCAC annual customer-group sales](<canonical/activity/ocac_sectoral_annual.csv>) | Maintained | Readable canonical CSV |
| [OCAC area sales](<canonical/activity/ocac_sectoral_provincial.csv>) | Maintained | Readable canonical CSV |
| [Ocac fy2015 16 transcription](<canonical/activity/ocac_fy2015_16_transcription.csv>) | Maintained | Readable canonical CSV |
| [Provincial vehicle registrations](<canonical/activity/vehicles_district.csv>) | Generated | Readable canonical CSV |
| [Vehicle distance assumptions](<canonical/activity/vkt.csv>) | Maintained | Readable canonical CSV |
| [Vehicle fuel-share assumptions](<canonical/activity/fuel_split.csv>) | Maintained | Readable canonical CSV |

## Parameters

Emission factors, scientific assumptions, scenarios and applicability rules.

| Asset | Authoring | Representation |
|---|---|---|
| [Transport params](<canonical/parameters/transport_params.csv>) | Maintained | Readable canonical CSV |

## Lookups

Names, identifiers, classifications and mappings used to interpret the observations.

| Asset | Authoring | Representation |
|---|---|---|
| [Vehicle classes](<canonical/lookups/vehicle_classes.csv>) | Maintained | Readable canonical CSV |

## Gis

Spatial inputs. Keep geometry, CRS, provenance and licensing companion files together.

| Asset | Authoring | Representation |
|---|---|---|
| [Pak road density 267x340](<gis/pak_road_density_267x340.npy>) | Generated | gis |
| [Pak road density 267x340.npy](<gis/pak_road_density_267x340.npy.txt>) | Generated | gis |
| [Road sources](<gis/ROAD_SOURCES.json>) | Generated | gis |

## Shared inputs

| Asset | Purpose |
|---|---|
| [Emission factors](<../../shared/canonical/parameters/emission_factors.csv>) | parameters |
| [Province shares](<../../shared/canonical/lookups/province_shares.csv>) | lookups |
| [Monthly request sector components](<../../shared/requests/monthly_request_components.csv>) | requests |
| [Monthly data request register](<../../shared/requests/monthly_request_register.csv>) | requests |


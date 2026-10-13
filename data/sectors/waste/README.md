# Waste data

Start with the readable CSV links below. Each asset has one owner; shared inputs are linked rather than copied.

`canonical/` contains generated, Git-versioned runtime/download CSVs. Edit the maintained source listed in the catalog, then run `make dev`; do not edit canonical copies independently.

Source identities remain stable even where the old identity looks like a former file path. See the [asset catalog](<../../catalog/assets.csv>) for physical locations, producers, consumers and source references.

## Activity

Observed source quantities and verified extracts; generated compatibility views are identified separately.

| Asset | Authoring | Representation |
|---|---|---|
| [Climatetrace waste sites pak](<canonical/activity/climatetrace_waste_sites_pak.csv>) | Generated | Readable canonical CSV |
| [HIES household waste disposal](<canonical/activity/hies_disposal_routes.csv>) | Generated | Readable canonical CSV |
| [Hydrowaste pak](<canonical/activity/hydrowaste_pak.csv>) | Generated | Readable canonical CSV |
| [Population district](<canonical/activity/population_district.csv>) | Generated | Readable canonical CSV |
| [Protein](<canonical/activity/wastewater/protein.csv>) | Maintained | Readable canonical CSV |
| [Sanitation service shares](<canonical/activity/wastewater/sanitation_shares.csv>) | Maintained | Readable canonical CSV |

## Parameters

Emission factors, scientific assumptions, scenarios and applicability rules.

| Asset | Authoring | Representation |
|---|---|---|
| [Waste params](<canonical/parameters/waste_params.csv>) | Generated | Readable canonical CSV |

## Lookups

Names, identifiers, classifications and mappings used to interpret the observations.

| Asset | Authoring | Representation |
|---|---|---|
| [District aliases](<canonical/lookups/district_aliases.csv>) | Maintained | Readable canonical CSV |

## Gis

Spatial inputs. Keep geometry, CRS, provenance and licensing companion files together.

| Asset | Authoring | Representation |
|---|---|---|
| [Landfill sources](<gis/LANDFILL_SOURCES.json>) | Generated | gis |
| [Pak landfill assets](<gis/pak_landfill_assets.csv>) | Generated | table |
| [Pak landfill coverage](<gis/pak_landfill_coverage.csv>) | Generated | table |

## Shared inputs

| Asset | Purpose |
|---|---|
| [Adm2 canonical](<../../shared/canonical/gis/adm2_canonical.csv>) | gis |
| [Adm2 crosswalk](<../../shared/canonical/gis/adm2_crosswalk.csv>) | gis |
| [Emission factors](<../../shared/canonical/parameters/emission_factors.csv>) | parameters |
| [Province shares](<../../shared/canonical/lookups/province_shares.csv>) | lookups |
| [Monthly request sector components](<../../shared/requests/monthly_request_components.csv>) | requests |
| [Monthly data request register](<../../shared/requests/monthly_request_register.csv>) | requests |


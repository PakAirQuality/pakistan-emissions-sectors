# Power data

Start with the readable CSV links below. Each asset has one owner; shared inputs are linked rather than copied.

`canonical/` contains generated, Git-versioned runtime/download CSVs. Edit the maintained source listed in the catalog, then run `make dev`; do not edit canonical copies independently.

Source identities remain stable even where the old identity looks like a former file path. See the [asset catalog](<../../catalog/assets.csv>) for physical locations, producers, consumers and source references.

## Activity

Observed source quantities and verified extracts; generated compatibility views are identified separately.

| Asset | Authoring | Representation |
|---|---|---|
| [Bagasse generation](<canonical/activity/bagasse_generation.csv>) | Generated | Readable canonical CSV |
| [Captive gas](<canonical/activity/captive_gas.csv>) | Generated | Readable canonical CSV |
| [Captive register](<canonical/activity/captive_register.csv>) | Generated | Readable canonical CSV |
| [Climatetrace power assets pak](<canonical/activity/climatetrace_power_assets_pak.csv>) | Generated | Readable canonical CSV |
| [Coal plant coordinates](<canonical/activity/coal_plant_coordinates.csv>) | Generated | Readable canonical CSV |
| [Coal plant fuel, back years](<activity/coal_plant_fuel_back_years.csv>) | Generated | table |
| [Electricity generation by fuel and system](<canonical/activity/generation_by_fuel.csv>) | Generated | Readable canonical CSV |
| [Gas plant coordinates](<canonical/activity/gas_plant_coordinates.csv>) | Generated | Readable canonical CSV |
| [Gem bioenergy pak](<canonical/activity/gem_bioenergy_pak.csv>) | Maintained | Readable canonical CSV |
| [Gem coal pak](<canonical/activity/gem_coal_pak.csv>) | Generated | Readable canonical CSV |
| [Gem gas oil pak](<canonical/activity/gem_gas_oil_pak.csv>) | Maintained | Readable canonical CSV |
| [Generation monthly coverage](<canonical/activity/generation_monthly_coverage.csv>) | Generated | Readable canonical CSV |
| [Grid monthly workbook](<canonical/activity/grid_monthly_workbook.csv>) | Generated | Readable canonical CSV |
| [Grid plant district](<canonical/activity/grid_plant_district.csv>) | Generated | Readable canonical CSV |
| [K-Electric system station fuel, back years](<activity/ke_station_fuel_back_years.csv>) | Maintained | table |
| [NEPRA plant generation](<canonical/activity/plant_fuel_generation.csv>) | Generated | Readable canonical CSV |
| [PBS and NEPRA monthly generation](<canonical/activity/generation_monthly.csv>) | Generated | Readable canonical CSV |
| [Plant coordinates](<canonical/activity/plant_coordinates.csv>) | Generated | Readable canonical CSV |
| [Plant fuel and generation calculations](<canonical/activity/plant_fuel_ledger.csv>) | Generated | Readable canonical CSV |
| [Plant fuel quantities, back years](<activity/plant_fuel_quantity_back_years.csv>) | Generated | table |
| [Plant heat rates](<canonical/activity/plant_heat_rates.csv>) | Generated | Readable canonical CSV |
| [Plant locations](<canonical/activity/plant_locations.csv>) | Generated | Readable canonical CSV |
| [Power coal energy, booked account](<activity/coal_energy_booking.csv>) | Maintained | table |
| [Power so2 admission](<canonical/activity/power_so2_admission.csv>) | Generated | Readable canonical CSV |
| [Power-sector fuel consumption](<canonical/activity/fuel_consumed.csv>) | Generated | Readable canonical CSV |
| [Sir month corrections](<canonical/activity/sir_month_corrections.csv>) | Maintained | Readable canonical CSV |
| [Tropomi no2 plants](<canonical/activity/tropomi_no2_plants.csv>) | Generated | Readable canonical CSV |

## Parameters

Emission factors, scientific assumptions, scenarios and applicability rules.

| Asset | Authoring | Representation |
|---|---|---|
| [Power coal blend by year](<canonical/parameters/power_coal_blend_by_year.csv>) | Maintained | Readable canonical CSV |
| [Power fuel quality](<canonical/parameters/power_fuel_quality.csv>) | Maintained | Readable canonical CSV |
| [Power params](<canonical/parameters/power_params.csv>) | Maintained | Readable canonical CSV |

## Lookups

Names, identifiers, classifications and mappings used to interpret the observations.

| Asset | Authoring | Representation |
|---|---|---|
| [Pbs sir aliases](<canonical/lookups/pbs_sir_aliases.csv>) | Maintained | Readable canonical CSV |
| [Plant aliases](<canonical/lookups/plant_aliases.csv>) | Maintained | Readable canonical CSV |
| [Plant name crosswalk](<canonical/lookups/plant_name_crosswalk.csv>) | Generated | Readable canonical CSV |

## Evidence

Independent comparisons, diagnostics, source extracts and evidence supporting interpretation.

| Asset | Authoring | Representation |
|---|---|---|
| [Power extract](<evidence/unfccc/power_extract.json>) | Generated | document |
| [Sir row discrepancies](<canonical/evidence/sir_row_discrepancies.csv>) | Generated | Readable canonical CSV |
| [UNFCCC power extract](<canonical/evidence/unfccc/power_extract.csv>) | Generated | Readable canonical CSV |
| [Workbook emissions crosscheck](<canonical/evidence/workbook_emissions_crosscheck.csv>) | Generated | Readable canonical CSV |

## Shared inputs

| Asset | Purpose |
|---|---|
| [PBS monthly industrial production](<../../shared/canonical/activity/monthly/pbs_qim_month_item.csv>) | activity |
| [Data gaps](<../../shared/requests/data_gaps.csv>) | requests |
| [Emission factors](<../../shared/canonical/parameters/emission_factors.csv>) | parameters |
| [Province shares](<../../shared/canonical/lookups/province_shares.csv>) | lookups |
| [Monthly request sector components](<../../shared/requests/monthly_request_components.csv>) | requests |
| [Monthly data request register](<../../shared/requests/monthly_request_register.csv>) | requests |


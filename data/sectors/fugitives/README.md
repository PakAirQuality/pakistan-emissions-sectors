# Fugitives data

Start with the readable CSV links below. Each asset has one owner; shared inputs are linked rather than copied.

`canonical/` contains generated, Git-versioned runtime/download CSVs. Edit the maintained source listed in the catalog, then run `make dev`; do not edit canonical copies independently.

Source identities remain stable even where the old identity looks like a former file path. See the [asset catalog](<../../catalog/assets.csv>) for physical locations, producers, consumers and source references.

## Activity

Observed source quantities and verified extracts; generated compatibility views are identified separately.

| Asset | Authoring | Representation |
|---|---|---|
| [Anchor activity](<canonical/activity/anchor_activity.csv>) | Maintained | Readable canonical CSV |
| [Anchor activity 2021 23](<canonical/activity/anchor_activity_2021_23.csv>) | Generated compatibility view | Readable canonical CSV |
| [Anchor activity 2023 24](<canonical/activity/anchor_activity_2023_24.csv>) | Generated compatibility view | Readable canonical CSV |
| [Fertiliser gas class by year](<activity/fertilizer_gas_class.csv>) | Maintained | table |
| [Field gas supply, 2023-24](<canonical/activity/field_gas_supply_2023_24.csv>) | Maintained | Readable canonical CSV |
| [Flare sites pak](<canonical/activity/flare_sites_pak.csv>) | Generated | Readable canonical CSV |
| [Gas and refinery infrastructure, 2023-24](<canonical/activity/infrastructure_2023_24.csv>) | Maintained | Readable canonical CSV |
| [Gas flow controls 2021 24](<canonical/activity/gas_flow_controls_2021_24.csv>) | Maintained | Readable canonical CSV |
| [Infrastructure history 2015 21](<canonical/activity/infrastructure_history_2015_21.csv>) | Maintained | Readable canonical CSV |
| [Lng terminal coordinates](<canonical/activity/lng_terminal_coordinates.csv>) | Maintained | Readable canonical CSV |
| [Mars plumes pak](<canonical/activity/mars_plumes_pak.csv>) | Generated | Readable canonical CSV |
| [Mars sources pak](<canonical/activity/mars_sources_pak.csv>) | Generated | Readable canonical CSV |
| [National oil and gas production](<canonical/activity/production.csv>) | Generated | Readable canonical CSV |
| [OGRA gas balance](<canonical/activity/gas_network.csv>) | Maintained | Readable canonical CSV |
| [Post meter end use 2023 24](<canonical/activity/post_meter_end_use_2023_24.csv>) | Maintained | Readable canonical CSV |
| [Provincial controls 2023 24](<canonical/activity/provincial_controls_2023_24.csv>) | Maintained | Readable canonical CSV |
| [Provincial oil and gas production](<canonical/activity/production_province.csv>) | Maintained | Readable canonical CSV |
| [Sector gas table, the two years no text layer gives](<activity/ogra_sector_gas_2021_2023.csv>) | Maintained | table |

## Parameters

Emission factors, scientific assumptions, scenarios and applicability rules.

| Asset | Authoring | Representation |
|---|---|---|
| [Fugitives ipcc2019 factors](<canonical/parameters/fugitives_ipcc2019_factors.csv>) | Maintained | Readable canonical CSV |
| [Fugitives params](<canonical/parameters/fugitives_params.csv>) | Maintained | Readable canonical CSV |

## Evidence

Independent comparisons, diagnostics, source extracts and evidence supporting interpretation.

| Asset | Authoring | Representation |
|---|---|---|
| [Benchmark controls](<canonical/evidence/benchmark_controls.csv>) | Maintained | Readable canonical CSV |
| [Completeness](<canonical/evidence/completeness.csv>) | Generated | Readable canonical CSV |
| [Distribution practice evidence](<canonical/evidence/distribution_practice_evidence.csv>) | Maintained | Readable canonical CSV |
| [Fugitives audit cells](<evidence/unfccc/fugitives_audit_cells.json>) | Generated | document |
| [Fugitives extract crt](<evidence/unfccc/fugitives_extract_crt.json>) | Generated | document |
| [UNFCCC fugitives audit cells](<canonical/evidence/unfccc/fugitives_audit_cells.csv>) | Generated | Readable canonical CSV |
| [UNFCCC fugitives extract crt 0](<canonical/evidence/unfccc/fugitives_extract_crt_0.csv>) | Generated | Readable canonical CSV |
| [UNFCCC fugitives extract crt 1](<canonical/evidence/unfccc/fugitives_extract_crt_1.csv>) | Generated | Readable canonical CSV |

## Shared inputs

| Asset | Purpose |
|---|---|
| [Pbs minerals month province](<../../shared/canonical/activity/monthly/pbs_minerals_month_province.csv>) | activity |
| [Emission factors](<../../shared/canonical/parameters/emission_factors.csv>) | parameters |
| [Province shares](<../../shared/canonical/lookups/province_shares.csv>) | lookups |
| [Monthly request sector components](<../../shared/requests/monthly_request_components.csv>) | requests |
| [Monthly data request register](<../../shared/requests/monthly_request_register.csv>) | requests |


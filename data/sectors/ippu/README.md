# IPPU data

Start with the readable CSV links below. Each asset has one owner; shared inputs are linked rather than copied.

`canonical/` contains generated, Git-versioned runtime/download CSVs. Edit the maintained source listed in the catalog, then run `make dev`; do not edit canonical copies independently.

Source identities remain stable even where the old identity looks like a former file path. See the [asset catalog](<../../catalog/assets.csv>) for physical locations, producers, consumers and source references.

## Activity

Observed source quantities and verified extracts; generated compatibility views are identified separately.

| Asset | Authoring | Representation |
|---|---|---|
| [Annual clinker trade controls](<canonical/activity/clinker_trade_annual_controls.csv>) | Generated | Readable canonical CSV |
| [Cement company annual reports](<canonical/activity/company_clinker_series.csv>) | Generated compatibility view | Readable canonical CSV |
| [Cement producer census, 2023-24](<canonical/activity/cement_producer_census_2023_24.csv>) | Generated compatibility view | Readable canonical CSV |
| [Chemical plant activity](<canonical/activity/chemical_plant_activity.csv>) | Generated | Readable canonical CSV |
| [Clinker trade annual](<canonical/activity/clinker_trade_annual.csv>) | Maintained | Readable canonical CSV |
| [Company clinker 2023 24](<canonical/activity/company_clinker_2023_24.csv>) | Generated compatibility view | Readable canonical CSV |
| [Company production](<canonical/activity/company_production.csv>) | Maintained | Readable canonical CSV |
| [Company roster](<canonical/activity/company_roster.csv>) | Maintained | Readable canonical CSV |
| [Facilities](<canonical/activity/facilities.csv>) | Maintained | Readable canonical CSV |
| [Hfc consumption controls](<canonical/activity/hfc_consumption_controls.csv>) | Generated | Readable canonical CSV |
| [Hfc inventory rows](<canonical/activity/hfc_inventory_rows.csv>) | Generated | Readable canonical CSV |
| [Hfc trade screening](<canonical/activity/hfc_trade_screening.csv>) | Maintained | Readable canonical CSV |
| [Hies appliance ownership](<canonical/activity/hies_appliance_ownership.csv>) | Maintained | Readable canonical CSV |
| [Monthly cement production, 2022](<canonical/activity/cement_monthly_2022.csv>) | Maintained | Readable canonical CSV |
| [Monthly clinker trade](<canonical/activity/clinker_trade_monthly.csv>) | Generated | Readable canonical CSV |
| [National industrial activity controls](<canonical/activity/national_activity.csv>) | Maintained | Readable canonical CSV |
| [Nitric acid monitoring](<canonical/activity/nitric_acid_monitoring.csv>) | Generated | Readable canonical CSV |
| [Nitric acid monitoring detail](<canonical/activity/nitric_acid_monitoring_detail.csv>) | Generated | Readable canonical CSV |
| [Production](<canonical/activity/production.csv>) | Generated | Readable canonical CSV |
| [Undp rac imports](<canonical/activity/undp_rac_imports.csv>) | Maintained | Readable canonical CSV |

## Parameters

Emission factors, scientific assumptions, scenarios and applicability rules.

| Asset | Authoring | Representation |
|---|---|---|
| [Ippu params](<canonical/parameters/ippu_params.csv>) | Maintained | Readable canonical CSV |

## Lookups

Names, identifiers, classifications and mappings used to interpret the observations.

| Asset | Authoring | Representation |
|---|---|---|
| [Facility geocoding overrides](<canonical/lookups/facility_geocoding_overrides.csv>) | Generated | Readable canonical CSV |

## Evidence

Independent comparisons, diagnostics, source extracts and evidence supporting interpretation.

| Asset | Authoring | Representation |
|---|---|---|
| [Cement thermal evidence](<canonical/evidence/cement_thermal_evidence.csv>) | Maintained | Readable canonical CSV |
| [Chemical plant evidence](<canonical/evidence/chemical_plant_evidence.csv>) | Generated | Readable canonical CSV |
| [Company boundary audit](<canonical/evidence/company_boundary_audit.csv>) | Maintained | Readable canonical CSV |
| [Company production evidence](<canonical/evidence/company_production_evidence.csv>) | Maintained | Readable canonical CSV |
| [Ippu audit cells](<evidence/unfccc/ippu_audit_cells.json>) | Generated | document |
| [Ippu extract background](<evidence/unfccc/ippu_extract_background.json>) | Generated | document |
| [Ippu extract fgas species](<evidence/unfccc/ippu_extract_fgas_species.json>) | Generated | document |
| [Ippu extract summary](<evidence/unfccc/ippu_extract_summary.json>) | Generated | document |
| [UNFCCC ippu audit cells](<canonical/evidence/unfccc/ippu_audit_cells.csv>) | Generated | Readable canonical CSV |
| [UNFCCC ippu extract background](<canonical/evidence/unfccc/ippu_extract_background.csv>) | Generated | Readable canonical CSV |
| [UNFCCC ippu extract fgas species](<canonical/evidence/unfccc/ippu_extract_fgas_species.csv>) | Generated | Readable canonical CSV |
| [UNFCCC ippu extract summary](<canonical/evidence/unfccc/ippu_extract_summary.csv>) | Generated | Readable canonical CSV |

## Metadata

Coverage descriptions, source inventories and schema documentation.

| Asset | Authoring | Representation |
|---|---|---|
| [Cdm access manifest](<metadata/cdm_access_manifest.csv>) | Generated | table |
| [Evidence maturity](<metadata/evidence_maturity.csv>) | Generated | table |
| [Hfc inventory import contract](<metadata/hfc_inventory_import_contract.csv>) | Generated | table |
| [Master data gap matrix](<metadata/master_data_gap_matrix.csv>) | Maintained | table |
| [Source manifest](<metadata/source_manifest.csv>) | Generated | table |

## Requests

Outstanding data requests, letters and prospective templates. Templates are not observations.

| Asset | Authoring | Representation |
|---|---|---|
| [Cement clinker request template](<requests/templates/cement_clinker_request_template.csv>) | Maintained | template |
| [Chemical plant request template](<requests/templates/chemical_plant_request_template.csv>) | Maintained | template |
| [Crt cement method request template](<requests/templates/crt_cement_method_request_template.csv>) | Maintained | template |
| [Data request packets](<requests/register.csv>) | Generated | table |
| [Hfc inventory request template](<requests/templates/hfc_inventory_request_template.csv>) | Maintained | template |

## Shared inputs

| Asset | Purpose |
|---|---|
| [PBS monthly industrial production](<../../shared/canonical/activity/monthly/pbs_qim_month_item.csv>) | activity |
| [NFDC plant gas use](<../../shared/canonical/activity/nfdc/afr2025_fertilizer_gas_by_plant.csv>) | activity |
| [NFDC monthly plant gas use](<../../shared/canonical/activity/nfdc/afr2025_fertilizer_gas_monthly.csv>) | activity |
| [Afr2025 offtake by product](<../../shared/canonical/activity/nfdc/afr2025_offtake_by_product.csv>) | activity |
| [Afr2025 production by manufacturer](<../../shared/canonical/activity/nfdc/afr2025_production_by_manufacturer.csv>) | activity |
| [Annex5 national month product](<../../shared/canonical/activity/nfdc/annex5_national_month_product.csv>) | activity |
| [Nfdc production by product series](<../../shared/canonical/activity/nfdc/nfdc_production_by_product_series.csv>) | activity |
| [Emission factors](<../../shared/canonical/parameters/emission_factors.csv>) | parameters |
| [Province shares](<../../shared/canonical/lookups/province_shares.csv>) | lookups |
| [Monthly request sector components](<../../shared/requests/monthly_request_components.csv>) | requests |
| [Monthly data request register](<../../shared/requests/monthly_request_register.csv>) | requests |


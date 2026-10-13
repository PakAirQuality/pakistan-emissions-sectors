# The claim matrix, resolved

One row per headline claim of the national manuscript (data/claim_matrix.csv), held to the release: `printed` is what the section prints today, `resolved` is what the release answers (through pakemis_query where a stored query exists, else through the pointer, else through the DOC_CLAIMS getter). `agrees` applies the DOC_CLAIMS rule (half an ulp at the printed precision plus the claim's registered tolerance); `strict` is half an ulp alone. Nothing here is repaired: a `no` is a finding for tests/paper_numbers/test_claim_matrix.py.

Rows: 106; agree: 106; disagree: 0; via query: 20, pointer: 65, getter: 21.

## Abstract

| claim_id | printed | resolved | unit | agrees | strict | evidence | via | limitation | artefact | refs |
|---|---|---|---|---|---|---|---|---|---|---|
| abs_total_L | 444.96 | 444.955421030000000000 | Mt CO2e AR5 | yes | yes | closure-exact | query | lim:incomplete-floor | tab:sectors | claim:national total in abstract;registry:national_total_L;table:tab:sectors |
| abs_total_AR6 | 438.19 | 438.190608970000000000 | Mt CO2e AR6 | yes | yes | closure-exact | query |  | tab:sectors | claim:national AR6 total in abstract |
| abs_total_S | 450.20 | 450.201684200000000000 | Mt CO2e AR5 | yes | yes | structural | query | lim:incomplete-floor | tab:dungvariants | claim:survey-configuration total in abstract;registry:national_total_S |
| abs_flat_share | 54.65 | 54.65 | percent | yes | yes | estimated-TE4 | pointer | lim:monthly-physics | fig:seasonality | claim:abstract monthly T4 share |
| abs_streams_gridded | 199 | 199 | streams | yes | yes | coverage-count | pointer |  |  | fact:grid_streams_allocated;claim:results gridded streams |
| abs_streams_total | 202 | 202 | streams | yes | yes | coverage-count | pointer |  |  | fact:grid_streams |
| abs_streams_unallocated | 3 | 3 | streams | yes | yes | spatial-S4 | pointer |  |  | fact:grid_streams_unallocated;claim:results unallocated streams |
| abs_unallocated_share | 0.05 | 0.056490085999660815 | percent | yes | no | spatial-S4 | pointer |  |  | claim:national S4 share |
| abs_mc_interval | 11.72 | 11.72 | percent | yes | yes | parametric | pointer |  | fig:uncertainty | claim:MC national low in abstract;table:tab:correlation |
| abs_mc_down | 10.3 | 10.35 | percent | yes | yes | parametric | pointer |  | fig:uncertainty | claim:national down arm in abstract |
| abs_mc_up | 13.1 | 13.09 | percent | yes | yes | parametric | pointer |  | fig:uncertainty | claim:national up arm in abstract |
| abs_structural_max | 9.07 | 9.07 | Mt CO2e AR5 | yes | yes | structural | pointer |  | fig:bridge | claim:priorities structural top |
| abs_legacy_control_delta | 17.78 | 17.78041 | Mt CO2e AR5 | yes | yes | structural | pointer |  | fig:bridge | claim:priorities structural top |
| abs_completeness_rows | 138 | 138 | rows | yes | yes | coverage-count | query | lim:incomplete-floor | tab:completeness | claim:abstract completeness rows;table:tab:completeness |
| abs_completeness_E | 54 | 54 | rows | yes | yes | coverage-count | query | lim:incomplete-floor | tab:completeness | table:tab:completeness |
| abs_completeness_NE | 71 | 71 | rows | yes | yes | coverage-count | query | lim:incomplete-floor | tab:completeness | table:tab:completeness |

## 1 Introduction

| claim_id | printed | resolved | unit | agrees | strict | evidence | via | limitation | artefact | refs |
|---|---|---|---|---|---|---|---|---|---|---|
| intro_contract_tests | 32 | 32.0 | tests | yes | yes | provenance-count | getter |  |  | claim:introduction contract tests |
| intro_enteric_share | 34.1 | 34.08 | percent | yes | yes | closure-exact | pointer |  | fig:sectors | claim:introduction enteric share |
| intro_residential_share | 5.4 | 5.44 | percent | yes | yes | closure-exact | pointer |  | fig:sectors | claim:introduction residential share |
| intro_total_L | 444.96 | 444.955421030000000000 | Mt CO2e AR5 | yes | yes | closure-exact | query | lim:incomplete-floor | tab:sectors | claim:national total in introduction;registry:national_total_L |
| intro_edgar_magnitude | 87 | 86.5 | percent | yes | yes | external-comparison | pointer | lim:incomplete-floor | tab:benchmarks | claim:introduction EDGAR coverage;table:tab:benchmarks |
| intro_edgar_scope | 11 | 11.0 | percent | yes | yes | external-comparison | pointer | lim:incomplete-floor | tab:benchmarks | claim:introduction EDGAR scope covered |
| intro_completeness_rows | 138 | 138 | rows | yes | yes | coverage-count | query |  | tab:completeness | claim:introduction completeness rows |
| intro_contract_invariants | 32 | 32.0 | tests | yes | yes | provenance-count | getter |  |  | claim:introduction contract invariants |
| intro_residual_variance | 2.5 | 2.48 | percent | yes | yes | parametric | pointer |  | fig:uncertainty | claim:introduction residual share;fact:uncertainty_variance_share_residual_pct |

## 2 Dataset scope and architecture

| claim_id | printed | resolved | unit | agrees | strict | evidence | via | limitation | artefact | refs |
|---|---|---|---|---|---|---|---|---|---|---|
| tab_completeness_rows | 138 | 138 | rows | yes | yes | coverage-count | query | lim:incomplete-floor | tab:completeness | table:tab:completeness;claim:completeness row total |
| tab_completeness_codes | 72 | 72.0 | codes | yes | yes | coverage-count | pointer | lim:incomplete-floor | tab:completeness | table:tab:completeness |

## 4 Dataset generation

| claim_id | printed | resolved | unit | agrees | strict | evidence | via | limitation | artefact | refs |
|---|---|---|---|---|---|---|---|---|---|---|
| tab_sectors_total | 444.96 | 444.955421030000000000 | Mt CO2e AR5 | yes | yes | closure-exact | query |  | tab:sectors | table:tab:sectors;claim:national total;registry:national_total_L |
| fig_sectors_agriculture_share | 50.2 | 50.22 | percent | yes | yes | closure-exact | pointer |  | fig:sectors | table:fig:sectors |
| tab_categorygas_CH4 | 242.932 | 242.932162340000000000 | Mt CO2e AR5 | yes | yes | closure-exact | query |  | tab:categorygas | table:tab:categorygas |
| tab_categorygas_CO2 | 160.944 | 160.943809950000000000 | Mt CO2e AR5 | yes | yes | closure-exact | query |  | tab:categorygas | table:tab:categorygas |
| tab_categorygas_N2O | 41.079 | 41.079448740000000000 | Mt CO2e AR5 | yes | yes | closure-exact | query |  | tab:categorygas | table:tab:categorygas |
| fig_series_first_year | 393.84 | 393.836273470000000000 | Mt CO2e AR5 | yes | yes | closure-exact | query | lim:series-basis | fig:series | table:fig:series;claim:series covered total first year |
| fig_series_window_change | 51.12 | 51.119147560000000000 | Mt CO2e AR5 | yes | yes | closure-exact | query | lim:series-basis | fig:series | fact:trend_window_change_Mt;claim:uncertainty window change |
| fig_seasonality_closure | 444.96 | 444.955421030531000000 | Mt CO2e AR5 | yes | yes | closure-exact | query |  | fig:seasonality | table:fig:seasonality;registry:national_total_L |
| fig_seasonality_flat_share | 54.65 | 54.65 | percent | yes | yes | estimated-TE4 | pointer | lim:monthly-physics | fig:seasonality | table:fig:seasonality;claim:seasonality caption T4 share |
| tab_correlation_national | 11.72 | 11.72 | percent | yes | yes | parametric | pointer |  | tab:correlation | table:tab:correlation;claim:MC independent national |
| tab_correlation_national_correlated | 11.75 | 11.75 | percent | yes | yes | parametric | pointer |  | fig:uncertainty | table:tab:correlation;claim:MC correlated national |
| fig_bridge_largest | 9.1 | 9.07 | Mt CO2e AR5 | yes | yes | structural | pointer |  | fig:bridge | table:fig:bridge;claim:priorities structural top |
| tab_dungvariants_difference | 5.2 | 5.246263170000000000 | Mt CO2e AR5 | yes | yes | structural | query | lim:incomplete-floor | tab:dungvariants | table:tab:dungvariants;registry:national_total_S |
| res_streams_gridded | 199 | 199 | streams | yes | yes | coverage-count | pointer |  |  | fact:grid_streams_allocated;claim:results gridded streams |
| res_streams_unallocated | 3 | 3 | streams | yes | yes | spatial-S4 | pointer |  |  | fact:grid_streams_unallocated;claim:results unallocated streams |
| res_agri_misaligned_crops | 3 | 3 | crops | yes | yes | coverage-count | pointer | lim:series-basis | fig:series | fact:agriculture_crops_misaligned_by_one_year;claim:results agriculture misaligned crops |
| res_agri_calendar_share | 77.37 | 77.37 | percent | yes | yes | estimated-TE4 | pointer | lim:series-basis | fig:series | fact:agriculture_calendar_basis_share_pct;claim:results agriculture calendar share |
| res_agri_basis_change | -7.6969 | -7.6969 | Mt CO2e AR5 | yes | yes | structural | pointer | lim:series-basis | fig:series | fact:agriculture_basis_change_Mt;claim:results agriculture basis change |
| res_agri_cotton_scope | 1.055 | 1.055 | Mt CO2e AR5 | yes | yes | structural | pointer | lim:series-basis | fig:series | fact:agriculture_cotton_scope_Mt;claim:results agriculture cotton scope |
| unc_trend_changes_tested | 8 | 8 | changes | yes | yes | parametric | pointer | lim:series-basis | fig:series | fact:trend_consecutive_changes_tested;claim:uncertainty consecutive changes tested |
| unc_trend_changes_resolved | 2 | 2 | changes | yes | yes | parametric | pointer | lim:series-basis | fig:series | fact:trend_consecutive_changes_resolved;claim:uncertainty consecutive changes resolved |
| unc_trend_common_window | 51.12 | 51.11915 | Mt CO2e AR5 | yes | yes | parametric | pointer | lim:series-basis | fig:series | fact:trend_common_window_change_Mt;claim:trend common window |
| unc_variance_persists | 76.56 | 76.56 | percent | yes | yes | parametric | pointer |  | fig:uncertainty | fact:uncertainty_variance_share_persists_pct;claim:uncertainty persisting variance share |
| unc_variance_residual | 2.48 | 2.48 | percent | yes | yes | parametric | pointer |  | fig:uncertainty | fact:uncertainty_variance_share_residual_pct;claim:uncertainty residual variance share |
| spatial_adm1_by_year_rows | 7864 | 7864.0 | rows | yes | yes | coverage-count | pointer |  |  | claim:adm1 by-year row count |
| spatial_adm2_by_year_rows | 10350 | 10350.0 | rows | yes | yes | coverage-count | pointer |  |  | claim:adm2 by-year row count |
| spatial_grid_fleet_substituted_fy2015_16 | 17.66 | 17.66 | Mt CO2e AR5 | yes | yes | spatial-S4 | getter |  |  | claim:grid fleet substituted mass fy2015_16 |
| spatial_stream_years_own_year | 795 | 795.0 | stream-years | yes | yes | provenance-count | getter |  |  | claim:stream years measured in their own year |
| spatial_stream_years_backcast | 306 | 306.0 | stream-years | yes | yes | provenance-count | pointer |  |  | claim:stream years carrying the reference pattern |
| spatial_adm2_monthly_by_year_rows | 122616 | 122616.0 | rows | yes | yes | coverage-count | pointer |  |  | claim:adm2 monthly by year row count |
| spatial_stream_years_timeless | 615 | 615.0 | stream-years | yes | yes | provenance-count | pointer |  |  | claim:stream years on a timeless surface |

## 6 Technical validation

| claim_id | printed | resolved | unit | agrees | strict | evidence | via | limitation | artefact | refs |
|---|---|---|---|---|---|---|---|---|---|---|
| tab_benchmarks_magnitude | 87 | 86.5 | percent | yes | yes | external-comparison | pointer | lim:incomplete-floor | tab:benchmarks | table:tab:benchmarks;claim:benchmarks magnitude ratio |

## 7 Usage notes and limitations

| claim_id | printed | resolved | unit | agrees | strict | evidence | via | limitation | artefact | refs |
|---|---|---|---|---|---|---|---|---|---|---|
| lim_single_year_period | FY2023--24 | FY2023-24 | label | yes | yes | coverage-count | pointer | lim:single-year |  | fact:annual_last_fy |
| lim_floor_edgar_1a2 | 44 | 43.98 | Mt CO2e AR5 | yes | yes | external-comparison | pointer | lim:incomplete-floor | tab:benchmarks | claim:limitations EDGAR 1A2 approx |
| lim_floor_industry_gas | 5.61 | 5.6092200000000005 | Mt CO2e AR5 | yes | yes | closure-exact | getter | lim:incomplete-floor | tab:sectors | claim:limitations industrial gas |
| lim_floor_1a2_remaining | 15.85 | 15.849999999999998 | Mt CO2e AR5 | yes | yes | external-comparison | pointer | lim:incomplete-floor | tab:benchmarks | registry:industry_1a2_remaining |
| lim_floor_chemical_filing | 19.4 | 19.40 | Mt CO2e AR5 | yes | yes | external-comparison | pointer | lim:incomplete-floor | tab:benchmarks | claim:limitations chemical-industries filing |
| lim_floor_commercial | 2.4 | 2.427 | Mt CO2e AR5 | yes | yes | structural | getter | lim:incomplete-floor |  | claim:limitations commercial floor |
| lim_floor_total_rounded | 445 | 444.955421030000000000 | Mt CO2e AR5 | yes | yes | closure-exact | query | lim:incomplete-floor | tab:sectors | claim:limitations national total;registry:national_total_L |
| lim_floor_dung_ratio | 4.9 | 4.908455867106329 | ratio | yes | yes | structural | getter | lim:incomplete-floor | tab:dungvariants | claim:limitations configuration ratio |
| lim_floor_config_difference | 5.25 | 5.246263170000000000 | Mt CO2e AR5 | yes | yes | structural | query | lim:incomplete-floor | tab:dungvariants | claim:limitations configuration difference;registry:national_total_S |
| lim_lulucf_sink | -4.01 | -4.008 | Mt CO2e AR5 | yes | yes | structural | pointer | lim:lulucf |  | table:lulucf_totals |
| lim_fugitives_floor | 9.601 | 9.601488974504125 | Mt CO2e AR5 | yes | yes | structural | pointer | lim:fugitive-envelope | fig:bridge | claim:national fugitives envelope floor |
| lim_fugitives_top | 23.499 | 23.499370669386575 | Mt CO2e AR5 | yes | yes | structural | pointer | lim:fugitive-envelope | fig:bridge | claim:national fugitives envelope top |
| lim_fugitives_lower | 14.894 | 14.893630864512566 | Mt CO2e AR5 | yes | yes | structural | pointer | lim:fugitive-envelope | fig:bridge | claim:national fugitives lower member |
| lim_series_first_fy | FY2015--16 | FY2015-16 | label | yes | yes | coverage-count | pointer | lim:series-basis | fig:series | fact:annual_first_fy |
| lim_series_calendar_share | 77.37 | 77.37 | percent | yes | yes | estimated-TE4 | pointer | lim:series-basis |  | fact:agriculture_calendar_basis_share_pct;claim:results agriculture calendar share |
| lim_series_ne_years | no | 0 | sector-years | yes | yes | coverage-count | pointer | lim:series-basis | fig:series | fact:annual_ne_sector_years |
| lim_firewood_energy_share | 38.7 | 38.69727296261369 | percent | yes | yes | structural | getter | lim:firewood |  | claim:limitations firewood energy share |
| lim_dung_energy_share | 13.6 | 13.59999843562567 | percent | yes | yes | structural | getter | lim:firewood |  | claim:limitations dung energy share |
| lim_firewood_uncertainty | 35 | 35 | percent | yes | yes | parametric | pointer | lim:firewood |  | claim:limitations firewood uncertainty |
| lim_firewood_faostat | 23.89 | 23.88751 | Mt CO2e AR5 | yes | yes | structural | pointer | lim:firewood | fig:bridge | claim:limitations firewood faostat case |
| lim_firewood_excluded | 20.81 | 20.80656 | Mt CO2e AR5 | yes | yes | structural | pointer | lim:firewood | fig:bridge | claim:limitations firewood excluded |
| lim_monthly_flat_share | 54.65 | 54.65 | percent | yes | yes | estimated-TE4 | pointer | lim:monthly-physics | fig:seasonality | claim:limitations monthly T4 share |
| lim_monthly_observed | 37.3 | 37.3 | percent | yes | yes | estimated-TE2 | pointer | lim:monthly-physics | fig:seasonality | fact:monthly_observed_share_pct;claim:limitations monthly observed share |
| lim_monthly_physical | 41.0 | 41.0 | percent | yes | yes | estimated-TE4 | pointer | lim:monthly-physics | fig:seasonality | fact:monthly_physical_share_pct;claim:limitations monthly physical share |
| lim_monthly_weakly_timed | 21.8 | 21.8 | percent | yes | yes | estimated-TE4 | pointer | lim:monthly-physics | fig:seasonality | fact:monthly_weakly_timed_share_pct;claim:limitations monthly weakly timed share |
| lim_grade_nine_year | 21.76 | 21.75952178342098 | percent | yes | yes | estimated-TE4 | getter | lim:monthly-grade | fig:seasonality | claim:temporal grade nine-year |
| lim_grade_reference_year | 9.57 | 9.566693650644538 | percent | yes | yes | estimated-TE4 | getter | lim:monthly-grade | fig:seasonality | claim:temporal grade reference year |
| lim_grade_target | 15 | 15.0 | percent | yes | yes | estimated-TE4 | getter | lim:monthly-grade |  | claim:temporal grade target |
| lim_grade_ocac_mass | 283.2 | 283.2 | Mt CO2e AR5 | yes | yes | estimated-TE4 | getter | lim:monthly-grade |  | claim:temporal grade ocac mass |
| lim_grade_after_ocac | 14.68 | 14.68 | percent | yes | yes | estimated-TE4 | getter | lim:monthly-grade |  | claim:temporal grade after ocac |
| lim_managed_soils_moved | 95.09 | 95.10503 | Mt CO2e AR5 | yes | no | estimated-TE2 | getter | lim:monthly-gap | fig:monthlychecks | claim:limitations managed soils moved |
| lim_agriculture_cells | 72 | 72.0 | cells | yes | yes | closure-exact | getter | lim:monthly-gap |  | claim:limitations agriculture cells |
| lim_fugitives_moved | 93.66 | 93.66437 | Mt CO2e AR5 | yes | yes | estimated-TE2 | getter | lim:monthly-gap |  | claim:limitations fugitives moved |
| lim_fugitives_t2_share | 43.0 | 42.959862915842436 | percent | yes | yes | estimated-TE2 | getter | lim:monthly-gap |  | claim:limitations fugitives t2 share |
| lim_deposit_sources | 217 | 217 | sources | yes | yes | provenance-count | pointer | lim:deposit |  | fact:source_register_entries;claim:limitations registered sources |
| lim_deposit_archived | 153 | 153 | documents | yes | yes | provenance-count | pointer | lim:deposit |  | fact:source_documents_archived;claim:limitations archived documents |
| lim_deposit_no_terms | 126 | 126 | sources | yes | yes | provenance-count | pointer | lim:deposit |  | fact:source_documents_not_redistributable;claim:limitations sources without terms |
| lim_deposit_sources_restated | 217 | 217 | sources | yes | yes | provenance-count | pointer | lim:deposit |  | fact:source_register_entries;claim:limitations registered sources, restated |
| lim_deposit_files | 1761 | 1761 | files | yes | yes | provenance-count | pointer | lim:deposit |  | fact:deposit_files;claim:limitations deposit files |

## 10 Conclusions

| claim_id | printed | resolved | unit | agrees | strict | evidence | via | limitation | artefact | refs |
|---|---|---|---|---|---|---|---|---|---|---|
| concl_total_L | 444.96 | 444.955421030000000000 | Mt CO2e AR5 | yes | yes | closure-exact | query | lim:incomplete-floor | tab:sectors | claim:national total in conclusion;registry:national_total_L |
| concl_contract_invariants | 32 | 32.0 | tests | yes | yes | provenance-count | getter |  |  | claim:conclusion contract invariants |
| concl_factor_trap | 8.0 | 7.99591720331962 | percent | yes | yes | structural | getter |  |  | claim:factor trap railway category |
| concl_mc_interval | 11.72 | 11.72 | percent | yes | yes | parametric | pointer |  | tab:correlation | claim:MC national low in conclusion;table:tab:correlation |
| concl_mc_road | 13.3 | 13.26 | percent | yes | yes | parametric | pointer |  | tab:correlation | claim:conclusion road independent |
| concl_wastewater_factor | 1.6 | 1.589463710343017 | ratio | yes | yes | structural | getter |  | fig:bridge | claim:conclusion wastewater factor |
| concl_edgar_1a2 | 44 | 43.98 | Mt CO2e AR5 | yes | yes | external-comparison | pointer | lim:incomplete-floor | tab:benchmarks | claim:conclusion EDGAR 1A2 approx |
| concl_activity_files | 217 | 217.0 | files | yes | yes | provenance-count | pointer | lim:deposit |  | claim:conclusion activity file count;fact:source_register_entries |


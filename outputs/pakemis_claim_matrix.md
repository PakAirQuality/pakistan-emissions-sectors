# The claim matrix, resolved

One row per headline claim of the national manuscript (data/claim_matrix.csv), held to the release: `printed` is what the section prints today, `resolved` is what the release answers (through pakemis_query where a stored query exists, else through the pointer, else through the DOC_CLAIMS getter). `agrees` applies the DOC_CLAIMS rule (half an ulp at the printed precision plus the claim's registered tolerance); `strict` is half an ulp alone. Nothing here is repaired: a `no` is a finding for tests/paper_numbers/test_claim_matrix.py.

Rows: 100; agree: 100; disagree: 0; via query: 0, pointer: 100, getter: 0.

## 4 Dataset generation

| claim_id | printed | resolved | unit | agrees | strict | evidence | via | limitation | artefact | refs |
|---|---|---|---|---|---|---|---|---|---|---|
| 00_abstract_PakLatestARfive | 457.2 | 457.2398322399998 | Mt | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestARfive |
| 00_abstract_PakRefARfive | 444.6 | 444.6077554900002 | Mt | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefARfive |
| 00_abstract_PakRefNHthree | 2670 | 2670.3884860000003 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefNHthree |
| 00_abstract_PakRefNOx | 816.6 | 816.638272 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefNOx |
| 00_abstract_PakRefPMfine | 422.8 | 422.8257290000001 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefPMfine |
| 06_results_PakChangeARfive | 14.9 | 14.931425253042363 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakChangeARfive |
| 06_results_PakChangeNHthree | 45.7 | 45.65464328299598 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakChangeNHthree |
| 06_results_PakChangeNOx | 18.2 | 18.164802029805948 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakChangeNOx |
| 06_results_PakChangePMfine | 24.0 | 24.035348775660893 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakChangePMfine |
| 06_results_PakChangeSOtwo | -45.0 | -45.03518931054845 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakChangeSOtwo |
| 06_results_PakLatestARfive | 457.2 | 457.2398322399998 | Mt | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestARfive |
| 06_results_PakLatestARsix | 450.2 | 450.20529629000004 | Mt | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestARsix |
| 06_results_PakLatestBC | 46.64 | 46.64349800000001 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestBC |
| 06_results_PakLatestCO | 5999 | 5998.811737 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestCO |
| 06_results_PakLatestNHthree | 2690 | 2690.0885439999997 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestNHthree |
| 06_results_PakLatestNMVOC | 1226 | 1226.466215 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestNMVOC |
| 06_results_PakLatestNOx | 833.1 | 833.1277690000001 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestNOx |
| 06_results_PakLatestPMfine | 422.7 | 422.696091 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestPMfine |
| 06_results_PakLatestSOtwo | 368.9 | 368.90514 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestSOtwo |
| 06_results_PakRefARfive | 444.6 | 444.6077554900002 | Mt | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefARfive |
| 06_results_PakRefARsix | 437.8 | 437.83028690999987 | Mt | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefARsix |
| 06_results_PakRefBC | 40.44 | 40.437172 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefBC |
| 06_results_PakRefCHfour | 8621 | 8621.196297999997 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefCHfour |
| 06_results_PakRefCO | 5991 | 5991.2278 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefCO |
| 06_results_PakRefCOtwo | 161 | 161.01146620799997 | Mt | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefCOtwo |
| 06_results_PakRefNHthree | 2670 | 2670.3884860000003 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefNHthree |
| 06_results_PakRefNMVOC | 1187 | 1186.722555 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefNMVOC |
| 06_results_PakRefNOx | 816.6 | 816.638272 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefNOx |
| 06_results_PakRefNtwoO | 153.4 | 153.44274800000005 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefNtwoO |
| 06_results_PakRefPMfine | 422.8 | 422.8257290000001 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefPMfine |
| 06_results_PakRefSOtwo | 213.6 | 213.614163 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefSOtwo |
| 07_uncertainty_GHGReferenceHigh | 503.2 | 503.2167084667016 | MtCO2e | yes | yes | parametric | pointer | sec:uncertainty |  | macro:PakRefARfiveHigh |
| 07_uncertainty_GHGReferenceLow | 399.9 | 399.8675867063499 | MtCO2e | yes | yes | parametric | pointer | sec:uncertainty |  | macro:PakRefARfiveLow |
| 07_uncertainty_PakRefNHthreeHigh | 3069 | 3069.025986247727 | Gg | yes | yes | parametric | pointer | sec:uncertainty |  | macro:PakRefNHthreeHigh |
| 07_uncertainty_PakRefNHthreeLow | 2297 | 2296.8639522060325 | Gg | yes | yes | parametric | pointer | sec:uncertainty |  | macro:PakRefNHthreeLow |
| 07_uncertainty_PakRefNOxHigh | 1029 | 1029.329914241718 | Gg | yes | yes | parametric | pointer | sec:uncertainty |  | macro:PakRefNOxHigh |
| 07_uncertainty_PakRefNOxLow | 660.6 | 660.6428150432497 | Gg | yes | yes | parametric | pointer | sec:uncertainty |  | macro:PakRefNOxLow |
| 07_uncertainty_PakRefPMfineHigh | 567 | 567.0472975400734 | Gg | yes | yes | parametric | pointer | sec:uncertainty |  | macro:PakRefPMfineHigh |
| 07_uncertainty_PakRefPMfineLow | 311.2 | 311.18836760402195 | Gg | yes | yes | parametric | pointer | sec:uncertainty |  | macro:PakRefPMfineLow |
| paper_AirLatestBC | 46.64 | 46.64349800000001 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestBC |
| paper_AirLatestCO | 5999 | 5998.811737 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestCO |
| paper_AirLatestNHthree | 2690 | 2690.0885439999997 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestNHthree |
| paper_AirLatestNMVOC | 1226 | 1226.466215 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestNMVOC |
| paper_AirLatestNOx | 833.1 | 833.1277690000001 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestNOx |
| paper_AirLatestPM | 422.7 | 422.696091 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestPMfine |
| paper_AirLatestSOtwo | 368.9 | 368.90514 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestSOtwo |
| paper_AirReferenceBC | 40.44 | 40.437172 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefBC |
| paper_AirReferenceCO | 5991 | 5991.2278 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefCO |
| paper_AirReferenceNHthree | 2670 | 2670.3884860000003 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefNHthree |
| paper_AirReferenceNMVOC | 1187 | 1186.722555 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefNMVOC |
| paper_AirReferenceNOx | 816.6 | 816.638272 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefNOx |
| paper_AirReferencePM | 422.8 | 422.8257290000001 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefPMfine |
| paper_AirReferenceSOtwo | 213.6 | 213.614163 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefSOtwo |
| paper_GHGLatestTotal | 457.2 | 457.2398322399998 | Mt | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestARfive |
| paper_GHGReferenceHigh | 503.2 | 503.2167084667016 | MtCO2e | yes | yes | parametric | pointer | sec:uncertainty |  | macro:PakRefARfiveHigh |
| paper_GHGReferenceLow | 399.9 | 399.8675867063499 | MtCO2e | yes | yes | parametric | pointer | sec:uncertainty |  | macro:PakRefARfiveLow |
| paper_GHGReferenceTotal | 444.6 | 444.6077554900002 | Mt | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefARfive |
| paper_PakChangeARfive | 14.9 | 14.931425253042363 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakChangeARfive |
| paper_PakChangeNHthree | 45.7 | 45.65464328299598 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakChangeNHthree |
| paper_PakChangeNOx | 18.2 | 18.164802029805948 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakChangeNOx |
| paper_PakChangePMfine | 24.0 | 24.035348775660893 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakChangePMfine |
| paper_PakChangeSOtwo | -45.0 | -45.03518931054845 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakChangeSOtwo |
| paper_PakNPartitionGHGChange | 0.04426 | 0.04425661257073443 | Mt_CO2e | yes | yes | structural | pointer | sec:scope |  | macro:PakRefNPartitionGHGChange |
| paper_PakNPartitionNHthreeChangeGg | 24.65 | 24.648932136633448 | Gg | yes | yes | structural | pointer | sec:scope |  | macro:PakRefNPartitionNHthreeChangeGg |
| paper_PakNPartitionNOxChangeGg | -149.8 | -149.75700318539782 | Gg | yes | yes | structural | pointer | sec:scope |  | macro:PakRefNPartitionNOxChangeGg |
| paper_PakRefCHfour | 8621 | 8621.196297999997 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefCHfour |
| paper_PakRefCOtwo | 161 | 161.01146620799997 | Mt | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefCOtwo |
| paper_PakRefNHthreeHigh | 3069 | 3069.025986247727 | Gg | yes | yes | parametric | pointer | sec:uncertainty |  | macro:PakRefNHthreeHigh |
| paper_PakRefNHthreeLow | 2297 | 2296.8639522060325 | Gg | yes | yes | parametric | pointer | sec:uncertainty |  | macro:PakRefNHthreeLow |
| paper_PakRefNOxHigh | 1029 | 1029.329914241718 | Gg | yes | yes | parametric | pointer | sec:uncertainty |  | macro:PakRefNOxHigh |
| paper_PakRefNOxLow | 660.6 | 660.6428150432497 | Gg | yes | yes | parametric | pointer | sec:uncertainty |  | macro:PakRefNOxLow |
| paper_PakRefNtwoO | 153.4 | 153.44274800000005 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefNtwoO |
| paper_PakRefPMfineHigh | 567 | 567.0472975400734 | Gg | yes | yes | parametric | pointer | sec:uncertainty |  | macro:PakRefPMfineHigh |
| paper_PakRefPMfineLow | 311.2 | 311.18836760402195 | Gg | yes | yes | parametric | pointer | sec:uncertainty |  | macro:PakRefPMfineLow |
| technical_supplement_AirReferenceNHthree | 2670 | 2670.3884860000003 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefNHthree |
| technical_supplement_AirReferenceNOx | 816.6 | 816.638272 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefNOx |
| technical_supplement_AirReferencePM | 422.8 | 422.8257290000001 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefPMfine |
| technical_supplement_GHGReferenceTotal | 444.6 | 444.6077554900002 | Mt | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefARfive |
| paper_PakLatestCoalSOtwoChangeGg | 173 | 173.207115 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestCoalSOtwoChangeGg |
| paper_PakLatestCoalSOtwoSupplyGg | -6.08 | -6.082368 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestCoalSOtwoSupplyGg |
| paper_PakLatestCoalSOtwoSeamGg | 50.5 | 50.496473 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestCoalSOtwoSeamGg |
| paper_PakLatestCoalSOtwoSplitGg | 120 | 119.530225 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestCoalSOtwoSplitGg |
| paper_PakLatestCoalSOtwoVintageGg | 9.26 | 9.262785 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestCoalSOtwoVintageGg |
| paper_PakLatestCoalSOtwoWithoutAllocationGg | -24 | -23.998507 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestCoalSOtwoWithoutAllocationGg |
| paper_PakLatestCoalPMfineWithoutAllocationGg | -8.71 | -8.714733 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestCoalPMfineWithoutAllocationGg |
| paper_PakRefNEmepNOxChangeGg | 118.2 | 118.19811309029078 | Gg | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRefNEmepNOxChangeGg |
| paper_PakChangeNOxNEmep | 17.4 | 17.381507107896187 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakChangeNOxNEmep |
| paper_PakChangeNOxNPartition | 11.5 | 11.515663390034426 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakChangeNOxNPartition |
| paper_PakFirstPowerOmitSOtwoLowPct | 0.04 | 0.04 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakFirstPowerOmitSOtwoLowPct |
| paper_PakFirstPowerOmitSOtwoHighPct | 0.31 | 0.31 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakFirstPowerOmitSOtwoHighPct |
| paper_PakFirstPowerOmitPMfineHighPct | 0.43 | 0.43 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakFirstPowerOmitPMfineHighPct |
| paper_PakLatestPowerOmitSOtwoLowPct | 6.43 | 6.43 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestPowerOmitSOtwoLowPct |
| paper_PakLatestPowerOmitSOtwoHighPct | 64.2 | 64.18 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestPowerOmitSOtwoHighPct |
| paper_PakLatestPowerOmitPMfineHighPct | 8.98 | 8.98 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestPowerOmitPMfineHighPct |
| paper_PakLatestPowerOmitNOxLowPct | 9.32 | 9.32 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestPowerOmitNOxLowPct |
| paper_PakLatestPowerOmitNOxHighPct | 14.3 | 14.28 | % | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakLatestPowerOmitNOxHighPct |
| paper_PakRoadConvPMfineHtapLow | 0.59 | 0.5867 | ratio | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRoadConvPMfineHtapLow |
| paper_PakRoadConvPMfineHtapHigh | 0.83 | 0.8324 | ratio | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRoadConvPMfineHtapHigh |
| paper_PakRoadConvBCHtapLow | 0.42 | 0.4209 | ratio | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRoadConvBCHtapLow |
| paper_PakRoadConvBCHtapHigh | 0.59 | 0.5861 | ratio | yes | yes | estimated-mixed | pointer | sec:scope |  | macro:PakRoadConvBCHtapHigh |


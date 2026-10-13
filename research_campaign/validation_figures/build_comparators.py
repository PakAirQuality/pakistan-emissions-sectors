#!/usr/bin/env python3
"""T-VAL-1. Build the comparator registry and the matched comparison.

READ-ONLY over the repository. Writes only into research_campaign/validation_figures/.

comparators.csv      one row per comparator dataset actually used anywhere in PakEmis
matched_comparison.csv  one row per comparison, native-gas where feasible
comparator_defects.csv  the registry contradictions found while building the above

Every PakEmis value is recomputed here from outputs/pakemis_source_streams.csv (the
shipped stream product) rather than transcribed, so the file fails loudly if the
product moves. Comparator values come from data/shared/evidence/benchmarks.csv and
benchmarks_air.csv, which pin their own source file and sha256.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent

streams = pd.read_csv(REPO / "outputs/pakemis_source_streams.csv", comment="#")
bench = pd.read_csv(REPO / "data/shared/evidence/benchmarks.csv", comment="#")
bair = pd.read_csv(REPO / "data/shared/evidence/benchmarks_air.csv", comment="#")
nbc = pd.read_csv(REPO / "outputs/national_benchmark_comparison.csv", comment="#")

# PakEmis native-gas masses, Gg, FY2023-24 reference configuration
def native(cat: str, gas: str) -> float:
    q = streams[(streams.ipcc_category == cat) & (streams.gas == gas)]
    assert len(q), (cat, gas)
    assert set(q.native_unit) == {"Gg"}, q.native_unit.unique()
    return float(q.emissions_native.sum())


PK = {
    ("Enteric fermentation", "CH4"): native("Enteric fermentation", "CH4"),
    ("Rice cultivation", "CH4"): native("Rice cultivation", "CH4"),
    ("Agricultural soils", "N2O"): native("Agricultural soils", "N2O"),
    ("Urea application", "CO2"): native("Urea application", "CO2"),
    ("Cement production", "CO2"): native("Cement production", "CO2"),
}

# GWP vintages, as each side applies them
AR5 = {"CH4_bio": 28.0, "CH4_fossil": 30.0, "N2O": 265.0, "CO2": 1.0}
AR6 = {"CH4_bio": 27.0, "CH4_fossil": 29.8, "N2O": 273.0, "CO2": 1.0}


def bm(source: str, cat: str, year: int) -> float:
    q = bench[(bench["source"] == source) & (bench.engine_category == cat) & (bench.year == year)]
    assert len(q) == 1, (source, cat, year, len(q))
    return float(q.value_Mt_co2e.iloc[0])


def eng(source: str, cat: str, year: int) -> float:
    q = nbc[(nbc["source"] == source) & (nbc.engine_category == cat) & (nbc.year == year)]
    assert len(q) == 1, (source, cat, year)
    return float(q.engine_Mt_co2e.iloc[0])


# ---------------------------------------------------------------- comparators.csv
COMP_COLS = [
    "comparator_id", "inventory_name", "dataset_release", "release_token_is_an_api_version",
    "retrieval_date", "retrieval_date_evidence", "original_url", "gases", "period_covered",
    "geographical_boundary", "sector_mapping", "gwp_vintage", "source_coverage",
    "shared_inputs_with_pakemis", "independence_class_code", "independence_class", "evaluation_purpose", "licence",
    "local_snapshot_path", "local_snapshot_sha256", "held", "used_in", "registry_defects",
]

NR = "NOT RECORDED"
P1 = "P1 extraction/accounting check"
P2 = "P2 external intercomparison"
P3 = "P3 independent activity/location check"
P4 = "P4 observational emissions evaluation"

C = [
dict(comparator_id="CMP-EDGAR-2025", inventory_name="EDGAR GHG booklet (JRC)",
 dataset_release="EDGAR 2025 GHG booklet, sheet GHG_by_sector_and_country",
 release_token_is_an_api_version="no",
 retrieval_date=NR, retrieval_date_evidence="only an EXTRACTION date is recorded (source_documents.csv row 64, 'boundary program Wave A 2026-09-11'); no retrieval field exists in any layer",
 original_url="https://edgar.jrc.ec.europa.eu/ (Datasets > GHG > EDGAR GHG emissions XLSX); the exact address is in code comments only, not in a registry",
 gases="CO2, CH4, N2O (F-gases reported separately and excluded both sides)",
 period_covered="CY1970-CY2024; the benchmark rows read CY2023 and CY2024",
 geographical_boundary="national, EDGAR's own Pakistan country mask (includes areas Pakistan administers; not reconciled cell-by-cell against the geoBoundaries frame)",
 sector_mapping="EDGAR sector labels (Power Industry, Buildings, Transport, Processes, Fuel Exploitation, Waste, Agriculture) mapped by hand to IPCC categories; Processes spans five IPPU categories against three estimated here",
 gwp_vintage="AR5", source_coverage="global, all sectors except LULUCF",
 shared_inputs_with_pakemis="HIGH for energy: EDGAR's Pakistani fuel combustion rests on IEA energy balances, which are built from the same national submissions (HDIP/OCAC) that PakEmis reads. Agreement on 1.A categories is therefore NOT independent corroboration of the activity.",
 independence_class="partial (method-independent, activity largely shared)", evaluation_purpose=P2,
 licence="CC-BY-4.0 (source_documents.csv rows 64,165)",
 local_snapshot_path="sources/EDGAR/EDGAR_2025_GHG_booklet_2025.xlsx",
 local_snapshot_sha256="8bd6b8a405b9c40548d8df11d06aaed8838d31acce1d4dee1cb858d7eade3597",
 held="yes", used_in="national_benchmark_comparison.csv; national_benchmark_scope_coverage.csv; national_edgar_transport_comparison.csv; pakemis_industry_edgar_divergence.csv",
 registry_defects="D-V10; D-V6"),

dict(comparator_id="CMP-EDGAR-2024", inventory_name="EDGAR GHG booklet (JRC), prior vintage",
 dataset_release="EDGAR 2024 GHG booklet", release_token_is_an_api_version="no",
 retrieval_date=NR, retrieval_date_evidence="none",
 original_url="https://edgar.jrc.ec.europa.eu/dataset_ghg2024",
 gases="CO2, CH4, N2O", period_covered="CY2023 column only, as held",
 geographical_boundary="national, EDGAR country mask",
 sector_mapping="EDGAR Agriculture aggregate",
 gwp_vintage="AR5", source_coverage="global",
 shared_inputs_with_pakemis="as CMP-EDGAR-2025",
 independence_class="partial", evaluation_purpose=P2,
 licence="'Open' only (docs/sources.md row 11); not stated for this vintage",
 local_snapshot_path="", local_snapshot_sha256="", held="no - value carried as a transcribed number with no pinned file",
 used_in="national_benchmark_comparison.csv (EDGAR TOTAL CY2023 = 267.4 Mt)",
 registry_defects="RETAINED, NOT REPLACED: the 2025 booklet was added BESIDE this row rather than overwriting it, so the agri-CH4 revision stays visible. That is the correct handling and is recorded here as verified. The row is nevertheless unreproducible: no file, no digest."),

dict(comparator_id="CMP-EDGAR-AP81", inventory_name="EDGAR v8.1 air pollutants, country x sector workbooks",
 dataset_release="EDGAR v8.1 FT2022 AP (August 2024); SO2 workbook is the _v2 reissue",
 release_token_is_an_api_version="no",
 retrieval_date="2026-09-17 for SO2(v2)/CO/NMVOC/NH3/BC; NOT RECORDED for NOx and PM2.5",
 retrieval_date_evidence="data/raw/ACQUISITION_LOG_industrial_air.csv; data/catalog/acquisition_attempts.csv lines 64-68",
 original_url="https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/v81_FT2022_AP_new/EDGAR_<POLL>_1970_2022[_v2].zip (no URL recorded for the NOx or PM2.5 zips)",
 gases="air pollutants: NOx, PM2.5, SO2, CO, NMVOC, NH3, BC (NOT greenhouse gases)",
 period_covered="CY1970-CY2022", geographical_boundary="national, EDGAR country mask",
 sector_mapping="EDGAR AP sector codes; railways read as 1.A.3.c",
 gwp_vintage="not applicable - native pollutant mass",
 source_coverage="global", shared_inputs_with_pakemis="none identified for the AP factors; activity lineage as CMP-EDGAR-2025",
 independence_class="partial", evaluation_purpose=P2,
 licence="not-established (source_documents.csv row 63 'undetermined'); attribution to the EDGARv8.1 AP website required",
 local_snapshot_path="sources/EDGAR/EDGAR_NOx_1970_2022.zip; sources/EDGAR/EDGAR_PM25_1970_2022.zip; data/raw/edgar/EDGAR_{SO2_v2,CO,NMVOC,NH3,BC}_1970_2022.zip",
 local_snapshot_sha256="NOx a1c99caeb3d7323df1b78b106226b8b5814146da85cc31ec9c996369103b9864; PM25 4af5b9c3fcac47d0b507f5b2d8cc55eb4bb851e31fb814ed45b8a50adda6c5a3; SO2v2 0c1de211e70e22c2dfe4a53b80719401f66dc44a9a3295e76cea7312fa5eac10",
 held="yes", used_in="benchmarks_air.csv; pakemis_industry_air_edgar_comparison.csv; railways_elk_crosscheck_2024.csv",
 registry_defects="D-V6 (licence 'not-established' for the same publisher the GHG booklet is CC-BY-4.0 for)"),

dict(comparator_id="CMP-EDGAR-GRID-SO2", inventory_name="EDGAR v8.1 air-pollutant gridmaps",
 dataset_release="v8.1_FT2022_AP, 0.1 degree annual NetCDF, SO2 ONLY",
 release_token_is_an_api_version="no",
 retrieval_date="2026-09-18 and 2026-09-19",
 retrieval_date_evidence="data/raw/ACQUISITION_LOG_industrial_air.csv",
 original_url="https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/v81_FT2022_AP_new/SO2/<SECTOR>/emi_nc/v8.1_FT2022_AP_SO2_<year>_<SECTOR>_emi_nc.zip",
 gases="SO2 only", period_covered="CY2015-CY2022, 19 sectors per year",
 geographical_boundary="global 0.1 degree lattice; summed here by area fraction over the ADM1/district polygons",
 sector_mapping="EDGAR gridmap sector codes", gwp_vintage="not applicable",
 source_coverage="global",
 shared_inputs_with_pakemis="EDGAR's own spatial proxies are independent of PakEmis's, but both use population and built-up surfaces of similar lineage; the agreement of two population-weighted maps is weak evidence",
 independence_class="large (spatially), partial (magnitude)", evaluation_purpose=P2,
 licence="not-established", local_snapshot_path="data/raw/edgar/gridmaps/ (152 zips)",
 local_snapshot_sha256="per file in data/catalog/raw_manifest.csv lines 91ff",
 held="yes", used_in="pakemis_air_lahore_external_comparison.csv; pakemis_air_provincial_external_comparison.csv",
 registry_defects="NO NOx and NO PM2.5 gridmaps are held, only the country x sector workbooks - so no gridded comparison exists for those pollutants"),

dict(comparator_id="CMP-FAOSTAT-GT", inventory_name="FAOSTAT Emissions Totals",
 dataset_release="domain GT (Emissions Totals), Pakistan area 165, element 723113; NO FAOSTAT release/update date is recorded anywhere",
 release_token_is_an_api_version="no",
 retrieval_date="2026-07-01 (interactive extract, not retained) AND 2026-09-30 (bulk, retained)",
 retrieval_date_evidence="data/catalog/not_retained_register.csv row faostat_emissions_totals; data/raw/ACQUISITION_LOG_faostat_soils.csv",
 original_url="https://www.fao.org/faostat/en/#data/GT ; bulk https://bulks-faostat.fao.org/production/Emissions_Totals_E_All_Data_(Normalized).zip",
 gases="CH4 and N2O by item, published as CO2e; the HELD 2026-07-01 extract carries CO2e ONLY, no native-gas column",
 period_covered="CY1961-CY2023 in the held panel; the benchmark rows read CY2023",
 geographical_boundary="national, FAO area 165",
 sector_mapping="FAO farm-gate items 5058/5059/5060/5061-5064/5066/1711 mapped to IPCC 3.A, 3.B, 3.C, 3.D, 3.F",
 gwp_vintage="AR5", source_coverage="global agriculture (farm-gate), no energy or IPPU",
 shared_inputs_with_pakemis="HIGH. FAOSTAT's Pakistan livestock heads and crop areas are Pakistan's own reported statistics - the same PBS / MNFSR lineage PakEmis reads. An agreement on enteric CH4 is therefore an EMISSION FACTOR comparison, not an independent check of the activity.",
 independence_class="partial (shared activity, independent factors and method)", evaluation_purpose=P2,
 licence="CC-BY-4.0", local_snapshot_path="data/sectors/agriculture/activity/historical/faostat_emissions.csv (CO2e extract); data/raw/faostat/faostat_emissions_totals_pakistan.csv (bulk, 10,152 rows)",
 local_snapshot_sha256="bulk 30d224332bff13bc36f23fb2313ed3fdf468ae2fc4ba76dff0c830fb0d8eb604; the CO2e extract carries NO sha256 in benchmarks.csv",
 held="yes (bulk, since 2026-09-30); the extract the benchmarks actually read is unhashed",
 used_in="national_benchmark_comparison.csv; timeseries_validation.csv; pakemis_faostat_nitrogen_flows.csv",
 registry_defects="D-V5"),

dict(comparator_id="CMP-FAOSTAT-QCL-RFN", inventory_name="FAOSTAT production and fertilizer panels",
 dataset_release="domains QCL (crops and livestock) and RFN (fertilizer by nutrient), normalized bulks; no release date recorded",
 release_token_is_an_api_version="no", retrieval_date="2026-07-01; re-probe 2026-08-23",
 retrieval_date_evidence="not_retained_register.csv row faostat_qcl_rfn_panel; acquisition_attempts.csv 2026-08-23",
 original_url="https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_All_Data_(Normalized).zip",
 gases="not applicable - activity data", period_covered="CY1961 onward; RFN updated Jul 2025",
 geographical_boundary="national", sector_mapping="crop and livestock items; nutrient N",
 gwp_vintage="not applicable", source_coverage="global",
 shared_inputs_with_pakemis="this is an INPUT to PakEmis history as well as a comparator in places; where it is both, the comparison is self-agreement and must be labelled so",
 independence_class="none where it is also the input", evaluation_purpose=P3,
 licence="CC-BY-4.0", local_snapshot_path="data/sectors/agriculture/activity/historical/{crops,livestock_stocks,fertilizer_n}.csv",
 local_snapshot_sha256="NOT RECORDED - not_retained_register states 'no byte-stable national file ever existed to hash'",
 held="derived extracts only", used_in="agriculture history; pakemis_faostat_nitrogen_flows.csv",
 registry_defects=""),

dict(comparator_id="CMP-CT-AGRI", inventory_name="Climate TRACE, country x subsector",
 dataset_release="UNRECORDED. The registries say 'Climate TRACE v7', which is the API PATH (https://api.climatetrace.org/v7), not a dataset release. One free-text note says 'v7.1.9'; no held payload carries a version field.",
 release_token_is_an_api_version="YES - this is the defect the registry exists to expose",
 retrieval_date=NR, retrieval_date_evidence="none; the extract itself is not held",
 original_url="https://api.climatetrace.org/v7 (country-by-subsector download)",
 gases="CH4, N2O, CO2 - published per gas upstream, but the held benchmark rows carry CO2e ONLY",
 period_covered="CY2024 for the benchmark rows", geographical_boundary="national, Climate TRACE country mask",
 sector_mapping="CT subsectors (enteric-fermentation, manure-management, rice-cultivation, synthetic-fertilizer-application, cropland-fires) mapped to IPCC 3.A/3.B/3.C/3.D/3.F by hand; CT routes manure-to-soils and manure-on-pasture into soils",
 gwp_vintage="AR6", source_coverage="global, all sectors",
 shared_inputs_with_pakemis="CT's livestock and crop activity for Pakistan anchors on FAO/national statistics, the same lineage as PakEmis and FAOSTAT. Its 'observation-driven' label does not extend to Pakistani agriculture.",
 independence_class="partial", evaluation_purpose=P2,
 licence="CC-BY-4.0", local_snapshot_path="", local_snapshot_sha256="",
 held="NO - benchmarks.csv carries benchmark_source_file = blank for every Climate TRACE agriculture row",
 used_in="national_benchmark_comparison.csv (6 rows)",
 registry_defects="D-V1"),

dict(comparator_id="CMP-CT-AVIATION", inventory_name="Climate TRACE aviation",
 dataset_release="UNRECORDED; held payloads declare only 'api: https://api.climatetrace.org/v7'",
 release_token_is_an_api_version="YES",
 retrieval_date="approx 2026-08-04 from file mtime only; NOT RECORDED as a registry field",
 retrieval_date_evidence="raw_manifest.csv mtime 1786013547",
 original_url="https://api.climatetrace.org/", gases="CO2",
 period_covered="CY2015-CY2024 national monthly; CY2021-CY2024 airport level",
 geographical_boundary="national and airport point sources",
 sector_mapping="CT domestic-aviation and international-aviation to 1.A.3.a",
 gwp_vintage="not applicable (CO2)", source_coverage="global",
 shared_inputs_with_pakemis="CT aviation is flight-movement driven (ADS-B lineage); PakEmis aviation is OCAC fuel driven. Genuinely different activity. BUT the airport coordinates are shared.",
 independence_class="large on magnitude, partial on geography", evaluation_purpose=P3,
 licence="CC-BY-4.0",
 local_snapshot_path="sources/Aviation/climatetrace_aviation_PAK_2015_2024.json; climatetrace_airports_PAK_2021_2024.json; climatetrace_sources_PAK_2023.json; climatetrace_rankings_PAK_2021_2024.json",
 local_snapshot_sha256="4eeb31ab32e80bddd36cf171dbc7a732746f3f5d2f35c416593425a28a388fd2 (aviation 2015-2024); f76fb13a59ef8e4a8ba2d4968833125ff4787fcf0109588ab82c6b2ed12b7ba4 (airports)",
 held="yes", used_in="aviation_climatetrace_national_monthly.csv; aviation_climatetrace_airport_comparison.csv",
 registry_defects="D-V1"),

dict(comparator_id="CMP-CT-POWER", inventory_name="Climate TRACE power assets",
 dataset_release="UNRECORDED and CONTRADICTED: source_documents.csv calls it 'Climate TRACE v7 power assets'; sources/Power Plants/README.md records the call as api.climatetrace.org/v6/assets. Both are API paths, neither is a dataset release.",
 release_token_is_an_api_version="YES", retrieval_date="approx 2026-08-04 from mtime; NOT RECORDED",
 retrieval_date_evidence="raw_manifest.csv mtime 1785835506",
 original_url="https://api.climatetrace.org/v6/assets?countries=PAK&sectors=power&limit=500",
 gases="CO2e (CT's own aggregation)", period_covered="asset snapshot with FY2023 generation",
 geographical_boundary="point assets inside Pakistan",
 sector_mapping="CT power assets to 1.A.1.a stations", gwp_vintage="CT's own, unstated in the held file",
 source_coverage="global power fleet",
 shared_inputs_with_pakemis="SEVERE. 29 of the 52 plant coordinates PakEmis uses are themselves Climate TRACE derived (13 climatetrace-only + 16 climatetrace+wri_gppd in data/sectors/power/activity/plant_coordinates.csv). Using CT to check those coordinates is circular.",
 independence_class="NONE for the location of 29 of 52 plants (circular); partial for magnitude",
 evaluation_purpose=P3, licence="CC-BY-4.0",
 local_snapshot_path="sources/Power Plants/climatetrace_power_assets_PAK.csv",
 local_snapshot_sha256="52637aa4ae5114926f054351d7b73f1067fe1503d3cce5477556ed1517060a27",
 held="yes", used_in="power_climatetrace_plants_fy2023_24.csv; plant_coordinates.csv (as an INPUT)",
 registry_defects="D-V1; D-V2; D-V11; D-V13"),

dict(comparator_id="CMP-CT-WASTE", inventory_name="Climate TRACE waste sources",
 dataset_release="UNRECORDED; payload declares 'api: https://api.climatetrace.org/v7'",
 release_token_is_an_api_version="YES", retrieval_date="approx 2026-08-13 from mtime; NOT RECORDED",
 retrieval_date_evidence="raw_manifest.csv mtime 1786765185",
 original_url="https://api.climatetrace.org/v7", gases="CH4",
 period_covered="CY2021-CY2024 rankings; 27 sources",
 geographical_boundary="point sources inside Pakistan",
 sector_mapping="solid-waste-disposal, domestic-wastewater-treatment-and-discharge to 4.A and 4.D",
 gwp_vintage="CT's own", source_coverage="global",
 shared_inputs_with_pakemis="none identified",
 independence_class="large", evaluation_purpose=P3, licence="CC-BY-4.0",
 local_snapshot_path="sources/ClimateTRACE/climatetrace_waste_PAK_sources.json",
 local_snapshot_sha256="4c8ab57e62e34f4285fc1f576292b0536c891f8959bc11a720efef52f0aeb316",
 held="yes", used_in="waste site register (candidate source, declared 'never ground truth')",
 registry_defects="D-V1"),

dict(comparator_id="CMP-CRT-2022", inventory_name="Pakistan UNFCCC Common Reporting Tables",
 dataset_release="Pakistan 2024 CRT submission, inventory year CY2022",
 release_token_is_an_api_version="no", retrieval_date=NR,
 retrieval_date_evidence="none in any layer; mtime approx 2026-08-09 only",
 original_url="https://unfccc.int/documents/655653 (two sector manifests) VS https://unfccc.int/documents/645241 (public_documents.csv and source_documents.csv row 29) - for the SAME sha256",
 gases="CO2, CH4, N2O, F-gases, plus NOx/CO/NMVOC/SO2 precursor columns",
 period_covered="CY2022 (single inventory year)",
 geographical_boundary="Pakistan's own reported national territory",
 sector_mapping="IPCC 2006 categories directly - the closest taxonomy match available",
 gwp_vintage="AR5 for the CO2e columns; native-gas cells also published, and the native cells are what PakEmis reads",
 source_coverage="whole national inventory including LULUCF",
 shared_inputs_with_pakemis="The CRT is Pakistan's own account built from the same national statistics (HDIP, PBS, OGAC). It is the OFFICIAL account, not an independent one. Where PakEmis reproduces a CRT cell that is an extraction/accounting check, not corroboration.",
 independence_class="partial (same country statistics, different compiler and method)",
 evaluation_purpose=P2 + " (and " + P1 + " for the hash-pinned cell audits)",
 licence="unfccc-public", local_snapshot_path="sources/Aviation/PAK_CRT_2024.zip",
 local_snapshot_sha256="afba70d10be0694aea6b2ba2cec311e149473346daa206319138185c190e8f38",
 held="yes", used_in="national_crt_crosswalk.csv; aviation/ippu/fugitives/railways/power CRT audits",
 registry_defects="D-V3; D-V6"),

dict(comparator_id="CMP-BTR1", inventory_name="Pakistan First Biennial Transparency Report",
 dataset_release="BTR1, submitted 2024; energy chapter reports CY2021",
 release_token_is_an_api_version="no", retrieval_date=NR, retrieval_date_evidence="none",
 original_url="https://unfccc.int/documents/645241", gases="CO2, CH4, N2O",
 period_covered="CY2021 energy; FY2020-21 land block",
 geographical_boundary="national", sector_mapping="IPCC 2006",
 gwp_vintage="AR5", source_coverage="whole inventory incl. LULUCF",
 shared_inputs_with_pakemis="as CMP-CRT-2022", independence_class="partial",
 evaluation_purpose=P2, licence="unfccc-public",
 local_snapshot_path="sources/UNFCCC/pakistan_btr1_2024.pdf (= sources/Aviation/Pakistan_BTR_2024.pdf, byte-identical)",
 local_snapshot_sha256="1d2e5970736b5e9d6f1596bd1e994adff9883430dbc02cebd711380752afe904",
 held="yes", used_in="fugitives benchmark_controls; residential_official_comparison_2024.csv; land lane",
 registry_defects="D-V6"),

dict(comparator_id="CMP-BUR1", inventory_name="Pakistan First Biennial Update Report",
 dataset_release="BUR1 (2022), national inventory FY2017-18",
 release_token_is_an_api_version="no", retrieval_date=NR, retrieval_date_evidence="none",
 original_url=NR + " (only the bare https://unfccc.int/documents/ in docs/sources.md row E4)",
 gases="CO2, CH4, N2O", period_covered="FY2017-18 - a FISCAL year, so this one comparator needs no calendar approximation",
 geographical_boundary="national", sector_mapping="IPCC 2006",
 gwp_vintage="AR5", source_coverage="whole inventory; the ONLY official account with a genuine gross forest split",
 shared_inputs_with_pakemis="as CMP-CRT-2022", independence_class="partial",
 evaluation_purpose=P2, licence="undetermined in source_documents rows 148/160, unfccc-public elsewhere",
 local_snapshot_path="data/raw/land/pakistan_bur1_2022.pdf",
 local_snapshot_sha256="130951595a088d8815da34ac3f68bc30931fcd433824a4b8daca7ae03ced72ed",
 held="yes", used_in="residential_official_comparison_2024.csv; railways official_benchmarks; land lane",
 registry_defects="D-V6"),

dict(comparator_id="CMP-TNC-2025", inventory_name="Pakistan Third National Communication",
 dataset_release="NC3/TNC, submitted 2025", release_token_is_an_api_version="no",
 retrieval_date=NR, retrieval_date_evidence="none",
 original_url="https://unfccc.int/documents/648622", gases="CO2, CH4, N2O",
 period_covered="FY2020-21 land block identical to BTR1 and CRT v2.83",
 geographical_boundary="national", sector_mapping="IPCC 2006", gwp_vintage="AR5",
 source_coverage="whole inventory",
 shared_inputs_with_pakemis="as CMP-CRT-2022; and this document REPUBLISHES the BTR1 land block, so it is not a third observation of the land account",
 independence_class="none vs BTR1 (same block republished)", evaluation_purpose=P2,
 licence="unfccc-public", local_snapshot_path="sources/UNFCCC/pakistan_tnc_2025.pdf",
 local_snapshot_sha256="57d85ee215a535f980a115ad69bc7bbe0abc707ddecd2e7f611a1ca35f857d6f",
 held="yes", used_in="land lane official_account.csv", registry_defects=""),

dict(comparator_id="CMP-OECD-AIR", inventory_name="OECD air transport (SDMX)",
 dataset_release="OECD.SDD.NAD.SEEA DSD_AIR_TRANSPORT@DF_AIR_TRANSPORT, dataflow 1.0",
 release_token_is_an_api_version="partly - 'dataflow 1.0' is the SDMX structure version, not a data vintage; the data vintage is NOT RECORDED",
 retrieval_date="2026-08-06", retrieval_date_evidence="data/sectors/aviation/metadata/source_manifest.csv version field 'OECD dataflow 1.0 extracted 2026-08-06'",
 original_url="https://sdmx.oecd.org/public/rest/data/OECD.SDD.NAD.SEEA/DSD_AIR_TRANSPORT@DF_AIR_TRANSPORT",
 gases="not applicable - fuel and flight activity",
 period_covered="2019-2025 monthly", geographical_boundary="resident-carrier and territory bases, both reported",
 sector_mapping="resident vs territory aviation, the 1.A.3.a / bunker split",
 gwp_vintage="not applicable", source_coverage="OECD members plus partners",
 shared_inputs_with_pakemis="none - OECD's residence basis is built independently of OCAC uplift",
 independence_class="large", evaluation_purpose=P3, licence=NR,
 local_snapshot_path="sources/Aviation/OECD_air_transport_PAK_2019_2025.csv; OECD_air_transport_PAK_FY2022_FY2023.csv",
 local_snapshot_sha256="in data/catalog/raw_manifest.csv", held="yes",
 used_in="aviation_ocac_oecd_annual_comparison.csv; aviation_oecd_monthly.csv", registry_defects=""),

dict(comparator_id="CMP-GEM-COAL", inventory_name="Global Energy Monitor Global Coal Plant Tracker",
 dataset_release="GEM Global Coal Plant Tracker, July 2026", release_token_is_an_api_version="no",
 retrieval_date=NR, retrieval_date_evidence="none for this tracker (2026-08-15 is recorded for the cement tracker only)",
 original_url=NR + " for the xlsx; https://www.gem.wiki/ for the per-station pages",
 gases="not applicable - asset register", period_covered="asset snapshot, 88 Pakistani units",
 geographical_boundary="point assets; GEM supplies its own province/district fields",
 sector_mapping="coal units to 1.A.1.a", gwp_vintage="not applicable", source_coverage="global coal fleet",
 shared_inputs_with_pakemis="GEM coordinates are used as an INPUT to data/sectors/power/activity/coal_plant_coordinates.csv, so a GEM-vs-register check is self-agreement for those rows",
 independence_class="partial; none where GEM is the coordinate source",
 evaluation_purpose=P3, licence="CC-BY-4.0 per sources/GEM/GEM_SOURCES.json; 'undetermined' in source_documents.csv row 121 whose own note says (CC BY 4.0)",
 local_snapshot_path="not held - only the extract data/sectors/power/activity/gem_coal_pak.csv",
 local_snapshot_sha256="621b86568996b8c50724fa3d61acbbd833b796144be7d0e6ce8e411c8dd16a30 (xlsx digest pinned although the xlsx is not archived)",
 held="extract only", used_in="power_gem_audit.csv; pakemis_power_province_boundary_audit.csv",
 registry_defects="D-V6; D-V9; D-V14"),

dict(comparator_id="CMP-GEM-CEMENT", inventory_name="GEM Global Cement and Concrete Tracker",
 dataset_release="GEM Global Cement and Concrete Tracker, July 2026, Standard Copy V1",
 release_token_is_an_api_version="no", retrieval_date="2026-08-15",
 retrieval_date_evidence="data/catalog/not_retained_register.csv row gem_tracker_xlsx",
 original_url="https://globalenergymonitor.org/projects/global-cement-and-concrete-tracker/download-data/",
 gases="not applicable", period_covered="asset snapshot, 32 Pakistani plants",
 geographical_boundary="point assets", sector_mapping="cement plants to 2.A.1",
 gwp_vintage="not applicable", source_coverage="global cement fleet",
 shared_inputs_with_pakemis="checked AGAINST the OpenStreetMap-derived coordinates the register already held, so the two registers are independent of each other",
 independence_class="large", evaluation_purpose=P3,
 licence="CC-BY-4.0 per GEM_SOURCES.json; 'undetermined' in source_documents.csv row 69",
 local_snapshot_path="not held - extract data/sectors/industry/activity/gem_cement_pak.csv",
 local_snapshot_sha256="3fc861ebd0be8f6e980b5bff6c05f28472f7b82f9f31f78d7fb98127938a33fb",
 held="extract only", used_in="ippu_facility_coordinate_agreement.csv", registry_defects="D-V6; D-V9"),

dict(comparator_id="CMP-GEM-GOGPT", inventory_name="GEM Global Oil and Gas Plant Tracker",
 dataset_release="GOGPT, August 2026", release_token_is_an_api_version="no",
 retrieval_date=NR, retrieval_date_evidence="none",
 original_url=NR, gases="not applicable",
 period_covered="asset snapshot, 88 units / 46 plants", geographical_boundary="point assets",
 sector_mapping="gas and oil units to 1.A.1.a", gwp_vintage="not applicable",
 source_coverage="global gas and oil power fleet",
 shared_inputs_with_pakemis="as CMP-GEM-COAL", independence_class="partial",
 evaluation_purpose=P3, licence="CC-BY-4.0 per GEM_SOURCES.json",
 local_snapshot_path="not held - extract data/sectors/power/activity/gem_gas_oil_pak.csv",
 local_snapshot_sha256="920dcf34c6bfc60fa95ba84a8a82e6fd9eb484ee920e3828a9cdb47b2f70b316",
 held="extract only", used_in="power_gem_audit.csv", registry_defects="D-V6; D-V9"),

dict(comparator_id="CMP-GEM-BIO", inventory_name="GEM Global Bioenergy Power Tracker",
 dataset_release="Global Bioenergy Power Tracker V3 (row release date 2025-06-23)",
 release_token_is_an_api_version="no", retrieval_date=NR, retrieval_date_evidence="none",
 original_url=NR, gases="not applicable", period_covered="asset snapshot, 23 Pakistani entries",
 geographical_boundary="point assets", sector_mapping="bagasse units to 1.A.1.a",
 gwp_vintage="not applicable", source_coverage="global bioenergy fleet",
 shared_inputs_with_pakemis="as CMP-GEM-COAL", independence_class="partial", evaluation_purpose=P3,
 licence="CC-BY-4.0", local_snapshot_path="not held - extract data/sectors/power/activity/gem_bioenergy_pak.csv",
 local_snapshot_sha256="4799a4dae94addf2f5b96e8eb4beb5f2ca7683659fd262020c5f3a1f9ad45590",
 held="extract only", used_in="power asset census", registry_defects="D-V6; D-V9"),

dict(comparator_id="CMP-WRI-GPPD", inventory_name="WRI Global Power Plant Database",
 dataset_release="v1.3 (recorded only in sources/Power Plants/README.md; the catalog layer records the opaque token 'climatetrace+wri_gppd')",
 release_token_is_an_api_version="no", retrieval_date=NR, retrieval_date_evidence="none; mtime approx 2026-08-04",
 original_url=NR + " - the README records the Climate TRACE call but no GPPD address",
 gases="not applicable", period_covered="snapshot register, no time series",
 geographical_boundary="point assets", sector_mapping="plants to 1.A.1.a",
 gwp_vintage="not applicable", source_coverage="global, 62 Pakistani plants",
 shared_inputs_with_pakemis="GPPD is an INPUT to plant_coordinates.csv for 39 of 52 plants (23 wri-only + 16 shared with CT); it cannot also be an independent check of those",
 independence_class="none where it is the coordinate source", evaluation_purpose=P3,
 licence="not-established", local_snapshot_path="sources/Power Plants/wri_gppd_PAK.csv",
 local_snapshot_sha256="c8b39affe0d57727ef6df5bce0646242700c9aa799d1d3999dd6bb605512f470",
 held="yes", used_in="plant_coordinates.csv (input); power_gem_audit.csv", registry_defects=""),

dict(comparator_id="CMP-GGFR-FLARE", inventory_name="World Bank GGFR global gas flaring site list",
 dataset_release="World Bank GGFR global gas flaring site list 2012-2025", release_token_is_an_api_version="no",
 retrieval_date=NR, retrieval_date_evidence="none; mtime approx 2026-08-07", original_url=NR,
 gases="not an emissions product - satellite-measured flared VOLUME in bcm",
 period_covered="CY2012-CY2025 annual", geographical_boundary="flare point locations",
 sector_mapping="upstream flaring, 1.B.2", gwp_vintage="not applicable",
 source_coverage="global flaring, 134 Pakistani rows",
 shared_inputs_with_pakemis="none - this is a true external observation of flaring",
 independence_class="large", evaluation_purpose=P4 + " for flared volume; " + P3 + " for site location",
 licence="no statement recorded in this repository (consumed_derivatives.csv, verbatim)",
 local_snapshot_path="sources/Fugitives/world_bank_flare_sites_2012_2025.xlsx",
 local_snapshot_sha256="8f00b83a29fbc9e08fd08575c09425ebca39c9b17de209f140db4238692c9104",
 held="yes", used_in="fugitives_mars_flare_matches_2024.csv; fugitives_viirs_flaring_2012_2025.csv",
 registry_defects="licence genuinely unknown; docs/DATA_ACQUISITION.md conflates this product with VIIRS Nightfire, which is NOT held"),

dict(comparator_id="CMP-MARS", inventory_name="UNEP IMEO Methane Alert and Response System",
 dataset_release="NOT RECORDED - the archive name unep_mars_plumes.zip is all there is; no release or version number anywhere",
 release_token_is_an_api_version="no", retrieval_date=NR, retrieval_date_evidence="none; mtime approx 2026-08-07",
 original_url=NR, gases="CH4 (plume detections, with a rate estimate per plume)",
 period_covered="the held extract's tile_date runs 2023-02-03 to 2026-06-30; the validation catalog declares 2021-2024",
 geographical_boundary="plume footprints, global",
 sector_mapping="oil and gas, 1.B.2", gwp_vintage="not applicable",
 source_coverage="detection-limited: absence of a plume bounds nothing below the sensor floor",
 shared_inputs_with_pakemis="none - a genuine external observation",
 independence_class="large", evaluation_purpose=P4 + " (partial: it evaluates presence, location and a super-emitter rate, NOT the sector total)",
 licence="CC-BY-NC-SA (the archive carries LICENSE-CC-BY-NC-SA.txt) - NON-COMMERCIAL SHARE-ALIKE, not an open licence, and not redistributable in the deposit",
 local_snapshot_path="sources/Fugitives/unep_mars_plumes.zip",
 local_snapshot_sha256="296730705ca379cd04025ccdfe3b4ad2f47701d66cd88c2fb5cad0f6154f09a6",
 held="yes", used_in="fugitives_observation_match_audit_2024.csv; fugitives_observation_field_evaluation_2024.csv",
 registry_defects="D-V7"),

dict(comparator_id="CMP-TROPOMI", inventory_name="Sentinel-5P TROPOMI",
 dataset_release="COPERNICUS/S5P/OFFL/L3 daily composites via Google Earth Engine, qa 0.75 upstream; no processor-version or reprocessing baseline is recorded",
 release_token_is_an_api_version="no", retrieval_date="extraction 2026-08-09; retrieval of the underlying archive NOT RECORDED",
 retrieval_date_evidence="outputs/power_tropomi_extraction_manifest.json 'generated'",
 original_url="https://sentinels.copernicus.eu/web/sentinel/missions/sentinel-5p (GEE collection COPERNICUS/S5P/OFFL/L3)",
 gases="NO2 and SO2 column enhancements (NOT a greenhouse gas; XCH4 use is declared future work)",
 period_covered="2020-01-01 to 2026-03-26 per the manifest; docs/sources.md says 2020-2026; validation_catalog says 2019-2024",
 geographical_boundary="0.1 degree feature grid over Pakistan, plant windows r_src 0.15 deg, annulus 0.3-0.7 deg",
 sector_mapping="plant-window enhancements at 1.A.1.a stations", gwp_vintage="not applicable",
 source_coverage="2,275 days, 9 source clusters, 59 plant-window rows",
 shared_inputs_with_pakemis="the plant coordinates the windows are centred on are PakEmis's own (and partly CT-derived), so the windows are not independently placed",
 independence_class="large on the observation, partial on the placement",
 evaluation_purpose="declared " + P4 + " but DELIVERS " + P3 + ": the repo's own limit statement is 'an enhancement locates a plume, not a tonnage; it validates placement and activity presence only'",
 licence=NR, local_snapshot_path="NOT in the repository - external volume /Volumes/Extreme SSD/grid/pakistan/tropomi; the derived table data/sectors/power/activity/tropomi_no2_plants.csv is held",
 local_snapshot_sha256="derived table d56b4a8e1c58a63b511b8af8bfc6fafb174a7f615e56a4f57856f9fc9001b944",
 held="derived table only; the archive is NOT reproducible from this repository",
 used_in="power_tropomi_crosscheck.csv", registry_defects="D-V8"),

dict(comparator_id="CMP-WORLDCOVER", inventory_name="ESA WorldCover",
 dataset_release="ESA WorldCover v200, observation year 2021; class 50 built-up and the cropland class, 34 tiles aggregated 10 m -> 0.05 deg",
 release_token_is_an_api_version="no", retrieval_date=NR,
 retrieval_date_evidence="read over the network at build time via /vsicurl; never archived, so no retrieval event exists",
 original_url="https://esa-worldcover.org/en/data-access", gases="not applicable - land cover",
 period_covered="observation year 2021, used to place FY2015-16 through FY2023-24",
 geographical_boundary="global 10 m raster, clipped to the grid",
 sector_mapping="built-up surface for residential/industry/waste; cropland for soils",
 gwp_vintage="not applicable", source_coverage="global",
 shared_inputs_with_pakemis="this is an INPUT (a spatial proxy), not only a comparator. It carries 15.0% of PakEmis CO2 and 4.8% of CH4 in FY2023-24, with a DECLARED vintage offset of 2-3 years.",
 independence_class="none as an input; large as the OSM mirror comparator", evaluation_purpose=P3,
 licence="CC-BY-4.0",
 local_snapshot_path="source rasters NOT held; derived caches data/shared/gis/proxy_builtup_267x340.npy and data/sectors/agriculture/gis/proxy_cropland_267x340.npy",
 local_snapshot_sha256="builtup a761c64d00f50f33198167ff38f9b1854a221517cbb1bb7294540d9dc82aeccc; cropland 7791ac5d6232996aae585354032df6acc411ce31442868c6559487adc5f26bfe",
 held="derived cache only", used_in="grid cube spatial weights; pakemis_builtup_comparison_adm2.csv",
 registry_defects="no row for WorldCover exists in source_documents.csv or pakemis_source_register.csv; holdings.py worldcover returns 0 in both"),

dict(comparator_id="CMP-SPAM", inventory_name="MapSPAM",
 dataset_release="SPAM 2020 V2r2 global physical area, RICE_A / RICE_I / RICE_R; reference year 2020",
 release_token_is_an_api_version="no", retrieval_date=NR + " (manual browser download; raster mtime approx 2026-08-21)",
 retrieval_date_evidence="none", original_url="https://doi.org/10.7910/DVN/SWPENT (Harvard Dataverse)",
 gases="not applicable - crop physical area", period_covered="reference year 2020",
 geographical_boundary="global 5 arc-min", sector_mapping="rice area for 3.C and the water-regime axis",
 gwp_vintage="not applicable", source_coverage="global",
 shared_inputs_with_pakemis="SPAM is calibrated to national crop statistics, the same lineage as the PBS district panel it is scored against. The repo records this itself: benchmark_tasks.csv spatial_rice_mnfsr says 'agreement is partly self-agreement and the row says so'.",
 independence_class="partial (self-agreement declared); and it is an INPUT, carrying 3.6% of PakEmis CO2",
 evaluation_purpose=P3, licence="CC-BY-4.0 in the sidecar; 'not-established' in data/catalog/assets.csv lines 266-268",
 local_snapshot_path="data/sectors/agriculture/gis/manual/spam_rice.tif + spam2020_V2r2_global_A_RICE_{I,R}.tif",
 local_snapshot_sha256="9b0c0b9ec21cbc73909daf314efb027209a107be7748724484baf4b3655f1240; 370ebfccc51dc5614699f3ff3857b53a2c955ed314c420dd66f39cdd18ea4bbc; 12da6f236a8975d7ca95ac8a322e393915d6bdb5f081f348a8ace4380a2e5d70",
 held="yes", used_in="rice water-regime axis; agri_reference_panel_divergence.csv", registry_defects="D-V6"),

dict(comparator_id="CMP-GLW4", inventory_name="FAO Gridded Livestock of the World 4",
 dataset_release="GLW 4, FAO 2024 release, reference year 2020; EF-weighted CTL/BFL/SHP/GTS",
 release_token_is_an_api_version="no", retrieval_date=NR + " (read over the network at build time)",
 retrieval_date_evidence="none",
 original_url="https://www.fao.org/livestock-systems/global-distributions/en/ ; https://dataverse.harvard.edu/dataverse/glw",
 gases="not applicable - livestock density", period_covered="reference year 2020, used for all nine periods",
 geographical_boundary="global 5 arc-min", sector_mapping="3.A enteric and 3.B manure placement",
 gwp_vintage="not applicable", source_coverage="global",
 shared_inputs_with_pakemis="GLW is itself fitted to national and subnational livestock census statistics - the same PBS lineage. It is an INPUT carrying 69.0% of PakEmis CH4 in FY2023-24 and it is ALSO used as the comparator in geo-livestock-district-glw. That check is substantially self-agreement.",
 independence_class="partial at best; none where it is both input and comparator",
 evaluation_purpose=P3, licence="CC-BY-4.0",
 local_snapshot_path="source rasters NOT held; cache data/shared/gis/proxy_glw_livestock_267x340.npy",
 local_snapshot_sha256="26081e1ef528991dc5d2a562f5fdab071f72174650b44136a8fadc184c9a1b59",
 held="derived cache only", used_in="grid cube CH4 weights; eval/validation/livestock_district_validation.csv",
 registry_defects="docs/sources.md note: the Harvard Dataverse collection is still labelled 2015; cite the FAO 2024 release"),

dict(comparator_id="CMP-OSM", inventory_name="OpenStreetMap via Geofabrik",
 dataset_release="Geofabrik Pakistan extract, snapshot 2026-08-06; 785,749 building footprints and 45,777 road links",
 release_token_is_an_api_version="no", retrieval_date="2026-08-06",
 retrieval_date_evidence="data/shared/gis/PROXY_SOURCES.md and validation_catalog geo-builtup-osm-mirror",
 original_url="https://download.geofabrik.de/ (exact extract URL not recorded)",
 gases="not applicable", period_covered="snapshot 2026-08-06",
 geographical_boundary="national extract", sector_mapping="road density for transport; building fraction as a built-up mirror",
 gwp_vintage="not applicable", source_coverage="crowd-sourced; measures MAPPING EFFORT as much as built area, which the repo states",
 shared_inputs_with_pakemis="road_density is an INPUT carrying the largest single share of PakEmis transport placement; building fraction is a DIAGNOSTIC only, never a stream proxy",
 independence_class="large vs WorldCover (different lineage); none where OSM is the input",
 evaluation_purpose=P3,
 licence="ODbL 1.0 - a DERIVATIVE DATABASE, share-alike. CC-BY cannot be granted over it. This is an open acceptance blocker for the ESS deposit.",
 local_snapshot_path="data/shared/gis/osm_building_fraction_267x340.npy; data/shared/gis/roads/pak_road_density_267x340.npy",
 local_snapshot_sha256="134c45b8efea0a13205f940fbd5b28a5bb9ec225008751337e1fe881d19becc4; 858bf3a1dd184a4d60e129af22e467996ae2f2f6505492b185620a0cceab7c92",
 held="derived rasters only", used_in="pakemis_builtup_comparison_adm2.csv; road weights; ippu_facility_coordinate_agreement.csv",
 registry_defects=""),

dict(comparator_id="CMP-GCD-RICE", inventory_name="GCD-Rice (Global Crop Dataset - Rice)",
 dataset_release="GCD-Rice Pakistan 2023 v1, 30 m classified paddy extent, file Classified-Rice-PAK-2023-v1.tif",
 release_token_is_an_api_version="no", retrieval_date=NR, retrieval_date_evidence="none",
 original_url="https://doi.org/10.57760/sciencedb.21665 (ScienceDB; Nature Scientific Data 2025)",
 gases="not applicable - classified paddy extent",
 period_covered="observation year 2023 - the ONLY own-year spatial comparator in the project",
 geographical_boundary="national 30 m raster", sector_mapping="rice geography for 3.C",
 gwp_vintage="not applicable", source_coverage="approx 88.9% overall accuracy, 258k validation samples",
 shared_inputs_with_pakemis="NONE - a satellite classification independent of both the statistical panel and SPAM. This is the strongest independent spatial comparator held.",
 independence_class="large", evaluation_purpose=P3,
 licence="per ScienceDB record (not transcribed into the repository); the 30 MB raster is not redistributed",
 local_snapshot_path="data/sectors/agriculture/gis/manual/gcd_rice_2023.tif; cache proxy_gcd_rice_267x340.npy",
 local_snapshot_sha256="ebbaf0607145256bc11b6a4af84f9a697915ca1424ea522ff1ce9e350c98f00c; cache 34a4cc45810c07e966fb1dd55abd95a7ab4a116b26407655a9185b13e7f66222",
 held="yes", used_in="pakemis_rice_geography_crosscheck.csv (geography only, never magnitude)",
 registry_defects=""),

dict(comparator_id="CMP-FIRMS", inventory_name="NASA FIRMS active fire",
 dataset_release="VIIRS_SNPP_SP (science-quality archive), 1,664,876 detections",
 release_token_is_an_api_version="no",
 retrieval_date="per fiscal window, Sept-June spans FY2015 through FY2023; exact dates in FIRMS_SOURCES.json windows_fetched",
 retrieval_date_evidence="data/sectors/agriculture/gis/manual/FIRMS_SOURCES.json",
 original_url="https://firms.modaps.eosdis.nasa.gov/ (MAP_KEY is an env var, never committed)",
 gases="not applicable - fire detections", period_covered="2015-09-01 to 2024-06-30, bbox 60.5,23.5,77.5,37.5",
 geographical_boundary="bounding box, wider than the national frame",
 sector_mapping="3.F residue burning timing and placement", gwp_vintage="not applicable",
 source_coverage="detection-limited; cloud and overpass gaps are not corrected",
 shared_inputs_with_pakemis="it is an INPUT to the 3.F timing kernel AND the comparator in tim-agriculture-firms-burning - the validation catalog correctly classes that row independence 'none'",
 independence_class="none where it is the input", evaluation_purpose=P3,
 licence=NR, local_snapshot_path="data/sectors/agriculture/gis/manual/firms_fire.csv",
 local_snapshot_sha256="2d26b95ad76bccc049ccba9ec9fc277143df631728cf08063127966d88079a59",
 held="yes", used_in="monthly_crosschecks.csv; residue burning timing", registry_defects=""),

dict(comparator_id="CMP-WORLDPOP", inventory_name="WorldPop constrained population",
 dataset_release="WorldPop constrained, Pakistan, 1 km, reference year 2020",
 release_token_is_an_api_version="no", retrieval_date=NR, retrieval_date_evidence="none",
 original_url=NR, gases="not applicable", period_covered="reference year 2020, used for all nine periods",
 geographical_boundary="national 1 km raster",
 sector_mapping="population weight for residential and waste", gwp_vintage="not applicable",
 source_coverage="global",
 shared_inputs_with_pakemis="an INPUT carrying 2.3% of PakEmis CO2 and 1.9% of CH4; declared vintage offset of 3-4 years",
 independence_class="none - input only", evaluation_purpose="not applicable (not used as a comparator)",
 licence="CC-BY-4.0",
 local_snapshot_path="data/shared/gis/worldpop_pak_2020_1km.tif; cache proxy_population_267x340.npy",
 local_snapshot_sha256="d24169128fef55cbe288e73887921d11d1384a53e873d234a68e3f8898f7cdbb; cache cd39673c5f913b253b36c5de1745faf94796e504211dac2f4de4fa3bd3ad8320",
 held="yes", used_in="grid cube spatial weights", registry_defects=""),

dict(comparator_id="CMP-ERA5", inventory_name="ECMWF ERA5 reanalysis",
 dataset_release="ERA5 pressure levels and 0.1 degree daily; no reanalysis stream or product version recorded",
 release_token_is_an_api_version="no", retrieval_date=NR + " (aviation route sample mtime approx 2026-08-06)",
 retrieval_date_evidence="none",
 original_url="https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels",
 gases="not applicable - meteorology", period_covered="FY2023-24 route sample; the daily archive is on an external volume",
 geographical_boundary="global reanalysis grid", sector_mapping="degree days for residential; route weather for aviation",
 gwp_vintage="not applicable", source_coverage="global",
 shared_inputs_with_pakemis="none - the inventory's own driver is NASA POWER (MERRA-2), so ERA5 is a genuinely different reanalysis",
 independence_class="large", evaluation_purpose=P3,
 licence=NR, local_snapshot_path="sources/Aviation/ERA5_route_weather_FY2023_24.nc; data/cache/aviation/era5/FY2023_24_pressure_levels_12utc.nc (LFS); the 0.1 deg daily archive is on an EXTERNAL volume",
 local_snapshot_sha256="1576ab63922a5f8af3f561be9ec8323b2e282551a5661e3f2973e973bacc6969",
 held="partially - the degree-day archive is not in the repository",
 used_in="era5_degree_day_crosscheck.csv; aviation_era5_route_weather.csv",
 registry_defects="the memory record for this check is that ERA5 validates TIMING, not degree days, because of an undocumented daily aggregation on the PakEmis side"),

dict(comparator_id="CMP-NASAPOWER", inventory_name="NASA POWER (MERRA-2)",
 dataset_release="NASA POWER monthly T2M; no POWER release version recorded",
 release_token_is_an_api_version="no", retrieval_date=NR, retrieval_date_evidence="none",
 original_url=NR, gases="not applicable", period_covered="monthly, all nine periods",
 geographical_boundary="reanalysis grid sampled to districts",
 sector_mapping="degree days driving residential heating demand", gwp_vintage="not applicable",
 source_coverage="global",
 shared_inputs_with_pakemis="this is the INPUT, not the comparator; ERA5 is the comparator against it",
 independence_class="not applicable - input", evaluation_purpose="not applicable",
 licence=NR, local_snapshot_path="", local_snapshot_sha256="", held="derived degree-day tables only",
 used_in="residential temporal profile", registry_defects=""),

dict(comparator_id="CMP-HTAP3", inventory_name="HTAP v3",
 dataset_release="NOT RECORDED - the value held is DERIVED, not extracted: benchmarks_air.csv states it is back-computed from a percentage quoted in the SANH 2026 paper",
 release_token_is_an_api_version="no", retrieval_date="not applicable - never retrieved",
 retrieval_date_evidence="benchmarks_air.csv derived='yes'", original_url=NR,
 gases="NH3", period_covered="CY2015", geographical_boundary="national, implied",
 sector_mapping="agricultural NH3 total", gwp_vintage="not applicable",
 source_coverage="not held", shared_inputs_with_pakemis="unknown - the dataset was never opened",
 independence_class="unknown - a derived number, not a read dataset",
 evaluation_purpose=P2 + " (weak: this is a quoted percentage inverted, not a comparator reading)",
 licence=NR, local_snapshot_path="", local_snapshot_sha256="", held="no",
 used_in="benchmarks_air.csv NH3 row (1372.5 kt, derived)",
 registry_defects="a DERIVED comparator value presented in the same table as read ones; the derived flag is the only thing separating them"),

dict(comparator_id="CMP-SANH-2026", inventory_name="SANH / Tomlinson et al., ESSD 18:2349 (2026)",
 dataset_release="South Asian NH3 inventory, ESSD 18:2349 (2026), Table 3",
 release_token_is_an_api_version="no", retrieval_date=NR, retrieval_date_evidence="none",
 original_url=NR, gases="NH3", period_covered="CY2015",
 geographical_boundary="South Asia, Pakistan rows",
 sector_mapping="SFA / GRM / MNM / CRB / CRR columns to managed soils, livestock and residue burning",
 gwp_vintage="not applicable", source_coverage="agricultural NH3 only",
 shared_inputs_with_pakemis="partly - a published inventory built on FAO activity",
 independence_class="partial", evaluation_purpose=P2, licence="journal open access, not transcribed",
 local_snapshot_path="", local_snapshot_sha256="", held="values transcribed into benchmarks_air.csv; the paper's data is not held",
 used_in="benchmarks_air.csv NH3 rows; eval/validation/spatial_nh3_validation.json", registry_defects=""),

dict(comparator_id="CMP-CUI-2021", inventory_name="Cui et al. 2021, Nature Food",
 dataset_release="Cui et al. 2021, 1,507-observation cropland N2O field database; figshare deposit",
 release_token_is_an_api_version="no", retrieval_date=NR, retrieval_date_evidence="none",
 original_url="https://doi.org/10.1038/s43016-021-00384-9 ; https://doi.org/10.6084/m9.figshare.14844069",
 gases="N2O", period_covered="field database, quoted at CY2021",
 geographical_boundary="global gridded 5 arc-min; the Pakistani value is MODEL-EXTRAPOLATED with 0 in-country observations",
 sector_mapping="cropland direct N2O, 3.D.1", gwp_vintage="AR5 as applied in benchmarks.csv",
 source_coverage="1,507 field observations, none in Pakistan",
 shared_inputs_with_pakemis="none - an independent empirical EF adjudicator",
 independence_class="large on the factor; the Pakistani value is extrapolated, so it is not an observation of Pakistan",
 evaluation_purpose=P2 + " (an EF adjudicator, not an emissions measurement)",
 licence="open (figshare)", local_snapshot_path="", local_snapshot_sha256="", held="no - a published literature value",
 used_in="national_benchmark_comparison.csv Managed soils diagnostic row", registry_defects=""),

dict(comparator_id="CMP-CCAC-SEI", inventory_name="CCAC / SEI Pakistan PM2.5 assessment",
 dataset_release="NOT RECORDED - no edition, year or document identity in any registry",
 release_token_is_an_api_version="no", retrieval_date=NR, retrieval_date_evidence="none", original_url=NR,
 gases="PM2.5 and the residential GHG estimate bridged from it",
 period_covered="not recorded", geographical_boundary="national",
 sector_mapping="residential solid fuel", gwp_vintage="not recorded",
 source_coverage="not recorded",
 shared_inputs_with_pakemis="likely HIES household fuel data, the same source PakEmis residential reads",
 independence_class="partial", evaluation_purpose=P2,
 licence=NR, local_snapshot_path="", local_snapshot_sha256="", held="no",
 used_in="residential_ccac_bridge_2024.csv (bridged to this release's boundary by named wedges)",
 registry_defects="the least documented comparator in the project: no edition, no URL, no date, no file"),

dict(comparator_id="CMP-PCAA", inventory_name="Pakistan Civil Aviation Authority traffic flows",
 dataset_release="major-traffic-flow-airports-2023-24 and major-traffic-flow-airlines-2023-24",
 release_token_is_an_api_version="no", retrieval_date=NR, retrieval_date_evidence="none",
 original_url="https://pcaawebadmin.pcaa.gov.pk/media/ykumyn4k/major-traffic-flow-airports-2023-24.pdf ; .../ufwmg42i/major-traffic-flow-airlines-2023-24.pdf",
 gases="not applicable - movements, passengers, cargo",
 period_covered="FY2023-24 - a FISCAL year, needing no calendar approximation",
 geographical_boundary="national airports", sector_mapping="1.A.3.a movement control",
 gwp_vintage="not applicable", source_coverage="official, all major airports",
 shared_inputs_with_pakemis="TOTAL - PCAA is the engine's own movement input. The validation catalog correctly records mag-aviation-departures independence as 'none'.",
 independence_class="none - same input on both sides", evaluation_purpose=P1,
 licence=NR, local_snapshot_path="sources/Aviation/major-traffic-flow-{airports,airlines}-2023-24.pdf",
 local_snapshot_sha256="in data/catalog/raw_manifest.csv", held="yes",
 used_in="aviation_departure_control_comparison.csv", registry_defects=""),
]

# closed vocabulary, matching outputs/pakemis_validation_catalog.csv's own terms, so the
# free-text independence_class above stays readable while the file stays machine-usable
CODE = {
 "CMP-EDGAR-2025": "partial", "CMP-EDGAR-2024": "partial", "CMP-EDGAR-AP81": "partial",
 "CMP-EDGAR-GRID-SO2": "partial", "CMP-FAOSTAT-GT": "partial",
 "CMP-FAOSTAT-QCL-RFN": "shared-upstream", "CMP-CT-AGRI": "partial",
 "CMP-CT-AVIATION": "large", "CMP-CT-POWER": "shared-upstream", "CMP-CT-WASTE": "large",
 "CMP-CRT-2022": "partial", "CMP-BTR1": "partial", "CMP-BUR1": "partial",
 "CMP-TNC-2025": "none", "CMP-OECD-AIR": "large", "CMP-GEM-COAL": "partial",
 "CMP-GEM-CEMENT": "large", "CMP-GEM-GOGPT": "partial", "CMP-GEM-BIO": "partial",
 "CMP-WRI-GPPD": "shared-upstream", "CMP-GGFR-FLARE": "large", "CMP-MARS": "large",
 "CMP-TROPOMI": "large", "CMP-WORLDCOVER": "shared-upstream", "CMP-SPAM": "shared-upstream",
 "CMP-GLW4": "shared-upstream", "CMP-OSM": "shared-upstream", "CMP-GCD-RICE": "large",
 "CMP-FIRMS": "shared-upstream", "CMP-WORLDPOP": "not-applicable", "CMP-ERA5": "large",
 "CMP-NASAPOWER": "not-applicable", "CMP-HTAP3": "unknown", "CMP-SANH-2026": "partial",
 "CMP-CUI-2021": "large", "CMP-CCAC-SEI": "partial", "CMP-PCAA": "none",
}
for r in C:
    r["independence_class_code"] = CODE[r["comparator_id"]]

with open(OUT / "comparators.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=COMP_COLS, quoting=csv.QUOTE_ALL)
    w.writeheader()
    for r in C:
        assert set(r) == set(COMP_COLS), set(COMP_COLS) ^ set(r)
        w.writerow(r)
print(f"comparators.csv: {len(C)} rows")


# ---------------------------------------------------------------- matched_comparison.csv
MC_COLS = [
    "comparison_id", "comparator_id", "comparator", "comparator_release",
    "category", "gas", "basis", "unit",
    "pakemis_value", "comparator_value", "absolute_diff", "relative_diff_pct",
    "pakemis_period", "comparator_period", "period_approximation",
    "boundary", "gwp_vintage_pakemis", "gwp_vintage_comparator",
    "harmonization", "exclusions", "shared_inputs", "independence_class_code",
    "evaluation_purpose", "interpretation", "source_product",
]

ROWS = []
def add(**kw):
    kw.setdefault("comparator_release", "")
    if kw.get("pakemis_value") not in ("", None) and kw.get("comparator_value") not in ("", None):
        pv, cv = float(kw["pakemis_value"]), float(kw["comparator_value"])
        kw["absolute_diff"] = round(pv - cv, 4)
        kw["relative_diff_pct"] = round(100.0 * (pv - cv) / cv, 2) if cv else ""
    else:
        kw.setdefault("absolute_diff", "")
        kw.setdefault("relative_diff_pct", "")
    for c in MC_COLS:
        kw.setdefault(c, "")
    for k in kw:
        assert k in MC_COLS, k
    ROWS.append(kw)

FY = "FY2023-24 (1 Jul 2023 - 30 Jun 2024)"
NOBLEND = ("NO BLEND APPLIED. A fiscal year is compared directly against one calendar year, "
           "which overlaps it by six months. The release's transport and industry rows DO apply "
           "0.5*CY(Y-1)+0.5*CY(Y); this row does not, and the inconsistency is the release's, not this file's.")
SHARED_FAO = ("HIGH: FAOSTAT's Pakistan livestock heads and crop areas are Pakistan's own reported "
              "statistics, the same PBS/MNFSR lineage PakEmis reads. Agreement here is an EMISSION "
              "FACTOR comparison, not an independent check of the activity.")
SHARED_CT = ("Climate TRACE's Pakistani agricultural activity anchors on FAO/national statistics, the "
             "same lineage. Its 'observation-driven' label does not extend to Pakistani agriculture.")
INV_AR5 = ("NATIVE-GAS RECOMPUTATION: the comparator publishes CO2e only in the held extract, so its "
           "native mass is recovered by dividing by the GWP it declares (AR5: CH4 28 non-fossil, N2O 265). "
           "The inversion is exact ONLY because this category is single-gas. PakEmis's side is read "
           "natively from outputs/pakemis_source_streams.csv; no GWP touches it.")
INV_AR6 = ("NATIVE-GAS RECOMPUTATION, WITH AN ASSUMPTION: Climate TRACE publishes CO2e at AR6 in the held "
           "benchmark row, and the native-gas rows its API serves were NOT retained. The inversion assumes "
           "AR6 non-fossil CH4 = 27 (N2O = 273). If CT applied the fossil value 29.8 the CH4 native mass "
           "falls about 9.4% and this row's gap narrows correspondingly. THE FIX IS TO RE-PULL CLIMATE "
           "TRACE AT NATIVE GAS, not to refine the inversion.")

# --- native-gas rows, FAOSTAT (AR5, single-gas categories only)
for cid, cat, gas, bcat, g in [
    ("MC-01", "Enteric fermentation", "CH4", "Enteric fermentation", AR5["CH4_bio"]),
    ("MC-02", "Rice cultivation", "CH4", "Rice cultivation", AR5["CH4_bio"]),
    ("MC-03", "Agricultural soils", "N2O", "Managed soils", AR5["N2O"]),
]:
    add(comparison_id=cid, comparator_id="CMP-FAOSTAT-GT", comparator="FAOSTAT Emissions Totals",
        comparator_release="domain GT, Pakistan area 165, element 723113 (no FAOSTAT release date recorded)",
        category=cat, gas=gas, basis="NATIVE GAS", unit="Gg " + gas,
        pakemis_value=round(PK[(cat, gas)], 4),
        comparator_value=round(bm("FAOSTAT", bcat, 2023) * 1000.0 / g, 4),
        pakemis_period=FY, comparator_period="CY2023", period_approximation=NOBLEND,
        boundary="national both sides; FAOSTAT area 165 vs the geoBoundaries frame including GB/AJK - not reconciled",
        gwp_vintage_pakemis="none applied (native)", gwp_vintage_comparator="AR5, inverted out",
        harmonization=INV_AR5, exclusions="none for this category",
        shared_inputs=SHARED_FAO, independence_class_code="partial",
        evaluation_purpose=P2, source_product="data/shared/evidence/benchmarks.csv; outputs/pakemis_source_streams.csv")

ROWS[-3]["interpretation"] = ("PakEmis enteric CH4 is 4.5% above FAOSTAT. Because both sides use Pakistan's own "
    "herd statistics, this 4.5% is a difference in emission factor and herd composition, not in activity. It is "
    "NOT independent corroboration of the national total.")
ROWS[-2]["interpretation"] = ("PakEmis rice CH4 is 15.7% above FAOSTAT on shared area statistics, so the gap is "
    "water regime and scaling factors. Note FAOSTAT rice area is PADDY; a prior defect in this repo came from "
    "treating it as milled.")
ROWS[-1]["interpretation"] = ("PakEmis soil N2O is HALF of FAOSTAT. The release names the mechanism and it is not "
    "an error on either side: FAOSTAT applies the 2006 aggregate EF1 0.01 / EF3PRP 0.02, PakEmis the 2019 "
    "disaggregated dry values 0.005 / 0.002. At EF1 = 0.010 PakEmis soils reach about 40 Mt CO2e. This is a "
    "METHOD divergence, and quoting it as an accuracy gap would be wrong.")

# --- native-gas rows, Climate TRACE (AR6 inverted, with the assumption stated)
for cid, cat, gas, bcat, g in [
    ("MC-04", "Enteric fermentation", "CH4", "Enteric fermentation", AR6["CH4_bio"]),
    ("MC-05", "Rice cultivation", "CH4", "Rice cultivation", AR6["CH4_bio"]),
    ("MC-06", "Agricultural soils", "N2O", "Managed soils", AR6["N2O"]),
]:
    add(comparison_id=cid, comparator_id="CMP-CT-AGRI", comparator="Climate TRACE",
        comparator_release="UNRECORDED - 'v7' is the API path, not a dataset release; the extract is not held",
        category=cat, gas=gas, basis="NATIVE GAS (inverted, assumption-dependent)", unit="Gg " + gas,
        pakemis_value=round(PK[(cat, gas)], 4),
        comparator_value=round(bm("Climate TRACE", bcat, 2024) * 1000.0 / g, 4),
        pakemis_period=FY, comparator_period="CY2024", period_approximation=NOBLEND,
        boundary="national both sides; Climate TRACE country mask, not reconciled against the frame",
        gwp_vintage_pakemis="none applied (native)", gwp_vintage_comparator="AR6, inverted out",
        harmonization=INV_AR6,
        exclusions="CT routes manure-to-soils and manure-on-pasture into its soils line, so its enteric and manure lines are not the IPCC split",
        shared_inputs=SHARED_CT, independence_class_code="partial",
        evaluation_purpose=P2, source_product="data/shared/evidence/benchmarks.csv")

ROWS[-3]["interpretation"] = ("PakEmis enteric CH4 is about 20% BELOW Climate TRACE, while being 4.5% ABOVE "
    "FAOSTAT on the same herd. Two comparators disagreeing by 25% among themselves bound the factor, not PakEmis. "
    "The comparator value here is also the least reproducible in the whole file: no held extract, no digest, no "
    "dataset release.")
ROWS[-2]["interpretation"] = ("PakEmis rice CH4 is about twice Climate TRACE and 16% above FAOSTAT. CT is the "
    "outlier against both; the release flags this as a genuine divergence in CT's area/water assumptions.")
ROWS[-1]["interpretation"] = ("Agreement to 0.4% - and it means little. The two routes differ in method and in "
    "GWP, agree here, and disagree with FAOSTAT by a factor of two on the same quantity. Close agreement with ONE "
    "comparator while a second differs twofold is not evidence of accuracy.")

# --- a genuinely GWP-invariant native row
add(comparison_id="MC-07", comparator_id="CMP-CT-AGRI", comparator="Climate TRACE",
    comparator_release="UNRECORDED (API path v7)", category="Urea application", gas="CO2",
    basis="NATIVE GAS (GWP-invariant on both sides)", unit="Gg CO2",
    pakemis_value=round(PK[("Urea application", "CO2")], 4),
    comparator_value=round(bm("Climate TRACE", "Urea application", 2024) * 1000.0, 4),
    pakemis_period=FY, comparator_period="CY2024", period_approximation=NOBLEND,
    boundary="national both sides",
    gwp_vintage_pakemis="not applicable (CO2)", gwp_vintage_comparator="not applicable (CO2)",
    harmonization="NONE NEEDED. Climate TRACE reports this line as pure CO2, so the comparison is native on both sides with no GWP assumption at all. This is the only agricultural row in the file free of a GWP inversion.",
    exclusions="PakEmis's 3.H also carries liming; CT's line is urea only",
    shared_inputs="both rest on fertiliser offtake statistics of the same NFDC lineage",
    independence_class_code="partial", evaluation_purpose=P2,
    interpretation="5.4% apart with no GWP assumption between them. This is the cleanest comparison in the table and it is a small category.",
    source_product="data/shared/evidence/benchmarks.csv")

# --- CO2e rows carried forward with the missing columns supplied
CO2E = [
 ("MC-08","CMP-FAOSTAT-GT","FAOSTAT","Manure management",2023,"CH4+N2O","partial",
  "NOT separable natively: the held FAOSTAT extract is CO2e only and this category mixes CH4 and N2O, so the inversion is not exact. The comparison stays in CO2e and says so.",
  "PakEmis includes indirect volatilisation; FAOSTAT's manure line does not.",SHARED_FAO,
  "45% above FAOSTAT, with a named scope difference that accounts for part of it. Not resolvable further without FAOSTAT's own gas split, which the held extract does not carry."),
 ("MC-09","CMP-FAOSTAT-GT","FAOSTAT","Field burning of residues",2023,"CH4+N2O","partial",
  "CO2e, not separable (two gases).","PakEmis routes crop-residue N2O to managed soils; FAOSTAT does not.",SHARED_FAO,
  "12% below FAOSTAT on a 0.7 Mt category. Materially irrelevant to the national total and included only so the agriculture set is complete."),
 ("MC-10","CMP-EDGAR-2025","EDGAR","Electricity and heat production",2024,"CO2+CH4+N2O","partial",
  "CO2e both sides, AR5 both sides, no inversion attempted: the category is CO2-dominated but not single-gas.",
  "PakEmis 1.A.1.a excludes captive and industrial self-generation, which NEPRA's scope excludes; EDGAR's Power Industry may include some.",
  "EDGAR's Pakistani power activity derives from IEA energy balances built on the same national submissions PakEmis reads. A 2% agreement on shared activity is close to arithmetic.",
  "The closest taxonomy match in the whole comparison, and the least independent. 1.02x. The residual is plausibly captive self-generation that both sides handle differently."),
 ("MC-11","CMP-EDGAR-2025","EDGAR","Residential fuel combustion",2024,"CO2+CH4+N2O","coverage",
  "CO2e both sides, AR5 both sides.",
  "PakEmis covers HOUSEHOLDS ONLY. Commercial and institutional buildings are not estimated. The gap is therefore expected and is a COVERAGE measure, not an accuracy measure.",
  "both rest on OGRA/HIES fuel supply of shared lineage",
  "0.94x under configuration L. Reading this as 6% accuracy would be wrong: the inventory omits a category EDGAR includes, so the comparison bounds the omission, not the error in what IS included."),
 ("MC-12","CMP-EDGAR-2025","EDGAR","waste",2023,"CH4+N2O","partial",
  "CO2e both sides, AR5 both sides, YEAR-MATCHED to EDGAR's CY2023 column (the CY2024 row is kept separately for release-vintage context and is NOT the benchmark).",
  "none declared","no shared activity identified; EDGAR's waste activity is modelled from population and income",
  "PakEmis is 143% of EDGAR, having been 48% before domestic wastewater was built. The row changed sides when a category was added, which is exactly what a coverage-sensitive comparator should do."),
 ("MC-13","CMP-EDGAR-2025","EDGAR","Fugitive emissions from oil and gas",2024,"CO2+CH4","diagnostic",
  "CO2e both sides, AR5 both sides.",
  "PakEmis's IPCC 2019 segment account spans production, gathering, processing, transmission, distribution, refining and post-meter; EDGAR's aggregate is labelled fuel exploitation and the segment boundaries are not matched.",
  "none identified",
  "1.41x on a broadly related but unmatched scope. Treat as an external model benchmark, never a calibration target - the release says so explicitly."),
 ("MC-14","CMP-EDGAR-2025","EDGAR","1A2 (all estimated)",2024,"CO2+CH4+N2O","coverage",
  "CO2e both sides, AR5 both sides.",
  "The largest single coverage gap in the inventory. Cement kiln fuel behind the clinker route is not priced; petcoke and bagasse are not priced.",
  "PakEmis's solid fuels here ARE the official HDIP coal-by-consumer allocation, which is itself under reconciliation; EDGAR's industrial activity shares the IEA/HDIP lineage.",
  "0.64x, and it is a COVERAGE statement. An omitted category is never evidence about the accuracy of the included ones, and this row must not be averaged into any accuracy claim."),
 ("MC-15","CMP-EDGAR-2025","EDGAR","NATIONAL",2024,"CO2+CH4+N2O","coverage",
  "CO2e both sides, AR5 both sides; F-gases excluded on BOTH sides (EDGAR reports 11.54 Mt separately, PakEmis does not estimate them); LULUCF excluded on both sides.",
  "F-gases, LULUCF, lime 2.A.2, commercial/institutional buildings.",
  "energy activity largely shared via IEA/HDIP; agriculture activity shared via FAO lineage",
  "PakEmis reports 91% of EDGAR's national total. The difference is CONCENTRATED in non-gas industrial combustion, F-gases and agriculture, not spread evenly, so the 9% is a coverage composition and not a uniform bias."),
]
for cid, cmp_id, cmp_name, cat, yr, gasscope, role, harm, excl, shared, interp in CO2E:
    add(comparison_id=cid, comparator_id=cmp_id, comparator=cmp_name,
        comparator_release=("EDGAR 2025 GHG booklet" if cmp_name == "EDGAR" else "domain GT, Pakistan area 165"),
        category=cat, gas=gasscope, basis="CO2e (native not feasible from the held extract)", unit="Mt CO2e AR5",
        pakemis_value=eng(cmp_name, cat, yr), comparator_value=bm(cmp_name, cat, yr),
        pakemis_period=FY, comparator_period=f"CY{yr}", period_approximation=NOBLEND,
        boundary="national both sides; comparator country masks not reconciled against the geoBoundaries frame incl. GB/AJK",
        gwp_vintage_pakemis="AR5", gwp_vintage_comparator="AR5",
        harmonization=harm, exclusions=excl, shared_inputs=shared,
        independence_class_code=("partial" if role != "coverage" else "partial"),
        evaluation_purpose=P2 + (" - COVERAGE, not accuracy" if role == "coverage" else ""),
        interpretation=interp, source_product="outputs/national_benchmark_comparison.csv")

# --- transport: the ONE row where a fiscal blend IS applied
add(comparison_id="MC-16", comparator_id="CMP-EDGAR-2025", comparator="EDGAR",
    comparator_release="EDGAR 2025 GHG booklet", category="transport (road residual + railways + domestic aviation)",
    gas="CO2+CH4+N2O", basis="CO2e", unit="Mt CO2e AR5",
    pakemis_value=40.889, comparator_value=48.13,
    pakemis_period=FY, comparator_period="0.5*CY2023 (47.500) + 0.5*CY2024 (48.760)",
    period_approximation=("A BLEND IS APPLIED HERE and nowhere else in this table. The fiscal year overlaps each "
        "calendar year by six months, so the blend is the closest annual approximation available - but it is an "
        "APPROXIMATION, not a fiscal-year comparator value, and it assumes activity is uniform within each calendar year."),
    boundary="scope-matched construction: EDGAR's transport row against road residual + railways + domestic aviation ONLY",
    gwp_vintage_pakemis="AR5", gwp_vintage_comparator="AR5",
    harmonization="The PakEmis side is rebuilt to EDGAR's transport scope rather than taking the module total. International aviation is excluded on both sides.",
    exclusions="international bunkers; navigation",
    shared_inputs="OCAC road-fuel sales lineage is shared with the IEA balances EDGAR rests on",
    independence_class_code="partial", evaluation_purpose=P2,
    interpretation=("0.85x against the blend. The release suppresses the ratio on its unmatched transport rows "
        "(ratio_permitted = false) precisely so unlike transport modules are not compared; only this scope-matched "
        "construction carries a ratio, and that discipline is correct."),
    source_product="outputs/national_edgar_transport_comparison.csv")

# --- coverage totals
for cid, cmp_id, cmp_name, yr, gw in [("MC-17","CMP-FAOSTAT-GT","FAOSTAT",2023,"AR5"),
                                      ("MC-18","CMP-CT-AGRI","Climate TRACE",2024,"AR6")]:
    add(comparison_id=cid, comparator_id=cmp_id, comparator=cmp_name,
        comparator_release=("domain GT" if cmp_name=="FAOSTAT" else "UNRECORDED (API path v7)"),
        category="Agriculture TOTAL", gas="CH4+N2O(+CO2)", basis="CO2e", unit=f"Mt CO2e {gw}",
        pakemis_value=eng(cmp_name,"TOTAL",yr), comparator_value=bm(cmp_name,"TOTAL",yr),
        pakemis_period=FY, comparator_period=f"CY{yr}", period_approximation=NOBLEND,
        boundary="farm-gate aggregate; PakEmis's module also carries urea and lime CO2 that the farm-gate definition excludes",
        gwp_vintage_pakemis=gw, gwp_vintage_comparator=gw,
        harmonization=f"both sides at {gw}; the PakEmis side is re-aggregated at the comparator's GWP vintage",
        exclusions="scope differs in both directions; this is a COVERAGE row",
        shared_inputs=(SHARED_FAO if cmp_name=="FAOSTAT" else SHARED_CT),
        independence_class_code="partial", evaluation_purpose=P2 + " - COVERAGE, not accuracy",
        interpretation=("0.96x FAOSTAT and 0.83x Climate TRACE. Climate TRACE and EDGAR both land near 261 Mt while "
            "FAOSTAT is 233 and PakEmis 223. The two higher comparators are not independent of each other on enteric "
            "CH4, so 'two sources agree' is weaker evidence than it looks."),
        source_product="outputs/national_benchmark_comparison.csv")

add(comparison_id="MC-19", comparator_id="CMP-CUI-2021", comparator="Cui et al. 2021 Nature Food",
    comparator_release="1,507-observation field database, figshare deposit",
    category="Agricultural soils", gas="N2O", basis="CO2e", unit="Mt CO2e AR5",
    pakemis_value=eng("Cui 2021","Managed soils",2021), comparator_value=bm("Cui 2021","Managed soils",2021),
    pakemis_period=FY, comparator_period="CY2021 (a field database, not an annual inventory)",
    period_approximation="The comparator has no meaningful year: it is an EF database applied to an activity year. The CY2021 label is the publication year.",
    boundary="global model extrapolated to Pakistan with ZERO in-country observations",
    gwp_vintage_pakemis="AR5", gwp_vintage_comparator="AR5",
    harmonization="the empirical crop-weighted EF is applied to PakEmis's own activity",
    exclusions="indirect N2O",
    shared_inputs="activity is PakEmis's own; only the factor comes from Cui",
    independence_class_code="large", evaluation_purpose=P2 + " - an EF adjudicator, NOT an emissions measurement",
    interpretation=("0.96x. This is the row that adjudicates MC-03: an empirical field database puts the Pakistani "
        "crop-weighted EF near 0.0055, supporting PakEmis's arid 0.005 over FAOSTAT's flat 0.010. But the Pakistani "
        "value is MODEL-EXTRAPOLATED from zero in-country observations, so it is a weak adjudicator and must not be "
        "called an observation of Pakistan."),
    source_product="outputs/national_benchmark_comparison.csv")

add(comparison_id="MC-20", comparator_id="CMP-CRT-2022", comparator="Pakistan UNFCCC CRT",
    comparator_release="Pakistan 2024 CRT, inventory year CY2022",
    category="Ammonia production", gas="CO2", basis="NATIVE GAS", unit="Gg CO2",
    pakemis_value="", comparator_value=round(bm("Pakistan 2022 CRT","Ammonia production",2022)*1000.0,1),
    pakemis_period="not estimated for CY2022", comparator_period="CY2022",
    period_approximation="no PakEmis value exists for the comparator's period, so NO difference is computed and none should be inferred",
    boundary="national", gwp_vintage_pakemis="not applicable", gwp_vintage_comparator="native CO2, no GWP",
    harmonization="none - native CO2 on the comparator side; the PakEmis side is absent",
    exclusions="PakEmis's own ammonia series is FY-based and starts elsewhere",
    shared_inputs="the CRT is Pakistan's own account on the same national statistics",
    independence_class_code="partial",
    evaluation_purpose=P2 + " - RED-FLAGGED COMPARATOR",
    interpretation=("COMPARATOR ONLY, AND THE COMPARATOR LOOKS WRONG. The CRT's reported ammonia activity would need "
        "about 1,240 MMCFD of gas at the IPCC 37.5 GJ/t requirement, while the whole fertiliser sector drew 756 "
        "(OGRA FY2023-24) to about 770 (NFDC FY2024-25). The recovery term implies 6,442 kt urea, which IS consistent "
        "with NFDC production, so the suspect leg is the activity. A disagreement with this cell is evidence about "
        "the CRT, not about PakEmis."),
    source_product="outputs/ippu_ammonia_activity_reconciliation.csv")

# --- air-pollutant rows (not GHG, kept because the release uses them as evidence)
rail = pd.read_csv(REPO / "outputs/railways_air_pollutants_2024.csv", comment="#")
RAIL = rail.groupby("pollutant").emissions_kt.sum()
for cid, poll, yr, interp in [
    ("MC-21","NOx",2022,"EDGAR is 2.3x this inventory's EMEP Tier 1 railway NOx at comparable years - a disagreement in the factor basis on shared diesel activity."),
    ("MC-22","PM2.5",2022,"EDGAR is TWENTY-EIGHT TIMES this inventory's EMEP Tier 1 railway PM2.5. A factor of 28 is not a calibration signal; it says one side's factor basis is wrong, and the release records it as unresolved rather than moving toward EDGAR."),
]:
    q = bair[(bair.pollutant==poll)&(bair.engine_scope=="Railways")&(bair.year==yr)]
    assert len(q)==1
    add(comparison_id=cid, comparator_id="CMP-EDGAR-AP81", comparator="EDGAR v8.1 AP",
        comparator_release="EDGAR v8.1 FT2022 AP (August 2024)",
        category="Railways 1.A.3.c", gas=poll, basis="NATIVE POLLUTANT MASS", unit="kt " + poll,
        pakemis_value=round(float(RAIL[poll]), 4), comparator_value=float(q.value_kt.iloc[0]),
        pakemis_period=FY, comparator_period=f"CY{yr}", period_approximation=NOBLEND,
        boundary="national; PakEmis side is traction + non-traction + furnace oil COMBUSTION only, wear PM excluded (as the release's own note intends)",
        gwp_vintage_pakemis="not applicable", gwp_vintage_comparator="not applicable",
        harmonization="native pollutant mass both sides, no GWP anywhere",
        exclusions="NOT A GREENHOUSE GAS. Carried here only because the release uses it as evidence; it must never stand in for a GHG comparison.",
        shared_inputs="rail diesel activity of shared lineage (Pakistan Railways Year Book / OCAC)",
        independence_class_code="partial", evaluation_purpose=P2,
        interpretation=interp, source_product="data/shared/evidence/benchmarks_air.csv")

add(comparison_id="MC-23", comparator_id="CMP-CT-POWER", comparator="Climate TRACE power assets",
    comparator_release="UNRECORDED; the held file came from api.climatetrace.org/v6 per the README while the catalog calls it v7",
    category="Power stations, asset level", gas="CO2e", basis="CO2e", unit="t CO2e per plant",
    pakemis_value="", comparator_value="",
    pakemis_period=FY, comparator_period="CY2023 generation",
    period_approximation="asset-level, year-matched only approximately",
    boundary="point assets", gwp_vintage_pakemis="AR5", gwp_vintage_comparator="unstated in the held file",
    harmonization="none applied - the comparison is plant-by-plant ratios",
    exclusions="plants Climate TRACE types differently from the ledger (e.g. Hubco typed coal where the plant is RFO)",
    shared_inputs=("CIRCULAR. 29 of the 52 plant coordinates PakEmis uses come from Climate TRACE itself "
        "(13 climatetrace-only + 16 climatetrace+wri_gppd). Using CT to check those locations is self-agreement."),
    independence_class_code="shared-upstream",
    evaluation_purpose=P3 + " - but DEGRADED to a self-check for 29 of 52 plants",
    interpretation=("TWO DEFECTS MAKE THIS UNUSABLE AS A MAGNITUDE BENCHMARK. (1) Climate TRACE applies a SINGLE "
        "intensity of 2431 g CO2e/kWh to all 14 Pakistani coal plants, so its coal CO2 carries no plant-specific "
        "information and the comparison tests generation data only. (2) 2431 g/kWh is roughly 2.5x any coal "
        "technology's plausible intensity. Plant ratios trace_over_engine therefore range 1.51 to 9.89 without "
        "telling us which side is wrong. The validation catalog labels this row independence 'partial'; on the "
        "evidence it is 'shared-upstream' for location and uninformative for magnitude."),
    source_product="outputs/power_climatetrace_plants_fy2023_24.csv")

with open(OUT / "matched_comparison.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=MC_COLS, quoting=csv.QUOTE_ALL)
    w.writeheader()
    for r in ROWS:
        w.writerow({c: r[c] for c in MC_COLS})
print(f"matched_comparison.csv: {len(ROWS)} rows")


# ---------------------------------------------------------------- comparator_defects.csv
D_COLS = ["defect_id", "severity", "where", "what", "evidence", "consequence", "suggested_fix", "found_by"]
D = [
("D-V1","high","data/shared/evidence/benchmarks.csv; data/catalog/source_documents.csv; every Climate TRACE row",
 "Climate TRACE is registered by its API PATH, not by a dataset release. 'v7' is the URL segment https://api.climatetrace.org/v7. No held payload carries a dataset version field; sources/ClimateTRACE/climatetrace_waste_PAK_SUMMARY.json records only \"api\": \"https://api.climatetrace.org/v7\". A single free-text note says 'v7.1.9 where the note says so', which is not a per-row field.",
 "sources/ClimateTRACE/climatetrace_waste_PAK_SUMMARY.json; sources/Power Plants/README.md; benchmarks.csv benchmark_release column",
 "The six Climate TRACE agriculture rows in national_benchmark_comparison.csv cannot be reproduced: no dataset release, no retrieval date, no held file, no digest. Climate TRACE restates history between releases, so the comparison is not re-runnable and a future disagreement cannot be attributed.",
 "Record the release the API reports in its own metadata, retain the country-by-subsector payload with a digest, and pull the NATIVE-GAS rows the API already serves so the CO2e inversion in MC-04..MC-06 becomes unnecessary.",
 "T-VAL-1"),
("D-V2","medium","sources/Power Plants/README.md vs data/catalog/source_documents.csv row 116",
 "The same file (sha256 52637aa4...) is called 'Climate TRACE v7 power assets' by the catalog and 'Climate TRACE v6 API' by the README, which records the call as api.climatetrace.org/v6/assets.",
 "grep -n v6 'sources/Power Plants/README.md' lines 9 and 13",
 "The power asset snapshot came from a DIFFERENT API generation than the aviation and waste snapshots, and nothing in the registry says so.",
 "Record the actual endpoint per file.","T-VAL-1"),
("D-V3","medium","data/sectors/{aviation,ippu}/metadata/source_manifest.csv vs data/catalog/public_documents.csv and source_documents.csv row 29",
 "One CRT zip (sha256 afba70d1...) carries two different UNFCCC document URLs: 655653 in the sector manifests, 645241 in the catalog. 645241 is the BTR1's own record.",
 "the four files named","A reader following the catalog URL lands on the BTR1, not the CRT.",
 "Pick the correct record and make the other a cross-reference.","T-VAL-1"),
("D-V4","medium","data/catalog/raw_manifest.csv, every data/raw/** row",
 "Each row points at 'data/manifests/source_manifest.csv', a path that does not exist; the curated manifests are at data/catalog/manifests/. That file covers apcma, fao_crop_calendar, ipcc, nfdc, ocac, ogra and pbs only - there is no EDGAR, GEM, FAOSTAT, land, emep or epa_ap42 row.",
 "data/catalog/raw_manifest.csv note column; ls data/manifests",
 "For the comparator families this registry covers, retrieved_at_utc, source_url, coverage and licence are unpopulated everywhere, and the pointer that would have said so is dangling.",
 "Fix the path and add the missing families.","T-VAL-1 (reported by the metadata sweep)"),
("D-V5","medium","data/catalog/not_retained_register.csv vs data/catalog/raw_manifest.csv + data/raw/ACQUISITION_LOG_faostat_soils.csv",
 "The catalog layer states FAOSTAT Emissions Totals was not retained and has no hash, while the raw manifest and the acquisition log show a held, hashed Pakistan extract acquired 2026-09-30 (30d22433..., 10,152 rows).",
 "the three files named","The benchmark rows still read the unhashed 2026-07-01 CO2e extract while a hashed native-gas-capable bulk sits beside it unused.",
 "Point the agriculture benchmarks at the held bulk and recover the native-gas columns, which would convert MC-01..MC-03 from an inversion to a direct read.","T-VAL-1"),
("D-V6","medium","data/catalog/source_documents.csv; outputs/pakemis_source_register.csv; data/catalog/assets.csv",
 "Licence status is inconsistent for the same publisher and sometimes inside one cell: EDGAR GHG booklet cc-by-4.0 but EDGAR v8.1 AP 'not-established'; UNFCCC 'unfccc-public' in public_documents.csv but 'undetermined' in source_documents rows 35/148/160; GEM CC-BY-4.0 in sources/GEM/GEM_SOURCES.json but 'undetermined' in source_documents rows 69 and 121, whose own note reads '(CC BY 4.0)'; SPAM CC-BY-4.0 in RICE_SOURCES.json but 'not-established' in assets.csv lines 266-268.",
 "the files named",
 "The per-product licence inventory is one of the four declared acceptance blockers; these contradictions are why it cannot be closed mechanically.",
 "Resolve to one value per publisher-product and test it.","T-VAL-1 (reported by the metadata sweep)"),
("D-V7","low","outputs/pakemis_validation_catalog.csv row geo-fugitives-mars",
 "The row declares period 2021-2024; the held extract's own tile_date column runs 2023-02-03 to 2026-06-30.",
 "data/sectors/fugitives/activity/mars_plumes_pak.csv tile_date","The declared comparator period does not describe the data used.",
 "Derive the period from the extract.","T-VAL-1 (reported by the metadata sweep)"),
("D-V8","low","outputs/power_tropomi_extraction_manifest.json vs docs/sources.md vs pakemis_validation_catalog.csv",
 "Three mutually inconsistent TROPOMI periods: manifest 2020-01-01 to 2026-03-26, docs 2020-2026, validation catalog '2019-2024 composites'.",
 "the three files","A reader cannot say which days the enhancement rows rest on.",
 "Derive from the manifest.","T-VAL-1 (reported by the metadata sweep)"),
("D-V9","low","outputs/pakemis_validation_catalog.csv rows geo-ippu-two-registers and geo-power-gem-census",
 "Both declare a 'GEM 2024 snapshot / 2024 vintage' while sources/GEM/GEM_SOURCES.json and source_documents.csv record July 2026 and August 2026 trackers.",
 "the files named","The declared comparator vintage is two years older than the file actually used.",
 "Carry the tracker's own version string.","T-VAL-1 (reported by the metadata sweep)"),
("D-V10","low","docs/sources.md line 40",
 "Still registers the comparator as 'EDGAR (EDGAR_2024_GHG)', 'to ~2021', URL dataset_ghg2024, while the evidence layer uses the 2025 booklet to CY2024.",
 "docs/sources.md vs benchmarks.csv","The documentation layer names a different comparator release from the one the numbers come from.",
 "Regenerate or correct the row.","T-VAL-1 (reported by the metadata sweep)"),
("D-V11","high","outputs/pakemis_validation_catalog.csv row geo-power-climatetrace (independence_class 'partial')",
 "The row treats Climate TRACE as a partially independent check on plant GEOGRAPHY, but 29 of the 52 coordinates in data/sectors/power/activity/plant_coordinates.csv are themselves Climate TRACE derived (sources column: 13 'climatetrace', 16 'climatetrace+wri_gppd'). For those plants the check is circular.",
 "value_counts of plant_coordinates.csv sources: wri_gppd 23, climatetrace+wri_gppd 16, climatetrace 13",
 "56% of the stations are checked against their own source. Agreement there is self-agreement and carries no evidence.",
 "Reclass to shared-upstream, and restrict the independent location claim to the 23 wri_gppd-only plants.",
 "T-VAL-1"),
("D-V12","medium","outputs/national_benchmark_comparison.csv (the engine_period / benchmark_period pair)",
 "The fiscal-to-calendar approximation is applied inconsistently and is buried in free text. Most rows match FY2023-24 directly against a single CY2023 or CY2024 column with no blend; the transport and industry comparisons apply an explicit 0.5*CY(Y-1)+0.5*CY(Y) blend. The file has no column that states which treatment a row used.",
 "national_benchmark_comparison.csv vs national_edgar_transport_comparison.csv and pakemis_industry_edgar_divergence.csv",
 "A six-month overlap is silently treated as a year match in most rows. The size of that approximation is not stated anywhere a reader can see it.",
 "Add a period_approximation column with a closed vocabulary (direct | blend | fiscal-native) - matched_comparison.csv here carries one as a worked example.",
 "T-VAL-1"),
("D-V13","high","outputs/power_climatetrace_plants_fy2023_24.csv",
 "Climate TRACE applies ONE intensity, 2431 g CO2e/kWh, to all 14 Pakistani coal plants (trace_g_per_kwh has exactly one distinct value for asset_type 'coal'). The gas classes are near-constant too. So CT's Pakistani power CO2 is activity x a per-fuel-class constant and carries no plant-specific intensity information. 2431 g/kWh is also roughly 2.5x any coal technology's plausible intensity.",
 "groupby asset_type on trace_g_per_kwh: coal nunique=1, value 2431.0",
 "Plant-level ratios trace_over_engine (1.51 to 9.89) are being read as a magnitude benchmark when the comparator can only test generation data. Any move toward this comparator would import a constant.",
 "State the constant-intensity limit on the product and stop quoting plant ratios as a magnitude check.",
 "T-VAL-1"),
("D-V14","medium","data/sectors/power/activity/coal_plant_coordinates.csv, gem_district column",
 "GEM assigns Engro Powergen Thar (24.8125 N, 70.3941 E), ThalNova (24.8155, 70.3884) and Thar Energy (24.8062, 70.4005) to district 'Thatta'. Those coordinates are in Tharparkar; Thatta is about 300 km west. Thar Coal Block-I, 11 km away, is correctly given as Tharparkar.",
 "the file's own gem_district and coordinate columns",
 "A comparator's district field disagrees with its own coordinates. Directly relevant to T-VAL-2's seven station conflicts.",
 "Use the coordinate, not GEM's district label, and record the conflict.","T-FIG-1 (found while reading the grid's peak cell)"),
("D-V15","medium","outputs/pakemis_stream_support_ledger.csv and pakemis_spatial_weights_by_year.csv, spatial_time_basis",
 "The vocabulary is not comparable across periods. 113 streams are labelled 'static_structural' in FY2023-24 and 'reference_shape_backcast' in FY2015-16 - the same streams carrying the same weights. They are 50.0% of reference-year CO2 and 72.3% of reference-year CH4.",
 "crosstab of spatial_time_basis between the two periods: static_structural(ref) x reference_shape_backcast(first) = 113 streams",
 "A per-period tally of 'borrowed' weights undercounts the reference year, because the reference year's own borrowed weights are filed under a different name. Any trend read off this column is an artefact.",
 "Add a period-invariant flag (own-period evidence yes/no) beside the existing label. Panels (c) and (d) of fig_ghg_grid.pdf show both labels adjacent and say so in the legend title.",
 "T-FIG-1"),
("D-V16","low","outputs/pakemis_grid_0p05_annual_ref_fy2015_16_fy2023_24.nc, co2/ch4/n2o _emissions comment attribute",
 "VERIFIED CORRECT, recorded because it is easy to get wrong when reading the cube: the comment says cells outside every district are _FillValue and an in-country zero is stored as 0. _FillValue is -9999.0 and masking is on by default, so np.nansum over the spatial_view axis silently converts out-of-country NaN to 0 and makes every cell look in-country. The figure script rebuilds the mask explicitly.",
 "ds.co2_emissions.encoding['_FillValue'] = -9999.0; 33,674 in-country cells of 90,780",
 "A consumer who uses nansum without rebuilding the mask will report 90,780 cells where there are 33,674.",
 "No product change needed; this is a consumer note.","T-FIG-1"),
]
with open(OUT / "comparator_defects.csv", "w", newline="") as fh:
    w = csv.writer(fh, quoting=csv.QUOTE_ALL)
    w.writerow(D_COLS)
    w.writerows(D)
print(f"comparator_defects.csv: {len(D)} rows")

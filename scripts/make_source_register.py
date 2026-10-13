"""Build data/source_documents.csv: which document is behind each activity file, and is it kept.

WHY. Every activity CSV in this repository carries a `source` column naming the publication
its numbers came from, and until now nothing checked that the publication was actually in
the repository. The release manifest hashes the CSVs, so a release could say "these are the
exact numbers" without being able to say "and here is the document they were read from".

That was not hypothetical. Agriculture - 49.6 percent of the inventory - cited the Pakistan
Economic Survey and the NFDC Fertilizer Review for its crop and fertiliser activity, and
neither document was under sources/. Nine other sectors archive theirs (OGRA 9 documents,
Railways 10, NEPRA 5, UNFCCC 3, Power Plants 12, IPPU 15, Aviation 82, Transport 57). The
largest one archived none, and no test could see it.

WHAT THE REGISTER IS. One row per activity CSV, naming the primary publication behind it and
its archival state:

    archived      the document is under sources/ and is hashed into the release manifest
    not-archived  it was obtained and used, but the file was not kept; a gap-register row
                  says so, and the citation cannot be checked until someone re-acquires it
    derived       the file is built from another file in this repository, not from an
                  outside document - an alias table, a crosswalk, a normalisation

This script seeds the register by reading each file's own source column and matching it
against the directories under sources/. The matching is deliberately crude and its output is
a DRAFT: every row must be looked at, because "it named OGRA and there are OGRA files" is not
evidence that the right OGRA edition is present. Rows already classified in the committed
register are preserved, so re-running never silently downgrades a human judgement.

Usage:  python3 scripts/make_source_register.py [--check]
Writes: data/source_documents.csv
"""
import csv
import collections
import os
import re
import sys

from pkinv.paths import DATA, ROOT
from pkinv.assets import catalog as asset_catalog, resolve, legacy_path

SOURCES = os.path.join(ROOT, "sources")
OUT = resolve(os.path.join(DATA, "source_documents.csv"), root=ROOT)
FIELDS = ("data_file", "primary_source", "archival_state", "archived_path", "gap_id", "note",
          "licence_status")

# Publication keyword -> directory under sources/ that would hold it. A hit here means the
# right FAMILY of document is present, never that the right edition is; the register row is
# where that judgement is recorded.
FAMILIES = [
    ("OGRA", "OGRA"),
    ("NEPRA", "Power Plants"),
    ("Pakistan Railways", "Railways"),
    ("Year Book", "Railways"),
    ("CRT", "UNFCCC"),
    ("UNFCCC", "UNFCCC"),
    ("Biennial", "UNFCCC"),
    ("National Communication", "UNFCCC"),
    ("OCAC", "Aviation"),
    ("CAA", "Aviation"),
    ("HIES", "HIES"),
    ("Economic Survey", "Agriculture"),
    ("NFDC", "Agriculture"),
    ("Agricultural Census", "Agriculture"),
    ("EMEP", "EMEP"),
    ("AP-42", "AP42"),
    ("IPCC", "IPCC"),
    ("EDGAR", "EDGAR"),
    ("Punjab", "Punjab Transport"),
    ("Provincial Bureaux", "Transport"),
    ("registered-vehicle", "Transport"),
    ("World Bank 2024 Pakistan Energy Survey", "Papers"),
    ("AGP", "AGP"),
    ("para ", "AGP"),
    ("Auditor", "AGP"),
    ("Domestic.xlsx", "Domestic.xlsx"),
    ("PBS 6th", "Domestic.xlsx"),
]

# Rows the keyword pass cannot settle, classified by hand with the reason on each. Three
# states, and the middle one is the finding this register exists to surface.
#
#   derived       an internal key or alias table - the "source" column holds a district
#                 name or a facility id, not a publication, so there is nothing to archive
#   not-archived  a real outside document that was read and not kept
CLASSIFIED = {
    # -- alias, normalisation and reconciliation tables: nothing outside to keep ----------
    "aviation/airport_aliases.csv": ("derived", "", "airport name normalisation"),
    "aviation/aircraft_aliases.csv": ("derived", "", "ICAO type-designator normalisation"),
    "aviation/operator_groups.csv": ("derived", "", "airline identity grouping"),
    "aviation/control_reconciliation_2023_24.csv": ("derived", "", "reconciles this repo's own controls"),
    "aviation/ocac_annual_sources.csv": ("derived", "", "manifest of the OCAC files under sources/"),
    "aviation/ocac_cumulative_sources.csv": ("derived", "", "manifest of the OCAC files under sources/"),
    "aviation/source_manifest.csv": ("derived", "", "manifest of this sector's own sources"),
    "waste/district_aliases.csv": ("derived", "", "district name normalisation"),
    "transport/vehicle_classes.csv": ("derived", "", "class definitions, not activity"),
    "fugitives/completeness.csv": ("derived", "", "notation keys over this sector's own rows"),
    "ippu/facilities.csv": ("derived", "", "facility register keyed to company_public evidence rows"),
    "ippu/source_manifest.csv": ("derived", "", "manifest of this sector's own evidence ids"),
    "ippu/evidence_maturity.csv": ("derived", "", "maturity ladder over this sector's own evidence"),
    "ippu/master_data_gap_matrix.csv": ("derived", "", "gap matrix over this sector's own rows"),
    "ippu/data_request_packets.csv": ("derived", "", "outbound data requests, not activity"),
    "ippu/cdm_access_manifest.csv": ("derived", "", "access manifest, not activity"),
    "power/tropomi_no2_plants.csv": ("derived", "", "plant ids keyed to the plant ledger"),
    "power/generation_monthly.csv": (
        "archived", "sources/Power Plants",
        "Plant-month generation in two lanes: PBS Electricity Generation Data FY2015-16 "
        "to FY2020-21 (scripts/ingest_pbs_generation.py, accepted only once the plant "
        "rows reconstruct the printed monthly Grand Total) and NEPRA SIR "
        "Detail-of-Generation listings FY2021-22 to FY2023-24 "
        "(scripts/ingest_sir_generation.py, every row closing on its own printed Sum, "
        "the five exceptions arbitrated against the plants' daily reports; listings "
        "held under data/raw/nepra/sir_detail/)"),
    "power/plant_fuel_generation.csv": (
        "archived", "sources/Power Plants",
        "NEPRA State of Industry Report 2020, Tables 16/19/24 - generation by station and "
        "fuel, FY2015-16 to FY2019-20; parsed by scripts/ingest_nepra_plant_fuel.py, which "
        "refuses any sub-table whose header does not resolve to distinct fuels"),
    "power/plant_coordinates.csv": (
        "archived", "sources/Power Plants",
        "WRI Global Power Plant Database and ClimateTRACE power assets, both tracked here; "
        "a coordinate is written only where it falls inside the district or province the "
        "station already declared, or where both databases agree within 10 km inside it"),
    "power/plant_aliases.csv": (
        "derived", "",
        "declared pairings between PBS's station names and NEPRA's, each corroborated in "
        "tests against the two sources' own annual generation for the same year"),
    "power/pbs_sir_aliases.csv": (
        "derived", "",
        "declared pairings between PBS's station names and the SIR listing sheets' "
        "company names (the same-year fuel crosswalk); corroborated at use - a label is "
        "assigned only where the two records' own annual magnitudes agree within the "
        "gross-vs-net band"),
    "power/sir_row_discrepancies.csv": (
        "derived", "",
        "the five SIR listing rows whose printed annual Sum fails their own twelve "
        "months, each carrying its arbitration outcome from the plant's daily reports"),
    "power/sir_month_corrections.csv": (
        "archived", "data/raw/nepra/sir_detail",
        "arbitration outcomes for those rows: four corrected month cells and one "
        "confirmed Sum typo, each hash-pinned to the daily report that decides it; "
        "consumed by scripts/ingest_sir_generation.py under a close-or-refuse gate"),
    "power/generation_monthly_coverage.csv": (
        "derived", "",
        "how much of each subitem's annual control the labelled plants observe, and the "
        "temporal grade that follows from it; both panel lanes (PBS and the NEPRA SIR "
        "listings), with any bound-assigned mass capped at TE3"),
    "ippu/facility_geocoding_overrides.csv": ("derived", "", "Nominatim lookups, re-runnable"),
    # -- real outside documents that were read and not kept -------------------------------
    "power/gem_coal_pak.csv": ("not-archived", "gem-tracker-extract",
                               "GEM Global Coal Plant Tracker July 2026, "
                               "Pakistani rows; xlsx sha256 pinned in "
                               "sources/GEM/GEM_SOURCES.json (CC BY 4.0)"),
    "industry/gem_cement_pak.csv": ("not-archived", "gem-tracker-extract",
                                    "GEM Global Cement and Concrete Tracker "
                                    "July 2026, Pakistani rows; xlsx sha256 "
                                    "pinned in sources/GEM/GEM_SOURCES.json; "
                                    "IPPU entity resolution is a named deferral"),
    "data/gis/manual/firms_fire.csv": ("not-archived", "firms-source",
                                       "NASA FIRMS VIIRS extraction, FY2023-24 "
                                       "burning-season windows; csv sha256 pinned "
                                       "in data/gis/manual/FIRMS_SOURCES.json"),
    "agriculture/es_fiscal_series.csv": ("archived", "sources/Agriculture",
                                        "Pakistan Economic Survey 2023-24 Agriculture "
                                        "chapter, statistical appendix Tables 2.3/2.4/2.9 "
                                        "- the PDF is under sources/Agriculture/"),
    "waste/hydrowaste_pak.csv": ("not-archived", "hydrowaste-source",
                                 "HydroWASTE v1.0 figshare extract (25 Pakistani "
                                 "WWTPs); zip sha256 pinned in "
                                 "sources/HydroWASTE/HYDROWASTE_SOURCES.json"),
    "industry/brick_kiln_coal.csv": ("not-archived", "pey-coal-table",
                                     "Pakistan Energy Yearbook Table 4.4 "
                                     "(2018/2021/2022 editions), transcribed; the "
                                     "PEY PDFs were read and not kept - witness "
                                     "manuscript archived at sources/Papers/"),
    "ippu/production.csv": ("not-archived", "ippu-punjab-pocket-book",
                            "Punjab Statistical Pocket Book 2025 Table 16.3"),
    "fugitives/distribution_practice_evidence.csv": (
        "archived", "sources/Fugitives",
        "SNGPL Annual Report 2023-24, held as sources/Fugitives/"
        "SNGPL_Annual_Report_2023-24.pdf (the rc29 re-audit found the not-archived "
        "state stale: the report had been archived after the row was classified)"),
    "ippu/cement_producer_census_2023_24.csv": (
        "archived", "sources/IPPU/company",
        "fifteen cement producers' annual reports, held under sources/IPPU/company/ "
        "and hashed in the manifest (rc29 re-audit: the not-archived state predated "
        "the archive)"),
    "ippu/company_boundary_audit.csv": (
        "archived", "sources/IPPU/company",
        "cement producers' annual reports, held under sources/IPPU/company/ (rc29 "
        "re-audit)"),
    "ippu/company_clinker_2023_24.csv": (
        "archived", "sources/IPPU/company",
        "cement producers' annual reports, held under sources/IPPU/company/; the "
        "sha256 the activity file quotes for Lucky matches the manifest hash of "
        "Lucky_Annual_Report_2024.pdf (rc29 re-audit)"),
    "ippu/chemical_plant_activity.csv": ("not-archived", "ippu-producer-annual-reports",
                                         "chemical producers' annual reports, cited by URL"),
    "ippu/chemical_plant_evidence.csv": ("not-archived", "ippu-producer-annual-reports",
                                         "chemical producers' annual reports, cited by URL"),
    "ippu/cement_monthly_2022.csv": (
        "archived", "data/raw/pbs/qim",
        "PBS Quantum Index of Manufacturing Table 2, FY2021-22 and FY2022-23 "
        "editions, held as data/raw/pbs/qim/pbs_qim_table2_{2021_22,2022_23}.pdf "
        "with URL/sha256/retrieval rows in data/manifests/source_manifest.csv "
        "(rc29 re-audit; the raw-archive precedent is power/sir_month_corrections)"),
    # THREE sources now, and their archival states differ. The state here is the weakest of
    # them, because a file-level "archived" would claim the QIM and State Bank editions are
    # kept and they are not. The cement rows for FY2015-16 to FY2018-19 come from a yearbook
    # that IS under sources/, inside the National provincial-statistics archive, and
    # scripts/extract_psyb_cement.py reads them back out of it on demand.
    "ippu/national_activity.csv": ("not-archived", "ippu-pbs-qim",
                                   "State Bank FY2023-24 Statistical Supplement, read and "
                                   "not kept - the one absent document behind this file "
                                   "since the rc29 re-audit found its other two on disk: "
                                   "the PBS QIM Table 2 editions are held under "
                                   "data/raw/pbs/qim/ and Pakistan Statistical Year Book "
                                   "2020 Table 13.2 is archived at 'sources/Provincial "
                                   "Statistics/National-20260803T134231Z-1-001.zip::National/"
                                   "Pakistan_Statistical_Year_Book_2020.pdf'"),
    "ippu/clinker_trade_annual.csv": ("not-archived", "ippu-un-comtrade",
                                      "UN Comtrade / WITS extract"),
    "ippu/clinker_trade_monthly.csv": ("not-archived", "ippu-un-comtrade",
                                       "UN Comtrade extract"),
    # The annual totals are not a second activity source. They are the CONTROL that lets a
    # month Comtrade is silent about be proved zero instead of assumed zero, which is the
    # only reason the pre-FY2023-24 years have a trade term at all.
    "ippu/clinker_trade_annual_controls.csv": ("not-archived", "ippu-un-comtrade",
                                               "UN Comtrade annual-frequency extract"),
    "ippu/hfc_consumption_controls.csv": (
        "archived", "sources/IPPU",
        "UNEP Ozone Secretariat country profile, archived as a dated snapshot "
        "(sources/IPPU/unep_ozone_pakistan_profile_2026-08-23.html) in the rc30 "
        "sweep - a churning dynamic page, so the snapshot is the dated witness of "
        "what was read, and the not-retained register keeps the live URL"),
    "ippu/hfc_trade_screening.csv": ("not-archived", "ippu-un-comtrade",
                                     "UN Comtrade public API, HS-2022 HFC lines "
                                     "(rc30); parsed in flight, re-derivable"),
    "ippu/hfc_inventory_import_contract.csv": ("not-archived", "ippu-unep-ozone",
                                               "National Ozone Unit correspondence"),
    "ippu/nitric_acid_monitoring.csv": ("not-archived", "ippu-producer-annual-reports",
                                        "producer monitoring evidence"),
    "ippu/nitric_acid_monitoring_detail.csv": ("not-archived", "ippu-producer-annual-reports",
                                               "producer monitoring evidence"),
    "aviation/aircraft_family_shares_2023_24.csv": ("not-archived", "aviation-operator-fleet-pages",
                                                    "operator fleet pages, cited by URL"),
    "aviation/route_evidence_2023_24.csv": (
        "archived", "sources/Aviation",
        "the PIA privatisation investment teaser, RE-FETCHED and archived by the rc29 "
        "reacquisition sweep as sources/Aviation/InvestmentTeaser_2342025.pdf (sha256 "
        "5e9937f8aa20...); per-row route corroborations also cite live pages "
        "(aeroroutes, operator sites) recorded in data/not_retained_register.csv row "
        "operator_fleet_route_pages"),
    "aviation/airport_coordinate_overrides.csv": (
        "derived", "", "hand-resolved coordinates (OSM centroid) the OurAirports "
                       "snapshot cannot supply; held-row-wins in the controls builder"),
    "aviation/airports.csv": (
        "archived", "sources/Aviation",
        "OurAirports snapshot, held as sources/Aviation/"
        "ourairports_airports_2026-08-06.csv (rc29 re-audit)"),
    "aviation/international_airports.csv": (
        "archived", "sources/Aviation",
        "OurAirports snapshot, held as sources/Aviation/"
        "ourairports_airports_2026-08-06.csv (rc29 re-audit)"),
    "aviation/airline_controls_2023_24.csv": (
        "archived", "sources/Aviation",
        "CAA major-traffic-flow tables, held as sources/Aviation/"
        "major-traffic-flow-airlines-2023-24.pdf (rc29 re-audit)"),
    "aviation/airport_controls_2023_24.csv": (
        "archived", "sources/Aviation",
        "CAA major-traffic-flow tables, held as sources/Aviation/"
        "major-traffic-flow-airports-{2022-23,2023-24}.pdf (rc29 re-audit)"),
    "aviation/benchmarks.csv": (
        "archived", "sources/Aviation",
        "OECD air-transport SDMX extracts, held as sources/Aviation/"
        "OECD_air_transport_PAK_{2019_2025,FY2022_FY2023}.csv; benchmarks.csv "
        "aggregates the archived monthly rows to fiscal years (rc29 re-audit)"),
    "aviation/unfccc_inventory_controls.csv": ("archived", "sources/UNFCCC", ""),
    "residential/woodfuel.csv": ("not-archived", "faostat-extracts", "FAOSTAT Forestry"),
    "wastewater/protein.csv": ("not-archived", "faostat-extracts", "FAOSTAT Food Balance Sheets"),
    "historical/crops.csv": ("not-archived", "faostat-extracts", "FAOSTAT historical panel"),
    "historical/livestock_stocks.csv": ("not-archived", "faostat-extracts", "FAOSTAT historical panel"),
    "historical/fertilizer_n.csv": ("not-archived", "faostat-extracts", "FAOSTAT historical panel"),
    "historical/faostat_emissions.csv": ("not-archived", "faostat-extracts", "FAOSTAT Emissions Totals"),
    "residential/monthly_degree_days.csv": ("not-archived", "nasa-power",
                                            "NASA POWER monthly T2M, re-fetchable by script"),
    "railways/wdi_rail.csv": ("not-archived", "worldbank-wdi",
                              "World Bank WDI, re-fetchable by script"),
    "fugitives/infrastructure_2023_24.csv": (
        "archived", "sources/OGRA",
        "OGRA State of the Regulated Petroleum Industry 2023-24, Tables 3.13/3.17/"
        "3.22/3.23 (the file's own source_reference column), held under sources/OGRA/; "
        "the transmission rows sum to the report's printed 13,526 km exactly (rc29 "
        "re-audit; the earlier 'utility annual reports' label was wrong about both "
        "the document and its retention)"),
    "data/gis/adm2_intersections_267x340.csv": (
        "derived", "",
        "exact cell x ADM2 area fractions computed from PAK_ADM2.geojson by "
        "scripts/build_adm2_intersections.py (rc32); a committed geometry cache "
        "like the proxy rasters, no external document behind it"),
    "ippu/requests/cement_clinker_request_template.csv": ("derived", "", "outbound request template"),
    "ippu/requests/chemical_plant_request_template.csv": ("derived", "", "outbound request template"),
    "ippu/requests/crt_cement_method_request_template.csv": ("derived", "", "outbound request template"),
    "ippu/requests/hfc_inventory_request_template.csv": ("derived", "", "outbound request template"),
    # -- the last six, each looked at rather than pattern-matched ------------------------
    # rc37: the ledger said the census tables were read from portal views with no file
    # to keep, while data/pbs_census/ holds Table_4/Table_6 district and national
    # workbooks (+ PDFs and their pdftotext dumps) and the hierarchical transcription the
    # activity files roll up. The claim was stale, not the holding.
    # rc38, the agriculture pass. TWO corrections in one row. The archive pointer was a
    # seeded guess - sources/Agriculture holds the Economic Survey and the NFDC review, not
    # the census - and the counts are ROUNDED where the district file is exact.
    "livestock_2024.csv": ("archived", "data/pbs_census",
        "PBS 7th Agricultural Census 2024 Table 6, national totals. THE COMMITTED COUNTS ARE "
        "ROUNDED TO THREE SIGNIFICANT FIGURES and the census is not: cattle 55,800,000 "
        "against 55,862,560 (-0.11%), buffalo 47,700,000 against 47,738,368 (-0.08%), sheep "
        "-0.19%, goats -0.03%, camels -0.75%. The exact counts are already in this "
        "repository at the finer grain, and the RE-BASE WAS TAKEN in rc39: the national row "
        "now carries the census's exact enumeration (cattle 55,862,560, ruminant total "
        "245,524,371) and the reference totals moved with it. The district transcription "
        "does NOT sum to the national row exactly - it runs eight sheep over and eight "
        "camels under, with cattle and buffalo out by one head each - and neither side is "
        "edited to close that. outputs/agriculture_livestock_reconciliation_2024.csv "
        "publishes the residual per species with the normalisation factor the spatial "
        "weights carry; data/transcription_checks.csv checks each cell against the "
        "document."),
    "livestock_district_2024.csv": ("archived", "data/pbs_census",
                                    "PBS 7th Agricultural Census 2024 Table 4/6 district workbooks, "
                                    "held beside the transcription they were read into"),
    "livestock_province_2024.csv": ("archived", "data/pbs_census",
                                    "PBS 7th Agricultural Census 2024 Table 4/6 national workbooks, "
                                    "held beside the transcription they were read into"),
    # rc37: the transcription directories (paths are relative to data/, not data/activity/)
    "data/pbs_census/livestock_by_district_2024.csv": ("archived", "data/pbs_census",
        "the hierarchical (province/division/district) transcription of Table 4/6; "
        "data/activity/livestock_district_2024.csv is its district roll-up"),
    "data/pbs_census/livestock_province_2024.csv": ("archived", "data/pbs_census",
        "the province transcription of Table 4/6"),
    "data/district_records/district_rice_area_MNFSR_2022-23.csv": ("archived", "data/district_records",
        "MNFSR Crops Area & Production district-wise 2022-23 booklet, held beside its pdftotext dump"),
    "data/district_records/district_wheat_area_MNFSR_2022-23.csv": ("archived", "data/district_records",
        "MNFSR Crops Area & Production district-wise 2022-23 booklet"),
    "data/district_records/district_rice_area_PunjabCRS_2022-25.csv": ("archived", "data/district_records",
        "Punjab Crop Reporting Service district-wise rice 2022-25 (two PDFs + dumps held)"),
    "data/gleam/gleam_mms_south_asia.csv": ("archived", "data/gleam",
        "FAO GLEAM 3.0 reference documentation Tables 3.2-3.5 (South Asia MMS shares), PDFs held; "
        "data/gleam_mms.csv is the Nex-blended derivation the sensitivity reads"),
    "data/gmw/pakistan_mangrove_extent.csv": ("archived", "data/gmw",
        "Global Mangrove Watch v3/v4 country statistics workbooks, held"),
    "railways/corridor_weights.csv": ("derived", "",
                                      "route weights derived from this repo's own network geometry"),
    "residential/hies/hies_diagnostics.csv": ("archived", "sources/HIES",
                                              "computed from the HIES microdata held under sources/"),
    "residential/hies/hies_fuel_quantities.csv": ("archived", "sources/HIES",
                                                  "computed from the HIES microdata held under sources/"),
    "waste/population_district.csv": ("archived", "sources/Domestic.xlsx",
                                      "the interpolated panel workbook is held; the 2024 row is "
                                      "projected from it by scripts/project_waste_population.py"),
}


# rc65 (2026-10-12), THE RETENTION SWEEP. These entries replace the ones above; they are kept
# together so the change the sweep made to the register can be read in one place. The
# per-document detail (which file, what was checked) is data/catalog/cited_documents.csv.
_FAO = "data/raw/faostat/faostat_%s_E_All_Data_(Normalized).zip"
_PSYB = ("sources/Provincial Statistics/National-20260803T134231Z-1-001.zip")
_AS_READ = "the bytes the table was read from, held since the rc65 retention sweep; "
CLASSIFIED.update({
    # -- held all along, or held on this machine outside the repository ---------------------
    "historical/crops.csv": ("archived", _FAO % "Production_Crops_Livestock",
        _AS_READ + "the bulk sat in a gitignored cache; fetch_history --check reproduces "
        "the table exactly"),
    "historical/livestock_stocks.csv": ("archived", _FAO % "Production_Crops_Livestock",
        _AS_READ + "fetch_history --check reproduces the table exactly"),
    "historical/fertilizer_n.csv": ("archived", _FAO % "Inputs_FertilizersNutrient",
        _AS_READ + "fetch_history --check reproduces the table exactly"),
    "historical/faostat_emissions.csv": ("archived", _FAO % "Emissions_Totals",
        _AS_READ + "fetch_history --check reproduces the table cell for cell"),
    "residential/woodfuel.csv": ("archived", _FAO % "Forestry",
        _AS_READ + "ingest_residential.py --check reproduces the table exactly"),
    "wastewater/protein.csv": ("archived", _FAO % "FoodBalanceSheets",
        "FAOSTAT Food Balance Sheets bulk, held; scripts/check_faostat_protein.py finds "
        "all four years in it"),
    "ippu/production.csv": ("archived",
        "sources/Provincial Statistics/Punjab-20260803T134030Z-1-001.zip",
        "Punjab Statistical Pocket Book 2025, member Punjab/SPB 2025.pdf, Table 16.3 on PDF "
        "p. 293. The register called it a priced volume that was not held; it was inside "
        "this archive, where the stale-claim test did not look"),
    # -- fetched and kept by the sweep ---------------------------------------------------------
    "industry/gem_cement_pak.csv": ("archived",
        "data/raw/gem/Plant-level data - Global Cement and Concrete Tracker - July 2026 - "
        "Standard Copy V1.xlsx",
        "GEM served the workbook byte-identical to the digest pinned in "
        "sources/GEM/GEM_SOURCES.json; fetch_gem_trackers.py --check reproduces the extract"),
    "power/gem_coal_pak.csv": ("archived",
        "data/raw/gem/Global-Coal-Plant-Tracker-July-2026.xlsx",
        "GEM served the workbook byte-identical to the pinned digest; --check reproduces "
        "the extract. The old row called the source 'live wiki pages'; the wiki addresses "
        "are a column of this workbook"),
    "power/gem_gas_oil_pak.csv": ("archived",
        "data/raw/gem/Global Oil and Gas Plant Tracker (GOGPT) - August 2026.xlsx",
        "served byte-identical to the pinned digest. The row had said archived at "
        "sources/GEM, which holds only the digest sidecar"),
    "power/gem_bioenergy_pak.csv": ("not-archived", "gem-tracker-extract",
        "GEM Global Bioenergy Power Tracker V3: read in memory, not kept, and no longer "
        "served. The held workbook is v4, a later edition. The row had said archived at "
        "sources/GEM, which holds only the digest sidecar"),
    "waste/hydrowaste_pak.csv": ("archived", "data/raw/hydrowaste/HydroWASTE_v10.zip",
        "figshare served the archive byte-identical to the pinned digest; "
        "fetch_hydrowaste.py --check reproduces the extract"),
    "railways/wdi_rail.csv": ("archived", "data/raw/worldbank_wdi",
        "the two World Bank API responses, kept; fetch_wdi_rail.py --check reproduces the "
        "table exactly"),
    "residential/monthly_degree_days.csv": ("archived", "data/raw/nasa_power",
        "the five NASA POWER responses, kept; fetch_hdd.py --check reproduces the table "
        "exactly"),
    "ippu/clinker_trade_monthly.csv": ("archived", "data/raw/un_comtrade/hs252310",
        "every UN Comtrade response for the window, the silent months included, kept; "
        "fetch_comtrade_clinker.py --check: 240 of 240 held rows agree"),
    "ippu/clinker_trade_annual_controls.csv": ("archived", "data/raw/un_comtrade/hs252310",
        "the annual-frequency responses, kept with the monthly ones; every control agrees"),
    "ippu/clinker_trade_annual.csv": ("archived", "data/raw/wits",
        "the two WITS pages, kept; both cited quantities are printed on them"),
    "ippu/hfc_trade_screening.csv": ("archived", "data/raw/un_comtrade/hfc",
        "the six UN Comtrade responses, kept; fetch_comtrade_hfc.py: 18 of 18 rows agree, "
        "and the responses report three HFC lines (2903.46, 2903.47) the table omits"),
    "ippu/national_activity.csv": ("archived",
        "data/raw/sbp/sbp_annual_report_fy24_statistical_supplement.pdf",
        "State Bank FY2023-24 Statistical Supplement, held. The register said its address "
        "had never been recorded; it was in references.bib, and it had moved. The other two "
        "sources of this file were already held (PBS QIM under data/raw/pbs/qim, Pakistan "
        "Statistical Year Book 2020 in the National archive)"),
    "ippu/nitric_acid_monitoring.csv": ("archived", "data/raw/unfccc_cdm",
        "the two CDM project pages, held as Internet Archive captures (the site refuses "
        "unattended clients); every monitoring figure in the file is printed on them"),
    "ippu/nitric_acid_monitoring_detail.csv": ("not-archived", "ippu-producer-annual-reports",
        "two CDM review-comment pages no route could fetch; the issuance request and its "
        "three review forms are held"),
    "ippu/chemical_plant_evidence.csv": ("archived", "data/raw/company_reports/fertilizer",
        "the Fatima report as cited through PSX, the Fatima site and both CDM project "
        "pages are held"),
    "ippu/chemical_plant_activity.csv": ("not-archived", "ippu-producer-annual-reports",
        "every cited report is now held except the retired FFBL site, which one row "
        "without a figure cites"),
    "data/ml/brick_kilns_pk.csv": ("archived",
        "data/raw/brick_kilns/zenodo_14718244_Brick_Kilns_IGP_PK-Main.csv",
        "the published file of Zenodo record 14718244, held; its md5 equals the digest the "
        "record prints"),
    # -- not a document at all -----------------------------------------------------------------
    "ippu/hfc_inventory_import_contract.csv": ("derived", "",
        "the compiler's own sixteen-field request schema for the National Ozone Unit. The "
        "register called it private correspondence that could not be archived; no letter "
        "was sent (request IPPU-HFC-01 is an unsent draft), so there is nothing to hold"),
    # -- still not held, and newly visible ------------------------------------------------------
    "aviation/aircraft_family_shares_2023_24.csv": ("not-archived",
        "aviation-operator-fleet-pages",
        "seven cited pages: four held with their content, one gone at the publisher, two "
        "held only as script shells"),
    "aviation/route_evidence_2023_24.csv": ("not-archived", "aviation-operator-fleet-pages",
        "fifteen cited sources: ten held with their content; one gone, one address now "
        "serving another article, three reddit threads held only as shells. The row had "
        "said archived on the strength of the one PDF"),
    "industry/brick_kiln_coal.csv": ("not-archived", "pey-coal-table",
        "HDIP Pakistan Energy Yearbook Table 4.4: priced, read from a collaborator's "
        "archive, not held; two held reprints witness most of the series"),
    "industry/coal_by_sector_vintages.csv": ("not-archived", "pey-coal-table",
        "sixteen rows cite the HDIP yearbooks, which are not held; the seven Economic "
        "Survey, supplement and Compendium PDFs it also cites are. The row had said "
        "archived"),
    "railways/fuel_consumption.csv": ("not-archived", "railways-yearbook-2014-15",
        "the two pre-series rows cite the 2014-15 Year Book, which is not held; the five "
        "later editions are. The row had said archived at a directory whose earliest "
        "edition is 2016-17"),
    "transport/fuel_sulfur_by_year.csv": ("not-archived", "road-fuel-sulfur",
        "both Dawn articles are held with their content; the PSO product page is held only "
        "as a script shell without the cited sentence"),
    "industry/fuel_sulfur_evidence.csv": ("not-archived", "road-fuel-sulfur",
        "one specification row rests on the same PSO product page, held only as a script "
        "shell; the Compendium, the literature, the fuel specifications and the Dawn "
        "articles this file cites are held. The row had said archived"),
    "waste/population_district.csv": ("not-archived", "pbs-census-2017-district-tables",
        "the 2023 census Table 1 workbooks are now held and reprint the 2017 totals; the "
        "2017 census's own district tables are not. The row had said archived on the "
        "compiled workbook"),
    "data/gis/manual/firms_fire.csv": ("not-archived", "firms-source",
        "the API responses were not kept; NASA's keyless country-year files are held and "
        "contain every in-window Pakistan detection of the layer"),
    # -- archived all along, at the wrong address ----------------------------------------------
    "fugitives/production.csv": ("archived", _PSYB,
        "Pakistan Statistical Year Book 2020 (member National/"
        "Pakistan_Statistical_Year_Book_2020.pdf) and the Economic Survey 2025-26 chapter "
        "under data/raw/finance_division; the row had pointed at sources/Railways"),
    "fugitives/production_province.csv": ("archived", _PSYB,
        "Pakistan Statistical Year Book 2020, Table 7.3; the row had pointed at "
        "sources/Railways"),
    "wastewater/sanitation_shares.csv": ("archived",
        "data/raw/who_unicef_jmp/JMP_2025_PAK_Pakistan_household.xlsx",
        "WHO/UNICEF JMP household country file, fetched by the sweep; the row had said "
        "archived at sources/OGRA and no JMP file was held anywhere"),
})
# rc66: the station fuel record behind the per-year provincial split of grid power.
CLASSIFIED["power/plant_fuel_quantity_back_years.csv"] = (
    "archived", "sources/Power Plants/NEPRA State of Industry Report 2020.pdf",
    "NEPRA State of Industry Report 2020, Tables 16 (GENCOs) and 19 (IPPs): each station's "
    "fuel quantity beside its generation, FY2015-16 to FY2019-20, read by "
    "scripts/ingest_nepra_plant_fuel_quantity.py, whose --check re-derives the table from the "
    "held report. Eight rows are typed from two other held editions: the three public-sector "
    "RLNG plants' FY2018-19 fuel from the 2023 report's Table 21 (PDF p. 115) and their "
    "commissioning generation from the 2021 report's station-wise generation table (PDF "
    "p. 106)")
# rc67: the K-Electric system's station fuel before the plant ledger begins.
CLASSIFIED["power/ke_station_fuel_back_years.csv"] = (
    "archived", "sources/Power Plants/NEPRA State of Industry Report 2020.pdf",
    "NEPRA State of Industry Report 2020, Table 24 (K-Electric and IPPs): each station's gas, "
    "RLNG and furnace-oil quantity beside its generation, FY2015-16 to FY2018-19. Three "
    "furnace-oil cells the report prints as n.p. are typed absences")
# rc67: the fertiliser gas class behind the membership of the post-meter leak base, and the two
# years of the regulator's sector table that no text layer gives.
CLASSIFIED["fugitives/fertilizer_gas_class.csv"] = (
    "archived", "sources/OGRA",
    "OGRA State of the Regulated Petroleum Industry, the Fertilizer row of the sector-wise gas "
    "consumption table in each edition from 2015-16 to 2023-24. FY2020-21 is read from the page "
    "image of a scanned edition; FY2022-23 is restated on the class vocabulary from the 2023-24 "
    "edition's comparison columns. Per-document detail is in data/catalog/cited_documents.csv")
CLASSIFIED["fugitives/ogra_sector_gas_2021_2023.csv"] = (
    "archived", "sources/OGRA",
    "OGRA State of the Regulated Petroleum Industry: the whole sector-wise gas table for "
    "FY2020-21 (Table 3.28, read from the page image) and FY2022-23 (the 2023-24 edition's "
    "Tables 3.28 and 3.30 comparison columns, with the independent systems from the 2022-23 "
    "edition's Table 3.25)")
for _name in ("afr2025_fertilizer_gas_by_plant", "afr2025_fertilizer_gas_monthly",
              "afr2025_offtake_by_product", "afr2025_production_by_manufacturer",
              "annex5_national_month_product"):
    CLASSIFIED["data/nfdc/%s.csv" % _name] = (
        "archived", "data/nfdc/AFR_2024-25.pdf",
        "NFDC Annual Fertilizer Review 2024-25, held beside its extractions; the row had "
        "pointed at sources/Agriculture")
CLASSIFIED["data/nfdc_offtake.csv"] = (
    "archived", "data/nfdc/AFR_2024-25.pdf",
    "NFDC Annual Fertilizer Review 2024-25; the row had pointed at sources/Agriculture")

# rc65: TWO NOTES THAT LIVED ONLY IN THE COMMITTED CSV. The builder writes a CLASSIFIED row's
# note from this ledger, so a note hand-edited into the CSV for such a row survives only until
# the next regeneration - and tests/test_data_provenance.py compares states, not notes. These
# two carried the table pointers the citation-pointer audit scores; the retention sweep was
# the first regeneration since they were written and it would have erased both. They are
# recorded here so the ledger and the register say the same thing.
_KEPT_NOTES = {
    "aviation/unfccc_inventory_controls.csv": "Pakistan BTR1 2024, sources/UNFCCC/btr1_2024.txt: the International Bunkers block at line 841, with 1A3a1 International Aviation on line 842 (0.11 Mt CO2) and 1A3d1 International Marine on line 843; domestic civil aviation is not separately reported in that table, which is why the matched row carries no value (pointer recovered 2026-10-05 from the held transcription).",
    "power/generation_monthly.csv": "Plant-month generation in two lanes: PBS Electricity Generation Data FY2015-16 to FY2020-21 (scripts/ingest_pbs_generation.py, accepted only once the plant rows reconstruct the printed monthly Grand Total) and NEPRA SIR Detail-of-Generation listings FY2021-22 to FY2023-24 (scripts/ingest_sir_generation.py, every row closing on its own printed Sum, the five exceptions arbitrated against the plants' daily reports; listings held under data/raw/nepra/sir_detail/) The PBS lane's figures are in the 'Electricity generation' worksheet of pbs_minerals_2020_21.xlsx and the equivalent sheet of the earlier editions - a separate sheet from 'mineral production', which is why the minerals parse and the generation parse read the same workbook for different tables (pointer recovered 2026-10-05 from the held workbook)."
}
for _key, _note in _KEPT_NOTES.items():
    CLASSIFIED[_key] = (CLASSIFIED[_key][0], CLASSIFIED[_key][1], _note)


def _primary_source(path):
    """The most-cited source string in one activity file, trimmed to its publication."""
    try:
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except (OSError, UnicodeDecodeError):
        return ""
    if not rows:
        return ""
    # Provenance hides under several column names in this repository - source, source_file,
    # source_id, source_reference - and a file with none of them is not merely unlabelled,
    # it is unprovenanced, which is its own finding.
    col = next((c for c in rows[0] if c and re.search(r"source|citation|reference|url",
                                                      c, re.I)), None)
    if not col:
        return ""
    counts = collections.Counter()
    for r in rows:
        s = (r.get(col) or "").strip()
        if s:
            counts[re.split(r"[;(]", s)[0].strip()] += 1
    return counts.most_common(1)[0][0][:160] if counts else ""


def _guess_family(source):
    for keyword, directory in FAMILIES:
        if keyword.lower() in source.lower():
            path = os.path.join(SOURCES, directory)
            if os.path.isdir(path) and os.listdir(path):
                return "sources/%s" % directory
    return ""


def _existing():
    if not os.path.exists(OUT):
        return {}
    with open(OUT, newline="", encoding="utf-8") as f:
        rows = {legacy_path(r["data_file"], root=ROOT): r
                for r in csv.DictReader(f)}
    # A row written before the licence column existed (or by a writer that lost it) must
    # come back as an explicit 'undetermined', never as a blank - blanks read as complete.
    for r in rows.values():
        r["data_file"] = legacy_path(r["data_file"], root=ROOT)
        if not (r.get("licence_status") or "").strip():
            r["licence_status"] = "undetermined"
    return rows


# Non-CSV geometry artefacts inside the provenance frame (rc11, the ODbL round):
# the OSM-derived rasters and network extract are DERIVATIVE DATABASES and must
# carry a licence row like any activity file. Named explicitly rather than swept
# by a *.npy glob, because the CC-BY proxy caches beside them are documented in
# data/gis/PROXY_SOURCES.md under different logic and a blanket sweep would drag
# them in. tests/test_data_provenance.py reads this same tuple.
# ---------------------------------------------------------------------------------------
# THE NOT-RETAINED REGISTER (rc29, the seventeenth review's ask): one row per source
# DOCUMENT that was read and not kept, carrying what the register rows above cannot -
# the exact URL, the access date, the page or table read, the retrieval script where one
# exists, the hash where one was pinned, and the reason the document is not held.
#
# CONTRACT, enforced by tests/test_data_provenance.py: every row must carry a sha256 OR a
# non-empty legal_reason_for_non_retention - a typed refusal, never a silent blank. Every
# not-archived activity file above must appear in exactly one row's data_files, and every
# data_files entry must be a not-archived row (the bijection).
#
# access_date_utc is the extract's first git commit date - a documented LOWER BOUND on
# retention, not a fabricated fetch timestamp - except where a sidecar or attempt row
# records the actual date.
NOT_RETAINED = {
    # rc65 (2026-10-12): the retention sweep. Twenty rows stood here through rc64 and the
    # manuscript said so. The sweep found that no cited document had been deleted: seventeen
    # of the twenty had never been saved (fetchers parsed responses in memory, pages were read
    # live) and three were held all along while this register called them absent. Every one
    # that could be fetched, copied in or restored is now under data/raw/ and listed, per
    # document, in data/catalog/cited_documents.csv. What remains here is what is still not
    # held, and it includes documents the old register never listed because their files were
    # marked "archived" at a directory that did not contain them.
    "aviation_route_and_fleet_pages": {
        "access_class": "free-to-read",
        "gap_id": "aviation-operator-fleet-pages",
        "data_files": "data/activity/aviation/aircraft_family_shares_2023_24.csv;"
                      "data/activity/aviation/route_evidence_2023_24.csv",
        "exact_url": "https://www.aeroroutes.com/eng/231102-erpkx; "
                     "https://www.piac.com.pk/corporate/about-us/fleet; "
                     "https://www.airblue.com/flightinfo/; "
                     "https://www.brecorder.com/news/40220197; "
                     "https://www.reddit.com/r/dubai/comments/199jved; "
                     "https://www.reddit.com/r/islamabad/comments/15e8vvq/; "
                     "https://www.reddit.com/r/pakistan/comments/174gchc",
        "access_date_utc": "2026-08-08",
        "page_table_coords": "the per-row source_reference addresses of the two files",
        "retrieval_script": "scripts/fetch_cited_documents.py",
        "sha256": "",
        "legal_reason_for_non_retention":
            "no legal bar; seven of the twenty-odd pages these two files cite could not be "
            "held with their content. The aeroroutes filing answers 404 and no archive "
            "captured it. The PIA fleet page, the Airblue flight-information page and the "
            "three reddit threads are built in the reader's browser: the bytes served to an "
            "unattended client are held and carry none of the cited content. The Business "
            "Recorder address now serves an unrelated article (a citation to check). Held "
            "witnesses: a later aeroroutes filing for the same service, and the PIA "
            "privatisation teaser for the fleet mix",
        "how_to_obtain": "open each address in a browser and save the rendered page to the "
                         "path data/raw/ACQUISITION_LOG_retention_2026_10.csv names for it"},
    "hdip_energy_yearbook": {
        "access_class": "paid",
        "gap_id": "pey-coal-table",
        "data_files": "data/activity/industry/brick_kiln_coal.csv;"
                      "data/activity/industry/coal_by_sector_vintages.csv",
        "exact_url": "https://www.hdip.gov.pk/pakistan-energy-yearbook",
        "access_date_utc": "2026-08-03",
        "page_table_coords": "Table 4.4, Consumption of Coal by Sector (National); the "
                             "2018, 2021 and 2022 editions",
        "retrieval_script": "",
        "sha256": "",
        "legal_reason_for_non_retention":
            "priced HDIP publication. The PDFs were read from a collaborator's archive "
            "(named Coal Use 2018.pdf, Coal Use 2021.pdf and Coal Use 2023.pdf in the "
            "transcription script, restored to data/raw/punjab_industry_bundle/) and are not "
            "on this machine. No open copy was found at the publisher, in the Internet "
            "Archive or by web search on 2026-10-12. Held reprints of the series: PBS "
            "Compendium on Environment Statistics 2020 Table A-45 and the Economic Survey "
            "2024-25 supplement Table 14.1",
        "how_to_obtain": "the three PDFs from whoever holds the Punjab-industry archive, or "
                         "purchase from HDIP; place them under data/raw/hdip_energy_yearbook/"},
    "cdm_review_comment_pages": {
        "access_class": "free-to-read",
        "gap_id": "ippu-producer-annual-reports",
        "data_files": "data/activity/ippu/nitric_acid_monitoring_detail.csv",
        "exact_url": "https://cdm.unfccc.int/Projects/DB/TUEV-SUED1155134039.49/iProcess/"
                     "DNV-CUK1218364087.49/ReviewInitialComments/UWGA8K2YM2Z0BQ48PVAFDVBVAGLZ8P; "
                     "https://cdm.unfccc.int/Projects/DB/TUEV-SUED1155134039.49/iProcess/"
                     "DNV-CUK1218364087.49/ReviewInitialComments/QRCJ4TFXFE2NXMFL2PML2A4DIL6F01",
        "access_date_utc": "2026-08-08",
        "page_table_coords": "two review-comment records of issuance request "
                             "DNV-CUK1218364087.49, Pakarab project 0557",
        "retrieval_script": "scripts/fetch_cited_documents.py",
        "sha256": "",
        "legal_reason_for_non_retention":
            "public UNFCCC records; the site answers an unattended client with a challenge "
            "page and no archive captured these two addresses. The project pages, the "
            "issuance request and its three request-for-review forms ARE held, from Internet "
            "Archive captures",
        "how_to_obtain": "open the two addresses in a browser and save each page to "
                         "data/raw/unfccc_cdm/ under the name the acquisition log gives"},
    "railways_year_book_2014_15": {
        "access_class": "dead-with-official-alternative",
        "gap_id": "railways-yearbook-2014-15",
        "data_files": "data/activity/railways/fuel_consumption.csv",
        "exact_url": "https://www.pakrail.gov.pk/yearbook.aspx",
        "access_date_utc": "2026-08-03",
        "page_table_coords": "Principal Statistics, H.S.D. oil, the 2013-14 and 2014-15 "
                             "columns (two rows before the inventory's first year)",
        "retrieval_script": "scripts/fetch_cited_documents.py",
        "sha256": "",
        "legal_reason_for_non_retention":
            "the publisher lists year books from 2015-16 on and its 2015-16 link answers "
            "404; the 2014-15 edition is in no archive searched. The file had been marked "
            "archived at sources/Railways, which holds 2016-17 onward. Held reprint: "
            "Pakistan Statistical Year Book 2020 Table 20.14 gives 121,836 for 2014-15 "
            "(equal) and 98,211 for 2013-14 (the table holds 98,212)",
        "how_to_obtain": "Pakistan Railways headquarters library; the two rows are outside "
                         "the nine inventory years"},
    "gem_bioenergy_tracker_v3": {
        "access_class": "openly-licensed",
        "gap_id": "gem-tracker-extract",
        "data_files": "data/activity/power/gem_bioenergy_pak.csv",
        "exact_url": "https://globalenergymonitor.org/projects/"
                     "global-bioenergy-power-tracker/download-data/",
        "access_date_utc": "2026-09-01",
        "page_table_coords": "Global Bioenergy Power Tracker V3, Pakistani rows (23 units)",
        "retrieval_script": "scripts/fetch_gem_trackers.py",
        "sha256": "4799a4dae94addf2f5b96e8eb4beb5f2ca7683659fd262020c5f3a1f9ad45590",
        "legal_reason_for_non_retention":
            "CC BY 4.0, no legal bar. The V3 workbook was read in memory and not kept; GEM "
            "serves only its current edition and now serves v4, which is held "
            "(data/raw/gem/). The same 23 units are in v4; three differ in capacity or "
            "status. The other three trackers were served byte-identical to their pinned "
            "digests and are held as read. The file had been marked archived at sources/GEM, "
            "which holds only the digest sidecar",
        "how_to_obtain": "GEM on request for a superseded edition; the held v4 otherwise"},
    "pbs_census_2017_district_tables": {
        "access_class": "free-to-read",
        "gap_id": "pbs-census-2017-district-tables",
        "data_files": "data/activity/waste/population_district.csv",
        "exact_url": "https://www.pbs.gov.pk/",
        "access_date_utc": "2026-08-03",
        "page_table_coords": "6th Population and Housing Census 2017, district population "
                             "by urban and rural",
        "retrieval_script": "",
        "sha256": "",
        "legal_reason_for_non_retention":
            "the district series was compiled into sources/Domestic.xlsx from the two "
            "censuses and neither census's tables were kept. The 2023 Table 1 workbooks are "
            "now held (data/raw/pbs/population_census_2023/) and print the 2017 district "
            "totals beside the 2023 ones, so both endpoints can be re-read from a held PBS "
            "file; the 2017 census's own tables were not found at the publisher",
        "how_to_obtain": "PBS census 2017 district tables; the held 2023 Table 1 reprints "
                         "the totals"},
    "pso_premier_euro5_page": {
        "access_class": "free-to-read",
        "gap_id": "road-fuel-sulfur",
        "data_files": "data/activity/transport/fuel_sulfur_by_year.csv;"
                      "data/activity/industry/fuel_sulfur_evidence.csv",
        "exact_url": "https://psopk.com/en/fuels/retail-fuels/premier-euro-5",
        "access_date_utc": "2026-08-08",
        "page_table_coords": "the sentence that the Euro-5 switch took petrol from 500 ppm "
                             "to 10 ppm",
        "retrieval_script": "scripts/fetch_cited_documents.py",
        "sha256": "",
        "legal_reason_for_non_retention":
            "a live product page built in the reader's browser: the served bytes are held "
            "and do not contain the sentence, and no archive capture does. The two Dawn "
            "articles the same file cites ARE held with their content",
        "how_to_obtain": "open the address in a browser and save the rendered page to "
                         "data/raw/web_snapshots/pso/"},
    "ffbl_public_page": {
        "access_class": "dead-with-official-alternative",
        "gap_id": "ippu-producer-annual-reports",
        "data_files": "data/activity/ippu/chemical_plant_activity.csv",
        "exact_url": "https://www.ffbl.com/",
        "access_date_utc": "2026-08-08",
        "page_table_coords": "one row naming the Fauji Fertilizer Bin Qasim ammonia plant; "
                             "it carries no production figure",
        "retrieval_script": "scripts/fetch_cited_documents.py",
        "sha256": "",
        "legal_reason_for_non_retention":
            "the company merged into Fauji Fertilizer and its site no longer answers; the "
            "archive's captures are an empty shell. Every other document this file cites is "
            "held: the Fatima, Agritech and Engro reports as cited through PSX, the Fatima "
            "2022 results, the two CDM project pages and the FFC page, which lists the "
            "pre-merger FFBL reports",
        "how_to_obtain": "ffc.com.pk, investor relations, FFBL pre-merger reports"},
    "firms_area_api_responses": {
        "access_class": "openly-licensed",
        "gap_id": "firms-source",
        "data_files": "data/gis/manual/firms_fire.csv",
        "exact_url": "https://firms.modaps.eosdis.nasa.gov/api/area/",
        "access_date_utc": "2026-08-11",
        "page_table_coords": "VIIRS S-NPP standard processing, box 60.5-77.5 E by "
                             "23.5-37.5 N, nine burning seasons in five-day windows",
        "retrieval_script": "src/pkinv/sectors/agriculture/gis/fetch_firms.py",
        "sha256": "2d26b95ad76bccc049ccba9ec9fc277143df631728cf08063127966d88079a59",
        "legal_reason_for_non_retention":
            "open data, no legal bar. The fetcher kept five columns of each detection and "
            "discarded the responses; asking again needs a personal MAP_KEY that this "
            "environment does not hold (the fetcher now keeps every response). Held "
            "witness: NASA's keyless country-year files for Pakistan, 2015 to 2024, in "
            "which all 523,936 detections dated inside the fetched windows are present in "
            "the fire layer. The part of the box outside Pakistan has no held witness",
        "how_to_obtain": "FIRMS_MAP_KEY=... python3 -m "
                         "pkinv.sectors.agriculture.gis.fetch_firms --backfetch-all"},
}

NOT_RETAINED_FIELDS = ("source_id", "access_class", "gap_id", "data_files", "exact_url",
                       "access_date_utc", "page_table_coords", "retrieval_script",
                       "sha256", "legal_reason_for_non_retention", "how_to_obtain")
NOT_RETAINED_OUT = resolve(os.path.join(DATA, "not_retained_register.csv"), root=ROOT)


def write_not_retained():
    """Emit the not-retained register beside the source register."""
    with open(NOT_RETAINED_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=NOT_RETAINED_FIELDS)
        w.writeheader()
        for source_id in sorted(NOT_RETAINED):
            row = dict(NOT_RETAINED[source_id])
            row["source_id"] = source_id
            w.writerow(row)
    print("Not-retained register -> %s  (%d source documents)"
          % (NOT_RETAINED_OUT, len(NOT_RETAINED)))


GEOMETRY_EXTRAS = (
    "data/gis/osm_building_fraction_267x340.npy",
    "data/gis/roads/pak_road_density_267x340.npy",
    "data/gis/rail/pak_rail_network.geojson",
    # rc47 Wave 6: the COD-AB acquisition - the bundle and its consumed ADM2 member
    "data/gis/cod_ab/pak_admin_boundaries.geojson.zip",
    "data/gis/cod_ab/pak_admin2.geojson",
)


def _activity_csvs():
    """Every CSV the register must cover, plus the named geometry extras.

    Match the established logical source families against catalog bindings, then
    read their current sector-folder locations. The register keeps those logical
    identities so relocation cannot create new sources or erase prior judgements.
    Disk enumeration remains available for an older checkout without the catalog.
    """
    found = []
    prefixes = ("data/activity/", "data/nfdc/", "data/ml/", "data/gis/", "data/pbs_census/",
                "data/district_records/", "data/gleam/", "data/gmw/")
    for asset in asset_catalog(root=ROOT):
        logical = asset["legacy_path"]
        if ((logical.startswith(prefixes) and logical.endswith(".csv")) or
                logical == "data/nfdc_offtake.csv" or logical in GEOMETRY_EXTRAS):
            found.append(os.path.join(ROOT, asset["path"]))
    for base in (os.path.join(DATA, "activity"), os.path.join(DATA, "nfdc"),
                 os.path.join(DATA, "ml"), os.path.join(DATA, "gis"),
                 # rc37: the four transcription directories the deposit manifest already
                 # calls "compilations, transcribed" and the register never scanned
                 os.path.join(DATA, "pbs_census"), os.path.join(DATA, "district_records"),
                 os.path.join(DATA, "gleam"), os.path.join(DATA, "gmw")):
        for dirpath, _dirs, files in os.walk(base):
            for name in files:
                if name.endswith(".csv"):
                    found.append(os.path.join(dirpath, name))
    loose = os.path.join(DATA, "nfdc_offtake.csv")
    if os.path.exists(loose):
        found.append(loose)
    for rel in GEOMETRY_EXTRAS:
        full = os.path.join(ROOT, rel)
        if os.path.exists(full):
            found.append(full)
    return sorted(set(found))


def build():
    keep = _existing()
    assets = {row["legacy_path"]: row for row in asset_catalog(root=ROOT)}
    known = {row[key] for row in assets.values() for key in ("asset_id", "legacy_path", "path")}
    rows = []
    for full in _activity_csvs():
        rel = legacy_path(full, root=ROOT)
        short = rel.replace("data/activity/", "")
        # Precedence (rc29): CLASSIFIED is the judgement ledger and wins for any
        # row it names - a re-audit is recorded there, reviewed in the script's
        # diff, and flows to the CSV on regeneration. The committed CSV is
        # preserved only for rows CLASSIFIED does not cover, so a hand judgement
        # made directly in the CSV survives, but a stale CSV row can no longer
        # outvote a corrected entry here (which is how ten rows stayed
        # not-archived after their documents had been archived).
        if rel in keep and short not in CLASSIFIED:
            rows.append(keep[rel])
            continue
        source = _primary_source(full)
        asset = assets.get(rel, {})
        references = [ref for ref in asset.get("source_refs", "").split(";") if ref]
        if short not in CLASSIFIED and asset.get("maintained") == "yes" and references and set(references) <= known:
            rows.append({"data_file": rel,
                         "primary_source": "Consolidated observations from " + "; ".join(references),
                         "archival_state": "derived", "archived_path": "", "gap_id": "",
                         "note": "Maintained source facts; compatibility views preserve the historical source identities.",
                         "licence_status": "derived-from-listed-sources"})
            continue
        if short in CLASSIFIED:
            state, key, why = CLASSIFIED[short]
            prior = keep.get(rel, {})
            rows.append({
                "data_file": rel,
                # Committed first: for derived rows the committed value is a
                # curated description, and the column sniff would replace it with
                # whatever string happens to dominate the file ("SUKKUR", "0.0").
                "primary_source": prior.get("primary_source") or source or why,
                "archival_state": state,
                "archived_path": key if state == "archived" else "",
                "gap_id": key if state == "not-archived" else "",
                "note": why,
                # The licence judgement lives in the CSV row (there is no licence
                # in CLASSIFIED); carry it across so a state flip never resets it.
                "licence_status": prior.get("licence_status", "undetermined")})
            continue
        family = _guess_family(source)
        rows.append({
            "data_file": rel,
            "primary_source": source,
            "archival_state": "archived" if family else "REVIEW",
            "archived_path": family,
            "gap_id": "",
            "note": "" if family else "seeded by script; classify before committing",
            # What may lawfully be redistributed. Filled only where the source's own
            # identity settles it; a new file starts undetermined rather than guessed -
            # a plausible licence is a fabricated one.
            "licence_status": "undetermined",
        })
    return sorted(rows, key=lambda r: r["data_file"])


def main():
    rows = build()
    if "--check" in sys.argv:
        unreviewed = [r["data_file"] for r in rows if r["archival_state"] == "REVIEW"]
        print("%d activity files, %d awaiting classification" % (len(rows), len(unreviewed)))
        for f in unreviewed[:40]:
            print("  ", f)
        return 1 if unreviewed else 0
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    states = collections.Counter(r["archival_state"] for r in rows)
    print("Source register -> %s" % OUT)
    print("  %d activity files: %s" % (len(rows), dict(states)))
    write_not_retained()
    return 0


if __name__ == "__main__":
    sys.exit(main())

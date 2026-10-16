#!/usr/bin/env python3
"""Consolidate the campaign's lane outputs into the six top-level deliverables.

    python3 research_campaign/build_campaign_tables.py

WHY A SCRIPT. The prompt names six files as this campaign's handoff surface and says the
detailed tables live beneath lane folders and are REFERENCED from these. Five of the six
were headers only at hour 15, which is the one defect in a campaign's own record that no
amount of good work elsewhere repairs: a reader arriving at the handoff would have found
nothing. They are built here rather than typed so that the mechanical parts - every
product's digest, every lane row - come from the artefacts themselves, and only the
JUDGEMENTS are literals in this file, where they can be read and disputed.

WHAT IS CONSOLIDATED FROM WHERE.
  source_register.csv       research_campaign/land/sources.csv (19 documents the land
                            lane acquired, schema mapped) + DIRECT_SOURCES below, the
                            documents this coordinator read itself with their exact
                            locators.
  comparison_results.csv    research_campaign/validation_figures/matched_comparison.csv
                            (23 external comparisons) + COMPARISONS below, the ones
                            established in the coordinator's own rounds.
  completeness.csv          research_campaign/missing_sources/coverage_matrix.csv (84
                            category rows, schema mapped) + CATEGORY_UPDATES below, where
                            this campaign changed what a category's row should say.
  claim_evidence.csv        CLAIMS below. One row per headline claim, each naming the
                            command that produced it and where its wording now lives, so
                            a claim with no published home is visible as such.
  product_manifest.json     the artefacts this campaign created or changed, with the
                            digest the release manifest records for each - so the manifest
                            cannot drift from the release it describes.

WHAT IS NOT HERE. FINAL_REPORT.txt is written at the deadline, from this and from
DECISIONS.txt. Nothing in this script computes a scientific result: every number it
carries was produced and recorded by a lane or a round, and this file only moves it.
"""
import csv
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))


def read(path, comments=True):
    full = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if not os.path.exists(full):
        return []
    with open(full, encoding="utf-8") as handle:
        lines = (line for line in handle if not (comments and line.startswith("#")))
        return list(csv.DictReader(lines))


def write(path, fieldnames, rows, banner=None):
    full = os.path.join(HERE, path)
    with open(full, "w", newline="", encoding="utf-8") as handle:
        for line in banner or []:
            handle.write("# %s\n" % line)
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


# --------------------------------------------------------------------------- sources
# The documents the coordinator read itself, with the locator each reading actually used.
# A locator here is what a reader needs to find the figure, not a bibliographic citation.
DIRECT_SOURCES = (
    ("SRC-CRT-2022", "Pakistan Common Reporting Tables (CRT), 2022 inventory",
     "Government of Pakistan / UNFCCC", "2024 submission",
     "https://unfccc.int/documents/645241", "2026-10-05", "CY2022",
     "IPPU-PAK-CRT.xlsx sheet Table2(II).B-Hs2, cells B54/E54/H54/K54 (2.F.1.a "
     "commercial refrigeration: species, operating stock, product-life factor, emissions)",
     "t of substance", "unfccc-public", "sources/Aviation/PAK_CRT_2024.zip",
     "read in place; four cells transcribed into the F-gas leak-rate screening",
     "T-MISS-2: the official 2.F reading the bank is compared with", "held"),
    ("SRC-BTR1", "Pakistan First Biennial Transparency Report",
     "Government of Pakistan / UNFCCC", "2024", "https://unfccc.int/documents/645241",
     "2026-10-05", "CY2020-21",
     "sources/UNFCCC/btr1_2024.txt line 843 (1A3d1 International Marine Bunkers); "
     "lines 769-900 for the national inventory table",
     "Mt CO2e", "unfccc-public", "sources/UNFCCC/btr1_2024.txt",
     "55 rows transcribed with line citations into "
     "data/shared/evidence/btr1_national_inventory.csv",
     "T-VAL-BTR comparator; T-BUNKERS the 0.040 Mt marine-bunkers contradiction", "held"),
    ("SRC-IPCC-V3-CH7", "2006 IPCC Guidelines Volume 3 Chapter 7, Emissions of "
     "Fluorinated Substitutes for Ozone Depleting Substances", "IPCC", "2006",
     "https://www.ipcc-nggip.iges.or.jp/public/2006gl/", "2026-09-11", "n/a",
     "Table 7.9 pp. 7.51-7.52, the operation-emission column for eight refrigeration "
     "and air-conditioning sub-applications",
     "percent of charge per year", "public-licence",
     "data/raw/ipcc/ipcc2006_V3_7_Ch7_ODS_Substitutes.pdf",
     "eight sub-application bands transcribed into the leak-rate screening",
     "T-MISS-2: the bands the bank's single rate is adjudicated against", "held"),
    ("SRC-OCAC-ANNUAL", "OCAC annual Oil Report / Sectoral Sales of Energy Products",
     "Oil Companies Advisory Council", "FY2016-17 to FY2024-25 (nine editions)",
     "https://www.ocac.org.pk/", "2026-08 (held)", "FY2016-17..FY2024-25",
     "2 pages per edition. FY2016-17 to FY2019-20 head both pages 'SECTORAL SALES / "
     "CONSUMPTION OF POL PRODUCTS' and separate them below (PAKISTAN - ENERGY PRODUCTS / "
     "- NON-ENERGY PRODUCTS); from FY2020-21 the titles split. Energy on page 1, "
     "non-energy on page 2",
     "M. Tons", "not-established", "sources/Aviation/ocac_annual/OCAC_FY*.pdf",
     "pointers recovered and written to data/catalog/source_documents.csv; no re-extraction",
     "T-CITATION-POINTERS: seven OCAC extractions located", "held"),
    ("SRC-OCAC-MONTHLY", "OCAC monthly Sectoral Sales of Energy Products",
     "Oil Companies Advisory Council", "July 2021 onward (48 editions)",
     "https://www.ocac.org.pk/", "2026-08 (held)", "202107 onward",
     "18 pages per edition: pages 1-9 energy products for AREA-PAKISTAN, SINDH, PUNJAB, "
     "KHYBER PAKHTUN KHAWA, BALOCHISTAN, GILGIT BALTISTAN, AZAD KASHMIR, FATA, KARACHI in "
     "that order; pages 10-18 the same nine areas for non-energy",
     "M. Tons", "not-established", "sources/Aviation/ocac_monthly/OCAC_*.pdf",
     "pointers recovered; no re-extraction",
     "T-CITATION-POINTERS: the provincial and monthly OCAC extractions located", "held"),
    ("SRC-PBS-MINERALS", "Minerals Production Data", "Pakistan Bureau of Statistics",
     "FY2016-17 to FY2023-24 (eight editions)", "https://www.pbs.gov.pk/",
     "2026-09 (held)", "FY2016-17..FY2023-24",
     "Four PDFs carry one running-head Table 'MINERALS PRODUCTION DATA <edition> "
     "( unit MT )' over 8 / 6 / 10 / 1 pages (2021-22 marked (F), 2022-23 (R)), columns "
     "S.NO / Name of Mineral / PROVINCES / twelve months / Total. Four workbooks carry no "
     "table title and the SHEET is the pointer: '17-18','Sheet1','merging','Quarterly',"
     "'final' (2017-18); 'Original' (2018-19, 2019-20); 'Electricity generation' and "
     "'mineral production' (2020-21)",
     "M. Tons", "not-established", "data/raw/pbs/minerals/pbs_minerals_*.pdf|xlsx",
     "pointers recovered; the FY2021-22 coal block re-read to prove the province "
     "attribution identity (four provinces = printed Total in all twelve months)",
     "T-POINTERS-PBS and T-MINERALS-MECHANISM", "held"),
    ("SRC-EXPLORER-RC59", "PakEmis Explorer served release 1.0.0rc59 (semantic layer)",
     "this project (served copy)", "1.0.0rc59, fetched from commit 5915e0c0",
     "n/a - local serving repository", "2026-10-05", "FY2015-16..FY2023-24",
     "outputs/semantic/fact_adm1_year.csv, fact_adm2_year.csv, fact_adm2_month.csv, "
     "fact_monthly.csv and semantic_release.json of the served directory",
     "Mt CO2e AR5", "own-work",
     "SERVING REPOSITORY pakemis-explorer, not this one: its "
     "data/releases/1.0.0rc59/ directory",
     "compared against this repository's tree; no bytes copied in",
     "T-AGENT-3 and T-VINTAGE-AXES: the vintage divergence", "read-not-retained"),
)
SOURCE_FIELDS = ("source_id", "title", "publisher", "edition", "url", "retrieved_utc",
                 "activity_period", "locator", "units", "licence_access",
                 "local_identity", "transformations", "used_for", "status")


def sources():
    rows = []
    for index, row in enumerate(read("research_campaign/land/sources.csv"), 1):
        rows.append({
            "source_id": "SRC-LAND-%03d" % index,
            "title": row["title"], "publisher": row["publisher"],
            "edition": row["edition_or_version"], "url": row["url"],
            "retrieved_utc": row["retrieval_date_utc"],
            "activity_period": row["activity_period_covered"],
            "locator": row["page_or_table_locator"], "units": row["units"],
            "licence_access": row["licence_or_access_status"],
            "local_identity": row["local_file_path"] or (row["sha256"] or "")[:16],
            "transformations": "see research_campaign/land/official_account.csv",
            "used_for": row["used_for"], "status": row["acquisition_outcome"],
        })
    for values in DIRECT_SOURCES:
        rows.append(dict(zip(SOURCE_FIELDS, values)))
    # The campaign's own instructions, kept from the stub: the authorization limits are a
    # source like any other and the register is where a reader checks what was permitted.
    rows.append({
        "source_id": "SRC-PROMPT",
        "title": "PakEmis 24-hour campaign instructions", "publisher": "user",
        "edition": "2026-10-05", "url": "", "retrieved_utc": "2026-10-05T02:58:36Z",
        "activity_period": "n/a", "locator": "PakEmis_24_hour_prompt.txt",
        "units": "n/a", "licence_access": "private",
        "local_identity": hashlib.sha256(
            open(os.path.join(ROOT, "PakEmis_24_hour_prompt.txt"), "rb").read()
        ).hexdigest()[:16],
        "transformations": "none",
        "used_for": "campaign scope and authorization limits", "status": "held",
    })
    return sorted(rows, key=lambda r: r["source_id"])


# ----------------------------------------------------------------------- comparisons
# The comparisons established in the coordinator's own rounds. independence_class says
# whether the comparator shares inputs with PakEmis, because a comparison between two
# readings of one source is a transcription check and not a validation.
COMPARISONS = (
    ("CMP-FOREST-SIGN", "-4.107 (FAOSTAT forest land)", "Pakistan CRT 2022 forest land",
     "+28.44 as printed", "1.0.0rc59", "CY2022",
     "forest land, LULUCF - outside every total",
     "CO2", "AR5", "32.55", "n/a - the signs oppose",
     "same year, same category, both whole-gas CO2",
     "LULUCF excluded from the inventory on both sides",
     "independent-sources", "The two available accounts disagree in DIRECTION, not "
     "magnitude, so no land component can be built without choosing one. FAOSTAT's own "
     "columns carry the mechanism: area rising at exactly +20.786 kha/yr for 2020-2023 "
     "(interpolation) and net forest conversion exactly 0.000 kha from 2020",
     "outputs/pakemis_forest_flux_adjudication.csv"),
    ("CMP-FOREST-CIRCULAR", "-3.52 (this project's exploratory land module)",
     "FAOSTAT net forest conversion", "0.000 kha", "1.0.0rc59", "recent years",
     "forest land", "CO2", "AR5", "n/a", "n/a",
     "the module's deforestation_area_ha_yr is SET from the FAOSTAT zero",
     "n/a", "shared-input", "NOT a corroboration: the module's sink is FAOSTAT's zero "
     "read a second time, and its stated justification ('afforestation offsets gross "
     "loss') is contradicted by the CRT's own gross pair - losses 14868.348 kt C against "
     "gains 7113.083, a ratio of 2.09",
     "outputs/pakemis_forest_flux_adjudication.csv"),
    ("CMP-FGAS-CRT", "5.85418 (species-resolved HFC bank)",
     "Pakistan CRT 2022 category 2.F", "0.00294", "1.0.0rc59", "FY2023-24 vs CY2022",
     "2.F product uses as substitutes for ODS", "HFC", "AR5", "5.85124", "1991x",
     "none attempted - the comparator is a near-zero filing",
     "2.F contributes zero to every PakEmis total; the bank is a screening lane",
     "independent-sources",
     "The official filing is ONE species (HFC-23, 0.236955 t) entered as exactly 1% of a "
     "declared 23.6954857 t operating stock at 2.F.1.a commercial refrigeration, every "
     "other species and sub-category NE or NO. HFC-23 is an HCFC-22 by-product, not a "
     "commercial refrigerant, so the defect is the SPECIES and the 1% factor is "
     "admissible where it was filed",
     "outputs/pakemis_fgas_leak_rate_adjudication.csv"),
    ("CMP-FGAS-BTR", "5.85418 (species-resolved HFC bank)",
     "Pakistan BTR1 category 2.F", "0", "1.0.0rc59", "FY2023-24 vs CY2020-21",
     "2.F", "HFC", "AR5", "5.85418", "n/a - the comparator is zero",
     "none - a zero is not a magnitude to harmonise",
     "2.C, 2.E and 2.G are also zero in BTR1", "independent-sources",
     "Pakistan's two most recent official submissions disagree about whether the category "
     "EXISTS: the CRT books 0.00294 Mt and the BTR books zero. That is not a boundary "
     "difference", "outputs/pakemis_btr_comparison.csv"),
    ("CMP-FGAS-TABLE79", "8.0 %/yr (bank refrigeration stratum)",
     "IPCC Table 7.9 operation-emission bands", "0.1-0.5 (domestic) .. 15-50 (transport)",
     "1.0.0rc59", "n/a", "refrigeration leak rate", "HFC", "n/a", "n/a", "16x to 80x "
     "above domestic refrigeration's whole band",
     "the stratum lumps five sub-applications whose bands share no common value",
     "n/a", "independent-sources",
     "For two of the five sub-applications the single rate is not uncertain but "
     "inadmissible. The band envelope moves the operating channel 155x (0.01329 to "
     "2.06204 Mt) while moving the stratum total only 2.9x, because with zero recovery "
     "the gas not leaked in operation is emitted at retirement - the rate decides WHEN, "
     "not whether", "outputs/pakemis_fgas_leak_rate_adjudication.csv"),
    ("CMP-VINTAGE-ADM1", "220.768318 (this tree, Punjab FY2015-16)",
     "the same product in the served 1.0.0rc59", "220.114574", "1.0.0rc59 (both)",
     "FY2015-16", "province total, all streams", "CO2e", "AR5", "0.653744", "0.296%",
     "identical product, identical label, identical result_row_ids",
     "none", "same-release-two-vintages",
     "A version string is not a pin. All NINE national totals agree to nine decimal "
     "places (FY2023-24 469.638224 on both sides) while the provincial allocation differs "
     "by 11.87 Mt absolute and exactly 0.000000 net - a declared furnace-oil provincial "
     "re-base that landed after the label was published. Every guard this project has is "
     "a guard on a period total, so nothing could see it",
     "outputs/pakemis_release_axis_fingerprints.csv"),
    ("CMP-VINTAGE-MONTHLY", "the monthly national table in this tree",
     "the same table in the served 1.0.0rc59", "36 cells differ", "1.0.0rc59 (both)",
     "within fiscal years", "national monthly, electricity and heat production",
     "CO2e", "AR5", "net exactly 0.000000000", "n/a",
     "identical product and label", "none", "same-release-two-vintages",
     "The same blind spot on the TIME axis: the within-year shape of power generation was "
     "re-based while every annual total it sums to was conserved, so fact_annual's "
     "fingerprint is byte-identical and the monthly one is not",
     "outputs/pakemis_release_axis_fingerprints.csv"),
    ("CMP-MINERALS-CONTROL", "the shipped minerals panel",
     "the parse's own closing group control", "nine cells disagree", "1.0.0rc59",
     "FY2015-16..FY2023-24", "PBS minerals production by province", "n/a", "n/a",
     "limestone FY2016-17 ships 6.9%; natural gas FY2020-21 ships 230.8%", "see left",
     "the control sums the rows the parser BUFFERED; the panel ships a different set",
     "n/a", "self-control",
     "A control that passes while its subject is short is not a control. For FY2021-22 "
     "coal it closes to the unit (9,678,139 both sides) while the panel holds 4,072,263. "
     "The cause is proved: PBS centres the mineral's name cell across its five province "
     "rows, so a layout extraction puts the name on the middle line and the parser loses "
     "the two rows above it - Punjab + Sindh + KPK + Balochistan equals the printed Total "
     "in EVERY one of the twelve months",
     "outputs/pakemis_minerals_panel_screening.csv"),
    ("CMP-MINERALS-SHAPE", "the served crude-oil profile, FY2021-22",
     "a complete-province shape from the years that have one", "78.76% in one month",
     "1.0.0rc59", "FY2021-22", "upstream oil timing", "n/a", "n/a",
     "up to 50 pp per month", "n/a",
     "both normalised to twelve shares summing to one", "n/a", "self-control",
     "The panel holds Balochistan alone and covers() asks for twelve months rather than "
     "for the country, so the profile is served at T2 'observed'. For natural gas the "
     "same defect costs at most 1.1 pp in a month because Pakistani gas has almost no "
     "season - that bound is what separates a tolerable case from this one",
     "outputs/pakemis_minerals_panel_screening.csv"),
)
# The stub's header carried fifteen columns and no pointer to the product that holds the
# comparison. A reader needs that pointer - a comparison they cannot open is an assertion -
# so the schema gains source_product. My first assembly silently DROPPED it by slicing the
# literal tuples to the old width, which is the quiet kind of loss this campaign keeps
# recording: the row still looked complete.
COMPARISON_FIELDS = ("comparison_id", "pakemis_value", "comparator", "comparator_value",
                     "release", "period", "boundary", "gas", "gwp", "absolute_diff",
                     "relative_diff", "harmonization", "exclusions",
                     "independence_class", "interpretation", "source_product",
                     "figures_reproducible")

# Whether a reader can find this row's FIGURES in the product it names. Applying the
# claim table's check here flagged 26 of 32 rows, for three different reasons, and
# flattening them into one count would have been as misleading as the silence it replaced:
#   yes                      every figure with two or more decimals is in the product
#   derived-in-this-table    the row states a difference or ratio that no product prints,
#                            computed from two values that are both published
#   external-copy            measured against the served release, which this repository
#                            does not hold, so no product here can carry it
#   lane-precision           inherited from a worker lane at the lane's own precision,
#                            above what its product prints; the lane's tables beneath
#                            research_campaign/ carry the figures as stated
# The guard holds the vocabulary closed and checks every `yes` row for real.
REPRODUCIBLE = {
    "CMP-FGAS-CRT": "derived-in-this-table",
    "CMP-FGAS-BTR": "derived-in-this-table",
    "CMP-VINTAGE-ADM1": "external-copy",
    "CMP-VINTAGE-MONTHLY": "external-copy",
    "CMP-MINERALS-SHAPE": "derived-in-this-table",
}


def comparisons():
    rows = []
    for row in read("research_campaign/validation_figures/matched_comparison.csv"):
        rows.append({
            "comparison_id": row["comparison_id"],
            "pakemis_value": row["pakemis_value"], "comparator": row["comparator"],
            "comparator_value": row["comparator_value"],
            "release": row["comparator_release"] or "1.0.0rc59",
            "period": "%s vs %s" % (row["pakemis_period"], row["comparator_period"]),
            "boundary": "%s / %s" % (row["category"], row["boundary"]),
            "gas": row["gas"],
            "gwp": "%s vs %s" % (row["gwp_vintage_pakemis"],
                                 row["gwp_vintage_comparator"]),
            "absolute_diff": row["absolute_diff"],
            "relative_diff": row["relative_diff_pct"],
            "harmonization": row["harmonization"], "exclusions": row["exclusions"],
            "independence_class": row["independence_class_code"],
            "interpretation": row["interpretation"],
            "source_product": row["source_product"],
            "figures_reproducible": "lane-precision",
        })
    for values in COMPARISONS:
        if len(values) != len(COMPARISON_FIELDS) - 1:
            raise SystemExit("comparison %s has %d fields against %d authored columns "
                             "(figures_reproducible is filled from REPRODUCIBLE)"
                             % (values[0], len(values), len(COMPARISON_FIELDS) - 1))
        row = dict(zip(COMPARISON_FIELDS, values + ("",)))
        row["figures_reproducible"] = REPRODUCIBLE.get(row["comparison_id"], "yes")
        rows.append(row)
    return rows


# ---------------------------------------------------------------------- completeness
# Where this campaign changed what a category's row should say. Each entry REPLACES the
# lane's row for that (code, gas) and says why.
CATEGORY_UPDATES = {
    ("2.F", "HFC"): {
        "campaign_status": "SCREENING, leak rate adjudicated",
        "materiality": "5.85418 Mt CO2e AR5 (species bank, screening); the official "
                       "filing is 0.00294 and BTR1 books zero",
        "open_data_strength": "strong for supply (Article-7, Comtrade), absent for "
                              "pre-charged equipment imports (REQ-NOU-01, not sent)",
        "overlap_risk": "none - 2.F contributes zero to every total",
        "work_needed": "a domestic/commercial refrigeration split; IPCC Table 7.9 "
                       "excludes the bank's single 8%/yr rate for two of the five "
                       "sub-applications it lumps",
        "owner": "coordinator (T-MISS-2)",
        "notes": "the official reading is one species misfiled at 2.F.1.a; the leak rate "
                 "decides WHEN not whether (operating channel 155x, total 2.9x)",
    },
    ("1.A.3.d", "CO2/CH4/N2O"): {
        "campaign_status": "NE, absence re-argued",
        "materiality": "0.040 Mt CO2e (Pakistan's own BTR1, CY2020-21) against roughly "
                       "3 Mt if built on the OGRA Overseas/Export line",
        "open_data_strength": "port bunkering records not acquired",
        "overlap_risk": "high if taken from the OGRA export line, which is cargo",
        "work_needed": "Karachi Port Trust / Port Qasim bunkering records",
        "owner": "coordinator (T-BUNKERS)",
        "notes": "the absence had rested on 'Pakistan had no formal bunkering market "
                 "until 2026'; a market's absence is not the absence of fuel delivered, "
                 "and the national submission books some. Repaired in four places",
    },
    ("LULUCF forest land", "CO2"): {
        "campaign_status": "SCREENING, excluded from every total",
        "materiality": "the two available accounts differ by 32.543 Mt and in SIGN",
        "open_data_strength": "FAOSTAT carries no annual information for the recent "
                              "years (area interpolated at exactly +20.786 kha/yr)",
        "overlap_risk": "n/a - outside the reported boundary",
        "work_needed": "a Pakistani forest-area time series on a stated definition; the "
                       "FRA 5 m and national 2 m-plus-legal stocks differ by 24%",
        "owner": "coordinator (T-LAND-2)",
        "notes": "the exploratory module's -3.52 Mt sink is FAOSTAT's zero read twice, "
                 "and the CRT contradicts its justification (losses 2.09x gains)",
    },
}
COMPLETENESS_FIELDS = ("ipcc_code", "category", "gas", "notation_key", "campaign_status",
                       "materiality", "open_data_strength", "overlap_risk", "work_needed",
                       "owner", "notes")


def completeness():
    rows, seen = [], set()
    for row in read("research_campaign/missing_sources/coverage_matrix.csv"):
        key = (row["ipcc_code"], row["gas"])
        update = CATEGORY_UPDATES.get(key)
        seen.add(key)
        rows.append({
            "ipcc_code": row["ipcc_code"], "category": row["category"],
            "gas": row["gas"], "notation_key": row["notation_key"],
            "campaign_status": (update or row)["campaign_status"],
            "materiality": (update["materiality"] if update
                            else row["plausible_magnitude_range"]),
            "open_data_strength": (update or row)["open_data_strength"],
            "overlap_risk": (update or row)["overlap_risk"],
            "work_needed": (update or row)["work_needed"],
            "owner": (update["owner"] if update else "worker:missing-sources"),
            "notes": (update["notes"] if update else row["notes"]),
        })
    for key, update in sorted(CATEGORY_UPDATES.items()):
        if key in seen:
            continue
        rows.append(dict({"ipcc_code": key[0], "category": key[0], "gas": key[1],
                          "notation_key": "NE"}, **update))
    return rows


# ---------------------------------------------------------------------- claim/evidence
# One row per headline claim this campaign makes. wording_location is deliberately blunt:
# a claim with no published home reads "not in any manuscript", which is the state a
# reader should be able to see without inferring it.
def _power_coal_ch4_ledger_cells():
    """(emission Gg, station coal mass kt) as the power activity-factor ledger prints them.

    rc68: the ledger books power coal as station mass times rank NCV, so the row no longer
    prints a single TOE-derived TJ figure; the mass is what it prints.

    Read rather than typed: tests/test_campaign_handoff.py scans numerical_output for any
    figure with two or more decimals and checks each against the product the claim names,
    so a retired value fails loudly and a hard-coded live one goes stale silently. Both of
    these moved with the 2026-10-07 power coal re-base.
    """
    import csv as _csv
    path = os.path.join(ROOT, "outputs", "power_activity_factor_ledger.csv")
    with open(path, encoding="utf-8") as handle:
        for row in _csv.DictReader(l for l in handle if not l.startswith("#")):
            if row["subitem"] == "Coal CH4":
                mass = row["activity"].split("power:Coal station consumption mass=")[1]
                mass = "%.2f" % float(mass.split(" kt")[0])
                return (row["emissions_Gg"], mass)
    raise SystemExit("no Coal CH4 row in the power activity-factor ledger")


CLAIMS = (
    ("CE-LAND-002",
     "The two available accounts of Pakistan's forest flux disagree in SIGN, so no land "
     "component can be built without choosing one",
     "forest land, CY2022, LULUCF - outside every total",
     "+28.44 Mt CO2 as the submission PRINTS it against -4.107 (FAOSTAT), gap 32.55 - "
     "and the printed figure is corroborated by reconstructing it from the CRT's own "
     "gross pair, 14868.348 kt C of losses against 7113.083 of gains, which nets 28.436",
     "sources/Aviation/PAK_CRT_2024.zip; FAOSTAT extract under data/raw/land/",
     "python3 scripts/build_forest_flux_adjudication.py",
     "SUPPORTED; published as a screening, nothing in a total",
     "paper_national/versions/v1/sections/12_limitations.tex",
     "the gap is priced, not resolved; a Pakistani area series on a stated definition "
     "would resolve it"),
    ("CE-LAND-003",
     "This project's own exploratory land sink is not independent of FAOSTAT, and its "
     "stated justification is contradicted by Pakistan's own submission",
     "the exploratory LULUCF module, recent years",
     "deforestation_area_ha_yr = 0 taken from FAOSTAT; CRT gross losses 14868.348 kt C "
     "against gains 7113.083, ratio 2.09, netting the printed +28.436 Mt",
     "data/sectors/lulucf/parameters/lulucf_params.csv; the CRT",
     "python3 scripts/build_forest_flux_adjudication.py",
     "SUPPORTED; the contradiction is recorded in the parameter's note and the value is "
     "UNCHANGED, because moving it would move a published exploratory figure",
     "data/sectors/lulucf/parameters/lulucf_params.csv and "
     "paper_national/versions/v1/sections/12_limitations.tex",
     "the module still publishes a sink built on that zero; correcting it is a declared "
     "decision, not an audit edit"),
    ("CE-FGAS-001",
     "All of Pakistan's reported F-gas category is one species, filed under a "
     "sub-category that species is not used in",
     "category 2.F, CY2022",
     "HFC-23, 0.236954857 t = exactly 1% of a declared 23.6954857 t operating stock, at "
     "2.F.1.a commercial refrigeration; 0.00294 Mt CO2e AR5",
     "PAK_CRT_2024.zip Table2(II).B-Hs2 cells B54/E54/H54/K54",
     "python3 scripts/build_fgas_leak_rate_adjudication.py",
     "SUPPORTED by direct cell reading",
     "papers/ippu/sections/07_discussion.tex",
     "the misfiling is the official record's, not this project's; nothing here corrects it"),
    ("CE-FGAS-002",
     "The bank's single leak rate per stratum is inadmissible for part of what one "
     "stratum lumps, and the rate decides WHEN rather than whether",
     "the species-resolved HFC bank, FY2023-24",
     "refrigeration 8.0%/yr against five IPCC bands spanning 0.1-50 with no common "
     "value; the envelope moves the operating channel 0.01329-2.06204 Mt (155x) and the "
     "stratum total 0.75685-2.19152 (2.9x), with the closing bank 1.959-12.559",
     "IPCC 2006 Vol 3 Table 7.9 pp.7.51-52; outputs/ippu_hfc_species_bank.csv",
     "python3 scripts/build_fgas_leak_rate_adjudication.py",
     "SUPPORTED; the builder re-runs the shipped kernel and refuses if the unmodified "
     "re-run does not reproduce the shipped file",
     "papers/ippu/sections/07_discussion.tex",
     "no parameter changed; a domestic/commercial split nobody holds decides 1.29 Mt"),
    ("CE-REL-001",
     "A version string is not a pin: two self-consistent artefacts labelled 1.0.0rc59 "
     "carry different content",
     "the whole release, as served against as held",
     "all nine national totals identical to nine decimal places; provincial allocation "
     "11.87 Mt absolute, 0.000000 net, over 45 cells",
     "the served 1.0.0rc59 directory against this repository's tree and git history",
     "python3 scripts/build_published_vintages.py; "
     "python3 scripts/build_release_axis_fingerprints.py",
     "SUPPORTED; all 13 published vintages re-hashed out of git, 13/13 reproduce both "
     "digests",
     "paper_national/versions/v1/sections/12_limitations.tex",
     "no version is bumped - minting is a release action and the campaign may not publish"),
    ("CE-REL-002",
     "Every guard on this release's numbers is a guard on a period total, so an "
     "allocation inside one can move unseen - and two did",
     "four disaggregated tables plus two controls",
     "four tables read FINE AXIS ONLY against the published vintage; fact_annual is "
     "unmoved and the air provincial layer moved on both axes",
     "git blobs of every published vintage",
     "python3 scripts/build_release_axis_fingerprints.py",
     "SUPPORTED; the guard asserts the two axes can disagree and that one table shows "
     "them disagreeing and one does not",
     "paper_national/versions/v1/sections/12_limitations.tex",
     "the fingerprints detect a divergence; they do not say which vintage is right"),
    ("CE-LIC-001",
     "The deposit offered 71 ODbL database rows under a CC-BY grant this project cannot "
     "make for them",
     "both facility registries, all releases to date",
     "71 of 12,680 rows licensed odbl-1.0; both files typed own-work",
     "outputs/pakemis_facility_registry.csv licence column; the semantic contract's "
     "odbl_carveouts",
     "python3 -m pkinv.report.deposit_manifest",
     "SUPPORTED and REPAIRED: both now ship mixed-per-row with the per-row counts in the "
     "reason, and the builder fails closed on a stale declaration",
     "paper_national/versions/v1/sections/12_limitations.tex and LICENSE-data",
     "the remaining half is a submission decision - ESSD will not take a primary CC-BY "
     "record containing ODbL-derived tables"),
    ("CE-CITE-001",
     "103 of 122 registered sources where a table pointer is the right notion carry one",
     "the whole source register",
     "103 pointed, 19 unpointed, 80 not-applicable, 9 unverifiable",
     "data/catalog/source_documents.csv and every produced table's own source column",
     "python3 scripts/build_citation_pointer_audit.py",
     "SUPPORTED; OCAC (7) and PBS minerals (3) closed from the held documents",
     "paper_national/versions/v1/sections/12_limitations.tex",
     "19 one-offs remain, each needing its own document read; the gap read 157 before the "
     "ingest layer was checked"),
    ("CE-MIN-001",
     "A monthly profile served as T2 observed puts 78.76% of a year in one month",
     "crude oil, FY2021-22, upstream oil timing",
     "served shares 2.78/2.71/2.55/2.66/2.61/1.11/0.86/0.91/78.76/1.51/1.74/1.81 percent",
     "pkinv.core.pbs_minerals.profile_or_flat over the shipped panel",
     "python3 scripts/build_minerals_panel_screening.py",
     "SUPPORTED at rc67; REPAIRED at rc68 - the parser keeps the vertically centred "
     "province labels, the FY2021-22 oil table holds all four producing provinces, and "
     "the anomalous oil and gas years are served on calendar-day (T4) timing",
     "CHANGELOG.md (1.0.0rc68)",
     "the figures are the rc67 product's, preserved under data/baselines/"
     "rc67_integrated_campaign; the current screening no longer contains them"),
    ("CE-MIN-002",
     "PBS prints all four provinces; the parse loses two, and the parse's own group "
     "control cannot see it",
     "PBS minerals editions, FY2015-16..FY2023-24",
     "FY2021-22 coal: Punjab + Sindh + KPK + Balochistan equals the printed Total in "
     "every one of the twelve months (9,678,139 both sides) while the panel holds "
     "4,072,263 - 42.1%. Nine canonical mineral-years disagree between a CLOSING control "
     "and the shipped panel, from 6.9% to 230.8%",
     "data/raw/pbs/minerals/pbs_minerals_2021_22.pdf page 1",
     "python3 scripts/build_minerals_panel_screening.py",
     "SUPPORTED by an exact twelve-month identity; the mechanism is the vertically "
     "centred name cell",
     "paper_national/versions/v1/sections/12_limitations.tex",
     "the parse is not repaired; the nine cells are declared and ratcheted so a tenth "
     "cannot hide among them"),
    ("CE-ENERGY-002",
     "The power coal CH4 row of the activity-factor ledger shows two factors the engine "
     "does not use and omits the one it does, because the coal CH4 shared group is the "
     "only fuel with no per-sector binding",
     "outputs/power_activity_factor_ledger.csv, the power coal CH4 stream",
     # Both figures are READ from the ledger - see _power_coal_ch4_ledger_cells above.
     "the row prints ef:ind_coal_ch4=10.0 and ef:res_ch4_coal=300.0 beside an emission of "
     "%s Gg on %s kt of station coal at rank NCVs, which is 1 kg/TJ - the registry's "
     "pow_ch4_coal"
     % _power_coal_ch4_ledger_cells(),
     "data/shared/parameters/emission_factors.csv and "
     "data/shared/parameters/parameter_scope.csv",
     "read the ledger row, then the registry, then the scope file's analogous bindings",
     "SUPPORTED; the analogues exist for oil, bagasse, wood, charcoal and liquid fuels "
     "and coal has none",
     "research_campaign/DECISIONS.txt D084; not in any manuscript",
     "NOT FIXED: that file declares which component rows a shared parameter multiplies, so "
     "it drives the uncertainty engine's correlation structure and a new row could move "
     "published uncertainty figures. A declared decision, specified to one line"),
    ("CE-CONTROL-SWEEP",
     "Of the ten shipped controls that publish a closure verdict, nine compare the row "
     "that ships and one compares an aggregate the parser assembled - and that one is the "
     "one that fails to describe its subject",
     "every outputs/*.csv carrying a closes / closed / agrees / reconciles column",
     "9 per-row controls (PBS QIM item-years, both CRT reproductions, the OCAC direct "
     "edition cross-check, the claim matrix, the national uncertainty decomposition, the "
     "FAO crop calendar, the waste parameter MC, the aviation reconciliation factor) "
     "against 1 per-group control (PBS minerals), which disagrees with its own panel in "
     "nine canonical mineral-years",
     "the shipped products and their builders",
     "column sweep over outputs/*.csv, then the builder of each control read",
     "SUPPORTED; two of the nine carry failing verdicts (national_uncertainty_"
     "decomposition 'no', fao_crop_calendar_crosscheck 'NO'), which is evidence they are "
     "live rather than vacuous",
     "research_campaign/DECISIONS.txt D079; not in any manuscript",
     "a per-row control cannot develop the minerals gap, but 'per-row' is a structural "
     "property and not a proof of correctness - it says the control's subject is the "
     "shipped object, not that the object is right"),
    ("CE-AGENT-003",
     "The 0.653744 Mt provincial shortfall is a vintage difference, not an API defect",
     "Punjab FY2015-16, the served API against this repository",
     "the served fact_adm1_year sums to 220.114574 by itself; the served copy is "
     "byte-identical to commit 5915e0c0; this tree has advanced 269 commits under the "
     "same label",
     "the served release directory; git",
     "python3 verify_release.py 1.0.0rc59 in the SERVING repository "
     "(pakemis-explorer, not this one); "
     "python3 scripts/build_published_vintages.py here",
     "SUPPORTED; supersedes the earlier reading that located the fault downstream of the "
     "products",
     "paper_national/versions/v1/sections/12_limitations.tex",
     "the divergence magnitudes stay out of the paper because they cannot be recomputed "
     "from the archive"),
)
# evidence_product is new and it is the column that makes the table checkable: the file a
# reader opens to find the numbers the row states. The guard in
# tests/test_campaign_handoff.py reads it and requires every figure in numerical_output to
# appear there, which caught CE-MIN-001 quoting a twelve-month profile the product
# published only the maximum of. A claim whose evidence is structural rather than numeric
# says so with the word STRUCTURAL.
CLAIM_FIELDS = ("claim_id", "claim", "scope", "numerical_output", "source", "command",
                "result_status", "wording_location", "remaining_limitation",
                "evidence_product")
EVIDENCE_PRODUCT = {
    "CE-AGENT-003": "STRUCTURAL: the comparison is between two trees, and the figure it "
                    "quotes is measured against a copy this repository does not hold; "
                    "data/catalog/published_release_vintages.csv carries the commit and "
                    "digests that ARE reproducible here",
    "CE-CITE-001": "outputs/pakemis_citation_pointer_audit.csv",
    "CE-ENERGY-002": "outputs/power_activity_factor_ledger.csv",
    "CE-CONTROL-SWEEP": "STRUCTURAL: a count of controls by shape over outputs/*.csv, "
                        "with the one failing case in "
                        "outputs/pakemis_minerals_panel_screening.csv",
    "CE-ENERGY-001": "outputs/pakemis_power_coal_energy_adjudication.csv",
    "CE-FGAS-001": "outputs/pakemis_fgas_leak_rate_adjudication.csv",
    "CE-FGAS-002": "outputs/pakemis_fgas_leak_rate_adjudication.csv",
    "CE-LAND-002": "outputs/pakemis_forest_flux_adjudication.csv",
    "CE-LAND-003": "outputs/pakemis_forest_flux_adjudication.csv",
    "CE-LIC-001": "outputs/pakemis_deposit_manifest.csv",
    # rc68: the claim describes the rc67 defect, so its evidence is the preserved rc67 product
    "CE-MIN-001": "data/baselines/rc67_integrated_campaign/outputs/pakemis_minerals_panel_screening.csv",
    "CE-MIN-002": "outputs/pakemis_minerals_panel_screening.csv",
    "CE-REL-001": "STRUCTURAL: the national totals agree and the allocation does not; "
                  "outputs/pakemis_release_axis_fingerprints.csv carries the two digests "
                  "per table and the magnitudes are measured against a copy this "
                  "repository does not hold",
    "CE-REL-002": "outputs/pakemis_release_axis_fingerprints.csv",
}


def claims():
    """CLAIMS above WINS over the file for any claim_id it defines.

    The first version kept the file's row whenever the id already existed, which made the
    builder unable to correct a row it had itself written: I qualified a serving-repository
    path in the literal, reran, and the stale text survived because the id matched. A
    builder that cannot overwrite its own output is not idempotent, it is append-only.
    Rows present only in the file are still preserved, so a hand-added claim is not lost.
    """
    literals = {}
    for values in CLAIMS:
        if len(values) != len(CLAIM_FIELDS) - 1:
            raise SystemExit("claim %s has %d fields against %d authored columns "
                             "(evidence_product is filled from EVIDENCE_PRODUCT)"
                             % (values[0], len(values), len(CLAIM_FIELDS) - 1))
        values = values + ("",)
        row = dict(zip(CLAIM_FIELDS, values))
        row["evidence_product"] = EVIDENCE_PRODUCT.get(row["claim_id"], "")
        if not row["evidence_product"]:
            raise SystemExit("claim %s names no evidence product; add it to "
                             "EVIDENCE_PRODUCT or mark it STRUCTURAL"
                             % row["claim_id"])
        literals[row["claim_id"]] = row
    rows = []
    for row in read("research_campaign/claim_evidence.csv"):
        if row["claim_id"] in literals:
            continue
        row.setdefault("evidence_product",
                       EVIDENCE_PRODUCT.get(row["claim_id"], ""))
        if not row["evidence_product"]:
            raise SystemExit("claim %s is in the file, names no evidence product and is "
                             "not a literal; add it to EVIDENCE_PRODUCT"
                             % row["claim_id"])
        rows.append(row)
    return sorted(rows + list(literals.values()), key=lambda r: r["claim_id"])


# -------------------------------------------------------------------- product manifest
# What this campaign created or changed, with the digest the RELEASE MANIFEST records for
# each - read from there rather than hashed here, so this file cannot describe a product
# the release does not. A product the manifest does not carry is recorded as such rather
# than omitted, which is the rule the stub already declared.
CAMPAIGN_PRODUCTS = (
    ("outputs/pakemis_forest_flux_adjudication.csv", "T-LAND-2",
     "the forest-flux sign screening; outside every total",
     "tests/test_forest_flux_adjudication.py"),
    ("outputs/pakemis_fgas_leak_rate_adjudication.csv", "T-MISS-2",
     "the bank's one leak rate per stratum against IPCC Table 7.9's per sub-application, "
     "with the official 2.F reading beside it",
     "tests/test_fgas_leak_rate_adjudication.py"),
    ("outputs/pakemis_btr_comparison.csv", "T-VAL-BTR",
     "year-matched comparison with Pakistan's first BTR, tiered",
     "tests/test_btr_comparison.py"),
    ("outputs/pakemis_release_axis_fingerprints.csv", "T-VINTAGE-AXES, T-AXIS-TIME",
     "coarse and fine digests per disaggregated table per published vintage",
     "tests/test_release_axis_fingerprints.py"),
    ("outputs/pakemis_citation_pointer_audit.csv", "T-CITATION-POINTERS, T-POINTERS-PBS",
     "whether a reader can find the figure in the document, per registered source",
     "tests/test_citation_pointer_audit.py"),
    ("outputs/pakemis_minerals_panel_screening.csv",
     "T-MINERALS-PANEL, T-MINERALS-MECHANISM",
     "which province-years of the minerals panel are whole, what a hole costs the served "
     "shape, and where a closing control does not describe the panel",
     "tests/test_minerals_panel_screening.py"),
    ("data/catalog/published_release_vintages.csv", "T-AGENT-3",
     "every published release as a commit and two digests, re-hashed out of git",
     "tests/test_published_vintages.py"),
    ("data/shared/evidence/btr1_national_inventory.csv", "T-VAL-BTR",
     "55 rows of Pakistan's BTR1 national inventory, transcribed with line citations",
     "tests/test_btr_comparison.py"),
    ("scripts/check_release_sequence.py", "T-RECORD-SEQUENCE",
     "proves the three release commits are in order; cannot live in the suite because the "
     "record is produced BY the suite", "(it is itself the check)"),
)


def products():
    manifest = {}
    path = os.path.join(ROOT, "outputs", "release_manifest.json")
    with open(path, encoding="utf-8") as handle:
        release = json.load(handle)
    for block in release.values():
        if isinstance(block, list):
            for row in block:
                if isinstance(row, dict) and row.get("path") and row.get("sha256"):
                    manifest[row["path"]] = row
    out = []
    for relative, task, what, guard in CAMPAIGN_PRODUCTS:
        row = manifest.get(relative)
        full = os.path.join(ROOT, relative)
        entry = {
            "path": relative, "task": task, "what": what, "guard": guard,
            "bytes": os.path.getsize(full) if os.path.exists(full) else None,
            "on_disk": os.path.exists(full),
        }
        if row:
            entry["sha256"] = row["sha256"]
            entry["hashed_in"] = "outputs/release_manifest.json"
        else:
            entry["sha256"] = None
            entry["hashed_in"] = ("not a release-manifest product - recorded here so the "
                                  "absence is visible rather than inferred")
        out.append(entry)
    return out


def _release_version():
    """The release the digests come from, read from the manifest's own version field."""
    with open(os.path.join(ROOT, "outputs", "release_manifest.json"),
              encoding="utf-8") as handle:
        release = json.load(handle)
    version = release.get("version") or release.get("product")
    if not version:
        raise SystemExit("the release manifest states no version; this manifest would "
                         "describe products without saying which release hashed them")
    return version


def main():
    counts = {}
    counts["source_register.csv"] = write(
        "source_register.csv", SOURCE_FIELDS, sources(),
        ["Every source this campaign read, with the locator the reading actually used.",
         "Lane detail stays in research_campaign/<lane>/; this is the index."])
    counts["comparison_results.csv"] = write(
        "comparison_results.csv", COMPARISON_FIELDS, comparisons(),
        ["Every comparison this campaign made. independence_class is the column that",
         "matters: a comparison between two readings of one source is a transcription",
         "check and not a validation, and three rows here say so."])
    counts["completeness.csv"] = write(
        "completeness.csv", COMPLETENESS_FIELDS, completeness(),
        ["The campaign's category view: what grade of treatment is supportable today.",
         "NO completeness percentage is computed - the denominator is what is unknown."])
    counts["claim_evidence.csv"] = write(
        "claim_evidence.csv", CLAIM_FIELDS, claims(),
        ["One row per headline claim, with the command that produced it and where its",
         "wording now lives. A claim with no published home says so."])
    manifest = {
        "generated_by": "research_campaign/build_campaign_tables.py",
        "note": "digests are read from outputs/release_manifest.json, never recomputed "
                "here, so this manifest cannot describe a product the release does not. "
                "A product the manifest does not carry is recorded explicitly.",
        "release": _release_version(),
        "products": products(),
    }
    with open(os.path.join(HERE, "product_manifest.json"), "w",
              encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    counts["product_manifest.json"] = len(manifest["products"])
    for name in sorted(counts):
        print("   %-26s %d row(s)" % (name, counts[name]))
    unhashed = [p["path"] for p in manifest["products"] if not p["sha256"]]
    missing = [p["path"] for p in manifest["products"] if not p["on_disk"]]
    print("   %d product(s) not in the release manifest: %s"
          % (len(unhashed), ", ".join(unhashed) or "none"))
    if missing:
        raise SystemExit("declared product(s) not on disk: %s" % ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

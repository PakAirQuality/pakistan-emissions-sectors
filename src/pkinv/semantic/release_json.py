"""semantic_release.json: the contract a consumer reads before it reads a table.

Byte-stable (no commit, no timestamp): the release identity is copied from the manifest's
STABLE fields and the commit is resolved by the consumer from release_manifest.json's git
block, so this file can itself be hashed by the manifest without a fixpoint."""
import json
import os

import pkinv
from pkinv.core import configurations as cfg
from pkinv.core.gwp import GWP
from pkinv.core.io import read_rows
from pkinv.paths import DATA, ROOT
from pkinv.semantic import SCHEMA

CONTEXT_BAR = ["release", "basis", "configuration_id", "gwp_basis", "geography_id", "lulucf"]

DEFAULTS = {"configuration_id": cfg.REFERENCE, "gwp_basis": "AR5", "basis": "fiscal",
            "period_id": "FY2023-24", "geography_id": "PK", "spatial_view": "all",
            "context_bar": CONTEXT_BAR}

ROUNDING = {
    "co2e_Mt": {"national_total": 5, "sector": 3, "category": 3, "stream": 6, "adm1": 4, "adm2": 4},
    "emissions_Gg": 8, "native_mass": 6, "share": 6, "pct": 1,
    "rule": "round half to even on the exact decimal string; the exact string is always "
            "returned beside the display value, and a bounded cell displays its interval",
}

QUERY_CONTRACT = {
    "package": "pakemis_query", "version": "1",
    "functions": ["query_emissions", "compare_emissions", "get_timeseries", "get_uncertainty",
                  "get_completeness", "get_evidence", "get_method", "get_spatial_lineage",
                  "get_cross_sector_transfer", "download_query_result", "get_grid_cell",
                  "query_activity",
                  "query_air"],
    "receipt_rule": "sha256('pakemis.receipt/v1' + canonical_request_json + release_id + result_sha256)",
    "placeholder_rule": "a consumer may print only {{result_cell_n}} values the server inserts; "
                        "a placeholder naming no cell is an error, and a number without a cell "
                        "is rejected",
}

BASE_LIMITATIONS = [
    {"id": "air_covered_sources", "scope": "query_air, the ten-fiscal-year panel",
     "notation_key": "E",
     "message": "the ten-fiscal-year panel covers the ESTIMATED sources alone "
                "(coverage_scope=covered_sources_only): grid power is inside it only for the "
                "species its admission register prices (oil and diesel SO2) and otherwise "
                "ships beside it as a controlled-to-uncontrolled screening pair; industrial "
                "combustion (rc58), IPPU "
                "process pollutants and fugitive NMVOC with flaring (rc59) are inside it as "
                "provisional estimates from the source-class register, with what each "
                "register cannot price typed absent per species in "
                "pakemis_air_coverage_matrix.csv - this is not a complete national "
                "seven-species inventory and does not claim to be, so 'the largest source' "
                "means the largest of the sources estimated here. Agricultural management/"
                "grazing NOx includes the adopted chemical partition of volatilised nitrogen; "
                "that partition is held in conditional intervals and tested separately by "
                "a nitrogen-conserving attribution diagnostic, not measured in Pakistan"},
    {"id": "air_beta", "scope": "query_air", "notation_key": "E",
     "message": "the integrated air-pollutant layer reports native "
                "kt of the named species, never CO2e, with assurance that is uneven across "
                "sectors (pakemis_air_coverage_matrix.csv states each sector, species and "
                "period) and outside every greenhouse-gas total"},
    {"id": "air_sector_ne", "scope": "query_air, sectors power and the register modules' typed classes",
     "notation_key": "NE",
     "message": "grid power is covered only for the species its admission register prices "
                "(oil and diesel SO2); for every other species it has no covered estimate and "
                "a screening scenario pair ships beside the panel. Within the register modules the classes no admissible factor or "
                "series can price - urea finishing, nitric acid, lime, glass, venting, "
                "post-meter NMVOC, LNG terminals, captive solids, bagasse - are recorded NE "
                "with their activity beside them, never counted as zero"},
    {"id": "pollutants_not_additive", "scope": "query_air, group_by without pollutant",
     "notation_key": "NA",
     "message": "the particulate strata contain one another (BC and OC inside PM2.5, PM2.5 "
                "inside PM10, PM10 inside TSP), so a sum across pollutants is refused, "
                "never computed"},
    {"id": "air_spatial_not_in_layer", "scope": "query_air, geography_level adm1/adm2",
     "notation_key": "NE",
     "message": "every sector's air layer is placed with its own streams' geography, for "
                "all ten fiscal periods (fact_air_adm1_year, fact_air_adm2_year). What a "
                "grain does not place stays typed, never zeroed, in "
                "pakemis_air_unallocated_by_year.csv - aviation cruise below the provinces, "
                "and mass outside the district frame - and a request for a sector the "
                "provincial or district table does not hold is refused naming the sectors "
                "it does"},
    {"id": "air_history_national_only", "scope": "query_air, years set",
     "notation_key": "NE",
     "message": "the 1990-2024 calendar-year air series is national and agriculture-only; "
                "provinces and districts carry the ten fiscal periods (FY2015-16..FY2024-25), "
                "not calendar years"},
    {"id": "calendar_basis_ne", "scope": "basis=calendar, sector != agriculture", "notation_key": "NE",
     "message": "calendar-year values exist only for the agriculture reconstruction "
                "(fact_annual_calendar); every other sector is fiscal (July-June) and a calendar "
                "request is refused, never computed"},
    {"id": "adm2_frame_is_fixed", "scope": "geography_level=ADM2, all periods",
     "notation_key": "NE",
     "message": "every period is published on one fixed district frame "
                "(geoBoundaries-gbOpen-PAK-ADM2-2019, 152 canonical units); eleven units were "
                "carved out of larger districts during the window, so an earlier year's row "
                "for such a district is the mass that would fall inside TODAY's boundary, not "
                "a figure any administration reported at the time. The contemporaneous "
                "geography is not held - see abs-adm2-frame-vintage"},
    {"id": "ar6_adm2_ne", "scope": "gwp_basis=AR6 at ADM2 or below", "notation_key": "NE",
     "message": "the ADM2 products carry native gas mass at module grain; AR6 CO2e is available "
                "nationally and at ADM1 in the monthly table fact_adm1_month. The annual ADM1 "
                "table fact_adm1_year and every ADM2 table carry AR5 only"},
    {"id": "configuration_structure", "scope": "all configurations", "notation_key": "E",
     "message": "S_TAN is the reference. L_TAN, S_IPCC and L_IPCC alter household dung destination and nitrogen methods. All four are annual and monthly native-gas calculations, not additive components or probability-weighted scenarios."},
    {"id": "industry_reported_fuel_series", "scope": "sector=industry", "notation_key": "E",
     "message": "Covered industrial-combustion emissions fell, reflecting lower recorded fuel use. "
                "This does not mean Pakistan's total industrial emissions declined; several "
                "industrial sources are reported elsewhere or remain outside the inventory. "
                "The industry (1.A.2) series is a REPORTED-FUEL estimate: its two largest streams, "
                "brick-kiln coal and cement-sector coal, are the official HDIP coal-by-consumer "
                "allocation (Finance Division Statistical Supplement Table 14.1(4), marked "
                "'** Estimated'), which swings threefold across the window and falls sharply after "
                "FY2020-21. The published coal account compares production, imports and station "
                "consumption and retains unresolved quantities. Its allocation changes must not "
                "be read as verified reductions from mitigation or efficiency. The column the Supplement prints as 'Cement' is the "
                "primary publication's 'Cement/Other Industry', so other industrial coal may sit "
                "inside it unsplit. Dated fleet and fuel-use alternatives are separate structural "
                "cases, without assigned probabilities"},
    {"id": "reporting_sector_view", "scope": "group_by=reporting_sector / reporting_sectors filter",
     "notation_key": "E",
     "message": "reporting_sector files each stream where IPCC 2006 reports it, in the module "
                "vocabulary, beside sector_id (the module that computed it): captive gas "
                "self-generation (1.A.2, computed by the power module because it shares the plant "
                "register and factor table) reports under industry; railways' unresolved "
                "'1.A.2/1.A.4.c' and transport's mixed off-road (1.A.4.c/1.A.2) keep their modules "
                "until their splits are published. The axis is additive with sector_id at every "
                "grain - the same atoms regrouped, no mass moved - and is declared per stream in "
                "data/stream_reporting_sector.csv (pkinv.core.declared.match_prefix, a stream with "
                "no row raises). It is answerable at every grain: the district tables carry the "
                "column too (since rc54 the cube keys its accumulator on the module and reporting "
                "sector together), so the industry reporting sector at district grain includes the "
                "captive generation the axis exists to include. The air lane stays module-keyed"},
    {"id": "economic_sector_view", "scope": "group_by=economic_sector", "notation_key": "E",
     "message": "the economic-sector view regroups the same atoms by what the activity is: "
                "'industrial' = the industry and ippu REPORTING sectors - 1.A.2 manufacturing "
                "combustion including the captive generation the power module computes (through the "
                "reporting_sector axis) plus every 2.x process category; every other sector keeps its "
                "module. It is additive with the IPCC view. Its industrial aggregate is "
                "'covered direct industrial sources' - the priced boundary only. Since rc52 that boundary "
                "holds ammonia (2.B.1), iron and steel (2.C.1) and lubricant use (2.D.1) as ten-year "
                "series beside cement; nitric acid (a pair), HFCs and SF6, lime, glass, soda ash (NA in "
                "IPPU) and industrial wastewater are screened or absent and are NOT inside it; each enters "
                "only with an explicitly supported period and boundary. The common core covers "
                "FY2015-16 through FY2024-25; partial FY2025-26 records cannot be summed into it"},
    {"id": "grid_not_tabular", "scope": "0.05 degree grid", "notation_key": "E",
     "message": "grid cells stay in the NetCDF products (CF-1.8), which the release manifest "
                "lists and hashes; the API reads a cell from the file and the map tiles are "
                "visual only"},
    {"id": "no_polygon_units", "scope": "dim_geography has_polygon=no", "notation_key": "E",
     "message": "the residual territories row and the census units the boundary file does not "
                "draw carry mass at ADM1 and are named rows without geometry"},
    {"id": "lulucf_excluded", "scope": "every total", "notation_key": "NE",
     "message": "no land-use, land-use-change or forestry flux enters any total; an exploratory "
                "Tier-1 module publishes a provisional sink outside every total"},
]


def _manifest():
    path = os.path.join(ROOT, "outputs", "release_manifest.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def build(tables, digests, limitations_from_completeness, download_catalog=None, activity_inputs=None):
    """`tables`: {name: {"kind", "path", "parquet", "sha256_csv", "rows", "primary_key",
    "columns", "aggregation", "derived_from"}}. `digests`: the sources block."""
    m = _manifest()
    stable = {
        "product": "PakEmis", "version": pkinv.__version__,
        "release_id": "PakEmis %s" % pkinv.__version__,
        "release_manifest": "outputs/release_manifest.json",
        "commit": "resolve from release_manifest.json git.describes_commit",
        "reporting_period": m.get("reporting_period"),
        "baseline_configuration": m.get("baseline_configuration", {}).get("code"),
        "ledger_configuration": cfg.LEDGER,
        "gwp_bases": {"reported": "AR5", "secondary": "AR6",
                      "factors": {b: {g: GWP[b][g] for g in ("CO2", "CH4", "CH4_fossil", "N2O")} for b in GWP}},
        "lulucf": {"status": "excluded", "notation_key": "NE",
                   "note": "an exploratory Tier-1 module publishes a provisional sink outside every total"},
        "licences": m.get("licences"),
    }
    dims = {n: t for n, t in tables.items() if t["kind"] == "dimension"}
    facts = {n: t for n, t in tables.items() if t["kind"] == "fact"}
    out = {
        "schema": SCHEMA,
        "release": stable,
        "defaults": DEFAULTS,
        "dimensions": dims,
        "facts": facts,
        "rounding": ROUNDING,
        "products": digests,
        "known_limitations": BASE_LIMITATIONS + limitations_from_completeness,
        "query_contract": QUERY_CONTRACT,
    }
    if download_catalog is not None:
        out["download_catalog"] = download_catalog
    if activity_inputs is not None:
        out["activity_inputs"] = activity_inputs
        from pkinv.semantic.assets import build as build_assets
        out["asset_catalog"] = build_assets(activity_inputs)
    return out


def completeness_limitations(rows):
    out = []
    seen = set()
    for r in rows:
        if r["notation_key"] in ("NE", "NO") and r["gap_id"] and r["gap_id"] not in seen:
            seen.add(r["gap_id"])
            out.append({"id": "completeness:%s" % r["gap_id"], "scope": "%s %s" % (r["code"], r["category"]),
                        "notation_key": r["notation_key"], "message": r["justification"]})
    return out

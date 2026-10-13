"""Fact tables: the release's numbers at their published grains, copied as strings.

Each builder returns (fieldnames, key, rows). Two tables carry computed columns, both exact
decimal arithmetic on two shipped numbers and both golden-tested to a closure the release
already publishes: fact_adm1_month (a stream's monthly mass times its month-invariant declared
province share, the cube's own identity) and the configuration-L rows of fact_adm2_month (the
ledger product's stream rows summed to the module grain the reference product carries)."""
import collections
from decimal import Decimal, ROUND_HALF_EVEN

from pkinv.core import configurations as cfg

TWELVE = Decimal(1).scaleb(-12)
REFERENCE_PERIOD = "FY2023-24"


def _q(value):
    return str(value.quantize(TWELVE, rounding=ROUND_HALF_EVEN))


def _dec(text):
    return Decimal(text) if text not in ("", None) else None


# --- annual --------------------------------------------------------------------------------

ATOM_FIELDS = ("period_id", "configuration_id", "geography_id", "grain", "component_id", "gas",
               "sector_id", "reporting_sector", "ipcc_code", "category", "subitem", "gas_origin",
               "estimate_status",
               "activity_status", "evidence_class", "method_id", "uncertainty_model_id",
               "native_mass", "native_unit", "co2e_Mt_AR5", "co2e_Mt_AR6", "source_stream_id",
               "basis")


def _ipcc_code_of(src):
    """(module, ipcc_category) -> ipcc_code, from the source-stream ledger."""
    out = {}
    for r in src.rows("provenance.source_streams"):
        out.setdefault((r["module"], r["ipcc_category"]), r["ipcc_code"])
    return out


def _reporting_sector_of(src):
    """source_stream_id -> reporting_sector, from the source-stream ledger.

    THE REPORTING-SECTOR AXIS (data/stream_reporting_sector.csv): the sector IPCC 2006 files a
    stream under, in the module vocabulary, beside the module that computed it. The national
    atoms and months carry it from the atomic table; the stream-keyed spatial facts (ADM1
    month and year, the unallocated ledger) look it up here per stream, exactly as
    spatial_view is carried. The ADM2 facts carry it too since rc54: the cube now keys its
    district accumulator on (module, reporting_sector) rather than the module alone, so a
    module's district mass is partitioned by where the Guidelines report it - exactly, from the
    same per-stream vectors, with the module total recoverable by summing over the pair. Before
    rc54 the district tables were module-resolved and the query core refused the axis there
    rather than answer it with the module."""
    return {r["source_stream_id"]: r["reporting_sector"]
            for r in src.rows("provenance.source_streams")}


def fact_annual(src):
    rows = []
    for r in src.rows("annual.atomic"):
        rows.append({"period_id": r["period_id"], "configuration_id": r["configuration_id"],
                     "geography_id": r["geography_id"], "grain": "atom",
                     "component_id": r["component_id"], "gas": r["gas"],
                     "sector_id": r["sector_id"], "reporting_sector": r["reporting_sector"],
                     "ipcc_code": r["ipcc_code"],
                     "category": r["category"], "subitem": r["subitem"],
                     "gas_origin": r["gas_origin"], "estimate_status": r["estimate_status"],
                     "activity_status": r["activity_status"], "evidence_class": r["evidence_class"],
                     "method_id": r["method_id"], "uncertainty_model_id": r["uncertainty_model_id"],
                     "native_mass": r["emission_native_mass"], "native_unit": r["native_unit"],
                     "co2e_Mt_AR5": r["co2e_Mt_AR5"], "co2e_Mt_AR6": r["co2e_Mt_AR6"],
                     "source_stream_id": r["source_stream_id"], "basis": "fiscal"})
    # configuration L: the residential module at category x gas grain, FY2023-24 only. The
    # REFERENCE's residual rows ("Diverted dung, unresolved fate", one per year) carry no
    # gas and no mass and stay where they are published (annual.panel), named in
    # known_limitations
    for r in src.rows("annual.panel"):
        if r["configuration_id"] != cfg.LEDGER or r["grain"] != "category_gas":
            continue
        rows.append({"period_id": r["period_label"], "configuration_id": cfg.LEDGER,
                     "geography_id": "PK", "grain": "category_gas",
                     "component_id": "%s|%s|%s" % (r["sector"], r["category"], r["gas"]),
                     "gas": r["gas"], "sector_id": r["sector"], "reporting_sector": r["sector"],
                     "ipcc_code": "1.A.4.b",
                     "category": r["category"], "subitem": "", "gas_origin": "",
                     "estimate_status": "E", "activity_status": r["activity_basis"],
                     "evidence_class": "", "method_id": "", "uncertainty_model_id": "",
                     "native_mass": "", "native_unit": "", "co2e_Mt_AR5": r["co2e_Mt_AR5"],
                     "co2e_Mt_AR6": r["co2e_Mt_AR6"], "source_stream_id": "", "basis": "fiscal"})
    key = ("period_id", "configuration_id", "geography_id", "grain", "component_id", "gas")
    return ATOM_FIELDS, key, rows


def fact_annual_calendar(src):
    fields = ("period_id", "basis", "year_basis", "sector_id", "category", "CO2_kt", "CH4_kt",
              "N2O_kt", "co2e_Mt_AR5")
    # the file's TOTAL rows are a sum the engine makes itself; the seven fiscal_census_anchor
    # rows (the reference year on its own basis) are kept and keyed by their basis
    rows = [{"period_id": "CY%s" % r["year"], "basis": "calendar", "year_basis": r["year_basis"],
             "sector_id": "agriculture", "category": r["category"], "CO2_kt": r["CO2_kt"],
             "CH4_kt": r["CH4_kt"], "N2O_kt": r["N2O_kt"], "co2e_Mt_AR5": r["co2e_Mt_AR5"]}
            for r in src.rows("timeseries_1990_2024") if r["category"] != "TOTAL"]
    return fields, ("period_id", "year_basis", "category"), rows


# --- monthly -------------------------------------------------------------------------------

MONTHLY_FIELDS = ("period_id", "month", "configuration_id", "geography_id", "grain",
                  "component_id", "gas", "sector_id", "reporting_sector", "ipcc_code", "category",
                  "subitem",
                  "gas_origin", "native_mass", "native_unit", "co2e_Mt_AR5", "co2e_Mt_AR6",
                  "share", "closure_basis", "temporal_evidence_class", "timing_target",
                  "temporal_status", "profile_id", "source_id", "borrowed_from_year",
                  "special_period_flag", "basis")


def fact_monthly(src):
    rows = []
    for r in src.rows("monthly.panel"):
        row = {k: r[k] for k in MONTHLY_FIELDS if k in r}
        row.update({"grain": "atom", "native_mass": r["emission_native_mass"], "basis": "fiscal"})
        rows.append(row)
    for r in src.rows("monthly.ledger_2024"):
        rows.append({"period_id": REFERENCE_PERIOD, "month": r["month"],
                     "configuration_id": r["configuration_id"], "geography_id": "PK",
                     "grain": "category_subitem_gas",
                     "component_id": "residential|%s|%s" % (r["category"], r["subitem"]),
                     "gas": r["gas"], "sector_id": "residential", "reporting_sector": "residential",
                     "ipcc_code": "1.A.4.b",
                     "category": r["category"], "subitem": r["subitem"], "gas_origin": "",
                     "native_mass": r["emissions_Gg"], "native_unit": "Gg",
                     "co2e_Mt_AR5": r["co2e_Mt_AR5"], "co2e_Mt_AR6": r["co2e_Mt_AR6"],
                     "share": r["share"], "closure_basis": "", "temporal_evidence_class": "",
                     "timing_target": "", "temporal_status": "", "profile_id": "",
                     "source_id": r["basis"], "borrowed_from_year": "", "special_period_flag": "",
                     "basis": "fiscal"})
    key = ("period_id", "month", "configuration_id", "geography_id", "grain", "component_id", "gas")
    return MONTHLY_FIELDS, key, rows


# --- ADM1 ----------------------------------------------------------------------------------

ADM1_FIELDS = ("configuration_id", "month", "province", "source_stream_id", "gas", "module",
               "reporting_sector", "spatial_view", "declared_share", "emissions_Gg", "co2e_Mt_AR5", "co2e_Mt_AR6",
               "share_status", "basis_note")


def fact_adm1_month(src):
    """Stream x province x month for the reference year: the monthly stream mass times the
    month-invariant declared province share (pakemis_grid_provincial_check.csv). Exact decimal
    products, twelve decimals; national == ADM1 per gas and month is the golden closure."""
    shares = {(r["source_stream_id"], r["province"]): r
              for r in src.rows("spatial.grid_provincial_check")}
    views = {r["source_stream_id"]: (r["spatial_view"], r["module"])
             for r in src.rows("provenance.source_streams")}
    reporting = _reporting_sector_of(src)
    rows = []
    for r in src.rows("monthly.panel"):
        if r["period_id"] != REFERENCE_PERIOD or r["configuration_id"] != cfg.REFERENCE:
            continue
        sid = r["source_stream_id"] if "source_stream_id" in r else r["component_id"]
        view, module = views.get(sid, ("", r["sector_id"]))
        for (stream, province), share in shares.items():
            if stream != sid:
                continue
            s = Decimal(share["declared_share"])
            rows.append({"configuration_id": cfg.REFERENCE, "month": r["month"],
                         "province": province, "source_stream_id": sid, "gas": r["gas"],
                         "module": module, "reporting_sector": reporting.get(sid, module),
                         "spatial_view": view,
                         "declared_share": share["declared_share"],
                         "emissions_Gg": _q(Decimal(r["emission_native_mass"]) * s),
                         "co2e_Mt_AR5": _q(Decimal(r["co2e_Mt_AR5"]) * s),
                         "co2e_Mt_AR6": _q(Decimal(r["co2e_Mt_AR6"]) * s),
                         "share_status": share["status"],
                         "basis_note": "monthly stream mass x declared province share"})
    for r in src.rows("spatial.adm1_ledger_2024"):
        rows.append({"configuration_id": r["configuration_id"], "month": r["month"],
                     "province": r["province"], "source_stream_id": r["source_stream_id"],
                     "gas": r["gas"], "module": r["module"],
                     # configuration L's stream ids are the residential module's; a
                     # stream the source-stream ledger does not name reports under its module
                     "reporting_sector": reporting.get(r["source_stream_id"], r["module"]),
                     "spatial_view": r["spatial_view"],
                     "declared_share": "", "emissions_Gg": r["emissions_Gg"],
                     "co2e_Mt_AR5": r["co2e_Mt_AR5"], "co2e_Mt_AR6": "",
                     "share_status": "ledger_product", "basis_note": "pakemis_adm1_ledger_2024.csv"})
    key = ("configuration_id", "month", "province", "source_stream_id", "gas")
    return ADM1_FIELDS, key, rows


# --- ADM2 ----------------------------------------------------------------------------------

ADM2_FIELDS = ("configuration_id", "month", "shape_id", "module", "reporting_sector", "gas",
               "spatial_view", "province", "adm2_ids", "allocation_status", "absence_reason", "emissions_Gg",
               "co2e_Mt_AR5", "co2e_exactness")


def fact_adm1_year(src):
    """Stream x province x YEAR, for all nine periods - the provincial layer the query
    surface refused until rc47's app wiring asked for it and found only the monthly
    reference table published.

    The source is the release's own nine-year ADM1 product (pakemis_adm1_by_year.csv):
    stream grain, EXACT co2e - ADM1 is the level the closure identity holds exactly at
    (ADM1 == ADM2 + unallocated below ADM1), so unlike fact_adm2_year there are no
    bounded cells and no absence rows to carry. AR5 only, like the district year table:
    the historical spatial layer prices one GWP basis, and the engine refuses AR6 here
    by name rather than converting."""
    reporting = _reporting_sector_of(src)
    rows = []
    for r in src.rows("spatial.adm1_by_year"):
        rows.append({"configuration_id": cfg.REFERENCE, "period_id": r["period_id"],
                     "province": r["province"],
                     "source_stream_id": r["source_stream_id"], "module": r["module"],
                     "reporting_sector": reporting.get(r["source_stream_id"], r["module"]),
                     "gas": r["gas"], "spatial_view": r["spatial_view"],
                     "emissions_Gg": r["emissions_Gg"],
                     "co2e_Mt_AR5": r["co2e_Mt_AR5"]})
    fields = ("configuration_id", "period_id", "province", "source_stream_id", "module",
              "reporting_sector", "gas", "spatial_view", "emissions_Gg", "co2e_Mt_AR5")
    key = ("configuration_id", "period_id", "province", "source_stream_id",
           "spatial_view")
    return fields, key, rows


def fact_spatial_basis_year(src):
    """How much of each year's mass rides geography that is THAT YEAR'S OWN - per period,
    module and reporting sector, by `spatial_time_basis`.

    The province and district year tables are mass and say nothing about where their
    geography comes from; that was a deliberate split (an evidence column on a mass table
    would vary by row and be summed over by every consumer). The provenance is the weight
    registry, pakemis_spatial_weights_by_year.csv, one row per (stream, period):

        annual_observed_activity   the pattern is that year's observed activity
        static_structural          a surface that does not change with time
        reference_shape_backcast   the reference year's pattern, rescaled to the year's mass
        substituted_surface        a stand-in surface (declared per stream)
        unallocated                retained at ADM1; no district geography at all

    A registry of stream-years cannot be read as "how much of this year is reconstructed":
    a hundred small streams and one large one are counted alike, and the only public
    statement of it was a prose count ("1,102 of 1,672 live stream-years") that the
    registry outran twice while the sentence stood. This table is that registry WEIGHTED
    BY MASS - each stream-year's ADM1 total (pakemis_adm1_by_year.csv, exact) filed under
    its basis - so the question has a number, per year and per sector, that is rebuilt
    with the data it describes.

    A stream with mass and no registry row RAISES: a share that silently left mass out
    would look more observed than the year is. The masses sum to fact_adm1_year per
    period (tests/test_spatial_basis_year.py). AR5, like the tables it describes."""
    from decimal import Decimal
    basis_of = {}
    for r in src.rows("spatial.weights_by_year"):
        basis_of[(r["source_stream_id"], r["period_id"])] = r["spatial_time_basis"]
    reporting = _reporting_sector_of(src)
    mass = {}
    module_of = {}
    for r in src.rows("spatial.adm1_by_year"):
        key = (r["period_id"], r["source_stream_id"])
        mass[key] = mass.get(key, Decimal(0)) + Decimal(r["co2e_Mt_AR5"])
        module_of[r["source_stream_id"]] = r["module"]
    out = {}
    for (period_id, stream), value in mass.items():
        basis = basis_of.get((stream, period_id))
        if not basis:
            raise ValueError("stream %s has ADM1 mass in %s and no row in the spatial weight "
                             "registry: its geography has no stated basis" % (stream, period_id))
        if basis == "not_present" and value != 0:
            raise ValueError("stream %s is typed not_present in %s and carries %s Mt"
                             % (stream, period_id, value))
        module = module_of[stream]
        key = (period_id, module, reporting.get(stream, module), basis)
        n, total = out.get(key, (0, Decimal(0)))
        out[key] = (n + 1, total + value)
    rows = [{"configuration_id": cfg.REFERENCE, "period_id": k[0], "module": k[1],
             "reporting_sector": k[2], "spatial_time_basis": k[3],
             "n_streams": str(n), "co2e_Mt_AR5": format(total, "f")}
            for k, (n, total) in sorted(out.items())]
    fields = ("configuration_id", "period_id", "module", "reporting_sector",
              "spatial_time_basis", "n_streams", "co2e_Mt_AR5")
    key = ("configuration_id", "period_id", "module", "reporting_sector",
           "spatial_time_basis")
    return fields, key, rows


def fact_adm2_year(src):
    """Module x district x YEAR, for all nine periods - the historical spatial layer as the
    query surface sees it.

    WHY A SECOND TABLE RATHER THAN NINE YEARS INSIDE fact_adm2_month. The month table is
    module-resolved and carries the reference year; making it cover nine years at the same
    grain costs about 36 MB, and what those rows would store, for two thirds of stream-years,
    is the reference year's within-province pattern repeated a hundred and eight times per
    district instead of nine - more rows carrying no more evidence. Splitting the tables puts
    that coverage asymmetry in the SCHEMA, where a consumer meets it, instead of inside one
    table whose completeness varies by row. A table that was module-complete for one year and
    empty for eight would give a right answer for FY2023-24 and a wrong one for any comparison
    across years, which is the defect class this release spends most of its guards on.

    WHAT IT DOES NOT CARRY. Evidence that each year's geography is its own. A stream-year's
    within-province pattern is that year's observation, a surface that does not change with
    time, or the reference year's rescaled; pakemis_spatial_weights_by_year.csv says which per
    stream-year and fact_spatial_basis_year sums it by mass per period and module. This table
    is the mass, those are its provenance, and neither is readable without the other. (This
    docstring used to quote a count of back-cast stream-years; the count moved twice after it
    was written and the sentence did not.)"""
    rows = []
    for r in src.rows("spatial.adm2_sector_by_year"):
        if r["allocation_status"] == "unallocated-below-adm1":
            continue          # published once, in fact_unallocated
        rows.append({"configuration_id": cfg.REFERENCE, "period_id": r["period_id"],
                     "shape_id": r["shape_id"], "module": r["module"],
                     "reporting_sector": r["reporting_sector"], "gas": r["gas"],
                     "spatial_view": r["spatial_view"], "province": r["province"],
                     "adm2_ids": r["adm2_ids"], "allocation_status": r["allocation_status"],
                     "absence_reason": r["absence_reason"], "emissions_Gg": r["emissions_Gg"],
                     "co2e_Mt_AR5": r["co2e_Mt_AR5"],
                     "co2e_exactness": "" if r["co2e_Mt_AR5"] == "" else "exact_stream_priced"})
    fields = ("configuration_id", "period_id") + ADM2_FIELDS[2:]
    key = ("configuration_id", "period_id", "shape_id", "module", "reporting_sector", "gas",
           "spatial_view", "province")
    return fields, key, rows


def fact_adm2_month(src):
    rows = []
    for r in src.rows("spatial.adm2_monthly_sector"):
        if r["allocation_status"] == "unallocated-below-adm1":
            continue          # published once, in fact_unallocated
        rows.append({"configuration_id": cfg.REFERENCE, "month": r["month"],
                     "shape_id": r["shape_id"], "module": r["module"],
                     "reporting_sector": r["reporting_sector"], "gas": r["gas"],
                     "spatial_view": r["spatial_view"], "province": r["province"],
                     "adm2_ids": r["adm2_ids"], "allocation_status": r["allocation_status"],
                     "absence_reason": r["absence_reason"], "emissions_Gg": r["emissions_Gg"],
                     "co2e_Mt_AR5": r["co2e_Mt_AR5"],
                     "co2e_exactness": "" if r["co2e_Mt_AR5"] == "" else "exact_stream_priced"})
    # configuration L: the ledger product is at stream grain; summed to the module grain
    sums = collections.OrderedDict()
    for r in src.rows("spatial.adm2_ledger_2024"):
        k = (r["configuration_id"], r["month"], r["shape_id"], r["module"],
             r.get("reporting_sector") or r["module"], r["gas"],
             r["spatial_view"], r["province"], r["adm2_ids"], r["allocation_status"], r["absence_reason"])
        if r["emissions_Gg"] == "":
            sums.setdefault(k, None)
            continue
        gg_sum, co2e_sum = sums.get(k) or (Decimal(0), Decimal(0))
        sums[k] = (gg_sum + Decimal(r["emissions_Gg"]),
                   co2e_sum + Decimal(r["co2e_Mt_AR5"]))
    for k, total in sums.items():
        rows.append({"configuration_id": k[0], "month": k[1], "shape_id": k[2], "module": k[3],
                     "reporting_sector": k[4],
                     "gas": k[5], "spatial_view": k[6], "province": k[7], "adm2_ids": k[8],
                     "allocation_status": k[9], "absence_reason": k[10],
                     "emissions_Gg": "" if total is None else _q(total[0]),
                     "co2e_Mt_AR5": "" if total is None else _q(total[1]),
                     "co2e_exactness": "" if total is None else "exact_stream_priced"})
    key = ("configuration_id", "month", "shape_id", "module", "reporting_sector", "gas",
           "spatial_view", "province")
    return ADM2_FIELDS, key, rows


def fact_unallocated(src):
    fields = ("configuration_id", "source_stream_id", "month", "level", "province", "module",
              "reporting_sector", "ipcc_category", "gas", "spatial_view", "emissions_Gg",
              "co2e_Mt_AR5", "reason")
    reporting = _reporting_sector_of(src)
    rows = [dict(configuration_id=cfg.REFERENCE,
                 reporting_sector=reporting.get(r["source_stream_id"], r["module"]),
                 **{k: r[k] for k in fields if k not in ("configuration_id", "reporting_sector")})
            for r in src.rows("spatial.unallocated")]
    return fields, ("configuration_id", "source_stream_id", "month", "level", "province"), rows


# --- uncertainty, completeness, transfers, evidence ------------------------------------------

def fact_uncertainty(src):
    rows = src.rows("uncertainty.joint")
    fields = tuple(rows[0].keys())
    return fields, ("category", "module", "resolution"), rows


def fact_uncertainty_series(src):
    fields = ("kind", "scope", "key", "scenario", "period_or_pair", "central_Mt", "P2.5_Mt",
              "P50_Mt", "P97.5_Mt", "rel_down_pct_95", "rel_up_pct_95", "n_iter", "note")
    rows = []
    for r in src.rows("uncertainty.longitudinal"):
        rows.append({"kind": "annual_level", "scope": "national", "key": r["period_label"],
                     "scenario": r["scenario"], "period_or_pair": r["period_label"],
                     "central_Mt": r["covered_total_Mt"], "P2.5_Mt": r["P2.5_Mt"],
                     "P50_Mt": r["P50_Mt"], "P97.5_Mt": r["P97.5_Mt"],
                     "rel_down_pct_95": r["rel_down_pct_95"], "rel_up_pct_95": r["rel_up_pct_95"],
                     "n_iter": r.get("n_iter", ""), "note": "covered total of the sectors present in the year"})
    for r in src.rows("uncertainty.trend"):
        rows.append({"kind": "trend_pair", "scope": "national",
                     "key": "%s->%s" % (r["from_period"], r["to_period"]), "scenario": r["scenario"],
                     "period_or_pair": "%s->%s" % (r["from_period"], r["to_period"]),
                     "central_Mt": r["difference_Mt"], "P2.5_Mt": r["P2.5_Mt"], "P50_Mt": r["P50_Mt"],
                     "P97.5_Mt": r["P97.5_Mt"], "rel_down_pct_95": "", "rel_up_pct_95": "",
                     "n_iter": r["n_iter"], "note": r["scope_note"]})
    for r in src.rows("uncertainty.national_montecarlo"):
        rows.append({"kind": "parametric_reference", "scope": r["scope"],
                     "key": "%s|%s" % (r["aggregation_level"], r["name"]), "scenario": r["scenario"],
                     "period_or_pair": REFERENCE_PERIOD, "central_Mt": r["mean_Mt"],
                     "P2.5_Mt": r["P2.5_Mt"], "P50_Mt": r["P50_Mt"], "P97.5_Mt": r["P97.5_Mt"],
                     "rel_down_pct_95": r["rel_down_pct_95"], "rel_up_pct_95": r["rel_up_pct_95"],
                     "n_iter": r["n_iter"], "note": r["distribution_id"]})
    return fields, ("kind", "scope", "key", "scenario"), rows


def fact_completeness(src):
    rows = src.rows("completeness")
    fields = tuple(rows[0].keys())
    return fields, ("code", "category", "gas"), rows


def fact_completeness_mass(src):
    rows = src.rows("completeness.mass")
    fields = tuple(rows[0].keys())
    return fields, ("row_type", "ipcc_code", "stream", "configuration_id"), rows


def fact_transfer(src):
    from pkinv.semantic.ledger import resolve
    fields = ("ledger_id", "row_id", "configuration_id", "kind", "status", "value", "units",
              "period_id", "origin_sector", "origin_source_stream", "destination_sector",
              "destination_source_stream", "origin_emissions_effect", "destination_emissions_effect",
              "source_file", "row_key", "value_column", "source_ids", "method_id")
    rows = []
    for r in src.rows("cross_sector_ledger_map"):
        hits = resolve(r, sources=src)
        value = hits[0][r["value_column"]] if len(hits) == 1 else ""
        for configuration in r["configuration_id"].split(";"):
            rows.append({"ledger_id": r["ledger_id"], "row_id": r["row_id"],
                         "configuration_id": configuration, "kind": r["kind"], "status": r["status"],
                         "value": value, "units": r["units"], "period_id": r["period_id"],
                         "origin_sector": r["origin_sector"], "origin_source_stream": r["origin_source_stream"],
                         "destination_sector": r["destination_sector"],
                         "destination_source_stream": r["destination_source_stream"],
                         "origin_emissions_effect": r["origin_emissions_effect"],
                         "destination_emissions_effect": r["destination_emissions_effect"],
                         "source_file": r["source_file"], "row_key": r["row_key"],
                         "value_column": r["value_column"], "source_ids": r["source_ids"],
                         "method_id": r["method_id"]})
    return fields, ("ledger_id", "row_id", "configuration_id"), rows


def fact_evidence(src):
    """One lineage row per stream: what the placement and timing registers measured for it."""
    spatial = {(r["module"], r["sub_category"], r["gas"]): r for r in src.rows("spatial.decomposition")}
    temporal = {}
    for r in src.rows("monthly.temporal_decomposition"):
        temporal[(r["sector_id"], r["component"])] = r
    fallbacks = collections.defaultdict(lambda: [0, Decimal(0)])
    for r in src.rows("spatial.grid_fallbacks"):
        fallbacks[r["source_stream_id"]][0] += 1
        if r["affected_Mt_AR5"]:
            fallbacks[r["source_stream_id"]][1] += Decimal(r["affected_Mt_AR5"])
    fields = ("source_stream_id", "module", "gas", "evidence_class", "temporal_class",
              "temporal_profile_id", "spatial_class", "spatial_class_measured", "placement_class",
              "allocation_surface", "located_mass_fraction", "unresolved_Mt_AR5",
              "flatness_class", "temporal_evidence_grade", "fallback_events", "fallback_Mt_AR5",
              "geometry_id", "release_height_class", "licence_status")
    rows = []
    for r in src.rows("provenance.source_streams"):
        sp = spatial.get((r["module"], r["sub_category"], r["gas"]), {})
        te = temporal.get((r["module"], r["ipcc_category"]), {}) or next(
            (v for (m, c), v in temporal.items() if m == r["module"] and r["sub_category"].startswith(c)), {})
        fb = fallbacks.get(r["source_stream_id"], [0, Decimal(0)])
        rows.append({"source_stream_id": r["source_stream_id"], "module": r["module"], "gas": r["gas"],
                     "evidence_class": r["evidence_class"], "temporal_class": r["temporal_class"],
                     "temporal_profile_id": r["temporal_profile_id"], "spatial_class": r["spatial_class"],
                     "spatial_class_measured": r["spatial_class_measured"],
                     "placement_class": sp.get("placement_class", ""),
                     "allocation_surface": sp.get("allocation_surface", ""),
                     "located_mass_fraction": sp.get("located_mass_fraction", ""),
                     "unresolved_Mt_AR5": sp.get("unresolved_Mt_AR5", ""),
                     "flatness_class": te.get("flatness_class", ""),
                     "temporal_evidence_grade": te.get("evidence_grade", ""),
                     "fallback_events": str(fb[0]), "fallback_Mt_AR5": _q(fb[1]) if fb[0] else "",
                     "geometry_id": r["geometry_id"], "release_height_class": r["release_height_class"],
                     "licence_status": r["licence_status"]})
    return fields, ("source_stream_id",), rows



# --- the air beta (rc48 lane) --------------------------------------------------------------
# Seven sectors compute an air-pollutant layer from the same activity the GHG layer burns,
# counts and collects; it was registered into the release manifest in this lane after
# shipping unhashed since its birth. Native kt only, never CO2e; species are NOT additive
# across the particulate strata (dim_pollutant carries the containment).

AIR_ANNUAL_FIELDS = ("sector_id", "period_id", "category", "subitem", "pollutant",
                     "emissions_kt", "uncert_pct", "assurance")

# (product_id, sector_id, period_id, subitem builder). Power's two coal strata share
# (category, fuel), so its subitem carries fuel_detail behind a pipe; railways' subitem is
# its fuel column. Everything else ships a subitem of its own.
_AIR_SECTOR_TABLES = (
    ("air.national", "agriculture", "CY2024", lambda r: r["subitem"]),
    ("air.residential", "residential", "CY2024", lambda r: r["subitem"]),
    ("air.transport", "transport", "CY2024", lambda r: r["subitem"]),
    ("air.power", "power", "FY2023-24",
     lambda r: r["fuel"] + ("|" + r["fuel_detail"] if r.get("fuel_detail") else "")),
    ("air.railways", "railways", "CY2024", lambda r: r["fuel"]),
    ("air.waste", "waste", "CY2024", lambda r: r["subitem"]),
    ("air.aviation", "aviation", "FY2023-24", lambda r: r["subitem"]),
)


def fact_air_annual(src):
    """The union of the seven sector layers at (sector, period, category, subitem,
    pollutant): emissions_kt and uncert_pct byte-copied from each sector's own table, the
    assurance word from the papers' own vocabulary (pkinv.report.figures.AIR_ASSURANCE).
    kt of the named species; a sum across pollutants is meaningless and the query layer
    refuses it."""
    from pkinv.report.figures import AIR_ASSURANCE
    rows = []
    for product_id, sector, period, subitem_of in _AIR_SECTOR_TABLES:
        for r in src.rows(product_id):
            rows.append({"sector_id": sector, "period_id": period,
                         "category": r["category"], "subitem": subitem_of(r),
                         "pollutant": r["pollutant"], "emissions_kt": r["emissions_kt"],
                         "uncert_pct": r.get("uncert_pct", ""),
                         "assurance": AIR_ASSURANCE[sector]})
    key = ("sector_id", "period_id", "category", "subitem", "pollutant")
    return AIR_ANNUAL_FIELDS, key, rows


def fact_air_timeseries(src):
    """Agriculture's 1990-2024 national series by (year, pollutant, category), the shipped
    table byte-copied - including its own TOTAL rows, which are the source's sums, not
    ours."""
    fields = ("year", "pollutant", "category", "emissions_kt")
    rows = [{k: r[k] for k in fields} for r in src.rows("air.timeseries")]
    return fields, ("year", "pollutant", "category"), rows


AIR_PANEL_FIELDS = ("sector_id", "period_id", "configuration_id", "category",
                    "pollutant", "emissions_kt", "coverage_scope")


def fact_air_panel(src):
    """The nine-fiscal-year covered-sources rollup, servable: one row per
    (sector, period, configuration, category, species), kt (the product's Gg, 1:1).
    Two configurations since the air spatial Wave A: REF_2023_24 (household dung on
    the survey-anchored series, the reference since rc67) and L_HERD1624 (all the
    diverted dung of each year's herd; residential differs, every other sector
    identical by construction). Every row carries
    coverage_scope=covered_sources_only - the query layer surfaces it as a
    limitation, because this panel is NOT a complete national seven-species
    inventory and must never be served as one. Grid power is in it only for the species
    its admission register prices (oil and diesel SO2); its screening scenario pair for
    every species ships beside the panel (fact_air_absence_screening), never inside it."""
    rows = [{"sector_id": r["sector_id"], "period_id": r["period_id"],
             "configuration_id": r["configuration_id"],
             "category": r["category"], "pollutant": r["pollutant"],
             "emissions_kt": r["emissions_Gg"],
             "coverage_scope": r["coverage_scope"]}
            for r in src.rows("air.annual")]
    return (AIR_PANEL_FIELDS,
            ("sector_id", "period_id", "configuration_id", "category", "pollutant"),
            rows)


def fact_air_adm1(src):
    """The ALL-SECTOR provincial air layer: every pollutant row times its own stream's
    declared province vector (the six inherited sectors), agriculture by its own layer;
    share_status carries the vector's standing (incl. unallocated_below_adm1 for aviation
    cruise, which is placed here and nowhere finer), evidence_grade/located_share the
    stream's own support. kt byte-copied from air.adm1."""
    fields = ("sector_id", "period_id", "province", "category", "subitem", "proxy",
              "pollutant", "emissions_kt", "share_status", "evidence_grade", "located_share")
    rows = [{k: r[k] for k in fields} for r in src.rows("air.adm1")]
    key = ("sector_id", "period_id", "province", "category", "subitem", "proxy", "pollutant")
    return fields, key, rows


def fact_air_adm2(src):
    """The ALL-SECTOR district air layer on the canonical shape frame: each row its
    stream's normalized shape vector (agriculture re-keyed from its own allocator); the
    no-polygon census units and the GB/AJK/ICT residual ride allocation_status with their
    unit_name; aviation cruise is ABSENT here - typed in the query layer, never zeroed.
    kt byte-copied from air.adm2."""
    fields = ("sector_id", "period_id", "shape_id", "adm2_ids", "unit_name", "province",
              "category", "subitem", "proxy", "pollutant", "emissions_kt",
              "allocation_status", "evidence_grade", "located_share")
    rows = [{k: r[k] for k in fields} for r in src.rows("air.adm2")]
    key = ("sector_id", "period_id", "shape_id", "unit_name", "category", "subitem",
           "proxy", "pollutant")
    return fields, key, rows


def fact_air_adm1_year(src):
    """Anchor stream x province x YEAR x configuration, all nine periods - the
    provincial air layer the query surface refused until the rc49 spatial family
    existed, and refused after it existed too (air_panel_national_only), which is
    the same registered-but-read-by-nothing gap fact_adm1_year closed for the
    greenhouse-gas lane after rc47.

    The source is the release's own nine-year product (pakemis_air_adm1_by_year.csv):
    each pollutant mass on its anchor stream's OWN province marginals for that period
    - the greenhouse-gas cube's dispatch, never a fresh guess. emissions_kt is the
    product's emissions_Gg verbatim: a gigagram IS a kilotonne, and kt is the unit
    every air fact serves. TWO CONFIGURATIONS (REF_2023_24 and the ledger series
    L_HERD1624, residential dung alone differing); a consumer that does not filter
    configuration_id double-counts, so the engine defaults REF and validates.
    Evidence per (period, stream) is the weight registry's, joined in
    pakemis_air_spatial_support_by_year.csv - this table is the mass, that one its
    provenance."""
    fields = ("configuration_id", "period_id", "province", "sector_id",
              "source_stream_id", "pollutant", "emissions_kt")
    rows = [{"configuration_id": r["configuration_id"], "period_id": r["period_id"],
             "province": r["province"], "sector_id": r["sector_id"],
             "source_stream_id": r["source_stream_id"], "pollutant": r["pollutant"],
             "emissions_kt": r["emissions_Gg"]}
            for r in src.rows("air.adm1_by_year")]
    # sector_id is part of the key: a stream is a geography, and two sectors may ride one
    # (IPPU soda ash on the general-industry gas stream, fugitive petrol on the two-wheeler
    # stream), so (stream, province, pollutant) alone names two rows - see
    # pkinv.report.air_spatial_by_year.load_atoms
    key = ("configuration_id", "period_id", "province", "sector_id", "source_stream_id",
           "pollutant")
    return fields, key, rows


def fact_air_adm2_year(src):
    """Sector x district x YEAR x configuration on the canonical shape frame, all nine
    periods - the district air layer as the query surface sees it, aggregated per
    (sector, pollutant, shape) from the same one allocation the grid and the ADM1
    table are marginals of.

    WHAT IT DOES NOT CARRY: the aviation cruise share (typed at ADM1 and in
    pakemis_air_unallocated_by_year.csv, never zeroed here), and any evidence badge -
    whether a year's geography is measured or the reference pattern rescaled is the
    weight registry's to say, per (period, stream), joined in
    pakemis_air_spatial_support_by_year.csv. kt is the product's Gg verbatim
    (one gigagram is one kilotonne)."""
    fields = ("configuration_id", "period_id", "shape_id", "adm2_ids",
              "allocation_status", "province", "sector_id", "pollutant",
              "emissions_kt")
    rows = [{"configuration_id": r["configuration_id"], "period_id": r["period_id"],
             "shape_id": r["shape_id"], "adm2_ids": r["adm2_ids"],
             "allocation_status": r["allocation_status"], "province": r["province"],
             "sector_id": r["sector_id"], "pollutant": r["pollutant"],
             "emissions_kt": r["emissions_Gg"]}
            for r in src.rows("air.adm2_by_year")]
    key = ("configuration_id", "period_id", "shape_id", "sector_id", "pollutant")
    return fields, key, rows


def fact_air_source_classes(src):
    """The source-class air layer at class grain (rc58 industry; rc59 ippu and fugitives): every
    (sector, period, class, species) estimate with its factor rows, activity and uncertainty,
    and beside them the typed absences (a species no held factor prices; a class whose sulfur
    evidence is not valid for the year; a class with no admissible factor or no series), the
    IE pointers (cement gas and coal into the integrated kiln, captive oil into the industrial
    liquids, cement process particulate into the integrated kiln) and the years a class has no
    activity. Estimate rows sum to the panel's atoms of that sector per (period, species); the
    rest carry no kt. Byte-copied from the layer's own detail file."""
    fields = ("period_id", "fiscal_end_year", "sector_id", "source_class_id", "physical_source_id",
              "category", "fuel", "equipment_type", "control_state", "pollutant",
              "activity_value", "activity_unit", "ef_ids", "emissions_kt", "uncert_pct",
              "status", "ghg_anchor_module", "ghg_subitem", "basis")
    rows = [{k: r[k] for k in fields} for r in src.rows("air.source_classes")]
    return fields, ("sector_id", "period_id", "source_class_id", "pollutant"), rows


def fact_air_lahore(src):
    """Lahore District's air pollutants by sector, period and configuration - the release's own
    ADM2 allocation cut for one census district, each row with its anchor streams' weight-registry
    basis - beside the NATIONAL mass no geometry placed below a province (row_kind
    unplaced_national), which a district figure is read against and never added to. Territorial:
    neighbouring districts and secondary particulate are outside it by construction."""
    fields = ("period_id", "configuration_id", "row_kind", "sector_id", "pollutant",
              "emissions_Gg", "geography", "allocation_basis", "note")
    rows = [{k: r[k] for k in fields} for r in src.rows("air.lahore")]
    return fields, ("period_id", "configuration_id", "row_kind", "sector_id", "pollutant"), rows


def fact_air_absence_screening(src):
    """The air panel's two big typed absences priced as SCENARIO ENDS, per period and
    species - the completeness-mass rule applied to air. Power carries a PAIR
    (controlled_case..uncontrolled: the two ends a fleet with an unpublished control
    inventory lies between); industry carries the uncontrolled end alone, its low end
    a typed absence. NEVER summed into the covered panel - the engine serves these
    rows in the envelope's completeness block, beside the headline, and a guard test
    holds the headline unchanged by their existence. Byte-copied from the ledger."""
    fields = ("period_id", "sector_id", "pollutant", "scenario_controlled_kt",
              "scenario_uncontrolled_kt", "controlled_absence_reason", "factor_basis",
              "gap_id")
    rows = [{k: r[k] for k in fields} for r in src.rows("air.absence_screening")]
    return fields, ("period_id", "sector_id", "pollutant"), rows


# ---------------------------------------------------------------------------------------------
# The activity data behind the estimates, published so it can be used without PakEmis.
#
# These eight are pass-throughs of outputs/activity/*.csv, which pkinv.activity.publish builds from
# the hand-verified ingest tree under one declared vocabulary. Nothing is recomputed here. What the
# semantic layer adds is what it adds to every table: a digest, a primary key, and - in `closure` -
# the sentence a reader needs before they add two rows together.
#
# ⚠ THE `closure` STRINGS ARE NOT DESCRIPTIONS, THEY ARE WARNINGS. Fuel sold in a province is not
# fuel burned there; offtake is distribution, not application; monthly power is generation, and the
# fuel behind it was never measured monthly. Each of those is a plausible misreading that the table
# itself cannot prevent, so the contract says it.
ACTIVITY_KEY = ("source_id", "source_row", "source_column", "variable", "category")


def _activity(src, name):
    """The READABLE table (outputs/activity/public/): `Period · Location · Measure · … · Record ID`.
    Since 2026-09-17 this is what ships under fact_activity_*; the twenty technical fields of every
    row ship beside it in fact_activity_source_details, joined on Record ID."""
    rows = src.rows("activity_public.%s" % name)
    # ⚠ NAME THE COLLECTION. `rows[0].keys()` on an empty table is an IndexError six frames deep,
    # and a mis-declared register row - a path typo, a filter that matches nothing - is exactly how
    # a collection comes back empty. The publication is declarative; its failures should be too.
    if not rows:
        raise ValueError("activity_public.%s published no rows: check its rows in data/activity_files.csv" % name)
    return tuple(rows[0].keys()), ("Record ID",), rows


def fact_activity_source_details(src):
    """Every technical row behind the seventeen readable tables, verbatim, under the Record ID the
    readable row carries. ⚠ THE KEY IS THE TECHNICAL ONE, so this table's result_row_id IS the
    Record ID - the same function on the same table name and key values minted both."""
    rows = src.rows("activity.source_details")
    if not rows:
        raise ValueError("activity.source_details published no rows")
    return tuple(rows[0].keys()), ACTIVITY_KEY, rows


def fact_activity_fuel_sales_national(src):
    return _activity(src, "fuel_sales_national")


def fact_activity_fuel_sales_area(src):
    return _activity(src, "fuel_sales_area")


def fact_activity_livestock(src):
    return _activity(src, "livestock")


def fact_activity_crops(src):
    return _activity(src, "crops")


def fact_activity_fertiliser(src):
    return _activity(src, "fertiliser")


def fact_activity_power_plants(src):
    return _activity(src, "power_plants")


def fact_activity_power_monthly(src):
    return _activity(src, "power_monthly")


def fact_activity_household_fuel(src):
    return _activity(src, "household_fuel")


def fact_activity_industry_fuel(src):
    return _activity(src, "industry_fuel")


def fact_activity_industry_production(src):
    return _activity(src, "industry_production")


def fact_activity_gas_supply(src):
    return _activity(src, "gas_supply")


def fact_activity_gas_network(src):
    return _activity(src, "gas_network")


def fact_activity_waste_services(src):
    return _activity(src, "waste_services")


def fact_activity_waste_flows(src):
    return _activity(src, "waste_flows")


def fact_activity_railways(src):
    return _activity(src, "railways")


def fact_activity_aviation(src):
    return _activity(src, "aviation")


def fact_activity_vehicles(src):
    return _activity(src, "vehicles")


FACTS = (
    ("fact_activity_industry_fuel", fact_activity_industry_fuel,
     {"id_column": "Record ID", "rule": "additive_within_consumer_period_and_unit",
      "closure": "coal, gas and fuel use by published industrial customer group. ⚠ PRINTED TOTAL ROWS ARE WITHHELD, not published beside their own members; the vintage panel carries one year as several editions and only rows sharing an edition may be summed; MMCFD is a RATE, not a quantity; and the feedstock gas a fertiliser plant turns into ammonia is never the fuel gas it burns"}),
    ("fact_activity_industry_production", fact_activity_industry_production,
     {"id_column": "Record ID", "rule": "additive_within_product_period_and_unit",
      "closure": "clinker, cement and other industrial output. ⚠ COMPANY-REPORTED, NEVER ALLOCATED TO PLANTS: a company total covers every plant it owns and nothing in this release splits it. Despatch is SALES, not production, and trade is neither"}),
    ("fact_activity_gas_supply", fact_activity_gas_supply,
     {"id_column": "Record ID", "rule": "additive_within_field_period_and_unit",
      "closure": "gas and oil produced and supplied. ⚠ THE NATIONAL AND PROVINCIAL TABLES PRINT CRUDE IN DIFFERENT UNITS - thousand barrels against barrels - and the unit column is the only thing that says so"}),
    ("fact_activity_gas_network", fact_activity_gas_network,
     {"id_column": "Record ID", "rule": "not_additive",
      "closure": "⚠ UNACCOUNTED-FOR GAS IS NOT AN EMISSION FIGURE AND MUST NEVER BE USED AS ONE. It is the difference between gas purchased and gas billed - theft, meter error and billing differences alongside physical leakage - and multiplying it by a GWP is the error this contract exists to prevent. The three flow rows are not additive: marketable gas already contains the other two"}),
    ("fact_activity_waste_services", fact_activity_waste_services,
     {"id_column": "Record ID", "rule": "additive_within_survey_scope_and_locality",
      "closure": "reported household disposal routes and sanitation shares. ⚠ THE `collected` AND `uncollected` ROWS ARE SUMS OF ROUTES 1-3 AND 4-7 and are typed `derived`; published beside their own parts they would count the same households twice"}),
    ("fact_activity_waste_flows", fact_activity_waste_flows,
     {"id_column": "Record ID", "rule": "additive_within_tier",
      "closure": "⚠ MODELLED, NOT MEASURED. Generation is a per-capita rate over an interpolated district population panel; collection, open burning and the unresolved remainder are a fate partition. No row here is measured municipal tonnage, and the household survey reads a different split"}),
    ("fact_activity_railways", fact_activity_railways,
     {"id_column": "Record ID", "rule": "additive_within_metric_period_and_unit",
      "closure": "Pakistan Railways' own metered fuel and published traffic. ⚠ A PRINTED NIL AND AN ABSENCE ARE DIFFERENT: railcar workings are zero because none ran, shunting is empty because no table reports it. Total train-km is the sum of the passenger and freight split beside it"}),
    ("fact_activity_aviation", fact_activity_aviation,
     {"id_column": "Record ID", "rule": "additive_within_airport_year_and_measure",
      "closure": "aircraft movements, passengers and freight by airport and by airline. ⚠ AVIATION COUNTS ITS FISCAL YEAR FROM THE START - year 2023 is FY2023-24 - which is the opposite of the railway, waste and transport tables in this same collection"}),
    ("fact_activity_vehicles", fact_activity_vehicles,
     {"id_column": "Record ID", "rule": "additive_within_class_year_and_place",
      "closure": "⚠ CUMULATIVE REGISTERED STOCK AS AT 30 JUNE. Not observed traffic, not an active fleet: a scrapped vehicle stays in the total until it is formally deregistered. The kilometre rates and fuel shares beside it are typed `assumption` because their own source declares no provenance"}),
    ("fact_activity_source_details", fact_activity_source_details,
     {"rule": "not_a_quantity_table",
      "closure": "the twenty technical fields behind every readable activity row, verbatim; join on "
                 "Record ID. Sums belong to the readable tables and their combinable column, not here"}),
    ("fact_activity_fuel_sales_national", fact_activity_fuel_sales_national,
     {"id_column": "Record ID", "rule": "additive_within_product_period_and_unit",
      "closure": "OCAC's national customer-class tables. SALES INTO A CUSTOMER CLASS, NOT FUEL "
                 "BURNED IN IT. Kept apart from the area tables because OCAC never prints their "
                 "joint breakdown; an empty value is a dash the source printed and is not zero"}),
    ("fact_activity_fuel_sales_area", fact_activity_fuel_sales_area,
     {"id_column": "Record ID", "rule": "additive_only_where_combinable_says_so",
      "closure": "OCAC's monthly AREA pages. FUEL SOLD IN A PROVINCE IS NOT FUEL BURNED IN IT - "
                 "freight crosses provincial boundaries. The cumulative editions overlap the "
                 "monthly ones: sum only rows whose combinable column permits it"}),
    ("fact_activity_livestock", fact_activity_livestock,
     {"id_column": "Record ID", "rule": "additive_within_species_period_and_evidence",
      "closure": "census enumeration and the Economic Survey's forward estimate in one table, told "
                 "apart by `evidence`. A PROJECTION IS NEVER SUMMED WITH A COUNT, which is what the "
                 "combinable column says on every projected row"}),
    ("fact_activity_crops", fact_activity_crops,
     {"id_column": "Record ID", "rule": "additive_within_crop_period_and_variable",
      "closure": "area and production by crop and place. A ROW WITH evidence=allocation IS A POOLED "
                 "PARENT SPLIT BY A DECLARED RULE, not an observed district figure; the rule is in "
                 "`transform`. Districts whose identity could not be resolved are withheld, not "
                 "published against a blank place"}),
    ("fact_activity_fertiliser", fact_activity_fertiliser,
     {"id_column": "Record ID", "rule": "additive_within_product_period_and_unit",
      "closure": "OFFTAKE IS DISTRIBUTION - fertiliser sold, not fertiliser applied to fields. "
                 "TONNES OF PRODUCT AND TONNES OF NITROGEN ARE DIFFERENT UNITS and are never added: "
                 "the unit column tells them apart, and phosphate and potash are neither"}),
    ("fact_activity_power_plants", fact_activity_power_plants,
     {"id_column": "Record ID", "rule": "additive_within_fiscal_year_and_unit",
      "closure": "plant-level fuel and generation from NEPRA's State of Industry reports. Fuel "
                 "quantities come in four different units and adding across them means nothing; the "
                 "implied heat rate is DERIVED by PakEmis from this row's own energy and generation "
                 "and is a ratio, not a reported figure"}),
    ("fact_activity_power_monthly", fact_activity_power_monthly,
     {"id_column": "Record ID", "rule": "additive_within_month",
      "closure": "MONTHLY GENERATION, AND ONLY GENERATION. The source measured electricity monthly "
                 "and never measured fuel monthly, so nothing here may be read as monthly fuel "
                 "consumption. PBS prints two rows under one truncated plant name in 24 cases; both "
                 "are published and `source_row` is how they are told apart"}),
    ("fact_activity_household_fuel", fact_activity_household_fuel,
     {"id_column": "Record ID", "rule": "additive_within_survey_round_unit_and_stratum",
      "closure": "DESIGN-WEIGHTED HIES ESTIMATES, not a census. The SURVEY ROUND is the period, "
                 "whatever year the inventory later applies the quantity to; n_obs travels as "
                 "sample support and a mean per household is not additive across strata"}),
    ("fact_annual", fact_annual, {"rule": "additive", "closure": "sum of atoms == national total per period and configuration; L = REF - residential(REF) + residential(L)"}),
    ("fact_annual_calendar", fact_annual_calendar, {"rule": "additive_within_sector", "closure": "agriculture only; calendar-year reconstruction, not a fiscal product"}),
    ("fact_monthly", fact_monthly, {"rule": "additive", "closure": "the twelve months of a period sum to its annual atom exactly (closure_basis native_mass)"}),
    ("fact_adm1_month", fact_adm1_month, {"rule": "additive", "closure": "sum over provinces == the stream's monthly mass (declared shares sum to one)"}),
    ("fact_adm2_month", fact_adm2_month, {"rule": "additive_within_view_and_across_views", "closure": "ADM1 == ADM2 + unallocated below ADM1, per gas and month; the three spatial views are disjoint and additive"}),
    ("fact_adm1_year", fact_adm1_year, {"rule": "additive_within_view_and_across_views",
     "closure": "national == sum over provinces, per gas, view and PERIOD, for all nine "
                "periods - ADM1 is exact (the closure identity's left-hand side), with "
                "the unallocated-below-ADM1 mass INSIDE these provincial rows"}),
    ("fact_adm2_year", fact_adm2_year, {"rule": "additive_within_view_and_across_views", "closure": "ADM1 == ADM2 + unallocated below ADM1, per gas and PERIOD, for all nine periods; the three spatial views are disjoint and additive. The geography of eight of the nine periods is the reference year's rescaled - see pakemis_spatial_weights_by_year.csv for the basis per stream-year"}),
    ("fact_spatial_basis_year", fact_spatial_basis_year, {"rule": "additive", "closure": "per period: the sum over module, reporting sector and spatial_time_basis == fact_adm1_year's total; a partition of the year's mass by what its within-province geography rests on. n_streams counts stream-years and is NOT additive across reporting sectors of one stream"}),
    ("fact_unallocated", fact_unallocated, {"rule": "additive", "closure": "the mass a spatial level does not place - THE REFERENCE YEAR'S; another year's is the same streams' rows in fact_adm1_year, which is where the query reads it"}),
    ("fact_uncertainty", fact_uncertainty, {"rule": "envelope_not_quadrature", "closure": "per-category envelopes; NEVER combined in quadrature across categories (the table's own aggregation_rule column)"}),
    ("fact_uncertainty_series", fact_uncertainty_series, {"rule": "not_additive", "closure": "quantiles of draws; a sum of quantiles is not a quantile of a sum"}),
    ("fact_completeness", fact_completeness, {"rule": "categorical", "closure": "one notation key per category x gas"}),
    ("fact_completeness_mass", fact_completeness_mass, {"rule": "bounds_not_additive", "closure": "screening bounds outside every total; composable only where the column says so"}),
    ("fact_transfer", fact_transfer, {"rule": "ledger", "closure": "per ledger and configuration: control == transfers + unresolved"}),
    ("fact_evidence", fact_evidence, {"rule": "categorical", "closure": "one lineage row per stream"}),
    ("fact_air_annual", fact_air_annual, {"rule": "additive_within_pollutant_only",
     "closure": "seven sector layers, native kt; rows sum within one pollutant and one "
                "sector's own scope only - the particulate strata contain one another "
                "(dim_pollutant) and a sum across species is refused, never computed"}),
    ("fact_air_timeseries", fact_air_timeseries, {"rule": "additive_within_pollutant_only",
     "closure": "agriculture national 1990-2024; the TOTAL category rows are the source's "
                "own sums and must not be added to the category rows beside them"}),
    ("fact_air_panel", fact_air_panel,
     {"rule": "additive_within_pollutant_only",
      "closure": "the covered panel's reference-period slice reproduces "
                 "fact_air_annual's six single-year layers to the rounding of those "
                 "files (industry, covered since rc58, has no single-year layer and is "
                 "asserted against its own class detail); coverage_scope=covered_sources_only on every "
                 "row, the absences typed in pakemis_air_coverage_matrix.csv"}),
    ("fact_air_adm1", fact_air_adm1, {"rule": "additive_within_pollutant_only",
     "closure": "every sector's provinces sum to its national layer per pollutant; the "
                "share vectors are the streams' own (pakemis_grid_provincial_check)"}),
    ("fact_air_adm2", fact_air_adm2, {"rule": "additive_within_pollutant_only",
     "closure": "districts sum to the provinces per (sector, pollutant) net of the typed "
                "aviation-cruise retention; the canonical shape frame throughout"}),
    ("fact_air_adm1_year", fact_air_adm1_year, {"rule": "additive_within_pollutant_only",
     "closure": "per configuration, period and pollutant the provinces sum to the covered "
                "panel exactly (ADM1 carries the cruise mass; the closure identity's "
                "left-hand side) - two configurations, NEVER summed across them. rc60 broke "
                "this briefly by publishing the admitted power SO2 at national grain, with no "
                "province to sum into; rc61 gave it a frame of its own and the sentence is "
                "true again"}),
    ("fact_air_source_classes", fact_air_source_classes,
     {"rule": "additive_within_pollutant_only",
      "closure": "status=estimate rows sum to the panel's atoms of their sector_id per (period, "
                 "species) (tests/test_industry_air.py); typed_absent, IE and no_activity rows "
                 "carry no kt and are never zeros; one physical source is priced once"}),
    ("fact_air_lahore", fact_air_lahore,
     {"rule": "additive_within_pollutant_only",
      "closure": "district rows are pakemis_air_adm2_by_year.csv for shape "
                 "60131773B12131197496886 verbatim; unplaced_national rows equal the "
                 "unallocated table's below_adm1 term per (period, configuration, species) and "
                 "are read beside the district, never added to it"}),
    ("fact_air_absence_screening", fact_air_absence_screening,
     {"rule": "scenario_ends_never_summed",
      "closure": "outside every total by construction: the covered panel's headline "
                 "is byte-unchanged by these rows; power's pair satisfies "
                 "controlled <= uncontrolled per (period, species) wherever both ends "
                 "are priced"}),
    ("fact_air_adm2_year", fact_air_adm2_year, {"rule": "additive_within_pollutant_only",
     "closure": "panel == ADM2 + outside_frame + unallocated_below_adm1 per "
                "(configuration, period, pollutant); the cruise share is typed in "
                "pakemis_air_unallocated_by_year.csv, never zeroed here; the geography of "
                "most stream-years is the reference pattern rescaled - "
                "pakemis_air_spatial_support_by_year.csv is the per-mass provenance"}),
)

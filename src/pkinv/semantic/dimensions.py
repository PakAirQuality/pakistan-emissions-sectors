"""Dimension tables: the closed vocabularies every fact row keys into.

Each builder returns (fieldnames, key, rows). Values are the registries' own strings; where a
dimension is code-only in the engine (GWP factors, evidence grades, configuration ids) the
table is the code's vocabulary written out, so a consumer never imports the engine to read it."""
from pkinv.core import configurations as cfg
from pkinv.core import evidence
from pkinv.core import notation
from pkinv.core.gwp import GWP


def dim_period(src):
    """The ten fiscal periods plus the calendar years the agriculture reconstruction publishes:
    basis is a COLUMN, so a request that names a period names its basis with it."""
    rows = []
    for r in src.rows("periods"):
        rows.append({"period_id": r["period_id"], "basis": "fiscal", "label": r["period_id"],
                     "period_start": r["period_start"], "period_end": r["period_end"],
                     "days": r["days"], "fiscal_end_year": r["fiscal_end_year"],
                     "is_reference": r["is_reference"], "availability": "all_sectors",
                     "note": "fiscal year, 1 July to 30 June (%s)" % r["time_basis"]})
    years = sorted({r["year"] for r in src.rows("timeseries_1990_2024")})
    for year in years:
        rows.append({"period_id": "CY%s" % year, "basis": "calendar", "label": "CY%s" % year,
                     "period_start": "%s-01-01" % year, "period_end": "%s-12-31" % year,
                     "days": "", "fiscal_end_year": "", "is_reference": "False",
                     "availability": "agriculture",
                     "note": "calendar-year reconstruction of the agriculture sector only "
                             "(outputs/timeseries_1990_2024.csv); NE for every other sector"})
    fields = ("period_id", "basis", "label", "period_start", "period_end", "days",
              "fiscal_end_year", "is_reference", "availability", "note")
    return fields, ("period_id",), rows


def dim_month(src):
    fields = ("month", "period_id", "fiscal_month_number", "calendar_year", "calendar_month",
              "period_start", "period_end", "days", "special_period_flag")
    rows = [{"month": r["month_id"], "period_id": r["fiscal_year"],
             "fiscal_month_number": r["fiscal_month_number"], "calendar_year": r["calendar_year"],
             "calendar_month": r["calendar_month"], "period_start": r["period_start"],
             "period_end": r["period_end"], "days": r["days_in_month"],
             "special_period_flag": r["special_period_flag"]} for r in src.rows("months")]
    return fields, ("month",), rows


def dim_configuration(src):
    """The two queryable configurations and the structural alternatives beside them.

    S is a residential-module substitution of the reference (every other sector identical by
    construction), and the table says so in columns: what it substitutes and at which grains
    it exists, so an engine composes S = REF - residential(REF) + residential(S) rather than
    looking for atoms that were never written."""
    fields = ("configuration_id", "kind", "queryable", "display_name", "substitutes_module",
              "available_periods", "available_grains", "family_id", "family_role",
              "national_total_Mt", "national_delta_Mt", "axis", "module", "note")
    from pkinv.core.reporting_window import CORE_PERIOD_IDS
    rows = []
    for cid in cfg.ALL:
        rows.append({"configuration_id": cid, "kind": "reference" if cid == cfg.REFERENCE else "structural_alternative",
                     "queryable": "yes", "display_name": cid,
                     "substitutes_module": "residential;agriculture" if cid != cfg.REFERENCE else "",
                     "available_periods": CORE_PERIOD_IDS[0] + ".." + CORE_PERIOD_IDS[-1],
                     "available_grains": "annual_atom;monthly_atom;adm1_year;adm2_year;adm1_month;adm2_month;annual_grid;air_annual;air_adm1_year;air_adm2_year;air_grid",
                     "family_id": "residential_nitrogen", "family_role": "reference" if cid == cfg.REFERENCE else "alternative",
                     "national_total_Mt": "", "national_delta_Mt": "", "axis": "dung_destination;nitrogen_method",
                     "module": "residential;agriculture",
                     "note": "Household dung basis: %s; nitrogen method: %s. Structural cases have no assigned probabilities."
                         % (cfg.dung_basis(cid), cfg.nitrogen_method(cid))})
    for r in src.rows("configurations.national"):
        cid = r["configuration_id"]
        if cid in cfg.ALL:
            continue
        rows.append({"configuration_id": cid, "kind": "structural_alternative",
                     "queryable": "no", "display_name": cid, "substitutes_module": r["module"],
                     "available_periods": "FY2023-24", "available_grains": "national_total",
                     "family_id": r["family_id"], "family_role": r["family_role"],
                     "national_total_Mt": r["national_total_Mt"],
                     "national_delta_Mt": r["national_delta_Mt"], "axis": r["axis"],
                     "module": r["module"], "note": r["note"]})
    from decimal import Decimal
    totals = {cid: Decimal(0) for cid in cfg.ALL}
    for atom in src.rows("annual.configuration_atoms"):
        if atom["period_id"] == "FY2023-24" and atom["co2e_Mt_AR5"]:
            totals[atom["configuration_id"]] += Decimal(atom["co2e_Mt_AR5"])
    for row in rows[:len(cfg.ALL)]:
        total = totals[row["configuration_id"]]
        row["national_total_Mt"] = str(total)
        row["national_delta_Mt"] = str(total - totals[cfg.REFERENCE])
    return fields, ("configuration_id",), rows


def dim_gwp():
    fields = ("gwp_basis", "gas_key", "factor", "source")
    source = {"AR5": "IPCC AR5 WGI Table 8.A.1 (GWP-100)",
              "AR6": "IPCC AR6 WGI Chapter 7 Supplementary Material Table 7.SM.7 (GWP-100)"}
    rows = [{"gwp_basis": basis, "gas_key": gas, "factor": repr(factor), "source": source[basis]}
            for basis, table in GWP.items() for gas, factor in table.items()]
    return fields, ("gwp_basis", "gas_key"), rows


def dim_gas(src):
    origins = {}
    for r in src.rows("annual.atomic"):
        origins.setdefault(r["gas"], set()).add(r["gas_origin"])
    fields = ("gas", "origins_present", "gwp_note")
    rows = [{"gas": gas, "origins_present": ";".join(sorted(o for o in ors if o)),
             "gwp_note": ("fossil-origin CH4 carries its own factor (CH4_fossil)" if gas == "CH4"
                          else "")} for gas, ors in origins.items()]
    return fields, ("gas",), rows


def _parent(code):
    parts = code.split(".")
    return ".".join(parts[:-1]) if len(parts) > 1 else ""


def dim_category(src):
    """IPCC code x engine category, with the hierarchy by code prefix and the notation keys per
    gas from completeness.csv (the release's own completeness statement, not re-declared)."""
    rows = {}
    for r in src.rows("completeness"):
        key = (r["code"], r["category"])
        row = rows.setdefault(key, {"ipcc_code": r["code"], "category": r["category"],
                                    "parent_code": _parent(r["code"]), "engine_category": r["engine_category"],
                                    "notation_keys": {}, "gap_ids": set(), "sector_ids": set()})
        row["notation_keys"][r["gas"]] = r["notation_key"]
        if r["gap_id"]:
            row["gap_ids"].add(r["gap_id"])
    for r in src.rows("provenance.source_streams"):
        key = (r["ipcc_code"], r["ipcc_category"])
        if key in rows:
            rows[key]["sector_ids"].add(r["module"])
    fields = ("ipcc_code", "category", "parent_code", "engine_category", "sector_ids",
              "notation_keys", "gap_ids")
    out = []
    for row in rows.values():
        out.append({"ipcc_code": row["ipcc_code"], "category": row["category"],
                    "parent_code": row["parent_code"], "engine_category": row["engine_category"],
                    "sector_ids": ";".join(sorted(row["sector_ids"])),
                    "notation_keys": ";".join("%s=%s" % kv for kv in sorted(row["notation_keys"].items())),
                    "gap_ids": ";".join(sorted(row["gap_ids"]))})
    return fields, ("ipcc_code", "category"), out


def dim_geography(src):
    """PK, the five ADM1 units, and every canonical ADM2 unit (incl. the two without a polygon
    and the outside-provinces residual), keyed by geography_id."""
    fields = ("geography_id", "level", "name", "parent_id", "shape_id", "shape_name",
              "geometry_relation", "has_polygon", "unit_kind", "status", "note")
    rows = [{"geography_id": "PK", "level": "national", "name": "Pakistan", "parent_id": "",
             "shape_id": "", "shape_name": "", "geometry_relation": "", "has_polygon": "yes",
             "unit_kind": "country", "status": "active",
             "note": "the inventory's national scope (the four provinces plus the territories row)"}]
    header = src.rows("province_shares")[0]
    # the header carries helper columns beside the marginals (proxy/source/note, and since the
    # transport re-base the per-row `other_membership` declaration); the dimension is the five
    # UNITS, so anything else in the header must be named here or the build stops - the rc47
    # follower where other_membership shipped as a sixth "province" is the reason this is a
    # closed vocabulary and not an exclusion list.
    provinces = [c for c in header if c not in ("proxy", "source", "note", "other_membership")]
    expected = {"Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan", "Other"}
    if set(provinces) != expected:
        raise ValueError("dim_geography: province_shares.csv header yields %r, not the five ADM1 units %r"
                         % (sorted(provinces), sorted(expected)))
    for prov in provinces:
        rows.append({"geography_id": "ADM1:%s" % prov, "level": "adm1", "name": prov,
                     "parent_id": "PK", "shape_id": "", "shape_name": "",
                     "geometry_relation": "", "has_polygon": "no" if prov == "Other" else "yes",
                     "unit_kind": "province" if prov != "Other" else "territories_residual",
                     "status": "active",
                     "note": "" if prov != "Other" else "GB, AJK and ICT: no shape in the district frame"})
    for r in src.rows("adm2_canonical"):
        rows.append({"geography_id": "ADM2:%s" % r["adm2_id"], "level": "adm2",
                     "name": r["canonical_name"], "parent_id": "ADM1:%s" % r["province_id"],
                     "shape_id": r["shape_id"], "shape_name": r["shape_name"],
                     "geometry_relation": r["geometry_relation"],
                     "has_polygon": "yes" if r["shape_id"] else "no",
                     "unit_kind": r["unit_kind"], "status": r["status"], "note": r["note"]})
    return fields, ("geography_id",), rows


STREAM_FIELDS = ("source_stream_id", "module", "reporting_sector", "ipcc_code", "ipcc_category",
                 "sub_category",
                 "process", "gas", "methane_origin", "notation_key", "evidence_class",
                 "temporal_class", "temporal_profile_id", "spatial_class", "spatial_class_measured",
                 "spatial_view", "spatial_profile_id", "geometry_id", "release_height_class",
                 "activity_parameter_ids", "conversion_parameter_ids", "factor_parameter_ids",
                 "scenario_id", "source_id", "source_document_ids", "archival_state", "licence_status")


def dim_stream(src):
    rows = [{k: r[k] for k in STREAM_FIELDS} for r in src.rows("provenance.source_streams")]
    return STREAM_FIELDS, ("source_stream_id",), rows


def dim_evidence_class():
    fields = ("class_id", "axis", "definition")
    rows = [{"class_id": k, "axis": "E", "definition": v} for k, v in evidence.EVIDENCE.items()]
    rows += [{"class_id": k, "axis": "TE", "definition": v} for k, v in evidence.TEMPORAL.items()]
    rows += [{"class_id": k, "axis": "S", "definition": v} for k, v in evidence.SPATIAL.items()]
    return fields, ("axis", "class_id"), rows


def dim_notation_key():
    fields = ("notation_key", "meaning", "carries_mass")
    rows = [{"notation_key": k, "meaning": m, "carries_mass": "yes" if cm else "no"}
            for k, (m, cm) in notation.NOTATION_KEYS.items()]
    return fields, ("notation_key",), rows



# The air beta's species, with the containment that forbids naive sums: BC and OC are
# components of PM2.5, PM2.5 of PM10, PM10 of TSP; PM is AP-42's filterable-PM label and
# VOC/HC are unharmonised source vocabularies beside NMVOC. Derived from the shipped
# tables (a new species stops the build here rather than shipping unnamed).
# The closed seven-species core (the panel's scope) against the supplemental labels a
# source vocabulary ships beside it. VOC and HC are NEVER renamed NMVOC, PM/PM10/TSP are
# never mapped to PM2.5, and BC/OC are components of PM2.5, not additional mass.
_POLLUTANTS = {
    "NOx": ("gas", "", "core7", "nitrogen oxides as NO2"),
    "SO2": ("gas", "", "core7", "sulfur dioxide"),
    "CO": ("gas", "", "core7", "carbon monoxide"),
    "NH3": ("gas", "", "core7", "ammonia"),
    "NMVOC": ("gas", "", "core7", "non-methane volatile organic compounds"),
    "VOC": ("gas", "", "supplemental", "AP-42's VOC label (power); not harmonised with NMVOC"),
    "HC": ("gas", "", "supplemental", "unspeciated hydrocarbons (aviation EEDB label)"),
    "HCl": ("gas", "", "supplemental", "hydrogen chloride (open waste burning)"),
    "TSP": ("particulate", "", "supplemental", "total suspended particulate"),
    "PM": ("particulate", "TSP", "supplemental", "AP-42 filterable PM (power); a stratum, not a species"),
    "PM10": ("particulate", "TSP", "supplemental", "particulate matter under 10 um"),
    "PM2.5": ("particulate", "PM10", "core7", "particulate matter under 2.5 um"),
    "BC": ("particulate", "PM2.5", "core7", "black carbon, a component of PM2.5"),
    "OC": ("particulate", "PM2.5", "supplemental", "organic carbon, a component of PM2.5"),
}

_AIR_PRODUCTS = ("air.national", "air.provincial", "air.district", "air.timeseries",
                 "air.adm1", "air.adm2",
                 "air.atomic_annual", "air.annual", "air.coverage",
                 "air.power_screening", "air.source_classes", "air.lahore", "air.industry_cy2023",
                 "air.residential", "air.transport", "air.power", "air.railways",
                 "air.waste", "air.aviation")


def dim_pollutant(src):
    seen = set()
    for product in _AIR_PRODUCTS:
        for r in src.rows(product):
            # rc58: the industry detail table carries class-level rows with no species (an
            # IE pointer, a typed-absent class, a year with no activity) - not a species
            if r["pollutant"]:
                seen.add(r["pollutant"])
    unknown = seen - set(_POLLUTANTS)
    if unknown:
        raise ValueError("dim_pollutant: unnamed species %r in the shipped air tables"
                         % sorted(unknown))
    fields = ("pollutant", "kind", "contained_in", "core", "note")
    rows = [{"pollutant": p, "kind": k, "contained_in": c, "core": core, "note": n}
            for p, (k, c, core, n) in _POLLUTANTS.items() if p in seen]
    return fields, ("pollutant",), rows


def dim_activity_columns(src):
    """What every column of the readable activity tables means - the data dictionary the brief asked
    for, one row per (file, column), generated by pkinv.activity.present from the same registers."""
    rows = src.rows("activity.column_guide")
    return ("file", "column", "meaning"), ("file", "column"), rows


DIMENSIONS = (
    ("dim_activity_columns", dim_activity_columns),
    ("dim_period", lambda src: dim_period(src)),
    ("dim_month", lambda src: dim_month(src)),
    ("dim_configuration", lambda src: dim_configuration(src)),
    ("dim_gwp", lambda src: dim_gwp()),
    ("dim_gas", lambda src: dim_gas(src)),
    ("dim_category", lambda src: dim_category(src)),
    ("dim_geography", lambda src: dim_geography(src)),
    ("dim_pollutant", lambda src: dim_pollutant(src)),
    ("dim_stream", lambda src: dim_stream(src)),
    ("dim_evidence_class", lambda src: dim_evidence_class()),
    ("dim_notation_key", lambda src: dim_notation_key()),
)

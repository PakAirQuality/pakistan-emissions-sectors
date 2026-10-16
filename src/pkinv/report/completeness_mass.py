"""Coverage gaps, source-specific cases and contextual comparisons, kept distinct.

NE identifies an unestimated source; it does not quantify its mass. Source-specific
screening calculations retain their own periods, boundaries and conditional cases.
Differences from EDGAR and F-gas benchmark or consumption-equivalent quantities are
not floors or upper bounds on missing emissions. None is composed into a national
completeness interval or added to the reference total.
"""
from __future__ import annotations

from pkinv.assets import asset_path

import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

OUT = asset_path(OUTPUTS, "pakemis_completeness_mass.csv")

FIELDS = ("row_type", "ipcc_code", "stream", "scope_status", "notation_key",
          "coverage_state", "configuration_id", "mass_basis", "mass_low_Mt",
          "mass_high_Mt", "composable", "contained_in", "note")

# Retired internal directive target retained for historical traceability only.
DIRECTIVE_TARGET_MT = 47.0

# Historical comparison labels retained for source traceability, never composed.
FUEL_LEDGER_RESIDUAL = "1A2-industrial-fuel residual (benchmark)"
FGAS_BENCHMARK_MT = 11.54


def _rows(path):
    return read_rows(path)


def _config_delta(configurations, config_id):
    for r in configurations:
        if r["configuration_id"] == config_id:
            return float(r["national_delta_Mt"])
    raise SystemExit("completeness-mass ledger names a configuration that does not "
                     "ship: %s" % config_id)


def _screen_row(path, key_col, key, low_col, high_col):
    for r in _rows(asset_path(OUTPUTS, path)):
        if r[key_col] == key:
            return float(r[low_col]), float(r[high_col])
    raise SystemExit("%s has no %r row" % (path, key))


def _screen_val(path, key_col, key, col):
    for r in _rows(asset_path(OUTPUTS, path)):
        if r[key_col] == key:
            return float(r[col])
    raise SystemExit("%s has no %r row" % (path, key))


def _fuel_ledger_residual():
    for r in _rows(asset_path(OUTPUTS, "industry_fuel_ledger_2024.csv")):
        if r.get("control_status") == "benchmark_residual":
            return float(r["Mt_co2e"])
    raise SystemExit("the fuel ledger has lost its benchmark residual row")


# A REFERENCE row's mass is anchored to the engine's own priced streams, by prefix -
# declared here so the anchor is a reviewable table rather than a fuzzy match. rc46 Wave 2
# added the first entry when industrial_solid_fuels_1a2 activated.
REFERENCE_STREAM_PREFIXES = {
    "industrial_solid_fuels_1a2": (
        "industry|industrial-fuel-combustion-(1a2)|brick-kiln-coal",
        "industry|industrial-fuel-combustion-(1a2)|cement-sector-coal"),
    # rc52 (boundary program Wave C): the three IPPU categories that entered as nine-year series
    "ammonia_2b1": ("ippu|ammonia-production|",),
    "steel_2c1": ("ippu|iron-and-steel-production|",),
    "lubricants_2d1": ("ippu|lubricant-use|",),
}


def _reference_stream_masses():
    """{category_id: summed co2e_Mt_AR5 of its anchored streams} from the stream ledger."""
    streams = _rows(asset_path(OUTPUTS, "pakemis_source_streams.csv"))
    out = {}
    for category_id, prefixes in REFERENCE_STREAM_PREFIXES.items():
        out[category_id] = sum(float(r["emissions_ar5"] or 0.0) for r in streams
                               if any(r["source_stream_id"].startswith(p) for p in prefixes))
    return out


def validate_scope_registry(configurations, residual_mt, stream_masses=None):
    """Every screening row names a shipped configuration, and its mass agrees with
    a named configuration's delta. Comparator residuals cannot substitute for that case.
    A REFERENCE row (rc46 Wave 2 onward) is validated instead against the summed
    co2e of its anchored streams in the shipped stream ledger - a registry mass
    agreeing with nothing the build prices is drift, whichever status carries it.
    `stream_masses` is injectable for the drift test and read from the ledger
    otherwise. Returns {category_id: row} for the ledger join."""
    registry = _rows(asset_path(DATA, "scope_registry.csv"))
    if stream_masses is None:
        stream_masses = _reference_stream_masses()
    for row in registry:
        if row["current_status"] != "reference":
            continue
        if row["category_id"] not in REFERENCE_STREAM_PREFIXES:
            raise SystemExit("scope registry: %s is 'reference' but has no stream anchor "
                             "in REFERENCE_STREAM_PREFIXES" % row["category_id"])
        mass = float(row["current_mass_Mt"])
        priced = stream_masses[row["category_id"]]
        if abs(priced - mass) > 0.01:
            raise SystemExit(
                "scope registry: %s carries current_mass_Mt=%.5f but its anchored "
                "streams price %.5f - the registry has drifted from the build"
                % (row["category_id"], mass, priced))
    shipped = {r["configuration_id"]: float(r["national_delta_Mt"])
               for r in configurations if r["configuration_id"]}
    for row in registry:
        if row["current_status"] != "screening":
            continue
        named = [t.strip("() ") for t in row["available_open_data"]
                 .replace("(", " ").replace(")", " ").split()
                 if t.strip("() ") in shipped]
        if not named:
            raise SystemExit("scope registry: %s is 'screening' but names no "
                             "shipped configuration" % row["category_id"])
        mass = float(row["current_mass_Mt"])
        candidates = [shipped[n] for n in named]
        if not any(abs(c - mass) < 0.01 for c in candidates):
            raise SystemExit(
                "scope registry: %s carries current_mass_Mt=%.5f but its named "
                "configuration(s) %s price %s - the registry "
                "has drifted from the build it describes"
                % (row["category_id"], mass, named,
                   ["%.5f" % shipped[n] for n in named]))
    return {r["category_id"]: r for r in registry}


def activated_reference_mt():
    """Mass the scope registry records as activated into the reference estimate."""
    return sum(float(r["current_mass_Mt"] or 0.0)
               for r in _rows(asset_path(DATA, "scope_registry.csv"))
               if r["current_status"] == "reference")


def build():
    configurations = _rows(asset_path(OUTPUTS, "national_configurations.csv"))
    scope = validate_scope_registry(configurations, residual_mt=None)
    residual_mt = _fuel_ledger_residual()
    rows = []

    def append(kind, code, name, basis, low="", high="", config="", note="", status=""):
        rows.append(dict(row_type=kind, ipcc_code=code, stream=name,
            scope_status=status or ("configuration" if kind == "case" else "diagnostic"),
            notation_key="", coverage_state="scenario_only" if kind == "case" else "context_only",
            configuration_id=config, mass_basis=basis,
            mass_low_Mt=round(float(low), 5) if low != "" else "",
            mass_high_Mt=round(float(high), 5) if high != "" else "",
            composable=False, contained_in="", note=note))

    append("diagnostic", "1.A.2", "Industrial EDGAR-minus-engine comparison",
           "comparison_not_missing_mass",
           note="Signed comparator difference %.5f Mt AR5 CO2e. Activity, factors, fuels, "
                "process scope and periods can explain differences; this is neither a "
                "floor nor an upper bound on unestimated emissions." % residual_mt)
    append("diagnostic", "2.F", "External F-gas benchmark",
           "comparison_not_missing_mass",
           note="The historical EDGAR comparator is %.2f Mt CO2e. An external estimate "
                "does not establish a bound. Consumption-equivalent quantities are not "
                "annual emitted gas; explicit bank configurations retain their own "
                "assumptions and are not a completeness interval." % FGAS_BENCHMARK_MT)

    coal_lo = _screen_val("fugitives_coal_screen_2024.csv", "bound", "low", "co2e_Mt_AR5")
    coal_hi = _screen_val("fugitives_coal_screen_2024.csv", "bound", "high", "co2e_Mt_AR5")
    append("case", "1.B.1", "Coal-mining surface-production cases",
           "partial_surface_scenario_endpoints", coal_lo, coal_hi,
           "coal_mining_fugitives_in_scope",
           "Conditional surface-mine factors/activity only. Underground mining remains "
           "unestimated; these endpoints do not bound the national missing category.")
    nitric_lo, nitric_hi = _screen_row("ippu_chemicals_screening_2024.csv", "configuration",
        "nitric_acid_unabated_in_scope", "bracket_low_Mt", "bracket_high_Mt")
    append("case", "2.B.2", "Nitric-acid unabated source case",
           "source_case_endpoints", nitric_lo, nitric_hi, "nitric_acid_unabated_in_scope",
           "One plant with calendar-2022 production under the stated unabated factors. "
           "The separate abatement case is a structural operating assumption; neither "
           "defines a lower or upper bound on current national nitric-acid emissions.")
    commercial = _config_delta(configurations, "commercial_institutional_in_scope")
    append("case", "1.A.4.a", "Supported commercial-fuel source case",
           "partial_source_case", commercial, commercial, "commercial_institutional_in_scope",
           "The supported streams alone, with their stated source/factor assumptions. "
           "A national reporting comparator from another period is not its upper bound.")
    cement_lo = _screen_val("industry_solid_screenings_2024.csv", "bound", "low", "quantity")
    cement_hi = _screen_val("industry_solid_screenings_2024.csv", "bound", "high", "quantity")
    booked_cement = sum(float(r["co2e_Mt_AR5"]) for r in _rows(
        asset_path(OUTPUTS, "industry_by_stream_2024.csv"))
        if r["subitem"].startswith("Cement-sector coal"))
    append("case", "1.A.2", "Cement-kiln transferred-intensity difference",
           "structural_difference_not_missing_mass", cement_lo-booked_cement,
           cement_hi-booked_cement, "cement_kiln_fuel_in_scope",
           "Modelled fuel demand minus booked coal under the stated clinker and heat "
           "intensities. Not a claimant contained within an external-inventory residual, "
           "nor a bound on other industry. Negative case differences remain meaningful.")
    bagasse = _config_delta(configurations, "bagasse_ceiling_in_scope")
    append("case", "1.A.2", "Sugar-mill process-bagasse activity case",
           "conditional_activity_case", bagasse, bagasse, "bagasse_ceiling_in_scope",
           "All-cane process-heat case, CH4 and N2O only. Its physical/activity assumptions "
           "remain conditional; it is not composed with independent missing-source estimates.")
    navigation = _screen_val("transport_navigation_screen_2024.csv", "fy_label", "FY2023-24",
                             "co2e_Mt_AR5")
    append("case", "1.A.3.d", "Navigation customer-fuel case", "partial_source_case",
           navigation, navigation,
           note="Customer fuel allocation is a source-boundary scenario, not an observed "
                "complete domestic-navigation account or a missing-emissions bound.")
    soda_scope = scope.get("soda_ash_2b7")
    if not soda_scope or soda_scope["current_status"] != "reference":
        low, high = _screen_row("ippu_chemicals_screening_2024.csv", "ipcc_code", "2.B.7",
                               "bracket_low_Mt", "bracket_high_Mt")
        append("case", "2.B.7", "Soda-ash process case", "source_case_endpoints", low, high,
               note="Conditional route assumptions; not a bound on missing industrial processes.")

    # Every actual NE entry remains a notation status, including finer omissions
    # beside an admitted subset. Estimated steel/ammonia rows are not relabelled NE.
    seen = set()
    for entry in _rows(asset_path(OUTPUTS, "completeness.csv")):
        key = (entry["code"], entry["category"])
        if entry["notation_key"] != "NE" or key in seen:
            continue
        seen.add(key)
        outside = entry["code"].startswith(("3.B", "3.D"))
        matches = [r for r in scope.values() if r["ipcc_code"] == entry["code"]
                   and r["current_status"] != "reference"]
        rows.append(dict(row_type="stream", ipcc_code=entry["code"], stream=entry["category"],
            scope_status=matches[0]["current_status"] if matches else "NE", notation_key="NE",
            coverage_state="outside_non_lulucf_scope" if outside else "NE",
            configuration_id="", mass_basis="outside_scope" if outside else "not_quantified",
            mass_low_Mt="", mass_high_Mt="", composable=False, contained_in="",
            note=entry["justification"] + (" Outside the maintained non-LULUCF inventory."
                                          if outside else " No missing-emissions mass bound assigned.")))
    rows.append(dict(row_type="summary", ipcc_code="", stream="Unestimated-source aggregate",
        scope_status="NE", notation_key="NE", coverage_state="not_quantified",
        configuration_id="", mass_basis="no_numerical_completeness_bound_declared",
        mass_low_Mt="", mass_high_Mt="", composable=False, contained_in="",
        note="No defensible composable national missing-emissions range is established. "
             "Blank is unknown, not zero. Source-specific conditional cases, unestimated "
             "categories and comparator disagreements remain distinct. The historical "
             "approximately 47 Mt internal target is retired, not filled with benchmark differences."))
    return rows


def main():
    rows = build()
    write_table(OUT, list(FIELDS), rows, banner=(
        "# Coverage gaps, conditional source cases and external comparisons; none enters reference totals.",
        "# NE is unestimated, not zero. Case endpoints do not compose a missing-emissions interval.",
        "# No national numerical completeness bound is declared.",
    ), lineterminator="\n")
    print("completeness ledger -> %s; %d rows; national missing-emissions range not quantified"
          % (OUT, len(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

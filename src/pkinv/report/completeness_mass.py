"""The completeness-mass ledger: every absent stream joined to what it would weigh.

WHY (Wave 4). Four registers take a position on absence and none of them carries a
mass: the scope registry has statuses, the completeness register has notation keys
with magnitudes buried in prose, the coverage matrix has cell states and no mass
column, and the gap register has requests. The masses live in a FIFTH place - the
configuration file and the per-sector screening CSVs. A reviewer asking the simplest
completeness question there is - "how much is missing, and how sure are you of that
number?" - had to join five artifacts by hand. This ledger is that join, one row per
candidate stream outside the reference total, each carrying the state every register
assigns it and the bound the shipped arithmetic supports.

THE FLOOR, MEASURED. The Pass-2 baseline quotes a directive target - "countable
floor ~47 Mt" - that the tree could not reconstruct: its own components (1A2 ~29,
F-gas 11.54) sum to 40.96, and "non-cement IPPU" and "industrial wastewater" carried
no number anywhere. After Wave 4 the ledger composes a measured band instead:
per-stream floors where a floor exists, per-stream bounds where only a bound does,
each row flagged composable or contained. The directive's 47 is quoted BESIDE the
measured band as the target it was; the baseline file itself is a frozen snapshot
and is not edited.

COMPOSITION DISCIPLINE (the not_composed rule, kept):
- A claimant CONTAINED in another row's bound (cement kiln fuel inside the 1A2
  benchmark residual) is listed with contained_in set and EXCLUDED from every sum -
  adding it to its own container would double-count.
- The floor sum adds only rows with a defensible floor; the bound sum adds each
  composable row's upper bound. F-gases have no credible floor (consumption is not
  emissions, and the filed 0.003 comparator is three orders below both lanes), so
  they enter the bound sum only.
- The two shared members of joint_uncertainty.completeness_national() (1A2, F-gas)
  are asserted equal to its constants, so the two artifacts cannot drift apart.

THE SCOPE-REGISTRY VALIDATOR (the reviewed doorway). This module is the first in
src/ to deliberately read data/scope_registry.csv - the no-op gate in
tests/test_pass2_registries.py names itself the doorway for exactly this wave - and
what it does with the registry is VALIDATE it against the build: every screening row
must name a shipped configuration whose national delta agrees with the registry's
own current_mass_Mt. A registry that drifts from the products it describes fails the
build rather than describing a release that no longer exists.

Usage:  python3 -m pkinv.report.completeness_mass
Writes: outputs/pakemis_completeness_mass.csv
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

# The directive target the measured band is quoted beside (docs/pass2_baseline.md,
# frozen). Never a computed quantity - that is the point of measuring the band.
DIRECTIVE_TARGET_MT = 47.0

# The two members joint_uncertainty.completeness_national() composes; asserted equal
# here so the ledger and the uncertainty surface give one answer.
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
    either a named configuration's delta or the fuel-ledger benchmark residual.
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
        candidates = [shipped[n] for n in named] + [residual_mt]
        if not any(abs(c - mass) < 0.01 for c in candidates):
            raise SystemExit(
                "scope registry: %s carries current_mass_Mt=%.5f but its named "
                "configuration(s) %s price %s (residual %.2f) - the registry "
                "has drifted from the build it describes"
                % (row["category_id"], mass, named,
                   ["%.5f" % shipped[n] for n in named], residual_mt))
    return {r["category_id"]: r for r in registry}


def activated_reference_mt():
    """Mass the scope registry records as activated into the reference estimate."""
    return sum(float(r["current_mass_Mt"] or 0.0)
               for r in _rows(asset_path(DATA, "scope_registry.csv"))
               if r["current_status"] == "reference")


def build():
    configurations = _rows(asset_path(OUTPUTS, "national_configurations.csv"))
    residual_mt = _fuel_ledger_residual()

    coal_lo = _screen_val("fugitives_coal_screen_2024.csv", "bound", "low",
                          "co2e_Mt_AR5")
    coal_hi = _screen_val("fugitives_coal_screen_2024.csv", "bound", "high",
                          "co2e_Mt_AR5")
    # ammonia: ACTIVATED at rc52 (Tier 1 calibrated) - no longer a screened band; its mass is in
    # the scope registry's reference rows (activated_reference_mt)
    nitric_lo, nitric_hi = _screen_row(
        "ippu_chemicals_screening_2024.csv", "configuration",
        "nitric_acid_unabated_in_scope", "bracket_low_Mt", "bracket_high_Mt")
    steel_lo, steel_hi = _screen_row(
        "ippu_chemicals_screening_2024.csv", "ipcc_code", "2.C.1",
        "bracket_low_Mt", "bracket_high_Mt")
    soda_lo, soda_hi = _screen_row(
        "ippu_chemicals_screening_2024.csv", "ipcc_code", "2.B.7",
        "bracket_low_Mt", "bracket_high_Mt")
    captive_lo, captive_hi = _screen_row(
        "industry_captive_screening_2024.csv", "configuration",
        "captive_coal_in_scope", "bracket_low_Mt", "bracket_high_Mt")
    # rc47 Wave 0: the cement claimant is the transferred model's EXCESS over the
    # measured cement coal the reference books (rc46 activation) - the band is read
    # from the screening product (the old hard-coded 11.808/15.412 pair had already
    # drifted from the shipped 11.994/15.655) and netted against the stream ledger.
    cement_lo = _screen_val("industry_solid_screenings_2024.csv", "bound", "low",
                            "quantity")
    cement_hi = _screen_val("industry_solid_screenings_2024.csv", "bound", "high",
                            "quantity")
    measured_cement = sum(
        float(r["co2e_Mt_AR5"]) for r in _rows(
            asset_path(OUTPUTS, "industry_by_stream_2024.csv"))
        if r["subitem"].startswith("Cement-sector coal"))
    cement_excess_lo = cement_lo - measured_cement
    cement_excess_hi = cement_hi - measured_cement
    commercial = _config_delta(configurations, "commercial_institutional_in_scope")
    navigation = _screen_val("transport_navigation_screen_2024.csv", "fy_label",
                             "FY2023-24", "co2e_Mt_AR5")

    streams = [
        # (code, stream, config, basis, low, high, composable, contained_in,
        #  floor_counts, note)
        ("1.A.2", "Unresolved industrial solid-fuel residual", "",
         "benchmark_residual", residual_mt, residual_mt, True, "", True,
         "EDGAR 1A2 minus the engine's estimated streams (post-activation: the "
         "measured brick and cement coal are INSIDE the engine now) - a bound "
         "on the benchmark gap, never evidence about its composition. Its "
         "remaining claimants are listed below as CONTAINED rows; up to %.1f Mt "
         "is claimed (the cement-model excess band and the bagasse ceiling) and "
         "the ~%.1f Mt left over is benchmark disagreement over an exhaustive "
         "consumer series, not a refusal - the rc46 supply-consumption identity "
         "closed the old industrial-coal/petcoke refusal, and the retired brick "
         "and captive screenings (superseded_by_reference_stream in the fuel "
         "ledger) no longer claim mass here"
         % (cement_excess_hi + 0.38964,
            residual_mt - (cement_excess_hi + 0.38964))),
        ("1.A.2", "Cement kiln fuel (model excess over measured)",
         "cement_kiln_fuel_in_scope",
         "screening_band", cement_excess_lo, cement_excess_hi, False,
         FUEL_LEDGER_RESIDUAL, False,
         "own-year census clinker under a transferred heat intensity, NET of "
         "the measured cement coal the reference books"),
        ("1.A.2", "Sugar-mill process bagasse", "bagasse_ceiling_in_scope",
         "ceiling", 0.0, 0.38964, False, FUEL_LEDGER_RESIDUAL, False,
         "all-cane ceiling, CH4+N2O only"),
        ("2.F", "F-gases (ODS substitutes)", "scope_plus_fgas_screening",
         "external_benchmark_bound", "", FGAS_BENCHMARK_MT, True, "", False,
         "EDGAR 2025 benchmark as the bound; the 9.815 consumption lane beside "
         "it is supply, not emissions, and the filed 0.003 comparator is three "
         "orders below both - so NO FLOOR is defensible and the row enters the "
         "bound sum only"),
        ("1.A.4.a", "Commercial and institutional combustion",
         "commercial_institutional_in_scope", "screening_floor",
         commercial, 3.8, True, "", True,
         "the two-stream quantifiable floor; Pakistan's own BUR-1 filed 3.8 Mt "
         "is the bound end - the category is at least the floor and its filed "
         "benchmark says how much more"),
        ("1.B.1", "Coal-mining fugitives (surface share)",
         "coal_mining_fugitives_in_scope", "partial_band",
         coal_lo, coal_hi, True, "", True,
         "PARTIAL by construction: underground mining is unquantified and its "
         "factors run ~30x the surface low, so the band bounds only the Thar "
         "surface share"),
        ("2.B.2", "Nitric acid N2O", "nitric_acid_unabated_in_scope",
         "screening_floor_prior_vintage", nitric_lo, nitric_hi, True, "", True,
         "one of two plants, calendar-2022 production; the abated variant "
         "(nitric_acid_abated_in_scope) prices the operating question the "
         "activation gate demands evidence on"),
        ("2.B.7", "Soda ash production", "", "ceiling", soda_lo, soda_hi,
         True, "", False, "route-agnostic ceiling; below materiality, no "
                          "configuration - bounded small, the bagasse pattern"),
        ("2.C.1", "Iron and steel (electric route)", "", "route_matched_point",
         steel_lo, steel_hi, True, "", True,
         "zero reported pig iron makes the electric route the only one the "
         "observed record supports; below materiality, no configuration"),
        ("1.A.3.d", "Navigation - domestic", "", "screening_point",
         navigation, navigation, True, "", True,
         "TYPED REFUSAL of a configuration: 0.01 Mt is two orders below every "
         "materiality line and the activity swings 32-8,342 t with no trend - "
         "the screen stays published "
         "(transport_navigation_screen_2024.csv) and a port-side series is "
         "the closer"),
    ]

    rows = []
    for (code, stream, config, basis, low, high, composable, contained,
         floor_counts, note) in streams:
        rows.append({
            "row_type": "stream", "ipcc_code": code, "stream": stream,
            "scope_status": "", "notation_key": "NE",
            "coverage_state": "screened" if config else "NE",
            "configuration_id": config, "mass_basis": basis,
            "mass_low_Mt": low if low == "" else round(float(low), 5),
            "mass_high_Mt": high if high == "" else round(float(high), 5),
            "composable": composable, "contained_in": contained,
            "note": note})

    # Every remaining NE register row gets a no_bound row, so the ledger's universe
    # is the completeness register's and absence of a bound is a value, not a gap
    # in the gap ledger.
    covered = {(r["ipcc_code"], r["stream"]) for r in rows}
    covered_codes = {r["ipcc_code"] for r in rows}
    for entry in _rows(asset_path(OUTPUTS, "completeness.csv")):
        if entry["notation_key"] != "NE":
            continue
        if entry["code"] in covered_codes:
            continue
        rows.append({
            "row_type": "stream", "ipcc_code": entry["code"],
            "stream": entry["category"], "scope_status": "",
            "notation_key": "NE", "coverage_state": "NE",
            "configuration_id": "", "mass_basis": "no_bound",
            "mass_low_Mt": "", "mass_high_Mt": "", "composable": False,
            "contained_in": "",
            "note": entry["justification"][:240]})

    scope = validate_scope_registry(configurations, residual_mt)
    for cid, srow in sorted(scope.items()):
        for r in rows:
            if r["ipcc_code"] == srow["ipcc_code"] and r["row_type"] == "stream":
                r["scope_status"] = srow["current_status"]

    floor_sum = sum(float(r["mass_low_Mt"]) for r in rows
                    if r["row_type"] == "stream" and r["composable"]
                    and r["mass_low_Mt"] != ""
                    and _floor_counts(streams, r))
    bound_sum = sum(float(r["mass_high_Mt"]) for r in rows
                    if r["row_type"] == "stream" and r["composable"]
                    and r["mass_high_Mt"] != "")

    from pkinv.report import joint_uncertainty
    jc = joint_uncertainty.completeness_national()
    composed = float(jc["composable_bound_Mt"])
    expected = residual_mt + FGAS_BENCHMARK_MT
    if abs(composed - expected) > 0.01:
        raise SystemExit(
            "the ledger and joint_uncertainty.completeness_national() disagree on "
            "the shared members: %.2f vs %.2f - one answer, not two" %
            (composed, expected))

    rows.append({
        "row_type": "summary", "ipcc_code": "", "stream":
        "countable outside-reference mass (composable rows only)",
        "scope_status": "", "notation_key": "", "coverage_state": "",
        "configuration_id": "", "mass_basis": "measured_band",
        "mass_low_Mt": round(floor_sum, 2), "mass_high_Mt": round(bound_sum, 2),
        "composable": True, "contained_in": "",
        "note": "floor sum adds only rows with a defensible floor; bound sum adds "
                "each composable row's upper bound. Contained claimants are "
                "excluded from both. The Pass-2 directive's countable-floor "
                "target (~%.0f Mt, docs/pass2_baseline.md - a target, not a "
                "computed quantity) no longer sits inside the REMAINING band: "
                "rc46 Wave 2 activated %.2f Mt of it (brick and cement coal) "
                "into the reference estimate, and the remaining band plus the "
                "activated mass still brackets the target - the directive is "
                "being paid down, not lost. "
                "joint_uncertainty.completeness_national()'s %.2f Mt is "
                "the two shared members (1A2 residual + F-gas benchmark), "
                "asserted equal here"
                % (DIRECTIVE_TARGET_MT, activated_reference_mt(), composed)})
    return rows


def _floor_counts(streams, row):
    for (code, stream, _c, _b, _lo, _hi, _comp, _cont, floor_counts, _n) in streams:
        if code == row["ipcc_code"] and stream == row["stream"]:
            return floor_counts
    return False


def main():
    rows = build()
    write_table(OUT, list(FIELDS), rows, banner=('# The completeness-mass ledger: every absent stream joined to the', '# bound the shipped arithmetic supports; contained claimants are', '# excluded from the sums. See completeness_mass.py.',), lineterminator="\n")
    summary = rows[-1]
    print("completeness-mass ledger -> %s" % OUT)
    print("  %d stream rows; measured band %.2f-%.2f Mt (directive target ~%.0f)"
          % (sum(1 for r in rows if r["row_type"] == "stream"),
             summary["mass_low_Mt"], summary["mass_high_Mt"],
             DIRECTIVE_TARGET_MT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate the 2006-to-2019 fugitives method ladder and empirical products."""
from __future__ import annotations

from pkinv.assets import asset_path

import json
import os
from collections import defaultdict

from pkinv.core import documents
from pkinv.core.components import co2e_Mt, enrich_co2e
from pkinv.core.downscale import allocate_rows, check_reconciliation
from pkinv.core.geography import PROVINCES
from pkinv.core.runner import Runner
from pkinv.paths import DATA, OUTPUTS, ROOT
from pkinv.sectors.fugitives import (
    audits, downscale, engine, gas_balance, leakage, observations,
    official_reporting, segment_inventory, uncertainty,
)
from pkinv.sectors.fugitives.data import FugitivesData, LEGACY_YEAR, YEAR
from pkinv.activity.store import read_rows


# Every file this run actually writes, in write order. The manifest used to report a
# DIRECTORY LISTING filtered by prefix instead, which meant any leftover in outputs/ was
# claimed as this run's product: a superseded FY2019-20 vintage, renamed out of the build
# when the sectors were harmonised onto one period, was still being listed as a generated
# output of the 2024 run. A manifest that reports what is lying around cannot detect the one
# thing a manifest is for.
def _read_dicts(path):
    return read_rows(path, comments=False)


def _hash(path):
    # rc41: live when the document is held, carried from data/raw_manifest.csv when it
    # is not (pkinv.core.documents) - the run manifest names the same digest either way.
    return documents.digest(path)


def _total(components):
    return sum(row["co2e_Mt_AR5"] for row in components)


SEGMENT_GROUPS = {
    "Oil production": "upstream/processing",
    "Oil pipeline transport": "upstream/processing",
    "Oil refining": "upstream/processing",
    "Gas production": "upstream/processing",
    "Gas gathering": "upstream/processing",
    "Gas processing": "upstream/processing",
    "Sour-gas processing": "upstream/processing",
    "Gas transmission": "network/import",
    "Gas distribution": "network/import",
    "LNG import terminals": "network/import",
    "Post-meter appliances": "post-meter",
    "Post-meter industrial and power": "post-meter",
}


def _segment_name(subitem):
    matches = [name for name in SEGMENT_GROUPS if subitem.startswith(name)]
    if len(matches) != 1:
        raise ValueError("annual component does not map uniquely: %s" % subitem)
    return matches[0]


def _production_only_2019(data, year, practice="higher"):
    oil_activity = data.oil_e3m3(year)
    gas_activity = data.gas_e6m3(year)
    rows = []
    for label, activity, stem in (
            ("Oil production", oil_activity, "oil_prod_%s" % ("low" if practice == "lower" else "high")),
            ("Gas production", gas_activity, "gas_prod_%s" % ("low" if practice == "lower" else "high"))):
        for gas in ("CH4", "CO2", "N2O"):
            factor = data.factor2019("%s_%s" % (stem, gas.lower()))
            rows.append({"category": leakage.CATEGORY, "subitem": "%s %s" % (label, gas),
                         "gas": gas, "emissions_Gg": activity * factor["value"] / 1000.0,
                         "uncert_pct": max(factor["uncertainty_low_pct"],
                                           factor["uncertainty_high_pct"]),
                         **({"fossil": True} if gas == "CH4" else {})})
    return enrich_co2e(rows)


def _method_ladder(data, reference):
    legacy_2020 = engine.build_components(data, year=LEGACY_YEAR, method="legacy2006")
    legacy_anchor = engine.build_components(data, year=YEAR, method="legacy2006")
    prod_2019 = _production_only_2019(data, YEAR)
    upstream_names = ("Oil production", "Gas production", "Gas gathering", "Gas processing",
                      "Sour-gas processing")
    upstream = [row for row in reference
                if any(row["subitem"].startswith(name + " ") for name in upstream_names)]
    return [
        {"order": 0, "method": "Legacy 2006 published benchmark", "fiscal_year": 2020,
         "coverage": "production only", "mt_co2e_ar5": _total(legacy_2020),
         "interpretation": "geometric midpoint of 2006 developing-country ranges"},
        {"order": 1, "method": "Legacy 2006 on common anchor activity", "fiscal_year": 2024,
         "coverage": "production only", "mt_co2e_ar5": _total(legacy_anchor),
         "interpretation": "isolates activity-year change from method change"},
        {"order": 2, "method": "2019 Refinement on common production support", "fiscal_year": 2024,
         "coverage": "oil and gas production only", "mt_co2e_ar5": _total(prod_2019),
         "interpretation": "isolates factor-framework change"},
        {"order": 3, "method": "2019 upstream completion", "fiscal_year": 2024,
         "coverage": "production, gathering and processing", "mt_co2e_ar5": _total(upstream),
         "interpretation": "adds separately defined upstream segments"},
        {"order": 4, "method": "2019 reference configuration", "fiscal_year": 2024,
         "coverage": "all publicly supported 1.B.2 segments", "mt_co2e_ar5": _total(reference),
         "interpretation": "registered result conditional on high/default practices where unknown"},
    ]


def _structural_scenarios(data):
    """Legacy one-at-a-time diagnostics retained separately from the joint envelope."""
    output = []
    for scenario in ("reference", "central", "lower_practices", "throughput",
                     "lower_throughput", "lower_distribution_only",
                     "lower_transmission_only", "post_meter_half_factor",
                     "post_meter_including_feedstock",
                     "post_meter_excluding_fertilizer", "no_post_meter_industrial",
                     "no_processing_proxy", "core_network_only"):
        comps = engine.build_components(data, scenario=scenario)
        output.append({"scenario": scenario, "mt_co2e_ar5": _total(comps),
                       "experiment_type": "one-at-a-time diagnostic",
                       "activity_basis": "throughput" if "throughput" in scenario else "pipeline length",
                       "practice": ("geometric mean of published bounds" if scenario == "central"
                                    else "lower" if scenario.startswith("lower")
                                    else "higher/default"),
                       "coverage": ("processing proxy excluded" if scenario == "no_processing_proxy"
                                    else "post-meter industrial excluded" if scenario == "no_post_meter_industrial"
                                    else "post-meter industrial factor halved" if scenario == "post_meter_half_factor"
                                    else "post-meter base with fertiliser feedstock inside "
                                         "(the membership through rc66)"
                                    if scenario == "post_meter_including_feedstock"
                                    else "post-meter base minus the whole fertiliser class, "
                                         "process fuel with the feed"
                                    if scenario == "post_meter_excluding_fertilizer"
                                    else "network core only" if scenario == "core_network_only"
                                    else "reference coverage")})
    # The 1.B.1 scope row (Wave 4): reference coverage PLUS the coal-mining surface
    # screen at its high bound. Not an engine scenario - the category is outside the
    # engine and stays NE - so the row is composed from the screen's own arithmetic
    # (coal_screen.rows) and the reference total. The screen is PARTIAL by
    # construction (underground unquantified, factors ~30x the surface low) and the
    # coverage string says so, so this row is never read as the category's bound.
    from pkinv.sectors.fugitives import coal_screen
    surface_hi = max(float(r["co2e_Mt_AR5"]) for r in coal_screen.rows()
                     if r["co2e_Mt_AR5"] != "")
    reference_mt = next(r["mt_co2e_ar5"] for r in output
                        if r["scenario"] == "reference")
    output.append({"scenario": "coal_screen_upper",
                   "mt_co2e_ar5": reference_mt + surface_hi,
                   "experiment_type": "scope screen (1.B.1, PARTIAL)",
                   "activity_basis": "pipeline length",
                   "practice": "higher/default",
                   "coverage": "reference coverage plus the Thar surface-mining "
                               "screen's high bound (underground unquantified - "
                               "a PARTIAL band, not the category bound)"})
    return output


def _factorial_scenarios(data):
    output = []
    for config in segment_inventory.factorial_configurations():
        components = engine.build_components(data, config=config)
        output.append({
            **config.as_dict(),
            "mt_co2e_ar5": _total(components),
            "coverage_complete_under_configuration": (
                config.processing_basis != "excluded" and
                config.post_meter_state != "excluded"),
            "probability_weight": "",
            "interpretation": ("joint deterministic structural/coverage configuration; "
                               "no probability assigned"),
        })
    return output


def _completeness():
    return _read_dicts(asset_path(DATA, "activity", "fugitives", "completeness.csv"))


def _benchmarks(crt_total):
    rows = _read_dicts(asset_path(DATA, "activity", "fugitives", "benchmark_controls.csv"))
    for row in rows:
        row["value_mt_co2e"] = float(row["value_mt_co2e"])
    crt = next(row for row in rows if row["benchmark_id"] == "pakistan_crt_1b2_2022")
    if abs(crt["value_mt_co2e"] - crt_total["total_co2e_kt"] / 1000.0) > 1e-9:
        raise ValueError("normalized CRT benchmark does not match workbook extraction")
    return rows


def _qa(run, data, reference, ledger, scenarios, factorial, flare_rows, mars, crt_total,
        flow_rows, ufg_compat, observation_stats, field_rows, field_stats,
        match_audit, permutation_rows, crt_reproduction, crt_waterfall, matched_years,
        segment_history, post_meter_rows):
    add = run.gate
    add("registered anchor year", data.year == 2024, data.year, 2024,
        "no FY2020 production is mixed into the registered estimate")
    add("transmission length closure",
        abs(data.activity("gas_transmission_pipeline")["value"] - (9320.69 + 4206.0)) < 1e-6,
        data.activity("gas_transmission_pipeline")["value"], 13526.69, "OGRA utility systems")
    add("distribution length closure",
        data.activity("gas_distribution_pipeline")["value"] == 151419 + 49811,
        data.activity("gas_distribution_pipeline")["value"], 201230, "OGRA utility systems")
    add("component-to-ledger closure",
        abs(sum(row["emissions_Gg"] for row in reference) -
            sum(row["emissions_Gg"] for row in ledger)) < 1e-9,
        sum(row["emissions_Gg"] for row in reference),
        sum(row["emissions_Gg"] for row in ledger), "gas-mass closure before GWP")
    by_name = {row["scenario"]: row["mt_co2e_ar5"] for row in scenarios}
    add("structural ordering",
        by_name["reference"] > by_name["central"] > by_name["lower_practices"],
        by_name["reference"], "> central > lower-practices",
        "technology scenarios stay structural; the geometric-mean central reading "
        "sits strictly inside the practice bounds")
    add("factorial structural configurations", len(factorial) == 280, len(factorial), 280,
        "all permissible joint configurations are retained without probability weights; "
        "280 since rc67 gave the post-meter base three memberships (feedstock out, the "
        "reference; feedstock in; the whole fertiliser class out) beside the two factor "
        "states - 224 before, 168 before that")
    add("joint envelope below OAT envelope",
        min(row["mt_co2e_ar5"] for row in factorial) <
        min(row["mt_co2e_ar5"] for row in scenarios),
        min(row["mt_co2e_ar5"] for row in factorial),
        "< one-at-a-time minimum", "coexisting structural choices are evaluated jointly")
    add("flare archive Pakistan coverage", len(flare_rows) == 14, len(flare_rows), 14,
        "2012-2025 inclusive")
    add("MARS oil-and-gas coverage", mars["oil_gas_sources"] > 0, mars["oil_gas_sources"], ">0",
        "detections are evaluation only")
    add("CRT workbook total", abs(crt_total["total_co2e_kt"] - 4432.821048632558) < 1e-9,
        crt_total["total_co2e_kt"], 4432.821048632558, "official 2022 cell audit")
    add("UFG mass conversion", leakage.ufg_bound_Gg_CH4(data) > 1000,
        leakage.ufg_bound_Gg_CH4(data), ">1000 Gg CH4 at 100%", "guards the former factor-1000 bug")
    add("gas supply identity closure", all(abs(row["supply_identity_residual_mmcfd"]) < 1e-6
                                            for row in flow_rows),
        max(abs(row["supply_identity_residual_mmcfd"]) for row in flow_rows), 0,
        "indigenous marketable supply plus RLNG equals reported supply")
    add("UFG compatibility computed", any(row["scenario"] == "reference" for row in ufg_compat),
        len(ufg_compat), ">=1", "network estimate is compared only with pre-meter UFG")
    add("quantitative observation evaluation", len(observation_stats) == 3,
        len(observation_stats), 3, "VIIRS volume and MARS sources/plumes are tested by province")
    add("field supply reconciliation",
        abs(sum(float(row["official_marketable_supply_mmcfd"]) for row in field_rows) -
            2637.75) < 1e-6,
        sum(float(row["official_marketable_supply_mmcfd"]) for row in field_rows), 2637.75,
        "canonical fields aggregate Table 3.34 source rows; 0.03 MMCFD is rounding")
    add("field observation statistics", len(field_stats) == 3, len(field_stats), 3,
        "field-level tests replace province correlations as the principal spatial evaluation")
    add("observation match audit", len(match_audit) == mars["oil_gas_sources"] and
        all(row["match_confidence"] in ("high", "review_required", "unmatched")
            for row in match_audit),
        len(match_audit), mars["oil_gas_sources"],
        "every MARS source has an auditable nearest-flare and canonical-field decision; "
        "unmatched records remain explicit")
    add("field permutation tests", len(permutation_rows) == 6, len(permutation_rows), 6,
        "three observation metrics are tested under national and within-province nulls")
    add("CRT activity-factor reproduction", all(row["closes"] for row in crt_reproduction),
        max(abs(row["difference_kt"]) for row in crt_reproduction), 0,
        "official activity multiplied by IEF reproduces reported native-gas rows")
    add("CRT waterfall closure", abs(crt_waterfall[-1]["delta_common_mt_co2e"]) < 1e-9,
        crt_waterfall[-1]["delta_common_mt_co2e"], 0,
        "segment replacements and additions close to the reconstructed native-gas ledger")
    add("nine-year infrastructure reconstruction", len(matched_years) == 9,
        len(matched_years), 9, "FY2015-16 through FY2023-24 with no interpolation")
    annual_segment_totals = defaultdict(float)
    for row in segment_history:
        annual_segment_totals[row["fiscal_year"]] += row["co2e_Mt_AR5"]
    add("annual segment history closure", all(
        abs(annual_segment_totals[row["fiscal_year"]] - row["co2e_Mt_AR5"]) < 1e-9
        for row in matched_years), len(segment_history), 9 * len(SEGMENT_GROUPS),
        "segment-resolved annual rows close exactly to every reference annual total")
    add("post-meter end-use control",
        abs(float(post_meter_rows[0]["rounding_residual_million_m3"])) < 0.1,
        post_meter_rows[0]["rounding_residual_million_m3"], "<0.1 million m3",
        "published sector rows reconcile to the registered transferred-factor activity")
    return run.checks


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = FugitivesData()
    run = Runner("fugitives", declared=(
        "fugitives_by_stream_2024.csv",
        "fugitives_segment_ledger_2024.csv",
        "fugitives_segment_native_gases_2024.csv",
        "fugitives_method_ladder_2024.csv",
        "fugitives_structural_scenarios_2024.csv",
        "fugitives_structural_factorial_2024.csv",
        "fugitives_uncertainty_2024.csv",
        "fugitives_uncertainty_inputs_2024.csv",
        "fugitives_uncertainty_attribution_2024.csv",
        "fugitives_conditional_intervals_2024.csv",
        "fugitives_distribution_shape_sensitivity_2024.csv",
        "fugitives_totals_2024.csv",
        "fugitives_infrastructure_timeseries_2016_2024.csv",
        "fugitives_infrastructure_segment_timeseries_2016_2024.csv",
        "fugitives_timeseries_2011_2025.csv",
        "fugitives_provincial_2024.csv",
        "fugitives_gas_flow_balance_2022_2024.csv",
        "fugitives_ufg_network_compatibility_2024.csv",
        "fugitives_ufg_diagnostic_2024.csv",
        "fugitives_viirs_flaring_2012_2025.csv",
        "fugitives_viirs_flare_sites.csv",
        "fugitives_viirs_flare_memo_2024.csv",
        "fugitives_upstream_gas_disposition_2022_2024.csv",
        "fugitives_mars_summary.csv",
        "fugitives_mars_sources.csv",
        "fugitives_mars_plumes.csv",
        "fugitives_observation_provincial_evaluation_2024.csv",
        "fugitives_observation_statistics_2024.csv",
        "fugitives_mars_flare_matches_2024.csv",
        "fugitives_observation_field_evaluation_2024.csv",
        "fugitives_observation_field_statistics_2024.csv",
        "fugitives_observation_match_audit_2024.csv",
        "fugitives_observation_permutation_2024.csv",
        "fugitives_assumption_audit_2024.csv",
        "fugitives_data_priorities_2024.csv",
        "fugitives_distribution_practice_evidence_2024.csv",
        "fugitives_post_meter_factor_lineage_2024.csv",
        "fugitives_post_meter_end_use_2024.csv",
        "fugitives_unfccc_crt_total.csv",
        "fugitives_unfccc_crt_rows.csv",
        "fugitives_unfccc_crt_cell_audit.csv",
        "fugitives_unfccc_crt_reproduction.csv",
        "fugitives_unfccc_crt_common_metric.csv",
        "fugitives_unfccc_crt_waterfall_2022.csv",
        "fugitives_unfccc_crt_fiscal_bracket_2022.csv",
        "fugitives_official_matched_2022.csv",
        "fugitives_benchmark_crosswalk.csv",
        "fugitives_completeness_2024.csv"))
    reference = engine.build_components(data)
    ledger = segment_inventory.inventory_rows(data)
    scenarios = _structural_scenarios(data)
    factorial = _factorial_scenarios(data)

    run.write_dicts("fugitives_by_stream_2024.csv", reference)
    run.write_dicts("fugitives_segment_ledger_2024.csv", ledger)
    native = audits.native_gas_table(data)
    run.write_dicts("fugitives_segment_native_gases_2024.csv", native)
    ladder = _method_ladder(data, reference)
    run.write_dicts("fugitives_method_ladder_2024.csv", ladder)
    run.write_dicts("fugitives_structural_scenarios_2024.csv", scenarios)
    run.write_dicts("fugitives_structural_factorial_2024.csv", factorial)

    legacy_stats, _ = uncertainty.legacy_loguniform(data, year=LEGACY_YEAR)
    mc_stats, _samples, sensitivity = uncertainty.refinement_analysis(data)
    uncertainty_rows = [{"segment": key, **value} for key, value in mc_stats.items()]
    uncertainty_rows.append({"segment": "LEGACY TOTAL", **legacy_stats})
    run.write_dicts("fugitives_uncertainty_2024.csv", uncertainty_rows)
    run.write_dicts("fugitives_uncertainty_inputs_2024.csv",
                 uncertainty.uncertainty_input_rows(data))
    run.write_dicts("fugitives_uncertainty_attribution_2024.csv", sensitivity)
    conditional_configs = segment_inventory.selected_conditional_configurations(factorial)
    conditional_intervals = uncertainty.conditional_interval_rows(
        data, conditional_configs)
    run.write_dicts("fugitives_conditional_intervals_2024.csv", conditional_intervals)
    shape_sensitivity = uncertainty.distribution_shape_rows(data)
    run.write_dicts("fugitives_distribution_shape_sensitivity_2024.csv", shape_sensitivity)

    total = _total(reference)
    reference_mc = mc_stats["TOTAL"]
    totals = [
        {"category": leakage.CATEGORY, "method": "IPCC 2019 infrastructure-constrained",
         "fiscal_year": 2024, "co2e_Mt_AR5": total,
         "mc_p025": reference_mc["p025"], "mc_p50": reference_mc["p50"],
         "mc_p975": reference_mc["p975"],
         "note": "Reference configuration; higher/default factors where Pakistan-specific evidence is absent."},
        {"category": "Legacy 2006 production-only benchmark", "method": "bounded log-uniform",
         "fiscal_year": 2020, "co2e_Mt_AR5": _total(engine.build_components(
             data, year=2020, method="legacy2006")), "mc_p025": legacy_stats["p025"],
         "mc_p50": legacy_stats["p50"], "mc_p975": legacy_stats["p975"],
         "note": "No uncertainty cap; published factor ranges sampled directly."},
    ]
    run.write_dicts("fugitives_totals_2024.csv", totals)

    # Segment-resolved annual reconstruction where matching OGRA controls exist.
    matched_years = []
    segment_history = []
    for year in range(2016, 2025):
        components = engine.build_components(data, year=year)
        gases = defaultdict(float)
        segment_values = defaultdict(lambda: defaultdict(float))
        for row in components:
            gases[row["gas"]] += row["emissions_Gg"]
            segment = _segment_name(row["subitem"])
            segment_values[segment][row["gas"]] += row["emissions_Gg"]
            segment_values[segment]["co2e_Mt_AR5"] += row["co2e_Mt_AR5"]
        for segment in SEGMENT_GROUPS:
            values = segment_values[segment]
            segment_history.append({
                "fiscal_year": year,
                "segment": segment,
                "reporting_group": SEGMENT_GROUPS[segment],
                "ch4_Gg": values["CH4"],
                "co2_Gg": values["CO2"],
                "n2o_Gg": values["N2O"],
                "co2e_Mt_AR5": values["co2e_Mt_AR5"],
                "configuration": "reference",
                "coverage": "matched public-data segment ledger; no interpolation",
            })
        matched_years.append({
            "fiscal_year": year,
            "configuration": "reference",
            "co2e_Mt_AR5": _total(components),
            "ch4_Gg": gases["CH4"], "co2_Gg": gases["CO2"], "n2o_Gg": gases["N2O"],
            "coverage": "full public-data segment ledger with matched annual infrastructure",
        })
    run.write_dicts("fugitives_infrastructure_timeseries_2016_2024.csv", matched_years)
    run.write_dicts("fugitives_infrastructure_segment_timeseries_2016_2024.csv",
                 segment_history)

    # Historical product: legacy series plus a common-support 2019 production-only diagnostic.
    timeseries = []
    for year in data.years():
        legacy = engine.build_components(data, year=year, method="legacy2006")
        refined = _production_only_2019(data, year)
        timeseries.append({"fiscal_year": year,
                           "crude_oil_000_bbl": data.production[year]["oil_000_bbl"],
                           "natural_gas_MMCFT": data.production[year]["gas_MMCFT"],
                           "legacy_2006_production_mt_co2e_ar5": _total(legacy),
                           "ipcc2019_production_common_support_mt_co2e_ar5": _total(refined),
                           "coverage_tier": "production-only"})
    run.write_dicts("fugitives_timeseries_2011_2025.csv", timeseries)

    # Process-matched provincial result; cruise-like fabrication onto districts is avoided.
    allocated = allocate_rows(reference, downscale.load_shares(), downscale.proxy_for, PROVINCES)
    check_reconciliation(allocated, reference)
    provincial = defaultdict(float)
    upstream_provincial = defaultdict(float)
    upstream_names = ("Oil production", "Gas production", "Gas gathering",
                      "Gas processing", "Sour-gas processing")
    for row in allocated:
        provincial[row["province"]] += row["co2e_Mt_AR5"]
        if row["subitem"].startswith(upstream_names):
            upstream_provincial[row["province"]] += row["co2e_Mt_AR5"]
    run.write_dicts("fugitives_provincial_2024.csv",
                 [{"province": p, "co2e_Mt_AR5": provincial[p]} for p in PROVINCES])

    # Physical gas-flow closure and UFG plausibility remain controls, never emissions.
    flow_rows = gas_balance.balance_rows(data)
    run.write_dicts("fugitives_gas_flow_balance_2022_2024.csv", flow_rows)
    ufg_compat = gas_balance.ufg_compatibility(data)
    run.write_dicts("fugitives_ufg_network_compatibility_2024.csv", ufg_compat)
    ufg_total = leakage.ufg_bound_Gg_CH4(data)
    run.write_dicts("fugitives_ufg_diagnostic_2024.csv", [
        {"physical_fraction_pct": pct, "ch4_Gg": ufg_total * pct / 100.0,
         "co2e_Mt_AR5": ufg_total * pct / 100.0 * 30.0 / 1000.0,
         "inventory_role": "diagnostic upper-bound scenario; excluded from estimate"}
        for pct in (10, 25, 50, 75, 100)])

    flare_rows = observations.flare_timeseries()
    run.write_dicts("fugitives_viirs_flaring_2012_2025.csv", flare_rows)
    flare_sites = observations.geolocated_flare_sites()
    run.write_dicts("fugitives_viirs_flare_sites.csv", flare_sites)
    run.write_dicts("fugitives_viirs_flare_memo_2024.csv",
                 [observations.flare_emission_memo(data)])
    upstream_disposition = gas_balance.upstream_disposition_rows(
        data, next(row["flare_volume_bcm"] for row in flare_rows if row["year"] == 2024))
    run.write_dicts("fugitives_upstream_gas_disposition_2022_2024.csv", upstream_disposition)
    mars = observations.mars_summary()
    run.write_dicts("fugitives_mars_summary.csv", [mars])
    run.write_dicts("fugitives_mars_sources.csv", observations.geolocated_mars_sources())
    run.write_dicts("fugitives_mars_plumes.csv", observations.pakistan_mars_plumes())
    observation_rows = observations.provincial_evaluation(upstream_provincial)
    observation_stats = observations.provincial_statistics(observation_rows)
    matches = observations.mars_flare_matches()
    run.write_dicts("fugitives_observation_provincial_evaluation_2024.csv", observation_rows)
    run.write_dicts("fugitives_observation_statistics_2024.csv", observation_stats)
    run.write_dicts("fugitives_mars_flare_matches_2024.csv", matches)
    field_rows = observations.field_observation_evaluation()
    field_stats = observations.field_observation_statistics(field_rows)
    match_audit = observations.observation_match_audit()
    permutation_rows = observations.field_observation_permutation(field_rows)
    run.write_dicts("fugitives_observation_field_evaluation_2024.csv", field_rows)
    run.write_dicts("fugitives_observation_field_statistics_2024.csv", field_stats)
    run.write_dicts("fugitives_observation_match_audit_2024.csv", match_audit)
    run.write_dicts("fugitives_observation_permutation_2024.csv", permutation_rows)

    assumption_rows = audits.assumption_audit(data)
    run.write_dicts("fugitives_assumption_audit_2024.csv", assumption_rows)
    run.write_dicts("fugitives_data_priorities_2024.csv",
                 audits.structural_data_priorities(total, scenarios, sensitivity))
    distribution_evidence = audits.distribution_practice_evidence()
    post_meter_rows = audits.post_meter_end_use_audit(data)
    run.write_dicts("fugitives_distribution_practice_evidence_2024.csv",
                 distribution_evidence)
    run.write_dicts("fugitives_post_meter_factor_lineage_2024.csv",
                 audits.post_meter_factor_lineage(data))
    run.write_dicts("fugitives_post_meter_end_use_2024.csv", post_meter_rows)

    crt_total, crt_rows = official_reporting.extract_crt()
    run.write_dicts("fugitives_unfccc_crt_total.csv", [crt_total])
    run.write_dicts("fugitives_unfccc_crt_rows.csv", crt_rows)
    run.write_dicts("fugitives_unfccc_crt_cell_audit.csv", official_reporting.audit_cells())
    crt_reproduction = official_reporting.reproduce_reported_rows()
    run.write_dicts("fugitives_unfccc_crt_reproduction.csv", crt_reproduction)
    crt_common = official_reporting.official_common_metric()
    crt_waterfall = official_reporting.reconstruction_waterfall(data)
    crt_bracket = official_reporting.fiscal_year_bracket(data)
    run.write_dicts("fugitives_unfccc_crt_common_metric.csv", [crt_common])
    run.write_dicts("fugitives_unfccc_crt_waterfall_2022.csv", crt_waterfall)
    run.write_dicts("fugitives_unfccc_crt_fiscal_bracket_2022.csv", crt_bracket)
    matched_2022 = next(row for row in matched_years if row["fiscal_year"] == 2022)
    run.write_dicts("fugitives_official_matched_2022.csv", [{
        "comparison_year": 2022,
        "reconstructed_reference_mt_co2e_ar5": matched_2022["co2e_Mt_AR5"],
        "reconstructed_ch4_Gg": matched_2022["ch4_Gg"],
        "official_crt_submitted_mt_co2e": crt_total["total_co2e_kt"] / 1000.0,
        "official_crt_common_mt_co2e": crt_common["common_ar5_fossil_ch4_mt_co2e"],
        "official_crt_ch4_Gg": crt_total["ch4_kt"],
        "co2e_ratio_reconstructed_to_crt_submitted": (
            matched_2022["co2e_Mt_AR5"] / (crt_total["total_co2e_kt"] / 1000.0)),
        "co2e_ratio_reconstructed_to_crt_common": (
            matched_2022["co2e_Mt_AR5"] /
            crt_common["common_ar5_fossil_ch4_mt_co2e"]),
        "ch4_ratio_reconstructed_to_crt": matched_2022["ch4_Gg"] / crt_total["ch4_kt"],
        "scope_note": "matched fiscal/reporting year; period conventions may still differ",
    }])
    run.write_dicts("fugitives_benchmark_crosswalk.csv", _benchmarks(crt_total))
    completeness = audits.completeness_materiality(_completeness(), total)
    run.write_dicts("fugitives_completeness_2024.csv", completeness)
    from pkinv.sectors.fugitives import coal_screen
    coal_screen.write()

    qa = _qa(run, data, reference, ledger, scenarios, factorial, flare_rows, mars, crt_total,
             flow_rows, ufg_compat, observation_stats, field_rows, field_stats,
             match_audit, permutation_rows, crt_reproduction, crt_waterfall, matched_years,
             segment_history, post_meter_rows)
    # write-then-raise: the table is on disk before a failing gate aborts, so a
    # red build ships a red table instead of the previous run's green one.
    run.finalize(qa_table="fugitives_qa_2024.csv")

    # The monthly layer builds BEFORE the manifest (rc35), so generated_outputs
    # lists it - it used to run after, and the manifest never named it.
    from pkinv.sectors.fugitives import monthly
    monthly.main()
    run.record(monthly.OUT)

    source_paths = [
        asset_path(ROOT, "sources", "IPCC", "19R_V2_4_Ch04_Fugitive_Emissions.pdf"),
        asset_path(ROOT, "sources", "OGRA", "ogra_state_of_industry_2023-24.pdf"),
        asset_path(ROOT, "sources", "OGRA", "ogra_state_of_industry_2021-22.pdf"),
        asset_path(ROOT, "sources", "OGRA", "ogra_state_of_industry_2022-23.pdf"),
        *[asset_path(ROOT, "sources", "OGRA",
                       "ogra_state_of_industry_%s.pdf" % fiscal)
          for fiscal in ("2015-16", "2016-17", "2017-18", "2018-19", "2019-20", "2020-21")],
        asset_path(ROOT, "data", "gis", "PAK_ADM1.geojson"),
        asset_path(ROOT, "data", "gis", "BOUNDARY_SOURCES.json"),
        observations.FLARE_SOURCE, observations.MARS_SOURCE,
        official_reporting.CRT_SOURCE,
    ]
    manifest = {
        "inventory": "Pakistan oil and gas fugitives",
        "anchor_fiscal_year": 2024,
        "method": "IPCC 2019 Refinement used with the 2006 Guidelines",
        "reference_configuration": "higher/default technologies and pipeline-length T&D",
        "infrastructure_history": "FY2015-16 through FY2023-24; no interpolation",
        "generated_outputs": sorted(set(run.written)),
        # documents.relative(), not os.path.relpath(): a run manifest records the stable
        # logical source identity, which is what every other sector's manifest carries and
        # what the source register joins on. A raw relpath of the RESOLVED path published
        # the sector layout's physical location here and the legacy identity everywhere
        # else, for the same two boundary files.
        "sources": [{"path": documents.relative(path), "sha256": _hash(path)}
                    for path in source_paths],
        "monte_carlo": {"iterations": uncertainty.N_ITER, "seed": uncertainty.SEED,
                        "legacy_distribution": "bounded log-uniform",
                        "refinement_distribution": "bounded split triangular",
                        "structural_configurations": len(factorial),
                        "conditional_configurations": [row["configuration"]
                                                        for row in conditional_intervals]},
        "field_observation_permutation": {"iterations": 10000, "base_seed": 42,
                                          "null_models": ["national", "within_province"]},
        "qa_passed": all(row["passed"] for row in qa),
    }
    with open(asset_path(OUTPUTS, "fugitives_run_manifest_2024.json"), "w",
              encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)

    report = [
        "# Pakistan oil-and-gas fugitives, FY2023-24",
        "",
        "Reference-configuration IPCC-2019 estimate: **%.3f Mt CO2e (AR5)**." % total,
        "Parametric 95%% interval: **%.3f-%.3f Mt** (bounded input ranges, structural scenarios separate)." %
        (reference_mc["p025"], reference_mc["p975"]),
        "Legacy 2006 production-only benchmark: **%.3f Mt** for FY2019-20." % totals[1]["co2e_Mt_AR5"],
        "Pakistan's official 2022 CRT reports **%.3f Mt** for 1.B.2." %
        (crt_total["total_co2e_kt"] / 1000.0),
        "",
        "The difference is not closed by assumption. It is decomposed by segment, practice, activity basis, "
        "coverage and observations in the generated products. UFG is diagnostic only; VIIRS flare volume "
        "and UNEP MARS events are evaluation layers and are not double-counted into inclusive Tier-1 factors.",
    ]
    with open(asset_path(OUTPUTS, "fugitives_report.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(report) + "\n")


    print("Fugitive oil and gas FY2023-24 reference: %.3f Mt CO2e (AR5)" % total)
    print("  parametric 95%% interval %.3f-%.3f Mt" %
          (reference_mc["p025"], reference_mc["p975"]))
    scenario_mt = {row["scenario"]: row["mt_co2e_ar5"] for row in scenarios}
    print("  structural central %.3f; lower-practices %.3f; throughput %.3f; "
          "feedstock inside the base %.3f Mt" %
          (scenario_mt["central"], scenario_mt["lower_practices"],
           scenario_mt["throughput"], scenario_mt["post_meter_including_feedstock"]))
    print("  legacy 2006 FY2019-20 %.3f; official CRT 2022 %.3f Mt" %
          (totals[1]["co2e_Mt_AR5"], crt_total["total_co2e_kt"] / 1000.0))
    print("  World Bank flare sites %d; MARS oil/gas sources %d (%d plumes)" %
          (len(observations.pakistan_flare_sites()), mars["oil_gas_sources"], mars["oil_gas_plumes"]))


if __name__ == "__main__":
    main()

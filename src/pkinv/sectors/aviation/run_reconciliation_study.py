"""Build the complete public-data aviation reconciliation study.

This runner is deliberately separate from the provisional flight-stage runner.  It
produces the empirically complete Paper-A result from public OCAC, PCAA and OECD controls,
while retaining the source-neutral import contract for a later observed-flight upgrade.
"""
from __future__ import annotations

from pkinv.assets import asset_path

from pkinv.activity.store import read_rows as _activity_rows
import csv
import hashlib
import json
import os

from pkinv.core.runner import Runner
from pkinv.paths import DATA, OUTPUTS, ROOT
from pkinv.sectors.aviation import (
    annual, climatetrace, era5, fuel_bridge, ledger, monthly,
    official_reporting, uncertainty,
)
from pkinv.sectors.aviation.data import AviationData
from pkinv.sectors.aviation.reconstructed import PCAAReconstructedSource
from pkinv.sectors.aviation.study import (
    annual_component_comparison, annual_replication, carrier_share_scenarios,
    common_support_ladder, independence_matrix, payload_capacity_audits,
    route_activity_scenarios, route_distance_bounds,
)

ACTIVITY = asset_path(DATA, "activity", "aviation")


def _write(run, name, rows):
    """An empty table is deliberately NOT written (the clone's early return)."""
    path = asset_path(OUTPUTS, name)
    if not rows:
        return path
    return run.write_dicts(name, rows)


def _hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _carrier_bridges(data, scenarios):
    output = []
    by_scenario = {}
    for row in scenarios:
        by_scenario.setdefault(row["scenario"], {})[row["customer_group"]] = float(
            row["calibrated_domestic_share"])
    for scenario, shares in by_scenario.items():
        mapped = {"Domestic Avi-PIA": shares["PIA"],
                  "Domestic Avi-Others": shares["Others"]}
        output.extend(fuel_bridge.build_with_customer_shares(
            data, mapped, 2023, "carrier_%s" % scenario))
    return output


def _qa(data, cumulative, month_fuel, month_recon, components, bridges,
        bounds, ladder):
    final = {(int(r["fiscal_year"]), r["customer_category"]): float(r["cumulative_t"])
             for r in cumulative if int(r["period_index"]) == 12}
    published = {(r["fiscal_year"], r["customer_category"]): r["tonnes"]
              for year in (2022, 2023) for r in data.fuel_sales_for(year)
              if r["fuel_type"] == "JP-1" and r["customer_category"] in monthly.CUSTOMERS}
    monthly_sum = {}
    for row in month_fuel:
        key = (int(row["fiscal_year"]), row["customer_category"])
        monthly_sum[key] = monthly_sum.get(key, 0.0) + float(row["monthly_t"])
    completed = next(r for r in ladder if r["step"] == "completed_total")
    checks = [
        ("monthly_source_periods", len(cumulative) == 240 and len(month_fuel) == 240,
         len(month_fuel), 240),
        ("monthly_differences_nonnegative", all(float(r["monthly_t"]) >= 0 for r in month_fuel),
         min(float(r["monthly_t"]) for r in month_fuel), 0),
        ("monthly_to_cumulative_closure", all(abs(monthly_sum[k] - final[k]) < 1e-6 for k in final),
         max(abs(monthly_sum[k] - final[k]) for k in final), 1e-6),
        ("published_annual_source_closure", all(abs(final[k] - published[k]) < 1e-6
                                                 for k in published),
         max(abs(final[k] - published[k]) for k in published), 1e-6),
        ("matched_oecd_months", len(month_recon) == 42, len(month_recon), 42),
        ("annual_component_identity", all(abs(
            next(x for x in components if x["fiscal_year"] == y and x["component"] == "resident")["difference_co2_t"] +
            next(x for x in components if x["fiscal_year"] == y and x["component"] == "foreign")["difference_co2_t"] -
            next(x for x in components if x["fiscal_year"] == y and x["component"] == "combined")["difference_co2_t"]
        ) < 1e-6 for y in (2022, 2023)), 0, 1e-6),
        ("bridge_source_row_closure", all(abs(sum(float(r[k]) for k in fuel_bridge.ACCOUNTS) -
                                                    float(r["reported_t"])) < 1e-6 for r in bridges),
         max(abs(sum(float(r[k]) for k in fuel_bridge.ACCOUNTS) - float(r["reported_t"]))
             for r in bridges), 1e-6),
        ("route_distance_bound_order", bounds[0]["mean_stage_nm"] <= bounds[1]["mean_stage_nm"] <=
                                         bounds[2]["mean_stage_nm"],
         bounds[2]["mean_stage_nm"] - bounds[0]["mean_stage_nm"], ">=0"),
        ("common_support_identical_activity", len({round(r["stage_count"], 6) for r in ladder
                                                    if r["experiment"] == "common_support"}) == 1,
         next(r["stage_count"] for r in ladder if r["experiment"] == "common_support"), "one value"),
        ("coverage_completion_activity", abs(float(completed["stage_count"]) - 20300) < 1e-5,
         completed["stage_count"], 20300),
    ]
    return [{"check": name, "status": "PASS" if passed else "FAIL",
             "value": value, "threshold_or_expected": threshold}
            for name, passed, value, threshold in checks]


def run():
    run = Runner("aviation", lineterminator="\n", declared=(
        "aviation_ocac_cumulative_monthly.csv",
        "aviation_ocac_monthly.csv",
        "aviation_oecd_monthly.csv",
        "aviation_monthly_reconciliation.csv",
        "aviation_monthly_summary.csv",
        "aviation_ocac_annual_source_rows.csv",
        "aviation_ocac_annual_summary.csv",
        "aviation_ocac_oecd_annual_comparison.csv",
        "aviation_ocac_monthly_annual_closure.csv",
        "aviation_unfccc_official_comparison.csv",
        "aviation_unfccc_crt_extracted.csv",
        "aviation_unfccc_crt_cell_audit.csv",
        "aviation_climatetrace_national_monthly.csv",
        "aviation_climatetrace_periods.csv",
        "aviation_climatetrace_airport_monthly.csv",
        "aviation_climatetrace_airport_comparison.csv",
        "aviation_climatetrace_spatial_diagnostics.csv",
        "aviation_adsblol_pilot_summary.csv",
        "aviation_adsblol_pilot_days.csv",
        "aviation_adsblol_positive_controls.csv",
        "aviation_era5_route_weather.csv",
        "aviation_era5_openap_audit.csv",
        "aviation_era5_openap_diagnostics.csv",
        "aviation_route_activity_scenarios.csv",
        "aviation_payload_capacity_airlines.csv",
        "aviation_payload_capacity_airports.csv",
        "aviation_departure_control_comparison.csv",
        "aviation_m2_uncertainty_intervals.csv",
        "aviation_m2_structural_envelope.csv",
        "aviation_m2_uncertainty_contributions.csv",
        "aviation_annual_component_comparison.csv",
        "aviation_two_year_replication.csv",
        "aviation_carrier_share_scenarios.csv",
        "aviation_route_distance_bounds.csv",
        "aviation_common_support_ladder.csv",
        "aviation_uncertainty_inputs_complete.csv",
        "aviation_uncertainty_sensitivity.csv",
        "aviation_independence_matrix.csv",
        "aviation_bridge_source_rows_all_scenarios.csv"))
    os.makedirs(OUTPUTS, exist_ok=True)
    data, source = AviationData(), PCAAReconstructedSource()
    route_stages, endpoint_residual = source.route_ledger()
    aircraft_ledger = ledger.read(asset_path(OUTPUTS,
                                               "aviation_aircraft_ledger_fy2023_24.csv"))
    assigned_stages = [stage for stage in aircraft_ledger if stage.source_tier != "D"]
    lookup_rows = list(_activity_rows(asset_path(OUTPUTS, "aviation_openap_lookup_fy2023_24.csv"), comments=False))
    share_rows = list(_activity_rows(asset_path(ACTIVITY, "aircraft_family_shares_2023_24.csv"), comments=False))
    airport_controls, airline_controls = source.controls()

    cumulative, month_fuel = monthly.ocac_monthly()
    month_oecd = monthly.oecd_monthly()
    month_recon = monthly.reconciliation(month_fuel, month_oecd,
                                         data.p("co2_per_t_fuel"))
    month_summary = monthly.summary(month_recon)
    annual_source_rows = annual.source_rows()
    annual_summaries = annual.summaries(annual_source_rows, data.p("co2_per_t_fuel"))
    annual_oecd = annual.oecd_comparison(annual_summaries, month_oecd,
                                         data.p("co2_per_t_fuel"))
    annual_monthly_closure = annual.monthly_annual_closure(month_fuel, annual_source_rows)
    official_controls = official_reporting.controls()
    official_comparison = official_reporting.comparison(official_controls, month_oecd)
    official_crt = official_reporting.extract_crt()
    official_crt_audit = official_reporting.extract_crt_audit()
    climate_monthly = climatetrace.national_monthly()
    climate_periods = climatetrace.national_periods(climate_monthly)
    climate_airport_monthly = climatetrace.airport_monthly()
    climate_airports = climatetrace.airport_comparison(climate_airport_monthly)
    climate_spatial = climatetrace.spatial_diagnostics(climate_airports)
    # rc41: the pilot package is read from its consumed-derivative copy under
    # data/activity/aviation (scripts/ingest_aviation_study_inputs.py), not from sources/.
    adsblol_path = asset_path(ROOT, "data", "activity", "aviation",
                               "adsblol_pilot_fy2023_24.json")
    with open(adsblol_path, encoding="utf-8") as handle:
        adsblol_package = json.load(handle)
    adsblol_summary = [adsblol_package["summary"]]
    adsblol_days = adsblol_package["days"]
    adsblol_positive = adsblol_package.get("positive_controls", [])
    weather_rows = era5.route_weather()
    weather_audit = era5.performance_audit(weather_rows)
    weather_diagnostics = era5.diagnostics(weather_audit)
    components = annual_component_comparison(data)
    replication = annual_replication(data)
    carrier_scenarios = carrier_share_scenarios(data, assigned_stages)
    route_scenarios = route_activity_scenarios(source, assigned_stages)
    bounds = route_distance_bounds(source, assigned_stages)
    ladder = common_support_ladder(data, route_stages, assigned_stages,
                                   endpoint_residual)
    completed_fuel = next(r["fuel_t"] for r in ladder if r["step"] == "completed_total")
    airline_payload, airport_payload, departure_checks = payload_capacity_audits(
        assigned_stages, lookup_rows, airport_controls, airline_controls)
    endpoint_count = sum(stage.activity_count for stage in endpoint_residual) / 2.0
    weather_effects = [float(row["weather_fuel_change_pct"]) for row in weather_audit
                       if row["payload_scenario"] == "central"]
    m2_intervals, m2_envelope, m2_contributions = uncertainty.run_completed_m2(
        data, route_scenarios, endpoint_count, lookup_rows, share_rows,
        weather_effects, n_iter=20000, seed=20230806)

    bridge_rows = []
    for year in (2022, 2023):
        for scenario in fuel_bridge.SCENARIOS:
            bridge_rows.extend(fuel_bridge.build(data, year, scenario))
    bridge_rows.extend(_carrier_bridges(data, carrier_scenarios))
    factor_rows = uncertainty.full_factor_table(data, bounds)
    sensitivity_rows = uncertainty.one_at_a_time_sensitivity(
        data, assigned_stages, completed_fuel, bounds)
    independence = independence_matrix()
    qa = _qa(data, cumulative, month_fuel, month_recon, components,
             bridge_rows, bounds, ladder)
    complete_oecd_years = [row for row in annual_oecd if row["period_status"] == "complete"]
    qa.extend([
        {"check": "nine_year_ocac_source_rows", "status": "PASS" if
         len(annual_source_rows) == 135 else "FAIL", "value": len(annual_source_rows),
         "threshold_or_expected": 135},
        {"check": "nine_year_ocac_summaries", "status": "PASS" if
         len(annual_summaries) == 9 else "FAIL", "value": len(annual_summaries),
         "threshold_or_expected": 9},
        {"check": "monthly_annual_revision_exposed", "status": "PASS" if
         sum(row["closure_status"] != "exact" for row in annual_monthly_closure) == 1 else "FAIL",
         "value": sum(row["closure_status"] != "exact" for row in annual_monthly_closure),
         "threshold_or_expected": "1 explicit FY2024 revision"},
        {"check": "five_complete_ocac_oecd_years", "status": "PASS" if
         len(complete_oecd_years) == 5 else "FAIL", "value": len(complete_oecd_years),
         "threshold_or_expected": 5},
        {"check": "official_unfccc_notation_complete", "status": "PASS" if
         len(official_comparison) == 6 and all(row["notation"] for row in official_comparison)
         else "FAIL", "value": len(official_comparison), "threshold_or_expected": 6},
        {"check": "official_crt_extraction", "status": "PASS" if
         len(official_crt) == 2 and abs(sum(row["domestic_distribution_pct"]
                                           for row in official_crt[:1]) - 80) < 1e-9
         else "FAIL", "value": len(official_crt), "threshold_or_expected": "2 aviation rows"},
        {"check": "official_crt_cell_audit", "status": "PASS" if
         len(official_crt_audit) == 21 and
         {row["source_reference"] for row in official_crt_audit} >=
         {"Table1!C25", "Table1!C53", "Table1.A(a)s3!C18", "Table1.D!L9", "Table1.D!M9"}
         else "FAIL", "value": len(official_crt_audit), "threshold_or_expected": "21 pinned cells"},
        {"check": "climatetrace_national_months", "status": "PASS" if
         len(climate_monthly) == 240 else "FAIL", "value": len(climate_monthly),
         "threshold_or_expected": 240},
        {"check": "climatetrace_airport_match_coverage", "status": "PASS" if
         sum(row["match_status"] != "unmatched" for row in climate_airport_monthly) /
         len(climate_airport_monthly) >= 0.80 else "FAIL",
         "value": sum(row["match_status"] != "unmatched" for row in climate_airport_monthly) /
         len(climate_airport_monthly), "threshold_or_expected": ">=0.80"},
        {"check": "climatetrace_spatial_rank", "status": "PASS" if
         all(float(row["spearman_rank_correlation"]) > 0.8 for row in climate_spatial)
         else "FAIL", "value": min(float(row["spearman_rank_correlation"])
                                     for row in climate_spatial),
         "threshold_or_expected": ">0.8"},
        {"check": "adsblol_four_day_pilot", "status": "PASS" if
         adsblol_summary[0]["archives_processed"] == 4 and
         adsblol_summary[0]["source_license"] == "Open Database License 1.0 (ODbL)"
         else "FAIL", "value": adsblol_summary[0]["archives_processed"],
         "threshold_or_expected": "4 archives; ODbL recorded"},
        {"check": "adsblol_coverage_result_explicit", "status": "PASS" if
         "pakistan_airport_linked_legs" in adsblol_summary[0] or
         adsblol_summary[0]["canonical_stages"] == 0 else "FAIL",
         "value": adsblol_summary[0].get("pakistan_airport_linked_legs", 0),
         "threshold_or_expected": ">=0; zero is a valid coverage finding"},
        {"check": "adsblol_positive_controls", "status": "PASS" if
         len(adsblol_positive) == 2 and all(row["status"] == "PASS"
                                             for row in adsblol_positive)
         else "FAIL", "value": sum(row.get("status") == "PASS"
                                    for row in adsblol_positive),
         "threshold_or_expected": "2 parser/gate controls"},
        {"check": "era5_route_weather_coverage", "status": "PASS" if
         len(weather_rows) == 6 and len(weather_audit) > 0 else "FAIL",
         "value": "%d routes; %d route-aircraft-payload rows" %
         (len(weather_rows), len(weather_audit)), "threshold_or_expected": "6 routes; >0 rows"},
        {"check": "m2_monte_carlo_stage_closure", "status": "PASS" if
         all(abs(float(row["stage_count"]) - 20300) < 1e-5 for row in m2_intervals)
         else "FAIL", "value": max(abs(float(row["stage_count"]) - 20300)
                                    for row in m2_intervals),
         "threshold_or_expected": "<1e-5 stages"},
        {"check": "m2_monte_carlo_convergence", "status": "PASS" if
         max(float(row["half_sample_p50_difference_pct"]) for row in m2_intervals) < 0.5
         else "FAIL", "value": max(float(row["half_sample_p50_difference_pct"])
                                    for row in m2_intervals),
         "threshold_or_expected": "<0.5% median difference"},
        {"check": "m2_excludes_aggregate_representation_term", "status": "PASS" if
         all("aggregate" not in row["parametric_inputs"].lower() for row in m2_intervals)
         else "FAIL", "value": sum("aggregate" in row["parametric_inputs"].lower()
                                    for row in m2_intervals), "threshold_or_expected": 0},
        {"check": "pcaa_payload_capacity_audit", "status": "PASS" if
         len(airline_payload) == 10 and all(float(row["passengers_per_departure"]) >= 0
                                            for row in airline_payload)
         else "FAIL", "value": len(airline_payload), "threshold_or_expected": 10},
        {"check": "published_departure_checks", "status": "PASS" if
         len(departure_checks) == 2 else "FAIL", "value": len(departure_checks),
         "threshold_or_expected": 2},
    ])
    # The literal PASS/FAIL rows become harness gates; finalize() below writes
    # the table on the unified schema and raises AFTER every product is on disk.
    for row in qa:
        run.gate(row["check"], row["status"] == "PASS",
                 row["value"], row["threshold_or_expected"])

    products = {
        "aviation_ocac_cumulative_monthly.csv": cumulative,
        "aviation_ocac_monthly.csv": month_fuel,
        "aviation_oecd_monthly.csv": month_oecd,
        "aviation_monthly_reconciliation.csv": month_recon,
        "aviation_monthly_summary.csv": month_summary,
        "aviation_ocac_annual_source_rows.csv": annual_source_rows,
        "aviation_ocac_annual_summary.csv": annual_summaries,
        "aviation_ocac_oecd_annual_comparison.csv": annual_oecd,
        "aviation_ocac_monthly_annual_closure.csv": annual_monthly_closure,
        "aviation_unfccc_official_comparison.csv": official_comparison,
        "aviation_unfccc_crt_extracted.csv": official_crt,
        "aviation_unfccc_crt_cell_audit.csv": official_crt_audit,
        "aviation_climatetrace_national_monthly.csv": climate_monthly,
        "aviation_climatetrace_periods.csv": climate_periods,
        "aviation_climatetrace_airport_monthly.csv": climate_airport_monthly,
        "aviation_climatetrace_airport_comparison.csv": climate_airports,
        "aviation_climatetrace_spatial_diagnostics.csv": climate_spatial,
        "aviation_adsblol_pilot_summary.csv": adsblol_summary,
        "aviation_adsblol_pilot_days.csv": adsblol_days,
        "aviation_adsblol_positive_controls.csv": adsblol_positive,
        "aviation_era5_route_weather.csv": weather_rows,
        "aviation_era5_openap_audit.csv": weather_audit,
        "aviation_era5_openap_diagnostics.csv": weather_diagnostics,
        "aviation_route_activity_scenarios.csv": route_scenarios,
        "aviation_payload_capacity_airlines.csv": airline_payload,
        "aviation_payload_capacity_airports.csv": airport_payload,
        "aviation_departure_control_comparison.csv": departure_checks,
        "aviation_m2_uncertainty_intervals.csv": m2_intervals,
        "aviation_m2_structural_envelope.csv": m2_envelope,
        "aviation_m2_uncertainty_contributions.csv": m2_contributions,
        "aviation_annual_component_comparison.csv": components,
        "aviation_two_year_replication.csv": replication,
        "aviation_carrier_share_scenarios.csv": carrier_scenarios,
        "aviation_route_distance_bounds.csv": bounds,
        "aviation_common_support_ladder.csv": ladder,
        "aviation_uncertainty_inputs_complete.csv": factor_rows,
        "aviation_uncertainty_sensitivity.csv": sensitivity_rows,
        "aviation_independence_matrix.csv": independence,
        "aviation_bridge_source_rows_all_scenarios.csv": bridge_rows,
    }
    written = {name: _write(run, name, rows) for name, rows in products.items()}
    run.finalize(qa_table="aviation_reconciliation_qa.csv")
    products["aviation_reconciliation_qa.csv"] = run.checks
    written["aviation_reconciliation_qa.csv"] = asset_path(
        OUTPUTS, "aviation_reconciliation_qa.csv")
    manifest = {
        "schema": "pkinv.aviation.reconciliation_study/v1",
        "status": "complete_public-data_reconciliation; flight-stage products provisional",
        "fiscal_years": list(range(2016, 2025)), "matched_months": len(month_recon),
        "qa_checks": len(run.checks), "qa_passed": sum(r["passed"] for r in run.checks),
        "products": {name: {"rows": len(products[name]), "sha256": _hash(path)}
                     for name, path in written.items()},
        "source_contract": "Tier A/B observed stages can replace Tier C/D without changing accounting",
    }
    manifest_path = asset_path(OUTPUTS, "aviation_reconciliation_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return manifest


def main():
    print(json.dumps(run(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

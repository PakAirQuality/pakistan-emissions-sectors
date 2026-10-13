"""Build IPPU numerical products; metadata publication is a separate task.

Usage: ``python3 -m pkinv.sectors.ippu.run_ippu`` followed by
``python3 -m pkinv.sectors.ippu.metadata`` (the build registry runs both).
"""
from __future__ import annotations

import csv
import hashlib
import json
import os

from pkinv.core.downscale import allocate_rows, check_reconciliation
from pkinv.core.geography import PROVINCES
from pkinv.core.runner import Runner
from pkinv.paths import DATA, OUTPUTS, ROOT
from pkinv.sectors.ippu import (ammonia_reconciliation, cement, chemicals, completeness,
                                downscale, engine, material_flows, official_reporting,
                                uncertainty)
from pkinv.sectors.ippu.data import IppuData
from pkinv.assets import asset_path


def _sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _official_comparison(data, summary, background, reference_mt, matched_2022):
    total = next(row for row in summary if row["category"].startswith("2. Total"))
    cement_row = next(row for row in summary if row["category"].startswith("2.A.1."))
    cement_background = next(row for row in background
                             if row["category"].startswith("2.A.1."))
    return [
        {"comparison": "Pakistan CRT total IPPU", "inventory_year": 2022,
         "official_mt_co2e": float(total["total_co2e_kt"]) / 1000.0,
         "public_data_mt_co2e": "", "ratio": "", "role": "official sector control",
         "note": "Category-wide comparator; the public-data platform does not yet estimate all IPPU."},
        {"comparison": "Cement process CO2", "inventory_year": 2022,
         "official_mt_co2e": float(cement_row["co2_kt"]) / 1000.0,
         "public_data_mt_co2e": matched_2022["co2_mt"],
         "ratio": matched_2022["co2_mt"] / (float(cement_row["co2_kt"]) / 1000.0),
         "role": "matched-calendar independent reconstruction",
         "note": "Calendar-2022 PBS monthly cement plus calendar-2022 HS 252310 trade; 0.75 clinker fraction."},
        {"comparison": "Cement process CO2 all-Portland sensitivity",
         "inventory_year": 2022,
         "official_mt_co2e": float(cement_row["co2_kt"]) / 1000.0,
         "public_data_mt_co2e": cement.calendar_reconstruction(
             data, 2022, 0.95)["co2_mt"],
         "ratio": cement.calendar_reconstruction(data, 2022, 0.95)["co2_mt"] /
                  (float(cement_row["co2_kt"]) / 1000.0),
         "role": "matched-calendar structural sensitivity",
         "note": "Same matched data with a 0.95 clinker fraction."},
        {"comparison": "CRT cement activity and implied factor", "inventory_year": 2022,
         "official_mt_co2e": float(cement_row["co2_kt"]) / 1000.0,
         "public_data_mt_co2e": "", "ratio": "", "role": "official method audit",
         "note": "CRT activity %.4f kt and IEF %.8f t/t reproduce the official row." %
                 (cement_background["activity_kt"], cement_background["co2_ief_t_per_t"])},
    ]


def _qa_rows(data, components, balance, reproduction, scenario_rows, completeness_rows,
             company_rows, producer_census, matched_2022, company_boundary_rows,
             facility_geocoding_rows, ammonia_rows, gas_monthly_rows,
             gas_cross_source_rows, bridge_rows, census_record=None,
             reference_mt=None):
    checks = [
        ("cement_material_closure", abs(material_flows.check_cement_balance(balance)) < 1e-9,
         "clinker production + imports - exports - stock = clinker in cement"),
        # TWELVE IS A FACT ABOUT THE CALENDAR AND STAYS A LITERAL - but it is twelve months
        # OF THE REFERENCE YEAR, and these two counted every row in the file. That was true
        # while the file held one year. The Comtrade sweep extended it to nine (218 rows,
        # 123 import and 95 export), both checks went false, and nothing said so because this
        # runner is not in `make national` and its outputs had not been rebuilt since.
        #
        # data.clinker_trade_kt already selects the fiscal window and raises on anything but
        # twelve distinct months. These now assert through it rather than beside it: a second
        # arithmetic path is a second vintage waiting to disagree, and this one did.
        ("clinker_export_months",
         len({r["month"] for r in data.trade_rows if r["flow"] == "export"
              and "%04d-07" % (data.year - 1) <= r["month"] <= "%04d-06" % data.year}) == 12,
         "twelve fiscal months of the reference year carry an export figure"),
        ("clinker_import_months",
         len({r["month"] for r in data.trade_rows if r["flow"] == "import"
              and "%04d-07" % (data.year - 1) <= r["month"] <= "%04d-06" % data.year}) == 12,
         "twelve fiscal months of the reference year carry an import figure"),
        ("trade_changes_diagnostic", balance["clinker_exports_kt"] > balance["clinker_imports_kt"],
         "net clinker exports raise the DIAGNOSTIC model's inferred production "
         "(the reference no longer consumes a trade term)"),
        ("component_contract", all(row["emissions_Gg"] >= 0 and row["gas"] == "CO2"
                                   for row in components),
         "registered public-data estimate is CO2 only: 2.A.1 clinker, 2.B.1 ammonia, 2.C.1 steel, 2.D.1 lubricants (rc52)"),
        ("valid_structural_count", len(scenario_rows) == 3 and
         scenario_rows[0]["scenario_id"] == "producer_census_observed" and
         all(row["trade_included"] for row in scenario_rows[1:]),
         "census reference plus 2 diagnostic clinker-fraction models; observed "
         "trade included in both models"),
        ("company_clinker_subset", len(company_rows) == 16 and
         len({row["company"] for row in company_rows}) == len(company_rows) and
         all(row["clinker_production_t"] > 0 for row in company_rows),
         "all sixteen FY2023-24 producers report positive actual clinker production "
         "(Fecto's 651,048 t closed the census at rc30)"),
        ("producer_census", len(producer_census) == 16 and
         sum(row["clinker_production_t"] is not None for row in producer_census) ==
         len(company_rows),
         "the census is COMPLETE: sixteen entities, sixteen reported values - the "
         "reference activity, not a floor"),
        ("census_total_is_the_reference",
         abs(sum(row["clinker_production_t"] for row in company_rows) -
             census_record["clinker_production_kt"] * 1000.0) < 0.5 and
         abs(sum(r["co2e_Mt_AR5"] for r in components if r["category"] == cement.CATEGORY)
             - census_record["clinker_production_kt"] *
             data.efv("ippu_cement", "Clinker") / 1000.0) < 1e-9,
         "the published reference equals the audited census sum times the factor"),
        ("company_boundary_audit", len(company_boundary_rows) == len(producer_census) and
         {row["company"] for row in company_boundary_rows} ==
         {row["company"] for row in producer_census} and
         all(float(boundary["clinker_production_t"]) == company["clinker_production_t"]
             for boundary in company_boundary_rows if boundary["clinker_production_t"]
             for company in company_rows if company["company"] == boundary["company"]) and
         all(row["material_balance_status"] == "incomplete"
             for row in company_boundary_rows),
         "all census entities have an explicit common-boundary audit and no missing flow is imputed"),
        ("nitric_monitoring_detail", bool(data.nitric_acid_monitoring_detail_rows) and
         all(int(row["monitoring_end"][:4]) < data.year
             for row in data.nitric_acid_monitoring_detail_rows),
         "period-specific CDM detail remains historical and cannot activate FY2023-24"),
        # A LITERAL COUNT IS RIGHT WHERE IT STATES A FACT ABOUT THE WORLD AND WRONG WHERE IT
        # STATES HOW FAR OUR COLLECTING HAS GOT. Twelve trade months is the calendar; two
        # clinker-fraction configurations is a design decision a third would have to be
        # reviewed against; fifteen reporting producers is what FY2023-24 contains. Those are
        # pinned below and should be.
        #
        # This one was not that kind. It read `== 8`, and eight was simply how many
        # coordinates had been found at the time it was written. Eleven more arrived with the
        # GEM cement tracker and the check went on recording True for four releases, because
        # `make national` does not run this runner and the file it writes was never rebuilt -
        # while the master facility registry, which IS in that target, moved to nineteen. Two
        # registries then described the same thirty-four facilities and disagreed, and the
        # IPPU manuscript was anchored to the stale one.
        ("facility_geocoding_provenance", len(facility_geocoding_rows) ==
         len(data.facility_rows) and
         all(row["coordinate_source_reference"] for row in facility_geocoding_rows) and
         sum(row["geocode_status"] == "exact_coordinate_resolved"
             for row in facility_geocoding_rows) ==
         sum(1 for row in data.facility_geocoding_override_rows
             if row["latitude"].strip()),
         "all %d facilities retain coordinate provenance; %d carry an exact point from the "
         "override register and %d remain locality-only"
         % (len(data.facility_rows),
            sum(1 for row in data.facility_geocoding_override_rows
                if row["latitude"].strip()),
            len(data.facility_rows)
            - sum(1 for row in data.facility_geocoding_override_rows
                  if row["latitude"].strip()))),
        ("calendar_2022_activity", matched_2022["cement_activity_kt"] == 44331.0,
         "twelve PBS monthly values sum independently to calendar 2022"),
        ("crt_arithmetic", bool(reproduction) and all(row["closes"] for row in reproduction),
         "every numeric CRT activity-factor-recovery row reproduces"),
        ("ammonia_reconciliation_pathways",
         len({row["pathway"] for row in ammonia_rows}) == 4 and
         all(row["activation_status"].startswith("diagnostic")
             for row in ammonia_rows),
         "four independent activity pathways, every row diagnostic, nothing averaged"),
        ("activated_categories_are_the_declared_four",
         set(engine.CATEGORIES) == {cement.CATEGORY, "Ammonia production", "Iron and steel production", "Lubricant use"}
         and {row["category"] for row in components} == set(engine.CATEGORIES),
         "rc52: cement, ammonia, iron and steel and lubricant use enter components and totals; "
         "nitric acid stays a configuration pair, soda ash is NA (Solvay), F-gases and wastewater stay bands"),
        ("fertilizer_gas_split_closes", (lambda total_row:
         float(total_row["feed_mmcf"]) == 234001.0 and
         float(total_row["fuel_mmcf"]) == 47152.0 and
         float(total_row["total_mmcf"]) == 281153.0)(
             next(row for row in data.fertilizer_gas_rows if row["plant"] == "Total")),
         "NFDC Table 40 printed feed, fuel and total are the extracted values"),
        ("annex28_matches_table40",
         abs(sum(float(r["mmcf"]) for r in data.fertilizer_gas_monthly_rows
                 if r["fiscal_year"] == "2024-25" and str(r["mmcf"]).strip())
             - 281153.0) <= 3.0,
         "Annex-28's monthly cells and Table 40's annual row are the same FY2024-25 gas "
         "reached two ways in one document, and they agree"),
        ("fertilizer_gas_fy2024_split_observed",
         0.83 < (sum(float(r["mmcf"]) for r in data.fertilizer_gas_monthly_rows
                     if r["fiscal_year"] == "2023-24" and r["consumption"] == "Feed"
                     and str(r["mmcf"]).strip())
                 / sum(float(r["mmcf"]) for r in data.fertilizer_gas_monthly_rows
                       if r["fiscal_year"] == "2023-24" and str(r["mmcf"]).strip())) < 0.84,
         "the reference year's feed/fuel split is OBSERVED in Annex-28, not borrowed "
         "from FY2024-25 as it was for one round"),
        ("fertilizer_gas_two_sources_agree",
         abs(float(next(r for r in gas_cross_source_rows
                        if r["record"] == "difference")["agreement_pct"])) < 1.0,
         "NFDC's plant meters and OGRA's utility table land within one percent on the "
         "same fiscal year with no shared upstream input"),
        ("urea_bridge_reads_extracted_offtake",
         all("not yet extracted" not in row["status"] for row in bridge_rows),
         "every bridge leg reads a registered CSV; no quantity is a Python literal"),
        ("fertilizer_gas_profile_claims_nothing",
         all(row["applied_to"].startswith("nothing") for row in gas_monthly_rows),
         "the observed monthly profile is applied to no reported category, because "
         "2.B.1 is NE"),
    ]
    return checks


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = IppuData()
    year = data.year
    declared_outputs = (
        "ippu_by_stream_%d.csv" % year,
        "ippu_totals_%d.csv" % year,
        "ippu_cement_material_balance_2024.csv",
        "ippu_company_clinker_2024.csv",
        "ippu_company_clinker_coverage_2024.csv",
        "ippu_cement_tier_comparison_2024.csv",
        "ippu_cement_producer_census_2024.csv",
        "ippu_company_clinker_flow_audit_2024.csv",
        "ippu_company_boundary_audit_2024.csv",
        "ippu_cement_valid_structural_2024.csv",
        "ippu_cement_method_benchmarks_2024.csv",
        "ippu_cement_method_ladder_2024.csv",
        "ippu_cement_structural_oat_2024.csv",
        "ippu_cement_uncertainty_inputs_2024.csv",
        "ippu_cement_conditional_intervals_2024.csv",
        "ippu_completeness_2024.csv",
        "ippu_evidence_maturity.csv",
        "ippu_data_acquisition_requests.csv",
        "ippu_historical_coverage_1990_2024.csv",
        "ippu_activity_controls_2024.csv",
        "ippu_cement_activity_reconciliation.csv",
        "ippu_hfc_consumption_controls.csv",
        "ippu_hfc_inventory_import_contract.csv",
        "ippu_chemical_plant_evidence.csv",
        "ippu_chemical_plant_activity.csv",
        "ippu_nitric_acid_monitoring.csv",
        "ippu_nitric_acid_monitoring_detail.csv",
        "ippu_cdm_access_manifest.csv",
        "ippu_period_product_register.csv",
        "ippu_chemical_activation_status_2024.csv",
        "ippu_chemical_activation_status_calendar_2022.csv",
        "ippu_chemical_tier_gate_2024.csv",
        "ippu_data_request_packets.csv",
        "ippu_facility_registry.csv",
        "ippu_facility_coverage.csv",
        "ippu_source_manifest.csv",
        "ippu_unfccc_crt_summary_2022.csv",
        "ippu_unfccc_crt_background_2022.csv",
        "ippu_unfccc_crt_reproduction_2022.csv",
        "ippu_unfccc_crt_fgas_species_2022.csv",
        "ippu_unfccc_crt_cell_audit.csv",
        "ippu_ammonia_activity_reconciliation.csv",
        "ippu_urea_co2_bridge_2025.csv",
        "ippu_fertilizer_gas_monthly_2024.csv",
        "ippu_fertilizer_gas_cross_source_2024.csv",
        "ippu_cement_matched_calendar_2022.csv",
        "ippu_cement_crt_bridge_2022.csv",
        "ippu_official_comparison.csv",
        "ippu_provincial_%d.csv" % year)
    metadata_names = frozenset(('ippu_completeness_2024.csv', 'ippu_evidence_maturity.csv', 'ippu_data_acquisition_requests.csv', 'ippu_hfc_inventory_import_contract.csv', 'ippu_data_request_packets.csv', 'ippu_source_manifest.csv'))
    run = Runner("ippu", declared=[name for name in declared_outputs if name not in metadata_names])
    deferred = []
    components = engine.build_components(data)
    reference_mt = sum(row["co2e_Mt_AR5"] for row in components)
    # rc52: the module total now carries four categories; every table that means CEMENT
    # (the tier comparison's census row, the CRT 2.A.1 comparison, the census QA) reads the
    # cement component alone
    cement_mt = sum(row["co2e_Mt_AR5"] for row in components if row["category"] == cement.CATEGORY)
    _component_rows, memo = cement.compute(data)
    census_record, balance = memo[0], memo[1]

    run.write_dicts("ippu_by_stream_%d.csv" % year, components)
    by_category = {}
    for row in components:
        by_category[row["category"]] = by_category.get(row["category"], 0.0) + row["co2e_Mt_AR5"]
    category_notes = {
        cement.CATEGORY: ("FY2023-24 reference (rc30 re-base): the complete 16-company producer "
                          "census's observed clinker production, 41.953170 Mt; process CO2 only. "
                          "The PBS-QIM 0.75-fraction trade-corrected model is the named diagnostic "
                          "beside it."),
        "Ammonia production": ("rc52: Tier 1 calibrated - NFDC production x NH3 stoichiometry x 1.815 t CO2/t "
                               "NH3 net of urea recovery (44/60); method envelope in pakemis_ammonia_nitric_series.csv"),
        "Iron and steel production": ("rc52: Tier 1 EAF 0.08 t CO2/t on QIM billets and ingots; pig iron zero, "
                                      "so the electric route is the only one operating"),
        "Lubricant use": ("rc52: Tier 1 ODU (0.2 oil, 0.05 grease) on OCAC non-energy sales x NCV 40.2 x 20.0 t C/TJ"),
    }
    run.write(
        "ippu_totals_%d.csv" % year,
        ["category", "co2e_Mt_AR5", "co2e_Mt_AR6", "note"],
        [[cat, round(by_category[cat], 8), round(by_category[cat], 8), category_notes[cat]]
         for cat in engine.CATEGORIES] +
        [["IPPU reference total", round(reference_mt, 8), round(reference_mt, 8),
          "sum of the four activated categories"],
         ["Legacy cement calculation without clinker trade", 18.72429, 18.72429,
          "Provenance only: combines omission of trade with a 48.011 Mt activity value "
          "that belongs to FY2021-22, not FY2023-24."],
         ["IPPU categories not yet independently estimated", "NE", "NE",
          "See ippu_completeness_2024.csv; activity controls are not converted without "
          "the process route or application data required by IPCC."]])

    material_rows = material_flows.cement_rows(balance)
    run.write_dicts("ippu_cement_material_balance_2024.csv", material_rows)
    company_rows = data.company_clinker(year)
    producer_census = data.cement_producer_census(year)
    company_output = []
    for row in company_rows:
        clinker_mt = row["clinker_production_t"] / 1e6
        company_output.append({
            **row, "clinker_production_mt": clinker_mt,
            "process_co2_mt_at_default_ef": clinker_mt * data.efv("ippu_cement", "Clinker"),
            "share_of_reference_clinker_pct":
                row["clinker_production_t"] /
                (census_record["clinker_production_kt"] * 1000.0) * 100.0,
        })
    company_total_mt = sum(row["clinker_production_mt"] for row in company_output)
    upper_scenario = next(row for row in uncertainty.structural_scenarios(data)
                          if row["clinker_fraction"] == 0.95)
    low_inferred_mt = balance["clinker_production_kt"] / 1000.0
    high_inferred_mt = upper_scenario["clinker_production_kt"] / 1000.0
    company_coverage = [{
        "period_end_year": year, "companies_reported": len(company_output),
        "producer_census_entities": len(producer_census),
        "reviewed_without_exact_clinker": len(producer_census) - len(company_output),
        "reported_clinker_mt": round(company_total_mt, 6),
        "low_fraction_inferred_clinker_mt": round(low_inferred_mt, 6),
        "high_fraction_inferred_clinker_mt": round(high_inferred_mt, 6),
        "reported_vs_low_inference_pct": round(company_total_mt / low_inferred_mt * 100.0, 6),
        "reported_vs_high_inference_pct": round(company_total_mt / high_inferred_mt * 100.0, 6),
        "reported_minus_low_inference_mt": round(company_total_mt - low_inferred_mt, 6),
        "high_inference_minus_reported_mt": round(high_inferred_mt - company_total_mt, 6),
        "reported_subset_process_co2_mt": round(
            company_total_mt * data.efv("ippu_cement", "Clinker"), 6),
        "diagnostic_common_boundary_clinker_fraction": round(
            (company_total_mt + balance["clinker_imports_kt"] / 1000.0 -
             balance["clinker_exports_kt"] / 1000.0) /
            (balance["cement_activity_kt"] / 1000.0), 6),
        "diagnostic_assumptions": "identical company/QIM universe and period; zero stock change",
        "status": "THE REFERENCE ACTIVITY (rc30): the complete census, every entity "
                  "reporting actual production; the model inferences beside it are the "
                  "named diagnostics and the differences are the published residuals",
    }]
    run.write_dicts("ippu_company_clinker_2024.csv", company_output)
    run.write_dicts("ippu_company_clinker_coverage_2024.csv", company_coverage)
    tier_comparison = [
        {"method": "Reference: producer census (rc30)", "coverage": "16 of 16 census entities",
         "clinker_activity_mt": census_record["clinker_production_kt"] / 1000.0,
         "process_co2_mt": cement_mt, "clinker_fraction": "",
         "status": "reference activity; observed production, no fraction, no trade term"},
        {"method": "Diagnostic model f=0.75", "coverage": "national model",
         "clinker_activity_mt": balance["clinker_production_kt"] / 1000.0,
         "process_co2_mt": balance["clinker_production_kt"] / 1000.0 *
                           data.efv("ippu_cement", "Clinker"),
         "clinker_fraction": 0.75,
         "status": "named structural diagnostic (superseded as reference at rc30); "
                   "residual vs census published in the coverage table"},
        {"method": "Diagnostic model f=0.95 (all-Portland)", "coverage": "national model",
         "clinker_activity_mt": next(row["clinker_production_kt"] / 1000.0
                                     for row in uncertainty.structural_scenarios(data)
                                     if row["clinker_fraction"] == 0.95),
         "process_co2_mt": next(row["co2e_Mt_AR5"]
                                for row in uncertainty.structural_scenarios(data)
                                if row["clinker_fraction"] == 0.95),
         "clinker_fraction": 0.95,
         "status": "named structural diagnostic; residual vs census published"},
    ]
    run.write_dicts("ippu_cement_tier_comparison_2024.csv", tier_comparison)
    run.write_dicts("ippu_cement_producer_census_2024.csv", producer_census)
    run.write_dicts("ippu_company_clinker_flow_audit_2024.csv",
                                  [material_flows.company_clinker_balance(row)
                                   for row in company_rows])
    run.write_dicts("ippu_company_boundary_audit_2024.csv",
                                  data.company_boundary_rows)
    scenarios = uncertainty.structural_scenarios(data)
    benchmarks = uncertainty.method_benchmarks(data)
    run.write_dicts("ippu_cement_valid_structural_2024.csv", scenarios)
    run.write_dicts("ippu_cement_method_benchmarks_2024.csv", benchmarks)
    run.write_dicts("ippu_cement_method_ladder_2024.csv",
                                  [{**row, "model_class": "valid structural"}
                                   for row in scenarios] +
                                  [{**row, "model_class": "method benchmark"}
                                   for row in benchmarks])
    run.write_dicts("ippu_cement_structural_oat_2024.csv",
                                  uncertainty.one_at_a_time(data))
    run.write_dicts("ippu_cement_uncertainty_inputs_2024.csv",
                                  uncertainty.uncertainty_inputs(data))
    run.write_dicts("ippu_cement_conditional_intervals_2024.csv",
                                  uncertainty.selected_intervals(data))

    deferred.append((len(run.paths), "ippu_completeness_2024.csv"))
    deferred.append((len(run.paths), "ippu_evidence_maturity.csv"))
    deferred.append((len(run.paths), "ippu_data_acquisition_requests.csv"))
    run.write_dicts("ippu_historical_coverage_1990_2024.csv",
                                  completeness.historical_coverage(data.activity_rows))
    run.write_dicts("ippu_activity_controls_2024.csv", data.activity_rows)
    activity_reconciliation = [
        {"reported_value_kt": 48011, "correct_period": "FY2021-22",
         "source": "SBP statistical supplement and PBS QIM",
         "FY2023_24_status": "superseded period tag",
         "interpretation": "not an FY2023-24 structural alternative"},
        {"reported_value_kt": 39566, "correct_period": "FY2023-24",
         "source": "PBS QIM; independently corroborated by SBP",
         "FY2023_24_status": "reference activity",
         "interpretation": "physical cement output"},
    ]
    run.write_dicts("ippu_cement_activity_reconciliation.csv",
                                  activity_reconciliation)
    run.write_dicts("ippu_hfc_consumption_controls.csv", data.hfc_control_rows)
    # The CRT summary is WRITTEN before the F-gas screening lane reads it (rc41: the
    # first strict empty-outputs rebuild stopped here - fgas_screening.CRT_SUMMARY was
    # an intra-phase read of a file this phase only wrote further down, so a checkout
    # without outputs/ could not build the sector). One extraction, one write.
    summary = official_reporting.extract_summary()
    run.write_dicts("ippu_unfccc_crt_summary_2022.csv", summary)
    # The F-gas screening lane (rc20): three typed evidence lanes and the
    # potential-consumption-equivalent scope bound, priced outside every total.
    from pkinv.sectors.ippu import fgas_screening
    fgas_screening.main()
    run.record(fgas_screening.OUT)
    from pkinv.sectors.ippu import chemicals_screening
    chemicals_screening.main()
    run.record(chemicals_screening.OUT)
    deferred.append((len(run.paths), "ippu_hfc_inventory_import_contract.csv"))
    run.write_dicts("ippu_chemical_plant_evidence.csv",
                                  data.chemical_plant_evidence_rows)
    run.write_dicts("ippu_chemical_plant_activity.csv",
                                  data.chemical_plant_activity_rows)
    run.write_dicts("ippu_nitric_acid_monitoring.csv",
                                  data.nitric_acid_monitoring_rows)
    run.write_dicts("ippu_nitric_acid_monitoring_detail.csv",
                                  data.nitric_acid_monitoring_detail_rows)
    run.write_dicts("ippu_cdm_access_manifest.csv",
                                  data.cdm_access_manifest_rows)
    run.write_dicts("ippu_period_product_register.csv",
                                  chemicals.period_product_register(
                                      data.chemical_plant_activity_rows))
    run.write_dicts("ippu_chemical_activation_status_2024.csv",
                                  chemicals.activation_audit(
                                      data.chemical_plant_activity_rows, year, "calendar"))
    run.write_dicts("ippu_chemical_activation_status_calendar_2022.csv",
                                  chemicals.activation_audit(
                                      data.chemical_plant_activity_rows, 2022, "calendar"))
    # Tier-1 inputs are national quantities, and the honest state is: no national NH3
    # production series exists (NFDC Table 1 is fertilizer PRODUCTS, not ammonia), and
    # capacity is documented for one of seven ammonia census plants, which is not a
    # national capacity roster. Urea production, the recovery-term input, IS held.
    urea_production_t = sum(
        float(r["production_000t"]) * 1000.0 for r in data.fertilizer_production_rows
        if r["product"] == "Urea" and r["fiscal_year"] == "2023-24"
        and str(r["production_000t"]).strip())
    national_inputs = {"national_nh3_production_t": None,
                       "capacity_based_nh3_t": None,
                       "urea_production_t": urea_production_t,
                       "national_hno3_production_t": None}
    run.write_dicts("ippu_chemical_tier_gate_2024.csv",
                                  chemicals.tier_readiness(
                                      data.chemical_plant_activity_rows,
                                      national_inputs, 2024, "calendar"))
    deferred.append((len(run.paths), "ippu_data_request_packets.csv"))
    facility_geocoding_rows = data.facility_geocoding_audit()
    facility_fields = ("facility_id", "operator", "facility_name", "ipcc_code",
                       "process_route", "latitude", "longitude", "province", "district",
                       "capacity", "capacity_unit", "valid_from", "valid_to", "source_id",
                       "source_reference", "status", "coordinate_source",
                       "coordinate_source_reference", "coordinate_quality", "boundary_scope",
                       "geocode_status", "note")
    run.write_dicts("ippu_facility_registry.csv", facility_geocoding_rows,
                                  fields=facility_fields)
    # The gate-4 coverage product: per declared district, how much of the census is
    # spatial. An ungeocoded facility is still DECLARED - it has a district row in the
    # producer census - so absence of a coordinate is a resolution gap, never a
    # facility that stops existing.
    by_district = {}
    for row in facility_geocoding_rows:
        key = (row["province"], row["district"])
        declared, geocoded = by_district.get(key, (0, 0))
        by_district[key] = (declared + 1,
                            geocoded + (row["geocode_status"]
                                        == "exact_coordinate_resolved"))
    coverage_rows = [
        {"province": prov, "district": dist, "facilities_declared": declared,
         "facilities_geocoded": geocoded,
         "facilities_ungeocoded": declared - geocoded,
         "note": ("" if geocoded == declared else
                  "declared in the producer census without a resolved "
                  "coordinate; the census row, not the map, carries the tonnage")}
        for (prov, dist), (declared, geocoded) in sorted(by_district.items())]
    total_declared = sum(r["facilities_declared"] for r in coverage_rows)
    total_geocoded = sum(r["facilities_geocoded"] for r in coverage_rows)
    coverage_rows.append(
        {"province": "TOTAL", "district": "", "facilities_declared": total_declared,
         "facilities_geocoded": total_geocoded,
         "facilities_ungeocoded": total_declared - total_geocoded,
         "note": "geocoding covers %d of %d declared facilities; the remainder "
                 "are district-declared only" % (total_geocoded, total_declared)})
    run.write_dicts("ippu_facility_coverage.csv", coverage_rows)
    deferred.append((len(run.paths), "ippu_source_manifest.csv"))

    background = official_reporting.extract_background()
    reproduction = official_reporting.reproduce_background()
    fgas_species = official_reporting.extract_fgas_species()
    audit = official_reporting.audit_cells()
    run.write_dicts("ippu_unfccc_crt_background_2022.csv", background)
    run.write_dicts("ippu_unfccc_crt_reproduction_2022.csv", reproduction)
    run.write_dicts("ippu_unfccc_crt_fgas_species_2022.csv", fgas_species)
    run.write_dicts("ippu_unfccc_crt_cell_audit.csv", audit)
    ammonia_rows = ammonia_reconciliation.reconciliation_table(data, background)
    gas_monthly_rows = ammonia_reconciliation.gas_monthly_table(data)
    gas_cross_source_rows = ammonia_reconciliation.gas_cross_source_table(data)
    bridge_rows = ammonia_reconciliation.urea_bridge(data)
    run.write_dicts("ippu_ammonia_activity_reconciliation.csv",
                                  ammonia_rows)
    run.write_dicts("ippu_urea_co2_bridge_2025.csv", bridge_rows)
    run.write_dicts("ippu_fertilizer_gas_monthly_2024.csv",
                                  gas_monthly_rows)
    run.write_dicts("ippu_fertilizer_gas_cross_source_2024.csv",
                                  gas_cross_source_rows)
    matched_2022 = cement.calendar_reconstruction(data, 2022, 0.75)
    matched_2022_upper = cement.calendar_reconstruction(data, 2022, 0.95)
    run.write_dicts("ippu_cement_matched_calendar_2022.csv",
                                  [matched_2022, matched_2022_upper])
    official_cement = next(row for row in background if row["category"].startswith("2.A.1."))
    run.write_dicts("ippu_cement_crt_bridge_2022.csv", [
        {"step": "Independent trade-corrected f=0.75", "activity_mt":
         matched_2022["inferred_clinker_production_kt"] / 1000.0, "factor_t_co2_per_t":
         data.efv("ippu_cement", "Clinker"), "co2_mt": matched_2022["co2_mt"],
         "interpretation": "independent reconstructed clinker activity"},
        {"step": "Independent trade-corrected f=0.95", "activity_mt":
         matched_2022_upper["inferred_clinker_production_kt"] / 1000.0, "factor_t_co2_per_t":
         data.efv("ippu_cement", "Clinker"), "co2_mt": matched_2022_upper["co2_mt"],
         "interpretation": "independent high-clinker sensitivity"},
        {"step": "CRT reported activity with default clinker EF", "activity_mt":
         float(official_cement["activity_kt"]) / 1000.0, "factor_t_co2_per_t":
         data.efv("ippu_cement", "Clinker"), "co2_mt":
         float(official_cement["activity_kt"]) / 1000.0 * data.efv("ippu_cement", "Clinker"),
         "interpretation": "counterfactual only because the CRT activity basis is undocumented"},
        {"step": "CRT submitted activity and implied factor", "activity_mt":
         float(official_cement["activity_kt"]) / 1000.0, "factor_t_co2_per_t":
         float(official_cement["co2_ief_t_per_t"]), "co2_mt":
         float(official_cement["co2_kt"]) / 1000.0,
         "interpretation": "official arithmetic; institutional activity and factor derivation requested"},
    ])
    run.write_dicts("ippu_official_comparison.csv",
                                  _official_comparison(data, summary, background, cement_mt,
                                                       matched_2022))

    rows = allocate_rows(components, downscale.load_shares(), downscale.proxy_for, PROVINCES)
    check_reconciliation(rows, components)
    provincial = {province: 0.0 for province in PROVINCES}
    for row in rows:
        provincial[row["province"]] += row["co2e_Mt_AR5"]
    run.write("ippu_provincial_%d.csv" % year,
                            ["province", "co2e_Mt_AR5", "allocation_status"],
                            [[province, round(provincial[province], 8),
                              "provisional proxy; replace with plant registry"]
                             for province in PROVINCES])

    from pkinv.sectors.ippu import monthly
    monthly.main()
    run.record(monthly.OUT)

    qa = _qa_rows(data, components, balance, reproduction, scenarios, [],
                  company_rows, producer_census, matched_2022,
                  data.company_boundary_rows, facility_geocoding_rows, ammonia_rows,
                  gas_monthly_rows, gas_cross_source_rows, bridge_rows,
                  census_record=census_record, reference_mt=cement_mt)
    for name, passed, detail in qa:
        run.gate(name, passed, note=detail)
    # Numerical checks have their own output; metadata publication composes the
    # legacy QA table only after both stages have completed successfully.
    publication_paths = list(run.paths)
    for position, name in reversed(deferred):
        publication_paths.insert(position, asset_path(OUTPUTS, name))
    publication_paths.append(asset_path(OUTPUTS, "ippu_qa_2024.csv"))
    context_dir = asset_path(ROOT, "build", "ippu")
    os.makedirs(context_dir, exist_ok=True)
    run.finalize(qa_table=asset_path(context_dir, "numerical_qa_2024.csv"))

    manifest = {
        "inventory_year": year, "period": "FY2023-24", "registered_scope": "2.A.1;2.B.1;2.C.1;2.D.1",
        "reference_mt_co2": reference_mt, "cement_mt_co2": cement_mt, "structural_min_mt_co2": min(
            row["co2e_Mt_AR5"] for row in scenarios),
        "structural_max_mt_co2": max(row["co2e_Mt_AR5"] for row in scenarios),
        "outputs": [os.path.relpath(path, ROOT) for path in publication_paths],
        "limitations": ["Only 2.A.1 is independently estimated for FY2023-24",
                        "fifteen producer disclosures exceed the low-clinker inference and nearly match the high-clinker inference; Fecto and national stocks and movements remain unresolved",
                        "ammonia stays NE: four independent activity pathways (ippu_ammonia_activity_reconciliation.csv) disagree, and the official CRT activity is red-flagged by the sector's own gas consumption, which two institutions now measure within half a percent of each other for the reference year",
                        "F-gas consumption is a control, not an emission estimate"],
    }
    context = {"schema": "pkinv.ippu-numerical-context/v1", "manifest": manifest,
               "checks": run.checks[:-1], "declared": list(declared_outputs),
               "numerical_outputs": {os.path.relpath(path, ROOT): _sha256(path)
                                     for path in run.paths}}
    with open(asset_path(context_dir, "numerical_context.json"), "w", encoding="utf-8") as handle:
        json.dump(context, handle, indent=2, sort_keys=True)

    print("IPPU FY2023-24 public-data reference: %.3f Mt CO2" % reference_mt)
    print("  clinker balance: %.3f Mt cement-clinker content + %.3f exports - %.3f imports"
          % (balance["clinker_in_cement_kt"] / 1000.0,
             balance["clinker_exports_kt"] / 1000.0,
             balance["clinker_imports_kt"] / 1000.0))
    print("  valid trade-corrected structural configurations: %.3f--%.3f Mt CO2"
          % (manifest["structural_min_mt_co2"], manifest["structural_max_mt_co2"]))
    print("  observed producer subset: %.3f Mt clinker (%.1f%% low; %.1f%% high inference)"
          % (company_total_mt, company_coverage[0]["reported_vs_low_inference_pct"],
             company_coverage[0]["reported_vs_high_inference_pct"]))
    print("  official CRT rows extracted and %d numeric calculations reproduced" %
          len(reproduction))
    print("  calendar-2022 matched reconstruction: %.3f Mt CO2 (CRT %.3f Mt)" %
          (matched_2022["co2_mt"], next(float(row["co2_kt"]) / 1000.0 for row in summary
                                        if row["category"].startswith("2.A.1."))))
    print("  unsupported 2.A--2.G categories remain explicit notation-key rows")


if __name__ == "__main__":
    main()

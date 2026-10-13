"""The label-aware registry (rc42, the twentieth review's M-7): every table with text row
labels, joined BY LABEL. tables.py extends LABELLED_TABLES with NEW_LABELLED at import. Labels are engine-keyed: each is derived from the loop variable
or CSV row the values come from, through a small printed-name map where the manuscript
prints a display name (the KEYCAT_PRINTED pattern). A TUPLE label matches several text
cells positionally (needed for continuation rows whose first cell is blank and for tables
keyed on two columns); see labelled_tables_edits.md for the matcher/parser edits this
relies on.
"""
import os

from paper_numbers.tables import (  # noqa: F401 - the helpers the builders reuse
    AGRI_PRINTED, _agri_apbench_rows, _agri_apresults_rows, _agri_apstruct_rows,
    _agri_apunc_rows, _agri_benchmark_rows, _agri_by_year_2023, _agri_crt_rows,
    _agri_districttop_rows, _agri_fertmix_rows, _agri_keycat_rows, _agri_labelled,
    _agri_mc_rows, _agri_nledger_rows, _agri_s2live_rows, _agri_sensitivity_rows,
    _agri_spatialstreams_rows, _agri_stages_rows, _agri_unc_rows,
    _agriculture_provincial_rows, _air_kt, _aviation_bridge_rows,
    _aviation_estimate_rows, _aviation_two_year_rows, _bench, _bench_ratio_withheld,
    _category_gas_rows, _cell, _constrained_round, _data_rows, _ef, _first_where,
    _fugitives_segment_rows, _waste_sensitivity_rows,
    _keycat, _mc, _notation, _power_air_rows, _power_captive_rows,
    _power_fuel_rows, _power_heatrate_rows, _power_keycat_rows, _power_results_rows,
    _power_scenarios_rows, _power_sensitivity_rows, _residential_air_pair_rows,
    _residential_configs_rows, _residential_fuel_rows, _residential_hies_rows,
    _residential_hiesdiag_rows, _residential_sensitivity_rows,
    _residential_streams_rows, _rows, _spatial_row, _sum_prefix, _sum_where,
    _temporal_row, _transport_fuelbridge_rows, _transport_year, _waste_year, _wpar)


def _zip(labels, rows):
    """Pair a row builder's output with engine-derived labels, refusing a length drift."""
    labels, rows = list(labels), list(rows)
    assert len(labels) == len(rows), (len(labels), len(rows))
    return list(zip(labels, rows))


# ---- printed-name maps (engine key -> what the manuscript prints) ---------------------------
MODULE_PRINTED = {
    "agriculture": "Agriculture", "power": "Electricity generation",
    "transport": "Road transport", "residential": "Residential fuel",
    "industry": "Industrial combustion", "ippu": "Cement (IPPU)", "waste": "Waste",
    "fugitives": "Fugitive oil and gas", "railways": "Railways",
    "aviation": "Domestic aviation", "NATIONAL": "National",
}
RAIL_EF_PRINTED = {"rail_co2_diesel": "CO2", "rail_ch4_diesel": "CH4",
                   "rail_n2o_diesel": "N2O"}
RAIL_STREAM_PRINTED = {"Diesel CO2": ("Diesel (traction)", "CO2"),
                       "Diesel N2O": ("", "N2O"), "Diesel CH4": ("", "CH4"),
                       "Furnace oil CO2": ("Furnace oil (traction)", "CO2")}
RAIL_TOTAL_PRINTED = {
    "Railway non-traction energy (1A2/1A4c unresolved)": "Non-traction",
    "Railways": "1A3c locomotive traction",
    "Module total (both categories)": "Module total",
    "Diagnostic: N2O on the road factor": "Road table (3.2.2) substituted",
}
RAIL_OFFICIAL_PRINTED = {"inc1994": "INC (derived)", "bur1": "BUR-1",
                         "crt2022": "CRT (= BTR-1 annex)"}
# the manuscript prints the scenario ids with escaped underscores; one is truncated in print
RAIL_SCENARIO_PRINTED = {"stock_timing_prior_year_mean": "stock\\_timing\\_prior\\_year"}
TRANSPORT_CATEGORY_PRINTED = {"Road transport": "Road transport (1A3b)",
                              "Mixed off-road (1A4c/1A2)": "Mixed off-road (1A4c/1A2)",
                              "TOTAL": "Total"}
TRANSPORT_CLASS_PRINTED = {
    "2W Petrol CO2": "Two-wheeler petrol", "HDV Diesel CO2": "Heavy-duty diesel",
    "BUS Diesel CO2": "Bus diesel", "4W1 Petrol CO2": "Four-wheeler (small) petrol",
    "LDV Petrol CO2": "Light-duty petrol", "LDV Diesel CO2": "Light-duty diesel",
    "Off-road machinery diesel CO2": "Off-road machinery diesel",
    "3W Petrol CO2": "Three-wheeler petrol", "CNG CO2": "CNG (all classes)",
}
TRANSPORT_LEDGER_CLAIMANT_PRINTED = {"On-road transport": "On-road residual"}
TRANSPORT_BOUNDARY_PRINTED = {
    "reference": "Reference (OCAC Road rows",
    "national_hsd_minus_bulk": "National HSD minus observed bulk rows",
    "road_share_low": "Road-share envelope, low", "road_share_high": "Road-share envelope, high",
    "retail_nonroad_2p5pct": "Retail non-road at 2.5",
    "retail_nonroad_5pct": "Retail non-road at 5\\%",
    "retail_nonroad_10pct": "Retail non-road at 10\\%",
    "offroad_share_5pct": "Off-road partition at 5\\%",
    "offroad_share_15pct": "Off-road partition at 15\\%",
    "class_intensity_low": "Class intensities at band low",
    "class_intensity_high": "Class intensities at band high",
    "calendar_2022_controls": "Calendar-2022 controls",
    "legacy_pes_control": "Superseded PES control", "pes_corrected_12_9": "PES arithmetic corrected",
}
TRANSPORT_BRIDGE_PRINTED = {
    ("Petrol", "opening"): "OCAC Road row (MS+HOBC)", ("Petrol", "deduction"): "less household generators",
    ("Petrol", "closing"): "operative control", ("Diesel", "opening"): "OCAC Road row (HSD)",
    ("Diesel", "partition"): "less off-road partition", ("Diesel", "closing"): "operative on-road control",
    ("CNG", "opening"): "OGRA metered gas (gross)", ("CNG", "net"): "gross-to-net 0.90",
    ("CNG", "closing"): "operative control",
}
WASTE_STREAM_PRINTED = {
    "Open waste burning CO2 (fossil)": ("Open burning (4C2)", "CO2 (fossil)"),
    "Open waste burning CH4": ("", "CH4"), "Open waste burning N2O": ("", "N2O"),
    "Managed and unmanaged disposal sites CH4": ("Solid-waste disposal (4A)", "CH4"),
    "Domestic wastewater CH4": ("Domestic wastewater (4D1)", "CH4"),
    "Domestic wastewater N2O": ("", "N2O"),
}
WASTE_CATEGORY_PRINTED = {"Domestic wastewater": "Domestic wastewater",
                          "Solid waste disposal": "Solid-waste disposal",
                          "Open burning of waste": "Open burning", "waste": "Sector",
                          "SECTOR": "Sector"}
WASTE_PARAM_PRINTED = {
    "uncollected_urban": ("Uncollected fraction, urban", "4A, 4C2"),
    "uncollected_rural": ("Uncollected fraction, rural", "4A, 4C2"),
    "burned_fraction": ("Burned fraction of uncollected", "4C2"),
    "swds_docf": ("DOC_f", "4A"), "swds_mcf": ("MCF (site management)", "4A"),
    "swds_f": ("F (CH4 in landfill gas)", "4A"), "swds_oxidation": ("Oxidation factor", "4A"),
    "swds_recovery_t": ("Methane recovery", "4A"), "dry_matter": ("Dry matter", "4C2"),
    "oxidation_factor": ("Oxidation factor", "4C2"),
    "ww_mcf_sewer": ("MCF, sewered / septic", "4D1"),
    "ww_industrial_factor": ("Industrial-commercial correction", "4D1"),
}
WASTE_SCENARIO_PRINTED = {
    "reference": "Reference (sewer 0.5)", "sewer_all_stagnant": "All-stagnant mixture endpoint",
    "sewer_all_flowing": "All-flowing mixture endpoint",
    "sewer_flowing_river_low": "River MCF at its floor", "sewer_flowing_river_high": "River MCF at its ceiling",
    "sewer_equal_mix": "Equal stagnant/flowing mix", "bod_india": "BOD at India's rate",
    "no_spinup": "Disposal without spin-up", "hies_route_shares": "HIES household route shares",
    "unresolved_inert": "Unresolved fate: inert", "unresolved_shallow_dumps": "Unresolved fate: shallow dumps",
    "unresolved_deep_dumps": "Unresolved fate: deep dumps",
    "effluent_ef_low": "Effluent EF at its floor", "effluent_ef_high": "Effluent EF at its ceiling",
}
WASTE_SENSITIVITY_PRINTED = ("Sewer MCF 0.5 (reported)", "Sewer MCF 0.1 (river reading)",
                             "BOD at India's 34 g/cap/day", "Disposal with spin-up (reported)",
                             "Disposal without spin-up")
AIR_PRINTED = {"BC": "Black carbon", "OC": "Organic carbon", "PM": "PM (filterable)"}
AVIATION_COMPONENT_PRINTED = {"resident": "Resident carriers", "foreign": "Foreign carriers",
                              "combined": "Combined commercial"}
AVIATION_ESTIMATE_PRINTED = ("Aggregate movement (M0)", "Route-resolved (M1)",
                             "Calibrated fuel bridge", "Movement-share bridge",
                             "Literal customer labels", "Completed route--aircraft model (M2)",
                             "OECD domestic territory")
POWER_FUEL_PRINTED = {"Coal": "Coal", "Gas": "Gas", "Furnace Oil": "Furnace oil",
                      "Diesel Oil": "Diesel oil"}
POWER_CATEGORY_PRINTED = {"Electricity and heat production": "Electricity and heat production",
                          "Captive gas self-generation (1A2)": "Captive gas self-generation",
                          "TOTAL": "Total"}
POWER_SENSITIVITY_PRINTED = {
    "Sensitivity: all coal bituminous": "All coal bituminous",
    "Electricity and heat production": "Reported (79\\% lignite)",
    "Sensitivity: all coal lignite": "All coal lignite",
    "Sensitivity: coal at ledger mass x implied CV": "Coal at implied CVs",
    "Sensitivity: Table 3 published coal energy (legacy control)":
        "Table 3 published energy",
    "Sensitivity: captive gas at 900 Btu/scf": "Captive at 900 Btu/scf",
    "Captive gas self-generation (1A2)": "Reported (1000 Btu/scf)",
}
POWER_SCENARIO_PRINTED = {
    "reference": "Reference (family reference)", "coal_all_bituminous": "All coal bituminous",
    "coal_all_lignite": "All coal lignite", "coal_at_implied_cv": "Coal at implied CVs",
    "coal_at_table3_legacy": "Table 3 published energy",
    "toe_gross_basis": "TOE on a gross basis",
    "grid_plus_ke_ledger_fuel": "Grid + K-Electric ledger fuel",
    "captive_hhv_900": "Captive at 900 Btu/scf",
}
POWER_HEATRATE_PRINTED = {"Gas": "Gas (incl.", "Furnace Oil": "Furnace oil", "Coal": "Coal",
                          "Diesel Oil": "Diesel oil"}
RESIDENTIAL_CONFIG_PRINTED = {
    "dung_air_dry_Mt": "Dung cake, air-dry (Mt)", "energy_TJ": "Household energy (TJ)",
    "co2e_Mt_AR5": "Sector CO2e, AR5 (Mt)", "memo_biogenic_Gg": "Biogenic memo CO2 (Gg)",
    "pm25_kt": "Primary", "bc_kt": "Black carbon (kt)",
    "pm_ratio_vs_road_exhaust": "Ratio vs road exhaust", "national_share_pct": "National share",
}
RESIDENTIAL_SENSITIVITY_PRINTED = {
    "Sensitivity: firewood excluded": "Firewood excluded entirely",
    "Sensitivity: firewood low": "Firewood quantity -35",
    "Residential fuel combustion": "Reported",
    "Sensitivity: firewood high": "Firewood quantity +35",
}
RESIDENTIAL_STREAM_PRINTED = {
    "Natural gas CO2": ("Natural gas", "CO2"), "Natural gas CH4": ("", "CH4"),
    "LPG CO2": ("LPG", "CO2"), "Kerosene CO2": ("Kerosene", "CO2"), "Coal CO2": ("Coal", "CO2"),
    "Generators CO2": ("Generators", "CO2"), "Dung cake CH4": ("Dung cake", "CH4"),
    "Dung cake N2O": ("", "N2O"), "Firewood CH4": ("Firewood", "CH4"),
    "Firewood N2O": ("", "N2O"), "Crop residues CH4": ("Crop resid.", "CH4"),
    "Crop residues N2O": ("", "N2O"),
}
RESIDENTIAL_HIESDIAG_PRINTED = ("Reporting households (n)", "Weighted user households (M)",
                                "kg per user household per day", "Top 1", "Top 5")
RESIDENTIAL_HIES_PRINTED = ("Firewood (Mt)", "Dung cake (Mt)", "LPG (Mt)", "Kerosene (ML)")
AGRI_PROVINCE_PRINTED = {"NATIONAL (control)": "National"}
AGRI_BENCHMARK_TAIL = ("Agriculture subtotal (ex urea/lime)", "vs EDGAR 2023 (AR5)",
                       "vs EDGAR 2024 (AR5)", "vs Climate TRACE 2024 (AR6)")
AGRI_STAGE_PRINTED = {"housing + storage": "Housing + storage",
                      "field application": "Field application", "grazing": "Grazing",
                      "TOTAL": "Total"}
AGRI_APUNC_PRINTED = {"PM2.5": "PM_2.5", "SO2": "SO_2"}
AGRI_MMS_PRINTED = {"current (FAOSTAT-consistent)": "Current (FAOSTAT-consistent)",
                    "benchmark-like (high grazing)": "Benchmark-like (high grazing)",
                    "GLEAM 3.0 South Asia": "GLEAM 3.0 South Asia",
                    "evidence-weighted mean": "Midpoint diagnostic"}
AGRI_APBENCH_SCOPE_PRINTED = {"Managed soils - synthetic": "Synthetic fertiliser",
                              "Livestock (grazing+manure+management)": "Livestock (all streams)",
                              "Field burning of residues": "Residue burning",
                              "TOTAL": "National total"}
AGRI_APBENCH_SOURCE_PRINTED = {"SANH 2026 (ESSD)": "SANH 2026", "EDGAR v8": "EDGAR v8",
                               "HTAP v3": "HTAP v3"}
AGRI_SPATIALSTREAM_PRINTED = ("Synthetic fertiliser", "Livestock (all)", "Residue burning",
                              "All streams")
AGRI_CRT_PRINTED = ("Code / category", ("3.A Enteric ferment.", "CH4"),
                    ("3.B Manure mgmt.", "CH4"), ("3.B Manure mgmt.", "N2O"),
                    ("3.C Rice cultivation", "CH4"), ("3.D Managed soils", "N2O"),
                    ("3.F Field burning", "CH4,N2O"), ("3.H Urea application", "CO2"),
                    "Agriculture total")
AGRI_SPECIES_PRINTED = ("Dairy cattle", "Other cattle", "Buffalo", "Sheep", "Goats", "Camels",
                        "Poultry")
# the sensitivity table prints the scenario with the EF macro, which _label_text reduces to
# "=0.010 (...)"; keyed on the eval file's own scenario strings
DISTRICT_PRINTED = {"Sheikhpura": "Sheikhupura"}   # the boundary file's spelling vs the paper's
AGRI_SENSITIVITY_PRINTED = {
    "Main case (EF1=0.005 dry; rice continuously flooded)": "Main case",
    "Soil EF1 = 0.010 (2006 aggregate)": "=0.010 (2006 aggregate)",
    "Soil EF1 = 0.016 (2019 wet climate)": "=0.016 (2019 wet)",
    "Soil EF1 = 0.0055 (Cui 2021 empirical)": "=0.0055 (Cui 2021)",
    "Pasture EF3PRP wet climate (2019 Refinement)": "EF_3PRP wet (2019)",
    "Pasture EF3PRP = 2006 aggregate": "EF_3PRP aggregate (2006)",
    "Both 2006 direct factors (EF1 0.010 + EF3PRP aggregate)": "Both 2006 direct factors",
    "Rice intermittent SFw = 0.52 (AWD)": "Rice intermittent SF_w=0.52",
    "Rice rainfed SFw = 0.28": "Rice rainfed SF_w=0.28",
    "Manure MMS = GLEAM 3.0 South-Asia split": "Manure GLEAM 3.0 split",
}
AGRI_FERTMIX_PRINTED = ("Urea", "DAP", "CAN", "Other NP", "Ammonium sulphate", "NPK", "Total")
DUNG_VARIANT_PRINTED = {
    # rc67: the survey reading is the reference, so the base row is printed as such
    "S_household_only_unallocated": "Declared unresolved stock (the reference)",
    "S_residual_nonhousehold_combustion": "Non-household combustion, same fuel chain",
    "S_residual_return_to_manure": "Return to manure management",
    "S_residual_field_application": "Field application (soils N2O)",
    "S_revised_diversion_fraction": "Diversion fraction revised down",
}
CORRELATION_PRINTED = ("National mean (Mt CO2e)", "National median", "2.5th percentile",
                       "97.5th percentile", "National \\%", "Transport module \\%",
                       "Road transport \\%", "Power module \\%", "Residential \\%",
                       "Railways \\%", "Agriculture \\%")
BENCHMARK_PRINTED = {
    ("EDGAR", "Electricity and heat production", 2024): ("Electricity (1A1a)", "EDGAR"),
    ("EDGAR", "Residential fuel combustion", 2024): ("Residential (households)", "EDGAR"),
    ("EDGAR", "waste", 2023): ("Waste (year-matched)", "EDGAR"),
    ("FAOSTAT", "TOTAL", 2023): ("Agriculture total", "FAOSTAT"),
    ("EDGAR", "TOTAL", 2024): ("Agriculture total", "EDGAR"),
    ("Climate TRACE", "TOTAL", 2024): ("Agriculture total", "Climate TRACE"),
    ("FAOSTAT", "Managed soils", 2023): ("Managed soils", "FAOSTAT"),
    ("Climate TRACE", "Rice cultivation", 2024): ("Rice cultivation", "Climate TRACE"),
    ("EDGAR", "Fugitive emissions from oil and gas", 2024): ("Fugitives (1B2 vs all 1B)", "EDGAR"),
    ("EDGAR", "transport", 2024): ("Transport module vs EDGAR modes", "EDGAR"),
    ("EDGAR", "NATIONAL", 2024): ("All sectors", "EDGAR"),
    ("EDGAR", "1A2 (all estimated)", 2024): ("Industrial combustion (1A2)", "EDGAR"),
    ("EDGAR", "Cement production", 2024): ("IPPU: cement term vs all processes", "EDGAR"),
}


# ---- engine-keyed row builders that the ordinal registry lacks a label for ----------------
def _transport_ledger_labelled():
    keys = (("Diesel", "national", "National internal HSD sales"),
            ("Diesel", "national", "Domestic"), ("Diesel", "national", "Agriculture (bulk)"),
            ("Diesel", "national", "Industry"), ("Diesel", "national", "Railways"),
            ("Diesel", "national", "Domestic bunkers"), ("Diesel", "national", "Power"),
            ("Diesel", "national", "Government"), ("Diesel", "national", "Road (retail pump sales)"),
            ("Diesel", "road", "Off-road machinery"), ("Diesel", "road", "On-road transport"),
            ("Petrol", "national", "National internal MS+HOBC sales"),
            ("Petrol", "national", "Industry"), ("Petrol", "national", "Government"),
            ("Petrol", "national", "Road (retail pump sales)"),
            ("Petrol", "road", "Household generators"), ("Petrol", "road", "On-road transport"))
    name = "transport_fuel_ledger_%d.csv" % _transport_year()
    return [((f, t, TRANSPORT_LEDGER_CLAIMANT_PRINTED.get(c, c)),
             [_first_where(name, "kt", fuel=f, tier=t, claimant=c),
              _first_where(name, "share_of_opening", fuel=f, tier=t, claimant=c)])
            for f, t, c in keys]


def _waste_scenarios_labelled():
    out = []
    for name in WASTE_SCENARIO_PRINTED:
        row = next(r for r in _rows("waste_uncertainty_scenarios_%d.csv" % _waste_year())
                   if r["structural_scenario"] == name)
        out.append((WASTE_SCENARIO_PRINTED[name],
                    [float(row[c]) for c in ("deterministic", "P2.5", "P97.5") if row[c] != ""]))
    return out


def _aviation_bridge_labels():
    """The source-bridge row labels from the same (customer category, fuel) keys the
    builder reads, in its order: 'Domestic Avi-PIA' prints with an en-dash."""
    keys = (("Domestic Avi-PIA", "JP-1"), ("Domestic Avi-Others", "JP-1"),
            ("Overseas/Foreign Aviation", "JP-1"), ("Government Aviation", "JP-1"),
            ("Government Other", "JP-1"), ("Government Other", "JP-8"))
    return [cat.replace("-", "--") + ", " + fuel for cat, fuel in keys] + \
        ["All reported 100LL", "Total"]


def _fugitives_segments_labelled():
    rows = sorted(_rows("fugitives_segment_native_gases_2024.csv"),
                  key=lambda r: -float(r["co2e_Mt_AR5"]))
    return _zip([r["segment"] for r in rows] + ["Total"], _fugitives_segment_rows())


def _districttop_labelled():
    got = {}
    for r in _rows("district_totals_2024.csv"):
        key = (r["district"], r["province"])
        got[key] = got.get(key, 0.0) + float(r["co2e_Mt_AR5"])
    top = sorted(got.items(), key=lambda kv: kv[1], reverse=True)[:15]
    return [((DISTRICT_PRINTED.get(d, d), p), [float(i + 1), v])
            for i, ((d, p), v) in enumerate(top)]


def _agri_sensitivity_labelled():
    from pkinv.eval import sensitivity_table
    rows, _total = sensitivity_table.scenarios()
    return _zip([AGRI_SENSITIVITY_PRINTED[r["scenario"]] for r in rows],
                _agri_sensitivity_rows())


NEW_LABELLED = [
    # ---- railways ----
    ("railways", "03_study_area_and_data.tex", "tab:fuel",
     lambda: [(s, [_cell("railways_fuel_2024.csv", "stream", s, "TJ"),
                   _cell("railways_fuel_2024.csv", "stream", s, "share_pct")])
              for s in ("Diesel", "Furnace oil")]),
    ("railways", "04b_emission_factors.tex", "tab:factors",
     lambda: [(RAIL_EF_PRINTED[k], [_ef(k), ipcc, _ef(k) / ipcc])
              for k, ipcc in (("rail_co2_diesel", 74100.0), ("rail_ch4_diesel", 3.9),
                              ("rail_n2o_diesel", 3.9))]),
    ("railways", "06_results.tex", "tab:streams",
     lambda: [(RAIL_STREAM_PRINTED[s],
               [_cell("railways_by_stream_2024.csv", "subitem", s, c)
                for c in ("emissions_Gg", "co2e_Mt_AR5", "uncert_pct")])
              for s in ("Diesel CO2", "Diesel N2O", "Diesel CH4", "Furnace oil CO2")]
             + [(("Non-traction, all fuels", "all"),
                 [_cell("railways_totals_2024.csv", "category",
                        "Railway non-traction energy (1A2/1A4c unresolved)", "co2e_Mt_AR5")])]
             + [(RAIL_TOTAL_PRINTED[k], [_cell("railways_totals_2024.csv", "category", k,
                                               "co2e_Mt_AR5")])
                for k in ("Railways", "Railway non-traction energy (1A2/1A4c unresolved)",
                          "Module total (both categories)")]),
    ("railways", "06_results.tex", "tab:diagnostic",
     lambda: [("Rail table (3.4.1), reported",
               [_cell("railways_totals_2024.csv", "category",
                      "Module total (both categories)", "co2e_Mt_AR5")]),
              (RAIL_TOTAL_PRINTED["Diagnostic: N2O on the road factor"],
               [_cell("railways_totals_2024.csv", "category",
                      "Diagnostic: N2O on the road factor", "co2e_Mt_AR5")])]),
    # keyed on the fiscal year the row is: the file's end year, printed as "2015--16"
    ("railways", "08_limitations.tex", "tab:yearbook",
     lambda: [("%d--%02d" % (int(r["fiscal_year"]) - 1, int(r["fiscal_year"]) % 100),
               [float(r["summary_k_litres"]), float(r["locomotive"]),
                float(r["other_than_locomotive"]), float(r["detail_total"])])
              for r in sorted(_rows("railways_fuel_reconciliation_2024.csv"),
                              key=lambda r: int(r["fiscal_year"]))]),
    ("railways", "06_results.tex", "tab:air",
     lambda: [(pol, [_air_kt(pol),
                     _first_where("railways_air_pollutants_2024.csv", "uncert_pct",
                                  fuel="Diesel", pollutant=pol)])
              for pol in ("NOx", "CO", "NMVOC", "TSP", "PM10", "PM2.5", "BC", "SO2", "NH3")]),
    ("railways", "05_validation.tex", "tab:official",
     lambda: [(RAIL_OFFICIAL_PRINTED[b],
               [_first_where("railways_official_comparison_2024.csv", col, benchmark_id=b)
                for col in ("official_Mt_co2e", "own_Mt_co2e", "ratio_official_over_own")])
              for b in ("inc1994", "bur1", "crt2022")]),
    ("railways", "06b_uncertainty.tex", "tab:scenarios",
     lambda: [(RAIL_SCENARIO_PRINTED.get(s, s.replace("_", "\\_")),
               [_first_where("railways_uncertainty_scenarios_2024.csv", "deterministic",
                             structural_scenario=s)])
              for s in ("reference", "road_n2o_factor", "ie_summary",
                        "stock_timing_prior_year_mean", "tier2_service_split")]),
    # ---- transport ----
    ("transport", "03_study_area_and_data.tex", "tab:fuel",
     lambda: [(f, [_cell("transport_fuel_%d.csv" % _transport_year(), "fuel", f, "TJ"),
                   _cell("transport_fuel_%d.csv" % _transport_year(), "fuel", f, "share_pct")])
              for f in ("Petrol", "Diesel")]
             + [("Total", [sum(_cell("transport_fuel_%d.csv" % _transport_year(), "fuel", f, "TJ")
                               for f in ("Petrol", "Diesel")), 100.0])]),
    ("transport", "06_results.tex", "tab:results",
     lambda: [(TRANSPORT_CATEGORY_PRINTED[c],
               [_cell("transport_totals_%d.csv" % _transport_year(), "category", c, "co2e_Mt_AR5"),
                _cell("transport_totals_%d.csv" % _transport_year(), "category", c, "co2e_Mt_AR6"),
                _mc("within_sector", "transport" if c == "TOTAL" else c, "approach1_pct_95")])
              for c in ("Road transport", "Mixed off-road (1A4c/1A2)", "TOTAL")]),
    ("transport", "06_results.tex", "tab:fuels",
     lambda: [(fuel, [sum(float(r["co2e_Mt_AR5"])
                          for r in _rows("transport_by_stream_%d.csv" % _transport_year())
                          if r["category"] == "Road transport"
                          and " %s " % fuel in " %s " % r["subitem"])])
              for fuel in ("Petrol", "Diesel")]
             + [("CNG", [_sum_prefix("transport_by_stream_%d.csv" % _transport_year(),
                                     "co2e_Mt_AR5", "subitem", "CNG")])]),
    ("transport", "06_results.tex", "tab:cnghhv",
     lambda: [("CNG at 1000 Btu/scf (reported)",
               [_cell("transport_totals_%d.csv" % _transport_year(), "category", "TOTAL",
                      "co2e_Mt_AR5")]),
              ("CNG at 900 Btu/scf",
               [_cell("transport_totals_%d.csv" % _transport_year(), "category",
                      "Sensitivity: CNG at 900 Btu/scf", "co2e_Mt_AR5")])]),
    ("transport", "06_results.tex", "tab:classes",
     lambda: [(TRANSPORT_CLASS_PRINTED[s],
               [_sum_where("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5",
                           subitem=s)]) for s in TRANSPORT_CLASS_PRINTED]
             + [("Remaining classes",
                 [_sum_where("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5",
                             gas="CO2")
                  - sum(_sum_where("transport_by_stream_%d.csv" % _transport_year(),
                                   "co2e_Mt_AR5", subitem=s) for s in TRANSPORT_CLASS_PRINTED)])]),
    ("transport", "06_results.tex", "tab:keycat",
     lambda: [(c, [_keycat(c, "level_pct"), _keycat(c, "variance_share_pct_independent_approx")])
              for c in ("Road transport", "Mixed off-road (1A4c/1A2)")]),
    # the second column is the FROZEN superseded workbook diagnostic, printed for the
    # old-vs-new comparison and never recomputed (its engine is retired); the row set
    # follows the Tier 1 layer: BC exists, the wear-only coarse strata (PM10, TSP)
    # stay out of this table, and the BC row's second cell is the word "absent"
    ("transport", "06b_air_pollutants.tex", "tab:air",
     lambda: [("Black carbon" if pol == "BC" else pol,
               [_sum_where("transport_air_pollutants_%d.csv" % _transport_year(),
                           "emissions_kt", pollutant=pol)]
               + ([] if pol == "BC" else
                  [{"CO": 3588.2, "NMVOC": 679.8, "NOx": 112.7, "SO2": 29.9,
                    "PM2.5": 21.6, "NH3": 5.9}[pol]]))
              for pol in ("CO", "NMVOC", "NOx", "SO2", "PM2.5", "BC", "NH3")]),
    ("transport", "04_methods.tex", "tab:ledger", _transport_ledger_labelled),
    ("transport", "06_results.tex", "tab:boundary",
     lambda: [(TRANSPORT_BOUNDARY_PRINTED[name],
               [_first_where("transport_uncertainty_scenarios_%d.csv" % _transport_year(), col,
                             structural_scenario=name)
                for col in ("road_Mt", "offroad_Mt", "deterministic")])
              for name in ("reference", "national_hsd_minus_bulk", "road_share_low",
                           "road_share_high", "retail_nonroad_2p5pct", "retail_nonroad_5pct",
                           "retail_nonroad_10pct", "offroad_share_5pct", "offroad_share_15pct",
                           "class_intensity_low", "class_intensity_high",
                           "calendar_2022_controls")]),
    ("transport", "06_results.tex", "tab:provenance",
     lambda: [(TRANSPORT_BOUNDARY_PRINTED[name],
               [_first_where("transport_uncertainty_scenarios_%d.csv" % _transport_year(),
                             "deterministic", structural_scenario=name)])
              for name in ("legacy_pes_control", "pes_corrected_12_9")]),
    ("transport", "05_validation.tex", "tab:fuelgap",
     lambda: [(f, [_first_where("transport_fleet_fuel_diagnostic_%d.csv" % _transport_year(),
                                "control_TJ", fuel=f),
                   _first_where("transport_fleet_fuel_diagnostic_%d.csv" % _transport_year(),
                                "ratio_mid_over_control", fuel=f)])
              for f in ("Petrol", "Diesel", "CNG")]),
    ("transport", "S1_uncertainty.tex", "tab:mc",
     lambda: [("Sector mean", [_mc(s, "transport", "mean_Mt") for s in ("within_sector", "cross_sector")]),
              ("2.5th percentile", [_mc(s, "transport", "P2.5_Mt") for s in ("within_sector", "cross_sector")]),
              ("97.5th percentile", [_mc(s, "transport", "P97.5_Mt") for s in ("within_sector", "cross_sector")]),
              ("Sector \\%", [_mc(s, "transport") for s in ("within_sector", "cross_sector")]),
              ("Road transport \\%", [_mc(s, "Road transport") for s in ("within_sector", "cross_sector")]),
              ("Mixed off-road \\%", [_mc(s, "Mixed off-road (1A4c/1A2)") for s in ("within_sector", "cross_sector")])]),
    ("transport", "04_methods.tex", "tab:fuelbridge",
     lambda: _zip([(f, TRANSPORT_BRIDGE_PRINTED[(f, k)]) for f, k in
                   (("Petrol", "opening"), ("Petrol", "deduction"), ("Petrol", "closing"),
                    ("Diesel", "opening"), ("Diesel", "partition"), ("Diesel", "closing"),
                    ("CNG", "opening"), ("CNG", "net"), ("CNG", "closing"))],
                  _transport_fuelbridge_rows())),
    # ---- waste ----
    ("waste", "06_results.tex", "tab:results",
     lambda: [(WASTE_STREAM_PRINTED[s],
               [_cell("waste_by_stream_%d.csv" % _waste_year(), "subitem", s, c)
                for c in ("emissions_Gg", "co2e_Mt_AR5", "uncert_pct")])
              for s in WASTE_STREAM_PRINTED]
             + [("Total", [_cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL",
                                 "co2e_Mt_AR5"),
                           _mc("within_sector", "waste", "approach1_pct_95")])]),
    ("waste", "06_results.tex", "tab:sensitivity",
     lambda: _zip(WASTE_SENSITIVITY_PRINTED, _waste_sensitivity_rows())),
    ("waste", "06_results.tex", "tab:keycat",
     lambda: [(WASTE_CATEGORY_PRINTED[c],
               [_keycat(c, "level_pct"), _keycat(c, "variance_share_pct_independent_approx")])
              for c in ("Domestic wastewater", "Solid waste disposal", "Open burning of waste")]),
    ("waste", "04b_emission_factors.tex", "tab:params",
     lambda: [(WASTE_PARAM_PRINTED[p], [_wpar(p)]) for p in WASTE_PARAM_PRINTED]),
    ("waste", "06b_air_pollutants.tex", "tab:air",
     lambda: [(AIR_PRINTED.get(pol, pol),
               [_cell("waste_air_pollutants_%d.csv" % _waste_year(), "pollutant", pol,
                      "emissions_kt")])
              for pol in ("CO", "NMVOC", "PM2.5", "HCl", "NOx", "BC", "NH3", "SO2")]),
    ("waste", "S1_uncertainty.tex", "tab:mc",
     lambda: [(WASTE_CATEGORY_PRINTED[n],
               [_mc("within_sector", n, "mean_Mt"), _mc("within_sector", n, "P2.5_Mt"),
                _mc("within_sector", n, "P97.5_Mt"), _mc("within_sector", n)])
              for n in ("Domestic wastewater", "Solid waste disposal", "Open burning of waste",
                        "waste")]),
    ("waste", "S1_uncertainty.tex", "tab:wastescenarios", _waste_scenarios_labelled),
    ("waste", "S1_uncertainty.tex", "tab:rerunmc",
     lambda: [(WASTE_CATEGORY_PRINTED[s],
               [_first_where("waste_parameter_mc_%d.csv" % _waste_year(), col, scope=s)
                for col in ("deterministic", "mean", "P2.5", "P50", "P97.5")])
              for s in ("Domestic wastewater", "Solid waste disposal", "Open burning of waste",
                        "SECTOR")]),
    # ---- aviation ----
    ("aviation", "06_results.tex", "tab:two-year",
     lambda: _zip([AVIATION_COMPONENT_PRINTED[c] for c in ("resident", "foreign", "combined")],
                  _aviation_two_year_rows())),
    ("aviation", "06_results.tex", "tab:source-bridge",
     lambda: _zip(_aviation_bridge_labels(), _aviation_bridge_rows())),
    ("aviation", "06_results.tex", "tab:bridge-results",
     lambda: _zip(AVIATION_ESTIMATE_PRINTED, _aviation_estimate_rows())),
    # ---- fugitives ----
    ("fugitives", "06_results.tex", "tab:segments", _fugitives_segments_labelled),
    # ---- power ----
    ("power", "03_study_area_and_data.tex", "tab:fuel",
     lambda: _zip([POWER_FUEL_PRINTED[f] for f in ("Coal", "Gas", "Furnace Oil", "Diesel Oil")]
                  + ["Total"], _power_fuel_rows())),
    ("power", "06_results.tex", "tab:results",
     lambda: _zip([POWER_CATEGORY_PRINTED[c] for c in
                   ("Electricity and heat production", "Captive gas self-generation (1A2)", "TOTAL")],
                  _power_results_rows())),
    ("power", "06_results.tex", "tab:sensitivity",
     lambda: _zip([POWER_SENSITIVITY_PRINTED[k] for k in
                   ("Sensitivity: all coal bituminous", "Electricity and heat production",
                    "Sensitivity: all coal lignite", "Sensitivity: coal at ledger mass x implied CV",
                    "Sensitivity: Table 3 published coal energy (legacy control)",
                    "Sensitivity: captive gas at 900 Btu/scf", "Captive gas self-generation (1A2)")],
                  _power_sensitivity_rows())),
    ("power", "06_results.tex", "tab:scenarios",
     lambda: _zip([POWER_SCENARIO_PRINTED[s] for s in
                   ("reference", "coal_all_bituminous", "coal_all_lignite", "coal_at_implied_cv",
                    "coal_at_table3_legacy", "toe_gross_basis", "grid_plus_ke_ledger_fuel",
                    "captive_hhv_900")],
                  _power_scenarios_rows())),
    ("power", "06_results.tex", "tab:keycat",
     lambda: _zip(["Electricity and heat production", "Captive gas self-generation (1A2)"],
                  _power_keycat_rows())),
    ("power", "06b_air_pollutants.tex", "tab:air",
     lambda: _zip([AIR_PRINTED.get(p, p) for p in ("PM", "SO2", "NOx", "PM10", "PM2.5", "CO", "VOC")],
                  _power_air_rows())),
    ("power", "05_validation.tex", "tab:heatrate",
     lambda: _zip([POWER_HEATRATE_PRINTED[f] for f in ("Gas", "Furnace Oil", "Coal", "Diesel Oil")],
                  _power_heatrate_rows())),
    # ---- residential ----
    ("residential", "06_results.tex", "tab:configs",
     lambda: _zip([RESIDENTIAL_CONFIG_PRINTED[c] for c in
                   ("dung_air_dry_Mt", "energy_TJ", "co2e_Mt_AR5", "memo_biogenic_Gg", "pm25_kt",
                    "bc_kt", "pm_ratio_vs_road_exhaust", "national_share_pct")],
                  _residential_configs_rows())),
    ("residential", "06_results.tex", "tab:sensitivity",
     lambda: _zip([RESIDENTIAL_SENSITIVITY_PRINTED[k] for k in
                   ("Sensitivity: firewood excluded", "Sensitivity: firewood low",
                    "Residential fuel combustion", "Sensitivity: firewood high")],
                  _residential_sensitivity_rows())),
    ("residential", "03_study_area_and_data.tex", "tab:fuel",
     lambda: _zip(["Dung cake", "Firewood", "Natural gas", "Crop residues", "LPG", "Kerosene",
                   "Generators", "Coal", "Charcoal", "Total"], _residential_fuel_rows())),
    ("residential", "06_results.tex", "tab:results",
     lambda: _zip([RESIDENTIAL_STREAM_PRINTED[k] for k in RESIDENTIAL_STREAM_PRINTED] + ["Total"],
                  _residential_streams_rows())),
    ("residential", "06b_air_pollutants.tex", "tab:air",
     lambda: _zip([AIR_PRINTED.get(p, p) for p in
                   ("CO", "NMVOC", "PM2.5", "NOx", "OC", "NH3", "SO2", "BC")],
                  _residential_air_pair_rows())),
    ("residential", "03_study_area_and_data.tex", "tab:hiesdiag",
     lambda: _zip(RESIDENTIAL_HIESDIAG_PRINTED, _residential_hiesdiag_rows())),
    ("residential", "06_results.tex", "tab:hies",
     lambda: _zip(RESIDENTIAL_HIES_PRINTED, _residential_hies_rows())),
    # ---- agriculture ----
    ("agriculture", "06_results.tex", "tab:provincial",
     lambda: _zip([AGRI_PROVINCE_PRINTED.get(r["province"], r["province"])
                   for r in _rows("provincial_totals_2024.csv")],
                  _agriculture_provincial_rows())),
    ("agriculture", "06_results.tex", "tab:benchmark",
     lambda: _zip([AGRI_PRINTED.get(c, c) for c in
                   ("Enteric fermentation", "Manure management", "Rice cultivation",
                    "Managed soils", "Field burning of residues")] + list(AGRI_BENCHMARK_TAIL),
                  _agri_benchmark_rows())),
    ("agriculture", "06_results.tex", "tab:districttop", _districttop_labelled),
    ("agriculture", "06_results.tex", "tab:stages",
     lambda: _zip([AGRI_STAGE_PRINTED[r["stage"]] for r in _rows("n_ledger_stage_comparison.csv")],
                  _agri_stages_rows())),
    ("agriculture", "06b_air_pollutants.tex", "tab:apresults",
     lambda: _zip(["Managed soils", "Manure management", "Field burning", "Total"],
                  _agri_apresults_rows())),
    ("agriculture", "06b_air_pollutants.tex", "tab:apunc",
     lambda: _zip([AGRI_APUNC_PRINTED.get(k, k) for k in
                   ("NH3", "NOx", "CO", "PM2.5", "NMVOC", "BC", "SO2")], _agri_apunc_rows())),
    ("agriculture", "06b_air_pollutants.tex", "tab:apstruct",
     lambda: _zip([AGRI_MMS_PRINTED[r["configuration"]]
                   for r in _rows(os.path.join("eval", "mms_structural_uncertainty.csv"))],
                  _agri_apstruct_rows())),
    ("agriculture", "06b_air_pollutants.tex", "tab:apbench",
     lambda: _zip([(AGRI_APBENCH_SCOPE_PRINTED[sc], AGRI_APBENCH_SOURCE_PRINTED[src]) for src, sc in
                   (("SANH 2026 (ESSD)", "Managed soils - synthetic"),
                    ("SANH 2026 (ESSD)", "Livestock (grazing+manure+management)"),
                    ("SANH 2026 (ESSD)", "Field burning of residues"),
                    ("SANH 2026 (ESSD)", "TOTAL"), ("EDGAR v8", "TOTAL"), ("HTAP v3", "TOTAL"))],
                  _agri_apbench_rows())),
    ("agriculture", "06b_air_pollutants.tex", "tab:spatialstreams",
     lambda: _zip(AGRI_SPATIALSTREAM_PRINTED, _agri_spatialstreams_rows())),
    ("agriculture", "10_appendix.tex", "tab:crt",
     lambda: _zip(AGRI_CRT_PRINTED, _agri_crt_rows())),
    ("agriculture", "10_appendix.tex", "tab:unc",
     lambda: _agri_labelled(_agri_unc_rows,
                            ("Enteric fermentation", "Manure management", "Managed soils",
                             "Rice cultivation", "Field burning of residues",
                             "Urea application", "TOTAL"))),
    ("agriculture", "S2_provenance.tex", "tab:s2live",
     lambda: _zip(AGRI_SPECIES_PRINTED, _agri_s2live_rows())),
    ("agriculture", "04b_emission_factors.tex", "tab:sensitivity", _agri_sensitivity_labelled),
    ("agriculture", "04c_shared_ledger.tex", "tab:fertmix",
     lambda: _zip(AGRI_FERTMIX_PRINTED, _agri_fertmix_rows())),
    # ---- national ----
    ("national", "14_appendix.tex", "tab:temporal",
     lambda: [(MODULE_PRINTED[s], _temporal_row(s)) for s in
              ("agriculture", "power", "transport", "residential", "industry", "ippu", "waste",
               "fugitives", "railways", "aviation")]),
    ("national", "14_appendix.tex", "tab:spatial",
     lambda: [(MODULE_PRINTED[s], _spatial_row(s)) for s in
              ("agriculture", "power", "transport", "residential", "industry", "ippu", "waste",
               "fugitives", "railways", "aviation", "NATIONAL")]),
    # tab:categorygas retired (v1.0.0 Wave 4): a stored query, see test_paper_artefacts.py
    ("national", "07_uncertainty.tex", "tab:dungvariants",
     lambda: [(DUNG_VARIANT_PRINTED[r["variant_id"]],
               [float(r["delta_vs_S_Mt_co2e_AR5"]), float(r["national_total_Mt_co2e_AR5"])])
              for r in _rows("national_dung_variants.csv")]),
    ("national", "07_uncertainty.tex", "tab:correlation",
     lambda: _zip(CORRELATION_PRINTED,
                  [[_mc(s, "TOTAL", c) for s in ("within_sector", "cross_sector")]
                   for c in ("mean_Mt", "P50_Mt", "P2.5_Mt", "P97.5_Mt", "rel_uncert_pct_MC_95")]
                  + [[_mc(s, n) for s in ("within_sector", "cross_sector")]
                     for n in ("transport", "Road transport", "power", "residential", "railways",
                               "agriculture")])),
    # tab:completeness retired (v1.0.0 Wave 4): four stored queries, see test_paper_artefacts.py
    ("national", "10_benchmarks.tex", "tab:benchmarks",
     lambda: [(BENCHMARK_PRINTED[(src, cat, year)],
               [_bench(src, cat, "benchmark_Mt_co2e", year), _bench(src, cat, "engine_Mt_co2e", year)]
               + ([] if _bench_ratio_withheld(src, cat, year)
                  else [_bench(src, cat, "ratio_engine_over_benchmark", year)]))
              for src, cat, year in BENCHMARK_PRINTED]),
]


def _proxyattr_labelled():
    """tab:proxyattr: per province, the three proxy corrections and their net, from the
    eval lane's proxy_attribution.csv (a held product make eval regenerates)."""
    out = []
    for r in _rows(os.path.join("eval", "proxy_attribution.csv")):
        if r["province"] == "Other":
            continue                      # the table prints the four named provinces
        out.append((r["province"], [float(r["1 split indirect by stream"]),
                                    float(r["2 manure -> manure_applied"]),
                                    float(r["3 rice -> rice_area"]), float(r["net"])]))
    return out


NEW_LABELLED.append(("agriculture", "06_results.tex", "tab:proxyattr", _proxyattr_labelled))

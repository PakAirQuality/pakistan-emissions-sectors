"""Bridge OCAC customer-class fuel sales to IPCC aviation boundaries.

OCAC describes who bought the fuel; IPCC classifies each flight by origin and
destination.  Those are deliberately separate columns here.  No scenario is allowed to
discard an unassigned tonne: assigned streams plus ``residual`` close to the source row.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
from pkinv.core.components import enrich_co2e
from pkinv.core.uncertainty import product
from pkinv.sectors.aviation import lto

SCENARIOS = ("literal_customer", "movement_count", "flight_fuel_weighted")
ANCHOR_SCENARIOS = ("literal_customer", "airline_flight_count",
                    "modelled_fuel", "residual_constrained")
ACCOUNTS = ("ipcc_domestic", "international_bunker", "military_1a5b",
            "general_aviation", "export_other", "residual")
LOCAL_CUSTOMERS = ("Domestic Avi-PIA", "Domestic Avi-Others")


def airline_control_customer_shares(activity_dir, year=2023):
    """Domestic departure shares by OCAC resident customer group."""
    import csv
    import os
    path = asset_path(activity_dir, "airline_controls_2023_24.csv")
    rows = list(_activity_rows(path, comments=False))
    resident = {"PIA": "Domestic Avi-PIA", "ABQ": "Domestic Avi-Others",
                "FJL": "Domestic Avi-Others", "SEP": "Domestic Avi-Others",
                "SIF": "Domestic Avi-Others"}
    counts = {category: {"domestic": 0.0, "international": 0.0}
              for category in LOCAL_CUSTOMERS}
    for row in rows:
        category = resident.get(row["airline_icao"])
        if category and row["traffic_scope"] in ("domestic", "international"):
            counts[category][row["traffic_scope"]] += float(row["departures"])
    return {category: values["domestic"] / sum(values.values())
            for category, values in counts.items() if sum(values.values())}


def ledger_customer_coverage(data, activity_dir, stages):
    """Quantitative departure and aircraft/fuel coverage by OCAC customer group."""
    import csv
    import os
    resident = {"PIA": "Domestic Avi-PIA", "ABQ": "Domestic Avi-Others",
                "FJL": "Domestic Avi-Others", "SEP": "Domestic Avi-Others",
                "SIF": "Domestic Avi-Others"}
    controls = list(_activity_rows(asset_path(activity_dir, "airline_controls_2023_24.csv"), comments=False))
    official = {category: {b: 0.0 for b in ("domestic", "international")}
                for category in LOCAL_CUSTOMERS}
    for row in controls:
        category = resident.get(row["airline_icao"])
        if category and row["traffic_scope"] in official[category]:
            official[category][row["traffic_scope"]] += float(row["departures"])
    assigned = {category: {b: 0.0 for b in ("domestic", "international")}
                for category in LOCAL_CUSTOMERS}
    fuelled = {category: {b: 0.0 for b in ("domestic", "international")}
               for category in LOCAL_CUSTOMERS}
    for stage in stages:
        code = (stage.operator or stage.callsign[:3]).strip().upper()
        group = data.operator_by_icao.get(code)
        if not group or group["ocac_customer_category"] not in assigned:
            continue
        category = group["ocac_customer_category"]
        if stage.boundary not in assigned[category]:
            continue
        assigned[category][stage.boundary] += stage.activity_count
        if stage.aircraft_type and stage.total_fuel_kg > 0:
            fuelled[category][stage.boundary] += stage.activity_count
    output = {}
    for category in LOCAL_CUSTOMERS:
        output[category] = {}
        for boundary in ("domestic", "international"):
            denominator = official[category][boundary]
            output[category][boundary] = {
                "official_departures": denominator,
                "route_coverage": min(1.0, assigned[category][boundary] / denominator)
                                  if denominator else 0.0,
                "fuel_coverage": min(1.0, fuelled[category][boundary] / denominator)
                                 if denominator else 0.0,
            }
    return output


def build_anchor_scenario(data, activity_dir, stages=None, year=2023,
                          scenario="airline_flight_count"):
    """Anchor bridge with explicit insufficiency instead of forced model closure."""
    if scenario not in ANCHOR_SCENARIOS:
        raise ValueError("unknown anchor bridge scenario %r" % scenario)
    count_shares = airline_control_customer_shares(activity_dir, year)
    model_shares = ledger_customer_shares(data, stages or []) if stages else {}
    coverage = ledger_customer_coverage(data, activity_dir, stages or [])
    out = []
    for src in data.fuel_sales_for(year):
        assigned = {key: 0.0 for key in ACCOUNTS}
        category, fuel, tonnes = src["customer_category"], src["fuel_type"], src["tonnes"]
        method, status = "explicit_other_stream", "complete"
        if fuel == "JP-1" and category in LOCAL_CUSTOMERS:
            if scenario == "literal_customer":
                share = 1.0
            elif scenario == "airline_flight_count":
                share = count_shares[category]
            elif scenario in ("modelled_fuel", "residual_constrained"):
                share = model_shares.get(category)
            else:
                share = None
            if share is None:
                assigned["residual"] = tonnes
                method, status = "insufficient_model_scope", "unresolved"
            elif scenario in ("literal_customer", "airline_flight_count"):
                assigned["ipcc_domestic"] = tonnes * share
                assigned["international_bunker"] = tonnes * (1 - share)
                method = scenario
            else:
                dom_cov = coverage[category]["domestic"]["fuel_coverage"]
                int_cov = coverage[category]["international"]["fuel_coverage"]
                complete = dom_cov >= 0.9 and int_cov >= 0.9
                allocated_fraction = 1.0 if complete else min(dom_cov, int_cov)
                assigned["ipcc_domestic"] = tonnes * allocated_fraction * share
                assigned["international_bunker"] = tonnes * allocated_fraction * (1 - share)
                assigned["residual"] = tonnes * (1 - allocated_fraction)
                method = ("modelled_fuel_complete" if complete else
                          "modelled_fuel_partial_covered_activity")
                status = "complete" if complete else "partial"
        elif fuel == "JP-1" and category == "Overseas/Foreign Aviation":
            assigned["international_bunker"] = tonnes
            method = "foreign_customer_principal_candidate"
        elif fuel == "JP-8":
            assigned["military_1a5b"] = tonnes
            method = "jp8_military_candidate"
        elif fuel == "100LL":
            assigned["general_aviation"] = tonnes
            method = "100ll_general_aviation_candidate"
        elif fuel == "JP-1" and category == "Government Aviation":
            assigned["military_1a5b"] = tonnes
            method = "government_aviation_candidate"
        else:
            assigned["residual"] = tonnes
            method, status = "unresolved", "unresolved"
        row = {"fiscal_year": year, "scenario": scenario,
               "customer_category": category, "fuel_type": fuel,
               "reported_t": tonnes, "bridge_method": method,
               "coverage_status": status, "inventory_status": "provisional",
               "source": src["source"]}
        if category in coverage:
            row.update({
                "domestic_route_coverage": coverage[category]["domestic"]["route_coverage"],
                "domestic_fuel_coverage": coverage[category]["domestic"]["fuel_coverage"],
                "international_route_coverage": coverage[category]["international"]["route_coverage"],
                "international_fuel_coverage": coverage[category]["international"]["fuel_coverage"],
            })
        else:
            row.update({key: "" for key in ("domestic_route_coverage", "domestic_fuel_coverage",
                                             "international_route_coverage",
                                             "international_fuel_coverage")})
        row.update(assigned)
        if abs(sum(assigned.values()) - tonnes) > 1e-6:
            raise AssertionError("anchor bridge failed source-row closure")
        out.append(row)
    return out


def _oecd_value(data, year, component):
    rows = [r for r in data.benchmarks_for(year, "OECD") if r["component"] == component]
    if len(rows) != 1:
        raise ValueError("expected one OECD %s row for FY%d, got %d"
                         % (component, year, len(rows)))
    return rows[0]["co2_t"]


def resident_domestic_share(data, year=None):
    """Fuel-modelled share of resident-carrier departures that are domestic."""
    year = data.year if year is None else year
    domestic = _oecd_value(data, year, "resident_domestic_in")
    international = _oecd_value(data, year, "resident_international_from")
    return domestic / (domestic + international)


def ledger_customer_shares(data, stages):
    """Domestic fuel share by OCAC resident-airline customer class.

    Unlike :func:`resident_domestic_share`, this contains no OECD input.  Unknown and
    foreign operators are deliberately excluded instead of being silently assigned to
    ``Domestic Avi-Others``.
    """
    fuel = {category: {"domestic": 0.0, "international": 0.0}
            for category in LOCAL_CUSTOMERS}
    for stage in stages:
        code = (stage.operator or stage.callsign[:3]).strip().upper()
        group = data.operator_by_icao.get(code)
        if not group or group["residence"] != "Pakistan" or stage.boundary not in fuel[LOCAL_CUSTOMERS[0]]:
            continue
        category = group["ocac_customer_category"]
        if category in fuel:
            fuel[category][stage.boundary] += (stage.total_fuel_kg *
                                               stage.activity_count / 1000.0)
    shares = {}
    for category, values in fuel.items():
        total = values["domestic"] + values["international"]
        shares[category] = values["domestic"] / total if total else None
    return shares


def build_from_ledger(data, stages, year=None):
    """Source-row-conserving bridge whose resident split comes from this inventory."""
    year = data.year if year is None else year
    shares = ledger_customer_shares(data, stages)
    missing = [category for category, share in shares.items() if share is None]
    if missing:
        raise ValueError("flight ledger has no modelled resident-carrier fuel for %s"
                         % ", ".join(missing))
    out = []
    for src in data.fuel_sales_for(year):
        category, fuel, tonnes = src["customer_category"], src["fuel_type"], src["tonnes"]
        assigned = {key: 0.0 for key in ACCOUNTS}
        method = "explicit_other_stream"
        if fuel == "JP-1" and category in LOCAL_CUSTOMERS:
            share = shares[category]
            assigned["ipcc_domestic"] = tonnes * share
            assigned["international_bunker"] = tonnes * (1.0 - share)
            method = "flight_ledger_modelled_fuel_share"
        elif fuel == "JP-1" and category == "Overseas/Foreign Aviation":
            assigned["international_bunker"] = tonnes
            method = "foreign_customer_international"
        elif fuel == "JP-8":
            assigned["military_1a5b"] = tonnes
            method = "jp8_military_candidate"
        elif fuel == "100LL":
            assigned["general_aviation"] = tonnes
            method = "100ll_general_aviation_candidate"
        elif fuel == "JP-1" and category == "Government Aviation":
            assigned["military_1a5b"] = tonnes
            method = "government_aviation_candidate"
        else:
            assigned["residual"] = tonnes
            method = "unresolved"
        row = {"fiscal_year": year, "scenario": "flight_ledger", "customer_category": category,
               "fuel_type": fuel, "reported_t": tonnes, "bridge_method": method,
               "source": src["source"]}
        row.update(assigned)
        if abs(sum(assigned.values()) - tonnes) > 1e-6:
            raise AssertionError("ledger fuel bridge failed to close for %s" % category)
        out.append(row)
    return out


def ledger_reconciliation(data, stages, year=None):
    """Unconstrained bottom-up totals, OCAC controls and boundary-specific scalars."""
    year = data.year if year is None else year
    bridge = totals(build_from_ledger(data, stages, year), "JP-1")
    model = {name: sum(s.total_fuel_kg * s.activity_count for s in stages
                       if s.boundary == name) / 1000.0
             for name in ("domestic", "international")}
    rows = []
    for name, account in (("domestic", "ipcc_domestic"),
                          ("international", "international_bunker")):
        control = bridge[account]
        bottom_up = model[name]
        rows.append({"fiscal_year": year, "boundary": name,
                     "bottom_up_fuel_t": bottom_up, "ocac_control_fuel_t": control,
                     "reconciliation_factor": control / bottom_up if bottom_up else "",
                     "statistical_discrepancy_t": control - bottom_up,
                     "central_split_uses_oecd": False})
    return rows


def movement_domestic_share(data, year=None):
    year = data.year if year is None else year
    cycles = lto.lto_cycles(data, year)
    return cycles["domestic"] / (cycles["domestic"] + cycles["international"])


def _local_share(data, year, scenario):
    if scenario == "literal_customer":
        return 1.0
    if scenario == "movement_count":
        return movement_domestic_share(data, year)
    if scenario == "flight_fuel_weighted":
        return resident_domestic_share(data, year)
    raise ValueError("unknown aviation fuel-bridge scenario %r" % scenario)


def build(data, year=None, scenario="flight_fuel_weighted"):
    """Return source-row-conserving fuel assignments for one fiscal year."""
    year = data.year if year is None else year
    local_share = _local_share(data, year, scenario)
    out = []
    for src in data.fuel_sales_for(year):
        assigned = {key: 0.0 for key in ACCOUNTS}
        category, fuel, tonnes = src["customer_category"], src["fuel_type"], src["tonnes"]
        method = "explicit_other_stream"
        if fuel == "JP-1" and category in LOCAL_CUSTOMERS:
            assigned["ipcc_domestic"] = tonnes * local_share
            assigned["international_bunker"] = tonnes * (1.0 - local_share)
            method = scenario
        elif fuel == "JP-1" and category == "Overseas/Foreign Aviation":
            assigned["international_bunker"] = tonnes
            method = "foreign_customer_international"
        elif fuel == "JP-8":
            assigned["military_1a5b"] = tonnes
            method = "jp8_military_candidate"
        elif fuel == "100LL":
            assigned["general_aviation"] = tonnes
            method = "100ll_general_aviation_candidate"
        elif fuel == "JP-1" and category == "Government Aviation":
            assigned["military_1a5b"] = tonnes
            method = "government_aviation_candidate"
        else:
            assigned["residual"] = tonnes
            method = "unresolved"
        row = {"fiscal_year": year, "scenario": scenario,
               "customer_category": category, "fuel_type": fuel,
               "reported_t": tonnes, "bridge_method": method,
               "source": src["source"]}
        row.update(assigned)
        if abs(sum(assigned.values()) - tonnes) > 1e-6:
            raise AssertionError("fuel bridge failed to close for %s" % category)
        out.append(row)
    return out


def build_with_customer_shares(data, shares, year=None, scenario="customer_specific"):
    """Build a closed bridge using an explicit share for each resident customer row.

    This is the public hook used by carrier-specific structural scenarios.  It keeps
    the same treatment of foreign, government, JP-8 and 100LL rows as :func:`build`,
    while making the PIA/other-airline assumption visible rather than silently using
    one resident-carrier average for both.
    """
    year = data.year if year is None else year
    missing = set(LOCAL_CUSTOMERS) - set(shares)
    if missing:
        raise ValueError("missing customer shares for %s" % ", ".join(sorted(missing)))
    if any(not 0.0 <= float(shares[key]) <= 1.0 for key in LOCAL_CUSTOMERS):
        raise ValueError("customer domestic shares must be between zero and one")
    out = []
    for src in data.fuel_sales_for(year):
        assigned = {key: 0.0 for key in ACCOUNTS}
        category, fuel, tonnes = src["customer_category"], src["fuel_type"], src["tonnes"]
        method = "explicit_other_stream"
        if fuel == "JP-1" and category in LOCAL_CUSTOMERS:
            share = float(shares[category])
            assigned["ipcc_domestic"] = tonnes * share
            assigned["international_bunker"] = tonnes * (1.0 - share)
            method = scenario
        elif fuel == "JP-1" and category == "Overseas/Foreign Aviation":
            assigned["international_bunker"] = tonnes
            method = "foreign_customer_international"
        elif fuel == "JP-8":
            assigned["military_1a5b"] = tonnes
            method = "jp8_military_candidate"
        elif fuel == "100LL":
            assigned["general_aviation"] = tonnes
            method = "100ll_general_aviation_candidate"
        elif fuel == "JP-1" and category == "Government Aviation":
            assigned["military_1a5b"] = tonnes
            method = "government_aviation_candidate"
        else:
            assigned["residual"] = tonnes
            method = "unresolved"
        row = {"fiscal_year": year, "scenario": scenario,
               "customer_category": category, "fuel_type": fuel,
               "reported_t": tonnes, "bridge_method": method,
               "source": src["source"]}
        row.update(assigned)
        if abs(sum(assigned.values()) - tonnes) > 1e-6:
            raise AssertionError("customer-specific bridge failed for %s" % category)
        out.append(row)
    return out


def totals(rows, fuel_type=None):
    selected = [r for r in rows if fuel_type is None or r["fuel_type"] == fuel_type]
    result = {key: sum(r[key] for r in selected) for key in ACCOUNTS}
    result["reported_t"] = sum(r["reported_t"] for r in selected)
    return result


def commercial_jp1_total(data, year=None):
    year = data.year if year is None else year
    return sum(r["tonnes"] for r in data.fuel_sales_for(year)
               if r["fuel_type"] == "JP-1"
               and r["customer_category"] in LOCAL_CUSTOMERS + ("Overseas/Foreign Aviation",))


def reconciliation(data, year=None):
    """Comparison of current bottom-up, bridge scenarios and matched OECD controls."""
    year = data.year if year is None else year
    co2_per_t = data.p("co2_per_t_fuel")
    bottom_up = lto.fuel_tonnes(data, year)
    rows = []
    for scenario in SCENARIOS:
        bridge = totals(build(data, year, scenario), "JP-1")
        rows.append({
            "fiscal_year": year, "scenario": scenario,
            "domestic_fuel_t": bridge["ipcc_domestic"],
            "domestic_co2_Gg": bridge["ipcc_domestic"] * co2_per_t / 1000.0,
            "international_fuel_t": bridge["international_bunker"],
            "international_co2_Gg": bridge["international_bunker"] * co2_per_t / 1000.0,
            "residual_fuel_t": bridge["residual"],
            "bottom_up_domestic_fuel_t": bottom_up["domestic"],
            "bottom_up_domestic_co2_Gg": bottom_up["domestic"] * co2_per_t / 1000.0,
            "domestic_reconciliation_factor": (bridge["ipcc_domestic"] /
                                                 bottom_up["domestic"]),
        })
    return rows


def components(data, year=None, scenario="flight_fuel_weighted"):
    """Domestic GHG components driven by bridged JP-1 rather than movement fuel."""
    year = data.year if year is None else year
    fuel = totals(build(data, year, scenario), "JP-1")["ipcc_domestic"]
    co2, ch4, n2o = lto._gases(data, fuel)
    rows = [
        {"category": lto.CATEGORY, "subitem": "Fuel-constrained domestic aviation CO2",
         "gas": "CO2", "emissions_Gg": co2,
         "uncert_pct": data.pu("co2_per_t_fuel")},
        {"category": lto.CATEGORY, "subitem": "Fuel-constrained domestic aviation CH4",
         "gas": "CH4", "fossil": True, "emissions_Gg": ch4,
         "uncert_pct": product(data.pu("jet_kerosene_ncv"), data.pu("ch4_kg_per_tj"))},
        {"category": lto.CATEGORY, "subitem": "Fuel-constrained domestic aviation N2O",
         "gas": "N2O", "emissions_Gg": n2o,
         "uncert_pct": product(data.pu("jet_kerosene_ncv"), data.pu("n2o_kg_per_tj"))},
    ]
    return enrich_co2e(rows)


def benchmark_summary(data, year=None):
    year = data.year if year is None else year
    bridge = next(r for r in reconciliation(data, year)
                  if r["scenario"] == "flight_fuel_weighted")
    oecd_dom = _oecd_value(data, year, "domestic")
    oecd_int = _oecd_value(data, year, "international_bunker")
    commercial = commercial_jp1_total(data, year)
    fuel_co2 = commercial * data.p("co2_per_t_fuel")
    return {
        "fiscal_year": year,
        "movement_domestic_co2_t": bridge["bottom_up_domestic_co2_Gg"] * 1000.0,
        "fuel_bridge_domestic_co2_t": bridge["domestic_co2_Gg"] * 1000.0,
        "oecd_domestic_co2_t": oecd_dom,
        "fuel_bridge_international_co2_t": bridge["international_co2_Gg"] * 1000.0,
        "oecd_international_co2_t": oecd_int,
        "commercial_jp1_t": commercial,
        "commercial_jp1_co2_t": fuel_co2,
        "oecd_territory_total_co2_t": oecd_dom + oecd_int,
        "fuel_over_oecd_total": fuel_co2 / (oecd_dom + oecd_int),
        "oecd_is_calibration_input": True,
    }

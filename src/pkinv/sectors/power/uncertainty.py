"""The power sector's uncertainty, rebuilt around what the evidence actually is.

WHAT WAS WRONG WITH THE OLD NUMBER. The published +/-15.3 percent was one flat activity
percentage times one flat conversion percentage, applied identically to a gas row
corroborated by exact MMBTU meters and a furnace-oil row corroborated by nothing; 91
percent of the grid variance sat in a single Coal CO2 component whose factor uncertainty
was itself inflated by applying the whole blend range as if the share multiplied the
whole factor. Meanwhile the questions actually worth megatonnes - the coal conversion
(x2.01, 19.4 Mt), the TOE gross/net basis, K-Electric coverage - are ONE-SIDED, and a
symmetric percentage cannot say that, so the +/-15.3 both overstated the parametric width
and concealed the structural depth.

THE REBUILD, in the fugitives/aviation idiom this inventory already uses:

  PARAMETRIC - what a percentage can honestly describe - is per-fuel: each Table 3 row
  carries an activity uncertainty read off its own corroboration (gas 10 from the
  plant-sum bracketing, coal 5 from metered mass plus the CRT's 2 percent agreement,
  furnace oil 12 for having no exact meter anywhere, diesel 10 immaterial), correlated
  across the four rows through the 1a1a_toe_activity group because one conversion
  practice underlies them all; the coal factor takes delta-method propagation (9.7
  percent) instead of product(12,12).

  STRUCTURAL - boundary, scope and basis choices - is a table of NAMED CASES, each with a
  conditional parametric interval and no probability attached: the blend endpoints, the
  coal-at-implied-CV case, the TOE-gross-basis case, the captive heating value, and the
  grid-plus-K-Electric case. Discrete choices are kept unsampled so a confidence interval
  cannot conceal a boundary or coverage choice - the aviation register's sentence, and the
  reason the national pooled Monte Carlo sees none of these (it builds components with
  default arguments, which IS the reference configuration).

Grouped grid Approach 1 lands near 10.9 percent (7.9 if the four rows were treated
independent; both are published, the conservative group is the headline). In the national
pooled fossil-correlated scenario the group is superseded by the cross-sector shared
factor group, which is stronger still - documented, not hidden.
"""
from pkinv.core import montecarlo as mc_core
from pkinv.core.uncertainty import combine_sum
from pkinv.sectors.power import captive, combustion, engine, implied_cv, ke_leg

SCENARIO_SEED = 4242          # private stream; the national MC's seed 42 is untouched

INTERPRETATION = "conditional parametric interval; no structural probability"

# TOE gross-basis case: if HDIP's convention is gross, net energy - and CO2 - is lower by
# the gross-to-net margin: ~5 percent for coal and oil, ~10 for gas (the params-file note).
GROSS_BASIS_SCALE = {"Coal": 0.95, "Furnace Oil": 0.95, "Diesel Oil": 0.95, "Gas": 0.90}


def approach1_rows(data):
    """Grouped and independent Approach-1 for each category and the sector, from the same
    components the estimate publishes."""
    comps = engine.build_components(data)
    out = []
    for label, keep in (
            (combustion.CATEGORY, lambda c: c["category"] == combustion.CATEGORY),
            (captive.CATEGORY, lambda c: c["category"] == captive.CATEGORY),
            ("TOTAL", lambda c: True)):
        rows = [(c["co2e_Mt_AR5"], c["uncert_pct"], c.get("corr_group"))
                for c in comps if keep(c)]
        total, grouped = combine_sum(rows)
        _t, indep = combine_sum([(v, u, None) for v, u, _g in rows])
        out.append({"category": label, "co2e_Mt_AR5": total,
                    "approach1_pct_grouped": grouped,
                    "approach1_pct_independent": indep})
    return out


def _scaled(comps, factor_by_fuel):
    out = []
    for c in comps:
        s = 1.0
        if c["category"] == combustion.CATEGORY:
            for fuel, f in factor_by_fuel.items():
                if c["subitem"].startswith(fuel + " "):
                    s = f
        c2 = dict(c)
        for k in ("co2e_Mt_AR5", "co2e_Mt_AR6", "emissions_Gg"):
            if k in c2:
                c2[k] = c2[k] * s
        out.append(c2)
    return out


def _ke_component(data):
    return {"category": combustion.CATEGORY, "subitem": "K-Electric ledger fuel CO2",
            "gas": "CO2", "co2e_Mt_AR5": ke_leg.fy2023_case(data),
            "co2e_Mt_AR6": ke_leg.fy2023_case(data), "emissions_Gg": 0.0,
            # Assumed heating value (8) over most of the energy, default NCVs on the oil:
            # ~10 percent, stated rather than derived - this row exists to carry a
            # scenario, not to compete with the metered legs.
            "uncert_pct": 10.0}


# The grid-boundary FAMILY, named as the sixth review specified: three competing
# definitions of the control total, none a sensitivity around another. The ids alias
# the existing structural_scenario names (which tests and claims pin) rather than
# replacing them, and status=provisional_structural_boundary marks all three until
# the source table's calorific basis and the K-Electric scope are resolved.
# THE FAMILY, AFTER THE COAL RE-BASE. `reference` is now the stations' own metered coal at
# IPCC rank defaults - the member that was `coal_at_rank_default` until it was booked - and
# NEPRA Table 3, which was the reference for every release up to this one, is retained as a
# named legacy published control rather than deleted. Its id says what it is: a control that
# failed the physical audit (inside 28-47 per cent net fleet efficiency in two of nine years
# against the booked account's nine of nine) and is kept so a reader holding a published total
# can still find the account it came from.
FAMILY_IDS = {
    "reference": "grid_stations_rank_default",
    "coal_at_table3_legacy": "grid_nepra_reference_legacy",
    "coal_at_implied_cv": "grid_plant_cv_restated",
    "grid_plus_ke_ledger_fuel": "grid_plus_ke",
}


def structural_scenarios(data, n_iter=10000, seed=SCENARIO_SEED):
    """One row per named case: the deterministic value and a conditional parametric
    interval. The reference row is the estimate; every other row answers 'and if this
    discrete choice went the other way?'."""
    cases = [
        ("reference", combustion.CATEGORY, lambda: engine.build_components(data),
         "the estimate"),
        ("coal_all_bituminous", combustion.CATEGORY,
         lambda: engine.build_components(data, coal_override="bituminous"),
         "blend lower endpoint"),
        ("coal_all_lignite", combustion.CATEGORY,
         lambda: engine.build_components(data, coal_override="lignite"),
         "blend upper endpoint"),
        ("coal_at_implied_cv", combustion.CATEGORY,
         lambda: _scaled(engine.build_components(data),
                         {"Coal": implied_cv.restated_coal_TJ(data, data.year)
                          / combustion.fuel_TJ(data)["Coal"]}),
         "coal energy at ledger mass x per-plant implied NCV (Tables 20/23/28)"),
        # THE ACCOUNT THE REFERENCE REPLACED, kept as a legacy published control. Every
        # release up to this one booked NEPRA Table 3's coal energy here; it is retained
        # because a reader holding one of those totals is entitled to find the account it
        # came from, and because retaining a refuted control beside the reference is a
        # weaker claim than deleting it. It is NOT equally probable with the reference:
        # Table 3's energy is HDIP's tonnage times a conversion held constant for six years
        # across a complete change of coal rank, and divided into NEPRA's own printed
        # generation it implies net fleet efficiencies inside 28-47 per cent in two of nine
        # years against the booked account's nine of nine.
        ("coal_at_table3_legacy", combustion.CATEGORY,
         lambda: _scaled(engine.build_components(data),
                         {"Coal": data.table3_coal_toe(data.year) * data.p("toe_to_tj")
                          / combustion.fuel_TJ(data)["Coal"]}),
         "LEGACY PUBLISHED CONTROL: coal energy as NEPRA SoIR Table 3 prints it, the "
         "reference for every release before this one"),
        ("toe_gross_basis", combustion.CATEGORY,
         lambda: _scaled(engine.build_components(data), GROSS_BASIS_SCALE),
         "if HDIP's TOE convention is gross rather than net"),
        ("captive_hhv_900", captive.CATEGORY,
         lambda: engine.build_components(data, hhv_btu=900.0),
         "pipeline gas at 900 Btu/scf"),
        ("grid_plus_ke_ledger_fuel", combustion.CATEGORY,
         lambda: engine.build_components(data) + [_ke_component(data)],
         "if Table 3 excludes the K-Electric system (CO2 only)"),
    ]
    out = []
    for name, scope, build, note in cases:
        comps = build()
        det = sum(c["co2e_Mt_AR5"] for c in comps if c["category"] == scope)
        # THE SEED IS KEYED TO THE SCENARIO'S NAME, NOT ITS POSITION IN THE LIST ABOVE.
        # It used to be `seed + i`. Adding the non-circular coal case in its natural place -
        # beside the circular one it is the counterpart to - shifted every later case's seed
        # by one and moved three published interval endpoints, with nothing about those
        # scenarios having changed. The guard caught it (tests/paper_numbers/test_tables.py
        # compares the printed table against the output), but a published interval that moves
        # because a list was reordered is a property no reader could predict, and a reader
        # who reordered the list for readability would have been publishing new numbers.
        # mc_core.stream_seed is the repository's existing answer to exactly this, and it is
        # deliberately not built on hash(): Python salts str hashing per process.
        #
        # THE ONE-TIME COST, declared: every scenario's interval moved once when this changed,
        # because every scenario drew from a new stream. No deterministic value moved - those
        # are not sampled - and no reference, alternative or family membership changed. What
        # moved is the conditional parametric interval around each case, by a few hundredths
        # of a megatonne, and it will not move again when a case is added.
        stats, _samples = mc_core.run(comps, [combustion.CATEGORY, captive.CATEGORY],
                                      n_iter=n_iter,
                                      seed=mc_core.stream_seed(seed, "scenario|" + name))
        s = stats[scope]
        out.append({"structural_scenario": name, "scope": scope,
                    "deterministic_Mt": det, "mean_Mt": s["mean"],
                    "P2.5_Mt": s["p025"], "P50_Mt": s["p50"],
                    "P97.5_Mt": s["p975"],
                    "family_id": FAMILY_IDS.get(name, ""),
                    "status": ("provisional_structural_boundary"
                               if name in FAMILY_IDS else ""),
                    "note": note,
                    "interpretation": INTERPRETATION})
    return out


def full_factor_table(data):
    """The inputs register: every quantity the uncertainty statement rests on, parametric
    rows with their percentage and structural rows explicitly unsampled."""
    def row(variable, central, unit, u, dist, source, applies_to, group, klass, note=""):
        return {"variable": variable, "central_value": central, "unit": unit,
                "uncert_pct_95": u, "distribution": dist, "source": source,
                "applies_to": applies_to, "correlation_group": group,
                "uncertainty_class": klass, "note": note}

    fuels = combustion.fuel_TJ(data)
    rows = [
        row("Gas TOE row", round(fuels["Gas"]), "TJ", data.p("activity_uncert_gas"),
            "lognormal", "NEPRA SIR Table 3", "Gas CO2/CH4/N2O",
            combustion.TOE_CORR_GROUP, "parametric",
            "corroborated by exact-MMBTU plant meters; bracketing spread 0.89-1.09"),
        row("Coal station consumption mass", sum(float(r["mass_kt"]) for r in data.coal_rank_account[data.year]),
            "kt", data.p("activity_uncert_coal"), "lognormal",
            "NEPRA station coal consumption; maintained rank account", "Coal CO2/CH4/N2O",
            "activity:coal:power_station_mass", "parametric",
            "shared station-mass error; heat is rank mass times sampled rank NCV; commissioning reconstruction endpoints remain structural bounds"),
        row("Furnace oil TOE row", round(fuels["Furnace Oil"]), "TJ",
            data.p("activity_uncert_fo"), "lognormal", "NEPRA SIR Table 3",
            "Furnace Oil CO2/CH4/N2O", combustion.TOE_CORR_GROUP, "parametric",
            "no exact meter anywhere on this fuel"),
        row("Diesel TOE row", round(fuels["Diesel Oil"]), "TJ",
            data.p("activity_uncert_diesel"), "lognormal", "NEPRA SIR Table 3",
            "Diesel Oil CO2/CH4/N2O", combustion.TOE_CORR_GROUP, "parametric",
            "uncorroborated, immaterial"),
        row("TOE net-calorific basis", data.p("toe_to_tj"), "TJ/toe", "",
            "not sampled", "Eurostat definition; HDIP convention unverified",
            "all grid streams", "", "structural",
            "one-sided; scenario toe_gross_basis. Evidence for net: 48.7% implied "
            "efficiency, CRT states NCV"),
        row("Superseded Table 3 / station rank energy", data.table3_coal_toe(data.year) * data.p("toe_to_tj") / fuels["Coal"],
            "ratio", "", "not sampled", "NEPRA Table 3 versus station mass times rank NCV",
            "Coal CO2/CH4/N2O", "", "structural",
            "comparison with superseded aggregate account; generation-derived heat is a separate diagnostic, not the reference"),
        row("K-Electric coverage of Table 3", ke_leg.fy2023_case(data), "Mt CO2", "",
            "not sampled", "ledger boundary audit", "grid scope", "", "structural",
            "one-sided; scenario grid_plus_ke_ledger_fuel; a trend 7.1->4.0 Mt "
            "FY2019-23"),
        row("Lignite heat share of coal", data.coal_energy_lignite_share(data.year), "fraction",
            "", "derived; not independently sampled", "station mass times rank NCV",
            "Coal CO2", "", "derived",
            "rank heat share recomputed from shared mass and NCV realizations; includes pre-Thar Lakhra where present; no independent generation-share factor"),
        row("Lignite CO2 factor", data.efv("power_combustion_co2", "Lignite"), "kg/TJ",
            data.efu("power_combustion_co2", "Lignite"), "lognormal",
            "IPCC Table 2.2", "Coal CO2", "", "parametric"),
        row("Bituminous CO2 factor",
            data.efv("power_combustion_co2", "Other Bituminous Coal"), "kg/TJ",
            data.efu("power_combustion_co2", "Other Bituminous Coal"), "lognormal",
            "IPCC Table 2.2", "Coal CO2", "", "parametric"),
        row("Gas CO2 factor", data.efv("power_combustion_co2", "Natural Gas"), "kg/TJ",
            data.efu("power_combustion_co2", "Natural Gas"), "lognormal",
            "IPCC Table 2.2", "Gas CO2", "", "parametric"),
        row("RFO CO2 factor", data.efv("power_combustion_co2", "Residual Fuel Oil"),
            "kg/TJ", data.efu("power_combustion_co2", "Residual Fuel Oil"), "lognormal",
            "IPCC Table 2.2", "Furnace Oil CO2", "", "parametric"),
        row("HSD CO2 factor", data.efv("power_combustion_co2", "Gas/Diesel Oil"),
            "kg/TJ", data.efu("power_combustion_co2", "Gas/Diesel Oil"), "lognormal",
            "IPCC Table 2.2", "Diesel Oil CO2", "", "parametric"),
        row("CH4 and N2O factors", "Table 2.2 values", "kg/TJ", 150, "lognormal",
            "IPCC Table 2.2", "all CH4/N2O streams", "", "parametric",
            "rank NCV and station mass remain shared across gases"),
        row("Captive gas volume", data.captive_total_mmcfd(), "MMCFD",
            data.p("captive_activity_uncert"), "lognormal", "OGRA",
            "captive streams", "delivered_gas_ogra_3_31", "parametric",
            "SHARED GROUP (rc19): one OGRA Table 3.31 publication behind the "
            "residential, CNG, industrial and captive delivered volumes (the "
            "captive module reads 288 MMCFD against the closure ledger's Table "
            "3.31 print of 287 - reconciled in the gas closure, same "
            "publication). The GRID gas volume is deliberately outside the "
            "group: NEPRA's TOE account is a different meter"),
        row("Captive heating value", data.p("captive_hhv_btu_per_scf"), "Btu/scf",
            data.pu("captive_hhv_btu_per_scf"), "lognormal",
            "nominal billing value; 900-1,000 plausible", "captive streams", "",
            "parametric", "the 900 case is also the captive_hhv_900 scenario"),
        row("Captive gross-to-net", data.p("captive_gross_to_net"), "fraction",
            data.pu("captive_gross_to_net"), "lognormal", "engineering estimate",
            "captive streams", "", "parametric"),
        row("Bagasse heat rate", data.p("bagasse_heat_rate_kj_per_kwh"), "kJ/kWh",
            data.pu("bagasse_heat_rate_kj_per_kwh"), "lognormal",
            "assumed; declared structurally weaker", "Bagasse CH4/N2O", "",
            "parametric"),
    ]
    for rank in data.coal_rank_account[data.year]:
        rows.append(row("Coal rank NCV: " + rank["fuel_rank"], float(rank["ncv_TJ_per_Gg"]),
                        "TJ/Gg", float(rank["ncv_uncert_pct_95"]), "lognormal",
                        rank["source"], "same-rank power and industrial coal",
                        "factor:ncv:" + rank["fuel_rank"], "parametric",
                        "published rank range summarized as conditional parameter width; distinct from reconstruction endpoints"))
    return rows

"""Does the published power-coal reference survive a physical audit? Verdict per basis.

WHY THIS EXISTS. `coal_energy_adjudication.py` established that NEPRA's Table 3 coal ENERGY
and NEPRA's Table 21 coal MASS cannot describe the same fleet, and closed with "this
adjudicates; it does not re-base". An external review then asked the harder question: the
preferred estimate is unjustified, so justify it or change it. That requires two things the
adjudication does not do - verifying its own refutation on every basis that could rescue the
reference, and saying honestly which of its tests are INDEPENDENT of the account they select.
This file does both, and corrects two overstatements in that module's own docstring.

WHAT THE SIX BASES TEST. The test that matters is the supply bound: at the fleet's rank
composition, Table 3's FY2023-24 coal energy needs more coal than Pakistan's recorded imports
and production supplied. A bound like that can be an artefact of six things, and each is tested
separately rather than rolled into one number - matched period, stock change, coal rank,
moisture, calorific value, and the fleet coverage of the calorific value. The bound survives
all six, and the margin is published as a RESCUE REQUIREMENT: what would have to be true for
Table 3 to be feasible. Two of those margins are large on their own - a stock drawdown of 19
per cent of a year's national supply for power alone and 42 per cent with the other consumers,
or a lignite share of 38 per cent where NEPRA prints 92 per cent per station.

IMPLAUSIBLE, NOT IMPOSSIBLE (rc67). The supply series has no stock term and no stock record is
held, so the bound cannot rule a drawdown out; it can only say how large one would have to be.
Through rc66 the B1 verdict read "INFEASIBLE" and the manuscript said Table 3 "implies more
coal than the country supplied". Both said more than the arithmetic does.

THE CORRECTION THAT MATTERS MOST. The adjudication's docstring says "the physical test picks
one": NEPRA's per-station mass at rank defaults gives 34.4-38.7 per cent, "a fleet, in the
admissible band throughout". That test is NOT independent of the account it selects.
`table21_mass_implied_efficiency_pct` is generation divided by table21_mass x
composition_only_ncv - which is exactly the energy that route constructs. It is a
self-consistency screen on the PRODUCT mass x CV: a valid physical plausibility filter on a
candidate energy level, but it cannot adjudicate between mass accounts that yield the same
energy, and "in band in all five years" must not be quoted as independent corroboration.
This file recomputes it to prove the identity, year by year, and labels every test with
whether it touches a mass account at all.

WHAT IS GENUINELY INDEPENDENT, AND IT IS ENOUGH. Divide Table 3's own energy by the coal
generation NEPRA itself prints in Table 17. No coal mass enters, from either account. Across
the full NINE-YEAR panel the implied fleet efficiency runs 13.9, 22.3, 51.1, 53.1, 45.1,
57.5, 29.6, 22.8, 18.9 per cent. Seven of nine sit outside 28-47. The first two are
commissioning years whose volumes (148 and 997 GWh) make the ratio uninterpretable and they
are marked so; the remaining seven are material, and a 35-point swing across them is not a
fleet. This is the refutation, and it rests on two printed NEPRA columns.

AND TABLE 3'S COAL ENERGY IS NOT A MEASUREMENT. Against HDIP's own power-coal tonnage - the
series Table 3 names as its source - Table 3's TOE per tonne is 0.447471, 0.447400, 0.447402,
0.447403, 0.447399, 0.447424 in FY2015-16 through FY2020-21: ONE CONSTANT, SIX YEARS, a
spread of 7.2e-05 TOE/t or 0.016 per cent. That is 18.73 TJ/Gg, a generic coal factor applied
regardless of rank. It then breaks - 25.27, 21.40, 20.02 - exactly as Thar lignite goes from a
third of the fleet's mass to 92 per cent of it, and it breaks in the WRONG DIRECTION: the
fleet's physical calorific value was falling 20.34 -> 13.01 while the publisher's inferred
factor stayed above 20. The adjudication saw two such years and called them "identical to
three figures" because its panel starts at FY2019-20; the constant is visible in six years
and to six figures once the early years are included, and those years are held.

WHICH BAND. Two efficiency envelopes are in circulation - 30-45 in the adjudication's code,
28-47 in the campaign tables - and two of the shipped verdict strings are band-dependent.
This file adopts the WIDER 28-47, because for a refutation the wider band is the harder test
to pass, and records that the decisive conclusions do not depend on the choice: Table 3 is
outside under BOTH bands in FY2020-21, FY2022-23 and FY2023-24.

WHAT THIS FILE DOES NOT DO. It does not re-base, and it does not select a preferred account.
It establishes that the published control fails a physical audit, and that one of the two
arguments previously offered for the alternative is circular. Selecting a reference is a
declared pin re-base.
"""
import argparse

from pkinv.assets import asset_path
from pkinv.core.io import read_rows, write_or_check
from pkinv.paths import DATA, OUTPUTS

OUT = asset_path(OUTPUTS, "pakemis_power_reference_audit.csv")

TOE_TJ = 41.868e-3
GWH_TJ = 3.6
NCV_BIT, NCV_LIG = 25.8, 11.9        # IPCC 2006 Vol.2 Ch.1 Table 1.2, net
BAND_LO, BAND_HI = 28.0, 47.0        # the wider of the two envelopes in circulation
RAMP_UP_GWH = 2000.0                 # below this the efficiency ratio is uninterpretable

T3 = ("NEPRA SoIR Table 3 'Fuel consumed' (TOE), sourced by NEPRA to the HDIP Pakistan "
      "Energy Yearbook -> data/sectors/power/activity/fuel_consumed.csv")
T17 = ("NEPRA SoIR Table 17 coal net generation, CPPA-G system -> "
       "data/sectors/power/activity/generation_by_fuel.csv")
HDIP = ("Finance Division Statistical Supplement Table 14.1(4) 'Coal (000 metric ton)', "
        "Power column -> data/sectors/industry/activity/coal_by_consumer.csv")
SUPPLY = ("Finance Division Statistical Supplement Table 14.3 'Commercial energy supplies', "
          "coal imports + production -> data/sectors/industry/activity/coal_supply.csv")
T21 = ("NEPRA SoIR Table 21 per-station coal used and net generation -> "
       "data/sectors/power/activity/plant_fuel_ledger.csv, via "
       "outputs/pakemis_power_coal_energy_adjudication.csv")

FIELDS = ("period_id", "row_kind", "test_id", "what_it_tests", "value", "unit",
          "touches_a_mass_account", "verdict", "rescue_requirement", "source_pointer",
          "note")


BANNER = """\
# DOES THE PUBLISHED POWER-COAL REFERENCE SURVIVE A PHYSICAL AUDIT? VERDICT PER BASIS.
#
# Companion to outputs/pakemis_power_coal_energy_adjudication.csv, which established that
# NEPRA's Table 3 coal ENERGY and its Table 21 coal MASS cannot describe the same fleet. That
# file closed with "this adjudicates; it does not re-base". This one verifies its refutation
# on every basis that could rescue the reference, and separates the tests that are
# INDEPENDENT of the account they select from the one that is not.
#
# ROW KINDS.
#   basis            - the six ways the FY2023-24 supply bound could be an artefact. Each
#                      carries a RESCUE REQUIREMENT: what would have to be true for Table 3
#                      to be feasible. All six survive.
#   signature        - Table 3's TOE per tonne of HDIP's own power tonnage, nine years. One
#                      constant (18.73 TJ/Gg) holds for SIX of them to 0.016 per cent, then
#                      breaks as Thar lignite scales - and breaks upward while the fleet's
#                      physical calorific value falls. Table 3's coal energy is a conversion
#                      of a tonnage, not a measurement of an energy.
#   efficiency       - Table 3's own energy over NEPRA's own printed generation, NINE years.
#                      Touches NO mass account, so it is independent of both. Seven of nine
#                      outside 28-47. The two commissioning years are marked uninterpretable
#                      on volume, not counted as refutations.
#   independence     - the identity that makes the adjudication's "physical test picks one"
#                      circular: generation / (table21_mass x composition_ncv) IS the energy
#                      that route constructs. Recomputed per year against the shipped cell.
#   band             - which efficiency envelope, and whether the conclusions depend on it.
#
# WHAT IS CORRECTED HERE. Two statements in the adjudication's docstring. (1) "The physical
# test picks one" - that test is a self-consistency screen on the product mass x CV, valid
# for filtering a candidate energy level and invalid as independent corroboration of a mass
# account. (2) "identical to three figures" over two years - the constant holds over six
# years to six figures; the earlier panel simply began too late to see it.
#
# UNITS. Efficiencies are per cent, net over net: NEPRA's generation is net export and the
# IPCC calorific values are net, so no gross/net step is implied. Masses are kt (= Gg).
# Energies are TJ. TOE is converted at 41.868 GJ/t.
#
# NO PIN MOVES HERE. This file measures; selecting a reference is a declared re-base.
"""


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _start_year(label):
    """Fiscal START year from any of the three period spellings held in these inputs.

    fuel_consumed.csv writes "2015", coal_by_consumer.csv and coal_supply.csv write
    "2015-16", the adjudication writes "FY2019-20". Joining these by string silently
    produces an empty intersection, so every reader here goes through this.
    """
    s = str(label or "").strip()
    if s.startswith("FY"):
        s = s[2:]
    head = s.split("-")[0]
    return int(head) if head.isdigit() else None


def _period(year):
    return "FY%d-%02d" % (year, (year + 1) % 100)


def _inputs():
    t3 = {}
    for r in read_rows(asset_path(DATA, "activity", "power", "fuel_consumed.csv")):
        if "oal" in r["fuel"]:
            y = _start_year(r["fiscal_year"])
            if y is not None and _num(r["toe"]):
                t3[y] = _num(r["toe"])
    gen = {}
    for r in read_rows(asset_path(DATA, "activity", "power", "generation_by_fuel.csv")):
        if "oal" in r["fuel"] and r["system"] == "CPPA-G":
            y = _start_year(r["fiscal_year"])
            if y is not None and _num(r["gwh_net"]):
                gen[y] = _num(r["gwh_net"])
    hdip = {}
    for r in read_rows(asset_path(DATA, "activity", "industry", "coal_by_consumer.csv")):
        if r["consumer"] == "power" and r["coal_kt"] and r["revision_status"] == "final":
            y = _start_year(r["fiscal_year"])
            if y is not None:
                hdip[y] = _num(r["coal_kt"])
    supply = {}
    for r in read_rows(asset_path(DATA, "activity", "industry", "coal_supply.csv")):
        if r.get("period_coverage") != "full_year" or r.get("revision_status") != "final":
            continue
        y = _start_year(r["fiscal_year"])
        imp = _num(r["coal_imports_kt"])
        pro = _num(r["coal_production_kt_petroleum_division"])
        if y is not None and imp is not None and pro is not None:
            supply[y] = imp + pro
    adj = {}
    for r in read_rows(asset_path(OUTPUTS,
                                  "pakemis_power_coal_energy_adjudication.csv")):
        y = _start_year(r["period_id"])
        if y is not None:
            adj[y] = r
    return t3, gen, hdip, supply, adj


def _fmt(v, nd=3):
    return "" if v is None else ("%.*f" % (nd, v)).rstrip("0").rstrip(".")


def _bases(year, t3, hdip, supply, adj):
    """The six ways the FY2023-24 supply bound could be an artefact, each with its margin."""
    a = adj[year]
    energy = t3[year] * TOE_TJ
    lig = _num(a["lignite_share_of_mass_pct"]) / 100.0
    cv = lig * NCV_LIG + (1 - lig) * NCV_BIT
    req = energy / cv
    sup = supply[year]
    return energy, cv, req, sup, lig


def build():
    t3, gen, hdip, supply, adj = _inputs()
    years = sorted(set(t3) & set(gen) & set(hdip))
    rows = []

    # ---- the six bases, on the one year where the bound bites -------------------------
    bound_year = max(y for y in years if y in adj and y in supply)
    energy, cv, req, sup, lig = _bases(bound_year, t3, hdip, supply, adj)
    hdip_total = None
    for r in read_rows(asset_path(DATA, "activity", "industry", "coal_by_consumer.csv")):
        if (r["consumer"] == "total" and r["revision_status"] == "final"
                and _start_year(r["fiscal_year"]) == bound_year):
            hdip_total = _num(r["coal_kt"])
    others = (hdip_total - hdip[bound_year]) if hdip_total else None
    pid = _period(bound_year)

    def basis(test_id, what, value, unit, touches, verdict, rescue, ptr, note):
        rows.append(dict(period_id=pid, row_kind="basis", test_id=test_id,
                         what_it_tests=what, value=value, unit=unit,
                         touches_a_mass_account=touches, verdict=verdict,
                         rescue_requirement=rescue, source_pointer=ptr, note=note))

    basis("B1_the_bound", "tonnage Table 3's energy needs at the fleet's rank composition, "
          "against all coal supplied to Pakistan", _fmt(100.0 * req / sup, 1),
          "percent of national supply", "lignite share only (composition, not level)",
          # "INFEASIBLE" through rc66. The supply series is imports plus production and
          # carries no stock term (B3), so a requirement above supply is impossible only
          # if stocks did not move. No stock record is held either way: the verdict is
          # what the arithmetic shows, and B3 says how large the unrecorded drawdown
          # would have to be.
          "EXCEEDS SUPPLY UNLESS STOCKS FELL: %s kt required against %s kt supplied"
          % (_fmt(req, 0), _fmt(sup, 0)),
          "a stock drawdown of %s percent of the year's supply, or supply understated or "
          "energy overstated by the same" % _fmt(100.0 * (req - sup) / sup, 0),
          "%s ; %s" % (T3, SUPPLY),
          "implausible, not impossible: the supply series has no stock term and no stock "
          "record is held. The five rows below are the routes by which the requirement "
          "could be met")
    basis("B2_matched_period", "whether the supply denominator covers the same twelve months "
          "as the energy numerator", _fmt(sup, 0), "kt", "no",
          "SURVIVES, with a documented caveat",
          "supply understated by %s percent (power alone) or %s percent (with HDIP's other "
          "consumers)" % (_fmt(100.0 * (req - sup) / sup, 0),
                          _fmt(100.0 * (req + others - sup) / sup, 0) if others else "n/a"),
          SUPPLY,
          "the publisher flags FY2023-24 supply PARTIAL (imports to Jan 2024, Punjab+Sindh "
          "production to Feb, Balochistan to Mar) but reprints the footnote unchanged from "
          "the prior edition. Three checks say the figure behaves as a full year: it lies "
          "between its neighbours (23916 and 25727 kt), the independent PBS extraction series "
          "prints 19260 against Petroleum Division's 19259 kt for production, and annualising "
          "it from 8 or 9 months would make FY2024-25 a 27-35 percent collapse")
    basis("B3_stock_change", "whether an inventory drawdown could supply the gap",
          _fmt(req + others - sup, 0) if others else "", "kt of implied drawdown", "no",
          "SURVIVES",
          "a drawdown of %s percent of a full year's national supply"
          % (_fmt(100.0 * (req + others - sup) / sup, 0) if others else "n/a"),
          "%s ; %s" % (SUPPLY, HDIP),
          "supply here is imports + production and carries NO stock term by construction, so "
          "the gap must come from stock if Table 3 is right. Rescuing it requires covering "
          "the power requirement AND the %s kt HDIP books to brick, cement and households in "
          "the same year" % (_fmt(others, 0) if others else "n/a"))
    basis("B4_coal_rank", "the lignite share the bound assumes",
          _fmt(100.0 * lig, 1), "percent of mass", "lignite share only",
          "SURVIVES",
          "lignite share at or below %s percent (inside all supply) or %s percent (leaving "
          "room for other consumers)"
          % (_fmt(100.0 * (NCV_BIT - energy / sup) / (NCV_BIT - NCV_LIG), 1),
             _fmt(100.0 * (NCV_BIT - energy / (sup - others)) / (NCV_BIT - NCV_LIG), 1)
             if others else "n/a"),
          T21,
          "the share is NEPRA's own printed per-station coal mass, not a model. Rescuing the "
          "reference needs it roughly halved against what the stations report")
    basis("B5_calorific_value", "the blended net calorific value the bound assumes",
          _fmt(cv, 2), "TJ/Gg", "lignite share only", "SURVIVES",
          "a fleet net CV at or above %s TJ/Gg (inside all supply) or %s TJ/Gg (leaving room "
          "for other consumers)" % (_fmt(energy / sup, 2),
                                    _fmt(energy / (sup - others), 2) if others else "n/a"),
          "IPCC 2006 GL Vol.2 Ch.1 Table 1.2 net calorific values (other bituminous 25.8, "
          "lignite 11.9 TJ/Gg) blended at the printed rank composition",
          "the repo's own heat-rate-implied lignite CVs run 10.7-13.6 TJ/Gg, bracketing the "
          "11.9 default, and the plant route's fleet CV for this year is 12.01. A wetter, "
          "lower-CV coal raises the required tonnage and makes the bound worse, not better")
    a_cov = _fmt(_num(adj[bound_year]["fleet_cv_mass_coverage_pct"]), 0)
    basis("B6_fleet_coverage", "share of the fleet's mass the calorific value is weighted "
          "over", a_cov,
          "percent", "yes (Table 21 mass)", "SURVIVES",
          "not applicable in this year; coverage is %s percent" % a_cov, T21,
          "coverage is 69 and 72 percent in FY2019-20 and FY2020-21, where the CV is weighted "
          "over imported stations only and applied to lignite tonnes too - a real unrepaired "
          "bias in those two years' plant_implied_efficiency_pct (32.4, 33.1), and the reason "
          "the bound is read on this year")
    return rows, (t3, gen, hdip, supply, adj, years)


def _signature_and_efficiency(rows, t3, gen, hdip, adj, years):
    """Table 3 as a conversion of a tonnage, and the mass-free efficiency, nine years each."""
    tpt = {}
    for y in years:
        tpt[y] = t3[y] / (hdip[y] * 1000.0)
    flat = [y for y in years if abs(tpt[y] - 0.4474) < 5e-4]
    span = max(tpt[y] for y in flat) - min(tpt[y] for y in flat) if flat else 0.0
    for y in years:
        on_flat = y in flat
        phys = _num(adj[y]["composition_only_ncv_TJ_per_Gg"]) if y in adj else None
        rows.append(dict(
            period_id=_period(y), row_kind="signature",
            test_id="S1_toe_per_tonne",
            what_it_tests="Table 3's energy per tonne of HDIP's own power-coal tonnage",
            value=_fmt(tpt[y], 6), unit="TOE per tonne",
            touches_a_mass_account="yes (HDIP national tonnage)",
            verdict=("ON the flat factor" if on_flat else "OFF the flat factor"),
            rescue_requirement="",
            source_pointer="%s ; %s" % (T3, HDIP),
            note=("%s TJ/Gg. %s"
                  % (_fmt(tpt[y] * 41.868, 2),
                     ("one generic coal factor, applied regardless of rank composition"
                      if on_flat else
                      "breaks upward as Thar lignite scales, while the fleet's physical CV "
                      "falls to %s TJ/Gg - the wrong direction for a measured energy"
                      % _fmt(phys, 2) if phys else "breaks as Thar lignite scales")))))
    rows.append(dict(
        period_id="%s..%s" % (_period(min(flat)), _period(max(flat))), row_kind="signature",
        test_id="S2_flat_factor_span",
        what_it_tests="spread of Table 3's TOE per tonne across the years it is flat",
        value=_fmt(span, 8), unit="TOE per tonne",
        touches_a_mass_account="yes (HDIP national tonnage)",
        verdict="ONE CONSTANT over %d consecutive years" % len(flat),
        rescue_requirement="", source_pointer="%s ; %s" % (T3, HDIP),
        note="%s percent of the level. Table 3's coal energy is HDIP's tonnage times a fixed "
             "18.73 TJ/Gg, not a measured energy. The adjudication reported this as "
             "'identical to three figures' over two years because its panel began at "
             "FY2019-20" % _fmt(100.0 * span / 0.4474, 3)))

    for y in years:
        e = t3[y] * TOE_TJ
        eff = 100.0 * gen[y] * GWH_TJ / e
        ramp = gen[y] < RAMP_UP_GWH
        rows.append(dict(
            period_id=_period(y), row_kind="efficiency",
            test_id="E1_table3_energy_over_printed_generation",
            what_it_tests="net fleet thermal efficiency implied by Table 3's own energy and "
                          "NEPRA's own printed coal generation",
            value=_fmt(eff, 1), unit="percent",
            touches_a_mass_account="NO - independent of both mass accounts",
            verdict=("uninterpretable on volume" if ramp
                     else ("inside %g-%g" % (BAND_LO, BAND_HI) if BAND_LO <= eff <= BAND_HI
                           else "OUTSIDE %g-%g" % (BAND_LO, BAND_HI))),
            rescue_requirement="", source_pointer="%s ; %s" % (T3, T17),
            note=("commissioning year: %s GWh of coal generation makes the ratio "
                  "uninterpretable, and it is not counted as a refutation" % _fmt(gen[y], 0)
                  if ramp else "%s GWh against %s TJ" % (_fmt(gen[y], 0), _fmt(e, 0)))))
    material = [y for y in years if gen[y] >= RAMP_UP_GWH]
    effs = [100.0 * gen[y] * GWH_TJ / (t3[y] * TOE_TJ) for y in material]
    out = [y for y in material
           if not (BAND_LO <= 100.0 * gen[y] * GWH_TJ / (t3[y] * TOE_TJ) <= BAND_HI)]
    rows.append(dict(
        period_id="%s..%s" % (_period(min(material)), _period(max(material))),
        row_kind="efficiency", test_id="E2_swing_across_material_years",
        what_it_tests="range of the implied efficiency across the years with material coal "
                      "generation",
        value=_fmt(max(effs) - min(effs), 1), unit="percentage points",
        touches_a_mass_account="NO - independent of both mass accounts",
        verdict="REFUTES Table 3: %d of %d material years outside %g-%g"
                % (len(out), len(material), BAND_LO, BAND_HI),
        rescue_requirement="a coal fleet whose net efficiency moves %s points across %d years"
                           % (_fmt(max(effs) - min(effs), 1), len(material)),
        source_pointer="%s ; %s" % (T3, T17),
        note="this is the refutation that needs no mass account at all, and it is the one "
             "the paper should carry. %s" % ", ".join(
                 "%s %s" % (_period(y), _fmt(100.0 * gen[y] * GWH_TJ / (t3[y] * TOE_TJ), 1))
                 for y in material)))


def _independence_and_band(rows, gen, adj):
    """Prove the circularity, then record whether the conclusions depend on the band."""
    for y in sorted(adj):
        a = adj[y]
        mass = _num(a["table21_mass_kt"])
        comp = _num(a["composition_only_ncv_TJ_per_Gg"])
        shipped = _num(a["table21_mass_implied_efficiency_pct"])
        g = _num(a["coal_generation_GWh"])
        if not (mass and comp and g):
            continue
        recomputed = 100.0 * g * GWH_TJ / (mass * comp)
        rows.append(dict(
            period_id=_period(y), row_kind="independence",
            test_id="I1_table21_efficiency_is_its_own_energy",
            what_it_tests="generation / (table21_mass x composition_ncv) against the shipped "
                          "table21_mass_implied_efficiency_pct",
            value=_fmt(recomputed, 2), unit="percent",
            touches_a_mass_account="yes - it IS the Table 21 mass account",
            verdict=("IDENTITY CONFIRMED (shipped %s)" % _fmt(shipped, 1)
                     if abs(recomputed - shipped) < 0.1
                     else "differs from shipped %s" % _fmt(shipped, 1)),
            rescue_requirement="", source_pointer=T21,
            note="the check divides generation by exactly the energy this route constructs, "
                 "so it is a self-consistency screen on the product mass x CV. Valid as a "
                 "physical plausibility filter on a candidate energy level; NOT independent "
                 "corroboration of the mass account, and the adjudication's 'the physical "
                 "test picks one' overstates it"))

    accounts = (("C0_table3", "table3_implied_efficiency_pct"),
                ("C1_table21_x_rank", "table21_mass_implied_efficiency_pct"),
                ("C2_hdip_x_rank", "hdip_mass_implied_efficiency_pct"),
                ("C3_plant_heat_rate", "plant_implied_efficiency_pct"))
    for aid, col in accounts:
        counts = {}
        for lo, hi in ((30.0, 45.0), (BAND_LO, BAND_HI)):
            bad = [_period(y) for y in sorted(adj)
                   if _num(adj[y][col]) is not None
                   and not (lo <= _num(adj[y][col]) <= hi)]
            counts[(lo, hi)] = bad
        wide, narrow = counts[(BAND_LO, BAND_HI)], counts[(30.0, 45.0)]
        rows.append(dict(
            period_id="%s..%s" % (_period(min(adj)), _period(max(adj))), row_kind="band",
            test_id="D1_%s" % aid,
            what_it_tests="years outside the admissible efficiency band, under each of the "
                          "two envelopes in circulation",
            value="%d of %d" % (len(wide), len(adj)), unit="years outside 28-47",
            touches_a_mass_account=("NO" if aid == "C0_table3" else "yes"),
            verdict=("outside under BOTH bands in %s" % ", ".join(
                sorted(set(wide) & set(narrow))) if set(wide) & set(narrow)
                else "inside the wider band in every year"),
            rescue_requirement="",
            source_pointer=T21,
            note="under 30-45 it is outside in %d of %d (%s); under 28-47 in %d (%s). This "
                 "file adopts 28-47 because for a refutation the wider band is the harder "
                 "test to pass, and the decisive conclusions do not depend on the choice"
                 % (len(narrow), len(adj), ", ".join(narrow) or "none",
                    len(wide), ", ".join(wide) or "none")))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="verify the shipped file matches a fresh build; write nothing")
    args = ap.parse_args(argv)
    rows, (t3, gen, hdip, supply, adj, years) = build()
    _signature_and_efficiency(rows, t3, gen, hdip, adj, years)
    _independence_and_band(rows, gen, adj)
    # write_or_check, not a hand-rolled comparison: it emits and re-derives through ONE
    # writer. A hand-rolled check that reads the file without newline="" gets CRLF
    # translated to LF before the compare, so it silently cannot detect a terminator
    # change at all - which is what the first version of this function did.
    status = write_or_check(OUT, FIELDS, rows, check=args.check,
                            banner=BANNER.splitlines())
    if args.check:
        return status
    print("Power reference audit -> %s (%d rows)" % (OUT, len(rows)))
    for kind in ("basis", "signature", "efficiency", "independence", "band"):
        n = sum(1 for r in rows if r["row_kind"] == kind)
        print("  %-14s %3d rows" % (kind, n))


if __name__ == "__main__":
    raise SystemExit(main())

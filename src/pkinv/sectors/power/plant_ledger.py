"""The plant fleet against the national fuel table: a physical energy closure.

WHY. This sector's activity data are four national rows of fuel in tonnes of oil equivalent,
and its largest declared risk is that nobody knows whether NEPRA's TOE convention is gross or
net calorific - worth 5 percent on coal and oil and 10 on gas. The paper has been saying that
the answer requires the HDIP Energy Yearbook.

It does not. The same report carries plant-level fuel quantities, and some of them are metered
in MMBTU, which is already energy. Those plants can be asked what efficiency they imply without
any calorific assumption whatever, and a power station's efficiency is a quantity with known
bounds. That is a test of the convention from the plant side, independent of the TOE table.

THE LEGS ARE NOT EQUALLY STRONG AND ARE REPORTED SEPARATELY.

  EXACT - gas and RLNG metered in MMBTU (Table 21, and Table 26's gas section). MMBTU to TJ is
  a definition. No assumption enters.

  ASSUMED - gas and RLNG metered in MMCFT (Table 18, Table 26's RLNG and multi-fuel sections).
  A volume needs a heating value, and Pakistani pipeline gas runs 900-1,000 Btu/scf with
  nothing in this inventory pinning it. Same unpinned quantity the captive category carries.

  DEFAULT - coal and RFO, metered as mass, needing net calorific values the repo does not hold
  for Pakistani fuel. IPCC Vol 2 Ch 1 Table 1.2 defaults are used and labelled as such; Thar
  lignite in particular is not a default-shaped fuel.

Pooling those into one number would present an exact result and a triple assumption as though
they were the same kind of evidence, so this module does not.

WHAT IT FINDS. The MMBTU plants imply 48.7 percent net efficiency in FY2023-24. That is what a
modern combined-cycle fleet achieves on a NET basis; read as gross the same fuel would imply
54.1 percent, at the very top of what any fleet average reaches. The TOE-side heat-rate
diagnostic independently puts gas near 49 percent. Two routes, one from the national table and
one from plant meters, agree - and both are consistent with net rather than gross.

The declared risk is not closed by this, because it is evidence rather than documentation. But
it is no longer untested, and the test did not need a paywalled yearbook.

WHAT DOES NOT CLOSE. Summing all gas plant energy at 1,000 Btu/scf gives about 8.5 percent more
than the national TOE gas row. Equality would need roughly 740 Btu/scf, below anything
plausible for pipeline gas - so the two sources do not fully reconcile, and the residual is
reported rather than absorbed. It is a statement about NEPRA's tables, in the same family as
the coal rows of Table 3 and Table 17 not covering the same plants.
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.core.units import TJ_PER_MMBTU
from pkinv.paths import DATA
from pkinv.activity.store import read_rows

LEDGER = asset_path(DATA, "activity", "power", "plant_fuel_ledger.csv")

# IPCC 2006 Vol 2 Ch 1 Table 1.2 net calorific values, TJ/Gg. DEFAULTS, not Pakistani
# measurements - carried here rather than in the parameter file because they serve only this
# diagnostic and must never reach the emissions path.
NCV_DEFAULT = {"Coal": 25.8, "RFO": 40.4, "HSD": 43.0}

# One million cubic feet at one Btu/scf, in TJ.
TJ_PER_MMCF_PER_BTU = 1e6 * 1.05505585262e-9

# THE POWER BOUNDARY, IN ONE PLACE (rc44). The national fuel table this sector's mass is
# built from - SoIR Table 3 - covers the CPPA side only: ke_boundary_audit tests that per
# year and per fuel and finds the national row brackets the plant sum only WITHOUT the
# K-Electric system, and ke_leg publishes K-E instead as a labelled sensitivity - a named
# configuration, not the baseline. Any consumer that WEIGHTS or PLACES that mass has to
# honour the same boundary or it spreads CPPA fuel over stations that never burned it.
# Until rc44 this was written as a bare string in four modules and honoured in three: the
# grid cube pooled Sindh's grid gas onto K-Electric's Karachi points, 15.6 percent of the
# whole located gas pool and the majority of Sindh's. A predicate cannot be honoured in
# three places out of four.
EXCLUDED_SYSTEMS = ("K-Electric",)


def in_boundary(row):
    """Is this plant-ledger row inside the baseline power boundary?"""
    return row["system"] not in EXCLUDED_SYSTEMS


def rows(year, path=LEDGER):
    return [r for r in read_rows(path, comments=False) if int(r["fiscal_year"]) == year]


def gas_energy_scale(data, year):
    """Basis of gas energy in the adopted reference, separately by source vintage.

    Earlier TOE comparisons retain their published convention. FY2024–25 is
    reconstructed from station physical quantities on the explicitly assumed
    NCV/GCV basis; the raw quantities themselves are never converted twice.
    """
    return data.p("captive_gross_to_net") if int(year) >= 2024 else 1.0


def legs(data, year=None, hhv_btu=None):
    """{exact_TJ, assumed_TJ, default_TJ, ...} - plant energy by evidence class, never pooled."""
    year = data.year if year is None else year
    hhv = data.p("captive_hhv_btu_per_scf") if hhv_btu is None else hhv_btu
    out = {"exact_TJ": 0.0, "assumed_TJ": 0.0, "default_TJ": 0.0,
           "exact_GWh": 0.0, "assumed_GWh": 0.0, "default_GWh": 0.0}
    for r in rows(year, path=LEDGER):
        q, g, unit = float(r["quantity"]), float(r["net_generation_GWh"]), r["quantity_unit"]
        if unit == "MMBTU":
            out["exact_TJ"] += q * TJ_PER_MMBTU
            out["exact_GWh"] += g
        elif unit == "MMCFT":
            out["assumed_TJ"] += q * hhv * TJ_PER_MMCF_PER_BTU
            out["assumed_GWh"] += g
        elif unit == "000 t" and r["fuel"] in NCV_DEFAULT:
            out["default_TJ"] += q * NCV_DEFAULT[r["fuel"]]      # 000 t = Gg
            out["default_GWh"] += g
    return out


def implied_efficiency(data, year=None):
    """Net electrical efficiency of the MMBTU-metered plants. THE ASSUMPTION-FREE NUMBER.

    A power station's efficiency is bounded by physics, so this asks the plants themselves
    whether their fuel figures behave like net or gross energy, without consulting the TOE
    table at all.
    """
    L = legs(data, year)
    if not L["exact_TJ"]:
        return None
    return (L["exact_GWh"] * 3600e3) / (L["exact_TJ"] * 1e6)


def gas_closure(data, year=None, hhv_btu=None):
    """Plant-summed gas energy against the national TOE gas row, and the heating value that
    would reconcile them."""
    year = data.year if year is None else year
    hhv = data.p("captive_hhv_btu_per_scf") if hhv_btu is None else hhv_btu
    L = legs(data, year, hhv)
    national = data.fuel_for(year)["Gas"] * data.p("toe_to_tj")
    mmcft = sum(float(r["quantity"]) for r in rows(year) if r["quantity_unit"] == "MMCFT")
    scale = gas_energy_scale(data, year)
    plant = (L["exact_TJ"] + L["assumed_TJ"]) * scale
    # The Btu/scf that would make the two agree, given the exact leg is fixed.
    implied_hhv = ((national - L["exact_TJ"] * scale) / (mmcft * TJ_PER_MMCF_PER_BTU * scale)
                   if mmcft else None)
    return {"plant_TJ": plant, "national_TJ": national,
            "ratio": plant / national if national else None,
            "implied_hhv_btu_per_scf": implied_hhv}

# IPCC Vol 2 Ch 1 Table 1.2 net calorific values for the two coal ranks, TJ/Gg. Defaults,
# used only to corroborate the generation-weighted blend and to state the NCV diagnostic;
# Thar lignite has no Pakistani measurement in this inventory.
NCV_LIGNITE, NCV_BITUMINOUS = 11.9, 25.8


def coal_blend(data, year=None):
    """The lignite share of coal, from the plants themselves - with the residual explicit.

    Replaces an inference. coal_lignite_share was derived from an older fleet's generation
    mix, and the Thar fleet then ramped: at FY2023-24 the mine-mouth plants are three
    quarters of coal generation. The ledger gives the split directly, per plant, with one
    residual - Lucky Electric, whose name states no origin - carried as BOUNDS rather than
    assigned.

    Two routes, reported side by side because they rest on different assumptions:

      generation-weighted   assumes plant efficiencies are comparable across origins;
      mass x default NCV    assumes IPCC rank NCVs describe Pakistani coal.

    They overlap (0.75-0.84 against 0.70-0.84 at FY2023-24), which is what makes the range
    defensible without resolving Lucky.
    """
    year = data.year if year is None else year
    g = {"Thar lignite": 0.0, "imported": 0.0, "unknown": 0.0}
    m = dict(g)
    for r in rows(year):
        if r["fuel"] != "Coal":
            continue
        g[r["fuel_origin"]] += float(r["net_generation_GWh"])
        m[r["fuel_origin"]] += float(r["quantity"])
    tg = sum(g.values())
    gen_lo = g["Thar lignite"] / tg                          # Lucky as imported
    gen_hi = (g["Thar lignite"] + g["unknown"]) / tg         # Lucky as Thar
    e_thar, e_imp = m["Thar lignite"] * NCV_LIGNITE, m["imported"] * NCV_BITUMINOUS
    ncv_lo = e_thar / (e_thar + e_imp + m["unknown"] * NCV_BITUMINOUS)
    ncv_hi = (e_thar + m["unknown"] * NCV_LIGNITE) / (
        e_thar + m["unknown"] * NCV_LIGNITE + e_imp)
    return {"generation_GWh": g, "mass_kt": m,
            "gen_weighted_lo": gen_lo, "gen_weighted_hi": gen_hi,
            "gen_weighted_mid": (gen_lo + gen_hi) / 2.0,
            "ncv_route_lo": ncv_lo, "ncv_route_hi": ncv_hi,
            "residual_share_of_generation": g["unknown"] / tg}


def coal_ncv_diagnostic(data, year=None):
    """What NCV the national coal TOE implies for the ledger's coal mass. A CONTROL-TOTAL
    QUESTION, published rather than acted on.

    Table 3's coal energy over the ledger's coal mass gives about 24 TJ/Gg - bituminous
    territory - for a fleet that is over ninety percent lignite by mass, which at IPCC rank
    defaults would average about 13. Either the TOE conversion treats all coal alike, or Thar
    coal's real calorific value is far above the lignite default, or the two sources do not
    share a scope. This is also the shape of the coal heat-rate instability: an implied
    efficiency near 20 percent is what a real 35-40 percent plant looks like through an
    energy figure inflated by roughly that ratio.

    Deciding between those readings would change the sector's activity basis, which is a
    methodological decision, not a diagnostic's. Reported only.
    """
    year = data.year if year is None else year
    mass = sum(float(r["quantity"]) for r in rows(year) if r["fuel"] == "Coal")
    # Table 3's OWN energy, not the engine's booked coal - see PowerData.table3_coal_toe.
    toe_tj = data.table3_coal_toe(year) * data.p("toe_to_tj")
    b = coal_blend(data, year)
    lig_mass = b["mass_kt"]["Thar lignite"] + b["mass_kt"]["unknown"]
    blended = (lig_mass * NCV_LIGNITE
               + b["mass_kt"]["imported"] * NCV_BITUMINOUS) / mass if mass else None
    return {"table3_TJ": toe_tj, "ledger_mass_kt": mass,
            "implied_NCV_TJ_per_Gg": toe_tj / mass if mass else None,
            "default_blend_NCV_TJ_per_Gg": blended,
            "ratio": (toe_tj / mass) / blended if mass and blended else None}

def ke_boundary_audit(data):
    """Does the national fuel table include K-Electric? Tested, per year, per fuel.

    The sector has implicitly assumed Table 3 covers the whole country. The ledger can ask:
    sum plant fuel energy with and without the K-Electric system and see which sum the
    national row agrees with.

    WHAT IT FINDS. On the gas leg - the stronger one, though its MMCFT part carries the
    heating value - the without-KE sum brackets the national row (0.89-1.09 across five
    years) while the with-KE sum exceeds it in every year, by 9 to 27 percent. On RFO, which
    rests on a default calorific value, neither reading centres cleanly - except in
    FY2023-24, the sharpest discriminator in the panel: the national RFO row sits at 0.890
    times the without-KE sum and 1.256 times the with-KE sum, because K-Electric's furnace
    oil collapsed in the same year the national row did. The evidence leans CPPA-side-only:
    K-Electric's own fuel - computed exactly in ke_leg.py - is NOT a flat number but a
    trend, 7.1 down to 4.0 Mt CO2 across FY2019-23 as its furnace oil retired, and is
    probably NOT inside the activity basis this sector estimates from.

    Like the coal NCV question, that is a control-total finding. Acting on it means either
    adding a K-Electric category built on ledger evidence (weaker classes: MMCFT plus
    default NCVs) or establishing that Table 3 does include KE after all, and either is the
    author's call. Published only.
    """
    out = []
    for year in sorted({int(r["fiscal_year"]) for r in rows(0, path=LEDGER)} |
                       {int(r["fiscal_year"]) for r in _all_rows()}):
        try:
            nat_gas = data.fuel_for(year)["Gas"] * data.p("toe_to_tj")
            nat_rfo = data.fuel_for(year)["Furnace Oil"] * data.p("toe_to_tj")
        except KeyError:
            continue
        hhv = data.p("captive_hhv_btu_per_scf")
        gas = {"KE": 0.0, "CPPA": 0.0}
        rfo = {"KE": 0.0, "CPPA": 0.0}
        for r in _all_rows():
            if int(r["fiscal_year"]) != year:
                continue
            side = "KE" if r["system"] == "K-Electric" else "CPPA"
            q = float(r["quantity"])
            if r["fuel"] in ("Gas", "RLNG"):
                gas[side] += ((q * TJ_PER_MMBTU if r["quantity_unit"] == "MMBTU"
                              else q * hhv * TJ_PER_MMCF_PER_BTU)
                             * gas_energy_scale(data, year))
            elif r["fuel"] == "RFO":
                rfo[side] += q * NCV_DEFAULT["RFO"]
        out.append({"fiscal_year": year,
                    "gas_without_KE_over_national": gas["CPPA"] / nat_gas,
                    "gas_with_KE_over_national": (gas["CPPA"] + gas["KE"]) / nat_gas,
                    "KE_gas_TJ": gas["KE"],
                    "rfo_without_KE_over_national": rfo["CPPA"] / nat_rfo,
                    "rfo_with_KE_over_national": (rfo["CPPA"] + rfo["KE"]) / nat_rfo,
                    "KE_rfo_TJ": rfo["KE"]})
    return out


def _all_rows(path=LEDGER):
    return read_rows(path, comments=False)


# Combined-cycle identification threshold: 9,000 kJ/kWh net is 40 percent efficiency, which
# no steam boiler or simple-cycle gas turbine reaches. Above it the ledger cannot separate a
# steam plant from an open-cycle turbine or a degraded combined cycle, so 10,500 kJ/kWh -
# comfortably below any combined-cycle design point but ordinary for steam - marks the
# boiler side, and the band between is left unresolved rather than guessed.
CC_HEAT_RATE_MAX_KJ_PER_KWH = 9000.0
BOILER_HEAT_RATE_MIN_KJ_PER_KWH = 10500.0


def gas_technology_split(data, year=None):
    """Grid gas and RLNG energy split by combustor type - turbine, boiler, or unresolved.

    WHY THE LEDGER CAN ANSWER THIS. The air layer's gas NOx factor depends on whether the
    fuel burns in a boiler (AP-42 Chapter 1.4, external combustion) or a gas turbine
    (Chapter 3.1), and NEPRA's national fuel table reports fuel without plant type. The
    ledger carries two things the national table does not: plant names and implied heat
    rates. Heat rate is the physical classifier - a plant at or below 9,000 kJ/kWh net can
    only be a combined cycle - and it is trusted over names, because names lie here: Bin
    Qasim TPS-II and TPS-III are combined-cycle blocks behind steam-era names. Names are
    used only where they assert turbine hardware (GTPS, CCPP), which heat rate alone cannot
    distinguish from a steam plant at simple-cycle efficiencies.

    EVIDENCE CLASSES, KEPT VISIBLE. MMBTU-metered plants carry exact heat rates. For
    MMCFT-metered plants the heat rate inherits the sector's assumed heating value, but the
    combined-cycle question survives it: the gap between 7,000 and 11,000 kJ/kWh dwarfs the
    900-1,000 Btu/scf range. One plant sits close enough for the assumption to matter -
    TPS Nandipur reads 8,204 at 900 Btu/scf and 9,116 at 1,000 - and at the central value
    it lands in the unresolved band, which is the honest place for it.

    K-ELECTRIC IS EXCLUDED, deliberately: the split describes the fleet behind the national
    gas row, and ke_boundary_audit finds that row brackets the plant sum only without the
    K-Electric system. Including K-E's combined-cycle-heavy fleet would sharpen a share that
    the activity it multiplies does not contain.

    Unresolved plants are NOT assigned. The caller keeps them on the boiler factor and
    reports them as the residual; this function only says how large that residual is.
    """
    year = data.year if year is None else year
    hhv = data.p("captive_hhv_btu_per_scf")
    plants = {}
    for r in rows(year, path=LEDGER):
        if r["fuel"] not in ("Gas", "RLNG") or not in_boundary(r):
            continue
        q, unit = float(r["quantity"]), r["quantity_unit"]
        if unit == "MMBTU":
            tj = q * TJ_PER_MMBTU
        elif unit == "MMCFT":
            tj = q * hhv * TJ_PER_MMCF_PER_BTU
        else:
            continue
        p = plants.setdefault(r["plant"], {"TJ": 0.0, "GWh": 0.0})
        p["TJ"] += tj
        p["GWh"] += float(r["net_generation_GWh"])

    out = {"turbine_TJ": 0.0, "boiler_TJ": 0.0, "unresolved_TJ": 0.0,
           "turbine_plants": [], "boiler_plants": [], "unresolved_plants": []}
    for name, p in sorted(plants.items()):
        hr = p["TJ"] * 1000.0 / p["GWh"] if p["GWh"] else None
        if "GTPS" in name or "CCPP" in name:
            bucket = "turbine"
        elif hr is not None and hr <= CC_HEAT_RATE_MAX_KJ_PER_KWH:
            bucket = "turbine"
        elif hr is not None and hr >= BOILER_HEAT_RATE_MIN_KJ_PER_KWH:
            bucket = "boiler"
        else:
            bucket = "unresolved"
        out[bucket + "_TJ"] += p["TJ"]
        out[bucket + "_plants"].append(name)
    total = out["turbine_TJ"] + out["boiler_TJ"] + out["unresolved_TJ"]
    out["total_TJ"] = total
    out["turbine_share"] = out["turbine_TJ"] / total if total else 0.0
    out["unresolved_share"] = out["unresolved_TJ"] / total if total else 0.0
    return out

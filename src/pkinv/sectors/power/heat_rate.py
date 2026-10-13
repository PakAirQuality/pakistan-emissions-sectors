"""Implied heat rate: the validation this sector had the data for and never ran.

WHAT THIS IS NOT. It is not an alternative activity basis. The sector estimates emissions from
fuel consumed in tonnes of oil equivalent and will go on doing so, because TOE is already an
energy unit and converting it needs one documented constant rather than a per-plant efficiency
assumption. Generation divided by fuel does not improve the estimate.

WHAT IT IS. A consistency check between two tables of the same NEPRA report that nobody had
made talk to each other. Table 3 gives fuel consumed by fuel; Table 17 gives net generation by
fuel and system. Dividing one by the other gives an implied heat rate, and a heat rate is a
quantity with known physical bounds - no coal plant has ever beaten about 47 percent, no
combined cycle about 64. So the ratio tests whether the two tables describe the same fleet,
which is exactly the question the sector's largest declared risk turns on.

THE SECTOR PAPER SAID NO GENERATION FIGURE WAS USED, AND THAT WAS TRUE OF THE ENGINE AND
MISLEADING ABOUT THE DATA. data/activity/power/generation_by_fuel.csv has been in this
repository, loaded by PowerData, since the sector was written; PowerData.generation_for() had
no callers. The check below is what that column was for.

TWO MAPPINGS THE TABLES FORCE, AND THEY ARE THE POINT.

  Table 3 reports one "Gas" row. Table 17 splits Gas from RLNG. Regasified LNG is natural gas
  by the time it reaches a turbine, and the fuel table has NO RLNG row at all, so the fuel
  behind Table 17's 26,501 GWh of FY2022 RLNG generation can only be inside Table 3's Gas
  figure - there is nowhere else in the fuel table for it to be. The comparison therefore puts
  Table 3's Gas against Table 17's Gas + RLNG.

  That is a completeness argument, not an argument from absurdity. Comparing against Table 17's
  Gas alone gives 18 percent, which is merely implausible rather than impossible, so it would
  not settle the question on its own.

  Diesel Oil is Table 17's HSD, and Furnace Oil its RFO. Those are the same fuels under the
  two documents' different labels.

WHAT IT FINDS. Gas is stable across the whole overlap at 48 to 56 percent, which is what a real
combined-cycle fleet does, and furnace oil is stable too. Coal is not stable: it runs 58 percent
in FY2020 - above any coal plant ever built - and 23 percent in FY2022, a 2.5-fold swing in
three years. No fleet changes efficiency like that, so the two tables are not covering the same
set of coal plants, and the mismatch moves year to year.

That is a COVERAGE finding about the source, not an error in the sector's own arithmetic. The
emissions estimate is driven by the fuel table alone and is unaffected either way. It is
reported rather than resolved, because resolving it needs the plant-level tables (SIR 20/23/28)
that nobody here has parsed.

WHAT IT SETTLES, PARTLY. The sector's largest declared risk is that the TOE figures might be on
a gross rather than net calorific basis, worth 5-10 percent on CO2. Gas at a stable 49 percent
net is what a modern combined cycle achieves on a NET basis; on a gross reading the same fuel
would imply about 55 percent, which is at the very top of what any fleet average reaches. That
is evidence for the net reading rather than proof of it, and the sector still reports the risk -
but it is no longer untested.

Writes the comparison as rows in the sector's outputs, on the same principle as the railway
factor-table diagnostic: a check whose result lives in a CSV a reader can see beats a claim in
a docstring.
"""
from pkinv.paths import OUTPUTS  # noqa: F401  (documents where the rows land)

# Table 3 fuel -> the Table 17 fuels that generation is reported under.
FUEL_MAP = {
    "Coal": ("Coal",),
    "Gas": ("Gas", "RLNG"),
    "Furnace Oil": ("RFO",),
    "Diesel Oil": ("HSD",),
}

# 1 kWh = 3600 kJ, so efficiency = 3600 / heat_rate(kJ/kWh).
KJ_PER_KWH = 3600.0

# The best net efficiency each technology has ever achieved anywhere, as a CEILING. These are
# physical facts about heat engines rather than judgements about Pakistan, which is what makes
# a breach evidence about the tables rather than about the fleet. Coal tops out at
# ultra-supercritical, gas at the best combined cycle, oil-fired steam well below both.
CEILING = {"Coal": 0.47, "Gas": 0.64, "Furnace Oil": 0.45, "Diesel Oil": 0.50}

# A floor is a judgement, not a fact, so it is set wide and only ever LABELS a row.
FLOOR = 0.20

# How much a fuel's implied heat rate may vary across the overlap before the two tables are
# not describing the same fleet. A real fleet's average efficiency moves a few points a year
# as plants commission and merit order shifts; it does not double.
#
# THIS IS THE ASSUMPTION-FREE HALF OF THE CHECK and the more useful one. It needs no view on
# what efficiency a Pakistani plant achieves - only that whatever it is, it cannot swing by a
# factor of two in three years. Coal fails it; gas passes comfortably.
MAX_SPREAD = 1.5

# Below this a fuel is too small for the ratio to mean anything: rounding in either table
# dominates. Diesel oil at 0.67 GWh in FY2019 is the case this exists for.
MATERIAL_GWH = 1000.0


def implied(data, year=None, basis="booked"):
    """[{fuel, toe, gwh_net, heat_rate_kJ_per_kWh, efficiency, verdict, note}] for one year.

    Only fuels present in BOTH tables appear. The two series do not cover the same years -
    fuel runs FY2018-2022 and generation FY2019-2023 - so a year outside the overlap yields
    an empty list rather than a partial comparison.
    """
    year = data.year if year is None else year
    # WHICH COAL ACCOUNT THIS DESCRIBES. "booked" is what the inventory reports, which is the
    # question a reader of the estimate is asking. "table3" is the regulator's printed energy,
    # which is the account this check REFUTED and which the inventory no longer books - kept
    # addressable because the refutation has to stay checkable after the thing it refuted
    # stopped being the default. Only coal differs between the two.
    if basis not in ("booked", "table3"):
        raise ValueError("basis is 'booked' or 'table3', not %r" % (basis,))
    fuel = dict(data.fuel_for(year))
    if basis == "table3" and "Coal" in fuel:
        fuel["Coal"] = data.table3_coal_toe(year)
    gen = data.generation_for(year)
    rows = []
    for f, gen_fuels in FUEL_MAP.items():
        toe = fuel.get(f)
        gwh = sum(r["gwh_net"] for r in gen if r["fuel"] in gen_fuels)
        if toe is None or not gwh:
            continue
        # TOE -> TJ -> kJ, over kWh.
        tj = toe * data.p("toe_to_tj")
        heat_rate = tj * 1e9 / (gwh * 1e6)          # kJ per kWh
        eff = KJ_PER_KWH / heat_rate
        if eff > CEILING[f]:
            verdict = "IMPLAUSIBLE-HIGH"
            note = ("implied efficiency exceeds the best %s plant ever built (%.0f%%) - the "
                    "generation table must cover output this fuel row does not, or the fuels "
                    "are mismapped" % (f.lower(), 100 * CEILING[f]))
        elif eff < FLOOR:
            verdict = "IMPLAUSIBLE-LOW"
            note = ("implied efficiency is below any grid thermal plant - the fuel row must "
                    "cover generation the table does not report, i.e. a COVERAGE gap in "
                    "Table 17 rather than an error in the emissions estimate")
        else:
            verdict = "plausible"
            note = "consistent with a real plant of this type"
        rows.append({"fuel": f, "generation_fuels": "+".join(gen_fuels), "toe": toe,
                     "gwh_net": round(gwh, 2),
                     "heat_rate_kJ_per_kWh": round(heat_rate, 1),
                     "efficiency": round(eff, 4), "verdict": verdict, "note": note})
    return rows


def overlap_years(data):
    """Fiscal years present in both tables, which is the only span the check is defined on."""
    return sorted({r["fiscal_year"] for r in data.fuel}
                  & {r["fiscal_year"] for r in data.generation})


def stability(data, basis="booked"):
    """{fuel: {years, lo, hi, spread, verdict}} over the overlap.

    The band-free half of the check. A fuel whose implied heat rate is stable across four years
    is a fuel whose two tables agree about which plants they cover; one that swings by a factor
    of two is not, whatever the true efficiency happens to be.
    """
    series = {}
    for y in overlap_years(data):
        for r in implied(data, y, basis=basis):
            # Materiality is judged PER YEAR, not per fuel. Diesel oil generated 0.67 GWh in
            # FY2019 and 1,422 in FY2021; keeping the fuel because its best year is material
            # would let the one meaningless year set the spread, which is how it first came
            # out at 105-fold. The unusable year is dropped, not the fuel.
            if r["gwh_net"] < MATERIAL_GWH:
                continue
            series.setdefault(r["fuel"], []).append((y, r["efficiency"]))
    out = {}
    for f in FUEL_MAP:
        pairs = series.get(f, [])
        if len(pairs) < 2:
            out[f] = {"years": len(pairs), "lo": None, "hi": None, "spread": None,
                      "verdict": "insufficient",
                      "note": "fewer than two years above %.0f GWh" % MATERIAL_GWH}
            continue
        effs = [e for _y, e in pairs]
        lo, hi = min(effs), max(effs)
        spread = hi / lo
        out[f] = {"years": len(pairs), "lo": round(lo, 4), "hi": round(hi, 4),
                  "spread": round(spread, 2),
                  "verdict": "stable" if spread <= MAX_SPREAD else "UNSTABLE",
                  "note": ""}
    return out


def unreported_generation_gwh(data, row):
    """GWh the fuel implies but the generation table does not report, at PLAUSIBLE_HI.

    A deliberately conservative statement of the coverage gap: it asks how much generation the
    fuel could NOT have produced even at the best efficiency any plant achieves, so it is a
    lower bound on what is missing rather than an estimate of it. Zero when nothing is missing.

    Takes `data` rather than closing over the constant, so the TOE convention lives in exactly
    one place - it is the sector's largest declared risk and a second copy of it here would be
    the obvious way for the two to drift apart.
    """
    implied_max = row["toe"] * data.p("toe_to_tj") * 1e9 / (KJ_PER_KWH / PLAUSIBLE_HI) / 1e6
    return max(0.0, round(implied_max - row["gwh_net"], 1))

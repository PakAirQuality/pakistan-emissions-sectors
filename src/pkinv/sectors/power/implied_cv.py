"""Per-plant implied coal calorific values from NEPRA's heat-rate tables - the third channel
on the sector's largest open question, and the sharpest.

THE QUESTION. The national fuel table (SIR Table 3) reports coal in TOE - energy. The plant
ledger meters coal in mass. Dividing one by the other implies 24.2 TJ/Gg over a fleet that
is 92 percent lignite by mass, against an IPCC lignite default near 11.9: ratio 1.86, worth
about 12 Mt CO2. Two readings were live: Table 3 converts all coal at a bituminous-like
calorific value (overstating coal energy ~40 percent), or the mass and energy tables do not
describe the same coal. The CRT's 2 percent agreement with Table 3's solid-fuel energy cut
against the first reading without closing it.

THE CHANNEL. Tables 20/23/28 of the same report publish per-plant heat rates in Btu/kWh,
five fiscal years. Heat rate x net generation is fuel energy; fuel energy over the ledger's
coal mass is a calorific value, plant by plant - no Table 3 in the loop. Table 28's footnote
states the basis: LHV. So what this module derives is an NCV, directly comparable to IPCC
Table 1.2 net calorific values.

WHAT THE DISCRIMINATOR SHOWED (and why the result is quotable either way). Before trusting
the channel, the gas plants test it: for MMBTU-metered plants the ledger holds true fuel
energy, so ledger-energy/generation against the printed heat rate reveals how the heat
rates were made. Three behaviours, all found: exactly three plants (Liberty Daharki, Sindh
Nooriabad-I and -II) print net heat rates that reproduce the ledger ratio to four digits -
fully circular there, the heat rate IS the fuel table; pipeline-gas plants (Uch, Uch-II)
sit at 1.104-1.109 against the net-export heat rate - exactly the natural-gas HHV/LHV
factor, same meters converted to LHV, consistent with the footnote; the RLNG combined
cycles drift year to year, an independent channel. NO COAL PLANT is in the circular set:
six of eight print year-varying (operational) heat rates; Sahiwal and Thar Coal Block-I
print flat design values. So what this module recovers per Thar plant is either a physical
NCV or the official system's own assumed CV - undecidable from this document, and it does
not matter for the question: BOTH readings pin what the official reporting chain believes
Thar coal's calorific value to be, which is precisely what Table 3's TOE conversion
depends on.

THE ANSWER, REGRESSION-PINNED IN TESTS. Thar plants land at 10.7-13.9 TJ/Gg, mass-weighted
11.6 - squarely IPCC lignite. Imported plants land at 19-25 - bituminous. The FY2022-23
fleet blend is ~14.6 against Table 3's implied 24.2. Table 3's coal row is high by a factor
of ~1.6-1.7 ON THIS CHANNEL; the CRT agreement stands as counter-evidence, and a scope
difference between the two coal figures is the surviving reconciliation. Bonus: Lucky
Electric - the ledger's one unresolved coal origin - implies 11.4-12.1 TJ/Gg, lignite-band.

DIAGNOSTIC ONLY. Nothing here feeds the estimate; combustion.py and engine.py never import
this module. The restated-coal case appears in power_totals as a labelled sensitivity row,
computed in the runner from this module's output - the same idiom as the blend bounds.
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA
from pkinv.sectors.power import plant_ledger
from pkinv.activity.store import read_rows

HR_CSV = asset_path(DATA, "activity", "power", "plant_heat_rates.csv")

BTU_TO_TJ = 1.05505585262e-9
# Outlier screen, TJ/Gg NCV. The ceiling is set by coal itself: IPCC anthracite is 26.7
# and coking coal 28.2, so nothing a power station burns reaches 30 - a CV above it means
# an input is wrong (a suspect mass cell, a partial-year mismatch), not an exotic coal.
CV_SANE_LO, CV_SANE_HI = 5.0, 30.0
GAS_HHV_LHV_LO, GAS_HHV_LHV_HI = 1.09, 1.12   # pipeline-gas band the discriminator found

# Heat-rate-table name -> ledger name, for the handful that differ. Coal plants join with
# no aliasing at all, which is itself a small validation of both parsers' name rule.
ALIAS = {
    "Engro Gen. Qadirpur": "Engro Powergen. Qadirpur",
    "NPPMCL (Haveli Bahadur Shah)": "NPPMCL (HBS)",
    "Punjab Thermal Power": "Punjab Thermal",
    "KAPCO": "RLNG RFO HSD Overall kWh) KAPCO",
}


def hr_rows(path=HR_CSV):
    return read_rows(path, comments=False)


def _index(rows=None):
    """{(ledger_plant, year): hr row}. Dual-fuel plants keep their Gas column - the ledger
    meters those plants' RLNG, and HSD is a startup fuel."""
    out = {}
    for r in rows if rows is not None else hr_rows():
        if r["fuel_column"] not in ("", "Gas"):
            continue
        plant = ALIAS.get(r["plant"], r["plant"])
        out[(plant, int(r["fiscal_year"]))] = r
    return out


def _f(cell):
    return float(cell) if cell not in ("", None) else None


def circularity(data):
    """The gas discriminator: how were the printed heat rates made?

    For every MMBTU-metered ledger plant-year with a heat-rate row, the ledger's own
    energy/generation ratio (Btu/kWh, HHV as metered) is compared against the printed
    gross and net-export heat rates. verdict:
      identical        - printed HR reproduces the ledger ratio (would mean fully circular;
                         observed nowhere)
      same-meters-LHV  - ratio to net HR sits in the pipeline-gas HHV/LHV band: same fuel
                         meters, converted to LHV, as Table 28's footnote says
      independent-drift - neither; the channel moves on its own
    """
    idx = _index()
    out = []
    for year in sorted({int(r["fiscal_year"]) for r in plant_ledger._all_rows()}):
        for r in plant_ledger.rows(year):
            if r["quantity_unit"] != "MMBTU":
                continue
            g = float(r["net_generation_GWh"])
            if not g:
                continue
            hr = idx.get((r["plant"], year))
            if hr is None:
                continue
            ledger_btu_kwh = float(r["quantity"]) / g   # MMBTU/GWh == Btu/kWh
            t_gross, t_net = _f(hr["hr_gross_btu_kwh"]), _f(hr["hr_net_btu_kwh"])
            ratio_gross = ledger_btu_kwh / t_gross if t_gross else None
            ratio_net = ledger_btu_kwh / t_net if t_net else None
            if any(x is not None and abs(x - 1.0) < 0.005
                   for x in (ratio_gross, ratio_net)):
                verdict = "identical"
            elif ratio_net is not None and GAS_HHV_LHV_LO <= ratio_net <= GAS_HHV_LHV_HI:
                verdict = "same-meters-LHV"
            else:
                verdict = "independent-drift"
            out.append({"fiscal_year": year, "plant": r["plant"], "fuel": r["fuel"],
                        "ledger_btu_kwh": round(ledger_btu_kwh, 1),
                        "t_hr_gross": t_gross, "t_hr_net": t_net,
                        "ratio_gross": round(ratio_gross, 4) if ratio_gross else "",
                        "ratio_net": round(ratio_net, 4) if ratio_net else "",
                        "verdict": verdict})
    return out


def _design_flat_years(rows):
    """{(plant, year)} whose gross heat rate repeats verbatim in another year - a contract
    or design figure, not an operational measurement."""
    by_plant = {}
    for r in rows:
        if r["fuel_column"] not in ("", "Gas"):
            continue
        g = _f(r["hr_gross_btu_kwh"])
        if g:
            by_plant.setdefault(ALIAS.get(r["plant"], r["plant"]), []).append(
                (int(r["fiscal_year"]), g))
    flat = set()
    for plant, pairs in by_plant.items():
        counts = {}
        for _y, g in pairs:
            counts[g] = counts.get(g, 0) + 1
        for y, g in pairs:
            if counts[g] >= 2:
                flat.add((plant, y))
    return flat


def implied_coal_cv(data):
    """One row per ledger coal plant-year: the implied NCV and how much to trust it.

    evidence_class:
      operational-net - year-varying heat rate, net-export basis; the strongest rows
      design-flat     - the heat rate repeats verbatim across years (contract figure)
      gross-only      - net columns are n.p. (Sahiwal); gross HR against net GWh
                        UNDERSTATES fuel, so the CV is a lower bound
      no-hr           - no heat-rate row for that plant-year (Engro FY2019/2020)
      outlier         - CV outside [5, 35] TJ/Gg: an input is wrong, not a coal
    """
    raw = hr_rows()
    idx = _index(raw)
    flat = _design_flat_years(raw)
    out = []
    for year in sorted({int(r["fiscal_year"]) for r in plant_ledger._all_rows()}):
        for r in plant_ledger.rows(year):
            if r["fuel"] != "Coal":
                continue
            mass = float(r["quantity"])                 # 000 t = Gg
            gwh = float(r["net_generation_GWh"])
            hr = idx.get((r["plant"], year))
            row = {"fiscal_year": year, "plant": r["plant"],
                   "fuel_origin": r["fuel_origin"], "mass_kt": mass,
                   "net_generation_GWh": gwh, "hr_btu_kwh": "", "hr_basis_used": "",
                   "implied_cv_TJ_per_Gg": "", "evidence_class": "no-hr",
                   "note": ""}
            if hr is not None and mass and gwh:
                net, gross = _f(hr["hr_net_btu_kwh"]), _f(hr["hr_gross_btu_kwh"])
                if net:
                    hr_val, basis = net, "net-export"
                    cls = ("design-flat" if (r["plant"], year) in flat
                           else "operational-net")
                elif gross:
                    hr_val, basis = gross, "gross-only"
                    cls = "gross-only"
                else:
                    hr_val = None
                if hr_val:
                    cv = gwh * 1e6 * hr_val * BTU_TO_TJ / mass
                    if not (CV_SANE_LO <= cv <= CV_SANE_HI):
                        cls = "outlier"
                    row.update({"hr_btu_kwh": hr_val, "hr_basis_used": basis,
                                "implied_cv_TJ_per_Gg": round(cv, 2),
                                "evidence_class": cls, "note": hr["note"]})
            out.append(row)
    return out


def fleet_cv(data, year):
    """Mass-weighted implied NCV for one year, split by origin, against Table 3's implied
    NCV where Table 3 covers that year. Outliers are excluded from the weights and counted."""
    rows = [r for r in implied_coal_cv(data) if r["fiscal_year"] == year]
    groups = {"Thar lignite": [0.0, 0.0], "imported": [0.0, 0.0], "unknown": [0.0, 0.0]}
    outliers = excluded = 0
    for r in rows:
        if r["evidence_class"] in ("no-hr",):
            excluded += 1
            continue
        if r["evidence_class"] == "outlier":
            outliers += 1
            continue
        g = groups[r["fuel_origin"]]
        g[0] += r["mass_kt"]
        g[1] += r["mass_kt"] * float(r["implied_cv_TJ_per_Gg"])
    def wavg(g):
        return g[1] / g[0] if g[0] else None
    fleet_mass = sum(g[0] for g in groups.values())
    fleet_energy = sum(g[1] for g in groups.values())
    ledger_mass = sum(r["mass_kt"] for r in rows)
    try:
        diag = plant_ledger.coal_ncv_diagnostic(data, year)
        table3 = diag["implied_NCV_TJ_per_Gg"]
    except (KeyError, ZeroDivisionError):
        table3 = None
    fleet = fleet_energy / fleet_mass if fleet_mass else None
    return {"fiscal_year": year,
            "thar_cv": wavg(groups["Thar lignite"]),
            "imported_cv": wavg(groups["imported"]),
            "unknown_cv": wavg(groups["unknown"]),
            "fleet_cv": fleet,
            "fleet_mass_kt": fleet_mass,
            "ledger_mass_kt": ledger_mass,
            # Table 3's implied NCV divides by ALL ledger mass; the fleet CV weights only
            # the covered plant-years. The share keeps the two denominators honest.
            "covered_share": fleet_mass / ledger_mass if ledger_mass else None,
            "table3_implied_ncv": table3,
            "table3_over_fleet": table3 / fleet if (table3 and fleet) else None,
            "outliers_excluded": outliers, "no_hr_excluded": excluded}


# IPCC 2006 Vol.2 Ch.1 Table 1.2 net calorific values, by the rank the regulator names.
# "unknown" takes the lignite value: it is the lower of the two, so an unstated rank
# lowers the energy rather than raising it.
RANK_DEFAULT_NCV = {"imported": 25.8, "Thar lignite": 11.9, "unknown": 11.9}


def restated_coal_TJ(data, year):
    """The sensitivity's activity leg: sum of plant mass x implied CV for the year, with
    no-hr and outlier plant-years carried at that year's fleet-weighted CV so the total
    covers the whole ledger mass rather than silently shrinking."""
    rows = [r for r in implied_coal_cv(data) if r["fiscal_year"] == year]
    f = fleet_cv(data, year)
    total = 0.0
    for r in rows:
        if r["evidence_class"] in ("no-hr", "outlier") or not r["implied_cv_TJ_per_Gg"]:
            total += r["mass_kt"] * (f["fleet_cv"] or 0.0)
        else:
            total += r["mass_kt"] * float(r["implied_cv_TJ_per_Gg"])
    return total


def rank_default_coal_TJ(data, year):
    """The same quantity as restated_coal_TJ above, computed with NO HEAT RATE.

    Placed beside its sibling deliberately, because the difference between them is the whole
    of the review's objection to the published power estimate. restated_coal_TJ multiplies the
    ledger mass by a calorific value derived as generation x a printed heat rate / mass, so the
    energy it returns CONTAINS the generation; divide electricity out of it and you recover the
    regulator's own printed efficiency, which is not a test of anything. This one multiplies the
    same mass by the IPCC 2006 Vol.2 Ch.1 Table 1.2 default for the rank the regulator says each
    station burns, and touches no heat rate at all - so the energy it returns is independent of
    the generation it will be judged against.

    Rank is read from the ledger's own fuel_origin column, not inferred. An origin the table
    does not state is carried at the lignite default, which is the conservative direction here:
    lignite has the lower calorific value, so an unknown rank lowers the energy rather than
    raising it, and the one station with a blank origin (Lucky Electric) implies 11.1-12.1
    TJ/Gg from its own generation, which is lignite-like.
    """
    from pkinv.sectors.power import plant_ledger
    rows = [r for r in plant_ledger.rows(year) if "oal" in r["fuel"]]
    if not rows:
        raise ValueError("the plant ledger carries no coal for FY%d-%02d"
                         % (year, (year + 1) % 100))
    total = 0.0
    for r in rows:
        ncv = RANK_DEFAULT_NCV.get((r.get("fuel_origin") or "").strip() or "unknown",
                                   RANK_DEFAULT_NCV["unknown"])
        total += float(r["quantity"]) * ncv
    return total


def main():
    from pkinv.sectors.power.data import PowerData
    data = PowerData()
    for year in (2021, 2022, 2023):
        f = fleet_cv(data, year)
        print("FY%d: Thar %.2f, imported %s, fleet %.2f TJ/Gg; Table 3 implies %s (x%s)"
              % (year, f["thar_cv"] or 0,
                 "%.2f" % f["imported_cv"] if f["imported_cv"] else "-",
                 f["fleet_cv"] or 0,
                 "%.2f" % f["table3_implied_ncv"] if f["table3_implied_ncv"] else "-",
                 "%.2f" % f["table3_over_fleet"] if f["table3_over_fleet"] else "-"))


if __name__ == "__main__":
    main()

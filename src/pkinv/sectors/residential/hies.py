"""Household survey fuel quantities - HIES 2018-19 and 2024-25, and what they govern.

WHAT A SURVEY IS ALLOWED TO DO HERE. The residential sector's architecture is official
controls for magnitude, surveys for distribution. OGRA meters gas, LPG and kerosene at the
point of supply; for those fuels HIES publishes DIAGNOSTIC ratios and strata distributions
but never moves a total. Where no statistic of HOUSEHOLD USE exists at all, the survey is
the best national quantity there is and becomes PRIMARY - firewood, dung cake (since rc67),
and (in later phases) charcoal, coal and crop residues. Dung was diagnostic through rc66
because the agriculture nitrogen ledger "fixed" it; what that ledger fixes is the supply
agriculture diverts, not what households burn. The
role of every fuel is declared on its comparison row, and tests assert the diagnostic
ratios are published-never-applied.

FIREWOOD CHANGES ANCHOR IN THIS EDITION. The previous estimate rode FAOSTAT's wood-fuel
series, which carries FAO's own "E" flag in every year and does not move. HIES 2024-25
records 23.1 million tonnes of firewood entering households as purchased, own-produced,
in-kind or gifted quantities - a design-weighted national measurement, and one the
2018-19 round independently reproduces within six percent (22.0 Mt). FAOSTAT's
moisture-matched equivalent sits seven percent above the survey; the two corroborate each
other, and FAOSTAT survives as the structural scenario firewood_faostat.

THE DUNG RATIO IS THE HEADLINE DIAGNOSTIC. The nitrogen ledger implies 58.7 Mt of air-dry
cake; households report consuming about 12 Mt. That factor-of-~5 gap (r_dung) is published
on the comparison table. The survey records household consumption of formed cake; the
ledger records all excreted N diverted from manure management. They are two quantities,
and since rc67 the residential row carries the first: the reference burns the survey's
quantity and the difference is carried as unresolved, outside the total.

Data path: data/activity/residential/hies/ - committed CSVs derived from the gitignored,
hash-pinned PBS microdata by scripts/ingest_hies.py (the only place pandas/pyreadstat are
allowed). Weighted household totals: 33.2M (2018-19), 39.9M (2024-25).
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA
from pkinv.activity.store import read_rows

HIES_DIR = asset_path(DATA, "activity", "residential", "hies")
SURVEYS = ("hies2019", "hies2025")
CURRENT = "hies2025"

# fuel -> engine role. "primary": the survey quantity IS the sector's activity number.
# "diagnostic": an official control keeps the magnitude; the ratio is published only.
# "sole-source": no official statistic exists; feeds the RES-5 new-stream phase.
# "expenditure": HIES records rupees, not physical quantity (questionnaire prints no unit).
ROLES = {
    "firewood": "primary",
    "natural_gas": "diagnostic-expenditure",
    "lpg": "diagnostic",
    "kerosene": "diagnostic",
    "dung_cake": "primary",
    "charcoal": "sole-source",
    "coal": "sole-source",
    "electricity": "expenditure",
    "generator_fuel": "sole-source-expenditure",
    "agricultural_waste": "sole-source-expenditure",
    "cotton_sticks": "sole-source-expenditure",
}


def _read(name):
    return read_rows(asset_path(HIES_DIR, name), comments=False)


def national_rows(survey=CURRENT):
    return [r for r in _read("hies_national_totals.csv") if r["survey"] == survey]


def national_quantity(fuel, survey=CURRENT):
    """(annual quantity, unit) for a physical-quantity fuel; raises on expenditure items."""
    for r in national_rows(survey):
        if r["fuel"] == fuel:
            if r["kind"] != "quantity":
                raise ValueError("%s is an expenditure-only HIES item (%s); it has no "
                                 "physical quantity" % (fuel, r["unit"]))
            return float(r["annual_total"]), r["unit"]
    raise KeyError("no HIES row for %r in %s" % (fuel, survey))


def users_share(fuel, survey=CURRENT):
    for r in national_rows(survey):
        if r["fuel"] == fuel:
            return float(r["users_share"])
    raise KeyError("no HIES row for %r in %s" % (fuel, survey))


def strata_shares(fuel, survey=CURRENT):
    """{(province, urban|rural): share of the national annual total} - sums to 1.

    The distribution layer: how a fuel's national quantity spreads over province and
    urban/rural strata. Works for expenditure items too (shares of rupees are still a
    usable spatial distribution where no physical quantity exists).
    """
    rows = [r for r in _read("hies_fuel_quantities.csv")
            if r["survey"] == survey and r["fuel"] == fuel]
    total = sum(float(r["annual_total"]) for r in rows)
    if not total:
        raise KeyError("no HIES strata rows for %r in %s" % (fuel, survey))
    return {(r["province"], r["region"]): float(r["annual_total"]) / total
            for r in rows}


def diagnostics(fuel, survey=CURRENT):
    """The survey diagnostics row for one fuel: n reporting households, weighted
    users, per-user-per-day quantity, stratum-clustered design SE, top-1%/5% outlier
    concentration, interview-quarter coverage - the numbers that make a
    design-weighted total checkable rather than assertable."""
    for r in _read("hies_diagnostics.csv"):
        if r["survey"] == survey and r["fuel"] == fuel:
            return r
    raise KeyError("no diagnostics row for %r in %s" % (fuel, survey))


def firewood_air_dry_kg(survey=CURRENT):
    """The sector's PRIMARY firewood activity: HIES air-dry kg entering households."""
    qty, unit = national_quantity("firewood", survey)
    assert unit == "kg"
    return qty


def sole_source_kg(fuel, survey=CURRENT):
    """Charcoal or coal: the survey is the only national quantity there is."""
    if ROLES[fuel] != "sole-source":
        raise ValueError("%s is not a sole-source quantity fuel" % fuel)
    qty, unit = national_quantity(fuel, survey)
    assert unit == "kg"
    return qty


def value_annual_rs(fuel, survey=CURRENT):
    """Weighted annual rupee value of an item, all four routes (own-produced and gifted
    consumption carries PBS's imputed value, so this is not purchase spending alone)."""
    for r in national_rows(survey):
        if r["fuel"] == fuel:
            return float(r["value_annual_rs"])
    raise KeyError("no HIES row for %r in %s" % (fuel, survey))


def unit_value_rs(fuel, survey=CURRENT):
    """Rs per physical unit, value over quantity from the same weighted households.
    Meaningful only where n is healthy - firewood 22.9 Rs/kg and LPG 260.6 Rs/kg land on
    retail reality; the 116-household kerosene item implies Rs 35/l against a Rs ~240
    market and is recorded as unusable."""
    qty, _unit = national_quantity(fuel, survey)
    return value_annual_rs(fuel, survey) / qty


def residue_implied_range_kg(survey=CURRENT):
    """(low, high) air-dry kg/yr implied by the residue expenditure items - a DIAGNOSTIC.

    The residue items (agricultural waste + cotton sticks) are value-only, so a quantity
    needs a price the survey does not record for them. Two survey-internal prices bound
    it: firewood's 22.9 Rs/kg (residues cannot cost more than the fuel they substitute
    for; implies the LOW quantity) and dung cake's 7.3 Rs/kg (the cheapest biomass the
    survey prices; implies the HIGH quantity). The residue STREAM does not use either -
    it rides the agriculture residue ledger, and the test asserts the ledger quantity
    falls inside this bracket."""
    value = value_annual_rs("agricultural_waste", survey) \
        + value_annual_rs("cotton_sticks", survey)
    return value / unit_value_rs("firewood", survey), \
        value / unit_value_rs("dung_cake", survey)


def generator_fuel_litres(data, survey=CURRENT):
    """HIES generator-fuel expenditure over the administered petrol price, litres/yr."""
    return value_annual_rs("generator_fuel", survey) / data.p("petrol_price_rs_l")


def r_dung(data, agri=None):
    """Ledger air-dry cake mass over the cake the 2024-25 round reports, about 4.9.

    A DIAGNOSTIC RATIO between two published quantities: what agriculture diverts and
    what one survey round observes households burning. Through rc66 it was "published,
    never applied" because the ledger kept control of the residential quantity. Since
    rc67 the survey does (on its two-round series, see combustion.dung_air_dry_kg), and
    this ratio is the size of the diverted mass that has no household destination."""
    from pkinv.sectors.residential import combustion
    hies_kg, unit = national_quantity("dung_cake")
    assert unit == "kg"
    return combustion.dung_air_dry_kg(data, agri, basis="ledger") / hies_kg


def comparison_rows(data, agri=None):
    """The published survey-versus-control table, one row per HIES fuel item.

    ratio = HIES quantity / engine quantity on a matched basis, blank where the survey
    records only expenditure or where no engine stream exists yet.
    """
    from pkinv.sectors.residential import combustion

    hies = {r["fuel"]: r for r in national_rows()}
    prev = {r["fuel"]: r for r in national_rows("hies2019")}
    moist = data.p("firewood_moisture_ar")
    faostat_air_dry = combustion.woodfuel_dry_matter_kg(data) / (1.0 - moist)
    engine = {
        "firewood": (firewood_air_dry_kg(), "kg",
                     "HIES IS the estimate; ratio shown against FAOSTAT's "
                     "moisture-matched air-dry equivalent",
                     firewood_air_dry_kg() / faostat_air_dry),
        "dung_cake": (combustion.dung_air_dry_kg(data, agri), "kg",
                      "the HIES rounds ARE the estimate (interpolated per household to "
                      "the reference year); ratio shown against the dung agriculture "
                      "diverts, air-dry basis - r_dung inverted, the part of the "
                      "diverted supply households are observed burning",
                      national_quantity("dung_cake")[0]
                      / combustion.dung_air_dry_kg(data, agri, basis="ledger")),
        "lpg": (data.quantity("Liquefied Petroleum Gases")
                * data.p("lpg_domestic_share") * 1000.0, "kg",
                "OGRA domestic LPG", None),
        "kerosene": (data.quantity("Other Kerosene") * 1e6
                     / data.p("kerosene_density_kg_l"), "litre",
                     "OCAC DOMESTIC kerosene (litres via density). The survey's 2.5x "
                     "excess rides 116 outlier-heavy households (0.3 percent users) "
                     "whose implied unit value is a fifth of retail - unusable as "
                     "evidence in either direction", None),
    }
    rows = []
    for fuel, role in ROLES.items():
        h = hies.get(fuel)
        if h is None:
            continue
        row = {"fuel": fuel, "role": role, "unit": h["unit"],
               "hies2425_annual": float(h["annual_total"]),
               "hies2425_users_share": float(h["users_share"]),
               "hies1819_annual":
                   float(prev[fuel]["annual_total"]) if fuel in prev else "",
               "engine_annual": "", "ratio_hies_over_engine": "", "note": ""}
        if fuel in engine:
            eng, unit, note, ratio = engine[fuel]
            assert unit == h["unit"], fuel
            row["engine_annual"] = round(eng)
            row["ratio_hies_over_engine"] = round(
                ratio if ratio is not None else float(h["annual_total"]) / eng, 3)
            row["note"] = note
        elif role == "sole-source":
            row["engine_annual"] = round(float(h["annual_total"]))
            row["ratio_hies_over_engine"] = 1.0
            row["note"] = ("survey IS the estimate; no supply-side statistic exists "
                           "(OGRA's household coal row is nil)")
        elif fuel in ("agricultural_waste", "cotton_sticks"):
            row["note"] = ("rupee expenditure only; the engine's residue stream rides "
                           "the agriculture ledger, and the price-implied bracket from "
                           "these values (firewood-priced low, dung-priced high) must "
                           "contain it - see residue_implied_range_kg and the test")
        elif fuel == "generator_fuel":
            row["note"] = ("rupee expenditure over the administered petrol price IS the "
                           "engine's generator stream; the mass is deducted from the "
                           "road petrol control with equality asserted")
        else:
            row["note"] = "rupee expenditure only; no physical quantity in HIES"
        rows.append(row)
    return rows

"""The air-pollutant emission-factor register, loaded and converted (rc58 W1).

data/air_emission_factors.csv holds every factor AS ITS SOURCE PRINTS IT - lb per thousand
gallons of No. 6 oil, lb per million standard cubic feet at 1,020 Btu/scf, g/GJ on the net
calorific basis, kg per tonne of clinker, g per kg of fired brick - with the document, table,
page and digest beside it. Nothing is pre-converted in the register, because a converted number
cannot be checked against its page. This module does the conversion, once, in the open:

    kg_per_unit(row)  ->  (kg of pollutant per ACTIVITY UNIT, the unit's name)

where the activity unit is the one the row's activity_basis names - TJ on the NCV basis
(energy_ncv), TJ on the HHV basis (energy_hhv), tonnes of fuel (fuel_mass), tonnes of fired
product (product_mass_brick), tonnes of clinker (clinker_mass) - and the caller supplies that
quantity from the engine's own activity. Two rows are not factors: pm25_share rows (BC as a
percentage of the class's PM2.5) and the sulfur_balance row (2 kg SO2 per kg S, applied by
pkinv.core.sulfur with the class's dated sulfur evidence).

FAIL-CLOSED: factor(ef_id) raises on an unknown id; a status=absent row has no value and
raises if a caller tries to price with it - it exists to be cited as a typed absence, never
multiplied. A held row missing its page or digest fails at load.

Ratings map to one declared uncertainty (A 15 %, B 30 %, C 50 %, D 75 %, E 100 %) where the
source prints a rating and no interval; rows with a printed 95 % interval carry its half-width.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.units import TJ_PER_MMBTU
from pkinv.paths import DATA

REGISTER = asset_path(DATA, "air_emission_factors.csv")

KG_PER_LB = 0.45359237
TONNE_PER_SHORT_TON = 0.90718474
AP42_GAS_BTU_PER_SCF = 1020.0        # AP-42 1.4 factors are stated at this HHV (table note a)
KG_PER_KGAL = {"no6": 3750.0,        # 3.75 kg/gal, residual oil at 15 C (power.air_pollutants)
               "no2": 3220.0}        # 7.1 lb/gal distillate (AP-42 3.4-1 note a)

RATING_UNCERT = {"A": 15.0, "B": 30.0, "C": 50.0, "D": 75.0, "E": 100.0}

BASES = ("energy_ncv", "energy_hhv", "fuel_mass", "product_mass_brick", "clinker_mass",
         "pm25_share", "sulfur_balance",
         "product_mass",        # rc59: per tonne of product handled or made (NH3, urea, steel, soda ash, crude, gasoline, flared gas)
         "gas_volume",          # rc59: per volume of gas produced, processed, transported or distributed
         "oil_volume")          # rc59: per volume of oil handled
STATUSES = ("held", "transcribed", "absent")


class UnknownFactor(KeyError):
    pass


class AbsentFactor(ValueError):
    """A typed-absence row was asked to price something."""


def _rows():
    return list(_activity_rows(REGISTER, comments=True))


def load():
    """{ef_id: row}, validated: closed vocabularies, and every held row names a page and a
    digest (a factor nobody can find again is not a factor)."""
    out = {}
    for r in _rows():
        if r["ef_id"] in out:
            raise ValueError("duplicate ef_id %s" % r["ef_id"])
        if r["activity_basis"] not in BASES:
            raise ValueError("%s: activity_basis %r not in %s" % (r["ef_id"], r["activity_basis"], BASES))
        if r["status"] not in STATUSES:
            raise ValueError("%s: status %r" % (r["ef_id"], r["status"]))
        if r["status"] == "absent":
            if r["value"] != "" or not r["gap_id"] or not r["note"]:
                raise ValueError("%s: an absent row carries no value and must name a gap and a reason"
                                 % r["ef_id"])
        else:
            if r["value"] == "":
                raise ValueError("%s: a held row without a value" % r["ef_id"])
            if r["activity_basis"] != "sulfur_balance" and (not r["source_page"] or not r["source_sha256"]):
                raise ValueError("%s: a held factor must cite its page and its document digest" % r["ef_id"])
        out[r["ef_id"]] = r
    return out


_CACHE = None


def factor(ef_id):
    global _CACHE
    if _CACHE is None:
        _CACHE = load()
    try:
        return _CACHE[ef_id]
    except KeyError:
        raise UnknownFactor("no emission factor %r in %s" % (ef_id, os.path.relpath(REGISTER)))


def uncert_pct(row):
    return float(row["uncert_pct"]) if row["uncert_pct"] != "" else RATING_UNCERT[row["rating"]]


def kg_per_unit(row):
    """(kg pollutant per activity unit, unit name). The activity unit follows activity_basis:
    'TJ_ncv', 'TJ_hhv', 't_fuel', 't_brick', 't_clinker', 't_product', 'e3m3_gas', 'm3_oil'.
    Sulfur- or ash-scaled rows return
    the coefficient PER WEIGHT-PERCENT (the caller multiplies by the class's evidence)."""
    if row["status"] == "absent":
        raise AbsentFactor("%s is a typed absence (%s); it cannot price anything" % (row["ef_id"], row["gap_id"]))
    v = float(row["value"])
    u = row["unit_original"]
    if u == "g/GJ_ncv":
        return v, "TJ_ncv"                                   # g/GJ == kg/TJ
    if u in ("g/Mg_clinker",):
        return v / 1000.0, "t_clinker"
    if u == "kg/Mg_clinker":
        return v, "t_clinker"
    if u in ("g/Mg_brick",):
        return v / 1000.0, "t_brick"
    if u == "g/kg_brick":
        return v, "t_brick"                                  # g/kg == kg/t
    if u == "lb/short_ton_brick":
        return v * KG_PER_LB / TONNE_PER_SHORT_TON, "t_brick"
    if u.startswith("lb/short_ton_coal"):
        return v * KG_PER_LB / TONNE_PER_SHORT_TON, "t_fuel"
    if u == "lb/MMscf_hhv1020":
        return v / AP42_GAS_BTU_PER_SCF * KG_PER_LB / TJ_PER_MMBTU, "TJ_hhv"
    if u == "lb/MMBtu_hhv":
        return v * KG_PER_LB / TJ_PER_MMBTU, "TJ_hhv"
    if u.startswith("lb/kgal_no6"):
        return v * KG_PER_LB / (KG_PER_KGAL["no6"] / 1000.0), "t_fuel"
    if u.startswith("lb/kgal_no2"):
        return v * KG_PER_LB / (KG_PER_KGAL["no2"] / 1000.0), "t_fuel"
    if u in ("g/Mg_product", "g/t_product"):
        return v / 1000.0, "t_product"                       # rc59 process and handling rows
    if u in ("kg/Mg_product", "kg/t_product"):
        return v, "t_product"
    if u == "g/m3_gas":
        return v, "e3m3_gas"                                 # g/m3 == kg per thousand m3
    if u == "kg/1000m3_gas":
        return v, "e3m3_gas"
    if u == "kg/m3_oil":
        return v, "m3_oil"
    if u == "g/m3_oil":
        return v / 1000.0, "m3_oil"
    if u == "pct_of_PM2.5":
        return v / 100.0, "share_of_PM2.5"
    if u == "kg_SO2_per_kg_S":
        return v, "kg_S"
    raise ValueError("%s: no conversion for unit %r" % (row["ef_id"], u))


def scaled_per_pct(row):
    """'S' or 'A' if the row's coefficient is per weight-percent sulfur or ash, else ''."""
    if row["sulfur_scaling"] == "per_pct_S":
        return "S"
    if row["ash_scaling"] == "per_pct_ash":
        return "A"
    return ""

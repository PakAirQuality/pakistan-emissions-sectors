"""Agriculture's factor parameters, named at last (rc18, the twelfth review).

WHY THIS EXISTS. 61 of the 75.4 points of unnamed national variance were
agriculture's residual alone - not because the sector's uncertainties were
undeclared, but because they were declared INSIDE each component's uncert_pct
(product(activity, factor, ...) in the engine) where the parameter registry
could not see them. Agriculture was the one sector with no uncertainty-inputs
table: its activity counts were named (livestock:*, crop:*, fertiliser:*
through core.parameters.ACTIVITY_FILES) and its factors were nobody's.

NO NEW NUMBERS. Every row below is read from data/emission_factors.csv - the
same table, the same values, the same uncertainties the engine composes into
each component's declared width. This module only gives those quantities NAMES
the registry parses (core.parameters.from_sector_inputs), scope rows bind them
to the components that carry them, and the variance attribution can then say
"EF1" instead of "residual:agriculture".

THE GROUPS CARRY THE PHYSICS. soils_EF1_dry is ONE parameter across the three
direct-N2O rows that multiply it; EF4 is one parameter across every
volatilisation row INCLUDING manure management's (manure.py harmonises on the
managed-soils EF4 explicitly); EF5 across every leaching row. The per-species
enteric and manure-CH4 factors are separate parameters - one species' default
being wrong says nothing about another's. Group ids carry the `ef:` prefix so
the longitudinal ensemble's prefix typing reads them as `persists` (a biased
IPCC default is biased in every year) without a hand-written type entry each.

ONE ENGINE QUIRK, recorded not repaired: manure.py:93 applies the sheep row's
30 percent to EVERY species' manure-CH4 factor ("all manure CH4 EFs ~30%"),
including camels whose own table row says 40. The parameter rows below carry
the width the ENGINE composes - naming the table's 40 would over-explain the
declared row variance and force a reconciliation entry for arithmetic the
engine never did.

Usage:  python3 -m pkinv.sectors.agriculture.uncertainty_inputs
Writes: outputs/agriculture_uncertainty_inputs_2024.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.core.io import write_table

OUT = asset_path(OUTPUTS, "agriculture_uncertainty_inputs_2024.csv")

FIELDS = ("variable", "input_type", "central_value", "uncert_pct_95", "unit",
          "distribution", "correlation_group", "applies_to", "source", "note")

# (variable, ef_category, ef_item, group, engine_uncert_override, applies_to)
# engine_uncert_override: None reads the table's width; a number records the
# width the engine actually composes where the two differ (the manure quirk).
CONSUMED = (
    ("enteric_ef_dairy_cattle", "enteric", "dairy_cattle",
     "ef:enteric_dairy_cattle", None, "Enteric fermentation / dairy_cattle"),
    ("enteric_ef_other_cattle", "enteric", "other_cattle",
     "ef:enteric_other_cattle", None, "Enteric fermentation / other_cattle"),
    ("enteric_ef_buffalo", "enteric", "buffalo",
     "ef:enteric_buffalo", None, "Enteric fermentation / buffalo"),
    ("enteric_ef_sheep", "enteric", "sheep",
     "ef:enteric_sheep", None, "Enteric fermentation / sheep"),
    ("enteric_ef_goats", "enteric", "goats",
     "ef:enteric_goats", None, "Enteric fermentation / goats"),
    ("enteric_ef_camels", "enteric", "camels",
     "ef:enteric_camels", None, "Enteric fermentation / camels"),
    ("manure_ch4_ef_dairy_cattle", "manure_ch4", "dairy_cattle_warm",
     "ef:manure_ch4_dairy_cattle", 30.0, "Manure management / dairy_cattle (CH4)"),
    ("manure_ch4_ef_other_cattle", "manure_ch4", "other_cattle_warm",
     "ef:manure_ch4_other_cattle", 30.0, "Manure management / other_cattle (CH4)"),
    ("manure_ch4_ef_buffalo", "manure_ch4", "buffalo_warm",
     "ef:manure_ch4_buffalo", 30.0, "Manure management / buffalo (CH4)"),
    ("manure_ch4_ef_sheep", "manure_ch4", "sheep",
     "ef:manure_ch4_sheep", None, "Manure management / sheep (CH4)"),
    ("manure_ch4_ef_goats", "manure_ch4", "goats",
     "ef:manure_ch4_goats", 30.0, "Manure management / goats (CH4)"),
    ("manure_ch4_ef_camels", "manure_ch4", "camels",
     "ef:manure_ch4_camels", 30.0,
     "Manure management / camels (CH4) - the engine applies the sheep row's 30, "
     "not this row's own 40 (manure.py:93)"),
    ("manure_ch4_ef_poultry", "manure_ch4", "poultry",
     "ef:manure_ch4_poultry", 30.0, "Manure management / poultry (CH4)"),
    ("manure_n2o_ef3", "manure_n2o_ef3", "solid_storage",
     "ef:manure_n2o_ef3", None,
     "Manure management / Direct N2O - every system row carries 100"),
    ("soils_EF1_dry", "soils", "EF1_dry", "ef:soils_EF1_dry", None,
     "Managed soils direct N2O: synthetic upland, organic manure, crop "
     "residues - ONE parameter across all three"),
    ("soils_EF1FR_rice", "soils", "EF1FR_rice", "ef:soils_EF1FR_rice", None,
     "Managed soils / Direct N2O - synthetic fertiliser (rice)"),
    ("soils_EF3PRP_cattle", "soils", "EF3PRP_cattle",
     "ef:soils_EF3PRP_cattle", None,
     "Managed soils / pasture deposition (cattle-type)"),
    ("soils_EF3PRP_sheepgoat", "soils", "EF3PRP_sheepgoat",
     "ef:soils_EF3PRP_sheepgoat", None,
     "Managed soils / pasture deposition (sheep/goat)"),
    ("soils_EF4_dry", "soils", "EF4_dry", "ef:soils_EF4_dry", None,
     "EVERY volatilisation row: the four managed-soils indirect rows and "
     "manure management's indirect N2O, which harmonises on this same factor "
     "(manure.py)"),
    ("soils_EF5", "soils", "EF5", "ef:soils_EF5", None,
     "every managed-soils leaching/runoff row"),
    ("rice_EFc", "rice", "EFc", "ef:rice_EFc", None,
     "Rice cultivation / Continuously flooded"),
    ("rice_SFw_continuous", "rice", "SFw_continuous",
     "ef:rice_SFw_continuous", None,
     "Rice cultivation / Continuously flooded (water-regime scaling)"),
    # The combustion factor is DELIBERATELY NOT NAMED on the burning rows: the
    # five crop activity groups are each scoped in full onto rows whose declared
    # width composes ONE mass-weighted joint activity term, so the graph already
    # over-counts the activity side, and naming the burned fraction too would
    # push the recomposition past the declared width and force the graph
    # authoritative over a row whose own arithmetic is right. It stays residual.
    ("burning_Gef_CH4", "burning", "Gef_CH4", "ef:burning_Gef_CH4", None,
     "Field burning / Residue burning CH4"),
    ("burning_Gef_N2O", "burning", "Gef_N2O", "ef:burning_Gef_N2O", None,
     "Field burning / Residue burning N2O"),
    # rc39 A4: the limestone factor's row is gone with the component it described. 3.G is
    # NE and emits nothing, so an uncertainty input for it would be an uncertainty about a
    # number this inventory does not publish.
    ("liming_EF_urea", "liming_urea", "EF_urea", "ef:liming_EF_urea", None,
     "Urea application / Urea application CO2"),
)


def _ef_table():
    out = {}
    for r in _activity_rows(asset_path(DATA, "emission_factors.csv"), comments=False):
        out[(r["category"], r["item"])] = r
    return out


def build():
    table = _ef_table()
    rows = []
    for variable, cat, item, group, override, applies in CONSUMED:
        ef = table[(cat, item)]
        width = float(ef["uncert_pct"]) if override is None else override
        note = ""
        if override is not None and override != float(ef["uncert_pct"]):
            note = ("engine width %s differs from the table row's %s - the "
                    "engine's composition is what the declared component "
                    "variance holds (see module docstring)"
                    % (override, ef["uncert_pct"]))
        rows.append({
            "variable": variable,
            "input_type": "emission_factor",
            "central_value": ef["value"],
            "uncert_pct_95": width,
            "unit": ef["unit"],
            "distribution": "lognormal",
            "correlation_group": group,
            "applies_to": applies,
            "source": ef["source"],
            "note": note,
        })
    return rows


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = build()
    write_table(OUT, list(FIELDS), rows, banner=("# AGRICULTURE'S FACTOR PARAMETERS, NAMED (rc18): the same values and widths the engine composes into each component's uncert_pct, read from data/emission_factors.csv and given registry-visible names.", '# No new numbers. Scope rows in data/parameter_scope.csv bind each group to the components that carry it; the ef: prefix types every group `persists` in the longitudinal ensemble.',))
    print("agriculture uncertainty inputs -> %s (%d named factor parameters, "
          "%d shared groups)"
          % (os.path.basename(OUT), len(rows),
             sum(1 for r in rows if "ONE parameter" in r["applies_to"]
                 or "EVERY" in r["applies_to"] or "every" in r["applies_to"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

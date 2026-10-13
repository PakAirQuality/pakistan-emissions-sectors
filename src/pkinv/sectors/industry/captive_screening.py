"""The non-gas captive fleet (1.A.2): the register-sized bracket, one fuel at a time.

WHY (Wave 4). The 1A2 fuel ledger's solid tier carries two claimants marked `neither`
- no screening and no control - and one of them is the captive fleet burning solids:
plants the register itself sizes (the completeness row counts them beside 1,294 MW of
estimated gas) with not one metered tonne of fuel among them. This module prices what
the register's own capacity supports, under a DECLARED utilization and heat-rate
bracket, and refuses the rest by name.

THE SCOPE IS DELIBERATELY NARROW, and each exclusion is a row:

- CAPTIVE COAL is the priced stream. Its fuel is bought coal that no held control
  covers: the OCAC petroleum classes carry no coal, the PEY brick-kiln series is a
  different population, and the power module's captive control is gas-only. The
  bracket is the screening.
- CAPTIVE FURNACE OIL AND DIESEL are NOT priced, to avoid a double-count this module
  cannot resolve: their fuel is bought from the same retail/industrial oil market the
  OCAC Total Industry rows already book into the estimated industrial-liquids
  category. Whether a captive engine's FO sits inside that control is exactly the
  per-class split the HDIP commercial energy balance would resolve; pricing it here
  would risk counting it twice.
- CAPTIVE BAGASSE is NOT priced here because the bagasse all-cane CEILING
  configuration already burns the entire crop's bagasse - any captive bagasse plant
  is a sub-claimant of that ceiling, and adding it on top would double-claim the
  same stalks.
- NON-BAGASSE BIOMASS gets a CH4+N2O bound (biogenic CO2 is outside every total by
  construction) - small, and published so the reader sees it bounded rather than
  unexamined.
- SELF-PRODUCED PROCESS GASES (one steel works' blast-furnace/coke-oven gas train)
  are refused: pricing them needs the works' own gas balance, not a capacity guess.
- Solar, hydel, wind, biogas and waste-heat entries burn nothing and are excluded
  arithmetically, not silently.

THE BRACKET IS A DECLARED JUDGEMENT, stated on every row that uses it: no Pakistani
captive-utilization statistic is published anywhere the acquisition campaigns have
reached, so the capacity factor spans seasonal-duty to baseload-process operation
[0.2, 0.7] and the heat rate spans modern engine to older steam sets [9, 12] MJ/kWh.
This is the kiln-intensity pattern - the unheld quantity is the bracket, the bracket
outranks every factor CI, and the row says which acquisition would collapse it
(NEPRA's captive licensing returns carry annual generation; REQ-NEPRA-02).

FUEL ATTRIBUTION RULE. The register's industry_fuel strings are multi-fuel
("FO/GAS", "BAGASSE/BIOMASS/FO"); a plant's capacity is attributed to its
FIRST-LISTED fuel - the register's own primary-fuel convention - and the attribution
counts are published so the rule is auditable. Gas-hybrid plants' metered gas is
inside the power module's captive control either way; what is screened here is
primary-fuel operation only.

Usage:  written by run_industry on every run; also
        python3 -m pkinv.sectors.industry.captive_screening
Writes: outputs/industry_captive_screening_2024.csv
"""
from __future__ import annotations

from pkinv.assets import asset_path

from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.core.io import write_table

REGISTER = asset_path(DATA, "activity", "power", "captive_register.csv")
OUT = asset_path(OUTPUTS, "industry_captive_screening_2024.csv")

# Screening-only constants, cited; deliberately not in any factor registry (the
# category is outside every total). Combustion factors: IPCC 2006 Vol 2 Ch 2
# Table 2.3 (manufacturing/construction).
CF_BRACKET = (0.2, 0.7)          # declared judgement; see module docstring
HEAT_RATE_MJ_KWH = (9.0, 12.0)   # declared judgement; engine vs older steam sets
COAL_CO2_KG_TJ = 94600.0         # other bituminous, Table 2.3 - the kiln screen's set
BIOMASS_CH4_KG_TJ = 30.0         # solid biomass, Table 2.3
BIOMASS_N2O_KG_TJ = 4.0
GWP_CH4, GWP_N2O = 28.0, 265.0

# Register token -> normalized fuel class. First-listed token decides.
NORMALIZE = {
    "GAS": "gas", "FO": "furnace_oil", "HSD": "diesel", "DIESEL": "diesel",
    "COAL": "coal", "IMPORTED CAOL": "coal", "LOCAL COAL": "coal",
    "BAGASSE": "bagasse", "BIOMASS": "biomass", "BIO MASS": "biomass",
    "BIOGAS": "non_combustion_or_renewable", "SOLAR": "non_combustion_or_renewable",
    "SOLAR RADIATIONS": "non_combustion_or_renewable",
    "HYDEL": "non_combustion_or_renewable", "WIND": "non_combustion_or_renewable",
    "WASTE HEAT EXHAUST FROM THE EXISTING ENGINES": "non_combustion_or_renewable",
    "BLAST FURNACE GAS": "works_process_gas",
    "BLAST FURNACE GAS/COAL TAR/COKE OVEN GAS": "works_process_gas",
}


def _primary_fuel(industry_fuel):
    head = industry_fuel.split("|")[0].strip()
    first = head.split("/")[0].strip().upper()
    return NORMALIZE.get(first, NORMALIZE.get(head.upper(), "unrecognized"))


def fleet():
    """{fuel_class: [capacity_MW, plant_count]} over rows carrying a capacity."""
    out = {}
    for r in _activity_rows(REGISTER, comments=True):
        if not r["capacity_mw"]:
            continue
        fuel = _primary_fuel(r["industry_fuel"])
        slot = out.setdefault(fuel, [0.0, 0])
        slot[0] += float(r["capacity_mw"])
        slot[1] += 1
    if "unrecognized" in out:
        raise SystemExit("captive register carries a fuel string the attribution "
                         "rule does not know: extend NORMALIZE rather than "
                         "letting capacity fall out of the fleet silently")
    return out


def _energy_tj(mw, cf, heat_rate):
    # MW * 8760 h = MWh; * 1000 kWh/MWh * (MJ/kWh) = fuel MJ; / 1e6 = TJ
    return mw * 8760.0 * cf * heat_rate * 1e-3


def rows():
    by_fuel = fleet()
    coal_mw, coal_n = by_fuel.get("coal", (0.0, 0))
    bio_mw, bio_n = by_fuel.get("biomass", (0.0, 0))

    def band(mw, factor_kg_tj):
        lo = _energy_tj(mw, CF_BRACKET[0], HEAT_RATE_MJ_KWH[0]) * factor_kg_tj / 1e9
        hi = _energy_tj(mw, CF_BRACKET[1], HEAT_RATE_MJ_KWH[1]) * factor_kg_tj / 1e9
        return lo, hi

    coal_lo, coal_hi = band(coal_mw, COAL_CO2_KG_TJ)
    bio_factor = BIOMASS_CH4_KG_TJ * GWP_CH4 + BIOMASS_N2O_KG_TJ * GWP_N2O
    bio_lo, bio_hi = band(bio_mw, bio_factor)

    judgement = ("capacity factor %.1f-%.1f and heat rate %.0f-%.0f MJ/kWh are "
                 "DECLARED JUDGEMENTS - no Pakistani captive-utilization statistic "
                 "is published; NEPRA's captive licensing returns (annual "
                 "generation) would collapse the bracket"
                 % (CF_BRACKET + HEAT_RATE_MJ_KWH))
    return [
        {"configuration": "reference", "fuel_class": "",
         "capacity_MW": "", "plants": "", "adjustment_Mt_co2e": 0.0,
         "bracket_low_Mt": "", "bracket_high_Mt": "",
         "status": "reference",
         "note": "the non-gas captive fleet stays NE in the reference; the rows "
                 "below are the register-sized screening and its named exclusions"},
        {"configuration": "captive_coal_in_scope", "fuel_class": "coal",
         "capacity_MW": round(coal_mw, 1), "plants": coal_n,
         "adjustment_Mt_co2e": round(coal_hi, 5),
         "bracket_low_Mt": round(coal_lo, 5), "bracket_high_Mt": round(coal_hi, 5),
         "status": "screening_capacity_bracket",
         "note": "bought coal no held control covers; priced at the bracket TOP, "
                 "the conservative-top convention. " + judgement},
        {"configuration": "(bound, biogenic fuels)", "fuel_class": "biomass",
         "capacity_MW": round(bio_mw, 1), "plants": bio_n,
         "adjustment_Mt_co2e": "",
         "bracket_low_Mt": round(bio_lo, 5), "bracket_high_Mt": round(bio_hi, 5),
         "status": "bounded_small_ch4_n2o_only",
         "note": "non-bagasse biomass: biogenic CO2 is outside every total by "
                 "construction, so the countable gases are CH4+N2O - bounded "
                 "small, the bagasse pattern. " + judgement},
        {"configuration": "(excluded, double-count risk)",
         "fuel_class": "furnace_oil+diesel",
         "capacity_MW": round(by_fuel.get("furnace_oil", (0, 0))[0]
                              + by_fuel.get("diesel", (0, 0))[0], 1),
         "plants": (by_fuel.get("furnace_oil", (0, 0))[1]
                    + by_fuel.get("diesel", (0, 0))[1]),
         "adjustment_Mt_co2e": "", "bracket_low_Mt": "", "bracket_high_Mt": "",
         "status": "excluded_possible_IE",
         "note": "captive FO/diesel buy from the same market the OCAC Total "
                 "Industry rows already book into the estimated "
                 "industrial-liquids category; whether a given engine's fuel is "
                 "inside that control is the per-class split only the HDIP "
                 "commercial energy balance resolves, so pricing it here would "
                 "risk a double-count - possibly included elsewhere, not "
                 "unexamined"},
        {"configuration": "(excluded, sub-claimant)", "fuel_class": "bagasse",
         "capacity_MW": round(by_fuel.get("bagasse", (0, 0))[0], 1),
         "plants": by_fuel.get("bagasse", (0, 0))[1],
         "adjustment_Mt_co2e": "", "bracket_low_Mt": "", "bracket_high_Mt": "",
         "status": "excluded_inside_existing_ceiling",
         "note": "the bagasse all-cane CEILING configuration already burns the "
                 "entire crop's bagasse; captive bagasse power is a sub-claimant "
                 "of that ceiling and adding it here would double-claim the same "
                 "stalks"},
        {"configuration": "(refused)", "fuel_class": "works_process_gas",
         "capacity_MW": round(by_fuel.get("works_process_gas", (0, 0))[0], 1),
         "plants": by_fuel.get("works_process_gas", (0, 0))[1],
         "adjustment_Mt_co2e": "", "bracket_low_Mt": "", "bracket_high_Mt": "",
         "status": "refused_needs_works_balance",
         "note": "one steel works' blast-furnace/coke-oven gas train: its carbon "
                 "is the works' own coal and coke inputs, and pricing it needs "
                 "the works' gas balance, not a capacity guess - a capacity "
                 "bracket would claim precision the fuel chemistry does not "
                 "support"},
        {"configuration": "(excluded, non-combustion)",
         "fuel_class": "non_combustion_or_renewable",
         "capacity_MW": round(by_fuel.get("non_combustion_or_renewable",
                                          (0, 0))[0], 1),
         "plants": by_fuel.get("non_combustion_or_renewable", (0, 0))[1],
         "adjustment_Mt_co2e": "", "bracket_low_Mt": "", "bracket_high_Mt": "",
         "status": "excluded_nothing_burns",
         "note": "solar, hydel, wind, biogas and waste-heat capacity: excluded "
                 "arithmetically, not silently"},
        {"configuration": "(register context)", "fuel_class": "gas",
         "capacity_MW": round(by_fuel.get("gas", (0, 0))[0], 1),
         "plants": by_fuel.get("gas", (0, 0))[1],
         "adjustment_Mt_co2e": "", "bracket_low_Mt": "", "bracket_high_Mt": "",
         "status": "estimated_elsewhere",
         "note": "the gas-primary fleet with labelled capacity, for scale; the "
                 "metered gas control (power module, 5.55 Mt) covers captive gas "
                 "regardless of the capacity label, which most gas plants lack"},
    ]


FIELDS = ("configuration", "fuel_class", "capacity_MW", "plants",
          "adjustment_Mt_co2e", "bracket_low_Mt", "bracket_high_Mt", "status",
          "note")


def main():
    out = rows()
    write_table(OUT, list(FIELDS), out, banner=('# The non-gas captive fleet: register-sized screening bracket and', '# named exclusions; the categories stay NE in the reference. See', '# captive_screening.py.',), lineterminator="\n")
    print("captive non-gas screening -> %s" % OUT)
    for r in out:
        print("  %-34s %-22s %8s MW  %s" % (r["configuration"][:34],
                                            r["fuel_class"], r["capacity_MW"],
                                            r["adjustment_Mt_co2e"]
                                            or r["bracket_high_Mt"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

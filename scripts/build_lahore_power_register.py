"""LAHORE DISTRICT'S GRID POWER UNITS, on the generation route.

WHY THIS EXISTED, AND WHAT IT IS NOW. This table was written when
outputs/pakemis_air_lahore_by_year.csv carried no power row in any of the nine periods, because
outputs/pakemis_air_coverage_matrix.csv typed power SO2 `NE`. It argued that the refusal was
defensible for a national coal fleet and much weaker for Lahore, and it measured the difference.

The argument was taken. rc60 admitted the oil and diesel fleet on a reviewed national register
(data/activity/power/power_so2_admission.csv) and rc61 placed it, so **Lahore publishes a power
SO2 row**: 10.981 Gg at FY2015-16 falling to 2.383 at FY2023-24, all of it Kohinoor Energy.
(Those read 4.842 and 1.051 until rc63, when the retired power sulfur row was merged into
fo_hsfo_grade_mix and the fleet moved from 1.3229 to 3.0 percent sulfur - see below.)

So this file is no longer the measure of an absence. It is the GENERATION-ROUTE view beside the
register's - generation x heat rate x sulfur balance, where the register prefers a metered fuel
quantity wherever NEPRA prints one - and the two agree on the early years by construction and
part on the ledger years, which is the informative half. THE PANEL IS FED BY THE REGISTER, NOT
BY THIS FILE; tests/test_power_plant_workbooks.py asserts that directly.

sources/Power Plants/power_plants_data_preparation.xlsx places THREE grid stations inside Lahore
District - the Raiwind cluster that scripts/ingest_grid_plant_coordinates.py left `unresolved`
because its rung 2b could only confirm the province. One of them, Kohinoor Energy, has twelve
months of generation in all nine fiscal years in this repository's own
data/activity/power/generation_monthly.csv (reached through plant_name_crosswalk.csv, which maps
its three panel spellings onto one canonical plant), a measured net heat rate in
plant_heat_rates.csv, and burns residual fuel oil.

THE ESTIMATE IS THIS REPOSITORY'S OWN CHAIN, NOT THE WORKBOOK'S FACTOR:

    generation [GWh] x heat rate [Btu/kWh]  ->  fuel energy [TJ]
    fuel energy / NCV [TJ/Gg]               ->  fuel mass [Gg]
    core.sulfur.so2_kt(mass, S, oxidised, retention)  ->  SO2 [Gg]

The workbook's own number (activity x a literature kg/MWh factor) is carried beside it as a
cross-check, never as the estimate. The ratio is ~0.44 and that is informative rather than
alarming: divide the workbook's emission by this chain's fuel mass and by AP-42's per-%S factor
and the sulfur the workbook ASSUMED comes back as 3.03 % on every year - Pakistan's regulatory
ceiling. The two methods therefore agree on the activity exactly and part only on the fuel
quality, by a stated and measurable amount. tests/test_power_plant_workbooks.py asserts that
decomposition, which is a real check; the old "they agree within a quarter" was not, because both
sides were then carrying the same ceiling.

WHAT IS ASSUMED, AND SAID PER ROW:
  heat rate      published FY2018-19..FY2022-23 and identical in all five (7986.85 net Btu/kWh,
                 an LHV figure per the source's own footnote). Earlier and later years carry it
                 as a DECLARED CONSTANT, flagged in heat_rate_basis. It is not measured there.
  NCV            the IPCC default 40.4 TJ/Gg for residual fuel oil, which is what
                 data/power_params.csv already names as the ledger's RFO basis.
  sulfur         fo_hsfo_grade_mix: 3.0 % central, band 1.0-3.5, basis `regulatory_max`,
                 from data/power_fuel_quality.csv's Pakistani residual-fuel-oil specifications.
                 THIS IS A SPECIFICATION SPAN, NOT AN ASSAY - no cargo was measured - but it is
                 fo_hsfo_grade_mix (3.0 %, `regulatory_max`). THIS ENTRY ARGUED THE OPPOSITE
                 UNTIL rc63 and the reversal is kept rather than overwritten. It read: power
                 should use "the power sector's own fuel rather than a borrowed one", because
                 fo_hsfo_grade_mix "names industrial classes only" and its value "is a CEILING;
                 that borrow put Kohinoor FY2015-16 at 10.98 Gg where this row puts it at 4.60, a
                 factor of 2.4 resting entirely on reading a legal maximum as a mean."
                 The objection was sound in shape and wrong in fact. What it defended,
                 power_rfo_spec_range at 1.3229 %, was the unweighted geometric middle of a
                 0.5-3.5 specification span - a midpoint, not a measurement of power's own fuel.
                 The furnace-oil import grade split transcribed at item 3
                 (data/activity/industry/furnace_oil_grade_mix.csv) shows the national pool running
                 85.3-100 % HIGH-sulphur grade, so it sits near the top of that span rather than
                 its middle. One national fuel cannot carry two centrals; the power row was
                 retired and these classes joined the industry row. Independent corroboration
                 arrived from this file's own cross-check: the workbook's 12 kg/MWh carried through
                 the heat rates implies 2.877 % sulfur, 4.1 % below the adopted 3.0 and 117 % above
                 the retired 1.3229.
  factor         ap42_1.3_no6_so2_157S, rating A, for No. 6 oil in a boiler. It carries its own
                 5.05 % sulfur retention; this file used to assert retention = 0 instead, which
                 silently claimed more than the held factor does.
  control        NO SO2 REMOVAL CREDITED - a declared default, not a finding. AP-42 Section 1.3
                 (held at data/raw/epa_ap42/) records scrubbing on oil-fired boilers at 90-95 %
                 removal, so "our factor table has no controlled-oil row" and "these units have
                 no scrubber" are different statements and only the first is established. This is
                 the assumption that would most change the answer, it is declared on every row,
                 and its sensitivity is the difference between this column and zero.

This table does not enter any total. Admitting it is a separate, declared step that edits
data/air_coverage_absences.csv beside a real panel atom.

Usage:  python3 scripts/build_lahore_power_register.py
Writes: outputs/pakemis_air_lahore_power_register.csv
"""
import collections
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path

from pkinv.core import air_factors, sulfur                               # noqa: E402
from pkinv.core.io import read_rows                                      # noqa: E402
from pkinv.sectors.power.point_sources import equipment_class            # noqa: E402

OUT = asset_path(ROOT, "outputs", "pakemis_air_lahore_power_register.csv")
ADM2_ID = "punjab_lahore"
PERIODS = tuple("FY%d-%02d" % (y, (y + 1) % 100) for y in range(2015, 2024))
BTU_J = 1055.06                  # exact, international table Btu
NCV_RFO = 40.4                   # TJ/Gg, IPCC default; data/power_params.csv names it the RFO basis
# rc63: was power_rfo_spec_range, retired when one fuel stopped having two centrals - see
# data/activity/industry/fuel_sulfur_evidence.csv. Equipment still changes the RETENTION
# and not the fuel, and SULFUR_CLASS below is what carries that.
SULFUR_EVIDENCE = "fo_hsfo_grade_mix"
SULFUR_CLASS = "power_rfo_boiler"
# The held AP-42 row for No. 6 oil, rating A, transcribed with page and digest. It
# carries its own retention: 18.990401 kg SO2 per tonne per weight-percent sulfur
# against the 20.0 a complete balance would give, i.e. 5.05 percent retained. Using
# it means the register cites an applicable factor for the actual source class
# rather than asserting a retention of zero, which is what this file used to do.
SO2_FACTOR = "ap42_1.3_no6_so2_157S"
# ...BUT ONLY FOR A BOILER. Kohinoor is "DEs+ST" in NEPRA SoIR Table 5 - reciprocating engines
# with a bottoming steam turbine - so the fuel burns in engines, and AP-42 Section 3.4 says of
# those that sulfur oxides are "a function of only the sulfur content in the fuel rather than
# any combustion variables" and that "essentially all the sulfur in the fuel is oxidized to
# SO2". A boiler's 5.05 percent ash retention is not available to an engine, and applying it
# here understated Lahore by that much (4.598 against 4.842 Gg at FY2015-16). The equipment
# rule is shared with the national admission register rather than restated, so the two files
# cannot drift apart.
COMPLETE_BALANCE_KG_PER_T_PER_PCT = 20.0
ENGINE_TURBINE_BASIS = ("AP-42 Section 3.4 / 3.1: conversion of fuel sulfur to SO2 is complete "
                        "in a reciprocating engine or a gas turbine, so no retention is credited")
FIELDS = ("plant", "adm2_id", "period_id", "fiscal_end_year", "fuel", "operating_status",
          "generation_gwh", "generation_basis", "heat_rate_btu_kwh", "heat_rate_basis",
          "fuel_energy_TJ", "fuel_mass_kt", "sulfur_evidence_id", "s_pct_central", "s_pct_lo",
          "s_pct_hi", "control_type", "control_basis", "so2_Gg", "so2_Gg_lo", "so2_Gg_hi",
          "workbook_so2_Gg", "workbook_basis", "ratio_engine_over_workbook",
          "published_so2_Gg", "published_route", "ratio_this_over_published", "evidence_class",
          "reading")


def canonical_names():
    """{panel spelling: canonical plant} from the crosswalk the power module already keeps."""
    out = {}
    for row in read_rows(asset_path(ROOT, "data", "activity", "power",
                                      "plant_name_crosswalk.csv")):
        out[row["panel_name"]] = row["canonical_plant"] or row["panel_name"]
    return out


def lahore_plants():
    """{canonical plant: fuel} for every grid station the workbook places in Lahore District."""
    names = canonical_names()
    out = {}
    for row in read_rows(asset_path(ROOT, "data", "activity", "power",
                                      "grid_plant_district.csv")):
        if row["adm2_id"] != ADM2_ID:
            continue
        out.setdefault(names.get(row["plant"], row["plant"]), row["fuel"])
    return out


def generation():
    """{(canonical plant, period): (GWh, basis)} - this repository's monthly sum first."""
    names = canonical_names()
    monthly, months = collections.defaultdict(float), collections.defaultdict(int)
    for row in read_rows(asset_path(ROOT, "data", "activity", "power",
                                      "generation_monthly.csv")):
        key = (names.get(row["plant"], row["plant"]), row["fiscal_year"])
        monthly[key] += float(row["gwh"] or 0)
        months[key] += 1
    workbook = {}
    for row in read_rows(asset_path(ROOT, "data", "activity", "power",
                                      "grid_plant_district.csv")):
        if row["generation_gwh"]:
            workbook[(names.get(row["plant"], row["plant"]), row["fiscal_year"])] = \
                float(row["generation_gwh"])
    out = {}
    for key in set(monthly) | set(workbook):
        if key in monthly and months[key] == 12:
            out[key] = (monthly[key], "this repository's twelve monthly rows (generation_monthly.csv)")
        elif key in workbook:
            out[key] = (workbook[key], "the workbook's annual sheet; this repository holds %d of "
                                       "twelve months" % months.get(key, 0))
        else:
            out[key] = (monthly[key], "this repository holds only %d of twelve months"
                                      % months[key])
    return out


def heat_rates():
    """{(plant, fiscal START year): (net Btu/kWh, basis)}.

    THE KEY IS THE FISCAL START YEAR, and reading it as the end year was a live defect in this
    file until rc60. plant_heat_rates.csv and plant_fuel_ledger.csv key `fiscal_year` 2019 to
    FY2019-20: the ledger's own net_generation_GWh for Kohinoor in 2019 is 363.86, which is this
    repository's FY2019-20 monthly sum to two decimals and not its FY2018-19 sum of 387.44. Across
    the whole ledger the start reading agrees within 0.5 % on 70 of the 78 plant-years it can be
    checked against and the end reading on none of 72; head to head, where both candidate periods
    hold twelve months, the start reading is closer on 71 of 71. That race is the guard in
    tests/test_power_plant_workbooks.py, so the convention is measured rather than declared.
    The old code computed `int(period[-2:]) + 2000` and looked the rate up there, so every plant
    read the FOLLOWING year's heat rate. Kohinoor's rate is identical in all five printed years so
    Lahore's numbers never moved, which is exactly why it survived - 31 of the 42 plants with a
    published rate do vary, and a national build on that key would have mis-dated all of them.
    """
    names = canonical_names()
    out = {}
    for row in read_rows(asset_path(ROOT, "data", "activity", "power",
                                      "plant_heat_rates.csv")):
        if not row.get("hr_net_btu_kwh"):
            continue
        plant = names.get(row["plant"], row["plant"])
        out[(plant, int(row["fiscal_year"]))] = (float(row["hr_net_btu_kwh"]), row["hr_basis"])
    return out


def _start_year(period):
    """FY2019-20 -> 2019, the key plant_heat_rates.csv and plant_fuel_ledger.csv actually use."""
    return int(period[2:6])


def workbook_so2():
    """{(plant, period): (Gg, basis)} from the workbook's own calculation."""
    names = canonical_names()
    out = {}
    for row in read_rows(asset_path(ROOT, "data", "activity", "power",
                                      "workbook_emissions_crosscheck.csv")):
        if row["adm2_id"] != ADM2_ID or not row["so2_t"]:
            continue
        out[(names.get(row["plant"], row["plant"]), row["fiscal_year"])] = (
            float(row["so2_t"]) / 1000.0, row["factor_basis"])
    return out


BANNER = """\
# LAHORE DISTRICT GRID POWER UNITS AND THEIR SO2 - the GENERATION-ROUTE cross-check beside the
# published number, not the published number itself.
#
# THIS BANNER SAID THE OPPOSITE UNTIL rc64, AND A REVIEWER READ IT AND CONCLUDED THE RELEASE HAD
# NOT PUBLISHED LAHORE'S POWER SO2 AT ALL. It read "a measurement this release does not publish...
# power SO2 NE in all nine periods, so none of this is in any total". That was true when written
# and false from rc60: outputs/pakemis_air_coverage_matrix.csv now types power SO2 as E in all
# nine periods, and outputs/pakemis_air_lahore_by_year.csv carries a power row in every one.
#
# WHAT IS PUBLISHED, AND FROM WHAT. Lahore holds one emitting grid station, Kohinoor Energy, sited
# by point-in-polygon with two independent databases agreeing to 70 m. The district's published
# power SO2 equals that station's own row in data/activity/power/power_so2_admission.csv to six
# decimals in all nine periods. Five of those nine (FY2019-20..FY2023-24) are METERED NEPRA fuel
# quantities - 70.11, 64.82, 99.68, 63.55, 39.71 kt of RFO - with no heat rate, calorific value or
# efficiency standing between the document and the mass. No national fuel series and no population
# proxy enters it.
#
# WHAT THIS FILE IS FOR. It prices the same station the other way round - generation x net heat
# rate -> TJ -> fuel mass at the IPCC RFO NCV -> core.sulfur.so2_kt - so the two routes can be
# compared where both exist. The workbook's own literature kg/MWh number is carried beside it as a
# second cross-check, never as the estimate. Every assumption that is not measured is named in its
# own column: the heat rate before FY2019-20 is this station's own published rate carried back, the
# sulfur is a regulatory maximum with its band, and the control state is an assumption of none,
# which is the row most likely to be wrong. Gg SO2.
#
# WHAT THIS CROSS-CHECK MEASURES, now that it can see the published number. In the five periods
# where NEPRA prints a fuel quantity, both routes exist and disagree: generation x heat rate runs
# 7.8 to 9.1 percent HIGH against the metered fuel, mean 8.3 percent. That is a bias in the
# generation route, because the metered side has no heat rate, calorific value or efficiency in it.
#
# IT MATTERS FOR THE DISTRICT'S ENDPOINT CHANGE, AND IT CUTS AGAINST THE PUBLISHED FIGURE. Lahore's
# OPENING year is on the generation route (no ledger exists before FY2019-20) and its CLOSING year
# is metered. So the base is priced by the route that runs high and the endpoint by the route that
# does not. Carrying the measured 8.3 percent bias back over the four generation-route years puts
# FY2015-16 at 26.45 Gg rather than 27.30, and the district's nine-year endpoint change at -62.8
# percent rather than -63.9 - about 1.2 points shallower. That correction is NOT booked: the bias
# is measured on one station in five years and assuming it held in the four earlier ones is exactly
# the kind of transfer this repository makes people declare. It is recorded here so the asymmetry
# is visible rather than implicit, and so nobody quotes the endpoint change without it.
# Generated by scripts/build_lahore_power_register.py.
"""


ADMISSION = asset_path(ROOT, "data", "activity", "power", "power_so2_admission.csv")


def published_so2():
    """{period_id: (Gg, activity_route)} for the Lahore rows the PANEL actually books.

    Without this the cross-check could only state its own number, which is how nine rows came to
    assert "against a published Lahore District total of nothing for power in this period" for
    three releases after the panel started publishing one.
    """
    out = {}
    if not os.path.exists(ADMISSION):
        return out
    for row in read_rows(ADMISSION):
        if (row["adm2_id"] == "punjab_lahore" and row["fuel"] == "RFO"
                and row["disposition"] == "provisional_estimate" and row["so2_Gg"]):
            out[row["period_id"]] = (float(row["so2_Gg"]), row["activity_route"])
    return out


def station_types():
    """{Table 5 station: station_type}, the evidence the equipment rule reads."""
    return {r["plant"]: r["station_type"] for r in
            read_rows(asset_path(ROOT, "data", "activity", "power", "plant_locations.csv"))}


def _reading(so2, pub):
    """What this row says relative to the number the panel publishes.

    It used to say "against a published Lahore District total of nothing for power in this period"
    on all nine rows - true at rc59, false from rc60, and the sentence a reviewer read before
    concluding the release had never published Lahore's power SO2.
    """
    if not pub:
        return ("%.2f Gg SO2 by the generation route; the panel publishes no power row for this "
                "period" % so2)
    value, route = pub
    if route == "ledger_quantity":
        return ("%.2f Gg SO2 by the generation route, against %.2f published from a METERED NEPRA "
                "fuel quantity - the published figure needs no heat rate, calorific value or "
                "efficiency, and this row is the independent check on it" % (so2, value))
    return ("%.2f Gg SO2 by the generation route, against %.2f published; both take the same route "
            "in this period, so they agree by construction and the row is not an independent check"
            % (so2, value))


def build():
    published = published_so2()
    plants = lahore_plants()
    gen, hrs, wb = generation(), heat_rates(), workbook_so2()
    station_types_ = station_types()
    evidence = sulfur.load()
    rows = []
    for plant, fuel in sorted(plants.items()):
        for period in PERIODS:
            fy_end = int(period[-2:]) + 2000
            amount = gen.get((plant, period))
            if amount is None:
                rows.append({f: "" for f in FIELDS} | {
                    "plant": plant, "adm2_id": ADM2_ID, "period_id": period,
                    "fiscal_end_year": str(fy_end), "fuel": fuel,
                    "operating_status": "no generation record",
                    "evidence_class": "absent",
                    "reading": "no generation is held for this plant-year in either lane; an "
                               "absence, not a zero",
                })
                continue
            gwh, gen_basis = amount
            if gwh <= 0:
                rows.append({f: "" for f in FIELDS} | {
                    "plant": plant, "adm2_id": ADM2_ID, "period_id": period,
                    "fiscal_end_year": str(fy_end), "fuel": fuel,
                    "generation_gwh": "0.0", "generation_basis": gen_basis,
                    "operating_status": "recorded as not generating",
                    "evidence_class": "observed-zero",
                    "reading": "the record says zero generation, which is an observation and is "
                               "kept as one",
                })
                continue
            held = hrs.get((plant, _start_year(period)))
            if held:
                rate, hr_basis = held
                hr_basis = "%s, published for this year" % hr_basis
            else:
                same = sorted(v[0] for (p, y), v in hrs.items() if p == plant)
                if not same:
                    rows.append({f: "" for f in FIELDS} | {
                        "plant": plant, "adm2_id": ADM2_ID, "period_id": period,
                        "fiscal_end_year": str(fy_end), "fuel": fuel,
                        "generation_gwh": repr(round(gwh, 4)), "generation_basis": gen_basis,
                        "operating_status": "generating",
                        "evidence_class": "activity-only",
                        "reading": "generation is held but NO heat rate is published for this "
                                   "plant in any year, so no fuel quantity can be formed and no "
                                   "SO2 is estimated here",
                    })
                    continue
                rate = same[0]
                hr_basis = ("DECLARED CONSTANT: no heat rate is published for this year; the "
                            "plant's own published rate is identical in every year it is printed "
                            "(%s), and that value is carried" % ", ".join(
                                "%.2f" % v for v in sorted(set(same))))
            row = sulfur.evidence(SULFUR_EVIDENCE, fy_end, SULFUR_CLASS, evidence)
            tj = gwh * 1e6 * rate * BTU_J / 1e12
            mass_kt = tj / NCV_RFO
            if equipment_class(station_types_.get(plant, "")) == "oil_fired_boiler":
                per_pct, _unit = air_factors.kg_per_unit(air_factors.factor(SO2_FACTOR))
            else:
                per_pct = COMPLETE_BALANCE_KG_PER_T_PER_PCT
            so2 = mass_kt * 1000.0 * per_pct * float(row["s_pct_central"]) / 1e6
            lo = mass_kt * 1000.0 * per_pct * float(row["s_pct_lo"]) / 1e6
            hi = mass_kt * 1000.0 * per_pct * float(row["s_pct_hi"]) / 1e6
            theirs = wb.get((plant, period))
            rows.append({
                "plant": plant, "adm2_id": ADM2_ID, "period_id": period,
                "fiscal_end_year": str(fy_end), "fuel": fuel, "operating_status": "generating",
                "generation_gwh": repr(round(gwh, 4)), "generation_basis": gen_basis,
                "heat_rate_btu_kwh": repr(round(rate, 2)), "heat_rate_basis": hr_basis,
                "fuel_energy_TJ": repr(round(tj, 3)), "fuel_mass_kt": repr(round(mass_kt, 3)),
                "sulfur_evidence_id": SULFUR_EVIDENCE,
                "s_pct_central": row["s_pct_central"], "s_pct_lo": row["s_pct_lo"],
                "s_pct_hi": row["s_pct_hi"],
                "control_type": "none assumed",
                "control_basis": "flue-gas desulphurisation is not standard practice on an "
                                 "oil-fired reciprocating-engine or steam IPP in Pakistan; an "
                                 "ASSUMPTION, and the one most likely to be wrong",
                "so2_Gg": repr(round(so2, 4)), "so2_Gg_lo": repr(round(lo, 4)),
                "so2_Gg_hi": repr(round(hi, 4)),
                "workbook_so2_Gg": repr(round(theirs[0], 4)) if theirs else "",
                "workbook_basis": theirs[1] if theirs else "",
                "ratio_engine_over_workbook": (repr(round(so2 / theirs[0], 4))
                                               if theirs and theirs[0] else ""),
                "evidence_class": ("measured-activity-declared-factor" if held
                                   else "measured-activity-constant-heat-rate"),
                "published_so2_Gg": repr(round(published[period][0], 6)) if period in published else "",
                "published_route": published[period][1] if period in published else "",
                "ratio_this_over_published": (repr(round(so2 / published[period][0], 4))
                                              if published.get(period, (0,))[0] else ""),
                "reading": _reading(so2, published.get(period)),
            })
    return rows


def main():
    rows = build()
    with open(OUT, "w", encoding="utf-8", newline="") as handle:
        handle.write(BANNER)
        writer = csv.DictWriter(handle, fieldnames=list(FIELDS), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    priced = [r for r in rows if r["so2_Gg"]]
    by_period = collections.defaultdict(float)
    for r in priced:
        by_period[r["period_id"]] += float(r["so2_Gg"])
    print("%s: %d rows, %d priced" % (os.path.relpath(OUT, ROOT), len(rows), len(priced)))
    for period in PERIODS:
        print("   %-10s %6.2f Gg" % (period, by_period.get(period, 0.0)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

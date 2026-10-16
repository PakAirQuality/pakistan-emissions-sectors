"""Railway air pollutants - EMEP/EEA 2023 Guidebook chapter 1.A.3.c, Tier 1.

THE GAP THAT WAS RECORDED AS BLOCKED, CLOSED. This layer was 'not estimated' for one stated
reason: the EMEP/EEA locomotive factors were not accessible, and AP-42 Chapter 3.3 (large
stationary diesels) genuinely does not substitute. The audit reported the chapter had become
downloadable, and it was: sources/EMEP/emep_eea_2023_1a3c_railways.pdf, fetched from the
EEA's new-site @@download endpoint. Table 3-1 gives Tier 1 factors per tonne of fuel for
exactly the fuels this sector burns, and the factors now live in data/emission_factors.csv
under railway_air with the chapter's own confidence intervals on each row.

SAME COMBUSTION AS THE GREENHOUSE-GAS LAYER. The activity is the identical litres-to-mass
chain traction.py uses - one metered fuel figure drives both layers, which is what makes
them one inventory rather than two. Everything here is kt of native pollutant mass, never
CO2e; these numbers must not be added to the greenhouse-gas totals.

SO2 IS STOICHIOMETRY, NOT A FACTOR. The chapter's equation (2): E_SO2 = 2 x S x fuel mass,
all sulphur to SO2. It also says operator sulfur values are preferable to defaults - Pakistan
Railways publishes none (the rail-diesel-sulfur gap), and Pakistani HSD spans 10 ppm (Euro-V
imports, mandatory January 2021) to the 1 percent ceiling of the old national spec, three
orders of magnitude. So SO2 is reported as EXPLICIT SULFUR CASES rather than one number: the
reference case (the 500 ppm pre-Euro-V spec, conservative for a supply that now mixes in
10 ppm imports) goes in the main output, and every case goes in the cases table. Do not
average the cases; the honest statement is the span.

MASS DISCIPLINE. PM2.5 is a component of PM10, PM10 of TSP; BC is 0.65 of PM2.5 by the
chapter's f-BC note, a component and never an addition. The chapter's printed 95% CIs for
the three PM rows do not bracket their central values - a defect of the source, recorded
verbatim on the factor rows with a conservative +/-100 percent adopted instead of a silent
repair.

Furnace oil is carried with the same Table 3-1 factors (the chapter's factors are common to
its diesel and gas-oil columns, and the stream is 0.07 percent of fuel mass); its SO2 uses
the furnace-oil sulfur parameter.

Usage:  python3 -m pkinv.sectors.railways.air_pollutants
Writes: outputs/railways_air_pollutants_2024.csv, railways_air_sulfur_cases_2024.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.activity.store import read_rows
from pkinv.core.uncertainty import product
from pkinv.paths import OUTPUTS
from pkinv.sectors.railways import traction
from pkinv.sectors.railways.data import RailwaysData

CATEGORY = traction.CATEGORY
NON_TRACTION_CATEGORY = traction.NON_TRACTION_CATEGORY
FACTOR_POLLUTANTS = ("NOx", "CO", "NMVOC", "NH3", "TSP", "PM10", "PM2.5")

# (case name, params row, scope note). Order is the SO2 ladder, low to high.
SULFUR_CASES = (
    ("euro5_import_spec", "diesel_sulfur_ppm_euro5"),
    ("reference_pre_euro5_spec", "diesel_sulfur_ppm_reference"),
    ("historical_0.5pct", "diesel_sulfur_ppm_historical_low"),
    ("historical_1.0pct", "diesel_sulfur_ppm_historical_high"),
)
REFERENCE_CASE = "reference_pre_euro5_spec"
REGIME = asset_path(os.path.dirname(__file__), "..", "..", "..", "..",
                      "data", "activity", "railways", "diesel_sulfur_regime.csv")


def case_for_year(year=None):
    """The declared central sulfur case for one fiscal-end year.

    Read from data/activity/railways/diesel_sulfur_regime.csv, where each boundary
    carries its citation: 0.5 percent sulfur before the January 2017 Euro-II import
    mandate, the 500 ppm spec from FY2017-18, and the same conservative 500 ppm central
    (unchanged shipped reference decision) through the post-2021 Euro-V import years
    whose supply the euro5_import_spec ladder endpoint spans. A year outside the table
    raises - a sulfur case is a claim about a year's fuel, never a default.
    """
    year = 2024 if year is None else year
    for r in read_rows(REGIME):
        if int(r["fiscal_end_year"]) == year:
            return r["sulfur_case"]
    raise KeyError("no diesel sulfur case declared for fiscal-end year %r" % year)


def fuel_tonnes(data, year=None):
    """{stream: tonnes of fuel}, the same litres->mass chain as traction.fuel_TJ.

    Deliberately mirrors traction's arithmetic term by term so the air and greenhouse-gas
    layers describe the same combustion; a test asserts the correspondence exactly.
    """
    out = {}
    for stream, item, density_param, _u in traction.FUELS:
        qty = data.quantity(item, year)
        unit = data.unit(item, year)
        if unit == "thousand litres":
            out[stream] = qty * 1000.0 * data.p(density_param) / 1000.0  # kL -> L -> kg -> t
        elif unit == "tonnes":
            out[stream] = qty
        else:
            raise ValueError("unhandled activity unit %r for %s" % (unit, item))
    return out


def so2_kt(tonnes_fuel, sulfur_frac):
    """SO2 in kt from fuel mass and sulfur mass fraction: 2 x S, chapter equation (2).

    tonnes of SO2 = 2 x (sulfur tonnes); kt = tonnes / 1e3.
    """
    return 2.0 * sulfur_frac * tonnes_fuel / 1e3


def _sulfur_frac(data, stream, case_param):
    if stream == "Furnace oil":
        return data.p("rfo_sulfur_pct") / 100.0
    return data.p(case_param) / 1e6


def compute(data, year=None, sulfur_case=None):
    """[{category, fuel, pollutant, emissions_kt, uncert_pct, source, sulfur_case, basis}].

    kt of native pollutant mass. The factor pollutants come straight off Table 3-1; BC is
    the f-BC fraction of PM2.5; SO2 is stoichiometric under the named sulfur case -
    sulfur_case=None takes the year's own declared regime case (case_for_year), so the
    nine-year series does not burn 500 ppm in years that circulated 0.5 percent fuel.

    THE TRACTION SPLIT (air spatial Wave A). This layer used to burn the whole fuel
    account on the traction anchors, which put six years of furnace oil - reported NIL
    locomotive in the detail table for every year through FY2020-21 - on a rail-network
    stream the greenhouse-gas panel itself marks absent in those periods: 54 air atoms
    inheriting dead geography. Each fuel now splits by the year's own
    traction.locomotive_fraction exactly as the greenhouse-gas engine splits it, with
    the same portion<=0 skip, and the non-traction rows anchor the non-traction streams
    (yard points, present in every period). The non-traction rows keep the same EMEP
    1.A.3.c Tier 1 factors this release - a DECLARED caveat carried on the row basis:
    stationary boilers and gensets are not locomotives, and equipment-appropriate
    factors are a named refinement, but the support repair is what the spatial build
    needs and a wrong-surface row is the worse error.
    """
    if sulfur_case is None:
        sulfur_case = case_for_year(year)
    case_param = dict(SULFUR_CASES)[sulfur_case]
    tonnes = fuel_tonnes(data, year)
    rows = []
    for stream, _item, _d, unc in traction.FUELS:
        loco = traction.locomotive_fraction(data, stream, year)
        splits = [(CATEGORY, "", loco),
                  (NON_TRACTION_CATEGORY,
                   "; non-traction equipment on locomotive Tier 1 factors, a declared "
                   "proxy", 1.0 - loco)]
        t_all = tonnes[stream]
        ad_u = data.p("activity_uncert_" + unc)
        for category, caveat, portion in splits:
            if portion <= 0.0:
                continue
            t = t_all * portion
            pm25_kt = None
            for pol in FACTOR_POLLUTANTS:
                kt = t * data.efv("railway_air", pol) / 1e6
                if pol == "PM2.5":
                    pm25_kt = kt
                rows.append({"category": category, "fuel": stream, "pollutant": pol,
                             "emissions_kt": kt,
                             "uncert_pct": product(ad_u, data.efu("railway_air", pol)),
                             "source": data.efs("railway_air", pol), "sulfur_case": "",
                             "basis": "Table 3-1 Tier 1, kg per tonne fuel" + caveat})
            frac = data.efv("railway_air_frac", "BC_of_PM2.5")
            rows.append({"category": category, "fuel": stream, "pollutant": "BC",
                         "emissions_kt": pm25_kt * frac,
                         "uncert_pct": product(ad_u, data.efu("railway_air", "PM2.5"),
                                               data.efu("railway_air_frac", "BC_of_PM2.5")),
                         "source": data.efs("railway_air_frac", "BC_of_PM2.5"),
                         "sulfur_case": "",
                         "basis": ("f-BC = %.2f of PM2.5; component of PM mass, not "
                                   "additive" % frac) + caveat})
            s = _sulfur_frac(data, stream, case_param)
            sulfur_u = (data.pu("rfo_sulfur_pct") if stream == "Furnace oil"
                        else data.pu(case_param)) or 0.0
            rows.append({"category": category, "fuel": stream, "pollutant": "SO2",
                         "emissions_kt": so2_kt(t, s),
                         "uncert_pct": product(ad_u, sulfur_u),
                         "source": "EMEP/EEA 2023 ch 1.A.3.c eq (2): E_SO2 = 2 x S x fuel mass",
                         "sulfur_case": sulfur_case,
                         "basis": ("stoichiometric at %s sulfur by mass"
                                   % ("%.1f%%" % (s * 100) if stream == "Furnace oil"
                                      else "%g ppm" % data.p(case_param))) + caveat})
    return rows


def sulfur_cases(data, year=None):
    """[(case, diesel ppm, total SO2 kt)] across the whole ladder - the scenario table."""
    tonnes = fuel_tonnes(data, year)
    fo_so2 = so2_kt(tonnes["Furnace oil"], data.p("rfo_sulfur_pct") / 100.0)
    return [(case, data.p(param),
             so2_kt(tonnes["Diesel"], data.p(param) / 1e6) + fo_so2)
            for case, param in SULFUR_CASES]


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = RailwaysData()
    rows = compute(data)
    with open(asset_path(OUTPUTS, "railways_air_pollutants_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "fuel", "pollutant", "emissions_kt", "uncert_pct",
                    "emep_source", "sulfur_case", "basis"])
        for r in rows:
            w.writerow([r["category"], r["fuel"], r["pollutant"],
                        round(r["emissions_kt"], 6), round(r["uncert_pct"], 1),
                        r["source"], r["sulfur_case"], r["basis"]])
    with open(asset_path(OUTPUTS, "railways_air_sulfur_cases_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sulfur_case", "diesel_sulfur_ppm", "so2_kt", "note"])
        for case, ppm, kt in sulfur_cases(data):
            w.writerow([case, "%g" % ppm, round(kt, 6),
                        "reference case, reported in the main output" if
                        case == REFERENCE_CASE else "scenario"])
    totals = {}
    for r in rows:
        totals[r["pollutant"]] = totals.get(r["pollutant"], 0.0) + r["emissions_kt"]
    print("Railways air pollutants FY%d-%02d (kt, native mass, never CO2e):"
          % (data.year - 1, data.year % 100))
    for pol in ("NOx", "CO", "NMVOC", "TSP", "PM10", "PM2.5", "BC", "SO2", "NH3"):
        print("  %-6s %10.4f" % (pol, totals[pol]))
    print("  SO2 by sulfur case: " + ", ".join(
        "%s %.4f" % (c, kt) for c, _p, kt in sulfur_cases(data)))


if __name__ == "__main__":
    main()

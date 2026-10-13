"""Cement kiln fuel and process bagasse: two screenings against the solid residual.

WHY THIS EXISTS. The solid tier's 29.31 Mt UNRESOLVED benchmark residual carried
two claimants with held activity and no fuel control - cement kiln fuel (the
producer census clinker) and sugar-mill process bagasse (the Economic Survey cane
series) - and the twelfth review named non-gas industrial combustion the primary
completeness problem. The HDIP Yearbook that would price them properly is a paid
acquisition this project has not made; what CAN be done from held activity is a
screening, the brick-kiln pattern (kiln_screening.py): outside every reference
total, priced as a named configuration, its dominant uncertainty stated first.

TWO SCREENINGS, TWO SHAPES OF HONESTY.

  cement  The activity is OBSERVED (15 of 16 census entities, own-year), and the
          unheld quantity is the kilns' specific heat consumption: no Pakistani
          kiln heat audit is held, so the intensity is TRANSFERRED - the
          dry-process range international audits publish - and the bracket it
          spans outranks every factor CI. The result says the residual's largest
          claimant is on the order of HALF the residual, which is exactly the
          kind of statement a screening exists to make.

  bagasse A CEILING, not an estimate: the mill crush share of the cane crop is
          not held anywhere in this tree (the ledger's earlier claim that "cane
          crush is a national statistic" described a statistic PSMA publishes and
          this project never acquired), so the screening burns the ENTIRE crop's
          bagasse and reports what even that ceiling amounts to. Its CO2 is
          biogenic and outside every total by construction; the CH4 and N2O that
          would count stay under half a megatonne AT THE CEILING - so bagasse
          cannot be a material part of the fossil-CO2 residual, and saying so
          resolves the claimant more usefully than any point estimate would.

Constants are DELIBERATELY NOT in data/emission_factors.csv, exactly as in
kiln_screening: nothing here enters a component row or the factor registry.

Usage:  python3 -m pkinv.sectors.industry.solid_screenings
Writes: outputs/industry_solid_screenings_2024.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.gwp import GWP
from pkinv.paths import DATA, OUTPUTS

CLINKER_CENSUS = asset_path(DATA, "activity", "ippu",
                              "company_clinker_2023_24.csv")
ES_SERIES = asset_path(DATA, "activity", "agriculture", "es_fiscal_series.csv")

# --- cement kiln fuel ---------------------------------------------------------
# Specific heat consumption of clinker, GJ/t: the dry-process range international
# audits publish (IEA/WBCSD Cement Technology Roadmap; the GNR global weighted
# average sits near 3.5). TRANSFERRED - no Pakistani kiln heat audit is held -
# and the range, not any factor CI, is the screening's dominant uncertainty.
HEAT_GJ_PER_T_LOW = 3.0
HEAT_GJ_PER_T_CENTRAL = 3.4
HEAT_GJ_PER_T_HIGH = 3.8
# CO2 per TJ: coal (IPCC 2006 Table 2.3 Other Bituminous, manufacturing) to
# petroleum coke - the mix is unheld, so the fuel bracket rides the EF.
KILN_CO2_KG_TJ_LOW = 94600.0     # all coal
KILN_CO2_KG_TJ_HIGH = 97500.0    # all petroleum coke
KILN_CH4_KG_TJ = 10.0            # Table 2.3
KILN_N2O_KG_TJ = 1.5             # Table 2.3

# --- process bagasse (ceiling) ------------------------------------------------
BAGASSE_T_PER_T_CANE = 0.30      # wet bagasse per tonne milled, ~50% moisture -
                                 # the sugar-engineering convention, transferred
BAGASSE_NCV_TJ_GG = 7.8          # wet basis; IPCC 2006 lists no bagasse row
BAGASSE_CH4_KG_TJ = 30.0         # Table 2.3 biomass, manufacturing
BAGASSE_N2O_KG_TJ = 4.0          # Table 2.3


def clinker_t():
    rows = [r for r in _activity_rows(CLINKER_CENSUS, comments=False) if r["clinker_production_t"]]
    return sum(float(r["clinker_production_t"]) for r in rows), len(rows)


def cane_t():
    row = next(r for r in _activity_rows(ES_SERIES, comments=True)
               if r.get("item") == "sugarcane_production_t"
               and r.get("fiscal_label") == "FY2023-24")
    return float(row["value"])


def cement_screening():
    """(low, central, high) Mt CO2e AR5, plus meta. Heat intensity x fuel EF."""
    t, companies = clinker_t()
    out = {}
    for name, gj_per_t, co2_kg_tj in (
            ("low", HEAT_GJ_PER_T_LOW, KILN_CO2_KG_TJ_LOW),
            ("central", HEAT_GJ_PER_T_CENTRAL, KILN_CO2_KG_TJ_LOW),
            ("high", HEAT_GJ_PER_T_HIGH, KILN_CO2_KG_TJ_HIGH)):
        tj = t * gj_per_t / 1000.0
        co2_mt = tj * co2_kg_tj / 1e9
        ch4_mt = tj * KILN_CH4_KG_TJ / 1e9 * GWP["AR5"]["CH4_fossil"]
        n2o_mt = tj * KILN_N2O_KG_TJ / 1e9 * GWP["AR5"]["N2O"]
        out[name] = co2_mt + ch4_mt + n2o_mt
    return out, {"clinker_t": t, "companies": companies,
                 "central_tj": t * HEAT_GJ_PER_T_CENTRAL / 1000.0}


def cement_screening_mt():
    """The headline central magnitude - what the configuration prices."""
    return cement_screening()[0]["central"]


def bagasse_ceiling():
    """Mt CO2e AR5 of CH4+N2O if the ENTIRE cane crop's bagasse were burned."""
    cane = cane_t()
    bagasse_gg = cane * BAGASSE_T_PER_T_CANE / 1000.0
    tj = bagasse_gg * BAGASSE_NCV_TJ_GG
    ch4_mt = tj * BAGASSE_CH4_KG_TJ / 1e9 * GWP["AR5"]["CH4"]
    n2o_mt = tj * BAGASSE_N2O_KG_TJ / 1e9 * GWP["AR5"]["N2O"]
    return {"cane_t": cane, "bagasse_gg": bagasse_gg, "tj": tj,
            "ch4_mt": ch4_mt, "n2o_mt": n2o_mt, "total_mt": ch4_mt + n2o_mt}


def bagasse_ceiling_mt():
    return bagasse_ceiling()["total_mt"]


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    cement, meta = cement_screening()
    bag = bagasse_ceiling()
    path = asset_path(OUTPUTS, "industry_solid_screenings_2024.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row_kind", "name", "bound", "quantity", "unit", "basis",
                    "note"])
        w.writerow(["activity", "Producer census clinker", "",
                    round(meta["clinker_t"]), "t clinker",
                    "data/activity/ippu/company_clinker_2023_24.csv",
                    "%d census companies, own-year, observed - the one solid "
                    "claimant whose activity needs no vintage caveat"
                    % meta["companies"]])
        for bound in ("low", "central", "high"):
            w.writerow(["ghg_screening", "Cement kiln fuel", bound,
                        round(cement[bound], 5), "Mt CO2e (AR5)",
                        "clinker x %.1f-%.1f GJ/t (transferred dry-process "
                        "range) x coal-to-petcoke EF"
                        % (HEAT_GJ_PER_T_LOW, HEAT_GJ_PER_T_HIGH),
                        "SCREENING comparator, outside every reference total; no "
                        "Pakistani kiln heat audit is held and the intensity bracket "
                        "outranks every factor CI. Since rc46 the reference BOOKS the "
                        "measured HDIP cement-sector coal, so 1A2 is no longer NE for "
                        "it; this model is priced against that stream NET as the "
                        "cement_kiln_fuel_in_scope replacement (+2.80), never added"])
        w.writerow(["activity", "Sugarcane production (NOT crush)", "",
                    round(bag["cane_t"]), "t cane",
                    "data/activity/agriculture/es_fiscal_series.csv FY2023-24",
                    "the mill crush share is UNHELD (PSMA publishes it; never "
                    "acquired), so the bagasse row below is a CEILING at the "
                    "all-cane bound, not an estimate"])
        w.writerow(["ghg_screening", "Process bagasse CH4+N2O", "ceiling",
                    round(bag["total_mt"], 5), "Mt CO2e (AR5)",
                    "cane x %.2f t bagasse/t x %.1f TJ/Gg wet x Table 2.3 "
                    "biomass EFs" % (BAGASSE_T_PER_T_CANE, BAGASSE_NCV_TJ_GG),
                    "CEILING: burns the entire crop's bagasse. Its CO2 is "
                    "biogenic and outside every total by construction; even at "
                    "this bound the countable gases stay under half a megatonne, "
                    "so bagasse cannot be a material part of the fossil-CO2 "
                    "benchmark residual"])
    print("solid-fuel screenings -> %s" % os.path.basename(path))
    print("  cement kiln fuel %.2f Mt central (%.2f-%.2f; ~%.0f%% of the 29.31 "
          "Mt residual); bagasse ceiling %.2f Mt CH4+N2O"
          % (cement["central"], cement["low"], cement["high"],
             100.0 * cement["central"] / 29.31, bag["total_mt"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

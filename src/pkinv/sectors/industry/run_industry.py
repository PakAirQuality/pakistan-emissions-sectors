"""Run the industrial-combustion inventory (IPCC 1A2, gas) and write its outputs.

Usage:  python3 -m pkinv.sectors.industry.run_industry
"""
import os

from pkinv.core.downscale import allocate_rows, check_reconciliation
from pkinv.core.geography import PROVINCES
from pkinv.core.runner import Runner
from pkinv.paths import OUTPUTS
from pkinv.sectors.industry import combustion, downscale, engine, kiln_screening
from pkinv.sectors.industry.data import IndustryData

# EDGAR Industrial Combustion (1A2), Pakistan 2024 - data/benchmarks.csv
EDGAR_1A2_2024 = 43.98
# The other 1A2 category, estimated in the power module; quoted here only to state coverage.
CAPTIVE_MT = 5.55


def inputs_register(data):
    """The module's declared inputs, in the same shape as the other sectors'
    registers - written so core.parameters can see them (rc19). The register
    exists for one load-bearing row: the OGRA delivered-gas volume, which since
    rc19 is a member of the cross-module dependency group
    delivered_gas_ogra_3_31 (one publication behind the residential, CNG,
    industrial and captive volumes, one shared draw direction). The other rows
    stay module-local; their widths already live in data/industry_params.csv."""
    def row(variable, central, unit, u, dist, source, applies_to, group, klass,
            note=""):
        return {"variable": variable, "central_value": central, "unit": unit,
                "uncert_pct_95": u, "distribution": dist, "source": source,
                "applies_to": applies_to, "correlation_group": group,
                "uncertainty_class": klass, "note": note}
    gas_mmcfd = sum(data.mmcfd(s) for s in data.streams())
    return [
        row("Industrial gas volume (General Industry + Cement)",
            round(gas_mmcfd, 1), "MMCFD", data.p("industry_activity_uncert"),
            "lognormal", "OGRA Table 3.31 sector rows", "all gas streams",
            "delivered_gas_ogra_3_31", "parametric",
            "SHARED GROUP (rc19): one OGRA Table 3.31 publication behind the "
            "residential, CNG, industrial and captive delivered volumes, so "
            "their activity errors share one draw direction; each module keeps "
            "its own declared width"),
        row("Industry gas HHV", data.p("industry_hhv_btu_per_scf"),
            "Btu/scf gross", data.pu("industry_hhv_btu_per_scf"), "lognormal",
            data.ps("industry_hhv_btu_per_scf"), "all gas streams", "",
            "parametric",
            "pinned equal to the captive and CNG values by test; the 900 case "
            "is the published sensitivity row"),
        row("Industry gross-to-net", data.p("industry_gross_to_net"),
            "fraction", data.pu("industry_gross_to_net"), "lognormal",
            data.ps("industry_gross_to_net"), "all gas streams", "",
            "parametric", "IPCC works net; the utilities bill gross"),
        row("OCAC Total Industry liquid fuels",
            "six product rows", "t/yr", data.p("industry_liquid_activity_uncert"),
            "lognormal", "OCAC Sectoral Sales of Energy Products",
            "all liquid-fuel streams", "", "parametric",
            "customer class, not end use; same publication basis as the "
            "transport controls"),
    ]


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    # The claimant ledger - the fluid tier's closure aborts the run if broken.
    kiln_screening.main()
    from pkinv.sectors.industry import solid_screenings
    solid_screenings.main()
    from pkinv.sectors.industry import captive_screening
    captive_screening.main()
    from pkinv.sectors.industry import fuel_ledger
    fuel_ledger.main()
    data = IndustryData()
    year = data.year
    run = Runner("industry", declared=(
        "industry_by_stream_%d.csv" % year, "industry_totals_%d.csv" % year,
        "industry_fuel_%d.csv" % year,
        "industry_uncertainty_inputs_%d.csv" % year,
        "industry_provincial_%d.csv" % year))
    comps = engine.build_components(data)
    total = sum(c["co2e_Mt_AR5"] for c in comps)
    # The measured solid-fuel activations (rc46 Wave 2), summed from the components so
    # every sensitivity row below is priced NET of what the reference already contains -
    # the rc47 Wave 0 repair of the double count the twenty-first review found.
    measured_brick = sum(c["co2e_Mt_AR5"] for c in comps
                         if c["subitem"].startswith("Brick-kiln coal"))
    measured_cement_coal = sum(c["co2e_Mt_AR5"] for c in comps
                               if c["subitem"].startswith("Cement-sector coal"))
    low = sum(c["co2e_Mt_AR5"] for c in engine.build_components(data, hhv_btu=900))

    run.write("industry_by_stream_%d.csv" % year,
           ["category", "subitem", "gas", "fossil", "emissions_Gg", "co2e_Mt_AR5",
            "co2e_Mt_AR6", "uncert_pct"],
           [[c["category"], c["subitem"], c["gas"], c.get("fossil", False),
             round(c["emissions_Gg"], 4), round(c["co2e_Mt_AR5"], 5),
             round(c["co2e_Mt_AR6"], 5), round(c["uncert_pct"], 1)] for c in comps])

    covered = total + CAPTIVE_MT
    run.write("industry_totals_%d.csv" % year,
           ["category", "co2e_Mt_AR5", "co2e_Mt_AR6", "note"],
           [[combustion.CATEGORY, round(total, 5),
             round(sum(c["co2e_Mt_AR6"] for c in comps), 5),
             "1A2 metered gas, OCAC's Total Industry liquid-fuel rows, and - rc46 "
             "Wave 2 - the measured HDIP brick-kiln and cement-sector coal: process "
             "heat, boilers and kilns on natural gas, furnace oil, diesel, LDO, "
             "kerosene, gasoline and coal. Still NOT estimated: petroleum coke "
             "(the Comtrade lane) and process bagasse (ceiling-bounded); 'other "
             "industrial coal' is definitionally ~zero under the supply-consumption "
             "identity."],
            ["Sensitivity: gas at 900 Btu/scf", round(low, 5), "",
             "The heating value is the assumption: OGRA reports a volume and IPCC works in "
             "net terajoules. Pakistani pipeline gas runs 900-1,000 Btu/scf and nothing read "
             "here pins it. Same treatment as the captive and CNG categories, whose heating "
             "values are pinned equal to this one by test."],
            ["Comparator: the retired brick-kiln coal screening",
             round(kiln_screening.screening_mt(), 5), "",
             "COMPARATOR, not a configuration: the reference CONTAINS measured "
             "brick-kiln coal (%.2f Mt, HDIP coal-by-consumer FY2023-24) since the "
             "rc46 activation, so the FY2022-23-vintage screening (%.2f Mt) is "
             "superseded and adding it would double-count - the configuration "
             "brick_kiln_coal_in_scope is retired (rc47 Wave 0). The gap between "
             "the two is a vintage-and-method note, not an alternative: the "
             "measured reference year is a trough (1,129 kt) in a series the "
             "screening's FY2022-23 vintage (2,991 kt) does not describe. Detail "
             "in outputs/industry_brick_kiln_screening_2024.csv"
             % (measured_brick, kiln_screening.screening_mt())],
            ["Sensitivity: cement kiln fuel at the transferred-intensity model "
             "(excess over measured)",
             round(total + solid_screenings.cement_screening_mt()
                   - measured_cement_coal, 5), "",
             "the 1A2 category with the transferred-intensity cement model "
             "REPLACING the measured HDIP cement coal it now contains: the "
             "reference books %.2f Mt of measured cement-sector coal (rc46 "
             "activation), the model implies %.2f Mt central over a %.2f-%.2f "
             "bracket (own-year census clinker under a TRANSFERRED dry-process "
             "heat intensity, no Pakistani kiln audit held), so the alternative "
             "prices the EXCESS %+.2f Mt - the question 'does the measured "
             "consumer series capture all kiln fuel?', not a second copy of the "
             "coal. Priced by the configuration cement_kiln_fuel_in_scope. "
             "Detail in outputs/industry_solid_screenings_2024.csv"
             % (measured_cement_coal, solid_screenings.cement_screening_mt(),
                solid_screenings.cement_screening()[0]["low"],
                solid_screenings.cement_screening()[0]["high"],
                solid_screenings.cement_screening_mt() - measured_cement_coal)],
            ["Sensitivity: including process bagasse (all-cane ceiling)",
             round(total + solid_screenings.bagasse_ceiling_mt(), 5), "",
             "the 1A2 category plus the bagasse CEILING (%.2f Mt of CH4+N2O if "
             "the ENTIRE cane crop's bagasse were burned; the mill crush share "
             "is unheld and the CO2 is biogenic, outside every total by "
             "construction) - priced as national configuration "
             "bagasse_ceiling_in_scope so a reader sees the claimant is bounded "
             "SMALL, not unexamined. Detail in "
             "outputs/industry_solid_screenings_2024.csv"
             % solid_screenings.bagasse_ceiling_mt()],
            ["Comparator: the retired captive-coal capacity bracket",
             round([r for r in captive_screening.rows()
                    if r["configuration"] == "captive_coal_in_scope"
                    ][0]["bracket_high_Mt"], 5), "",
             "COMPARATOR, not a configuration: the industrial_solid_fuels_1a2 "
             "activation gate's own text records that captive coal sits INSIDE "
             "the brick residual column the reference now books (supply "
             "exhausts consumption, so a separate captive activation would "
             "double-count) - the configuration captive_coal_in_scope is "
             "retired (rc47 Wave 0) and the bracket (0.17-1.31 Mt) stands as "
             "the register-sized bound on the captive share OF the booked "
             "residual, not as mass to add. Non-coal captive fuels stay "
             "excluded BY NAME (FO/diesel on double-count risk with the OCAC "
             "liquids control, bagasse under the all-cane ceiling). Detail in "
             "outputs/industry_captive_screening_2024.csv"],
            ["Coverage: 1A2 estimated against EDGAR", round(100 * covered / EDGAR_1A2_2024, 1),
             "", "PERCENT, not Mt: this category (%.2f Mt) plus captive self-generation "
                 "(%.2f Mt, power module) against EDGAR's %.2f Mt for Pakistani industrial "
                 "combustion. The remainder - roughly %.0f Mt - is every non-gas industrial "
                 "fuel and remains unestimated."
                 % (total, CAPTIVE_MT, EDGAR_1A2_2024, EDGAR_1A2_2024 - covered)],
            ["Excluded: fertiliser gas, feed and process fuel (756 MMCFD)", "", "",
             "Deliberately absent, on the IPCC ammonia method: the TOTAL gas requirement "
             "of ammonia production - feedstock and process fuel together, 83.5/16.5 on "
             "NFDC's monthly plant annex for this fiscal year - belongs to 2B1, and only "
             "separately metered "
             "auxiliary combustion outside the process boundary would stay in 1A2. The "
             "feedstock carbon leaves as urea and is priced by the 2B1 ledger and at "
             "application in 3.H; booking the row here would inflate the category three "
             "and a half fold and double-count against the ammonia accounting."]])

    run.write("industry_fuel_%d.csv" % year, ["stream", "mmcfd", "TJ_net"],
           [[s, data.mmcfd(s), round(combustion.gas_TJ(data, s), 1)]
            for s in data.streams()])

    reg = inputs_register(data)
    run.write_dicts("industry_uncertainty_inputs_%d.csv" % year, reg,
                    fields=list(reg[0].keys()))

    rows = allocate_rows(comps, downscale.load_shares(), downscale.proxy_for, PROVINCES)
    check_reconciliation(rows, comps)
    prov = {p: 0.0 for p in PROVINCES}
    for r in rows:
        prov[r["province"]] += r["co2e_Mt_AR5"]
    run.write("industry_provincial_%d.csv" % year, ["province", "co2e_Mt_AR5"],
           [[p, round(prov[p], 5)] for p in PROVINCES])

    print("Industrial combustion (1A2) FY%d-%02d: %.2f Mt CO2e (AR5)"
          % (year - 1, year % 100, total))
    for s in data.streams():
        print("  %-18s %7.1f MMCFD  %9.1f TJ" % (s, data.mmcfd(s),
                                                 combustion.gas_TJ(data, s)))
    print("  gas + OCAC liquid fuels; industrial coal, petroleum coke and bagasse are "
          "not estimated")
    print("  1A2 coverage: %.2f Mt here + %.2f captive = %.0f%% of EDGAR's %.2f Mt; ~%.0f Mt open"
          % (total, CAPTIVE_MT, 100 * covered / EDGAR_1A2_2024, EDGAR_1A2_2024,
             EDGAR_1A2_2024 - covered))
    print("  heating-value sensitivity: %.2f Mt at 900 Btu/scf" % low)
    print("  provincial reconciliation exact; %s"
          % ", ".join("%s %.2f" % (p, prov[p]) for p in PROVINCES))

    print("-- monthly profile --")
    from pkinv.sectors.industry import monthly
    monthly.main()

    run.finalize(qa_table="industry_qa_%d.csv" % year)


if __name__ == "__main__":
    main()

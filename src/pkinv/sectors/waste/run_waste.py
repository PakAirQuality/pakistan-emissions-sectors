"""Run the open-waste-burning inventory (IPCC 4C2) and write its outputs.

Usage:  python3 -m pkinv.sectors.waste.run_waste
Writes: outputs/waste_totals_2023.csv, waste_by_stream_2023.csv,
        waste_air_pollutants_2023.csv, waste_provincial_2023.csv, waste_report.md,
        waste_qa_2023.csv
"""

from pkinv.assets import asset_path
import os

from pkinv.core.downscale import allocate_rows, check_reconciliation
from pkinv.core.geography import PROVINCES
from pkinv.core.runner import Runner
from pkinv.paths import OUTPUTS
from pkinv.sectors.waste import (air_pollutants, downscale, engine, ledger, open_burning,
                                 swds, wastewater)
from pkinv.sectors.waste.data import WasteData

CAT = open_burning.CATEGORY


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = WasteData()
    year = data.year
    run = Runner("waste", declared=(
        "waste_by_stream_%d.csv" % year, "waste_totals_%d.csv" % year,
        "waste_air_pollutants_%d.csv" % year, "waste_provincial_%d.csv" % year,
        "waste_report.md"))
    comps = engine.build_components(data)
    memo = engine.memo_items(data)
    air = air_pollutants.compute(data)
    burnt = open_burning.waste_burnt(data)

    run.write("waste_by_stream_%d.csv" % year,
              ["category", "subitem", "gas", "emissions_Gg", "co2e_Mt_AR5", "co2e_Mt_AR6", "uncert_pct"],
              [[c["category"], c["subitem"], c["gas"], round(c["emissions_Gg"], 4),
                round(c["co2e_Mt_AR5"], 4), round(c["co2e_Mt_AR6"], 4), round(c["uncert_pct"], 1)]
               for c in comps])

    total = sum(c["co2e_Mt_AR5"] for c in comps)
    by_cat = {}
    for c in comps:
        by_cat.setdefault(c["category"], [0.0, 0.0])
        by_cat[c["category"]][0] += c["co2e_Mt_AR5"]
        by_cat[c["category"]][1] += c["co2e_Mt_AR6"]
    no_spinup = swds.ch4_emitted(data, spinup=False) * 28 / 1000.0
    # Both wastewater sensitivities move CH4 only - N2O depends on protein, not on the sewer
    # or the BOD rate - but they are written into a column whose other rows are CATEGORY
    # totals, so the invariant N2O has to be added back. Without it the file reported 12.50
    # against a 24.28 category total, implying a factor of 1.94 where the real one is 1.57,
    # and disagreed with this module's own printed line, which had always added it.
    ww_n2o = sum(c["co2e_Mt_AR5"] for c in comps
                 if c["category"] == wastewater.CATEGORY and c["gas"] == "N2O")
    ww_river = (wastewater.ch4_gg(data, sewer_mcf=data.p("ww_mcf_sewer_river")) * 28 / 1000.0
                + ww_n2o)
    ww_india = wastewater.ch4_gg(data, bod=data.p("ww_bod_india")) * 28 / 1000.0 + ww_n2o
    run.write("waste_totals_%d.csv" % year, ["category", "co2e_Mt_AR5", "co2e_Mt_AR6", "note"],
              # FIVE DECIMALS, as the national rollup and the other sectors' totals carry.
              # At four, the three category rows summed 1.1e-4 from the engine at rc67 and
              # the AR6 total sat exactly half a unit from the rollup's: a second rounding,
              # which two release-integrity tests read as a stale file.
              [[c, round(v[0], 5), round(v[1], 5),
                "IPCC 4C2" if c == CAT
                # the wastewater row carried the disposal row's note through rc66
                else "IPCC 4D1: methane by sanitation pathway; nitrous oxide on the 2019 "
                     "Refinement since rc67" if "wastewater" in c.lower()
                else "IPCC 4A, First Order Decay over a %d-%d deposit "
                     "series (pre-%d back-projected)"
                     % (swds.SPINUP_FROM, year, min(swds.panel_years(data)))]
               for c, v in by_cat.items()]
              + [["TOTAL", round(total, 5), round(sum(c["co2e_Mt_AR6"] for c in comps), 5), ""],
                 ["Sensitivity: disposal without spin-up", round(no_spinup, 5), "",
                  "What 4A would report if the model started at the panel's first year with an "
                  "empty site, i.e. ignoring every deposit before %d"
                  % min(swds.panel_years(data))],
                 ["Sensitivity: wastewater on the river-discharge MCF (category total)", round(ww_river, 5), "",
                  "IPCC gives stagnant open sewers 0.5 and river discharge 0.1. Pakistani "
                  "urban drains are open, warm and untreated, which is why 0.5 is central - "
                  "but EDGAR's waste total sits closer to this reading, and that tension is "
                  "worth seeing rather than resolving by assertion."],
                 ["Sensitivity: wastewater on India's BOD rate (category total)", round(ww_india, 5), "",
                  "34 g/person/day (IPCC Table 6.4, India) instead of the 40 regional default "
                  "that covers Pakistan"]]
              + [[m["item"], "", "", "%.4f Gg CO2 - %s" % (m["emissions_Gg"], m["note"])] for m in memo])

    run.write("waste_air_pollutants_%d.csv" % year,
              ["category", "subitem", "ghg_subitem", "pollutant", "emissions_kt", "uncert_pct"],
              [[r["category"], r["subitem"], r["ghg_subitem"], r["pollutant"],
                round(r["emissions_kt"], 3), round(r["uncert_pct"], 1)] for r in air])

    rows = allocate_rows(comps, downscale.load_shares(), downscale.proxy_for, PROVINCES)
    check_reconciliation(rows, comps)
    prov = {p: 0.0 for p in PROVINCES}
    for r in rows:
        prov[r["province"]] += r["co2e_Mt_AR5"]
    run.write("waste_provincial_%d.csv" % year, ["province", "co2e_Mt_AR5"],
              [[p, round(prov[p], 4)] for p in PROVINCES])

    # The district (ORIGIN) product - canonical-input tier per
    # docs/spatial_products_contract.md, reconciled to the provincial allocation.
    from pkinv.sectors.waste.gis import district_downscale
    district_downscale.main()

    with open(asset_path(OUTPUTS, "waste_report.md"), "w", encoding="utf-8") as f:
        f.write("# Open burning of municipal solid waste (IPCC 4C2), %d\n\n" % year)
        f.write("Waste openly burned: **%.2f Mt/yr** (wet), from a %d-district census-interpolated\n"
                "population panel via IPCC Eq 5.7.\n\n" % (burnt / 1e6, len({r["district"] for r in data.population})))
        f.write("| Stream | Gas | Gg | Mt CO2e (AR5) | +/- |\n|---|---|---|---|---|\n")
        for c in comps:
            f.write("| %s | %s | %.2f | %.3f | %.0f%% |\n"
                    % (c["subitem"], c["gas"], c["emissions_Gg"], c["co2e_Mt_AR5"], c["uncert_pct"]))
        f.write("| **Total** | | | **%.3f** | |\n\n" % total)
        for m in memo:
            f.write("_%s: %.2f Gg CO2._ %s\n\n" % (m["item"], m["emissions_Gg"], m["note"]))
        f.write("## Air pollutants (mass, never CO2e)\n\n| Pollutant | kt | +/- |\n|---|---|---|\n")
        for r in air:
            f.write("| %s | %.1f | %.0f%% |\n" % (r["pollutant"], r["emissions_kt"], r["uncert_pct"]))
    run.record("waste_report.md")

    # The partition as a published account: closure raises here if D + U != G.
    ledger.write(data)

    generated = swds.waste_generated(data)
    disposed = swds.waste_disposed(data)
    print("Municipal solid waste (%d): %.2f Mt generated -> %.2f Mt CO2e (AR5)"
          % (year, generated / 1e6, total))
    print("  %.2f Mt collected and disposed (4A); %.2f Mt uncollected, of which %.2f Mt "
          "burned (4C2)" % (disposed / 1e6, (generated - disposed) / 1e6, burnt / 1e6))
    pop = wastewater.population(data)
    print("  domestic wastewater (4D): %.0f M urban and %.0f M rural on the JMP sanitation "
          "split" % (pop["Urban"] / 1e6, pop["Rural"] / 1e6))
    print("    on the river-discharge MCF it would be %.2f Mt instead of %.2f"
          % (ww_river, sum(c["co2e_Mt_AR5"] for c in comps
                           if c["category"] == wastewater.CATEGORY)))
    for c in comps:
        print("  %-38s %8.2f Gg  %6.3f Mt CO2e" % (c["subitem"], c["emissions_Gg"], c["co2e_Mt_AR5"]))
    print("  provincial reconciliation exact; %s" % ", ".join("%s %.3f" % (p, prov[p]) for p in PROVINCES))

    from pkinv.sectors.waste import monthly
    monthly.main()

    run.finalize(qa_table="waste_qa_%d.csv" % year)


if __name__ == "__main__":
    main()

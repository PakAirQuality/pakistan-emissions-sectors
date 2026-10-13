"""Run the residential fuel-combustion inventory (IPCC 1A4b) and write its outputs.

Usage:  python3 -m pkinv.sectors.residential.run_residential
Writes: outputs/residential_totals_2024.csv, residential_by_stream_2024.csv,
        residential_fuel_2024.csv, residential_provincial_2024.csv
"""
import os

from pkinv.core.downscale import allocate_rows, check_reconciliation
from pkinv.core.geography import PROVINCES
from pkinv.core.runner import Runner
from pkinv.paths import OUTPUTS
from pkinv.sectors.residential import (air_pollutants, combustion, downscale, dung_ledger,
                                       engine, hies, official_reporting, uncertainty)
from pkinv.sectors.residential.data import ResidentialData

VINTAGE_NOTE = ("Fossil streams are FY2023-24 (OGRA); the dung-cake stream is the "
                "household survey's per-household quantity interpolated between the HIES "
                "2018-19 and 2024-25 rounds; firewood rides the 2024-25 round as measured. "
                "Mixed vintages inside one sector, stated rather than smoothed over.")


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = ResidentialData()
    year = data.year
    run = Runner("residential", declared=(
        "residential_by_stream_%d.csv" % year, "residential_totals_%d.csv" % year,
        "residential_configurations_%d.csv" % year,
        "residential_air_pollutants_%d.csv" % year, "residential_fuel_%d.csv" % year,
        "residential_hies_comparison_%d.csv" % year, "residential_strata_%d.csv" % year,
        "residential_provincial_%d.csv" % year))
    comps = engine.build_components(data)
    memo = engine.memo_items(data)
    total = sum(c["co2e_Mt_AR5"] for c in comps)
    tj = combustion.fuel_TJ(data)

    run.write("residential_by_stream_%d.csv" % year,
           ["category", "subitem", "gas", "fossil", "emissions_Gg", "co2e_Mt_AR5",
            "co2e_Mt_AR6", "uncert_pct"],
           [[c["category"], c["subitem"], c["gas"], c.get("fossil", False),
             round(c["emissions_Gg"], 4), round(c["co2e_Mt_AR5"], 5),
             round(c["co2e_Mt_AR6"], 5), round(c["uncert_pct"], 1)] for c in comps])

    none = sum(c["co2e_Mt_AR5"] for c in engine.build_components(data, woodfuel_override="none"))
    lo = sum(c["co2e_Mt_AR5"] for c in engine.build_components(data, woodfuel_override="low"))
    hi = sum(c["co2e_Mt_AR5"] for c in engine.build_components(data, woodfuel_override="high"))
    ledger_comps = engine.build_components(data, dung_basis="ledger")
    ledger_cfg = sum(c["co2e_Mt_AR5"] for c in ledger_comps)
    ledger_dung_mt = sum(c["co2e_Mt_AR5"] for c in ledger_comps
                         if c["subitem"].startswith("Dung"))
    # a reading of configuration L's own mass chain, so it is measured from L
    legacy = ledger_cfg - ledger_dung_mt * (
        1.0 - combustion.dung_vs_kg(data)
        / combustion.dung_air_dry_kg(data, basis="ledger"))
    run.write("residential_totals_%d.csv" % year,
           ["category", "co2e_Mt_AR5", "co2e_Mt_AR6", "note"],
           [[combustion.CATEGORY, round(total, 5),
             round(sum(c["co2e_Mt_AR6"] for c in comps), 5),
             "1A4b, anchored on fuel supplied to households; household dung is what "
             "the HIES rounds report burning (the reference since rc67). Configuration "
             "L, all the dung agriculture diverts burned in households, is reported "
             "alongside - see residential_configurations_%d.csv. " % year + VINTAGE_NOTE],
            ["Sensitivity: dung configuration L (all diverted dung)",
             round(ledger_cfg, 5), "",
             "A destination assumption for the diverted dung, the reference through "
             "rc66; not a reading of household use"],
            ["Sensitivity: dung legacy VS basis", round(legacy, 5), "",
             "Configuration L on the superseded three-bases conflation, kept visible"],
            ["Sensitivity: firewood excluded", round(none, 5), "",
             "What the sector would report if the HIES firewood quantity were dropped"],
            ["Sensitivity: firewood low", round(lo, 5), "", "HIES quantity less 35%"],
            ["Sensitivity: firewood high", round(hi, 5), "", "HIES quantity plus 35%"]]
           + [[m["item"], "", "", "%.1f Gg CO2 - %s" % (m["emissions_Gg"], m["note"])]
              for m in memo])

    # TWO CONFIGURATIONS. Household dung has a demand-side observation (the survey, S)
    # and agriculture's diverted supply (the ledger, L), about five times larger. Since
    # rc67 the reference is S, because the residential row is meant to measure what
    # households burn, and L is a destination assumption for the whole diverted supply.
    # Every headline quantity is still reported under both.
    from pkinv.sectors.transport import air_pollutants as road_air
    from pkinv.sectors.transport.data import TransportData
    # the fleet sum: the transport air layer is per (class, fuel, process) since the
    # EMEP Tier 1 refactor, and the ratio's denominator is the whole EXHAUST fleet -
    # never one fuel, and never the wear processes the ratio's definition excludes
    road_pm = sum(r["emissions_kt"] for r in road_air.compute(TransportData())
                  if r["pollutant"] == "PM2.5" and r["process"] == "exhaust")
    # Every sector except this one, built in-process. This used to read the committed
    # national_all_sectors.csv and subtract the residential row, which made the printed
    # share depend on whether the rollup had been re-run first - and it had not, so the
    # shipped shares (6.34 / 5.29) no longer reproduced against the rollup (6.42 / 5.36).
    # A share that changes depending on file ordering is not a share.
    from pkinv.core import registry
    national_others = sum(
        c["co2e_Mt_AR5"]
        for sector in registry.all_sectors() if sector.NAME != "residential"
        for c in sector.build_components(sector.load_data()))
    config_rows = []
    for code, basis, label in (
            ("S", "survey", "HIES rounds, reported cake (household demand); reference"),
            ("L", "ledger", "agriculture nitrogen ledger (all diverted supply)")):
        c_comps = engine.build_components(data, dung_basis=basis)
        c_memo = engine.memo_items(data, dung_basis=basis)
        c_tj = combustion.fuel_TJ(data, dung_basis=basis)
        c_air = air_pollutants.compute(data, dung_basis=basis)
        c_pm = sum(r["emissions_kt"] for r in c_air if r["pollutant"] == "PM2.5")
        c_bc = sum(r["emissions_kt"] for r in c_air if r["pollutant"] == "BC")
        c_co2e = sum(c["co2e_Mt_AR5"] for c in c_comps)
        config_rows.append({
            "configuration": code, "dung_quantity_basis": label,
            "dung_air_dry_Mt": round(
                combustion.dung_air_dry_kg(data, basis=basis) / 1e9, 2),
            "energy_TJ": round(sum(c_tj.values())),
            "co2e_Mt_AR5": round(c_co2e, 3),
            "co2e_Mt_AR6": round(sum(c["co2e_Mt_AR6"] for c in c_comps), 3),
            "memo_biogenic_Gg": round(sum(m["emissions_Gg"] for m in c_memo)),
            "pm25_kt": round(c_pm, 1), "bc_kt": round(c_bc, 1),
            "pm_ratio_vs_road_exhaust": round(c_pm / road_pm, 1),
            "national_share_pct": (round(100 * c_co2e / (national_others + c_co2e), 2)
                                   if national_others else ""),
            "note": ("the reference; %.1f Mt of diverted air-dry cake has no observed "
                     "household destination and is carried as unresolved, outside the "
                     "total" % ((combustion.dung_air_dry_kg(data, basis="ledger")
                                 - combustion.dung_air_dry_kg(data)) / 1e9)
                     if code == "S" else
                     "a destination assumption: all the diverted dung burned in "
                     "households. The reference of every release through rc66"),
        })
    run.write("residential_configurations_%d.csv" % year, list(config_rows[0].keys()),
           [list(r.values()) for r in config_rows])

    # The dung-fate account behind the L/S disagreement, closure asserted at write time:
    # D_diverted = D_household + D_unresolved, with S's 46.7 Mt unresolved row explicit.
    dung_ledger.write(data, year=year)

    # The layer that matters most here: household solid fuel is a minor greenhouse-gas
    # sector and Pakistan's dominant source of primary particulate.
    air = air_pollutants.compute(data)
    run.write("residential_air_pollutants_%d.csv" % year,
           ["category", "subitem", "ghg_subitem", "pollutant", "emissions_kt", "uncert_pct"],
           [[r["category"], r["subitem"], r["ghg_subitem"], r["pollutant"],
             round(r["emissions_kt"], 3), round(r["uncert_pct"], 1)] for r in air])

    run.write("residential_fuel_%d.csv" % year, ["stream", "TJ", "share_pct"],
           [[k, round(v, 0), round(v / sum(tj.values()) * 100, 2)]
            for k, v in sorted(tj.items())])

    # Survey versus control, one row per HIES fuel item. Ratios are published
    # diagnostics; the only row where the survey IS the estimate is firewood.
    comp = hies.comparison_rows(data)
    run.write("residential_hies_comparison_%d.csv" % year,
           ["fuel", "role", "unit", "hies2425_annual", "hies2425_users_share",
            "hies1819_annual", "engine_annual", "ratio_hies_over_engine", "note"],
           [[r["fuel"], r["role"], r["unit"], r["hies2425_annual"],
             r["hies2425_users_share"], r["hies1819_annual"], r["engine_annual"],
             r["ratio_hies_over_engine"], r["note"]] for r in comp])

    strata = downscale.strata_rows(data, comps)
    run.write("residential_strata_%d.csv" % year,
           ["fuel", "province", "region", "hies_share", "allocated_Mt_co2e", "basis"],
           [[r["fuel"], r["province"], r["region"], r["hies_share"],
             r["allocated_Mt_co2e"], r["basis"]] for r in strata])

    rows = allocate_rows(comps, downscale.load_shares(), downscale.proxy_for, PROVINCES)
    check_reconciliation(rows, comps)
    prov = {p: 0.0 for p in PROVINCES}
    for r in rows:
        prov[r["province"]] += r["co2e_Mt_AR5"]
    run.write("residential_provincial_%d.csv" % year, ["province", "co2e_Mt_AR5"],
           [[p, round(prov[p], 5)] for p in PROVINCES])

    print("Residential fuel combustion (1A4b) FY%d-%02d: %.2f Mt CO2e (AR5)"
          % (year - 1, year % 100, total))
    by_stream = {}
    for c in comps:
        by_stream.setdefault(c["subitem"].rsplit(" ", 1)[0], 0.0)
        by_stream[c["subitem"].rsplit(" ", 1)[0]] += c["co2e_Mt_AR5"]
    for s, v in sorted(by_stream.items(), key=lambda kv: -kv[1]):
        print("  %-12s %9.0f TJ  %6.2f Mt CO2e" % (s, tj[s], v))
    for m in memo:
        print("  memo: %-52s %8.0f Gg CO2" % (m["item"], m["emissions_Gg"]))
    print("  firewood sensitivity: %.2f (excluded) to %.2f Mt (HIES +35%%)" % (none, hi))
    print("  r_dung (ledger air-dry / HIES-reported cake): %.2f - published, never applied"
          % hies.r_dung(data))
    lo, hi_b = hies.residue_implied_range_kg()
    print("  residue ledger %.2f Mt air-dry, inside the HIES price bracket %.1f-%.1f Mt"
          % (combustion.residue_air_dry_kg(data) / 1e9, lo / 1e9, hi_b / 1e9))
    print("  generator carve-out: %.1f kt petrol deducted from the road control"
          % combustion.generator_petrol_kt(data))
    print("  dung cake closes against agriculture: %.3f Mt N -> %.1f Mt VS -> %.1f Mt dry "
          "solids -> %.1f Mt air-dry cake"
          % (sum(combustion.diverted_n_by_species().values()) / 1e9,
             combustion.dung_vs_kg(data) / 1e9, combustion.dung_ts_kg(data) / 1e9,
             combustion.dung_air_dry_kg(data) / 1e9))
    totals = {}
    for r in air:
        totals[r["pollutant"]] = totals.get(r["pollutant"], 0.0) + r["emissions_kt"]
    print("  air pollutants (all streams): %.0f kt PM2.5, %.0f kt BC, %.0f kt NOx - the "
          "dominant particulate source in the country"
          % (totals["PM2.5"], totals["BC"], totals["NOx"]))
    print("  provincial reconciliation exact; %s"
          % ", ".join("%s %.1f" % (p, prov[p]) for p in PROVINCES))
    print("-- official benchmarks --")
    official_reporting.main()
    print("-- uncertainty --")
    uncertainty.main()
    print("-- district allocation --")
    from pkinv.sectors.residential.gis import district_downscale
    district_downscale.main()
    print("-- time series --")
    from pkinv.sectors.residential import timeseries
    timeseries.main()
    print("-- monthly profiles --")
    from pkinv.sectors.residential import monthly
    monthly.main()

    run.finalize(qa_table="residential_qa_%d.csv" % year)


if __name__ == "__main__":
    main()

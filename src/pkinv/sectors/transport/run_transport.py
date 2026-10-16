"""Run the road-transport inventory (IPCC 1A3b) and write its outputs.

Orchestrates the core GHG and air layers, the fuel-claimant ledger, the uncertainty
system, and closes with a run manifest that hashes every primary source - the railways
pattern. Each phase module keeps its own main() for standalone runs.

Usage:  python3 -m pkinv.sectors.transport.run_transport
Writes: ~12 outputs/transport_* files and outputs/transport_run_manifest_2024.json
"""

from pkinv.assets import asset_path
import glob
import json
import os

from pkinv.core import documents
from pkinv.core.components import enrich_co2e as enrich
from pkinv.core.downscale import allocate_rows, check_reconciliation
from pkinv.core.geography import PROVINCES
from pkinv.core.runner import Runner
from pkinv.paths import OUTPUTS, ROOT
from pkinv.sectors.transport import (air_pollutants, cng, cng_gap, downscale, engine,
                                     fuel_gap, fuel_ledger, monthly, navigation_screen,
                                     ocac_diagnostics, offroad, road, timeseries,
                                     uncertainty)
from pkinv.sectors.transport.data import TransportData


def _fiscal_label():
    """The sector's own reporting period, for the notes that name it.

    These strings were literals. When the sector moved from FY2021-22 to FY2023-24 the
    numbers moved and the labels did not, so the run manifest, the totals note and the fuel
    ledger all described current controls as FY2021-22 for a full release. A basis that names
    the wrong year is worse than no basis: it is checkable and wrong.
    """
    from pkinv.core import period, registry
    s = registry.get("transport")
    return period.label(s.PERIOD_START, s.PERIOD_END)


FY = _fiscal_label()

MANIFEST_SOURCES = (
    # The workbooks AND the transcribed CSVs are both hashed, deliberately: the ingest
    # script's recorded source path predates the sources/ reorganisation, so the CSVs
    # under data/activity/transport/ are the operative inputs and the workbooks are
    # the provenance they were transcribed from. The OCAC sectoral PDFs - the fuel
    # controls' primary source since the August 2026 re-anchor - live under
    # sources/Aviation/ because that sector fetched them first.
    "sources/Transport/*.xlsx",
    "sources/Punjab Transport/*.xlsx",
    "sources/Punjab Transport/Punjab Transport.pdf",
    "sources/OGRA/*.pdf",
    "sources/Railways/ipcc_2006_v2_ch3_mobile.pdf",
    "sources/Aviation/ocac_annual/*.pdf",
    "sources/Aviation/ocac_monthly/*.pdf",
    "data/activity/transport/*.csv",
    "data/transport_params.csv",
)


def _manifest(data, out_path=None):
    # `out_path`: where to write. The runner writes the canonical outputs/ file; a test that
    # wants the manifest's CONTENT passes a temporary path, because writing into outputs/
    # from a test replaced a packaged output inside the rc40 validation package (the
    # package registers the transport workbooks rather than shipping them, so the
    # rewritten hashed-sources list differed) - found by the package's own container run.
    # rc41: hashed live where held, carried from data/raw_manifest.csv where not
    # (pkinv.core.documents.digests) - the same list in a tree without the workbooks.
    sources = documents.digests(MANIFEST_SOURCES)
    from pkinv.run_all import written_by_other_phases
    _others = written_by_other_phases('pkinv.sectors.transport.run_transport')
    scen = [r["structural_scenario"] for r in uncertainty.structural_scenarios(
        data, n_iter=10)]
    manifest = {
        "inventory": "Pakistan road transport (1.A.3.b) and off-road machinery "
                     "(1.A.4.c ii)",
        "reference_year": "2024 = FY2023-24, the common reference period; petrol/diesel "
                          "controls OCAC FY2023-24 Road rows. Two SHAPES are borrowed "
                          "because the reference period does not carry them: the class "
                          "split rides the 2023 registration panel (2024 reports 30 percent "
                          "of the best-covered year) and the provincial split rides the "
                          "FY2024-25 monthly area pages (FY2023-24 has one month, not "
                          "twelve). Neither moves a tonne - see "
                          "outputs/transport_provincial_shape_brackets.csv. Generator "
                          "carve-out HIES 2024-25; rail cross-check now year-matched.",
        # Interpolated from the live data layer, never typed: a hard-coded pair in
        # this string sat at the FY2021-22 tonnages for a full release while the label
        # beside it said FY2023-24 - the exact failure the module docstring warns about.
        "control_totals": "petrol %.1f kt/yr (Road MS+HOBC) and HSD %.1f kt/yr "
                          "(Road row), OCAC Sectoral Sales %s; CNG %.0f MMCFD "
                          "%s (OGRA Tables 3.31/6.1)"
                          % (data.efv("transport_fuel_supply", "Motor Gasoline"),
                             data.efv("transport_fuel_supply", "Gas/Diesel Oil"),
                             FY, data.cng_mmcfd(), FY),
        "methods": {
            "ghg": "IPCC 2006 Vol 2 Ch 3 Tier 1, fuel-anchored: Table 3.2.1/3.2.2 "
                   "road, Table 3.3.1 off-road; CNG on OGRA metered gas",
            "air": "EMEP/EEA 2023 Tier 1 per class and process on the OCAC road fuel "
                   "(exhaust, evaporation, tyre and brake wear, road wear); SO2 from declared "
                   "fuel sulfur; resuspended dust not estimated (air_pollutants.py)",
            "spatial": "province proxies in data/province_shares.csv "
                       "(transport_vkt, transport_offroad, transport_cng_vkt)",
            "ledger": "fuel-claimant ledger over both petroleum controls, unresolved "
                      "claimants carried as status (fuel_ledger.py)",
        },
        "monte_carlo": {"iterations": 10000, "national_seed": 42,
                        "scenario_seed": uncertainty.SCENARIO_SEED,
                        "distribution": "lognormal",
                        "structural_scenarios": scen},
        "sources": sources,
        # rc41: the disk glob minus what OTHER phases declare they write and the manifest
        # itself (run_all.written_by_other_phases) - a first run from an empty outputs/
        # and the fixpoint tree list the same files.
        "generated_outputs": sorted(
            name for name in (os.path.basename(p)
                              for p in glob.glob(asset_path(OUTPUTS, "transport_*")))
            if name not in _others and not name.startswith("transport_run_manifest_")),
    }
    path = out_path or asset_path(OUTPUTS, "transport_run_manifest_%d.json" % data.year)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return path, len(sources)


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = TransportData()
    year = data.year
    run = Runner("transport", declared=(
        "transport_by_stream_%d.csv" % year,
        "transport_totals_%d.csv" % year,
        "transport_air_pollutants_%d.csv" % year,
        "transport_fuel_%d.csv" % year,
        "transport_provincial_%d.csv" % year,
        "transport_cng_%d.csv" % year,
        "transport_cng_crosscheck_%d.csv" % year,
        "transport_provincial_proxy_comparison_%d.csv" % year,
        "transport_calendar_year_controls_%d.csv" % year))
    comps = engine.build_components(data)
    memo = engine.memo_items(data)
    total = sum(c["co2e_Mt_AR5"] for c in comps)
    tj = road.fuel_TJ(data)
    _vkt, cells, capped = road.effective_vkt(data)

    run.write("transport_by_stream_%d.csv" % year,
           ["category", "subitem", "gas", "fossil", "emissions_Gg", "co2e_Mt_AR5",
            "co2e_Mt_AR6", "uncert_pct"],
           [[c["category"], c["subitem"], c["gas"], c.get("fossil", False),
             round(c["emissions_Gg"], 4), round(c["co2e_Mt_AR5"], 5),
             round(c["co2e_Mt_AR6"], 5), round(c["uncert_pct"], 1)] for c in comps])

    by_cat = {}
    for c in comps:
        by_cat.setdefault(c["category"], [0.0, 0.0])
        by_cat[c["category"]][0] += c["co2e_Mt_AR5"]
        by_cat[c["category"]][1] += c["co2e_Mt_AR6"]
    # The published heating-value sensitivity, computed the same way the captive category's is.
    cng_900 = sum(c["co2e_Mt_AR5"] for c in engine.build_components(data, cng_hhv_btu=900))
    off_tj = road.off_road_TJ(data)
    road_n2o = off_tj * data.efv("transport_fuel_n2o", "Gas/Diesel Oil") / 1e6 * 265 / 1000.0
    run.write("transport_totals_%d.csv" % year, ["category", "co2e_Mt_AR5", "co2e_Mt_AR6", "note"],
           [[c, round(v[0], 5), round(v[1], 5),
             "1A3b, on TWO activity bases: petrol and diesel from OCAC's " + FY + " "
             "Road customer-class rows (rail excluded by construction; generator "
             "petrol carved out by relay), and CNG from OGRA's metered sector gas. "
             "They are different fuels from different statistics and cannot "
             "double-count." if c == road.CATEGORY else
             "Reported under 1A4c ii; the class mixes agricultural machinery with the "
             "source workbook's residual bucket, incl. construction machinery IPCC "
             "books to 1A2 gvii - hence the mixed name. Carved from the same diesel "
             "control by vehicle-km share; IPCC Vol 2 Ch 3 Table 3.3.1 factors, not "
             "the road table"]
            for c, v in by_cat.items()]
           + [["TOTAL", round(total, 5), round(sum(c["co2e_Mt_AR6"] for c in comps), 5), ""],
              ["Sensitivity: CNG at 900 Btu/scf", round(cng_900, 5), "",
               "The CNG heating value is the assumption in that stream, as it is for captive "
               "gas: OGRA reports a volume and IPCC works in net terajoules. Pakistani "
               "pipeline gas runs 900-1,000 Btu/scf and nothing read here pins it. This is "
               "the whole-sector total with CNG at 900 instead of 1,000."],
              ["Diagnostic: off-road N2O on the road factor", round(road_n2o, 5), "",
               "What 1A4c would report for N2O using Table 3.2.2 (3.9 kg/TJ) instead of "
               "Table 3.3.1 (28.6). The gap is why the table choice is pinned by a test."]]
           + [[m["item"], "", "", "%.4f Gg CO2 - %s" % (m["emissions_Gg"], m["note"])]
              for m in memo])

    # Mass, never CO2e. ONE producer per artifact (the rc41 rule this block once
    # violated): the Tier 1 engine's own writer emits the file - ten columns, LF,
    # %.6f - and the runner only RECORDS it, so a runner re-run and a standalone
    # `python3 -m pkinv.sectors.transport.air_pollutants` produce identical bytes
    # instead of flip-flopping schemas, which is exactly what broke a gate's
    # noise check the day the second writer survived the refactor.
    air_pollutants.main()
    run.record("transport_air_pollutants_%d.csv" % year)

    run.write("transport_fuel_%d.csv" % year, ["fuel", "TJ", "share_pct"],
           [[f, round(v, 0), round(v / sum(tj.values()) * 100, 2)] for f, v in sorted(tj.items())])

    rows = allocate_rows(comps, downscale.load_shares(), downscale.proxy_for, PROVINCES)
    check_reconciliation(rows, comps)
    prov = {p: 0.0 for p in PROVINCES}
    for r in rows:
        prov[r["province"]] += r["co2e_Mt_AR5"]
    run.write("transport_provincial_%d.csv" % year, ["province", "co2e_Mt_AR5"],
           [[p, round(prov[p], 5)] for p in PROVINCES])

    print("Transport sector FY%d: %.2f Mt CO2e (AR5)" % (year, total))
    for c, v in by_cat.items():
        print("  %-26s %6.2f Mt" % (c, v[0]))
    by_fuel = {}
    for c in comps:
        if c["category"] != road.CATEGORY:
            continue
        fuel = c["subitem"].split()[-2]
        by_fuel[fuel] = by_fuel.get(fuel, 0.0) + c["co2e_Mt_AR5"]
    for f, v in sorted(by_fuel.items()):
        print("    on-road %-8s %6.2f Mt" % (f, v))
    for m in memo:
        print("  memo: %s: %.1f Gg CO2 (outside the total)" % (m["item"], m["emissions_Gg"]))
    # The fleet-cap diagnostic: how often equation 6's survival model exceeds the stock
    # ever registered. It measures how pervasive the source workbook's defect is.
    print("  fleet cap binds on %d of %d district-class cells (%.0f%%)"
          % (capped, cells, 100.0 * capped / cells if cells else 0.0))
    # fleet sums over the engine's own rows (per class x fuel x process since Tier 1)
    air = air_pollutants.compute(data)
    fleet = lambda pol: sum(r["emissions_kt"] for r in air if r["pollutant"] == pol)
    print("  air pollutants (all processes): %.1f kt PM2.5, %.0f kt NOx, %.0f kt CO"
          % (fleet("PM2.5"), fleet("NOx"), fleet("CO")))
    # The CNG omission, sized in vehicle-kilometres. Not an emissions estimate: see
    # sectors/transport/cng_gap.py for why neither route to one is open yet.
    run.write("transport_cng_%d.csv" % year,
           ["fiscal_year", "mmcfd", "TJ_net", "mt_co2e_AR5"],
           [[y, data.cng_mmcfd(y), round(cng.gas_TJ(data, y), 1),
             round(sum(c["co2e_Mt_AR5"] for c in enrich(cng.compute(data, y))), 5)]
            for y in data.cng_years()])

    cng_summary = cng_gap.summary(data)
    run.write("transport_cng_crosscheck_%d.csv" % year,
           ["item", "value", "unit", "note"],
           [["Metered gas (OGRA)", round(cng_summary["gas_TJ"], 1), "TJ net",
             "sets the emissions"],
            ["Modelled CNG travel (fleet)", round(cng_summary["cng_vkt"], 0), "vehicle-km",
             "sets the geography and the air-pollutant layer; %.2f%% of all road vehicle-km"
             % cng_summary["share_pct"]],
            ["Implied energy intensity", round(cng_summary["mj_per_km"], 3), "MJ/vehicle-km",
             "%s - plausible band %.1f-%.1f MJ/km for a fleet %.0f%% three-wheeler by "
             "distance; bounds are judgement, not a Pakistani measurement"
             % (cng_summary["verdict"], cng_gap.PLAUSIBLE_MJ_PER_KM[0],
                cng_gap.PLAUSIBLE_MJ_PER_KM[1],
                next((sh for c, _v, sh in cng_summary["by_class"] if c == "3W"), 0.0))]]
           + [["CNG travel %s" % c, round(v, 0), "vehicle-km",
               "%.2f%% of CNG vehicle-km" % sh] for c, v, sh in cng_summary["by_class"]])

    print("  CNG: %.2f Mt from %.0f MMCFD of metered gas; fleet model puts %.2f%% of road "
          "vehicle-km on CNG, implying %.2f MJ/km (%s)"
          % (sum(c["co2e_Mt_AR5"] for c in comps if c["subitem"].startswith("CNG")),
             data.cng_mmcfd(), cng_summary["share_pct"], cng_summary["mj_per_km"],
             cng_summary["verdict"]))
    print("  provincial reconciliation exact; %s"
          % ", ".join("%s %.1f" % (p, prov[p]) for p in PROVINCES))

    # The provincial-proxy comparison: fuel-sales allocation vs the superseded
    # registration diagnostic - the published record of why the proxy changed.
    shares = downscale.load_shares()
    run.write("transport_provincial_proxy_comparison_%d.csv" % year,
           ["province", "fuel_sales_Mt", "registration_Mt", "petrol_share_fuel",
            "diesel_share_fuel", "share_registration"],
           [[p, round(prov[p], 5),
             round(total * shares[downscale.REGISTRATION_PROXY][p], 5),
             shares[downscale.PETROL_PROXY][p], shares[downscale.DIESEL_PROXY][p],
             shares[downscale.REGISTRATION_PROXY][p]] for p in PROVINCES])
    chk = road.rail_crosscheck(data)
    print("  rail cross-check: Year Book %.1f kt vs OCAC Railways %.1f kt (%.1f%%)"
          % (chk["yb_kt"], chk["ocac_kt"], 100 * chk["rel_diff"]))

    # The calendar-year construction the crosswalk cites: national-only (the
    # cumulative editions carry no provincial pages), mixed monthly/annual vintage
    # declared, demand-collapse context stated.
    cy = timeseries.calendar_year_road_t(2022)
    cy_petrol = (cy["MS"] + cy["HOBC"]) / 1000.0
    cy_diesel = cy["HSD"] / 1000.0
    fy_petrol = data.efv("transport_fuel_supply", "Motor Gasoline")
    fy_diesel = data.efv("transport_fuel_supply", "Gas/Diesel Oil")
    run.write("transport_calendar_year_controls_%d.csv" % year,
           ["item", "value", "unit", "note"],
           [["CY2022 Road petrol (MS+HOBC)", round(cy_petrol, 3), "kt",
             "Jan-Jun direct monthlies + Dec cumulative (Jul-Dec FYTD); "
             "mixed monthly/annual vintage ~0.2%"],
            ["CY2022 Road diesel (HSD)", round(cy_diesel, 3), "kt",
             "same construction; CY2022 straddles the mid-2022 demand collapse"],
            ["CY/FY petrol ratio", round(cy_petrol / fy_petrol, 6), "",
             "vs the %s Road row" % FY],
            ["CY/FY diesel ratio", round(cy_diesel / fy_diesel, 6), "",
             "vs the %s Road row" % FY],
            ["Provincial coverage", "", "",
             "cumulative editions are national-only: no provincial detail for "
             "Jul-Dec of the calendar year"]])

    # The parity phases: ledger -> uncertainty -> series -> fleet diagnostic ->
    # manifest, each with its own main() for standalone runs. The manifest goes
    # LAST so generated_outputs is complete.
    fuel_ledger.main()
    fuel_ledger.write_bridge(data)
    navigation_screen.write()
    ocac_diagnostics.main(data)
    uncertainty.main()
    timeseries.main()
    fuel_gap.main()
    monthly.main()
    # finalize BEFORE the manifest, which globs outputs/transport_* from disk.
    run.finalize(qa_table="transport_qa_%d.csv" % year)
    path, n = _manifest(data)
    print("  manifest: %d sources hashed -> %s" % (n, os.path.relpath(path, ROOT)))


if __name__ == "__main__":
    main()

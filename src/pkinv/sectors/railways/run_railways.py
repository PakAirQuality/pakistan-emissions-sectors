"""Run the railway inventory (IPCC 1A3c) and write its outputs.

Orchestrates the whole stdlib pipeline - core GHG, the EMEP air layer, the Tier 2
diagnostic, the official-benchmark extraction, the uncertainty system, the intensity
quotients, the quinquennial history - and closes with a run manifest that hashes every
primary source. Each phase module keeps its own main() for standalone runs (the power
pattern); the spatial products live behind the gis extra as a separate entry point
(pkinv.sectors.railways.gis.run_gis).

Usage:  python3 -m pkinv.sectors.railways.run_railways
Writes: ~17 outputs/railways_* files and outputs/railways_run_manifest_2024.json
"""

from pkinv.assets import asset_path
import glob
import json
import os

from pkinv.core import documents
from pkinv.core.downscale import allocate_rows, check_reconciliation
from pkinv.core.geography import PROVINCES
from pkinv.core.runner import Runner
from pkinv.paths import OUTPUTS, ROOT
from pkinv.sectors.railways import (air_pollutants, downscale, efficiency, engine,
                                    fuel_claimants,
                                    history, monthly, official_reporting, reconcile,
                                    tier2, traction, uncertainty, wear_pm)
from pkinv.sectors.railways.data import RailwaysData

MANIFEST_SOURCES = (
    "sources/Railways/*.pdf",
    "sources/Aviation/PAK_CRT_2024.zip",
    "sources/EMEP/emep_eea_2023_1a3c_railways.pdf",
    "sources/UNFCCC/*.pdf",
    "data/gis/rail/pak_rail_network.geojson",
    "data/gis/rail/RAIL_SOURCES.json",
)

# Deliberately untracked local copies (.gitignore's Railways block: 146 MB of scanned
# editions, re-fetchable, and NOT needed for the fuel series - see reconcile.py). The
# manifest must describe the RELEASE, so a file a clean clone cannot have may not
# appear in it just because the maintainer's disk holds one: that is exactly the
# clean-room diff scripts/clean_rebuild.sh caught in rc10.
MANIFEST_UNTRACKED_SCANS = frozenset((
    "sources/Railways/yearbook2017_18.pdf",
    "sources/Railways/yearbook2018_19.pdf",
    "sources/Railways/yearbook2019_20.pdf",
    "sources/Railways/yearbook2021_22.pdf",
    "sources/Railways/yearbook2024-25.pdf",
))


def _manifest(data):
    # rc41: hashed live where held, carried from data/raw_manifest.csv where not
    # (pkinv.core.documents.digests) - the same list in a tree without the documents.
    sources = documents.digests(MANIFEST_SOURCES, skip=MANIFEST_UNTRACKED_SCANS)
    from pkinv.run_all import written_by_other_phases
    _others = written_by_other_phases('pkinv.sectors.railways.run_railways')
    scen = [r["structural_scenario"] for r in uncertainty.structural_scenarios(
        data, n_iter=10)]
    manifest = {
        "inventory": "Pakistan railways, IPCC 1.A.3.c",
        "reference_year": "FY2023-24 (series year 2024); FY2025 provisional in the series",
        "control_total": "Year Book fuel consumption: 132,588 thousand litres diesel "
                         "+ 79.907 t furnace oil",
        "methods": {
            "ghg": "IPCC 2006 Vol 2 Ch 3 Table 3.4.1 Tier 1",
            "air": "EMEP/EEA 2023 ch 1.A.3.c Table 3-1 Tier 1; SO2 stoichiometric "
                   "under declared sulfur cases",
            "spatial": "route-constrained network model (gis extra), shares transcribed "
                       "to data/province_shares.csv",
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
                              for p in glob.glob(asset_path(OUTPUTS, "railways_*")))
            if name not in _others and not name.startswith("railways_run_manifest_")),
    }
    path = asset_path(OUTPUTS, "railways_run_manifest_%d.json" % data.year)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return path, len(sources)


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = RailwaysData()
    year = data.year
    run = Runner("railways", declared=(
        "railways_by_stream_%d.csv" % year, "railways_totals_%d.csv" % year,
        "railways_fuel_reconciliation_%d.csv" % year, "railways_fuel_%d.csv" % year,
        "railways_provincial_%d.csv" % year, "railways_timeseries_%d.csv" % year))
    comps = engine.build_components(data)
    fuel_claimants.main()
    total = sum(c["co2e_Mt_AR5"] for c in comps)
    tj = traction.fuel_TJ(data)

    run.write("railways_by_stream_%d.csv" % year,
           ["category", "subitem", "gas", "fossil", "emissions_Gg", "co2e_Mt_AR5",
            "co2e_Mt_AR6", "uncert_pct"],
           [[c["category"], c["subitem"], c["gas"], c.get("fossil", False),
             round(c["emissions_Gg"], 4), round(c["co2e_Mt_AR5"], 5),
             round(c["co2e_Mt_AR6"], 5), round(c["uncert_pct"], 1)] for c in comps])

    # What the sector would report on the road N2O factor, which is the mistake the
    # rail-specific table exists to prevent.
    road_n2o = sum(tj.values()) * 3.9 / 1e6 * 265 / 1000.0
    rail_n2o = sum(c["co2e_Mt_AR5"] for c in comps if c["gas"] == "N2O")
    # BUR-1's inventory year is fiscal 2017-18, series year 2018 (years are labelled by
    # ending year). The primary benchmark is matched-year: same method, same GWP basis,
    # the BUR's own year. The reference-year figure is reported separately.
    bur_year = 2018
    matched = engine.build_components(data, bur_year)
    matched_total = sum(c["co2e_Mt_AR5"] for c in matched)
    by_cat5 = {}
    by_cat6 = {}
    for c in comps:
        by_cat5[c["category"]] = by_cat5.get(c["category"], 0.0) + c["co2e_Mt_AR5"]
        by_cat6[c["category"]] = by_cat6.get(c["category"], 0.0) + c["co2e_Mt_AR6"]
    run.write("railways_totals_%d.csv" % year,
           ["category", "co2e_Mt_AR5", "co2e_Mt_AR6", "note"],
           [[traction.CATEGORY, round(by_cat5[traction.CATEGORY], 5),
             round(by_cat6[traction.CATEGORY], 5),
             "1A3c, LOCOMOTIVE TRACTION ONLY under the re-based reference: the Year Book "
             "detail table splits locomotive from other-than-locomotive fuel, and the "
             "measured non-traction share books at its own category below. From "
             "Pakistan Railways Year Book metered fuel consumption. The mainline "
             "network has been diesel-only since about 2010 (electric energy NIL from "
             "the 2010-2015 quinquennium), so there is no scope-2 stream in the "
             "inventory years; urban electric rail is outside the operator and "
             "accounted under power."],
            [traction.NON_TRACTION_CATEGORY,
             round(by_cat5[traction.NON_TRACTION_CATEGORY], 5),
             round(by_cat6[traction.NON_TRACTION_CATEGORY], 5),
             "Workshops, power houses, pumps and track machinery, measured by the "
             "Year Book detail table and booked at its own category since rc11 - by "
             "IPCC definition this fuel belongs in 1.A.2 / 1.A.4.c BY USE, and the "
             "source publishes no per-use split, which the category name declares. "
             "Rail factors retained (no use-specific factor is supportable), so the "
             "module total is conserved exactly against the pre-rc11 booking."],
            ["Module total (both categories)", round(total, 5),
             round(sum(c["co2e_Mt_AR6"] for c in comps), 5),
             "the conserved sector total: traction plus non-traction equals the "
             "summary fuel account's emissions to the last digit"],
            ["Diagnostic: N2O on the road factor", round(total - rail_n2o + road_n2o, 5),
             "", "What this sector would report if IPCC Table 3.2.2 (road, 3.9 kg N2O/TJ) "
                 "were used instead of Table 3.4.1 (rail, 28.6). The gap is the reason "
                 "the table choice is pinned by a test."],
            ["Non-traction share of diesel",
             round(100 * reconcile.non_traction_share(data), 4), "",
             "PERCENT, not Mt: the fraction of railway diesel burnt by workshops, power "
                 "houses, pumps and track machines rather than by locomotives, from the "
                 "detail table (since the 2024-25 restatement the detail and summary "
                 "denominators agree to one part in 132,588). This sector used to call "
                 "that split unobtainable. By IPCC definition the fuel belongs outside "
                 "1A3c - track machinery in off-road transport, workshops and power houses "
                 "in stationary combustion, pumps by end use - not as a single block in "
                 "1A4c ii. Since rc11 it is BOOKED AT ITS OWN CATEGORY (1A2/1A4c "
                 "unresolved) rather than left in 1A3c; only the final end-use split "
                 "awaits the source."],
            # This row used to be called "Deducted from road transport", and it named a
            # subtraction that no longer happens: while transport anchored on a single
            # national HSD supply figure it removed this quantity so the two sectors could
            # not double-count, but transport now anchors on the petroleum industry's
            # customer classes, where Railways is its own row and the double-count is
            # excluded at source. The quantity is unchanged and still worth publishing -
            # it is what the operator's own meters say - so the row stayed and only its
            # claim about what transport does with it was wrong, for one release.
            ["Traction diesel, for cross-source comparison",
             round(traction.diesel_kt(data), 2),
             "", "kt of diesel, not Mt CO2e: the operator's own metered traction fuel, "
                 "published for comparison against the petroleum industry's Railways "
                 "customer-class total. Transport no longer deducts it - Railways is "
                 "outside the Road customer class by construction - so this is an "
                 "independent cross-source check, not an internal correction."],
            ["Matched year: own FY2017-18 estimate", round(matched_total, 5),
             round(sum(c["co2e_Mt_AR6"] for c in matched), 5),
             "Mt CO2e by the identical method for series year 2018 (fiscal 2017-18), "
                 "the inventory year BUR-1 reports as 4.06 Mt. The matched-year ratio is "
                 "8.7. This is the primary benchmark; the reference-year figure differs "
                 "from the BUR's year by fuel (18 percent), not by method."]])

    # The Year Book against itself. Diagnostic: it does not move the reported number, which
    # stays on the Principal Statistics summary the whole series is built from.
    rec = reconcile.reconciliation(data)
    run.write("railways_fuel_reconciliation_%d.csv" % year,
           ["fiscal_year", "summary_k_litres", "locomotive", "other_than_locomotive",
            "detail_total", "diff", "pct", "verdict"],
           [[r["fiscal_year"], round(r["summary"], 0), round(r["locomotive"], 0),
             round(r["other"], 0), round(r["detail_total"], 0), round(r["diff"], 0),
             round(r["pct"], 3),
             "reconciles" if abs(r["pct"]) <= 0.1 else "DISAGREES"] for r in rec])

    run.write("railways_fuel_%d.csv" % year, ["stream", "TJ", "share_pct"],
           [[k, round(v, 1), round(v / sum(tj.values()) * 100, 3)]
            for k, v in sorted(tj.items())])

    rows = allocate_rows(comps, downscale.load_shares(), downscale.proxy_for, PROVINCES)
    check_reconciliation(rows, comps)
    prov = {p: 0.0 for p in PROVINCES}
    for r in rows:
        prov[r["province"]] += r["co2e_Mt_AR5"]
    run.write("railways_provincial_%d.csv" % year, ["province", "co2e_Mt_AR5"],
           [[p, round(prov[p], 5)] for p in PROVINCES])

    series = []
    for y in data.years():
        c = engine.build_components(data, y)
        try:
            fo_q, fo_u = data.quantity("Residual Fuel Oil", y), data.unit(
                "Residual Fuel Oil", y)
        except KeyError:
            fo_q, fo_u = "", ""
        gas = {g: sum(x["emissions_Gg"] for x in c if x["gas"] == g)
               for g in ("CO2", "CH4", "N2O")}
        series.append([y, round(data.quantity("Gas/Diesel Oil", y), 0), fo_q, fo_u,
                       round(gas["CO2"], 4), round(gas["CH4"], 5), round(gas["N2O"], 5),
                       round(sum(x["co2e_Mt_AR5"] for x in c), 5),
                       round(sum(x["co2e_Mt_AR6"] for x in c), 5)])
    run.write("railways_timeseries_%d.csv" % year,
           ["fiscal_year", "diesel_thousand_litres", "fo_quantity", "fo_unit",
            "co2_Gg", "ch4_Gg", "n2o_Gg", "mt_co2e_AR5", "mt_co2e_AR6"], series)

    print("Railways module (1A3c + non-traction) FY%d-%02d: %.3f Mt CO2e (AR5)"
          % (year - 1, year % 100, total))
    for c in comps:
        if c["emissions_Gg"] >= 0.01:
            print("  %-16s %10.3f Gg  %7.4f Mt" % (c["subitem"], c["emissions_Gg"],
                                                   c["co2e_Mt_AR5"]))
    print("  N2O is %.1f%% of the sector on the rail factor, %.1f%% on the road factor"
          % (100 * rail_n2o / total, 100 * road_n2o / (total - rail_n2o + road_n2o)))
    bad = reconcile.disagreeing_years(data)
    print("  Year Book self-check: %d of %d years reconcile summary against detail%s"
          % (len(rec) - len(bad), len(rec),
             ("; FY%d differs by %+.2f%%" % (bad[0]["fiscal_year"], bad[0]["pct"]))
             if bad else " (FY2024 restated by the 2024-25 edition; all close)"))
    print("  non-traction fuel is %.2f%% of railway diesel, measured not assumed"
          % (100 * reconcile.non_traction_share(data)))
    print("  %.1f kt metered railway diesel, its own OCAC customer class - no "
          "road-control deduction happens any more" % traction.diesel_kt(data))
    print("  matched year FY2017-18: %.3f Mt against BUR-1's 4.06 (ratio %.1f)"
          % (matched_total, 4.06 / matched_total))
    print("  series %d-%d, %d years, no gaps (FY2018 and FY2019 recovered from the "
          "2020-21 edition's historical table)"
          % (min(data.years()), max(data.years()), len(data.years())))
    print("  provincial reconciliation exact; %s"
          % ", ".join("%s %.3f" % (p, prov[p]) for p in PROVINCES))

    for label, phase in (("air pollutants", air_pollutants.main),
                         ("wear PM (exploratory)", wear_pm.main),
                         ("tier 2 split", tier2.main),
                         ("official benchmarks", official_reporting.main),
                         ("uncertainty", uncertainty.main),
                         ("intensity", efficiency.main),
                         ("history", history.main),
                         ("monthly layer", monthly.main)):
        print("-- %s --" % label)
        phase()
    # finalize BEFORE the manifest: _manifest globs outputs/railways_* from
    # disk, so the QA table must exist when it looks or two consecutive runs
    # would produce different manifests.
    run.finalize(qa_table="railways_qa_%d.csv" % year)
    path, n = _manifest(data)
    print("-- manifest: %s (%d hashed sources) --" % (os.path.basename(path), n))


if __name__ == "__main__":
    main()

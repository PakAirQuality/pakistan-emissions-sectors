"""Run the civil aviation inventory (IPCC 1A3a) and write its outputs.

Usage:  python3 -m pkinv.sectors.aviation.run_aviation
Writes: outputs/aviation_totals_fy2023_24.csv, aviation_by_stream_fy2023_24.csv,
        aviation_air_pollutants_fy2023_24.csv, aviation_provincial_fy2023_24.csv,
        aviation_timeseries_2006_fy2023_24.csv, aviation_report.md
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import hashlib
import os

from pkinv.core.downscale import allocate_rows, check_reconciliation
from pkinv.core.geography import PROVINCES
from pkinv.core.runner import Runner
from pkinv.paths import OUTPUTS, ROOT
from pkinv.sectors.aviation import air_pollutants, downscale, engine, fuel_bridge, lto, uncertainty
from pkinv.sectors.aviation.data import AviationData
from pkinv.core import period

def _sfx(year):
    """The output filename's period suffix - "fy2023_24", not a bare year (rc15:
    this sector keys on the fiscal-START year, so _2023 named the same twelve
    months as the _2024 files beside it)."""
    return period.file_suffix(year, engine.YEAR_CONVENTION)



CAT = lto.CATEGORY


def _route_resolved_mt():
    """The resolution ladder's route_resolved CO2, Mt, read from its own table -
    a second arithmetic path would be a second vintage waiting to disagree."""
    import csv as _csv
    path = asset_path(OUTPUTS, "aviation_model_resolution_fy2023_24.csv")
    for row in _activity_rows(path, comments=True):
        if row["model"] == "route_resolved":
            return float(row["co2_kt"]) / 1000.0
    raise SystemExit("the resolution ladder has no route_resolved row; the "
                     "ladder configuration cannot price")


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = AviationData()
    year = data.year
    run = Runner("aviation", lineterminator="\n", declared=(
        "aviation_by_stream_%s.csv" % _sfx(year),
        "aviation_totals_%s.csv" % _sfx(year),
        "aviation_unallocated_fuel_%s.csv" % _sfx(year),
        "aviation_air_pollutants_%s.csv" % _sfx(year),
        "aviation_fuel_bridge_%s.csv" % _sfx(year),
        "aviation_reconciliation_%s.csv" % _sfx(year),
        "aviation_fuel_constrained_by_stream_%s.csv" % _sfx(year),
        "aviation_benchmark_summary_%s.csv" % _sfx(year),
        "aviation_uncertainty_factors_%s.csv" % _sfx(year),
        "aviation_uncertainty_scenarios_%s.csv" % _sfx(year),
        "aviation_activity_decomposition_2006_%s.csv" % _sfx(year),
        "aviation_completeness_%s.csv" % _sfx(year),
        "aviation_run_manifest_%s.csv" % _sfx(year),
        "aviation_provincial_%s.csv" % _sfx(year),
        "aviation_timeseries_2006_%s.csv" % _sfx(year)))
    comps = engine.build_components(data)
    memo = engine.memo_items(data)
    air = air_pollutants.compute(data)
    cyc = lto.lto_cycles(data)
    total = sum(c["co2e_Mt_AR5"] for c in comps)

    run.write("aviation_by_stream_%s.csv" % _sfx(year),
           ["category", "subitem", "gas", "fossil", "emissions_Gg", "co2e_Mt_AR5",
            "co2e_Mt_AR6", "uncert_pct"],
           [[c["category"], c["subitem"], c["gas"], c.get("fossil", False),
             round(c["emissions_Gg"], 5), round(c["co2e_Mt_AR5"], 5),
             round(c["co2e_Mt_AR6"], 5), round(c["uncert_pct"], 1)] for c in comps])

    # The 1A5b/GA fuel the sixth review found unpriced: the bridge holds the tonnages
    # (identical across its scenarios); price them here as memo rows and as one filled
    # sensitivity row the national configuration machinery can point at. CO2 only, like
    # the bunker memos - the CH4/N2O share of jet fuel is sub-percent.
    bridge_literal = fuel_bridge.build(data, year, "literal_customer")
    military_t = sum(r["military_1a5b"] for r in bridge_literal)
    ga_t = sum(r["general_aviation"] for r in bridge_literal)
    residual_t = sum(r["residual"] for r in bridge_literal)
    co2_jet = data.p("co2_per_t_fuel")
    co2_avgas = data.p("co2_per_t_avgas")
    military_Mt = military_t * co2_jet / 1e6
    ga_Mt = ga_t * co2_avgas / 1e6
    residual_Mt = residual_t * co2_jet / 1e6
    in_scope_total = total + military_Mt + ga_Mt + residual_Mt

    # Memo rows carry BLANK CO2e cells on purpose. The international stream is large
    # relative to the national total, so anything summing the co2e column must still get
    # the right national figure even if it ignores the memo entirely.
    run.write("aviation_totals_%s.csv" % _sfx(year),
           ["category", "co2e_Mt_AR5", "co2e_Mt_AR6", "note"],
           [[CAT, round(total, 5), round(sum(c["co2e_Mt_AR6"] for c in comps), 5),
             "1A3a ii domestic aviation; the national total"]]
           + [[m["item"], "", "", "%.1f Gg CO2, excluded from the national total. %s"
               % (m["emissions_Gg"], m["note"])] for m in memo]
           + [["Military and government aviation (1A5b candidates)", "", "",
               "%.1f Gg CO2 (%.0f t jet fuel x %.2f), excluded from the national "
               "total: IPCC reports military aviation under 1A5b and no record "
               "attributes the activity between military operations and civil "
               "government use. See completeness 1.A.5.b and gap aviation-1a5b-scope."
               % (military_Mt * 1000, military_t, co2_jet)],
              ["General aviation (100LL)", "", "",
               "%.1f Gg CO2 (%.0f t aviation gasoline x %.2f), excluded from the "
               "national total: fuel identified, activity unresolved."
               % (ga_Mt * 1000, ga_t, co2_avgas)],
              ["Unresolved government JP-1", "", "",
               "%.1f Gg CO2 (%.0f t x %.2f), excluded from the national total: the "
               "bridge's unresolved residual, labelled as such."
               % (residual_Mt * 1000, residual_t, co2_jet)],
              # The three scope decisions are INDEPENDENTLY switchable since rc11
              # (the seventh review's last aviation lump): each fuel evidence class
              # is its own sensitivity row and its own national configuration,
              # because military attribution, general-aviation activity and an
              # unresolved bridge residual are three different questions with three
              # different closers.
              ["Sensitivity: including military/government scope",
               round(total + military_Mt, 5), "",
               "the 1A3a total plus the military/government jet stream alone "
               "(%.3f Mt CO2); configuration military_government_in_scope"
               % military_Mt],
              ["Sensitivity: including general aviation 100LL",
               round(total + ga_Mt, 5), "",
               "the 1A3a total plus the 100LL general-aviation stream alone "
               "(%.3f Mt CO2); configuration general_aviation_in_scope" % ga_Mt],
              ["Sensitivity: including unresolved government JP-1",
               round(total + residual_Mt, 5), "",
               "the 1A3a total plus the bridge's unresolved government residual "
               "alone (%.3f Mt CO2); configuration unresolved_jp1_in_scope"
               % residual_Mt],
              ["Sensitivity: including military and general aviation scope",
               round(in_scope_total, 5), "",
               "the 1A3a total plus all three priced streams above (%.3f Mt CO2) - "
               "the joint scope alternative, retained as the sum of the three "
               "independently switchable rows; CO2-only on the added "
               "streams" % (military_Mt + ga_Mt + residual_Mt)],
              # Wave 6: the resolution-ladder reading, priced so the deferred
              # re-base question is a configuration instead of a note. The
              # ladder's route_resolved model is read from its own published
              # table (never retyped) and the reference stays on
              # aggregate_movement: every finer product is stamped provisional
              # and the OCAC-vs-ledger reconciliation factors span 0.98-3.81.
              ["Sensitivity: route-resolved ledger reading",
               round(_route_resolved_mt(), 5), "",
               "the domestic total read from the flight-route ledger instead "
               "of aggregate movements (coverage 99.0%%, CO2-only like the "
               "resolution table); configuration "
               "aviation_route_resolved_reading. The re-base itself is "
               "REFUSED BY TYPE: provisional stamps on every finer product "
               "and a 0.98-3.81 reconciliation spread; the EMEP fuel-sales "
               "reconciliation is the closer"]])

    # The observed-unallocated ACCOUNT (rc14, the ninth review): observed fuel must
    # not look absent merely because the reference excludes it. Every identified
    # tonne outside the 1A3a boundary gets a first-class row with a closed evidence
    # vocabulary and a named closer - the memo rows restated as an account a reader
    # can total, not footnotes a reader must collect.
    lto_noncomm = next((m for m in memo if "Non-commercial" in m["item"]), None)
    unallocated = [
        {"account": "military_government_jet", "fuel_type": "JP-1",
         "tonnes": round(military_t), "co2_Gg": round(military_Mt * 1000, 1),
         "evidence_class": "fuel_identified_activity_unattributed",
         "disposition": "booked_as_configuration (military_government_in_scope)",
         "closer": "any record attributing the OCAC government/defence class "
                   "between military operations (1A5b) and civil government use"},
        {"account": "general_aviation_100ll", "fuel_type": "100LL avgas",
         "tonnes": round(ga_t), "co2_Gg": round(ga_Mt * 1000, 1),
         "evidence_class": "fuel_identified_activity_unresolved",
         "disposition": "booked_as_configuration (general_aviation_in_scope)",
         "closer": "a GA movement or flight-hours record for the piston fleet"},
        {"account": "unresolved_government_jp1", "fuel_type": "JP-1",
         "tonnes": round(residual_t), "co2_Gg": round(residual_Mt * 1000, 1),
         "evidence_class": "observed_unallocated_residual",
         "disposition": "booked_as_configuration (unresolved_jp1_in_scope)",
         "closer": "the OCAC bridge's own residual: nothing attributes it, and "
                   "forcing it into any account would manufacture attribution"},
    ]
    if lto_noncomm is not None:
        unallocated.append(
            {"account": "non_commercial_lto", "fuel_type": "JP-1/avgas mix",
             "tonnes": "", "co2_Gg": round(lto_noncomm["emissions_Gg"], 1),
             "evidence_class": "movement_observed_fuel_mixed",
             "disposition": "memo_row (LTO portion of non-commercial movements)",
             "closer": "movement-level operator attribution at joint-use "
                       "airfields; mixes GA, training circuits and military"})
    run.write("aviation_unallocated_fuel_%s.csv" % _sfx(year),
           ["account", "fuel_type", "tonnes", "co2_Gg", "evidence_class",
            "disposition", "closer"],
           [[u["account"], u["fuel_type"], u["tonnes"], u["co2_Gg"],
             u["evidence_class"], u["disposition"], u["closer"]]
            for u in unallocated])

    run.write("aviation_air_pollutants_%s.csv" % _sfx(year),
           ["category", "subitem", "ghg_subitem", "pollutant", "emissions_kt", "uncert_pct",
            "method", "engine_coverage_share", "imputed"],
           [[r["category"], r["subitem"], r["ghg_subitem"], r["pollutant"],
             round(r["emissions_kt"], 4), round(r["uncert_pct"], 1), r["method"],
             r["engine_coverage_share"], r["imputed"]] for r in air])

    bridge_rows = []
    for scenario in fuel_bridge.SCENARIOS:
        bridge_rows.extend(fuel_bridge.build(data, year, scenario))
    bridge_header = (["fiscal_year", "scenario", "customer_category", "fuel_type",
                      "reported_t"] + list(fuel_bridge.ACCOUNTS)
                     + ["bridge_method", "source"])
    run.write("aviation_fuel_bridge_%s.csv" % _sfx(year), bridge_header,
           [[r[h] for h in bridge_header] for r in bridge_rows])

    recon = fuel_bridge.reconciliation(data, year)
    recon_header = list(recon[0])
    run.write("aviation_reconciliation_%s.csv" % _sfx(year), recon_header,
           [[r[h] for h in recon_header] for r in recon])

    fuel_comps = fuel_bridge.components(data, year)
    run.write("aviation_fuel_constrained_by_stream_%s.csv" % _sfx(year),
           ["category", "subitem", "gas", "fossil", "emissions_Gg", "co2e_Mt_AR5",
            "co2e_Mt_AR6", "uncert_pct"],
           [[c["category"], c["subitem"], c["gas"], c.get("fossil", False),
             round(c["emissions_Gg"], 6), round(c["co2e_Mt_AR5"], 6),
             round(c["co2e_Mt_AR6"], 6), round(c["uncert_pct"], 1)] for c in fuel_comps])

    bench = fuel_bridge.benchmark_summary(data, year)
    run.write("aviation_benchmark_summary_%s.csv" % _sfx(year), list(bench),
           [[bench[h] for h in bench]])

    factors = uncertainty.factor_table(data)
    factor_header = list(factors[0])
    run.write("aviation_uncertainty_factors_%s.csv" % _sfx(year), factor_header,
           [[r[h] for h in factor_header] for r in factors])
    scenarios = uncertainty.run(data, year)
    scenario_header = list(scenarios[0])
    run.write("aviation_uncertainty_scenarios_%s.csv" % _sfx(year), scenario_header,
           [[r[h] for h in scenario_header] for r in scenarios])
    decomp = uncertainty.decomposition(data)
    decomp_header = list(decomp[0])
    run.write("aviation_activity_decomposition_2006_%s.csv" % _sfx(year), decomp_header,
           [[r[h] for h in decomp_header] for r in decomp])

    completeness = [
        ["Scheduled domestic", "estimated", "Full flight; movement and fuel-bridge models"],
        ["International aviation bunkers", "estimated", "Full flight from fuel bridge"],
        ["International LTO at Pakistani airports", "estimated", "Separate airport quantity"],
        ["General aviation and training", "partial", "100LL identified; operations unresolved"],
        ["Military aviation (1A5b)", "memo", "JP-8/government candidates; not in 1A3a"],
        ["Helicopters", "not estimated", "No classified activity"],
        ["APU and ground support", "not estimated", "Requires airport survey"],
        ["Aircraft main-engine LTO pollutants", "estimated", "Tier-1 aircraft-family factors"],
        ["Climb/cruise/descent pollutants", "not estimated", "CO2/CH4/N2O only"],
        ["Tyre and brake wear", "not estimated", "No local activity or factor assignment"],
    ]
    run.write("aviation_completeness_%s.csv" % _sfx(year),
           ["source_stream", "status", "note"], completeness)

    manifest_rows = []
    manifest_path = asset_path(data.data_dir, "activity", "aviation", "source_manifest.csv")
    for source_row in _activity_rows(manifest_path, comments=False):
        source_path = asset_path(ROOT, source_row["artifact"])
        # rc41: VERIFY WHEN PRESENT. The manifest's digests are the record; a document
        # the tree does not hold (the validation package registers the OCAC PDFs
        # rather than shipping them) is carried forward as declared and said so,
        # while a document that IS present and does not match still raises.
        if not os.path.exists(source_path):
            print("   aviation source not held in this tree, digest carried from the manifest: %s"
                  % source_row["artifact"])
            actual = source_row["sha256"]
        else:
            digest = hashlib.sha256()
            with open(source_path, "rb") as source_file:
                for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
                    digest.update(chunk)
            actual = digest.hexdigest()
            if actual != source_row["sha256"]:
                raise ValueError("aviation source digest mismatch: %s" % source_row["artifact"])
        manifest_rows.append([source_row["artifact"], actual, source_row["version"],
                              source_row["role"], uncertainty.N_ITER, uncertainty.SEED,
                              "|".join(fuel_bridge.SCENARIOS)])
    run.write("aviation_run_manifest_%s.csv" % _sfx(year),
           ["artifact", "sha256", "version", "role", "mc_draws", "mc_seed",
            "structural_scenarios"], manifest_rows)

    rows = allocate_rows(comps, downscale.load_shares(), downscale.proxy_for, PROVINCES)
    check_reconciliation(rows, comps)
    prov = {p: 0.0 for p in PROVINCES}
    for r in rows:
        prov[r["province"]] += r["co2e_Mt_AR5"]
    run.write("aviation_provincial_%s.csv" % _sfx(year), ["province", "co2e_Mt_AR5"],
           [[p, round(prov[p], 5)] for p in PROVINCES])

    series = []
    for y in sorted({r["year"] for r in data.movements}):
        c = engine.build_components(data, y)
        series.append([y, round(lto.lto_cycles(data, y)["domestic"], 0),
                       round(sum(x["co2e_Mt_AR5"] for x in c) * 1000.0, 1)])
    run.write("aviation_timeseries_2006_%s.csv" % _sfx(year),
           ["fiscal_year", "domestic_lto_cycles", "domestic_kt_co2e_AR5"], series)

    with open(asset_path(OUTPUTS, "aviation_report.md"), "w", encoding="utf-8") as f:
        f.write("# Civil aviation (IPCC 1A3a), fiscal year %d-%02d\n\n" % (year, (year + 1) % 100))
        f.write("Years are CAA fiscal years, July to June. LTO cycles are movements / 2 "
                "(ICAO: one arrival and one departure count as two movements).\n\n")
        f.write("LTO cycles: domestic %.0f, international %.0f, non-commercial %.0f.\n\n"
                % (cyc["domestic"], cyc["international"], cyc["noncommercial"]))
        f.write("| Stream | Gas | Gg | Mt CO2e (AR5) | +/- |\n|---|---|---|---|---|\n")
        for c in comps:
            f.write("| %s | %s%s | %.4f | %.5f | %.0f%% |\n"
                    % (c["subitem"], c["gas"], " (fossil)" if c.get("fossil") else "",
                       c["emissions_Gg"], c["co2e_Mt_AR5"], c["uncert_pct"]))
        f.write("| **Total (1A3a ii)** | | | **%.5f** | |\n\n" % total)
        f.write("## Memo items, excluded from the national total\n\n")
        for m in memo:
            f.write("- **%s** — %.1f Gg CO2. %s\n" % (m["item"], m["emissions_Gg"], m["note"]))
        central = next(r for r in recon if r["scenario"] == "flight_fuel_weighted")
        f.write("\n## Fuel-control comparison\n\n")
        f.write("The OCAC customer labels are not treated as IPCC boundaries. Under the "
                "flight-fuel-weighted bridge, domestic aviation is %.1f Gg CO2 versus "
                "%.1f Gg in the unconstrained movement model (factor %.3f).\n\n"
                % (central["domestic_co2_Gg"], central["bottom_up_domestic_co2_Gg"],
                   central["domestic_reconciliation_factor"]))
        f.write("Commercial JP-1 implies %.1f Gg CO2 versus OECD's matched domestic plus "
                "international territory total of %.1f Gg (ratio %.3f). OECD supplies the "
                "central split and is therefore a calibration input, not independent validation.\n"
                % (bench["commercial_jp1_co2_t"] / 1000.0,
                   bench["oecd_territory_total_co2_t"] / 1000.0,
                   bench["fuel_over_oecd_total"]))
        f.write("\n## Air pollutants (mass, never CO2e)\n\n| Pollutant | kt | +/- |\n|---|---|---|\n")
        for r in air:
            f.write("| %s | %.4f | %.0f%% |\n" % (r["pollutant"], r["emissions_kt"], r["uncert_pct"]))

    print("Civil aviation FY%d: %.0f domestic LTO cycles -> %.1f kt CO2e (AR5)"
          % (year, cyc["domestic"], total * 1000.0))
    central = next(r for r in recon if r["scenario"] == "flight_fuel_weighted")
    print("  FUEL BRIDGE domestic %.1f kt CO2 | factor vs movement %.3f"
          % (central["domestic_co2_Gg"], central["domestic_reconciliation_factor"]))
    print("  COMMERCIAL FUEL/OECD territory closure %.3f" % bench["fuel_over_oecd_total"])
    for c in comps:
        print("  %-26s %9.4f Gg  %8.2f kt CO2e" % (c["subitem"], c["emissions_Gg"],
                                                   c["co2e_Mt_AR5"] * 1000.0))
    for m in memo:
        print("  MEMO %-45s %8.1f kt CO2 (excluded)" % (m["item"], m["emissions_Gg"]))
    print("  provincial reconciliation exact; %s"
          % ", ".join("%s %.1f kt" % (p, prov[p] * 1000.0) for p in PROVINCES))

    from pkinv.sectors.aviation import monthly_layer
    monthly_layer.main()

    run.finalize(qa_table="aviation_qa_%s.csv" % _sfx(year))


if __name__ == "__main__":
    main()

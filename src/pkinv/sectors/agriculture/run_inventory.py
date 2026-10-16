"""Run the national Tier 1 agricultural GHG inventory for Pakistan (Priority-4).

Usage:  python3 -m pkinv.sectors.agriculture.run_inventory
Writes: outputs/by_category.csv, national_totals_2024.csv,
        inventory_report.md   (no external dependencies)
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os
import sys


from pkinv.sectors.agriculture.ef_library import InventoryData, _read, DATA_DIR  # noqa: E402
from pkinv.sectors.agriculture import enteric, manure, rice, soils, residue_burning, liming_urea  # noqa: E402
from pkinv.core import gwp  # noqa: E402
from pkinv.core.uncertainty import combine_sum  # noqa: E402

from pkinv.core.runner import Runner
from pkinv.paths import ROOT

YEAR = 2024
OUT_DIR = asset_path(ROOT, "outputs")

# Single source of truth for the category list (imported by downscale, timeseries, gis).
CATEGORIES = ["Enteric fermentation", "Manure management", "Rice cultivation",
              "Managed soils", "Field burning of residues", "Urea application"]


def co2e_Mt(gas, emissions_Gg, ar):
    # Gg gas * GWP = Gg CO2e; /1000 -> Mt (Tg) CO2e
    return gwp.to_co2e(gas, emissions_Gg, ar) / 1000.0


def build_components(data, ef1_override=None, nitrogen_method=None):
    """Compute all category components with CO2e enrichment. Reused by downscale.py.

    ef1_override forces the managed-soils upland EF1 (sensitivity pass); None = Tier 2 default.
    """
    components = []
    components += enteric.compute(data)
    manure_comp, npools = manure.compute(data, method=nitrogen_method)
    components += manure_comp
    components += rice.compute(data)
    components += soils.compute(data, npools, ef1_override=ef1_override)
    components += residue_burning.compute(data)
    components += liming_urea.compute(data)
    for c in components:
        c["co2e_Mt_AR5"] = co2e_Mt(c["gas"], c["emissions_Gg"], "AR5")
        c["co2e_Mt_AR6"] = co2e_Mt(c["gas"], c["emissions_Gg"], "AR6")
    return components


def soils_total(components):
    return sum(c["co2e_Mt_AR5"] for c in components if c["category"] == "Managed soils")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    data = InventoryData()
    run = Runner("agriculture", declared=(
        "by_category.csv", "national_totals_2024.csv",
        "agriculture_livestock_reconciliation_2024.csv",
        "agriculture_fertiliser_composition_2024.csv",
        "agriculture_crop_residue_ledger_2024.csv",
        "inventory_report.md"))
    components = build_components(data)

    _write_livestock_reconciliation(run, data)
    _write_fertiliser_composition(run, data)
    _write_crop_residue_ledger(run, data)
    _write_by_category(run, components)
    cat_rows, total = _write_national_totals(run, components)
    sens = _sensitivity(data, components)
    _write_report(run, components, cat_rows, total, sens)

    print("Pakistan agricultural emissions (%d, provisional, Tier 2, %d categories):"
          % (YEAR, len(CATEGORIES)))
    for r in cat_rows:
        print("  %-20s %8.1f Mt CO2e (AR5)  +/-%.0f%%" %
              (r["category"], r["co2e_Mt_AR5"], r["uncert_pct"]))
    print("  %-20s %8.1f Mt CO2e (AR5)  +/-%.0f%%" %
          ("TOTAL", total["co2e_Mt_AR5"], total["uncert_pct"]))
    print("  EF1 sensitivity (managed soils): EF1=0.005 (primary) -> %.1f Mt soils / %.1f total ; "
          "Cui-2021 0.0055 -> %.1f / %.1f ; EF1=0.010 -> %.1f / %.1f"
          % (sens["soils_lo"], sens["total_lo"], sens["soils_cui"], sens["total_cui"],
             sens["soils_hi"], sens["total_hi"]))


def _sensitivity(data, base_components):
    """Soils + national total at three EF1 points: 0.005 (Tier 2 dry, PRIMARY), 0.0055 (Cui 2021
    empirical field-obs adjudicator) and 0.010 (IPCC-2006 / Pakistan-official)."""
    base_total = sum(c["co2e_Mt_AR5"] for c in base_components)
    base_soils = soils_total(base_components)
    cui = build_components(data, ef1_override=data.efv("soils", "EF1_cui"))  # 0.0055
    hi = build_components(data, ef1_override=data.efv("soils", "EF1_agg"))   # 0.010
    return {"soils_lo": base_soils, "total_lo": base_total,
            "soils_cui": soils_total(cui), "total_cui": sum(c["co2e_Mt_AR5"] for c in cui),
            "soils_hi": soils_total(hi), "total_hi": sum(c["co2e_Mt_AR5"] for c in hi)}


def _write_by_category(run, components):
    run.write("by_category.csv",
              ["category", "subitem", "gas", "emissions_Gg",
               "co2e_Mt_AR5", "co2e_Mt_AR6", "uncert_pct"],
              [[c["category"], c["subitem"], c["gas"],
                round(c["emissions_Gg"], 4), round(c["co2e_Mt_AR5"], 4),
                round(c["co2e_Mt_AR6"], 4), round(c["uncert_pct"], 1)]
               for c in components])


def _write_livestock_reconciliation(run, data):
    """The national control against the district transcription, species by species.

    rc39. The national counts drive the inventory; the district counts drive the spatial
    allocation. They are two transcriptions of one census table and they do NOT agree
    exactly - district sums run 8 sheep over and 8 camels under the national row, with
    cattle and buffalo out by one head each. NEITHER IS EDITED TO MAKE THEM MATCH: the
    published district values stand, the official national table is the emissions control,
    and the difference is published here with the normalisation factor the spatial weights
    carry. A residual that is silently absorbed is a residual nobody can audit; the
    previous release claimed the two agreed to a single head, which held for cattle and
    buffalo and did not for sheep and camels.
    """
    import csv as _csv
    import os as _os
    from pkinv.paths import DATA as _DATA
    district = _os.path.join(_DATA, "activity", "livestock_district_2024.csv")
    drows = [r for r in _activity_rows(district, comments=True)]
    rows = []
    for species, entry in sorted(data.livestock.items()):
        if entry.get("activity_basis") != "census_enumeration":
            continue
        national = entry["head"]
        dsum = sum(int(r[species]) for r in drows if r.get(species, "").strip())
        residual = int(national) - dsum
        rows.append([
            species, int(national), dsum, int(residual),
            round(residual / national * 100.0, 8) if national else "",
            round(national / dsum, 12) if dsum else "",
            len(drows), entry["source_document_id"],
        ])
    run.write("agriculture_livestock_reconciliation_2024.csv",
              ["species", "national_control_head", "district_sum_head",
               "residual_head", "residual_pct_of_national",
               "spatial_normalisation_factor", "districts", "source_document_id"],
              rows)


def _write_fertiliser_composition(run, data):
    """The product mix that weights FracGASF, over the fiscal year it claims to describe.

    rc39 A2. This factor drives BOTH the ammonia layer and the synthetic indirect-N2O row,
    and it used to be weighted by NFDC Annex-7, whose year runs April-March. The composition
    therefore came from a period that is not the one the inventory reports. Annex-5 is the
    same publication's national monthly offtake and its fiscal year IS Jul-Jun, so the
    weighting is now taken from the window it belongs to: 0.1608191992 kg NH3-N per kg N.

    THE ANNEXE IS NOT THE ACTIVITY DATUM. Its own nitrogen over the window is 3.746448 Mt N
    against the audited 3.775 Mt N in fertilizer_2024.csv - 0.756% lower. Only the NORMALISED
    composition crosses between the two; the magnitude stays with the audited table. The TOTAL
    row states both so they cannot be read as one quantity.
    """
    from pkinv.sectors.agriculture import fertiliser_mix as fm
    weighted, detail, window_n = fm.weighted_fracgasf(data)
    _, tonnes = fm.national_product_nitrogen(data)
    audited = data.fertilizer["nitrogen_N_offtake"]["value_t"]
    by = {d["product"]: d for d in detail}
    rows = []
    for product in sorted(tonnes, key=lambda p: -by.get(p, {}).get("share_of_N", 0.0)):
        d = by.get(product)
        try:
            nc = data.efv("fert_n_content", product)
        except KeyError:
            nc = 0.0
        rows.append([
            product, round(tonnes[product], 3), nc,
            round(tonnes[product] * nc, 3),
            round(d["share_of_N"], 10) if d else 0.0,
            d["EF_NH3N_per_N"] if d else "",
            round(d["contribution"], 12) if d else "",
            "" if d else "carries no nitrogen; tonnage shown for the offtake it represents",
        ])
    rows.append([
        "TOTAL", round(sum(tonnes.values()), 3), "", round(window_n, 3), 1.0, "",
        round(weighted, 12),
        "weighted FracGASF over %s; annexe nitrogen %.0f t N vs the audited activity datum "
        "%.0f t N (%.3f%% lower) - the annexe supplies COMPOSITION only"
        % (fm.FY_LABEL, window_n, audited, 100.0 * (1.0 - window_n / audited)),
    ])
    run.write("agriculture_fertiliser_composition_2024.csv",
              ["product", "offtake_product_tonnes", "n_content_frac", "nitrogen_t",
               "share_of_N", "ef_nh3n_per_kg_n_highpH", "contribution", "note"],
              rows)


def _write_crop_residue_ledger(run, data):
    """Every tonne of crop residue, and which destination claims it (rc39 A6).

    THE PROBLEM THIS FIXES. Three modules each take the fraction they need from the same
    residue: residue_burning takes frac_burned, soils takes frac_returned, and residential
    combustion takes frac_fuel. Each is right on its own and none of them shows the whole, so
    production x RPR was never published and the residue that is NEITHER returned, burned nor
    used as fuel had no name, no number and no owner. Under this year's parameters that
    remainder is the largest destination of all - it is fodder, bedding, industrial use and
    straw left standing - and an inventory that cannot say how big it is cannot say how much
    room there is for the destinations it does price.

    The columns are ordered as the residue actually moves: what the crop produced, what the
    residue ratio makes of it, then each destination with the fraction that claims it, then
    the fuel stream's conversion to air-dry and to energy. The dry -> air-dry step is the one
    place a mass changes basis, so it carries its own moisture column rather than being folded
    into a factor.
    """
    from pkinv.sectors.agriculture import residue_burning
    cf = data.efv("burning", "combustion_factor")
    moisture = None
    try:
        from pkinv.sectors.residential.data import ResidentialData
        moisture = ResidentialData().p("residue_moisture_ar")
        ncv = ResidentialData().efv("residential_ncv", "Other Primary Solid Biomass")
    except Exception:                       # the ledger must not depend on another sector
        moisture, ncv = 0.12, 11.6
    rows, tot = [], {k: 0.0 for k in ("dry", "returned", "fire", "combusted", "fuel", "other")}
    for crop in sorted(data.residue):
        prod = data.crops.get(crop, {}).get("production_t")
        rr = data.residue[crop].get("residue_ratio_ag")
        if not prod or not rr:
            continue
        dry = prod * rr / 1e6
        f_ret = data.residue[crop].get("frac_returned", 0.0)
        f_fuel = data.residue[crop].get("frac_fuel", 0.0)
        f_burn = data.burning.get(crop, {}).get("frac_burned", 0.0)
        returned, fire, fuel = dry * f_ret, dry * f_burn, dry * f_fuel
        combusted = fire * cf
        other = dry - returned - fire - fuel
        for key, value in (("dry", dry), ("returned", returned), ("fire", fire),
                           ("combusted", combusted), ("fuel", fuel), ("other", other)):
            tot[key] += value
        rows.append([
            crop, prod, rr, round(dry, 6),
            f_ret, round(returned, 6),
            f_burn, round(fire, 6), cf, round(combusted, 6),
            f_fuel, round(fuel, 6), round(other, 6),
            round(100.0 * other / dry, 4) if dry else "",
            moisture, round(fuel / (1.0 - moisture), 6),
            ncv, round(fuel / (1.0 - moisture) * 1000.0 * ncv, 4),
            "residential 1.A.4.b (configuration L and S alike)",
        ])
    air_dry = tot["fuel"] / (1.0 - moisture)
    rows.append([
        "TOTAL", "", "", round(tot["dry"], 6),
        "", round(tot["returned"], 6),
        "", round(tot["fire"], 6), cf, round(tot["combusted"], 6),
        "", round(tot["fuel"], 6), round(tot["other"], 6),
        round(100.0 * tot["other"] / tot["dry"], 4),
        moisture, round(air_dry, 6), ncv, round(air_dry * 1000.0 * ncv, 4),
        "",
    ])
    # The identity, unrounded, before anything is published: every destination and the
    # remainder must add back to the residue the crops produced.
    closure = tot["dry"] - (tot["returned"] + tot["fire"] + tot["fuel"] + tot["other"])
    if abs(closure) > 1e-9:
        raise ValueError("the residue ledger does not close: %.12f Mt unaccounted" % closure)
    run.write("agriculture_crop_residue_ledger_2024.csv",
              ["crop", "production_t", "residue_ratio_ag", "dry_residue_Mt",
               "frac_returned", "returned_to_soil_Mt",
               "frac_burned", "to_fire_Mt", "combustion_factor", "combusted_Mt",
               "frac_fuel", "fuel_dry_Mt", "other_unresolved_Mt", "other_pct_of_dry",
               "moisture_air_dry", "fuel_air_dry_Mt", "ncv_TJ_per_Gg", "energy_TJ",
               "receiving_configuration"],
              rows)


def _write_national_totals(run, components):
    cats = CATEGORIES
    cat_rows = []
    for cat in cats:
        members = [(c["co2e_Mt_AR5"], c["uncert_pct"], c.get("corr_group")) for c in components
                   if c["category"] == cat]
        co2e5, u = combine_sum(members)
        co2e6 = sum(c["co2e_Mt_AR6"] for c in components if c["category"] == cat)
        cat_rows.append({"category": cat, "co2e_Mt_AR5": co2e5,
                         "co2e_Mt_AR6": co2e6, "uncert_pct": u})

    total_co2e5, total_u = combine_sum(
        [(c["co2e_Mt_AR5"], c["uncert_pct"], c.get("corr_group")) for c in components])
    total = {"category": "TOTAL", "co2e_Mt_AR5": total_co2e5,
             "co2e_Mt_AR6": sum(c["co2e_Mt_AR6"] for c in components),
             "uncert_pct": total_u}

    # rc38: the identity the paper calls enforced on every run. It was - in tests/,
    # where a reader of the shipped QA table cannot see it. Asserted on the PUBLISHED
    # figures rather than on the intermediates, because what a reader adds up is the
    # printed column: a component belonging to no category, or to two, breaks this.
    published_cats5 = sum(r["co2e_Mt_AR5"] for r in cat_rows)
    run.gate("published categories add to the published total (AR5)",
             abs(published_cats5 - total["co2e_Mt_AR5"]) < 1e-6,
             actual=round(published_cats5, 6), expected=round(total["co2e_Mt_AR5"], 6),
             note="the six IPCC categories partition the sector")
    component_sum5 = sum(c["co2e_Mt_AR5"] for c in components)
    run.gate("the published total is the sum of its components (AR5)",
             abs(component_sum5 - total["co2e_Mt_AR5"]) < 1e-6,
             actual=round(component_sum5, 6), expected=round(total["co2e_Mt_AR5"], 6),
             note="combine_sum may only combine UNCERTAINTY; the central value is additive")
    published_cats6 = sum(r["co2e_Mt_AR6"] for r in cat_rows)
    run.gate("published categories add to the published total (AR6)",
             abs(published_cats6 - total["co2e_Mt_AR6"]) < 1e-6,
             actual=round(published_cats6, 6), expected=round(total["co2e_Mt_AR6"], 6),
             note="the same identity on the second metric, which no test covered")

    # rc41 (M-3): three decimals, not two. At two the TOTAL printed 223.45 and every
    # manuscript that rounded it once more printed 223.4 - a second rounding of a rounded
    # number, half a unit below the engine's 223.454 - and the half-ulp comparator admitted
    # it. Three decimals leave the printed 1-dp figure with only one rounding step.
    run.write("national_totals_2024.csv",
              ["category", "co2e_Mt_AR5", "co2e_Mt_AR6", "uncert_pct"],
              [[r["category"], round(r["co2e_Mt_AR5"], 3),
                round(r["co2e_Mt_AR6"], 3), round(r["uncert_pct"], 1)]
               for r in cat_rows + [total]])
    return cat_rows, total


def _write_report(run, components, cat_rows, total, sens):
    lines = []
    lines.append("# Pakistan Agricultural GHG Inventory - Tier 2 (%d categories), %d\n"
                 % (len(CATEGORIES), YEAR))
    lines.append("**Provisional estimate.** National inventory for the full IPCC agriculture "
                 "sector - enteric fermentation, manure management, rice cultivation, managed "
                 "soils, field burning of residues, and liming & urea CO2 - using Tier 1 methods "
                 "with Tier 2 country-specific livestock weights, dairy share, manure-system "
                 "shares and rice agronomy (see `docs/tier2_changelog.md`).\n")
    lines.append("## Headline\n")
    lines.append("**Pakistan agricultural emissions = %.0f Mt CO2e "
                 "(AR5 GWP-100, +/-%.0f%%), provisional.**  "
                 "(AR6: %.0f Mt CO2e.)\n"
                 % (total["co2e_Mt_AR5"], total["uncert_pct"], total["co2e_Mt_AR6"]))
    lines.append("**Managed-soils EF1 sensitivity (3-point).** At the best-supported dry EF1=0.005 "
                 "(primary), soils = %.1f Mt / national = %.1f Mt. Cui et al. 2021 --- the largest "
                 "field-observation N2O database (1,507 obs) --- gives a Pakistan crop-weighted EF of "
                 "**0.0055**, essentially the primary value (soils = %.1f / national = %.1f Mt), "
                 "empirically anchoring the low arid EF1 over FAOSTAT's flat EF1=0.010 (soils = %.1f / "
                 "national = %.1f Mt). Pakistan itself has no field observations, so the Cui value is "
                 "climate-model-extrapolated with a wide CI, but its central estimate clearly favours "
                 "0.005.\n"
                 % (sens["soils_lo"], sens["total_lo"], sens["soils_cui"], sens["total_cui"],
                    sens["soils_hi"], sens["total_hi"]))
    lines.append("## By category\n")
    lines.append("| Category | Mt CO2e (AR5) | Mt CO2e (AR6) | Uncertainty |")
    lines.append("|---|---:|---:|---:|")
    for r in cat_rows:
        lines.append("| %s | %.1f | %.1f | +/-%.0f%% |"
                     % (r["category"], r["co2e_Mt_AR5"], r["co2e_Mt_AR6"], r["uncert_pct"]))
    lines.append("| **TOTAL** | **%.1f** | **%.1f** | **+/-%.0f%%** |"
                 % (total["co2e_Mt_AR5"], total["co2e_Mt_AR6"], total["uncert_pct"]))
    lines.append("")
    lines.append("## Detailed components\n")
    lines.append("| Category | Component | Gas | Gg | Mt CO2e (AR5) |")
    lines.append("|---|---|---|---:|---:|")
    for c in components:
        lines.append("| %s | %s | %s | %.1f | %.2f |"
                     % (c["category"], c["subitem"], c["gas"],
                        c["emissions_Gg"], c["co2e_Mt_AR5"]))
    lines.append("")
    lines.append("## Method\n")
    lines.append("- IPCC 2006 Guidelines Vol 4 + 2019 Refinement; Tier 1 methods with Tier 2 "
                 "country-specific activity data and parameters.\n"
                 "- GWP-100: AR5 primary (CH4 28, N2O 265) for UNFCCC ETF/CRT; AR6 secondary.\n"
                 "- Tier 2 country-specific: FAOSTAT dairy share, Pakistan animal weights, "
                 "manure-system shares, rice agronomy, residue return (see tier2_changelog.md).\n"
                 "- Every emission factor traces to `data/emission_factors.csv`; "
                 "uncertainty by IPCC Approach 1 error propagation.\n")
    lines.append("## Key assumptions & provisional flags\n")
    for a in [
        "Livestock basis = PBS 7th Agricultural Census 2024; dairy share = FAOSTAT QCL 2024 "
        "Milk Animals/Stocks (cattle 0.295). Animal weights = Pakistan herd-averages (Tier 2).",
        "Managed-soils EF1 = 0.005 (2019 dry) is the best-supported value for irrigated arid "
        "cropland - the dry EF1 was itself derived largely from irrigated dry fields "
        "(PMC9293294). A sensitivity at EF1=0.010 (Pakistan-official) is reported.",
        "Leaching retained on the ~80% irrigated area (FracLEACH 0.24, EF5 0.011) despite the "
        "dry climate - canal irrigation exceeds field capacity (defensible asymmetry).",
        "Rice harvested area ~3.5 Mha provisional; cultivation period 125 d (area-weighted).",
        "Manure-management-system shares are Tier 2 South-Asia/Pakistan estimates pending a "
        "national survey; dung-cake-burned N (~28%) routed to Energy, not Manure Management.",
        "FSOM (N mineralised from SOC loss) set to 0.",
        "Benchmarks: FAOSTAT (Pakistan 2023, AR5), EDGAR_2024 (2023 data) and EDGAR_2025 "
        "(2024 data, year-matched: agri 261 Mt vs engine 222 Mt, ratio 0.85). The managed-soils "
        "divergence from FAOSTAT (engine ~28 vs FAOSTAT 58 Mt) is METHODOLOGICAL - FAOSTAT "
        "uses 2006 aggregate defaults (EF1 0.01, EF3PRP 0.02); the engine uses the "
        "empirically-better 2019 disaggregated dry values. The EF1=0.010 sensitivity brackets it.",
    ]:
        lines.append("- " + a)
    lines.append("")
    path = asset_path(OUT_DIR, "inventory_report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    run.record(path)

    from pkinv.sectors.agriculture import monthly
    monthly.main()
    # Wave 6: the water-regime readings ride every run so the configuration's
    # alternative row can never go stale against the rice total it re-weights.
    from pkinv.sectors.agriculture import water_regime
    water_regime.main()

    run.finalize(qa_table="agriculture_qa_%d.csv" % YEAR)


if __name__ == "__main__":
    main()

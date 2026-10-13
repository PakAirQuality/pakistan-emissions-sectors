"""Back-calculate the buffalo NH3 emission factor the benchmark must be using, since it never states one.

Our livestock NH3 runs ~2.9x an independent South Asian inventory at matched year. The shared nitrogen
ledger makes the volatilisation chain a secondary rather than a primary suspect -- the IPCC and EMEP
representations of the same manure pool reach totals within 1.06x while both stay far above the
benchmark -- but does not clear it, because that agreement is two stage-level disagreements cancelling
(see n_ledger.stage_comparison). What the two chains genuinely share is the excreted-nitrogen pool they
are applied to, so that pool is the more promising place to look, and buffalo dominate it.

The benchmark cannot be checked on that point directly. Its Table A8 of implicit emission factors lists
asses, dairy and non-dairy cattle, broilers, layers, goats, horses, mules and sheep -- but NOT buffalo,
even though its own text names "large numbers of Buffalo" as the reason Pakistan's grazing emissions are
high. So we infer the factor it must have applied: take its published Pakistan livestock total, subtract
what its own tabulated factors account for, and attribute the residual.

THIS IS OUR DERIVATION, NOT A PUBLISHED VALUE, and the residual is not buffalo alone -- it also absorbs
camels and equines, which Table A8 either omits or which our activity data does not resolve. It is
reported as an upper bound on the implied buffalo factor for that reason.

Usage:  python3 -m pkinv.eval.buffalo_implied_ef
Writes: outputs/eval/buffalo_implied_ef.json
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import json
import os
import sys


from pkinv.sectors.agriculture.ef_library import InventoryData  # noqa: E402
from pkinv.sectors.agriculture import manure  # noqa: E402

from pkinv.paths import ROOT, DATA

OUT = asset_path(ROOT, "outputs", "eval")
HIST = asset_path(DATA, "activity", "historical", "livestock_stocks.csv")
YEAR = 2015

# Tomlinson et al. 2026 ESSD Table A8, kg NH3 per Annual Average Population per year (AGS + MNM total).
# Verified against the published table; buffalo is absent from it, which is the point of this module.
TABLE_A8 = {"Cattle, dairy": 6.33, "Cattle, non-dairy": 2.07, "Sheep": 1.44, "Goats": 1.11,
            "Chickens, broilers": 0.11, "Chickens, layers": 0.20,
            "Asses": 5.87, "Horses": 10.75, "Mules": 5.87}
# Their Pakistan 2015 livestock NH3 = GRM (grazing + spreading) + MNM (housing + storage), Table 3.
BENCH_GRM, BENCH_MNM = 359.4, 136.3


def _population(year=YEAR):
    import csv
    for r in _activity_rows(HIST, comments=False):
        if int(r["year"]) == year:
            return {k: float(v) for k, v in r.items() if k != "year"}
    raise KeyError("no livestock stocks for %d" % year)


MANAGED = ("daily_spread", "solid_storage", "drylot", "liquid_slurry", "poultry_litter")


def per_head_nh3(data, mms_split):
    """Our EMEP chain applied to one buffalo under a given manure-management split, kg NH3/head/yr.

    Uses the species-specific EMEP/EEA Table 3-9 factors the engine now applies, not the single
    solid-manure chain an earlier version ran over every species -- buffalo differ from cattle in
    both TAN fraction (0.50 vs 0.60) and storage factor (0.17 vs 0.32), which is exactly the kind of
    detail this comparison is meant to expose.
    """
    from pkinv.sectors.agriculture import air_pollutants as ap
    nex = data.nex_per_head("buffalo")
    tan_frac = data.efv("nh3_emep_tan", "buffalo")
    prp = mms_split.get("pasture_range_paddock", 0.0)
    managed = sum(mms_split.get(k, 0.0) for k in MANAGED)

    lost = nex * prp * tan_frac * data.efv("nh3_emep_grazing", "buffalo")
    for system in MANAGED:
        share = mms_split.get(system, 0.0)
        stages = ap.SYSTEM_STAGES.get(system)
        if not share or not stages:
            continue
        tan = nex * share * tan_frac
        for stage in stages:
            step = tan * data.efv("nh3_emep_" + stage, "buffalo")
            lost += step
            tan -= step
    return lost * 17.0 / 14.0, managed, prp


def management_comparison(data=None):
    """Where the residual divergence actually sits: the manure-management split.

    Our per-head buffalo factor is bracketed by two external parameterisations that disagree with
    EACH OTHER by more than a factor of four (they are not statistically independent -- both draw on
    overlapping FAO activity data -- so they bracket rather than corroborate) -- GLEAM assumes no buffalo grazing at all and lands
    above us, the benchmark's implied factor is consistent with buffalo manure being overwhelmingly
    grazing-deposited and lands far below. The split is not measured for Pakistan, so neither can be
    ruled out from available data.
    """
    import csv as _csv
    if data is None:
        data = InventoryData()
    gleam = {}
    path = asset_path(ROOT, "data", "gleam_mms.csv")
    for r in _activity_rows(path, comments=False):
        gleam.setdefault(r["species"], {})[r["system"]] = float(r["share"])
    out = {}
    for label, split in (("ours", data.mms["buffalo"]), ("GLEAM 3.0 South Asia", gleam["buffalo"])):
        ef, managed, prp = per_head_nh3(data, split)
        out[label] = {"kg_NH3_per_head_yr": ef, "managed_share": managed, "grazing_share": prp}
    return out


def derive(data=None):
    if data is None:
        data = InventoryData()
    pop = _population()
    dairy_share = data.p("dairy_cattle_share")

    # What Table A8 CAN account for, on the same populations we use.
    attributed = {
        "Cattle, dairy": pop["cattle"] * dairy_share * TABLE_A8["Cattle, dairy"],
        "Cattle, non-dairy": pop["cattle"] * (1 - dairy_share) * TABLE_A8["Cattle, non-dairy"],
        "Sheep": pop["sheep"] * TABLE_A8["Sheep"],
        "Goats": pop["goats"] * TABLE_A8["Goats"],
        # our activity data carries one poultry figure; broilers dominate Pakistani flocks, and the
        # layer/broiler factors differ by only 0.09 kg so the choice is immaterial at this scale
        "Chickens, broilers": pop["poultry"] * TABLE_A8["Chickens, broilers"],
    }
    attributed_kt = {k: v / 1e6 for k, v in attributed.items()}     # kg -> kt
    bench_total = BENCH_GRM + BENCH_MNM
    residual_kt = bench_total - sum(attributed_kt.values())
    unattributed_head = pop["buffalo"] + pop["camels"]

    implied = residual_kt * 1e6 / unattributed_head if unattributed_head else None
    implied_buffalo_only = residual_kt * 1e6 / pop["buffalo"] if pop["buffalo"] else None

    # our own implied factor, for comparison: livestock NH3 / same head-count basis
    from pkinv.sectors.agriculture import air_pollutants as ap
    rows = ap.engine_rows_for_year(YEAR)
    ours = None
    if rows:
        sc = ap.scopes(rows)
        ours_livestock = sc["Livestock (grazing+manure+management)"]
        _, npools = manure.compute(data)
        ours = {"livestock_NH3_kt": ours_livestock,
                "ratio_to_benchmark": ours_livestock / bench_total}

    return {
        "year": YEAR,
        "benchmark_livestock_kt": bench_total,
        "benchmark_components": {"GRM": BENCH_GRM, "MNM": BENCH_MNM},
        "attributed_by_table_A8_kt": attributed_kt,
        "attributed_total_kt": sum(attributed_kt.values()),
        "residual_kt": residual_kt,
        "unattributed_head": {"buffalo": pop["buffalo"], "camels": pop["camels"]},
        "implied_EF_kg_NH3_per_head": implied,
        "implied_EF_buffalo_only_upper_bound": implied_buffalo_only,
        "table_A8_dairy_cattle_EF": TABLE_A8["Cattle, dairy"],
        "ours": ours,
        "management_comparison": management_comparison(data),
        "caveat": "Our derivation, not a published value. Table A8 omits buffalo, so the residual is "
                  "inferred and also absorbs camels and any species the table does not tabulate.",
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    r = derive()
    with open(asset_path(OUT, "buffalo_implied_ef.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, indent=2)

    print("Implied buffalo NH3 factor in the benchmark (%d) -- OUR DERIVATION, not published:" % YEAR)
    print("  benchmark Pakistan livestock NH3 (GRM+MNM)     %8.1f kt" % r["benchmark_livestock_kt"])
    for k, v in sorted(r["attributed_by_table_A8_kt"].items(), key=lambda kv: -kv[1]):
        print("    less %-26s %8.1f kt" % (k, v))
    print("  residual, unattributed by Table A8             %8.1f kt" % r["residual_kt"])
    print("  unattributed head (buffalo + camels)           %8.1f M" %
          (sum(r["unattributed_head"].values()) / 1e6))
    print()
    print("  implied EF over buffalo+camels   %6.2f kg NH3 head-1 yr-1" %
          r["implied_EF_kg_NH3_per_head"])
    print("  upper bound, buffalo alone       %6.2f kg NH3 head-1 yr-1" %
          r["implied_EF_buffalo_only_upper_bound"])
    print("  their tabulated dairy cattle EF  %6.2f  (Table A8, for scale)" %
          r["table_A8_dairy_cattle_EF"])
    if r["ours"]:
        print()
        print("  our livestock NH3 at %d            %8.1f kt (%.2fx the benchmark)"
              % (YEAR, r["ours"]["livestock_NH3_kt"], r["ours"]["ratio_to_benchmark"]))
    mc = r["management_comparison"]
    print()
    print("  Per-head buffalo factor under different manure-management splits:")
    for lbl, v in sorted(mc.items(), key=lambda kv: -kv[1]["kg_NH3_per_head_yr"]):
        print("    %-22s %6.2f kg NH3 head-1 yr-1  (managed %.2f, grazing %.2f)"
              % (lbl, v["kg_NH3_per_head_yr"], v["managed_share"], v["grazing_share"]))
    print("    %-22s %6.2f  (implied, this module)" % ("benchmark", r["implied_EF_buffalo_only_upper_bound"]))
    print()
    print("  Two external parameterisations bracket ours in OPPOSITE directions and disagree with")
    print("  each other by %.1fx, which points the residual divergence towards the management split"
          % (mc["GLEAM 3.0 South Asia"]["kg_NH3_per_head_yr"] / r["implied_EF_buffalo_only_upper_bound"]))
    print("  -- which is not measured for Pakistan and is already declared a limitation.")
    print()
    print("  " + r["caveat"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""FAOSTAT's managed soils is half this inventory's - and the nitrogen agrees.

WHY THIS EXISTS. The benchmark table records managed soils at 0.49 of FAOSTAT and the
manuscript explains it in one clause: FAOSTAT "applies a synthetic-fertiliser default to a
national nitrogen supply that this inventory tracks through an explicit ledger". That
sentence points at the fertiliser, and the fertiliser is the one thing that agrees.

WHAT MATCHES. Both compilations publish two of the nitrogen flows behind managed soils, and
both are held here as FAOSTAT's own extracts:

  synthetic fertiliser N   3,775,000 t N in this inventory (NFDC offtake, the ledger's own
                           activity) against FAOSTAT's 3,808,775 for 2023 - agreement to
                           0.9 per cent
  livestock head           2.311 billion against 2.289 billion summed over the six species
                           both carry - 0.9 per cent, and the difference runs the WRONG WAY
                           for the headline: this inventory counts MORE sheep (1.36x), goats
                           (1.10x) and camels (1.30x) than FAOSTAT, so more excreted nitrogen,
                           not less

So the factor of two is not in the nitrogen. It is in the factors applied to it and in how
excreted nitrogen is partitioned.

WHAT THE EF VINTAGE EXPLAINS, AND WHAT IT DOES NOT. FAOSTAT applies the 2006 Guidelines'
aggregate EF1 of 0.010; this inventory applies the 2019 Refinement's disaggregated 0.005 for
dry climates. The repository already prices that as a named scenario, and taking it moves
managed soils from 28.51 to 40.41 Mt - closing 11.90 of the 29.99 Mt gap, about 40 per cent.
The remaining 18.09 Mt is neither activity nor the direct-EF vintage.

WHERE IT LIES, ACQUIRED RATHER THAN GUESSED. The first version of this module said the
residual needed FAOSTAT's four items priced separately and that only their sum was held. They
were then acquired - public, free, and logged in data/raw/ACQUISITION_LOG_faostat_soils.csv
with its four negatives - and they localise it to one pool:

  manure on pasture          7.711 here against 27.291   +19.580 Mt   65.3% of the gap
  synthetic fertiliser      12.248 against 21.016         +8.768      29.3%
  crop residues              0.631 against  3.328         +2.697       9.0%
  manure applied to soils    7.936 against  6.864         -1.072      -3.6%

The residual is not diffuse. Two-thirds of it is pasture deposition, and the mechanism is the
same one that drives the fertiliser pool: the 2019 Refinement disaggregated these direct
factors by climate and Pakistan sits at the dry end. EF1 is 0.005 dry here against the 2006
aggregate 0.010, and EF3PRP for cattle is 0.002 dry here against the 2006 default of 0.02 - a
tenfold cut. FAOSTAT applies the aggregate values.

AND ONE POOL RUNS THE OTHER WAY, which the factor vintage cannot explain. Manure applied to
soils is 1.16 times FAOSTAT's despite the lower factor, so this inventory routes MORE excreted
nitrogen to field application than FAOSTAT does. That is the partition, not the factor, and it
is the one place the two compilations disagree about where the nitrogen goes rather than what
happens to it.

THE POOLS THEMSELVES MATCH. FAOSTAT's four items map one-to-one onto this inventory's four
pools, so none of the gap is scope. That was worth checking first and it is why the finding
is about factors: had the pools differed, no comparison of totals would have meant anything.
The acquired extract also validates itself against what the repository already held - its four
items sum to 58.4996 Mt for 2023, which is the 58.5 the benchmark register carries.

Usage:  python3 -m pkinv.sectors.agriculture.faostat_nitrogen_flows [--check]
Writes: outputs/pakemis_faostat_nitrogen_flows.csv
"""
import argparse
import csv
import io
import os
import re

from pkinv.assets import asset_path, resolve
from pkinv.core.io import read_rows, write_table
from pkinv.paths import DATA, OUTPUTS

OUT = asset_path(OUTPUTS, "pakemis_faostat_nitrogen_flows.csv")

# FAOSTAT's own extracts, held as historical panels
FAO_FERT = "data/activity/historical/fertilizer_n.csv"
FAO_STOCK = "data/activity/historical/livestock_stocks.csv"
# acquired 2026-09-30: Pakistan's rows of FAOSTAT's Emissions Totals, filtered out of the
# world bulk rather than kept whole (20.5 MB compressed, 364 MB expanded, for one country)
FAO_ITEMS = os.path.join("raw", "faostat", "faostat_emissions_totals_pakistan.csv")
FAO_ITEM_CODES = {"5061": "synthetic fertiliser", "5062": "manure applied to soils",
                  "5063": "manure on pasture", "5064": "crop residues"}
FAO_CO2E_AR5 = "723113"          # the element code, from the archive's own Elements table
FAO_ITEM_YEAR = "2023"

LEDGER = "agriculture_activity_factor_ledger.csv"
SENSITIVITY = os.path.join("eval", "sensitivity.csv")
BENCHMARKS = os.path.join("shared", "evidence", "benchmarks.csv")

# The species both compilations carry. Poultry is included because both publish it; the
# release's excretion ledger treats it separately and the comparison here is of HEAD, not of
# nitrogen, so the species set is the intersection and nothing is imputed.
SPECIES = ("cattle", "buffalo", "sheep", "goats", "camels", "poultry")

# FAOSTAT's calendar year set against this inventory's FY2023-24. Declared rather than
# derived: a fiscal-to-calendar choice is a decision, and the alternative (2024, which
# FAOSTAT also publishes for stocks but not for fertiliser) is reported beside it.
FAO_FERT_YEAR = "2023"
FAO_STOCK_YEAR = "2024"

MAIN_SCENARIO = "Main case (EF1=0.005 dry; rice continuously flooded)"
EF_2006_SCENARIO = "Soil EF1 = 0.010 (2006 aggregate)"
BOTH_2006_SCENARIO = "Both 2006 direct factors (EF1 0.010 + EF3PRP aggregate)"

FIELDS = ("row_kind", "flow", "basis", "pakemis", "faostat", "unit",
          "pakemis_over_faostat", "verdict")

BANNER = """\
# FAOSTAT'S MANAGED SOILS IS HALF THIS INVENTORY'S, AND THE NITROGEN AGREES
#
# row_kind=activity    a nitrogen flow both compilations publish, compared directly. These
#                      are the rows that matter: if they agree, no difference in the totals
#                      can be attributed to the nitrogen.
# row_kind=pool        this inventory's managed-soils emissions by nitrogen pool, against
#                      FAOSTAT's four item codes, which map onto them one-to-one.
# row_kind=attribution what the gap between the two totals is made of.
#
# The manuscript used to attribute the difference to FAOSTAT's synthetic-fertiliser
# treatment. The synthetic fertiliser agrees to 0.9 per cent; see the module docstring.
"""


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def build():
    fert = {r["year"]: _num(r["n_tonnes"]) for r in read_rows(resolve(FAO_FERT))}
    stock = {r["year"]: r for r in read_rows(resolve(FAO_STOCK))}
    led = [r for r in read_rows(asset_path(OUTPUTS, LEDGER))
           if r["category"] == "Managed soils"]
    if not led:
        raise SystemExit("the activity-factor ledger holds no Managed soils rows")

    # the release's own activity, read out of the ledger's activity strings rather than
    # recomputed - the ledger is what the emissions were actually built from
    n_offtake = None
    heads = {}
    for r in led:
        m = re.search(r"nitrogen_N_offtake=([\d.]+)", r["activity"])
        if m:
            n_offtake = float(m.group(1))
        for h in re.finditer(r"agriculture:livestock:(\w+)=([\d.]+) head", r["activity"]):
            heads[h.group(1)] = float(h.group(2))
    if n_offtake is None:
        raise SystemExit("no nitrogen_N_offtake in the ledger's synthetic-fertiliser rows")

    rows = []

    def add(kind, flow, basis, a, b, unit, verdict):
        rows.append({
            "row_kind": kind, "flow": flow, "basis": basis,
            "pakemis": "" if a is None else ("%.0f" % a if abs(a) >= 1000 else "%.4f" % a),
            "faostat": "" if b is None else ("%.0f" % b if abs(b) >= 1000 else "%.4f" % b),
            "unit": unit,
            "pakemis_over_faostat": "" if not (a and b) else "%.3f" % (a / b),
            "verdict": verdict,
        })

    fao_n = fert[FAO_FERT_YEAR]
    add("activity", "synthetic fertiliser nitrogen",
        "PakEmis: NFDC offtake, the ledger's own activity for FY2023-24. FAOSTAT: "
        "fertilizer_n historical panel, calendar %s" % FAO_FERT_YEAR,
        n_offtake, fao_n, "t N",
        "AGREES to %.1f per cent - the flow the manuscript attributed the difference to"
        % abs(100 * (n_offtake / fao_n - 1)))

    tot_r = tot_f = 0.0
    for sp in SPECIES:
        a, b = heads.get(sp), _num(stock[FAO_STOCK_YEAR].get(sp))
        if a and b:
            tot_r += a
            tot_f += b
            add("activity", "livestock head: %s" % sp,
                "PakEmis: the census re-base. FAOSTAT: stocks panel, calendar %s"
                % FAO_STOCK_YEAR, a, b, "head",
                "%s by %.0f per cent" % ("PakEmis higher" if a > b else "FAOSTAT higher",
                                         abs(100 * (a / b - 1))))
    add("activity", "livestock head: all six species", "summed over the species both carry",
        tot_r, tot_f, "head",
        "AGREES to %.1f per cent, and the residual runs the WRONG WAY for the headline: "
        "more animals means more excreted nitrogen, not less"
        % abs(100 * (tot_r / tot_f - 1)))

    pools = {}
    for r in led:
        s = r["subitem"]
        kind = ("synthetic fertiliser" if "synthetic" in s else
                "manure applied to soils" if "organic manure" in s else
                "crop residues" if "crop residues" in s else
                "manure on pasture" if "pasture" in s else "other")
        leg = "direct" if s.startswith("Direct") else "indirect"
        pools[(kind, leg)] = pools.get((kind, leg), 0.0) + float(r["co2e_Mt_AR5"])
    fao_items = {v: k for k, v in FAO_ITEM_CODES.items()}
    # the acquired per-item values, in Mt to match the pools
    fao_pool = {}
    for r in read_rows(asset_path(DATA, FAO_ITEMS)):
        if (r["Item Code"] in FAO_ITEM_CODES and r["Element Code"] == FAO_CO2E_AR5
                and r["Year"] == FAO_ITEM_YEAR):
            fao_pool[FAO_ITEM_CODES[r["Item Code"]]] = float(r["Value"]) / 1000.0
    if len(fao_pool) != len(FAO_ITEM_CODES):
        raise SystemExit("the FAOSTAT extract is missing managed-soils items for %s: got %s"
                         % (FAO_ITEM_YEAR, sorted(fao_pool)))

    by_kind = {}
    for (kind, leg), v in pools.items():
        by_kind[kind] = by_kind.get(kind, 0.0) + v
    pakemis_total = sum(pools.values())
    gap_total = sum(fao_pool[k] - by_kind.get(k, 0.0) for k in fao_pool)

    for kind in sorted(fao_pool, key=lambda k: -(fao_pool[k] - by_kind.get(k, 0.0))):
        a, b = by_kind.get(kind, 0.0), fao_pool[kind]
        gap = b - a
        add("pool", kind,
            "PakEmis pool against FAOSTAT item %s, CO2eq AR5, calendar %s"
            % (fao_items[kind], FAO_ITEM_YEAR), a, b, "Mt CO2e AR5",
            "%+.3f Mt, %.1f per cent of the gap%s"
            % (gap, 100 * gap / gap_total,
               " - PakEmis is HIGHER here, which the factor vintage cannot explain and "
               "the nitrogen partition can" if gap < 0 else ""))
    # the direct/indirect legs beneath each pool, so the EF vintage's reach is visible
    for (kind, leg), v in sorted(pools.items(), key=lambda kv: -kv[1]):
        add("pool_leg", "%s (%s)" % (kind, leg),
            "PakEmis only; FAOSTAT does not split its items into direct and indirect",
            v, None, "Mt CO2e AR5", "")

    sens = {r["scenario"]: r for r in read_rows(asset_path(OUTPUTS, SENSITIVITY))}
    main = _num(sens[MAIN_SCENARIO]["soils"])
    ef2006 = _num(sens[EF_2006_SCENARIO]["soils"])
    bench = next(r for r in read_rows(asset_path(DATA, BENCHMARKS))
                 if r["source"] == "FAOSTAT" and r["engine_category"] == "Managed soils")
    fao_total = _num(bench["value_Mt_co2e"])

    add("attribution", "managed soils, as reported", "PakEmis main case against FAOSTAT",
        main, fao_total, "Mt CO2e AR5",
        "the headline ratio; the gap to account for is %.2f Mt" % (fao_total - main))
    add("attribution", "managed soils, at FAOSTAT's EF1 vintage",
        "the repository's own named scenario: 2006 aggregate EF1 0.010 in place of the "
        "2019 Refinement's 0.005 for dry climates", ef2006, fao_total, "Mt CO2e AR5",
        "closes %.2f Mt, %.0f per cent of the gap - the single largest identified term"
        % (ef2006 - main, 100 * (ef2006 - main) / (fao_total - main)))
    both = _num(sens[BOTH_2006_SCENARIO]["soils"])
    add("attribution", "managed soils, at BOTH of FAOSTAT's 2006 direct factors",
        "the EF1 scenario above plus the pasture factor at its 2006 aggregate; the two are "
        "DISJOINT - EF1 scales synthetic fertiliser, organic manure and crop residues, "
        "EF3PRP scales the two pasture rows, and no subitem is in both sets",
        both, fao_total, "Mt CO2e AR5",
        "closes %.2f Mt, %.0f per cent of the gap. The comparator's direct-factor vintage is "
        "therefore almost the whole story; what is left is %.2f Mt in the indirect factors "
        "(EF4 and EF5 also changed between vintages) and the nitrogen partition"
        % (both - main, 100 * (both - main) / (fao_total - main), fao_total - both))
    biggest = max(fao_pool, key=lambda k: fao_pool[k] - by_kind.get(k, 0.0))
    add("attribution", "unexplained after activity and EF1 vintage",
        "neither nitrogen nor the EF1 vintage; localised by pool since the four FAOSTAT "
        "items were acquired (2026-09-30)",
        fao_total - ef2006, None, "Mt CO2e AR5",
        "LOCALISED: %s carries %+.3f Mt, %.1f per cent of the whole gap, and its factor is "
        "the same climate disaggregation - EF3PRP for cattle 0.002 dry here against the 2006 "
        "default 0.02. The EF1 scenario above moves only the EF1 pools, which is why it left "
        "a remainder this size"
        % (biggest, fao_pool[biggest] - by_kind.get(biggest, 0.0),
           100 * (fao_pool[biggest] - by_kind.get(biggest, 0.0)) / gap_total))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify the shipped file matches a fresh build; write nothing")
    args = ap.parse_args(argv)
    rows = build()
    if args.check:
        if not os.path.exists(OUT):
            raise SystemExit("%s does not exist" % OUT)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        if io.open(OUT, encoding="utf-8").read() != BANNER + buf.getvalue():
            raise SystemExit("%s differs from a fresh build" % OUT)
        print("%s: current" % OUT)
        return
    write_table(OUT, FIELDS, rows, banner=BANNER.splitlines())
    print("FAOSTAT nitrogen-flow comparison -> %s (%d rows)" % (OUT, len(rows)))
    for r in rows:
        if r["row_kind"] in ("activity", "attribution") and "all six" not in r["flow"]:
            if r["row_kind"] == "pool":
                continue
            print("  %-46s %12s %12s  %s"
                  % (r["flow"][:46], r["pakemis"], r["faostat"] or "-",
                     r["pakemis_over_faostat"] or ""))


if __name__ == "__main__":
    main()

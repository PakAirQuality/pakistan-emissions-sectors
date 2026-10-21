"""Managed-soils method comparison, not independent accuracy validation.

Current emissions and conditional direct-factor substitutions are calculated
from the engine, not rounded published outputs. PakEmis FY2023-24 flows plus a
2024 census/projection herd are compared with retained FAOSTAT CY2023 emissions.
CY2024 stocks are a separate diagnostic, not the inputs behind CY2023 emissions.

The substitutions hold N pools, rice EF1FR and all indirect terms fixed. They
are not a complete vintage swap or reconstruction of FAOSTAT. The fraction of
the difference bridged is conditional on this path; the residual is unattributed.

The FAOSTAT values are read from data/sectors/agriculture/evidence/faostat_soils_pools.csv:
FAOSTAT's own Pakistan rows for the four items, unrounded, with every element (direct and
indirect N2O, CO2e AR5), written by scripts/ingest_faostat_soils_pools.py from the held
Emissions Totals extract. (The 21 October 2026 pass had used a four-row snapshot rounded to
4 dp; the held extract replaces it.) See docs/nitrogen_comparison_evaluation.md for limits.

Usage: python3 -m pkinv.sectors.agriculture.faostat_nitrogen_flows [--check]
"""
import argparse
import copy
import math
import os

from pkinv.assets import asset_path, resolve
from pkinv.core import gwp
from pkinv.core.io import read_rows, table_text, write_table
from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.agriculture import manure, soils
from pkinv.sectors.agriculture.ef_library import InventoryData

OUT = asset_path(OUTPUTS, "pakemis_faostat_nitrogen_flows.csv")
FAO_FERT = "data/activity/historical/fertilizer_n.csv"
FAO_STOCK = "data/activity/historical/livestock_stocks.csv"
EXTRACT = os.path.join(DATA, "sectors", "agriculture", "evidence", "faostat_soils_pools.csv")
FAO_N2O_DIRECT, FAO_N2O_INDIRECT, FAO_N2O_TOTAL = "7234", "7236", "7230"
FAO_ITEM_CODES = {"5061": "synthetic fertiliser", "5062": "manure applied to soils",
                  "5063": "manure on pasture", "5064": "crop residues"}
FAO_FERT_YEAR, FAO_STOCK_YEAR, FAO_ITEM_YEAR = "2023", "2024", "2023"
SPECIES = ("cattle", "buffalo", "sheep", "goats", "camels", "poultry")
FAO_CO2E_AR5 = "723113"
FIELDS = ("row_kind", "flow", "basis", "pakemis", "faostat", "unit",
          "pakemis_over_faostat", "verdict")
CASE_FLOWS = {
    "current": "managed soils, current engine",
    "ef1": "managed soils, EF1-only substitution",
    "ef3prp": "managed soils, EF3PRP-only substitution",
    "both": "managed soils, EF1 + EF3PRP substitution",
}
BANNER = """\
# PAKEMIS MANAGED SOILS IS ABOUT HALF THE RETAINED FAOSTAT COMPARATOR
# Method comparison; not independent validation or a complete FAOSTAT reconstruction.
# PakEmis FY2023-24 flows include a 2024 census/projection herd; FAOSTAT emissions
# and fertiliser are CY2023, while the stock diagnostic is CY2024. No year alignment
# or harmonisation of animal coverage, excretion, routing or residue inputs is implied.
# row_kind=activity: synthetic-N comparison; stock_diagnostic: species heads, not N.
# row_kind=nitrogen_pool: modelled PakEmis N inputs; no FAOSTAT pool-N values held here.
# row_kind=pool/pool_leg: current engine emissions by broad source and direct/indirect leg.
# row_kind=attribution: conditional direct-factor substitutions at fixed N pools.
# FAOSTAT values: FAOSTAT's own Pakistan rows, unrounded (data/sectors/agriculture/evidence/
# faostat_soils_pools.csv); pool_leg rows carry FAOSTAT's direct and indirect N2O legs at AR5.
"""


def _finite_number(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("%s is not numeric: %r" % (label, value)) from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError("%s must be finite and nonnegative" % label)
    return number


def _year_row(rows, year, label):
    selected = [r for r in rows if r["year"] == year]
    if len(selected) != 1:
        raise ValueError("%s needs exactly one row for %s, got %d"
                         % (label, year, len(selected)))
    return selected[0]


def _extract_rows(rows=None):
    rows = read_rows(EXTRACT) if rows is None else rows
    out = [r for r in rows if r["area"] == "Pakistan" and r["year"] == FAO_ITEM_YEAR]
    if not out:
        raise ValueError("the FAOSTAT extract holds no Pakistan rows for %s" % FAO_ITEM_YEAR)
    return out


def comparator_pools(rows=None):
    """The four FAOSTAT items' CO2e AR5 (Mt) for the comparison year; reject duplicates and gaps."""
    pools = {}
    for r in _extract_rows(rows):
        if r["element_code"] != FAO_CO2E_AR5:
            continue
        code = r["item_code"]
        if code not in FAO_ITEM_CODES or code in pools:
            raise ValueError("unexpected or duplicate FAOSTAT item %s" % code)
        if r["unit"] != "kt":
            raise ValueError("FAOSTAT item %s is in %r, not kt" % (code, r["unit"]))
        pools[code] = _finite_number(r["value"], "FAOSTAT item " + code) / 1000.0
    if set(pools) != set(FAO_ITEM_CODES):
        raise ValueError("the FAOSTAT extract must carry exactly the four managed-soils items")
    return {FAO_ITEM_CODES[code]: value for code, value in pools.items()}


def comparator_legs(rows=None):
    """{(pool, 'direct'|'indirect'): Mt CO2e AR5} from FAOSTAT's N2O elements (kt N2O x AR5 GWP).

    Where FAOSTAT prints no indirect element for an item (synthetic fertilizers), the indirect leg
    is its total N2O less its direct N2O, and the second element of the value says so."""
    by = {}
    for r in _extract_rows(rows):
        if r["item_code"] in FAO_ITEM_CODES and r["element_code"] in (FAO_N2O_DIRECT, FAO_N2O_INDIRECT,
                                                                        FAO_N2O_TOTAL):
            by[(r["item_code"], r["element_code"])] = _finite_number(r["value"], "FAOSTAT N2O")
    legs = {}
    for code, name in FAO_ITEM_CODES.items():
        direct = by.get((code, FAO_N2O_DIRECT))
        indirect, basis = by.get((code, FAO_N2O_INDIRECT)), "printed"
        if indirect is None and direct is not None and (code, FAO_N2O_TOTAL) in by:
            indirect, basis = by[(code, FAO_N2O_TOTAL)] - direct, "total less direct"
        for leg, value, leg_basis in (("direct", direct, "printed"), ("indirect", indirect, basis)):
            if value is not None:
                legs[(name, leg)] = (gwp.to_co2e("N2O", value, "AR5") / 1000.0, leg_basis)
    return legs


def _pool(subitem):
    for text, name in (("synthetic", "synthetic fertiliser"),
                       ("organic manure", "manure applied to soils"),
                       ("crop residues", "crop residues"),
                       ("pasture", "manure on pasture")):
        if text in subitem:
            return name
    raise ValueError("unmapped managed-soils subitem: %s" % subitem)


def _emissions(rows):
    values = {}
    for r in rows:
        if r["category"] != "Managed soils" or r["gas"] != "N2O":
            raise ValueError("comparison received a non-soils or non-N2O component")
        if r["subitem"] in values:
            raise ValueError("duplicate managed-soils subitem: %s" % r["subitem"])
        values[r["subitem"]] = gwp.to_co2e("N2O", r["emissions_Gg"], "AR5") / 1000.0
    return values


def engine_cases(data=None):
    """Fresh engine runs at common N pools; factor substitutions leave activity fixed."""
    data = InventoryData() if data is None else data
    _, npools = manure.compute(data)
    target_ef1 = data.efv("soils", "EF1_agg")
    pasture = copy.deepcopy(data)
    for key in ("EF3PRP_cattle", "EF3PRP_sheepgoat"):
        pasture.ef[("soils", key)]["value"] = data.efv("soils", key + "_agg")
    cases = {
        "current": _emissions(soils.compute(data, npools)),
        "ef1": _emissions(soils.compute(data, npools, ef1_override=target_ef1)),
        "ef3prp": _emissions(soils.compute(pasture, npools)),
        "both": _emissions(soils.compute(pasture, npools, ef1_override=target_ef1)),
    }
    return data, npools, cases


def build(data=None):
    data, npools, cases = engine_cases(data)
    fao_pool = comparator_pools()
    fao_legs = comparator_legs()
    fert = _year_row(read_rows(resolve(FAO_FERT)), FAO_FERT_YEAR, "FAOSTAT fertiliser")
    stock = _year_row(read_rows(resolve(FAO_STOCK)), FAO_STOCK_YEAR, "FAOSTAT stock")
    rows = []

    def add(kind, flow, basis, a, b, unit, verdict):
        rows.append({"row_kind": kind, "flow": flow, "basis": basis,
                     "pakemis": "" if a is None else "%.6f" % a,
                     "faostat": "" if b is None else "%.6f" % b,
                     "unit": unit,
                     "pakemis_over_faostat": "" if a is None or not b else "%.6f" % (a / b),
                     "verdict": verdict})

    n_offtake = data.fertilizer["nitrogen_N_offtake"]["value_t"]
    fao_n = _finite_number(fert["n_tonnes"], "FAOSTAT synthetic N")
    add("activity", "synthetic fertiliser nitrogen",
        "PakEmis NFDC offtake FY2023-24; FAOSTAT fertiliser panel CY2023; shared national "
        "statistics may underlie both compilations", n_offtake, fao_n, "t N",
        "Difference %.3f per cent; this supports a limited synthetic-N consistency check, "
        "not agreement of manure/residue N pools or independent accuracy validation"
        % (100 * (n_offtake / fao_n - 1)))
    for sp in SPECIES:
        entry = data.livestock[sp]
        a, b = entry["head"], _finite_number(stock[sp], "FAOSTAT stock " + sp)
        add("stock_diagnostic", "livestock head: " + sp,
            "PakEmis %s (%s; %s); FAOSTAT stock CY%s, not the CY2023 emissions input"
            % (entry["activity_basis"], entry["reference_period"], entry["source_document_id"],
               FAO_STOCK_YEAR), a, b, "head",
            "Difference %.3f per cent; head counts do not establish excreted N or its routing"
            % (100 * (a / b - 1)))

    inputs = {"FSN synthetic N": n_offtake * 1000,
              "FON applied manure N": npools["FON_N"],
              "FCR returned crop-residue N": soils.residue_N(data),
              "FPRP cattle-type pasture N": npools["FPRP_cattle_N"],
              "FPRP sheep/goat/other pasture N": npools["FPRP_other_N"]}
    for name, value in inputs.items():
        add("nitrogen_pool", name, "Current engine input to managed soils, at its mixed "
            "FY2023-24/census reference basis", value / 1000, None, "t N",
            "PakEmis modelled pool; corresponding FAOSTAT pool-N activity not held in this comparison")

    pools = {}
    for subitem, value in cases["current"].items():
        key = (_pool(subitem), "direct" if subitem.startswith("Direct") else "indirect")
        pools[key] = pools.get(key, 0.0) + value
    by_pool = {name: sum(v for (pool, _), v in pools.items() if pool == name)
               for name in fao_pool}
    totals = {case: sum(values.values()) for case, values in cases.items()}
    fao_total = sum(fao_pool.values())
    gap = fao_total - totals["current"]
    for code, name in FAO_ITEM_CODES.items():
        a, b = by_pool[name], fao_pool[name]
        add("pool", name,
            "PakEmis current reference basis; FAOSTAT item %s CY2023. Broad category "
            "mapping only; detailed activity/coverage not harmonised" % code,
            a, b, "Mt CO2e AR5",
            "FAOSTAT minus PakEmis = %+.6f Mt; emissions alone cannot identify whether "
            "N quantity, routing, factors, year or coverage caused this difference" % (b - a))
    for (name, leg), value in sorted(pools.items()):
        fao, basis = fao_legs.get((name, leg), (None, ""))
        add("pool_leg", "%s (%s)" % (name, leg), "Current engine; FAOSTAT %s N2O leg (%s) at AR5"
            % (leg, basis or "not printed"), value, fao, "Mt CO2e AR5", "")

    factor_note = ("EF1 %.6f -> %.6f; EF3PRP cattle-type %.6f -> %.6f; other %.6f -> %.6f. "
                   "Targets read from registered aggregate factors. Rice EF1FR remains %.6f; "
                   "N pools and all indirect terms remain current. FY2023-24 reference "
                   "against CY2023 comparator") % (
        data.efv("soils", "EF1_dry"), data.efv("soils", "EF1_agg"),
        data.efv("soils", "EF3PRP_cattle"), data.efv("soils", "EF3PRP_cattle_agg"),
        data.efv("soils", "EF3PRP_sheepgoat"), data.efv("soils", "EF3PRP_sheepgoat_agg"),
        data.efv("soils", "EF1FR_rice"))
    for case, flow in CASE_FLOWS.items():
        delta = totals[case] - totals["current"]
        if case == "current":
            verdict = "Current engine total; FAOSTAT minus PakEmis %.6f Mt" % gap
        else:
            fraction = "undefined (zero baseline difference)" if gap == 0 else "%.3f per cent" % (100 * delta / gap)
            verdict = ("Conditional substitution changes PakEmis by %+.6f Mt (%s of the "
                       "baseline difference); this is not causal attribution or independent validation"
                       % (delta, fraction))
        add("attribution", flow, "Selected case: " + case + ". " + factor_note,
            totals[case], fao_total, "Mt CO2e AR5", verdict)
    add("attribution", "unresolved residual after direct-factor substitutions",
        "Retained FAOSTAT total minus the combined conditional case",
        fao_total - totals["both"], None, "Mt CO2e AR5",
        "Unresolved combination of activity, N routing, other factors, detailed coverage "
        "and period differences; their individual contributions have not been identified")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="compare the shipped file with a fresh public build")
    args = ap.parse_args(argv)
    rows = build()
    if args.check:
        with open(OUT, encoding="utf-8", newline="") as handle:
            existing = handle.read()
        if existing != table_text(FIELDS, rows, banner=BANNER.splitlines()):
            raise SystemExit("%s differs from a fresh build" % OUT)
        print("%s: current" % OUT)
        return
    write_table(OUT, FIELDS, rows, banner=BANNER.splitlines())
    print("FAOSTAT managed-soils method comparison -> %s (%d rows)" % (OUT, len(rows)))
    for row in rows:
        if row["row_kind"] == "attribution":
            print("  %s: %s (comparator %s)" % (row["flow"], row["pakemis"], row["faostat"] or "none"))


if __name__ == "__main__":
    main()

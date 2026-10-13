"""The national result as IPCC category x gas, which is how an inventory is actually read.

WHY THIS EXISTS. Every other national output is organised by MODULE - the unit of software -
and the modules are not IPCC categories. The power module is 1.A.1.a grid generation plus
1.A.2 captive self-generation; the transport module is 1.A.3.b road plus mixed 1.A.4.c
off-road machinery; the industry module is the other part of 1.A.2. All three statements are
true at once, and none of them is legible from a module table. A reader who wants to compare
1.A.2 against anybody else's 1.A.2 has to reconstruct it from two modules and a footnote.

AND THE ABSENCE OF THIS TABLE COST SOMETHING CONCRETE. The manuscript's gas decomposition -
"the inventory is X Mt CO2, Y Mt of methane and Z of nitrous oxide, and methane is N percent
of the total" - was typed, because there was no generated table to read it from. It went
stale: it kept printing a decomposition from a superseded release whose three parts summed to
455.14 against a headline of 448.00, with CO2 wrong by 9.5 Mt, through several rounds in which
every other headline number was re-anchored. The paper's central methodological claim is that
its numbers are read from outputs and cannot drift, and the one paragraph with no output
behind it is the one that drifted.

THE MAPPING IS NOT DECLARED HERE. Which IPCC code an engine category belongs to is read from
outputs/completeness.csv, which already carries that mapping for all 82 category-gas
combinations and is itself generated. A second hand-written mapping in this file would be one
more thing to fall out of step with the first - the failure this module exists downstream of.
If a category has no code there, that is an error and this raises, because a national result
row that cannot say which IPCC category it belongs to is not a national result row.

What IS declared here is the Guidelines' NAME for each code, because that is a property of the
IPCC 2006 Guidelines rather than of this inventory - see IPCC_CATEGORY_NAMES.

Usage:  python3 -m pkinv.report.category_ledger
Writes: outputs/national_category_gas.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core import registry
from pkinv.paths import OUTPUTS
from pkinv.report import national_rollup

# One row per module in the reported ledger names the module a category's emissions were
# computed in. It is the join back to the software, and it is the column that makes
# "1.A.2 = captive gas in power + industrial fuel in industry" visible in one place.
FIELDS = ("ipcc_code", "ipcc_category", "ipcc_allocation", "engine_category", "module",
          "gas", "ch4_origin", "configuration", "co2e_Mt_AR5", "co2e_Mt_AR6", "share_pct")


# The IPCC 2006 Guidelines' own names for the codes this inventory reports. Declared here
# rather than read from the completeness matrix, because that matrix's `category` column is a
# STREAM label - "Residential - piped natural gas", "Electricity - bagasse and biomass
# generation" - and one code carries a dozen of them. Reading a category name out of it gives
# whichever stream happened to sort last, which is how the first draft of this file labelled
# 1.A.1.a "Electricity - bagasse and biomass generation".
#
# This is a property of the Guidelines, not of this inventory, which is why it can be written
# down. What must NOT be written down twice is the engine-category-to-code mapping: that is
# read from the completeness matrix below. A test asserts this table has a name for every code
# the ledger produces and no names for codes it does not, so it cannot drift either way.
IPCC_CATEGORY_NAMES = {
    "1.A.1.a": "Public electricity and heat production",
    "1.A.2": "Manufacturing industries and construction",
    "1.A.3.a": "Civil aviation",
    "1.A.3.b": "Road transportation",
    "1.A.3.c": "Railways",
    "1.A.4.b": "Residential",
    # The engine reports this as "Mixed off-road (1A4c/1A2)" and means it: the residual class
    # mixes agricultural machinery with construction and industrial mobile plant, which the
    # Guidelines book under 1.A.2. It is placed at 1.A.4.c because that is where the larger
    # part belongs, and UNRESOLVED_ALLOCATION records that the placement is not settled - it
    # must not read as a clean 1.A.4.c category.
    "1.A.4.c": "Agriculture/forestry/fishing/fish farms",
    # The rc11 rail re-base's receiving category: the Year Book measures ONE
    # non-locomotive aggregate (workshops, power houses, pumps, track machinery) and
    # publishes no per-use split, so the code is the honest pair rather than a single
    # destination - UNRESOLVED_ALLOCATION carries the placement note.
    "1.A.2/1.A.4.c": "Railway stationary and off-road energy (unresolved split)",
    "1.B.2": "Fugitive emissions from oil and natural gas",
    "2.A.1": "Cement production",
    # rc52: the three IPPU categories that entered the reference through their gates
    "2.B.1": "Ammonia production",
    "2.C.1": "Iron and steel production",
    "2.D.1": "Lubricant use",
    # MIGRATED 2026-10-06 with the rest of sector 3. These six keys used to read 3.A, 3.B,
    # 3.C, 3.D, 3.F and 3.H - UNFCCC CRT codes under a dict whose docstring claims the names
    # are "a property of the IPCC 2006 Guidelines". They were not: the Guidelines name 3.A
    # Livestock and put enteric fermentation at 3.A.1, and they have no 3.D agricultural
    # soils at all. Names below follow Table 8.2's categories in this file's sentence case.
    "3.A.1": "Enteric fermentation",
    "3.A.2": "Manure management",
    # The two that SPLIT. Manure management's indirect N2O is a category of its own in the
    # aggregate-sources block, and agricultural soils divides by pathway; naming them is the
    # only way a reader of the ledger can tell 3.A.2 from 3.C.6 at a glance.
    "3.C.6": "Indirect N2O emissions from manure management",
    "3.C.4": "Direct N2O emissions from managed soils",
    "3.C.5": "Indirect N2O emissions from managed soils",
    "3.C.7": "Rice cultivation",
    "3.C.1.b": "Biomass burning in croplands",
    # NOT "Urea application and liming". Liming is 3.C.2 (3.G before the migration) and this
    # inventory does not estimate it: the completeness matrix carries it as NE, pending
    # national lime-use data. A display name that absorbs a category the same release declares
    # unestimated is a completeness claim smuggled into a label, and a test now asserts no name
    # here mentions an NE category.
    "3.C.3": "Urea application",
    "4.A": "Solid waste disposal",
    "4.C.2": "Open burning of waste",
    "4.D.1": "Domestic wastewater treatment and discharge",
}


# Codes whose engine content is not wholly inside them, with what it mixes and why the
# placement stands. Printed beside the row rather than resolved silently.
UNRESOLVED_ALLOCATION = {
    "1.A.4.c": "mixed mobile machinery: the source's residual class carries construction and "
               "industrial plant that the Guidelines book under 1.A.2, and the split is not "
               "published",
    "1.A.2/1.A.4.c": "railway workshops and power houses are stationary combustion (1.A.2 "
                     "or 1.A.4.a by operator type), track machinery is off-road transport; "
                     "the Year Book publishes one non-locomotive aggregate and no per-use "
                     "split, so the pair is declared rather than resolved",
}


def category_codes():
    """engine category -> IPCC code, from the completeness matrix.

    Only rows whose notation key is E carry an engine category, which is exactly the set that
    can appear in this ledger.
    """
    path = asset_path(OUTPUTS, "completeness.csv")
    if not os.path.exists(path):
        raise IOError("outputs/completeness.csv is missing: run "
                      "python3 -m pkinv.report.completeness first")
    from pkinv.report import category_crosswalk
    split = category_crosswalk.split_categories()
    out = {}
    for r in _activity_rows(path, comments=False):
        engine = (r.get("engine_category") or "").strip()
        if not engine or r.get("notation_key") != "E":
            continue
        code = (r.get("code") or "").strip()
        # A SPLIT CATEGORY IS LEFT OUT, not resolved to one of its codes. Under IPCC 2006 two
        # engine categories map to two codes each along a component line - manure management's
        # indirect N2O is 3.C.6 while its CH4 and direct N2O are 3.A.2, and managed soils
        # divides into 3.C.4 and 3.C.5 - so for these the code is a property of the COMPONENT
        # and this dict cannot express it. Omitting them makes a caller that still keys on the
        # category raise a KeyError, which is what sends it to component_code(); returning
        # either code, or the parent, would have shipped a plausible wrong answer.
        if engine in split:
            continue
        if engine in out and out[engine] != code:
            raise ValueError(
                "the completeness matrix maps engine category %r to two IPCC codes, "
                "%s and %s, and the crosswalk does not declare it as a split; a national "
                "result row cannot belong to both"
                % (engine, out[engine], code))
        out[engine] = code
    return out


def component_code(category, subitem, gas):
    """IPCC 2006 code for one component: the crosswalk first, the matrix for the rest.

    The crosswalk holds every category that MOVED or SPLIT when this release adopted IPCC 2006
    as canonical (agriculture and LULUCF). Energy (1.x) and IPPU (2.x) carry the same codes in
    both schemes and waste was already IPCC 2006, so those resolve from the completeness
    matrix's own code, which the migration did not touch. There is no silent default: a
    category in neither place raises, because the old behaviour here was
    `codes.get(category, "unresolved")` and an "unresolved" string in a shipped code column is
    indistinguishable from a category that genuinely has no code.
    """
    from pkinv.report import category_crosswalk
    try:
        return category_crosswalk.resolve(category, subitem, gas)[0]
    except KeyError:
        pass
    codes = category_codes()
    if category not in codes:
        raise KeyError(
            "engine category %r has no IPCC 2006 code: it is in neither the crosswalk "
            "(data/shared/lookups/category_crosswalk.csv) nor the completeness matrix"
            % category)
    return codes[category]


def build(dung_basis=national_rollup.BASELINE):
    """Rows of (code, category, module, gas), summed, largest first.

    A category computed in two modules keeps two rows rather than one. That is deliberate:
    collapsing them would hide the split the table exists to make visible, and the code column
    still lets a reader add them.
    """
    # Built per sector rather than through registry.build_all() because the ledger must be
    # producible under either configuration, and build_all() takes no configuration argument.
    # The `_sector` key registry.build_all() adds is stamped here for the same reason.
    components = []
    for s in registry.all_sectors():
        components.extend(dict(c, _sector=s.NAME)
                          for c in national_rollup._build(s, dung_basis))
    # THE CODE IS RESOLVED PER COMPONENT, not per engine category, because two categories
    # split under IPCC 2006 (manure management into 3.A.2 and 3.C.6, managed soils into 3.C.4
    # and 3.C.5). It therefore has to enter the aggregation key below: grouping on the category
    # first and labelling afterwards would collapse the two halves of a split into one row and
    # then give that row a single code, which is precisely the mixing this migration removed.
    unmapped = []
    for c in components:
        try:
            component_code(c["category"], c.get("subitem"), c["gas"])
        except KeyError:
            if c["category"] not in unmapped:
                unmapped.append(c["category"])
    if unmapped:
        raise ValueError(
            "these engine categories have no IPCC 2006 code in the crosswalk or the "
            "completeness matrix, so their emissions cannot be reported as a category: %s"
            % ", ".join(sorted(unmapped)))

    # CH4 carries its origin, because the two have different GWPs and the manuscript reports
    # the fossil share. Splitting the rows rather than adding a column would put two CH4 rows
    # in one category and make the table print methane twice; the column keeps the ledger one
    # row per (category, module, gas) and still lets the share be computed rather than typed.
    totals = {}
    for c in components:
        origin = ("fossil" if c.get("fossil") else "biogenic") if c["gas"] == "CH4" else ""
        key = (component_code(c["category"], c.get("subitem"), c["gas"]),
               c["category"], c["_sector"], c["gas"], origin)
        ar5, ar6 = totals.get(key, (0.0, 0.0))
        totals[key] = (ar5 + c["co2e_Mt_AR5"], ar6 + c["co2e_Mt_AR6"])
    national = sum(v[0] for v in totals.values())

    config = national_rollup.CONFIGURATIONS[dung_basis]
    rows = []
    for (code, category, module, gas, origin), (ar5, ar6) in totals.items():
        label = IPCC_CATEGORY_NAMES.get(code)
        if label is None:
            raise ValueError(
                "IPCC code %s has no name in IPCC_CATEGORY_NAMES; the ledger will not print a "
                "code it cannot name" % code)
        rows.append({"ipcc_code": code, "ipcc_category": label,
                     "ipcc_allocation": ("unresolved" if code in UNRESOLVED_ALLOCATION
                                         else "settled"),
                     "engine_category": category, "module": module, "gas": gas,
                     "ch4_origin": origin, "configuration": config,
                     "co2e_Mt_AR5": ar5, "co2e_Mt_AR6": ar6,
                     "share_pct": (100.0 * ar5 / national) if national else 0.0})
    rows.sort(key=lambda r: (r["ipcc_code"], r["module"], r["gas"], r["ch4_origin"]))
    return rows


def by_gas(rows=None, dung_basis=national_rollup.BASELINE):
    """{gas: (AR5 Mt, AR6 Mt, AR5 share of the national total)}, plus a TOTAL entry.

    The manuscript's gas decomposition reads this. It is a function rather than a column so
    the share is computed once, in the place that owns the arithmetic, instead of in whichever
    document happens to quote it.
    """
    rows = rows if rows is not None else build(dung_basis)
    out = {}
    for r in rows:
        ar5, ar6 = out.get(r["gas"], (0.0, 0.0))
        out[r["gas"]] = (ar5 + r["co2e_Mt_AR5"], ar6 + r["co2e_Mt_AR6"])
    total5 = sum(v[0] for v in out.values())
    total6 = sum(v[1] for v in out.values())
    stats = {g: (v[0], v[1], 100.0 * v[0] / total5 if total5 else 0.0)
             for g, v in out.items()}
    stats["TOTAL"] = (total5, total6, 100.0)
    return stats


def methane_origin(rows=None, dung_basis=national_rollup.BASELINE):
    """(fossil Mt, biogenic Mt, fossil share of all methane, percent).

    The manuscript reports the fossil share because it is the part whose oxidation adds a
    carbon atom the atmosphere did not already have, and because it is the part whose AR6 GWP
    differs from the biogenic one. It was typed and had drifted.
    """
    rows = rows if rows is not None else build(dung_basis)
    fossil = sum(r["co2e_Mt_AR5"] for r in rows if r["ch4_origin"] == "fossil")
    biogenic = sum(r["co2e_Mt_AR5"] for r in rows if r["ch4_origin"] == "biogenic")
    total = fossil + biogenic
    return fossil, biogenic, (100.0 * fossil / total if total else 0.0)


def by_code(rows=None, dung_basis=national_rollup.BASELINE):
    """{IPCC code: AR5 Mt}, summed across the modules a category is computed in."""
    rows = rows if rows is not None else build(dung_basis)
    out = {}
    for r in rows:
        out[r["ipcc_code"]] = out.get(r["ipcc_code"], 0.0) + r["co2e_Mt_AR5"]
    return out


def _write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for r in rows:
            w.writerow([r["ipcc_code"], r["ipcc_category"], r["ipcc_allocation"],
                        r["engine_category"], r["module"], r["gas"], r["ch4_origin"],
                        r["configuration"],
                        round(r["co2e_Mt_AR5"], 5), round(r["co2e_Mt_AR6"], 5),
                        round(r["share_pct"], 3)])


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = build()
    path = asset_path(OUTPUTS, "national_category_gas.csv")
    _write(path, rows)
    _write(asset_path(OUTPUTS, "national_category_gas_ledger.csv"), build(national_rollup.ALTERNATIVE))

    gases = by_gas(rows)
    codes = by_code(rows)
    print("national ledger by IPCC category and gas -> %s" % path)
    print("  %d rows over %d codes and %d gases; configuration %s"
          % (len(rows), len(codes), len(gases) - 1, national_rollup.BASELINE))
    for gas, (ar5, _ar6, share) in sorted(gases.items(), key=lambda kv: -kv[1][0]):
        print("    %-6s %8.2f Mt CO2e (AR5)  %5.2f%%" % (gas, ar5, share))
    print("  codes computed in more than one module:")
    multi = {}
    for r in rows:
        multi.setdefault(r["ipcc_code"], set()).add(r["module"])
    for code, modules in sorted(multi.items()):
        if len(modules) > 1:
            print("    %-10s %s" % (code, " + ".join(sorted(modules))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Measure a spatial re-base: what moved, by how much, and what did not.

Usage:  python3 scripts/measure_spatial_rebase.py <baseline git ref OR directory> <rebase name>
                [--append] [--adm1-may-move] [--modules a,b]

Compares five spatial products in the working tree against the same products at a
committed baseline (`git show <ref>:outputs/<file>`), and writes one row per
(re-base, product, scope) to outputs/pakemis_spatial_rebase_rc44.csv:

  adm2      pakemis_adm2_monthly_sector.csv, physical view, summed over months to
            (module, shape, gas): shapes moved, gross and net mass, the largest single
            shape delta and its name;
  fallback  pakemis_grid_fallbacks.csv: fallback mass by (module, scope) before and after;
  district  district_totals_2024.csv (the agriculture panel): districts moved, gross and
            net mass per category.

THE THREE ABOVE SEE THE REFERENCE YEAR ONLY, which is what rc42 needed and what rc44 cannot
use. Since rc43 the inventory publishes nine periods, and a re-base that moves FY2017-18 and
leaves FY2023-24 alone is INVISIBLE to all three - the exact case rc44's sequence is built
around, because seven of its commits move non-reference years. Two nine-year products are
therefore measured as well:

  adm2_year  pakemis_adm2_sector_by_year.csv, scoped (period, module): shapes whose annual
             mass moved, with the (period, module, province, gas) marginals asserted unchanged;
  adm1_year  pakemis_adm1_by_year.csv, scoped (period, module): provinces whose mass moved.

ADM1 IS AN INVARIANT FOR TWELVE OF THE FOURTEEN rc44 COMMITS AND THE DELIVERABLE FOR ONE.
Period-keying the provincial shares is supposed to move ADM1; everything else is supposed not
to. So provincial movement is REPORTED as data, and the assertion sits one level up, on the
per-(period, module, gas) national totals, which no spatial re-base may ever move. Pass
--adm1-may-move when the ADM1 movement is the point; without it, any provincial movement
exits 1 like the other invariants.

--adm1-may-move APPLIES AT EVERY GRAIN, which it did not until rc62. The flag reached only
the nine-year provincial product, so the two earlier steps - the ADM2 view's (module,
province, gas) marginals and the by-year view's (period, module, view, province, gas) ones -
went on failing a re-base whose declared purpose was to move exactly those. rc60's captive
year-keying was recorded with three pages of "INVARIANT BROKEN" beside rows that were
correct. The assertion does not disappear when the flag is given: it MOVES UP to the national
sum over provinces at the same grain, which no spatial re-base may move at any step. A guard
that fires on its own deliverable is not a guard, and one that is simply switched off is not
either.

--modules restricts WHICH ROWS ARE WRITTEN to the named modules, for the case where two
uncommitted re-bases share one baseline and each must be published under its own name. It
does NOT restrict the invariants: those still run over every module, so a re-base that moves
a module it did not name still exits 1 rather than being filtered out of its own report.

THE INVARIANTS ARE ASSERTED, NOT DESCRIBED. A spatial re-base moves mass BETWEEN shapes
inside a province and never across a province or into or out of the national total: the
per-(module, province, gas) sums of the ADM2 view and the per-(category) sums of the
district panel must agree with the baseline to 1e-6 Gg / 1e-4 Mt (five-decimal rows), and the script exits 1
if they do not. Mass is reported in CO2e Mt AR5 with the methane origin the module carries
(biogenic for agriculture, residential biomass and waste; fossil otherwise).

This is the rc40 G2 idiom ("37 of 126 shapes moved, gross 2.31 Mt, net +5e-9") made a
product, so every re-base of rc42 carries its own measured movement. Hand-run (needs git),
registered as a held product.
"""
import collections
import csv
import io
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.core.io import read_rows, write_table  # noqa: E402
from pkinv.paths import OUTPUTS, ROOT  # noqa: E402

OUT = asset_path(OUTPUTS, "pakemis_spatial_rebase_rc44.csv")
FIELDS = ("rebase", "product", "scope", "units_moved", "gross_Mt_AR5", "net_Mt_AR5",
          "max_unit_delta_Mt_AR5", "max_unit", "fallback_before_Mt_AR5", "fallback_after_Mt_AR5",
          "before_Mt_AR5", "after_Mt_AR5", "baseline_ref", "note")
# The two columns above `baseline_ref` are rc62's: they carry the BEFORE AND AFTER of a single
# unit, which the gross/net/max summary cannot. They are filled only on the per-province rows a
# declared provincial re-base writes (--adm1-may-move), because that is the one case where the
# unit that moved is the thing a reader has to be able to check, province by province and year by
# year, rather than a shape id they cannot look up. Every other row leaves them empty, and the
# fallback rows keep their own differently-named pair rather than being renamed underneath the
# rc42 file, which shares this schema and is frozen.
GWP_AR5 = {"CO2": 1.0, "CH4_fossil": 30.0, "CH4_biogenic": 28.0, "N2O": 265.0}
BIOGENIC_MODULES = ("agriculture", "residential", "waste")
TOL_GG = 1e-6
# the panel is written at five decimals of Mt, so a category total over ~120 rounded rows
# may differ by a few units in the fifth decimal without any mass having moved
TOL_CATEGORY_MT = 1e-4


def _baseline(ref, rel):
    """The baseline copy of one product, from a git ref OR from a preserved directory.

    THIS READ GIT ONLY, AND THAT WAS A LIMITATION OF THE TOOL MISTAKEN FOR A PROPERTY OF THE
    MEASUREMENT. Comparing the working tree against `HEAD` isolates a change only when that change
    is the sole uncommitted one. When two changes land in a session, the second cannot be measured
    against HEAD at all - HEAD reports both - and the conclusion drawn was that the measurement had
    to wait for a commit. It does not: two preserved states are comparable whether or not either is
    a commit, which is exactly what a reviewer pointed out. `ref` may now be a directory holding
    the baseline products, and a comparison built that way is a REPORTED result with its inputs
    named rather than a regeneration - the directory should carry its own digests and say so.
    """
    if os.path.isdir(ref):
        path = asset_path(ref, os.path.basename(rel))
        if not os.path.exists(path):
            raise SystemExit("baseline directory %s holds no %s" % (ref, os.path.basename(rel)))
        with open(path, encoding="utf-8") as handle:
            return [r for r in csv.DictReader(l for l in handle if not l.startswith("#"))]
    text = subprocess.check_output(["git", "show", "%s:%s" % (ref, rel)], cwd=ROOT).decode("utf-8")
    return [r for r in csv.DictReader(line for line in io.StringIO(text) if not line.startswith("#"))]


def _co2e_Mt(module, gas, gg):
    key = "CH4_biogenic" if (gas == "CH4" and module in BIOGENIC_MODULES) else ("CH4_fossil" if gas == "CH4" else gas)
    return gg * GWP_AR5[key] / 1000.0


def adm2_rows(rows):
    """{(module, shape_id, gas): Gg} over the physical view, all months."""
    out = collections.defaultdict(float)
    prov = collections.defaultdict(float)
    for r in rows:
        if r["spatial_view"] != "physical" or r["emissions_Gg"] == "":
            continue
        gg = float(r["emissions_Gg"])
        out[(r["module"], r["shape_id"], r["gas"])] += gg
        prov[(r["module"], r["province"], r["gas"])] += gg
    return out, prov


def compare_units(before, after, module_of, gas_of):
    """(units moved, gross, net, max delta, max unit) in Mt AR5 over a {unit: Gg} pair."""
    moved = gross = net = 0.0
    worst = (0.0, "")
    for key in set(before) | set(after):
        d = after.get(key, 0.0) - before.get(key, 0.0)
        if abs(d) <= TOL_GG:
            continue
        mt = _co2e_Mt(module_of(key), gas_of(key), d)
        moved += 1
        gross += abs(mt)
        net += mt
        if abs(mt) > abs(worst[0]):
            worst = (mt, "|".join(str(k) for k in key))
    return int(moved), gross, net, worst[0], worst[1]


def _module_of_scope(scope):
    """The module a written row is about. The five scopes are shaped differently - a bare
    module, "module/surface", "period|module", "period|module|view" and an agriculture
    category - so the module is whichever field names one."""
    parts = scope.replace("/", "|").split("|")
    return parts[1] if len(parts) > 1 and parts[0].startswith("FY") else parts[0]


def _marginal_problems(before, after, adm1_may_move, what, drop, label):
    """Province-grain marginals, asserted at the grain the caller is entitled to.

    Without --adm1-may-move the province marginal itself must hold, which is the ordinary
    case: a re-base moves mass between shapes INSIDE a province. With the flag, provincial
    movement is the deliverable, so the assertion climbs one level and is made on the sum
    over provinces (`drop` names the province position in the key) - the total that no
    spatial re-base may move whatever else it does.
    """
    problems = []
    if not adm1_may_move:
        for key in sorted(set(before) | set(after)):
            if abs(after.get(key, 0.0) - before.get(key, 0.0)) > TOL_GG:
                problems.append("%s moved: %s %.9f -> %.9f Gg"
                                % (what, label(key), before.get(key, 0.0), after.get(key, 0.0)))
        return problems
    def rolled(d):
        out = collections.defaultdict(float)
        for key, value in d.items():
            out[tuple(k for i, k in enumerate(key) if i not in drop)] += value
        return out
    b, a = rolled(before), rolled(after)
    # the roll-up is a sum over five provinces of numbers up to ~1e3 Gg, so it carries a few
    # ulps more float noise than a single cell does; the bound is loosened to match, and is
    # still eleven orders below the smallest movement any re-base has reported
    tol = TOL_GG * 1000.0
    for key in sorted(set(b) | set(a)):
        if abs(a.get(key, 0.0) - b.get(key, 0.0)) > tol:
            problems.append("%s: the NATIONAL sum over provinces moved, which no re-base may "
                            "do: %s %.9f -> %.9f Gg" % (what, label(key), b.get(key, 0.0), a.get(key, 0.0)))
    return problems


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    ref, name = argv[0], argv[1]
    append = "--append" in argv
    adm1_may_move = "--adm1-may-move" in argv
    modules_only = None
    for i, a in enumerate(argv):
        if a == "--modules" and i + 1 < len(argv):
            modules_only = {m.strip() for m in argv[i + 1].split(",") if m.strip()}
    rows = []
    problems = []

    # 1. the ADM2 view
    rel = "outputs/pakemis_adm2_monthly_sector.csv"
    b_units, b_prov = adm2_rows(_baseline(ref, rel))
    a_units, a_prov = adm2_rows(read_rows(asset_path(ROOT, rel)))
    for module in sorted({k[0] for k in set(b_units) | set(a_units)}):
        bu = {k: v for k, v in b_units.items() if k[0] == module}
        au = {k: v for k, v in a_units.items() if k[0] == module}
        moved, gross, net, worst, unit = compare_units(bu, au, lambda k: k[0], lambda k: k[2])
        if moved:
            rows.append({"rebase": name, "product": "pakemis_adm2_monthly_sector.csv", "scope": module,
                         "units_moved": moved, "gross_Mt_AR5": "%.6f" % gross, "net_Mt_AR5": "%.9f" % net,
                         "max_unit_delta_Mt_AR5": "%.6f" % worst, "max_unit": unit,
                         "fallback_before_Mt_AR5": "", "fallback_after_Mt_AR5": "",
                         "before_Mt_AR5": "", "after_Mt_AR5": "", "baseline_ref": ref,
                         "note": "shapes (module|shape_id|gas) whose physical-view mass moved; "
                                 "provincial marginals asserted unchanged"})
    problems += _marginal_problems(b_prov, a_prov, adm1_may_move, "ADM1 marginal",
                                   drop=(1,), label=lambda k: "|".join(k))

    # 2. the fallback ledger
    rel = "outputs/pakemis_grid_fallbacks.csv"
    def fallback_mass(rs):
        out = collections.defaultdict(float)
        for r in rs:
            out[(r["module"], r["scope"])] += float(r["affected_Mt_AR5"] or 0.0)
        return out
    fb, fa = fallback_mass(_baseline(ref, rel)), fallback_mass(read_rows(asset_path(ROOT, rel)))
    for key in sorted(set(fb) | set(fa)):
        if abs(fa.get(key, 0.0) - fb.get(key, 0.0)) > 1e-9:
            rows.append({"rebase": name, "product": "pakemis_grid_fallbacks.csv", "scope": "%s/%s" % key,
                         "units_moved": "", "gross_Mt_AR5": "", "net_Mt_AR5": "",
                         "max_unit_delta_Mt_AR5": "", "max_unit": "",
                         "fallback_before_Mt_AR5": "%.6f" % fb.get(key, 0.0),
                         "fallback_after_Mt_AR5": "%.6f" % fa.get(key, 0.0),
                         "before_Mt_AR5": "", "after_Mt_AR5": "", "baseline_ref": ref,
                         "note": "mass on a declared fallback surface, before and after"})

    # 3. the agriculture district panel
    rel = "outputs/district_totals_2024.csv"
    def panel(rs):
        out, cat = {}, collections.defaultdict(float)
        for r in rs:
            out[(r["category"], r["district"])] = float(r["co2e_Mt_AR5"]) * 1000.0   # Mt -> "Gg co2e" for the shared helper
            cat[r["category"]] += float(r["co2e_Mt_AR5"])
        return out, cat
    pb, cb = panel(_baseline(ref, rel))
    pa, ca = panel(read_rows(asset_path(ROOT, rel)))
    for category in sorted({k[0] for k in set(pb) | set(pa)}):
        bu = {k: v for k, v in pb.items() if k[0] == category}
        au = {k: v for k, v in pa.items() if k[0] == category}
        moved, gross, net, worst, unit = compare_units(bu, au, lambda k: "co2e", lambda k: "CO2")
        if moved:
            rows.append({"rebase": name, "product": "district_totals_2024.csv", "scope": category,
                         "units_moved": moved, "gross_Mt_AR5": "%.6f" % gross, "net_Mt_AR5": "%.9f" % net,
                         "max_unit_delta_Mt_AR5": "%.6f" % worst, "max_unit": unit,
                         "fallback_before_Mt_AR5": "", "fallback_after_Mt_AR5": "",
                         "before_Mt_AR5": "", "after_Mt_AR5": "", "baseline_ref": ref,
                         "note": "districts whose category mass moved; the category total asserted unchanged"})
    for category in set(cb) | set(ca):
        if abs(ca.get(category, 0.0) - cb.get(category, 0.0)) > TOL_CATEGORY_MT:
            problems.append("category total moved: %s %.9f -> %.9f Mt" % (category, cb.get(category, 0.0), ca.get(category, 0.0)))

    # 4. the nine-year district view, scoped (period, module)
    rel = "outputs/pakemis_adm2_sector_by_year.csv"
    def sector_year(rs):
        """EVERY VIEW, not just the physical one (rc45).

        This filtered `spatial_view != "physical"` and so measured 68 percent of the mass.
        Transport's entire 30.2 percent is booked in the accounting view and waste's 1.8 in
        origin, so every re-base this rig has reported - through rc44 and the first waves of
        rc45 - was silent about both. Worse, the ADM1 marginal assertion below was built from
        the same filtered rows, so it could not have caught a provincial move in a view it
        never read. (The cumulative rc44 result stands: the release-level diff against rc43
        keyed on spatial_view and covered all three.)

        The view is part of the scope now rather than a filter, so a module that moves in one
        view and not another says so instead of averaging the two into silence.
        """
        units, marg = {}, collections.defaultdict(float)
        for r in rs:
            if not r["emissions_Gg"]:
                continue
            gg = float(r["emissions_Gg"])
            key = (r["period_id"], r["module"], r["spatial_view"], r["shape_id"], r["gas"])
            units[key] = units.get(key, 0.0) + gg
            marg[(r["period_id"], r["module"], r["spatial_view"],
                  r["province"], r["gas"])] += gg
        return units, marg
    b_units, b_marg = sector_year(_baseline(ref, rel))
    a_units, a_marg = sector_year(read_rows(asset_path(ROOT, rel)))
    for scope in sorted({(k[0], k[1], k[2]) for k in set(b_units) | set(a_units)}):
        bu = {k: v for k, v in b_units.items() if (k[0], k[1], k[2]) == scope}
        au = {k: v for k, v in a_units.items() if (k[0], k[1], k[2]) == scope}
        moved, gross, net, worst, unit = compare_units(bu, au, lambda k: k[1], lambda k: k[4])
        if moved:
            rows.append({"rebase": name, "product": "pakemis_adm2_sector_by_year.csv",
                         "scope": "%s|%s|%s" % scope, "units_moved": moved,
                         "gross_Mt_AR5": "%.6f" % gross, "net_Mt_AR5": "%.9f" % net,
                         "max_unit_delta_Mt_AR5": "%.6f" % worst, "max_unit": unit,
                         "fallback_before_Mt_AR5": "", "fallback_after_Mt_AR5": "",
                         "before_Mt_AR5": "", "after_Mt_AR5": "", "baseline_ref": ref,
                         "note": "shapes whose annual physical-view mass moved in this period; "
                                 "the (period, module, province, gas) marginals are asserted "
                                 "unchanged"})
    problems += _marginal_problems(b_marg, a_marg, adm1_may_move, "by-year ADM1 marginal",
                                   drop=(3,), label=lambda k: "|".join(k))

    # 5. the nine-year provincial product. Provincial movement is DATA here, not a defect -
    # commit 9 of rc44 exists to produce it - so the assertion sits on the national total per
    # (period, module, gas), which no spatial re-base may move at any point in the sequence.
    rel = "outputs/pakemis_adm1_by_year.csv"
    def adm1_year(rs):
        units, nat = {}, collections.defaultdict(float)
        for r in rs:
            mt = float(r["co2e_Mt_AR5"])
            k = (r["period_id"], r["module"], r["province"])
            units[k] = units.get(k, 0.0) + mt * 1000.0        # Mt -> the helper's Gg-of-co2e
            nat[(r["period_id"], r["module"], r["gas"])] += mt
        return units, nat
    b_units, b_nat = adm1_year(_baseline(ref, rel))
    a_units, a_nat = adm1_year(read_rows(asset_path(ROOT, rel)))
    for scope in sorted({(k[0], k[1]) for k in set(b_units) | set(a_units)}):
        bu = {k: v for k, v in b_units.items() if (k[0], k[1]) == scope}
        au = {k: v for k, v in a_units.items() if (k[0], k[1]) == scope}
        moved, gross, net, worst, unit = compare_units(bu, au, lambda k: "co2e", lambda k: "CO2")
        if moved:
            rows.append({"rebase": name, "product": "pakemis_adm1_by_year.csv",
                         "scope": "%s|%s" % scope, "units_moved": moved,
                         "gross_Mt_AR5": "%.6f" % gross, "net_Mt_AR5": "%.9f" % net,
                         "max_unit_delta_Mt_AR5": "%.6f" % worst, "max_unit": unit,
                         "fallback_before_Mt_AR5": "", "fallback_after_Mt_AR5": "",
                         "before_Mt_AR5": "", "after_Mt_AR5": "", "baseline_ref": ref,
                         "note": "provinces whose mass moved in this period; the national total "
                                 "per (period, module, gas) is asserted unchanged"})
            if not adm1_may_move:
                problems.append(
                    "ADM1 moved in %s|%s (%d provinces, gross %.6f Mt) and --adm1-may-move "
                    "was not given" % (scope[0], scope[1], moved, gross))
            else:
                # A DECLARED re-base owes its reader the province, not a summary of provinces.
                # The summary row above says five moved and names the largest; these say which
                # five and to what, so the claim "no national total moves" can be added up by
                # hand from the published file.
                for key in sorted(set(bu) | set(au)):
                    b, a = bu.get(key, 0.0) / 1000.0, au.get(key, 0.0) / 1000.0
                    if abs(a - b) <= TOL_GG:
                        continue
                    rows.append({"rebase": name, "product": "pakemis_adm1_by_year.csv",
                                 "scope": "%s|%s|%s" % key, "units_moved": 1,
                                 "gross_Mt_AR5": "%.6f" % abs(a - b), "net_Mt_AR5": "%.9f" % (a - b),
                                 "max_unit_delta_Mt_AR5": "", "max_unit": "",
                                 "fallback_before_Mt_AR5": "", "fallback_after_Mt_AR5": "",
                                 "before_Mt_AR5": "%.6f" % b, "after_Mt_AR5": "%.6f" % a,
                                 "baseline_ref": ref,
                                 "note": "this province's own mass before and after the declared "
                                         "re-base; the nine provinces of a period sum to the same "
                                         "national total on both sides"})
    for key in set(b_nat) | set(a_nat):
        if abs(a_nat.get(key, 0.0) - b_nat.get(key, 0.0)) > TOL_CATEGORY_MT:
            problems.append("national total moved: %s %.9f -> %.9f Mt"
                            % ("|".join(key), b_nat.get(key, 0.0), a_nat.get(key, 0.0)))

    if modules_only is not None:
        rows = [r for r in rows if _module_of_scope(r["scope"]) in modules_only]
    existing = []
    if append and os.path.exists(OUT):
        existing = [r for r in read_rows(OUT) if r["rebase"] != name]
    write_table(OUT, list(FIELDS), existing + rows, banner=(
        "SPATIAL RE-BASE MEASUREMENTS (rc44): what each named re-base moved between shapes,",
        "against the committed baseline named in baseline_ref; ADM1 marginals and category",
        "totals are asserted unchanged by scripts/measure_spatial_rebase.py, which exits 1 otherwise.",
        "CO2e Mt AR5 with the module's methane origin (biogenic for agriculture, residential, waste).",
    ))
    print("spatial re-base %r against %s -> %s (%d rows)" % (name, ref, os.path.relpath(OUT, ROOT), len(rows)))
    for r in rows:
        print("  %-36s %-32s moved %-4s gross %s net %s max %s (%s)" % (
            r["product"], r["scope"], r["units_moved"], r["gross_Mt_AR5"], r["net_Mt_AR5"],
            r["max_unit_delta_Mt_AR5"], r["max_unit"][:40]))
    for p in problems:
        print("  INVARIANT BROKEN: %s" % p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

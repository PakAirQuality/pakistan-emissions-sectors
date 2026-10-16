"""One walk per sector: the published source, the corrections, what the engine used, the result.

WHY. Every step of this chain is already computed and none of it is assembled. A reader who
wants to know how 20.3 million registered vehicles become 41.93 Mt CO2e has to find
transport_fuel_bridge_2024.csv, transport_fuel_ledger_2024.csv, transport_fuel_2024.csv and
transport_totals_2024.csv, know that those four are the ones that matter out of twenty-three
transport outputs, and know the order to read them in. Nothing said so. The verification bundle
shipped all twenty-three and made that worse, not better: more files, same silence about which
four are the spine.

WHAT THIS IS. `outputs/<sector>_derivation_chain.csv` - long format, sorted, walkable top to
bottom, in four stages:

  1_source      the numbers as the publisher printed them, before any inventory decision
  3_correction  what was taken off, added, partitioned or re-anchored, and why
  2_used        what the engine finally integrated
  4_final       the emissions

(The stage LABELS are numbered by the order a reader meets them in the source-to-result story,
which is 1, 3, 2, 4: corrections happen to the source and produce the used value. The file is
sorted by the registry's own `order`, not by the label, so the walk reads correctly.)

WHAT THIS IS NOT. It computes nothing. Every value is read from a file the build already wrote
and carries `evidence_file` naming it, so a chain row and its source agree by construction and a
disagreement is impossible rather than merely unlikely. Where a sector has no artifact for a
stage, the registry says `declared_absent` and the chain says so in a row - it does not quietly
skip the stage, because a chain with a missing link that looks complete is worse than no chain.

THE REGISTRY is data/verification_chain.csv. Two recipes, because the artifacts have two shapes:

  ledger      long already - one chain row per source row (transport's bridge, waste's ledger)
  comparison  wide - one chain row per (row, declared value column), which is how a
              side-by-side reads as a walk (power's boundary audit, railways' reconciliation)

Usage:  python3 -m pkinv.report.derivation_chain [--check] [--out DIR]
Exit:   1 if a declared source file or column is missing
"""

from pkinv.assets import asset_path
import argparse
import collections
import os
import sys

from pkinv.activity.store import read_rows
from pkinv.core.io import write_table
from pkinv.paths import DATA, OUTPUTS, ROOT

REGISTRY = asset_path(DATA, "verification_chain.csv")

FIELDS = ("stage", "step", "section", "subject", "item", "kind", "value", "unit",
          "evidence_file", "note")

STAGES = ("1_source", "3_correction", "2_used", "4_final")
RECIPES = ("ledger", "comparison", "absent")

BANNER = (
    "THE DERIVATION CHAIN: the published source, the corrections, what the engine used,",
    "and the result - one walk, in the order a reader meets it. Every value is READ from",
    "the file named in evidence_file; nothing here is recomputed. A stage a sector has no",
    "artifact for is declared absent in a row rather than skipped.",
    "Registry: data/verification_chain.csv. See pkinv.report.derivation_chain.",
)


def registry(path=REGISTRY):
    """{sector: [row]} in declared order."""
    out = collections.defaultdict(list)
    for row in read_rows(path):
        out[row["sector"]].append(row)
    for sector in out:
        out[sector].sort(key=lambda r: int(r["order"]))
    return out


def _numeric(text):
    try:
        return float(str(text).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _filtered(rows, spec):
    """Apply the registry's optional single-column filter. MAX takes the latest value."""
    column = spec.get("filter_column") or ""
    if not column:
        return rows
    value = spec["filter_value"]
    if value == "MAX":
        present = [r[column] for r in rows if r.get(column, "") != ""]
        if not present:
            return []
        value = max(present, key=lambda v: (_numeric(v) if _numeric(v) is not None else 0, v))
    return [r for r in rows if r.get(column, "") == value]


def _require(rows, spec, columns):
    """The registry names a column the file does not have -> say which, do not guess."""
    if not rows:
        return ["%s is empty" % spec["source_file"]]
    held = set(rows[0])
    return ["%s has no column %r" % (spec["source_file"], c)
            for c in columns if c and c not in held]


def value_columns(spec):
    """[(column, unit)] - the value column, or a pipe-separated fallback chain.

    ONE FILE CAN CARRY TWO UNITS. transport's bridge prints liquids in `kt` and CNG in `TJ`,
    because a gas has no tonnage row; declaring `kt` alone rendered every CNG step blank - a
    correction that silently showed nothing, which is the failure this whole file exists to
    stop. `kt|TJ` takes the first column with a value and reports the unit paired with it.
    """
    columns = [c.strip() for c in spec["value_column"].split("|") if c.strip()]
    units = [u.strip() for u in spec["unit"].split("|")]
    return [(c, units[i] if i < len(units) else units[-1]) for i, c in enumerate(columns)]


def _value_of(row, pairs, unit_column):
    """(value, unit) - the first declared column this row actually fills."""
    for column, unit in pairs:
        if row.get(column, "") != "":
            return row[column], (row.get(unit_column, "") or unit if unit_column else unit)
    return "", (row.get(unit_column, "") or pairs[-1][1] if unit_column else pairs[-1][1])


def _chain_row(spec, subject, item, kind, value, unit, note):
    return {"stage": spec["stage"], "step": int(spec["order"]), "section": spec["title"],
            "subject": subject, "item": item, "kind": kind, "value": value, "unit": unit,
            "evidence_file": spec["source_file"], "note": note}


def build_section(spec, root=ROOT):
    """([chain row], [problem]) for one registry row."""
    if spec["status"] == "declared_absent":
        return [{"stage": spec["stage"], "step": int(spec["order"]), "section": spec["title"],
                 "subject": "", "item": "(declared absent)", "kind": "declared_absent",
                 "value": "", "unit": "", "evidence_file": "", "note": spec["note"]}], []

    path = asset_path(root, spec["source_file"])
    if not os.path.isfile(path):
        return [], ["%s does not exist" % spec["source_file"]]
    rows = _filtered(read_rows(path), spec)

    subject_c = spec.get("subject_column") or ""
    item_c = spec["item_column"]
    kind_c = spec.get("kind_column") or ""
    note_c = spec.get("note_column") or ""
    unit_c = spec.get("unit_column") or ""

    if spec["recipe"] == "ledger":
        pairs = value_columns(spec)
        wanted = [subject_c, item_c, kind_c, note_c, unit_c] + [c for c, _u in pairs]
        problems = _require(rows, spec, wanted)
        if problems:
            return [], problems
        out = []
        for r in rows:
            value, unit = _value_of(r, pairs, unit_c)
            out.append(_chain_row(spec, r.get(subject_c, ""), r[item_c],
                                  r.get(kind_c, "") or spec.get("kind_default", ""),
                                  value, unit, r.get(note_c, "")))
        return out, []

    # comparison: a side-by-side table read as a walk, one row per declared value column
    columns = [c.strip() for c in spec["value_columns"].split(";") if c.strip()]
    problems = _require(rows, spec, [subject_c, item_c, note_c] + columns)
    if problems:
        return [], problems
    out = []
    for r in rows:
        for column in columns:
            out.append(_chain_row(spec, r[item_c], column, "reading", r.get(column, ""),
                                  spec["unit"], r.get(note_c, "")))
    return out, []


def build(sector, reg=None, root=ROOT):
    """([chain row] in reading order, [problem]) for one sector."""
    reg = reg or registry()
    rows, problems = [], []
    for spec in reg.get(sector, ()):
        made, trouble = build_section(spec, root=root)
        rows.extend(made)
        problems.extend(trouble)
    return rows, problems


def sectors(reg=None):
    return sorted(reg or registry())


# ------------------------------------------------------------------ the activity x factor side

LEDGER_FIELDS = ("source_stream_id", "category", "subitem", "gas", "method_id", "equation",
                 "activity", "conversion", "factor", "unresolved_ids",
                 "emissions_Gg", "native_unit", "co2e_Mt_AR5", "reproduces", "reproduction_note")

LEDGER_BANNER = (
    "WHAT WENT IN AND WHAT CAME OUT, per source stream: the activity quantities, the",
    "conversions, the emission factors and the published emission on ONE row.",
    "",
    "Outside fugitives - whose segment ledger has always carried activity x factor x",
    "structural multiplier - nothing in this release put those numbers beside each other.",
    "fact_annual carries the emission and the method_id but neither of the two numbers that",
    "were multiplied, and every *_by_stream_*.csv carries only the output. This closes that.",
    "",
    "IT IS NOT AN IDENTITY. `reproduces` is yes ONLY where one activity times one factor",
    "lands on the published emission within tolerance. Most streams are no or not_attempted,",
    "because the engines apply steps the parameter ids do not carry - a partition, a share, a",
    "survival curve, a first-order decay. That is the honest state of the join and the reason",
    "is on the row; a yes that had not been checked would be worth less than nothing.",
    "",
    "Written by pkinv.report.derivation_chain; parameter values resolve through",
    "core.parameters.registry() by dependency_group, and factor ids through",
    "data/emission_factors.csv.",
)

REFERENCE_PERIOD = "FY2023-24"
REFERENCE_CONFIGURATION = "S_TAN"
TOLERANCE = 0.005          # half a percent, against a published Gg


def _parameter_values():
    """({dependency_group: [(id, value, unit)]}, {ef_id: (value, unit)})."""
    from pkinv.core import parameters
    by_group = collections.defaultdict(list)
    for p in parameters.registry():
        group = (p.get("dependency_group") or "").strip()
        if group:
            by_group[group].append((p["parameter_id"], p.get("value", ""), p.get("unit", "")))
    factors = {}
    for r in read_rows(asset_path(DATA, "emission_factors.csv")):
        factors[r["ef_id"]] = (r.get("value", ""), r.get("unit", ""))
    return by_group, factors


def _resolve(ids, by_group, factors):
    """('id=value unit; ...', [unresolved id], [(value, unit)]) for one ';'-joined id field."""
    shown, missing, numbers = [], [], []
    for raw in (ids or "").split(";"):
        group = raw.strip()
        if not group or group in ("none", "unresolved", "not-applicable"):
            continue
        # EVERY MEMBER, not the first. A dependency group can hold more than one number -
        # 1a3b_diesel_control holds the calorific value AND the control total - and taking
        # by_group[group][0] published "43.0 TJ/Gg" as transport's diesel ACTIVITY while
        # silently dropping the 5,551.442 kt/yr that is the activity. 56 groups have more
        # than one member, so that was not a corner case.
        members = []
        if group in by_group:
            members = [(pid, v, u) for pid, v, u in by_group[group]]
        elif group.startswith("ef:") and group[3:] in factors:
            members = [(group[3:],) + factors[group[3:]]]
        elif group in factors:
            members = [(group,) + factors[group]]
        if not members:
            missing.append(group)
            continue
        for pid, value, unit in members:
            shown.append("%s=%s%s" % (pid, value, (" " + unit) if unit else ""))
            numbers.append((value, unit))
    return "; ".join(shown), missing, numbers


def activity_factor_rows(sector):
    """One row per source stream of this sector, inputs beside output."""
    from pkinv.report import method_registry as methods
    by_group, factors = _parameter_values()
    streams = {r["source_stream_id"]: r for r in
               read_rows(asset_path(OUTPUTS, "semantic", "dim_stream.csv"))
               if r["module"] == sector}
    facts = [r for r in read_rows(asset_path(OUTPUTS, "semantic", "fact_annual.csv"))
             if r["sector_id"] == sector and r["period_id"] == REFERENCE_PERIOD
             and r["configuration_id"] == REFERENCE_CONFIGURATION]
    rules = methods.rules() if hasattr(methods, "rules") else None

    out = []
    for fact in facts:
        stream = streams.get(fact["source_stream_id"], {})
        activity, miss_a, nums_a = _resolve(stream.get("activity_parameter_ids"), by_group, factors)
        conversion, miss_c, _ = _resolve(stream.get("conversion_parameter_ids"), by_group, factors)
        factor, miss_f, nums_f = _resolve(stream.get("factor_parameter_ids"), by_group, factors)
        try:
            method, _model = methods.lookup(fact["category"], fact["subitem"],
                                            sector=sector, gas=fact["gas"])
        except Exception:
            method = fact.get("method_id", "")
        equation = ""
        for row in read_rows(asset_path(DATA, "method_registry.csv")):
            if row["method_id"] == (fact.get("method_id") or method):
                equation = row["equation"]
                break

        # THE CHECK IS DELIBERATELY CONSERVATIVE. It fires only where one DISTINCT activity
        # value meets one DISTINCT factor value, so that the product it tests is the only
        # product those parameters can form. Where a bucket holds two unlike numbers - a
        # control total and a calorific value both sitting in `activity` - there is more than
        # one candidate product and searching them for whichever lands nearest the published
        # mass would manufacture agreement rather than test it.
        published = _numeric(fact.get("native_mass"))
        distinct_a = sorted({v for v, _u in nums_a if _numeric(v) is not None}, key=str)
        distinct_f = sorted({v for v, _u in nums_f if _numeric(v) is not None}, key=str)
        reproduces, why = "not_attempted", ""
        if len(distinct_a) == 1 and len(distinct_f) == 1 and published:
            a, f = _numeric(distinct_a[0]), _numeric(distinct_f[0])
            for scale, label in ((1.0, "x1"), (1e-3, "x1e-3"), (1e-6, "x1e-6")):
                if abs(a * f * scale - published) <= TOLERANCE * abs(published):
                    reproduces = "yes"
                    why = "%s x %s %s reproduces the published mass" % (a, f, label)
                    break
            else:
                reproduces = "no"
                why = ("one activity value and one factor value resolve and their product is "
                       "not the published mass: the engine applies a step the parameter ids "
                       "do not carry")
        else:
            why = ("%d distinct activity and %d distinct factor values resolve; more than one "
                   "product is definable, so no identity is claimed"
                   % (len(distinct_a), len(distinct_f)))

        out.append({
            "source_stream_id": fact["source_stream_id"], "category": fact["category"],
            "subitem": fact["subitem"], "gas": fact["gas"],
            "method_id": fact.get("method_id", "") or method, "equation": equation,
            "activity": activity, "conversion": conversion, "factor": factor,
            "unresolved_ids": "; ".join(miss_a + miss_c + miss_f),
            "emissions_Gg": fact.get("native_mass", ""), "native_unit": fact.get("native_unit", ""),
            "co2e_Mt_AR5": fact.get("co2e_Mt_AR5", ""),
            "reproduces": reproduces, "reproduction_note": why})
    out.sort(key=lambda r: (r["category"], r["subitem"], r["gas"]))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="build every chain and report, writing nothing")
    parser.add_argument("--out", default=OUTPUTS)
    parser.add_argument("--sectors", default="")
    args = parser.parse_args(argv)

    reg = registry()
    wanted = tuple(s.strip() for s in args.sectors.split(",") if s.strip()) or tuple(sectors(reg))
    problems, written = [], 0
    for sector in wanted:
        rows, trouble = build(sector, reg)
        problems.extend(trouble)
        stages = collections.Counter(r["stage"] for r in rows)
        absent = sum(1 for r in rows if r["kind"] == "declared_absent")
        print("%-12s %4d rows  %s%s"
              % (sector, len(rows),
                 " ".join("%s=%d" % (s.split("_")[1][:3], stages.get(s, 0)) for s in STAGES),
                 "   %d DECLARED ABSENT" % absent if absent else ""))
        ledger = activity_factor_rows(sector)
        verdicts = collections.Counter(r["reproduces"] for r in ledger)
        print("%12s %4d streams  %s" % ("", len(ledger),
              " ".join("%s=%d" % (v, verdicts.get(v, 0))
                       for v in ("yes", "no", "not_attempted"))))
        if not args.check:
            os.makedirs(args.out, exist_ok=True)
            write_table(asset_path(args.out, "%s_derivation_chain.csv" % sector),
                        list(FIELDS), rows, banner=BANNER)
            write_table(asset_path(args.out, "%s_activity_factor_ledger.csv" % sector),
                        list(LEDGER_FIELDS), ledger, banner=LEDGER_BANNER)
            written += 2
    if written:
        print("wrote %d files to %s" % (written, os.path.relpath(args.out, ROOT)))
    if problems:
        print("\nPROBLEMS (a declared source or column is missing):")
        for p in problems:
            print("  " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

"""Monthly emissions over the supported fiscal panel, closing in native gas mass.

The atomic annual product supplies each component-year's magnitude; the temporal
profile register supplies its twelve monthly weights. The product is their
multiplication. Every component-year must close to its compatible annual native
mass and GWP aggregate before records are written. Periods and configurations are
read from their maintained registers rather than inferred from the latest year.

Current common-core rows contain native gas masses. The explicit closure_basis
field also supports legacy CO2e-only records without representing a missing native
mass as zero. A sector-year declared absent has no estimated monthly records; it
is never manufactured as twelve zero emissions.

Source identifiers, timing targets, evidence classes, borrowed-year labels and
profile status accompany every component-month. These describe the allocation's
support and do not turn a proxy shape into observed emission timing.

Usage: python3 -m pkinv.report.monthly_all_years
Writes the supported-period monthly product, its configuration expansion and the
monthly evidence register under outputs/.
"""
from __future__ import annotations

from pkinv.assets import asset_path

import collections
import csv
import os

from pkinv.paths import OUTPUTS
from pkinv.report import temporal_profiles
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

OUT = asset_path(OUTPUTS, "pakemis_monthly_fy2015_16_fy2024_25.csv")
EVIDENCE_OUT = asset_path(OUTPUTS, "pakemis_monthly_evidence.csv")
CONFIGURATIONS_OUT = asset_path(OUTPUTS, "pakemis_ghg_configuration_monthly.csv")

FIELDS = ("period_id", "month", "component_id", "sector_id", "reporting_sector",
          "ipcc_code", "category",
          "subitem", "gas", "gas_origin", "configuration_id", "geography_id",
          "emission_native_mass", "native_unit", "co2e_Mt_AR5", "co2e_Mt_AR6",
          "share", "closure_basis", "temporal_evidence_class", "timing_target",
          "temporal_status",
          "profile_id", "source_id", "borrowed_from_year", "special_period_flag",
          "release_id")

# The closure tolerance, relative, on native mass. The share is a pure redistribution, so
# the only error available is floating-point summation over twelve terms.
TOL = 1e-9


def _atom():
    return temporal_profiles._atom_rows()


def _profiles():
    """Read the preceding task's published profiles, without rebuilding sector engines."""
    out = collections.defaultdict(dict)
    for row in read_rows(temporal_profiles.OUT):
        key = (row["component_id"], row["fiscal_year"])
        if row["month"] in out[key]:
            raise ValueError("duplicate temporal profile for %s in %s, month %s"
                             % (*key, row["month"]))
        out[key][row["month"]] = row
    return out


def _months_table():
    from pkinv.report import months as month_registry
    return {r["month_id"]: r for r in month_registry.rows()}


def build(atom=None):
    atom = _atom() if atom is None else atom
    profiles = _profiles()
    calendar = _months_table()
    rows = []
    for component in atom:
        key = (component["component_id"], component["period_id"])
        shape = profiles.get(key)
        if not shape:
            raise KeyError("no temporal profile for %s in %s - a live annual row with no "
                           "timing is a silent hole, not a flat month" % key)
        raw_native = component["emission_native_mass"]
        native = float(raw_native) if raw_native else None
        ar5 = float(component["co2e_Mt_AR5"])
        ar6 = float(component["co2e_Mt_AR6"] or 0.0)
        for month in sorted(shape):
            profile = shape[month]
            share = float(profile["weight"])
            rows.append({
                "period_id": component["period_id"],
                "month": month,
                "component_id": component["component_id"],
                "sector_id": component["sector_id"],
                # copied from the atom, never re-resolved: one registry lookup per stream
                "reporting_sector": component["reporting_sector"],
                "ipcc_code": component["ipcc_code"],
                "category": component["category"],
                "subitem": component["subitem"],
                "gas": component["gas"],
                "gas_origin": component["gas_origin"],
                "configuration_id": component["configuration_id"],
                "geography_id": component["geography_id"],
                "emission_native_mass": ("" if native is None else native * share),
                "native_unit": component["native_unit"],
                "co2e_Mt_AR5": ar5 * share,
                "co2e_Mt_AR6": ar6 * share,
                "share": share,
                "closure_basis": "co2e_AR5" if native is None else "native_mass",
                "temporal_evidence_class": profile["temporal_evidence_class"],
                "timing_target": profile["timing_target"],
                "temporal_status": profile["temporal_status"],
                "profile_id": profile["profile_id"],
                "source_id": profile["source_id"],
                "borrowed_from_year": profile["borrowed_from_year"],
                "special_period_flag": calendar[month]["special_period_flag"],
                "release_id": component["release_id"],
            })
    check(rows, atom)
    return rows


def check(rows, atom):
    """Twelve months sum to the annual row, per component-year. Raises.

    On native gas mass where the annual row has one, and on AR5 CO2e always. The two are
    not redundant: native mass is the stronger check and cannot be satisfied by two GWPs
    cancelling, and CO2e is the only one available for the coarse agriculture history.
    """
    native = collections.defaultdict(float)
    co2e = collections.defaultdict(float)
    counted = collections.Counter()
    for row in rows:
        key = (row["component_id"], row["period_id"])
        if row["emission_native_mass"] != "":
            native[key] += row["emission_native_mass"]
        co2e[key] += row["co2e_Mt_AR5"]
        counted[key] += 1

    problems = []
    for component in atom:
        key = (component["component_id"], component["period_id"])
        if counted[key] != 12:
            problems.append("%s %s: %d months, not 12" % (key + (counted[key],)))
            continue
        checks = [("co2e AR5", float(component["co2e_Mt_AR5"]), co2e.get(key))]
        if component["emission_native_mass"]:
            checks.append(("native mass", float(component["emission_native_mass"]),
                           native.get(key)))
        for what, want, got in checks:
            if got is None:
                problems.append("%s %s: no monthly rows" % key)
            elif abs(got - want) > max(TOL * abs(want), TOL):
                problems.append("%s %s: months sum to %.12g on %s, annual row is %.12g"
                                % (key + (got, what, want)))
    live = {(c["component_id"], c["period_id"]) for c in atom}
    for key in set(co2e) - live:
        problems.append("%s %s: monthly rows with no live annual row" % key)
    if problems:
        raise AssertionError("the monthly layer does not close:\n  %s"
                             % "\n  ".join(problems[:20]))
    return True


def evidence_table(rows):
    """Class shares BY MASS, per fiscal year and nationally.

    By mass and not by row: a registry counted by rows says the inventory is mostly TE4
    because livestock has many small components, and says nothing about how much of the
    inventory's WEIGHT is timed by evidence, which is the question.
    """
    by_year = collections.defaultdict(lambda: collections.defaultdict(float))
    for row in rows:
        by_year[row["period_id"]][row["temporal_evidence_class"]] += row["co2e_Mt_AR5"]
        by_year["NATIONAL"][row["temporal_evidence_class"]] += row["co2e_Mt_AR5"]
    out = []
    for scope in sorted(by_year):
        total = sum(by_year[scope].values())
        for cls in sorted(by_year[scope]):
            out.append({"scope": scope, "temporal_evidence_class": cls,
                        "co2e_Mt_AR5": round(by_year[scope][cls], 5),
                        "share_of_scope_pct": round(100.0 * by_year[scope][cls] / total, 2)})
    return out


def main():
    rows = build()
    from pkinv.core import configurations as conf
    from pkinv.report.atomic_annual import CONFIGURATIONS_OUT as CONFIGURED_ATOMS
    atoms = [r for r in read_rows(CONFIGURED_ATOMS) if r["co2e_Mt_AR5"] != ""]
    configured = [row for configuration in conf.ALL
                  for row in build([r for r in atoms if r["configuration_id"] == configuration])]
    write_table(CONFIGURATIONS_OUT, FIELDS, configured)
    os.makedirs(OUTPUTS, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (round(v, 12) if isinstance(v, float) else v)
                             for k, v in row.items()})
    table = evidence_table(rows)
    write_table(EVIDENCE_OUT, ("scope", "temporal_evidence_class",
                                                    "co2e_Mt_AR5", "share_of_scope_pct"), table)

    print("monthly layer -> %s" % OUT)
    natively = len({(r["component_id"], r["period_id"]) for r in rows
                    if r["closure_basis"] == "native_mass"})
    print("  %d rows, %d months, %d component-years; %d close in native gas mass and the "
          "rest on AR5 CO2e, at %g"
          % (len(rows), len({r["month"] for r in rows}),
             len({(r["component_id"], r["period_id"]) for r in rows}), natively, TOL))
    national = {r["temporal_evidence_class"]: r["share_of_scope_pct"]
                for r in table if r["scope"] == "NATIONAL"}
    print("  national mass by timing evidence: %s"
          % ", ".join("%s %.1f%%" % (c, national.get(c, 0.0))
                      for c in ("TE1", "TE2", "TE3", "TE4")))
    per_year = collections.defaultdict(float)
    totals = collections.defaultdict(float)
    for row in rows:
        totals[row["period_id"]] += row["co2e_Mt_AR5"]
        if row["temporal_evidence_class"] != "TE4":
            per_year[row["period_id"]] += row["co2e_Mt_AR5"]
    for year in sorted(totals):
        print("  %s  %7.2f Mt, %5.1f%% of it timed by evidence"
              % (year, totals[year], 100.0 * per_year[year] / totals[year]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

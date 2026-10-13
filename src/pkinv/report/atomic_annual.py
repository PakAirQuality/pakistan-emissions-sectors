"""The atomic annual table: one row per emission stream per period, and nothing aggregated.

WHAT THIS IS FOR. Every additive product in this repository has, until now, mixed grains.
`national_all_sectors.csv` carries a `TOTAL` row in the same `sector` column as its ten
parts; `pakemis_national_series.csv` carries nine `COVERED_TOTAL` rows beside its sector
rows. Both were correct only because every reader remembered to filter a magic string out of
a free-text column, and about a hundred and sixty call sites do exactly that by hand. This
table holds the parts alone. Aggregates are derived from it, never stored beside it, so a
naive sum is right by construction rather than by discipline.

The two legacy files keep their shape: the TOTAL row is anchored in far too many readers to
move, and moving it would move no number. What they gained is a typed `row_kind` column, so
the kind of a row can be ASKED rather than pattern-matched out of its name, and a test that
the atom reproduces both of them cell for cell - which is what makes them derivable from
this table rather than merely in agreement with it this week.

WHAT THIS TABLE IS NOT, YET. It is not the source of truth. It READS
outputs/pakemis_national_series.csv below to assemble its sector-year rows, so the chain
still runs sectors -> series -> atom rather than sectors -> atom -> series. Inverting it is
a declared, deferred debt with its own section in docs/ROADMAP_STATE.md: what it needs, in
what order, and the equivalence tests that have to keep passing through the move. Do not
build anything on the assumption that this file is upstream of the rollups.

THE KEY IS FIVE-PART: period_id, component_id, gas, configuration_id, geography_id. Two of
those five are honest placeholders today and say so on every row rather than in a footnote:

  configuration_id  is REF_2023_24 throughout. Configurations exist as national delta
                    scalars, not as re-runs, so there is nothing per-component to record
                    for an alternative. Fugitives is the exception that proves it is
                    unbuilt rather than impossible - its engine takes a year and a scenario
                    together and twelve of thirteen scenarios run all nine years - but the
                    per-sector scenario RUNNERS write their alternatives for the reference
                    year alone.
  geography_id      is PK, the national total. The ADM2 machinery exists and is stable
                    (data/adm2_canonical.csv, 152 ids) but is applied at module grain in
                    the grid cube, never at component grain. Putting a district key here
                    would claim a resolution the allocation does not have.

Both columns are present, populated and constant. A column that exists and holds one value
is a declared limitation; a column that does not exist is a silence, and this project has
paid for enough of those.

SPARSITY IS A ROW, NOT A HOLE. Where a sector cannot be built for a period the table still
carries the cell, with `estimate_status` naming why. The nine-year series declares eleven
such sector-years, and those absences are themselves asserted rather than measured - see
the declared-absence-untested gap - so this table reports the declaration and does not
launder it into evidence.

WHAT IT DOES NOT RECOMPUTE. Values come from the sector engines through
`national_series`, the same path the annual product uses. This is a re-expression, not a
second arithmetic: a second path to the same quantity is a second vintage waiting to
disagree, which is why component identity moved into the schema in v3 rather than being
synthesised here.

Usage:  python3 -m pkinv.report.atomic_annual
Writes: outputs/pakemis_atomic_annual.csv
        outputs/pakemis_atomic_annual_aggregates.csv
"""
from __future__ import annotations

from pkinv.assets import asset_path

import collections
import csv
import os

from pkinv.paths import OUTPUTS
from pkinv.report import annual_product, method_registry, national_series

OUT = asset_path(OUTPUTS, "pakemis_atomic_annual.csv")
AGGREGATES = asset_path(OUTPUTS, "pakemis_atomic_annual_aggregates.csv")

NATIONAL_GEOGRAPHY = "PK"
from pkinv.core import configurations as _conf
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table
REFERENCE_CONFIGURATION = _conf.REFERENCE
# The period every coverage fraction is measured against, and the only period in which
# "national" and "every sector" are the same statement.
REFERENCE_PERIOD = "FY2023-24"
UNRESOLVED = "unresolved"

FIELDS = ("period_id", "component_id", "gas", "configuration_id", "geography_id",
          "sector_id", "reporting_sector", "ipcc_code", "category", "subitem", "gas_origin",
          "estimate_status", "activity_status", "evidence_class", "method_id",
          "uncertainty_model_id", "emission_native_mass", "native_unit",
          "co2e_Mt_AR5", "co2e_Mt_AR6", "source_stream_id", "release_id")

# Aggregation levels the derived table publishes. Each is a strict roll-up of the atom;
# none is ever written into the atomic file.
LEVELS = (("sector", ("period_id", "sector_id")),
          ("category_gas", ("period_id", "sector_id", "category", "gas")),
          ("national", ("period_id",)))


def _component_code():
    """(category, subitem, gas) -> IPCC 2006 code. Report-layer join; core may not read
    completeness.

    Keyed on the component, not the engine category: two categories split under IPCC 2006 and
    the code is a property of the row, not of its label. The previous version of this helper
    returned a dict and the call site did `codes.get(category, "unresolved")`, so a category
    the matrix did not cover shipped the literal string "unresolved" in the code column of
    every product downstream. There is no default now - a miss raises.
    """
    from pkinv.report import category_ledger
    return category_ledger.component_code


def build():
    import pkinv
    component_code = _component_code()
    series = {(r["sector"], int(r["fiscal_end_year"])): r
              for r in _read("pakemis_national_series.csv")}
    periods = {int(r["fiscal_end_year"]): r["period_id"]
               for r in _read_data("periods.csv")}

    rows = []
    rules = method_registry.registry()
    context = annual_product.build_context()
    # The reporting-sector axis (data/stream_reporting_sector.csv): where IPCC 2006 files
    # the stream, in the module vocabulary, beside sector_id (the module that computed it).
    # Every priced row resolves through the registry - a category with no row RAISES - and
    # a declared-absent sector-period carries its own sector_id, there being no stream to
    # file elsewhere.
    from pkinv.report import reporting_sectors
    reporting_rows = reporting_sectors.rows()
    for fy_end, period_id in sorted(periods.items()):
        for sector_row in sorted(series):
            name, year = sector_row
            if year != fy_end or series[sector_row]["row_kind"] != "sector":
                continue
            s = series[sector_row]
            base = {"period_id": period_id, "configuration_id": REFERENCE_CONFIGURATION,
                    "geography_id": NATIONAL_GEOGRAPHY, "sector_id": name,
                    "release_id": pkinv.__version__,
                    # rc39 A7: resolved per atom below from data/method_registry.csv. These
                    # two stayed on the literal for every row in the product because the base
                    # dict set them and nothing downstream ever revisited it - the equations
                    # were in the modules' docstrings the whole time.
                    "method_id": UNRESOLVED, "uncertainty_model_id": UNRESOLVED,
                    "native_unit": "Gg"}
            if s["co2e_Mt_AR5"] == national_series.ABSENT:
                rows.append({**base, "component_id": "%s|%s|absent" % (name, period_id),
                             "reporting_sector": name,
                             "gas": "", "ipcc_code": "", "category": "", "subitem": "",
                             "gas_origin": "", "estimate_status": "absent",
                             "activity_status": "absent", "evidence_class": "",
                             "emission_native_mass": "", "co2e_Mt_AR5": "",
                             "co2e_Mt_AR6": "", "source_stream_id": "",
                             })
                continue
            for c in _components(name, fy_end, context):
                method, model = method_registry.lookup(c["category"], c["subitem"], rules,
                                                       sector=name, gas=c["gas"])
                rows.append({
                    **base,
                    "method_id": method, "uncertainty_model_id": model,
                    "component_id": c["component_id"], "gas": c["gas"],
                    "reporting_sector": reporting_sectors.resolve(
                        reporting_rows, name, c["category"], c["subitem"]),
                    "ipcc_code": component_code(c["category"], c["subitem"], c["gas"]),
                    "category": c["category"], "subitem": c["subitem"],
                    "gas_origin": ("fossil" if c.get("fossil") else "biogenic")
                                  if c["gas"] == "CH4" else "not-applicable",
                    "estimate_status": "E-category-gas" if c.get("_coarse") else "E",
                    "activity_status": s["activity_basis"],
                    "evidence_class": c["evidence_class"],
                    "emission_native_mass": (round(c["emissions_Gg"], 6)
                                             if c["emissions_Gg"] != "" else ""),
                    "co2e_Mt_AR5": round(c["co2e_Mt_AR5"], 8),
                    "co2e_Mt_AR6": round(c["co2e_Mt_AR6"], 8),
                    "source_stream_id": c["component_id"],
                })
    return rows


COARSE_GRAIN = ("no component split exists for this sector-period: the pre-reference "
                "agriculture history is a FAOSTAT-basis reconstruction carried by "
                "category and gas, not by stream, so this row is one grain coarser than "
                "the rest of the table and says so rather than being dropped")


def _components(name, fy_end, context):
    """Component rows for one sector-period, through the annual product's own dispatch.

    WHERE THERE IS NO COMPONENT SPLIT, THE ROWS STILL EXIST. Agriculture before the
    reference year is carried by category and gas rather than by stream, and an earlier
    draft of this function returned an empty list for it - which silently dropped half the
    inventory and printed a FY2015-16 national total of 135.85 Mt against the series'
    305.42. That is precisely the silence this table was built to remove, reintroduced by
    the table itself. Coarser rows are emitted with their grain declared.
    """
    comps = annual_product.components_for(name, fy_end, context)
    if comps is not None:
        return comps
    out = []
    for (category, gas), (ar5, ar6) in sorted(context["agri_gas"].get(fy_end, {}).items()):
        out.append({"category": category, "subitem": "(no component split)", "gas": gas,
                    "component_id": "%s|%s|category-gas-only|%s"
                                    % (name, category.lower().replace(" ", "-"),
                                       gas.lower()),
                    "co2e_Mt_AR5": ar5, "co2e_Mt_AR6": ar6,
                    "emissions_Gg": "", "evidence_class": "", "_coarse": True})
    return out


def _read(name):
    return read_rows(asset_path(OUTPUTS, name), comments=False)


def _read_data(name):
    from pkinv.paths import DATA
    return read_rows(asset_path(DATA, name), comments=False)


def _sector_universe(rows):
    """Every sector the product knows about, absent rows included."""
    return {r["sector_id"] for r in rows}


def aggregates(rows):
    """Roll-ups derived from the atom, in their own file so nothing sums a total twice.

    THE TOP LEVEL IS NOT ALWAYS "NATIONAL", and calling it that in a year the inventory does
    not cover is the specific overstatement this guards against. A period whose sectors are
    all present gets `national`; a period missing any sector gets `covered_total`, with the
    number of sectors behind it and its share of the reference year's mass on the row. Both
    are the same arithmetic - the difference is what a reader is entitled to conclude from
    it, and FY2015-16 at 319 Mt is not a national total for Pakistan, it is eight sectors of
    one.
    """
    universe = _sector_universe(rows)
    covered = collections.defaultdict(set)
    for row in rows:
        if row["co2e_Mt_AR5"] != "":
            covered[row["period_id"]].add(row["sector_id"])
    reference_mass = sum(float(r["co2e_Mt_AR5"]) for r in rows
                         if r["period_id"] == REFERENCE_PERIOD and r["co2e_Mt_AR5"] != "")
    reference_by_sector = collections.defaultdict(float)
    for row in rows:
        if row["period_id"] == REFERENCE_PERIOD and row["co2e_Mt_AR5"] != "":
            reference_by_sector[row["sector_id"]] += float(row["co2e_Mt_AR5"])

    out = []
    for level, keys in LEVELS:
        totals = collections.defaultdict(lambda: [0.0, 0.0])
        for row in rows:
            if row["co2e_Mt_AR5"] == "":
                continue
            key = tuple(row[k] for k in keys)
            totals[key][0] += float(row["co2e_Mt_AR5"])
            totals[key][1] += float(row["co2e_Mt_AR6"])
        for key, (ar5, ar6) in sorted(totals.items()):
            entry = {"aggregation_level": level, "co2e_Mt_AR5": round(ar5, 8),
                     "co2e_Mt_AR6": round(ar6, 8),
                     "configuration_id": REFERENCE_CONFIGURATION,
                     "geography_id": NATIONAL_GEOGRAPHY,
                     "sectors_covered": "", "sectors_expected": "",
                     "coverage_fraction_of_reference": ""}
            entry.update(dict(zip(keys, key)))
            if level == "national":
                present = covered[entry["period_id"]]
                entry["sectors_covered"] = len(present)
                entry["sectors_expected"] = len(universe)
                share = (sum(reference_by_sector[s] for s in present) / reference_mass
                         if reference_mass else 0.0)
                entry["coverage_fraction_of_reference"] = round(share, 6)
                if present != universe:
                    entry["aggregation_level"] = "covered_total"
            out.append(entry)
    return out


def main():
    rows = build()
    write_table(OUT, FIELDS, rows, extrasaction="ignore")

    agg = aggregates(rows)
    fields = ["aggregation_level", "period_id", "sector_id", "category", "gas",
              "configuration_id", "geography_id", "co2e_Mt_AR5", "co2e_Mt_AR6",
              "sectors_covered", "sectors_expected", "coverage_fraction_of_reference"]
    write_table(AGGREGATES, fields, agg, extrasaction="ignore")

    priced = [r for r in rows if r["co2e_Mt_AR5"] != ""]
    absent = len(rows) - len(priced)
    national = [r for r in agg if r["aggregation_level"] == "national"]
    print("atomic annual -> %s" % OUT)
    print("  %d rows: %d priced components, %d declared-absent sector-periods"
          % (len(rows), len(priced), absent))
    print("  %d periods, %d components at the reference period"
          % (len({r["period_id"] for r in rows}),
             len({r["component_id"] for r in priced
                  if r["period_id"] == "FY2023-24"})))
    print("  national totals: %s"
          % ", ".join("%s %.2f" % (r["period_id"], r["co2e_Mt_AR5"])
                      for r in sorted(national, key=lambda x: x["period_id"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

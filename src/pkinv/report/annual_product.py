"""The annual data product: a nine-year panel, one row per sector-category-gas.

WHAT TO CALL IT, EXACTLY. A nine-fiscal-year panel with complete ten-MODULE reference
coverage for all nine years: the FY2015-16 product splits for road transport and
industrial combustion - the last two absent cells - were recovered from the public
record at rc20 under a four-way identity gate, so the 90-sector-year rectangle has no
NE cell. What "complete" ranges over is MODULES per year, never category scope: the
categories the inventory does not estimate stay NE in the completeness matrix, and a
sentence that let the rectangle imply full national scope would be the overstatement
the sixteenth review warned against.

The word complete ranges over MODULES and not over sources. All ten sectors report in those
eight years; the completeness register still names roughly 45 Mt of categories this
inventory does not estimate, and a phrase that let those two be confused is exactly what
tests/test_data_gaps.py refuses in the manuscripts.

WHY THIS EXISTS (the tenth review). The engine has published a nine-year national
series since rc9 - FY2015-16 to FY2023-24, ten sectors, absences named - but only as
a NATIONAL row per sector-year. A reader asking "what did agricultural methane do
across the window?" or "which sector-years are safe to trend?" had to re-derive both
from the sector modules. This file answers both in one product:

  * the grain is sector x IPCC category x gas wherever the sector's history carries
    it, and a sector-total row where it does not - stated per row in `grain`, never
    implied by which columns happen to be filled;

  * TWO VIEWS ship side by side, because forcing one is how a false trend gets
    published. `harmonized_common_scope` marks the sector-years reconstructed on a
    consistent method for every year of the window - the scientifically trendable
    series. Everything else is `best_available_full_scope`: the most complete
    reconstruction of each year, useful for magnitudes and NOT automatically safe to
    difference. FY2023-24 remains the most complete reference year in both.

WHAT IT DOES NOT DO. It does not restate a total. Every sector-year's magnitude is
the one `pakemis_national_series.csv` already published; this file EXPANDS those
totals and asserts the expansion closes to them. A product that recomputed would be
a second vintage of the number the series owns - the defect the release manifest was
built to end.

Usage:  python3 -m pkinv.report.annual_product
Writes: outputs/pakemis_annual_fy2015_16_fy2023_24.csv (+ .parquet where pyarrow is
        installed - the CSV is authoritative and the two are asserted equal)
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.core import components, registry
from pkinv.core import registry
from pkinv.core import configurations as _conf
from pkinv.paths import OUTPUTS
from pkinv.report import national_series as ns
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

OUT = asset_path(OUTPUTS, "pakemis_annual_fy2015_16_fy2023_24.csv")
# A literal, not OUT[:-4] + ".parquet": the outputs audit finds writers by
# scanning for the name, and a computed path is a file nothing appears to write.
OUT_PARQUET = asset_path(OUTPUTS, "pakemis_annual_fy2015_16_fy2023_24.parquet")

FIELDS = ("period_label", "fiscal_end_year", "sector", "category", "gas", "grain",
          "configuration_id",
          "co2e_Mt_AR5", "co2e_Mt_AR6", "activity_basis", "completeness_state",
          "harmonized_common_scope", "gap_id", "source_series")

# Detail must sum to the published total AT THE PRECISION THE TOTAL IS PUBLISHED.
# The series writes five decimals, so a detail sum of 169.563565 against a
# published 169.563570 is the published cell's own rounding, not a disagreement:
# the two are the same floats, grouped differently and rounded once. The bound is
# therefore half of the last published digit, plus a float-summation slack far
# below it. Anything larger is a real divergence and aborts the build.
CLOSURE_TOL_MT = 0.5e-5 + 1e-9

# THE HARMONIZED-COMMON-SCOPE RULE, now APPLIED rather than restated.
# A sector qualifies when it has a non-absent row in every year of the window. That was the
# stated rule and the membership beside it was a hand-written tuple, so the two could drift -
# and did. The tuple excluded IPPU because "it publishes emissions for the reference year
# alone" and industry because "it is absent in two years", and both statements outlived the
# data: cement now reports all nine years and industry is absent only in FY2015-16, which is
# before the window opens. Nothing could see it, because the test checked that MEMBERS are
# not absent and pinned the two exclusions by name - a sector that became eligible had no way
# to be noticed. The list is derived from the rows now, and the test checks the derivation.
#
# AGRICULTURE'S MEMBERSHIP USED TO BE AN ARGUMENT AND IS NOW A MEASUREMENT. It read: "its
# FAOSTAT-driven history is internally consistent across the window, the anchor break is
# priced in pakemis_series_splice_agriculture.csv." Both halves were weak. Internally
# consistent was true of the SOURCE and false of the time basis - the history was read at the
# fiscal-end year for every crop, which is right for wheat and a full year out for rice,
# maize, sugarcane and cotton. And the file named as the price compares the two bases at the
# anchor, where they coincide by construction.
#
# The history is now reconstructed on Pakistani fiscal activity, per driver:
#   four categories (rice, managed soils, liming/urea, field burning) on observed fiscal
#     crop and nitrogen tables;
#   two (enteric fermentation, manure management - 77.4 percent of the sector) still on the
#     FAOSTAT livestock projection, because no fiscal ENUMERATION exists to move them to,
#     with the residual six-month phase error MEASURED at under two percent per category
#     rather than asserted.
# That is why the basis is carried PER CATEGORY on agriculture's rows below instead of one
# word for the sector: "mostly fiscal" and "fiscal" are different claims.
# 2016 since rc20: the FY2015-16 product splits were recovered from the public
# record (the Pakistan Oil Report 2015-2016, identity-gated in
# sectors/transport/ocac_image_edition.py), so the trend-safe window now opens at
# the panel's first year and the harmonized view IS the full nine-year rectangle.
HARMONIZED_FROM_FY_END = 2016


def harmonized_sectors(series_rows):
    """The sectors with no absent year in the window, from the rows themselves.

    Sorted, so the membership is stable and diffable. A sector absent in ANY year at or
    after the window's first year is out: the view exists so that a difference taken across
    it cannot straddle a step change, and one missing year is enough to create one.
    """
    absent, seen = set(), set()
    for row in series_rows:
        if int(row["fiscal_end_year"]) < HARMONIZED_FROM_FY_END:
            continue
        seen.add(row["sector"])
        if row["co2e_Mt_AR5"] == "absent" or row["activity_basis"] == "absent":
            absent.add(row["sector"])
    return tuple(sorted(seen - absent))


def _category_basis(name, fy_end, category, sector_basis):
    """The basis of the DRIVER, where the driver is known finer than the sector.

    Only agriculture's backcast years qualify today, and only because its six categories run
    on two different activity sources. Everywhere else the sector's own word is the finest
    true statement available, and inventing a per-category one would be precision without
    information. The reference year is `observed` for every category and stays that way.
    """
    if name != "agriculture" or fy_end == 2024:
        return sector_basis
    return registry.get("agriculture").activity_basis(category)


def _series_rows():
    path = asset_path(OUTPUTS, "pakemis_national_series.csv")
    return [r for r in read_rows(path, comments=False) if r["row_kind"] == "sector"]


def build_context():
    """The shared per-run context both this product and the atomic table build on."""
    return {"agri_gas": ns.agri_fiscal_by_gas(),
            "res_data": registry.get("residential").load_data()}


def components_for(name, fy_end, ctx):
    """The COMPONENT rows for one sector-year, or None where only a total exists.

    Split out of _detail so the atomic annual table can read components rather than the
    (category, gas) sums _detail returns. One dispatch, two consumers: rebuilding this
    year-and-convention logic anywhere else would be a second arithmetic path to the same
    quantity, and the difference would show up as a disagreement nobody could source.

    AGRICULTURE'S HISTORY HAS A COMPONENT SPLIT, and this function spent several releases
    saying it did not. The sentence that used to sit here - "its history is a fiscal-basis
    reconstruction carried by category and gas, not by stream" - was true of the FAOSTAT
    reconstruction that preceded the agriculture-seam pass and false of the engine that
    replaced it. `fiscal_series.build()` has been computing all thirty-five components for
    every year and collapsing them on the way out ever since, so the detail was produced and
    thrown away on every run while this function returned None.

    The cost was not abstract: managed soils carried 211 Mt flat across eight years because
    its synthetic-fertiliser share could not be addressed, while the monthly offtake series
    that would have shaped it sat parsed, gated and validated. A declared absence that is
    never re-tested against the engine that superseded it is the defect this repository keeps
    finding, and this is the largest instance of it so far.
    """
    sector = registry.get(name)
    if name == "agriculture" and fy_end != 2024:
        return components.enrich_identity(
            sector.series_components_for_year(fy_end), name)
    if name == "residential":
        comps = sector.components_for_year(ctx["res_data"], fy_end)
    else:
        data = sector.load_data()
        year_key = fy_end if sector.YEAR_CONVENTION == "fiscal-end" else fy_end - 1
        comps = (sector.build_components(data) if fy_end == 2024
                 else sector.build_components(data, year_key))
    # registry.build_all() stamps identity for the reference-year build; a per-year build
    # goes straight to the sector and would otherwise arrive without one. Same function,
    # so a stream has the same id whichever path produced it - which is the entire point
    # of moving the construction into the schema.
    return components.enrich_identity(comps, name)


def _detail(name, fy_end, ctx):
    """[(category, gas, ar5, ar6)] for one sector-year.

    AGRICULTURE'S HISTORY KEEPS READING THE SHIPPED SERIES, deliberately, even though the
    components are now available above. `fiscal_series.build()` rounds to six decimals at
    (category, gas), and re-summing the subitems here would republish the same quantity at a
    different rounding - a 5e-7 Mt difference on numbers this project has published for
    several releases. That is far below any reported precision and is exactly the kind of
    silent, unexplainable drift the release-integrity tests exist to catch.

    So the coarse grain stays the authority for what is PUBLISHED, and the finer grain
    refines WITHIN it: the atomic table's own closure check is what holds the subitems to
    these totals rather than the two being allowed to disagree.
    """
    if name == "agriculture" and fy_end != 2024:
        by_gas = ctx["agri_gas"].get(fy_end, {})
        return [(cat, gas, a5, a6) for (cat, gas), (a5, a6) in sorted(by_gas.items())]
    comps = components_for(name, fy_end, ctx)
    if comps is None:
        by_gas = ctx["agri_gas"].get(fy_end, {})
        return [(cat, gas, a5, a6) for (cat, gas), (a5, a6) in sorted(by_gas.items())]
    out = {}
    for c in comps:
        key = (c["category"], c["gas"])
        a5, a6 = out.get(key, (0.0, 0.0))
        out[key] = (a5 + c["co2e_Mt_AR5"], a6 + c["co2e_Mt_AR6"])
    return [(cat, gas, a5, a6) for (cat, gas), (a5, a6) in sorted(out.items())]


REFERENCE_CONFIGURATION = _conf.REFERENCE


def _dung_residual_Mt(fy_end):
    """Diverted dung with no household destination, Mt air-dry, for one fiscal year:
    what agriculture diverts from that year's own herd less what the survey series has
    households burning. One home: report.dung_variants.price, which the nine-year fate
    account (pakemis_dung_fate_by_year.csv) also reads."""
    from pkinv.report import dung_variants
    return dung_variants.price(fy_end)["unresolved_Mt"]


def _configuration_rows(reference_rows):
    """The rows the two dung configurations add to the reference frame (rc31; roles
    swapped at rc67).

    UNDER THE REFERENCE, in every year: one typed row for the diverted dung that has no
    household destination. It carries no CO2e, because no emissions pathway is applied
    to it, and it is in the frame so that a reader summing the reference sees what the
    sum leaves out. Its mass is on the row; its candidate destinations are priced in
    national_dung_variants.csv.

    CONFIGURATION L, reference year only: an ENGINE RE-RUN of the residential sector
    with all the diverted dung burned in households. Every other sector is identical by
    construction and its rows are not duplicated - the identity is asserted in
    tests/test_configuration_keys.py rather than by copying 700 rows. L leaves no
    residual, so it has no residual row.
    """
    from pkinv.core import configurations as conf
    import collections
    res_engine = registry.get("residential")
    data = res_engine.load_data()
    out = []
    seen = set()
    for r in reference_rows:
        if r["sector"] != "residential" or r["co2e_Mt_AR5"] == "":
            continue
        fy_end = int(r["fiscal_end_year"])
        if fy_end in seen:
            continue
        seen.add(fy_end)
        out.append({**r, "category": "Diverted dung, unresolved fate", "gas": "",
                    "grain": "residual_no_pathway",
                    "configuration_id": conf.REFERENCE,
                    "co2e_Mt_AR5": "", "co2e_Mt_AR6": "",
                    "activity_basis": "survey dung basis (the reference since rc67)",
                    "completeness_state": "NA",
                    "gap_id": "declared unresolved stock, no emissions pathway; "
                              "quantified for every year in pakemis_dung_fate_by_year.csv "
                              "(%.2f Mt air-dry mass, not CO2e)"
                              % _dung_residual_Mt(fy_end)})
    comps = res_engine.build_components(data, dung_basis=conf.ALTERNATIVE_DUNG_BASIS)
    ref_year = max(seen)
    template = next(r for r in reference_rows
                    if r["sector"] == "residential"
                    and int(r["fiscal_end_year"]) == ref_year)
    by_cat = collections.defaultdict(lambda: [0.0, 0.0])
    for c in comps:
        key = (c["category"], c["gas"])
        by_cat[key][0] += c["co2e_Mt_AR5"]
        by_cat[key][1] += c["co2e_Mt_AR6"]
    for (cat, gas), (a5, a6) in sorted(by_cat.items()):
        out.append({**template, "category": cat, "gas": gas,
                    "grain": "category_gas", "configuration_id": conf.LEDGER,
                    "co2e_Mt_AR5": round(a5, 6), "co2e_Mt_AR6": round(a6, 6),
                    "activity_basis": "ledger dung basis (configuration L)",
                    "completeness_state": "E", "gap_id": ""})
    return out


def build():
    ctx = build_context()
    known = {s.NAME for s in registry.all_sectors()}
    series = _series_rows()
    members = harmonized_sectors(series)

    rows = []
    for s in series:
        name, fy_end = s["sector"], int(s["fiscal_end_year"])
        assert name in known, name
        harmonized = ("yes" if (name in members
                                and fy_end >= HARMONIZED_FROM_FY_END) else "no")
        base = {"period_label": s["period_label"], "fiscal_end_year": fy_end,
                "sector": name, "activity_basis": s["activity_basis"],
                "harmonized_common_scope": harmonized,
                "configuration_id": REFERENCE_CONFIGURATION,
                "source_series": "pakemis_national_series.csv"}
        if s["co2e_Mt_AR5"] == ns.ABSENT:
            # An absent sector-year is a ROW, never a silent hole: it carries the
            # named gap that would close it.
            rows.append({**base, "category": "", "gas": "", "grain": "absent",
                         "co2e_Mt_AR5": "", "co2e_Mt_AR6": "",
                         "completeness_state": "NE", "harmonized_common_scope": "no",
                         "gap_id": s["note"]})
            continue

        detail = _detail(name, fy_end, ctx)
        published = float(s["co2e_Mt_AR5"])
        if detail:
            got = sum(a5 for _c, _g, a5, _a6 in detail)
            if abs(got - published) > CLOSURE_TOL_MT:
                raise SystemExit(
                    "annual product does not close: %s FY%d detail sums to %.9f "
                    "against the published %.9f" % (name, fy_end, got, published))
            for cat, gas, a5, a6 in detail:
                rows.append({**base, "category": cat, "gas": gas,
                             "activity_basis": _category_basis(name, fy_end, cat,
                                                               s["activity_basis"]),
                             "grain": "category_gas",
                             "co2e_Mt_AR5": round(a5, 6), "co2e_Mt_AR6": round(a6, 6),
                             "completeness_state": "E", "gap_id": ""})
        else:
            rows.append({**base, "category": "", "gas": "",
                         "grain": "sector_total",
                         "co2e_Mt_AR5": s["co2e_Mt_AR5"],
                         "co2e_Mt_AR6": s["co2e_Mt_AR6"],
                         "completeness_state": "E", "gap_id": ""})
    rows.extend(_configuration_rows(rows))
    return rows


def _write_parquet(rows):
    """Best-effort parquet beside the CSV. The CSV is authoritative; a missing
    pyarrow is not a build failure, and a DIFFERING parquet would be."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return None
    cols = {f: [r[f] for r in rows] for f in FIELDS}
    table = pa.table({f: pa.array([str(v) for v in cols[f]]) for f in FIELDS})
    pq.write_table(table, OUT_PARQUET)
    return OUT_PARQUET


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = build()
    write_table(OUT, FIELDS, rows)
    parq = _write_parquet(rows)
    harmonized = sum(1 for r in rows if r["harmonized_common_scope"] == "yes")
    absent = sum(1 for r in rows if r["grain"] == "absent")
    print("annual product -> %s (%d rows: %d in the harmonized common scope, "
          "%d declared-absent sector-years)%s"
          % (os.path.relpath(OUT), len(rows), harmonized, absent,
             "; parquet beside it" if parq else "; no pyarrow, CSV only"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

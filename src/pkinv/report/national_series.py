"""The national series, FY2015-16 to FY2023-24: nine years that do not touch the tenth digit.

WHAT THIS IS. One row per (sector, fiscal year) over the reviewer's common period, plus a
COVERED_TOTAL row per year. It is the reviewer's Stage 3 product, built under one invariant:
the FY2023-24 column equals outputs/national_all_sectors.csv sector by sector, exactly - the
reference year is anchored in roughly seventy places and a series that moved it would be a
fourth national vintage, the precise failure Round 5 spent a release repairing.

WHAT A COVERED TOTAL IS, AND IS NOT. IPPU needs six more fiscal years of national cement
ACTIVITY - its clinker trade is now observed in all nine, so the gap that named trade for
eight years is closed and what remains is the other half of the balance; industry is missing
the FY2020-21 OGRA edition and any pre-FY2016-17 OCAC edition; transport's OCAC panel starts
at FY2016-17. Those years are ABSENT rows naming their gap - not zeros, not held-forward
values. The COVERED_TOTAL sums what exists and carries a coverage share measured against the
frozen reference year, so a reader can see at a glance that the FY2015-16 total stands on
88.6 percent of the reference scope and the last three years on 100. Backfilling the absent
sectors at their reference values was considered and refused: it would manufacture a flat 26
Mt history and read as observation.

THE DECLARED BREAKS (the reviewer's changelog gate, in one place):
- agriculture is reconstructed on PAKISTANI FISCAL activity, per driver rather than per
  sector. Crops and nitrogen ride the Economic Survey's own fiscal tables
  (agriculture/fiscal_series.py); livestock stocks stay on the FAOSTAT projection, because
  Pakistan has no fiscal-year livestock ENUMERATION to move them to and the Economic
  Survey's fiscal head counts are, by their own footnote, the same inter-census projection
  under a different label. The per-category bases ship in the annual product and in
  outputs/pakemis_agriculture_fiscal_series.csv; the residual phase error on the two
  categories that keep a calendar driver is MEASURED, not asserted, at under two percent of
  each category.
  THE EARLIER EDITION OF THIS PARAGRAPH WAS WRONG ABOUT WHERE THE BREAK WAS. It said the
  history "rides FAOSTAT stocks" and pointed at
  outputs/pakemis_series_splice_agriculture.csv for the price. That file compares the two
  bases AT THE ANCHOR, where the FAOSTAT-basis series rides the census engine BY
  CONSTRUCTION, so it reported about 0.0001 Mt and could never have reported anything else.
  The break was in the eight years before the anchor, where nothing measured it. It is
  measured now, in outputs/pakemis_agriculture_basis_change.csv, and it was worth -7.70 Mt
  of basis and +1.06 Mt of missing cotton across those eight years.
  AND MOST OF IT WAS AN OFF-BY-ONE. FAOSTAT labels each crop by its own harvest calendar
  year; a Pakistani fiscal year holds the KHARIF crop harvested in the preceding calendar
  year and the RABI crop harvested in its own. Reading the whole history at the fiscal-end
  year was therefore right for wheat and wrong by a full year for rice, maize, sugarcane and
  cotton. outputs/pakemis_agriculture_crop_calendar.csv measures it: those four agree with
  the fiscal tables to 0.02-0.13 percent one year back and disagree by 7-11 percent where
  they were read. The cost was concrete - FY2022-23, the year of the floods, was published
  with 3.64 Mha of rice, which is the FOLLOWING year's recovered crop against an actual
  2.98 Mha.
- transport's control was repointed from a static FY2023-24 factor row to the OCAC panel by
  year (bit-identical at the reference, tests/test_national_series.py holds the equality as
  float ==). Its class composition borrows the nearest COMPLETE registration year in either
  direction, declared per year.
- waste holds the 2023 JMP sanitation split in every year; protein uses its own observed
  2020-2023 values and clamps outside them. residential holds its sub-four-percent streams
  (LPG, kerosene, coal, charcoal, generators) at reference values, declared per stream by its
  own series module. power's captive panel is fiscal-END keyed and the engine shifts the grid
  year by +1 to reach it.

Usage:  python3 -m pkinv.report.national_series
Writes: outputs/pakemis_national_series.csv
        outputs/pakemis_national_series_coverage.csv
        outputs/pakemis_series_splice_agriculture.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core import gwp, period, registry
from pkinv.paths import OUTPUTS
from pkinv.report import unallocated_controls
from pkinv.core.io import seq_sum, write_table

from pkinv.core.reporting_window import CORE_FY_ENDS
SERIES_YEARS = CORE_FY_ENDS

# row_kind is typed for the same reason it is in national_all_sectors.csv: nine
# COVERED_TOTAL rows sit in the same `sector` column as the ten sector rows they sum, and
# nothing but reader discipline stopped a column sum from double-counting. The parts alone
# are outputs/pakemis_atomic_annual.csv; the aggregates derived from them, with their level
# named, are outputs/pakemis_atomic_annual_aggregates.csv.
FIELDS = ("row_kind", "period_label", "fiscal_end_year", "sector", "sector_year_key",
          "year_convention", "period_start", "period_end",
          "co2e_Mt_AR5", "co2e_Mt_AR6", "activity_basis", "held_constant", "note")

ABSENT = "absent"

# The column that stops this file being read as something it is not. It compares the engine
# against the FAOSTAT-calendar basis AT THE REFERENCE YEAR ONLY, where the FAOSTAT-basis
# series rides the census engine by construction - so a number near zero here is arithmetic,
# not evidence that the two bases agreed. The basis change is priced across the eight
# backcast years in outputs/pakemis_agriculture_basis_change.csv, and it is not near zero.
WHAT_THE_SPLICE_PRICES = ("reference-year only; the two bases coincide here by construction. "
                          "The basis change is priced across FY2015-16..FY2022-23 in "
                          "pakemis_agriculture_basis_change.csv")

# The machine-readable reason both surviving absences carry, defined where the ledger that
# holds their evidence defines it so the two cannot drift apart. A coverage product that
# spells one absence nine ways cannot be counted; a reason CODE can.
REASON_CODE = unallocated_controls.REASON_CODE

# What is held constant, per sector, for every non-reference year. Declared here once
# rather than discovered in code review; the residential list is read from its own series
# module at build time and these are the rest.
HELD = {
    "transport": "generator-petrol carve-out (HIES 2024-25); MJ/km intensity bands; "
                 "class composition borrows nearest complete registration year",
    # rc67: the sanitation pathway shares left this list. Each year reads its own JMP row
    # (2015-2023); the note said "JMP 2023 ... shares" for a release after the engine stopped
    # holding them.
    "waste": "generation and collection rates; waste composition; "
             "protein clamped to its 2020-2023 panel outside it",
    # The coal blend used to sit in this entry as "plant fuel mix vintages". It is no
    # longer held: data/power_coal_blend_by_year.csv carries a lignite share per fiscal
    # year, zero before the Thar fleet existed. What remains held is named.
    "power": "grid heat rates; captive heating value",
    "fugitives": "practice factors and technology assumptions of the reference structural "
                 "configuration",
    # THIS ENTRY WAS FALSE, and eight shipped rows carried it. Railways already builds
    # every historical year on that year's own measured locomotive/other split from
    # data/activity/railways/fuel_detail.csv, and the non-traction share moves between
    # 1.01 and 1.56 percent across the window - it is one of the better-evidenced things
    # in the series, and the series declared it frozen. What is actually held is the
    # parameter vintage underneath it.
    "railways": "fuel densities and traction emission factors at reference vintage",
    "aviation": "fleet fuel-burn fits",
    # Cement's clinker fraction and its calcination factor are reference-vintage parameters
    # applied to each year's own activity and its own observed trade. The stock change is
    # zero in every year for the same reason it is zero at the reference: no public control.
    "ippu": "clinker fraction, clinker calcination factor and the zero stock-change "
            "assumption at reference vintage (activity and trade move per year)",
    "agriculture": "Tier-2 rates, manure-management shares and dung fractions held; "
                   "census-anchored livestock reconstruction uses the adopted 2024 stock "
                   "anchors and species-specific relative proxy changes, with declared "
                   "post-census extrapolation; fiscal crop and nitrogen activities vary",
}

# Why a sector-year is absent, named per the no-silent-nulls discipline.
GAPS = {
    # IPPU IS GONE FROM THIS DICT, and both halves of its absence closed by reading rather
    # than by acquiring. The trade half went first: the monthly HS 252310 panel now runs July
    # 2014 to June 2024 and every fiscal year resolves to an observed trade term. The
    # activity half went the same way - the State Bank supplement reaches back to FY2019-20
    # and Pakistan Statistical Year Book 2020 Table 13.2 covers FY2015-16 to FY2018-19, a
    # document under sources/ throughout. Cement now reports all nine years. The two
    # publications overlap at FY2019-20 and agree to 1 kt in 39,122, which is what makes the
    # join between them a measured bridge; see outputs/pakemis_cement_activity_sources.csv.
    # FY2020-21 is gone from here too: the OGRA edition was HELD all along and is an image
    # scan, so its sector table was rendered and OCR'd rather than declared absent
    # (scripts/ocr_ogra_2020_21.py).
    #
    # THE LAST TWO CLOSED THE SAME WAY (rc20, the fifteenth review). For four releases
    # transport and industry FY2015-16 were NE with their observed totals held in the
    # unallocated-controls ledger - Road 12,440,195 and Total Industry 2,023,377 t from the
    # FY2016-17 edition's prior-year column - because the product split existed in no held
    # document and a 16-source search was logged negative. The fifteenth review pointed out
    # the split IS public: ocac.org.pk serves the Pakistan Oil Report 2015-2016 as a
    # 602-pixel image flipbook, and page 50 is the product-by-sector table. The search-log
    # row had crawled the statistics page, which links only current-year files. The page is
    # held (data/raw/ocac/oil_report_2015_16/), its transcription is quadruple-identity-
    # gated (sectors/transport/ocac_image_edition.py) - and the two held totals became the
    # TWO-DOCUMENT gate: the new edition's Road and Total Industry TOTALs equal them
    # exactly. Both engines build FY2015-16 from the recovered cells with no code change.
    # The dict is deliberately left in place, empty: absences are rows, not silences, and
    # the next absence goes here with its reason.
}


def _agri_timeseries():
    """{year: {category: (AR5, AR6)}} from the FAOSTAT-basis series, metrics from the gas
    masses through core.gwp - the file carries AR5 only, and restating a GWP here would be
    a second statement of a number the engine already owns."""
    path = asset_path(OUTPUTS, "timeseries_1990_2024.csv")
    out = {}
    for row in _activity_rows(path, comments=False):
        if row["category"] == "TOTAL":
            continue
        year = int(row["year"])
        ar5 = ar6 = 0.0
        for gas_name, column in (("CO2", "CO2_kt"), ("CH4", "CH4_kt"), ("N2O", "N2O_kt")):
            gg = float(row[column] or 0.0)
            # Agriculture methane is biogenic throughout - enteric, manure, rice.
            ar5 += gwp.to_co2e(gas_name, gg, "AR5", fossil=False) / 1000.0
            ar6 += gwp.to_co2e(gas_name, gg, "AR6", fossil=False) / 1000.0
        out.setdefault(year, {})[row["category"]] = (ar5, ar6)
    return out


def agri_fiscal_series():
    """{fiscal_end_year: {category: (AR5, AR6)}} on the Pakistani fiscal basis.

    The published agriculture history. Computed by agriculture/fiscal_series.py from the
    Economic Survey's own fiscal tables rather than read back from a written file, so the
    series and the sector product cannot be two vintages of one number.
    """
    from pkinv.sectors.agriculture import fiscal_series
    return fiscal_series.series_by_category()


def agri_fiscal_by_gas():
    """{fiscal_end_year: {(category, gas): (AR5, AR6)}} - the annual product's grain.

    Sibling of agri_fiscal_series above, one grouping finer, for the same reason the
    calendar pair were siblings: the series needs the category total and the annual product
    needs the gas split, and a refactor that merged them would put the shipped series'
    arithmetic at the mercy of the finer product's.
    """
    from pkinv.sectors.agriculture import fiscal_series
    return fiscal_series.series_by_gas()


def agri_timeseries_by_gas():
    """{year: {(category, gas): (AR5, AR6)}} - the same file and the same GWP call
    as _agri_timeseries above, one grouping finer. The annual product needs the gas
    split; the series needs the category total. Kept as a sibling rather than a
    refactor of the collapsed reader so the shipped series' arithmetic - and
    therefore its every published digit - is untouched by the finer product."""
    path = asset_path(OUTPUTS, "timeseries_1990_2024.csv")
    out = {}
    for row in _activity_rows(path, comments=False):
        if row["category"] == "TOTAL":
            continue
        year = int(row["year"])
        for gas_name, column in (("CO2", "CO2_kt"), ("CH4", "CH4_kt"),
                                 ("N2O", "N2O_kt")):
            gg = float(row[column] or 0.0)
            if not gg:
                continue
            ar5 = gwp.to_co2e(gas_name, gg, "AR5", fossil=False) / 1000.0
            ar6 = gwp.to_co2e(gas_name, gg, "AR6", fossil=False) / 1000.0
            out.setdefault(year, {})[(row["category"], gas_name)] = (ar5, ar6)
    return out


def _sum(pairs):
    # sequential, not built-in sum(): see pkinv.core.io.seq_sum (rc42) - the published
    # cells sit on rounding ties that CPython 3.12's compensated sum() flips
    return (seq_sum(a for a, _ in pairs), seq_sum(b for _, b in pairs))


def build():
    from pkinv.sectors.agriculture import fiscal_activity as agri_activity
    rows = []
    splice = []
    reference = {}          # sector -> (AR5, AR6) at FY2023-24, from the engines

    # The FAOSTAT-calendar history is still read, but ONLY to keep
    # pakemis_series_splice_agriculture.csv - a hashed canonical product the manuscripts
    # cite - reporting the same anchor comparison it always did. The published history now
    # comes from the fiscal series. Keeping both readable is what lets
    # pakemis_agriculture_basis_change.csv price the move rather than assert it.
    agri_ts = _agri_timeseries()
    agri_fiscal = agri_fiscal_series()
    agri_engine = registry.get("agriculture")
    agri_data = agri_engine.load_data()
    engine_2024 = {}
    for c in agri_engine.build_components(agri_data):
        a5, a6 = engine_2024.get(c["category"], (0.0, 0.0))
        engine_2024[c["category"]] = (a5 + c["co2e_Mt_AR5"], a6 + c["co2e_Mt_AR6"])
    for category in sorted(engine_2024):
        eng = engine_2024[category][0]
        ts = agri_ts.get(2024, {}).get(category, (0.0, 0.0))[0]
        splice.append({"category": category, "engine_Mt_AR5": round(eng, 5),
                       "faostat_basis_Mt_AR5": round(ts, 5),
                       "splice_difference_Mt": round(eng - ts, 5),
                       "what_this_prices": WHAT_THE_SPLICE_PRICES})

    from pkinv.sectors.residential import timeseries as res_ts
    from pkinv.sectors.residential.data import ResidentialData
    res_data = ResidentialData()

    for fy_end in SERIES_YEARS:
        label = period.label(*period.fiscal(fy_end - 1))
        for name in sorted(s.NAME for s in registry.all_sectors()):
            sector = registry.get(name)
            convention = sector.YEAR_CONVENTION
            year_key = fy_end if convention == "fiscal-end" else fy_end - 1
            start, end = period.fiscal(fy_end - 1)
            gap = GAPS.get(name)
            if isinstance(gap, dict):
                gap = gap.get(fy_end)
            # The ippu special case that lived here - "absent in every year except the
            # reference" - is gone: its entry is a per-year dict like industry's now, which
            # is what let FY2021-22 and FY2022-23 open the moment their evidence landed.
            base = {"row_kind": "sector",
                    "period_label": label, "fiscal_end_year": fy_end, "sector": name,
                    "sector_year_key": year_key, "year_convention": convention,
                    "period_start": start.isoformat(), "period_end": end.isoformat()}
            if gap:
                rows.append({**base, "co2e_Mt_AR5": ABSENT, "co2e_Mt_AR6": ABSENT,
                             "activity_basis": ABSENT, "held_constant": ABSENT,
                             "note": gap})
                continue

            if name == "agriculture" and fy_end != 2024:
                ar5, ar6 = _sum(list(agri_fiscal[fy_end].values()))
                basis, held = "reconstructed-fiscal", HELD["agriculture"]
                note = ("Fiscal crop/nitrogen activity: Economic Survey and NFDC; "
                        + agri_activity.livestock_provenance(fy_end) + ". Per-category bases in "
                        "pakemis_agriculture_fiscal_series.csv; the change from the former "
                        "FAOSTAT-level/calendar history is reported in "
                        "pakemis_agriculture_basis_change.csv")
            elif name == "residential":
                comps = res_ts.components_for_year(res_data, fy_end)
                ar5 = sum(c["co2e_Mt_AR5"] for c in comps)
                ar6 = sum(c["co2e_Mt_AR6"] for c in comps)
                if fy_end == 2024:
                    basis, held, note = "observed", "none", "the engine's own reference build"
                else:
                    streams = res_ts.basis_for_year(res_data, fy_end)
                    held = "; ".join(sorted({"%s: %s" % (s, b) for s, b in streams.items()
                                             if "held" in b or "reference" in b}))
                    basis = "reconstructed"
                    note = "per-stream bases from residential/timeseries.py"
            else:
                data = sector.load_data()
                comps = (sector.build_components(data) if fy_end == 2024
                         else sector.build_components(data, year_key))
                ar5 = sum(c["co2e_Mt_AR5"] for c in comps)
                ar6 = sum(c["co2e_Mt_AR6"] for c in comps)
                if fy_end == 2024:
                    basis, held, note = "observed", "none", "the engine's own reference build"
                else:
                    basis = "observed"
                    held = HELD.get(name, "none")
                    note = "the engine at this year's own activity"
            if fy_end == 2024:
                reference[name] = (ar5, ar6)
            rows.append({**base, "co2e_Mt_AR5": round(ar5, 5), "co2e_Mt_AR6": round(ar6, 5),
                         "activity_basis": basis, "held_constant": held, "note": note})

    reference_total = sum(a for a, _ in reference.values())
    coverage = []
    for fy_end in SERIES_YEARS:
        label = period.label(*period.fiscal(fy_end - 1))
        year_rows = [r for r in rows
                     if r["fiscal_end_year"] == fy_end and r["sector"] != "COVERED_TOTAL"]
        covered = [r for r in year_rows if r["activity_basis"] != ABSENT]
        missing = [r["sector"] for r in year_rows if r["activity_basis"] == ABSENT]
        ar5 = sum(float(r["co2e_Mt_AR5"]) for r in covered)
        ar6 = sum(float(r["co2e_Mt_AR6"]) for r in covered)
        share = 100.0 * sum(reference[r["sector"]][0] for r in covered) / reference_total
        start, end = period.fiscal(fy_end - 1)
        rows.append({"row_kind": "covered_total",
                     "period_label": label, "fiscal_end_year": fy_end,
                     "sector": "COVERED_TOTAL", "sector_year_key": fy_end,
                     "year_convention": "fiscal-end",
                     "period_start": start.isoformat(), "period_end": end.isoformat(),
                     "co2e_Mt_AR5": round(ar5, 5), "co2e_Mt_AR6": round(ar6, 5),
                     "activity_basis": "covered-sum",
                     "held_constant": "not-applicable",
                     "note": "%d of %d sectors; absent: %s"
                             % (len(covered), len(year_rows),
                                "; ".join(missing) if missing else "none")})
        coverage.append({
            "period_label": label,
            "sectors_covered": len(covered),
            "sectors_absent": "; ".join(missing) if missing else "none",
            "covered_Mt_AR5": round(ar5, 5),
            "coverage_share_pct_of_reference": round(share, 2),
            "bases": "; ".join(sorted({r["activity_basis"] for r in covered})),
        })
    return rows, coverage, splice, reference


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows, coverage, splice, reference = build()

    path = asset_path(OUTPUTS, "pakemis_national_series.csv")
    write_table(path, list(FIELDS), rows)

    cov_path = asset_path(OUTPUTS, "pakemis_national_series_coverage.csv")
    write_table(cov_path, list(coverage[0]), coverage)

    splice_path = asset_path(OUTPUTS, "pakemis_series_splice_agriculture.csv")
    write_table(splice_path, list(splice[0]), splice)

    print("national series -> %s" % path)
    print("  %s..%s, %d sector-years + %d covered totals"
          % (coverage[0]["period_label"], coverage[-1]["period_label"],
             sum(1 for r in rows if r["sector"] != "COVERED_TOTAL"), len(coverage)))
    for c in coverage:
        print("  %s  %6.2f Mt  %d sectors  %5.1f%% of reference scope"
              % (c["period_label"], c["covered_Mt_AR5"], c["sectors_covered"],
                 c["coverage_share_pct_of_reference"]))
    gap = sum(r["splice_difference_Mt"] for r in splice)
    print("  agriculture splice at the 2024 anchor: %+.2f Mt engine-minus-FAOSTAT "
          "(per category in %s)" % (gap, os.path.basename(splice_path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

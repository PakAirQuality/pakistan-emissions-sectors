"""Pakistani FISCAL-year agricultural activity, FY2015-16 to FY2023-24.

WHY THIS EXISTS. The nine-year agriculture history rode FAOSTAT, and FAOSTAT is a CALENDAR
series. `national_series.py` indexed it by fiscal-END year, so FY2015-16 - published with
`year_convention = fiscal-end` over 2015-07-01 to 2016-06-30 - was driven by calendar-2016
activity. Six months of overlap between a declared period and its own drivers. The eleventh
review called that a structural seam rather than a source citation, and it was right.

The replacement was transcribed into data/activity/agriculture/es_fiscal_series.csv in August
2026 from the Economic Survey statistical appendix, registered as a source document - AND THEN
READ BY NOTHING for eighty-eight commits. That is this project's recurring defect wearing a new
coat: not a declared value nothing can contradict, but a declared SOURCE nothing consumes. This
module is the consumer, and tests/test_agriculture_fiscal.py is the guard that it stays one.

WHAT IS FISCAL HERE AND WHAT IS NOT, per driver rather than per sector.

  crops (area, production)   ES Tables 2.3 / 2.4     observed_fiscal
  nitrogen offtake           ES Table 2.9 / NFDC     observed_fiscal
  livestock stocks           FAOSTAT                 calendar_projection

Livestock is NOT re-based, and the reason is a fact about the source rather than an appetite
for work. Economic Survey Table 2.14 does publish fiscal head counts; its own footnote calls
them "estimated figures based on inter-census growth rate of Livestock Census 1996 & 2006",
and they are numerically the FAOSTAT series they would replace. Transcribing them would buy a
fiscal label and an honest citation and ZERO new observation. Only two real enumerations exist
for Pakistan (Livestock Census 2006, PBS 7th Agricultural Census 2024) and the 2006 national
counts are not held here, so no two-enumeration interpolation can be built either.

That split is not a compromise, and it is worth saying why: the drivers that CAN be re-based
are the volatile ones (cotton fell 51 percent between FY2021-22 and FY2022-23 and then doubled),
and the driver that cannot is a smooth geometric projection, where a six-month phase shift is a
level offset of about one percent and very little trend error. The seam did its damage in the
crop categories, and those are exactly the ones this closes. The residual phase error is
MEASURED rather than asserted, in fiscal_series.livestock_phase_envelope().

THE SCOPE BREAK THIS ALSO CLOSES. data/activity/historical/crops.csv carries four crops; the
FY2023-24 anchor carries five. Cotton was absent from all eight history years and present at
the anchor - 0.150 Mt CO2e of residue burning and residue nitrogen appearing from nowhere at
the join, declared nowhere. The fiscal file carries cotton in all nine years.

Usage:  python3 -m pkinv.sectors.agriculture.fiscal_activity
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA
from pkinv.sectors.agriculture.ef_library import InventoryData
from pkinv.sectors.agriculture import timeseries as calendar_ts
from pkinv.activity.store import read_rows

SERIES = asset_path(DATA, "activity", "agriculture", "es_fiscal_series.csv")
FISCAL_YEARS = tuple(range(2016, 2025))          # fiscal-END keys: 2016 = FY2015-16
CROPS = ("wheat", "rice", "maize", "sugarcane", "cotton")

# SEED COTTON PER THOUSAND BALES. The Economic Survey publishes cotton as lint BALES; every
# engine equation that touches cotton wants seed-cotton tonnes. The anchor row in
# data/activity/crops_2024.csv documents the conversion in prose - a 170 kg lint bale at about
# a 35 percent ginning outturn - and prose is not machine-readable, so the factor is stated
# once here and CHECKED against the crossing of two independent files: the fiscal
# transcription's FY2023-24 bale count and the anchor's FY2023-24 seed-cotton tonnage. Neither
# is derived from the other, so the check is real rather than tautological. Deriving the factor
# from the anchor instead would make the anchor-parity assertion below pass by construction,
# which is the defect this repository has now found nine times.
SEED_COTTON_T_PER_1000_BALES = 485.9
COTTON_FACTOR_TOL = 0.001                        # 0.1 percent: the Survey rounds to 000 t

# The drivers, per engine category, and what they are keyed on. Published so the annual
# product's per-category `activity_basis` is read from one place rather than restated in three.
DRIVER = {
    "Enteric fermentation":       ("livestock stocks", "calendar_projection"),
    "Manure management":          ("livestock stocks", "calendar_projection"),
    "Rice cultivation":           ("rice area", "observed_fiscal"),
    "Managed soils":              ("N offtake, crop residues, manure N",
                                   "observed_fiscal_mixed"),
    "Urea application":        ("N offtake", "observed_fiscal"),
    "Field burning of residues":  ("crop production", "observed_fiscal"),
}
CALENDAR_BASIS = "calendar_projection"
FISCAL_BASIS = "observed_fiscal"
MIXED_BASIS = "observed_fiscal_mixed"

# Managed soils draws nitrogen from FOUR pools - synthetic offtake, crop residues, applied
# manure and pasture deposition - and only the first two are re-based. It gets its own basis
# word rather than being rounded into either neighbour, because "mostly fiscal" and "fiscal"
# are different claims. The share is MEASURED in fiscal_series.managed_soils_n_split() and a
# test holds the label against it, so the word cannot outlive the arithmetic.
MIXED_DRIVER_CATEGORIES = ("Managed soils",)

# The one FY2023-24 cell where the fiscal transcription and the anchor disagree, and the
# transcription is the better source. crops_2024.csv derives maize AREA from the narrative's
# "4.5 percent decrease" applied to the prior year (1,642); the statistical appendix publishes
# 1,641. Maize area feeds no engine equation - only maize PRODUCTION does, through the residue
# term - so nothing moves either way, and the anchor is left alone rather than edited for
# tidiness. Declared as an exception so the parity assertion stays absolute everywhere else.
ANCHOR_PARITY_EXCEPTIONS = {
    ("maize", "area_ha"): "the appendix publishes 1,641; the anchor derives 1,642 from "
                          "narrative prose. Feeds no equation - only maize production does.",
}


def _rows():
    return read_rows(SERIES)


def activity():
    """{fiscal_end_year: {item: float}} - the transcription, parsed and nothing more."""
    out = {}
    for row in _rows():
        out.setdefault(int(row["fiscal_end_year"]), {})[row["item"]] = float(row["value"])
    return out


def crops_for_year(table, fy_end):
    """{crop: {area_ha, production_t}} on the fiscal basis, cotton in seed tonnes."""
    year = table[fy_end]
    out = {}
    for crop in CROPS:
        production = (year["cotton_bales_000"] * SEED_COTTON_T_PER_1000_BALES
                      if crop == "cotton" else year["%s_production_t" % crop])
        out[crop] = {"area_ha": year["%s_area_ha" % crop], "production_t": production}
    return out


def data_for_fiscal_year(fy_end, table=None, stocks=None):
    """An InventoryData on FISCAL crops and nitrogen, with FAOSTAT livestock stocks.

    The mutation shape is timeseries._apply_year's, deliberately: the engine reads activity
    only from .livestock / .crops / .fertilizer, so a year is a mutation and not a refactor,
    and using a second shape here would be a second way for the two histories to disagree
    about what "the same engine" means.

    fy_end 2024 returns the census anchor untouched. That is not a shortcut - the reference
    year is anchored in roughly seventy places and a series that recomputed it would be a
    fourth national vintage. The parity assertion below is what makes it safe to say the
    fiscal path and the anchor are one basis rather than two.
    """
    if fy_end == 2024:
        return InventoryData()
    table = table if table is not None else activity()
    live, _crops, _nitro = (stocks if stocks is not None else calendar_ts._load_history())
    if fy_end not in table:
        raise ValueError("no fiscal activity for fiscal-end %d (have %s)"
                         % (fy_end, sorted(table)))
    # The FAOSTAT stock year is the fiscal-END year, the same mapping the calendar history
    # used. It is kept ON PURPOSE so that the basis-change measurement isolates ONE variable:
    # everything that moves between the two series moves because the crops and nitrogen moved.
    # The phase error this mapping leaves on the livestock half is measured separately.
    if fy_end not in live:
        raise ValueError("no FAOSTAT livestock stocks for %d" % fy_end)

    anchor = InventoryData()
    data = InventoryData()
    data.livestock = {s: {"head": live[fy_end][s], "uncert_pct": 15}
                      for s in calendar_ts.SPECIES}
    fiscal_crops = crops_for_year(table, fy_end)
    # Activity uncertainty per crop comes from the anchor rather than a fresh literal: the
    # widths encode how each cell was published (cotton widest because of the bale
    # conversion), and that reasoning does not change with the year.
    data.crops = {crop: {"area_ha": values["area_ha"],
                         "production_t": values["production_t"],
                         "uncert_pct": anchor.crops[crop]["uncert_pct"]}
                  for crop, values in fiscal_crops.items()}
    data.fertilizer["nitrogen_N_offtake"]["value_t"] = table[fy_end]["nitrogen_N_offtake_t"]
    # rc39 A3: the SECOND backcast path, and it has to declare itself for the same reason the
    # calendar one does. This function carries a fiscal total-N figure and no product split, so
    # its urea mass must be reconstructed; only the reference year has NFDC's printed offtake.
    # The stamp was added to timeseries._apply_year first and this path was missed, which gave
    # every historical year the reference year's MEASURED urea mass - moving eight fiscal years
    # by up to 1.42 Mt while the reference year moved by 0.01. The docstring above already says
    # the mutation shape is shared on purpose; the declaration is part of that shape.
    data.faostat_basis_year = fy_end
    return data


def anchor_parity(table=None):
    """[(cell, fiscal, anchor, status)] - every FY2023-24 fiscal cell against the anchor.

    The transcription's header CLAIMED this parity ("the FY2023-24 rows reproduce
    data/activity/crops_2024.csv exactly, which is the check that the anchor and the history
    are now the same basis rather than two") and nothing ever checked it. A claim in a comment
    is a claim nothing can fail.
    """
    table = table if table is not None else activity()
    anchor = InventoryData()
    fiscal = crops_for_year(table, 2024)
    out = []
    for crop in CROPS:
        for field in ("area_ha", "production_t"):
            mine, theirs = fiscal[crop][field], anchor.crops[crop][field]
            if (crop, field) in ANCHOR_PARITY_EXCEPTIONS:
                status = "declared-exception"
            elif crop == "cotton" and field == "production_t":
                # Converted, not transcribed: held to the conversion's own tolerance.
                status = ("ok" if abs(mine - theirs) <= COTTON_FACTOR_TOL * theirs
                          else "DISAGREES")
            else:
                status = "ok" if mine == theirs else "DISAGREES"
            out.append(("%s.%s" % (crop, field), mine, theirs, status))
    mine = table[2024]["nitrogen_N_offtake_t"]
    theirs = anchor.fertilizer["nitrogen_N_offtake"]["value_t"]
    out.append(("nitrogen_N_offtake.value_t", mine, theirs,
                "ok" if mine == theirs else "DISAGREES"))
    return out


def crop_scope_parity(table=None):
    """{'anchor': set, 'fiscal': set, 'calendar_faostat': set} - the cotton finding, generalised.

    A history year carrying FEWER crops than the anchor puts a step in the series at the join
    and calls it a trend. That is what happened: FAOSTAT's Pakistan crop extract carries four
    crops, the anchor carries five, and cotton's 0.150 Mt of residue burning and residue
    nitrogen appeared at the anchor from nowhere. Reported as sets rather than a count so the
    NEXT missing crop names itself.
    """
    table = table if table is not None else activity()
    _live, calendar_crops, _n = calendar_ts._load_history()
    return {"anchor": set(InventoryData().crops),
            "fiscal": set(crops_for_year(table, 2024)),
            "calendar_faostat": set(calendar_crops[2023])}


def main():
    table = activity()
    print("fiscal agricultural activity: %d years, FY%d-%02d to FY%d-%02d"
          % (len(table), min(table) - 1, min(table) % 100,
             max(table) - 1, max(table) % 100))

    print("\ncotton conversion, checked across two independent files:")
    bales, seed = table[2024]["cotton_bales_000"], InventoryData().crops["cotton"]["production_t"]
    print("  %.0f thousand bales x %.1f = %.0f t seed cotton; the anchor publishes %.0f "
          "(%+.3f%%)" % (bales, SEED_COTTON_T_PER_1000_BALES,
                         bales * SEED_COTTON_T_PER_1000_BALES, seed,
                         100.0 * (bales * SEED_COTTON_T_PER_1000_BALES - seed) / seed))

    print("\nFY2023-24 anchor parity:")
    bad = 0
    for cell, mine, theirs, status in anchor_parity(table):
        if status != "ok":
            bad += status == "DISAGREES"
            print("  %-28s fiscal %14.1f  anchor %14.1f  %s" % (cell, mine, theirs, status))
    print("  %d cells checked, %d declared exceptions, %d disagreements"
          % (len(anchor_parity(table)), len(ANCHOR_PARITY_EXCEPTIONS), bad))

    scope = crop_scope_parity(table)
    print("\ncrop scope: anchor %d, fiscal %d, calendar FAOSTAT %d"
          % (len(scope["anchor"]), len(scope["fiscal"]), len(scope["calendar_faostat"])))
    missing = scope["anchor"] - scope["calendar_faostat"]
    print("  absent from the calendar history and present at the anchor: %s"
          % (", ".join(sorted(missing)) or "none"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

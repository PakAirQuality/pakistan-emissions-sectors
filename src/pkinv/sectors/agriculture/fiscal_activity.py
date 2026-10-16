"""Pakistani fiscal agricultural activity, July2015-June2025.

Crop area/production and nitrogen offtake use the Economic Survey fiscal tables
and NFDC product records. The five census livestock species retain the adopted
PBS2024 levels; poultry retains its separately identified Survey projection.
Other years use FAOSTAT relative stock changes rescaled to those adopted anchors.
Beyond2024 the species-specific2019-2024 geometric relative trend is continued.
This is an explicit reconstruction/extrapolation, not a new annual enumeration.

The fiscal crop panel includes all five admitted crops. Driver-specific bases
remain distinct: reported crop/nutrient flows, reconstructed livestock stocks,
and mixed nitrogen sources. The detailed FY2023-24 anchor is independent of the
latest common-core year.
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA
from pkinv.sectors.agriculture.ef_library import InventoryData
from pkinv.sectors.agriculture import timeseries as calendar_ts
from pkinv.activity.store import read_rows

SERIES = asset_path(DATA, "activity", "agriculture", "es_fiscal_series.csv")
from pkinv.core.reporting_window import CORE_FY_ENDS
FISCAL_YEARS = CORE_FY_ENDS
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
    "Enteric fermentation":       ("livestock stocks", "census_anchored_reconstruction"),
    "Manure management":          ("livestock stocks", "census_anchored_reconstruction"),
    "Rice cultivation":           ("rice area", "observed_fiscal"),
    "Managed soils":              ("N offtake, crop residues, manure N",
                                   "observed_fiscal_mixed"),
    "Urea application":        ("N offtake", "observed_fiscal"),
    "Field burning of residues":  ("crop production", "observed_fiscal"),
}
CALENDAR_BASIS = "census_anchored_reconstruction"
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


def proxy_stocks_for_year(live, year):
    """Held relative stocks, or the declared species-specific post-2024 trend."""
    if year in live:
        return live[year]
    if year < 2024 or 2019 not in live or 2024 not in live:
        raise ValueError("livestock proxy bridge requires held year or 2019/2024 endpoints")
    return {species: live[2024][species] * (live[2024][species] / live[2019][species]) ** ((year - 2024) / 5.)
            for species in calendar_ts.SPECIES}


def livestock_provenance(fy_end):
    """Textual provenance of the existing reconstruction; no activity calculation."""
    anchor = ("adopted FY2023-24 stock anchors (five PBS2024 census species; "
              "Survey-projected poultry)")
    if fy_end == 2024:
        return anchor
    if fy_end < 2024:
        return anchor + "; FAOSTAT relative annual stock shape, fiscal-end-year mapping; reconstructed, not enumerated"
    return anchor + "; species-specific2019-2024 relative geometric trend continued after2024; modelled extrapolation, not enumeration"


def data_for_fiscal_year(fy_end, table=None, stocks=None):
    """Fiscal crops/nitrogen and the adopted stock-anchor relative reconstruction.

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
    # The relative stock-shape year is the fiscal-end year. Its level is rescaled
    # to the adopted2024 anchor below; it is not the old FAOSTAT stock level.
    anchor = InventoryData()
    data = InventoryData()
    # One census basis throughout the core. FAOSTAT contributes relative annual
    # changes, not an incompatible level spliced directly onto the new census.
    # Beyond the last proxy stock year, continue the 2019-2024 geometric trend;
    # this is a modelled extrapolation, explicitly distinguished from enumeration.
    if 2024 not in live or 2019 not in live:
        raise ValueError("livestock bridge requires held 2019 and 2024 proxy stocks")
    relative = proxy_stocks_for_year(live, fy_end)
    data.livestock = {s: {"head": anchor.livestock[s]["head"] * relative[s] / live[2024][s], "uncert_pct": 15}
                      for s in calendar_ts.SPECIES}
    data.livestock_basis = ("census_anchored_extrapolation" if fy_end > 2024
                           else "census_anchored_relative_stock_reconstruction")
    data.fiscal_activity_year = fy_end
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
    if fy_end == 2025:
        data.urea_offtake_product_t = 5890000.0
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

"""Agriculture on fiscal crops/nutrients and a consistent livestock-anchor bridge.

The ten-year July2015-June2025 core uses the maintained source activity and
unchanged sector calculation methods. Crop/nutrient flows, reconstructed stock
activity and mixed nitrogen sources carry their own driver provenance. The
archived FAOSTAT-level/calendar history is retained as an explicit source/basis
comparison, not described as the current stock series.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core import gwp
from pkinv.paths import OUTPUTS
from pkinv.sectors.agriculture import fiscal_activity as fa
from pkinv.sectors.agriculture import timeseries as calendar_ts
from pkinv.sectors.agriculture.ef_library import InventoryData
from pkinv.sectors.agriculture.run_inventory import build_components, CATEGORIES

SERIES_OUT = asset_path(OUTPUTS, "pakemis_agriculture_fiscal_series.csv")
BASIS_OUT = asset_path(OUTPUTS, "pakemis_agriculture_basis_change.csv")
CALENDAR_OUT = asset_path(OUTPUTS, "pakemis_agriculture_crop_calendar.csv")
UREA_BASIS_OUT = asset_path(OUTPUTS, "agriculture_urea_basis.csv")
GASES = ("CO2", "CH4", "N2O")

# Agricultural methane is biogenic throughout - enteric, manure, rice - and the CO2e call
# says so explicitly rather than relying on a default that could change under it.
FOSSIL = False

# Managed-soils nitrogen pools, by the subitem strings soils.py writes. Split here rather
# than re-derived from the equations: the labels are what the component carries, so a pool
# renamed upstream fails this map instead of silently landing in the wrong half.
FISCAL_N_POOLS = ("synthetic fertiliser", "crop residues")
LIVESTOCK_N_POOLS = ("organic manure", "pasture deposition", "manure")

# --- the evidence class of the history, DERIVED from the basis already declared ------------
#
# WHY THIS EXISTS AT ALL. These rows shipped with an EMPTY evidence_class - 282 of them
# carrying 1,515.5 Mt, 41.2 per cent of the nine-year mass - and nothing tested it and no
# output published it. It is not a hole this pass opened: the same mass sat unclassified
# across 66 coarser rows before the annual grain was corrected. It is a hole nobody had
# looked into.
#
# NOTHING IS INVENTED HERE. `DRIVER` in fiscal_activity already declares what each category's
# quantity rests on, and core/evidence.py already defines what the classes mean. This is the
# join of those two, written once:
#
#   observed_fiscal      -> E2  "published statistic for this source and period" - the
#                               Economic Survey's own fiscal tables for that year
#   census_anchored_reconstruction -> E3: relative stock changes rescaled to
#                               adopted anchors, not a new enumerated annual count
#
# AND IT IS NOT THE REFERENCE YEAR'S GRADE. The census year is E2 on a livestock ENUMERATION;
# these years are a projection of it. Stamping the reference class here - which is what
# routing through engine.build_components would have done - would claim a count that was
# never taken for eight of the nine years.
BASIS_EVIDENCE = {
    fa.FISCAL_BASIS: "E2",
    fa.CALENDAR_BASIS: "E3",
}

# Managed soils is `observed_fiscal_mixed` because its nitrogen comes from four pools with two
# different bases, so the class is decided per subitem rather than per category. Every subitem
# names its pool, including the indirect terms, which inherit the pool they are computed from.
#
# THIS IS A SEPARATE MATCH FROM `LIVESTOCK_N_POOLS` ABOVE, deliberately. That tuple says
# "pasture deposition", which the DIRECT rows carry and the INDIRECT ones write as
# "(pasture, cattle-type)"; widening it would change what `managed_soils_n_split` reports and
# that figure is pinned by a test for a different claim. Two questions, two vocabularies.
N_POOL_EVIDENCE = (
    ("synthetic fertiliser", "E2"),      # NFDC offtake, a fiscal-year statistic
    ("crop residues", "E2"),             # residue mass from the fiscal crop tables
    ("organic manure", "E3"),            # excretion off projected stocks
    ("pasture", "E3"),                   # deposition off projected stocks
)


# rc39 A7: categories whose class is decided by HOW THE ACTIVITY IS DERIVED rather than by
# which basis the year sits on. The basis join above answers "how current is this activity";
# it cannot answer "is there a published statistic for it at all", and for field burning the
# second question dominates in every year. Burned residue is production x a residue ratio x a
# burned fraction - E3's definition, "derived from a related published quantity" - and no
# statistic for it is published in any year, fiscal basis or calendar. The reference year was
# corrected in the engine at the same time; grading the same method two ways either side of
# 2024 would make the class a property of the year rather than of the method.
DERIVATION_EVIDENCE = {
    "Field burning of residues": "E3",
}


def evidence_class_for(category, subitem):
    """The E class of one history component, from the basis its category declares.

    RAISES on a managed-soils subitem naming no pool, rather than defaulting. A default here
    would silently grade a new nitrogen stream with whatever the fallback happened to be, and
    an unclassified stream is the thing this function exists to end.
    """
    if category in DERIVATION_EVIDENCE:
        return DERIVATION_EVIDENCE[category]
    _driver, basis = fa.DRIVER[category]
    if basis in BASIS_EVIDENCE:
        return BASIS_EVIDENCE[basis]
    lowered = subitem.lower()
    for pool, grade in N_POOL_EVIDENCE:
        if pool in lowered:
            return grade
    raise KeyError(
        "%s / %r names no nitrogen pool, so its evidence class cannot be derived. Add the "
        "pool to N_POOL_EVIDENCE with the basis it actually rests on - do not let it default"
        % (category, subitem))


def _label(fy_end):
    return "FY%d-%02d" % (fy_end - 1, fy_end % 100)


def _components(fy_end, table=None, stocks=None, nitrogen_method=None):
    return build_components(fa.data_for_fiscal_year(fy_end, table=table, stocks=stocks),
                            nitrogen_method=nitrogen_method)


def _co2e(gas, gg):
    return (gwp.to_co2e(gas, gg, "AR5", fossil=FOSSIL) / 1000.0,
            gwp.to_co2e(gas, gg, "AR6", fossil=FOSSIL) / 1000.0)


def _by_category_gas(components):
    """{(category, gas): emissions_Gg} - the engine's own masses, summed, nothing converted."""
    out = {}
    for component in components:
        key = (component["category"], component["gas"])
        out[key] = out.get(key, 0.0) + component["emissions_Gg"]
    return out


def build(table=None, stocks=None):
    """[row] - one per (fiscal year, category, gas) with a non-zero mass."""
    table = table if table is not None else fa.activity()
    stocks = stocks if stocks is not None else calendar_ts._load_history()
    rows = []
    for fy_end in fa.FISCAL_YEARS:
        masses = _by_category_gas(_components(fy_end, table, stocks))
        for category in CATEGORIES:
            driver, basis = fa.DRIVER[category]
            for gas in GASES:
                gg = masses.get((category, gas), 0.0)
                if not gg:
                    continue
                ar5, ar6 = _co2e(gas, gg)
                rows.append({
                    "fiscal_end_year": fy_end,
                    "fiscal_label": _label(fy_end),
                    "category": category,
                    "gas": gas,
                    "emissions_Gg": round(gg, 6),
                    "co2e_Mt_AR5": round(ar5, 6),
                    "co2e_Mt_AR6": round(ar6, 6),
                    "activity_basis": basis,
                    "driver": driver,
                    "driver_source": (fa.livestock_provenance(fy_end) if basis == fa.CALENDAR_BASIS else
                                      "Economic Survey Tables2.3/2.4/2.9; NFDC" +
                                      ("; " + fa.livestock_provenance(fy_end)
                                       if basis == fa.MIXED_BASIS else "")),
                })
    return rows


def series_by_category(rows=None):
    """{fiscal_end_year: {category: (AR5, AR6)}} - what national_series consumes."""
    out = {}
    for row in (rows if rows is not None else build()):
        year = out.setdefault(row["fiscal_end_year"], {})
        ar5, ar6 = year.get(row["category"], (0.0, 0.0))
        year[row["category"]] = (ar5 + row["co2e_Mt_AR5"], ar6 + row["co2e_Mt_AR6"])
    return out


def series_by_gas(rows=None):
    """{fiscal_end_year: {(category, gas): (AR5, AR6)}} - what the annual product consumes."""
    out = {}
    for row in (rows if rows is not None else build()):
        out.setdefault(row["fiscal_end_year"], {})[(row["category"], row["gas"])] = (
            row["co2e_Mt_AR5"], row["co2e_Mt_AR6"])
    return out


def components_for_year(fy_end, table=None, stocks=None, nitrogen_method=None):
    """The engine's own COMPONENT rows for one fiscal year - the grain `build()` throws away.

    THE THIRD SIBLING, and it exists because the first two were not enough. `build()` has
    always computed every component for every year and then collapsed them to (category, gas)
    on its way out, so the subitem detail was produced and discarded on every run. Meanwhile
    `annual_product.components_for` returned None for these years and said in its docstring
    that agriculture's history "is carried by category and gas, not by stream" - which was
    true of the FAOSTAT reconstruction that preceded the seam pass and false of this engine.
    The cost of that stale sentence was the whole of managed soils carried flat for eight
    years while the monthly evidence to shape it sat parsed and validated.

    A SIBLING RATHER THAN A REFACTOR, for the reason the other two already give: the shipped
    series needs the coarse total and the annual product needs the fine one, and merging them
    would put every published digit of the series at the mercy of the finer product.

    NOTHING IS RECOMPUTED. This returns `_components()` - the same call `build()` makes, on
    the same activity - so the finer grain cannot disagree with the coarser one by
    construction. Re-aggregating it reproduces `series_by_gas()` across all 72 year-category-
    gas cells to 5e-7 Mt, which is `build()`'s own six-decimal rounding and not a difference.

    THE EVIDENCE CLASS IS DERIVED FROM THE DECLARED BASIS, not borrowed from the reference
    year. `engine.build_components` stamps the census year's classes and a hard-coded
    `activity_year = 2024`, so routing through it would date FY2015-16 rows to 2024 and claim
    an enumeration that was never taken; that is why this field was left empty when the grain
    was corrected, and why it is filled from `evidence_class_for` now rather than from there.
    See BASIS_EVIDENCE above for the join, which is `DRIVER` and `core/evidence.py` and no
    new judgement.

    `activity_period_kind` IS stamped, because it is not a grade - it is the difference
    between a stock and a flow, and it is what stops a livestock count ever receiving a
    shaped profile. Enteric fermentation and manure ride a stock in every year, censused in
    the reference one and projected in the rest; a projected stock still carries no month.
    """
    from pkinv.sectors.agriculture.engine import ENUMERATED_CATEGORIES

    rows = _components(fy_end, table=table, stocks=stocks, nitrogen_method=nitrogen_method)
    for row in rows:
        row["activity_year"] = fy_end
        row["activity_period_kind"] = ("enumeration"
                                       if row["category"] in ENUMERATED_CATEGORIES
                                       else "span")
        row["evidence_class"] = evidence_class_for(row["category"], row["subitem"])
    return rows


# ---------------------------------------------------------------------------
# What the change cost, decomposed so that two different things stay two numbers
# ---------------------------------------------------------------------------

def _calendar_by_category():
    """{year: {category: AR5}} from the FAOSTAT-calendar history, as it was published."""
    path = asset_path(OUTPUTS, "timeseries_1990_2024.csv")
    out = {}
    for row in _activity_rows(path, comments=False):
        if row["category"] == "TOTAL":
            continue
        total = 0.0
        for gas, column in (("CO2", "CO2_kt"), ("CH4", "CH4_kt"), ("N2O", "N2O_kt")):
            total += gwp.to_co2e(gas, float(row[column] or 0.0), "AR5",
                                 fossil=FOSSIL) / 1000.0
        out.setdefault(int(row["year"]), {})[row["category"]] = total
    return out


def _fiscal_without_cotton(fy_end, table, stocks):
    """The fiscal year rebuilt with cotton dropped - the calendar history's own crop scope.

    This exists so the decomposition is EXACT and additive rather than argued:
        difference = basis_term + scope_term
        scope_term = fiscal - fiscal_without_cotton     (what cotton contributes)
        basis_term = fiscal_without_cotton - calendar   (same four crops, different source
                                                         and different twelve months)
    A single "difference" column would let a reader attribute a scope break to a timing fix,
    and the two have completely different standing: one is a correction, the other is a
    category that was silently missing for eight years.
    """
    data = fa.data_for_fiscal_year(fy_end, table=table, stocks=stocks)
    data.crops = {crop: values for crop, values in data.crops.items() if crop != "cotton"}
    return _by_category_gas(build_components(data))


def basis_change(rows=None, table=None, stocks=None):
    """[row] - per (fiscal year, category): calendar Mt, fiscal Mt, and the two terms.

    THE DIAGNOSTIC THIS REPLACES could not see what it was built for.
    outputs/pakemis_series_splice_agriculture.csv compares the engine against the FAOSTAT
    basis AT THE ANCHOR, where the FAOSTAT-basis series rides the census engine by
    construction, and duly reported about 1e-5 Mt. The break was never at the anchor. It was
    in the eight years before it, where nothing measured it at all.
    """
    table = table if table is not None else fa.activity()
    stocks = stocks if stocks is not None else calendar_ts._load_history()
    fiscal = series_by_category(rows if rows is not None else build(table, stocks))
    calendar = _calendar_by_category()

    out = []
    for fy_end in fa.FISCAL_YEARS:
        no_cotton = _fiscal_without_cotton(fy_end, table, stocks)
        for category in CATEGORIES:
            driver, basis = fa.DRIVER[category]
            fiscal_mt = fiscal[fy_end].get(category, (0.0, 0.0))[0]
            calendar_mt = calendar.get(fy_end, {}).get(category)
            compared = calendar_mt is not None
            without = sum(_co2e(gas, no_cotton.get((category, gas), 0.0))[0]
                          for gas in GASES)
            scope = fiscal_mt - without
            out.append({
                "fiscal_end_year": fy_end,
                "fiscal_label": _label(fy_end),
                "category": category,
                "calendar_faostat_Mt": round(calendar_mt, 6) if compared else "",
                "fiscal_Mt": round(fiscal_mt, 6),
                "difference_Mt": round(fiscal_mt - calendar_mt, 6) if compared else "",
                "basis_term_Mt": round(without - calendar_mt, 6) if compared else "",
                "scope_term_Mt": round(scope, 6),
                "driver": driver,
                "driver_basis": basis,
                "comparison_status": ("compared_to_archived_calendar" if compared else
                                      "archived_calendar_comparator_absent"),
            })
    return out


# The Pakistani cropping calendar, which is the reason the old mapping could not be right for
# every crop at once. A fiscal year FY(Y-1)-Y runs July Y-1 to June Y and therefore contains
# the KHARIF crop sown around June Y-1 and harvested October-December Y-1, and the RABI crop
# sown November Y-1 and harvested April-May Y. FAOSTAT labels each crop by its own harvest
# calendar year. So one fiscal year straddles two FAOSTAT years, and which one depends on the
# season - a fact no single offset can satisfy.
SEASON = {"wheat": "rabi", "rice": "kharif", "maize": "kharif",
          "sugarcane": "kharif", "cotton": "kharif"}
# FAOSTAT reports rice as PADDY and the Economic Survey as milled; the ratio is 0.667 in every
# one of the nine years, to three figures, which is the standard milling outturn rather than a
# disagreement. Recorded so the alignment below compares shapes and not units.
UNIT_RATIO = {("rice", "production_t"): 2.0 / 3.0}


def crop_calendar_alignment():
    """[row] - which FAOSTAT calendar year each fiscal crop cell actually is.

    THE FINDING THIS PASS DID NOT EXPECT. national_series read the FAOSTAT history at the
    fiscal-END year for every crop. Measured against the Economic Survey's own fiscal tables,
    that mapping is right for wheat and wrong BY A FULL YEAR for rice, maize, sugarcane and
    cotton - and the evidence is not an argument about growing seasons, it is that the cells
    agree to 0.01-0.02 percent at the other offset and disagree by 7-9 percent at the one
    that was used.

    What it cost: FY2022-23 - the year of the 2022 floods - was published with 3.64 Mha of
    rice, which is the FOLLOWING year's recovered crop. The actual fiscal-year area was
    2.98 Mha. The floods were averaged out of the published series by an off-by-one.
    """
    table = fa.activity()
    _live, calendar_crops, _nitro = calendar_ts._load_history()
    out = []
    for crop in fa.CROPS:
        for field in ("area_ha", "production_t"):
            scores = {}
            for shift in (0, -1):
                deltas = []
                for fy_end in fa.FISCAL_YEARS:
                    item = ("cotton_bales_000" if crop == "cotton" and field == "production_t"
                            else "%s_%s" % (crop, field))
                    mine = table[fy_end].get(item)
                    theirs = (calendar_crops.get(fy_end + shift, {})
                              .get(crop, {}) or {}).get(field)
                    if not mine or not theirs:
                        continue
                    theirs *= UNIT_RATIO.get((crop, field), 1.0)
                    deltas.append(100.0 * abs(mine - theirs) / theirs)
                if deltas:
                    scores[shift] = sum(deltas) / len(deltas)
            if not scores:
                # Cotton: absent from the calendar history entirely. That IS the answer.
                out.append({"crop": crop, "field": field, "season": SEASON[crop],
                            "mean_abs_pct_at_fiscal_end_year": "",
                            "mean_abs_pct_at_fiscal_start_year": "",
                            "best_offset": "not-in-calendar-history",
                            "offset_the_published_history_used": 0})
                continue
            best = min(scores, key=lambda s: scores[s])
            out.append({
                "crop": crop, "field": field, "season": SEASON[crop],
                "mean_abs_pct_at_fiscal_end_year": round(scores.get(0, float("nan")), 4),
                "mean_abs_pct_at_fiscal_start_year": round(scores.get(-1, float("nan")), 4),
                "best_offset": best,
                "offset_the_published_history_used": 0,
            })
    return out


def livestock_phase_envelope(stocks=None):
    """[row] - what the six-month calendar-to-fiscal phase shift is worth, per year.

    THE NUMBER THAT LICENSES THE COMPROMISE, and it is measured rather than argued. Enteric
    fermentation and manure management keep a calendar-year driver because no fiscal
    enumeration exists. FAOSTAT's stock for calendar year Y is a point on a smooth
    inter-census projection; the fiscal year ending in Y is centred half a year earlier, so
    the phase-corrected stock is the midpoint of Y-1 and Y. Re-driving the two categories on
    that midpoint and differencing gives the error the mapping leaves behind.

    Interpolating is faithful HERE and would not be everywhere: the series being interpolated
    is a deterministic geometric projection off two censuses, not an observation with a shape
    of its own. A linear midpoint on a geometric series understates by less than a tenth of a
    percent at these growth rates, which is far inside the answer's own width.
    """
    live, _crops, _nitro = (stocks if stocks is not None else calendar_ts._load_history())
    table = fa.activity()
    out = []
    for fy_end in fa.FISCAL_YEARS:
        if fy_end == 2024:
            continue
        shifted = dict(live)
        previous = fa.proxy_stocks_for_year(live, fy_end - 1)
        current = fa.proxy_stocks_for_year(live, fy_end)
        shifted[fy_end] = {species: 0.5 * (previous[species] + current[species])
                           for species in calendar_ts.SPECIES}
        as_published = _by_category_gas(_components(fy_end, table, (live, _crops, _nitro)))
        as_shifted = _by_category_gas(_components(fy_end, table, (shifted, _crops, _nitro)))
        for category in ("Enteric fermentation", "Manure management"):
            published = sum(_co2e(gas, as_published.get((category, gas), 0.0))[0]
                            for gas in GASES)
            phase = sum(_co2e(gas, as_shifted.get((category, gas), 0.0))[0] for gas in GASES)
            out.append({
                "fiscal_end_year": fy_end,
                "fiscal_label": _label(fy_end),
                "category": category,
                "published_Mt": round(published, 6),
                "phase_corrected_Mt": round(phase, 6),
                "phase_error_Mt": round(published - phase, 6),
                "phase_error_pct": round(100.0 * (published - phase) / published, 4),
            })
    return out


def managed_soils_n_split(fy_end=2024):
    """(fiscal_share_pct, {pool: Mt}) - what `observed_fiscal_mixed` actually means.

    Managed soils is labelled mixed because its nitrogen comes from four pools and only two
    of them moved to a fiscal basis. The label is held to this measurement by a test, so it
    cannot outlive the arithmetic that justified it.
    """
    components = (build_components(InventoryData()) if fy_end == 2024
                  else _components(fy_end))
    pools = {}
    for component in components:
        if component["category"] != "Managed soils":
            continue
        subitem = component["subitem"].lower()
        side = "livestock"
        if any(pool in subitem for pool in FISCAL_N_POOLS):
            side = "fiscal"
        elif not any(pool in subitem for pool in LIVESTOCK_N_POOLS):
            # Indirect terms (volatilisation, leaching) inherit the mix of the pools they
            # are computed from; counted as mixed rather than assigned to a side by guess.
            side = "indirect"
        pools[side] = pools.get(side, 0.0) + gwp.to_co2e(
            component["gas"], component["emissions_Gg"], "AR5", fossil=FOSSIL) / 1000.0
    direct = pools.get("fiscal", 0.0) + pools.get("livestock", 0.0)
    return (100.0 * pools.get("fiscal", 0.0) / direct if direct else 0.0), pools


# ---------------------------------------------------------------------------

def _write(path, rows, header_lines):
    os.makedirs(OUTPUTS, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        for line in header_lines:
            handle.write("# %s\n" % line)
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def urea_basis_rows(table, stocks):
    """Which urea mass Eq. 11.13 used, per fiscal year, and on what basis (rc39 A3).

    The reference year has NFDC's printed national offtake; the historical years have a fiscal
    total-N figure and no product split, so theirs is reconstructed as N x urea_N_share /
    urea_N_content. The two differ by 0.207% at the reference year, which is small enough to
    hide and large enough to matter at the fifth decimal the release pins - so the basis is
    published per year rather than inferred.

    This table exists INSTEAD of a flag on the component row. core.components v3 is a closed
    schema whose own comment records the reason: a provenance key most sectors omit describes
    the rows that bothered to set it. A per-year table can also say what a per-row flag cannot,
    which is that the historical basis is a limit of the sources rather than a choice.
    """
    from pkinv.sectors.agriculture import liming_urea
    rows = []
    for fy_end in sorted(table):
        data = fa.data_for_fiscal_year(fy_end, table=table, stocks=stocks)
        mass, basis = liming_urea.urea_mass_t(data)
        co2_t = mass * data.efv("liming_urea", "EF_urea") * liming_urea.C_TO_CO2
        # What the reconstruction WOULD have given, published beside what was used. For the
        # historical years the two are the same by construction; for the reference year the
        # difference is the whole reason 3.H changed basis, so it is a column rather than a
        # sentence someone has to keep in step by hand.
        recon = (data.fertilizer["nitrogen_N_offtake"]["value_t"]
                 * data.p("urea_N_share") / data.p("urea_N_content"))
        rows.append({
            "fiscal_year": "FY%d-%s" % (fy_end - 1, str(fy_end)[2:]),
            "fiscal_end_year": fy_end,
            "urea_mass_t": round(mass, 3),
            "urea_activity_basis": basis,
            "reconstruction_t": round(recon, 3),
            "shortfall_of_reconstruction_pct": round(100.0 * (mass - recon) / mass, 6),
            "co2_Mt": round(co2_t / 1e6, 6),
            "source": ("NFDC Annex-5 printed national offtake, Jul-Jun window"
                       if basis == "direct_product_offtake"
                       else "reconstructed from the fiscal total-N figure; no product split "
                            "is published for this year"),
        })
    return rows


def main():
    table = fa.activity()
    stocks = calendar_ts._load_history()
    rows = build(table, stocks)
    _write(SERIES_OUT, rows, [
        "Agriculture fiscal activity, %s to %s." % (_label(min(fa.FISCAL_YEARS)), _label(max(fa.FISCAL_YEARS))),
        "Crops/nitrogen use Economic Survey/NFDC fiscal records; livestock use adopted2024 "
        "anchors and FAOSTAT relative stock changes, with explicit post2024 extrapolation.",
        "activity_basis is a property of each category's DRIVER, not of the sector.",
        "The method is untouched: run_inventory.build_components, as the reference year "
        "calls it. Only the activity varies.",
    ])

    change = basis_change(rows, table, stocks)
    _write(BASIS_OUT, change, [
        "Source/basis change from archived FAOSTAT-level/calendar activity to current "
        "fiscal crops/nutrients and adopted-anchor livestock reconstruction, by year/category.",
        "Where a calendar comparator exists, difference_Mt = basis_term_Mt + scope_term_Mt.",
        "A missing archived calendar comparator is typed, not zero; fiscal mass and the "
        "within-fiscal cotton scope term remain available.",
        "scope_term_Mt is COTTON: the calendar history carried four crops and the reference "
        "year carried five, so cotton's residue burning and residue nitrogen appeared at the "
        "join from nowhere. A source break and a scope break are different claims and are "
        "never summed into one column here.",
        "This measures what outputs/pakemis_series_splice_agriculture.csv could not: that "
        "file compares the two bases AT THE ANCHOR, where they coincide by construction.",
    ])

    _write(UREA_BASIS_OUT, urea_basis_rows(table, stocks), [
        "WHICH UREA MASS Eq. 11.13 USED, PER FISCAL YEAR, AND ON WHAT BASIS (rc39 A3).",
        "direct_product_offtake: NFDC Annex-5's printed national row for the Jul-Jun window.",
        "reconstructed_from_total_N_and_share: N x urea_N_share / urea_N_content, the only "
        "basis available to a year with a total-N figure and no product split.",
        "The two differ by 0.207% at the reference year (6,578,838 t against 6,565,217).",
        "The engine used to reconstruct EVERY year, including the one that has a measurement.",
    ])

    by_category = series_by_category(rows)
    print("agriculture, fiscal basis -> %s" % os.path.relpath(SERIES_OUT))
    print("  %-11s %10s %10s %9s" % ("year", "fiscal Mt", "calendar", "change"))
    calendar = _calendar_by_category()
    for fy_end in fa.FISCAL_YEARS:
        fiscal_total = sum(a for a, _ in by_category[fy_end].values())
        if fy_end in calendar:
            calendar_total = sum(calendar[fy_end].values())
            print("  %-11s %10.5f %10.5f %+9.5f"
                  % (_label(fy_end), fiscal_total, calendar_total,
                     fiscal_total - calendar_total))
        else:
            print("  %-11s %10.5f calendar comparator absent" % (_label(fy_end), fiscal_total))

    print("\nbasis change -> %s" % os.path.relpath(BASIS_OUT))
    backcast = [r for r in change if r["fiscal_end_year"] < 2024
                and r["comparison_status"] == "compared_to_archived_calendar"]
    basis_total = sum(r["basis_term_Mt"] for r in backcast)
    scope_total = sum(r["scope_term_Mt"] for r in backcast)
    print("  %d matched backcast years: basis %+.4f Mt, cotton scope %+.4f Mt"
          % (len({r["fiscal_end_year"] for r in backcast}), basis_total, scope_total))

    alignment = crop_calendar_alignment()
    _write(CALENDAR_OUT, alignment, [
        "WHICH FAOSTAT CALENDAR YEAR EACH FISCAL CROP CELL ACTUALLY IS.",
        "The published history read FAOSTAT at the fiscal-END year for every crop. That is "
        "right for wheat (rabi, harvested inside the fiscal year it is labelled with) and "
        "wrong by a full year for rice, maize, sugarcane and cotton (kharif, harvested in "
        "the preceding calendar year).",
        "The evidence is not an argument about growing seasons: the cells agree to 0.01-0.02 "
        "percent at the other offset and disagree by 7-9 percent at the one that was used.",
        "Rice production is compared after the declared0.667 paddy-to-milled outturn; "
        "differences from later revised fiscal cells remain explicit.",
    ])
    print("\ncrop calendar -> %s" % os.path.relpath(CALENDAR_OUT))
    print("  %-10s %-14s %-8s %10s %10s  %s"
          % ("crop", "field", "season", "at fy_end", "at fy_start", "best"))
    for row in alignment:
        print("  %-10s %-14s %-8s %10s %10s  %s"
              % (row["crop"], row["field"], row["season"],
                 row["mean_abs_pct_at_fiscal_end_year"],
                 row["mean_abs_pct_at_fiscal_start_year"], row["best_offset"]))

    envelope = livestock_phase_envelope(stocks)
    worst = max(abs(r["phase_error_pct"]) for r in envelope)
    print("\nlivestock phase error (the two categories that keep a calendar driver):")
    print("  worst year %.3f%% of the category; %d rows measured" % (worst, len(envelope)))

    share, pools = managed_soils_n_split()
    print("\nmanaged soils nitrogen: %.1f%% of direct N2O from fiscal pools "
          "(%s)" % (share, ", ".join("%s %.3f Mt" % kv for kv in sorted(pools.items()))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

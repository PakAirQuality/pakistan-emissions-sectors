"""Agriculture, resolved into the twelve months of FY2023-24 - on four different bases.

Half the national inventory sits here, and its categories have less in common temporally than
any other module's. Four treatments, and the differences are the substance:

NITROGEN, FROM THE YEAR'S OWN TWELVE MONTHS (Pass 2, the sixteenth review's false-gap
fix). For two releases the reference year's last three months were borrowed from the
opening year and graded T3, on the stated ground that the Annex-7 edition held here runs
April to March - while the same Review's Annex-5 carried all twelve July-to-June months
the whole time. scripts/ingest_nfdc_annex5.py reads them into the Table 3.4 panel under
the page's own three identities, so nfdc_monthly.covers() is true for the reference year
and every month is observed T2; the Annex-7 provincial table is now the CROSS-CHECK
(exact to the tonne July-November; the four-province table runs up to half a percent
under the national ledger thereafter, a boundary difference the test bounds rather than
hides). The borrowed-months branch survives below for any year only Annex-7 reaches.

RICE, FROM THE FLOODED WINDOW. Rice methane is produced while the paddy is flooded and
essentially not otherwise, so the profile is the flooding window itself, from the provincial
crop calendar's transplant and drain weeks. Punjab's window is used and declared: it is the
dominant producing belt, and a national weighted window would need provincial rice areas this
module does not carry. T3 - a process-based profile, not an observation of methane.

ENTERIC FERMENTATION AND MANURE, FLAT BECAUSE THE ACTIVITY HAS NO MONTH. These are 38 percent
of the national inventory and they ride a livestock CENSUS - a stock counted once, which the
component rows declare as activity_period_kind="enumeration". The emission is a continuous
biological process at a roughly constant rate, so equal twelfths is close to right; but the
reason it is flat is that the ACTIVITY carries no timing, not that the emission is known to be
aseasonal. A test asserts no enumeration row ever carries a non-flat profile.

RESIDUE BURNING RIDES THE FIRE RECORD IT ALREADY HELD (rc20). Crop-residue burning is
concentrated in the weeks after harvest, and for two releases the repository held 109,693
VIIRS active-fire detections over the reference year's two burning windows while using them
only as the SPATIAL proxy - the fifteenth review's exact catch. The monthly profile now
reads their acquisition dates: FRP-weighted monthly shares inside the two season windows
(rice stubble Oct 20-Dec 5, wheat residue Apr 10-May 31), zero outside them. Graded T3,
not T2, deliberately: the within-window weights are satellite-OBSERVED, but the windows
themselves are the crop calendar's claim - the fetch was season-scoped, so an out-of-window
zero is calendar-asserted rather than observed. One year's fire record is never carried to
another: a year without a fetched season uses elapsed-day weights at T4. The held
archive supports own-year profiles through FY2024–25; that year's windows were filled
(rc69) from NASA's keyless country-year files (fetch_firms --from-country-archive 2024).
The annual burned mass is estimated independently of monthly timing.

Usage:  python3 -m pkinv.sectors.agriculture.monthly
Writes: outputs/agriculture_monthly_2024.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core import monthly as core_monthly
from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.agriculture import engine, nfdc_monthly
from pkinv.sectors.agriculture.ef_library import InventoryData

FY_START = 2023
ANNEX7 = asset_path(DATA, "nfdc", "annex7_province_month_product_2023-24.csv")
RICE_CALENDAR = asset_path(DATA, "rice_calendar.csv")
FIRMS_FIRE = asset_path(DATA, "gis", "manual", "firms_fire.csv")
OUT = asset_path(OUTPUTS, "agriculture_monthly_2024.csv")

MONTH_NUMBER = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}

# Categories whose activity is a census enumeration rather than a flow over the period.
ENUMERATED = ("Enteric fermentation", "Manure management")
SOILS = ("Managed soils", "Urea application")
RICE = ("Rice cultivation",)
BURNING = ("Field burning of residues",)

# A soils row follows the calendar of the NITROGEN IT CAME FROM, not of the category it is
# reported under. Only the synthetic-fertiliser streams and the urea CO2 ride NFDC's observed
# offtake; the organic-manure and pasture-deposition streams - more than half of Managed soils
# by CO2e - come off the same livestock census as enteric fermentation and have no more month
# than it does, and the crop-residue streams follow a harvest this release does not profile.
# Putting all of them on the fertiliser shape would have closed just as exactly and would have
# claimed an observed monthly basis for 15 Mt of emissions that has none.
SYNTHETIC = ("Direct N2O - synthetic", "Indirect N2O - volatilisation (synthetic",
             "Indirect N2O - leaching/runoff (synthetic", "Urea application", "Liming CO2")

RICE_PROVINCE = "Punjab"


def nitrogen_profile(fy_start=FY_START):
    """({month: share}, {month: T-class}) from NFDC Annex-7 urea offtake.

    Urea alone rather than total product: it is about four fifths of the nitrogen and the only
    product whose N content is a single number, so weighting the twelve months by it is the
    closest thing to weighting them by nitrogen without re-deriving the nutrient split here.
    """
    observed = {}
    for r in _activity_rows(ANNEX7, comments=False):
        # The annex prints the opening months of the NEXT Kharif as well; those months
        # belong to the following year and are the fifteen-month trap the ingest declares.
        if r["season"] == "Kharif2024":
            continue
        key = "%s%02d" % (r["calendar_year"], MONTH_NUMBER[r["month"]])
        observed[key] = observed.get(key, 0.0) + float(r["Urea"] or 0.0)

    weights, method = {}, {}
    for key in core_monthly.months_for(fy_start):
        if key in observed:
            weights[key], method[key] = observed[key], "T2"
        else:
            # April, May and June of the closing year: outside the fertiliser year this
            # edition covers, so the same months of the opening year stand in.
            borrowed = "%d%s" % (int(key[:4]) - 1, key[4:])
            if borrowed not in observed:
                raise KeyError("Annex-7 has neither %s nor %s" % (key, borrowed))
            weights[key], method[key] = observed[borrowed], "T3"
    return core_monthly.normalise(weights), method


def annex7_covers(fy_start=FY_START):
    """Whether the Annex-7 edition held can shape this fiscal year.

    Asked directly rather than by catching what nitrogen_profile raises, because the answer
    used to arrive as an exception and the exception was thrown past RICE. The rice profile
    needs no fertiliser data at all - it is a crop calendar - and for eight of the nine years
    it was discarded on the way out, leaving three percent of the national inventory flat for
    want of a file it does not read.
    """
    try:
        nitrogen_profile(fy_start)
    except (KeyError, OSError):
        return False
    return True


def _rice_area_shares():
    """{province: harvested-area share} from the audited proxy row."""
    for row in _activity_rows(asset_path(DATA, "province_shares.csv"), comments=False):
        if row["proxy"] == "rice_area":
            return {p: float(row[p]) for p in
                    ("Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan")
                    if float(row[p]) > 0}
    raise KeyError("province_shares.csv has no rice_area row")


def rice_profile(fy_start=FY_START):
    """{month: share} - CULTIVATION AREA-DAYS across the provinces, not one window.

    Rewritten at Wave 3 (the sixteenth review's rice item). The previous shape was
    Punjab's flood-to-drain window with each WEEK counting 1.0 through an
    approximate week->month map: 63 flooded days, all of rice methane in
    July-September, while this module's own ANNUAL model integrates emission over an
    area-weighted 125-day cultivation period (data/parameters.csv) and FAO's
    calendar harvests Punjab rice in late October. The docstring's old blocker - "a
    national weighted window would need provincial rice areas this module does not
    carry" - had been false since the MNFSR share row landed.

    Now: per province, the cultivation window transplant_start_week ->
    harvest_end_week as REAL dates (datetime ISO-week arithmetic; the old //30+1
    map drifted a day per month), each month weighted by
    province_area_share x cultivation-days-in-month. The month set follows the
    annual model's own convention (cultivation period, not the flooded subset), so
    the two models finally describe one process. Still T3: a calendar is an
    agronomic proxy, and the within-window weights are day counts, not observed
    methane.

    THE FISCAL BOUNDARY CLIPS THE TRANSPLANT TAIL. Sindh transplants from early
    June, inside the PREVIOUS fiscal year; the annual model books the whole
    season's emission in the fiscal year the season sits in, and the layer
    contract normalises within that year - so cultivation days before July 1 are
    clipped and the season's mass distributes over its in-year days. A declared
    convention (the same one the burning windows use), not a claim that June
    emits nothing.
    """
    import datetime
    calendar = {r["province"]: r for r in _activity_rows(RICE_CALENDAR, comments=False)}
    shares = _rice_area_shares()
    weights = {m: 0.0 for m in core_monthly.months_for(fy_start)}
    for province, share in shares.items():
        if province not in calendar:
            raise KeyError("no rice calendar row for %s" % province)
        row = calendar[province]
        # Rice weeks all fall in the fiscal year's OPENING calendar year (Jun-Nov).
        start = datetime.date.fromisocalendar(
            fy_start, int(row["transplant_start_week"]), 1)
        end = datetime.date.fromisocalendar(
            fy_start, int(row["harvest_end_week"]), 7)
        day = start
        while day <= end:
            key = "%d%02d" % (day.year, day.month)
            if key in weights:
                weights[key] += share
            day += datetime.timedelta(days=1)
    return core_monthly.normalise(weights)


def residue_profile(fy_start=FY_START):
    """{month: share} for returned crop-residue nitrogen: harvest, then mineralization.

    Wave 3 (the sixteenth review's residue item). Returned residue nitrogen reaches
    the soil at HARVEST and releases as it mineralizes - a process with a season and
    a tail, carried flat for want of exactly this model. Per crop: the FAO calendar's
    harvest window (burn_windows.harvest_sessions, the same derivation the burning
    windows use) deposits the crop's returned nitrogen uniformly over its window;
    each day's deposit then releases along an exponential kernel whose e-folding time
    is the declared parameter residue_mineralization_efold_months - a judgement with
    a name and a provenance note, not a fit. Crops are weighted by returned residue
    nitrogen (production x residue_ratio_ag x n_ag_frac x frac_returned, the same
    ledger the annual model closes on).

    THE TAIL FOLDS ACROSS JUNE 30 AT CYCLIC STEADY STATE: the season repeats yearly,
    so the previous season's kernel tail seeds this fiscal year's opening months.
    Implemented as two consecutive identical seasons over a 24-month domain, keeping
    the second year - state across the boundary without carrying one year's DATA
    into another (the windows and weights are the year's own; only the physics of
    decay crosses).

    Graded T3: the windows are a calendar's claim and the kernel a declared
    parameter; nothing here observes a soil.
    """
    import datetime
    import math
    from pkinv.sectors.agriculture import burn_windows
    data = InventoryData()
    tau_months = data.p("residue_mineralization_efold_months")

    weights_by_crop = {}
    for crop, params in data.residue.items():
        production = data.crops.get(crop, {}).get("production_t")
        if not production:
            continue
        returned_n = (production * params["residue_ratio_ag"] * params["n_ag_frac"]
                      * params["frac_returned"])
        if returned_n > 0:
            weights_by_crop[crop] = returned_n
    total_n = sum(weights_by_crop.values())

    # daily release intensity over 24 months (two identical seasons), day-indexed
    # from July 1 of the year BEFORE the fiscal year
    origin = datetime.date(fy_start - 1, 7, 1)
    horizon = (datetime.date(fy_start + 1, 7, 1) - origin).days
    release = [0.0] * horizon
    tau_days = tau_months * 30.436875          # mean month; the kernel's own clock
    for offset_year in (fy_start - 1, fy_start):
        for crop, early, late in burn_windows.harvest_sessions():
            share = weights_by_crop.get(crop, 0.0) / total_n if total_n else 0.0
            if share <= 0:
                continue
            start = burn_windows._anchor(early, offset_year)
            end = burn_windows._anchor(late, offset_year)
            if end < start:
                end = datetime.date(end.year + 1, end.month, end.day)
            window_days = (end - start).days + 1
            day = start
            while day <= end:
                deposited = share / window_days
                day_index = (day - origin).days
                # this day's deposit releases exponentially over the following year
                for lag in range(0, 366):
                    at = day_index + lag
                    if 0 <= at < horizon:
                        release[at] += deposited * (
                            math.exp(-lag / tau_days) - math.exp(-(lag + 1) / tau_days))
                day += datetime.timedelta(days=1)
    # keep the second year - the fiscal year itself, with its predecessor's tail
    weights = {m: 0.0 for m in core_monthly.months_for(fy_start)}
    for index, value in enumerate(release):
        when = origin + datetime.timedelta(days=index)
        key = "%d%02d" % (when.year, when.month)
        if key in weights:
            weights[key] += value
    return core_monthly.normalise(weights)


def firms_covers(fy_start=FY_START):
    """Whether the held FIRMS record has detections inside this fiscal year."""
    try:
        for r in _activity_rows(FIRMS_FIRE, comments=False):
            year, month = int(r["acq_date"][:4]), int(r["acq_date"][5:7])
            fy = year if month >= 7 else year - 1
            if fy == fy_start:
                return True
    except OSError:
        return False
    return False


# A VIIRS detection within this many degrees of a registered kiln is a persistent
# industrial source, not a field: brick kilns burn continuously through the very
# months residue burns, and 11,272 of them are geocoded in the facility registry.
# 0.01 degrees is ~1.1 km - one VIIRS pixel (375 m) plus geolocation error, wide
# enough to catch the plume pixel and narrow enough that a field one village over
# still counts. A declared radius, not a fit.
KILN_EXCLUSION_DEG = 0.01
FACILITY_REGISTRY = asset_path(DATA, "facility_registry.csv")

_kiln_bins_cache = None


def _kiln_bins():
    global _kiln_bins_cache
    if _kiln_bins_cache is None:
        bins = {}
        for r in _activity_rows(FACILITY_REGISTRY, comments=True):
            if "kiln" not in r["facility_id"].lower() or not r["latitude"]:
                continue
            lat, lon = float(r["latitude"]), float(r["longitude"])
            key = (round(lat / KILN_EXCLUSION_DEG),
                   round(lon / KILN_EXCLUSION_DEG))
            bins.setdefault(key, []).append((lat, lon))
        _kiln_bins_cache = bins
    return _kiln_bins_cache


def _near_kiln(lat, lon):
    bins = _kiln_bins()
    base = (round(lat / KILN_EXCLUSION_DEG), round(lon / KILN_EXCLUSION_DEG))
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for klat, klon in bins.get((base[0] + dy, base[1] + dx), ()):
                if abs(klat - lat) < KILN_EXCLUSION_DEG \
                        and abs(klon - lon) < KILN_EXCLUSION_DEG:
                    return True
    return False


_cropland_cache = None


def _cell_state(lat, lon):
    """"outside_pakistan" | "cropland" | "non_cropland" for the cell under a point.

    The distinction matters more than it looks: the fetch BBOX is a rectangle over
    Pakistan that necessarily includes INDIAN Punjab, whose November stubble fires
    are the subcontinent's largest - and the pre-Wave-3 profile, which applied no
    spatial filter at all, was weighting Pakistan's burning months by India's
    fires. The cropland test rides the same WorldCover-derived raster the spatial
    allocation uses (data/gis/proxy_cropland_267x340.npy on core.gis.grid's own
    transform), and the grid's district_id supplies the national mask, so the
    temporal attribution, the spatial proxy and the country boundary are one set
    of facts."""
    global _cropland_cache
    if _cropland_cache is None:
        import numpy as np
        from pkinv.core.gis.grid import RES, build_grid
        grid = build_grid()
        raster = np.load(asset_path(DATA, "gis", "proxy_cropland_267x340.npy"))
        _cropland_cache = (grid, raster, RES)
    grid, raster, res = _cropland_cache
    minx, _miny, _maxx, maxy = grid.bounds
    row = int((maxy - lat) / res)
    col = int((lon - minx) / res)
    if not (0 <= row < raster.shape[0] and 0 <= col < raster.shape[1]):
        return "outside_pakistan"
    if grid.district_id[row, col] < 0:
        return "outside_pakistan"
    return "cropland" if raster[row, col] > 0 else "non_cropland"


def burning_attribution(fy_start=FY_START):
    """(monthly FRP weights of ATTRIBUTED detections, counts dict) for one year.

    Wave 3's attribution ladder, each rung a filter a detection must pass to time
    residue burning: inside a crop's own FAO-derived burning window
    (burn_windows - the same objects that scoped the fetch, so nothing can be
    attributed where nothing was fetched); on cropland (the spatial proxy's own
    raster); and away from registered kilns (persistent industrial fires burn
    through exactly these months). What fails a rung is COUNTED, never forced -
    the counts publish through the burning cross-check."""
    # rc42 (S-3): the ladder lives in pkinv.core.gis.firms and the spatial raster walks the
    # SAME attributed set with the same weight; the counts published here are the counts
    # the raster's description carries.
    from pkinv.core.gis import firms
    from pkinv.sectors.agriculture import burn_windows
    windows = burn_windows.windows(fy_start)
    weights = {m: 0.0 for m in core_monthly.months_for(fy_start)}
    hits, counts = firms.attribute(fy_start, lambda when: burn_windows.in_window(windows, when))
    for _row, _col, frp, key in hits:
        if key in weights:
            weights[key] += frp
    return weights, counts


def burning_profile(fy_start=FY_START):
    """{month: share} for residue burning, FRP-weighted from the held VIIRS record.

    FRP (fire radiative power) is proportional to the combustion rate, so weighting
    detections by it makes the monthly share track burned MASS rather than fire
    COUNT - the same basis the spatial proxy already uses. Months outside the
    crop windows carry zero by the calendar's claim, not by observation, and the
    attribution filters (burning_attribution) are proxies for what a field is;
    both asymmetries are why the profile is T3 and not T2."""
    weights, _counts = burning_attribution(fy_start)
    if not any(weights.values()):
        raise KeyError("no attributed FIRMS detections inside FY%d-%02d"
                       % (fy_start, (fy_start + 1) % 100))
    return core_monthly.normalise(weights)


def published_nitrogen_profile(fy_start=FY_START):
    """(weights, method, basis) - THE published fertiliser profile, one selection.

    Table 3.4 first, because it is published on THIS inventory's fiscal year and
    needs no borrowing; the Annex-7 path borrows April-June and exists only for a
    year Table 3.4 does not cover; otherwise flat with the reason. This selection
    used to live inline in rows() while the monthly CROSSCHECK called the Annex-7
    helper directly - two vintages of the same profile in one repository, and the
    seventeenth review read the crosscheck's borrowed-months labels beside the
    limitations section's correct "no borrowed months" and called it the
    contradiction it was. One selector, both consumers (rc28)."""
    flat = core_monthly.days_weighted_profile(fy_start)
    if nfdc_monthly.covers(fy_start):
        nitrogen, nitrogen_method = nfdc_monthly.profile(fy_start)
        nitrogen_basis = ("NFDC %s urea offtake by month, the year's own "
                          "July-June fiscal months; no month borrowed"
                          % nfdc_monthly.source_name(fy_start))
    elif annex7_covers(fy_start):
        nitrogen, nitrogen_method = nitrogen_profile(fy_start)
        nitrogen_basis = ("NFDC Annex-7 urea offtake by month; April-June borrowed from the "
                          "opening year")
    else:
        # One year's offtake is not another's. Carrying this shape across would be exactly
        # the borrowing cement's QIM profile is graded TE4 for, and it would be borrowing a
        # shape that moves: sowing dates, water and import arrivals all shift it year to year.
        nitrogen, nitrogen_method = flat, "T4"
        nitrogen_basis = ("flat: the NFDC Annex-7 edition held does not reach this fiscal "
                          "year, and one year's offtake shape is not carried to another")
    return nitrogen, nitrogen_method, nitrogen_basis


def rows(data=None, fy_start=FY_START):
    data = data if data is not None else InventoryData()
    components = engine.build_components(data)
    # Days-weighted, not equal twelfths: these streams declare no seasonality, which
    # is a claim about the SOURCE and not a licence to mis-divide the calendar.
    flat = core_monthly.days_weighted_profile(fy_start)
    rice = rice_profile(fy_start)
    nitrogen, nitrogen_method, nitrogen_basis = published_nitrogen_profile(fy_start)

    def synthetic(c):
        return c["category"] in SOILS and c["subitem"].startswith(SYNTHETIC)

    def residue_nitrogen(c):
        # the two Managed-soils subitems the mineralization kernel times (Wave 3);
        # MUST be tested before livestock_nitrogen - the plans loop does not
        # de-duplicate, so overlapping predicates double-count
        return (c["category"] in SOILS and
                c["subitem"].startswith(("Direct N2O - crop residues",
                                         "Indirect N2O - leaching/runoff (crop residues")))

    def livestock_nitrogen(c):
        return c["category"] in SOILS and not synthetic(c) and not residue_nitrogen(c)

    residue = residue_profile(fy_start)
    plans = [
        (synthetic, nitrogen,
         (lambda _c, m: nitrogen_method[m]) if isinstance(nitrogen_method, dict)
         else nitrogen_method,
         nitrogen_basis),
        (residue_nitrogen, residue, "T3",
         "harvest windows from the FAO calendar followed by an exponential "
         "nitrogen-mineralization kernel (declared e-folding, "
         "residue_mineralization_efold_months); the prior season's tail folds across "
         "the fiscal boundary at cyclic steady state"),
        (livestock_nitrogen, flat, "T4",
         "flat: this nitrogen is deposited or applied off a livestock census "
         "enumeration and carries no month of its own"),
        (RICE, rice, "T3",
         "cultivation area-days across the provincial rice calendars (transplant to "
         "harvest end), harvested-area weighted; June transplant days clipped at the "
         "fiscal boundary by declared convention"),
        (ENUMERATED, flat, "T4",
         "flat: the activity is a livestock census enumeration and carries no month"),
        (BURNING,) + ((burning_profile(fy_start), "T3",
         "VIIRS active-fire acquisition dates inside the year's own FAO-derived crop "
         "burning windows, FRP-weighted and attribution-filtered (national mask, "
         "cropland raster, kiln exclusion - burning_attribution; the unfiltered "
         "record is dominated by Indian Punjab's fires inside the fetch box); "
         "within-window weights observed, windows and filters calendar- and "
         "proxy-asserted - which is why this is T3, not T2")
        if firms_covers(fy_start) else (flat, "T4",
         "flat: the held VIIRS fire record has no season fetched inside this fiscal "
         "year, and one year's fire record is never carried to another "
         "(acquisition: FIRMS archive API, windows per burn_windows.py)")),
    ]
    out, seen = [], set()
    for which, shares, method, basis in plans:
        members = [c for c in components
                   if (which(c) if callable(which) else c["category"] in which)]
        seen.update(id(c) for c in members)
        if members:
            out.extend(core_monthly.apply_profile(members, shares, fy_start,
                                                  temporal_method=method, basis=basis))
    unplanned = [c for c in components if id(c) not in seen]
    if unplanned:
        raise KeyError("no monthly treatment declared for %s"
                       % sorted({c["category"] for c in unplanned}))
    return components, out


def main():
    components, month_rows = rows()
    core_monthly.write_layer(OUT, month_rows, components)
    shares = {}
    for r in month_rows:
        shares[r["temporal_method"]] = shares.get(r["temporal_method"], 0.0) + r["co2e_Mt_AR5"]
    total = sum(shares.values())
    print("agriculture monthly layer -> %s" % OUT)
    print("  %d rows; closes exactly" % len(month_rows))
    for cls in sorted(shares):
        print("    %s %5.1f%% of the sector" % (cls, 100 * shares[cls] / total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

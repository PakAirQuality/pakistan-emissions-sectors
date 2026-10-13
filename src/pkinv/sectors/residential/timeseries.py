"""The residential time series, 2016-2025 - and the matched years the comparisons owed.

WHAT MOVES AND WHAT IS HELD, STREAM BY STREAM. Gas rides a transcribed nine-edition
OGRA series (one interpolated year, labelled in the data file). Dung rides the two HIES
rounds exactly as firewood does (rc67: the survey is the reference for household dung;
through rc66 it rode the livestock series through the nitrogen ledger, which now carries
configuration L). Firewood rides the two HIES
rounds: per-household quantity interpolated between 2018-19 and 2024-25, household
count from the census-interpolated population on each round's own persons-per-
household, per-household quantity held flat before the first round (a labelled
assumption, not a trend claim - FAOSTAT is never used as one). Crop residues ride the
crop production series through the ledger's fixed fractions. LPG, kerosene, coal,
charcoal and generators - together under four percent of the sector - are HELD at
their reference values with basis flags; their OGRA/OCAC archive series is recorded
as remaining work, not silently pretended.

WHY THE SERIES STARTS AT 2016. The OGRA State-of-Industry archive held here starts at
FY2015-16; before that the gas control has no source in this repository. A biomass-only
series would reach back decades on the livestock and crop files, but publishing a
'sector' series whose largest CO2 stream is missing would mislead more than inform -
so the sector series is exactly as long as its weakest measured stream.

THE MATCHED YEARS ARE THE POINT. A calendar inventory year straddles two fiscal years;
matched values are the mean of the two, stated as such. matched_cy(2022) upgrades the
CRT comparison from UNMATCHED YEAR to a straddle-mean; matched_cy(2021) gives the CCAC
bridge the matched-2021 PM2.5 its year wedge was declared to await.

NO SEASONALITY HERE. Monthly profiles are a separate, synthetic-labelled layer
(monthly.py) constrained to these annual totals.

Usage:  python3 -m pkinv.sectors.residential.timeseries
Writes: outputs/residential_timeseries.csv
"""
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.residential import combustion, hies
from pkinv.sectors.residential.data import ResidentialData
from pkinv.activity.store import read_rows
from pkinv.assets import asset_path

HISTORY = asset_path(DATA, "activity", "residential", "fuel_supply_history.csv")
POP_CSV = asset_path(DATA, "activity", "waste", "population_district.csv")
CROPS = asset_path(DATA, "activity", "historical", "crops.csv")

YEARS = tuple(range(2016, 2025))     # FY2015-16 .. FY2023-24, the OGRA archive's span
# HIES anchors: fiscal-year label of each round, weighted households, firewood kg.
HIES_ANCHORS = {2019: {"households": 33.2e6}, 2025: {"households": 39.9e6}}


def _read(path):
    return read_rows(path, comments=False)


def gas_mmcfd():
    """{fiscal_year: MMCFD} from the transcribed OGRA series."""
    return {int(r["fiscal_year"]): float(r["quantity"]) for r in _read(HISTORY)
            if r["fuel"] == "Natural Gas"}


def _population():
    pop = {}
    for r in _read(POP_CSV):
        pop[int(r["year"])] = pop.get(int(r["year"]), 0.0) + float(r["pop_total"])
    last = max(pop)
    growth = pop[last] / pop[last - 1]
    for y in range(last + 1, 2026):        # extend the census interpolation's trend
        pop[y] = pop[y - 1] * growth
    return pop


def households(year):
    """Household count: HIES rounds anchor persons-per-household; the census
    population carries the shape between and before them."""
    pop = _population()
    pph = {y: pop[min(y, max(pop))] / a["households"]
           for y, a in HIES_ANCHORS.items()}
    y0, y1 = sorted(HIES_ANCHORS)
    if year <= y0:
        return pop[year] / pph[y0]
    if year >= y1:
        return pop[min(year, max(pop))] / pph[y1]
    w = (year - y0) / (y1 - y0)
    return pop[year] / (pph[y0] * (1 - w) + pph[y1] * w)


def firewood_air_dry_kg(year):
    """Per-household firewood between the two survey rounds, held flat outside them."""
    per_hh = {y: hies.firewood_air_dry_kg(s) / households(y)
              for y, s in ((2019, "hies2019"), (2025, "hies2025"))}
    y0, y1 = 2019, 2025
    if year <= y0:
        rate = per_hh[y0]
    elif year >= y1:
        rate = per_hh[y1]
    else:
        w = (year - y0) / (y1 - y0)
        rate = per_hh[y0] * (1 - w) + per_hh[y1] * w
    return rate * households(year)


def dung_survey_air_dry_kg(year):
    """The SURVEY-anchored dung series, THE REFERENCE since rc67: per-household cake
    between the two HIES rounds, firewood's exact construction. It began as the air
    panel's second configuration (L_HERD1624); it is now what the greenhouse-gas and
    air products both burn.

    Two anchors, not nine observations: HIES 2018-19 reports 6.50 Mt air-dry and
    2024-25 reports 11.97 Mt, an 84 percent jump between rounds. Much of it is a few
    large reports: the top 5 percent of reporting households hold 44.7 percent of the
    2024-25 total against 19.6 percent in 2018-19 (hies_diagnostics.csv). The series
    INTERPOLATES between the rounds per household and holds the 2019 per-household
    rate flat before the first anchor. Every consumer labels the years accordingly
    (survey_anchored_interpolation between the anchors,
    survey_anchored_extrapolated_flat before 2019). The ledger series (herd-scaled
    nitrogen, herd_scale) carries configuration L."""
    per_hh = {y: hies.national_quantity("dung_cake", s)[0] / households(y)
              for y, s in ((2019, "hies2019"), (2025, "hies2025"))}
    y0, y1 = 2019, 2025
    if year <= y0:
        rate = per_hh[y0]
    elif year >= y1:
        rate = per_hh[y1]
    else:
        w = (year - y0) / (y1 - y0)
        rate = per_hh[y0] * (1 - w) + per_hh[y1] * w
    return rate * households(year)


def dung_survey_basis(year):
    """The activity-basis label the survey dung series carries for one year."""
    if year <= 2019:
        return "survey_anchored_extrapolated_flat"
    return "survey_anchored_interpolation"


_HERD_SCALE = {}


def herd_scale(year):
    """Diverted dung relative to the reference year: agriculture's own diversion for that
    fiscal year over the reference year's.

    rc67: this used to scale the reference year's diverted nitrogen by the cattle and
    buffalo head counts of the stock series, which tracked agriculture's fiscal back-cast
    to within 0.2 per cent and not exactly. The dung fate account
    (report.dung_variants.price) re-runs agriculture for each year, so two products
    carried two diverted masses for the same year. Both now read the same engine: the
    volatile solids agriculture diverts as fuel in that year. Beyond the reference year
    the reference herd is held."""
    data = ResidentialData()
    y = min(int(year), data.year)
    if y == data.year:
        return 1.0
    if y not in _HERD_SCALE:
        from pkinv.sectors.agriculture import fiscal_activity
        from pkinv.sectors.agriculture.ef_library import InventoryData
        _HERD_SCALE[y] = (
            combustion.dung_vs_kg(data, fiscal_activity.data_for_fiscal_year(y))
            / combustion.dung_vs_kg(data, InventoryData()))
    return _HERD_SCALE[y]


def residue_scale(year):
    """Ledger fuel mass relative to the reference year: production is the only lever."""
    from pkinv.sectors.agriculture import residue_ledger
    from pkinv.sectors.agriculture.ef_library import InventoryData
    agri = InventoryData()
    led = residue_ledger.ledger(agri)
    crops = {}
    for r in _read(CROPS):
        crops.setdefault(int(r["year"]), {})[r["crop"]] = float(r["production_t"])
    y = min(year, max(crops))
    ref_y = max(crops)
    num = den = 0.0
    for crop, row in led.items():
        if crop in crops[y] and crop in crops[ref_y]:
            num += row["fuel"] * crops[y][crop] / crops[ref_y][crop]
            den += row["fuel"]
    return num / den


def fuel_TJ_series(data=None, dung_basis=None):
    """{year: {stream: TJ, ..., "_basis": {stream: basis}}} for the series years.

    dung_basis None is the reference (the survey series); "ledger" is configuration L,
    the diverted dung of each year's own herd."""
    data = data or ResidentialData()
    dung_basis = combustion.reference_basis(dung_basis)
    ref = combustion.fuel_TJ(data, dung_basis=dung_basis)
    gas = gas_mmcfd()
    out = {}
    for y in YEARS:
        if y == data.year:
            # The reference year IS the engine - byte-identical, never re-derived, so
            # the series can never disagree with the reported sector at its own year.
            tj = dict(ref)
            tj["_basis"] = {s: "reference year - the engine's own values"
                            for s in ref}
            out[y] = tj
            continue
        tj = {}
        basis = {}
        tj["Natural gas"] = gas[y] * 365.0 * data.p("gas_mmcf_to_TJ")
        basis["Natural gas"] = ("OGRA series"
                                if y != 2021 else "OGRA series (2021 interpolated)")
        tj["Firewood"] = (firewood_air_dry_kg(y) / 1e6
                          * data.efv("residential_ncv", "Wood/Wood Waste"))
        basis["Firewood"] = ("HIES rounds interpolated" if 2019 <= y <= 2025
                             else "per-household held at nearest HIES round")
        if dung_basis == "survey":
            tj["Dung cake"] = (ref["Dung cake"] * dung_survey_air_dry_kg(y)
                               / dung_survey_air_dry_kg(data.year))
            basis["Dung cake"] = ("HIES rounds interpolated" if y > 2019
                                  else "per-household held at the first HIES round")
        else:
            tj["Dung cake"] = ref["Dung cake"] * herd_scale(y)
            basis["Dung cake"] = "herd-scaled nitrogen ledger (rates and shares held)"
        tj["Crop residues"] = ref["Crop residues"] * residue_scale(y)
        basis["Crop residues"] = "crop production series through the fixed ledger"
        for stream in ("LPG", "Kerosene", "Coal", "Charcoal", "Generators"):
            tj[stream] = ref[stream]
            basis[stream] = "HELD at reference value (archive series not transcribed)"
        tj["_basis"] = basis
        out[y] = tj
    return out


def components_for_year(data, year, dung_basis=None):
    """Component-shaped rows for one series year, by LINEAR SCALING of the engine's own rows.

    At the reference year this returns engine.build_components(data) verbatim - exactness by
    construction, asserted by tests/test_national_series.py. For any other year, each of the
    engine's 23 rows is scaled by its stream's fuel ratio tj[year]/tj[reference]: every
    emission row is linear in its stream's TJ with all factors held, so scaling IS the
    reference factor arithmetic applied to the year's fuel - one arithmetic path, not a
    second implementation that could drift from the first. AR5 and AR6 both scale, so the
    series gets both metrics without restating a GWP anywhere (the local co2e_Mt above
    hardcodes AR5 factors and is kept only for the legacy series file).

    The biogenic CO2 memo stays excluded for the same reason it is excluded from the engine:
    these are the engine's rows, scaled.
    """
    from pkinv.sectors.residential import engine
    reference_rows = engine.build_components(data, dung_basis=dung_basis)
    if year == data.year:
        return reference_rows
    series = fuel_TJ_series(data, dung_basis)
    if year not in series:
        raise KeyError("residential series covers %d-%d; %d requested"
                       % (min(YEARS), max(YEARS), year))
    tj, ref = series[year], series[data.year]
    out = []
    for row in reference_rows:
        stream = row["subitem"].rsplit(" ", 1)[0]
        if stream not in tj:
            raise KeyError("engine row %r names stream %r, which the fuel series does not "
                           "carry - the scaling would silently drop it"
                           % (row["subitem"], stream))
        ratio = tj[stream] / ref[stream] if ref[stream] else 0.0
        scaled = dict(row)
        for field in ("emissions_Gg", "co2e_Mt_AR5", "co2e_Mt_AR6"):
            scaled[field] = row[field] * ratio
        scaled["activity_year"] = year
        out.append(scaled)
    return out


def basis_for_year(data, year):
    """{stream: basis prose} for the series' held_constant column."""
    return fuel_TJ_series(data)[year]["_basis"]


def co2e_Mt(data, tj):
    """AR5 Mt CO2e for one year's fuel dict, the reference year's factor arithmetic."""
    total = 0.0
    for stream, item, _ad in combustion.FOSSIL_FUELS:
        t = tj[stream]
        total += t * data.efv("residential_combustion_co2", item) / 1e9
        total += t * data.efv("residential_combustion_ch4", item) / 1e9 * 30.0
        total += t * data.efv("residential_combustion_n2o", item) / 1e9 * 265.0
    for stream, item, _ad, _g in combustion.BIOMASS_FUELS:
        t = tj[stream]
        total += t * data.efv("residential_combustion_ch4", item) / 1e9 * 28.0
        total += t * data.efv("residential_combustion_n2o", item) / 1e9 * 265.0
    return total


WORD_OF = {"Natural": "Natural gas", "LPG": "LPG", "Kerosene": "Kerosene",
           "Coal": "Coal", "Dung": "Dung cake", "Firewood": "Firewood",
           "Charcoal": "Charcoal", "Crop": "Crop residues"}


def air_kt(data, tj, year_tj_ref=None):
    """{(stream, pollutant): kt} for one year: each stream's reference air rows scaled
    by its fuel ratio.

    Valid because every air row is linear in its stream's mass and the factors are
    held; the scaling preserves exactly the reference year's factor choices. A species
    a stream does not emit at the reference (fossil NH3, EMEP's own not-applicable) is
    ABSENT from the dict, never zero - the nine-year panel writes it as its notation
    key. The generators omission rides through unchanged: no reference rows, no series.
    """
    from pkinv.sectors.residential import air_pollutants
    ref = year_tj_ref or combustion.fuel_TJ(data)
    out = {}
    for r in air_pollutants.compute(data):
        stream = WORD_OF[r["subitem"].split()[0]]
        key = (stream, r["pollutant"])
        out[key] = out.get(key, 0.0) + r["emissions_kt"] * tj[stream] / ref[stream]
    return out


def pm25_kt(data, tj, year_tj_ref=None):
    """PM2.5 for one year - the summed PM2.5 slice of air_kt, kept as the interface the
    timeseries table and the matched-CY comparison already publish."""
    return sum(kt for (_stream, pol), kt in air_kt(data, tj, year_tj_ref).items()
               if pol == "PM2.5")


def matched_cy(cal_year, data=None, series=None):
    """Straddle-mean values for a calendar inventory year: the mean of the two fiscal
    years it spans, stated as such - a bound, not a point match."""
    data = data or ResidentialData()
    series = series or fuel_TJ_series(data)
    fy = (cal_year, cal_year + 1)
    tj_pair = [series[y] for y in fy]
    return {
        "calendar_year": cal_year, "fiscal_years": "FY%d-%02d and FY%d-%02d" % (
            fy[0] - 1, fy[0] % 100, fy[1] - 1, fy[1] % 100),
        "co2e_Mt_AR5": sum(co2e_Mt(data, t) for t in tj_pair) / 2.0,
        "pm25_kt": sum(pm25_kt(data, t) for t in tj_pair) / 2.0,
        "gas_TJ": sum(t["Natural gas"] for t in tj_pair) / 2.0,
    }


def write_configurations_by_year(data, series):
    """outputs/residential_configurations_by_year.csv - the nine-year sibling of the
    reference-year configurations register, so the two dung series reconcile against
    something SHIPPED: per (fiscal_end_year, configuration), the dung mass, its basis
    label, and the dung-stream PM2.5.

    The reference is the two-anchor HIES interpolation, and its basis column says which
    years are interpolation and which the flat pre-anchor extrapolation. Configuration L
    is the herd-scaled nitrogen ledger: all the dung agriculture diverts in that year."""
    from pkinv.core import configurations as conf
    from pkinv.sectors.residential import air_pollutants as res_ap

    def dung_pm(rows):
        return sum(r["emissions_kt"] for r in rows
                   if r["pollutant"] == "PM2.5" and r["subitem"].startswith("Dung"))

    dung_pm_s = dung_pm(res_ap.compute(data, dung_basis="survey"))
    dung_pm_l = dung_pm(res_ap.compute(data, dung_basis="ledger"))
    ledger_ref_kg = combustion.dung_air_dry_kg(data, None, "ledger")
    survey_ref_kg = dung_survey_air_dry_kg(data.year)
    path = asset_path(OUTPUTS, "residential_configurations_by_year.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["fiscal_end_year", "configuration_id", "dung_air_dry_Mt",
                    "dung_activity_basis", "dung_pm25_kt"])
        for y in YEARS:
            kg = dung_survey_air_dry_kg(y)
            w.writerow([y, conf.REFERENCE, round(kg / 1e9, 4),
                        dung_survey_basis(y),
                        round(dung_pm_s * kg / survey_ref_kg, 3)])
            scale_l = 1.0 if y == data.year else herd_scale(y)
            w.writerow([y, conf.LEDGER_SERIES,
                        round(ledger_ref_kg * scale_l / 1e9, 4),
                        "herd_scaled_nitrogen_ledger",
                        round(dung_pm_l * scale_l, 3)])
    print("configurations by year -> %s" % os.path.relpath(path))


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = ResidentialData()
    series = fuel_TJ_series(data)
    write_configurations_by_year(data, series)
    streams = ("Natural gas", "Firewood", "Dung cake", "Crop residues", "LPG",
               "Kerosene", "Coal", "Charcoal", "Generators")
    with open(asset_path(OUTPUTS, "residential_timeseries.csv"), "w",
              newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fiscal_year"] + ["%s_TJ" % s for s in streams]
                   + ["co2e_Mt_AR5", "pm25_kt", "basis_notes"])
        for y in YEARS:
            tj = series[y]
            w.writerow([y] + [round(tj[s], 1) for s in streams]
                       + [round(co2e_Mt(data, tj), 5),
                          round(pm25_kt(data, tj), 2),
                          "; ".join(sorted(set(tj["_basis"].values())))])
    print("Residential time series FY2016-FY2025:")
    for y in YEARS:
        print("  FY%d-%02d  %7.0f TJ gas  %6.2f Mt CO2e  %6.1f kt PM2.5"
              % (y - 1, y % 100, series[y]["Natural gas"],
                 co2e_Mt(data, series[y]), pm25_kt(data, series[y])))
    for cy in (2021, 2022):
        m = matched_cy(cy, data, series)
        print("  matched CY%d (%s): %.2f Mt CO2e, %.1f kt PM2.5"
              % (cy, m["fiscal_years"], m["co2e_Mt_AR5"], m["pm25_kt"]))


if __name__ == "__main__":
    main()

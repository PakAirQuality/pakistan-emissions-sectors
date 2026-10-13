"""SYNTHETIC monthly profiles for the residential year - shape, never magnitude.

EVERY PROFILE HERE IS LABELLED SYNTHETIC. No Pakistani monthly household fuel
statistic exists (OGRA's gas is the exception a future upgrade can transcribe from
its monthly system reports); these profiles are a declared end-use model on measured
degree-days, and each month row carries the label so no downstream user mistakes a
shape for a measurement. The constraint that IS hard: every stream's twelve months sum
exactly to its annual total, asserted on every run.

THE MODEL. Each fuel splits into a flat base load (cooking, water heating, lighting)
and a climate-shaped remainder: heating load follows the province-emission-weighted
HDD-18 shape (NASA POWER monthly T2M, data/activity/residential/
monthly_degree_days.csv), and the generator stream follows the CDD-24 shape instead -
gensets run against summer load-shedding, the one household fuel whose season is the
inverse of the others. The heating fractions are DECLARED JUDGEMENT per fuel, stated
in HEATING_FRACTION with the reasoning inline; OGRA's own vintage note (domestic gas
'peaks in winter') and the CRT's gaseous seasonality are the qualitative anchors.

Usage:  python3 -m pkinv.sectors.residential.monthly
Writes: outputs/residential_monthly_2024.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core import monthly as core_monthly
from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.residential import air_pollutants, combustion, downscale
from pkinv.sectors.residential.data import ResidentialData

DD_CSV = asset_path(DATA, "activity", "residential", "monthly_degree_days.csv")
LABEL = "SYNTHETIC PROFILE"

# core.evidence: a process-based seasonal profile on measured degree-days. NOT T1 - the
# degree-days are observed, the fuel split across them is not. The distinction is the whole
# reason the label above is printed on every row.
TEMPORAL_METHOD = "T3"

FY_START = 2023          # FY2023-24, the residential reference year

# fuel -> fraction of the annual quantity that follows the heating (HDD) shape; the
# rest is flat. Generators are CDD-shaped instead (load-shedding season).
HEATING_FRACTION = {
    "Natural gas": 0.40,   # cooking+water heat year-round; strong winter space/water peak
    "Firewood": 0.30,      # cooking-dominated; northern space heating in winter
    "Dung cake": 0.30,     # as firewood; cake is stockpiled and burned through winter
    "Crop residues": 0.30, # harvest-linked in reality; heating shape is the declared proxy
    "LPG": 0.25,           # winter uptake where gas pressure drops
    "Kerosene": 0.20,
    "Coal": 0.50,          # the most heating-shaped solid fuel where it survives
    "Charcoal": 0.20,
    "Generators": None,    # CDD-shaped: summer outages, not winter cold
}


def _months(fy_start=FY_START):
    return core_monthly.months_for(fy_start)


def degree_day_shapes(data=None, fy_start=FY_START):
    """(hdd_shape, cdd_shape): {month: fraction}, each summing to 1, weighted by each
    province's share of the sector so Punjab's winter counts more than Quetta's.

    THE YEAR IS THE ARGUMENT THAT MATTERS. This read whatever months the degree-day file
    held and ignored the caller's year, which was harmless only while the file held one
    fiscal year. It holds ten now, and the thing being read is exactly the thing that
    varies between them: Lahore's heating demand runs from 179 to 482 HDD across these
    years, a factor of 2.7. Borrowing a winter is the least defensible borrowing available
    to this sector, so the months are selected here and a missing one raises.
    """
    data = data or ResidentialData()
    from pkinv.sectors.residential import engine
    shares = downscale.load_shares()
    comps = engine.build_components(data)
    prov_weight = {}
    for c in comps:
        proxy = downscale.proxy_for(c)
        for p, s in shares[proxy].items():
            prov_weight[p] = prov_weight.get(p, 0.0) + c["co2e_Mt_AR5"] * s
    tot = sum(prov_weight.values())
    prov_weight = {p: v / tot for p, v in prov_weight.items()}

    months = _months(fy_start)
    hdd = {m: 0.0 for m in months}
    cdd = {m: 0.0 for m in months}
    seen = set()
    for r in _activity_rows(DD_CSV, comments=False):
        if r["month"] not in hdd:
            continue
        w = prov_weight.get(r["province"], 0.0)
        hdd[r["month"]] += w * float(r["hdd18"])
        cdd[r["month"]] += w * float(r["cdd24"])
        seen.add(r["month"])
    missing = sorted(set(months) - seen)
    if missing:
        raise ValueError("no degree days for %s; run scripts/fetch_hdd.py rather than "
                         "letting a fiscal year borrow another one's winter" % missing)
    return core_monthly.normalise(hdd), core_monthly.normalise(cdd)


def profiles(data=None, fy_start=FY_START):
    """{stream: {month: fraction}}, every stream summing to exactly 1."""
    data = data or ResidentialData()
    hdd, cdd = degree_day_shapes(data, fy_start)
    months = _months(fy_start)
    # The non-heating half of every stream is cooking and water heating: continuous, so it
    # is days-weighted rather than equal-twelfthed. Only the heating half follows the
    # degree days, which is what the fraction below has always meant.
    base = core_monthly.days_weighted_profile(fy_start)
    out = {}
    for stream, h in HEATING_FRACTION.items():
        if h is None:
            prof = {m: cdd[m] for m in months}
        else:
            prof = {m: (1.0 - h) * base[m] + h * hdd[m] for m in months}
        out[stream] = core_monthly.normalise(prof)
    return out


def monthly_rows(data=None):
    data = data or ResidentialData()
    tj = combustion.fuel_TJ(data)
    pm = {}
    for r in air_pollutants.compute(data):
        if r["pollutant"] == "PM2.5":
            word = r["subitem"].split()[0]
            pm[word] = pm.get(word, 0.0) + r["emissions_kt"]
    word_of = {"Natural gas": "Natural", "Firewood": "Firewood",
               "Dung cake": "Dung", "Crop residues": "Crop", "LPG": "LPG",
               "Kerosene": "Kerosene", "Coal": "Coal", "Charcoal": "Charcoal",
               "Generators": "Generators"}
    prof = profiles(data)
    hdd, cdd = degree_day_shapes(data)
    months = _months()
    base = core_monthly.days_weighted_profile(FY_START)
    rows = []
    for stream, monthly in prof.items():
        annual_tj = tj[stream]
        annual_pm = pm.get(word_of[stream], 0.0)
        h = HEATING_FRACTION[stream]
        for m in _months():
            if h is None:
                base_share, climate_share = 0.0, monthly[m]
            else:
                s = (1.0 - h) * base[m] + h * hdd[m]
                base_share = (1.0 - h) * base[m] / s * monthly[m]
                climate_share = h * hdd[m] / s * monthly[m]
            rows.append({
                "stream": stream, "month": m,
                "TJ": annual_tj * monthly[m],
                "TJ_base_load": annual_tj * base_share,
                "TJ_climate_load": annual_tj * climate_share,
                "pm25_kt": annual_pm * monthly[m],
                "share": monthly[m],
                "temporal_method": TEMPORAL_METHOD,
                "basis": ("%s: CDD-shaped (load-shedding season)" % LABEL
                          if HEATING_FRACTION[stream] is None else
                          "%s: %.0f%% flat + %.0f%% HDD-shaped" % (
                              LABEL, 100 * (1 - HEATING_FRACTION[stream]),
                              100 * HEATING_FRACTION[stream])),
            })
    return rows


def _stream_of(component):
    """Which fuel stream a component row belongs to. Raises rather than defaulting."""
    for stream in HEATING_FRACTION:
        if component["subitem"].startswith(stream + " "):
            return stream
    raise KeyError("no residential monthly profile for %r" % component["subitem"])


def _basis(component):
    h = HEATING_FRACTION[_stream_of(component)]
    if h is None:
        return "%s: CDD-shaped (load-shedding season)" % LABEL
    return "%s: %.0f%% flat + %.0f%% HDD-shaped" % (LABEL, 100 * (1 - h), 100 * h)


def rows(data=None, fy_start=FY_START):
    """(annual components, month rows) - core.registry's monthly-layer contract.

    The TJ layer above came first and is what the air-pollutant work consumes; this is the
    same twelve shapes carried onto the emission components, which is what the national
    monthly product needs. Both close against their own control, and neither is derived
    from the other - so if the fuel-to-emission chain ever stopped being linear in the
    quantity, the two would disagree and the closure here would be the one that broke.
    """
    data = data or ResidentialData()
    from pkinv.sectors.residential import engine
    components = engine.build_components(data)
    prof = profiles(data, fy_start)
    out = core_monthly.apply_profile(
        components, None, fy_start, TEMPORAL_METHOD,
        profile_for=lambda c: prof[_stream_of(c)], basis=_basis)
    core_monthly.check_closure(out, components)
    return components, out


def check(rows, data=None):
    """Twelve months must reproduce every annual total exactly.

    The control here is energy, not CO2e, so this uses the generic core.monthly closure
    rather than check_closure: same invariant, different column.
    """
    data = data or ResidentialData()
    tj = combustion.fuel_TJ(data)
    return core_monthly.check_totals(rows, {s: tj[s] for s in HEATING_FRACTION},
                                     lambda r: r["stream"], "TJ",
                                     what="residential monthly TJ")


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = ResidentialData()
    energy = monthly_rows(data)
    check(energy, data)
    with open(asset_path(OUTPUTS, "residential_monthly_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["stream", "month", "TJ", "TJ_base_load",
                                          "TJ_climate_load", "pm25_kt", "share",
                                          "temporal_method", "basis"])
        w.writeheader()
        for r in energy:
            w.writerow({**r, "TJ": round(r["TJ"], 2),
                        "TJ_base_load": round(r["TJ_base_load"], 2),
                        "TJ_climate_load": round(r["TJ_climate_load"], 2),
                        "pm25_kt": round(r["pm25_kt"], 4),
                        "share": round(r["share"], 5)})

    components, month_rows = rows(data)
    core_monthly.write_layer(
        asset_path(OUTPUTS, "residential_emissions_monthly_%d.csv" % data.year),
        month_rows, components)

    jan = sum(r["pm25_kt"] for r in energy if r["month"] == "202401")
    jun = sum(r["pm25_kt"] for r in energy if r["month"] == "202406")
    print("Residential monthly profiles (%s): 12 x %d streams, annual closure exact; "
          "synthetic winter peak coincides with the smog season - January PM2.5 "
          "%.1f kt/month vs June %.1f (ratio %.1f)" % (LABEL, len(HEATING_FRACTION),
                                                       jan, jun, jan / jun))


if __name__ == "__main__":
    main()


# Public names (rc34): the survey-basis monthly layer reads these across the
# sector boundary.
stream_of = _stream_of
basis = _basis

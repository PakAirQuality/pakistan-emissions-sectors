"""The provincial split of grid power, by fuel and by fiscal year.

THE DEFECT. data/province_shares.csv carries one row per grid fuel, measured on FY2023-24, and
the engine applied it to all nine fiscal years. For coal that put 89 percent of every year's
emissions in Sindh, including FY2017-18, when Sahiwal in Punjab generated 69 percent of the
country's coal power and the Thar plants did not exist. The manuscript reported the largest
consequence itself (11.6 Mt CO2e in one province-year), said a per-year split was possible from
the same records, and left it undone as "a declared revision". A review asked why.

Not every fuel was fixed. Furnace oil and diesel took own-year GENERATION shares for FY2015-16
to FY2019-20 (generation_panel, rc44) and captive gas took its own year throughout
(captive_panel, rc60). What was still borrowed: coal and gas in every year, bagasse, and
furnace oil in FY2020-21 to FY2022-23, where the committed row booked 100 percent to Punjab
while Hub (Balochistan) and Jamshoro (Sindh) burned it.

WHAT THIS MODULE RETURNS. For each fuel stream and fiscal year, the province shares that
year's stations imply, with the basis, the coverage and, where the station record gives out,
the reason. One function, one table: `record(stream, fiscal_start_year)`.

THE BASIS, FUEL BY FUEL.

  Coal       the stations' booked energy: tonnage times the rank-default calorific value,
             which is how the NATIONAL coal account is booked
             (pkinv.sectors.power.fuel_reconciliation). A province therefore gets exactly the
             coal energy its stations are booked at, and the split conserves by construction.
             The committed row had used per-plant implied calorific values, which the
             reconciliation calls circular and which nearly doubles one station's FY2019-20
             energy. Three years carry a reconstructed commissioning lane (generation with no
             printed tonnage); it is placed on that year's coal stations that the tonnage
             tables do not enumerate, by their generation, and labelled reconstructed.
  Gas, RLNG  station fuel quantities. FY2019-20 on: the plant fuel ledger (NEPRA 2024 report).
  Furnace    FY2015-16 to FY2018-19: the same columns of the 2020 report
  oil,       (plant_fuel_quantity_back_years.csv), which the first ingest of that report did
  diesel     not read. MMBTU is exact; MMCFT takes the sector's declared heating value; oil
             takes the IPCC default NCV. A station-year with no usable quantity is weighted by
             its generation times its OWN specific consumption in the nearest year that has
             one, and the record says what share of the year's energy came in that way.
  Bagasse    the eight plants' generation; activity is generation there, so nothing better
             exists. No emissions are booked before FY2019-20.

SHARES, NOT MASSES. Gas, furnace oil and diesel are booked nationally from a separate control
(NEPRA Table 3). The stations supply the split and never the total, so no national number can
move here. `coverage` is the station energy over that control: it says how much of the year
the record sees, and it is reported, not used as a weight.

ONE PROVINCE AUTHORITY: NEPRA's Table 5 (plant_locations.csv), the record the station
placement reads, with the mine-mouth rule for the three Thar plants Table 5 leaves blank.
Four stations of the 2020 report retired before the 2024 Table 5 and are placed by the town
in their own names; RETIRED says so for each.

K-ELECTRIC IS OUTSIDE, as plant_ledger.in_boundary has it: the split describes the fleet
behind the national fuel control, which the boundary audit finds to be the CPPA side. That
reading is evidence and not proof, and it is the boundary's question, not this module's.

THE REFERENCE YEAR IS THE COMMITTED ROW. For FY2023-24 the engine reads
data/province_shares.csv, and tests hold this module to reproducing those rows. The row is the
reference year of a per-year series; it is no longer the series.

WHAT IT DOES NOT CORRECT. Sahiwal's FY2021-22 tonnage (1,444 kt for 6,881 GWh, twice its
usual intensity) and Guddu's gas volume at an assumed heating value are used as booked and
flagged. Changing either changes the national account, which is not what a split may do.
"""
import collections
import csv

from pkinv.assets import asset_path
from pkinv.core.geography import PROVINCES, curated_province
from pkinv.paths import DATA
from pkinv.sectors.power import plant_ledger, point_sources
from pkinv.sectors.power.plant_names import plant_key

STREAMS = ("power_coal", "power_gas", "power_rfo", "power_hsd", "bagasse_grid")
FIRST_YEAR, LAST_YEAR = 2015, 2023          # fiscal START years: FY2015-16 .. FY2023-24
REFERENCE_YEAR = 2023                       # FY2023-24: the committed rows ARE this year
LEDGER_FIRST_YEAR = 2019                    # the plant fuel ledger begins at FY2019-20
BAGASSE_FIRST_YEAR = 2019                   # no bagasse emissions are booked before it

BACK_YEARS = asset_path(DATA, "activity", "power", "plant_fuel_quantity_back_years.csv")
BAGASSE = asset_path(DATA, "activity", "power", "bagasse_generation.csv")
GENERATION = asset_path(DATA, "activity", "power", "generation_monthly.csv")
CROSSWALK = asset_path(DATA, "activity", "power", "plant_name_crosswalk.csv")

# The national control each stream is booked from (NEPRA Table 3, in TOE).
CONTROL_FUEL = {"power_gas": "Gas", "power_rfo": "Furnace Oil", "power_hsd": "Diesel Oil"}

# Names the 2020 report prints differently from Table 5.
BACK_YEAR_ALIAS = {
    "TNB Liberty Power": "Liberty Daharki Power",
    "KAPCO (Dual Fuel)": "KAPCO",
    "TPS Quetta (Isolated Generation) (GENCO-II)": "TPS Quetta",
    "FBC Lakhra (GENCO-IV)": "FBC Lakhra",
}
# Stations that had retired before the 2024 Table 5 was printed. Each is placed by the town in
# its own name, and the reason that town settles the province is given.
RETIRED = {
    "TPS Guddu (Units 1-4) (GENCO-II)": (
        "Sindh", "units 1-4 of the Guddu complex; Table 5 places its other three blocks at "
                 "Guddu, Sindh"),
    "GTPS Kotri (GENCO-I)": (
        "Sindh", "named for Kotri, Jamshoro district, Sindh; a GENCO-I station, the Jamshoro "
                 "company"),
    "SPS Faisalabad (GENCO- III)": (
        "Punjab", "named for Faisalabad; Table 5 places its sister station GTPS Faisalabad "
                  "there"),
    "GTPS Faisalabad (GENCO-III)": (
        "Punjab", "Table 5: GTPS Faisalabad, Faisalabad, Punjab"),
}

# THREE BAGASSE PLANTS WHERE TABLE 5 IS NOT THE LAST WORD. Each is settled by the district
# polygon its held coordinate falls in (data/shared/gis/PAK_ADM2.geojson; coordinates from
# the GEM bioenergy tracker, data/activity/power/gem_bioenergy_pak.csv) together with the
# district the generation workbook (grid_plant_district.csv) carries for the same plant.
# Two independent records against one, in the two cases where they differ:
#   Almoiz Industries      Table 5 says Mianwali, Punjab. Its coordinate (32.039 N, 70.977 E)
#                          is inside Dera Ismail Khan and the workbook says Dera Ismail Khan.
#   Jamal Din Wali-III     Table 5 says Rahim Yar Khan, Punjab, where unit II is. The JDW
#                          coordinate GEM holds (28.048 N, 69.321 E) is inside Ghotki, and the
#                          workbook files JDW-III at Ghotki, Sindh.
#   The Thal Industries    no Table 5 row. Its Layyah mill's coordinate (30.986 N, 70.950 E)
#   Corporation            is inside Layyah, Punjab.
# tests/test_province_panel.py repeats the polygon test, so these cannot outlive the evidence.
BAGASSE_PLACEMENT = {
    "Almoiz Industries": ("Khyber Pakhtunkhwa", (70.9772690958136, 32.0390435537013),
                          "Dera Ismail Khan"),
    "Jamal Din Wali-III": ("Sindh", (69.3212815, 28.0475817), "Ghotki"),
    "The Thal Industries Corporation": ("Punjab", (70.9497, 30.9861), "Layyah"),
}

# A lane or a residual smaller than this share of the year is noted and not placed.
NEGLIGIBLE = 0.005
# Below this coverage of the national control a cell keeps the reference vector: a split
# measured on under half of a fuel's energy describes the stations that happened to be
# printed, not the fuel.
COVERAGE_FLOOR = 0.50

_cache = {}


def panel_year(fiscal_start_year):
    """The fiscal start year, if this panel covers it; None otherwise (including None)."""
    if fiscal_start_year is None:
        return None
    year = int(fiscal_start_year)
    return year if FIRST_YEAR <= year <= LAST_YEAR else None


def _data():
    if "data" not in _cache:
        from pkinv.sectors.power.data import PowerData
        _cache["data"] = PowerData()
    return _cache["data"]


def _read(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


def _located():
    if "located" not in _cache:
        _cache["located"] = {plant_key(r["plant"]): r
                             for r in point_sources.locations().values()}
    return _cache["located"]


def province_of(plant):
    """(inventory province, how it was established) for a station name, or (None, reason)."""
    if plant in RETIRED:
        return RETIRED[plant][0], "retired before Table 5 (2024): " + RETIRED[plant][1]
    name = BACK_YEAR_ALIAS.get(plant, point_sources.ALIAS.get(plant, plant))
    if name in point_sources.MINE_MOUTH:
        return point_sources.MINE_MOUTH[name][1], "mine-mouth rule (Table 5 location blank)"
    hit = _located().get(plant_key(name))
    if hit is None or not (hit.get("province") or "").strip():
        return None, "no Table 5 row for %r" % plant
    return curated_province(hit["province"].strip()), "Table 5"


def _blank():
    return {"shares": None, "basis": "", "coverage": None, "energy_TJ": 0.0, "stations": 0,
            "derived_share": 0.0, "unplaced_TJ": 0.0, "flags": [], "fallback": ""}


def _finish(out, energy, unplaced):
    total = sum(energy.values())
    out["energy_TJ"], out["unplaced_TJ"] = total, unplaced
    if total > 0:
        out["shares"] = {p: energy.get(p, 0.0) / total for p in PROVINCES}
    return out


# --- gas, furnace oil, diesel ----------------------------------------------------------------

def _quantity_tj(quantity, unit):
    if unit == "MMBTU":
        return quantity * point_sources.TJ_PER_MMBTU
    if unit == "MMCFT":
        return (quantity * _data().p("captive_hhv_btu_per_scf")
                * plant_ledger.TJ_PER_MMCF_PER_BTU)
    if unit == "000 t":
        return quantity * point_sources.RFO_NCV_TJ_PER_GG
    if unit == "000 L":
        return quantity * point_sources.HSD_KG_PER_L * point_sources.HSD_NCV_TJ_PER_GG / 1000.0
    raise ValueError("no energy conversion for unit %r" % unit)


def _back_year_rows():
    """Station fuel rows of the 2020 report with energy where a quantity stands."""
    if "back" in _cache:
        return _cache["back"]
    rows = []
    for r in _read(BACK_YEARS):
        gwh = float(r["generation_gwh"] or 0.0)
        tj = _quantity_tj(float(r["quantity"]), r["quantity_unit"]) if r["quantity"] else None
        rows.append({"year": int(r["fiscal_year"][:4]), "plant": r["plant"], "fuel": r["fuel"],
                     "stream": point_sources.FUEL_GROUP[r["fuel"]], "gwh": gwh, "tj": tj,
                     "basis": r["quantity_basis"]})
    _cache["back"] = rows
    return rows


def _specific_energy(row, rows):
    """TJ per GWh for a station-year with no quantity: the station's own, nearest year first
    (this file, then the ledger); failing that, the median of its stream in that year."""
    own = sorted((abs(r["year"] - row["year"]), r["tj"] / r["gwh"]) for r in rows
                 if r["plant"] == row["plant"] and r["stream"] == row["stream"]
                 and r["tj"] and r["gwh"] > 0)
    if own:
        return own[0][1], "the station's own specific consumption, %d year(s) away" % own[0][0]
    key = plant_key(BACK_YEAR_ALIAS.get(row["plant"], row["plant"]))
    for year in range(LEDGER_FIRST_YEAR, LAST_YEAR + 1):
        for r in plant_ledger.rows(year):
            alias = point_sources.ALIAS.get(r["plant"], r["plant"])
            if (plant_key(alias) == key
                    and point_sources.FUEL_GROUP.get(r["fuel"]) == row["stream"]
                    and float(r["net_generation_GWh"] or 0.0) > 0 and r["quantity"]):
                tj = _quantity_tj(float(r["quantity"]), r["quantity_unit"])
                return (tj / float(r["net_generation_GWh"]),
                        "the station's own specific consumption in FY%d-%02d (plant fuel ledger)"
                        % (year, (year + 1) % 100))
    for scope, label in ((lambda r: r["year"] == row["year"], "that year"),
                         (lambda r: True, "over the report's five years")):
        peers = sorted(r["tj"] / r["gwh"] for r in rows
                       if scope(r) and r["stream"] == row["stream"] and r["tj"] and r["gwh"] > 0)
        if peers:
            return (peers[len(peers) // 2],
                    "the median specific consumption of its fuel %s" % label)
    return None, "no specific consumption to borrow"


def _fuel_record(stream, year):
    out = _blank()
    energy, unplaced, derived = collections.defaultdict(float), 0.0, 0.0
    if year >= LEDGER_FIRST_YEAR:
        for r in point_sources.rows(_data(), year):
            if not plant_ledger.in_boundary(r) or point_sources.FUEL_GROUP[r["fuel"]] != stream:
                continue
            if r["located_by"] == "UNMATCHED":
                unplaced += r["energy_TJ"]
                continue
            energy[curated_province(r["province"])] += r["energy_TJ"]
            out["stations"] += 1
        out["basis"] = "station fuel quantity (plant fuel ledger, NEPRA SoIR 2024)"
    else:
        rows = _back_year_rows()
        for r in rows:
            if r["year"] != year or r["stream"] != stream or r["gwh"] <= 0:
                continue
            tj = r["tj"]
            if tj is None:
                rate, _how = _specific_energy(r, rows)
                if rate is None:
                    unplaced += 0.0
                    out["flags"].append("%s has generation and no usable specific consumption"
                                        % r["plant"])
                    continue
                tj = r["gwh"] * rate
                derived += tj
            province, _how = province_of(r["plant"])
            if province is None:
                unplaced += tj
                out["flags"].append("%s is not placed" % r["plant"])
                continue
            energy[province] += tj
            out["stations"] += 1
        out["basis"] = "station fuel quantity (NEPRA SoIR 2020 Tables 16 and 19)"
    _finish(out, energy, unplaced)
    if out["energy_TJ"] > 0:
        out["derived_share"] = derived / out["energy_TJ"]
        if out["derived_share"] > NEGLIGIBLE:
            out["basis"] += ("; %.1f%% of the energy is generation x the station's own "
                             "specific consumption" % (100.0 * out["derived_share"]))
        if out["derived_share"] > 0.999:
            out["basis"] = ("station generation x the station's own specific consumption "
                            "(no fuel quantity is printed for this fuel)")
    try:
        control = _data().fuel_for(year)[CONTROL_FUEL[stream]] * _data().p("toe_to_tj")
    except KeyError:
        control = None
    if control:
        out["coverage"] = (out["energy_TJ"] + unplaced) / control
    if out["shares"] is None:
        out["fallback"] = "no station of the CPPA system burned this fuel on record this year"
    elif out["coverage"] is not None and out["coverage"] < COVERAGE_FLOOR:
        out["fallback"] = ("the station record covers %.0f%% of the national control, under "
                           "the %.0f%% floor" % (100 * out["coverage"], 100 * COVERAGE_FLOOR))
    return out


# --- coal ------------------------------------------------------------------------------------

def _coal_generation(year):
    """{station name: coal-labelled GWh} for one fiscal year from the generation panel."""
    names = {r["panel_name"]: r["canonical_plant"] for r in _read(CROSSWALK)
             if r["row_class"] == "grid_station"}
    label = "FY%d-%02d" % (year, (year + 1) % 100)
    out = collections.defaultdict(float)
    for r in _read(GENERATION):
        if r["fiscal_year"] == label and r["fuel"] == "Coal" and r["gwh"] and r["plant"] in names:
            out[names[r["plant"]]] += float(r["gwh"])
    return out


def _coal_record(year):
    from pkinv.sectors.power import fuel_reconciliation
    out = _blank()
    period = "FY%d-%02d" % (year, (year + 1) % 100)
    if "coal" not in _cache:
        _cache["coal"] = fuel_reconciliation.account_rows()
    rows = [r for r in _cache["coal"] if r["period_id"] == period]
    energy, unplaced, enumerated = collections.defaultdict(float), 0.0, set()
    booked = None
    for r in rows:
        if r["plant_coverage_class"] == "booked total":
            booked = float(r["energy_TJ_booked_basis"]) if r["energy_TJ_booked_basis"] else None
        elif r["plant_coverage_class"] == "enumerated station" and r["energy_TJ_booked_basis"]:
            tj = float(r["energy_TJ_booked_basis"])
            if tj <= 0:
                continue
            province, _how = province_of(r["plant"])
            enumerated.add(plant_key(BACK_YEAR_ALIAS.get(r["plant"],
                                                         point_sources.ALIAS.get(r["plant"], r["plant"]))))
            if province is None:
                unplaced += tj
                out["flags"].append("%s is not placed" % r["plant"])
                continue
            energy[province] += tj
            out["stations"] += 1
    station_tj = sum(energy.values()) + unplaced
    out["basis"] = "station tonnage x rank-default NCV (the national booking's own basis)"
    lane = (booked - station_tj) if booked else 0.0
    if booked and lane > NEGLIGIBLE * booked:
        # The commissioning lane: generation the tonnage tables do not enumerate. It goes to
        # the coal stations of this year's generation panel that are NOT among the enumerated
        # ones, by their generation, at the booked lane energy. No tonnage is invented.
        candidates = {name: gwh for name, gwh in _coal_generation(year).items()
                      if plant_key(name) not in enumerated and gwh > 0}
        total = sum(candidates.values())
        if total > 0:
            for name, gwh in candidates.items():
                province, _how = province_of(name)
                if province is None:
                    unplaced += lane * gwh / total
                    out["flags"].append("%s (commissioning) is not placed" % name)
                    continue
                energy[province] += lane * gwh / total
                out["stations"] += 1
            out["derived_share"] = lane / booked
            out["basis"] += ("; %.1f%% of the booked energy is a reconstructed commissioning "
                             "lane, placed on %s by generation"
                             % (100.0 * lane / booked, ", ".join(sorted(candidates))))
        else:
            out["flags"].append("%.1f%% of the booked energy is a commissioning lane with no "
                                "station in the generation panel; the split is over the "
                                "enumerated stations" % (100.0 * lane / booked))
    elif booked and abs(lane) > 1e-6 * booked:
        out["flags"].append("%.2f%% of the booked energy is outside the enumerated stations "
                            "and is not placed" % (100.0 * lane / booked))
    _finish(out, energy, unplaced)
    if booked:
        out["coverage"] = (out["energy_TJ"] + unplaced) / booked
    if period == "FY2021-22":
        out["flags"].append("Sahiwal's tonnage this year (1,444 kt for 6,881 GWh) is twice its "
                            "usual intensity; used as booked")
    if out["shares"] is None:
        out["fallback"] = "no coal station is enumerated or in the generation panel this year"
    return out


# --- bagasse ---------------------------------------------------------------------------------

def _bagasse_record(year):
    out = _blank()
    if year < BAGASSE_FIRST_YEAR:
        out["fallback"] = "no bagasse emissions are booked before FY2019-20"
        return out
    energy, unplaced = collections.defaultdict(float), 0.0
    for r in _read(BAGASSE):
        if int(r["fiscal_year"]) != year or not r["generation_GWh"]:
            continue
        gwh = float(r["generation_GWh"])
        if r["plant"] in BAGASSE_PLACEMENT:
            province = BAGASSE_PLACEMENT[r["plant"]][0]
        else:
            province, _how = province_of(r["plant"])
        if province is None:
            unplaced += gwh
            out["flags"].append("%s has no Table 5 row" % r["plant"])
            continue
        energy[province] += gwh
        out["stations"] += 1
    out["basis"] = ("station generation (activity for this stream is generation; NEPRA SoIR "
                    "2024 Table 8)")
    _finish(out, energy, unplaced)
    total = out["energy_TJ"] + unplaced
    out["coverage"] = (out["energy_TJ"] / total) if total else None
    if out["shares"] is None:
        out["fallback"] = "no bagasse plant is on record this year"
    return out


# --- the interface ---------------------------------------------------------------------------

def record(stream, fiscal_start_year):
    """Everything this panel knows about one stream in one fiscal year.

    {shares: {province: share} or None, basis, coverage, energy_TJ, stations, derived_share,
     unplaced_TJ, flags, fallback}. `fallback` is non-empty exactly when the engine must keep
    the reference vector for this cell, and says why."""
    year = panel_year(fiscal_start_year)
    if year is None or stream not in STREAMS:
        raise KeyError("no provincial panel for %r in %r" % (stream, fiscal_start_year))
    key = (stream, year)
    if key not in _cache:
        if stream == "power_coal":
            _cache[key] = _coal_record(year)
        elif stream == "bagasse_grid":
            _cache[key] = _bagasse_record(year)
        else:
            _cache[key] = _fuel_record(stream, year)
    return _cache[key]


def province_shares(fiscal_start_year):
    """{stream: {province: share}} for every stream whose own-year record stands. A stream
    that falls back is ABSENT, so the caller's committed row remains. The reference year
    returns nothing: its shares are the committed rows, which this panel is tested against,
    so the reference year's products cannot drift on a sixth decimal place."""
    out = {}
    if panel_year(fiscal_start_year) == REFERENCE_YEAR:
        return out
    for stream in STREAMS:
        found = record(stream, fiscal_start_year)
        if found["shares"] is not None and not found["fallback"]:
            out[stream] = dict(found["shares"])
    return out

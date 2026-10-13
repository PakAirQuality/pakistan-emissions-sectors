"""THE REVIEWED PLANT-FUEL-YEAR REGISTER for oil- and diesel-fired main-activity power.

WHY. outputs/pakemis_air_coverage_matrix.csv types power SO2 `NE` in all nine periods with
basis `uncontrolled-screening-only`, and a screening runs beside the panel rather than in it.
That refusal is defensible for a coal fleet whose control inventory NEPRA does not publish. It
is not defensible for the oil and diesel fleet, where this repository holds metered fuel
quantities, a fuel-quality register, published station types and an applicable AP-42 factor for
every equipment class involved. This file is the register that decides, source by source, which
rows can be estimated and which cannot.

WHAT IS NOT AN ADMISSION TEST. An earlier draft proposed admitting oil because the screening's
uncontrolled and controlled endpoints coincide for it. They coincide because the repository's
controlled case applies a coal FGD residual and nothing to oil - a property of the model, not of
the plants. AP-42 Section 1.3 (data/raw/epa_ap42/ap42_c01s03_fuel_oil_combustion.pdf) records
scrubbing on oil-fired boilers at 90 to 95 percent SO2 removal, so these three statements are
different and only the first two are established:

    the factor table holds no controlled-oil row          true, a limitation of our register
    the model credits no SO2 removal to oil               true, a modelling assumption
    these Pakistani oil units carry no SO2 removal        NOT ESTABLISHED by either of the above

The third is the declared default below. It is stated on every row, it is the assumption that
would most change the answer, and it is not dressed up as a finding.

THE FIVE AUDIT QUESTIONS, each answered in its own column rather than in prose:

  activity   physical mass or a derived one? consumed or a proxy? which reporting period?
  sulfur     which value, in which year, on what basis - assay, specification or proxy?
  equipment  boiler, reciprocating engine or gas turbine, and does the factor apply to it?
  removal    documented control, justified default, or a missing database field?
  boundary   main-activity power or captive industry? which district, on what evidence?

TWO ACTIVITY ROUTES, and the weaker one says so.

  ledger_quantity  FY2019-20..FY2023-24. data/activity/power/plant_fuel_ledger.csv prints a
                   METERED QUANTITY per plant, fuel and year - RFO in thousand tonnes, HSD in
                   thousand litres. No heat rate, no NCV, no efficiency assumption stands
                   between the document and the mass. This is the strong population.

  generation_x_heat_rate  FY2015-16..FY2018-19, where no ledger exists. The generation is this
                   repository's own twelve monthly rows per plant-year, by fuel; the heat rate
                   is the plant's published net rate where there is one, and otherwise the
                   YEAR'S OWN national implied furnace-oil rate from
                   src/pkinv/sectors/power/heat_rate.py, which is national fuel over national
                   generation in that same year - a measured annual quantity rather than a
                   carried constant, certified `stable` over nine years at a spread of 1.31 and
                   `plausible` in each of the four years used here.

  Backcasting is not optional. CLAUDE.md requires a new category to reach FY2015-16 before it
  may enter a comparable aggregate, and the reason is visible in this very fleet: furnace-oil
  generation falls from 19.5 TWh in FY2015-16 to 7.8 TWh in FY2018-19 and further after. A
  register covering only the ledger years would add emissions to the late years and none to the
  early ones, which would flatten a real decline with a coverage artefact - the exact defect
  this programme exists to remove.

EQUIPMENT IS NOT DECORATION. AP-42 Section 1.3's 157 lb/kgal-per-%S is a factor for BOILERS,
and half this fleet is not boilers. NEPRA SoIR Table 5 prints a station type for every plant,
and it separates them cleanly - no station carries both a gas turbine and a reciprocating
engine - so each row takes the factor for what it actually is:

  ST, STs              oil-fired boiler        ap42_1.3_no6_so2_157S, rating A, and it carries
                                               its own 5.05 percent sulfur retention (18.990401
                                               against the 20.0 of a complete balance)
  DE, DEs, DGs, REs    reciprocating engine    AP-42 Section 3.4, which states that "essentially
                                               all the sulfur in the fuel is oxidized to SO2"
                                               and is "a function of only the sulfur content in
                                               the fuel rather than any combustion variables"
  GTs, CCPPs           gas turbine             AP-42 Section 3.1, Table 3.1-2a footnote h: "All
                                               sulfur in the fuel is assumed to be converted to
                                               SO2", factor 1.01S lb/MMBtu, rating B

  The last two are therefore priced as a COMPLETE balance (retention zero) on their own
  documented authority, not by asserting zero for want of a number. Both sections are held:
  sources/AP42/c03s01.pdf and data/raw/epa_ap42/ap42_c03s04_large_stationary_diesel_2025.pdf.

THREE DISPOSITIONS, and an unresolved unit never blocks a clear one:

  provisional_estimate  activity and sulfur defensible, factor applicable to the equipment,
                        control either documented or an explicitly justified default. ENTERS.
  scenario_only         a material unresolved question - no equipment class, no district, no
                        usable heat rate, an incomplete generation year. STAYS OUT, and is the
                        only population the remaining-power scenario may contain.

Usage:  python3 scripts/build_power_admission_register.py [--check]
Writes: data/activity/power/power_so2_admission.csv
"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path

from pkinv.core import air_factors, sulfur                                   # noqa: E402
from pkinv.core.io import read_rows, write_or_check                          # noqa: E402
from pkinv.sectors.power import heat_rate as heat_rate_module                # noqa: E402
from pkinv.sectors.power.data import PowerData                               # noqa: E402
from pkinv.sectors.power.point_sources import (ALIAS, HSD_KG_PER_L,          # noqa: E402
                                               HSD_NCV_TJ_PER_GG,
                                               RFO_NCV_TJ_PER_GG, equipment_class)

OUT = asset_path(ROOT, "data", "activity", "power", "power_so2_admission.csv")
PERIODS = tuple("FY%d-%02d" % (y, (y + 1) % 100) for y in range(2015, 2024))
LEDGER_PERIODS = frozenset(PERIODS[4:])          # FY2019-20.. , where a metered quantity exists
FUELS = ("RFO", "HSD")
KJ_PER_KWH = 3600.0

# The boiler factor is transcribed and held; the engine and turbine sections are cited for the
# ONE quantity this balance needs from them, which is that conversion is complete.
BOILER_FACTOR = "ap42_1.3_no6_so2_157S"
ENGINE_CITE = ("AP-42 Section 3.4 (Large Stationary Diesel Engines, 2025), p. 3.4-2: sulfur "
               "oxides are \"a function of only the sulfur content in the fuel rather than any "
               "combustion variables\" and \"essentially all the sulfur in the fuel is oxidized "
               "to SO2\"; Table 3.4-1 gives 1.01S lb/MMBtu, rating B")
TURBINE_CITE = ("AP-42 Section 3.1 (Stationary Gas Turbines, 4/00), Table 3.1-2a footnote h: "
                "\"All sulfur in the fuel is assumed to be converted to SO2\"; the distillate-oil "
                "factor is 1.01S lb/MMBtu, rating B")
OXIDISED = 1.0

CONTROL_TYPE = "none credited"
CONTROL_BASIS = (
    "DECLARED DEFAULT, NOT A FINDING: no SO2 removal is credited because no control record is "
    "held for this unit. AP-42 Section 1.3 documents oil-fired scrubbing at 90-95 percent "
    "removal, so an installed control would reduce this row by up to that much. The absence of "
    "a database field is not evidence of absent equipment, and this column says which one it is.")

# `sulfur.evidence` takes the candidates as one ";"-joined string and returns the single row
# valid for the fiscal-END year, raising if two overlap. Diesel therefore offers both regimes
# and lets the register's own validity dates choose - the Euro-II boundary is a property of the
# evidence, not of this script.
# rc63: RFO moved from power_rfo_spec_range to fo_hsfo_grade_mix. One national fuel had two
# centrals 2.27x apart - 1.3229 % here and 3.0 % for industry - and the held import grade split
# (85.3-100 % high-sulphur grade) says the pool sits near the top of the 0.5-3.5 specification
# span rather than at its unweighted geometric middle. The retired row now resolves for no year,
# so leaving this string would raise rather than quietly price the fleet at a superseded value.
SULFUR_BY_FUEL = {"RFO": "fo_hsfo_grade_mix",
                  "HSD": "hsd_pre_euro2;hsd_euro2_onward"}
SOURCE_CLASS = {"RFO": "power_rfo_boiler", "HSD": "power_hsd_engine"}

FIELDS = (
    "plant", "fuel", "period_id", "fiscal_start_year",
    # boundary
    "boundary", "system", "adm2_id", "town", "province", "geography_basis",
    # equipment
    "station_type", "equipment_class", "factor_id", "factor_equipment_match",
    "retention_frac", "factor_basis",
    # activity
    "activity_route", "activity_quantity", "activity_unit", "generation_gwh",
    "heat_rate_kJ_per_kWh", "heat_rate_basis", "fuel_mass_kt", "activity_basis",
    "activity_evidence_class",
    # sulfur
    "sulfur_evidence_id", "s_pct_central", "s_pct_lo", "s_pct_hi", "sulfur_basis",
    # removal
    "control_type", "control_basis",
    # result
    "so2_Gg", "so2_Gg_lo", "so2_Gg_hi", "so2_uncert_pct",
    "disposition", "disposition_reason",
)


def _start_year(period):
    """FY2019-20 -> 2019, the key plant_heat_rates.csv and plant_fuel_ledger.csv use."""
    return int(period[2:6])


def _period(start):
    return "FY%d-%02d" % (start, (start + 1) % 100)


def canonical_names():
    """{panel spelling: station}, falling back to the NORMALIZED STEM rather than the raw name.

    An `unmapped` crosswalk row carries no canonical_plant, and taking its panel spelling
    verbatim re-splits what normalization had already joined - "Gulf Power" and "Gulf Power RF"
    become two stations again. The stem is the crosswalk's own answer for those rows.
    """
    return {r["panel_name"]: (r["canonical_plant"] or r["normalized_stem"] or r["panel_name"])
            for r in read_rows(asset_path(ROOT, "data", "activity", "power",
                                            "plant_name_crosswalk.csv"))}


def station(ledger_or_panel_name, names):
    """ONE vocabulary for both sources: NEPRA Table 5's station name.

    THIS FUNCTION IS THE DOUBLE-COUNT GUARD. The ledger calls a station "Hub" and the monthly
    panel calls it "Hub Power"; a register that unions the two name spaces prices that station
    twice, once from each route. The first build of this file did exactly that, and the result
    exceeded the national furnace-oil supply by up to 50 percent in the ledger years - which is
    how it was caught, because a fleet cannot burn more fuel than the country delivered.
    """
    return ALIAS.get(ledger_or_panel_name, names.get(ledger_or_panel_name,
                                                     ledger_or_panel_name))


def locations():
    """{Table 5 plant: row} plus the ledger-name alias, so one lookup answers both."""
    loc = {r["plant"]: r for r in
           read_rows(asset_path(ROOT, "data", "activity", "power", "plant_locations.csv"))}
    return loc


def districts():
    """{Table 5 plant: adm2_id} from the facility registry, which resolves the town."""
    out = {}
    for r in read_rows(asset_path(ROOT, "data", "facility_registry.csv")):
        if r["module"] != "power" or not r["adm2_id"] or r["adm2_id"] == "unresolved":
            continue
        out.setdefault(r["name"], r["adm2_id"])
        if r["source_key"]:
            out.setdefault(r["source_key"], r["adm2_id"])
    return out


def generation_by_fuel(names):
    """{(station, fuel, period): (GWh, complete?)} from this repository's monthly rows.

    A station can arrive as several PANEL ROWS that are units rather than duplicates - TPS
    Muzaffargarh prints six ("Block 1 Unit 1" ... "Block 3 Unit 6"), KAPCO two, Jamshoro four -
    and their generation genuinely sums to the station. So the completeness test counts months
    PER CONSTITUENT ROW: the year is complete when every spelling that reported at all reported
    twelve times. Testing the pooled count instead reads a well-covered six-unit station as
    "72 of twelve months" and throws it away, which is what this function did first.
    """
    gwh, months = {}, {}
    for r in read_rows(asset_path(ROOT, "data", "activity", "power",
                                    "generation_monthly.csv")):
        if r["fuel"] not in FUELS:
            continue
        key = (station(r["plant"], names), r["fuel"], r["fiscal_year"])
        gwh[key] = gwh.get(key, 0.0) + float(r["gwh"] or 0)
        months.setdefault(key, {})
        months[key][r["plant"]] = months[key].get(r["plant"], 0) + 1
    return {k: (v, months[k]) for k, v in gwh.items()}


def plant_heat_rates(names):
    """{(plant, fiscal START year): net kJ/kWh}. A printed ZERO is not a heat rate.

    Three stations print 0 for FY2019-20 - Hub, KAPCO and TPS Jamshoro - which is an absence the
    document types as a zero, and dividing by it or reading it as an efficiency of infinity are
    equally wrong. They are dropped here so the row falls through to the fleet rate.
    """
    out = {}
    for r in read_rows(asset_path(ROOT, "data", "activity", "power",
                                    "plant_heat_rates.csv")):
        btu = float(r["hr_net_btu_kwh"] or 0)
        if btu <= 0:
            continue
        out[(station(r["plant"], names), int(r["fiscal_year"]))] = btu * 1.05506   # -> kJ/kWh
    return out


def national_rfo_heat_rates():
    """{fiscal start year: (kJ/kWh, verdict)} - the year's OWN national implied furnace-oil rate."""
    data = PowerData()
    out = {}
    for year in heat_rate_module.overlap_years(data):
        for row in heat_rate_module.implied(data, year):
            if row["fuel"] == "Furnace Oil":
                out[int(year)] = (row["heat_rate_kJ_per_kWh"], row["verdict"])
    return out


def sulfur_row(fuel, fy_end):
    """The dated evidence row, or None where the register covers no such year (typed, not zero)."""
    try:
        return sulfur.evidence(SULFUR_BY_FUEL[fuel], fy_end, SOURCE_CLASS[fuel])
    except sulfur.NoSulfurEvidence:
        return None


def _boiler_kg_per_t_per_pct():
    value, _unit = air_factors.kg_per_unit(air_factors.factor(BOILER_FACTOR))
    return value


def ledger_systems(names):
    """{station: system} from the ledger, for EVERY year including those it does not cover.

    A station's system is a structural fact - Bin Qasim is K-Electric's whether or not the
    ledger prints a row for FY2015-16 - and the national furnace-oil control needs it on the
    generation-route rows too, or K-Electric's mass is compared against a national row that
    excludes it.
    """
    out = {}
    for r in read_rows(asset_path(ROOT, "data", "activity", "power",
                                    "plant_fuel_ledger.csv")):
        out.setdefault(station(r["plant"], names), r["system"])
    return out


def ledger_fuels_by_station(names):
    """{station: {fuels the ledger ever names for it}} - the fuel-label conflict test.

    The monthly panel labels a fuel per plant-month, and those labels are not always right:
    it prints 2,955 GWh of RFO for Liberty Daharki, which the ledger meters as a GAS station
    in every year it appears. A label that disagrees with the metered record is a question,
    not an activity, so those rows become scenario_only. The test is only applied to stations
    the ledger actually covers - a station it never lists is an absence of evidence, not a
    contradiction, and its panel label stands.
    """
    out = {}
    for r in read_rows(asset_path(ROOT, "data", "activity", "power",
                                    "plant_fuel_ledger.csv")):
        out.setdefault(station(r["plant"], names), set()).add(r["fuel"])
    return out


def build():
    loc, dist = locations(), districts()
    names = canonical_names()
    gen = generation_by_fuel(names)
    plant_hr, fleet_hr = plant_heat_rates(names), national_rfo_heat_rates()
    ledger_fuels = ledger_fuels_by_station(names)
    systems = ledger_systems(names)
    boiler_per_pct = _boiler_kg_per_t_per_pct()
    # the retention the held boiler factor implies, against a complete balance of 20.0 kg/t/%S
    boiler_retention = 1.0 - boiler_per_pct / 20.0

    ledger_by = {}
    for r in read_rows(asset_path(ROOT, "data", "activity", "power",
                                    "plant_fuel_ledger.csv")):
        if r["fuel"] in FUELS and r["quantity"]:
            ledger_by[(station(r["plant"], names), r["fuel"],
                       _period(int(r["fiscal_year"])))] = r

    # ONE name space, so no station can be reached twice by two different spellings
    plants = {p for (p, _f, _y) in ledger_by} | {p for (p, _f, _y) in gen}
    rows = []
    for plant in sorted(plants):
        place = loc.get(plant)
        station_type = place["station_type"] if place else ""
        klass = equipment_class(station_type)
        for fuel in FUELS:
            for period in PERIODS:
                row = _row(plant, plant, fuel, period, place, klass, station_type, dist,
                           ledger_by, gen, plant_hr, fleet_hr, names,
                           boiler_per_pct, boiler_retention, ledger_fuels, systems)
                if row:
                    rows.append(row)
    rows.sort(key=lambda r: (r["plant"], r["fuel"], r["period_id"]))
    return rows


def _row(plant, t5, fuel, period, place, klass, station_type, dist, ledger_by, gen,
         plant_hr, fleet_hr, names, boiler_per_pct, boiler_retention, ledger_fuels,
         systems):
    """One plant x fuel x period, or None where this plant burned none of this fuel then."""
    start = _start_year(period)
    fy_end = start + 1
    led = ledger_by.get((plant, fuel, period))
    gwh, months = gen.get((plant, fuel, period), (0.0, {}))
    if not led and gwh <= 0:
        return None

    r = {f: "" for f in FIELDS}
    r.update(plant=plant, fuel=fuel, period_id=period, fiscal_start_year=start,
             boundary="main-activity power (CPPA/K-Electric grid station)",
             system=led["system"] if led else systems.get(plant, ""),
             station_type=station_type, town=place["town"] if place else "",
             province=place["province"] if place else "",
             control_type=CONTROL_TYPE, control_basis=CONTROL_BASIS,
             generation_gwh=round(gwh, 3) if gwh else "")

    adm2 = dist.get(t5, "")
    r["adm2_id"] = adm2
    r["geography_basis"] = ("facility registry district for NEPRA Table 5 station %r" % t5
                            if adm2 else
                            "NO RESOLVED DISTRICT for %r - the row is national only" % t5)

    blockers = []
    # THE BOUNDARY, and it is a scope question rather than an evidence one. K-Electric's
    # stations have exactly the same evidence as the rest - metered fuel, a printed station
    # type, a resolved district - but this inventory's power layer covers the CPPA side only
    # (the national fuel table does, and so does every greenhouse-gas power stream). Admitting
    # K-Electric's SO2 into a panel whose power CO2 does not contain those plants would put
    # air coverage ahead of the inventory boundary, and the spatial layer could not place the
    # mass at all: it inherits the CPPA stream's district vector, which has no K-Electric in
    # it, so Bin Qasim's and Korangi's emissions would be spread across Punjab. They are held
    # as scenarios until the CPPA/K-Electric control-total question is settled for the sector
    # as a whole, which is the power paper's open item and not this register's to decide.
    if (r["system"] or systems.get(plant, "")) == "K-Electric":
        blockers.append("K-Electric sits outside this inventory's power boundary (the national "
                        "fuel table and every greenhouse-gas power stream are CPPA-side only); "
                        "a scope question, not a gap in the evidence for these plants")
    known = ledger_fuels.get(plant)
    if not led and known and fuel not in known:
        blockers.append("the monthly panel labels %s for a station the ledger meters only as %s; "
                        "an unreviewed fuel label is a question, not an activity"
                        % (fuel, "/".join(sorted(known))))
    # ---- equipment and factor -------------------------------------------------------------
    if klass == "oil_fired_boiler":
        r.update(equipment_class=klass, factor_id=BOILER_FACTOR,
                 factor_equipment_match="entitled: the factor names \"boilers, all sizes\"",
                 retention_frac="%.6f" % boiler_retention,
                 factor_basis="AP-42 Section 1.3, 157 lb/kgal per %%S, rating A = %.6f kg SO2 "
                              "per tonne per %%S, which implies %.2f percent sulfur retention "
                              "against a complete balance"
                              % (boiler_per_pct, 100 * boiler_retention))
        per_pct = boiler_per_pct
    elif klass in ("reciprocating_engine", "gas_turbine"):
        r.update(equipment_class=klass, factor_id="sulfur_balance_complete_conversion",
                 factor_equipment_match="entitled: the section for this equipment states that "
                                        "conversion is complete",
                 retention_frac="0.000000",
                 factor_basis=ENGINE_CITE if klass == "reciprocating_engine" else TURBINE_CITE)
        per_pct = 20.0
    else:
        r.update(equipment_class="", factor_id="", retention_frac="",
                 factor_equipment_match="",
                 factor_basis="NEPRA Table 5 prints no station type for %r, so no equipment "
                              "class can be read and no factor is entitled" % t5)
        per_pct = None
        blockers.append("equipment class unreadable")

    # ---- activity --------------------------------------------------------------------------
    mass_kt = None
    if led:
        q = float(led["quantity"])
        r.update(activity_route="ledger_quantity", activity_quantity=q,
                 activity_unit=led["quantity_unit"],
                 activity_evidence_class="metered_fuel_quantity",
                 activity_basis="NEPRA SoIR 2024 %s, quantity of %s consumed by this station in "
                                "this fiscal year, read directly - no heat rate, calorific value "
                                "or efficiency stands between the document and the mass"
                                % (led["source_table"], fuel))
        if led["quantity_unit"] == "000 t":
            mass_kt = q
        elif led["quantity_unit"] == "000 L":
            mass_kt = q * HSD_KG_PER_L / 1000.0
            r["activity_basis"] += ("; thousand litres to mass at %.2f kg/L, the power module's "
                                    "own density (point_sources.HSD_KG_PER_L)" % HSD_KG_PER_L)
        else:
            blockers.append("unit %r is neither mass nor volume" % led["quantity_unit"])
    else:
        short = {name: n for name, n in months.items() if n != 12}
        if not months:
            blockers.append("no monthly generation rows")
        elif short:
            blockers.append("incomplete monthly generation: %s"
                            % "; ".join("%s reported %d of twelve months" % (n, c)
                                        for n, c in sorted(short.items())))
        rate = plant_hr.get((plant, start))
        if rate:
            r["heat_rate_basis"] = ("this station's own published net heat rate for FY%d-%02d"
                                    % (start, (start + 1) % 100))
        else:
            carried = sorted(y for (p, y) in plant_hr if p == plant)
            if carried:
                rate = plant_hr[(plant, carried[0])]
                r["heat_rate_basis"] = (
                    "this station's own published net rate CARRIED BACK from FY%d-%02d, its "
                    "earliest published year; not measured in this period"
                    % (carried[0], (carried[0] + 1) % 100))
            elif fuel == "RFO" and start in fleet_hr:
                rate, verdict = fleet_hr[start]
                r["heat_rate_basis"] = (
                    "THIS YEAR'S OWN national implied furnace-oil heat rate (national fuel over "
                    "national generation, power.heat_rate.implied), verdict %r; a fleet figure "
                    "applied to one station, and measured in this period rather than carried"
                    % verdict)
                if verdict != "plausible":
                    blockers.append("the fleet heat rate for this year is %s" % verdict)
            else:
                blockers.append("no published heat rate and no fleet rate for this fuel-year")
        if rate:
            ncv = RFO_NCV_TJ_PER_GG if fuel == "RFO" else HSD_NCV_TJ_PER_GG
            tj = gwh * 1e6 * rate / 1e9                    # GWh -> kWh -> kJ -> TJ
            mass_kt = tj / ncv
            r.update(activity_route="generation_x_heat_rate",
                     activity_quantity=round(gwh, 3), activity_unit="GWh",
                     heat_rate_kJ_per_kWh=round(rate, 1),
                     activity_evidence_class="generation_x_heat_rate",
                     activity_basis="twelve monthly generation rows for this station and fuel "
                                    "(generation_monthly.csv) x the heat rate named beside, over "
                                    "the IPCC default NCV of %.1f TJ/Gg" % ncv)

    # ---- sulfur ------------------------------------------------------------------------------
    s_row = sulfur_row(fuel, fy_end)
    if s_row is None:
        blockers.append("no sulfur evidence row applies to %s in FY%d" % (fuel, fy_end))
    else:
        r.update(sulfur_evidence_id=s_row["evidence_id"],
                 s_pct_central=s_row["s_pct_central"], s_pct_lo=s_row["s_pct_lo"],
                 s_pct_hi=s_row["s_pct_hi"], sulfur_basis="%s - %s"
                 % (s_row["basis"], s_row["source"]))

    # ---- the balance --------------------------------------------------------------------------
    if mass_kt is not None and per_pct is not None and s_row is not None:
        scale = per_pct / 20.0                      # the factor's own retention, as a fraction
        for col, key in (("so2_Gg", "s_pct_central"), ("so2_Gg_lo", "s_pct_lo"),
                         ("so2_Gg_hi", "s_pct_hi")):
            r[col] = round(sulfur.so2_kt(mass_kt, float(s_row[key]), OXIDISED, 1.0 - scale), 6)
        r["so2_uncert_pct"] = round(
            sulfur.so2_uncert_pct(s_row, 1.0 - scale, 0.0), 2)
    r["fuel_mass_kt"] = round(mass_kt, 4) if mass_kt is not None else ""

    if blockers:
        r.update(disposition="scenario_only", disposition_reason="; ".join(blockers))
        r["so2_Gg"] = r["so2_Gg_lo"] = r["so2_Gg_hi"] = ""
    else:
        r.update(disposition="provisional_estimate",
                 disposition_reason="metered or measured activity, an applicable factor for the "
                                    "station's own equipment class, a dated sulfur evidence row, "
                                    "and a declared control default")
    return r


def national_control(priced):
    """The check that caught the first build: a fleet cannot burn more than the country supplied.

    The national furnace-oil row covers the CPPA side ONLY - the boundary audit behind
    data/power_params.csv activity_uncert_fo establishes that, and it is why K-Electric's mass
    is reported separately here rather than being compared against a total that excludes it.
    Printed on every run so an over-count cannot pass unseen again.
    """
    data = PowerData()
    lines = []
    for period in PERIODS:
        start = _start_year(period)
        national = data.fuel_for(start).get("Furnace Oil", 0.0) * 0.041868 / RFO_NCV_TJ_PER_GG
        rfo = [r for r in priced if r["fuel"] == "RFO" and r["period_id"] == period]
        ke = sum(float(r["fuel_mass_kt"]) for r in rfo if r["system"] == "K-Electric")
        cppa = sum(float(r["fuel_mass_kt"]) for r in rfo) - ke
        lines.append((period, cppa, ke, national,
                      (cppa / national) if national else float("nan")))
    return lines


def main():
    rows = build()
    check = "--check" in sys.argv
    write_or_check(OUT, FIELDS, rows, check=check)
    priced = [r for r in rows if r["disposition"] == "provisional_estimate"]
    out = {}
    for r in priced:
        out[r["period_id"]] = out.get(r["period_id"], 0.0) + float(r["so2_Gg"])
    print("%s: %d rows, %d admitted, %d scenario_only"
          % (os.path.relpath(OUT, ROOT), len(rows), len(priced), len(rows) - len(priced)))
    print()
    print("   %-10s %9s | %10s %9s %10s %7s" % ("period", "SO2 Gg", "RFO CPPA", "RFO K-E",
                                                "national", "CPPA/n"))
    over = []
    for period, cppa, ke, national, ratio in national_control(priced):
        print("   %-10s %9.2f | %10.1f %9.1f %10.1f %7.3f"
              % (period, out.get(period, 0.0), cppa, ke, national, ratio))
        if ratio > 1.0:
            over.append((period, round(ratio, 3)))
    if over:
        sys.exit("the CPPA-side furnace oil exceeds the national supply in %s - a register that "
                 "burns more fuel than the country delivered is double counting, which is how "
                 "the first build of this file was caught" % over)


if __name__ == "__main__":
    from pkinv.activity.store import staging_inputs
    with staging_inputs():
        main()

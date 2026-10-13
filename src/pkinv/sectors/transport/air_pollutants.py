"""Air-pollutant emissions from road transport: EMEP/EEA Tier 1, per class and process.

Reported in mass (kt), never converted to CO2e and never part of the greenhouse-gas
reconciliation. Row schema matches the other sectors' air layers so they concatenate.

THE SECOND BUILD OF THIS LAYER. The first was an exploratory diagnostic on a Punjab
workbook's g/km factors with no primary citation, one anchor per fuel, no BC, and
exhaust only - reported in the supplement as such and never given a policy weight. This
build replaces the factor basis with the EMEP/EEA guidebook 2023's Tier 1 road-transport
chapters, transcribed by hand into data/activity/transport/emep_tier1_road_air.csv
(204 cells, each verified against the held PDFs) and bridged to the fleet model's
classes by the DECLARED map in data/activity/transport/emep_class_map.csv - a cell the
guidebook does not publish takes a named proxy there, never a silent one.

FUEL IS THE ACTIVITY, AND IT RECONCILES TO OCAC BY CONSTRUCTION. Tier 1 factors are
g/kg fuel; the fuel each class burns is the OCAC Road control total for the year
(road.road_control_kt, the same panel the greenhouse-gas side burns, net of the same
household-generator carve-out) split by road._shares' energy-weighted class weights.
Modelled fuel therefore EQUALS sold fuel per fuel per year - the reconciliation the
factor refactor was asked for - and the class split rides the same declared intensity
weights the CO2 side rides, so the two layers cannot disagree about composition.
Off-road (NRV) keeps its share of the diesel and stays outside this layer (1A4c), so
the on-road classes never absorb its fuel.

FOUR PROCESSES, EACH ITS OWN ATOM:
  exhaust          Tier 1 g/kg fuel (Tables 3-5/3-6/3-7): CO, NMVOC, NOx, PM2.5, NH3.
                   Hot and cold running are inside the Tier 1 factor by construction.
                   Exhaust PM is PM2.5 by the chapter's own statement (coarse exhaust
                   PM is negligible, "hence PM=PM2.5"); PM10 is therefore NOT emitted
                   as a separate exhaust species - the old layer's exhaust PM10 was a
                   1.2x scaling of PM2.5 with no basis in the new source.
  evaporative      petrol NMVOC, g/vehicle/day at the guidebook's 20-35 C daily range
                   (Pakistan's), on the fleet model's own active vehicle counts.
  tyre_brake_wear  g/vkm on the same survival-weighted vehicle-kilometres the fuel
  road_wear        split rides: TSP, PM10, PM2.5. No BC: abrasion is a low-temperature
                   process and the chapter proposes no Tier 1 BC for it.

BC is the Tier 1 f-BC fraction of exhaust PM2.5 (Table 3-11) - a component of PM2.5,
never additional mass. SO2 is not a factor: E_SO2 = 2 x kS x fuel mass (equation (2)),
with the sulfur content per fiscal year DECLARED in
data/activity/transport/fuel_sulfur_by_year.csv (diesel on the same cited regime the
railways layer burns; CNG carries no SO2 row - pipeline gas is desulfurised and the
guidebook publishes no CNG sulfur, an absence, not a zero).

EVERY ROW ANCHORS ITS OWN CLASS'S STREAM: ghg_subitem is "{class} {fuel} CO2" (the
real sub_category of the sector's streams, asserted fail-closed by the air join), so
the diesel NOx of trucks rides the truck fleet's geography and the spatial lane
inherits a per-class vector - the repair of the one-anchor-per-fuel shape this build
supersedes. CNG classes share the sector's single CNG stream.

POLLUTANT BASES. NOx is NO2-equivalent (the guidebook's own basis). NMVOC is
non-methane. TSP/PM10 from wear are supplemental strata beside the PM2.5 core and are
never summed with it.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.uncertainty import product
from pkinv.sectors.transport import road
from pkinv.sectors.transport.data import TransportData

CATEGORY = road.CATEGORY
ACTIVITY_DIR = asset_path(os.path.dirname(__file__), "..", "..", "..", "..",
                            "data", "activity", "transport")
FACTORS = asset_path(ACTIVITY_DIR, "emep_tier1_road_air.csv")
CLASS_MAP = asset_path(ACTIVITY_DIR, "emep_class_map.csv")
SULFUR = asset_path(ACTIVITY_DIR, "fuel_sulfur_by_year.csv")

# the panel's own seven-species core slice of this layer (wear TSP/PM10 supplemental)
POLLUTANTS = ("NOx", "CO", "NMVOC", "PM2.5", "SO2", "NH3", "BC")
PROCESSES = ("exhaust", "evaporative", "tyre_brake_wear", "road_wear")


def _read(path):
    return list(_activity_rows(path, comments=True))


def factors():
    """{(process, emep_category, fuel, pollutant): (value, lo, hi)}."""
    out = {}
    for r in _read(FACTORS):
        out[(r["process"], r["emep_category"], r["fuel"], r["pollutant"])] = (
            float(r["value"]),
            float(r["lo"]) if r["lo"] else None,
            float(r["hi"]) if r["hi"] else None)
    return out


def class_map():
    """{(ei_class, fuel): (emep_category, emep_fuel, proxy_note)} - the declared bridge."""
    return {(r["ei_class"], r["fuel"]): (r["emep_category"], r["emep_fuel"],
                                         r["proxy_note"])
            for r in _read(CLASS_MAP)}


def sulfur_ppm(year=None):
    """{fuel: (central, lo, hi)} ppm for one fiscal-end year; raises off the table."""
    year = 2024 if year is None else year
    out = {r["fuel"]: (float(r["ppm_central"]), float(r["ppm_lo"]), float(r["ppm_hi"]))
           for r in _read(SULFUR) if int(r["fiscal_end_year"]) == year}
    if not out:
        raise KeyError("no road-fuel sulfur declared for fiscal-end year %r" % year)
    return out


def _uncert(mean, lo, hi):
    """Half the min-max span as a percentage of the mean - the Tier 1 tables' own
    uncontrolled-to-latest-technology spread, the honest width for an unmeasured fleet."""
    if lo is None or hi is None or not mean:
        return None
    return (hi - lo) / 2.0 / mean * 100.0


def fuel_kt_by_class(data, year=None):
    """{(ei_class, fuel): kt fuel} for the year - the OCAC control split by the energy
    weights, on-road classes only, off-road's share left with 1A4c. CNG is the metered
    OGRA volume converted at the declared NCV, split over the CNG classes by the same
    weights (normalised within CNG's own on-road cells: CNG has one control and no
    off-road claimant)."""
    vkt, _cells, _capped = road.effective_vkt(data, year)
    shares = road._shares(data, vkt)
    out = {}
    for fuel, param in (("Petrol", "Motor Gasoline"), ("Diesel", "Gas/Diesel Oil")):
        kt = road.road_control_kt(data, param, year)
        if fuel == "Petrol":
            kt -= road.generator_petrol_kt()
        for (cls, f), share in shares.items():
            if f == fuel and cls != road.OFF_ROAD and share:
                out[(cls, fuel)] = kt * share
    cng_kt = cng_fuel_kt(data, year)
    cng_cells = {k: v for k, v in vkt.items() if k[1] == "CNG" and k[0] != road.OFF_ROAD}
    tot = sum(cng_cells.values())
    for (cls, _f), km in cng_cells.items():
        if tot:
            out[(cls, "CNG")] = cng_kt * km / tot
    return out


def cng_fuel_kt(data, year=None):
    """CNG mass, kt/yr: the OGRA metered volume through the sector's own energy chain,
    then the declared natural-gas NCV (g/kg factors need mass, not energy)."""
    from pkinv.core.units import mmcfd_to_TJ
    from pkinv.sectors.transport import cng as cng_mod
    year = 2024 if year is None else year
    tj = mmcfd_to_TJ(data.cng_mmcfd(year), data.p("cng_hhv_btu_per_scf"),
                     data.p("cng_gross_to_net"))
    return tj / data.p("cng_ncv_tj_per_gg")


def active_counts(data, year=None):
    """{(ei_class, fuel): active vehicles} - the same survival-weighted fleet the
    vehicle-kilometres ride, without the km, for the per-vehicle evaporative factor."""
    year = data.fleet_year(year)
    out = {}
    for province, district, cls in data.cells(year):
        series = data.stock_series(province, district, cls)
        if year not in series:
            continue
        from pkinv.sectors.transport import fleet
        active, _capped = fleet.active_fleet(
            series, data.p("weibull_beta_%s" % cls), data.p("weibull_life_%s" % cls),
            year)
        for f, share in data.split_for(cls, year).items():
            if share:
                out[(cls, f)] = out.get((cls, f), 0.0) + active * share
    return out


def compute(data, year=None):
    """One row per (class, fuel, process, pollutant). Columns: category, subitem,
    ghg_subitem, ei_class, fuel, process, pollutant, emissions_kt, uncert_pct,
    factor_basis. kt of native pollutant mass."""
    ef = factors()
    bridge = class_map()
    act_u = road.activity_uncert(data)
    rows = []

    def emit(cls, fuel, process, pollutant, kt, factor_u, basis):
        rows.append({
            "category": CATEGORY,
            "subitem": "Road transport %s %s %s" % (cls, fuel.lower(), process),
            "ghg_subitem": ("CNG CO2" if fuel == "CNG" else
                            "%s %s CO2" % (cls, fuel)),
            "ei_class": cls, "fuel": fuel, "process": process,
            "pollutant": pollutant, "emissions_kt": kt,
            "uncert_pct": product(act_u, factor_u) if factor_u else act_u,
            "factor_basis": basis})

    fuel_kt = fuel_kt_by_class(data, year)
    ppm = sulfur_ppm(year)
    for (cls, fuel), kt_fuel in sorted(fuel_kt.items()):
        cat, efuel, proxy = bridge[(cls, fuel)]
        pm25 = None
        pm25_u = None
        for pol in ("CO", "NMVOC", "NOx", "PM2.5", "NH3"):
            key = ("exhaust", cat, efuel, pol)
            if key not in ef:
                continue  # the guidebook's own absence (CNG-bus NH3): absent, not zero
            v, lo, hi = ef[key]
            kt = kt_fuel * v / 1000.0
            u = _uncert(v, lo, hi)
            basis = "Tier 1 %s %s g/kg fuel" % (cat, efuel)
            if proxy:
                basis += "; " + proxy
            emit(cls, fuel, "exhaust", pol, kt, u, basis)
            if pol == "PM2.5":
                pm25, pm25_u = kt, u
        bc_key = ("bc_fraction", cat, efuel, "BC")
        if pm25 is not None and bc_key in ef:
            frac = ef[bc_key][0]
            emit(cls, fuel, "exhaust", "BC", pm25 * frac, pm25_u,
                 "f-BC %.2f of exhaust PM2.5 (Table 3-11); component, not additive"
                 % frac)
        if fuel in ppm:
            c, lo, hi = ppm[fuel]
            emit(cls, fuel, "exhaust", "SO2", 2.0 * c / 1e6 * kt_fuel,
                 _uncert(c, lo, hi),
                 "stoichiometric at %g ppm declared sulfur (fuel_sulfur_by_year)" % c)

    counts = active_counts(data, year)
    for (cls, fuel), n in sorted(counts.items()):
        if fuel != "Petrol":
            continue
        cat, efuel, _proxy = bridge[(cls, fuel)]
        key = ("evaporative", cat, "Petrol", "NMVOC")
        if key not in ef:
            continue  # HDV/BUS petrol: the chapter's own exclusion
        v, lo, hi = ef[key]
        emit(cls, fuel, "evaporative", "NMVOC", n * v * 365.0 / 1e9,
             _uncert(v, lo, hi),
             "Tier 1 %s g/vehicle/day, 20-35 C daily range" % cat)

    vkt, _cells, _capped = road.effective_vkt(data, year)
    for (cls, fuel), km in sorted(vkt.items()):
        if cls == road.OFF_ROAD:
            continue
        cat, _efuel, _proxy = bridge[(cls, fuel)]
        for process in ("tyre_brake_wear", "road_wear"):
            for pol in ("TSP", "PM10", "PM2.5"):
                v, lo, hi = ef[(process, cat, "", pol)]
                emit(cls, fuel, process, pol, km * v / 1e9, _uncert(v, lo, hi),
                     "Tier 1 %s g/vkm (wear factors are fuel-blind)" % cat)
    return rows


def main():
    import io
    from pkinv.paths import OUTPUTS
    rows = compute(TransportData())
    path = asset_path(OUTPUTS, "transport_air_pollutants_2024.csv")
    fields = ("category", "subitem", "ghg_subitem", "ei_class", "fuel", "process",
              "pollutant", "emissions_kt", "uncert_pct", "factor_basis")
    with io.open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            out = dict(r)
            out["emissions_kt"] = "%.6f" % r["emissions_kt"]
            out["uncert_pct"] = ("%.1f" % r["uncert_pct"]
                                 if r["uncert_pct"] is not None else "")
            w.writerow(out)
    total = {}
    for r in rows:
        total[r["pollutant"]] = total.get(r["pollutant"], 0.0) + r["emissions_kt"]
    print("transport air (EMEP Tier 1): %d rows" % len(rows))
    for p in sorted(total):
        print("  %-6s %10.3f kt" % (p, total[p]))


if __name__ == "__main__":
    main()

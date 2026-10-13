"""Air-pollutant co-emissions from civil aviation.

Reported in mass (kt), never converted to CO2e and never part of the greenhouse-gas
reconciliation. Row schema matches the other sectors' air layers so they concatenate.

Two emission bases are retained. NOx, CO and HC use representative aircraft--engine
combinations from the ICAO Aircraft Engine Emissions Databank.  Those combinations are
explicitly flagged as imputed until registration-level engine fits are available. SO2 and
PM2.5 remain fuel-based; BC is a fixed fraction of PM2.5.

Domestic only. The international and non-commercial streams are memo items on the
greenhouse-gas side and are left out here too, so the two layers cover the same scope.
"""
from pkinv.core.uncertainty import product
from pkinv.sectors.aviation import lto
from pkinv.sectors.aviation.data import AviationData

CATEGORY = lto.CATEGORY

PER_LTO = [("NOx", "nox_kg_per_lto"), ("CO", "co_kg_per_lto"),
           ("HC", "hc_kg_per_lto")]
PER_FUEL = [("SO2", "SO2"), ("PM2.5", "PM2.5")]


def compute(data, year=None):
    y = data.year if year is None else year
    cycles = lto.lto_cycles(data, year)["domestic"]
    fuel_t = lto.fuel_tonnes(data, year)["domestic"]
    mix = data.fleet_for("commercial", y)
    ad_u = lto.activity_uncert(data)
    rows = []

    for poll, field in PER_LTO:
        covered = [(ac, share, data.engine_map.get(ac)) for ac, share in mix.items()]
        available_share = sum(share for _ac, share, row in covered if row.get(field) is not None)
        if available_share == 0:
            continue
        # Renormalise only the pollutant factor across types with a published value. The
        # missing share is exposed on every output row; it is not silently called complete.
        ef = sum(share * row[field] for _ac, share, row in covered
                 if row.get(field) is not None) / available_share
        u = 40.0 if poll != "HC" else 60.0
        # rc47 Wave 3: these are cycles x per-CYCLE EFs - LTO quantities by
        # construction, and they now say so: the anchor is the LTO stream the
        # GHG split created, so the pollutant rides airport geography honestly.
        rows.append({"category": CATEGORY, "subitem": "Domestic aviation " + poll,
                     "ghg_subitem": "Domestic aviation LTO CO2", "pollutant": poll,
                     "emissions_kt": cycles * ef / 1e6, "uncert_pct": product(ad_u, u),
                     "method": "ICAO EEDB representative engine",
                     "engine_coverage_share": available_share, "imputed": True})

    # rc47 Wave 3: fuel-based pollutants are FULL-FLIGHT quantities and split the
    # way the fuel does - the LTO share anchors to the airports, the cruise share
    # to the accounting-view stream that is not placed below the province. One row
    # per (pollutant, stage), so no pollutant sits whole at an airport it mostly
    # never visits.
    stage_anchor = {"LTO": "Domestic aviation LTO CO2",
                    "cruise": "Domestic aviation cruise CO2"}
    y = data.year if year is None else year
    lto_fuel = min(fuel_t, cycles * lto._fleet_fuel(data, "commercial", y, False) / 1000.0)
    stage_fuel = {"LTO": lto_fuel, "cruise": fuel_t - lto_fuel}
    pm25 = {}
    for poll, item in PER_FUEL:
        ef = data.efv("aviation_fuel_ef", item)
        for stage, tonnes in stage_fuel.items():
            kt = tonnes * ef / 1e6
            if poll == "PM2.5":
                pm25[stage] = kt
            rows.append({"category": CATEGORY,
                         "subitem": "Domestic aviation %s %s" % (stage, poll),
                         "ghg_subitem": stage_anchor[stage], "pollutant": poll,
                         "emissions_kt": kt,
                         "uncert_pct": product(ad_u, data.efu("aviation_fuel_ef", item)),
                         "method": "fuel-based aviation factor",
                         "engine_coverage_share": "", "imputed": True})

    frac = data.efv("aviation_fuel_ef", "BC_fraction")
    for stage in ("LTO", "cruise"):
        rows.append({"category": CATEGORY,
                     "subitem": "Domestic aviation %s BC" % stage,
                     "ghg_subitem": stage_anchor[stage], "pollutant": "BC",
                     "emissions_kt": pm25[stage] * frac,
                     "uncert_pct": product(ad_u, data.efu("aviation_fuel_ef", "BC_fraction")),
                     "method": "fraction of PM2.5", "engine_coverage_share": "",
                     "imputed": True})
    return rows


def main():
    data = AviationData()
    print("Domestic aviation air pollutants (FY%d):" % data.year)
    for r in compute(data):
        print("  %-6s %9.3f kt  +/-%3.0f%%" % (r["pollutant"], r["emissions_kt"], r["uncert_pct"]))


if __name__ == "__main__":
    main()

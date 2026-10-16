"""Residential primary air-pollutant masses on the common household fuel account.

Reference S uses the survey-anchored household dung series. Alternative L assumes
all ledger-diverted dung is burned in households; material diversion alone does
not establish that destination. Field and household residue burning are separate
flows. Biomass factors use dry fuel including ash: oven-dry firewood, total dry
dung solids and crop-residue dry matter. Historical activity allocation follows
the documented household reconstruction, with interpolation/extrapolation typed.

Andreae/Akagi source-specific biomass factors are retained. Natural gas, LPG,
kerosene and coal use applicable EMEP small-combustion factors on fuel energy.
The gaseous-fuel table is a declared LPG appliance proxy. Missing household
engine/genset factors and unusable charcoal sulfur factors remain omissions.
Particulate definitions are retained where the sources do not permit harmonising
filterable and condensable mass. BC and OC are components of PM2.5, not additions.

Every NOx row is NO2-equivalent; original biomass NO factors are converted by
46/30. Reported kt are native pollutant masses, never CO2-equivalent. These are
gross appliance emissions. An outdoor escape fraction is not estimated, so the
product is not a measured outdoor release or an ambient concentration product.
"""
from pkinv.core.uncertainty import product
from pkinv.sectors.residential import combustion, hies
from pkinv.sectors.residential.data import ResidentialData

CATEGORY = combustion.CATEGORY
POLLUTANTS = ("PM25", "BC", "OC", "CO", "NOx", "NMVOC", "SO2", "NH3")
# Andreae's own labels; the output name is the conventional one.
LABEL = {"PM25": "PM2.5", "PM10": "PM10", "TSP": "TSP"}
# (stream, EF suffix, dry-mass-incl-ash function, activity-uncert key, ghg anchor,
#  pollutant subset). Charcoal omits SO2: Andreae's charcoal-burning SO2 entry rides two
# measurements and prints a range its own average falls outside - an unusable cell,
# omitted rather than guessed (the repo's omit-never-zero-fill rule). Charcoal mass is
# the HIES as-purchased quantity taken as dry: lump charcoal equilibrates at a few
# percent moisture, a conflation bounded well below the stream's 40 percent activity
# uncertainty and stated here rather than papered over with a parameter.
STREAMS = (
    ("Dung cake", "Dung", lambda d, y, a, db: combustion.dung_ts_kg(d, a, db, y),
     "dung", "Dung cake CH4", POLLUTANTS),
    ("Firewood", "Wood", lambda d, y, a, db: combustion.firewood_oven_dry_kg(d, y),
     "woodfuel", "Firewood CH4", POLLUTANTS),
    ("Crop residues", "Residue", lambda d, y, a, db: combustion.residue_dry_kg(d, a),
     "residue", "Crop residues CH4", POLLUTANTS),
    ("Charcoal", "Charcoal", lambda d, y, a, db: hies.sole_source_kg("charcoal"),
     "charcoal", "Charcoal CH4",
     ("PM25", "BC", "OC", "CO", "NOx", "NMVOC", "NH3")),
)

# Fossil streams: EMEP Tier 1 on ENERGY (g/GJ), not mass. NH3 is omitted where the
# chapter's tables mark it not applicable (gas, LPG, kerosene), never zero-filled; coal
# is the one fossil household fuel with a printed NH3 factor and carries it. Generators
# have NO air rows: the chapter has no household-genset class, and borrowing road
# exhaust factors would cross the mobile/stationary boundary this sector polices - the
# omission is declared on the completeness table, bounded by the stream's 56 kt of fuel.
FOSSIL_POLLUTANTS = ("NOx", "CO", "NMVOC", "SO2", "PM25")
# (stream, factor-item fuel suffix, activity-uncert key, ghg anchor, BC fraction item,
#  pollutant subset)
FOSSIL_STREAMS = (
    ("Natural gas", "NaturalGas", "gas", "Natural gas CO2", "BC_of_PM25_gaseous",
     FOSSIL_POLLUTANTS),
    ("LPG", "LPG", "lpg", "LPG CO2", "BC_of_PM25_gaseous", FOSSIL_POLLUTANTS),
    ("Kerosene", "Kerosene", "kerosene", "Kerosene CO2", "BC_of_PM25_liquid",
     FOSSIL_POLLUTANTS),
    ("Coal", "Coal", "coal", "Coal CO2", "BC_of_PM25_solid",
     ("NOx", "CO", "NMVOC", "SO2", "PM25", "PM10", "TSP", "NH3")),
)


def compute(data, year=None, agri=None, dung_basis=None):
    """Return one row per stream and pollutant. Mass in kt, never CO2e.

    dung_basis selects whose dung quantity is burned: None is the reference (the
    household survey, since rc67), "ledger" is configuration L (all diverted dung).
    Everything else is configuration-invariant.
    """
    rows = []
    for stream, suffix, dry_mass, ad_key, ghg_subitem, polls in STREAMS:
        kg = dry_mass(data, year, agri, dung_basis)
        ad_u = data.p("activity_uncert_" + ad_key)
        for poll in polls:
            item = "Gef_%s_%s" % (poll, suffix)
            name = LABEL.get(poll, poll)
            rows.append({
                "category": CATEGORY, "subitem": "%s %s" % (stream, name),
                "ghg_subitem": ghg_subitem, "pollutant": name,
                "emissions_kt": kg * data.efv("residential_biofuel", item) / 1e9,
                "uncert_pct": product(ad_u, data.efu("residential_biofuel", item)),
            })

    tj = combustion.fuel_TJ(data, year, agri, dung_basis=dung_basis)
    for stream, fuel, ad_key, ghg_subitem, bc_item, polls in FOSSIL_STREAMS:
        gj = tj[stream] * 1000.0
        ad_u = data.p("activity_uncert_" + ad_key)
        pm25_kt = None
        for poll in polls:
            item = "Gef_%s_%s" % (poll, fuel)
            name = LABEL.get(poll, poll)
            kt = gj * data.efv("residential_air_fossil", item) / 1e9
            if poll == "PM25":
                pm25_kt = kt
            rows.append({
                "category": CATEGORY, "subitem": "%s %s" % (stream, name),
                "ghg_subitem": ghg_subitem, "pollutant": name,
                "emissions_kt": kt,
                "uncert_pct": product(ad_u,
                                      data.efu("residential_air_fossil", item)),
            })
        rows.append({
            "category": CATEGORY, "subitem": "%s BC" % stream,
            "ghg_subitem": ghg_subitem, "pollutant": "BC",
            "emissions_kt": pm25_kt * data.efv("residential_air_fossil_frac", bc_item),
            "uncert_pct": product(
                ad_u,
                data.efu("residential_air_fossil", "Gef_PM25_%s" % fuel),
                data.efu("residential_air_fossil_frac", bc_item)),
        })
    return rows


def main():
    data = ResidentialData()
    rows = compute(data)
    print("Residential solid-fuel air pollutants (FY%d-%02d), biomass only:"
          % (data.year - 1, data.year % 100))
    totals = {}
    for r in rows:
        totals[r["pollutant"]] = totals.get(r["pollutant"], 0.0) + r["emissions_kt"]
        print("  %-14s %-6s %9.2f kt  +/-%3.0f%%"
              % (r["subitem"], "", r["emissions_kt"], r["uncert_pct"]))
    print("  ---")
    for p, v in sorted(totals.items(), key=lambda kv: -kv[1]):
        print("  %-6s total %9.2f kt" % (p, v))


if __name__ == "__main__":
    main()

"""Air-pollutant co-emissions from residential solid-fuel burning.

Reported in mass (kt), never converted to CO2e and never part of the greenhouse-gas
reconciliation. Row schema matches the other sectors' air layers so they concatenate.

THIS IS PROBABLY THE MOST IMPORTANT AIR-QUALITY LAYER IN THE INVENTORY. On the
greenhouse-gas side, household fuel is about six percent of the national total and the
sector is a minor one. On the air-quality side, residential biomass is repeatedly identified as the
largest single source of primary PM2.5 and black carbon in Pakistan and across South Asia -
larger than transport, larger than industry. The same two streams that contribute a few
megatonnes of CO2e here contribute most of the country's household and ambient particulate
exposure.

DUNG AND WOOD ARE KEPT APART BECAUSE THEY BURN DIFFERENTLY. Andreae (2019) tabulates dung
as its own category rather than folding it into biofuels, and the difference is real: 24%
more PM2.5 per kilogram and half again the ammonia. Pakistan burns a great deal of dung -
this inventory derives 38.7 Mt of it a year from the agriculture sector's own nitrogen
flow - so collapsing the two would lose a distinction the measurements support.

SAME SOURCE FAMILY AS THE OTHER BURNING LAYERS, DELIBERATELY. Crop-residue burning
(agriculture) and open waste burning (waste) already take their pollutant factors from
Andreae 2019 and Akagi 2011. Using the same compilation for household fuel means Pakistan's
three combustion inventories rest on one set of field measurements and can be compared
against each other without a methods caveat.

THE MASS BASIS IS STATED, NOT ASSUMED - the August 2026 correction. Andreae's factors are
per kilogram of DRY FUEL INCLUDING ASH. Dung burns combustion.dung_ts_kg - total dry
solids, VS plus the cake's mineral ash, not the ash-free volatile solids this layer once
used (that conflation understated dung PM by the ash fraction; a test pins the pairing).
Firewood burns combustion.firewood_oven_dry_kg - the HIES air-dry survey quantity less
its equilibrium moisture - since the survey re-anchoring; the superseded FAOSTAT path was
already oven-dry through IPCC's BCEF_R, so the basis is unchanged even though the anchor
moved. The same fuel chain that drives the greenhouse-gas side drives the pollutants; the
two layers differ only by the moisture the energy basis adds.

FOSSIL HOUSEHOLD FUELS ARE COVERED - the August 2026 extension. Gas, LPG and kerosene
carry the EMEP/EEA 1.A.4 Small Combustion Tier 1 factors (sources/EMEP/, the chapter this
layer was once recorded as blocked on), on the same fuel energies the greenhouse-gas side
burns; household coal joined them in the August 2026 new-streams round on the chapter's
hard-coal table. Generators carry no air rows: the chapter has no household-genset class,
and road exhaust factors would cross the mobile/stationary boundary - a declared omission
bounded by the stream's 56 kt of fuel. Their basis is energy (g/GJ), unlike Andreae's per-kilogram, and the difference is
carried on the rows, not assumed away. LPG is assigned the gaseous-fuel table (a
premixed-flame appliance class, no separate LPG column exists) and the assignment is noted
on its rows. NH3 is 'not applicable' in the chapter's own tables for these fuels and is
omitted rather than zero-filled. The chapter's own review note - that it is unclear
whether its PM factors are filterable-only or include condensables - is quoted on the PM
rows; the fossil PM contribution is under one percent of the biomass PM either way.

ONE NOX BASIS. Every NOx row is NO2-equivalent: EMEP publishes as NO2, and the Andreae
rows (published as NO) are converted x46/30 on the factor rows themselves - mass as NO
cannot be added to mass as NO2, and the road-transport comparison is on the NO2 basis.
The August 2026 correction; the previous edition summed mixed bases.
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

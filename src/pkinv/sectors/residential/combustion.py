"""Residential fuel combustion - IPCC 1A4b.

ANCHORED ON FUEL, like road transport. Every stream is a national quantity of fuel
delivered to households, converted to TJ and run through IPCC Vol 2 Ch 2 Table 2.5. There
is no household-count model and no per-capita intensity, so there is nothing that can
drift away from the fuel that was actually supplied.

WHICH IPCC TABLE. Chapter 2 publishes four parallel default tables and this sector must
use Table 2.5, Residential and Agriculture/Forestry/Fishing - NOT Table 2.2, Energy
Industries, which the power sector uses. CO2 is identical between them, because it depends
only on the carbon in the fuel. CH4 and N2O are not: residential natural gas is 5 kg
CH4/TJ against 1 for a utility boiler, and residential kerosene is 10 against 3. A small
appliance burns less completely than a power station. src/pkinv/sectors/power/combustion.py
carries the mirror-image warning, and tests/test_residential.py pins the direction.

ELECTRICITY IS NOT HERE. Household electricity is the largest single item in every
Pakistani energy statistic - 39,728 GWh, nearly half of national consumption - and it is
deliberately absent. Those emissions are generated at the power station and are already
counted in 1A1a. Adding them here would double-count roughly a quarter of the national
inventory. tests/test_residential.py asserts no electricity stream exists, so a future
edit that "fixes the missing electricity" fails loudly.

THE DUNG-CAKE TRANSFER, CLOSED. The agriculture sector removes 28 percent of cattle and
30 percent of buffalo excreted nitrogen from the manure-management balance because that
dung is burnt as household fuel, and books it IE to Energy (see data/mms_shares.csv and
docs/completeness.md). Until now nothing received it. This module does, and it derives the
mass from agriculture's own nitrogen flow rather than estimating dung independently: the
same herd, the same burned_fuel shares, converted to volatile solids through IPCC's VS
rates for the same animal categories and region that supply the nitrogen rates. The
closure is exact by construction and tested with ==, not a tolerance.

WHAT THE CLOSURE DOES NOT SAY (rc67). It closes the SUPPLY: the dung agriculture diverts
is a definite mass. It says nothing about who burns it. Through rc66 the reference burned
all of it in households; the household survey observes about a fifth. The reference now
books what the survey observes (dung_air_dry_kg), and the remainder of the diverted mass
is carried as unresolved, outside the total, with its candidate destinations priced
beside it. Burning all of it in households survives as configuration L.

THREE DUNG MASSES, ONE NITROGEN ANCHOR - the basis correction of August 2026. The ledger
supplies ash-free volatile solids (dung_vs_kg). Total dry solids add the mineral ash a
hand-formed cake carries (dung_ts_kg = VS/(1-ash)); as-received cake mass adds its air-dry
moisture (dung_air_dry_kg = TS/(1-moisture)). Energy pairs the AS-RECEIVED cake mass with
IPCC's as-received Other Primary Solid Biomass NCV; the air layer burns TOTAL DRY SOLIDS,
which is the basis Andreae's per-kilogram-dry-fuel factors describe. The previous pairing -
ash-free VS with the as-received NCV - conflated three bases and understated the stream;
it survives as the structural scenario dung_basis_legacy_vs so the correction is visible,
and the superseded claim that the pairing was "physically correct" is retracted on the NCV
factor row itself.

BIOGENIC CO2 IS A MEMO. Dung and firewood CO2 is reported outside the sector total, as
IPCC requires and as the waste sector already does for burnt biomass. Their CH4 and N2O
ARE counted - incomplete combustion is a real net source regardless of the carbon's
origin. Pakistan's own BUR-1 states the same convention for the same fuels.

FIREWOOD IS SURVEY-PRIMARY - the re-anchoring of August 2026. Firewood is the second
largest household fuel in the country and the only fuel here with no supply-side control:
nobody meters trees. The quantity is now the HIES 2024-25 design-weighted national total,
23.1 Mt of air-dry wood entering households as purchased, own-produced, in-kind or gifted
consumption - a measurement, where the previous FAOSTAT series was FAO's own flagged
estimate, unmoving since 2015. Two independent anchors corroborate it: HIES 2018-19
reproduces the total within 6 percent, and FAOSTAT's moisture-matched equivalent sits 7
percent above. The bases pair cleanly now too - air-dry survey mass with IPCC's
as-received NCV for energy, oven-dry mass (via firewood_moisture_ar) for Andreae's
per-kg-dry-fuel air factors - where the old path burned oven-dry mass on the as-received
NCV and had to lean on the factor's published CI to excuse it. FAOSTAT survives as the
structural scenario firewood_faostat; see hies.py for what surveys are and are not
allowed to govern.
"""
from pkinv.core.uncertainty import product
from pkinv.sectors.agriculture import manure
from pkinv.sectors.agriculture.ef_library import InventoryData

CATEGORY = "Residential fuel combustion"
DUNG_GROUP = "residential_dung"

# (stream label, IPCC emission-factor item, activity-uncertainty parameter suffix)
FOSSIL_FUELS = (("Natural gas", "Natural Gas", "gas"),
                ("LPG", "Liquefied Petroleum Gases", "lpg"),
                ("Kerosene", "Other Kerosene", "kerosene"),
                ("Coal", "Other Bituminous Coal", "coal"),
                ("Generators", "Motor Gasoline", "generators"))
# (stream label, IPCC emission-factor item, activity-uncertainty suffix, corr group).
# Biomass streams: CH4 and N2O counted, CO2 to the memo.
BIOMASS_FUELS = (("Dung cake", "Other Primary Solid Biomass", "dung", DUNG_GROUP),
                 ("Firewood", "Wood/Wood Waste", "woodfuel", None),
                 ("Charcoal", "Charcoal", "charcoal", None),
                 ("Crop residues", "Other Primary Solid Biomass", "residue", None))
# mms_shares.csv is keyed by herd species; manure.py splits cattle into dairy and other.
MMS_KEY = {"dairy_cattle": "cattle", "other_cattle": "cattle"}
# Species whose diverted nitrogen becomes dung cake. Sheep, goats and camels have no
# burned_fuel share in mms_shares.csv; poultry litter is not made into cake.
DUNG_SPECIES = ("dairy_cattle", "other_cattle", "buffalo")


def diverted_n_by_species(agri=None):
    """{species: kg N/yr} that agriculture removes as dung-cake fuel.

    Recomputed here from agriculture's own excretion pools and MMS shares rather than
    passed across, because manure.compute returns only the national total. The two must
    agree exactly; tests/test_residential.py asserts it.
    """
    agri = InventoryData() if agri is None else agri
    _components, npools = manure.compute(agri)
    out = {}
    for species, nex in npools["nex_by_species"].items():
        share = agri.mms[MMS_KEY.get(species, species)].get("burned_fuel", 0.0)
        if share:
            out[species] = nex * share
    return out


def dung_vs_kg(data, agri=None):
    """Ash-free volatile solids diverted as dung cake, kg/yr - the ledger intermediate.

    Per species: agriculture's diverted nitrogen times the VS-to-nitrogen rate ratio for
    the same animal category (algebraically N x vs_rate/nex_rate; the typical animal mass
    scales both rates identically and cancels - stated here so nobody mistakes the
    intermediate head-count arithmetic for a lever). This is NOT a burnable-fuel mass: VS
    excludes the mineral ash a cake carries and the moisture it holds. dung_ts_kg and
    dung_air_dry_kg are the fuel bases.
    """
    agri = InventoryData() if agri is None else agri
    total = 0.0
    for species, n in diverted_n_by_species(agri).items():
        tam = agri.p("tam_" + species)
        nex_per_head = agri.p("nex_rate_" + species) * tam * 365.0 / 1000.0
        vs_per_head = data.p("vs_rate_" + species) * tam * 365.0 / 1000.0
        total += (n / nex_per_head) * vs_per_head
    return total


def reference_basis(basis=None):
    """The dung basis a call means: the named one, or the reference (rc67: the survey)."""
    from pkinv.core import configurations
    if basis is None:
        return configurations.REFERENCE_DUNG_BASIS
    if basis not in (configurations.REFERENCE_DUNG_BASIS,
                     configurations.ALTERNATIVE_DUNG_BASIS):
        raise ValueError("dung basis must be 'survey' or 'ledger', not %r" % (basis,))
    return basis


def dung_ts_kg(data, agri=None, basis=None, year=None):
    """Total dry solids of the cake, kg/yr: the basis Andreae's per-kg-dry-fuel
    pollutant factors describe.

    Under the LEDGER configuration this is VS plus the mineral ash a hand-formed cake
    carries (cake ash exceeds IPCC eq 10.24's fresh-manure 0.08 because of soil
    contact; the fraction is a declared literature-range parameter). Under the SURVEY
    configuration it is the HIES-reported air-dry cake less its equilibrium moisture -
    the same composition parameters, so the two configurations differ ONLY in whose
    quantity they believe, never in chemistry.
    """
    if reference_basis(basis) == "survey":
        return (dung_air_dry_kg(data, agri, "survey", year)
                * (1.0 - data.p("dung_cake_moisture_ar")))
    return dung_vs_kg(data, agri) / (1.0 - data.p("dung_ash_frac_dry"))


def dung_air_dry_kg(data, agri=None, basis=None, year=None):
    """As-received (air-dry) cake mass, kg/yr - the mass the energy calculation burns.

    basis="survey" (THE REFERENCE since rc67): what households report burning. The two
    HIES rounds (2018-19: 6.50 Mt; 2024-25: 11.97 Mt) anchor a per-household quantity,
    interpolated between them and held at the first round's rate before it, times each
    year's households (timeseries.dung_survey_air_dry_kg). FY2023-24 lies between the
    rounds and takes the interpolated 10.93 Mt, not the later round's own figure: one
    construction for every year of the panel.

    basis="ledger" (configuration L, the alternative): agriculture's diverted nitrogen
    through the VS/ash/moisture chain, 58.74 Mt in FY2023-24, ALL of it burned by
    households. Mass conservation fixes what agriculture diverted. It is not evidence of
    where the diverted mass went, and through rc66 this module's default treated it as
    if it were.

    The identity is D_diverted = D_household + D_unresolved. Under the reference about
    47.8 Mt of diverted cake, and the nitrogen in it, has no observed destination
    (candidates: non-household burning, return to manure management, field application,
    an over-stated diversion). It sits in no emitting account; its destinations are
    priced one at a time, for every year, in outputs/national_dung_variants.csv.
    """
    if reference_basis(basis) == "survey":
        from pkinv.sectors.residential import timeseries
        return timeseries.dung_survey_air_dry_kg(data.year if year is None else year)
    return dung_vs_kg(data, agri) / (1.0 - data.p("dung_ash_frac_dry")) \
        / (1.0 - data.p("dung_cake_moisture_ar"))


def woodfuel_dry_matter_kg(data, year=None):
    """FAOSTAT removal volume (m3) -> oven-dry biomass (kg) through IPCC BCEF_R.

    SCENARIO PATH ONLY (firewood_faostat) since the HIES re-anchoring; the reported
    estimate is firewood_air_dry_kg. Kept because the comparison table and the structural
    scenario both need FAOSTAT's number on a declared basis.
    """
    return data.woodfuel_m3(year) * data.p("woodfuel_bcef_r") * 1000.0


def firewood_air_dry_kg(data, year=None):
    """The reported firewood activity: HIES air-dry kg/yr entering households.

    year is accepted for signature parity with the FAOSTAT path but unused - HIES is a
    survey round, not a series; the temporal phase will interpolate between rounds.
    """
    from pkinv.sectors.residential import hies
    return hies.firewood_air_dry_kg()


def firewood_oven_dry_kg(data, year=None):
    """Oven-dry firewood mass, kg/yr - the basis Andreae's air factors burn."""
    return firewood_air_dry_kg(data, year) * (1.0 - data.p("firewood_moisture_ar"))


def residue_dry_kg(data, agri=None):
    """Crop-residue dry matter burned as household fuel, kg/yr - the LEDGER's number.

    Supply-side control, exactly like dung: agriculture's residue ledger diverts
    frac_fuel of each crop's above-ground residue to households, and the closure test
    (returned + burned + fuel + other == 1, other >= 0) prevents the three consuming
    layers from summing past the residue that exists. The HIES expenditure items
    corroborate the destination and bracket the mass (see hies.residue_implied_range_kg)
    but cannot fix it - they record rupees, not kilograms.
    """
    from pkinv.sectors.agriculture import residue_ledger
    return residue_ledger.fuel_available_t(agri) * 1000.0


def residue_air_dry_kg(data, agri=None):
    """As-received residue mass: dry matter plus air-dry equilibrium moisture - the
    basis IPCC's as-received Other Primary Solid Biomass NCV describes."""
    return residue_dry_kg(data, agri) / (1.0 - data.p("residue_moisture_ar"))


def generator_petrol_kt(data=None):
    """Household generator petrol, kt/yr, from HIES expenditure over the administered
    price. This mass is DEDUCTED from the road-transport petrol control (the second
    carve-out on that control after railway diesel): the fuel is bought at the same
    stations but burned in stationary household engines, so it books to 1A4b.
    tests/test_residential.py asserts the carve-out equality with road.py."""
    from pkinv.sectors.residential import hies
    from pkinv.sectors.residential.data import ResidentialData
    data = ResidentialData() if data is None else data
    return (hies.generator_fuel_litres(data)
            * data.p("petrol_density_kg_l") / 1e6)


def fuel_TJ(data, year=None, agri=None, firewood_basis="hies", dung_basis=None):
    """{stream: TJ} for every residential fuel, fossil and biomass alike.

    firewood_basis "hies" (reported) pairs the survey's air-dry mass with the as-received
    NCV; "faostat" reproduces the superseded path - FAOSTAT oven-dry mass on the same NCV,
    the basis conflation the old estimate carried - for the structural scenario.
    """
    gas_mmcf = data.quantity("Natural Gas", year) * 365.0        # MMCFD -> MMCF/yr
    lpg_gg = (data.quantity("Liquefied Petroleum Gases", year)
              * data.p("lpg_domestic_share") / 1000.0)           # t -> Gg
    kero_gg = data.quantity("Other Kerosene", year)              # kt == Gg
    if firewood_basis == "hies":
        firewood_gg = firewood_air_dry_kg(data) / 1e6
    elif firewood_basis == "faostat":
        firewood_gg = woodfuel_dry_matter_kg(data, year) / 1e6
    else:
        raise ValueError("firewood_basis must be 'hies' or 'faostat', not %r"
                         % (firewood_basis,))
    from pkinv.sectors.residential import hies
    return {
        "Natural gas": gas_mmcf * data.p("gas_mmcf_to_TJ"),
        "LPG": lpg_gg * data.efv("residential_ncv", "Liquefied Petroleum Gases"),
        "Kerosene": kero_gg * data.efv("residential_ncv", "Other Kerosene"),
        "Dung cake": (dung_air_dry_kg(data, agri, dung_basis, year) / 1e6
                      * data.efv("residential_ncv", "Other Primary Solid Biomass")),
        "Firewood": firewood_gg * data.efv("residential_ncv", "Wood/Wood Waste"),
        "Charcoal": (hies.sole_source_kg("charcoal") / 1e6
                     * data.efv("residential_ncv", "Charcoal")),
        "Coal": (hies.sole_source_kg("coal") / 1e6
                 * data.efv("residential_ncv", "Other Bituminous Coal")),
        "Crop residues": (residue_air_dry_kg(data, agri) / 1e6
                          * data.efv("residential_ncv", "Other Primary Solid Biomass")),
        "Generators": (generator_petrol_kt(data)
                       * data.efv("residential_ncv", "Motor Gasoline")),
    }


def _row(subitem, gas, tj, ef, ad_u, ef_u, fossil=False, corr_group=None):
    r = {"category": CATEGORY, "subitem": subitem, "gas": gas,
         "emissions_Gg": tj * ef / 1e6, "uncert_pct": product(ad_u, ef_u)}
    if fossil:
        r["fossil"] = True
    if corr_group:
        r["corr_group"] = corr_group
    return r


def compute(data, year=None, woodfuel_override=None, agri=None, dung_basis=None):
    """Return (components, memo).

    components: 1A4b, fossil CO2/CH4/N2O plus biomass CH4/N2O.
    memo:       biogenic CO2 from dung cake and firewood, which must not be summed in.

    woodfuel_override takes "none", "low" or "high" for the sensitivity run - firewood is
    the softest number in the sector and the runner reports the range it spans.
    """
    tj = fuel_TJ(data, year, agri, dung_basis=dung_basis)
    if woodfuel_override is not None:
        spread = data.p("activity_uncert_woodfuel") / 100.0
        factor = {"none": 0.0, "low": 1.0 - spread, "high": 1.0 + spread}
        if woodfuel_override not in factor:
            raise ValueError("woodfuel_override must be none, low or high, not %r"
                             % (woodfuel_override,))
        tj["Firewood"] *= factor[woodfuel_override]

    components = []
    for stream, item, ad_key in FOSSIL_FUELS:
        ad_u = data.p("activity_uncert_" + ad_key)
        t = tj[stream]
        components.append(_row("%s CO2" % stream, "CO2", t,
                               data.efv("residential_combustion_co2", item), ad_u,
                               data.efu("residential_combustion_co2", item)))
        # Fossil CH4 takes AR5 30, not 28 - as in power, aviation and transport.
        components.append(_row("%s CH4" % stream, "CH4", t,
                               data.efv("residential_combustion_ch4", item), ad_u,
                               data.efu("residential_combustion_ch4", item), fossil=True))
        components.append(_row("%s N2O" % stream, "N2O", t,
                               data.efv("residential_combustion_n2o", item), ad_u,
                               data.efu("residential_combustion_n2o", item)))

    # Biomass: CH4 and N2O only. No CO2 component - it is biogenic and goes to the memo.
    for stream, item, ad_key, group in BIOMASS_FUELS:
        if ad_key == "dung" and reference_basis(dung_basis) == "survey":
            # the survey's own uncertainty, not the nitrogen chain's: a different
            # quantity from a different instrument (rc67)
            ad_key = "dung_survey"
        ad_u = data.p("activity_uncert_" + ad_key)
        t = tj[stream]
        components.append(_row("%s CH4" % stream, "CH4", t,
                               data.efv("residential_combustion_ch4", item), ad_u,
                               data.efu("residential_combustion_ch4", item),
                               corr_group=group))
        components.append(_row("%s N2O" % stream, "N2O", t,
                               data.efv("residential_combustion_n2o", item), ad_u,
                               data.efu("residential_combustion_n2o", item),
                               corr_group=group))

    memo = [
        {"item": "Biogenic CO2 from dung cake (IPCC memo item)", "gas": "CO2",
         "emissions_Gg": (tj["Dung cake"]
                          * data.efv("residential_combustion_co2",
                                     "Other Primary Solid Biomass") / 1e6),
         "note": "Reported outside the national total: the carbon was fixed by the crop "
                 "the animal ate within the same year. Its CH4 and N2O are counted as "
                 "components, because incomplete combustion is a net source whatever the "
                 "carbon's origin. Pakistan's BUR-1 states the same convention."},
        {"item": "Biogenic CO2 from firewood (IPCC memo item)", "gas": "CO2",
         "emissions_Gg": (tj["Firewood"]
                          * data.efv("residential_combustion_co2", "Wood/Wood Waste") / 1e6),
         "note": "Memo under IPCC's biomass convention. Any net carbon loss from the "
                 "forest and tree stock that supplies this wood belongs in LULUCF, not "
                 "here - counting it in both places is the double-count the memo "
                 "convention exists to prevent."},
        {"item": "Biogenic CO2 from crop residues (IPCC memo item)", "gas": "CO2",
         "emissions_Gg": (tj["Crop residues"]
                          * data.efv("residential_combustion_co2",
                                     "Other Primary Solid Biomass") / 1e6),
         "note": "Memo: the carbon was fixed by the crop within the year. The mass comes "
                 "from the agriculture residue ledger's frac_fuel destination, so it "
                 "cannot overlap the field-burning category or the soils return."},
        {"item": "Biogenic CO2 from charcoal (IPCC memo item)", "gas": "CO2",
         "emissions_Gg": (tj["Charcoal"]
                          * data.efv("residential_combustion_co2", "Charcoal") / 1e6),
         "note": "Memo, like wood. The 4-6 kg of wood consumed per kg of charcoal MADE "
                 "is a separate upstream loss this inventory does not estimate - see "
                 "the completeness table."},
    ]
    return components, memo

"""Main activity electricity and heat production - IPCC 1A1a.

Fuel consumed (NEPRA SIR Table 3, tonnes of oil equivalent) -> TJ -> IPCC 2006 Vol 2 Ch 2
Table 2.2 factors. A fuel-based Tier 1 inventory with no efficiency assumption anywhere.

Why fuel rather than generation. Generation would need a heat rate to become fuel, and the
per-plant heat rates in SIR Tables 20/23/28 are a large parsing job for a number NEPRA
already publishes directly. More importantly, TOE is an energy unit: the IPCC bituminous
and lignite CO2 factors differ by only 6.8% per TJ but by a factor of two per TONNE of
coal, because their net calorific values differ by 54% and lignite's own range spans
5.50-21.6 TJ/Gg. Working in energy makes that uncertainty disappear.

TABLE 2.2, NOT 2.3, 2.4 OR 2.5. Chapter 2 publishes four parallel emission-factor tables,
for energy industries, manufacturing, commercial and residential. CO2 is identical across
all four because it depends only on carbon content, but CH4 and N2O are not - the
residential table would materially inflate them. Grid power generation is 1A1a, so Table
2.2 is the right one. Captive and industrial self-generation is 1A2 and uses Table 2.3;
NEPRA's scope excludes it, which is most of why Ember's Pakistani total exceeds NEPRA's.

NO SEPARATE OXIDATION FACTOR. The 2006 Guidelines assume complete oxidation and fold it
into the emission factor - Table 1.4 carries an explicit oxidation column that is 1.0 for
every fuel. Applying the old 1996-era 0.98 on top would double-discount. Note the
deliberate contrast with the waste sector, which DOES carry an oxidation factor of 0.71,
because open burning genuinely is incomplete. A test pins this so nobody "fixes" it.
"""
from pkinv.core.uncertainty import product
from pkinv.sectors.fugitives import post_meter

CATEGORY = "Electricity and heat production"

# SIR Table 3 fuel label -> (CO2 emission-factor item, CH4/N2O item)
FUEL_EF = {
    "Gas": ("Natural Gas", "Natural Gas"),
    "Furnace Oil": ("Residual Fuel Oil", "Oil"),
    "Diesel Oil": ("Gas/Diesel Oil", "Oil"),
    # Coal is handled separately: SIR reports one combined figure and the sector blends
    # the imported-bituminous and Thar-lignite factors.
}


def fuel_TJ(data, year=None):
    """{fuel: TJ}. Public so the air-pollutant layer reuses the identical energy."""
    toe_tj = data.p("toe_to_tj")
    return {f: t * toe_tj for f, t in data.fuel_for(year).items()}


def coal_lignite_share(data, year=None):
    """The lignite share of coal generation for one year, and where it comes from.

    THIS USED TO BE ONE NUMBER FOR EVERY YEAR, and the number described FY2023-24. The
    parameter's own note warns that its predecessor (0.35) was wrong because it was read
    off an earlier year's generation mix while the Thar fleet ramped - and the same defect
    then pointed the other way, applying a three-quarters-lignite blend back to years when
    no domestic-lignite plant was running. the plant closure's coal_blend() has been
    year-aware the whole time and was never called from here.

    Three regimes, each declared:

      the reference year   the published parameter, which IS the ledger's own FY2023-24
                           figure rounded for publication (0.79 against 0.7933). The
                           parameter carries the source and the uncertainty, so it stays
                           the reported value and the headline does not move on a rounding.
      2019-20 onwards      the ledger's generation-weighted mid for that year, from
                           data/activity/power/plant_fuel_ledger.csv.
      before 2019-20       zero, because the domestic-lignite fleet did not exist: the
                           first Thar unit starts in 2019 and Thar Energy, Lucky and
                           ThalNova in 2022-23 (GEM commissioning years), while the coal
                           generation of those years is the imported Sahiwal and Port
                           Qasim units that came on in 2017. The caveat, stated rather
                           than hidden: Lakhra is domestic lignite and dates to 1995, so
                           the true share is not exactly zero. It is a 150 MW plant that
                           barely runs, and total coal generation in the two years it
                           could matter is 148 and 1,059 GWh - if every one of those
                           kilowatt-hours were lignite the factor moves by 6,400 kg/TJ on
                           under two percent of the decade's coal, which is smaller than
                           the parameter's own 12 percent uncertainty.

    The per-year shares are READ FROM DATA, not computed here, and deliberately so.
    The plant closure derives them, but it also carries IPCC default NCVs for Thar lignite -
    the weakest evidence in this sector - and tests/test_plant_closure.py holds that this
    module may not import it, so a default NCV can never reach the emissions path. The
    shares are therefore derived once into data/power_coal_blend_by_year.csv, each row
    carrying its basis, its source and its lo/hi bound, where they can be audited like any
    other activity datum instead of appearing out of a function call.
    """
    if year is None or year == data.year:
        return data.p("coal_lignite_share")
    return data.coal_blend_share(year)


def coal_co2_factor(data, override=None, year=None):
    """Generation-weighted kg CO2/TJ for coal, for the year asked about.

    override='bituminous' or 'lignite' forces a bound, for the sensitivity run.
    """
    bit = data.efv("power_combustion_co2", "Other Bituminous Coal")
    lig = data.efv("power_combustion_co2", "Lignite")
    if override == "bituminous":
        return bit
    if override == "lignite":
        return lig
    share = coal_lignite_share(data, year)
    return bit * (1.0 - share) + lig * share


# Which per-fuel activity uncertainty each Table 3 row carries. One flat percentage used
# to cover all four; the evidence never supported that - the gas row is corroborated by
# exact MMBTU meters, the coal mass by two institutions to 2 percent, and furnace oil by
# nothing - so each row now carries its own value with its basis in the parameter note.
ACTIVITY_UNCERT_KEY = {"Coal": "activity_uncert_coal", "Gas": "activity_uncert_gas",
                       "Furnace Oil": "activity_uncert_fo",
                       "Diesel Oil": "activity_uncert_diesel"}

# One conversion practice underlies all four TOE rows, so their activity errors do not
# cancel in the category sum. The group makes combine_sum and the Monte Carlo add them
# linearly - CO2 rows only, because the CH4/N2O rows are 150-percent-factor-dominated and
# linear-adding their absolute uncertainties into the group would swamp it with noise.
TOE_CORR_GROUP = "1a1a_toe_activity"


def activity_uncert(data, fuel):
    """Per-fuel activity uncertainty on the TOE row, with the (now zero) conversion
    residual kept in the formula so a future re-estimate of toe_to_tj flows through."""
    return product(data.p(ACTIVITY_UNCERT_KEY[fuel]), data.pu("toe_to_tj"))


def coal_co2_factor_uncert(data):
    """Delta-method uncertainty of the blended coal CO2 factor.

    The previous form - product(lignite EF uncert, blend uncert) = 16.97 percent - applied
    the whole 12 percent blend range as if the share multiplied the whole factor. It does
    not: the factor is bit + share x (lig - bit), so a 12 percent share error moves the
    blend by share x (EF_lig - EF_bit) / EF_blend = about 0.6 percent. Propagating each
    term by its actual sensitivity:

        u^2 = (w_lig u_lig)^2 + (w_bit u_bit)^2 + (share dEF/EF u_share)^2

    with w the factor-weighted rank shares. The blend ENDPOINTS remain published as the
    all-bituminous/all-lignite scenario rows, so nothing the old number gestured at is
    lost - it is just no longer misfiled as parametric width.
    """
    import math
    share = data.p("coal_lignite_share")
    lig, bit = (data.efv("power_combustion_co2", "Lignite"),
                data.efv("power_combustion_co2", "Other Bituminous Coal"))
    blend = bit * (1.0 - share) + lig * share
    w_lig, w_bit = share * lig / blend, (1.0 - share) * bit / blend
    share_term = share * (lig - bit) / blend * data.pu("coal_lignite_share")
    return math.sqrt((w_lig * data.efu("power_combustion_co2", "Lignite")) ** 2
                     + (w_bit * data.efu("power_combustion_co2", "Other Bituminous Coal")) ** 2
                     + share_term ** 2)


def compute(data, year=None, coal_override=None):
    """Return (components, memo). No memo items in this sector; the tuple keeps the
    signature identical to the other sectors so the engine facade is interchangeable."""
    tj = fuel_TJ(data, year)
    components = []

    for fuel, tj_v in sorted(tj.items()):
        ad_u = activity_uncert(data, fuel)
        if fuel == "Coal":
            co2_ef = coal_co2_factor(data, coal_override, year)
            co2_u = coal_co2_factor_uncert(data)
            ch4_ef = data.efv("power_combustion_ch4", "Coal")
            n2o_ef = data.efv("power_combustion_n2o", "Coal")
            ch4_u = data.efu("power_combustion_ch4", "Coal")
            n2o_u = data.efu("power_combustion_n2o", "Coal")
        else:
            co2_item, non_co2_item = FUEL_EF[fuel]
            co2_ef = data.efv("power_combustion_co2", co2_item)
            co2_u = data.efu("power_combustion_co2", co2_item)
            ch4_ef = data.efv("power_combustion_ch4", non_co2_item)
            n2o_ef = data.efv("power_combustion_n2o", non_co2_item)
            ch4_u = data.efu("power_combustion_ch4", non_co2_item)
            n2o_u = data.efu("power_combustion_n2o", non_co2_item)

        # THE GAS BOUNDARY DECISION (rc19, the fourteenth review): the leaked
        # share of delivered gas is not burned, so the gas rows book combustion
        # NET of it - all three gases, because none of them is produced by gas
        # that leaves upstream of the burner tip. The share has one home
        # (fugitives.post_meter); the delivered meter itself stays gross in
        # fuel_TJ for the energy closure, the CRT comparison and the air layer.
        # The gross delivered-gas booking is the named alternative view.
        net = post_meter.combusted_fraction() if fuel == "Gas" else 1.0

        # kg/TJ x TJ = kg; /1e6 -> Gg
        components.append({
            "category": CATEGORY, "subitem": "%s CO2" % fuel, "gas": "CO2",
            "corr_group": TOE_CORR_GROUP,
            "emissions_Gg": tj_v * net * co2_ef / 1e6,
            "uncert_pct": product(ad_u, co2_u),
            # Wave 6: per-draw gas identity (see uncertainty_all)
            "net_of_leak": fuel == "Gas"})
        components.append({
            "category": CATEGORY, "subitem": "%s CH4" % fuel, "gas": "CH4",
            # Coal, natural gas and oil products are all fossil, so this CH4 takes the
            # fossil GWP: AR5 30 rather than 28. Same as aviation, opposite to waste.
            "fossil": True,
            "emissions_Gg": tj_v * net * ch4_ef / 1e6,
            "uncert_pct": product(ad_u, ch4_u),
            "net_of_leak": fuel == "Gas"})
        components.append({
            "category": CATEGORY, "subitem": "%s N2O" % fuel, "gas": "N2O",
            "emissions_Gg": tj_v * net * n2o_ef / 1e6,
            "uncert_pct": product(ad_u, n2o_u),
            "net_of_leak": fuel == "Gas"})

    return components, []

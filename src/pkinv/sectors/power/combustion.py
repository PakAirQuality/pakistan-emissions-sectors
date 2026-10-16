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
    """Lignite share of booked heat from station mass and rank-specific NCV.

    CO2 factors are expressed per unit of fuel energy. Electricity shares cannot
    weight them because ranks have different conversion efficiencies. Generation
    remains a separate diagnostic and never enters this factor weighting.
    """
    return data.coal_energy_lignite_share(year)


def coal_co2_factor(data, override=None, year=None):
    """Energy-weighted kg CO2/TJ for coal, for the year asked about.

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


def coal_co2_factor_uncert(data, year=None):
    """Factor-only uncertainty conditional on the station rank heat account.

    Rank NCV uncertainty enters the energy drivers separately and changes the
    heat shares there. An independent generation-blend share draw would duplicate
    a retired assumption rather than describe the documented physical account.
    """
    import math
    share = coal_lignite_share(data, year)
    lig, bit = (data.efv("power_combustion_co2", "Lignite"),
                data.efv("power_combustion_co2", "Other Bituminous Coal"))
    blend = bit * (1.0 - share) + lig * share
    w_lig, w_bit = share * lig / blend, (1.0 - share) * bit / blend
    return math.sqrt((w_lig * data.efu("power_combustion_co2", "Lignite")) ** 2
                     + (w_bit * data.efu("power_combustion_co2", "Other Bituminous Coal")) ** 2)


def compute(data, year=None, coal_override=None):
    """Return (components, memo). No memo items in this sector; the tuple keeps the
    signature identical to the other sectors so the engine facade is interchangeable."""
    tj = fuel_TJ(data, year)
    components = []

    for fuel, tj_v in sorted(tj.items()):
        ad_u = activity_uncert(data, fuel)
        if fuel == "Coal":
            co2_ef = coal_co2_factor(data, coal_override, year)
            co2_u = coal_co2_factor_uncert(data, year)
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

    # The booked coal account is mass × rank NCV, unlike the three retained
    # Table 3 energy controls. Name those actual dependencies and remove the
    # obsolete shared TOE-convention draw from coal.
    for row in components:
        if row["subitem"].startswith("Coal "):
            widths = data.coal_uncertainty_drivers(year, row["gas"])
            row["uncertainty_driver_widths"] = widths
            row.pop("corr_group", None)
            # The graph samples a product of lognormal drivers. Summing relative
            # widths in Approach 1 and then converting that sum to log variance
            # is not equivalent when CH4/N2O factor widths are large. Derive the
            # declared marginal in the same domain; retain the first-order
            # diagnostic separately. No variance is silently clamped or widened.
            import math
            from pkinv.core.parameters import sigma_log, pct_from_sigma
            row["approach1_uncert_pct"] = product(*widths.values())
            row["uncert_pct"] = pct_from_sigma(math.sqrt(sum(sigma_log(width) ** 2
                                                          for width in widths.values())))
            row["reconstruction_interval_kind"] = "conditional_no_probability"
    return components, []

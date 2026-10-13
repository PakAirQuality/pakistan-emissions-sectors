"""Which physical emission factor each fossil-CO2 stream actually uses.

WHY THIS EXISTS. The correlated-factor Monte Carlo asks what happens if the IPCC default
carbon contents are wrong. That question only makes sense per FACTOR: if the guidelines'
number for gas/diesel oil is biased, it is biased everywhere diesel is burned - in road
transport, in railways, in off-road machinery, in industrial boilers - because there is one
carbon content of diesel. It says nothing about natural gas.

The first implementation put every fossil-CO2 component of every fuel-burning sector into ONE
correlation group. That is not a defensible physical claim: it asserts that diesel, petrol,
natural gas, furnace oil, coal and jet kerosene are all wrong together, in the same direction,
by the same relative amount. It also inflates the correlated band, which made the paper's
headline finding look stronger than the evidence supports.

Grouping by factor identity is the correct treatment, and it is the one the transport
supplement already described.

WHY A DECLARED TABLE RATHER THAN A DERIVED ONE. The obvious shortcut is to read the fuel out
of the component's subitem - "HDV Diesel CO2" plainly says diesel. It does not generalise:
"Domestic aviation CO2" is jet kerosene, "Generators CO2" is motor gasoline, "Cement gas CO2"
is natural gas, and "Gas CO2" is natural gas in power but would be ambiguous anywhere else.
Inferring a physical factor from a display label is exactly the class of guess this inventory
has been caught by before, so the mapping is written down.

The entries are IPCC emission-factor item names, the same strings the sectors index
data/emission_factors.csv with, so a factor identity here is the identity the engine actually
used rather than a parallel vocabulary. tests/test_uncertainty_all.py asserts the table covers
every fossil-CO2 row exactly - no row without a factor, no factor without a row - so it cannot
fall behind a sector that gains a fuel.
"""

# (sector, component subitem) -> the IPCC emission-factor item the CO2 row is computed with.
FOSSIL_CO2_FACTOR = {
    # --- aviation: ICAO fuel burn x the jet-kerosene carbon content -----------------------
    # rc47 Wave 3: the LTO/cruise split - same jet kerosene, same factor identity,
    # so the correlated draw treats the two stages as one fuel (which they are).
    ("aviation", "Domestic aviation LTO CO2"): "Jet Kerosene",
    ("aviation", "Domestic aviation cruise CO2"): "Jet Kerosene",

    # --- industry: OGRA sector gas, plus OCAC's Total Industry liquid customer class ------
    # rc46 Wave 2: the two activated solid streams share the OBC identity - and the
    # correlated scenario should move them together, because they share the one NCV
    # bucket and the one EF row by construction.
    ("industry", "Brick-kiln coal CO2"): "Other Bituminous Coal",
    ("industry", "Cement-sector coal CO2"): "Other Bituminous Coal",
    ("industry", "General Industry gas CO2"): "Natural Gas",
    ("industry", "Cement gas CO2"): "Natural Gas",
    ("industry", "Industrial furnace oil CO2"): "Residual Fuel Oil",
    ("industry", "Industrial diesel CO2"): "Gas/Diesel Oil",
    ("industry", "Industrial light diesel oil CO2"): "Gas/Diesel Oil",
    ("industry", "Industrial kerosene CO2"): "Other Kerosene",
    ("industry", "Industrial gasoline CO2"): "Motor Gasoline",
    ("industry", "Industrial HOBC CO2"): "Motor Gasoline",

    # --- power: NEPRA fuel consumed, plus the captive gas register ------------------------
    ("power", "Gas CO2"): "Natural Gas",
    ("power", "Captive natural gas CO2"): "Natural Gas",
    ("power", "Coal CO2"): "Other Bituminous Coal",
    ("power", "Furnace Oil CO2"): "Residual Fuel Oil",
    ("power", "Diesel Oil CO2"): "Gas/Diesel Oil",

    # --- railways: Year Book metered purchases --------------------------------------------
    ("railways", "Diesel CO2"): "Gas/Diesel Oil",
    ("railways", "Furnace oil CO2"): "Residual Fuel Oil",
    # the rc11 re-base's non-traction rows burn the SAME purchases at the same factors
    ("railways", "Non-traction diesel CO2"): "Gas/Diesel Oil",
    ("railways", "Non-traction furnace oil CO2"): "Residual Fuel Oil",

    # --- residential: OGRA domestic supply and the HIES survey -----------------------------
    ("residential", "Natural gas CO2"): "Natural Gas",
    ("residential", "LPG CO2"): "Liquefied Petroleum Gases",
    ("residential", "Kerosene CO2"): "Other Kerosene",
    ("residential", "Coal CO2"): "Other Bituminous Coal",
    ("residential", "Generators CO2"): "Motor Gasoline",

    # --- transport: the OCAC Road control, split by class ----------------------------------
    ("transport", "CNG CO2"): "Natural Gas",
    ("transport", "Off-road machinery diesel CO2"): "Gas/Diesel Oil",
}

# Every road class carries the same two petroleum factors; listing them by hand would be
# twelve near-identical lines that a new vehicle class would silently fall out of.
_ROAD_CLASSES = ("2W", "3W", "4W1", "4W2", "4WT", "LDV", "BUS", "HDV", "NRV")
for _cls in _ROAD_CLASSES:
    FOSSIL_CO2_FACTOR[("transport", "%s Petrol CO2" % _cls)] = "Motor Gasoline"
    FOSSIL_CO2_FACTOR[("transport", "%s Diesel CO2" % _cls)] = "Gas/Diesel Oil"


def factor_id(component):
    """The IPCC factor item behind a component's CO2, or None if it is not fossil-fuel CO2.

    Returns None rather than raising for process CO2 (cement), urea and liming, open-burning
    CO2 and fugitive CO2: those are real CO2 rows that do not come from a fuel-carbon table,
    and giving them a fuel identity would put them in a correlation group they have no
    physical reason to share.
    """
    if component.get("gas") != "CO2":
        return None
    return FOSSIL_CO2_FACTOR.get((component.get("_sector"), component.get("subitem")))


# Every gas a fuel stream emits reads the SAME fuel's factor row family, so the fuel identity
# is a property of the stream and not of the gas. FOSSIL_CO2_FACTOR is keyed on the CO2 row's
# subitem because that is what it was built for; stripping the gas suffix makes the same table
# answer for the CH4, N2O and calorific rows of the same stream.
_GASES = ("CO2", "CH4", "N2O")


def fuel_of(component):
    """The IPCC fuel a component's stream burns, whatever gas the row reports.

    Returns None for a row that is not fuel combustion - process CO2 from cement, urea, open
    burning, fugitive venting - which is the same exclusion factor_id() makes and for the same
    reason: those are real emissions that do not come from a fuel-carbon table, and giving them
    a fuel identity would put them in a correlation group they have no physical reason to share.
    """
    subitem = component.get("subitem") or ""
    for gas in _GASES:
        if subitem.endswith(" " + gas):
            subitem = subitem[: -(len(gas) + 1)]
            break
    sector = component.get("_sector")
    for candidate in (subitem, "%s CO2" % subitem):
        hit = FOSSIL_CO2_FACTOR.get((sector, candidate))
        if hit:
            return hit
    return None


def fossil_co2_rows(components):
    """The components this table claims are fuel-carbon CO2."""
    return [c for c in components if factor_id(c) is not None]

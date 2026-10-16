"""The shared four-configuration vocabulary for all maintained product families.

S_TAN is the reference: survey-based household dung combustion and the TAN nitrogen
ledger. L_TAN assigns all diverted dung to household combustion under the same
nitrogen method. S_IPCC and L_IPCC repeat those household cases with the explicit
IPCC nitrogen method. These are structural configurations, with no probabilities;
each is evaluated over the full core period using the same source-account boundaries.

Historical period-named identifiers are retained only as aliases. They do not denote
separate estimates or an alternative available only in the detailed reference year.
A new canonical identifier is a schema change: annual, monthly, administrative,
spatial, uncertainty and query products share this closed vocabulary.
"""
REFERENCE = "S_TAN"
LEDGER = "L_TAN"
IPCC_REFERENCE = "S_IPCC"
IPCC_LEDGER = "L_IPCC"

# The one dung-basis switch (rc67). Every engine default and every "second configuration"
# product reads these two names; nothing else in the repository may type "ledger" or
# "survey" to choose a basis. Before this constant the choice was a defaulted keyword in
# five modules and a module constant in a sixth.
REFERENCE_DUNG_BASIS = "survey"
ALTERNATIVE_DUNG_BASIS = "ledger"

# Compatibility name for the consistently applied ledger-dung configuration.
# GHG and air products use the same identifier and full core-period applicability.
LEDGER_SERIES = LEDGER
ALL = (REFERENCE, LEDGER, IPCC_REFERENCE, IPCC_LEDGER)
AIR_ALL = ALL
RETIRED = {"S_2023_24": REFERENCE, "S_HIES1925": REFERENCE}
ALIASES = {"REF_2023_24": REFERENCE, "L_2023_24": LEDGER,
           "L_HERD1624": LEDGER, **RETIRED}


def canonical(configuration_id):
    return ALIASES.get(configuration_id, configuration_id)


def nitrogen_method(configuration_id):
    return "ipcc" if canonical(configuration_id) in (IPCC_REFERENCE, IPCC_LEDGER) else "tan"


def dung_basis(configuration_id):
    return "ledger" if canonical(configuration_id) in (LEDGER, IPCC_LEDGER) else "survey"

# The register's display name for the ledger configuration, kept for the
# configurations table where display belongs.
LEDGER_DISPLAY = "all_diverted_dung_household_fuel"

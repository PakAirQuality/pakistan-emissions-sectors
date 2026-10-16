"""Public configuration ids and historical aliases; independent of the inventory runtime."""
REFERENCE = "S_TAN"
LEDGER = "L_TAN"
AIR_ALL = (REFERENCE, LEDGER, "S_IPCC", "L_IPCC")
ALIASES = {"REF_2023_24": REFERENCE, "S_2023_24": REFERENCE,
           "S_HIES1925": REFERENCE, "L_2023_24": LEDGER, "L_HERD1624": LEDGER}


def canonical(value):
    return ALIASES.get(value, value)

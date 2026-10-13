"""The IPCC notation keys, one vocabulary for every ledger that types an absence.

E is the only key that carries mass. NE (not estimated) is a debt, NO (not occurring)
a fact about Pakistan, IE (included elsewhere) an accounting pointer, NA (not
applicable) a category the method does not define. A missing estimate is written as
its key, NEVER as a zero - zero is a measurement.
"""

# key -> (meaning, carries_mass)
NOTATION_KEYS = {
    "E": ("estimated", True),
    "NE": ("not estimated", False),
    "IE": ("included elsewhere", False),
    "NO": ("not occurring", False),
    "NA": ("not applicable", False),
}

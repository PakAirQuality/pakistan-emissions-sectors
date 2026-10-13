"""The configuration vocabulary: ONE set of ids for the whole product family (rc31).

The eighteenth review found the same alternative wearing four names across the
products - ``S``, ``observed_household_demand``, ``residential_dung_axis=S``,
and absence - which makes a per-configuration join impossible for a reader. The
ids live here, the three module constants consume them, and the display names
stay in the configurations register where display belongs.

  REF_2023_24   the reference configuration (every axis at its reference setting) -
                the id the monthly and atomic products have carried since Pass 1.
                SINCE rc67 ITS HOUSEHOLD DUNG IS THE SURVEY'S: what households report
                burning, in every year of the panel.
  L_2023_24     the ledger dung basis (configuration L): residential re-run with ALL
                the dung agriculture diverts burned by households, every other sector
                identical by construction. A destination assumption for the diverted
                dung, retained and bounded, not a reading of household use.

THE ROLES SWAPPED AT rc67. Through rc66 the reference burned the whole diverted supply
in households (58.7 Mt, configuration L) and the survey reading (configuration S, about
a fifth of it) was the alternative, published as ``S_2023_24``. The review's question was
what the residential reference measures; the answer taken is household use, which the
survey observes and the nitrogen ledger does not. ``S_2023_24`` and ``S_HIES1925`` are
retired ids (RETIRED below, and the rc67 section of CHANGELOG.md): what they named is
now the reference.

A NEW id is a schema event: the annual, monthly, ADM2 and uncertainty consumers
key on this closed set, and tests/test_configuration_keys.py holds the closure.
"""
REFERENCE = "REF_2023_24"
LEDGER = "L_2023_24"

# The one dung-basis switch (rc67). Every engine default and every "second configuration"
# product reads these two names; nothing else in the repository may type "ledger" or
# "survey" to choose a basis. Before this constant the choice was a defaulted keyword in
# five modules and a module constant in a sixth.
REFERENCE_DUNG_BASIS = "survey"
ALTERNATIVE_DUNG_BASIS = "ledger"

# The air panel's nine-year alternative. L_2023_24 is period-named and guard-tested
# against being manufactured for history
# (tests/test_annual_grid.py::test_the_period_named_alternative_is_not_manufactured_for_history),
# so a SERIES on the ledger dung basis is a different claim with its own id: the diverted
# dung of each year's own herd (FY2015-16 to FY2023-24), all of it burned in households.
# It exists for the AIR product family, where the dung basis moves residential PM2.5 by a
# factor of two and a reader needs both series.
LEDGER_SERIES = "L_HERD1624"
ALL = (REFERENCE, LEDGER)
AIR_ALL = (REFERENCE, LEDGER_SERIES)
RETIRED = {"S_2023_24": REFERENCE, "S_HIES1925": REFERENCE}

# The register's display name for the ledger configuration, kept for the
# configurations table where display belongs.
LEDGER_DISPLAY = "all_diverted_dung_household_fuel"

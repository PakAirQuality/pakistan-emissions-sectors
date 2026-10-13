"""Unit conversions that more than one sector needs, defined once.

WHY THIS FILE EXISTS. The British thermal unit appears in three places in this inventory -
captive gas, power air pollutants, and now transport CNG - because Pakistani gas is metered in
cubic feet and billed in MMBTU while every IPCC factor is per terajoule. It was written out
separately each time, and one of those copies was wrong by a factor of a thousand. It produced
48 Mt of NOx from Pakistani power stations against a global total near 120, which is the only
reason anyone noticed; a smaller error in the same place would have shipped.

A conversion constant restated per sector is a conversion constant that will eventually differ
per sector, and the difference is invisible in every output. So they live here, with the
sectors importing rather than repeating them.

NOTHING HERE IS AN ASSUMPTION. Btu to joule is exact by definition, cubic feet are a volume,
and a year is 365 days. The quantities that ARE assumptions - a gas heating value in Btu/scf,
a gross-to-net ratio - stay in each sector's parameter file with their own uncertainty and
their own source, because those are properties of Pakistani pipeline gas rather than of
arithmetic.
"""

# Exact by definition: 1 Btu_IT = 1055.05585262 J.
J_PER_BTU = 1055.05585262

# One million standard cubic feet of gas at one Btu/scf, in terajoules.
#   1 MMCF x 1 Btu/scf = 1e6 Btu = 1.05505585262e9 J = 1.05505585262e-3 TJ
TJ_PER_MMCF_PER_BTU = 1e6 * J_PER_BTU / 1e12

# One million Btu in terajoules. Same constant, different starting unit - power stations are
# billed in MMBTU while gas volumes are reported in MMCF, and both appear in this inventory.
TJ_PER_MMBTU = 1e6 * J_PER_BTU / 1e12

DAYS_PER_YEAR = 365.0


def mmcfd_to_TJ(mmcfd, hhv_btu, gross_to_net=1.0, days=DAYS_PER_YEAR):
    """Million cubic feet per day -> terajoules per year.

    hhv_btu is the GROSS heating value in Btu per standard cubic foot, which is how Pakistani
    utilities bill. gross_to_net converts to the net calorific basis IPCC factors are defined
    on; leave it at 1.0 to get gross energy.

    Both are the caller's parameters, not this module's: they are properties of the gas and
    belong in a sector's parameter file where they can carry a source and an uncertainty.
    """
    return mmcfd * days * hhv_btu * TJ_PER_MMCF_PER_BTU * gross_to_net

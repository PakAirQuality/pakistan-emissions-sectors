"""The post-meter whole-gas leak share: one derived quantity, one home (rc19).

THE BOUNDARY DECISION THIS SERVES. Until rc19 the reference booked delivered gas
as fully combusted while the fugitives sector also booked a post-meter leak on
the same molecules - a double-claim the ledger quantified (rc14), a priced
configuration removed (+0.28767 restored as gross_delivered_gas_accounting; the
rc17 print of -0.286/-0.287 predates the twin-defect fix), and the fourteenth review required the
reference to stop making: leaked gas is not burned, so the physical-atmosphere
inventory books combustion NET of the leaked share, and the gross delivered-gas
booking becomes the named alternative view. The share below is the quantity the
combustion engines net by.

WHY THIS MODULE EXISTS. The three inputs each already have exactly one declared
home - the post-meter CH4 factor in data/fugitives_ipcc2019_factors.csv (6.1 t
CH4 per million m3, IPCC 2019 Table 4.2.4k), and the CH4 mass fraction and gas
density in data/fugitives_params.csv - and the derivation
(factor / ch4_fraction) / (density x 1000) had started growing twins:
report/gas_closure.py carried its own 6.1 for two releases, the exact defect
class its _fugitives_param docstring records for the other two constants. This
module is the one derivation; every consumer imports it.

WHAT THE SHARE IS NOT. It is not an emissions change: the leaked molecules stay
in the inventory, booked where they physically go - 1.B.2 as fugitive CH4. The
netting removes a double-claim (CO2-negative, CH4-neutral), and it applies to
all three combustion gases, because gas that leaks upstream of the burner tip
produces none of them.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import DATA

_CACHE = {}


def factor_value(factor_id):
    for r in _activity_rows(asset_path(DATA, "fugitives_ipcc2019_factors.csv"), comments=False):
        if r["factor_id"] == factor_id:
            return float(r["value"])
    raise KeyError(factor_id)


def param_value(param):
    for r in _activity_rows(asset_path(DATA, "fugitives_params.csv"), comments=False):
        if r["param"] == param:
            return float(r["value"])
    raise KeyError(param)


def whole_gas_leak_share():
    """Fraction of delivered gas (whole-gas mass) the post-meter factor prices
    as leaked: (6.1 / 0.90) / (0.68 * 1000) = 0.0099673...

    The combustion engines multiply their gas emission rows by
    (1 - whole_gas_leak_share()); the gross delivered-gas alternative divides
    it back out."""
    if "share" not in _CACHE:
        _CACHE["share"] = (
            (factor_value("post_meter_industrial_ch4")
             / param_value("gas_ch4_fraction"))
            / (param_value("gas_density_kg_per_m3") * 1000.0))
    return _CACHE["share"]


def combusted_fraction():
    """The factor the reference booking applies to delivered-gas combustion."""
    return 1.0 - whole_gas_leak_share()

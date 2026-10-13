"""Data library for industrial fuel combustion (IPCC 1A2)."""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA
from pkinv.activity.store import read_rows

YEAR = 2024          # FY2023-24, the OGRA State of the Regulated Petroleum Industry vintage
#
# FISCAL YEARS ARE KEYED BY END YEAR here: 2024 means July 2023 - June 2024. Power and
# aviation key by start year and mean the same twelve months by 2023. Both conventions are
# in the repository and neither is wrong; what is wrong is a message that formats one as
# the other, so fy() below is the only place this sector turns a key into a printed year.


def fy(end_year):
    """2024 -> 'FY2023-24'."""
    return "FY%d-%02d" % (end_year - 1, end_year % 100)


def _read(p):
    return read_rows(p, comments=False)


def _num(s):
    s = (s or "").strip()
    return None if s == "" else float(s)


class IndustryData:
    def __init__(self, data_dir=DATA, year=YEAR):
        self.data_dir, self.year = data_dir, year

        self.ef = {}
        for r in _read(asset_path(data_dir, "emission_factors.csv")):
            self.ef[(r["category"], r["item"])] = {
                "value": _num(r["value"]), "uncert_pct": _num(r["uncert_pct"]),
                "source": r["source"]}

        self.params, self.param_uncert, self.param_source = {}, {}, {}
        for r in _read(asset_path(data_dir, "industry_params.csv")):
            self.params[r["param"]] = _num(r["value"])
            self.param_uncert[r["param"]] = _num(r["uncert_pct"])
            self.param_source[r["param"]] = r["source"]

        self.gas = {}
        for r in _read(asset_path(data_dir, "activity", "industry",
                                    "gas_consumption.csv")):
            self.gas[(int(r["fiscal_year"]), r["stream"])] = float(r["total_mmcfd"])

        # Industrial LIQUID fuels, from OCAC's own Total Industry customer-class row.
        #
        # These were in the repository the whole time. The transport sector ingested all
        # nine annual OCAC editions for its Road rows, and the same tables carry a Total
        # Industry row for every petroleum product - furnace oil, diesel, kerosene, LDO and
        # gasoline - which nothing read. The gap register called industrial fuel
        # "not-acquired" while 642,021 tonnes of FY2023-24 furnace oil sat in a committed
        # CSV. That is the fourth time this inventory has found a category absent from its
        # own outputs and present in its own data.
        #
        # Fiscal years are keyed by START year to match the OCAC file, and converted to the
        # sector's end-year convention on read.
        self.liquid = {}
        for r in _read(asset_path(data_dir, "activity", "transport",
                                    "ocac_sectoral_annual.csv")):
            if r["sector_row"] != "Total Industry":
                continue
            if r["product"] in ("TOTAL", "TOTAL_PRIOR"):
                continue
            tonnes = float(r["tonnes"])
            if not tonnes:
                continue
            self.liquid[(int(r["inventory_year"]), r["product"])] = tonnes

    def efv(self, c, i):
        return self.ef[(c, i)]["value"]

    def efu(self, c, i):
        return self.ef[(c, i)]["uncert_pct"]

    def p(self, n):
        return self.params[n]

    def pu(self, n):
        return self.param_uncert[n]

    def ps(self, n):
        return self.param_source[n]

    # OCAC product code -> (IPCC item for the factor tables, item for the NCV table).
    # HOBC is a gasoline blending component and takes the Motor Gasoline factor; LDO has no
    # IPCC line of its own and is mapped to Gas/Diesel Oil with a widened NCV uncertainty,
    # declared on the ind_ncv_ldo row.
    LIQUID_ITEMS = {
        "FO":   ("Residual Fuel Oil", "Residual Fuel Oil"),
        "HSD":  ("Gas/Diesel Oil", "Gas/Diesel Oil"),
        "LDO":  ("Gas/Diesel Oil", "Light Diesel Oil"),
        "KERO": ("Other Kerosene", "Other Kerosene"),
        "MS":   ("Motor Gasoline", "Motor Gasoline"),
        "HOBC": ("Motor Gasoline", "Motor Gasoline"),
    }

    def liquid_products(self, year=None):
        """OCAC product codes with a non-zero Total Industry quantity in `year`.

        RAISES on an uncovered year, for the same reason streams() does.
        """
        year = self.year if year is None else year
        out = sorted(pr for (y, pr) in self.liquid if y == year)
        if not out:
            years = sorted({y for (y, _p) in self.liquid})
            raise KeyError(
                "no OCAC Total Industry rows for %s: the panel covers %s to %s "
                "(data/activity/transport/ocac_sectoral_annual.csv)"
                % (fy(year), fy(min(years)), fy(max(years))))
        return out

    def liquid_tonnes(self, product, year=None):
        year = self.year if year is None else year
        return self.liquid[(year, product)]

    def streams(self, year=None):
        """Gas stream names for one fiscal year.

        RAISES on an uncovered year. An empty list made combustion.compute sum an empty
        set and return 0.0 Mt - a sector silently vanishing from the national total, which
        is indistinguishable from a sector that genuinely emits nothing.
        """
        year = self.year if year is None else year
        out = sorted(s for (y, s) in self.gas if y == year)
        if not out:
            years = sorted({y for (y, _s) in self.gas})
            raise KeyError(
                "no industrial gas streams for %s: the table covers %s "
                "(data/activity/industry/gas_consumption.csv). FY2020-21 is absent on "
                "purpose - that OGRA edition is an image scan with no extractable text, "
                "and the sector-wise table was not recovered from it."
                % (fy(year), ", ".join(fy(y) for y in years)))
        return out

    def mmcfd(self, stream, year=None):
        """Indexed, not .get(): a missing stream must raise rather than silently shrink
        the category."""
        return self.gas[(self.year if year is None else year, stream)]

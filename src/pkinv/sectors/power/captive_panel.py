"""The captive fleet's province geography, keyed by the year OGRA actually publishes.

THE DEFECT. data/province_shares.csv carries ONE `captive_gas` row - Punjab 0.339982, Sindh
0.603083, KP 0.048268, Balochistan 0.006600, ICT 0.002067 - and the engine applies it to all nine
fiscal years. It is the FY2023-24 register's own split, and it is a good measurement OF THAT YEAR.
It is not a good measurement of FY2020-21, when the SNGPL captive lane collapsed to 1 MMCFD
against SSGCL's 202 and Punjab's true share was nearer 0.008. A factor of forty-one, applied
silently, for eight years.

WHAT HAS A YEAR AXIS AND WHAT DOES NOT. The register's dates do NOT: its `gas_mmcfd` is a FY2024
snapshot, so the 103 plants carrying a disconnection date hold 2.925 MMCFD of 288.01 between them
- the register knows THAT they existed, not how much gas they drew while they did. Using those
dates as a weight would be false precision. What does have a year axis is the split OGRA publishes
between the two gas utilities, in data/activity/power/captive_gas.csv, every year:

    sngpl 138 204 169 117 110   1  51  78 107
    ssgcl 186 189 211 204 180 202 192  45 181

SNGPL's network is Punjab, Khyber Pakhtunkhwa and Islamabad; SSGCL's is Sindh and Balochistan.
So the year axis sits on the FRANCHISE MIX, and the geography WITHIN each franchise stays the one
FY2024 pattern the register measures. That is what this module computes, and the basis string it
produces says exactly that rather than implying the plant map itself is dated.

THE METHOD IS ALREADY IN THIS REPOSITORY. The `industry_gas` row of data/province_shares.csv says
so on its face: "Derived: the General Industry row's own utility split (SNGPL 155, SSGCL 136
MMCFD, OGRA Table 3.31) allocated across each utility's franchise in proportion to the captive_gas
plant register above." This is that arithmetic, applied to the proxy it was borrowed from, with
the year axis the source table already supports.

THE CHECK THAT LICENSES IT. Weighting each franchise by its OWN ASSIGNED gas - which is how the
committed row's note says the 37 province-less plants holding 12.26 MMCFD are handled, "pro rata
over the assigned fleet" - reproduces the committed row to within 1.5e-5 at FY2023-24. The
reference year moves no published number; the other eight are the finding. tests/test_power.py
holds that reproduction, and if it ever stops holding, this module has drifted from the hand
arithmetic that produced the value the release shipped.

A SECOND RECONCILIATION, STRONGER THAN THE ONE ALREADY ADVERTISED. The register sums to 288.01
MMCFD against OGRA's 288, which the repository already cites. Grouped by franchise it agrees lane
by lane: the register's SNGPL pool is 107.00 against OGRA's 107, and its SSGC pool 181.01 against
181. Two artefacts describing the same fleet, not just the same total.

FISCAL CONVENTION, AND THE TRAP IN IT. captive_gas.csv is keyed by fiscal END year (2024 is
FY2023-24), exactly as the power engine already reads it. `period.fiscal_start_year` is the START.
The +1 happens once, here, in `panel_year`.
"""

from pkinv.assets import asset_path
import collections

from pkinv.activity.store import read_rows
from pkinv.paths import DATA

import os

PANEL = asset_path(DATA, "activity", "power", "captive_gas.csv")
REGISTER = asset_path(DATA, "activity", "power", "captive_register.csv")
STREAM = "captive_gas"
# Which utility's network a register row sits on. The register carries this per plant, so the
# franchise is read rather than inferred from the province - a plant in Punjab on the SSGC
# network is a real thing and it stays where the register puts it.
FRANCHISE = {"SNGPL": "sngpl", "NEPRA+SNGPL": "sngpl", "SSGC": "ssgcl"}
# The NEPRA-licensed rows carry no metered gas at all, so they weigh nothing either way.
LANES = ("sngpl", "ssgcl")
# The register names Islamabad in full; the engine's province vocabulary folds it into `Other`,
# which is what the committed row's `other_membership = ict_only` declares. Mapped here, once,
# because a plain lookup against the engine's names drops Islamabad silently and the vector then
# sums to 0.999972 rather than 1 - small enough to pass unnoticed and wrong all the same.
TO_ENGINE = {"Islamabad Capital Territory": "Other"}


def panel_year(fiscal_start_year):
    """2015 -> '2016', the fiscal END year captive_gas.csv is keyed by, or None."""
    if not fiscal_start_year:
        return None
    return str(int(fiscal_start_year) + 1)


def lanes():
    """({lane: {province: assigned MMCFD}}, {lane: placement rate}).

    A plant with no province is NOT dropped and NOT spread: it lowers its own lane's placement
    rate, which is what "redistributed pro rata over the assigned fleet" means arithmetically,
    and it is the convention the committed row already uses. All 37 of them are SSGC.
    """
    assigned = collections.defaultdict(lambda: collections.defaultdict(float))
    whole = collections.defaultdict(float)
    for row in read_rows(REGISTER):
        lane = FRANCHISE.get(row["sources"])
        if lane is None:
            continue
        gas = float(row["gas_mmcfd"] or 0.0)
        whole[lane] += gas
        if row["province_region"]:
            assigned[lane][row["province_region"]] += gas
    rate = {lane: (sum(assigned[lane].values()) / whole[lane]) if whole[lane] else 0.0
            for lane in whole}
    return assigned, rate


def published(fiscal_end_year):
    """The OGRA lane totals for one fiscal END year, or None where the table does not reach."""
    for row in read_rows(PANEL):
        if row["fiscal_year"] == str(fiscal_end_year):
            return {lane: float(row["%s_mmcfd" % lane] or 0.0) for lane in LANES}, row
    return None, None


def province_shares(fiscal_end_year):
    """{province: share} for the captive stream in one fiscal year, or None.

    None - not an empty vector and not the reference year's - where OGRA publishes no split, so
    the caller falls back to the committed row rather than to a silent zero.
    """
    totals, _row = published(fiscal_end_year)
    if totals is None or not any(totals.values()):
        return None
    assigned, rate = lanes()
    weighted = collections.defaultdict(float)
    for lane in LANES:
        pool = totals.get(lane, 0.0) * rate.get(lane, 0.0)
        within = sum(assigned[lane].values())
        if pool <= 0 or within <= 0:
            continue
        for province, gas in assigned[lane].items():
            weighted[province] += pool * (gas / within)
    grand = sum(weighted.values())
    if grand <= 0:
        return None
    out = collections.defaultdict(float)
    for province, value in weighted.items():
        out[TO_ENGINE.get(province, province)] += value / grand
    total = sum(out.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError("captive province shares for %s sum to %.12f, not 1: a province the "
                         "engine's vocabulary does not name has been dropped"
                         % (fiscal_end_year, total))
    return dict(out)


def unplaced_mmcfd(fiscal_end_year):
    """The independent lane: captive gas OGRA reports outside either utility's network, and
    therefore outside any franchise geography. 65 MMCFD in FY2015-16, nil afterwards. Reported
    so the share vector's silence about it is visible, never spread across the provinces."""
    _totals, row = published(fiscal_end_year)
    return float((row or {}).get("independent_mmcfd") or 0.0)

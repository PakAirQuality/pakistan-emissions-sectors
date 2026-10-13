"""Province allocation for industrial fuel combustion.

Measured at the utility level, proxied within it. The General Industry row is reported split
between SNGPL (155 MMCFD) and SSGCL (136), which is the actual division of the gas being
allocated rather than a stand-in for it; the split within each franchise rides the 1,105-plant
captive register, because captive plants sit in the same industrial estates that draw process
gas. The row in data/province_shares.csv carries the derivation and its known bias.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.geography import PROVINCES
from pkinv.paths import DATA

PROXY = "industry_gas"

# The liquid fuels do not ride the gas geography. Gas goes where the pipeline network and
# the captive fleet are; furnace oil and diesel go where industry burns fuel it can truck
# in, which is a different map - and OCAC publishes that map directly in its monthly area
# pages, so the proxy is the same publication as the control rather than a stand-in for it.
#
# rc62: NOR DO THE LIQUIDS RIDE EACH OTHER'S. There was one `industry_liquid_fuel` row summing
# six products, and it put furnace oil at Punjab 0.657 where furnace oil's own area pages say
# 0.784 - thirteen points, because high-speed diesel, motor spirit and kerosene sell through a
# far more Karachi-weighted network. Diesel moves the other way, to very nearly half Sindh. The
# split is by product and it is earned: see pkinv.sectors.industry.province_shape for why the
# four small liquids stay blended rather than each getting a vector built on a few thousand tonnes.
PROXY_MAP = {}
PROXY_FALLBACK = {"Industrial fuel combustion (1A2)": PROXY}


def _liquid_proxy(c):
    """The product-specific liquid profile for a subitem, or None if it is not a liquid."""
    from pkinv.sectors.industry import province_shape
    group = province_shape.group_for_subitem(c["subitem"])
    return province_shape.PROFILE_OF_GROUP[group] if group else None


# rc46 Wave 2: the solid-fuel streams carry their own registers' geography - brick coal the
# kiln allocation's provincial weight (11,272 surveyed points + the benchmarked unsurveyed
# frame), cement coal the GEM tracker's operating clinker capacity. Neither is the gas
# franchise map nor the liquids' truck map, and putting either on those would repeat the
# borrowed-geography defect this inventory keeps finding in other people's tables.
def _solid_proxy(c):
    if c["subitem"].startswith("Brick-kiln coal"):
        return "brick_coal"
    if c["subitem"].startswith("Cement-sector coal"):
        return "cement_coal"
    return None


def load_shares(period=None):
    """{proxy: {province: share}}, with the liquid profiles served from the period's OWN area
    pages wherever OCAC printed twelve provincial months for that product.

    The committed rows stay the reference year's, so a period the panel cannot serve keeps the
    reference shape and the weight registry types it a backcast - the same contract the road
    fuels run under (pkinv.sectors.transport.downscale). A partial year is never averaged into
    a shape; province_shape.shares raises on one.
    """
    shares = {}
    for r in _activity_rows(asset_path(DATA, "province_shares.csv"), comments=False):
        shares[r["proxy"]] = {p: float(r[p]) for p in PROVINCES}
    if period is not None and hasattr(period, "fiscal_start_year"):
        from pkinv.sectors.industry import province_shape
        fiscal_year = int(period.fiscal_start_year) + 1   # the panel keys on the END year
        # THE REFERENCE YEAR KEEPS THE COMMITTED TABLE, and the reason is the road fuels'
        # (pkinv.sectors.transport.downscale): the own-year path reproduces the committed row
        # only to its printed six decimals, and a last-digit difference would give the
        # reference a pattern digest that its own backcast years cannot match - which is
        # exactly the drift the weight registry is built to detect. The committed row IS the
        # reference year's own pages; recomputing it buys nothing and costs the digest.
        if fiscal_year != province_shape.REFERENCE_SHAPE_YEAR:
            rows = province_shape._panel()
            for group, profile in province_shape.PROFILE_OF_GROUP.items():
                if province_shape.months_covered(fiscal_year, group, rows) == 12:
                    shares[profile] = province_shape.shares(group, fiscal_year, rows)
    return shares


def proxy_for(c):
    # Indexed with [], not .get(): an unknown category must raise rather than silently
    # allocate onto the wrong geography at an unchanged national total.
    solid = _solid_proxy(c)
    if solid:
        return solid
    liquid = _liquid_proxy(c)
    if liquid:
        return liquid
    return PROXY_MAP.get((c["category"], c["subitem"]), PROXY_FALLBACK[c["category"]])

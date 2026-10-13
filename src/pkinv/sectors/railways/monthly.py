"""Railway traction, resolved into the twelve months of FY2023-24.

OCAC PUBLISHES A RAILWAYS CUSTOMER-CLASS ROW MONTHLY, and this sector's own annual quantity
comes from a different chain - Pakistan Railways' Year Book, the operator's metered purchases.
So the magnitude and the shape come from two independent publications about the same fuel, and
using the second for timing while keeping the first for size is exactly the arrangement the
paper describes as an independent cross-source check, applied to a different axis.

The two chains do not agree on the annual figure: the Year Book records 112.0 kt against
OCAC's 107.9 kt for the same year, 3.7 percent apart. That disagreement is reported in the
benchmarks section and it does not enter here, because a profile is normalised to twelve shares
before it is applied. Only the timing is borrowed.

Furnace oil rides the same profile. It is a marginal residue of the steam era and no separate
monthly series exists for it; the basis column says so.

Usage:  python3 -m pkinv.sectors.railways.monthly
Writes: outputs/railways_monthly_2024.csv
"""

from pkinv.assets import asset_path
import os

from pkinv.core import monthly as core_monthly
from pkinv.core import ocac_monthly
from pkinv.paths import OUTPUTS
from pkinv.sectors.railways import engine
from pkinv.sectors.railways.data import RailwaysData

FY_START = 2023
OUT = asset_path(OUTPUTS, "railways_monthly_2024.csv")
BASIS = ("OCAC Railways customer class, HSD, monthly editions differenced; the annual "
         "magnitude remains the Year Book's metered purchase")
FLAT_BASIS = ("flat: the OCAC panel does not reach this fiscal year, and one year's sales "
              "shape is not carried to another")


def rows(data=None, fy_start=FY_START):
    data = data if data is not None else RailwaysData()
    components = engine.build_components(data)
    shares, method, covered = ocac_monthly.profile_or_flat(
        ocac_monthly.RAILWAYS, ocac_monthly.DIESEL, fy_start)
    return components, core_monthly.apply_profile(
        components, shares, fy_start, temporal_method=method,
        basis=BASIS if covered else FLAT_BASIS)


def main():
    components, month_rows = rows()
    core_monthly.write_layer(OUT, month_rows, components)
    totals = core_monthly.month_totals(month_rows)
    print("railways monthly layer -> %s" % OUT)
    print("  %d rows over %d months; closes exactly" % (len(month_rows), len(totals)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

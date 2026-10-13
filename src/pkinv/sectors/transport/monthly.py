"""Road transport and mixed off-road machinery, resolved into the twelve months of FY2023-24.

THE SHAPE COMES FROM THE SAME PUBLICATION THE MAGNITUDE DOES. This sector anchors on OCAC's
Road customer-class rows, and OCAC issues those rows monthly. So the seasonal profile is not a
model of driving behaviour - it is the same table, read at the resolution it is published at,
differenced out of the cumulative columns (core.ocac_monthly). Petrol classes take the Road
MS+HOBC series, diesel classes and off-road machinery take Road HSD.

Off-road rides the DIESEL profile, and that is a declared approximation rather than an
oversight. Its fuel is carved out of the same Road HSD control by construction, so it cannot
have a different monthly total; whether agricultural and construction machinery burn it on the
same monthly rhythm as trucks is a separate question this inventory has no evidence on. The
row says T2 because the quantity is reconstructed from a monthly administrative record, and the
basis column says which control it inherited.

CNG IS FLAT AND DECLARED T4. OGRA meters gas to the CNG sector annually; no monthly series was
obtained. A flat profile asserts that CNG demand is aseasonal, which is wrong - CNG stations
ration by season and by load-shedding - and declaring it is the only honest option available.
It is the single largest improvement available to this layer and it needs an acquisition, not a
better model.

Usage:  python3 -m pkinv.sectors.transport.monthly
Writes: outputs/transport_monthly_2024.csv
"""

from pkinv.assets import asset_path
import os

from pkinv.core import monthly as core_monthly
from pkinv.core import ocac_monthly
from pkinv.paths import OUTPUTS
from pkinv.sectors.transport import engine
from pkinv.sectors.transport.data import TransportData

FY_START = 2023
OUT = asset_path(OUTPUTS, "transport_monthly_2024.csv")


def _fuel_of(subitem):
    """Which OCAC series a component stream belongs to."""
    if "Petrol" in subitem:
        return "petrol"
    if "Diesel" in subitem or subitem.startswith("Off-road machinery"):
        return "diesel"
    return "cng"


def profiles(fy_start=FY_START):
    """{fuel: ({month: share}, {month: T-class})} for the three streams."""
    petrol = ocac_monthly.profile_or_flat(ocac_monthly.ROAD, ocac_monthly.PETROL, fy_start)
    diesel = ocac_monthly.profile_or_flat(ocac_monthly.ROAD, ocac_monthly.DIESEL, fy_start)
    # Days-weighted, not equal twelfths: these streams declare no seasonality, which
    # is a claim about the SOURCE and not a licence to mis-divide the calendar.
    flat = core_monthly.days_weighted_profile(fy_start)
    return {"petrol": petrol, "diesel": diesel,
            "cng": (flat, (lambda _c, _m: "T4"), False)}


def rows(data=None, fy_start=FY_START):
    data = data if data is not None else TransportData()
    components = engine.build_components(data)
    prof = profiles(fy_start)
    basis = {
        "petrol": "OCAC Road customer class, MS+HOBC, monthly editions differenced",
        "diesel": "OCAC Road customer class, HSD, monthly editions differenced",
        "cng": "flat: no monthly metered CNG series obtained",
    }
    flat_basis = ("flat: the OCAC panel does not reach this fiscal year, and one year's "
                  "sales shape is not carried to another")
    out = []
    for fuel, (shares, method, covered) in prof.items():
        members = [c for c in components if _fuel_of(c["subitem"]) == fuel]
        if not members:
            continue
        out.extend(core_monthly.apply_profile(
            members, shares, fy_start, temporal_method=method,
            basis=basis[fuel] if (covered or fuel == "cng") else flat_basis))
    return components, out


def main():
    components, month_rows = rows()
    core_monthly.write_layer(OUT, month_rows, components)
    totals = core_monthly.month_totals(month_rows)
    print("transport monthly layer -> %s" % OUT)
    print("  %d rows over %d months; closes to the annual control exactly"
          % (len(month_rows), len(totals)))
    peak = max(totals, key=totals.get)
    trough = min(totals, key=totals.get)
    print("  peak %s %.3f Mt, trough %s %.3f Mt (flat would be %.3f)"
          % (peak, totals[peak], trough, totals[trough], sum(totals.values()) / 12.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

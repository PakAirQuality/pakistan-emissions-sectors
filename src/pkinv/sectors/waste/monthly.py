"""Waste, resolved into the twelve months of FY2023-24.

SOLID WASTE DISPOSAL RUNS THE FOD AT A MONTHLY STEP since rc20 (the fifteenth
review's recursion, S_m = S_{m-1} e^(-k/12) + W_m in swds.monthly_decomposition_
shares): this year's methane comes from a stock deposited over decades, and running
the decay monthly MEASURES how flat that makes the year instead of asserting it.
The measured within-year spread is about 7.1 percent of a flat month, of which the
calendar's own month lengths contribute 6.7 - the physical model sits within half a
point per month of days-weighting, which is the finding. Graded T3: the model is
physics over an observed deposit history, but the within-year deposit split is
days-weighted by declaration, not observed.

THE OTHER TWO STAY FLAT T4, for different reasons the basis column keeps apart.
Domestic wastewater is warm-climate anaerobic decay whose methane correction factor
is temperature-dependent in the IPCC method, so it plainly has a seasonal shape and
this inventory does not model one. Open burning is concentrated in dry weather and
around residue burning, and twelve equal months for it is wrong in a direction
anyone familiar with a Pakistani winter could name; it needs an acquisition.

Usage:  python3 -m pkinv.sectors.waste.monthly
Writes: outputs/waste_monthly_2024.csv
"""

from pkinv.assets import asset_path
import os

from pkinv.core import monthly as core_monthly
from pkinv.paths import OUTPUTS
from pkinv.sectors.waste import engine
from pkinv.sectors.waste.data import WasteData

FY_START = 2023
OUT = asset_path(OUTPUTS, "waste_monthly_2024.csv")

BASIS = {
    # The SWDS basis is BUILT, not typed: the spread figure comes from
    # monthly_spread_pct at layer build (Wave 3) - its predecessor hard-coded 7.1/6.7
    # while the function that could compute them had zero callers, the exact
    # "docstring quotes a number no code computes" failure this module's own history
    # records. See _swds_basis().
    "Domestic wastewater":
        "flat: the IPCC methane correction factor is temperature-dependent and no monthly "
        "treatment or temperature series is modelled here",
    "Open burning of waste":
        "flat: burning is concentrated in dry weather and no monthly evidence was obtained; "
        "the flat profile is a placeholder, not a finding",
}


def _swds_basis(data, fy_start):
    from pkinv.sectors.waste import swds
    spread = swds.monthly_spread_pct(data, fy_start)
    delay = int(data.p("swds_delay_months"))
    return ("first-order decay as one continuous monthly state engine from the 1960 "
            "spin-up (swds.monthly_state): measured within-year spread %.1f%% of a "
            "flat month; reaction delay %d months (shape only - the annual FOD "
            "carries none); within-year deposits days-weighted by declaration"
            % (spread, delay))


def rows(data=None, fy_start=FY_START):
    data = data if data is not None else WasteData()
    components = engine.build_components(data)
    # Days-weighted, not equal twelfths: these streams declare no seasonality, which
    # is a claim about the SOURCE and not a licence to mis-divide the calendar.
    flat = core_monthly.days_weighted_profile(fy_start)
    from pkinv.sectors.waste import swds
    fod = swds.monthly_decomposition_shares(data, fy_start)
    out = []
    for c in components:
        if c["category"] == "Solid waste disposal":
            out.extend(core_monthly.apply_profile(
                [c], fod, fy_start, temporal_method="T3",
                basis=_swds_basis(data, fy_start)))
        else:
            out.extend(core_monthly.apply_profile(
                [c], flat, fy_start, temporal_method="T4",
                basis=BASIS[c["category"]]))
    return components, out


def main():
    components, month_rows = rows()
    core_monthly.write_layer(OUT, month_rows, components)
    print("waste monthly layer -> %s" % OUT)
    t3 = sum(1 for r in month_rows if r["temporal_method"] == "T3")
    print("  %d rows; closes exactly; %d rows on the monthly FOD (T3), the rest "
          "flat T4" % (len(month_rows), t3))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

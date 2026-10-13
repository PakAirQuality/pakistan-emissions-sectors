"""Oil and gas fugitives, resolved into twelve months - upstream on observed production.

THIS LAYER WAS FLAT THROUGHOUT, BY DECLARATION, and half of that declaration has now been
replaced with data the repository already held. PBS publishes monthly provincial production of
natural gas and crude oil; the panel was parsed two passes ago and deliberately left unwired
because it covers only five or six of the nine fiscal years, until an external review
overruled the refusal: use the observed years at T2, leave the missing years flat at T4, and
never carry one year's shape to another. `core/pbs_minerals.py` implements that contract and
this layer consumes it.

WHICH STREAMS RIDE IT, AND WHY THE LINE SITS WHERE IT DOES. Upstream fugitive emissions scale
with what the fields produce: gas production, gathering, processing and sour-gas processing
leak and vent in proportion to throughput, and monthly field output is a direct administrative
record of that throughput. Oil production rides crude output the same way. The line stops
exactly there:

  * distribution, transmission, post-meter and LNG streams follow DELIVERIES and send-out -
    demand-side quantities with their own season (winter heating, summer power) that field
    production does not observe. They stay flat T4 with the acquisition named. Wiring
    production onto them would be the wrong-driver overclaim.
  * oil refining and pipeline transport follow refinery intake, not wellhead output; flat T4.

A tonne sold is not a tonne burned, and a cubic foot produced is not a cubic foot delivered:
the timing target on the shaped rows is production-side, and the registry publishes it.

Usage:  python3 -m pkinv.sectors.fugitives.monthly
Writes: outputs/fugitives_monthly_2024.csv
"""

from pkinv.assets import asset_path
import os

from pkinv.core import monthly as core_monthly
from pkinv.core import pbs_minerals
from pkinv.paths import OUTPUTS
from pkinv.sectors.fugitives import engine
from pkinv.sectors.fugitives.data import FugitivesData

FY_START = 2023
OUT = asset_path(OUTPUTS, "fugitives_monthly_2024.csv")

# The upstream streams, by the subitem prefixes the engine writes. Sour-gas processing is
# upstream throughput exactly as sweet-gas processing is; the CO2 it vents is the reservoir's.
GAS_UPSTREAM = ("Gas production", "Gas gathering", "Gas processing", "Sour-gas processing")
OIL_UPSTREAM = ("Oil production",)

FLAT_BASIS = ("flat: this stream follows deliveries, send-out or refinery intake - "
              "demand-side quantities no production series observes - and no monthly "
              "throughput ledger was obtained (SNGPL/SSGC/PPIS, request-only)")

GAS_BASIS_COVERED = ("PBS monthly provincial natural-gas production, the year's own twelve "
                     "months summed nationally; times FIELD OUTPUT, not deliveries")
OIL_BASIS_COVERED = ("PBS monthly provincial crude-oil production, the year's own twelve "
                     "months; times FIELD OUTPUT, not refinery intake")
FLAT_BASIS_UNCOVERED = ("days-weighted: the PBS minerals panel does not cover this fiscal "
                        "year and one year's production shape is never carried to another")


def _is(prefixes):
    return lambda c: any(c["subitem"].startswith(p) for p in prefixes)


def rows(data=None, fy_start=FY_START):
    data = data if data is not None else FugitivesData()
    components = engine.build_components(data)
    flat = core_monthly.days_weighted_profile(fy_start)

    plans = []
    for mineral, prefixes, covered_basis in (
            (pbs_minerals.NATURAL_GAS, GAS_UPSTREAM, GAS_BASIS_COVERED),
            (pbs_minerals.CRUDE_OIL, OIL_UPSTREAM, OIL_BASIS_COVERED)):
        shares, method_map, covered = pbs_minerals.profile_or_flat(mineral, fy_start)
        plans.append((_is(prefixes), shares,
                      lambda _c, m, _mm=method_map: _mm[m],
                      covered_basis if covered else FLAT_BASIS_UNCOVERED))
    plans.append((lambda c: True, flat, "T4", FLAT_BASIS))

    out, seen = [], set()
    for which, shares, method, basis in plans:
        members = [c for c in components if id(c) not in seen and which(c)]
        seen.update(id(c) for c in members)
        if members:
            out.extend(core_monthly.apply_profile(members, shares, fy_start,
                                                  temporal_method=method, basis=basis))
    return components, out


def main():
    components, month_rows = rows()
    core_monthly.write_layer(OUT, month_rows, components)
    shares = {}
    for row in month_rows:
        shares[row["temporal_method"]] = shares.get(row["temporal_method"], 0.0) \
            + row["co2e_Mt_AR5"]
    total = sum(shares.values())
    print("fugitives monthly layer -> %s" % OUT)
    print("  %d rows; closes exactly" % len(month_rows))
    for method in sorted(shares):
        print("  %s  %6.2f Mt  %5.1f%%" % (method, shares[method],
                                           100.0 * shares[method] / total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

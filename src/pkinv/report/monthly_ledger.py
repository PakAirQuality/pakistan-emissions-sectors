"""Configuration L at monthly grain: the one sector where L differs, resolved.

ROLES SWAPPED AT rc67. This module published configuration S (the survey dung basis)
while the reference burned all the diverted dung. The reference is now the survey, so the
second configuration with months is L: all the diverted dung burned in households.

THE FIFTEENTH REVIEW ASKED for every structural configuration at monthly
resolution. The honest scope of that ask is narrower than it sounds: the
configurations are priced as national delta scalars, and only a configuration
that is a complete component-level re-run can carry months. L is exactly that -
it re-runs the RESIDENTIAL engine on the ledger dung basis
and leaves the other nine sectors bit-identical to the reference - so its
monthly view is the residential monthly layer over the L components, and
nothing else. This module publishes that view and states the identity for the
rest, instead of republishing 2,400 unchanged rows as if they were new
information.

The other configurations stay delta-scalar-only, and the axis register now says
so per row (monthly_grain column) - the absence is typed, not silent. The
fugitives envelope members would be the next candidates (their engine takes a
scenario), and their monthly grain is declared not-built until someone builds it.

Usage:  python3 -m pkinv.report.monthly_ledger
Writes: outputs/pakemis_monthly_ledger_2024.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.core import monthly as core_monthly
from pkinv.core import configurations as _conf
from pkinv.paths import OUTPUTS

OUT = asset_path(OUTPUTS, "pakemis_monthly_ledger_2024.csv")
FY_START = 2023


def rows():
    from pkinv.sectors.residential import engine, monthly as res_monthly
    from pkinv.sectors.residential.data import ResidentialData
    data = ResidentialData()
    components = engine.build_components(
        data, dung_basis=_conf.ALTERNATIVE_DUNG_BASIS)
    prof = res_monthly.profiles(data, FY_START)
    out = core_monthly.apply_profile(
        components, None, FY_START, res_monthly.TEMPORAL_METHOD,
        profile_for=lambda c: prof[res_monthly.stream_of(c)],
        basis=res_monthly.basis)
    core_monthly.check_closure(out, components)
    return components, out


def main():
    components, month_rows = rows()
    os.makedirs(OUTPUTS, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        f.write("# Configuration L at monthly grain. ONLY the residential sector is here,\n"
                "# because L differs from the reference in the residential dung basis and\n"
                "# nowhere else: every other sector's monthly rows are bit-identical to\n"
                "# pakemis_monthly_fy2015_16_fy2023_24.csv's reference-configuration rows\n"
                "# for FY2023-24, and republishing them would present sameness as data.\n")
        w = csv.DictWriter(f, fieldnames=["configuration_id", "category", "subitem",
                                          "gas", "month", "share", "emissions_Gg",
                                          "co2e_Mt_AR5", "co2e_Mt_AR6",
                                          "temporal_method", "basis"])
        w.writeheader()
        for r in month_rows:
            w.writerow({"configuration_id": _conf.LEDGER,
                        "category": r["category"], "subitem": r["subitem"],
                        "gas": r["gas"], "month": r["month"],
                        # rc41: the same precision as the reference monthly layer (8 dp
                        # shares and Gg, 10 dp Mt); the cube reads this file to build the
                        # L grid, and 4 dp lost 0.16 kg of a 49 t charcoal stream
                        "share": round(r["share"], 8),
                        "emissions_Gg": round(r["emissions_Gg"], 8),
                        "co2e_Mt_AR5": round(r["co2e_Mt_AR5"], 10),
                        "co2e_Mt_AR6": round(r["co2e_Mt_AR6"], 10),
                        "temporal_method": r["temporal_method"],
                        "basis": r["basis"]})
    total = sum(c["co2e_Mt_AR5"] for c in components)
    print("monthly ledger view -> %s (%d rows; residential under L %.5f Mt, "
          "closes exactly; all other sectors identical to the reference monthly "
          "product by construction)" % (os.path.relpath(OUT), len(month_rows), total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

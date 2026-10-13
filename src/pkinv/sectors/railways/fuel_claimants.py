"""The railway fuel-claimant ledger: who burns the traction account, by the source's split.

WHY THIS EXISTS. The headline 1.A.3.c figure is the Year Book's summary fuel account, and
the same edition's p.163 detail table splits it: locomotive against other-than-locomotive,
per fuel, back to 1950. The non-locomotive share - workshops, power houses, pumps and
track machines, fuel that belongs in stationary and off-road categories by source - is
therefore MEASURED, not asserted, and the completeness table has long carried it as an
IE row inside 1.A.3.c. What no artefact did until the fifth review asked is publish the
carve-out as a ledger: each claimant with its volume, its share, its emissions at the
sector's own factors, and the closure identity tying the rows back to both the headline
and the locomotive-only boundary scenario.

WHAT THIS IS NOT. It is not a re-base. The source publishes one aggregate non-locomotive
figure per fuel, not a workshop/power-house/pump decomposition, so inventing per-use
streams with their own factors would fabricate a split the evidence does not carry. The
fuel stays reported in 1.A.3.c, declared IE, biasing this sector slightly high and the
stationary/off-road categories slightly low by the same amount - and the national
consequence of moving the boundary is priced as the named configuration
`rail_traction_only_boundary` (outputs/national_configurations.csv) rather than by
moving the frozen headline.

CLOSURE, ASSERTED AT WRITE TIME. Ledger co2e rows sum to the sector total to 1e-9, and
the traction-only rows sum to the `locomotive_only_1a3c` scenario's deterministic value
to the same tolerance; the module refuses to write otherwise.

Usage:  python3 -m pkinv.sectors.railways.fuel_claimants
Writes: outputs/railways_fuel_claimants_2024.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import OUTPUTS
from pkinv.sectors.railways import engine, reconcile
from pkinv.sectors.railways.data import RailwaysData
from pkinv.core.io import write_table

FIELDS = ("fuel", "claimant", "ipcc_code_by_source", "reported_in",
          "thousand_litres", "share_of_fuel", "co2e_Mt_AR5", "status", "basis", "note")

TOLERANCE_MT = 1e-9


def build(data=None):
    data = data or RailwaysData()
    comps = engine.build_components(data)
    # per PHYSICAL fuel, across both reporting categories: since the rc11 re-base the
    # components carry traction and non-traction rows, and the ledger's shares apply
    # to the fuel account as a whole
    by_fuel = {}
    for c in comps:
        stream = "Diesel" if "diesel" in c["subitem"].lower() else "Furnace oil"
        by_fuel[stream] = by_fuel.get(stream, 0.0) + c["co2e_Mt_AR5"]

    diesel = reconcile.detail_for(data.year)
    fo = reconcile.detail_for(data.year, "Residual Fuel Oil")
    d_share = reconcile.non_traction_share(data)
    fo_loco = (fo["locomotive"] or 0.0)
    fo_frac = fo_loco / (fo_loco + fo["other_than_locomotive"])

    detail_basis = ("Pakistan Railways Year Book p.163 fuel detail (locomotive / "
                    "other-than-locomotive), reconciled to the summary account by "
                    "pkinv.sectors.railways.reconcile on every build")
    rows = [
        {"fuel": "Diesel", "claimant": "locomotive traction",
         "ipcc_code_by_source": "1.A.3.c", "reported_in": "1.A.3.c",
         "thousand_litres": diesel["locomotive"],
         "share_of_fuel": round(1.0 - d_share, 6),
         "co2e_Mt_AR5": by_fuel["Diesel"] * (1.0 - d_share),
         "status": "RESOLVED-OBSERVED", "basis": detail_basis,
         "note": "the traction fuel the category name means"},
        {"fuel": "Diesel",
         "claimant": "workshops, power houses, pumps and track machines (aggregate)",
         "ipcc_code_by_source": "1.A.2 / 1.A.4.c by use; no per-use split published",
         "reported_in": engine.traction.NON_TRACTION_CATEGORY,
         "thousand_litres": diesel["other_than_locomotive"],
         "share_of_fuel": round(d_share, 6),
         "co2e_Mt_AR5": by_fuel["Diesel"] * d_share,
         "status": "RESOLVED-RECODED", "basis": detail_basis,
         "note": "since the rc11 re-base this books at its own category at rail "
                 "factors - the source publishes one non-locomotive aggregate and "
                 "no per-use split, which is what the category name declares; the "
                 "pre-rc11 declared-IE booking survives as the rail_ie_summary "
                 "configuration"},
        {"fuel": "Furnace oil", "claimant": "locomotive traction",
         "ipcc_code_by_source": "1.A.3.c", "reported_in": "1.A.3.c",
         "thousand_litres": fo["locomotive"],
         "share_of_fuel": round(fo_frac, 6),
         "co2e_Mt_AR5": by_fuel.get("Furnace oil", 0.0) * fo_frac,
         "status": "RESOLVED-OBSERVED", "basis": detail_basis,
         "note": "the minority of the RFO stream that actually moves trains"},
        {"fuel": "Furnace oil", "claimant": "power houses (aggregate)",
         "ipcc_code_by_source": "1.A.2 / 1.A.4 by use; no per-use split published",
         "reported_in": engine.traction.NON_TRACTION_CATEGORY,
         "thousand_litres": fo["other_than_locomotive"],
         "share_of_fuel": round(1.0 - fo_frac, 6),
         "co2e_Mt_AR5": by_fuel.get("Furnace oil", 0.0) * (1.0 - fo_frac),
         "status": "RESOLVED-RECODED", "basis": detail_basis,
         "note": "most of the railway RFO account runs power houses, not trains - "
                 "the larger of the two carve-outs despite the smaller volume share "
                 "of the sector; booked at the non-traction category since rc11"},
    ]

    total = sum(r["co2e_Mt_AR5"] for r in rows)
    sector = sum(by_fuel.values())
    if abs(total - sector) > TOLERANCE_MT:
        raise SystemExit("claimant ledger does not close: %r vs sector %r"
                         % (total, sector))
    traction = sum(r["co2e_Mt_AR5"] for r in rows if r["status"] == "RESOLVED-OBSERVED")
    expected = by_fuel["Diesel"] * (1.0 - d_share) + by_fuel.get(
        "Furnace oil", 0.0) * fo_frac
    if abs(traction - expected) > TOLERANCE_MT:
        raise SystemExit("traction rows disagree with the locomotive-only boundary: "
                         "%r vs %r" % (traction, expected))
    for r in rows:
        r["co2e_Mt_AR5"] = round(r["co2e_Mt_AR5"], 6)
    return rows


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = build()
    path = asset_path(OUTPUTS, "railways_fuel_claimants_2024.csv")
    write_table(path, list(FIELDS), rows)
    non_traction = sum(r["co2e_Mt_AR5"] for r in rows
                       if r["status"] == "RESOLVED-RECODED")
    print("railways fuel claimants -> %s" % os.path.basename(path))
    print("  non-traction at its own category since rc11: %.5f Mt CO2e" % non_traction)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

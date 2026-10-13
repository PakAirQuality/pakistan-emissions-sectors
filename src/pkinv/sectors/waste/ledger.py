"""The waste-fate ledger: the D + U = G partition as an executable account.

The sector's central accounting claim - solid-waste disposal and open burning are an
exhaustive partition of one national generation figure - has always been asserted in
code (tests pin the closure exactly). This module writes it as a CSV in the same
claimant style as the transport fuel ledger, so the partition is a published artefact
rather than a property a reader must trust the tests about.

The ledger deliberately carries a fate with no emissions: the uncollected waste that
does NOT burn. It is dumped on land or tipped into watercourses, produces nothing this
inventory currently estimates, and is the honest remainder of the partition - roughly
6 Mt/yr whose only Pakistani evidence is the HIES 2024-25 household route shares
(rural open-space disposal 88%, waterways under 1%). Writing the row is the point:
a fate that vanished from the file would look resolved, and it is not.

Closure is checked at write time and raises rather than warns, mirroring
core.downscale.check_reconciliation: collected + uncollected = generated, and
burned + unresolved = uncollected, both to within one tonne on a ~30 Mt account.

Usage: written by run_waste on every run; also  python3 -m pkinv.sectors.waste.ledger
Writes: outputs/waste_ledger_2023.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import OUTPUTS
from pkinv.sectors.waste import open_burning, swds
from pkinv.sectors.waste.data import WasteData
from pkinv.core.io import write_table

TOLERANCE_T = 1.0                     # tonnes, on a ~30,000,000 t account

UNRESOLVED = "UNRESOLVED - dumped to land and waterways, unburned"


def rows(data, year=None):
    """The ledger rows, tonnes wet waste, closure asserted."""
    generated = swds.waste_generated(data, year)
    disposed = swds.waste_disposed(data, year)
    burned = open_burning.waste_burnt(data, year)
    uncollected = generated - disposed
    unresolved = uncollected - burned

    if abs(disposed + uncollected - generated) > TOLERANCE_T:
        raise ValueError("waste ledger does not close: collected %.1f + uncollected %.1f "
                         "!= generated %.1f t" % (disposed, uncollected, generated))
    if abs(burned + unresolved - uncollected) > TOLERANCE_T:
        raise ValueError("uncollected fates do not close: burned %.1f + unresolved %.1f "
                         "!= uncollected %.1f t" % (burned, unresolved, uncollected))

    def share(t):
        return round(t / generated, 4)

    return [
        {"tier": "national", "claimant": "Generated", "Mt_wet": round(generated / 1e6, 4),
         "share_of_generated": share(generated), "ipcc_category": "",
         "treatment": "control",
         "note": "district population panel x Pak-EPA per-capita rates (swds.waste_generated)"},
        {"tier": "national", "claimant": "Collected to disposal sites",
         "Mt_wet": round(disposed / 1e6, 4), "share_of_generated": share(disposed),
         "ipcc_category": "4.A", "treatment": "First Order Decay over the deposit series",
         "note": "the collected complement of the uncollected fractions; decays over "
                 "decades at the uncategorised-site MCF"},
        {"tier": "national", "claimant": "Uncollected",
         "Mt_wet": round(uncollected / 1e6, 4), "share_of_generated": share(uncollected),
         "ipcc_category": "", "treatment": "partitioned below",
         "note": "urban 0.30 / rural 0.70 of stratum generation (What a Waste); HIES "
                 "2024-25 household routes read 0.42 / 0.93 - a named structural scenario"},
        {"tier": "uncollected", "claimant": "Openly burned",
         "Mt_wet": round(burned / 1e6, 4), "share_of_generated": share(burned),
         "ipcc_category": "4.C.2", "treatment": "IPCC Eq 5.7 x Eq 5.2; air-pollutant layer "
         "on the identical mass",
         "note": "0.60 of uncollected waste (IPCC Box 5.1); emits immediately, mostly as "
                 "biogenic CO2 with a fossil third"},
        {"tier": "uncollected", "claimant": UNRESOLVED,
         "Mt_wet": round(unresolved / 1e6, 4), "share_of_generated": share(unresolved),
         "ipcc_category": "", "treatment": "no GHG pathway applied",
         "note": "not landfilled (no site conditions), not burned; the honest remainder. "
                 "Only evidence on its composition: HIES 2024-25 routes (rural open space "
                 "0.88, waterways under 0.01). A tonne moved here from collection is a "
                 "tonne removed from slow landfill decay"},
    ]


def write(data, year=None):
    out = rows(data, year)
    path = asset_path(OUTPUTS, "waste_ledger_%d.csv" % (year or data.year))
    write_table(path, ["tier", "claimant", "Mt_wet",
                                          "share_of_generated", "ipcc_category",
                                          "treatment", "note"], out)
    return path, out


def main():
    data = WasteData()
    path, out = write(data)
    print("waste-fate ledger -> %s" % path)
    for r in out:
        print("  %-12s %-55s %8.2f Mt  %.3f" % (r["tier"], r["claimant"][:55],
                                                r["Mt_wet"], r["share_of_generated"]))


if __name__ == "__main__":
    main()

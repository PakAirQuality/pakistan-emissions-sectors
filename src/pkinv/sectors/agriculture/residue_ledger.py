"""Where crop residues go - a mass ledger with four destinations that must close.

WHY A LEDGER. Three parts of this inventory consume the same above-ground residue mass:
managed soils return a fraction of its nitrogen (frac_returned, feeding FCR), field
burning burns a fraction (frac_burned, the 3.F category and its air layer), and - since
the August 2026 residential round - households burn a fraction as domestic fuel
(frac_fuel, the 1.A.4.b residue stream). Before this module those fractions lived in two
separate files with nothing asserting they described one physical mass. A crop whose
fractions summed past 1 would have silently created residue out of nothing, each consumer
individually plausible.

THE CLOSURE. Per crop: returned + burned + fuel + other == 1 exactly, where "other" is
the residual destination (fodder, bedding, sale - bhusa and stover are fodder before they
are anything else in Pakistan) and must be non-negative. tests/test_agriculture.py asserts
both properties for every crop, so a future edit that raises one fraction without room
fails loudly.

WHAT THIS LEDGER IS NOT. Bagasse is a mill fuel counted in the power sector; it never
enters this ledger, which covers field residues only. And frac_fuel is ALL fuel use of
the residue, not household fuel specifically - brick kilns and small industry burn
sticks too - so the residential stream is AN UPPER-BOUND RESIDENTIAL ALLOCATION of the
ledger's fuel destination (R_fuel = R_household + R_commercial/industrial +
R_unresolved; it can only overstate households), and
the HIES price bracket is the demand-side check that keeps it bounded: the residential
stream RIDES fuel_available as its supply-side control (like dung under configuration
L), and a test asserts the ledger quantity falls inside the survey's price-implied
bracket (see pkinv.sectors.residential.hies.residue_implied_range_kg).
"""
from pkinv.sectors.agriculture.ef_library import InventoryData

DESTINATIONS = ("returned", "burned", "fuel", "other")


def ledger(agri=None):
    """{crop: {"residue_t": t, "returned": t, "burned": t, "fuel": t, "other": t,
    "fractions": {...}}} - above-ground residue dry matter by destination."""
    agri = InventoryData() if agri is None else agri
    out = {}
    for crop, rp in agri.residue.items():
        prod = agri.crops.get(crop, {}).get("production_t")
        rr = rp.get("residue_ratio_ag")
        if not prod or not rr:
            continue
        mass = prod * rr
        fr = rp.get("frac_returned", 0.0)
        fb = agri.burning.get(crop, {}).get("frac_burned", 0.0)
        ff = rp.get("frac_fuel", 0.0)
        fo = 1.0 - fr - fb - ff
        out[crop] = {
            "residue_t": mass,
            "returned": mass * fr, "burned": mass * fb,
            "fuel": mass * ff, "other": mass * fo,
            "fractions": {"returned": fr, "burned": fb, "fuel": ff, "other": fo},
        }
    return out


def fuel_available_t(agri=None):
    """Total residue dry matter available as household fuel, t/yr - the supply-side
    bound the residential HIES-derived quantity must not exceed."""
    return sum(row["fuel"] for row in ledger(agri).values())

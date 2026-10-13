"""NEPRA's per-plant generation by fuel, FY2015-16 to FY2019-20, as a provincial share vector.

NOT APPLIED SINCE rc66. From rc44 to rc65 `downscale.load_shares` took furnace oil's and
diesel's provincial split from this module for the five years it reaches, and left gas on the
reference-year vector on the measurement described below. Both decisions are superseded:
pkinv.sectors.power.province_panel splits every grid fuel by each year's own FUEL record, which
for these years is the fuel-quantity columns of the same report tables this module reads the
generation columns of. What remains live here is `basis_change`, the published comparison of
generation against fuel for the one year both exist, and it is a record, not a rule.

Two things in the text below are known to be wrong and are kept as history, not as argument.
The gas comparison was run on a panel holding 47.5 percent of FY2019-20's gas generation
(Balloki, Bhikki, Haveli Bahadur Shah and KAPCO are absent from it), so "own-year generation
is four times worse for gas" was a statement about an incomplete panel. And the panel files
Narowal Energy's generation under Gas: the report prints that station under the wrong
sub-table heading, and it burns furnace oil (scripts/ingest_nepra_plant_fuel_quantity.py).

WHAT THIS IS FOR. data/activity/power/plant_fuel_generation.csv has sat in the tree read by no
module in src/ while those same five fiscal years allocated grid power on the REFERENCE year's
provincial shares, because a zero-argument load_shares had no other vector to return. For
furnace oil that is not a small error: the shipped vector reads 1.0 Punjab, and in FY2015-16
Hub Power in Balochistan was 7,547 GWh - 31.2 percent of national furnace-oil generation.

WHY GAS IS NOT RE-BASED HERE, which is the important part of this module.

FY2019-20 is covered by BOTH this panel and the plant FUEL ledger, and emissions follow fuel,
not generation, so for that one year there is a correct answer to score candidates against.
Total-variation distance from the own-year fuel vector:

                    borrowed FY2023-24    own-year generation
    power_gas                   0.0665                 0.3299
    power_rfo                   0.0664                 0.0051
    power_hsd                   0.0000                 0.0000

For gas the vector this module would install is FIVE TIMES WORSE than the one it would replace,
and for furnace oil it is THIRTEEN TIMES BETTER. Balochistan is the sharpest gas case: fuel says
0.1576, the borrowed vector says 0.1739, and generation says 0.3593. Generation shares equal fuel shares only when every plant burns at the
same heat rate, and the gas fleet is exactly where that collapses - Punjab's RLNG combined-cycle
stations against Uch's low-BTU plants in Balochistan are not the same machine. Furnace-oil
plants are alike enough that generation tracks fuel to 0.028.

Converting generation to fuel with the ledger's implied heat rates is the obvious escape and it
is refused with a number: those heat rates cover 26.5 percent of FY2015-16 gas generation and
37.8 percent of FY2019-20 - Guddu, Jamshoro and Nandipur, the largest stations here, have none -
so it would mean imputing heat rates for most of the fleet. It is also CIRCULAR in the only year
that could test it, because the implied heat rate is derived from that year's own fuel and
generation.

TWO LIMITS, stated because one overlap year is thin evidence. The test year is four years from
the reference vintage while FY2015-16 is eight, so proximity flatters the borrowed vector and
the gas result should be expected to weaken going back; and n is one. What would settle it is
the fuel-quantity columns that sit beside the generation columns in these same NEPRA tables -
the ingest reads only the ones headed (GWh) and says so - and reading them is an acquisition,
not a wiring.

THE CONTROL HAD A HOLE, and closing it is what made this test worth running. On its first
pass the FY2019-20 fuel vector reported 26.5 percent of furnace oil UNPLACED and Sindh's share
as zero, which made the borrowed vector look closer than own-year generation. The unplaced fuel
was two stations - TPS Jamshoro, which is Sindh, and KAPCO, which is Punjab - whose EARLIER
ledger rows carry cost-column prefixes that point_sources.ALIAS did not cover. The reference
year has no unmatched rows at all, so those three aliases move no published share; they close a
diagnostic that was reporting an absence it had manufactured. With the control complete, furnace
oil's own-year vector goes from marginally worse than the borrowed one to thirteen times better.
A control is not a control until you have asked what it cannot see.

THE K-ELECTRIC SCOPE IS EXCLUDED WHOLE, corroborated rather than assumed. NEPRA groups eight
plants under "K-Electric and IPPs", mixing K-E's own stations with the IPPs that sell to it. Of
those eight, six appear in the plant ledger as system K-Electric and NOT ONE appears as CPPA, so
the scope is homogeneous and no plant-by-plant judgement is needed. SoIR Table 3 - the national
fuel table this sector's mass is built from - is CPPA-only, which plant_ledger.in_boundary is
the single definition of.
"""

from pkinv.assets import asset_path
import collections
import os

from pkinv.paths import DATA
from pkinv.activity.store import read_rows
from pkinv.sectors.power.plant_names import plant_key

PANEL = asset_path(DATA, "activity", "power", "plant_fuel_generation.csv")
KE_SCOPE = "K-Electric and IPPs"

# The panel's fuel words to this inventory's spatial share rows. RLNG and pipeline gas are one
# Table 3 row and one emission stream, as everywhere else in this sector.
FUEL_STREAM = {"Gas": "power_gas", "RLNG": "power_gas",
               "RFO": "power_rfo", "HSD": "power_hsd"}

# The streams this module re-based from rc44 to rc65. Nothing reads this for an allocation any
# more (see the module docstring); `province_shares` below is kept because `basis_change`
# compares it with the fuel vector.
REBASED = ("power_rfo", "power_hsd")

PANEL_YEARS = ("2015-16", "2016-17", "2017-18", "2018-19", "2019-20")


def panel_year(fiscal_start_year):
    """'2015' -> '2015-16', or None where this panel does not reach."""
    if not fiscal_start_year:
        return None
    start = int(fiscal_start_year)
    label = "%d-%02d" % (start, (start + 1) % 100)
    return label if label in PANEL_YEARS else None


def rows(fiscal_year):
    """The CPPA-scope panel rows for one panel year."""
    return [r for r in read_rows(PANEL)
            if r["fiscal_year"] == fiscal_year and r["scope"] != KE_SCOPE]


def _locations():
    from pkinv.sectors.power import point_sources
    return {plant_key(r["plant"]): r for r in point_sources.locations().values()}


def generation_by_province(fiscal_year):
    """({stream: {province: GWh}}, {stream: unmatched GWh}).

    A plant this module cannot place is REPORTED, never spread: it lands in the unmatched
    total, and the share vector is normalised over what is placed. Five plants and 3.7 percent
    of the panel are unmatched, essentially all of it gas; for furnace oil and diesel - the
    streams this module actually re-bases - it is under 0.2 percent in every year.
    """
    located = _locations()
    placed = collections.defaultdict(lambda: collections.defaultdict(float))
    unmatched = collections.defaultdict(float)
    for r in rows(fiscal_year):
        stream = FUEL_STREAM.get(r["fuel"])
        if stream is None:
            continue
        gwh = float(r["generation_gwh"] or 0.0)
        hit = located.get(plant_key(r["plant"]))
        if hit is None:
            unmatched[stream] += gwh
        else:
            placed[stream][hit["province"]] += gwh
    return placed, unmatched


def province_shares(fiscal_year):
    """{stream: {province: share}} for the streams this panel is entitled to re-base."""
    placed, _unmatched = generation_by_province(fiscal_year)
    out = {}
    for stream in REBASED:
        total = sum(placed[stream].values())
        if total <= 0:
            continue
        out[stream] = {province: gwh / total for province, gwh in placed[stream].items()}
    return out


# --- the basis diagnostic ------------------------------------------------------------------

BASIS_OUT = "pakemis_power_grid_basis_change.csv"
# The panel labels a fiscal year "2019-20"; the plant ledger keys it by its start year as
# an INTEGER, which plant_ledger.rows compares with int(). One year, two spellings.
OVERLAP_PANEL_YEAR, OVERLAP_LEDGER_YEAR = "2019-20", 2019


def _renormalise(vector):
    """Drop point_sources' UNMATCHED residual and renormalise over located provinces.

    THE KEY IS A HAZARD, not a province: fuel_province_shares reports unplaceable energy under
    'UNMATCHED' precisely so it cannot be silently spread, and a consumer that passes it on to
    the grid would have the mass dropped instead. Comparing two vectors requires both to be
    over the same support, so it is removed here and its size reported beside the comparison.
    """
    located = {p: v for p, v in vector.items() if p != "UNMATCHED"}
    total = sum(located.values())
    return ({p: v / total for p, v in located.items()} if total > 0 else {},
            vector.get("UNMATCHED", 0.0))


def _tvd(a, b):
    return 0.5 * sum(abs(a.get(p, 0.0) - b.get(p, 0.0)) for p in set(a) | set(b))


def basis_change(data):
    """What re-basing grid power from FUEL to GENERATION would cost, per stream and province.

    FY2019-20 is the only fiscal year both bases cover, so it is the only place this question
    has an answer rather than an opinion. Emissions follow fuel, so the fuel vector is the
    control and the other two are candidates: the borrowed reference-year vector the release
    ships for every period, and this panel's own-year generation.

    This table is the evidence for re-basing furnace oil and NOT gas, and it is published so
    that the decision can be re-examined against the same numbers rather than re-argued.
    """
    from pkinv.sectors.power import downscale, point_sources
    fuel = point_sources.fuel_province_shares(data, OVERLAP_LEDGER_YEAR)
    borrowed = downscale.load_shares()
    placed, unmatched = generation_by_province(OVERLAP_PANEL_YEAR)
    out = []
    for stream in ("power_gas", "power_rfo", "power_hsd"):
        if stream not in fuel:
            continue
        control, unmatched_fuel = _renormalise(fuel[stream])
        total = sum(placed[stream].values())
        generation = {p: g / total for p, g in placed[stream].items()} if total > 0 else {}
        borrowed_v = {p: v for p, v in borrowed.get(stream, {}).items() if v}
        d_gen, d_borrow = _tvd(control, generation), _tvd(control, borrowed_v)
        for province in sorted(set(control) | set(generation) | set(borrowed_v)):
            out.append({
                "stream": stream, "province": province,
                "fuel_basis_share": "%.6f" % control.get(province, 0.0),
                "generation_basis_share": "%.6f" % generation.get(province, 0.0),
                "borrowed_reference_share": "%.6f" % borrowed_v.get(province, 0.0),
                "generation_minus_fuel": "%+.6f" % (generation.get(province, 0.0)
                                                    - control.get(province, 0.0)),
                "tvd_generation_vs_fuel": "%.6f" % d_gen,
                "tvd_borrowed_vs_fuel": "%.6f" % d_borrow,
                "unmatched_fuel_share": "%.6f" % unmatched_fuel,
                "unmatched_generation_share": "%.6f" % (
                    unmatched[stream] / (total + unmatched[stream])
                    if total + unmatched[stream] else 0.0),
                "rebased": "yes" if stream in REBASED else "no",
                "decision": ("own-year generation is closer to the fuel control"
                             if d_gen < d_borrow else
                             "the borrowed reference vector is closer to the fuel control; "
                             "generation shares equal fuel shares only under a uniform heat "
                             "rate, and the gas fleet is where that fails"),
            })
    return out


def main():
    import csv
    import sys
    from pkinv.paths import OUTPUTS
    from pkinv.sectors.power.data import PowerData
    rows = basis_change(PowerData())
    path = asset_path(OUTPUTS, BASIS_OUT)
    fields = ["stream", "province", "fuel_basis_share", "generation_basis_share",
              "borrowed_reference_share", "generation_minus_fuel", "tvd_generation_vs_fuel",
              "tvd_borrowed_vs_fuel", "unmatched_fuel_share", "unmatched_generation_share",
              "rebased", "decision"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        handle.write(
            "# WHICH BASIS IS CLOSER TO THE ONE EMISSIONS ACTUALLY FOLLOW (rc44).\n"
            "# FY2019-20 is the only fiscal year covered by both the NEPRA generation panel\n"
            "# and the plant FUEL ledger, so it is the only year in which this question has\n"
            "# an answer rather than an opinion. Emissions follow fuel, so fuel_basis_share\n"
            "# is the control and the other two columns are candidates: the borrowed\n"
            "# reference-year vector this release ships for every period, and the panel's\n"
            "# own-year generation. rebased=yes marks the streams this release moved.\n")
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    for r in rows:
        print("  %-11s %-14s fuel %s  generation %s  borrowed %s"
              % (r["stream"], r["province"], r["fuel_basis_share"],
                 r["generation_basis_share"], r["borrowed_reference_share"]))
    seen = {}
    for r in rows:
        seen[r["stream"]] = (r["tvd_generation_vs_fuel"], r["tvd_borrowed_vs_fuel"], r["rebased"])
    for stream, (gen, bor, rebased) in sorted(seen.items()):
        print("  %-11s TVD generation %s vs borrowed %s -> re-based: %s"
              % (stream, gen, bor, rebased))
    print("  -> %s" % path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

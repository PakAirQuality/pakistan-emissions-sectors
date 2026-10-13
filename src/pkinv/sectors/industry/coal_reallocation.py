"""If the power column is wrong, the industrial column moves. By how much, and does it help?

WHY THIS EXISTS. HDIP's coal CONSUMPTION is its coal SUPPLY: the allocation identity closes to
plus or minus a kilotonne in thirteen of fourteen years, which means the sectoral split is a
redistribution of a fixed total and not fourteen independent measurements. So the power-coal
question and the industrial-coal question are ONE question. Replacing HDIP's power column with
the stations' own metered coal changes what is left for brick, cement and households by exactly
the same tonnage, in the opposite direction, and the national effect is the difference of two
numbers rather than one. An estimate that moved power alone would be arithmetic, not an
inventory.

THE TWO TREATMENTS, BOTH DEFENSIBLE, AND THEY DISAGREE ABOUT SOMETHING THAT MATTERS.
  A  power only. The residual is treated as not emitted - stock, or the statistical difference
     an apparent-consumption series carries by construction. The reference year falls 18.0 Mt
     and the series PEAK MOVES from FY2021-22 to FY2020-21.
  B  reconciled. The residual flows to the industrial lane at industry_ncv. The reference year
     falls 9.9 Mt and the peak STAYS at FY2021-22.
Eight megatonnes at the reference year, and the peak-location finding survives under one and
not the other. This file publishes both and names which the evidence favours.

WHAT DECIDES IT IS AN INDEPENDENT LINE THAT WAS ALREADY HERE. The allocation identity carries
the brick-kiln FLEET bound - a kiln census that shares no input with NEPRA's per-station coal
metering. As booked, brick sits BELOW that fleet's own low bound in THREE of the nine years
(FY2016-17, FY2022-23, FY2023-24). Adding the power residual brings all nine inside the bound.
So the reallocation never makes the brick position worse and repairs it where it was broken -
a consistency argument in its favour, NOT a proof: six years were already inside, and the bound
is wide enough that landing inside it is a weak test. An earlier draft of this docstring said
"most years". The product says three, and the product is right.

WHAT THIS DOES NOT CLAIM. The fleet bound is one count with no time axis, so "inside the
bound" is a consistency check and not a measurement of brick coal; the bound's own width
(3,095 to 9,005 kt) is wider than the quantity in dispute. And the residual is not evidence
that brick specifically burned it - only that the coal was supplied and that the power stations
did not burn it. Which non-power consumer took it is not resolved here and the file says so.
"""
import argparse

from pkinv.assets import asset_path
from pkinv.core.io import read_rows, write_or_check
from pkinv.paths import DATA, OUTPUTS

OUT = asset_path(OUTPUTS, "pakemis_coal_sector_reallocation.csv")
CFG = asset_path(OUTPUTS, "pakemis_power_coal_configurations.csv")
ALLOC = asset_path(OUTPUTS, "pakemis_coal_allocation_identity.csv")

IND_NCV = 25.8          # TJ/Gg, industry_ncv "Other Bituminous Coal", the declared honest bucket
IND_CO2 = 94.6          # t CO2/TJ, other bituminous
UPLIFT = 1.00429        # CH4 and N2O beside the CO2

# FY2015-16 IS THE ONE YEAR THE IDENTITY DOES NOT CLOSE, by -203.8 kt, which the allocation
# identity already declares as its single unexplained exception. The two deltas therefore do
# NOT offset that year, and they offset by construction in the other eight. The gap is carried
# in identity_closes_kt rather than smoothed, because a reallocation that silently absorbed a
# known non-closure would be inventing 204 kt of coal.
FIELDS = ("period_id", "fiscal_start_year", "national_supply_kt", "station_power_kt",
          "hdip_power_kt", "power_delta_kt", "hdip_industrial_kt",
          "residual_industrial_kt", "industrial_delta_kt", "industrial_offset_Mt",
          "brick_booked_kt", "brick_fleet_low_kt", "brick_with_residual_kt",
          "brick_position_booked", "brick_position_with_residual", "identity_closes_kt",
          "note")

BANNER = """\
# IF THE POWER COLUMN MOVES, THE INDUSTRIAL COLUMN MOVES. BY HOW MUCH, AND WHETHER IT HELPS.
#
# HDIP's coal consumption IS its coal supply - the allocation identity closes to a kilotonne in
# thirteen of fourteen years - so the sectoral split redistributes a fixed total. Replacing the
# power column with the stations' own metered coal therefore changes the industrial residual by
# the same tonnage in the opposite direction, and the national effect is a difference of two
# numbers. power_delta_kt and industrial_delta_kt are that pair.
#
# THE CROSS-CHECK IS THE POINT OF THE FILE, and it comes from an unrelated source. The
# brick-kiln FLEET bound is a kiln census; NEPRA's per-station coal is metering. They share no
# input. brick_position_booked reads "below the fleet floor" in THREE of the nine years, and
# brick_position_with_residual reads "inside the bound" in all nine. The reallocation therefore
# never worsens the brick position and repairs it where it was broken - a consistency argument
# for the reconciled treatment rather than a proof of it, since six years were already inside
# and the bound is wide.
#
# WHAT THE COLUMNS DO NOT SAY. The fleet was counted ONCE and has no time axis, so its bound is
# constant across the panel and "inside" is a consistency check, not a measurement - the bound
# is wider than the quantity in dispute. And the residual shows only that coal was supplied and
# that the stations did not burn it; WHICH non-power consumer took it is unresolved, and
# attributing all of it to brick is an upper reading used to test the direction, never a
# booking.
#
# NOTHING IS BOOKED FROM THIS FILE. It measures the consequence of a re-base; the re-base
# itself is a declared pin movement.
"""


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _period(y):
    return "FY%d-%02d" % (y, (y + 1) % 100)


def build():
    cfg = {int(r["fiscal_start_year"]): r for r in read_rows(CFG, comments=True)
           if r["configuration_id"] == "C1_stations_rank_default"}
    supply, consumers, bounds, booked = {}, {}, {}, {}
    for r in read_rows(asset_path(DATA, "activity", "industry", "coal_supply.csv"),
                       comments=True):
        if r.get("period_coverage") != "full_year" or r.get("revision_status") != "final":
            continue
        y = int(r["fiscal_year"].split("-")[0])
        imp, pro = _num(r["coal_imports_kt"]), _num(r["coal_production_kt_petroleum_division"])
        if imp is not None and pro is not None:
            supply[y] = imp + pro
    for r in read_rows(asset_path(DATA, "activity", "industry", "coal_by_consumer.csv"),
                       comments=True):
        if r["coal_kt"] and r["revision_status"] == "final":
            consumers.setdefault(int(r["fiscal_year"].split("-")[0]), {})[r["consumer"]] = \
                float(r["coal_kt"])
    for r in read_rows(ALLOC, comments=True):
        if r["row_kind"] == "brick_bound":
            y = int(r["period_id"][2:6])
            lo = _num(r["fleet_low_kt"])
            if lo is not None:
                bounds[y] = min(bounds.get(y, lo), lo)      # the LOWEST floor either reading gives
            booked[y] = _num(r["value_kt"])

    rows = []
    for y in sorted(set(cfg) & set(supply) & set(consumers)):
        c = cfg[y]
        stn = _num(c["mass_kt"]) or _num(c["mass_hi_kt"])
        hp = consumers[y].get("power")
        hi = consumers[y].get("brick_kilns", 0.0) + consumers[y].get("cement", 0.0)
        house = consumers[y].get("household", 0.0)
        if stn is None or hp is None:
            continue
        resid = supply[y] - stn - house
        d_ind = resid - hi
        offset = d_ind * IND_NCV * IND_CO2 * UPLIFT / 1e6
        bk, floor = booked.get(y), bounds.get(y)
        bk_resid = (bk + d_ind) if (bk is not None and d_ind > 0) else bk
        def place(v):
            if v is None or floor is None:
                return ""
            return "below the fleet floor" if v < floor else "inside the bound"
        rows.append({
            "period_id": _period(y), "fiscal_start_year": y,
            "national_supply_kt": "%.0f" % supply[y],
            "station_power_kt": "%.0f" % stn, "hdip_power_kt": "%.0f" % hp,
            "power_delta_kt": "%+.0f" % (stn - hp),
            "hdip_industrial_kt": "%.0f" % hi,
            "residual_industrial_kt": "%.0f" % resid,
            "industrial_delta_kt": "%+.0f" % d_ind,
            "industrial_offset_Mt": "%+.2f" % offset,
            "brick_booked_kt": "" if bk is None else "%.0f" % bk,
            "brick_fleet_low_kt": "" if floor is None else "%.0f" % floor,
            "brick_with_residual_kt": "" if bk_resid is None else "%.0f" % bk_resid,
            "brick_position_booked": place(bk),
            "brick_position_with_residual": place(bk_resid),
            # supply less everything HDIP books. Zero in eight years by construction; -204 kt
            # in FY2015-16, the allocation identity's one declared exception.
            "identity_closes_kt": "%+.0f" % (supply[y] - hp - hi - house),
            "note": ("the industrial lane moves %+.0f kt, worth %+.2f Mt CO2e at industry_ncv "
                     "%.1f TJ/Gg - against the power lane's %+.0f kt. Which non-power consumer "
                     "took the coal is NOT resolved; attributing all of it to brick is an upper "
                     "reading used to test direction%s"
                     % (d_ind, offset, IND_NCV, stn - hp,
                        ". NOTE: HDIP's own supply and consumption do not close this year, by "
                        "%+.0f kt - the allocation identity's single declared exception - so "
                        "the two deltas do not offset here and the difference is that gap"
                        % (supply[y] - hp - hi - house)
                        if abs(supply[y] - hp - hi - house) > 2.0 else ""))})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="verify the shipped file matches a fresh build; write nothing")
    args = ap.parse_args(argv)
    rows = build()
    status = write_or_check(OUT, FIELDS, rows, check=args.check, banner=BANNER.splitlines())
    if args.check:
        return status
    print("Coal sector reallocation -> %s (%d years)" % (OUT, len(rows)))
    print("  %-10s %11s %11s %12s %24s %22s" % ("period", "power kt", "industry kt",
                                                "offset Mt", "brick booked", "with residual"))
    below = 0
    for r in rows:
        below += r["brick_position_booked"] == "below the fleet floor"
        print("  %-10s %11s %11s %12s %24s %22s"
              % (r["period_id"], r["power_delta_kt"], r["industrial_delta_kt"],
                 r["industrial_offset_Mt"], r["brick_position_booked"],
                 r["brick_position_with_residual"]))
    inside = sum(1 for r in rows if r["brick_position_with_residual"] == "inside the bound")
    print("  brick below its own fleet floor as booked: %d of %d years; with the residual, "
          "inside the bound in %d" % (below, len(rows), inside))


if __name__ == "__main__":
    raise SystemExit(main())

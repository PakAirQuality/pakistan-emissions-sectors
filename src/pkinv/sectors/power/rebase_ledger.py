"""What the coal re-base moved, year by year, and which printed table caused each move.

WHY THIS EXISTS. The review asked for the numerical changes AND their source-level causes,
which a pair of totals cannot give. A reader handed "469.64 became 451.86" can check nothing;
a reader handed, for each year, the two coal energies, the mass and calorific terms they
decompose into, the named table and column each side comes from, and the national consequence,
can check all of it. That is this file.

THE DECOMPOSITION IS EXACT, not a regression. The ratio of the booked account to the
superseded one factorises as

    booked / superseded  =  (station mass / HDIP mass)  x  (fleet rank CV / 18.73)

because both accounts are a mass times a calorific value and C2 in the configurations product
holds the second factor fixed while changing the first. Both terms are printed here and their
product is asserted against the ratio.

WHAT THE DECOMPOSITION SAYS, and an earlier draft of the configurations module said something
weaker and wrong. It claimed the mass term "stays inside 0.74-0.99" so that the sign change
was entirely the conversion. It does not: across the panel the mass term runs 0.569 to 1.423
and the calorific term 0.635 to 1.377, and BOTH cross unity. What is true is which one is
larger, and that has to be measured in log space for the two to be comparable: the calorific
term is the larger in seven of the nine years, and two to three times the mass term in
FY2021-22, FY2022-23 and FY2023-24, which carry the three biggest moves. The two years the
mass account dominates are real disagreements between the records, not rounding - FY2016-17,
where the stations report 445-534 kt against HDIP's 859.6, and FY2020-21, where they report
13,111 kt against 9,215.

WHAT IS NOT IN HERE. The industrial consequence. HDIP's coal consumption is its supply, so
moving the power column leaves a residual in the non-power lane; that residual is published
BESIDE the total in outputs/pakemis_coal_sector_reallocation.csv and is NOT booked, because
which non-power consumer took the coal is unresolved and a diagnostic gap is never inserted as
a residual. This file records the power move only, which is the move that happened.
"""
import argparse
import math

from pkinv.assets import asset_path
from pkinv.core.io import read_rows, write_or_check
from pkinv.paths import DATA, OUTPUTS

TOE_TJ = 41.868e-3
OUT = asset_path(OUTPUTS, "pakemis_power_coal_rebase_ledger.csv")
CFG = asset_path(OUTPUTS, "pakemis_power_coal_configurations.csv")
TRAJ = asset_path(OUTPUTS, "pakemis_structural_trajectories.csv")
SERIES = asset_path(OUTPUTS, "pakemis_national_series.csv")
BOOKING = asset_path(DATA, "activity", "power", "coal_energy_booking.csv")

LEGACY_AXIS = "power coal energy basis (legacy published control)"

FIELDS = ("period_id", "fiscal_start_year", "booked_toe", "superseded_toe",
          "ratio_booked_to_superseded", "mass_term", "calorific_term",
          "dominant_term", "booked_evidence_grade",
          "grid_booked_Mt", "grid_superseded_Mt", "grid_move_Mt",
          "national_booked_Mt", "national_superseded_Mt", "national_move_Mt",
          "booked_source", "superseded_source", "note")

BANNER = """\
# WHAT THE COAL RE-BASE MOVED, YEAR BY YEAR, AND WHAT CAUSED EACH MOVE.
#
# One row per fiscal year. booked_* is the account the engine books - the generating stations'
# own metered coal at IPCC Vol.2 Ch.1 Table 1.2 rank default net calorific values. superseded_*
# is NEPRA SoIR Table 3's published coal energy, the reference for every release before this
# one, retained as a named legacy control rather than deleted.
#
# THE CAUSE IS THE PAIR OF TERMS, NOT THE RATIO. ratio = mass_term x calorific_term exactly,
# where mass_term is the stations' tonnage over HDIP's power column and calorific_term is the
# fleet's own rank-weighted calorific value over Table 3's flat 18.73 TJ/Gg. Both cross unity
# across the panel (mass 0.569-1.423, calorific 0.635-1.377), so neither alone explains the
# sign changes; dominant_term says which is larger in that year, measured in log space so the
# two are comparable. The calorific term is larger in seven of nine years.
#
# national_move_Mt IS THE PUBLISHED SERIES' OWN CHANGE, taken from the legacy axis in
# outputs/pakemis_structural_trajectories.csv rather than from a remembered total, so a reader
# can reproduce it from the shipped products without trusting this file.
#
# NOTHING HERE IS A SCENARIO AND NOTHING HERE IS A CHOICE. The choice is recorded in
# scripts/check_pins.py with its reason; this file measures what it did.
"""


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def build():
    cfg = {}
    for r in read_rows(CFG, comments=True):
        cfg.setdefault(int(r["fiscal_start_year"]), {})[r["configuration_id"]] = r
    booking = {int(r["fiscal_year"]): r for r in read_rows(BOOKING, comments=True)}
    legacy = {}
    for r in read_rows(TRAJ, comments=True):
        if r["axis"] == LEGACY_AXIS:
            legacy[int(r["fiscal_end_year"]) - 1] = r
    national = {r["period_label"]: _num(r["co2e_Mt_AR5"])
                for r in read_rows(SERIES, comments=True)
                if r["row_kind"] == "covered_total"}

    rows = []
    for y in sorted(set(cfg) & set(booking) & set(legacy)):
        period = "FY%d-%02d" % (y, (y + 1) % 100)
        c0, c1 = cfg[y]["C0_table3"], cfg[y]["C1_stations_rank_default"]
        b = booking[y]
        m1 = _num(c1["mass_kt"])
        if m1 is None:
            m1 = 0.5 * (_num(c1["mass_lo_kt"]) + _num(c1["mass_hi_kt"]))
        m0 = _num(c0["mass_kt"])
        mass = m1 / m0
        # THE CALORIFIC TERM IS THE BOOKED ACCOUNT'S EFFECTIVE VALUE, booked energy over
        # booked mass, NOT the blend the configurations product prints. For the five years
        # whose plant masses are all printed the two are the same number. For the four
        # reconstructed years they are not: the configurations blend is computed on the HIGH
        # masses while the booked energy is the MIDPOINT of the interval, so dividing one by
        # the other left the decomposition 1.3 per cent short of its own ratio in FY2016-17.
        # The identity check below caught it rather than the file shipping a product of two
        # terms that is not the ratio it sits beside.
        booked_TJ = _num(b["booked_toe"]) * TOE_TJ
        cal = (booked_TJ / m1) / _num(c0["cv_TJ_per_Gg"])
        ratio = _num(b["booked_toe"]) / _num(b["superseded_toe"])
        # The identity the file rests on: a decomposition that does not reproduce its own
        # ratio is not a decomposition, and a note saying so is not a substitute for raising.
        if abs(mass * cal / ratio - 1.0) > 2e-3:
            raise ValueError(
                "%s: mass x calorific = %.6f but booked/superseded = %.6f - the "
                "decomposition does not reproduce its own ratio" % (period, mass * cal, ratio))
        dominant = ("mass account" if abs(math.log(mass)) > abs(math.log(cal))
                    else "calorific conversion")
        lg = legacy[y]
        grid_booked = _num(lg["reference_Mt"])
        grid_superseded = _num(lg["alternative_Mt"])
        move = _num(lg["delta_Mt"])
        nat = national.get(period)
        rows.append({
            "period_id": period, "fiscal_start_year": y,
            "booked_toe": "%.0f" % _num(b["booked_toe"]),
            "superseded_toe": "%.0f" % _num(b["superseded_toe"]),
            "ratio_booked_to_superseded": "%.3f" % ratio,
            "mass_term": "%.3f" % mass, "calorific_term": "%.3f" % cal,
            "dominant_term": dominant,
            "booked_evidence_grade": b["evidence_grade"],
            "grid_booked_Mt": "" if grid_booked is None else "%.5f" % grid_booked,
            "grid_superseded_Mt": "" if grid_superseded is None else "%.5f" % grid_superseded,
            "grid_move_Mt": "" if move is None else "%+.5f" % (-move),
            "national_booked_Mt": "" if nat is None else "%.5f" % nat,
            "national_superseded_Mt": ("" if (nat is None or move is None)
                                       else "%.5f" % (nat + move)),
            "national_move_Mt": "" if move is None else "%+.5f" % (-move),
            "booked_source": ("the stations' own metered coal (NEPRA SoIR 2018/2020/2023/2024 "
                              "per-station tables, via outputs/"
                              "pakemis_power_fuel_reconciliation.csv) x IPCC 2006 Vol.2 Ch.1 "
                              "Table 1.2 rank default NCV"),
            "superseded_source": b["superseded_source"],
            "note": ("%s dominates: the stations' tonnage is %.3f of HDIP's power column and "
                     "the fleet's rank calorific value is %.3f of Table 3's flat 18.73 TJ/Gg"
                     % (dominant, mass, cal))})
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
    print("Coal re-base ledger -> %s (%d years)" % (OUT, len(rows)))
    print("  %-10s %8s %8s %8s %-22s %12s" % ("period", "ratio", "mass", "cal",
                                              "dominant", "national Mt"))
    for r in rows:
        print("  %-10s %8s %8s %8s %-22s %12s" % (
            r["period_id"], r["ratio_booked_to_superseded"], r["mass_term"],
            r["calorific_term"], r["dominant_term"], r["national_move_Mt"]))


if __name__ == "__main__":
    raise SystemExit(main())

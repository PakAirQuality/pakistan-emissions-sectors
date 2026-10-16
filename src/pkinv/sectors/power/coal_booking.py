"""Book the current station-mass/rank-NCV account, with conditional bounds.

The source transcription is retained. This producer prevents the declared booking
from becoming stale when a commissioning reconstruction changes. Bounds describe
the reconstruction and carry no assigned probability or confidence level.
"""
import argparse

from pkinv.assets import asset_path
from pkinv.core.io import read_rows, write_or_check
from pkinv.paths import DATA

OUT = asset_path(DATA, "activity", "power", "coal_energy_booking.csv")
RANK_OUT = asset_path(DATA, "activity", "power", "coal_rank_account.csv")
RANK_FIELDS = ("fiscal_year", "fuel_rank", "mass_kt", "ncv_TJ_per_Gg", "energy_TJ",
               "energy_share", "ncv_uncert_pct_95", "source", "basis")
FIELDS = ("fiscal_year", "fuel", "booked_toe", "booked_lo_toe", "booked_hi_toe",
          "basis", "mass_account", "superseded_toe", "superseded_source",
          "ratio_to_superseded", "evidence_grade", "note")
TOE_TJ = 0.041868


def station_accounts():
    """Source-derived station rows without reading a booked or reported output.

    This is deliberately usable before canonical materialisation and the power
    sector build. It shares the reconciliation's source reconstruction, not its
    generated CSV or the heat-rate diagnostics.
    """
    from pkinv.sectors.power.fuel_reconciliation import account_rows
    return [r for r in account_rows(include_booking=False, panel_only=False)
            if r["fuel"] == "Coal" and r["plant"] != "(no coal station)" and
            r["plant_coverage_class"] in ("enumerated station", "reconstructed lane")]


def build():
    from collections import defaultdict
    energy = defaultdict(lambda: [0.0, 0.0])
    for row in station_accounts():
        ncv = float(row["ncv_TJ_per_Gg"])
        lo = float(row["mass_kt"] or row["mass_lo_kt"])
        hi = float(row["mass_kt"] or row["mass_hi_kt"])
        year = int(row["period_id"][2:6])
        energy[year][0] += lo * ncv
        energy[year][1] += hi * ncv
    fuel_rows = [r for r in read_rows(asset_path(DATA, "activity", "power", "fuel_consumed.csv"))
                 if r["fuel"] == "Coal"]
    table3 = {int(r["fiscal_year"]): float(r["toe"]) for r in fuel_rows
              if "Table 3" in r.get("source", "")}
    rows = []
    for year in sorted({int(row["fiscal_year"]) for row in fuel_rows}):
        if year not in energy:
            raise ValueError("no current station coal account for FY%d" % year)
        lo, hi = energy[year]
        central = (lo + hi) / 2 / TOE_TJ
        rows.append({
            "fiscal_year": year, "fuel": "Coal", "booked_toe": "%.1f" % central,
            "booked_lo_toe": "%.1f" % (lo / TOE_TJ),
            "booked_hi_toe": "%.1f" % (hi / TOE_TJ),
            "basis": "C1_stations_rank_default", "mass_account": "coal used, as the stations report it",
            "superseded_toe": "%.1f" % table3[year] if year in table3 else "",
            "superseded_source": ("NEPRA SoIR Table 3 'Fuel consumed' (TOE), via data/activity/power/fuel_consumed.csv"
                                  if year in table3 else "not available: no Table 3 national value printed for this year; reconstructed station energy is the reference itself, not an independent prior control"),
            "ratio_to_superseded": "%.6f" % (central / table3[year]) if year in table3 else "",
            "evidence_grade": "reconstructed_interval" if lo != hi else "printed-other-edition" if year < 2015 else "printed",
            "note": ("midpoint of the current station reconstruction; low/high are conditional bounds, not a 95% interval"
                     if lo != hi else "printed station mass times documented fixed rank NCV; equality of bounds does not remove NCV uncertainty")})
    return rows


def rank_account():
    from collections import defaultdict
    acc = defaultdict(float)
    for row in station_accounts():
        try:
            ncv = float(row["ncv_TJ_per_Gg"])
            mass = (float(row["mass_kt"]) if row["mass_kt"] else
                    (float(row["mass_lo_kt"]) + float(row["mass_hi_kt"])) / 2)
        except ValueError:
            continue
        year = int(row["period_id"][2:6])
        acc[(year, "Lignite" if ncv == 11.9 else "Other Bituminous Coal", ncv)] += mass
    totals = defaultdict(float)
    for (year, rank, ncv), mass in acc.items():
        totals[year] += mass * ncv
    return [{"fiscal_year": year, "fuel_rank": rank, "mass_kt": "%.6f" % mass,
             "ncv_TJ_per_Gg": ncv, "energy_TJ": "%.6f" % (mass * ncv),
             "energy_share": "%.12f" % (mass * ncv / totals[year]),
             "ncv_uncert_pct_95": "%.6f" % ((21.6 - 5.5) / (2 * 11.9) * 100 if rank == "Lignite" else 21),
             "source": "IPCC 2006 Vol.2 Ch.1 Table 1.2 rank NCV confidence ranges; station fuel reconciliation",
             "basis": "fixed rank default; conditional parameter width summarises the published NCV range"}
            for (year, rank, ncv), mass in sorted(acc.items()) if totals[year] > 0]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    status = write_or_check(OUT, FIELDS, build(), check=args.check,
                          banner=("# Current station-mass × fixed rank-NCV coal booking; prior Table 3 controls retained.",
                                  "# Reconstruction endpoints are conditional bounds with no assigned probability.",
                                  "# Generated by pkinv.sectors.power.coal_booking."))
    rank_status = write_or_check(RANK_OUT, RANK_FIELDS, rank_account(), check=args.check)
    return status or rank_status


if __name__ == "__main__":
    raise SystemExit(main())

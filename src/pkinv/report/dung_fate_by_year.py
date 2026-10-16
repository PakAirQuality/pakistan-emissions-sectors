"""The diverted dung, year by year: what households burn, what is unresolved, and what each
destination of the unresolved part would be worth.

WHY THIS EXISTS (rc67). Since rc67 the residential reference burns the dung households are
observed burning, in every year of the panel. Agriculture still diverts about five times that
from manure management, on the same burned-fuel shares as before, so in every year most of the
diverted mass, and the nitrogen in it, sits in no emitting account. Through rc66 that residual
was priced for the reference year only, as a footnote to a second configuration. It is now part
of what the reference leaves out, and a reader of any year needs to see it.

ONE ROW PER FISCAL YEAR AND DESTINATION. The masses and the nitrogen are the same on every row
of a year; what differs is where the unresolved part is taken to go:

  S_household_only_unallocated        nowhere: a declared stock, no emission. THE REFERENCE.
  S_residual_nonhousehold_combustion  burned by non-household users on the same fuel chain.
                                      This is configuration L by another name.
  S_residual_return_to_manure         never left manure management: agriculture RE-RUN for that
                                      year with the diversion reduced to what the survey
                                      supports, so volatile solids and nitrogen move together.
  S_residual_field_application        applied to fields: soils re-run with the residual nitrogen
                                      added to organic amendments.
  S_revised_diversion_fraction        the same recomputation as the return to manure, read as a
                                      correction of the diversion assumption.

NO PROBABILITIES. Conservation says the mass exists. It does not say where it went, and nothing
held observes a destination. The reference takes the first row because it asserts nothing; the
other rows bound what an assertion would cost.

THE CHECKS ARE IN THE BUILD. Household + destination + unresolved = diverted on every row, in
mass and in nitrogen; the reference row's total is the national series' own total for that
year; and at the reference year every row reproduces national_dung_variants.csv.

COMPARATOR ONLY. Nothing here enters a total, a factor or an allocation.

Usage:  python3 -m pkinv.report.dung_fate_by_year
Writes: outputs/pakemis_dung_fate_by_year.csv
"""
import csv
import os

from pkinv.assets import asset_path
from pkinv.core.io import write_table
from pkinv.core.reporting_window import REFERENCE_PERIOD
from pkinv.paths import DATA, OUTPUTS

OUT = os.path.join(OUTPUTS, "pakemis_dung_fate_by_year.csv")
SERIES = os.path.join(OUTPUTS, "pakemis_national_series.csv")
REFERENCE_YEAR_FILE = os.path.join(OUTPUTS, "national_dung_variants.csv")
PERIODS = asset_path(DATA, "periods.csv")
TOLERANCE_MT = 0.0002
REFERENCE_VARIANT = "S_household_only_unallocated"

FIELDS = ("period_id", "variant_id", "is_reference", "destination", "diverted_Mt",
          "household_Mt", "destination_Mt", "unresolved_Mt", "diverted_N_kt",
          "household_N_kt", "destination_N_kt", "unresolved_N_kt", "household_basis",
          "ch4_Gg", "n2o_Gg", "biogenic_co2_memo_Gg", "delta_Mt_co2e_AR5",
          "reference_national_Mt_co2e_AR5", "national_total_Mt_co2e_AR5")


def _rows(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


def _series_totals():
    return {int(r["fiscal_end_year"]): float(r["co2e_Mt_AR5"]) for r in _rows(SERIES)
            if r["row_kind"] == "covered_total"}


def build():
    # imported at call time: the report layer loads no sector module on import
    from pkinv.report import dung_variants
    from pkinv.sectors.residential import timeseries
    totals = _series_totals()
    periods = sorted((int(r["fiscal_end_year"]), r["period_id"]) for r in _rows(PERIODS))
    rows, problems = [], []
    for year, period_id in periods:
        if year not in totals:
            problems.append("%s: the national series has no total" % period_id)
            continue
        priced = dung_variants.price(year)
        for variant_id, v in priced["variants"].items():
            share = (v["destination_Mt"] / priced["diverted_Mt"]
                     if priced["diverted_Mt"] else 0.0)
            destination_n = priced["diverted_N_kt"] * share
            unresolved_n = priced["unresolved_N_kt"] - destination_n
            mass_gap = (priced["household_Mt"] + v["destination_Mt"] + v["unresolved_Mt"]
                        - priced["diverted_Mt"])
            n_gap = (priced["household_N_kt"] + destination_n + unresolved_n
                     - priced["diverted_N_kt"])
            if abs(mass_gap) > TOLERANCE_MT or abs(n_gap) > 1e-6:
                problems.append("%s %s does not conserve: mass %.6f Mt, nitrogen %.6f kt"
                                % (period_id, variant_id, mass_gap, n_gap))
            rows.append({
                "period_id": period_id, "variant_id": variant_id,
                "is_reference": "yes" if variant_id == REFERENCE_VARIANT else "no",
                "destination": v["destination"],
                "diverted_Mt": "%.4f" % priced["diverted_Mt"],
                "household_Mt": "%.4f" % priced["household_Mt"],
                "destination_Mt": "%.4f" % v["destination_Mt"],
                "unresolved_Mt": "%.4f" % v["unresolved_Mt"],
                "diverted_N_kt": "%.3f" % priced["diverted_N_kt"],
                "household_N_kt": "%.3f" % priced["household_N_kt"],
                "destination_N_kt": "%.3f" % destination_n,
                "unresolved_N_kt": "%.3f" % (unresolved_n + 0.0 if abs(unresolved_n) >= 5e-4
                                             else 0.0),
                "household_basis": timeseries.dung_survey_basis(year),
                "ch4_Gg": "%.4f" % v["ch4_Gg"], "n2o_Gg": "%.4f" % v["n2o_Gg"],
                "biogenic_co2_memo_Gg": "%.2f" % v["biogenic_co2_memo_Gg"],
                "delta_Mt_co2e_AR5": "%.4f" % v["delta"],
                "reference_national_Mt_co2e_AR5": "%.5f" % totals[year],
                "national_total_Mt_co2e_AR5": "%.5f" % (totals[year] + v["delta"])})

    # the reference year must be the reference-year file, row for row
    shipped = {r["variant_id"]: r for r in _rows(REFERENCE_YEAR_FILE)}
    for r in rows:
        if r["period_id"] != REFERENCE_PERIOD:
            continue
        other = shipped.get(r["variant_id"])
        if other is None or abs(float(other["national_total_Mt_co2e_AR5"])
                                - float(r["national_total_Mt_co2e_AR5"])) > 2e-5:
            problems.append("%s %s: %s here, %s in national_dung_variants.csv"
                            % (REFERENCE_PERIOD, r["variant_id"], r["national_total_Mt_co2e_AR5"],
                               other and other["national_total_Mt_co2e_AR5"]))
    if problems:
        raise SystemExit("the dung fate account does not close:\n  " + "\n  ".join(problems))
    return rows


def main():
    rows = build()
    write_table(OUT, FIELDS, rows, banner=(
        "# The dung agriculture diverts from manure management, by fiscal year: what the",
        "# household survey has households burning (the reference since rc67), what is left",
        "# with no observed destination, in mass and in nitrogen, and the change in the",
        "# national total if the unresolved part went to each candidate destination. The",
        "# reference row (is_reference = yes) applies no emission to it. No probabilities.",
        "# pkinv.report.dung_fate_by_year. COMPARATOR ONLY.",))
    last = [r for r in rows if r["period_id"] == rows[-1]["period_id"]]
    spread = max(float(r["delta_Mt_co2e_AR5"]) for r in last)
    print("dung fate by year: %d rows, %d periods; %s unresolved %s Mt (%s kt N), "
          "destinations worth up to +%.3f Mt CO2e"
          % (len(rows), len({r["period_id"] for r in rows}), last[0]["period_id"],
             last[0]["unresolved_Mt"], last[0]["unresolved_N_kt"], spread))


if __name__ == "__main__":
    main()

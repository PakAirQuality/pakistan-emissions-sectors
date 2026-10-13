"""Grid power by province, fuel and year: what was booked before, what is booked now, and why.

WHY THIS EXISTS. Through rc65 each grid fuel carried one provincial share vector, measured on
FY2023-24, and coal and gas rode it in all nine fiscal years. At rc66 every fuel-year takes
its own stations (pkinv.sectors.power.province_panel). That is a re-base of provincial and
district numbers and of nothing else, and a re-base is only as good as the reader's ability to
see what moved. This product is that view: one row per fuel, fiscal year and province.

WHAT EACH ROW SAYS.
  co2e_Mt_AR5_before   the province's emissions of this fuel in release 1.0.0rc65
                       (data/baselines/pre_rc66_power_provincial/, pinned by digest)
  co2e_Mt_AR5_after    the same in this release (outputs/pakemis_adm1_by_year.csv)
  difference_Mt_CO2e   after minus before. Positive: the province is booked more now.
  share_before/after   each as a fraction of the fuel's national total that year
  basis                what the applied split rests on: station fuel quantities, booked coal
                       energy, generation, or the reference-year vector
  coverage             station energy over the national control the fuel is booked from
  fallback_reason      non-empty exactly where the reference vector is still applied

EVERY QUANTITY IS EMISSIONS, in Mt CO2e on the AR5 basis, all three gases of the fuel summed.
The comparator this replaces (pakemis_power_fixed_pattern_exposure.csv) had a header that said
"the coal mass the fixed vector books" over a column in Mt CO2e, and a reader of the manuscript
could not tell which was meant.

THE CONSERVATION CHECK IS IN THE BUILD. For every fuel and year the provinces must sum to the
same national total before and after, to 1e-6 Mt. If they do not, the split has changed a
total, which it has no right to do, and this module raises instead of writing.

COMPARATOR ONLY. Nothing here enters a total, a factor or an allocation.

Usage:  python3 -m pkinv.report.power_provincial_basis
Writes: outputs/pakemis_power_provincial_basis_by_year.csv
"""
import collections
import csv
import os

from pkinv.assets import asset_path
from pkinv.core.geography import PROVINCES
from pkinv.core.io import write_table
from pkinv.paths import DATA, OUTPUTS, ROOT

BASELINE = os.path.join(ROOT, "data", "baselines", "pre_rc66_power_provincial",
                        "pakemis_adm1_by_year_power.csv")
ADM1 = os.path.join(OUTPUTS, "pakemis_adm1_by_year.csv")
PERIODS = asset_path(DATA, "periods.csv")
OUT = os.path.join(OUTPUTS, "pakemis_power_provincial_basis_by_year.csv")

# sub_category prefix in the ADM1 product -> the panel's stream
STREAM_OF = {"Coal": "power_coal", "Gas": "power_gas", "Furnace Oil": "power_rfo",
             "Diesel Oil": "power_hsd", "Bagasse": "bagasse_grid"}
FUEL_LABEL = {"power_coal": "coal", "power_gas": "gas and RLNG", "power_rfo": "furnace oil",
              "power_hsd": "diesel", "bagasse_grid": "bagasse (CH4 and N2O)"}
BASIS_CLASS = ("own_year_fuel_quantity", "own_year_booked_energy", "own_year_generation",
               "reference_year_row", "reference_vector_fallback", "not_applicable")
TOLERANCE_MT = 1e-6

FIELDS = ("period_id", "stream", "fuel", "province", "co2e_Mt_AR5_before",
          "co2e_Mt_AR5_after", "difference_Mt_CO2e", "share_before", "share_after",
          "national_co2e_Mt_AR5", "basis_class", "basis", "coverage_of_national_control",
          "stations", "generation_derived_share", "fallback_reason", "flags")


def _mass(path):
    """{(period, stream): {province: Mt CO2e AR5}} for the grid fuels, gases summed."""
    out = collections.defaultdict(lambda: collections.defaultdict(float))
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(line for line in handle if not line.startswith("#")):
            if row["module"] != "power":
                continue
            fuel = row["sub_category"].rsplit(" ", 1)[0]
            stream = STREAM_OF.get(fuel)
            if stream is None:
                continue                                  # captive gas: already per year
            out[(row["period_id"], stream)][row["province"]] += float(row["co2e_Mt_AR5"])
    return out


STREAMS = ("power_coal", "power_gas", "power_rfo", "power_hsd", "bagasse_grid")


def _panel():
    # imported at call time: the report layer imports no sector module when it is imported
    # (tests/test_sector_contract.py), so a report can be read without loading an engine
    from pkinv.sectors.power import province_panel
    assert province_panel.STREAMS == STREAMS, "the panel's stream list moved"
    return province_panel


def basis_class(stream, year, found):
    province_panel = _panel()
    if found["shares"] is None:
        return "not_applicable"
    if year == province_panel.REFERENCE_YEAR:
        return "reference_year_row"
    if found["fallback"]:
        return "reference_vector_fallback"
    if stream == "power_coal":
        return "own_year_booked_energy"
    if stream == "bagasse_grid" or found["derived_share"] > 0.999:
        return "own_year_generation"
    return "own_year_fuel_quantity"


def build():
    province_panel = _panel()
    before, after = _mass(BASELINE), _mass(ADM1)
    with open(PERIODS, encoding="utf-8", newline="") as handle:
        periods = [(r["period_id"], int(r["fiscal_start_year"])) for r in csv.DictReader(handle)]
    rows, problems = [], []
    for period_id, year in sorted(periods):
        for stream in province_panel.STREAMS:
            old, new = before.get((period_id, stream), {}), after.get((period_id, stream), {})
            total_old, total_new = sum(old.values()), sum(new.values())
            if abs(total_old - total_new) > TOLERANCE_MT:
                problems.append("%s %s: national %.6f Mt before, %.6f after"
                                % (period_id, stream, total_old, total_new))
            if total_new <= 0 and total_old <= 0:
                continue
            found = province_panel.record(stream, year)
            for province in PROVINCES:
                a, b = old.get(province, 0.0), new.get(province, 0.0)
                rows.append({
                    "period_id": period_id, "stream": stream, "fuel": FUEL_LABEL[stream],
                    "province": province,
                    "co2e_Mt_AR5_before": "%.6f" % a, "co2e_Mt_AR5_after": "%.6f" % b,
                    "difference_Mt_CO2e": "%.6f" % (b - a),
                    "share_before": "%.6f" % (a / total_old if total_old else 0.0),
                    "share_after": "%.6f" % (b / total_new if total_new else 0.0),
                    "national_co2e_Mt_AR5": "%.6f" % total_new,
                    "basis_class": basis_class(stream, year, found),
                    "basis": found["basis"],
                    "coverage_of_national_control":
                        "" if found["coverage"] is None else "%.4f" % found["coverage"],
                    "stations": found["stations"],
                    "generation_derived_share": "%.4f" % found["derived_share"],
                    "fallback_reason": found["fallback"],
                    "flags": "; ".join(found["flags"])})
    if problems:
        raise SystemExit("the provincial split changed a national total, which it may not:\n  "
                         + "\n  ".join(problems))
    return rows


def main():
    rows = build()
    write_table(OUT, FIELDS, rows, banner=(
        "# Grid power by fuel, fiscal year and province: emissions before (release 1.0.0rc65,",
        "# one reference-year provincial vector per fuel) and after (each year's own stations).",
        "# Every quantity is Mt CO2e on the AR5 basis, the fuel's three gases summed. The",
        "# national total of each fuel-year is the same before and after; the build refuses to",
        "# write otherwise. pkinv.report.power_provincial_basis. COMPARATOR ONLY.",))
    worst = max(rows, key=lambda r: abs(float(r["difference_Mt_CO2e"])))
    borrowed = sorted({(r["period_id"], r["fuel"]) for r in rows
                       if r["basis_class"] == "reference_vector_fallback"})
    print("power provincial basis: %d rows; largest movement %s Mt CO2e (%s, %s, %s); "
          "%d fuel-years still on the reference vector"
          % (len(rows), worst["difference_Mt_CO2e"], worst["period_id"], worst["fuel"],
             worst["province"], len(borrowed)))
    for period_id, fuel in borrowed:
        print("  borrowed: %s %s" % (period_id, fuel))


if __name__ == "__main__":
    main()

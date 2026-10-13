"""The flat-profile crosswalk: one table joining the two true flat-share statements.

WHY THIS EXISTS. The release publishes two figures about flat months over the same
nine-year monthly mass, and the sixteenth review read them as an unreconciled pair:
about three fifths of the mass sits on a TE4 profile (pakemis_monthly_coverage_summary.csv,
month x sector x category grain; the live figure is that file's), while the physical
decomposition says 43.4 percent is
correctly flat (continuous or stock-driven) and the variable-but-unobserved remainder
(the Pass-2 metric; the current figure lives in the shipped crosswalk, not this prose)
(pakemis_temporal_decomposition.csv, sector-component grain). Both are true; they are
different CLASSIFICATIONS - one grades the evidence behind each month, the other judges
whether flatness is the right physics for each stream - and the bridge between them was
derivable from the shipped outputs but published nowhere. This module publishes it.

THE BRIDGE, in one paragraph. At the component grain every stream's mass falls into
exactly one of three buckets: flat_physically_appropriate (the decomposition says a flat
- properly days-weighted - profile is the correct answer; enteric fermentation is the
canonical case), variable_timed (the stream should vary and an observed or modeled
series carries it), and variable_unobserved (it should vary and nothing does - the
Pass-2 metric). Crossing those buckets with each month-row's OWN TE grade shows where
the two headline numbers come from and why they cannot be added to each other: TE4
contains both appropriate flatness and unobserved variability, and the appropriate
bucket contains both TE4 and the stock-driven TE3.

THE GRAIN (rc42, the twentieth review's T-1). Until rc41 this table joined each
component's DOMINANT TE grade (temporal_decomposition's most_common) to its buckets, so a
component 60 percent TE4 by mass was filed wholly under TE4 - which put 159.6 Mt of
"variable_unobserved" mass under TE2/TE3 and 246.2 Mt of "variable_timed" under TE4,
cells that are impossible by the definitions above, and left a -2.32 percent "grain
difference" against the coverage summary. The join is at the atom now: every row of the
108-month product carries its own grade, the bucket follows the component's physics and
that row's grade, and the coverage summary's TE4 is reproduced exactly. The
grain_difference row is kept and reads zero; a non-zero value there is a defect.

Usage:  python3 -m pkinv.report.flatness_crosswalk
Writes: outputs/pakemis_flatness_crosswalk.csv
"""

from pkinv.assets import asset_path
import collections
import csv
import os

from pkinv.paths import OUTPUTS
from pkinv.activity.store import read_rows

DECOMPOSITION = asset_path(OUTPUTS, "pakemis_temporal_decomposition.csv")
COVERAGE_SUMMARY = asset_path(OUTPUTS, "pakemis_monthly_coverage_summary.csv")
OUT = asset_path(OUTPUTS, "pakemis_flatness_crosswalk.csv")

FIELDS = ("row_kind", "te_class", "flatness_bucket", "co2e_Mt_AR5",
          "share_of_monthly_mass_pct", "note")

# The residue a decomposition component may carry between its total and
# observed+unobserved: the file rounds to five decimals, so three rounded columns can
# disagree by 1e-5 each; the bucket check above allows that per component.
ROUNDING = 3e-5


def _rows(path):
    return read_rows(path)


def bucket(row):
    if row["flatness_physically_appropriate"] == "yes":
        return "flat_physically_appropriate"
    if float(row["unobserved_Mt_AR5"]) > 0 and float(row["observed_Mt_AR5"]) > 0:
        return "variable_split"          # resolved into the two real buckets below
    if float(row["unobserved_Mt_AR5"]) > 0:
        return "variable_unobserved"
    return "variable_timed"


def build():
    from pkinv.report import temporal_decomposition as td
    # rc42 (T-1): the atom grain. Each month-row of the nine-year product is bucketed by
    # its component's physics (the decomposition's classification, reused - not
    # re-declared here) and its OWN temporal_evidence_class; nothing is summarised to a
    # dominant grade first.
    cells = collections.defaultdict(float)
    total = 0.0
    for row in td._monthly_rows():
        sector = row["sector_id"]
        physics = td._classify(sector, td.grain_of(row))[0]
        te = row["temporal_evidence_class"]
        mass = float(row["co2e_Mt_AR5"])
        total += mass
        if physics in (td.CONTINUOUS, td.STOCK):
            cells[(te, "flat_physically_appropriate")] += mass
        elif te == td.FLAT_GRADE:
            cells[(te, "variable_unobserved")] += mass
        else:
            cells[(te, "variable_timed")] += mass

    # The decomposition partitions the same mass at the component grain; the bucket
    # totals must agree with it to rounding, or one of the two products has drifted.
    decomposition = _rows(DECOMPOSITION)
    checks = {
        "flat_physically_appropriate": sum(float(r["co2e_Mt_AR5"]) for r in decomposition
                                           if r["flatness_physically_appropriate"] == "yes"),
        "variable_timed": sum(float(r["observed_Mt_AR5"]) for r in decomposition),
        "variable_unobserved": sum(float(r["unobserved_Mt_AR5"]) for r in decomposition),
    }
    for name, expected in checks.items():
        got = sum(m for (_te, b), m in cells.items() if b == name)
        if abs(got - expected) > ROUNDING * max(1, len(decomposition)):
            raise ValueError("%s: atom-grain %.5f != decomposition %.5f - the two products "
                             "no longer partition the same mass and this crosswalk must "
                             "not paper over it" % (name, got, expected))

    out = []
    for (te, name), mass in sorted(cells.items()):
        out.append({"row_kind": "cell", "te_class": te, "flatness_bucket": name,
                    "co2e_Mt_AR5": round(mass, 3),
                    "share_of_monthly_mass_pct": round(100 * mass / total, 2),
                    "note": ""})

    # the two decomposition headlines, as column sums a reader can re-add
    for name, note in (
            ("flat_physically_appropriate",
             "the 'correctly flat' headline: flat (days-weighted) is the physical "
             "answer and a monthly series would not change the shape"),
            ("variable_timed",
             "should vary and an observed or modeled series carries it (the "
             "decomposition's 'observed' column)"),
            ("variable_unobserved",
             "should vary, nothing observes it - the Pass-2 reduction target")):
        mass = sum(m for (te, b), m in cells.items() if b == name)
        out.append({"row_kind": "bucket_total", "te_class": "any",
                    "flatness_bucket": name, "co2e_Mt_AR5": round(mass, 3),
                    "share_of_monthly_mass_pct": round(100 * mass / total, 2),
                    "note": note})

    # the TE4 total at this grain, and the grain difference against the coverage summary
    te4 = sum(m for (te, b), m in cells.items() if te == "TE4")
    out.append({"row_kind": "te_total", "te_class": "TE4", "flatness_bucket": "any",
                "co2e_Mt_AR5": round(te4, 3),
                "share_of_monthly_mass_pct": round(100 * te4 / total, 2),
                "note": "TE4 at the atom (month-row) grain, equal to the coverage "
                        "summary's: contains BOTH physically appropriate flatness and "
                        "unobserved variability, which is why the flat share and the "
                        "correctly-flat share are different statements"})
    summary = _rows(COVERAGE_SUMMARY)
    coverage_total = sum(float(r["co2e_Mt_AR5"]) for r in summary)
    coverage_te4 = sum(float(r["TE4_Mt"]) for r in summary)
    out.append({"row_kind": "grain_difference", "te_class": "TE4",
                "flatness_bucket": "any",
                "co2e_Mt_AR5": round(coverage_te4 - te4, 3),
                "share_of_monthly_mass_pct":
                    round(100 * (coverage_te4 - te4) / coverage_total, 2),
                "note": "coverage-summary TE4 (month x sector x category grain, the "
                        "published %.2f%%) minus this table's TE4: zero since rc42, when "
                        "the join moved to the atom grain; a non-zero value here is a "
                        "defect" % (100 * coverage_te4 / coverage_total)})
    return out, total


def main():
    rows, total = build()
    os.makedirs(OUTPUTS, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        handle.write("# The crosswalk between the TE-class flat share and the physical "
                     "flatness decomposition,\n# over the same %.3f Mt of nine-year "
                     "monthly mass. See pkinv/report/flatness_crosswalk.py.\n" % total)
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print("flatness crosswalk -> %s" % OUT)
    for row in rows:
        if row["row_kind"] != "cell":
            print("  %-18s %-4s %-28s %8.1f Mt  %5.1f%%"
                  % (row["row_kind"], row["te_class"], row["flatness_bucket"],
                     row["co2e_Mt_AR5"], row["share_of_monthly_mass_pct"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

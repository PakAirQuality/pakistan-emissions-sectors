"""The Year Book against itself: summary total versus locomotive/non-locomotive detail.

WHAT THIS SETTLES. This sector used to record that workshop, stationary-plant and track-machine
fuel sits inside the traction figure and cannot be split out of it. That was a claim about the
source, and the source refutes it: the same edition carries a detailed fuel table on p.163
giving locomotive and other-than-locomotive consumption separately, for diesel and for furnace
oil, back to 1950. The split was one page away in a document this sector already reads.

Non-traction diesel is 1,599 thousand litres in FY2023-24 - about 1.2 percent of the total. The
non-traction overlap this sector has always declared - fuel that belongs outside 1A3c, in
stationary and off-road categories by source, not as a single block in 1A4c ii - is now
measured rather than asserted.

THE ONE DISAGREEMENT THIS CHECK EVER FOUND, AND HOW THE SOURCE ITSELF SETTLED IT. The
2023-24 edition's two tables disagreed about FY2023-24: the detail printed locomotive
diesel as "136.988" - a decimal point where every other row uses a comma, so the cell
already carried a typesetting anomaly - making the detail sum 138,587 against the summary's
twice-stated 132,588, a 4.52 percent gap and the only failure across every year both tables
cover. This sector kept reporting the summary (stated twice against once) and published the
detail reading as a labelled sensitivity, 0.412 against 0.394 Mt.

The 2024-25 edition resolved it. Its historical run restates the cell as 130,988 (printed
"130.988" - the same decimal-point quirk on the same row), and 130,988 + 1,599 = 132,587,
within one part in 132,588 of the summary. The misprint hypothesis was right, the summary
was right, and the reported number never moved. The current table:

    FY        summary      locomotive + other = detail       gap
    2015-16   139,487      137,908 +  1,579   = 139,487      0
    2016-17   144,631      142,607 +  2,024   = 144,631      0
    2017-18   156,396      154,357 +  2,039   = 156,396      0
    2018-19   159,927      157,979 +  1,948   = 159,927      0
    2019-20   139,600      137,969 +  1,630   = 139,599     -1
    2020-21   140,257      138,841 +  1,416   = 140,257      0
    2021-22   142,086      140,482 +  1,601   = 142,083     -3
    2022-23   104,909      103,272 +  1,637   = 104,909      0
    2023-24   132,588      130,988 +  1,599   = 132,587     -1   (restated by 2024-25)
    2024-25   138,673      137,096 +  1,577   = 138,673      0   (provisional)

All ten years both tables cover now reconcile - eight to the digit, two to within three
parts in 140,000 - which establishes that the summary IS defined as locomotive plus other
and that the two tables are meant to agree.

(FY2017-18 and FY2018-19 appear here at all only because this same table supplied them: both
were absent from the series until the 2020-21 edition's historical run was read. See
data/activity/railways/fuel_consumption.csv.)

WHY THIS MATTERED MORE THAN 4.5 PERCENT OF A 0.4 Mt SECTOR. This paper's argument is that a
national submission can be refuted on a fuel account. An inventory making that argument has
to hold its own fuel account to the standard it is applying, and this sector once had not:
it read one table, never checked it against the other in the same document, and described
the split it did not attempt as impossible. The check now runs on every build, it caught a
real misprint in a national statistical publication before the publisher corrected it, and
the correction went the way the evidence pointed.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import DATA

_FILE = asset_path(DATA, "activity", "railways", "fuel_detail.csv")
ITEM = "Gas/Diesel Oil"


def _num(s):
    s = (s or "").strip()
    return None if s == "" else float(s)


def load_detail(path=_FILE):
    """[{fiscal_year, fuel, locomotive, other_than_locomotive, unit, ...}]."""
    rows = list(_activity_rows(path, comments=False))
    for r in rows:
        r["fiscal_year"] = int(r["fiscal_year"])
        r["locomotive"] = _num(r["locomotive"])
        r["other_than_locomotive"] = _num(r["other_than_locomotive"])
    return rows


def detail_for(year, fuel=ITEM, path=_FILE):
    for r in load_detail(path):
        if r["fiscal_year"] == year and r["fuel"] == fuel:
            return r
    return None


def non_traction_share(data, year=None, path=_FILE):
    """Fraction of diesel that is NOT locomotive fuel, from the detail table.

    This is the quantity the stationary/off-road crosswalk wants and that this sector used
    to call unobtainable. It is
    taken as a share rather than a volume so that it is meaningful whichever of the two
    disputed FY2023-24 totals turns out to be right.
    """
    year = data.year if year is None else year
    d = detail_for(year, path=path)
    if d is None:
        return None
    total = d["locomotive"] + d["other_than_locomotive"]
    return d["other_than_locomotive"] / total if total else None


def reconciliation(data, path=_FILE):
    """[{fiscal_year, summary, locomotive, other, detail_total, diff, pct}] over every year
    both tables cover. The evidence, published rather than summarised."""
    out = []
    for d in load_detail(path):
        if d["fuel"] != ITEM:
            continue
        y = d["fiscal_year"]
        try:
            summary = data.quantity(ITEM, y)
        except KeyError:
            continue
        total = d["locomotive"] + d["other_than_locomotive"]
        out.append({"fiscal_year": y, "summary": summary,
                    "locomotive": d["locomotive"], "other": d["other_than_locomotive"],
                    "detail_total": total, "diff": total - summary,
                    "pct": 100.0 * (total - summary) / summary if summary else None})
    return sorted(out, key=lambda r: r["fiscal_year"])


def disagreeing_years(data, tol_pct=0.1, path=_FILE):
    """Years where the two tables differ by more than a rounding step."""
    return [r for r in reconciliation(data, path)
            if r["pct"] is not None and abs(r["pct"]) > tol_pct]

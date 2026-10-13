"""Check the temperature series the residential profile rides against an independent reanalysis.

WHAT IS ON TEST. `data/activity/residential/monthly_degree_days.csv` carries NASA POWER's
monthly T2M at five city points, and the residential monthly layer - 256.8 Mt across the
nine-year product, class TE3 - is built from the heating and cooling degree days derived from
it. Nothing had ever checked that series against anything.

WHAT IT IS CHECKED AGAINST. ERA5, held on the maintainer's external volume as a 0.1 degree
daily Pakistan grid. ERA5 and NASA POWER's MERRA-2 are separate reanalyses built by different
institutions from different assimilation systems, so this is a genuinely independent
measurement rather than two views of one product - which is why the registry row claims LARGE
independence, a claim most rows in that file cannot make.

WHAT IT ACTUALLY VALIDATED, WHICH IS NOT WHAT IT SET OUT TO. The two series agree on SHAPE
almost exactly - the monthly correlation is 0.97 to 0.99 at all five cities - and disagree on
LEVEL by a systematic 3.2 to 6.1 C, ERA5 colder, in every month of every city.

That offset is definitional rather than a disagreement. One day on the volume holds exactly one
row per grid cell, so its `t2m` is a single daily value and not a mean of twenty-four hours,
and the files carry NO metadata saying which value it is - no units, no aggregation, nothing. A
fixed pre-dawn synoptic hour would be systematically colder and would damp the inland seasonal
amplitude, which is what the numbers show.

THE CONSEQUENCE, and it is the finding. Degree days are a function of LEVEL:
HDD18 = max(0, 18 - T). A five-degree offset would roughly double them. So this subset CANNOT
validate the degree-day series the residential layer is built from; it validates the TIMING of
the temperature signal and nothing else. Saying so is worth more than the clean pass this was
expected to be.

WHAT IT IS NOT, and the limit is on every row. ERA5 is held here from January 2020, so the
overlap is 54 of the inventory's 108 months. Agreement bounds the period it covers and says
nothing whatever about 2015 to 2019. It is also a CHECK and not a source: no profile changes,
nothing is copied off the volume, and the residential layer keeps reading NASA POWER.

TWO UNITS AND ONE TRAP. ERA5 publishes `t2m` in KELVIN and the degree-day file is in Celsius.
A comparison that forgot the 273.15 would report a catastrophic disagreement and look like a
finding; one that applied it twice would report a suspiciously perfect one.

THE GRID IS SAMPLED AT A FIXED CELL, VERIFIED. The nearest cell to each city is resolved once
from the first day read and then re-checked against a later file, because a grid that shifted
between files would silently sample a different place while still returning plausible numbers.

Usage:  python3 scripts/crosscheck_era5_degree_days.py
Writes: outputs/era5_degree_day_crosscheck.csv
Skips cleanly, with a message and exit 0, when the volume is not mounted - CI has no SSD and
the committed output is what the tests read.
"""

from pkinv.assets import asset_path
import collections
import csv
import glob
import os
import re
import sys

from pkinv.paths import DATA, OUTPUTS
from pkinv.core.io import read_rows

MET = "/Volumes/Extreme SSD/grid/pakistan/met"
DEGREE_DAYS = asset_path(DATA, "activity", "residential", "monthly_degree_days.csv")
OUT = asset_path(OUTPUTS, "era5_degree_day_crosscheck.csv")

KELVIN = 273.15
# The window this inventory reports, intersected with what the volume holds.
FIRST_MONTH, LAST_MONTH = "202001", "202406"

FIELDS = ("month", "province", "city", "lat", "lon", "era5_cell_lat", "era5_cell_lon",
          "era5_days", "era5_t2m_C", "nasa_power_t2m_C", "delta_C", "abs_delta_C",
          "validates")

# What a row is evidence of, written on the row so it cannot be read as more than it is.
VALIDATES = "seasonal-timing-only: the level differs by an undocumented aggregation"


def _rows(path):
    return read_rows(path)


def city_points():
    """{(province, city): (lat, lon)} from the degree-day file's OWN source string.

    Parsed rather than retyped. The coordinate is what that file declares it sampled, so a
    hand-copied pair here could disagree with it and the comparison would quietly be against
    a different place.
    """
    out = {}
    for row in _rows(DEGREE_DAYS):
        match = re.search(r"point\s*([-\d.]+),\s*([-\d.]+)", row["source"])
        if match:
            out[(row["province"], row["city"])] = (float(match.group(1)),
                                                   float(match.group(2)))
    return out


def nasa_power():
    """{(city, month): t2m in Celsius} for the months inside the overlap."""
    out = {}
    for row in _rows(DEGREE_DAYS):
        if FIRST_MONTH <= row["month"] <= LAST_MONTH:
            out[(row["city"], row["month"])] = float(row["t2m_C"])
    return out


def _read_day(path):
    import pyarrow.parquet as pq
    # ParquetFile, not read_table: the files carry their own `date` column AND sit under a
    # date= partition directory, and the dataset reader refuses to merge the two types.
    return pq.ParquetFile(path).read(columns=["lat", "lon", "t2m"])


def nearest_cells(table, points):
    """{(province, city): (index, cell_lat, cell_lon)} - resolved once, checked later."""
    lats = table.column("lat").to_pylist()
    lons = table.column("lon").to_pylist()
    out = {}
    for key, (lat, lon) in points.items():
        best, best_d = None, None
        for index, (cell_lat, cell_lon) in enumerate(zip(lats, lons)):
            distance = (cell_lat - lat) ** 2 + (cell_lon - lon) ** 2
            if best_d is None or distance < best_d:
                best, best_d = index, distance
        out[key] = (best, lats[best], lons[best])
    return out


def days_in_window():
    return sorted(path for path in glob.glob(asset_path(MET, "date=*"))
                  if FIRST_MONTH <= os.path.basename(path)[5:].replace("-", "")[:6]
                  <= LAST_MONTH)


def build():
    points = city_points()
    if not points:
        raise ValueError("no city coordinates could be parsed from %s" % DEGREE_DAYS)

    directories = days_in_window()
    if not directories:
        raise ValueError("no ERA5 day directories inside %s..%s" % (FIRST_MONTH, LAST_MONTH))

    first = asset_path(directories[0], "part-000.parquet")
    cells = nearest_cells(_read_day(first), points)

    # THE GRID CHECK. Re-resolve on the last day and require the same cell coordinates; a grid
    # that moved would keep returning plausible temperatures for the wrong place.
    last = asset_path(directories[-1], "part-000.parquet")
    recheck = nearest_cells(_read_day(last), points)
    for key, (_index, lat, lon) in cells.items():
        _other_index, other_lat, other_lon = recheck[key]
        if abs(lat - other_lat) > 1e-9 or abs(lon - other_lon) > 1e-9:
            raise ValueError(
                "the ERA5 grid moved between %s and %s for %s: (%.4f, %.4f) vs (%.4f, %.4f)"
                % (directories[0], directories[-1], key, lat, lon, other_lat, other_lon))

    totals = collections.defaultdict(lambda: [0.0, 0])
    for directory in directories:
        path = asset_path(directory, "part-000.parquet")
        if not os.path.exists(path):
            continue
        month = os.path.basename(directory)[5:].replace("-", "")[:6]
        column = _read_day(path).column("t2m")
        for key, (index, _lat, _lon) in cells.items():
            value = column[index].as_py()
            if value is None:
                continue
            bucket = totals[(key, month)]
            bucket[0] += value
            bucket[1] += 1

    power = nasa_power()
    rows = []
    for ((province, city), month), (total, days) in sorted(totals.items()):
        if not days:
            continue
        era5 = total / days - KELVIN
        theirs = power.get((city, month))
        if theirs is None:
            continue
        _index, cell_lat, cell_lon = cells[(province, city)]
        lat, lon = points[(province, city)]
        rows.append({
            "month": month, "province": province, "city": city,
            "lat": lat, "lon": lon,
            "era5_cell_lat": round(cell_lat, 4), "era5_cell_lon": round(cell_lon, 4),
            "era5_days": days,
            "era5_t2m_C": round(era5, 3),
            "nasa_power_t2m_C": round(theirs, 3),
            "delta_C": round(era5 - theirs, 3),
            "abs_delta_C": round(abs(era5 - theirs), 3),
            "validates": VALIDATES,
        })
    return rows


def by_city_series(rows):
    """{city: [(month, era5, nasa_power)]} in month order."""
    out = collections.defaultdict(list)
    for row in rows:
        out[row["city"]].append((row["month"], row["era5_t2m_C"], row["nasa_power_t2m_C"]))
    return {city: sorted(values) for city, values in out.items()}


def correlation(series):
    """Pearson r of the two monthly series - what agrees, as opposed to what does not."""
    ours = [value for _m, value, _t in series]
    theirs = [value for _m, _e, value in series]
    mean_ours = sum(ours) / len(ours)
    mean_theirs = sum(theirs) / len(theirs)
    numerator = sum((a - mean_ours) * (b - mean_theirs) for a, b in zip(ours, theirs))
    denominator = ((sum((a - mean_ours) ** 2 for a in ours)
                    * sum((b - mean_theirs) ** 2 for b in theirs)) ** 0.5)
    return numerator / denominator if denominator else 0.0


def offset(series):
    return (sum(e for _m, e, _t in series) - sum(t for _m, _e, t in series)) / len(series)


def main():
    if not os.path.isdir(MET):
        print("ERA5 volume not mounted at %s - nothing re-computed, the committed "
              "cross-check stands" % MET)
        return 0

    rows = build()
    os.makedirs(OUTPUTS, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        handle.write("# ERA5 against the NASA POWER series the residential profile rides. "
                     "A CHECK, NOT A SOURCE: no profile reads this and\n")
        handle.write("# nothing was copied off the volume - the grid is read in place.\n")
        handle.write("# ERA5 and MERRA-2 are separate reanalyses from different institutions, "
                     "which is why this claims LARGE independence.\n")
        handle.write("# LIMIT: the volume holds ERA5 from January 2020, so this covers 54 of "
                     "the 108 months and says nothing about 2015-2019.\n")
        handle.write("# t2m is published in KELVIN and converted here; the degree-day file is "
                     "already Celsius.\n")
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    months = sorted({r["month"] for r in rows})
    deltas = [r["abs_delta_C"] for r in rows]
    mean = sum(r["delta_C"] for r in rows) / len(rows)
    within = sum(1 for d in deltas if d <= 1.0)
    print("ERA5 degree-day cross-check -> %s" % os.path.relpath(OUT, OUTPUTS))
    print("  %d comparisons over %d months and %d cities"
          % (len(rows), len(months), len({r["city"] for r in rows})))
    print("  mean signed difference %+.3f C; median absolute %.3f C; worst %.3f C"
          % (mean, sorted(deltas)[len(deltas) // 2], max(deltas)))
    print("  %d of %d within 1.0 C (%.1f%%)" % (within, len(rows), 100.0 * within / len(rows)))
    print("  THE SHAPE AGREES AND THE LEVEL DOES NOT, which is the finding. Per city:")
    print("    %-10s %8s %10s %10s" % ("city", "corr", "offset_C", "months"))
    for city, series in sorted(by_city_series(rows).items()):
        print("    %-10s %8.4f %+10.2f %10d"
              % (city, correlation(series), offset(series), len(series)))
    print("  Correlation is what this validates: the seasonal TIMING of the temperature the")
    print("  residential profile rides. The offset is definitional - one row per cell per day")
    print("  means t2m is a single daily value, and the files say nothing about which - so it")
    print("  CANNOT validate the degree days, which are a function of level.")
    return 0


if __name__ == "__main__":
    import sys as _sys
    if "--check" in _sys.argv[1:]:
        # re-derive into a temporary directory and compare; nothing in the tree is written
        from pkinv.core.checkmode import compare_only
        _sys.exit(compare_only(globals(), ("OUT",), main))
    sys.exit(main())

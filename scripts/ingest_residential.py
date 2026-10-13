"""Build the residential wood-fuel activity series from the FAOSTAT Forestry bulk.

The other three residential fuels (piped gas, LPG, kerosene) are hand-entered from OGRA
tables into data/activity/residential/fuel_supply.csv - there is nothing to parse, the
figures are three numbers a year out of a PDF. Wood fuel is different: it is a full
annual series that only exists in a 18 MB FAOSTAT bulk, so it gets a script.

Reuses the stream-from-the-zip pattern of src/pkinv/sectors/agriculture/fetch_history.py
rather than inventing a second way of talking to FAOSTAT. The bulk is a HELD document under
data/raw/faostat/ (it used to sit in a gitignored cache, so the series had no kept source);
it is downloaded and kept only if it is not held, and never replaced.

WHAT THIS DATA IS, STATED PLAINLY. Every Pakistan wood-fuel row from 2009 onward carries
FAO's own "E" flag, meaning FAO estimated it rather than receiving it from Pakistan; only
eight years in the whole 1961-2024 series (1998-2008) are flagged "A" for an official
return. The recent series is literally unchanged from 2015 to 2020 and then moves by under
half a percent a year. It is an FAO placeholder, not a Pakistani measurement. It is used anyway because
firewood is the largest household fuel in the country and omitting it would understate
1A4b by a factor of two to three, which a reader of the published total cannot see. The
uncertainty carried on it (60 percent) and this note are the honest handling.

--check re-derives the series from the held bulk and compares; it writes nothing.

Usage:  python3 scripts/ingest_residential.py [--check]
"""
import csv
import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pkinv.assets import asset_path

from pkinv.core import retention       # noqa: E402
from pkinv.paths import ROOT           # noqa: E402

OUT = asset_path(ROOT, "data", "activity", "residential", "woodfuel.csv")
URL = "https://bulks-faostat.fao.org/production/Forestry_E_All_Data_(Normalized).zip"


def _download():
    held = "faostat_" + URL.rsplit("/", 1)[1]
    path = os.path.join(retention.RAW, "faostat", held)
    if not os.path.exists(path):
        print("  downloading %s ..." % held)
        path = retention.fetch_and_keep(URL, "faostat", held, timeout=300)
    return path


def build(check=False):
    z = zipfile.ZipFile(_download())
    name = [n for n in z.namelist() if n.endswith("(Normalized).csv")][0]
    series = {}
    with z.open(name) as fb:
        r = csv.reader(io.TextIOWrapper(fb, encoding="latin-1"))
        hdr = next(r)
        ci = {k: i for i, k in enumerate(hdr)}
        for row in r:
            # "Wood fuel" only - NOT the coniferous/non-coniferous rows, which are its
            # components and would double-count if summed alongside it.
            if (row[ci["Area"]] == "Pakistan" and row[ci["Item"]] == "Wood fuel"
                    and row[ci["Element"]] == "Production" and row[ci["Value"]]):
                series[int(row[ci["Year"]])] = (float(row[ci["Value"]]),
                                                row[ci["Unit"]], row[ci["Flag"]])

    text = io.StringIO()
    w = csv.writer(text)
    w.writerow(["year", "woodfuel_m3", "unit", "faostat_flag", "source"])
    for y in sorted(series):
        v, unit, flag = series[y]
        w.writerow([y, int(v), unit, flag,
                    "FAOSTAT Forestry Production and Trade, item 'Wood fuel', "
                    "element 'Production', area Pakistan"])
    if check:
        return retention.report_check("FAOSTAT wood fuel", OUT, text.getvalue())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        f.write(text.getvalue())

    flags = {f for _v, _u, f in series.values()}
    print("  wrote %s: %d-%d, %d rows" % (OUT, min(series), max(series), len(series)))
    print("  FAOSTAT flags present: %s%s"
          % (", ".join(sorted(flags)),
             "  <- every row is an FAO estimate, not a Pakistani return" if flags == {"E"} else ""))


if __name__ == "__main__":
    sys.exit(build(check="--check" in sys.argv[1:]) or 0)

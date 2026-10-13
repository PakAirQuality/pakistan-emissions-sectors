"""The OCAC edition inventory: every held edition population, counted not remembered.

WHY. The transport paper said "forty-eight monthly editions" in one paragraph
and "thirty-six direct monthly editions" five lines later - both true, of two
different document populations the prose never distinguished (the thirteenth
review's finding). The populations are counted here from the holdings
themselves, and the manuscript's counts are claim-bound to this file.

Usage:  python3 scripts/make_ocac_edition_inventory.py
Writes: outputs/ocac_edition_inventory.csv
"""

from pkinv.assets import asset_path
import csv
import glob
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = asset_path(ROOT, "outputs", "ocac_edition_inventory.csv")

POPULATIONS = (
    ("cumulative_monthly", "sources/Aviation/ocac_monthly/*.pdf",
     "OCAC monthly reports with CUMULATIVE national tables, fetched by the "
     "aviation sector for their jet-fuel columns; months are recovered by "
     "differencing"),
    ("direct_monthly", "data/raw/ocac/monthly_sector_province/*.pdf",
     "OCAC direct single-month editions whose area pages carry the provincial "
     "split; the source of the reference year's own provincial shape"),
    ("annual_control", "data/raw/ocac/annual_controls/*.pdf",
     "OCAC annual editions used as the panel's yearly controls"),
    ("alternate_upload", "data/raw/ocac/alternate_uploads/*.pdf",
     "alternate uploads of months also held above, kept for the revision "
     "diagnostic"),
)


def build():
    rows = []
    for kind, pattern, note in POPULATIONS:
        files = sorted(glob.glob(asset_path(ROOT, pattern)))
        if not files:
            raise SystemExit("edition population %r matches no held file "
                             "(%s) - the inventory would print a zero that "
                             "reads as a holding statement" % (kind, pattern))
        rows.append({"kind": kind, "count": len(files),
                     "holding_dir": os.path.dirname(pattern), "note": note})
    return rows


def main():
    rows = build()
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        f.write("# EVERY held OCAC edition population, counted from the holdings "
                "at build time. Two true counts of two different populations "
                "(48 cumulative vs 36 direct) read as a contradiction until "
                "this file distinguished them.\n")
        w = csv.DictWriter(f, fieldnames=("kind", "count", "holding_dir", "note"))
        w.writeheader()
        w.writerows(rows)
    print("ocac edition inventory -> %s" % os.path.relpath(OUT, ROOT))
    for r in rows:
        print("  %-18s %3d  %s" % (r["kind"], r["count"], r["holding_dir"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Extract NFDC Annex-7: province x month x product fertiliser offtake, from the archived PDF.

WHAT IT IS FOR. The agriculture sector's nitrogen MAGNITUDE is the audited annual offtake in
data/activity/fertilizer_2024.csv. Annex-7 supplies only the COMPOSITION - which products
that nitrogen arrived in, by province and month - because the crop-mix and application-timing
work needs the split and the annual total cannot provide it.

WHY IT IS EXTRACTED RATHER THAN BORROWED. When the sector moved onto FY2023-24 the committed
annex still described FY2024-25, and a composition from the wrong year is exactly the kind of
shape this project is willing to borrow when the right one does not exist. Here it does: the
NFDC Fertilizer Review 2023-24 carries its own Annex-7 for Kharif 2023 and Rabi 2023-24, and
the document is archived. Borrowing a shape that is sitting in a held PDF would be economising,
not evidence.

THE FIFTEEN-MONTH TRAP, which this file exists downstream of. The annex prints Kharif, Rabi
AND the opening months of the next Kharif, so summing it whole double-counts a season and
inflates nitrogen by about 19 percent. The extractor keeps the season label on every row so
the consumer can take the fiscal-year window; tests/test_fertiliser_mix.py asserts the trap is
still detectable.

Usage:  python3 scripts/ingest_nfdc_annex7.py
Writes: data/nfdc/annex7_province_month_product_2023-24.csv
"""

from pkinv.assets import asset_path
import csv
import io
import os
import re
import subprocess
import sys

from pkinv.core.io import write_or_check
from pkinv.paths import DATA, ROOT

PDF = asset_path(ROOT, "sources", "Agriculture", "NFDC_Fertilizer_Review_2023-24.pdf")
OUT = asset_path(DATA, "nfdc", "annex7_province_month_product_2023-24.csv")

# The annex's column order. The 2023-24 edition prints TSP where the 2024-25 edition prints
# UP; both are empty in every Pakistani row, and the committed schema keeps UP so the two
# editions stay one table.
PRODUCTS = ("Urea", "DAP", "NP", "CAN", "SSP", "UP", "SOP", "MAP", "MOP", "AS", "NPKs")
FIELDS = ("province", "season", "month", "calendar_year") + PRODUCTS + ("Total", "source")

PROVINCES = {"PUNJAB": "Punjab", "SINDH": "Sindh", "KP": "KP", "BALOCHISTAN": "Balochistan"}
KHARIF = ("April", "May", "June", "July", "Aug", "Sep")
RABI = ("Oct", "Nov", "Dec", "Jan", "Feb", "Mar")
MONTH_ALIASES = {"April": "Apr", "June": "Jun", "July": "Jul", "Sept": "Sep"}

SOURCE = ("NFDC AFR 2023-24 Annex-7 (product tonnes; "
          "sources/Agriculture/NFDC_Fertilizer_Review_2023-24.pdf)")


def _text():
    if not os.path.exists(PDF):
        raise SystemExit("the archived NFDC review is missing: %s" % PDF)
    return subprocess.run(["pdftotext", "-layout", PDF, "-"],
                          capture_output=True, text=True, check=True).stdout


def _number(token):
    token = token.strip()
    if token in ("", "-", "--"):
        return ""
    return str(int(token.replace(",", "")))


def parse(text):
    """Rows for the fiscal year's twelve months, per province.

    Reads a province header, then month lines under a season heading. A 'Total' line closes a
    season and is not emitted - the consumer sums the months, so a printed subtotal would be
    a second, silently-preferred path to the same quantity.
    """
    rows, province, season = [], None, None
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped in PROVINCES:
            province, season = PROVINCES[stripped], None
            continue
        if province is None:
            continue
        if re.match(r"^Kharif\s+2023\b", stripped):
            season = ("Kharif2023", 2023)
            continue
        if re.match(r"^Rabi\s+2023-24\b", stripped):
            season = ("Rabi2023-24", None)
            continue
        if season is None:
            continue
        m = re.match(r"^(?:\d+\s+)?([A-Z][a-z]+)\s+((?:[\d,]+|-)(?:\s+(?:[\d,]+|-))*)\s*$",
                     stripped)
        if not m:
            continue
        month = MONTH_ALIASES.get(m.group(1), m.group(1))
        if month == "Total":
            # A season subtotal closes it. What FOLLOWS a Rabi subtotal is the opening of the
            # NEXT Kharif, printed without a heading - and those months are the fifteen-month
            # trap. They are ingested with their own season label rather than dropped: the
            # extractor's job is to say what the annex says, and the consumer's job is to take
            # the twelve-month window. Dropping them here would hide the trap instead of
            # letting tests/test_fertiliser_mix.py keep proving it is still detectable.
            season = ("Kharif2024", 2024) if season[0].startswith("Rabi") else None
            continue
        label, year = season
        wanted = KHARIF if label.startswith("Kharif") else RABI
        if month not in [MONTH_ALIASES.get(x, x) for x in wanted]:
            continue
        values = [_number(v) for v in m.group(2).split()]
        if len(values) != len(PRODUCTS) + 1:   # products plus the row total
            continue
        if year is None:                       # Rabi straddles the new year
            year = 2023 if month in ("Oct", "Nov", "Dec") else 2024
        row = {"province": province, "season": label, "month": month,
               "calendar_year": year, "source": SOURCE}
        row.update(dict(zip(PRODUCTS, values[:-1])))
        row["Total"] = values[-1]
        rows.append(row)
    return rows





def main(check=False):
    rows = parse(_text())
    if write_or_check(OUT, FIELDS, rows, check):
        return 1
    if check:
        print("NFDC Annex-7 reproduces from the held document.")
        return 0
    urea = sum(int(r["Urea"] or 0) for r in rows)
    total = sum(int(r["Total"] or 0) for r in rows)
    print("NFDC Annex-7 FY2023-24 -> %s" % OUT)
    print("  %d rows over %d provinces and %d seasons"
          % (len(rows), len({r["province"] for r in rows}),
             len({r["season"] for r in rows})))
    print("  urea %s t, all products %s t (product tonnes, not nutrient tonnes)"
          % ("{:,}".format(urea), "{:,}".format(total)))
    return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))

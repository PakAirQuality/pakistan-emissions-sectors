"""Read OGRA's FY2020-21 sector-wise gas table off an image scan, and make it check itself.

WHY THIS YEAR NEEDS A SCRIPT. Every other year of OGRA's Table 3.x sector-wise gas consumption
was read from a text layer. The FY2020-21 edition has none - eighty-eight characters in the
whole eighty-eight-page file - so industry's General Industry row was declared ABSENT and the
sector-year with it, and power's captive row was carried as a provisional total read off a
chart data label. The table is perfectly legible; only the text layer is missing. What was
required was rendering and OCR, and the reason it is a script rather than four typed numbers
is that an OCR read nobody can repeat is indistinguishable from an invention.

HOW IT AVOIDS TRUSTING THE OCR. The table carries its own arithmetic, and this refuses to
report a row that fails it:

  - the three utility systems must sum to the total on every row;
  - each row's percentage share must equal its total over the grand total;
  - the subtotal must equal the sum of the eight sector rows.

An OCR that turns 202 into 292 breaks the first check; one that drops a digit from the total
breaks the second. Three independent identities over one small table is a stronger guarantee
than a human transcription of the same page, which has none.

WHAT IT CORROBORATES. data/activity/power/captive_gas.csv holds FY2021 as a provisional 203
MMCFD read from a chart label with no utility split. This table's Captive Power row reads
1 + 202 + 0 = 203: the same total from a different element of the same document, which is what
lets that row become verified and gain its split.

Usage:  python3 scripts/ocr_ogra_2020_21.py [--page 53] [--dpi 300]
Writes: nothing. It prints the table and checks the committed rows against it.
"""

from pkinv.assets import asset_path
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = asset_path(ROOT, "sources", "OGRA", "ogra_state_of_industry_2020-21.pdf")
INDUSTRY = asset_path(ROOT, "data", "activity", "industry", "gas_consumption.csv")
CAPTIVE = asset_path(ROOT, "data", "activity", "power", "captive_gas.csv")

PAGE, DPI = 53, 300
FISCAL_YEAR = "2021"                       # fiscal-END key: FY2020-21
SECTORS = ("Residential", "Commercial", "General Industry", "Fertilizer", "Cement",
           "Captive Power", "Power", "Transport")
# "General Industry 202 163 0 365 8.49" - three systems, a total, a percentage. Zeros are
# sometimes OCR'd as the letter O or as a stray bracket, which is why the third column is
# matched loosely and then normalised rather than required to be a digit.
ROW = re.compile(r"^(%s)\s+([\d,]+)\s+([\d,]+)\s+([\dO()e)]+)\s+([\d,]+)\s+([\d.]+)\s*$"
                 % "|".join(SECTORS))
SUBTOTAL = re.compile(r"^Subtotal\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d.]+)\s*$")
GRAND = re.compile(r"^Grand\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d.]+)\s*$")


def _number(token):
    """OCR renders an isolated zero as O, (, ) or e often enough to be worth naming."""
    cleaned = token.replace(",", "").strip()
    if cleaned in ("O", "o", "(", ")", "()", "(¢)", "e", "-"):
        return 0.0
    return float(cleaned)


def ocr_page(page=PAGE, dpi=DPI):
    for tool in ("pdftoppm", "tesseract"):
        if not shutil.which(tool):
            raise SystemExit("%s is not installed; nothing read and nothing checked" % tool)
    with tempfile.TemporaryDirectory() as work:
        stem = asset_path(work, "page")
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-f", str(page), "-l", str(page),
                        PDF, stem], check=True, stderr=subprocess.DEVNULL)
        rendered = [asset_path(work, n) for n in sorted(os.listdir(work))]
        if not rendered:
            raise SystemExit("page %d did not render" % page)
        result = subprocess.run(["tesseract", rendered[0], "stdout"],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    return result.stdout.decode("utf-8", "replace")


def parse(text):
    """{sector: dict} plus the subtotal and grand rows. Raises on a failed identity."""
    rows, subtotal, grand = {}, None, None
    for line in text.splitlines():
        line = " ".join(line.split())
        match = ROW.match(line)
        if match:
            name = match.group(1)
            sngpl, ssgcl, independent = (_number(match.group(i)) for i in (2, 3, 4))
            total, share = _number(match.group(5)), _number(match.group(6))
            rows[name] = {"sngpl_mmcfd": sngpl, "ssgcl_mmcfd": ssgcl,
                          "independent_mmcfd": independent, "total_mmcfd": total,
                          "pct_national_gas": share}
            continue
        if SUBTOTAL.match(line):
            subtotal = [_number(g) for g in SUBTOTAL.match(line).groups()]
        elif GRAND.match(line):
            grand = [_number(g) for g in GRAND.match(line).groups()]

    missing = [s for s in SECTORS if s not in rows]
    if missing:
        raise SystemExit("the OCR did not yield %s; NOTHING may be taken from a partial "
                         "read of this table" % ", ".join(missing))

    problems = []
    for name, row in rows.items():
        parts = row["sngpl_mmcfd"] + row["ssgcl_mmcfd"] + row["independent_mmcfd"]
        if abs(parts - row["total_mmcfd"]) > 0.5:
            problems.append("%s: systems sum to %g, the printed total is %g"
                            % (name, parts, row["total_mmcfd"]))
    if grand:
        for name, row in rows.items():
            implied = 100.0 * row["total_mmcfd"] / grand[3]
            if abs(implied - row["pct_national_gas"]) > 0.05:
                problems.append("%s: %g of %g is %.2f%%, the printed share is %.2f%%"
                                % (name, row["total_mmcfd"], grand[3], implied,
                                   row["pct_national_gas"]))
    if subtotal:
        sectors_total = sum(r["total_mmcfd"] for r in rows.values())
        if abs(sectors_total - subtotal[3]) > 0.5:
            problems.append("the eight sectors sum to %g, the printed subtotal is %g"
                            % (sectors_total, subtotal[3]))
    if problems:
        raise SystemExit("the OCR read fails the table's own arithmetic:\n  %s\n"
                         "Nothing may be committed from it." % "\n  ".join(problems))
    return rows, subtotal, grand


def _committed(path, key_field, key):
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row[key_field] == key and row.get("stream", "") in ("", "General Industry"):
                return row
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", type=int, default=PAGE)
    parser.add_argument("--dpi", type=int, default=DPI)
    args = parser.parse_args(argv)

    rows, subtotal, grand = parse(ocr_page(args.page, args.dpi))
    print("OGRA State of the Regulated Petroleum Industry 2020-21, sector-wise gas "
          "consumption (MMCFD), page %d at %d dpi" % (args.page, args.dpi))
    print("  %-17s %7s %7s %7s %8s %7s" % ("sector", "SNGPL", "SSGCL", "indep", "total", "%"))
    for name in SECTORS:
        row = rows[name]
        print("  %-17s %7g %7g %7g %8g %7.2f"
              % (name, row["sngpl_mmcfd"], row["ssgcl_mmcfd"], row["independent_mmcfd"],
                 row["total_mmcfd"], row["pct_national_gas"]))
    print("  all three identities hold: systems sum to totals, shares match the grand total "
          "of %g, and the sectors sum to the subtotal" % (grand[3] if grand else float("nan")))

    problems = []
    industry = _committed(INDUSTRY, "fiscal_year", FISCAL_YEAR)
    if industry is None:
        problems.append("gas_consumption.csv has no FY2020-21 General Industry row")
    else:
        for field in ("sngpl_mmcfd", "ssgcl_mmcfd", "total_mmcfd"):
            if abs(float(industry[field]) - rows["General Industry"][field]) > 0.5:
                problems.append("gas_consumption.csv %s is %s, the table says %g"
                                % (field, industry[field],
                                   rows["General Industry"][field]))
    captive = _committed(CAPTIVE, "fiscal_year", FISCAL_YEAR)
    if captive is None:
        problems.append("captive_gas.csv has no FY2021 row")
    else:
        for field in ("sngpl_mmcfd", "ssgcl_mmcfd", "total_mmcfd"):
            if captive[field] and abs(float(captive[field])
                                      - rows["Captive Power"][field]) > 0.5:
                problems.append("captive_gas.csv %s is %s, the table says %g"
                                % (field, captive[field], rows["Captive Power"][field]))
    if problems:
        print("\nDISAGREEMENT with the committed activity:")
        for line in problems:
            print("  %s" % line)
        return 1
    print("\nThe committed industry and captive rows both match the document.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

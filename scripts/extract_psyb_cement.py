"""Read national cement production out of the Pakistan Statistical Year Book, and check it.

WHY THIS EXISTS RATHER THAN FOUR TYPED NUMBERS. Cement was reported for the last three fiscal
years because the activity file held three rows, and the four before them were declared absent
- while Table 13.2 of a yearbook already under sources/ carried them the whole time. A gap that
turns out to be an unread table is the failure mode this project keeps finding, and the
correction is worth nothing if the replacement is four numbers typed by hand: the next reader
has no way to tell a transcription from a guess. So the table is READ here, and this script
compares what it reads against what data/activity/ippu/national_activity.csv claims.

WHAT THE TABLE IS. "13.2 Production of Manufacturing Items", cement panel, physical output in
thousand tonnes by Pakistani fiscal year, sourced by the yearbook to the Ministry of Industries
and reported for 23 factories. It is not the Quantum Index of Table 13.1, which is an index on
2005-06=100 and cannot be used as activity.

THE OVERLAP IS THE POINT. The yearbook and the State Bank supplement both publish FY2019-20:
39,122 against 39,121 thousand tonnes, a difference of one part in forty thousand. Two
independent publications agreeing to that tolerance is what makes the join between them a
measured bridge rather than an assumption, and it is why the earlier years can be carried on
the yearbook without declaring a break in the series.

Usage:  python3 scripts/extract_psyb_cement.py [--print]
Checks: data/activity/ippu/national_activity.csv against the document; exits non-zero on a
        disagreement and writes nothing, ever.
"""

from pkinv.assets import asset_path
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pkinv.core.io import read_rows

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = asset_path(ROOT, "sources", "Provincial Statistics",
                       "National-20260803T134231Z-1-001.zip")
MEMBER = "National/Pakistan_Statistical_Yearbook_2020.pdf"
MEMBER_CANDIDATES = ("National/Pakistan_Statistical_Year_Book_2020.pdf",
                     "National/Pakistan_Statistical_Yearbook_2020.pdf")
ACTIVITY = asset_path(ROOT, "data", "activity", "ippu", "national_activity.csv")
SOURCE_ID = "psyb_2020_table_13_2"

# The cement panel sits in a three-item block: motor tubes, cement, sewing machines. Each data
# line is  year, tube factories, tube production, CEMENT FACTORIES, CEMENT PRODUCTION, sewing
# factories, sewing production - so cement is the fifth field, and the fourth must be the
# reported factory count, which is what distinguishes this block from the other panels of the
# same table that share its year column.
CEMENT_FACTORIES = 23
ROW = re.compile(r"^\s*(20\d{2}-\d{2})\s+(\d+)\s+([\d.]+)\s+(\d+)\s+([\d.]+)\s+(\d+)\s+([\d.]+)\s*$")


def _pdf_text():
    if not shutil.which("pdftotext"):
        raise SystemExit("pdftotext is not installed; nothing read and nothing checked")
    with zipfile.ZipFile(ARCHIVE) as archive:
        member = next((m for m in MEMBER_CANDIDATES if m in archive.namelist()), None)
        if member is None:
            raise SystemExit("%s holds no yearbook member; looked for %s"
                             % (os.path.basename(ARCHIVE), ", ".join(MEMBER_CANDIDATES)))
        blob = archive.read(member)
    result = subprocess.run(["pdftotext", "-layout", "-", "-"], input=blob,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    return result.stdout.decode("utf-8", "replace")


def read_cement_kt(text=None):
    """{fiscal_end_year: kt} from Table 13.2's cement panel.

    Keyed by the year the fiscal year CLOSES in, which is the convention
    national_activity.csv uses: the yearbook's "2015-16" is period_end_year 2016.
    """
    text = text if text is not None else _pdf_text()
    out = {}
    for line in text.splitlines():
        match = ROW.match(line)
        if not match:
            continue
        label, _tube_factories, _tubes, factories, cement, _sew_factories, _sewing = \
            match.groups()
        if int(factories) != CEMENT_FACTORIES:
            continue
        out[int(label[:4]) + 1] = float(cement)
    if not out:
        raise SystemExit("Table 13.2's cement panel did not parse; the layout may have "
                         "changed and NOTHING should be written until it is re-read by hand")
    return out


def committed_cement_kt():
    """{period_end_year: kt} for the rows the activity file attributes to this document."""
    return {int(r["period_end_year"]): float(r["quantity"]) for r in read_rows(ACTIVITY, comments=False) if r["product"] == "Cement" and r["source_id"] == SOURCE_ID}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check the cement rows against the yearbook.")
    parser.add_argument("--print", dest="show", action="store_true",
                        help="print every year the table holds, not only the committed ones")
    args = parser.parse_args(argv)

    document = read_cement_kt()
    committed = committed_cement_kt()

    print("Pakistan Statistical Year Book 2020, Table 13.2, cement (000 tonnes)")
    for year in sorted(document):
        mark = ""
        if year in committed:
            mark = " <- committed" if committed[year] == document[year] else " <- DISAGREES"
        if args.show or year in committed:
            print("  FY%d-%02d  %9.0f%s" % (year - 1, year % 100, document[year], mark))

    problems = []
    for year, value in sorted(committed.items()):
        if year not in document:
            problems.append("FY%d-%02d is attributed to this table and is not in it"
                            % (year - 1, year % 100))
        elif document[year] != value:
            problems.append("FY%d-%02d: the file says %.0f and the table says %.0f"
                            % (year - 1, year % 100, value, document[year]))
    if problems:
        print("\nDISAGREEMENT between the committed activity and the document:")
        for line in problems:
            print("  %s" % line)
        return 1
    print("\n%d committed rows all match the document." % len(committed))
    return 0


if __name__ == "__main__":
    sys.exit(main())

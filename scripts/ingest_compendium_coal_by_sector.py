"""Transcribe HDIP's "Consumption of Indigenous Coal by Sector" as the PBS Compendium on
Environment Statistics reprints it (Table A-45 in the 2015 and 2020 editions), with the
publisher's footnotes carried on every row.

WHY THIS TABLE MATTERS. It is the primary publication's own statement of what the official
brick-kiln coal series IS:

    *   Estimated by deducting other uses of indigenous coal from the total production.
    **  Include indigenous as well as imported coal.
    *** Imported coal/coke used as coke in Pak Steel.

The brick-kiln column is therefore a RESIDUAL of domestic production by construction - every
tonne of indigenous coal the other columns book (power first) is a tonne the brick column loses.
That is the mechanism the coal balance's H2 (HDIP power against NEPRA's metered burn) tests,
and it is why recomputing that residual from the same inputs can never be a correction. The
Cement/Other Industry column mixes indigenous and imported coal; the label is the primary one
(the Finance Division Supplement prints it as "Cement").

WHAT IT IS NOT. Fired-brick production, kiln counts or coal-per-brick: the Compendium carries
none (CCAC's fact sheet, which names the Compendium, is itself the only brick-count anchor).

Reads:  data/raw/pbs/compendium_environment/pbs_compendium_environment_statistics_{2015,2020}.pdf
Writes: data/activity/industry/coal_by_sector_pey_compendium.csv
Every row closes on the printed Total (status verified) or is marked with its residual.
"""
import csv
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.paths import DATA, ROOT  # noqa: E402

RAW = asset_path(DATA, "raw", "pbs", "compendium_environment")
EDITIONS = {"2015": "pbs_compendium_environment_statistics_2015.pdf",
            "2020": "pbs_compendium_environment_statistics_2020.pdf"}
OUT = asset_path(DATA, "activity", "industry", "coal_by_sector_pey_compendium.csv")
FIELDS = ("fiscal_year", "compendium_edition", "table", "power_wapda_t", "brick_kiln_t", "domestic_t",
          "cement_other_industry_t", "pak_steel_t", "total_printed_t", "row_sum_t", "closure_residual_t",
          "status", "primary_source", "footnote_brick", "footnote_cement_other", "footnote_pak_steel", "source_file")
FOOT_BRICK = "* Estimated by deducting other uses of indigenous coal from the total production."
FOOT_CEMENT = "** Include indigenous as well as imported coal."
FOOT_STEEL = "*** Imported coal/coke used as coke in Pak Steel."
ROW = re.compile(r"^\s*(\d{4}-\d{2})\s+([\d,]+|-)\s+([\d,]+|-)\s+([\d,]+|-)\s+([\d,]+|-)\s+([\d,]+|-)\s+([\d,]+)\s*$")


def _num(tok):
    return 0 if tok == "-" else int(tok.replace(",", ""))


def parse(edition, path):
    text = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, check=True).stdout
    start = text.rindex("Consumption of Indigenous Coal by Sector")   # the LAST occurrence: the table, not the contents entry
    block = text[start:start + 12000]
    rows = []
    for line in block.splitlines():
        m = ROW.match(line)
        if not m:
            continue
        fy, power, brick, dom, cem, steel, total = m.groups()
        vals = [_num(v) for v in (power, brick, dom, cem, steel)]
        s, t = sum(vals), _num(total)
        rows.append({
            "fiscal_year": "FY" + fy, "compendium_edition": edition, "table": "A-45 Consumption of Indigenous Coal by Sector",
            "power_wapda_t": vals[0], "brick_kiln_t": vals[1], "domestic_t": vals[2], "cement_other_industry_t": vals[3],
            "pak_steel_t": vals[4], "total_printed_t": t, "row_sum_t": s, "closure_residual_t": s - t,
            "status": "verified" if s == t else "verified-open-residual",
            "primary_source": "Hydrocarbon Development Institute of Pakistan, Pakistan Energy Yearbook (as cited by the Compendium)",
            "footnote_brick": FOOT_BRICK, "footnote_cement_other": FOOT_CEMENT, "footnote_pak_steel": FOOT_STEEL,
            "source_file": os.path.relpath(path, ROOT),
        })
    return rows


def main():
    out = []
    for edition, name in sorted(EDITIONS.items()):
        out += parse(edition, asset_path(RAW, name))
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write("# HDIP's coal-by-sector allocation as the PBS Compendium on Environment Statistics reprints it (Table A-45,\n"
                "# 2015 and 2020 editions), tonnes, with the publisher's own footnotes on every row. THE BRICK-KILN COLUMN IS A\n"
                "# RESIDUAL BY CONSTRUCTION (footnote *). Transcribed by scripts/ingest_compendium_coal_by_sector.py; every row\n"
                "# closes on the printed Total (status verified) or carries its residual. One edition per row; overlapping\n"
                "# fiscal years are the inter-edition comparison, kept apart.\n")
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    closed = sum(1 for r in out if r["status"] == "verified")
    print("wrote %s (%d rows, %d close on the printed total)" % (os.path.relpath(OUT, ROOT), len(out), closed))
    for r in out:
        if r["compendium_edition"] == "2020" and r["fiscal_year"] >= "FY2014-15":
            print("  %s brick %10s  cement/other %10s  power %9s  total %10s  %s" % (
                r["fiscal_year"], "{:,}".format(r["brick_kiln_t"]), "{:,}".format(r["cement_other_industry_t"]),
                "{:,}".format(r["power_wapda_t"]), "{:,}".format(r["total_printed_t"]), r["status"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""The two power-coal lanes reconciled, per year, with the unmatched tonnage typed (rc46 W2).

TWO LANES, ONE FUEL. The inventory's grid-coal stream is built from NEPRA's plant-fuel lane
(SoIR tables, named stations, mine-mouth and import deliveries); the new solid-fuel streams
are built from HDIP's coal-by-consumer lane (Statistical Supplement Table 14.1(4), national
estimates whose categories exhaust supply). Where both speak - the five ledger years - they
disagree, and the disagreement CHANGES SIGN: NEPRA's named plants report MORE coal than
HDIP's power estimate in FY2019-20 and FY2020-21 (-1.4, -3.9 Mt) and less from FY2021-22
(+0.6, +1.5, +3.3). The unmatched tonnage is PUBLISHED here and never spread across named
plants - a station's fuel is what its lane reports, not what a national residual implies.

WHY THE SIGN FLIP MATTERS BEYOND POWER. HDIP's consumption categories exhaust supply, so a
kilotonne HDIP under-books to power is a kilotonne its residual-style BRICK column absorbs.
The years NEPRA exceeds HDIP-power are exactly the years the brick column spikes (8,184 and
8,678 kt against 1,129-3,941 in the surrounding years) - the boundary wobble between the
lanes surfaces as brick-kiln coal. That is the measured basis of the solid-fuel streams'
30 percent activity uncertainty (industry_params.csv), not a hedge.

Deterministic; --check re-derives and diffs.

Usage:  python3 scripts/build_coal_reconciliation.py [--check]
Writes: outputs/industry_coal_reconciliation.csv
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.core.io import read_rows, write_or_check  # noqa: E402
from pkinv.paths import DATA, OUTPUTS  # noqa: E402

SERIES = asset_path(DATA, "activity", "industry", "coal_by_consumer.csv")
LEDGER = asset_path(DATA, "activity", "power", "plant_fuel_ledger.csv")
OUT = asset_path(OUTPUTS, "industry_coal_reconciliation.csv")
FIELDS = ("fiscal_year", "hdip_power_kt", "nepra_named_plant_kt", "unmatched_kt",
          "unmatched_direction", "hdip_brick_kt", "note")


def build():
    hdip = {}
    brick = {}
    for row in read_rows(SERIES):
        if row["revision_status"] not in ("final", "provisional"):
            continue
        if row["consumer"] == "power" and row["coal_kt"]:
            hdip[row["fiscal_year"]] = float(row["coal_kt"])
        if row["consumer"] == "brick_kilns" and row["coal_kt"]:
            brick[row["fiscal_year"]] = float(row["coal_kt"])
    nepra = {}
    for row in read_rows(LEDGER, comments=False):
        if row["fuel"] == "Coal" and row.get("quantity"):
            start = int(row["fiscal_year"])
            label = "%d-%02d" % (start, (start + 1) % 100)
            nepra[label] = nepra.get(label, 0.0) + float(row["quantity"])
    rows = []
    for label in sorted(hdip):
        if label < "2015-16" or label > "2024-25":
            continue
        n = nepra.get(label)
        h = hdip[label]
        row = {"fiscal_year": label, "hdip_power_kt": "%.1f" % h,
               "hdip_brick_kt": "%.1f" % brick.get(label, 0.0)}
        if n is None:
            reason = ("the plant-fuel ledger begins FY2019-20; before it HDIP is the only "
                      "power-coal lane" if label < "2019-20" else
                      "beyond the plant-fuel ledger's last ingested year")
            if label == "2015-16":
                reason += ("; brick shown as the supplement PRINTS it (3,541.1) - the "
                           "solid-fuel stream itself adopts the balance-consistent PEY "
                           "vintage 3,337.1, see solid_fuels.py")
            row.update({"nepra_named_plant_kt": "", "unmatched_kt": "",
                        "unmatched_direction": "no_nepra_lane", "note": reason})
        else:
            u = h - n
            row.update({"nepra_named_plant_kt": "%.1f" % n, "unmatched_kt": "%.1f" % u,
                        "unmatched_direction": ("hdip_exceeds_named_plants" if u >= 0
                                                else "named_plants_exceed_hdip"),
                        "note": ("published, never spread: no station receives a share of a "
                                 "national residual" if u >= 0 else
                                 "NEPRA's named stations report more coal than HDIP books "
                                 "to power; HDIP's exhaustive categories put the difference "
                                 "somewhere, and the brick column's spike this year is where")})
        rows.append(row)
    return rows


def main(check=False):
    rows = build()
    banner = [
        "POWER COAL, TWO LANES RECONCILED (rc46 Wave 2): HDIP's coal-by-consumer power",
        "column against the NEPRA plant-fuel ledger's named-station coal, per fiscal year.",
        "The unmatched tonnage is typed and published, never spread across plants; its sign",
        "FLIPS across the window, and the negative years are the brick-column spike years -",
        "see scripts/build_coal_reconciliation.py for the exhaustive-categories argument.",
    ]
    return write_or_check(OUT, list(FIELDS), rows, check=check, banner=banner, lineterminator="\n")


if __name__ == "__main__":
    raise SystemExit(main(check="--check" in sys.argv))

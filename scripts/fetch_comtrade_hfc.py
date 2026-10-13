#!/usr/bin/env python3
"""Keep the UN Comtrade responses behind the HFC trade screening and check the table.

data/activity/ippu/hfc_trade_screening.csv is eighteen rows of Pakistan's annual trade in the
HS-2022 HFC subheadings (2903.41 to 2903.49 bulk gases, 3827 mixtures), read from the Comtrade
public API in August 2026 by hand. No script fetched it and no response was kept, so the table
had a source and no document.

This asks the same endpoint for each calendar year and flow, KEEPS every response under
data/raw/un_comtrade/hfc/ (pkinv.core.retention), and compares net weight and trade value
with the table. It writes no table: the screening stays the transcription it is, and this is
its cross-check. A response already kept is read from the kept file and not asked for again.

Comtrade revises: a row may legitimately differ from what was read in August. The script
reports each difference and exits non-zero, so a revision is seen and decided, never absorbed.

Usage:  python3 scripts/fetch_comtrade_hfc.py
Writes: data/raw/un_comtrade/hfc/A_<flow>_<year>.json
"""
import csv
import json
import os
import sys
import time
import urllib.parse

from pkinv.assets import asset_path
from pkinv.core import retention

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE = asset_path(ROOT, "data", "activity", "ippu", "hfc_trade_screening.csv")
BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
CODES = ["2903%02d" % n for n in range(41, 50)] + ["3827"]
FLOWS = {"M": "import", "X": "export"}
PACE_S = 6.0            # the pacing fetch_comtrade_clinker.py measured to draw no 429


def response(year, flow_code):
    name = "hfc/A_%s_%s.json" % (flow_code, year)
    path = os.path.join(retention.RAW, "un_comtrade", name)
    if not os.path.exists(path):
        url = BASE + "?" + urllib.parse.urlencode({
            "reporterCode": 586, "partnerCode": 0, "cmdCode": ",".join(CODES),
            "flowCode": flow_code, "period": year})
        body = retention.get(url, attempts=3, timeout=90, pause=45.0,
                             headers={"Accept": "application/json"})
        json.loads(body.decode("utf-8"))          # a challenge page is not a response
        path = retention.keep(body, "un_comtrade", name, url)
        time.sleep(PACE_S)
    with open(path, encoding="utf-8") as handle:
        return json.load(handle).get("data") or []


def main():
    with open(TABLE, encoding="utf-8", newline="") as handle:
        table = list(csv.DictReader(handle))
    years = sorted({r["calendar_year"] for r in table})
    source = {}
    for year in years:
        for flow_code, flow in FLOWS.items():
            for record in response(year, flow_code):
                # one aggregate record per commodity: partner World, no second partner,
                # all customs procedures and transport modes
                if str(record.get("partner2Code", 0)) not in ("0", "None") \
                        or str(record.get("motCode", 0)) not in ("0", "None"):
                    continue
                key = (year, flow, str(record["cmdCode"]))
                source[key] = (record.get("netWgt"), record.get("primaryValue"))
    wrong = []
    for row in table:
        key = (row["calendar_year"], row["flow"], row["hs_code"])
        if key not in source:
            wrong.append("%s %s %s: the table holds a row the source no longer reports" % key)
            continue
        kg, usd = source[key]
        if round(float(kg or 0)) != int(row["net_kg"]) \
                or round(float(usd or 0)) != int(row["trade_value_usd"]):
            wrong.append("%s %s %s: table %s kg / %s USD, source now %s kg / %s USD"
                         % (key + (row["net_kg"], row["trade_value_usd"], kg, usd)))
    held = {(r["calendar_year"], r["flow"], r["hs_code"]) for r in table}
    extra = sorted(k for k in source if k not in held)
    for line in wrong:
        print("  ! %s" % line)
    for key in extra:
        print("  + %s %s %s: reported by the source, not in the table" % key)
    print("Comtrade HFC screening: %d of %d table rows agree with the kept responses; "
          "%d source records are not in the table" % (len(table) - len(wrong), len(table),
                                                      len(extra)))
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())

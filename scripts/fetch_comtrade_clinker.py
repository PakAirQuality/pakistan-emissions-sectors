"""Try to extend the monthly HS 252310 clinker trade panel backwards from UN Comtrade.

WHAT THIS WOULD UNBLOCK. Cement (2.A.1) is the one IPPU category with a live estimator and
it is reported for a single fiscal year, because IPCC Equation 2.1 needs a clinker trade
correction and data/activity/ippu/clinker_trade_monthly.csv holds twenty-four months:
July 2023 to June 2024. Further fiscal years of cement wait on further twelve-month blocks.
The reference year already cites "UN Comtrade public API; reporter 586, partner World" as
its source, so this script asks the same source for the earlier months.

A MONTH THAT COMES BACK EMPTY IS NOT A ZERO, and this is the whole difficulty. Comtrade
returns no record both for a month in which nothing was traded and for a month it has not
processed, and the response cannot tell them apart. Pakistan imports clinker in small,
sporadic quantities - 26 kt across the whole of FY2023-24 against 3,792 kt exported - so
empty months are common and reading them as zeros would fabricate a complete panel out of
an incomplete one.

So this script also fetches the ANNUAL total for each calendar year and flow, from the same
source. That is what lets a zero be proved instead of assumed: if the twelve monthly records
of a calendar year sum to that year's annual total, then the months with no record are
established zeros - the source itself says nothing more was traded. If they do not sum, the
missing months are unobtained and the fiscal years touching that calendar year stay NE. The
reconciliation is done by the gate in src/pkinv/sectors/ippu/trade_evidence.py, not here;
this script only records what the source said.

THE FAILURE CONTRACT. If the API does not resolve, this writes NOTHING, touches NOTHING and
exits non-zero, printing what to fetch by hand. An unobtained year is a declared gap; an
invented one is a fabricated result.

The public preview endpoint takes ONE period per request and rate-limits aggressively, so a
full sweep is a few hundred paced requests and takes roughly forty minutes. It is resumable:
month-flows already held are never re-requested.

EVERY RESPONSE IS KEPT. Each request's body is written to data/raw/un_comtrade/hs252310/
before it is parsed (pkinv.core.retention), the silent ones included: an empty record list is
what the source said about that month, and it is the evidence the zero rests on. Until
October 2026 the responses were parsed in memory and dropped, so the two tables this script
writes had no held document behind them.

--check asks for every period of the window again (or reads the response already held),
compares it with the rows the tables hold, and writes neither table. It exits non-zero if a
held row disagrees with what the source says now.

Usage:  python3 scripts/fetch_comtrade_clinker.py [--dry-run] [--check] [--from 2014-07] [--to 2024-12]
Writes: data/raw/un_comtrade/hs252310/<freq>_<flow>_<period>.json  (every response)
        data/activity/ippu/clinker_trade_monthly.csv          (affirmative records only)
        data/activity/ippu/clinker_trade_annual_controls.csv  (the annual reconciliation)
"""

from pkinv.assets import asset_path
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pkinv.core import retention
from pkinv.core.io import read_rows

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IPPU = asset_path(ROOT, "data", "activity", "ippu")
MONTHLY = asset_path(IPPU, "clinker_trade_monthly.csv")
CONTROLS = asset_path(IPPU, "clinker_trade_annual_controls.csv")

MONTHLY_FIELDS = ("month", "flow", "hs_code", "quantity_t", "source_id",
                  "source_reference", "period_basis", "coverage", "note")
CONTROL_FIELDS = ("calendar_year", "flow", "hs_code", "quantity_t", "source_id",
                  "source_reference", "period_basis", "coverage", "note")

BASE = "https://comtradeapi.un.org/public/v1/preview/C/%s/HS"
REPORTER = 586          # Pakistan
PARTNER = 0             # World
COMMODITY = "252310"    # cement clinker
FLOWS = {"M": "import", "X": "export"}
SOURCE_ID = "un_comtrade"
PACE_S = 6.0            # measured: six seconds between requests draws no 429
BACKOFF_S = 90.0

MANUAL = """
Nothing was written. To supply the earlier months by hand:

  1. Open https://comtradeplus.un.org/TradeFlow with reporter Pakistan (586),
     partner World, HS 252310, frequency Monthly, and the periods you need.
  2. Export the result and append rows to
     data/activity/ippu/clinker_trade_monthly.csv with columns:
       month, flow, hs_code, quantity_t, source_id, source_reference,
       period_basis, coverage, note
     using net weight in tonnes, one row per (month, flow) THAT THE SOURCE REPORTS.
     Do not write zero rows for months the source is silent about.
  3. Fetch the same years at annual frequency into
     data/activity/ippu/clinker_trade_annual_controls.csv so the silent months can be
     proved zero rather than assumed zero.

Only fiscal years whose twelve months are each either reported or annual-reconciled become
estimable; the rest stay NE against their registered gap, which is the correct outcome and
not a failure of this run.
"""


def _months(first, last):
    y, m = (int(p) for p in first.split("-"))
    ly, lm = (int(p) for p in last.split("-"))
    out = []
    while (y, m) <= (ly, lm):
        out.append("%04d%02d" % (y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _read(path):
    if not os.path.exists(path):
        return []
    return read_rows(path, comments=False)


RAW_SOURCE = "un_comtrade"


def _raw_name(frequency, period, flow_code):
    return "hs%s/%s_%s_%s.json" % (COMMODITY, frequency, flow_code, period)


def held_response(frequency, period, flow_code):
    """The path of the response already kept for this request, or None."""
    path = os.path.join(retention.RAW, RAW_SOURCE, _raw_name(frequency, period, flow_code))
    return path if os.path.exists(path) else None


def _records(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle).get("data") or []


def query(frequency, period, flow_code, timeout=60):
    """One request, one period. The response is kept, then the kept file is parsed.
    Returns the record list, or raises after one 429 retry."""
    params = {"reporterCode": REPORTER, "partnerCode": PARTNER, "cmdCode": COMMODITY,
              "flowCode": flow_code, "period": period}
    url = (BASE % frequency) + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
            json.loads(body.decode("utf-8"))      # a challenge page is not a response
            return _records(retention.keep(body, RAW_SOURCE,
                                           _raw_name(frequency, period, flow_code), url))
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 1:
                time.sleep(BACKOFF_S)
                continue
            raise
    return []


def check(first, last):
    """Ask the source again for every period of the window and compare with the held rows.
    Writes no table. A request whose response is already kept is read from the kept file."""
    held_m = {(r["month"], r["flow"]): r["quantity_t"] for r in _read(MONTHLY)
              if r["source_id"] == SOURCE_ID}
    held_a = {(r["calendar_year"], r["flow"]): r["quantity_t"] for r in _read(CONTROLS)
              if r["source_id"] == SOURCE_ID}
    wanted = _months(first, last)
    plan = [("M", p, f) for f in sorted(FLOWS) for p in wanted]
    plan += [("A", y, f) for f in sorted(FLOWS) for y in sorted({p[:4] for p in wanted})]
    agree, differ, absent, unreached = 0, [], [], []
    for frequency, period, flow_code in plan:
        kept = held_response(frequency, period, flow_code)
        try:
            data = _records(kept) if kept else query(frequency, period, flow_code)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as exc:
            unreached.append("%s %s %s: %s" % (frequency, flow_code, period, exc))
            time.sleep(PACE_S)
            continue
        if not kept:
            time.sleep(PACE_S)
        key = (("%s-%s" % (period[:4], period[4:])) if frequency == "M" else period,
               FLOWS[flow_code])
        table = held_m if frequency == "M" else held_a
        tonnes = _tonnes(data[0]) if data else None
        now = None if tonnes is None else "%d" % round(tonnes)
        if key not in table:
            if now is not None:
                absent.append("%s %s %s: the source reports %s t and the table holds no row"
                              % (frequency, key[1], key[0], now))
        elif now == table[key] or (now is None and table[key] == "0"):
            # a zero row in the table records the source's silence for that month (its note
            # says so); a silent response now is the same statement, not a disagreement
            agree += 1
        else:
            differ.append("%s %s %s: table %s t, source now %s"
                          % (frequency, key[1], key[0], table[key],
                             "silent" if now is None else now + " t"))
    for line in differ + absent + unreached:
        print("  ! %s" % line)
    print("check: %d held rows agree, %d differ, %d reported by the source and not held, "
          "%d requests unreached" % (agree, len(differ), len(absent), len(unreached)))
    return 1 if differ or unreached else 0


def _tonnes(record):
    """Net weight, in tonnes. `qty` carries the reported unit, which is not always weight;
    netWgt is the one quantity comparable across months."""
    for key in ("netWgt", "netWeight", "NetWeight"):
        value = record.get(key)
        if value not in (None, ""):
            return float(value) / 1000.0
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch HS 252310 clinker trade.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="re-ask every period, keep the responses, compare, write no table")
    parser.add_argument("--from", dest="first", default="2014-07")
    parser.add_argument("--to", dest="last", default="2024-12")
    args = parser.parse_args(argv)
    if args.check:
        return check(args.first, args.last)

    monthly = _read(MONTHLY)
    controls = _read(CONTROLS)
    held_months = {(r["month"], r["flow"]) for r in monthly}
    held_years = {(r["calendar_year"], r["flow"]) for r in controls}

    wanted = _months(args.first, args.last)
    years = sorted({p[:4] for p in wanted})
    todo = [(f, p) for f in sorted(FLOWS) for p in wanted
            if (("%s-%s" % (p[:4], p[4:])), FLOWS[f]) not in held_months]
    year_todo = [(f, y) for f in sorted(FLOWS) for y in years
                 if (y, FLOWS[f]) not in held_years]

    print("UN Comtrade HS %s, reporter %d, partner World" % (COMMODITY, REPORTER))
    print("  window:    %s to %s" % (args.first, args.last))
    print("  held:      %d month-flow rows, %d annual controls"
          % (len(held_months), len(held_years)))
    print("  to fetch:  %d monthly + %d annual requests (~%d min at %.0fs pacing)"
          % (len(todo), len(year_todo),
             round((len(todo) + len(year_todo)) * (PACE_S + 2.5) / 60.0), PACE_S))

    if args.dry_run:
        print("\n--dry-run: nothing requested, nothing written.")
        return 0

    new_months, new_controls, errors, silent = [], [], [], 0
    for flow_code, period in todo:
        flow = FLOWS[flow_code]
        try:
            data = query("M", period, flow_code)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as exc:
            errors.append("monthly %s %s: %s" % (flow, period, exc))
            time.sleep(PACE_S)
            continue
        time.sleep(PACE_S)
        if not data:
            # NOT a zero. The gate decides, from the annual control, whether this month is
            # an established zero or an unobtained one.
            silent += 1
            continue
        record = data[0]
        tonnes = _tonnes(record)
        if tonnes is None:
            errors.append("monthly %s %s: record carries no net weight" % (flow, period))
            continue
        new_months.append({
            "month": "%s-%s" % (period[:4], period[4:]), "flow": flow,
            "hs_code": COMMODITY, "quantity_t": "%d" % round(tonnes),
            "source_id": SOURCE_ID,
            "source_reference": "UN Comtrade public API; reporter 586, partner World, "
                                "flow %s" % flow_code,
            "period_basis": "calendar_month", "coverage": "national",
            "note": "Net weight, aggregate record; fetched by "
                    "scripts/fetch_comtrade_clinker.py",
        })

    for flow_code, year in year_todo:
        flow = FLOWS[flow_code]
        try:
            data = query("A", year, flow_code)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as exc:
            errors.append("annual %s %s: %s" % (flow, year, exc))
            time.sleep(PACE_S)
            continue
        time.sleep(PACE_S)
        if not data:
            errors.append("annual %s %s: the source returned no annual record, so the "
                          "silent months of this year cannot be proved zero" % (flow, year))
            continue
        tonnes = _tonnes(data[0])
        if tonnes is None:
            errors.append("annual %s %s: record carries no net weight" % (flow, year))
            continue
        new_controls.append({
            "calendar_year": year, "flow": flow, "hs_code": COMMODITY,
            "quantity_t": "%d" % round(tonnes), "source_id": SOURCE_ID,
            "source_reference": "UN Comtrade public API; reporter 586, partner World, "
                                "flow %s, annual frequency" % flow_code,
            "period_basis": "calendar_year", "coverage": "national",
            "note": "Annual control: the sum the monthly records must reach before a "
                    "silent month may be read as zero",
        })

    for line in errors[:40]:
        print("  ! %s" % line)
    if len(errors) > 40:
        print("  ! ... and %d more" % (len(errors) - 40))
    print("  returned: %d monthly records, %d annual controls, %d silent months"
          % (len(new_months), len(new_controls), silent))

    if not new_months and not new_controls:
        print("\nThe API returned nothing usable for the requested window.")
        print(MANUAL)
        return 1

    if new_months:
        rows = monthly + new_months
        rows.sort(key=lambda r: (r["flow"], r["month"]))
        with open(MONTHLY, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(MONTHLY_FIELDS))
            writer.writeheader()
            writer.writerows({k: r[k] for k in MONTHLY_FIELDS} for r in rows)
        print("wrote %s (%d rows, %d new)"
              % (os.path.relpath(MONTHLY, ROOT), len(rows), len(new_months)))
    if new_controls:
        rows = controls + new_controls
        rows.sort(key=lambda r: (r["flow"], r["calendar_year"]))
        with open(CONTROLS, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(CONTROL_FIELDS))
            writer.writeheader()
            writer.writerows({k: r[k] for k in CONTROL_FIELDS} for r in rows)
        print("wrote %s (%d rows, %d new)"
              % (os.path.relpath(CONTROLS, ROOT), len(rows), len(new_controls)))

    print("\nWhich fiscal years this closes is decided by the gate, not here:")
    print("  python3 -m pkinv.sectors.ippu.trade_evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main())

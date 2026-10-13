#!/usr/bin/env python3
"""Version-pin Pakistan WASTE source records from the public Climate TRACE v7 API.

WHY (rc13, the eighth review's waste item). The waste release-candidate registry
holds only the 56 OSM landfill polygons; Climate TRACE publishes source-level waste
assets (solid-waste-disposal sites, wastewater plants) that can seed MORE candidates
- as a COMPARATOR/CANDIDATE source, never ground truth, per the review's own
caveat. The fetch mirrors the aviation pinner: pinned subsectors, sidecar summary,
and on ANY failure it writes nothing and exits non-zero so a broken network can
never fabricate an empty candidate set.

Usage:  python3 scripts/fetch_climatetrace_waste.py [--delay S]
Writes: sources/ClimateTRACE/climatetrace_waste_PAK_*.json (+ _SUMMARY sidecar)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "sources" / "ClimateTRACE"
API = "https://api.climatetrace.org/v7"
SUBSECTORS = "solid-waste-disposal,domestic-wastewater-treatment-and-discharge"
GASES = ("ch4",)


def _get(path, params):
    url = API + path + "?" + urlencode(params)
    request = Request(url, headers={"User-Agent": "pkinv-waste/1.0"})
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def fetch(delay=0.05):
    rankings = []
    source_ids = set()
    for year in range(2021, 2025):
        for gas in GASES:
            response = _get("/sources", {"year": year, "gas": gas, "gadmId": "PAK",
                                         "subsectors": SUBSECTORS, "limit": 1000})
            rankings.append({"requested_year": year, "gas": gas,
                             "response": response})
            source_ids.update(int(row["id"]) for row in response)
            time.sleep(delay)
    details = []
    for source_id in sorted(source_ids):
        details.append(_get("/sources/%d" % source_id,
                            {"start": "2021-01", "end": "2024-12",
                             "timeGranularity": "month", "gas": "ch4"}))
        time.sleep(delay)
    return rankings, details


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=0.05)
    args = parser.parse_args()
    try:
        rankings, details = fetch(args.delay)
    except Exception as exc:                                   # noqa: BLE001
        print("Climate TRACE waste fetch FAILED (%s: %s); nothing written.\n"
              "Manual route: https://climatetrace.org/data, waste sector, "
              "Pakistan source inventory." % (type(exc).__name__, exc))
        return 1
    if not any(r["response"] for r in rankings):
        print("Climate TRACE returned no Pakistani waste sources; nothing "
              "written (an empty candidate set must never look fetched).")
        return 1
    DEST.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, value in (("climatetrace_waste_PAK_rankings_2021_2024.json", rankings),
                        ("climatetrace_waste_PAK_sources.json", details)):
        p = DEST / name
        p.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                     encoding="utf-8")
        paths[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    summary = {"api": API, "subsectors": SUBSECTORS, "gases": list(GASES),
               "ranking_years": "2021-2024", "source_count": len(details),
               "sha256": paths,
               "role": "comparator/candidate source for the waste release "
                       "registry - never ground truth (the review's own caveat)"}
    (DEST / "climatetrace_waste_PAK_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Climate TRACE waste: %d ranking pulls, %d sources -> %s"
          % (len(rankings), len(details), DEST))
    return 0


if __name__ == "__main__":
    sys.exit(main())

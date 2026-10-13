#!/usr/bin/env python3
"""Version-pin Pakistan aviation records from the public Climate TRACE v7 API."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "sources" / "Aviation"
API = "https://api.climatetrace.org/v7"
SUBSECTORS = "domestic-aviation,international-aviation"


def _get(path, params):
    url = API + path + "?" + urlencode(params)
    request = Request(url, headers={"User-Agent": "pkinv-aviation/1.0"})
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fetch(delay=0.05):
    national = []
    for year in range(2015, 2025):
        national.append({"requested_year": year, "response": _get(
            "/sources/emissions", {"year": year, "gas": "co2", "gadmId": "PAK",
                                    "subsectors": SUBSECTORS})})
        time.sleep(delay)
    rankings = []
    source_ids = set()
    for year in range(2021, 2025):
        response = _get("/sources", {"year": year, "gas": "co2", "gadmId": "PAK",
                                     "subsectors": SUBSECTORS, "limit": 1000})
        rankings.append({"requested_year": year, "response": response})
        source_ids.update(int(row["id"]) for row in response)
        time.sleep(delay)
    details = []
    for source_id in sorted(source_ids):
        details.append(_get("/sources/%d" % source_id,
                            {"start": "2021-01", "end": "2024-12",
                             "timeGranularity": "month", "gas": "co2"}))
        time.sleep(delay)
    _write(DEST / "climatetrace_aviation_PAK_2015_2024.json", national)
    _write(DEST / "climatetrace_rankings_PAK_2021_2024.json", rankings)
    _write(DEST / "climatetrace_airports_PAK_2021_2024.json", details)
    return {"national_years": len(national), "ranking_years": len(rankings),
            "airport_sources": len(details)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=0.05,
                        help="polite delay between requests in seconds")
    args = parser.parse_args()
    print(json.dumps(fetch(args.delay), sort_keys=True))


if __name__ == "__main__":
    main()

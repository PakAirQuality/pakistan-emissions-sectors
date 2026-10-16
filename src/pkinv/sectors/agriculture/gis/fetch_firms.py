"""Fetch NASA FIRMS VIIRS active-fire detections over Pakistan for the crop-residue
burning seasons, for use as the residue-burning spatial proxy.

The MAP_KEY is read from the FIRMS_MAP_KEY environment variable and is NEVER written to disk
or committed: the address recorded with each kept response carries {MAP_KEY} in its place.

EVERY RESPONSE IS KEPT (October 2026). Each window's CSV is written to
data/raw/firms/area_api/ before it is parsed (pkinv.core.retention). Until then only five
columns of each detection survived, in data/gis/manual/firms_fire.csv, and the responses they
were read from were gone. The nine back-fetched fiscal years predate this and have no kept
responses; scripts/fetch_firms_country_archive.py holds NASA's keyless country-year files as
their witness.

FIRMS area API note: DAY_RANGE is capped at 5, so seasons are covered in 5-day windows.
VIIRS_SNPP_SP (science-quality) archive covers 2012 -> ~2 months ago.

Usage:  FIRMS_MAP_KEY=xxxx python3 -m pkinv.sectors.agriculture.gis.fetch_firms
        [--season 2024-25]     # the nowcast stream's newer window, kept by name
        python3 -m pkinv.sectors.agriculture.gis.fetch_firms --from-country-archive 2024 [--check]
                               # rc69: a fiscal year from the held keyless country files
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import hashlib
import io
import json
import os
import sys
import urllib.request
from datetime import date, timedelta

from pkinv.paths import ROOT
from pkinv.core import retention
from pkinv.core.io import write_table

OUT_CSV = asset_path(ROOT, "data", "gis", "manual", "firms_fire.csv")
SIDECAR = asset_path(ROOT, "data", "gis", "manual", "FIRMS_SOURCES.json")
BBOX = "60.5,23.5,77.5,37.5"          # Pakistan west,south,east,north
SOURCE = "VIIRS_SNPP_SP"
STEP = 5                               # FIRMS DAY_RANGE max
# THE DEFAULT IS THE REPORTING PERIOD'S OWN SEASON (rc13, the eighth review's
# period-mismatch fix): FY2023-24's rice-stubble and wheat-residue windows. The
# previous constants pinned Oct 2024 - May 2025 - one full burning season, but
# not the one inside the reporting period - and that window survives as the
# named --season 2024-25 option because the NOWCAST stream legitimately wants
# the newest season while the INVENTORY wants the matched one.
SEASON_SETS = {
    "2023-24": [("rice", date(2023, 10, 20), date(2023, 12, 5)),
                ("wheat", date(2024, 4, 10), date(2024, 5, 31))],
    "2024-25": [("rice", date(2024, 10, 20), date(2024, 12, 5)),
                ("wheat", date(2025, 4, 10), date(2025, 5, 31))],
}
SEASONS = SEASON_SETS["2023-24"]
API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{src}/{bbox}/{days}/{start}"


def fetch_area(key, start, days, source=SOURCE, bbox=BBOX):
    """Fetch FIRMS active-fire detections for one date window (shared by fetch_firms +
    the nowcast stream). Returns a list of csv.DictReader rows. Raises on an API error string.

    days is capped at 5 by the FIRMS area API; source can be a near-real-time product
    (VIIRS_SNPP_NRT / VIIRS_NOAA20_NRT) for live use instead of the SP science archive.
    """
    url = API.format(key=key, src=source, bbox=bbox, days=days, start=start.isoformat())
    with urllib.request.urlopen(url, timeout=90) as r:
        body = r.read()
    if not body.startswith(b"latitude"):       # error string, not CSV
        raise RuntimeError(body.decode("utf-8", "replace").strip()[:120])
    kept = retention.keep(
        body, "firms", "area_api/%s/%s_%s_%dd.csv" % (source, bbox.replace(",", "_"),
                                                     start.isoformat(), days),
        API.format(key="{MAP_KEY}", src=source, bbox=bbox, days=days,
                   start=start.isoformat()))
    with open(kept, encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def _fetch(key, start, days):
    return fetch_area(key, start, days)


def _fetch_spans(fy_start):
    """The distinct 5-day fetch spans one fiscal year's crop windows cover.

    The per-crop windows overlap heavily (four crops harvest Sep-Dec), so the FETCH
    is over their union - the API is asked for each day once - while attribution
    keeps the per-crop boundaries (burn_windows.in_window)."""
    from pkinv.sectors.agriculture import burn_windows
    spans = sorted((s, e) for _crop, s, e in burn_windows.windows(fy_start))
    merged = []
    for start, end in spans:
        if merged and start <= merged[-1][1] + timedelta(days=1):
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _existing():
    """(rows, fetched-window keys) already held, so a re-run never re-asks or drops."""
    rows, fetched = [], set()
    if os.path.exists(OUT_CSV):
        rows = list(_activity_rows(OUT_CSV, comments=False))
    if os.path.exists(SIDECAR):
        with open(SIDECAR, encoding="utf-8") as f:
            fetched = set(tuple(w) for w in json.load(f).get("windows_fetched", []))
    return rows, fetched


COUNTRY_FILE = os.path.join(retention.RAW, "firms", "country_archive",
                            "viirs-snpp_%d_Pakistan.csv")


def country_archive_rows(fy_start):
    """The fiscal year's window rows from NASA's keyless country-year files (rc69).

    The same VIIRS S-NPP standard product as the area API, for Pakistan only: every
    country-file detection inside the fetched windows of FY2015-16..FY2023-24 is in this
    layer (scripts/fetch_firms_country_archive.py, 100 percent). A year the MAP_KEY route
    never reached can therefore be filled from held files without a key. Attribution keeps
    Pakistan detections only, so the box outside Pakistan, which these files lack, never
    enters the burning stream. Rows keep the fetch's five columns and its fyYYYY label."""
    rows, seen = [], set()
    for start, end in _fetch_spans(fy_start):
        for year in sorted({start.year, end.year}):
            path = COUNTRY_FILE % year
            if not os.path.exists(path):
                raise FileNotFoundError("%s is not held; keep it first with "
                                        "scripts/fetch_firms_country_archive.py --years %d"
                                        % (path, year))
            with open(path, encoding="utf-8", newline="") as handle:
                for r in csv.DictReader(handle):
                    when = date.fromisoformat(r["acq_date"])
                    k = (r["latitude"], r["longitude"], r["acq_date"])
                    if start <= when <= end and k not in seen:
                        seen.add(k)
                        rows.append({"latitude": r["latitude"], "longitude": r["longitude"],
                                     "acq_date": r["acq_date"], "frp": r["frp"],
                                     "confidence": r["confidence"],
                                     "season": "fy%d" % fy_start})
    return rows


def extend_from_country_archive(fy_start, check=False):
    """Append one fiscal year's windows from the held country files; --check compares."""
    rows, fetched = _existing()
    label = "fy%d" % fy_start
    fresh = country_archive_rows(fy_start)
    held = [r for r in rows if r["season"] == label]
    if check:
        same = [tuple(r[c] for c in sorted(r)) for r in held] == \
               [tuple(r[c] for c in sorted(r)) for r in fresh]
        print("%s: %d rows held, %d from the country files, %s"
              % (label, len(held), len(fresh), "identical" if same else "DIFFERENT"))
        return 0 if same else 1
    seen = {(r["latitude"], r["longitude"], r["acq_date"]) for r in rows if r["season"] != label}
    rows = [r for r in rows if r["season"] != label]
    rows += [r for r in fresh if (r["latitude"], r["longitude"], r["acq_date"]) not in seen]
    windows = [(label, s.isoformat(), e.isoformat()) for s, e in _fetch_spans(fy_start)]
    fetched |= set(windows)
    write_table(OUT_CSV, ["latitude", "longitude", "acq_date", "frp", "confidence", "season"],
                rows)
    with open(OUT_CSV, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    with open(SIDECAR, encoding="utf-8") as f:
        sidecar = json.load(f)
    by_archive = set(tuple(w) for w in sidecar.get("windows_from_country_archive", []))
    by_archive |= set(windows)
    sidecar.update({"windows_fetched": sorted(fetched), "detections": len(rows),
                    "csv_sha256": sha,
                    "windows_from_country_archive": sorted(by_archive),
                    "country_archive_note":
                        "windows listed here were filled without a key from NASA's "
                        "country-year files held in data/raw/firms/country_archive/ - the "
                        "same VIIRS S-NPP standard product, Pakistan only (the box outside "
                        "Pakistan is absent for them); see fetch_firms.country_archive_rows"})
    with open(SIDECAR, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, sort_keys=True)
    print("%s: %d rows from the country files; layer now %d detections"
          % (label, len(fresh), len(rows)))
    return 0


def main():
    if "--from-country-archive" in sys.argv:
        fy = int(sys.argv[sys.argv.index("--from-country-archive") + 1])
        return extend_from_country_archive(fy, check="--check" in sys.argv)
    key = os.environ.get("FIRMS_MAP_KEY")
    if not key:
        sys.exit("Set FIRMS_MAP_KEY (never committed): FIRMS_MAP_KEY=xxxx python3 -m pkinv.sectors.agriculture.gis.fetch_firms")
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)

    # Three modes: the named season sets (back-compat, the nowcast stream's route);
    # --backfetch YYYY for one fiscal year's FAO-derived windows; --backfetch-all
    # for every inventory year. The windows come from burn_windows, the same
    # derivation attribution uses, so a detection can never sit in a window the
    # fetch did not cover.
    if "--backfetch-all" in sys.argv:
        years = list(range(2015, 2024))
        jobs = [("fy%d" % fy, s, e) for fy in years for s, e in _fetch_spans(fy)]
    elif "--backfetch" in sys.argv:
        fy = int(sys.argv[sys.argv.index("--backfetch") + 1])
        jobs = [("fy%d" % fy, s, e) for s, e in _fetch_spans(fy)]
    else:
        season_key = "2023-24"
        if "--season" in sys.argv:
            season_key = sys.argv[sys.argv.index("--season") + 1]
        jobs = SEASON_SETS[season_key]

    rows, fetched_windows = _existing()
    seen = {(r["latitude"], r["longitude"], r["acq_date"]) for r in rows}
    added = failed = 0
    for name, start, end in jobs:
        window_key = (name, start.isoformat(), end.isoformat())
        if window_key in fetched_windows:
            continue
        window_ok = True
        d = start
        while d <= end:
            span = min(STEP, (end - d).days + 1)
            try:
                recs = _fetch(key, d, span)
            except Exception as e:
                print("  %s %s(+%dd): FAILED (%s)" % (name, d, span, e), flush=True)
                window_ok = False
                failed += 1
                d += timedelta(days=span)
                continue
            for r in recs:
                k = (r["latitude"], r["longitude"], r["acq_date"])
                if k in seen:
                    continue
                seen.add(k)
                rows.append({"latitude": r["latitude"], "longitude": r["longitude"],
                             "acq_date": r["acq_date"], "frp": r.get("frp", ""),
                             "confidence": r.get("confidence", ""),
                             # the season column carries the FETCH label; per-crop
                             # attribution happens against burn_windows at use
                             "season": name})
                added += 1
            d += timedelta(days=span)
        if window_ok:
            fetched_windows.add(window_key)
        print("  %-8s %s..%s done (%d rows so far)" % (name, start, end, len(rows)),
              flush=True)

    if not rows:
        sys.exit("FIRMS returned zero detections across every window; nothing "
                 "written (an empty fire layer must never look fetched)")
    write_table(OUT_CSV, ["latitude", "longitude", "acq_date", "frp",
                                          "confidence", "season"], rows)
    with open(OUT_CSV, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    with open(SIDECAR, "w", encoding="utf-8") as f:
        json.dump({"product": SOURCE, "bbox": BBOX,
                   "windows_fetched": sorted(fetched_windows),
                   "detections": len(rows), "csv_sha256": sha,
                   "note": "science-quality VIIRS SP archive; the MAP_KEY is an env "
                           "var, never committed; windows derive from the FAO "
                           "calendar (burn_windows.py) since Wave 3; a window is "
                           "recorded fetched only when every span in it succeeded"},
                  f, indent=2, sort_keys=True)
        f.write("\n")
    print("firms_fire.csv: %d detections (+%d this run, %d failed spans; sha256 %s...)"
          % (len(rows), added, failed, sha[:12]))


if __name__ == "__main__":
    raise SystemExit(main())

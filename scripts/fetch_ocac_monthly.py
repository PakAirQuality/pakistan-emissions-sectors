"""Fetch OCAC's monthly sector x product x province petroleum reports, July 2021 - June 2024.

WHY THIS EXISTS. The OCAC customer-class panel is the single most load-bearing monthly series
in this inventory: it times road transport, railways, domestic aviation, industrial liquid
fuels and liquid-fuel power. Three fiscal years of it are public and were not held.

HOW IT FINDS THEM, and why the obvious route fails. The statistics page lists only the newest
month, and the archive path a reviewer cited (/full-statistics/) is a 404. The files are in
the WordPress media library, and its REST endpoint answers without authentication:

    /wp-json/wp/v2/media?search=Pak-Provinces&per_page=100&page=N

Two traps in the filenames, both real and both silent if unhandled:

  * THE MONTH IS SPELLED TWO WAYS. "Jun-2024-Pak-Provinces.pdf" and
    "December-2023-Pak-Provinces-2.pdf" are the same series. Matching only the three-letter
    form finds about a third of the window and looks like a coverage gap rather than a
    parsing bug.
  * THE -N SUFFIX IS A REVISION, NOT A DUPLICATE. WordPress appends -1, -2, -4 when a file is
    re-uploaded under a name already taken, which for this publisher means the month was
    restated. The HIGHEST suffix is the current one, and taking the unsuffixed file - the
    natural reading - silently prefers the superseded first upload. Every downloaded row
    records which revision it is, and the alternatives are recorded rather than discarded.

The upload folder is NOT the report month: every file sits under /uploads/2022/05/ regardless
of the month it reports, so a URL pattern built from the report date resolves for exactly the
months whose name happens to match and 404s for the rest. That was measured, not assumed - a
first attempt at pattern construction found 4 of 36.

Usage:  python3 scripts/fetch_ocac_monthly.py [--out data/raw/ocac/monthly_sector_province]
Writes: the PDFs, plus a manifest row per file with its sha256 and revision.
"""

from pkinv.assets import asset_path
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request

API = ("https://www.ocac.org.pk/wp-json/wp/v2/media"
       "?search=Pak-Provinces&per_page=100&page=%d")
UA = "Mozilla/5.0 (research; PakEmis-GHG national inventory)"

# The reviewer's window: July 2021 through June 2024, the months OCAC publishes openly.
FIRST, LAST = (2021, 7), (2024, 6)

MONTHS = {"jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
          "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
          "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
          "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12}

DEFAULT_OUT = asset_path("data", "raw", "ocac", "monthly_sector_province")


def _get(url, retries=3):
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except Exception as error:                                  # noqa: BLE001
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
            print("    retry %d after %s" % (attempt + 1, type(error).__name__))
    return None


def media_urls():
    """Every media URL the search returns, across pages."""
    out, page = [], 1
    while page <= 8:
        try:
            batch = json.loads(_get(API % page))
        except Exception as error:                                  # noqa: BLE001
            print("  media page %d failed: %s" % (page, error))
            break
        if not batch:
            break
        out += [item["source_url"] for item in batch]
        page += 1
    return out


def _ym(year, month):
    return year * 12 + month


def in_window(year, month):
    return _ym(*FIRST) <= _ym(year, month) <= _ym(*LAST)


def resolve(urls):
    """{(year, month): (url, revision, [superseded urls])} - highest revision wins."""
    import re
    found = {}
    for url in urls:
        name = url.rsplit("/", 1)[-1]
        # THE FILENAME IS NOT ONE PATTERN. The maintainer's bundle turned up two editions this
        # regex had silently skipped - "New-June-2023-Pak-Provinces.pdf" and
        # "Sectoral-Sales-Consumption-April-2022-Pakistan-Provinces.pdf" - because it demanded
        # the month at the START and "Pak-Provinces" at the end. Both proved to be alternate
        # uploads whose national controls match the editions already held, so nothing shipped
        # was wrong; what was wrong is that a name the publisher uses could not be seen at all,
        # and the next one might be a restatement rather than a duplicate.
        #
        # So the month and year are found ANYWHERE in the name, and the fixed tail is optional.
        match = re.match(r"^(?:New-|Sectoral-Sales-\S*?-)?([A-Za-z]+)-(\d{4})"
                         r"[-A-Za-z]*?(?:-(\d+))?\.pdf$", name)
        if not match:
            continue
        month = MONTHS.get(match.group(1).lower())
        year = int(match.group(2))
        if not month or not in_window(year, month):
            continue
        revision = int(match.group(3)) if match.group(3) else 0
        key = (year, month)
        if key not in found or revision > found[key][1]:
            previous = found.get(key)
            found[key] = (url, revision, (previous[2] + [previous[0]]) if previous else [])
        else:
            found[key][2].append(url)
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    print("querying the OCAC media library")
    urls = media_urls()
    print("  %d media entries" % len(urls))
    found = resolve(urls)

    expected = [(y, m) for y in range(2021, 2025) for m in range(1, 13)
                if in_window(y, m)]
    missing = [k for k in expected if k not in found]
    print("  %d of %d target months resolved; %d missing"
          % (len(found), len(expected), len(missing)))
    for year, month in missing:
        print("    MISSING %04d-%02d" % (year, month))

    manifest, failures = [], []
    for (year, month) in sorted(found):
        url, revision, superseded = found[(year, month)]
        local = asset_path(args.out, "ocac_sector_province_%04d_%02d.pdf" % (year, month))
        if os.path.exists(local):
            print("  have %04d-%02d" % (year, month))
        else:
            try:
                body = _get(url)
            except Exception as error:                              # noqa: BLE001
                print("  FAILED %04d-%02d %s" % (year, month, error))
                failures.append((year, month, url, str(error)[:120]))
                continue
            with open(local, "wb") as handle:
                handle.write(body)
            print("  got  %04d-%02d  %7d bytes  rev %d" % (year, month, len(body), revision))
            time.sleep(0.4)
        digest = hashlib.sha256(open(local, "rb").read()).hexdigest()
        manifest.append({
            "source_id": "ocac_sector_province_%04d_%02d" % (year, month),
            "local_path": local,
            "original_filename": url.rsplit("/", 1)[-1],
            "source_url": url,
            "sha256": digest,
            "coverage_start": "%04d-%02d-01" % (year, month),
            "coverage_end": "%04d-%02d" % (year, month),
            "revision_status": "revision-%d" % revision if revision else "first-upload",
            "superseded_urls": ";".join(superseded),
        })

    out_manifest = asset_path(args.out, "_fetch_manifest.json")
    with open(out_manifest, "w", encoding="utf-8") as handle:
        json.dump({"fetched": manifest, "missing": missing, "failures": failures},
                  handle, indent=1)
    print("\n%d files present, %d failures -> %s"
          % (len(manifest), len(failures), out_manifest))
    revised = [m for m in manifest if m["revision_status"] != "first-upload"]
    if revised:
        print("%d months are RESTATEMENTS; the superseded upload is recorded, not deleted:"
              % len(revised))
        for m in revised:
            print("   %s %s" % (m["source_id"][-7:], m["revision_status"]))
    return 1 if (missing or failures) else 0


if __name__ == "__main__":
    sys.exit(main())

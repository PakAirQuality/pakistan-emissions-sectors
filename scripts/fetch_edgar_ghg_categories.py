"""Try to fetch EDGAR's category-resolved GHG product for Pakistan's 1.A.3 rows.

WHAT THIS WOULD IMPROVE. The paper claims EDGAR's Pakistani "Transport" aggregate covers
road, rail and civil aviation and contains no navigation row. That claim currently rests
on EDGAR's category-resolved AIR-POLLUTANT files (v8.1), because the GHG booklet publishes
sector aggregates with no IPCC split - a different release from the booklet the benchmark
value comes from. The inference is declared as inference everywhere it appears, but direct
GHG category data would retire the caveat.

THE FAILURE CONTRACT, WHICH MATTERS MORE THAN THE SUCCESS PATH. If no candidate product
resolves, this script prints what to download by hand, writes NOTHING, touches NOTHING,
and exits non-zero. In particular it must never synthesise a GHG category split from the
air-pollutant split: the two releases' category shares are not the same quantity, and
asserting otherwise would be exactly the "a match against a benchmark is not provenance"
failure this inventory documents elsewhere. A missing file is a declared caveat; an
invented one is a fabricated result.

Usage:  python3 scripts/fetch_edgar_ghg_categories.py [--dry-run]
Writes: data/activity/transport/edgar_pak_ghg_categories.csv  (only on success)
"""

from pkinv.assets import asset_path
import hashlib
import io
import os
import sys
import urllib.error
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = asset_path(ROOT, "data", "activity", "transport",
                   "edgar_pak_ghg_categories.csv")

# Ordered by preference: newest release first. EDGAR reorganises its download paths
# between releases, so several plausible layouts are probed rather than one.
CANDIDATES = (
    ("EDGAR v8.0 GHG, IPCC-coded, CO2 excl short-cycle",
     "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/v80_FT2022_GHG/"
     "EDGARv8.0_FT2022_GHG_CO2_1970_2022.zip"),
    ("EDGAR v8.0 GHG, IPCC-coded, CH4",
     "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/v80_FT2022_GHG/"
     "EDGARv8.0_FT2022_GHG_CH4_1970_2022.zip"),
    ("EDGAR v8.0 GHG, IPCC-coded, N2O",
     "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/v80_FT2022_GHG/"
     "EDGARv8.0_FT2022_GHG_N2O_1970_2022.zip"),
)

MANUAL = """
Nothing was written. To supply the direct GHG category evidence by hand:

  1. Open https://edgar.jrc.ec.europa.eu/dataset_ghg2024 (or the current GHG release).
  2. Download the per-substance files that carry an IPCC 2006 code column
     (CO2, CH4 and N2O; the "by sector and country" products, not the booklet).
  3. Place the archives under sources/EDGAR/ and re-run this script with the
     directory as an argument, or extract the Pakistani 1.A.3.* rows into
     data/activity/transport/edgar_pak_ghg_categories.csv with columns:
       ipcc_code_2006, mode, substance, year, value_Gg, present, release,
       source_file, source_sha256, caveat

Until then the scope inference continues to rest on the v8.1 air-pollutant category
files, which is what the paper, data/benchmarks.csv and
data/activity/transport/edgar_pak_transport_categories.csv all say it rests on.
"""


def probe(url, timeout=30):
    """HEAD-ish probe: returns (ok, status_or_error)."""
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, r.status
    except urllib.error.HTTPError as e:
        return False, "HTTP %s" % e.code
    except (urllib.error.URLError, OSError) as e:
        return False, str(e.reason if hasattr(e, "reason") else e)


def download(url, timeout=300):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    dry = "--dry-run" in argv

    print("Probing EDGAR category-resolved GHG products:")
    reachable = []
    for label, url in CANDIDATES:
        ok, status = probe(url)
        print("  %-52s %s" % (label, "OK" if ok else "unavailable (%s)" % status))
        if ok:
            reachable.append((label, url))

    if dry:
        print("\n--dry-run: %d of %d candidates reachable; nothing fetched."
              % (len(reachable), len(CANDIDATES)))
        return 0 if reachable else 1

    if not reachable:
        print("\nNo candidate product resolved.")
        print(MANUAL)
        return 1

    # Success path: download, verify the archive actually carries an IPCC code column,
    # and only then write. A file that downloads but has the wrong schema is a failure,
    # not a partial success.
    for label, url in reachable:
        try:
            blob = download(url)
        except (urllib.error.URLError, OSError) as e:
            print("  %s: download failed (%s)" % (label, e))
            continue
        digest = hashlib.sha256(blob).hexdigest()
        try:
            zf = zipfile.ZipFile(io.BytesIO(blob))
        except zipfile.BadZipFile:
            print("  %s: not a zip archive; skipping" % label)
            continue
        names = [n for n in zf.namelist() if n.lower().endswith((".xlsx", ".csv"))]
        print("  %s: %d data members, sha256 %s" % (label, len(names), digest[:12]))
        print("\nA candidate resolved, but writing the extract needs the schema to be "
              "confirmed against the actual member layout - EDGAR's column names differ "
              "between releases. Inspect the archive and extend this script's parser "
              "before it writes anything; nothing was written.")
        return 1

    print(MANUAL)
    return 1


if __name__ == "__main__":
    sys.exit(main())

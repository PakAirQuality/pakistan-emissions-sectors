"""Acquire EDGAR v8.1 gridded SO2 (0.1 degree, annual) for the Lahore district comparison.

WHY. The release's Lahore SO2 curve falls 54 % across nine years, and the decomposition
(outputs/pakemis_air_lahore_so2_attribution.csv) shows the fall is carried by two NATIONAL fuel
series spread onto the district by patterns that never move - a kiln frame and a flat provincial
share - plus one declared fuel-specification step. Nothing in that chain is an observation of
Lahore, so nothing inside this repository can test it. EDGAR is the one external compilation held
or obtainable that resolves a district: 0.1 degree cells, about four of them across Lahore, built
from its own proxies rather than our kiln survey.

WHAT IS FETCHED. Annual global NetCDF gridmaps, calendar 2015-2022 (EDGAR v8.1 ends at 2022), for
TOTALS and EVERY sector, so that the comparison never reads a sector by leftover and TOTALS
decomposes completely.

THE CROSSWALK, AND THE ERROR IT CORRECTS. An earlier version of this file said "NMM is where EDGAR
books brick and cement kilns". That is wrong and it produced a wrong finding. EDGAR's sector codes
follow the IPCC 2006 categories:

  IND      1.A.2      COMBUSTION for manufacturing - and kiln FUEL is combustion, so this is the
                      counterpart for brick-kiln coal, cement-kiln coal and industrial furnace oil
  NMM      2.A.1      non-metallic mineral PROCESS emissions - clinker calcination, not fuel
  ENE      1.A.1.a    power industry (the annual code; the monthly bulk grouping is broader and
                      may carry autoproducers, which is why both are fetched)
  TRO      1.A.3.b    road transport
  RCO      1.A.4      residential and commercial
  REF_TRF  1.A.1.b/c  refineries and other transformation
  CHE/IRO/NFE  2.B/2.C  chemical, iron and steel, non-ferrous process
  PRO_FFF  1.B        fuel exploitation
  AWB      3.F        agricultural waste burning
  SWD_INC  4.C        waste incineration

The check that this crosswalk is right is arithmetic, not reading: the IND grid summed over
Pakistan reproduces EDGAR's OWN published 1.A.2 country total, and NMM reproduces 2.A.1. The
comparison product asserts exactly that, per year, and a test holds it.

MONTHLY, FOR EXACT FISCAL YEARS. Eight calendar years are not eight July-June years. EDGAR's
monthly grids run through December 2022, so the last complete fiscal year obtainable exactly is
FY2021-22. Two monthly bulk groupings are fetched: bkl_POWER_INDUSTRY (28 MB) and
bkl_IND_COMBUSTION (332 MB). bkl_TRANSPORT is 4.15 GB and is NOT fetched - the road comparison is
already decided by a factor of sixty at annual resolution and monthly precision cannot move it;
that omission is a logged row, not a silence.

A comparison input, never an activity and never a residual to insert. Nothing downstream of this
is read back into any register.

Every attempt is logged to data/raw/ACQUISITION_LOG_industrial_air.csv, hits and negatives alike.
Re-running is safe: a file already held with a non-zero size is skipped and not re-logged.
"""

from pkinv.assets import asset_path
import csv
import hashlib
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = ("https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/"
        "v81_FT2022_AP_new/SO2")
DEST = asset_path(ROOT, "data", "raw", "edgar", "gridmaps")
MONTHLY_DEST = asset_path(ROOT, "data", "raw", "edgar", "gridmaps_monthly")
LOG = asset_path(ROOT, "data", "raw", "ACQUISITION_LOG_industrial_air.csv")
STREAMS = ("TOTALS", "ENE", "IND", "NMM", "TRO", "RCO", "REF_TRF", "CHE", "IRO", "NFE",
           "PRO_FFF", "AWB", "SWD_INC", "FOO_PAP", "TNR_Other", "TNR_Ship",
           "TNR_Aviation_CDS", "TNR_Aviation_CRS", "TNR_Aviation_LTO")
# TNR_Aviation_SPS (supersonic) is published for some species but 404s for SO2 in
# every year 2015-2022: EDGAR carries no supersonic SO2. A real absence, logged as
# not-fetched in the acquisition log rather than silently dropped.
# the monthly bulk groupings, whole-archive zips covering 2000-2022
MONTHLY = ("bkl_POWER_INDUSTRY", "bkl_IND_COMBUSTION")
YEARS = tuple(range(2015, 2023))
SOURCE = "EDGAR v8.1 AP gridmaps"
NOTE = ("0.1 degree annual gridded SO2 for the Lahore district comparison; "
        "a comparison input, never an activity")


def url_for(stream, year):
    name = "v8.1_FT2022_AP_SO2_%d_%s_emi_nc.zip" % (year, stream)
    return "%s/%s/emi_nc/%s" % (BASE, stream, name), name


def monthly_url_for(grouping):
    """The monthly bulk groupings sit beside the annual tree, not inside the species folder."""
    name = "%s_emi_nc.zip" % grouping
    root = BASE.rsplit("/", 1)[0]
    return "%s/monthly/SO2/%s/%s" % (root, grouping, name), name


def sha16(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def log_rows(rows):
    with open(LOG, "a", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)


def fetch(url, path):
    request = urllib.request.Request(url, headers={"User-Agent": "pakemis-acquisition/1.0"})
    with urllib.request.urlopen(request, timeout=180) as response, open(path, "wb") as out:
        while True:
            block = response.read(1 << 20)
            if not block:
                break
            out.write(block)


def main():
    os.makedirs(DEST, exist_ok=True)
    os.makedirs(MONTHLY_DEST, exist_ok=True)
    today = time.strftime("%Y-%m-%d")
    rows, failures = [], 0
    jobs = [(url_for(s, y), DEST) for s in STREAMS for y in YEARS]
    jobs += [(monthly_url_for(g), MONTHLY_DEST) for g in MONTHLY]
    for (url, name), dest in jobs:
        path = asset_path(dest, name)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            print("held      %s" % name, flush=True)
            continue
        try:
            fetch(url, path)
        except (urllib.error.URLError, OSError) as exc:
            failures += 1
            if os.path.exists(path):
                os.remove(path)
            print("FAILED    %s: %s" % (name, exc), flush=True)
            rows.append([today, SOURCE, url, "", "", "", "not-fetched", "%s; %s" % (NOTE, exc)])
            continue
        size = os.path.getsize(path)
        rows.append([today, SOURCE, url, os.path.relpath(path, ROOT), sha16(path), size,
                     "fetched", NOTE])
        print("fetched   %s  %d bytes" % (name, size), flush=True)
    if rows:
        log_rows(rows)
    print("\n%d logged, %d failed" % (len(rows), failures), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

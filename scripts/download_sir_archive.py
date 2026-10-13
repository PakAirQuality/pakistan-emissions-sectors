"""The whole Detail-of-Generation archive, downloaded and hashed - Pass 2, Wave 1.

WHY THE WHOLE ARCHIVE. rc21 parsed the listing sheets and fetched a 68-document
verification sample; the sixteenth review's Pass-2 program makes the full corpus a
durable evidence asset: the daily reports are the arbitration instrument for every
future discrepancy, the FY2021-22 fuel-identity record, and the only per-plant grain
the archive serves. Acquisition runs ahead of parsing by design - documents are
immutable once fetched, content-hashed, and typed in the document manifest; parse
status advances separately and later.

RESUMABLE AND HONEST. A file already on disk is never re-fetched (immutability rule);
a failed fetch is recorded and retried on the next run rather than aborting the
campaign; every landed file is hashed by the manifest builder
(scripts/build_power_month_manifest.py derives download_status/parse_status/sha256
from the tree, so the manifest cannot claim a document the tree does not hold).

Usage:  python3 scripts/download_sir_archive.py [--limit N] [--delay SECONDS]
Stores: data/raw/nepra/sir_detail/daily_reports/<FY>/<plant_dir>/<file>
Writes: outputs/sir_archive_download_log.csv (per-run outcomes, appended)
"""

from pkinv.assets import asset_path
import argparse
import csv
import datetime
import os
import shutil
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = asset_path(ROOT, "data", "manifests", "power_sir_document_manifest.csv")
STORE = asset_path(ROOT, "data", "raw", "nepra", "sir_detail", "daily_reports")
LOG = asset_path(ROOT, "outputs", "sir_archive_download_log.csv")


def local_path(row):
    url = row["url"]
    name = urllib.parse.unquote(url.rsplit("/", 1)[1])
    plant_dir = urllib.parse.unquote(url.rsplit("/", 2)[1])
    fy = int(row["fiscal_year_start"])
    label = "FY%d-%02d" % (fy, (fy + 1) % 100)
    return asset_path(STORE, label, plant_dir, name)


def fetch(url, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=120) as response, \
            open(path + ".part", "wb") as handle:
        shutil.copyfileobj(response, handle)
    os.replace(path + ".part", path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download the SIR daily-report archive.")
    parser.add_argument("--limit", type=int, default=0, help="stop after N fetches")
    parser.add_argument("--delay", type=float, default=0.7, help="seconds between fetches")
    args = parser.parse_args(argv)

    with open(MANIFEST, newline="", encoding="utf-8") as handle:
        docs = list(csv.DictReader(handle))
    pending = [d for d in docs if not os.path.exists(local_path(d))]
    print("%d documents in the manifest; %d already held; %d to fetch"
          % (len(docs), len(docs) - len(pending), len(pending)), flush=True)

    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    new_log = not os.path.exists(LOG)
    fetched = failed = 0
    with open(LOG, "a", newline="", encoding="utf-8") as log:
        writer = csv.writer(log)
        if new_log:
            writer.writerow(["fetched_at_utc", "url", "outcome", "detail"])
        for row in pending:
            if args.limit and fetched >= args.limit:
                break
            path = local_path(row)
            stamp = datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
            try:
                fetch(row["url"], path)
                fetched += 1
                writer.writerow([stamp, row["url"], "downloaded",
                                 os.path.getsize(path)])
            except Exception as error:  # noqa: BLE001 - recorded, campaign continues
                failed += 1
                if os.path.exists(path + ".part"):
                    os.remove(path + ".part")
                writer.writerow([stamp, row["url"], "failed", str(error)[:200]])
            if (fetched + failed) % 100 == 0:
                log.flush()
                print("  progress: %d fetched, %d failed, %d remaining"
                      % (fetched, failed, len(pending) - fetched - failed), flush=True)
            time.sleep(args.delay)
    print("done: %d fetched, %d failed this run" % (fetched, failed), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

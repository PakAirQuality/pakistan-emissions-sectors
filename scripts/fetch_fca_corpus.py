"""The NEPRA FCA determination corpus for the pre-sheet years, acquired and typed.

WHAT THIS IS AND IS NOT. FY2015-16 and FY2016-17 have no machine-readable plant-month
generation record anywhere on nepra.org.pk - the Detail-of-Generation listing sheets
404 at every spelling before FY2017-18. What exists is the monthly Fuel Charges
Adjustment determination corpus: scanned PDFs whose plant-wise annex appears only in a
subset of 2016 months, whose OCR corrupts digits, and whose coverage misses one to two
months of each fiscal year outright. That corpus cannot build a twelve-month shape
today, and this script deliberately does NOT parse it. It does what Pass 2's
acquisition rule requires: fetch the documents while they are served, hash them
immutably, and type each one in a manifest - so the parse decision is made against
held evidence, and the refusal to parse is a row, not a silence.

DISCOVERY IS THE INDEX PAGES, NOT URL PATTERNS. Directory listings are 403 and the
filenames carry no derivable convention ("TRF-100 MFPA FCA Feb-2016 04-04-2016
4271-89.PDF" beside "TRF-100 MFPA FCA XWDISCOs 07-08-2020 20257-74 .PDF"), so the two
authoritative manifests are the DISCO tariff page (any one lists the shared Ex-WAPDA
archive; LESCO is used) and the K-Electric tariff page.

Usage:  python3 scripts/fetch_fca_corpus.py [--dry-run] [--limit N]
Stores: data/raw/nepra/fca/<lane>/<year>/<file>.PDF
Writes: data/manifests/fca_document_manifest.csv
"""

from pkinv.assets import asset_path
import argparse
import csv
import hashlib
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = asset_path(ROOT, "data", "raw", "nepra", "fca")
MANIFEST = asset_path(ROOT, "data", "manifests", "fca_document_manifest.csv")

INDEXES = {
    "xwdisco": "https://nepra.org.pk/tariff/Distribution%20LESCO.php",
    "ke": "https://nepra.org.pk/tariff/Distribution%20K-Electric.php",
}
# The corpus slices Pass 2 wants held: the two pre-sheet fiscal years' XWDISCO
# determinations (calendar folders 2015-2017 cover FY2015-16 and FY2016-17), the 2020
# folder (the Nov19-Jun20 combined COVID determination), and the K-Electric corpus
# through the KE combined docs (2015-2021).
WANT = {
    "xwdisco": ("/Tariff/Ex-WAPDA%20DISCOS/2015/", "/Tariff/Ex-WAPDA%20DISCOS/2016/",
                "/Tariff/Ex-WAPDA%20DISCOS/2017/", "/Tariff/Ex-WAPDA%20DISCOS/2020/",
                "/Tariff/DISCOs/Ex-WAPDA%20DISCOS/"),
    "ke": ("/Tariff/KESC/2015/", "/Tariff/KESC/2016/", "/Tariff/KESC/2017/",
           "/Tariff/KESC/2018/", "/Tariff/KESC/2019/", "/Tariff/KESC/2020/",
           "/Tariff/KESC/2021/"),
}
FIELDS = ("lane", "document", "url", "sha256", "bytes", "fetched_at_utc",
          "annex_kind", "parse_status", "note")


def _fetch(url, binary=False):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        blob = response.read()
    return blob if binary else blob.decode("utf-8", "replace")


def discover():
    """[(lane, absolute url)] for every wanted determination, from the index pages."""
    out = []
    for lane, index_url in INDEXES.items():
        page = _fetch(index_url)
        hrefs = set(re.findall(r'href="([^"]+\.(?:PDF|pdf))"', page))
        for href in sorted(hrefs):
            absolute = urllib.parse.urljoin(index_url, href)
            quoted = urllib.parse.quote(urllib.parse.unquote(absolute), safe=":/%")
            if any(fragment in quoted for fragment in WANT[lane]):
                out.append((lane, absolute))
    return out


def local_path(lane, url):
    decoded = urllib.parse.unquote(url)
    match = re.search(r"/(\d{4})/([^/]+)$", decoded)
    year, name = (match.group(1), match.group(2)) if match \
        else ("undated", decoded.rsplit("/", 1)[1])
    return asset_path(STORE, lane, year, name)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch the NEPRA FCA corpus slice.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    documents = discover()
    print("%d determinations discovered across %d lanes"
          % (len(documents), len({lane for lane, _u in documents})), flush=True)
    if args.dry_run:
        for lane, url in documents[:20]:
            print("  %-8s %s" % (lane, urllib.parse.unquote(url).rsplit("/", 1)[1]))
        return 0

    # annex_kind is typed BY INSPECTION after fetching, and a re-run must not erase
    # that judgement - carry the typed columns forward by url.
    previous = {}
    if os.path.exists(MANIFEST):
        with open(MANIFEST, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(line for line in handle
                                      if not line.startswith("#")):
                previous[row["url"]] = (row["annex_kind"], row["parse_status"],
                                        row["note"])

    rows, fetched, failed = [], 0, 0
    for lane, url in documents:
        if args.limit and fetched >= args.limit:
            break
        path = local_path(lane, url)
        name = os.path.basename(path)
        import datetime
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                blob = _fetch(url, binary=True)
                with open(path + ".part", "wb") as handle:
                    handle.write(blob)
                os.replace(path + ".part", path)
                fetched += 1
                time.sleep(0.7)
            except Exception as error:  # noqa: BLE001 - typed, campaign continues
                failed += 1
                if os.path.exists(path + ".part"):
                    os.remove(path + ".part")
                rows.append({"lane": lane, "document": name, "url": url, "sha256": "",
                             "bytes": "", "fetched_at_utc": stamp,
                             "annex_kind": "unknown", "parse_status": "fetch_failed",
                             "note": str(error)[:120]})
                continue
        digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
        kind, status, note = previous.get(url, ("unknown", "pending", ""))
        rows.append({"lane": lane, "document": name, "url": url, "sha256": digest,
                     "bytes": os.path.getsize(path), "fetched_at_utc": stamp,
                     # annex_kind is typed at inspection, never guessed from a name:
                     # the recon found plant-wise annexes in only a subset of 2016
                     # months and none elsewhere; every document starts unknown and
                     # keeps whatever a later inspection typed.
                     "annex_kind": kind, "parse_status": status, "note": note})
    with open(MANIFEST, "w", newline="", encoding="utf-8") as handle:
        handle.write("# The NEPRA FCA determination corpus slice Pass 2 holds: the two "
                     "pre-sheet fiscal years (XWDISCO 2015-2017), the Nov19-Jun20 "
                     "combined COVID determination, and the K-Electric corpus 2015-2021.\n"
                     "# ACQUIRED, NOT PARSED: the recon verdict (scan-grade OCR, "
                     "inconsistent plant-wise annexes, 1-2 months of each fiscal year "
                     "never determined) is why parse_status stays pending and the "
                     "shape stays refused; see the search log.\n")
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["lane"], r["document"])))
    print("fetched %d, failed %d -> %s" % (fetched, failed,
                                           os.path.relpath(MANIFEST, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

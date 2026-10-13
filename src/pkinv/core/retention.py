"""Keep what was read: every fetched document is written to data/raw/ before it is parsed.

WHY THIS EXISTS. Until October 2026 the fetch scripts parsed a response in memory and let the
bytes go: UN Comtrade, the World Bank API, NASA POWER, the HydroWASTE archive, four Global
Energy Monitor workbooks, the FIRMS detections. Twenty sources ended in
data/catalog/not_retained_register.csv that way, and the manuscript had to say that some cited
documents were not retained. None had been deleted. They had never been saved.

THE RULE. A fetcher calls keep() with the bytes it received and then parses the file keep()
returns. It never parses the response directly, so a table cannot exist in this repository
without the bytes it was read from. tests/test_document_retention.py holds every script named
as a retrieval route to that.

NEVER OVERWRITE. A second fetch of the same address may return different bytes (FAOSTAT revises
its bulks, GEM replaces a tracker edition, a news page changes its markup). keep() then writes
the new bytes beside the old under a dated name and leaves the first file as it was. Which
bytes a table was read from stays answerable.

Each source directory carries RETRIEVALS.csv: one row per file kept, with the address, the
time, the digest and the route. A copy taken from the Internet Archive says so in `via` and
carries the capture's own timestamp, because it is evidence of what the page said then and not
of what the publisher serves now.
"""
import csv
import datetime
import hashlib
import os
import time
import urllib.error
import urllib.request

from pkinv.paths import ROOT

RAW = os.path.join(ROOT, "data", "raw")
LOG_NAME = "RETRIEVALS.csv"
LOG_FIELDS = ["file", "url", "retrieved_utc", "sha256", "bytes", "via", "note"]
# How a held copy was obtained. `direct` is the publisher's own address; `internet-archive`
# is a web.archive.org capture; `local-copy` came from another directory on the maintainer's
# machine; `git-history` was restored from an earlier commit of this repository;
# `browser-save` is a page the maintainer saved by hand because unattended clients are refused.
VIA = ("direct", "internet-archive", "local-copy", "git-history", "browser-save")
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
              "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")


def sha256_of(body):
    return hashlib.sha256(body).hexdigest()


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def _log_rows(directory):
    path = os.path.join(directory, LOG_NAME)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _append(directory, row):
    path = os.path.join(directory, LOG_NAME)
    fresh = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS, lineterminator="\n")
        if fresh:
            writer.writeheader()
        writer.writerow(row)


def keep(body, source, name, url, via="direct", note="", retrieved=None):
    """Write `body` to data/raw/<source>/<name>, record it, and return the path written.

    Identical bytes already held under that name: nothing is written and that path returns.
    Different bytes already held: the new bytes go to <stem>__<UTC date><ext> (and a time is
    added if that name is taken too); the first file is not touched.
    """
    if via not in VIA:
        raise ValueError("via must be one of %s, not %r" % (", ".join(VIA), via))
    if not isinstance(body, (bytes, bytearray)) or not body:
        raise ValueError("%s/%s: nothing to keep (an empty response is not a document)"
                         % (source, name))
    directory = os.path.join(RAW, source)
    os.makedirs(directory, exist_ok=True)
    digest = sha256_of(body)
    stamp = retrieved or _now().strftime("%Y-%m-%dT%H:%M:%SZ")
    target = os.path.join(directory, name)
    if os.path.exists(target):
        with open(target, "rb") as handle:
            if sha256_of(handle.read()) != digest:
                stem, ext = os.path.splitext(name)
                day = _now().strftime("%Y-%m-%d")
                target = os.path.join(directory, "%s__%s%s" % (stem, day, ext))
                if os.path.exists(target):
                    with open(target, "rb") as again:
                        same = sha256_of(again.read()) == digest
                    if not same:
                        target = os.path.join(directory, "%s__%s%s" % (
                            stem, _now().strftime("%Y-%m-%dT%H%M%SZ"), ext))
    if not os.path.exists(target):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(body)
    relative = os.path.relpath(target, directory)
    if not any(r["file"] == relative and r["sha256"] == digest for r in _log_rows(directory)):
        _append(directory, {"file": relative, "url": url, "retrieved_utc": stamp,
                            "sha256": digest, "bytes": len(body), "via": via, "note": note})
    return target


PLAIN_AGENT = "pkinv-retention/1.0 (PakEmis emission inventory; document archival)"


def get(url, attempts=3, timeout=120, headers=None, pause=3.0):
    """The bytes at `url`, or an OSError naming the last failure.

    Sends a browser's user agent first, because several publishers answer the default one
    with an empty body. A repository API does the opposite (Zenodo answers a browser's agent
    with 403 and a plain client with the file), so a 403 is asked once more under this
    project's own name. Neither is a way past a challenge page: a response that is a
    challenge is returned as it came, and the caller decides it is not a document."""
    last = None
    for agent in (USER_AGENT, PLAIN_AGENT):
        request = urllib.request.Request(
            url, headers=dict({"User-Agent": agent, "Accept": "*/*"}, **(headers or {})))
        refused = False
        for attempt in range(attempts):
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    return response.read()
            except urllib.error.HTTPError as error:
                last = error
                if error.code in (401, 403, 404, 410):
                    refused = error.code == 403
                    break
            except (urllib.error.URLError, OSError) as error:
                last = error
            if attempt + 1 < attempts:
                time.sleep(pause * (attempt + 1))
        if not refused:
            break
    raise OSError("%s: %s" % (url, last))


def fetch_and_keep(url, source, name, note="", **options):
    """get() then keep(): the one call a fetcher needs. Returns the path of the held file."""
    return keep(get(url, **options), source, name, url, note=note)


LINE_ENDINGS = "the tables differ only in line endings"


def table_differences(path, text, limit=12):
    """Lines on which the table at `path` differs from `text`, the table a fetcher would
    write from the document it just kept. Empty when they are the same bytes. This is what a
    fetcher's --check prints: it re-derives the table and compares, and writes nothing."""
    if not os.path.exists(path):
        return ["%s does not exist" % os.path.relpath(path, ROOT)]
    with open(path, encoding="utf-8", newline="") as handle:
        held = handle.read()
    if held == text:
        return []
    old, new = held.splitlines(), text.splitlines()
    out = []
    if len(old) != len(new):
        out.append("held table has %d lines, the kept document yields %d" % (len(old), len(new)))
    wrong = [i for i in range(min(len(old), len(new))) if old[i] != new[i]]
    for i in wrong[:limit]:
        out.append("line %d: held %r | document %r" % (i + 1, old[i][:160], new[i][:160]))
    if len(wrong) > limit:
        out.append("... and %d more differing lines" % (len(wrong) - limit))
    return out or [LINE_ENDINGS]


def report_check(label, path, text):
    """Print a --check verdict and return the exit code (0 same, 1 different)."""
    found = table_differences(path, text)
    if not found or found == [LINE_ENDINGS]:
        # a table normalised to LF after it was written holds the same cells
        print("%s: the kept document reproduces %s %s"
              % (label, os.path.relpath(path, ROOT),
                 "exactly" if not found else "cell for cell (line endings differ)"))
        return 0
    print("%s: the kept document does NOT reproduce %s" % (label, os.path.relpath(path, ROOT)))
    for line in found:
        print("  ! %s" % line)
    return 1

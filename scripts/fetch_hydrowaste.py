#!/usr/bin/env python3
"""Fetch HydroWASTE's Pakistani wastewater-treatment-plant rows (rc13).

WHY. The waste release registry's wastewater side has NO candidates at all - the
OSM seed is landfills only. HydroWASTE (Ehalt Macedo et al. 2022, ESSD 14:559-577,
doi:10.5194/essd-14-559-2022) is a global register of ~58,500 WWTPs with
coordinates, population served and treatment level, published on figshare under
CC-BY 4.0. This pins the Pakistani subset as release CANDIDATES - locations of
plausible treated-discharge points, never an allocation basis and never evidence
that treatment actually happens at the modelled 1 percent share.

CONTRACT. The figshare article id is pinned; the script discovers the current file
listing through the figshare API, downloads the zip, extracts ONLY the Pakistani
rows of HydroWASTE_v10.csv, and records the zip sha256 in a sidecar. On ANY
failure it prints the manual route, writes NOTHING, and exits non-zero.

THE ARCHIVE IS KEPT (October 2026). The zip and the figshare listing that named it are
written to data/raw/hydrowaste/ before the zip is opened (pkinv.core.retention). Until then
the zip was read in memory and only its sha256 survived.

--check keeps the archive, compares its sha256 with the one the sidecar pinned and the
Pakistani rows with the held extract, and writes neither the extract nor the sidecar.

Usage:  python3 scripts/fetch_hydrowaste.py [--check]
Writes: data/raw/hydrowaste/<archive>.zip, data/raw/hydrowaste/figshare_article_14847786.json
        data/activity/waste/hydrowaste_pak.csv
        sources/HydroWASTE/HYDROWASTE_SOURCES.json
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

from pkinv.assets import asset_path
from pkinv.core import retention

ROOT = Path(__file__).resolve().parents[1]
# the legacy name is the file's identity; asset_path gives where it lives
DATA_OUT = Path(asset_path(str(ROOT), "data", "activity", "waste", "hydrowaste_pak.csv"))
SRC_DIR = ROOT / "sources" / "HydroWASTE"

FIGSHARE_ARTICLE = 14847786          # Ehalt Macedo et al. 2022, HydroWASTE v1.0
DOI = "10.5194/essd-14-559-2022"
LICENCE = "CC-BY-4.0"
COUNTRY = "Pakistan"


def _get(url):
    request = Request(url, headers={"User-Agent": "pkinv-hydrowaste/1.0"})
    with urlopen(request, timeout=300) as response:
        return response.read()


def main(argv=None):
    checking = "--check" in (sys.argv[1:] if argv is None else argv)
    try:
        api = "https://api.figshare.com/v2/articles/%d" % FIGSHARE_ARTICLE
        with open(retention.keep(_get(api), "hydrowaste",
                                 "figshare_article_%d.json" % FIGSHARE_ARTICLE, api),
                  encoding="utf-8") as handle:
            listing = json.load(handle)
        target = next(f for f in listing["files"]
                      if f["name"].lower().endswith(".zip")
                      and "hydrowaste" in f["name"].lower())
        kept = retention.keep(_get(target["download_url"]), "hydrowaste", target["name"],
                              target["download_url"],
                              note="figshare article %d, doi:%s" % (FIGSHARE_ARTICLE, DOI))
        with open(kept, "rb") as handle:
            sha = hashlib.sha256(handle.read()).hexdigest()
        zf = zipfile.ZipFile(kept)
        csv_name = next(n for n in zf.namelist()
                        if n.lower().endswith(".csv") and "hydrowaste" in n.lower())
        rows = list(csv.DictReader(
            io.TextIOWrapper(zf.open(csv_name), encoding="utf-8", errors="replace")))
        pak = [r for r in rows if (r.get("COUNTRY") or "").strip() == COUNTRY]
        if not pak:
            raise ValueError("zero Pakistani rows in %s" % csv_name)
    except Exception as exc:                                   # noqa: BLE001
        print("HydroWASTE fetch FAILED (%s: %s); nothing written.\n"
              "Manual route: figshare article %d (doi:%s), file "
              "HydroWASTE_v10.zip -> filter COUNTRY == Pakistan into "
              "data/activity/waste/hydrowaste_pak.csv"
              % (type(exc).__name__, exc, FIGSHARE_ARTICLE, DOI))
        return 1

    text = io.StringIO()
    w = csv.DictWriter(text, fieldnames=list(pak[0].keys()))
    w.writeheader()
    w.writerows(pak)
    if checking:
        with open(SRC_DIR / "HYDROWASTE_SOURCES.json", encoding="utf-8") as handle:
            pinned = json.load(handle)["zip_sha256"]
        print("HydroWASTE archive %s: %s" % (target["name"],
              "the bytes the extract was read from (sha256 matches the sidecar)"
              if pinned == sha else "NOT the pinned archive (%s now, %s pinned)"
              % (sha[:12], pinned[:12])))
        return max(retention.report_check("HydroWASTE", str(DATA_OUT), text.getvalue()),
                   0 if pinned == sha else 1)

    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_OUT, "w", newline="", encoding="utf-8") as f:
        f.write(text.getvalue())
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    (SRC_DIR / "HYDROWASTE_SOURCES.json").write_text(json.dumps({
        "dataset": "HydroWASTE v1.0 (Ehalt Macedo et al. 2022)",
        "doi": DOI, "figshare_article": FIGSHARE_ARTICLE,
        "file": target["name"], "zip_sha256": sha,
        "source_csv": csv_name, "pak_rows": len(pak),
        "licence": LICENCE,
        "role": "wastewater release CANDIDATES for the waste release registry - "
                "locations only, never an allocation basis, never evidence of "
                "treatment shares",
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("HydroWASTE: %d Pakistani WWTP rows -> %s (zip sha256 %s...)"
          % (len(pak), DATA_OUT.relative_to(ROOT), sha[:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

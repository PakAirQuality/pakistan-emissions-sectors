#!/usr/bin/env python3
"""Resolve and optionally download the four-day ADSB.lol Pakistan coverage pilot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from urllib.request import Request, urlopen

from pkinv.sectors.aviation.adsblol import CACHE, LICENSE, PILOT_DATES


def _metadata(date):
    year = date[:4]
    tag = "v%s-planes-readsb-prod-0" % date.replace("-", ".")
    url = "https://api.github.com/repos/adsblol/globe_history_%s/releases/tags/%s" % (year, tag)
    with urlopen(Request(url, headers={"User-Agent": "pkinv-aviation/1.0"}), timeout=120) as response:
        release = json.load(response)
    release_assets = sorted(
        [asset for asset in release["assets"] if ".tar" in asset["name"]],
        key=lambda item: item["name"])
    if not release_assets:
        raise ValueError("no tar assets in ADSB.lol release %s" % tag)
    parts = [{"name": asset["name"], "url": asset["browser_download_url"],
              "size_bytes": asset["size"], "updated_at": asset["updated_at"]}
             for asset in release_assets]
    return {"date": date, "repository": "adsblol/globe_history_%s" % year,
            "tag": release["tag_name"], "asset_parts": parts,
            "size_bytes": sum(part["size_bytes"] for part in parts),
            "license": LICENSE}


def _download_part(part, destination):
    existing = destination.stat().st_size if destination.exists() else 0
    headers = {"User-Agent": "pkinv-aviation/1.0"}
    if existing:
        headers["Range"] = "bytes=%d-" % existing
    request = Request(part["url"], headers=headers)
    with urlopen(request, timeout=300) as response:
        append = existing and getattr(response, "status", None) == 206
        mode = "ab" if append else "wb"
        with destination.open(mode) as handle:
            shutil.copyfileobj(response, handle, length=8 * 1024 * 1024)
    if destination.stat().st_size != part["size_bytes"]:
        raise IOError("incomplete ADSB.lol asset part %s" % part["name"])


def run(download=False, dates=PILOT_DATES):
    destination = Path(CACHE)
    destination.mkdir(parents=True, exist_ok=True)
    assets = []
    for date in dates:
        item = _metadata(date)
        target = destination / (date + ".tar")
        item["local_file"] = str(target)
        item["downloaded"] = target.exists() and target.stat().st_size == item["size_bytes"]
        if download and not item["downloaded"]:
            parts = []
            for index, part in enumerate(item["asset_parts"]):
                partial = (target.with_suffix(".tar.partial") if len(item["asset_parts"]) == 1
                           else target.with_suffix(".tar.part%02d" % index))
                _download_part(part, partial)
                parts.append(partial)
            if len(parts) == 1:
                parts[0].replace(target)
            else:
                with target.open("wb") as combined:
                    for partial in parts:
                        with partial.open("rb") as handle:
                            shutil.copyfileobj(handle, combined, length=8 * 1024 * 1024)
                if target.stat().st_size != item["size_bytes"]:
                    raise IOError("incomplete combined ADSB.lol asset %s" % date)
            item["downloaded"] = True
        assets.append(item)
    manifest = {"schema": "pkinv.aviation.adsblol_pilot/v1", "license": LICENSE,
                "raw_data_policy": "gitignored cache; do not redistribute without ODbL review",
                "assets": assets}
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"assets": len(assets), "downloaded": sum(a["downloaded"] for a in assets),
                      "total_gib": sum(a["size_bytes"] for a in assets) / 1024 ** 3}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--date", action="append", choices=PILOT_DATES,
                        help="select one or more pilot dates; default is all four")
    args = parser.parse_args()
    run(args.download, tuple(args.date) if args.date else PILOT_DATES)


if __name__ == "__main__":
    main()

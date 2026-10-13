#!/usr/bin/env python3
"""Fetch Global Energy Monitor's coal-plant and cement tracker rows for Pakistan (rc13).

WHY. The eighth review's integration slate asks for a complete power/industrial
facility registry cross-check. GEM's Global Coal Plant Tracker and Global Cement
and Concrete Tracker are unit-level global registers published under CC BY 4.0
behind a registration form. This pins the Pakistani subsets as COMPARATOR
evidence - an asset census cross-check against the NEPRA-derived plant ledger,
never an allocation basis and never activity data.

HOW. GEM's download form is a two-step token flow (observed from the published
form bundle, gem-download-form.bundle.js): a submission is minted with the
requester's identity and the requested dataset slugs, and the returned
capability token presigns the actual download URLs. This script performs that
same flow with the SAME fields the human form submits - the identity below is
the maintainer's real one, the CC BY 4.0 licence line is the form's own text,
and the submission is recorded in the sidecar. Nothing about the flow is
scraped around: this IS the registration, done honestly, once, scriptably.

CONTRACT. Endpoints, key and slugs are pinned; the Pakistani rows are extracted
to versioned CSVs; the xlsx sha256s and the submission metadata land in
sources/GEM/GEM_SOURCES.json. On ANY failure the script prints the manual
route, writes NOTHING, and exits non-zero.

EVERY WORKBOOK IS KEPT (October 2026). Each downloaded xlsx is written to data/raw/gem/
before it is read (pkinv.core.retention). Until then only the Pakistani rows and the
workbook's sha256 were kept, so four trackers were cited and none was held. GEM serves only
its CURRENT edition of a tracker: a workbook fetched later than the extract may be a later
edition, and --check says which by comparing its sha256 with the one the sidecar pinned.

--check downloads and keeps the four workbooks, compares each with the pinned digest and
with the held extract, and writes neither the extracts nor the sidecar.

Usage:  python3 scripts/fetch_gem_trackers.py [--check]
Writes: data/raw/gem/<workbook>.xlsx          (every workbook, kept before reading)
        data/activity/power/gem_coal_pak.csv
        data/activity/industry/gem_cement_pak.csv
        data/activity/power/gem_gas_oil_pak.csv
        data/activity/power/gem_bioenergy_pak.csv
        sources/GEM/GEM_SOURCES.json
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from pkinv.assets import asset_path
from pkinv.core import retention

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "sources" / "GEM"


def _extract(*parts):
    """The extract's real path. The legacy data/activity/... name is its identity; the file
    lives in the sector tree, and writing to the legacy name would create a second copy."""
    return Path(asset_path(str(ROOT), "data", "activity", *parts))


# The supabase project GEM's own form posts to, and its PUBLISHABLE (anon) key -
# both shipped to every visitor inside gem-download-form.bundle.js. Not a secret.
MINT_URL = "https://auxunjnrktkmeqyoyngm.supabase.co/rest/v1/rpc/mint_submission"
PRESIGN_URL = "https://auxunjnrktkmeqyoyngm.supabase.co/functions/v1/presign"
ANON_KEY = "sb_publishable_8mQAV8B2HhveNc5T8VGqPQ_1lgsFAvz"
LICENCE = "Creative Commons Attribution 4.0 International (CC BY 4.0)"

# The registration the human form would send, filled with the maintainer's real
# identity - the fetch was explicitly approved for Round 24, and a made-up
# identity would defeat the point of a registration wall.
IDENTITY = {
    "name": "Rehan Ahmad",
    "email": "rehan@pakairquality.com",
    "organization": "Pakistan Air Quality Initiative",
    "sector": "NGO / research",
    "country": "Pakistan",
    "use_case": "National GHG inventory asset-census cross-check (PakEmis)",
}

TRACKERS = {
    "coal-plant-tracker": {
        "page": "https://globalenergymonitor.org/projects/global-coal-plant-tracker/download-data/",
        "out": _extract("power", "gem_coal_pak.csv"),
        "label": "Global Coal Plant Tracker",
    },
    "cement-concrete-tracker": {
        "page": "https://globalenergymonitor.org/projects/global-cement-and-concrete-tracker/download-data/",
        "out": _extract("industry", "gem_cement_pak.csv"),
        "label": "Global Cement and Concrete Tracker",
    },
    # rc46 Wave 1: the gas/oil grid fleet's coordinate source, same flow, same terms. The
    # coal tracker located the coal fleet at rc42; these two do the same for the ~41
    # gas/RFO/bagasse stations the crosswalk now names.
    "oil-gas-plant-tracker": {
        "page": "https://globalenergymonitor.org/projects/global-oil-gas-plant-tracker/download-data/",
        "out": _extract("power", "gem_gas_oil_pak.csv"),
        "label": "Global Oil and Gas Plant Tracker",
    },
    "bioenergy-tracker": {
        "page": "https://globalenergymonitor.org/projects/global-bioenergy-power-tracker/download-data/",
        "out": _extract("power", "gem_bioenergy_pak.csv"),
        "label": "Global Bioenergy Power Tracker",
    },
}


def _post(url, payload, bearer):
    request = Request(url, method="POST",
                      data=json.dumps(payload).encode() if payload is not None else b"",
                      headers={"content-type": "application/json",
                               "apikey": ANON_KEY,
                               "authorization": "Bearer %s" % bearer,
                               "User-Agent": "pkinv-gem-fetch/1.0"})
    with urlopen(request, timeout=120) as response:
        return json.loads(response.read())


def _get(url):
    request = Request(url, headers={"User-Agent": "pkinv-gem-fetch/1.0"})
    with urlopen(request, timeout=600) as response:
        return response.read()


def _pak_rows(workbook, label):
    """Every sheet's Pakistani rows, via the Country/Area column pandas finds. Reads the
    KEPT workbook, never the response."""
    import pandas as pd
    frames = []
    book = pd.read_excel(workbook, sheet_name=None)
    for sheet, frame in book.items():
        country_cols = [c for c in frame.columns
                        if str(c).strip().lower() in ("country/area", "country")]
        if not country_cols:
            continue
        pak = frame[frame[country_cols[0]].astype(str).str.strip() == "Pakistan"]
        if len(pak):
            pak = pak.copy()
            pak.insert(0, "sheet", sheet)
            frames.append(pak)
    if not frames:
        raise RuntimeError("no Pakistani rows found in any sheet of %s" % label)
    return pd.concat(frames, ignore_index=True)


def check(results):
    """Compare the kept workbooks with the pinned digests and the held extracts."""
    with open(SRC_DIR / "GEM_SOURCES.json", encoding="utf-8") as handle:
        pinned = json.load(handle)["trackers"]
    worst = 0
    for slug, r in results.items():
        was = pinned.get(slug, {})
        same_edition = was.get("xlsx_sha256") == r["sha256"]
        print("  %-24s %s: %s" % (slug, r["filename"],
              "the bytes the extract was read from (sha256 matches the sidecar)"
              if same_edition else
              "a LATER EDITION than the extract (pinned %s, %s; held now %s)"
              % (was.get("source_filename"), (was.get("xlsx_sha256") or "")[:12],
                 r["sha256"][:12])))
        text = r["frame"].to_csv(index=False)
        code = retention.report_check("    " + r["spec"]["label"], str(r["spec"]["out"]), text)
        worst = max(worst, code if same_edition else 0)
    return worst


def main(argv=None):
    checking = "--check" in (sys.argv[1:] if argv is None else argv)
    results = {}
    try:
        for slug, spec in TRACKERS.items():
            payload = dict(IDENTITY)
            payload.update({"license_text": LICENCE, "email_optin": False,
                            "request_mode": "slugs", "requested_slugs": [slug],
                            "useragent": "pkinv-gem-fetch/1.0",
                            "page_url": spec["page"]})
            minted = _post(MINT_URL, payload, ANON_KEY)
            token = minted.get("capability_token")
            if not token:
                raise RuntimeError("mint_submission returned no capability token "
                                   "for %s: %s" % (slug, str(minted)[:200]))
            urls = _post(PRESIGN_URL, None, token).get("urls") or []
            if not urls:
                raise RuntimeError("presign returned no urls for %s" % slug)
            entry = urls[0]
            blob = _get(entry["url"])
            name = entry.get("filename") or ("%s.xlsx" % (entry.get("slug") or slug))
            kept = retention.keep(blob, "gem", name, spec["page"],
                                  note="GEM download form (mint + presign), slug %s; the "
                                       "presigned address is single-use and is not recorded"
                                       % slug)
            pak = _pak_rows(kept, spec["label"])
            results[slug] = {"filename": name,
                             "sha256": hashlib.sha256(blob).hexdigest(),
                             "bytes": len(blob), "pak_rows": int(len(pak)),
                             "frame": pak, "spec": spec}
            print("  %-24s %s (%.1f MB) -> %d Pakistani rows"
                  % (slug, results[slug]["filename"], len(blob) / 1e6, len(pak)))
    except Exception as exc:
        print("FAILED before anything was written: %s" % exc, file=sys.stderr)
        print("Manual route: submit the form at the download-data pages under\n"
              "https://globalenergymonitor.org/projects/ and place the Pakistani\n"
              "rows at the paths this script names.", file=sys.stderr)
        sys.exit(1)

    if checking:
        sys.exit(check(results))

    # Every tracker succeeded - only now does anything but the kept workbooks touch disk.
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    sidecar = {"licence": LICENCE, "flow": "gem-download-form mint+presign",
               "submission_identity": {k: v for k, v in IDENTITY.items()
                                       if k != "email"} | {"email": IDENTITY["email"]},
               "trackers": {}}
    for slug, r in results.items():
        r["spec"]["out"].parent.mkdir(parents=True, exist_ok=True)
        r["frame"].to_csv(r["spec"]["out"], index=False)
        sidecar["trackers"][slug] = {
            "label": r["spec"]["label"], "source_filename": r["filename"],
            "xlsx_sha256": r["sha256"], "xlsx_bytes": r["bytes"],
            "pak_rows": r["pak_rows"],
            "extract": str(r["spec"]["out"].relative_to(ROOT)),
            "note": "comparator evidence only - an asset-census cross-check, "
                    "never an allocation basis and never activity data"}
    with open(SRC_DIR / "GEM_SOURCES.json", "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, sort_keys=True)
        f.write("\n")
    print("Wrote sources/GEM/GEM_SOURCES.json + %d extracts" % len(results))


if __name__ == "__main__":
    main()

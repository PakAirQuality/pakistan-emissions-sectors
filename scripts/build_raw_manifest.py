"""One row per raw acquisition, with the fields a reviewer asked to see beside every file.

WHY. data/raw/ now holds official documents from five publishers acquired three different ways
- some downloaded by script, some by a browser session, some by hand - and an inventory that
cannot say WHICH cannot be audited. The reviewer's field list is the answer, and the two that
matter most are the ones nothing else in this repository records: `access_mode`, because a file
a script can re-fetch and a file a human clicked are different kinds of evidence, and
`redistribution_status`, because these are third-party publications and the deposit must
exclude them.

WHAT IS NOT INVENTED. `source_url` is written only where the URL is known. A file whose
provenance came from a browser session that has since closed carries an empty URL and
`access_mode = manual`, which is an honest "a person fetched this" rather than a plausible
guess that would fail silently when someone tried to re-download it.

Usage:  python3 scripts/build_raw_manifest.py
Writes: data/manifests/source_manifest.csv
"""
import csv
import datetime
import hashlib
import json
import os

from pkinv.paths import ROOT
from pkinv.assets import resolve

RAW = os.path.join(ROOT, "data", "raw")
OUT_DIR = os.path.join(ROOT, "data", "manifests")
OUT = resolve(os.path.join(OUT_DIR, "source_manifest.csv"), root=ROOT)
OUT_DIR = os.path.dirname(OUT)

FIELDS = ("source_id", "local_path", "original_filename", "source_url", "retrieved_at_utc",
          "sha256", "bytes", "coverage_start", "coverage_end", "geography", "unit",
          "access_mode", "licence", "redistribution_status", "revision_status",
          "temporal_role", "notes")

# What each subtree is, declared once. `temporal_role` is the field that decides whether a
# file can time anything: an annual control cannot, however good it is.
TREES = {
    "pbs/qim": dict(
        publisher="Pakistan Bureau of Statistics", geography="Pakistan",
        unit="physical output, item-specific", temporal_role="monthly_activity",
        coverage="fiscal-year file, twelve months each",
        notes="Table 2, Quantum Index of Large Scale Manufacturing. All nine editions carry "
              "a TEXT LAYER - an earlier note here called them image scans needing OCR and "
              "that was simply wrong - and the series is gated on each row's twelve months "
              "summing to the annual total the same row prints"),
    "pbs/electricity": dict(
        publisher="Pakistan Bureau of Statistics", geography="Pakistan",
        unit="GWh by plant and fuel", temporal_role="monthly_activity",
        coverage="1999-2000 to 2020-21", notes="plant/unit x fuel x month; has a text layer"),
    "pbs/minerals": dict(
        publisher="Pakistan Bureau of Statistics", geography="Pakistan, by province",
        unit="tonnes / barrels / MMCF", temporal_role="monthly_activity",
        coverage="fiscal-year file", notes="coal, crude oil and natural gas production by "
                                           "month and province"),
    "pbs/hies": dict(
        publisher="Pakistan Bureau of Statistics", geography="Pakistan, household",
        unit="survey microdata", temporal_role="profile_anchor",
        coverage="survey round", notes="enumeration month and household fuel use; a survey "
                                       "round anchors a profile and is NOT a monthly series"),
    "ocac/monthly_sector_province": dict(
        publisher="Oil Companies Advisory Council", geography="Pakistan, by province",
        unit="tonnes by product", temporal_role="monthly_activity",
        coverage="one month each", notes="product x consuming sector x province. Times fuel "
                                         "SALES, never combustion"),
    "ocac/annual_controls": dict(
        publisher="Oil Companies Advisory Council", geography="Pakistan",
        unit="tonnes by product", temporal_role="annual_control",
        coverage="fiscal year", notes="the annual total a monthly reconstruction must close "
                                      "to; it cannot time anything itself"),
    "nfdc": dict(
        publisher="National Fertilizer Development Centre", geography="Pakistan, by province",
        unit="nutrient and product tonnes", temporal_role="monthly_activity",
        coverage="fiscal year", notes="offtake times the DEPOT, not field application"),
    "ogra/lpg_consumption": dict(
        publisher="Oil and Gas Regulatory Authority", geography="Pakistan, by province",
        unit="metric tonnes", temporal_role="monthly_activity",
        coverage="one month each",
        notes="province x sector LPG consumption. The DOMESTIC column is TE1 for residential "
              "LPG; commercial, industrial and automotive belong to their own sectors and "
              "national supply is not a substitute for either"),
    # The edition is decided PER FILE (ipcc_edition below). Through rc66 every file in
    # this directory was stamped "2019 Refinement" and given the Refinement's Volume 5
    # address, because the first file kept here was the Refinement's waste model. Ten
    # chapters of the 2006 Guidelines were then added and inherited the label, and the
    # wastewater chapter of 2006 was cited as the Refinement's for it.
    "ipcc": dict(
        publisher="IPCC / IGES", geography="global method", unit="model workbook",
        temporal_role="method", coverage="2019 Refinement",
        notes="the first-order-decay waste model; a method, not an observation"),
    "apcma": dict(
        publisher="All Pakistan Cement Manufacturers Association", geography="Pakistan",
        unit="tonnes dispatched", temporal_role="monthly_activity",
        coverage="fiscal-year page, FY2015-16..FY2019-20",
        notes="monthly cement DISPATCHES, which are sales and not production and not "
              "clinker calcination. A second and independent monthly series beside PBS QIM "
              "output, useful as a cross-check rather than a substitute"),
    "fao_crop_calendar": dict(
        publisher="FAO", geography="Pakistan, by crop", unit="calendar dates",
        temporal_role="profile_anchor", coverage="climatological",
        notes="sowing and harvest windows by crop; a climatology, NOT a year-specific "
              "observation, so it can shape a season and can never date one"),
    "ocac/alternate_uploads": dict(
        publisher="Oil Companies Advisory Council", geography="Pakistan, by province",
        unit="tonnes by product", temporal_role="provenance_evidence",
        coverage="one month each",
        notes="ALTERNATE UPLOADS of months already held under a different filename. Their "
              "national controls are identical to the held editions, so they are not "
              "restatements and nothing reads them; they are kept because the fetcher's "
              "filename pattern could not match them, which is a fact about the fetcher"),
}

# Files acquired by a route a script cannot repeat, and the reason. Everything else defaults
# to `direct` because a fetch script in this repository produced it.
MANUAL = {
    "apcma": "arrived in the maintainer's PakEmis_108_month_data_bundle",
    "fao_crop_calendar": "as above",
    "ocac/alternate_uploads": "as above",
    "pbs/qim": "downloaded by the maintainer into monthly_scrape/ before this manifest existed",
    "pbs/electricity": "as above",
    "pbs/minerals": "as above",
}

# Where a fetch script recorded what it did, so its URLs and revisions reach this manifest
# rather than being retyped.
FETCH_MANIFESTS = ("ocac/monthly_sector_province/_fetch_manifest.json",)

KNOWN_URLS = {
    "pbs/qim": "https://www.pbs.gov.pk/wp-content/uploads/2020/07/",
    "pbs/minerals": "https://www.pbs.gov.pk/wp-content/uploads/2020/07/",
    "pbs/hies": "https://www.pbs.gov.pk/wp-content/uploads/2020/07/",
    "nfdc": "https://nfdc.gov.pk/publications/",
    "ipcc": "https://www.ipcc-nggip.iges.or.jp/public/2019rf/pdf/5_Volume5/",
    "ocac/annual_controls": "https://www.ocac.org.pk/wp-content/uploads/2022/05/",
    "ogra/lpg_consumption": "https://www.ogra.org.pk/download/(numeric id, see lpg-7)",
    "apcma": "https://www.apcma.com/data_monthly(YYYY).html",
    "fao_crop_calendar": "https://www.fao.org/agriculture/seed/cropcalendar/",
    "ocac/alternate_uploads": "https://www.ocac.org.pk/wp-content/uploads/2022/05/",
}


IPCC_2006 = "https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/"
IPCC_2019 = "https://www.ipcc-nggip.iges.or.jp/public/2019rf/pdf/"
IPCC_VOLUME = {"V1": "1_Volume1/", "V2": "2_Volume2/", "V3": "3_Volume3/",
               "V4": "4_Volume4/", "V5": "5_Volume5/"}


def ipcc_edition(name):
    """(coverage, url, unit, notes) for one file kept under data/raw/ipcc/, read from its
    NAME: `ipcc2006_V5_6_...` is a chapter of the 2006 Guidelines, `19R_V5_6_...` a chapter
    of the 2019 Refinement, `ipcc2019_...` the Refinement's workbook. Returns None for a
    name that says neither, so an unlabelled file fails the build instead of inheriting an
    edition."""
    parts = name.split("_")
    if name.startswith("ipcc2006_") and parts[1] in IPCC_VOLUME:
        return ("2006 IPCC Guidelines", IPCC_2006 + IPCC_VOLUME[parts[1]]
                + "(chapter file as published)", "guidance chapter",
                "a chapter of the 2006 IPCC Guidelines; a method, not an observation")
    if name.startswith("19R_") and parts[1] in IPCC_VOLUME:
        return ("2019 Refinement", IPCC_2019 + IPCC_VOLUME[parts[1]] + name,
                "guidance chapter",
                "a chapter of the 2019 Refinement to the 2006 IPCC Guidelines; a method, "
                "not an observation")
    if name.startswith("ipcc2019_"):
        return ("2019 Refinement", IPCC_2019 + "5_Volume5/(filename as published)",
                "model workbook",
                "the first-order-decay waste model; a method, not an observation")
    return None


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _fetched_urls():
    """{basename: (url, revision_status)} from every fetch script's own record."""
    out = {}
    for relative in FETCH_MANIFESTS:
        path = os.path.join(RAW, relative)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
        for row in record.get("fetched", []):
            out[os.path.basename(row["local_path"])] = (row["source_url"],
                                                        row.get("revision_status", ""))
    return out


def build():
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fetched = _fetched_urls()
    rows = []
    for tree, meta in sorted(TREES.items()):
        directory = os.path.join(RAW, tree)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            path = os.path.join(directory, name)
            if not os.path.isfile(path) or name.startswith((".", "_")):
                continue
            if name == "RETRIEVALS.csv":
                continue                      # the directory's own retrieval log
            url, revision = fetched.get(name, ("", ""))
            if not url and tree in KNOWN_URLS:
                url = KNOWN_URLS[tree] + "(filename as published)"
            if tree == "ipcc":
                edition = ipcc_edition(name)
                if edition is None:
                    raise SystemExit("data/raw/ipcc/%s: the name does not say which IPCC "
                                     "edition it is" % name)
                meta = dict(meta, coverage=edition[0], unit=edition[2], notes=edition[3])
                url = edition[1]
            rows.append({
                "source_id": "%s/%s" % (tree, os.path.splitext(name)[0]),
                "local_path": os.path.relpath(path, ROOT),
                "original_filename": name,
                "source_url": url,
                "retrieved_at_utc": now,
                "sha256": _sha256(path),
                "bytes": os.path.getsize(path),
                "coverage_start": meta["coverage"],
                "coverage_end": "",
                "geography": meta["geography"],
                "unit": meta["unit"],
                "access_mode": "manual" if tree in MANUAL else "direct",
                # Every one of these is a third-party official publication. None carries a
                # stated open licence, which is the ordinary condition of a government
                # statistical release and is why the deposit ships derived tables instead.
                "licence": "not-stated",
                "redistribution_status": "not-established",
                "revision_status": revision or "as-published",
                "temporal_role": meta["temporal_role"],
                "notes": meta["notes"] + ((" | " + MANUAL[tree]) if tree in MANUAL else ""),
            })
    return rows


def main():
    rows = build()
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        handle.write("# Every raw acquisition under data/raw/, with how it was obtained and "
                     "whether it may be republished.\n")
        handle.write("# redistribution_status is not-established for all of them: these are "
                     "third-party official publications, so the\n")
        handle.write("# archive deposit ships this project's DERIVED tables and names these "
                     "in outputs/pakemis_source_register.csv instead.\n")
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    import collections
    print("raw manifest -> %s" % os.path.relpath(OUT, ROOT))
    print("  %d files, %.1f MB" % (len(rows), sum(r["bytes"] for r in rows) / 1e6))
    for tree, count in sorted(collections.Counter(
            r["source_id"].rsplit("/", 1)[0] for r in rows).items()):
        print("    %-32s %3d" % (tree, count))
    modes = collections.Counter(r["access_mode"] for r in rows)
    print("  access: %s" % ", ".join("%s %d" % kv for kv in sorted(modes.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

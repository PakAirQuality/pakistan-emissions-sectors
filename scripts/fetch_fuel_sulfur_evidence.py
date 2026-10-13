#!/usr/bin/env python3
"""Acquire the public documents that bear on FUEL SULFUR as consumed, not as specified (item 3).

WHY A SCRIPT. `data/activity/industry/fuel_sulfur_evidence.csv` declares a five-word basis
vocabulary whose first entry is `measured_avg` - "consignment analyses of consumed fuel". No row
used it until rc63, when brick-kiln coal became the first row to earn it. Every row was a
`regulatory_max`, `field_range` or `declared_regime` - a ceiling, a resource range, or a mandate
date - when this script was written, and finding the documents below is what changed that. Two of those rows name, in their own notes, the acquisition that
would collapse them - "a refinery/OMC sulfur assay series (OGRA or HDIP)" for furnace oil, and "a
kiln-coal consignment assay series (Punjab EPD / BKOAP)" for brick coal. Nobody had gone looking.
This script goes looking, fetches what is public to data/raw/<source>/ (never sources/, the frozen
legacy tree), hashes it, and writes one log row per attempt - hits and misses alike - so that "not
held" can never again be confused with "never fetched".

WHAT THE HELD TREE ALREADY ANSWERS, CHECKED FIRST AND LOGGED AS NEGATIVES. Two of these documents
were expected to carry the answer and do not, which is worth recording because the evidence rows
point at them:
  - OGRA State of Industry, all nine held editions (sources/OGRA/): every occurrence of "sulphur"
    is an abbreviations-page gloss of HSFO/LSFO. No product sulfur specification, and no HSFO/LSFO
    tonnage table. The regulator's own flagship publication does not carry what the register's note
    hoped it would.
  - PBS Compendium on Environment Statistics 2020, Table B-10 (p.161, HELD): DOES carry the import
    grade split in tonnes, but for FY2014-15..FY2018-19 only - four of the nine panel years - and
    imports are not consumption. It is transcribed by scripts/ingest_fuel_sulfur_documents.py
    rather than re-fetched here.

THE ADDRESSES ARE THE RESOLVED ONES, located from the publishers' own pages on 2026-09-20. One
target is expected to fail and is listed anyway: the Elsevier Lahore kiln paper answers 403 to an
unauthenticated request, and a logged refusal is worth more than an unlisted silence.

Idempotent: a file already on disk is left alone and logged as `held`.

Usage:  python3 scripts/fetch_fuel_sulfur_evidence.py [--dry-run]
Writes: data/raw/petroleum_gov/*.pdf, data/raw/fuel_specs/*.html, data/raw/literature/*.pdf
        data/raw/ACQUISITION_LOG_fuel_sulfur.csv (one row per attempt)
        data/acquisition_attempts.csv (appended, one row per dataset)
"""

from pkinv.assets import asset_path
import csv
import datetime as dt
import hashlib
import os
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = asset_path(ROOT, "data", "raw")
LOG = asset_path(RAW, "ACQUISITION_LOG_fuel_sulfur.csv")
ATTEMPTS = asset_path(ROOT, "data", "acquisition_attempts.csv")
DRY = "--dry-run" in sys.argv
TODAY = dt.date.today().isoformat()
UA = "PakEmis/1.0 (research inventory)"

# (source, dataset label, url, destination under data/raw/, expected magic, why it is wanted)
TARGETS = (
    ("Petroleum Division", "Pakistan Oil Refining Policy for Upgradation of Existing Refineries 2023",
     "https://petroleum.gov.pk/SiteImage/Downloads/Brownfield%20Refinery%20Policy-2023.pdf",
     "petroleum_gov/pakistan_brownfield_refinery_policy_2023.pdf", b"%PDF",
     "the government's own statement of current and mandated product sulfur, with dates; the "
     "document that says what Pakistani refineries were permitted to produce across the panel"),

    ("PARCO/Gunvor", "Industrial fuels product specifications (furnace oil, HSD, LDO)",
     "https://parcogunvor.com.pk/business-customers/industrial-fuels",
     "fuel_specs/parcogunvor_industrial_fuels_spec.html", b"<",
     "the ONLY located Pakistani LDO sulfur specification (1.8 percent max). industry_ldo and "
     "industry_kero currently borrow road-diesel sulfur because the register records no LDO spec "
     "as held; this is that spec"),

    ("J. Petroleum Technology & Alternative Fuels",
     "Yasin, Bhanger et al., Quality of commercial high speed diesel and its environmental impact",
     "https://academicjournals.org/article/article1379951807_Yasin%20et%20al.pdf",
     "literature/yasin_commercial_hsd_quality.pdf", b"%PDF",
     "ASTM D4294 sulfur on commercial HSD sampled at Multan - a MEASURED as-sold value against the "
     "declared spec. Two search-engine readings of this paper disagreed (1.0 percent wt against "
     "0.24-0.89 percent wt), which is precisely why it must be held and transcribed, not cited"),

    ("Int. J. Analytical Chemistry (Wiley, open access)",
     "Hasnain et al. 2026, stack emissions from zigzag and FCBTK brick kilns, Faisalabad",
     # the PDF is bot-blocked identically at PMC, Wiley pdfdirect and the Europe PMC API (403 or
     # a challenge page). The open-access FULL TEXT is served as HTML at the article address, so
     # that is what is held - the same content, and hashable.
     "https://pmc.ncbi.nlm.nih.gov/articles/PMC12869272/",
     "literature/hasnain_2026_kiln_stack_emissions_faisalabad.html", b"<",
     "measured stack SO2 by kiln technology and fuel mix, 30 FCBTK + 30 zigzag, March-April 2023. "
     "The only located test of the declared 0.25 sulfur retention, which the register applies "
     "identically to both technologies"),

    ("CDPR / IGC", "Investigating the Environmental and Economic Benefits of Energy Efficient Brick Kilns",
     "https://www.cdpr.org.pk/wp-content/uploads/2025/06/"
     "Investigating-the-Environmental-and-Economic-Benefits-of-Energy-Efficient-Brick-Kilns.-Report.pdf",
     "literature/cdpr_igc_energy_efficient_brick_kilns.pdf", b"%PDF",
     "LABORATORY ANALYSES OF COAL SAMPLED AT THE STUDIED KILNS - the exact acquisition the gap "
     "industry-coal-sulfur names. Table 2 (printed p.17) is reported to carry sulfur for "
     "Balochistan coal, Hyderabad coal and a mixed batch, with the authors cautioning that these "
     "are particular batches rather than average compositions. If those readings hold, they are a "
     "second, third and fourth as-fired Pakistani kiln-coal analysis against the ONE this round "
     "found, and they may corroborate the booked 4.5 percent rather than undercut it"),

    ("SAARC Energy Centre", "Pakistan country report on the brick sector",
     "https://www.saarcenergy.org/wp-content/uploads/2016/02/Pakistan-Report-on-Brick.pdf",
     "literature/saarc_pakistan_brick_sector_report.pdf", b"%PDF",
     "candidate coal quality and consumption for Pakistani kilns; the register's coal row is a "
     "resource range by coalfield, never an as-fired analysis"),

    ("Auditor-General of Pakistan", "Audit report on the Petroleum Division and OGRA 2022-23",
     "https://agp.gov.pk/SiteImage/Policy/AR%20DGAPNR%202022-23%20PNR%20_%20OGRA%20signed%20by%20AGP.pdf",
     "petroleum_gov/agp_audit_petroleum_division_ogra_2022_23.pdf", b"%PDF",
     "the audit of the regulator; candidate source for fuel-quality testing findings that OGRA's "
     "own State of Industry editions do not carry"),

    # Listed in the knowledge that it refuses. A negative that names what stands in is evidence;
    # an unlisted document is not.
    ("Elsevier (Case Studies in Chemical and Environmental Engineering)",
     "Optimization of brick kiln technology and fuel type, selected brick kilns in Lahore",
     "https://www.sciencedirect.com/science/article/pii/S230741082500152X",
     "literature/lahore_kiln_optimization.pdf", b"%PDF",
     "LAHORE-specific measured kiln stack emissions - the nearest thing to a direct observation of "
     "the district this work is about. Expected 403: Elsevier refuses unauthenticated fetches. The "
     "Faisalabad study above stands in, with its city difference declared"),
)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url, dest, magic):
    """Retrieve, verify the content is what was asked for, and write. Returns (bytes, how)."""
    how = ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read()
    except urllib.error.URLError as exc:
        # SOME PAKISTANI GOVERNMENT HOSTS OMIT THEIR INTERMEDIATE CERTIFICATE. agp.gov.pk serves a
        # valid certificate but not the chain above it, so Python cannot build a path while curl
        # can - macOS fetches the missing intermediate from the issuer named in the certificate.
        # This is a retry with the SAME verification, not a relaxation of it: no -k, no
        # ssl._create_unverified_context. If the certificate were actually untrusted, curl would
        # refuse too, and the attempt would be logged as the negative it is.
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        out = subprocess.run(["curl", "-sSL", "--max-time", "120", "-A", UA, url],
                             capture_output=True)
        if out.returncode != 0:
            raise ValueError("curl also refused: %s" % out.stderr.decode("utf-8", "replace")[:200])
        body, how = out.stdout, (" [obtained with curl: the host omits its intermediate "
                                 "certificate, so python cannot build the chain and macOS can. "
                                 "Verification was NOT disabled]")
    if not body.lstrip()[:len(magic)].startswith(magic):
        raise ValueError("unexpected content (first bytes %r)" % body[:12])
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(body)
    return len(body), how


def main():
    rows, attempts = [], []
    for source, label, url, rel, magic, why in TARGETS:
        dest = asset_path(RAW, rel)
        if os.path.exists(dest):
            status, note, size = "held", "already on disk; not re-fetched. %s" % why, os.path.getsize(dest)
        elif DRY:
            status, note, size = "dry-run", "would fetch. %s" % why, ""
        else:
            try:
                size, how = fetch(url, dest, magic)
                status, note = "fetched", why + how
            except Exception as exc:          # noqa: BLE001 - every failure is a logged negative
                status, note, size = "failed", "%s: %s -- wanted for: %s" % (type(exc).__name__, exc, why), ""
        digest = sha256(dest)[:16] if os.path.exists(dest) else ""
        rows.append({"date": TODAY, "source": source, "url": url, "file": "data/raw/" + rel,
                     "sha256_16": digest, "size_bytes": size, "status": status, "note": note})
        attempts.append({"attempt_date": TODAY, "dataset": "%s - %s" % (source, label),
                         "recipient": source, "url_tried": url,
                         "outcome": "fetched" if status in ("fetched", "held") else "discovery_failed",
                         "detail": "%s -> data/raw/%s" % (status, rel),
                         "next_step": "" if status in ("fetched", "held") else
                                      "the publisher refuses or moved the address; record what stands in "
                                      "rather than leaving the row silent"})
        print("%-8s %s" % (status, rel))
    if DRY:
        return 0
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="", encoding="utf-8") as h:
        if new:
            h.write("# The fuel-sulfur evidence acquisition (item 3): every attempt logged, hits and\n"
                    "# negatives alike. Documents land in data/raw/<source>/; sources/ is frozen.\n")
        w = csv.DictWriter(h, fieldnames=list(rows[0]), lineterminator="\n")
        if new:
            w.writeheader()
        w.writerows(rows)
    with open(ATTEMPTS, "a", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(attempts[0]), lineterminator="\n")
        w.writerows(attempts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

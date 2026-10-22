#!/usr/bin/env python3
"""Acquire the public evidence a second contribution-evidence brief (22 October 2026) pointed to.

WHAT IT IS FOR. docs/contribution_evidence_returned.md listed what the restricted layers could not
supply on 21 October. A follow-up brief named public places for most of it:
- FAOSTAT: the bulk catalogue (each domain's file date and size), the Emissions from Crops (GCE) and
  Emissions from Livestock (GLE) bulks, and the four assumption tables the Livestock Manure (EMN)
  methodology lists under Related Documents (typical animal mass, N excretion rates, manure-system
  shares, loss fractions);
- the open-access Slater et al. 2024 article by routes other than the ACS PDF link that returned 403;
- PBS's HIES page, for the 16 January 2026 correction to the Section 6 consumption microdata;
- Pakistani stove and manure studies (Aneeq & Mahmood 2022; Usman et al.; Ali et al. 2019; Zuhra et al.
  2025).
`scripts/holdings.py` found none of them held (2026-10-22).

TWO STAGES. Several addresses are not known in advance. A derived target is fetched only from an
address printed in bytes this script kept first (the FAOSTAT catalogue, a PBS page) or returned by a web
search on 2026-10-22 (named in its note). Addresses that are PATTERN-DERIVED say so in their notes: the EMN
methodological note (the GLE note's address with the domain code changed), and the four Related Documents
the EMN note names, tried beside it in the same folder. Every attempt gets a log row, hits, misses and
blocked addresses alike, and bytes are kept through pkinv.core.retention before anything reads them.

Usage:  PYTHONPATH=src python3 scripts/fetch_contribution_followup_evidence.py [--dry-run] [--only NAME ...]
Writes: data/raw/<source>/ (through the restricted-layer mount)
        data/raw/ACQUISITION_LOG_contribution_followup_20261022.csv
"""
import csv
import datetime as dt
import hashlib
import os
import sys

from pkinv.assets import asset_path
from pkinv.core import retention

LOG = asset_path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw",
                 "ACQUISITION_LOG_contribution_followup_20261022.csv")
FIELDS = ["retrieved_utc", "url", "local_path", "status", "sha256", "bytes", "note"]
DRY = "--dry-run" in sys.argv
ONLY = sys.argv[sys.argv.index("--only") + 1:] if "--only" in sys.argv else None

# (source directory, file name, url, accepted leading bytes, why)
TARGETS = [
    ("faostat", "faostat_bulk_catalogue_datasets_E.json",
     "https://bulks-faostat.fao.org/production/datasets_E.json", (b"{", b"["),
     "FAOSTAT bulk-download catalogue: each domain's file name, date and size, the version record for "
     "every FAOSTAT bulk held"),
    ("faostat", "faostat_documents_EMN.json",
     "https://faostatservices.fao.org/api/v1/en/documents/EMN/", (b"{", b"["),
     "FAOSTAT documents list for Livestock Manure (EMN): the methodology note and its Related Documents"),
    ("faostat", "faostat_documents_GCE.json",
     "https://faostatservices.fao.org/api/v1/en/documents/GCE/", (b"{", b"["),
     "FAOSTAT documents list for Emissions from Crops (GCE)"),
    ("faostat", "faostat_documents_RFN.json",
     "https://faostatservices.fao.org/api/v1/en/documents/RFN/", (b"{", b"["),
     "FAOSTAT documents list for Fertilizers by Nutrient (RFN): country notes on fertilizer years"),
    ("literature", "openalex_slater_2024_acsestair_4c00003.json",
     "https://api.openalex.org/works/doi:10.1021/acsestair.4c00003", (b"{",),
     "OpenAlex record for Slater et al. 2024: its open-access locations"),
    ("literature", "europepmc_slater_2024_search.json",
     "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:10.1021/acsestair.4c00003"
     "&format=json&resultType=core", (b"{",),
     "Europe PMC search for Slater et al. 2024: a PMC full text, if one exists"),
    ("literature", "slater_2024_acsestair_4c00003_full.html",
     "https://pubs.acs.org/doi/full/10.1021/acsestair.4c00003", (b"<",),
     "Slater et al. 2024 full-text HTML (ACS), Section 2.2.1 and Table 3 household activities"),
    ("pbs", "pbs_hies_2024_25_page.html",
     "https://www.pbs.gov.pk/content/household-integrated-economic-survey-hies-2024-25", (b"<",),
     "PBS HIES 2024-25 page: the downloads and the 16 January 2026 Section 6 correction notice"),
    ("literature", "openalex_search_aneeq_mahmood_2022.json",
     "https://api.openalex.org/works?search=Aneeq%20Mahmood%20improved%20cookstove%20Sindh", (b"{",),
     "OpenAlex search for Aneeq & Mahmood 2022 (improved mud stove, Sindh; Heritage and Sustainable "
     "Development)"),
    ("literature", "openalex_search_usman_lpg_stove.json",
     "https://api.openalex.org/works?search=Usman%20LPG%20cookstove%20thermal%20efficiency%20Pakistan",
     (b"{",), "OpenAlex search for Usman et al. (Pakistani LPG stove designs)"),
    ("literature", "openalex_search_ali_2019_buffalo_manure.json",
     "https://api.openalex.org/works?search=buffalo%20manure%20storage%20nitrogen%20NARC%20Islamabad",
     (b"{",), "OpenAlex search for Ali et al. 2019 (buffalo-manure storage experiment, NARC Islamabad)"),
    ("literature", "openalex_search_zuhra_2025_dairy_manure.json",
     "https://api.openalex.org/works?search=Zuhra%20dairy%20farms%20manure%20management%20Punjab",
     (b"{",), "OpenAlex search for Zuhra et al. 2025 (manure practices on 15 Central Punjab dairy farms)"),
]
# Derived targets: appended by hand after reading a kept discovery file, each naming the kept file whose
# bytes printed the address.
DERIVED = [
    ("faostat", "faostat_Emissions_crops_E_All_Data_(Normalized).zip",
     "https://bulks-faostat.fao.org/production/Emissions_crops_E_All_Data_(Normalized).zip", (b"PK",),
     "FAOSTAT Emissions from Crops (GCE), catalogue DateUpdate 2025-10-28: crop-residue N and synthetic-N "
     "activities beside their N2O (address from the kept bulk catalogue)"),
    ("faostat", "faostat_Emissions_livestock_E_All_Data_(Normalized).zip",
     "https://bulks-faostat.fao.org/production/Emissions_livestock_E_All_Data_(Normalized).zip", (b"PK",),
     "FAOSTAT Emissions from Livestock (GLE), catalogue DateUpdate 2025-10-28: manure-management and enteric "
     "emissions by species (address from the kept bulk catalogue)"),
    ("faostat", "faostat_fenix_documents_EMN.json",
     "https://fenixservices.fao.org/faostat/api/v1/en/documents/EMN/", (b"{", b"["),
     "FAOSTAT documents list for EMN on the fenixservices host (the faostatservices host returned 401): the "
     "methodology note and its Related Documents"),
    ("faostat", "faostat_fenix_documents_GCE.json",
     "https://fenixservices.fao.org/faostat/api/v1/en/documents/GCE/", (b"{", b"["),
     "FAOSTAT documents list for GCE on the fenixservices host"),
    ("faostat", "faostat_fenix_documents_RFN.json",
     "https://fenixservices.fao.org/faostat/api/v1/en/documents/RFN/", (b"{", b"["),
     "FAOSTAT documents list for RFN on the fenixservices host: country notes on fertilizer years"),
    ("faostat", "faostat_GLE_methodological_note_GLE_e.pdf", "https://files-faostat.fao.org/internal/GLE/GLE_e.pdf",
     (b"%PDF",), "FAOSTAT Emissions from Livestock methodological note (found by web search): the manure-N chain "
                 "and where its coefficient tables are published"),
    ("faostat", "faostat_EMN_methodological_note_EMN_e.pdf", "https://files-faostat.fao.org/internal/EMN/EMN_e.pdf",
     (b"%PDF",), "FAOSTAT Livestock Manure methodological note: PATTERN-DERIVED address (the GLE note's, domain "
                 "code changed); it lists the Related Documents holding the MMS shares and loss fractions"),
    ("faostat", "faostat_EMN_TAM_Country.csv", "https://files-faostat.fao.org/internal/EMN/TAM_Country.csv", (b"",),
     "EMN Related Document named by the EMN methodological note p.4 (typical animal mass by country and livestock type): PATTERN-DERIVED address beside the note"),
    ("faostat", "faostat_EMN_N_ExcrRate_Country.csv", "https://files-faostat.fao.org/internal/EMN/N_ExcrRate_Country.csv", (b"",),
     "EMN Related Document named by the EMN methodological note p.4 (N excretion rates by country and livestock type): PATTERN-DERIVED address beside the note"),
    ("faostat", "faostat_EMN_Share_MMS_Lvstck_Country.csv", "https://files-faostat.fao.org/internal/EMN/Share_MMS_Lvstck_Country.csv", (b"",),
     "EMN Related Document named by the EMN methodological note p.4 (shares of manure by country, management system and livestock type): PATTERN-DERIVED address beside the note"),
    ("faostat", "faostat_EMN_FracLoss_MMS_Lvstck_Country.csv", "https://files-faostat.fao.org/internal/EMN/FracLoss_MMS_Lvstck_Country.csv", (b"",),
     "EMN Related Document named by the EMN methodological note p.4 (fraction of N lost by country, management system and livestock type): PATTERN-DERIVED address beside the note"),
    ("pbs", "pbs_hies_index_page.html", "https://www.pbs.gov.pk/hies/", (b"<",),
     "PBS HIES index page (linked from the kept HIES 2024-25 page): the microdata downloads and any correction "
     "notice"),
    ("literature", "aneeq_mahmood_2022_hsd_v4i1_73_landing.html", "https://doi.org/10.37868/hsd.v4i1.73", (b"<",),
     "Aneeq & Mahmood 2022, Heritage and Sustainable Development 4(1), doi 10.37868/hsd.v4i1.73 (found by web "
     "search): an improved two-burner mud stove with chimney, Khipro, Sindh; WBT efficiency"),
    ("literature", "aneeq_mahmood_2022_hsd_v4i1_73.pdf",
     "https://hsd.ardascience.com/index.php/journal/article/download/73/65", (b"%PDF",),
     "Aneeq & Mahmood 2022, the article PDF (citation_pdf_url printed by the kept landing page)"),
    ("literature", "usman_2023_eds_s10668_022_02273_y_landing.html",
     "https://link.springer.com/article/10.1007/s10668-022-02273-y", (b"<",),
     "Usman et al. 2023, Environment, Development and Sustainability 25(6) 5427-5442, doi "
     "10.1007/s10668-022-02273-y (found by web search): two Pakistani LPG stoves under WBT 4.2.3; landing page "
     "and abstract only, the article is not open access"),
    ("literature", "ali_2019_jem_icrisat_oar_11234.html", "https://oar.icrisat.org/11234/", (b"<",),
     "Ali et al. 2019, Journal of Environmental Management 241 468-478 (ICRISAT OAR record 11234, found by web "
     "search): six-month buffalo-manure storage, N and C losses by storage treatment"),
]
NOT_FOUND = [
    ("Zuhra et al. 2025 (Central Punjab dairy-farm manure practices)",
     "named by the brief as an author-uploaded paper on ResearchGate, without title or DOI; an OpenAlex search "
     "and a web search on 2026-10-22 did not find it, so no address was fetched"),
]


def _log(row):
    fresh = not os.path.exists(LOG)
    with open(LOG, "a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        if fresh:
            writer.writeheader()
        writer.writerow(row)


def fetch(source, name, url, magic, why):
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    if DRY:
        print("would fetch %s -> data/raw/%s/%s" % (url, source, name))
        return True
    try:
        body = retention.get(url)
    except OSError as error:
        _log({"retrieved_utc": stamp, "url": url, "local_path": "", "status": "failed",
              "sha256": "", "bytes": "", "note": "%s; %s" % (why, error)})
        print("FAILED  %s: %s" % (name, error))
        return False
    if not body.lstrip().startswith(magic):
        _log({"retrieved_utc": stamp, "url": url, "local_path": "", "status": "not-a-document",
              "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
              "note": "%s; the response does not start with %r" % (why, magic)})
        print("REFUSED %s: not the expected file type" % name)
        return False
    path = retention.keep(body, source, name, url, note=why)
    _log({"retrieved_utc": stamp, "url": url,
          "local_path": os.path.relpath(path, os.path.dirname(os.path.dirname(LOG))),
          "status": "acquired", "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body), "note": why})
    print("kept    %s (%d bytes)" % (path, len(body)))
    return True


def main():
    misses = 0
    for source, name, url, magic, why in TARGETS + DERIVED:
        if ONLY is not None and name not in ONLY:
            continue
        misses += not fetch(source, name, url, magic, why)
    if not DRY:
        for title, why in NOT_FOUND:
            if ONLY is not None and not any(n in title for n in ONLY):
                continue
            _log({"retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "url": "", "local_path": "",
                  "status": "not-found", "sha256": "", "bytes": "", "note": "%s: %s" % (title, why)})
    return 0 if not misses else 1


if __name__ == "__main__":
    sys.exit(main())

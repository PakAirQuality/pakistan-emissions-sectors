"""What this release is called, resolved once.

WHY THIS EXISTS. The release named itself four different ways, and each artefact that stated
an identity stated a different one:

    CITATION.cff / .zenodo.json   "Pakistan Emissions Inventory (pkinv)"
    paper_national.tex            "the PakEmis inventory"
    references.bib                "{PakEmis} v1.0"  -- beside a note saying "release 1.0.0rc1"
    README.md                     "Pakistan National Greenhouse Gas Inventory"
    release_manifest.json         no product name at all

Worse, `CITATION.cff` gave `repository-code` and `license-url` as `pakistan-emissions-nowcast`,
which README describes as a DIFFERENT companion repository. That is the metadata Zenodo reads:
minting a DOI against it would have bound the archived release to the wrong repository.

None of this was catchable, because none of it is a number.

THE FAMILY. The anthropogenic greenhouse-gas product is PakEmis-GHG. The air-pollutant layer
already calls itself PakEmis-Air beta in the discussion and the supplement. A land-sector
product would be PakEmis-Land, and it is named here so that keeping it out of the GHG totals
stays a boundary decision rather than an omission.

The version itself stays in __init__.py; this module imports it rather than restating it, for
the same reason everything else here exists.
"""
from pkinv import __version__

# The product family, and this release's member of it.
FAMILY = "PakEmis"
# One canonical product name. The corpus alternated between "PakEmis-GHG" and "PakEmis";
# the reviewer asked for one form, the titles and abstracts already use the short one, and
# the repository name (PakEmis-GHG) stays what it is - a repository is not a product.
PRODUCT = "PakEmis"
AIR_PRODUCT = "PakEmis-Air"
LAND_PRODUCT = "PakEmis-Land"

LONG_TITLE = ("PakEmis: greenhouse gas and air pollutant emissions in Pakistan, "
              "July 2015–June 2025, excluding LULUCF")

# The import package, which is not the product name and never has been.
PACKAGE = "pkinv"

# THE REPOSITORY A READER CAN OPEN (rc68). Through rc67 this named the working repository,
# which is private: every manuscript printed a URL that returned 404 to its readers. rc68
# published a COPY of the release there. From rc69 the work is committed there directly, and
# the third-party source documents stay in the private checkout as the restricted layers
# (pkinv.core.layers; docs/restricted_layers.md says what and why). Releases through rc68
# were made in the private repository, so the commits their manifests name are not in the
# public history - REPOSITORY_NOTE says so wherever the manifest gives the URL.
OWNER = "PakAirQuality"
REPO = "pakistan-emissions-sectors"
REPO_URL = "https://github.com/%s/%s" % (OWNER, REPO)
LICENCE_URL = "%s/blob/main/LICENSE" % REPO_URL
REPOSITORY_NOTE = ("the public development repository, without the third-party source "
                   "documents, whose checksums it lists; the git block names its commit, and "
                   "restricted_layers the commit of the private checkout that holds the "
                   "documents. Every release candidate through 1.0.0rc68 was made in that "
                   "private repository, and their commits are not in the public history")

# Where the dataset can be explored interactively, and whose project it is. The explorer is
# deployed separately from the archive and can serve an earlier release than the one a
# reader holds, so nothing here or in the manuscripts says which release it serves.
EXPLORER_URL = "https://emissions.hawanama.org"
INITIATIVE = "Pakistan Air Quality Initiative"
INITIATIVE_URL = "https://pakairquality.com"

# A real, separate repository: satellite nowcasting of agricultural emissions between census
# years. It depends on this one. It is not where this one lives, and it did not move with it.
COMPANION_OWNER = "RehanAhmad13"
COMPANION_REPO = "pakistan-emissions-nowcast"
COMPANION_URL = "https://github.com/%s/%s" % (COMPANION_OWNER, COMPANION_REPO)

SCHEMA = "pkinv.release/v1"

# THE SUBMISSION STATUS IS DATA, NOT PROSE (rc19, the fourteenth review). The
# papers/pdf README said the national article "is submitted" - written when a
# submission was imminent, false at the release it shipped with, and invisible
# to the identity sweep because that README sat in its SKIP list. The status now
# lives here, the manifest carries it, and the sweep bans any "is submitted"
# claim in either README while this constant says otherwise. When the article is
# actually submitted, set "submitted" and record the journal's identifier.
MANUSCRIPT_STATUS = "preparation"
SUBMISSION_IDENTIFIER = None

# v1.0.0: the national manuscript is a data-description article (Earth System Science Data)
# and the sector manuscripts are its Sector Technical Notes, numbered here and nowhere else.
# TN08 (industrial combustion) is numbered and reserved: its text is written after the
# Explorer shell. Paths and document names (papers/<sector>/) do not change - 1,127 sector
# claims key on them - only the titles, the first-page banner and the deposited PDF names.
NATIONAL_ARTICLE_TITLE = ("PakEmis %s: greenhouse gas and air pollutant emissions in Pakistan, "
                          "July 2015–June 2025" % __version__)
NATIONAL_ARTICLE_VENUE = "Earth System Science Data (data-description article, in preparation)"
SECTOR_ORDER = ("agriculture", "power", "transport", "waste", "residential", "fugitives", "ippu",
                "railways", "aviation")
RESERVED_TECHNICAL_NOTES = ("industry",)
TECHNICAL_NOTES = {"agriculture": "TN01", "power": "TN02", "transport": "TN03", "waste": "TN04",
                   "residential": "TN05", "fugitives": "TN06", "ippu": "TN07", "industry": "TN08",
                   "railways": "TN09", "aviation": "TN10"}


def technical_note(sector):
    """The TN code of a sector module (KeyError for anything that is not one)."""
    return TECHNICAL_NOTES[sector]


def tn_pdf(sector):
    """The deposited file name of a technical note: PakEmis_TN01_agriculture.pdf. The
    shipped papers/pdf/<sector>_paper.pdf names are kept until the release build renames."""
    return "PakEmis_%s_%s.pdf" % (TECHNICAL_NOTES[sector], sector)


def cite_name():
    """How the product is named in a citation: the product and the release it is."""
    return "%s %s" % (PRODUCT, __version__)

"""The manuscript registry and the generic accessors every paper test shares.

Split from tests/test_paper_numbers.py in rc35; the shim of that name
re-exports the data and helpers. Test modules import only from the four data
modules (_common, doc_claims, tables, quantity_policy), never from each other.
"""

from pkinv.assets import asset_path
import collections
import csv
import io
import filecmp
import glob
import json
import math
import os
import re
import sys
import unittest

from pkinv import paths
from pkinv.paths import PAPER_NATIONAL_MAIN, PAPER_NATIONAL_SECTIONS, PAPER_NATIONAL_VERSIONS  # noqa: E402
from pkinv.core.io import read_rows


ROOT = paths.ROOT


OUT = paths.OUTPUTS


SECTORS = ("agriculture", "waste", "transport", "power", "residential", "ippu", "fugitives",
           "railways", "aviation")


# Every manuscript in this repository, and where its prose lives. Until this existed the whole
# file pointed at the agriculture paper alone, so the national manuscript and the sector
# documents could drift from the engine with nothing failing. A document listed here with no
# claims is still covered by the figure and layout checks, which are defined by what is on
# disk rather than by what someone remembered to list.
DOCS = {"national": PAPER_NATIONAL_SECTIONS}


# The national supplement keeps its prose inline rather than in sections/, so its "sections
# directory" is the manuscript directory and its one section is supplement.tex. Listing it as
# a document is what puts its quantities under the same coverage rule as the paper's - the
# air-pollutant figures moved there, and moving a number must not move it out of coverage.
DOCS["national-supplement"] = PAPER_NATIONAL_MAIN
# The release record is prose too, and it was the last place a superseded vintage could live.
# docs/reproducibility.md printed 455.14 / 450.01 Mt against a current 448.00 / 442.88, and
# still described the inventory as a sum across reference years three rounds after the sectors
# were harmonised onto one - in the file that calls itself the authority on what this release
# is. Nothing read it, so nothing failed. It is a document here now.
#
# The coverage sweep skips sections that are not .tex, so listing these enrols them in the
# claims check without demanding LaTeX markup of a markdown file: the numbers named below are
# anchored to outputs, and the rest of the prose is not swept.
# v2, the compact rewrite, as a DOCUMENT but deliberately NOT as a MANUSCRIPTS entry.
# DOCS answers "where does this document's prose live", which is what the claim and table
# resolvers need; MANUSCRIPTS drives the build-artefact guards (layout, figure freshness,
# provenance block, PDF staleness) and those belong to versions the release actually ships.
#
# This is not a new idea, it is a latent error the version move exposed: tab:categories is
# registered in technical_supplement.tex, which is v2's supplement, under the document key
# "national-supplement", whose root is the SHIPPED version. Both resolved to
# paper_national/ before the move, so the mis-key was invisible; afterwards the table
# simply could not be found.
DOCS["national-v3"] = os.path.join(PAPER_NATIONAL_VERSIONS, "v3")
DOCS["release-record"] = os.path.join(ROOT, "docs")
DOCS.update({n: os.path.join(ROOT, "papers", n, "sections") for n in SECTORS})


# Figure directories and the class option each manuscript compiles under. Only two-column
# documents can have a table overrun its column, so the layout rule applies to 5p documents;
# the national article compiles one-column under the Copernicus class ("copernicus", the
# ESSD manuscript layout) and is outside that rule like the a4 supplements.
# (name, root, class option, main tex). The fourth field is what killed three scattered
# `if doc == "national-supplement"` special cases: two documents can share a root, so the
# registry has to say which .tex each one IS. Sector supplements are listed as documents in
# their own right -- until they were, their S*.tex inputs sat outside every
# MANUSCRIPTS-driven guard and five shipped supplement PDFs carried no provenance block.
MANUSCRIPTS = [("national", PAPER_NATIONAL_MAIN, "copernicus",
                "paper_national.tex"),
               ("national-supplement", PAPER_NATIONAL_MAIN, "a4",
                "supplement.tex")]


MANUSCRIPTS += [(n, os.path.join(ROOT, "papers", n), "5p", "paper.tex") for n in SECTORS]


# Class options read from each supplement's own \documentclass: two are two-column 5p
# (aviation, railways) and fall under the wide-table layout rule like the papers do.
MANUSCRIPTS += [("%s-supplement" % n, os.path.join(ROOT, "papers", n), cls,
                 "supplement.tex")
                for n, cls in (("agriculture", "a4"), ("aviation", "5p"),
                               ("fugitives", "a4"), ("railways", "5p"),
                               ("transport", "a4"))]


def _doc_path(doc, section):
    """Resolve (document, section file) to a path. Notes are one file, papers are a directory."""
    return os.path.join(DOCS[doc], section)


def _main_tex(root, main=None):
    """The manuscript's own .tex. The registry names it explicitly (fourth MANUSCRIPTS
    field) because two documents can share a root; the no-argument fallback survives for
    callers that mean "the paper in this directory"."""
    # The no-argument fallback used to be "the .tex named after its directory", which
    # worked while the national article sat in paper_national/. Under versioning the
    # directory is called v1, so basename(root)+".tex" became v1.tex and three title
    # checks errored out. The article's own name is a third candidate now; the registry
    # still names it explicitly, so this is only for callers that mean "the paper here".
    candidates = ((main,) if main
                  else ("paper.tex", os.path.basename(root) + ".tex",
                        "paper_national.tex"))
    for name in candidates:
        path = asset_path(root, name)
        if os.path.exists(path):
            return path
    raise IOError("no manuscript .tex under %s (wanted %s)" % (root, candidates))


def _inputs_of(tex_path, root):
    """The files a document actually \\inputs, in document order.

    Transport's supplement shares a sections/ directory with its paper, so "which
    files belong to this document" can no longer be answered by globbing that
    directory - it has to be read from the document itself.

    IT USED TO MATCH sections/ ONLY, and that is how a release shipped every PDF with a
    stale provenance box. paper_common/release_cover.tex is \\input by eighteen documents
    and carries the release version, the commit and the manifest digest; matching only
    sections/ meant regenerating it never marked a single paper stale. Relative inputs
    are resolved against the document's own directory, so ../../paper_common/... lands on
    the real path.

    NESTED INPUTS ARE FOLLOWED (the ESSD re-targeting): the national article's sections are
    containers that \\input the fragments, and a graph read one level deep would have
    dropped every fragment from the staleness, prose and reference sweeps at once. Each
    file is listed once, in first-visit document order."""
    found = []
    seen = set()

    def walk(path):
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        text = re.sub(r"(?m)^\s*%.*$", "", text)          # ignore commented-out inputs
        for m in re.finditer(r"\\input\{([^}]+)\}", text):
            target = m.group(1)
            if not target.endswith(".tex"):
                target += ".tex"
            base = root if target.startswith("sections/") else os.path.dirname(path)
            resolved = os.path.normpath(os.path.join(base, target))
            if os.path.exists(resolved) and resolved not in seen:
                seen.add(resolved)
                found.append(resolved)
                walk(resolved)

    walk(tex_path)
    return found


def _figures_of(tex_paths, root):
    """The figure files a document draws, resolved through its \\graphicspath.

    A manuscript's sources are not only its prose. `make all` regenerates every PNG from the
    engine and `sync_figures` copies them into the manuscript directories, so a rebuild that
    moves a chart leaves the shipped PDF drawing the OLD one - with every number in the text
    still correct, every anchor still passing, and nothing in the suite able to see it. That
    is the same failure this file's PDF check was written for, one level down from the text.
    """
    # THE \graphicspath IS READ, not assumed to be "figures/ beside the document". The
    # national paper's figures are SHARED across its versions, so the article at
    # paper_national/versions/v1/ declares \graphicspath{{../../figures/}} and neither
    # <root>/figures/ nor <root>/<name> resolves. The staleness check's own positive
    # control caught that as "national resolved no figures" rather than passing on an
    # empty list, which is the only reason this is a two-line fix and not a silent hole.
    roots = [root]
    for tex in tex_paths:
        if not os.path.exists(tex):
            continue
        with open(tex, encoding="utf-8") as handle:
            head = re.sub(r"(?m)^\s*%.*$", "", handle.read())
        for decl in re.finditer(r"\\graphicspath\{((?:\{[^}]*\})+)\}", head):
            for one in re.finditer(r"\{([^}]*)\}", decl.group(1)):
                roots.append(os.path.normpath(
                    os.path.join(os.path.dirname(tex), one.group(1))))
    out = []
    for tex in tex_paths:
        if not os.path.exists(tex):
            continue
        with open(tex, encoding="utf-8") as handle:
            text = re.sub(r"(?m)^\s*%.*$", "", handle.read())
        for name in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", text):
            base = name.group(1)
            candidates = [os.path.join(r, base) for r in roots]
            candidates += [os.path.join(root, "figures", base), asset_path(root, base),
                           os.path.normpath(os.path.join(os.path.dirname(tex), base))]
            for candidate in candidates:
                if os.path.exists(candidate):
                    out.append(candidate)
                    break
    return out


def _sector_row(name):
    for r in _rows("national_all_sectors.csv"):
        if r["sector"] == name:
            return r
    raise KeyError(name)


def _sector(name, col="co2e_Mt_AR5"):
    return float(_sector_row(name)[col])


def _csv_rows(out_name):
    """Every row of one outputs/ CSV, as dicts.

    The `#` filter is not decoration. Outputs in this release carry header comments - the
    ADM2 views explain why they hold no per-cell uncertainty, the joint-uncertainty and
    product-facts tables explain what they are - and a DictReader without this reads the
    first comment as the header and every subsequent lookup raises KeyError. That has now
    happened four times in one release, in four different readers, each time on the day
    someone finally wrote a comment. Every other reader in the repository already filters.
    """
    import csv as _csv
    with open(os.path.join(OUT, out_name), newline="", encoding="utf-8") as handle:
        return list(_csv.DictReader(line for line in handle
                                    if not line.startswith("#")))


def _transport_year():
    """The transport sector's reference year, so year-named outputs follow the sector."""
    from pkinv.sectors.transport.data import TransportData
    return TransportData().year


def _waste_year():
    from pkinv.sectors.waste.data import WasteData
    return WasteData().year


def _load_repo_script(name):
    """Import a scripts/*.py generator as a module, so a test can call render() and
    compare the committed artefact against a fresh regeneration. Same helper the sector
    appendix tests use; lifted here because the README needs it too."""
    import importlib.util
    path = os.path.join(ROOT, "scripts", name)
    spec = importlib.util.spec_from_file_location(name[:-3], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sector_alt(name, col="co2e_Mt_AR5"):
    """The same sector under configuration L, the retained alternative (the ledger rollup).

    Through rc66 this read the survey rollup, then the alternative; since rc67 the survey
    reading is the reference and the alternative is configuration L. It keeps its own
    getter so a reader need not obtain it by subtraction."""
    for r in _rows("national_all_sectors_ledger.csv"):
        if r["sector"] == name:
            return float(r[col])
    raise KeyError(name)


def _cell(fname, key_col, key, col):
    """One value from any sector output, matched on a key column."""
    for r in _rows_banner(fname):
        if r[key_col] == key:
            return float(r[col])
    raise KeyError((fname, key))


def _sum_where(fname, col, **match):
    return sum(float(r[col]) for r in _rows_banner(fname)
               if all(r[k] == v for k, v in match.items()))


def _sum_prefix(fname, col, key, prefix):
    return sum(float(r[col]) for r in _rows_banner(fname) if r[key].startswith(prefix))


def _first_where(fname, col, **match):
    # BANNER-AWARE. These shared selectors read whichever product a claim names, and a
    # product may GROW a banner - power_climatetrace_plants did, to say that its
    # comparator applies one intensity per fuel class. A non-banner-aware read then takes
    # the first '#' line as the header and the claim errors. For a product with no banner
    # the two readers are identical, so nothing else changes.
    for row in _rows_banner(fname):
        if all(row[key] == value for key, value in match.items()):
            return float(row[col])
    raise KeyError((fname, match, col))


def _min_where(fname, col, **match):
    values = [float(row[col]) for row in _rows_banner(fname)
              if all(row[key] == value for key, value in match.items())]
    if not values:
        raise KeyError((fname, match, col))
    return min(values)


def _max_where(fname, col, **match):
    values = [float(row[col]) for row in _rows_banner(fname)
              if all(row[key] == value for key, value in match.items())]
    if not values:
        raise KeyError((fname, match, col))
    return max(values)


def _rows(name):
    return read_rows(os.path.join(OUT, name), comments=False)


def _rows_banner(name):
    """Rows of an output that OPENS WITH A '#' COMMENTARY BLOCK.

    _rows above passes comments=False, so it reads a banner line as the header row. Most
    published products carry no banner and are fine; the ones that document themselves in
    place need this. The alternative - stripping the banner so the claims reader can cope -
    would delete the documentation to suit the tool.
    """
    return read_rows(os.path.join(OUT, name))


def _data_rows(relpath):
    """Rows of a CSV under data/ - for source constants (factors, params, activity)."""
    return read_rows(asset_path(ROOT, 'data', relpath), comments=False)


def _data_rows_nocomment(relpath):
    """Same, for the registries whose files open with a # commentary block."""
    return read_rows(asset_path(ROOT, 'data', relpath))

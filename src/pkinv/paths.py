"""Repository paths, resolved once.

Every module used to compute its own root as `os.path.join(os.path.dirname(__file__),
"..", "..")`, which hardcodes how deep that module sits. Moving a file then silently
redirected its output: `os.makedirs(..., exist_ok=True)` creates the wrong directory
rather than raising, so the pipeline writes CSVs into `src/` and still reports success.

Resolution order:
  1. $PKINV_ROOT, for a non-editable install or a relocated data directory.
  2. The first ancestor of this file holding both `pyproject.toml` and `data/`. This
     searches rather than counting `..` levels, so moving modules around inside the
     package cannot break it.

Paths are `str`, not `pathlib.Path`: callers concatenate and call `.startswith` on them,
and this module exists to remove a whole class of bug, not to introduce a new one.
"""
import os

_MARKERS = ("pyproject.toml", "data")


def _find_root():
    env = os.environ.get("PKINV_ROOT")
    if env:
        return os.path.abspath(env)
    here = os.path.dirname(os.path.abspath(__file__))
    while True:
        if all(os.path.exists(os.path.join(here, m)) for m in _MARKERS):
            return here
        parent = os.path.dirname(here)
        if parent == here:                       # reached the filesystem root
            raise RuntimeError(
                "cannot locate the repository root from %s; set PKINV_ROOT to the "
                "checkout containing pyproject.toml and data/" % __file__)
        here = parent


ROOT = _find_root()
DATA = os.path.join(ROOT, "data")
OUTPUTS = os.path.join(ROOT, "outputs")
DOCS = os.path.join(ROOT, "docs")
SRC = os.path.join(ROOT, "src")

# THE NATIONAL PAPER IS VERSIONED, and this is the single place that says which version the
# release builds, hashes and ships. paper_national/versions/<v>/ holds one self-contained
# version - its main .tex, its supplement, its sections/ and its generated/ - while
# paper_national/figures/ and paper_national/queries/ are shared, because they are inputs
# to every version rather than part of any one.
#
# Before this existed the article sat at paper_national/ and a second candidate
# (pakemis_rewritten.tex) sat beside it at the same level, so "the paper" and "a draft of
# the paper" were indistinguishable by path and ~160 references hard-coded the one layout.
# Promoting a version is now two strings: PAPER_NATIONAL_CURRENT here and NATIONAL_VERSION
# in the Makefile. tests/test_paper_versions.py holds them to agreeing with each other,
# with the CURRENT symlink and with what is on disk.
PAPER_NATIONAL = os.path.join(ROOT, "paper_national")
PAPER_NATIONAL_VERSIONS = os.path.join(PAPER_NATIONAL, "versions")
PAPER_NATIONAL_CURRENT = "v1"
PAPER_NATIONAL_MAIN = os.path.join(PAPER_NATIONAL_VERSIONS, PAPER_NATIONAL_CURRENT)
PAPER_NATIONAL_SECTIONS = os.path.join(PAPER_NATIONAL_MAIN, "sections")
PAPER_NATIONAL_GENERATED = os.path.join(PAPER_NATIONAL_MAIN, "generated")
PAPER_NATIONAL_FIGURES = os.path.join(PAPER_NATIONAL, "figures")
PAPER_NATIONAL_QUERIES = os.path.join(PAPER_NATIONAL, "queries")
# Relative forms, for the places that build repo-relative strings rather than filesystem
# paths - the release manifest's product list, the deposit audit and the doc globs.
PAPER_NATIONAL_REL = "paper_national"
PAPER_NATIONAL_MAIN_REL = "paper_national/versions/%s" % PAPER_NATIONAL_CURRENT

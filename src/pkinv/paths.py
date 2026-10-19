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

"""Shared test infrastructure - NOT a test module.

unittest has no conftest hook, so the shared pieces live in an ordinary
module that discover never collects (the name does not match test*.py). Everything a test file used to hand-roll is here:

  ROOT, DATA, OUTPUTS, DOCS   from pkinv.paths - the repo root found by marker
                              search, never by counting ".." (which broke one
                              level down, silently)
  OUT                         the tests' historic name for OUTPUTS
  read_rows, write_table      the core.io kernel, re-exported
  rows(name, base=OUTPUTS)    an outputs/ table by basename
  data_rows(relpath)          a data/ table by relative path
  scripts_on_path()           for the six tests that import a scripts/ module
                              by bare name (scripts/ is not a package)
  load_script(name)           a scripts/ module by file path
  cached_build(...)           grid_cube.build() once per process per argument set,
                              with a mutation guard (see the block at the foot)

The 34 `sys.path.insert(0, ROOT/src)` lines this replaced were redundant:
the package is editable-installed (.venv's .pth resolves pkinv), and the
Makefile/CI invoke the suite from that venv. The six scripts/ insertions were
the only load-bearing ones.
"""

from pkinv.assets import asset_path
import importlib.util
import os
import sys

from pkinv import paths
from pkinv.core import layers
from pkinv.core.io import read_rows, write_table  # noqa: F401  (re-exported)

ROOT, DATA, OUTPUTS, DOCS = paths.ROOT, paths.DATA, paths.OUTPUTS, paths.DOCS
OUT = OUTPUTS
SCRIPTS = os.path.join(ROOT, "scripts")


def scripts_on_path():
    """Put scripts/ on sys.path for bare-name imports (call before the import)."""
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)


def load_script(name):
    """scripts/<name>.py as a module, loaded by file path."""
    stem = name[:-3] if name.endswith(".py") else name
    spec = importlib.util.spec_from_file_location(
        stem, os.path.join(SCRIPTS, stem + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FILE_INVENTORY = os.path.join(ROOT, "FILE_INVENTORY.csv")


def in_validation_package():
    """True when the tree the suite runs in is a built validation package rather than
    the repository (rc40): the package carries FILE_INVENTORY.csv at its root."""
    return os.path.exists(FILE_INVENTORY)


def presentation_layer():
    """Relative paths of the validation package's READING INDEX - presentation copies of
    canonical files under the specification's names, views computed from them, and the
    package's own records, logs and environment folder - as FILE_INVENTORY.csv declares
    them. Empty in the repository. Tests that enumerate outputs/ or data/ to assert
    'every file here is a registered product' subtract this set, because those files are
    not products of the build; they are the index a reviewer reads them through, and
    tests/validation/test_presentation_identity.py holds each copy to its source."""
    if not in_validation_package():
        return frozenset()
    layer = set()
    for r in read_rows(FILE_INVENTORY):
        if (r.get("generated_or_source") in ("presentation_copy", "view", "generated")
                or r.get("artifact_role") in ("register", "record", "log", "environment")):
            layer.add(os.path.normpath(r["relative_path"]))
    return frozenset(layer)


def rows(name, base=OUTPUTS, comments=True):
    return read_rows(os.path.join(base, name), comments=comments)


def data_rows(relpath, comments=True):
    return read_rows(asset_path(DATA, relpath), comments=comments)


_unshipped = None


def unshipped_registered():
    """frozenset of repo-relative paths a built package registers and does not carry - the
    NOT INCLUDED rows of its data/SOURCE_MANIFEST.csv (5,273 in rc41, 15.8 GB). Empty in the
    repository, where nothing is registered-not-held."""
    global _unshipped
    if _unshipped is None:
        found = set()
        path = asset_path(ROOT, "data", "SOURCE_MANIFEST.csv")
        if in_validation_package() and os.path.exists(path):
            for row in read_rows(path):
                if row.get("relative_path_or_not_included") == "NOT INCLUDED":
                    found.add(row["source_document_id"].rstrip("/"))
        _unshipped = frozenset(found)
    return _unshipped


LAYERS_ABSENT = "restricted layers absent:"


def require_layers(what):
    """Skip a test that reads the restricted layers (third-party documents, their git
    history) when a public clone has none mounted; do nothing where they are present.

    rc69. The prefix is fixed because tests/test_layers_exercised.py and the published test
    record count it: a run on the full tree must show ZERO such skips, and an absent-mode
    run must skip exactly the set pinned in data/catalog/restricted_gated_tests.txt. A
    broken mount raises (layers.LayersError) rather than skipping."""
    import unittest
    if not layers.present(ROOT) and layers.mode(ROOT) != "package":
        raise unittest.SkipTest("%s %s" % (LAYERS_ABSENT, what))


LARGE_NOT_BUILT = "large product not built:"


def readable(rel_path):
    """True unless the path belongs to restricted layers this checkout does not mount (rc69).
    For tests that check a list of cited documents: the public rows are still checked in a
    public clone, and only the rows naming a document it cannot hold are passed over."""
    return layers.present(ROOT) or layers.mode(ROOT) == "package" \
        or not restricted(rel_path)


def restricted(rel_path):
    """Restricted by its own path or by where the asset catalog stores it: documents are
    still cited by historical paths (data/gis/cod_ab/... for data/shared/gis/cod_ab/...)."""
    if layers.is_restricted(rel_path):
        return True
    physical = os.path.relpath(asset_path(ROOT, rel_path), ROOT)
    return layers.is_restricted(physical)


def require_built(*rel_paths):
    """Skip a test that reads one of this project's own products too large for GitHub when a
    clone has not built it (rc69): the three are ignored by git and ship in the deposit
    (layers.TOO_LARGE). Any other missing product still fails."""
    import unittest
    paths = rel_paths or layers.TOO_LARGE
    missing = [p for p in paths if not os.path.exists(os.path.join(ROOT, p))]
    if not missing:
        return
    unexpected = [p for p in missing if p not in layers.TOO_LARGE]
    if unexpected:
        raise AssertionError("products missing: %s" % "; ".join(unexpected))
    raise unittest.SkipTest("%s %s" % (LARGE_NOT_BUILT, "; ".join(missing)))


RELEASE_TIME = "release-time check:"


def release_time_check(what):
    """Skip, when PKINV_RELEASE_CHECKS=0, a test that holds only at a release commit.

    rc69. The work is now committed in the public repository one change at a time, and its
    CI runs on every push. A few tests compare the committed RELEASE bookkeeping (release
    manifest, deposit manifest, deposit archives) with the content, and between a content
    commit and the next `make release-fixpoint` they fail by design - the bookkeeping is
    regenerated once per release, not once per commit. The public CI sets the variable and
    prints how many tests it skipped this way; a maintainer's run, the release path and the
    published test record never set it, so at a release every one of these runs."""
    import unittest
    if os.environ.get("PKINV_RELEASE_CHECKS") == "0":
        raise unittest.SkipTest("%s %s" % (RELEASE_TIME, what))


def require_documents(*rel_paths):
    """Skip, inside a validation package, a test that needs a source document the package
    registers and does not carry; fail, everywhere, when the document is simply missing.

    rc42 (the twentieth review's gate 14). The package ships no third-party documents
    (sources/, data/raw/, data/cache/ - 15.8 GB, user-gated), so the tests that re-read them
    failed inside every package and were carried as a 32-name KNOWN_EXCEPTION. They are a
    separate gate now: in the repository this helper does nothing and a missing document
    fails the test as it always did; inside a package a missing path that data/raw_manifest.csv
    registers (as a file, or as a file under the named directory) raises SkipTest with the
    reason `document vault not mounted: <path>`, which validate.sh --documents DIR turns
    into a run over a mounted vault. A missing path that is NOT registered still fails: the
    skip is for absence by design, never for absence by accident.
    """
    import unittest
    missing = [p for p in rel_paths if not os.path.exists(asset_path(ROOT, p))]
    if not missing:
        return
    if not in_validation_package():
        # rc69: a public clone without the restricted layers holds none of the documents,
        # by design. Absent only if layers says so - a missing document in a checkout
        # that HAS the layers still fails, as it always did.
        if layers.mode(ROOT) == "absent" and all(restricted(p) for p in missing):
            raise unittest.SkipTest("%s %s" % (LAYERS_ABSENT, "; ".join(missing)))
        return
    unshipped = unshipped_registered()
    unregistered = []
    for p in missing:
        key = p.rstrip("/")
        # skippable only for a document the PACKAGE ITSELF registers as not included
        # (data/SOURCE_MANIFEST.csv, written by the packager from data/raw_manifest.csv);
        # a missing file the package does not so register is absent by accident
        if key in unshipped or any(r.startswith(key + "/") for r in unshipped):
            continue
        unregistered.append(p)
    if unregistered:
        raise AssertionError("documents missing and not registered in data/raw_manifest.csv: %s"
                             % "; ".join(unregistered))
    raise unittest.SkipTest("document vault not mounted: %s" % "; ".join(missing))


# ---------------------------------------------------------------------------------------
# THE SHARED CUBE (speed, rc55 preparation). grid_cube.build() costs 4-6 seconds and the
# suite called it TWENTY-FOUR times in six modules, about 132 seconds of a 616-second run.
# Two of those modules - test_grid_cube_period and test_spatial_by_year - performed the
# IDENTICAL nine-period sweep, and three more each rebuilt the reference cube. Ten distinct
# arguments were behind the twenty-four calls.
#
# THE MEMO LIVES HERE AND NOT IN grid_cube.build(). Two reasons, both load-bearing:
#
#   1. test_annual_grid_gates.test_one_period_built_alone_matches_the_nine_period_run builds
#      the same period TWICE ON PURPOSE and compares the two pattern-hash maps. A memo inside
#      build() would hand it the same object twice and the test could no longer fail. That is
#      the defect class retracted in tests/test_industrial_coal_decision.py - a test that
#      pins its own answer - and it is not being reintroduced one level down. That call site
#      keeps calling grid_cube.build() directly, and this helper is opt-in everywhere else.
#   2. A memo in production would change the builder's own allocation behaviour, which the
#      spatial family's determinism and isolation gates are partly there to observe.
#
# THE RESULT IS SHARED AND MUTABLE, so a consumer that wrote into it would silently change
# another module's input. Every cache HIT re-fingerprints the cached object first and fails
# loudly if it moved. The last consumer of a key is unguarded by construction (nothing hits
# after it); tests/test_shared_fixtures.py proves the fingerprint actually detects a planted
# mutation, so the guard is a check and not a comfort.
_CUBE_CACHE = {}
_CUBE_PRINT = {}


def _fingerprint(obj, depth=0):
    """A structural digest that moves when a value, a length or a key set moves.

    numpy arrays digest as (shape, dtype, sum) - a mutated cell moves the sum, and the sum
    of a 12x267x340 float64 array costs about a millisecond. Everything else digests by
    repr, which is exact for the dicts, lists, strings and floats the cube carries.
    """
    if depth > 6:
        return "..."
    if hasattr(obj, "shape") and hasattr(obj, "dtype"):        # numpy, without importing it
        return "nd%s%s%.17g" % (obj.shape, obj.dtype, float(obj.sum()))
    if isinstance(obj, dict):
        return "{%s}" % ",".join("%r:%s" % (k, _fingerprint(obj[k], depth + 1))
                                 for k in sorted(obj, key=repr))
    if isinstance(obj, (list, tuple)):
        return "[%d:%s]" % (len(obj), ",".join(_fingerprint(v, depth + 1) for v in obj))
    return repr(obj)


def cached_build(period=None, ledger=True, with_district_factors=True):
    """grid_cube.build() with the identical arguments, computed once per suite process.

    PeriodKeys is a namedtuple, so it is the cache key itself - there is no id to derive and
    no spelling to get wrong. Call grid_cube.build() directly when a test's point is that
    building twice gives the same answer.
    """
    from pkinv.report import grid_cube
    key = (period or grid_cube.REFERENCE, ledger, with_district_factors)
    if key in _CUBE_CACHE:
        now = _fingerprint(_CUBE_CACHE[key])
        if now != _CUBE_PRINT[key]:
            raise AssertionError(
                "the shared cube for %s was MUTATED by an earlier test: the fingerprint moved "
                "since it was built. A consumer of _support.cached_build() wrote into the "
                "result, so every later consumer of this key was reading someone else's edit. "
                "Find the writer; do not copy the cube to work around it."
                % (key[0].period_id,))
        return _CUBE_CACHE[key]
    result = grid_cube.build(period=period, ledger=ledger,
                             with_district_factors=with_district_factors)
    _CUBE_CACHE[key] = result
    _CUBE_PRINT[key] = _fingerprint(result)
    return result

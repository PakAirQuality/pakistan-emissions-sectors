"""Shared test infrastructure - NOT a test module.

unittest has no conftest hook, so the shared pieces live in an ordinary
module that discover neither collects (the name does not match test*.py)
nor counts (paper_numbers.doc_claims._test_function_count only reads
test_*.py). Everything a test file used to hand-roll is here:

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
    if not in_validation_package():
        return
    missing = [p for p in rel_paths if not os.path.exists(asset_path(ROOT, p))]
    if not missing:
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

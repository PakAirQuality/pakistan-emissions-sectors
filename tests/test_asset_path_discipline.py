"""No file access may name a relocated legacy path without going through the shim.

WHY THIS EXISTS. `src/pkinv/assets.py` keeps every historical `data/...` path working as a
logical alias, and the central readers (`core.io.read_rows`, `activity.store`,
`build_support.physical_paths`, `core.manifest.sha256_sources`) call it, so the great
majority of the repository's legacy literals are correct and must stay. What is NOT covered
is a bare `open()`, `np.load()`, or a directory walk. Those fail only at the moment the file
is touched, and three of them shipped through the sector-layout migration:

  * `scripts/release_fixpoint.py` raw-opened `data/gis/PROXY_SOURCES.md` - the
    `make release-check` spatial gate, dead with a FileNotFoundError;
  * `scripts/ingest_nfdc_production_series.py` read an absent input and would have written
    a SECOND vintage of its table beside the raw PDFs while every reader used the catalog's;
  * `scripts/holdings.py` walked `data/activity/`, found an empty directory, and reported
    "0 table(s)" for every keyword - a false negative in the one gate that exists to stop a
    document being re-acquired.

The first two were found by tests that happened to cover them. The third was not covered by
anything, and would have caused exactly the duplication CLAUDE.md's four-layer rule forbids.
So the rule is checked here rather than remembered: a moved legacy path reaching a raw file
operation is a defect, and the fix is always the same - wrap it in `resolve`/`asset_path`.

WHAT THIS DOES NOT CLAIM. It reads syntax, not behaviour. A legacy path assembled at runtime
from variables is invisible to it, and it says nothing about declaration tables - the source
register, deposit manifest and release manifest deliberately PUBLISH legacy identities and
never open them by that name.
"""
import ast
import os
import unittest

from _support import ROOT
from pkinv.assets import catalog, resolve

# Operations that touch the filesystem directly, with no resolution of their own.
RAW_FILE_CALLS = {"open", "load", "loadtxt", "savetxt", "save", "imread", "read_text",
                  "write_text", "read_bytes", "write_bytes", "unlink"}
RAW_DIR_CALLS = {"walk", "listdir", "scandir", "glob", "iglob", "rglob", "iterdir"}
# "path" is semantic.sources.Sources.path, which ends in asset_path(); a call whose
# attribute is literally `path` is otherwise vanishingly rare in this repository.
RESOLVERS = {"resolve", "asset_path", "legacy_path", "data_rows", "read_rows", "write_table",
             "members", "storage_path", "physical_paths", "path"}
# The same names as they appear spelled out in a shell or CI line.
RESOLVERS_CALLED = ("resolve(", "asset_path(", "legacy_path(", "data_rows(", "read_rows(")
# The migration script names both sides of every move by definition; it is the map.
EXEMPT = {os.path.join("scripts", "migrate_data_layout.py"),
          os.path.join("tests", "test_asset_path_discipline.py")}
TREES = ("src", "scripts", "tests")


def _moved():
    """Legacy paths that no longer exist at their own name, and their vanished directories."""
    files, directories = set(), set()
    for row in catalog():
        legacy, path = row["legacy_path"], row["path"]
        if legacy == path:
            continue
        files.add(legacy)
        parent = os.path.dirname(legacy)
        while parent and parent != "data":
            directories.add(parent)
            parent = os.path.dirname(parent)
    # A vanished directory that the shim CANNOT resolve is the dangerous kind: wrapping it
    # in asset_path() looks like resolution and is not, because resolve() only translates a
    # directory whose whole subtree moved by one prefix substitution. `data/activity` fans
    # out across eleven sectors, so it passes through unchanged - which is precisely how
    # holdings.py came to walk an empty directory and report nothing held.
    unresolvable = {d for d in directories
                    if not os.path.isdir(os.path.join(ROOT, d))
                    and resolve(d) in (d, os.path.join(ROOT, d))}
    return files, unresolvable


def _literals(node):
    """Every relative path spelled out of literals in this expression.

    Covers the three shapes that occur: a whole path in one string, an os.path.join of
    trailing literal components, and pathlib's `ROOT / "data/x/y.csv"`.
    """
    found, parts = set(), []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            value = child.value.strip("/")
            if value:
                found.add(value)
                parts.append(value)
    # A join/division chain: stitch the literal tail together, keeping only paths that
    # begin at "data" so an unrelated filename cannot collide with a registered one.
    for start in range(len(parts)):
        if parts[start].split("/")[0] != "data":
            continue
        for end in range(start + 1, len(parts) + 1):
            found.add("/".join(parts[start:end]))
    return found


def _is_resolver(node):
    if not isinstance(node, ast.Call):
        return False
    return (isinstance(node.func, ast.Name) and node.func.id in RESOLVERS
            or isinstance(node.func, ast.Attribute) and node.func.attr in RESOLVERS)


def _resolved(chain, argument):
    """A resolver anywhere around the call, or anywhere inside the path expression."""
    return (any(_is_resolver(call) for call in chain)
            or any(_is_resolver(node) for node in ast.walk(argument)))


class TestNoRawAccessToARelocatedPath(unittest.TestCase):
    def test_every_raw_file_operation_resolves_its_legacy_path(self):
        files, directories = _moved()
        self.assertTrue(files and directories, "the asset catalog declares no relocations")
        offences = []
        for tree in TREES:
            for base, _dirs, names in os.walk(os.path.join(ROOT, tree)):
                for name in sorted(names):
                    if not name.endswith(".py"):
                        continue
                    relative = os.path.relpath(os.path.join(base, name), ROOT)
                    if relative in EXEMPT:
                        continue
                    source = open(os.path.join(base, name), encoding="utf-8").read()
                    offences += _scan(source, relative, files, directories)
        self.assertEqual(offences, [], "raw file access on a relocated legacy path:\n  "
                         + "\n  ".join(offences))


def _scan(source, relative, files, directories):
    try:
        tree = ast.parse(source)
    except SyntaxError:  # a fixture that is deliberately not importable
        return []
    # Each call carries the calls enclosing it, so a resolver anywhere in the argument
    # expression or around it counts as resolution.
    offences, stack = [], []

    def visit(node, chain):
        if isinstance(node, ast.Call):
            chain = chain + [node]
            name = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else "")
            if name in RAW_FILE_CALLS | RAW_DIR_CALLS and node.args:
                spelled = _literals(node.args[0])
                if name in RAW_DIR_CALLS:
                    # No resolver exemption: for these directories there is none to have.
                    for hit in sorted(spelled & directories):
                        offences.append("%s:%d %s(%s)" % (relative, node.lineno, name, hit))
                elif not _resolved(chain, node.args[0]):
                    for hit in sorted(spelled & files):
                        offences.append("%s:%d %s(%s)" % (relative, node.lineno, name, hit))
        for child in ast.iter_child_nodes(node):
            visit(child, chain)

    visit(tree, stack)
    return offences


class TestNoDeclaredSourcePatternMatchesNothing(unittest.TestCase):
    """A hashed-source pattern that matches nothing is how provenance disappears quietly.

    `pkinv.core.documents.digests` globbed `asset_path(ROOT, pattern)`, and a pattern is not
    a registered file, so `data/activity/transport/*.csv` went through untranslated to a
    directory the sector layout had emptied. The transport run manifest lost fourteen of its
    eighty-nine hashed sources - every activity table behind the sector's numbers - and
    still validated, because nothing said a declared pattern must match something. Only a
    full cold build surfaced it, by diffing the manifest against the previous release.
    """

    def test_every_manifest_source_pattern_matches_at_least_one_file(self):
        from pkinv.core import documents
        from pkinv.sectors.railways import run_railways
        from pkinv.sectors.transport import run_transport
        empty = []
        for module in (run_transport, run_railways):
            for pattern in module.MANIFEST_SOURCES:
                if not documents.digests((pattern,)):
                    empty.append("%s: %s" % (module.__name__, pattern))
        self.assertEqual(empty, [], "declared source patterns match nothing, so the run "
                         "manifest silently omits them:\n  " + "\n  ".join(empty))


class TestNoShellFileNamesARelocatedPath(unittest.TestCase):
    """Everything above reads Python. A shell script gets no shim and was never scanned.

    `scripts/mirror_raw_data.sh` kept `MANIFEST="$ROOT/data/raw_manifest.csv"` through the
    sector layout, so the repository's ONLY off-machine backup - for 12.87 GB of raw
    documents, several of them no longer published anywhere, on a disk its own header calls
    89 percent full with no cloud copy - failed on its first check. Worse, the hint it
    printed named the builder, which writes the register to its NEW location, so an
    operator who followed the advice got the identical error again.

    Comments count here. In shell there is no reliable way to tell a comment from code, and
    a comment naming a path that no longer exists is the same reader-facing defect as the
    documentation ones: somebody follows it and finds nothing.
    """

    # Both exclusions are deliberate.
    #   dist/ is gitignored build output - frozen validation packages for already-cut
    #     releases, which must keep saying what they said when they shipped.
    #   validation_package/ ships INSIDE those packages, where
    #     scripts/build_validation_package.py puts the register at
    #     data/source_documents/raw_manifest.csv - a third layout again. Printing the
    #     stable logical identity the migration preserves is the right thing to do there.
    EXCLUDED_TREES = ("dist", "validation_package")
    SUFFIXES = (".sh", ".yml", ".yaml")

    def _files(self):
        for base, dirs, names in os.walk(ROOT):
            dirs[:] = sorted(d for d in dirs
                             if not d.startswith(".") and d not in ("node_modules", "data")
                             and os.path.relpath(os.path.join(base, d), ROOT)
                             not in self.EXCLUDED_TREES)
            for name in sorted(names):
                if name.endswith(self.SUFFIXES) or name == "Makefile":
                    yield os.path.relpath(os.path.join(base, name), ROOT)
        for name in sorted(os.listdir(os.path.join(ROOT, ".github", "workflows"))):
            if name.endswith((".yml", ".yaml")):
                yield os.path.join(".github", "workflows", name)

    def test_no_shell_or_ci_file_names_a_path_that_moved(self):
        moved = sorted({row["legacy_path"] for row in catalog()
                        if row["legacy_path"] != row["path"]}, key=len, reverse=True)
        self.assertTrue(moved, "the asset catalog declares no relocations")
        offences = []
        for relative in self._files():
            path = os.path.join(ROOT, relative)
            for number, line in enumerate(open(path, encoding="utf-8",
                                               errors="replace"), 1):
                # A line that hands the identity to the shim is the FIX, not the defect -
                # the same exemption the Python scan makes, and the repair to
                # mirror_raw_data.sh necessarily spells the legacy name to resolve it.
                if any(token in line for token in RESOLVERS_CALLED):
                    continue
                for legacy in moved:
                    if legacy in line:
                        offences.append("%s:%d names %s" % (relative, number, legacy))
                        break
        self.assertEqual(offences, [], "a shell or CI file names a relocated path, and "
                         "nothing resolves it there:\n  " + "\n  ".join(offences))


if __name__ == "__main__":
    unittest.main()

"""A frozen version of the national paper stays the bytes its release recorded.

WHY THIS EXISTS. paper_national/versions/v2 was the rewritten article through rc63: built,
swept for claims, patched at every mint. At rc64 the article moved to versions/v3 with its
eight redesigned figures, and v2 went back to what release 1.0.0rc62 shipped: the text and the
seven figures that were reviewed. From that moment v2 is a record, and a record has a failure
the live version does not have. Nothing builds it, so nothing notices when it changes: a
mint script that still names it, a sweep that "fixes" a number in it, a figure script that
overwrites fig4_validation.pdf. Each would leave a v2 that no release ever shipped, under a
name that says one did.

"Frozen" is therefore a digest, not a word. paper_national/versions/FROZEN.csv lists every
file of a frozen version with the release and commit it was taken from, and these tests hold
the tree to it. The seven figure PDFs are listed too: they sit in the shared figures/
directory, where the version's own .tex looks for them, beside the eight that v3 uses.

WHAT IT DOES NOT PROMISE. v2's .tex inputs paper_common/macros, the generated release cover
and figures/fig_ghg_grid_provenance.tex, all of which follow the current release. Compiling
v2 in this tree would therefore mix rc62 prose with a later cover. The PDFs are the record;
to rebuild them, check out the commit the register names.
"""
import csv
import hashlib
import os
import re
import unittest

from pkinv.paths import PAPER_NATIONAL_CURRENT, PAPER_NATIONAL_VERSIONS, ROOT

REGISTER = os.path.join(PAPER_NATIONAL_VERSIONS, "FROZEN.csv")

# What LaTeX leaves beside a source it compiled, and what a file browser leaves in a folder it
# opened. Their presence is not a change to the record: git ignores them, so no release ships
# them. Named here as well as asked of git, because a validation package is not a checkout
# and git cannot answer there.
BYPRODUCTS = (".aux", ".log", ".fls", ".fdb_latexmk", ".out", ".bbl", ".blg", ".synctex.gz",
              ".toc", ".DS_Store")


def _git_ignored():
    """Repo-relative paths git ignores under versions/, or an empty set where git cannot say."""
    import subprocess
    try:
        out = subprocess.run(["git", "-C", ROOT, "ls-files", "--others", "--ignored",
                              "--exclude-standard", "--", "paper_national/versions"],
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    if out.returncode != 0:
        return frozenset()
    return frozenset(os.path.normpath(line) for line in out.stdout.split("\n") if line)

# The files that build or patch the live article. None may name a frozen version.
WRITERS = ("Makefile", "src/pkinv/run_all.py", "scripts/mint_release.py",
           "scripts/make_btr_qualified_table.py", "scripts/make_closure_table.py",
           "scripts/make_coal_audit_table.py", "scripts/make_five_classes_table.py",
           "scripts/make_livestock_factor_table.py", "scripts/build_manuscript_figures.py",
           "scripts/make_fig_ghg_grid.py", "paper_national/figures/rewrite_inputs/plot_figures.py",
           "paper_national/figures/rewrite_inputs/plot_construction.py")


def register():
    with open(REGISTER, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def differences(rows, read):
    """Rows whose file is missing or is not the recorded bytes. `read` returns a file's bytes
    or None; it is a parameter so the control below can hand this a tampered file."""
    out = []
    for row in rows:
        body = read(row["path"])
        if body is None:
            out.append("%s is missing" % row["path"])
        elif (hashlib.sha256(body).hexdigest() != row["sha256"]
              or len(body) != int(row["bytes"])):
            out.append("%s is not the file release %s recorded at %s"
                       % (row["path"], row["release"], row["commit"]))
    return out


def _read(relative):
    path = os.path.join(ROOT, relative)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as handle:
        return handle.read()


class TestFrozenVersionsAreTheirRecordedBytes(unittest.TestCase):
    def test_the_register_names_a_version_that_exists(self):
        rows = register()
        self.assertGreaterEqual(len(rows), 10, "the register is nearly empty")
        for version in {r["version"] for r in rows}:
            self.assertTrue(os.path.isdir(os.path.join(PAPER_NATIONAL_VERSIONS, version)),
                            "the register freezes %s, which is not under versions/" % version)
            self.assertNotEqual(version, PAPER_NATIONAL_CURRENT,
                                "%s is the version the release builds; it cannot also be "
                                "frozen" % version)

    def test_every_frozen_file_is_the_recorded_file(self):
        self.assertFalse(differences(register(), _read),
                         "a frozen version changed:\n  "
                         + "\n  ".join(differences(register(), _read)))

    def test_the_check_would_see_one_changed_byte(self):
        """THE POSITIVE CONTROL. A comparison that hashed the wrong thing passes on any tree."""
        rows = [r for r in register() if r["path"].endswith("paper.tex")]
        self.assertTrue(rows)
        tampered = lambda relative: _read(relative) + b" "
        self.assertEqual(len(differences(rows, tampered)), len(rows))
        self.assertEqual(len(differences(rows, lambda relative: None)), len(rows))

    def test_nothing_was_added_to_a_frozen_version(self):
        """The register is the whole version, so a file it does not list is an addition."""
        rows = register()
        listed = {os.path.normpath(r["path"]) for r in rows}
        ignored = _git_ignored()
        strays = []
        for version in {r["version"] for r in rows}:
            base = os.path.join(PAPER_NATIONAL_VERSIONS, version)
            for folder, _dirs, names in os.walk(base):
                for name in names:
                    relative = os.path.normpath(os.path.relpath(os.path.join(folder, name), ROOT))
                    if (relative not in listed and relative not in ignored
                            and not name.endswith(BYPRODUCTS)):
                        strays.append(relative)
        self.assertFalse(strays, "files in a frozen version that its release did not ship:\n  "
                         + "\n  ".join(sorted(strays)))

    def test_an_added_file_would_be_seen(self):
        """THE POSITIVE CONTROL for the rule above, which a too-generous exemption would empty:
        a real file in a frozen version is neither ignored by git nor a by-product."""
        ignored = _git_ignored()
        for row in register():
            relative = os.path.normpath(row["path"])
            self.assertNotIn(relative, ignored, "%s is frozen and git ignores it" % relative)
            self.assertFalse(relative.endswith(BYPRODUCTS),
                             "%s is frozen and would be exempt as a by-product" % relative)

    def test_a_frozen_manuscript_states_the_release_it_was_frozen_at(self):
        """The register's release column is checked against the manuscript's own words, so
        the record cannot name one release while the article names another."""
        pattern = re.compile(r"\b1\.\d+\.\d+rc\d+\b")
        for version, release in {(r["version"], r["release"]) for r in register()}:
            text = _read("paper_national/versions/%s/paper.tex" % version).decode("utf-8")
            self.assertEqual(set(pattern.findall(text)), {release},
                             "versions/%s/paper.tex does not state exactly %s"
                             % (version, release))

    def test_no_build_step_writes_into_a_frozen_version(self):
        """A target or a phase that names a frozen version would rebuild or patch it."""
        offenders = []
        for version in {r["version"] for r in register()}:
            needles = ("versions/%s/" % version, "versions/%s " % version,
                       '"versions", "%s"' % version)
            for relative in WRITERS:
                body = _read(relative)
                self.assertIsNotNone(body, "%s is gone; the list of writers is stale" % relative)
                # a comment may say where the article used to live; only code can write there
                text = re.sub(r"(?m)^\s*#.*$", "", body.decode("utf-8"))
                offenders += ["%s names %s" % (relative, n.strip()) for n in needles if n in text]
        self.assertFalse(offenders, "a builder still points at a frozen version:\n  "
                         + "\n  ".join(offenders))

    def test_the_release_hashes_the_same_frozen_pdfs(self):
        """outputs/pakemis_paper_hashes.csv is rewritten at every release and globs every
        version, so it must report for a frozen PDF the digest the register holds."""
        sidecar = os.path.join(ROOT, "outputs", "pakemis_paper_hashes.csv")
        if not os.path.exists(sidecar):
            self.skipTest("the hash sidecar has not been written in this checkout")
        with open(sidecar, encoding="utf-8", newline="") as handle:
            hashed = {r["path"]: r["sha256"] for r in csv.DictReader(handle)}
        for row in register():
            if row["path"].endswith(".pdf") and "/versions/" in row["path"]:
                self.assertEqual(hashed.get(row["path"]), row["sha256"],
                                 "%s: the release record and the frozen register disagree"
                                 % row["path"])


if __name__ == "__main__":
    unittest.main()

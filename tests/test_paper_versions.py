"""The national paper is versioned, and the two strings that say which version agree.

paper_national/versions/<v>/ holds one self-contained version of the national article;
paper_national/figures/ and paper_national/queries/ are shared, because they are inputs to
every version rather than part of any one. Before this layout the article sat at
paper_national/ with a second candidate (pakemis_rewritten.tex) beside it at the same
level, so "the paper" and "a draft of the paper" were indistinguishable by path.

WHICH VERSION SHIPS is said in exactly two places - PAPER_NATIONAL_CURRENT in
src/pkinv/paths.py and NATIONAL_VERSION in the Makefile - plus the CURRENT symlink a human
reads. Three statements of one fact drift unless something compares them, which is what
this file is for. It also holds the structural promises the ~160 migrated references rely
on: that the shipped version carries a main, a supplement, sections and generated
fragments, and that every version is self-contained.
"""
import glob
import os
import re
import unittest

from pkinv.paths import (PAPER_NATIONAL, PAPER_NATIONAL_CURRENT, PAPER_NATIONAL_GENERATED,
                         PAPER_NATIONAL_MAIN, PAPER_NATIONAL_MAIN_REL,
                         PAPER_NATIONAL_SECTIONS, PAPER_NATIONAL_VERSIONS, ROOT)


def versions():
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(
        PAPER_NATIONAL_VERSIONS, "*")) if os.path.isdir(p))


class TestTheVersionedLayout(unittest.TestCase):
    def test_there_are_versions_and_the_current_one_is_among_them(self):
        """The positive control: an empty versions/ must fail here, not silently pass."""
        found = versions()
        self.assertGreaterEqual(len(found), 2,
                                "paper_national/versions/ holds %r; the layout exists to "
                                "carry more than one version of the article" % found)
        self.assertIn(PAPER_NATIONAL_CURRENT, found,
                      "PAPER_NATIONAL_CURRENT is %r, which is not a directory under "
                      "versions/ (%r)" % (PAPER_NATIONAL_CURRENT, found))

    def test_the_makefile_builds_the_version_the_code_reads(self):
        """Two strings, one fact. A promotion that edits one and not the other ships the
        wrong article, and every path constant would still resolve - so nothing else can
        catch it."""
        with open(os.path.join(ROOT, "Makefile"), encoding="utf-8") as handle:
            text = handle.read()
        m = re.search(r"(?m)^NATIONAL_VERSION \?= *(\S+)", text)
        self.assertTrue(m, "the Makefile no longer declares NATIONAL_VERSION")
        self.assertEqual(
            m.group(1), PAPER_NATIONAL_CURRENT,
            "the Makefile builds %s and pkinv.paths reads %s; one promotion edited one "
            "string and not the other" % (m.group(1), PAPER_NATIONAL_CURRENT))

    def test_the_current_symlink_points_at_the_current_version(self):
        """What a human arriving at the directory follows."""
        link = os.path.join(PAPER_NATIONAL, "CURRENT")
        self.assertTrue(os.path.islink(link),
                        "paper_national/CURRENT is not a symlink; a reader has no way to "
                        "tell which version ships")
        self.assertEqual(os.path.realpath(link), os.path.realpath(PAPER_NATIONAL_MAIN),
                         "CURRENT points at %s, not at the current version"
                         % os.readlink(link))

    def test_the_shipped_version_is_complete(self):
        for name in ("paper_national.tex", "supplement.tex", "short_summary.txt"):
            self.assertTrue(os.path.exists(os.path.join(PAPER_NATIONAL_MAIN, name)),
                            "the shipped version has no %s" % name)
        self.assertGreaterEqual(len(glob.glob(os.path.join(PAPER_NATIONAL_SECTIONS,
                                                           "*.tex"))), 20)
        self.assertTrue(glob.glob(os.path.join(PAPER_NATIONAL_GENERATED, "*.tex")),
                        "no generated fragments under the shipped version")

    def test_every_version_declares_its_own_main(self):
        """Self-contained is the point: a version with no main is a directory of orphans."""
        for v in versions():
            root = os.path.join(PAPER_NATIONAL_VERSIONS, v)
            mains = [n for n in ("paper.tex", "paper_national.tex")
                     if os.path.exists(os.path.join(root, n))]
            self.assertTrue(mains, "version %s has neither paper.tex nor "
                                   "paper_national.tex" % v)

    def test_no_version_reaches_a_sibling_version(self):
        """Versions may share figures and queries; they may not read each other."""
        offenders = []
        for v in versions():
            root = os.path.join(PAPER_NATIONAL_VERSIONS, v)
            for tex in glob.glob(os.path.join(root, "**", "*.tex"), recursive=True):
                with open(tex, encoding="utf-8") as handle:
                    text = re.sub(r"(?m)^\s*%.*$", "", handle.read())
                for other in versions():
                    if other != v and "versions/%s/" % other in text:
                        offenders.append("%s reads %s"
                                         % (os.path.relpath(tex, ROOT), other))
        self.assertFalse(offenders, "a version is not self-contained:\n  "
                                    + "\n  ".join(offenders))

    def test_the_relative_form_matches_the_absolute_one(self):
        self.assertEqual(os.path.join(ROOT, PAPER_NATIONAL_MAIN_REL.replace("/", os.sep)),
                         PAPER_NATIONAL_MAIN)

    def test_no_version_directory_survives_at_the_top_level(self):
        """The complement of the rule above, and it caught a real split brain.

        sections/ and generated/ belong to a version. Three fragments were regenerated
        at the OLD top-level paths while the writers were being migrated, `git add -A`
        swept them into the commit, and the tree then held two copies of
        gen_tab_completeness.tex - one live under v1 and one stale at the top, with
        nothing to say which a reader should believe. A directory that belongs to a
        version must not exist beside versions/.
        """
        for name in ("sections", "generated"):
            stray = os.path.join(PAPER_NATIONAL, name)
            self.assertFalse(
                os.path.exists(stray),
                "paper_national/%s exists; it belongs to a version, and a copy here is "
                "either a stale duplicate or a writer that was not migrated" % name)

    def test_the_shared_directories_are_not_inside_a_version(self):
        """figures/ and queries/ are inputs to every version, so they stay at the top."""
        for name in ("figures", "queries"):
            shared = os.path.join(PAPER_NATIONAL, name)
            self.assertTrue(os.path.isdir(shared), "paper_national/%s is missing" % name)
            for v in versions():
                self.assertFalse(
                    os.path.isdir(os.path.join(PAPER_NATIONAL_VERSIONS, v, name)),
                    "version %s has its own %s; it is meant to be shared, and two copies "
                    "drift" % (v, name))


if __name__ == "__main__":
    unittest.main()

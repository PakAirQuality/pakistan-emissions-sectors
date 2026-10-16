"""A cited document is held, and a held document cannot disappear.

WHY THIS EXISTS. On 2026-10-12 a reviewer quoted the manuscript's own sentence, "some cited
primary documents have not been retained", and the author asked the obvious question: every
document was supposed to be kept, so why were they not? The audit's answer had three parts,
and each part is a test here.

1. THEY WERE NEVER SAVED. Seventeen of the twenty sources the not-retained register listed had
   been read by a fetcher that parsed the response in memory, or from a web page nobody
   snapshotted. A fetcher now keeps the bytes first (pkinv.core.retention) and parses the kept
   file. TestEveryFetcherKeepsWhatItReads holds each one to that.

2. THE REGISTER COULD NOT SEE WHAT WAS HELD, OR WHAT WAS NOT. data/source_documents.csv
   answers per FILE and its archived_path is usually a directory. Three "not kept" documents
   were on disk the whole time (one inside a zip), and at least eight files marked "archived"
   cited a document their directory did not contain: a JMP workbook "at" sources/OGRA, a
   2014-15 year book "at" a directory whose earliest edition is 2016-17.
   data/catalog/cited_documents.csv answers per DOCUMENT and names the file;
   TestEveryCitedDocumentIsAccountedFor holds it to the disk and holds the per-file register
   to it.

3. NOTHING STOPPED A DELETION. A file removed from data/raw/ failed one test until the
   manifest was regenerated, which dropped the row. A file removed from sources/ failed
   nothing. A cleanup commit in August removed 103 API responses as unreferenced and the suite
   stayed green. data/catalog/document_retention.csv only grows; TestTheLedgerOnlyGrows holds
   the tree to it, and the last test there reads the ledger's own history.

WHAT IT DOES NOT PROMISE. That a held page says what the publisher said on the day it was
read: a copy fetched later is labelled (`held-later-edition`, `held-archive-copy`) and
compared, never passed off as the bytes read. And it does not re-hash 17 GB: the digest is
checked for documents under 2 MB here and for all of them by
`python3 scripts/retain_document.py --verify`, which `make release-check` runs.
"""
import csv
import hashlib
import os
import re
import subprocess
import sys
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pkinv.assets import asset_path                                     # noqa: E402
from _support import load_script, require_layers, unshipped_registered  # noqa: E402
from pkinv.core import layers                                          # noqa: E402

LEDGER = os.path.join(ROOT, "data", "catalog", "document_retention.csv")
LEDGER_GIT = "data/catalog/document_retention.csv"
CITED = os.path.join(ROOT, "data", "catalog", "cited_documents.csv")
STATES = ("held", "held-archive-copy", "held-later-edition", "held-witness",
          "held-without-cited-content", "not-held")
# The states under which a file's cited document is NOT held as cited. One such row keeps
# the file not-archived whatever witnesses stand beside it.
OPEN = ("not-held", "held-without-cited-content")
SMALL = 2_000_000

# Every script that fetches a document the inventory reads. Each must keep what it fetched.
FETCHERS = (
    "scripts/fetch_cited_documents.py",
    "scripts/fetch_comtrade_clinker.py",
    "scripts/fetch_comtrade_hfc.py",
    "scripts/fetch_firms_country_archive.py",
    "scripts/fetch_gem_trackers.py",
    "scripts/fetch_hdd.py",
    "scripts/fetch_hydrowaste.py",
    "scripts/fetch_wdi_rail.py",
    "scripts/ingest_residential.py",
    "scripts/check_faostat_protein.py",
    "src/pkinv/sectors/agriculture/fetch_history.py",
    "src/pkinv/sectors/agriculture/gis/fetch_firms.py",
)


# Responses a fetcher parses and deliberately does NOT keep, with the reason.
NOT_DOCUMENTS = {
    "scripts/fetch_gem_trackers.py":
        "the mint and presign calls return single-use capability tokens; a token is a "
        "credential, not a document. The four workbooks the tokens unlock are kept.",
}


def _rows(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


def _in_git():
    try:
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "--is-inside-work-tree"],
                              capture_output=True, text=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# --- the comparisons, as functions, so the controls can hand them a broken world --------------

def missing_or_changed(ledger, stat, digest):
    """Ledger rows whose document is gone, has another size, or (small files) other bytes.
    `stat(path)` returns the size or None; `digest(path)` returns the sha256."""
    out = []
    for row in ledger:
        size = stat(row["path"])
        if size is None:
            out.append("GONE     %s" % row["path"])
        elif size != int(row["bytes"]):
            out.append("SIZE     %s" % row["path"])
        elif size <= SMALL and digest(row["path"]) != row["sha256"]:
            out.append("CONTENT  %s" % row["path"])
    return out


def unlisted(held, ledger):
    """Held documents the ledger does not list."""
    listed = {r["path"] for r in ledger}
    return sorted(p for p in held if p not in listed)


def dropped(earlier, ledger):
    """Paths an earlier version of the ledger listed and this one does not."""
    return sorted({r["path"] for r in earlier} - {r["path"] for r in ledger})


def path_exists(path):
    """True if a cited path is on disk: a file, a directory, or archive.zip::member."""
    if "::" in path:
        archive, member = path.split("::", 1)
        full = asset_path(ROOT, archive)
        if not os.path.exists(full):
            return False
        with zipfile.ZipFile(full) as handle:
            return member in handle.namelist()
    return os.path.exists(asset_path(ROOT, path))


def _size(path):
    full = os.path.join(ROOT, path)
    return os.path.getsize(full) if os.path.exists(full) else None


def _digest(path):
    with open(os.path.join(ROOT, path), "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class TestTheLedgerOnlyGrows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = _rows(LEDGER)
        cls.tool = load_script("retain_document")

    def test_the_ledger_is_well_formed(self):
        self.assertGreater(len(self.ledger), 5000, "the ledger is nearly empty")
        paths = [r["path"] for r in self.ledger]
        self.assertEqual(len(paths), len(set(paths)), "a document is listed twice")
        for row in self.ledger:
            self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$", row["path"])
            self.assertTrue(row["path"].startswith(self.tool.TREES), row["path"])
            self.assertTrue(row["first_held"].strip(), row["path"])

    def test_every_listed_document_is_still_here(self):
        """The test a deletion fails, and keeps failing: nothing regenerates this list."""
        require_layers("the held documents")
        absent_by_design = unshipped_registered()      # inside a package, never in the repo
        rows = [r for r in self.ledger if r["path"] not in absent_by_design
                and not any(r["path"].startswith(p + "/") for p in absent_by_design)]
        problems = missing_or_changed(rows, _size, _digest)
        self.assertFalse(
            problems,
            "%d held documents are gone or changed. A held document is never deleted and "
            "never edited; restore it (git checkout, or the mirror):\n  %s"
            % (len(problems), "\n  ".join(problems[:30])))

    def test_every_held_document_is_listed(self):
        """A document that arrives must join the ledger, or deleting it would cost nothing."""
        new = unlisted([path for path, _sha, _size in self.tool.held_documents()], self.ledger)
        self.assertFalse(
            new, "%d held documents are not in the retention ledger - run "
                 "scripts/raw_data_manifest.py then scripts/retain_document.py:\n  %s"
                 % (len(new), "\n  ".join(new[:20])))

    def test_the_ledger_and_the_manifest_agree_on_every_digest(self):
        manifest = {path: sha for path, sha, _size in self.tool.held_documents()}
        wrong = sorted(r["path"] for r in self.ledger
                       if r["path"] in manifest and manifest[r["path"]] != r["sha256"])
        self.assertFalse(wrong, "the raw manifest records other bytes for a held document "
                                "than the ledger first recorded:\n  " + "\n  ".join(wrong[:20]))

    def test_no_committed_version_of_the_ledger_listed_more(self):
        """A ROW REMOVED FROM THE LEDGER is the one deletion the tests above cannot see: take
        the file and its row together and they pass. So this reads every version of the
        ledger git holds and requires each to be a subset of the present one."""
        if not _in_git():
            self.skipTest("not a git checkout: the ledger's history is not available here")
        # rc69: the ledger's history through rc68 is in the private checkout, and from rc69
        # in the public repository; read both (src/pkinv/core/layers.py).
        commits = []
        for repo in layers.history_repositories(ROOT):
            log = subprocess.run(["git", "-C", repo, "log", "--format=%H", "--", LEDGER_GIT],
                                 capture_output=True, text=True, timeout=120)
            commits += [(repo, c) for c in log.stdout.split() if c]
        if not commits:
            self.skipTest("the ledger has not been committed yet")
        for repo, commit in commits:
            shown = subprocess.run(["git", "-C", repo, "show", "%s:%s" % (commit, LEDGER_GIT)],
                                   capture_output=True, text=True, timeout=120)
            earlier = list(csv.DictReader(shown.stdout.splitlines()))
            lost = dropped(earlier, self.ledger)
            self.assertFalse(lost, "the ledger at %s listed documents this one does not:\n  %s"
                                   % (commit[:10], "\n  ".join(lost[:20])))

    def test_records_about_documents_are_not_frozen(self):
        """The logs beside the documents must stay appendable, so they are not in the ledger."""
        frozen_logs = [r["path"] for r in self.ledger if self.tool.is_record(r["path"])]
        self.assertFalse(frozen_logs, frozen_logs[:10])
        for name in ("data/raw/gem/RETRIEVALS.csv", "data/raw/ACQUISITION_LOG_x.csv",
                     "sources/GEM/GEM_SOURCES.json"):
            self.assertFalse(self.tool.covered(name), name)
        self.assertTrue(self.tool.covered("data/raw/gem/Global-Coal-Plant-Tracker-July-2026.xlsx"))

    def test_the_manifest_builder_refuses_to_forget_a_document(self):
        """scripts/raw_data_manifest.py rebuilds its list from the disk. It must read the
        ledger and refuse, before writing, when a listed path is no longer on disk."""
        with open(os.path.join(ROOT, "scripts", "raw_data_manifest.py"), encoding="utf-8") as h:
            source = h.read()
        refusal = source.find("REFUSED")
        write = source.find('with open(OUT, "w"')
        self.assertGreater(refusal, 0, "the manifest builder no longer reads the ledger")
        self.assertIn("document_retention.csv", source)
        self.assertLess(refusal, write, "the refusal must come before the manifest is written")

    def test_the_tool_has_no_mode_that_removes_a_row(self):
        with open(os.path.join(ROOT, "scripts", "retain_document.py"), encoding="utf-8") as h:
            source = h.read()
        code = re.sub(r'(?s)""".*?"""', "", source)
        self.assertNotIn('open(LEDGER, "w"', code, "the ledger may only be appended to")
        self.assertIn('open(LEDGER, "a"', code)


class TestTheComparisonsWouldSeeADeletion(unittest.TestCase):
    """THE POSITIVE CONTROLS. Each rule above is run against a world in which it must fire."""
    LEDGER = [{"path": "data/raw/x/a.pdf", "sha256": "a" * 64, "bytes": "10"},
              {"path": "data/raw/x/b.pdf", "sha256": "b" * 64, "bytes": "20"}]

    def test_a_deleted_document_is_seen(self):
        sizes = {"data/raw/x/a.pdf": 10}
        found = missing_or_changed(self.LEDGER, sizes.get, lambda p: "a" * 64)
        self.assertEqual(found, ["GONE     data/raw/x/b.pdf"])

    def test_a_truncated_document_is_seen(self):
        sizes = {"data/raw/x/a.pdf": 10, "data/raw/x/b.pdf": 19}
        found = missing_or_changed(self.LEDGER, sizes.get, lambda p: p[-5] * 64)
        self.assertEqual(found, ["SIZE     data/raw/x/b.pdf"])

    def test_one_changed_byte_is_seen(self):
        sizes = {"data/raw/x/a.pdf": 10, "data/raw/x/b.pdf": 20}
        found = missing_or_changed(self.LEDGER, sizes.get, lambda p: "a" * 64)
        self.assertEqual(found, ["CONTENT  data/raw/x/b.pdf"])

    def test_an_unlisted_document_is_seen(self):
        self.assertEqual(unlisted(["data/raw/x/a.pdf", "data/raw/x/new.pdf"], self.LEDGER),
                         ["data/raw/x/new.pdf"])

    def test_a_removed_row_is_seen(self):
        self.assertEqual(dropped(self.LEDGER, self.LEDGER[:1]), ["data/raw/x/b.pdf"])

    def test_a_missing_zip_member_is_seen(self):
        self.assertTrue(path_exists("sources/Provincial Statistics/"
                                    "Punjab-20260803T134030Z-1-001.zip::Punjab/SPB 2025.pdf")
                        or "sources/Provincial Statistics" in
                        "".join(unshipped_registered()) or not os.path.isdir(
                            os.path.join(ROOT, "sources", "Provincial Statistics")))
        self.assertFalse(path_exists("sources/Provincial Statistics/"
                                     "Punjab-20260803T134030Z-1-001.zip::Punjab/no_such.pdf"))
        self.assertFalse(path_exists("data/raw/no_such_source/no_such.pdf"))


class TestEveryCitedDocumentIsAccountedFor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cited = _rows(CITED)
        cls.register = {r["data_file"]: r
                        for r in _rows(asset_path(ROOT, "data", "source_documents.csv"))}

    def test_the_vocabulary_is_closed(self):
        self.assertGreater(len(self.cited), 400)
        for row in self.cited:
            self.assertIn(row["state"], STATES, row["data_file"])
            self.assertTrue(row["document"].strip(), row["data_file"])
            self.assertTrue(row["basis"].strip(), "%s: %s says nothing about how it was "
                            "established" % (row["data_file"], row["document"][:60]))
            if row["state"] == "not-held":
                self.assertFalse(row["path"].strip(), "a not-held document has no path")
            else:
                self.assertTrue(row["path"].strip(), "%s: a %s document names no file"
                                % (row["data_file"], row["state"]))

    def test_every_held_document_is_on_disk(self):
        """The check the per-file register could not make: it named directories."""
        require_layers("the held documents")
        absent_by_design = unshipped_registered()
        if absent_by_design:
            self.skipTest("a validation package registers the documents and does not carry them")
        gone = sorted({"%s -> %s" % (r["data_file"], r["path"]) for r in self.cited
                       if r["state"] != "not-held" and not path_exists(r["path"])})
        self.assertFalse(gone, "cited documents the register calls held and the disk does "
                               "not have:\n  " + "\n  ".join(gone[:30]))

    def test_every_archived_and_not_archived_file_is_covered(self):
        """Each file that cites an outside document appears here, and nothing else does."""
        covered = {r["data_file"] for r in self.cited}
        outside = {f for f, r in self.register.items() if r["archival_state"] != "derived"}
        self.assertFalse(sorted(outside - covered),
                         "files citing outside documents with no row in cited_documents.csv")
        self.assertFalse(sorted(covered - set(self.register)),
                         "cited_documents.csv names files the source register does not")

    def test_the_file_state_follows_its_documents(self):
        """THE RULE: a file is archived only if every document it cites is held as cited.
        This is what stops a file with one unheld citation from hiding behind the others."""
        open_files = {r["data_file"] for r in self.cited if r["state"] in OPEN}
        wrong = []
        for data_file, row in sorted(self.register.items()):
            state = row["archival_state"]
            if state == "archived" and data_file in open_files:
                wrong.append("%s is archived and cites a document that is not held" % data_file)
            if state == "not-archived" and data_file not in open_files:
                wrong.append("%s is not-archived and every document it cites is held"
                             % data_file)
            if state == "derived" and data_file in open_files:
                wrong.append("%s is derived and cites an outside document" % data_file)
        self.assertFalse(wrong, "\n  ".join(wrong))

    def test_a_witness_never_stands_alone_as_holding(self):
        """A reprint is evidence for the figures, not the document: a file whose only rows
        for a citation are witnesses must also carry the not-held row they stand in for."""
        by_file = {}
        for row in self.cited:
            by_file.setdefault(row["data_file"], []).append(row["state"])
        alone = sorted(f for f, states in by_file.items()
                       if "held-witness" in states and not (set(states) & set(OPEN)))
        self.assertFalse(alone, "files with a witness and no unheld original: say which "
                                "document the witness stands in for:\n  " + "\n  ".join(alone))

    def test_the_saved_pages_say_what_they_are_cited_for(self):
        """A saved page is not the cited fact. The retention sweep kept PIA's fleet page,
        219 kB of it, and it names no aircraft: the site builds the page in the browser. A
        row may call a page `held` only if the held bytes carry the cited content."""
        if unshipped_registered():
            self.skipTest("a validation package does not carry the pages")
        fetch = load_script("fetch_cited_documents")
        states = fetch.verify()
        file_of = {}
        for key in fetch.DOCUMENTS:
            for copy in fetch._copies(key):
                file_of[os.path.relpath(copy, ROOT)] = key
        wrong = []
        for row in self.cited:
            key = file_of.get(row["path"])
            if key is None or row["state"] == "held-witness":
                continue
            carries = states[key][0] == "held"
            if row["state"] in ("held", "held-archive-copy") and not carries:
                wrong.append("%s is called %s and the page does not carry the cited content"
                             % (row["path"], row["state"]))
            if row["state"] == "held-without-cited-content" and carries:
                wrong.append("%s now carries its cited content; the row is stale" % row["path"])
        self.assertFalse(wrong, "\n  ".join(wrong))

    def test_the_content_check_can_tell_a_page_from_a_shell(self):
        """THE POSITIVE CONTROL for the rule above: among the held pages there is at least
        one that passes and at least one that fails, or the check proves nothing."""
        require_layers("the saved pages")
        if unshipped_registered():
            self.skipTest("a validation package does not carry the pages")
        states = [s for s, _detail in load_script("fetch_cited_documents").verify().values()]
        self.assertIn("held", states)
        self.assertIn("empty-of-it", states,
                      "no held page fails the content check any more. If every page now "
                      "carries its content, replace this control with a synthetic shell.")


class TestEveryFetcherKeepsWhatItReads(unittest.TestCase):
    def test_each_fetcher_keeps_before_it_parses(self):
        """The defect was a pattern: json.load(urlopen(...)), and the bytes were gone."""
        careless = []
        for relative in FETCHERS:
            path = os.path.join(ROOT, relative)
            self.assertTrue(os.path.exists(path), "%s is gone; FETCHERS is stale" % relative)
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
            if not re.search(r"retention\.(keep|fetch_and_keep)\(", source):
                careless.append("%s never calls pkinv.core.retention" % relative)
            # parsing a live response directly is the pattern that lost the documents
            if relative not in NOT_DOCUMENTS and re.search(
                    r"json\.load\(\s*r\s*\)|json\.loads\(\s*response\.read\(\)", source):
                careless.append("%s parses a response it has not kept" % relative)
        self.assertFalse(careless, "\n  ".join(careless))

    def test_every_named_retrieval_route_is_a_fetcher_that_keeps(self):
        """A not-retained row that names a script is promising that the script would hold
        the document if it could be run. The script must be one this test covers."""
        rows = _rows(asset_path(ROOT, "data", "not_retained_register.csv"))
        named = sorted({r["retrieval_script"].strip() for r in rows
                        if r["retrieval_script"].strip()})
        self.assertFalse([s for s in named if s not in FETCHERS],
                         "retrieval scripts the fetcher list does not cover")

    def test_keep_never_overwrites(self):
        """A second fetch may return other bytes. The first file must survive it."""
        import tempfile
        from pkinv.core import retention
        with tempfile.TemporaryDirectory() as scratch:
            real = retention.RAW
            retention.RAW = scratch
            try:
                first = retention.keep(b"as read in August", "s", "page.html", "https://x/")
                again = retention.keep(b"as read in August", "s", "page.html", "https://x/")
                later = retention.keep(b"as served in October", "s", "page.html", "https://x/")
                with open(first, "rb") as handle:
                    self.assertEqual(handle.read(), b"as read in August")
                self.assertEqual(first, again)
                self.assertNotEqual(first, later)
                with open(os.path.join(scratch, "s", "RETRIEVALS.csv"), encoding="utf-8") as h:
                    self.assertEqual(len(list(csv.DictReader(h))), 2)
                with self.assertRaises(ValueError):
                    retention.keep(b"", "s", "empty.html", "https://x/")
            finally:
                retention.RAW = real


if __name__ == "__main__":
    unittest.main()

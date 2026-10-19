"""Author-year strings in data/*.csv must resolve, or be explicitly declared as informal.

The .bib is checked; the data files were not. That gap is how a fabricated author list ("Ahmed et
al.") survived in data/benchmarks_air.csv for a whole revision after paper/references.bib had already
been corrected to the real authors (Tomlinson et al.). A source string that *looks* like a citation
is treated as one by any reader, so it has to be held to the same standard.

Two outcomes are acceptable for a name-year string in a data file:
  1. it resolves to an entry in paper/references.bib, or
  2. it is listed in INFORMAL below -- an unverified or secondary attribution, deliberately NOT
     promoted to a citation.

Adding a name to INFORMAL is cheap and honest. Inventing a .bib entry to make this test pass is the
failure mode it exists to prevent: never write a bibliography entry from a title or DOI without
having read the author list.
"""
import csv
import glob
import os
import re
import unittest

from _support import require_documents  # noqa: E402  (rc42: the documents gate)

from pkinv.report import completeness
from _support import ROOT
from pkinv.assets import asset_path, catalog
from _support import readable  # noqa: E402



def _load_script(name):
    """Import a scripts/*.py generator so a test can call build() and compare the committed
    artefact against a fresh run."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        name[:-3], os.path.join(ROOT, "scripts", name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
# The references the data tables cite (key, authors, year, title). rc70: extracted from the
# project bibliography, which no longer lives in this repository, for exactly the author-year
# strings data/ carries; a new citation in data/ needs its row here.
BIB = os.path.join(ROOT, "data", "catalog", "data_references.csv")
FIELDS = ("source", "note", "scope_detail", "justification")

# "Surname et al. 2020", "Surname & Other 2020", "Surname and Other (2020)"
PATTERN = re.compile(
    r"\b([A-Z][A-Za-zÀ-ɏ\-]{2,})\s+"
    r"(?:et al\.?|and\s+[A-Z][A-Za-z\-]+|&\s*[A-Z][A-Za-z\-]+)[,.]?\s*\(?((?:19|20)\d{2})")

# name -> why it is not a citation. Keep the reason specific enough to re-audit later.
INFORMAL = {
    "Doorn": "secondary attribution inside an IPCC source string (the wastewater Bo of 0.6 kg "
             "CH4/kg BOD is cited to IPCC 2006 V5 Ch6 Table 6.2, whose own source line reads "
             "'expert judgment by lead authors and on Doorn et al. (1997)'); the primary source "
             "is the IPCC table, which is what the engine cites, and the 1997 report has not "
             "been read",
    "Webb": "secondary attribution inside an IPCC source string (RN2_N2O is cited to IPCC 2019 "
            "Refinement V4 Ch10 Table 10.23, which itself credits Webb & Misselbrook 2004); the "
            "primary source is the IPCC table, which is what the engine cites",
    # The LULUCF mangrove-area attribution ("Hussain") moved with data/lulucf_params.csv to
    # the agriculture research repository, where the land sector is reported as an exploratory
    # supplementary note. Its INFORMAL declaration moved with it: an entry here naming a source
    # that no longer appears in data/ is exactly what this file's companion check flags.
}


def _bib_surnames():
    if not os.path.exists(BIB):
        return None
    text = open(BIB, encoding="utf-8").read()
    return {w.lower() for w in re.findall(r"[A-Z][A-Za-zÀ-ɏ\-]{2,}", text)}


def _data_citations():
    """{(surname, year): {files}} over every CSV under data/."""
    found = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "**", "*.csv"), recursive=True)):
        # A preserved release has its own source vintage and bibliography. It is
        # not a current source record; live data still receive the full sweep.
        if os.path.relpath(path, ROOT).replace(os.sep, "/").startswith("data/baselines/"):
            continue
        try:
            rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
        except Exception:
            continue
        for r in rows:
            for key in FIELDS:
                for m in PATTERN.finditer(r.get(key) or ""):
                    found.setdefault((m.group(1), m.group(2)),
                                     set()).add(os.path.relpath(path, ROOT))
    return found


class TestDataProvenance(unittest.TestCase):
    def test_every_author_year_resolves_or_is_declared_informal(self):
        bib = _bib_surnames()
        if bib is None:
            self.skipTest("data_references.csv not present")
        unresolved = []
        for (name, year), files in sorted(_data_citations().items()):
            if name in INFORMAL or name.lower() in bib:
                continue
            unresolved.append("%s %s (%s)" % (name, year, ", ".join(sorted(files))))
        self.assertFalse(unresolved,
                         "author-year strings in data/ that are neither in data_references.csv nor "
                         "declared informal:\n  " + "\n  ".join(unresolved))

    def test_the_corrected_attribution_has_not_regressed(self):
        """The specific failure this test was written for: benchmarks_air.csv credited an invented
        author list while the .bib already had the real one."""
        path = asset_path(ROOT, "data", "benchmarks_air.csv")
        if not os.path.exists(path):
            self.skipTest("benchmarks_air.csv not present")
        text = open(path, encoding="utf-8").read()
        self.assertNotIn("Ahmed et al", text, "the fabricated SANH author list is back")
        self.assertIn("Tomlinson", text, "SANH attribution lost")

    def test_informal_entries_are_actually_used(self):
        """Stop INFORMAL becoming a graveyard: every entry must still appear in the data files, so
        a name whose source string was fixed does not stay whitelisted forever."""
        names = {n for n, _ in _data_citations()}
        stale = sorted(set(INFORMAL) - names)
        self.assertFalse(stale, "INFORMAL lists names no longer present in data/: %s" % stale)


class TestEveryActivityFileDeclaresItsDocument(unittest.TestCase):
    """A citation nothing can check is not provenance.

    Every activity CSV names the publication its numbers came from, and until this test
    existed nothing verified that the publication was in the repository. The release
    manifest hashes the CSVs, so a release could say "these are the exact numbers" without
    being able to say "and here is the document they were read from".

    That was not hypothetical, and it was worst where it mattered most. Agriculture - 49.6
    percent of the inventory - cited the Pakistan Economic Survey and the NFDC Fertilizer
    Review, and neither was under sources/, while nine other sectors archived theirs. The
    hole was invisible for the same reason every hole in this project has been invisible:
    the thing that would have failed was never asserted.

    data/source_documents.csv now classifies all of them, and this is the assertion that
    keeps it honest: archived means the document is here, not-archived means it is not and a
    gap row says so, derived means there is no outside document to keep.
    """

    STATES = ("archived", "not-archived", "derived")

    @classmethod
    def setUpClass(cls):
        with open(asset_path(ROOT, "data", "source_documents.csv"),
                  newline="", encoding="utf-8") as handle:
            cls.register = list(csv.DictReader(handle))
        cls.by_file = {r["data_file"]: r for r in cls.register}

    def _activity_files(self):
        # The same places scripts/make_source_register.py enumerates: the activity
        # home directory, data/nfdc (NFDC document extractions - activity by another
        # path), data/ml and data/gis (the geospatial CSVs the rc7 round pulled into
        # the provenance frame), and the loose pre-directory nfdc_offtake.csv. Keep
        # the two in step or files drift out of both scans and neither notices.
        prefixes = ("data/activity/", "data/nfdc/", "data/ml/", "data/gis/",
                    "data/pbs_census/", "data/district_records/", "data/gleam/", "data/gmw/")
        found = sorted({row["legacy_path"] for row in catalog(ROOT)
                        if row["legacy_path"].endswith(".csv")
                        and row["legacy_path"].startswith(prefixes)})
        if any(row["legacy_path"] == "data/nfdc_offtake.csv" for row in catalog(ROOT)):
            found.append("data/nfdc_offtake.csv")
        # the named non-CSV geometry artefacts (OSM derivative databases) come
        # from the generator's own tuple, so the two scans cannot drift
        mod = _load_script("make_source_register.py")
        for rel in mod.GEOMETRY_EXTRAS:
            if os.path.exists(asset_path(ROOT, rel)):
                found.append(rel)
        return sorted(found)

    def test_every_activity_file_is_registered(self):
        """Complete by construction: the test enumerates the files, so a new one added
        without a register entry fails here rather than shipping unprovenanced."""
        missing = sorted(set(self._activity_files()) - set(self.by_file))
        self.assertFalse(missing, "activity files with no source_documents.csv row:\n  "
                                  + "\n  ".join(missing))

    def test_the_register_has_no_phantom_rows(self):
        stale = sorted(p for p in set(self.by_file) - set(self._activity_files())
                       if readable(p))   # rc69: a restricted file a clone does not mount
        self.assertFalse(stale, "register rows for files that no longer exist:\n  "
                                + "\n  ".join(stale))

    def test_every_state_is_from_the_vocabulary(self):
        for r in self.register:
            self.assertIn(r["archival_state"], self.STATES, r["data_file"])

    def test_an_archived_document_is_actually_here(self):
        """The whole point. A row may not claim a document is archived unless it is."""
        require_documents(*sorted({r["archived_path"] for r in self.register
                                   if r["archival_state"] == "archived" and r["archived_path"]}))
        missing = []
        for r in self.register:
            if r["archival_state"] != "archived":
                continue
            path = asset_path(ROOT, r["archived_path"])
            if not r["archived_path"] or not os.path.exists(path):
                missing.append("%s -> %r" % (r["data_file"], r["archived_path"]))
        self.assertFalse(missing, "rows claiming an archive that is not there:\n  "
                                  + "\n  ".join(missing))

    def test_an_unarchived_document_is_declared_in_the_gap_register(self):
        """Not-archived is allowed, silence is not. Each must point at a gap row whose
        claim_class says exactly that, so the reader of the register meets the caveat."""
        gaps = {g["gap_id"]: g for g in completeness.load_data_gaps()}
        problems = []
        for r in self.register:
            if r["archival_state"] != "not-archived":
                continue
            gap = gaps.get(r["gap_id"])
            if gap is None:
                problems.append("%s: gap_id %r is not in data_gaps.csv"
                                % (r["data_file"], r["gap_id"]))
            elif gap["claim_class"] != "not-archived":
                problems.append("%s: gap %s has claim_class %r, expected not-archived"
                                % (r["data_file"], r["gap_id"], gap["claim_class"]))
        self.assertFalse(problems, "unarchived documents that are not declared:\n  "
                                   + "\n  ".join(problems))

    def test_a_not_archived_claim_is_actually_absent_from_the_archive(self):
        """The inverse the register never had, and the check that found ten stale rows
        in the rc29 re-audit: archived rows are tested for presence, but nothing
        tested a NOT-archived row against the archive, so a document could arrive
        and its register row would keep claiming absence forever.
        The match is deliberately conservative - the folded basename of the cited
        source must appear as (or inside) a filename - so prose citations like
        'FAOSTAT historical panel' can never false-positive.

        rc65: IT LOOKED IN ONE PLACE. This walked sources/ only. The 2026-10-12 retention
        sweep found three rows claiming absence for documents that were held the whole
        time: the Fatima reports and a FAOSTAT extract under data/raw/, and the Punjab
        Pocket Book as a member of a zip under sources/. It now walks both document trees
        and reads every archive's member list. A not-archived file may still cite documents
        that ARE held (its state is its weakest citation), so a hit that
        data/catalog/cited_documents.csv already lists for that file is not a stale claim."""
        import zipfile

        def fold(text):
            return re.sub(r"[^a-z0-9]+", "", text.lower())
        on_disk = []
        for tree in ("sources", os.path.join("data", "raw")):
            for dirpath, _dirs, files in os.walk(os.path.join(ROOT, tree)):
                for name in files:
                    relative = os.path.relpath(os.path.join(dirpath, name), ROOT)
                    on_disk.append((fold(name), relative))
                    if name.lower().endswith(".zip"):
                        try:
                            with zipfile.ZipFile(os.path.join(dirpath, name)) as archive:
                                members = archive.namelist()
                        except (zipfile.BadZipFile, OSError):
                            continue        # an LFS pointer or a damaged archive lists nothing
                        for member in members:
                            on_disk.append((fold(os.path.basename(member)),
                                            "%s::%s" % (relative, member)))
        accounted = {}
        with open(os.path.join(ROOT, "data", "catalog", "cited_documents.csv"),
                  encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(line for line in handle if not line.startswith("#")):
                accounted.setdefault(row["data_file"], set()).add(row["path"])
        stale = []
        for r in self.register:
            if r["archival_state"] != "not-archived":
                continue
            cited = fold(os.path.basename(r["primary_source"]))
            if len(cited) <= 12:      # short tokens match everything; prose never a file
                continue
            listed = accounted.get(r["data_file"], set())
            hits = [path for folded, path in on_disk
                    if (cited in folded or folded in cited) and len(folded) > 12
                    # A *_SOURCES.json sidecar is a witness OF non-retention (it
                    # pins the hash of a document that was not kept); a row citing
                    # its own sidecar is correct, not stale.
                    and not path.endswith("_SOURCES.json")
                    and path not in listed
                    and not any(path.startswith(d.rstrip("/") + "/") for d in listed if d)]
            if hits:
                stale.append("%s cites %r which exists: %s"
                             % (r["data_file"], r["primary_source"], hits[:2]))
        self.assertFalse(stale,
                         "not-archived rows whose cited document is held and is not listed "
                         "for them in data/catalog/cited_documents.csv - list it there and "
                         "flip the row in scripts/make_source_register.py CLASSIFIED if "
                         "nothing else it cites is open:\n  "
                         + "\n  ".join(stale))

    def test_the_not_retained_register_is_a_bijection_with_the_not_archived_rows(self):
        """rc29: every not-archived activity file appears in exactly one not-retained
        register row's data_files, and every data_files entry is a not-archived row.
        A file in neither direction is a silent gap; a file in both twice is a
        double-count."""
        with open(asset_path(ROOT, "data", "not_retained_register.csv"),
                  newline="", encoding="utf-8") as f:
            register_rows = list(csv.DictReader(f))
        covered = []
        for r in register_rows:
            covered.extend(p.strip() for p in r["data_files"].split(";") if p.strip())
        not_archived = [r["data_file"] for r in self.register
                        if r["archival_state"] == "not-archived"]
        self.assertEqual(sorted(covered), sorted(set(covered)),
                         "a data file appears in two register rows")
        self.assertEqual(sorted(covered), sorted(not_archived))

    def test_every_not_retained_row_has_a_hash_or_a_typed_reason(self):
        """The register's contract: sha256 XOR-at-least legal reason - a row with
        neither is a silent blank, which is the thing this register exists to end.
        Where a retrieval script is named it must exist; where a date is given it is
        ISO; where a URL is given it is one."""
        with open(asset_path(ROOT, "data", "not_retained_register.csv"),
                  newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertTrue(rows)
        problems = []
        for r in rows:
            sid = r["source_id"]
            if not (r["sha256"].strip() or r["legal_reason_for_non_retention"].strip()):
                problems.append("%s: neither sha256 nor legal reason" % sid)
            if r["sha256"].strip() and not re.fullmatch(r"[0-9a-f]{64}", r["sha256"]):
                problems.append("%s: malformed sha256" % sid)
            script = r["retrieval_script"].strip()
            if script and not os.path.exists(asset_path(ROOT, script)):
                problems.append("%s: retrieval script %r does not exist" % (sid, script))
            if r["access_class"].strip() not in (
                    "openly-licensed", "free-to-read", "available-on-request",
                    "paid", "computational", "dead-with-official-alternative"):
                problems.append("%s: access_class %r outside the closed vocabulary"
                                % (sid, r["access_class"]))
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["access_date_utc"].strip()):
                problems.append("%s: access_date_utc not ISO" % sid)
            for url in r["exact_url"].split(";"):
                url = url.strip()
                if url and not url.startswith("https://"):
                    problems.append("%s: URL %r not https" % (sid, url))
        self.assertFalse(problems, "\n  ".join(problems))

    def test_the_agriculture_documents_are_archived_now(self):
        """The specific hole this register was built to close: the largest sector's crop
        and fertiliser activity cited two documents the repository did not hold."""
        require_documents("sources/Agriculture/Pakistan_Economic_Survey_2023-24_Agriculture.pdf",
                          "sources/Agriculture/NFDC_Fertilizer_Review_2023-24.pdf")
        for name in ("Pakistan_Economic_Survey_2023-24_Agriculture.pdf",
                     "NFDC_Fertilizer_Review_2023-24.pdf"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, "sources", "Agriculture", name)),
                            "%s is not archived" % name)

    def test_the_register_regenerates(self):
        """The committed register must be what the script produces, so a hand edit cannot
        drift from the classification logic."""
        mod = _load_script("make_source_register.py")
        fresh = {r["data_file"]: r["archival_state"] for r in mod.build()}
        committed = {k: v["archival_state"] for k, v in self.by_file.items()}
        self.assertEqual(committed, fresh)


if __name__ == "__main__":
    unittest.main()

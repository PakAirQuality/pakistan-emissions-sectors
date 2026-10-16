"""One release, named the same thing by every artefact that names it.

WHY THIS FILE EXISTS. Before this round the release called itself four things, and the two
files Zenodo actually reads pointed at the wrong repository:

    CITATION.cff / .zenodo.json   "Pakistan Emissions Inventory (pkinv)"
    paper_national.tex            "the PakEmis inventory"
    references.bib                "{PakEmis} v1.0" -- beside its own note saying "1.0.0rc1"
    README.md                     "Pakistan National Greenhouse Gas Inventory"
    CITATION.cff repository-code  .../pakistan-emissions-nowcast   <- the COMPANION repo

None of it is a number, so the whole numeric apparatus in tests/paper_numbers/ was
blind to it. The bibliography case is the sharpest: one entry claimed version 1.0 in its title
and 1.0.0rc1 in its note, and a reader citing this work would have propagated the wrong one.

The identity now resolves through src/pkinv/release.py, and this file asserts that every
artefact agrees with it. Modelled on tests/test_build_definition.py: parse each artefact
textually, then assert they say the same thing.
"""

from pkinv.assets import asset_path
import glob
import json
import os
from pkinv.paths import PAPER_NATIONAL_GENERATED, PAPER_NATIONAL_MAIN, PAPER_NATIONAL_SECTIONS  # noqa: E402
import re
import sys
import unittest


import pkinv                                               # noqa: E402
from pkinv import release                                  # noqa: E402
from _support import ROOT

# Every file that states who this release is. The last test asserts this list is complete.
ARTEFACTS = [
    "CITATION.cff",
    ".zenodo.json",
    "README.md",
    "docs/reproducibility.md",
    # The classification-scheme report (2026-10-06): what the codes are, where they came from
    # and what the migration to IPCC 2006 moved. It names the product throughout and states
    # the pins it did NOT move, which is the whole claim of a re-coding, so the sweep must
    # read it. It deliberately states no release version - its identity is the release record
    # it accompanies, as docs/reproducibility.md does.
    "docs/classification_scheme.md",
    # The power coal energy-basis report (2026-10-07), Stage 2 of the twenty-second review.
    # Same reasoning as the classification report above: it states the pins it did NOT move
    # and names the products throughout, so a reader could take it for a statement about
    # which release this is. It deliberately states no version.
    "docs/power_coal_energy_basis.md",
    # The dung-destination report (2026-10-07), Stage 3 of the same review. It prints the
    # difference between the two national pins as the residential configurations' own gap,
    # which is a statement a reader could take for a statement about the release. Like the
    # two above it, it deliberately states no version.
    "docs/dung_destination.md",
    # The power station geography report (2026-10-07), Stage 4 of the same review. It
    # prints provincial and national CO2 totals as the proof that nothing moved, which is
    # exactly the kind of statement a reader could take for a statement about which
    # release this is. Like the three above it, it deliberately states no version.
    "docs/power_station_geography.md",
    "paper_common/references.bib",
    "paper_common/release_cover.tex",
    "paper_national/versions/v1/paper_national.tex",
    "paper_national/versions/v1/sections/00_abstract.tex",
    "paper_national/versions/v1/supplement.tex",
    # The compact editorial rewrite of the national article (1 October 2026), which states
    # the candidate release in its availability text. It is registered here before it is
    # anything else in this repository, because this registry's own question - "a new
    # artefact cannot quietly become a seventh answer" - is the first one a second
    # manuscript of the same inventory raises. It names the canonical repository rather
    # than the companion, and the release it states is the package version.
    "paper_national/versions/v3/paper.tex",
    # Its technical documentation, installed from the author's source package on 2026-10-05.
    # It names the product and deliberately states NO version: its identity is the release
    # record it accompanies, and a literal here would go stale between releases - the same
    # reasoning as docs/zenodo_data_record.md above. Registered so the sweep reads it.
    "paper_national/versions/v3/technical_supplement.tex",
    "outputs/release_manifest.json",
    # A design specification names the project and states no release, which is exactly the
    # case this registry exists to make someone think about rather than skip.
    "docs/product_catalog_design.md",
    # The rebuild log names the release it reconstructs, in its filename and body.
    "docs/rebuild_log.md",
    "docs/rebuild_log.json",
    # The prepared-not-deposited data record (rc29) deliberately states no version:
    # the deposit form takes the manifest's version at deposit time, and a literal
    # here would go stale between releases.
    "docs/zenodo_data_record.md",
    # The drafted request letters (rc20) name the project so a recipient knows what the
    # data serves; they deliberately state no version - a letter sent months later must
    # not carry a stale release claim.
    "docs/data_request_letters.md",
    # The ESSD outline (v1.0.0 program) names the product as "PakEmis v1.0" in the title of
    # the data-description article: the two-component PRODUCT NAME of the 1.0 line, accepted
    # only while the release is 1.0.x (see _same_release).
    "docs/essd_outline.md",
    # The semantic contract's prose names the product and the frozen release's identity rule.
    "docs/semantic_contract.md",
    # The availability statements are GENERATED from the manifest by
    # scripts/make_availability.py, so they name the release by construction; registered
    # so that the sweep reads what the article and the technical notes actually print.
    "paper_national/versions/v1/generated/availability.tex",
    "paper_national/versions/v1/generated/abstract_doi.tex",
    "paper_common/generated_availability_tn.tex",
    "paper_common/tn_banner.tex",
]


def _same_release(found, current):
    """Is a version string attached to the product name a claim about THIS release?

    Exact equality, or the two-component PRODUCT NAME of a release line ("PakEmis v1.0")
    while the release is on that line ("1.0.0", "1.0.0rc42", "1.0.3"). The name form is the
    one the ESSD article's title uses; it is not a version, and a full version beside the
    product name must still match exactly. "PakEmis v1.0" beside release 1.1.0 is the
    bibliography defect this file was written for, and it still fails."""
    if found == current:
        return True
    return found.count(".") == 1 and current.startswith(found + ".")

# A version attached to the product name, e.g. "PakEmis v1.0" or "PakEmis-GHG 1.0.0rc1".
PRODUCT_VERSION = re.compile(r"\{?\{?PakEmis[\w-]*\}?\}?[\s~]+v?(\d+\.\d+(?:\.\d+)?(?:rc\d+)?)")

# A release-candidate version standing on its own, e.g. "release 1.0.0rc2" or a tag
# "v1.0.0-rc2". PRODUCT_VERSION only fires when the version touches the product name, so
# the abstract's "under release \texttt{1.0.0rc2}" and reproducibility.md's tag
# instructions could go stale silently on a bump -- and would have, twice, without this.
BARE_RC_VERSION = re.compile(r"\bv?(\d+\.\d+\.\d+-?rc\d+)\b")

# v1.0.0: at a FINAL version the rc pattern above matches nothing that equals the release,
# so every rc literal left in an artefact must be marked history - and a final version is a
# claim only when a release word introduces it ("release \\texttt{1.0.0}", "version: 1.0.0",
# "tag v1.0.0", "| Version | **1.0.0** |"), never when it is a schema or interpreter version
# (cff-version 1.2.0, "git version 2.49.0", "python 3.11.10", a dependency pin).
RELEASE_CLAIM = re.compile(
    r"(?:release|(?<!cff-)(?<!git )(?<!lfs )(?<!python )version|tag)\b[^\n\d]{0,24}?v?(\d+\.\d+\.\d+(?:-?rc\d+)?)\b",
    re.IGNORECASE)

# Words that mark a version mention as history rather than a claim about THIS release:
# "Since 1.0.0rc1 was first cut", "v1.0.0-rc1 is the only tag that exists", "the rc42 tree,
# frozen", "every release candidate's history".
HISTORY_MARKERS = ("since", "was first cut", "only tag", "frozen", "release candidate",
                   "previous release", "superseded")

# A printed DOI: either the manifest's, or nothing. A placeholder (zenodo.XXXXXXX, TBD) that
# resolves to nothing is worse than an absence.
DOI = re.compile(r"\b10\.\d{4,9}/[^\s\)\]\}\"',;]+")

# Words that mark a mention of the companion repository as a deliberate cross-reference
# rather than a claim about where this code lives.
COMPANION_MARKERS = ("companion", "nowcast", "different question", "depends on this one")

# Directories whose contents are build output or vendored, not artefacts we author.
# CHANGELOG.md is exempt BY DESIGN: it is the release HISTORY, so it names every
# past rc deliberately - holding it to single-version consistency would either
# force history out of the changelog or fail on every legitimate entry. Its
# current-release section is the [unreleased]/topmost one, checked by eye at the
# version bump, and historical totals there are labelled as history.
SKIP = ("papers/pdf", ".git", "outputs/figures", "Code_files_", ".venv", "node_modules",
        "CHANGELOG.md", "CLAUDE.md")


def _text(relative):
    with open(asset_path(ROOT, relative), encoding="utf-8") as handle:
        return handle.read()


def _git_ignored():
    """Repo-relative paths git ignores, or an empty set where git cannot answer.

    A validation package is not a checkout, so the absence of git must not turn this into
    a skip-everything or an error; it simply means nothing is known to be ignored.
    """
    import subprocess
    try:
        out = subprocess.run(["git", "-C", ROOT, "ls-files", "--others", "--ignored",
                              "--exclude-standard", "--directory"],
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    if out.returncode != 0:
        return frozenset()
    return frozenset(os.path.normpath(line) for line in out.stdout.split("\n") if line)


class TestTheReleaseIsNamedTheSameThingEverywhere(unittest.TestCase):

    def test_the_metadata_version_fields_are_the_package_version(self):
        self.assertIn('version: %s' % pkinv.__version__, _text("CITATION.cff"))
        self.assertEqual(json.loads(_text(".zenodo.json"))["version"], pkinv.__version__)
        self.assertEqual(json.loads(_text("outputs/release_manifest.json"))["version"],
                         pkinv.__version__)

    def test_no_artefact_attaches_a_different_version_to_the_product(self):
        """The bibliography defect: "PakEmis v1.0" beside "release 1.0.0rc1"."""
        problems = []
        for relative in ARTEFACTS:
            for match in PRODUCT_VERSION.finditer(_text(relative)):
                if not _same_release(match.group(1), pkinv.__version__):
                    problems.append("%s: names the product at version %s; the release is %s"
                                    % (relative, match.group(1), pkinv.__version__))
        self.assertFalse(problems, "the product is versioned inconsistently:\n  "
                         + "\n  ".join(problems))

    def test_no_artefact_gives_the_companion_repository_as_this_one(self):
        """CITATION.cff gave repository-code and license-url as the companion repository.

        That is what Zenodo reads. A DOI minted against it would have archived this release
        under a URL pointing at different software.
        """
        problems = []
        for relative in ARTEFACTS:
            text = _text(relative)
            for match in re.finditer(re.escape(release.COMPANION_REPO), text):
                window = text[max(0, match.start() - 260):match.end() + 260].lower()
                if not any(marker in window for marker in COMPANION_MARKERS):
                    problems.append("%s: names %s with nothing marking it as the companion"
                                    % (relative, release.COMPANION_REPO))
        self.assertFalse(problems, "artefacts point at the companion repository:\n  "
                         + "\n  ".join(problems))

    def test_the_citation_metadata_names_this_repository(self):
        citation = _text("CITATION.cff")
        self.assertIn("repository-code: \"%s\"" % release.REPO_URL, citation)
        self.assertIn("license-url: \"%s\"" % release.LICENCE_URL, citation)

    def test_every_manuscript_prints_the_repository_url(self):
        """The fifth review found the URL in exactly one of eleven manuscripts: ten
        availability sections said "the repository" without naming it, so a reader of
        any paper but transport's could not find the software. Every main manuscript
        must print the canonical URL as a \\url{} in its availability text."""
        mains = [os.path.join(PAPER_NATIONAL_MAIN, "paper.tex")]
        mains += sorted(glob.glob(os.path.join(ROOT, "papers", "*", "paper.tex")))
        self.assertGreaterEqual(len(mains), 10, "manuscript resolver went blind")
        needle = "\\url{%s}" % release.REPO_URL
        missing = [os.path.relpath(m, ROOT) for m in mains
                   if needle not in open(m, encoding="utf-8").read()]
        self.assertFalse(missing, "manuscripts that never name the repository:\n  "
                         + "\n  ".join(missing))

    def test_the_product_name_is_the_declared_one(self):
        """The citation metadata carried no product name at all, which is why it could drift
        without contradicting anything."""
        for relative in ("CITATION.cff", ".zenodo.json", "README.md",
                         "paper_national/versions/v1/paper_national.tex", "paper_common/release_cover.tex"):
            self.assertIn(release.PRODUCT, _text(relative),
                          "%s does not name the product" % relative)

    def test_the_registry_covers_every_file_that_states_an_identity(self):
        """A new artefact cannot quietly become a seventh answer.

        Same closure argument scripts/audit_outputs.py makes for outputs/: it is not enough
        to check the files we remembered to list.
        """
        token = re.compile(r"PakEmis|repository-code|%s" % re.escape(release.COMPANION_REPO))
        registered = {os.path.normpath(a) for a in ARTEFACTS}
        # A file git IGNORES is not part of the release and cannot become a seventh answer
        # for any reader: it is not in the tree they clone, the manifest, or the deposit. A
        # local working file at the repository root - a handoff prompt, a scratch note -
        # would otherwise fail this, which says nothing about the release's identity.
        ignored = _git_ignored()
        unregistered = []
        from _support import presentation_layer
        index = presentation_layer()        # a validation package's own records; empty here
        for pattern in ("*.md", "*.cff", "*.json", "docs/*.md", "paper_common/*.tex",
                        "paper_common/*.bib", "paper_national/versions/v1/*.tex"):
            for path in glob.glob(asset_path(ROOT, pattern)):
                relative = os.path.relpath(path, ROOT)
                if any(s in relative for s in SKIP) or os.path.normpath(relative) in registered:
                    continue
                if os.path.normpath(relative) in ignored:
                    continue
                if os.path.normpath(relative) in index:
                    continue
                try:
                    body = open(path, encoding="utf-8").read()
                except (UnicodeDecodeError, OSError):
                    continue
                if token.search(body):
                    unregistered.append(relative)
        self.assertFalse(unregistered, "these state a release identity and are not in "
                         "ARTEFACTS:\n  " + "\n  ".join(sorted(unregistered)))

    def test_the_sweep_is_not_looking_at_nothing(self):
        """Every registered artefact must exist and must actually mention an identity, or
        the checks above hold over an empty set."""
        self.assertGreaterEqual(len(ARTEFACTS), 6)
        for relative in ARTEFACTS:
            path = asset_path(ROOT, relative)
            self.assertTrue(os.path.exists(path), "%s is registered but missing" % relative)
        naming = [a for a in ARTEFACTS if release.FAMILY in _text(a)]
        self.assertGreaterEqual(len(naming), 5,
                                "only %d artefacts name the product family; the identity "
                                "checks would be nearly vacuous" % len(naming))

    def test_the_final_version_guard_has_its_controls(self):
        """Stored controls for RELEASE_CLAIM (v1.0.0): a release word before a full version is
        a claim; a schema or interpreter version is not."""
        positive = "| Version | **1.0.0rc42** |", "This paper describes release \\texttt{1.0.0} of PakEmis", \
                   "git tag -a v1.0.0 -m", "version: 1.0.0"
        for text in positive:
            self.assertIsNotNone(RELEASE_CLAIM.search(text), text)
        for text in ("cff-version: 1.2.0", "Python 3.11.10", "pandas==2.3.3", "schema pkinv.release/v1"):
            self.assertIsNone(RELEASE_CLAIM.search(text), text)
        self.assertEqual(RELEASE_CLAIM.search("| Version | **1.0.0rc42** |").group(1), "1.0.0rc42")

    def test_every_printed_doi_is_the_manifests(self):
        """No placeholder identifier anywhere, and every real one is the release manifest's."""
        from pkinv.report import release_manifest as rm
        minted = {v for v in rm.DOI.values() if v}
        problems = []
        files = list(ARTEFACTS) + sorted(glob.glob(os.path.join(ROOT, "papers", "*", "*.tex"))
                                         + glob.glob(os.path.join(ROOT, "papers", "*", "sections", "*.tex"))
                                         + glob.glob(os.path.join(PAPER_NATIONAL_MAIN, "*.tex"))
                                         + glob.glob(os.path.join(PAPER_NATIONAL_SECTIONS, "*.tex"))
                                         + glob.glob(os.path.join(PAPER_NATIONAL_GENERATED, "*.tex")))
        for relative in files:
            path = relative if os.path.isabs(relative) else asset_path(ROOT, relative)
            own_entry = True
            for line in open(path, encoding="utf-8"):
                if line.lstrip().startswith(("#", "%")):
                    continue                     # a commented example is not a claim
                if path.endswith(".bib") and line.lstrip().startswith("@"):
                    # a cited third party's DOI is theirs; only this project's own entries
                    # (pakemis*, ahmad2026*) must carry the manifest's identifiers
                    key = line.split("{", 1)[1].split(",")[0].strip().lower() if "{" in line else ""
                    own_entry = key.startswith(("pakemis", "ahmad2026"))
                if path.endswith(".bib") and not own_entry:
                    continue
                for doi in DOI.findall(line):
                    doi = doi.rstrip(".")
                    if "zenodo." in doi and not doi.split("zenodo.")[1].isdigit():
                        problems.append("%s: placeholder %s" % (os.path.relpath(path, ROOT), doi))
                    elif "zenodo" in doi and doi not in minted:
                        problems.append("%s: %s is not the manifest's" % (os.path.relpath(path, ROOT), doi))
        self.assertFalse(problems, "printed DOIs that are not the release's:\n  " + "\n  ".join(problems))

    def test_the_guard_catches_the_bibliography_defect(self):
        """Stored positive control, from the entry this round corrected."""
        historical = "title = {{PakEmis} v1.0 Technical Documentation: Agriculture Module},"
        match = PRODUCT_VERSION.search(historical)
        self.assertIsNotNone(match, "the pattern no longer matches the defect it was "
                                    "written for")
        # The defect was the product name of one line beside the release of another; the
        # v1.0.0 program accepts the 1.0 NAME while the release is 1.0.x, so the control is
        # held against a release off that line, and the accepted form is asserted beside it.
        self.assertFalse(_same_release(match.group(1), "1.1.0"))
        self.assertFalse(_same_release("0.9", "1.0.0"))
        self.assertTrue(_same_release("1.0", "1.0.0"))
        self.assertTrue(_same_release("1.0", "1.0.0rc42"))
        self.assertFalse(_same_release("1.0.0rc41", "1.0.0rc42"))

    def test_no_artefact_states_a_bare_version_that_is_not_this_release(self):
        """Every rc version an artefact states, product-name-adjacent or not, is either
        this release or marked history. Tag forms normalise: v1.0.0-rc3 is 1.0.0rc3."""
        current = pkinv.__version__
        problems = []
        for relative in ARTEFACTS:
            text = _text(relative)
            claims = [(m.start(), m.end(), m.group(1)) for m in BARE_RC_VERSION.finditer(text)]
            claims += [(m.start(1), m.end(1), m.group(1)) for m in RELEASE_CLAIM.finditer(text)]
            for start, end, found in sorted(set(claims)):
                if found.replace("-rc", "rc") == current:
                    continue
                window = text[max(0, start - 220):end + 220].lower()
                if any(marker in window for marker in HISTORY_MARKERS):
                    continue
                problems.append("%s: states %s; the release is %s and nothing marks it "
                                "as history" % (relative, found, current))
        self.assertFalse(problems, "artefacts state a version that is not this "
                         "release:\n  " + "\n  ".join(problems))

    def test_the_bare_version_guard_catches_the_rc2_abstract(self):
        """Stored positive control: the sentence that would have gone stale silently."""
        historical = ("data and every output quoted here are in one repository under "
                      "release \\texttt{1.0.0rc2}.")
        match = BARE_RC_VERSION.search(historical)
        self.assertIsNotNone(match)
        self.assertNotEqual(match.group(1).replace("-rc", "rc"), pkinv.__version__,
                            "the stored rc2 control equals the current release; move the "
                            "control forward so the guard still demonstrates the defect")
        self.assertIsNone(PRODUCT_VERSION.search(historical),
                          "PRODUCT_VERSION now catches the bare form; this guard can only "
                          "retire if that stays true")



class TestTheCoverPrintsBothDigestsUnderTheirOwnNames(unittest.TestCase):
    """rc9-rc40 printed ONE digest - the release manifest's - under the label "Source
    manifest", on every PDF that carries the cover (the nineteenth review's M-7). The two
    files are different things with different lifetimes, and the cover now prints both.
    The release-manifest line stays VOLATILE (its digest changes with the commit); the
    source-manifest digest is a property of the acquisition register and is checked."""

    def setUp(self):
        self.cover = _text("paper_common/release_cover.tex")

    def _line(self, label):
        lines = [l for l in self.cover.split("\n") if l.startswith(label)]
        self.assertEqual(len(lines), 1, "%r printed %d times" % (label, len(lines)))
        return lines[0]

    def test_both_labels_are_present_and_name_their_file(self):
        release = self._line("Release manifest &")
        source = self._line("Source manifest &")
        self.assertIn("release\\_manifest.json", release)
        self.assertIn("source\\_manifest.csv", source)
        self.assertNotIn("release\\_manifest", source)

    def test_the_source_digest_is_the_registers(self):
        import hashlib
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import make_release_cover
        with open(asset_path(ROOT, "data", "manifests", "source_manifest.csv"), "rb") as f:
            want = hashlib.sha256(f.read()).hexdigest()[:16]
        printed = re.search(r"\\texttt\{([0-9a-f]{16})\}", self._line("Source manifest &"))
        self.assertIsNotNone(printed, "no 16-hex digest on the source-manifest line")
        self.assertEqual(printed.group(1), want)
        self.assertEqual(make_release_cover.source_manifest_digest()[:16], want)

    def test_the_two_digests_differ(self):
        rel = re.search(r"\\texttt\{([0-9a-f]{16})\}", self._line("Release manifest &"))
        src = re.search(r"\\texttt\{([0-9a-f]{16})\}", self._line("Source manifest &"))
        self.assertIsNotNone(rel)
        self.assertNotEqual(rel.group(1), src.group(1),
                            "the same digest is printed under both labels - the rc40 defect")

    def test_only_the_release_manifest_line_is_volatile(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import make_release_cover
        self.assertIn("Release manifest &", make_release_cover.VOLATILE)
        self.assertNotIn("Source manifest &", make_release_cover.VOLATILE)


class TestTheChangelogNamesThisRelease(unittest.TestCase):
    """CHANGELOG.md is exempt from the version-consistency sweep by design, because it is
    history and must name every past rc. That exemption left a hole: nothing asserted the
    CURRENT version has a section at all, so a release could ship with no entry and every
    test stay green - which is "checked by eye at the version bump", i.e. checked by
    nobody. This asserts only existence and topmost position, never absence of history."""

    def test_the_current_version_has_a_section(self):
        path = os.path.join(ROOT, "CHANGELOG.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        heading = "## [%s]" % pkinv.__version__
        self.assertIn(heading, text,
                      "CHANGELOG.md has no section for the current release %s - add one "
                      "at the top before minting" % pkinv.__version__)

    def test_the_current_version_is_the_topmost_section(self):
        path = os.path.join(ROOT, "CHANGELOG.md")
        with open(path, encoding="utf-8") as handle:
            sections = [line for line in handle if line.startswith("## [")]
        self.assertTrue(sections, "CHANGELOG.md carries no release sections")
        self.assertTrue(sections[0].startswith("## [%s]" % pkinv.__version__),
                        "the topmost CHANGELOG section is %r, not the current release %s"
                        % (sections[0].strip(), pkinv.__version__))


class TestNoUnmadeSubmissionIsClaimed(unittest.TestCase):
    """The eleventh review found the bibliography asserting the national article was
    Submitted. It is not - ROADMAP Stage 11 records the rewrite as correctly not
    started, no DOI exists, no journal is named, the branch has never been pushed -
    and the claim had propagated into five compiled .bbl files and the shipped PDFs
    through one shared entry. A status a reader cannot verify must not be asserted."""

    def test_the_shared_bibliography_claims_no_submission(self):
        text = open(os.path.join(ROOT, "paper_common", "references.bib"),
                    encoding="utf-8").read()
        entry = text[text.index("@unpublished{ahmad2026national"):]
        entry = entry[:entry.index("\n}")]
        self.assertNotIn("submitted", entry.lower())
        self.assertIn("local review package prepared", entry.lower())
        self.assertIn("pending", entry.lower())

    def test_no_readme_claims_a_submission_the_status_constant_denies(self):
        """The fourteenth review found the SAME defect class one directory over:
        papers/pdf/README.md said the national article 'is submitted' - written
        when submission was imminent, false at the release it shipped with, and
        unreachable by the vintage sweep because papers/pdf sits in its SKIP
        list (compiled PDFs, deliberately). The status is now a constant
        (release.MANUSCRIPT_STATUS), the manifest carries it, and BOTH READMEs
        are swept here explicitly - the SKIP list no longer shelters the claim."""
        from pkinv import release
        pattern = re.compile(r"\bis submitted\b|\bwas submitted\b"
                             r"|\bhas been submitted to\b")
        for relative in ("README.md", os.path.join("papers", "pdf", "README.md")):
            text = open(asset_path(ROOT, relative), encoding="utf-8").read()
            # a DENIAL is not a claim: "No manuscript here has been submitted"
            # is the truthful status sentence and must keep passing
            hits = [m.group(0) for m in pattern.finditer(text)
                    if not re.search(r"\b(?:no|none|nothing)\b[^.]*$",
                                     text[max(0, m.start() - 80):m.start()],
                                     re.IGNORECASE)]
            if release.MANUSCRIPT_STATUS != "submitted":
                self.assertFalse(
                    hits,
                    "%s asserts a submission (%s) while release.MANUSCRIPT_STATUS "
                    "is %r - either the sentence or the constant is lying"
                    % (relative, hits, release.MANUSCRIPT_STATUS))

    def test_the_manifest_carries_the_manuscript_status(self):
        import json
        from pkinv import release
        manifest = json.load(open(os.path.join(ROOT, "outputs",
                                               "release_manifest.json"),
                                  encoding="utf-8"))
        self.assertEqual(manifest["product"]["manuscript_status"],
                         release.MANUSCRIPT_STATUS)
        self.assertEqual(manifest["product"]["submission_identifier"],
                         release.SUBMISSION_IDENTIFIER)

    def test_no_manuscript_claims_a_doi_at_submission(self):
        import glob as _glob
        for pattern in (os.path.join(ROOT, "papers", "*", "*.tex"),
                        os.path.join(ROOT, "papers", "*", "sections", "*.tex"),
                        os.path.join(PAPER_NATIONAL_MAIN, "*.tex"),
                        os.path.join(PAPER_NATIONAL_SECTIONS, "*.tex")):
            for path in _glob.glob(pattern):
                text = " ".join(open(path, encoding="utf-8").read().split())
                self.assertNotIn("DOI minted at submission", text,
                                 os.path.basename(path))
                self.assertNotIn("archived with a DOI \\emph{at submission}", text,
                                 os.path.basename(path))


class TestTheManifestDeclaresTheLicenceCarveouts(unittest.TestCase):
    """The tenth review's ESSD gate: the machine-readable manifest claimed blanket
    CC-BY over a tree whose own LICENSE-data carves out ODbL derivative databases.
    A submission record built from the manifest would have mis-stated the rights on
    five files, 71 registry rows and one file LICENSE-data itself had missed."""

    def test_the_manifest_names_every_odbl_carveout(self):
        import json
        manifest = json.load(open(os.path.join(ROOT, "outputs",
                                               "release_manifest.json"),
                                  encoding="utf-8"))
        licences = manifest["licences"]
        self.assertIn("odbl_carveouts", licences,
                      "the manifest claims one licence for the whole tree while "
                      "LICENSE-data carves out ODbL databases")
        # Each whole-file entry reads "<published identity> (ships at <path>)" since
        # the two differ, so this matches on the published identity rather than on the
        # whole string. The agreement between the two documents and the archive is
        # asserted in tests/test_deposit_licensing.py; here the point is only that the
        # manifest has not lost a carve-out.
        declared = {entry.split(" (ships at ")[0] for entry in licences["odbl_carveouts"]}
        text = open(os.path.join(ROOT, "LICENSE-data"), encoding="utf-8").read()
        for path in ("data/gis/landfills/pak_landfill_assets.csv",
                     "data/gis/rail/pak_rail_network.geojson",
                     "data/gis/rail/yards.csv",
                     "data/gis/roads/pak_road_density_267x340.npy",
                     "data/gis/osm_building_fraction_267x340.npy"):
            self.assertIn(path, text, "LICENSE-data lost a carveout")
            self.assertIn(path, declared, "the manifest omits %s" % path)

    def test_the_manifest_declares_the_evaluation_only_layer(self):
        import json
        manifest = json.load(open(os.path.join(ROOT, "outputs",
                                               "release_manifest.json"),
                                  encoding="utf-8"))
        note = manifest["licences"].get("undetermined", "")
        self.assertIn("MARS", note,
                      "MARS carries no licence declaration anywhere; its status "
                      "must be stated, not silent")
        self.assertIn("evaluation", note.lower())


if __name__ == "__main__":
    unittest.main()

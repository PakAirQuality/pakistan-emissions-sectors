"""One release, named the same thing by every artefact that names it.

WHY THIS FILE EXISTS. Before this round the release called itself four things, and the two
files Zenodo actually reads pointed at the wrong repository:

    CITATION.cff / .zenodo.json   "Pakistan Emissions Inventory (pkinv)"
    the national description      "the PakEmis inventory"
    the bibliography              "{PakEmis} v1.0" -- beside its own note saying "1.0.0rc1"
    README.md                     "Pakistan National Greenhouse Gas Inventory"
    CITATION.cff repository-code  .../pakistan-emissions-nowcast   <- the COMPANION repo

None of it is a number, so every numeric check was blind to it. The bibliography case is the sharpest: one entry claimed version 1.0 in its title
and 1.0.0rc1 in its note, and a reader citing this work would have propagated the wrong one.

The identity now resolves through src/pkinv/release.py, and this file asserts that every
artefact agrees with it. Modelled on tests/test_build_definition.py: parse each artefact
textually, then assert they say the same thing.
"""

from pkinv.assets import asset_path
import glob
import json
import os
import re
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
    # The semantic contract's prose names the product and the frozen release's identity rule.
    "docs/semantic_contract.md",
    "docs/contribution_evidence_review.md",
    "docs/nitrogen_comparison_evaluation.md",
    "docs/pakistan_inventory_comparison.md",
]


def _same_release(found, current):
    """Is a version string attached to the product name a claim about THIS release?

    Exact equality, or the two-component PRODUCT NAME of a release line ("PakEmis v1.0")
    while the release is on that line ("1.0.0", "1.0.0rc42", "1.0.3"). The name form is the
    one a citation title uses; it is not a version, and a full version beside the
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
# docs/history_rewrite.md is history in the same sense: it quotes every rewritten commit's
# subject, release names included, as it was written.
SKIP = (".git", "outputs/figures", "Code_files_", ".venv", "node_modules",
        "CHANGELOG.md", "CLAUDE.md", "docs/history_rewrite.md")


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

    def test_the_product_name_is_the_declared_one(self):
        """The citation metadata carried no product name at all, which is why it could drift
        without contradicting anything."""
        for relative in ("CITATION.cff", ".zenodo.json", "README.md"):
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
        for pattern in ("*.md", "*.cff", "*.json", "docs/*.md"):
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
        positive = "| Version | **1.0.0rc42** |", "This dataset describes release \\texttt{1.0.0} of PakEmis", \
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
        files = list(ARTEFACTS)
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
        # rc69: work is committed publicly between releases, under one "## [Unreleased]"
        # section at the very top that the next mint renames. Anywhere else it is a section
        # a mint forgot to rename.
        unreleased = [i for i, line in enumerate(sections) if line.startswith("## [Unreleased]")]
        self.assertIn(unreleased, ([], [0]),
                      "an [Unreleased] CHANGELOG section may appear once, at the top")
        sections = sections[len(unreleased):]
        self.assertTrue(sections, "CHANGELOG.md carries no release sections")
        self.assertTrue(sections[0].startswith("## [%s]" % pkinv.__version__),
                        "the topmost CHANGELOG section is %r, not the current release %s"
                        % (sections[0].strip(), pkinv.__version__))



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

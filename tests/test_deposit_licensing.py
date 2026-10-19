"""Nothing enters the archive deposit under a licence this project cannot grant.

WHY. sources/ holds 357 tracked files - 3.8 GB of OGRA, NEPRA, PBS, NFDC and PCAA
publications plus 580 MB of HIES microdata - and sixty of the sixty-five archived documents
carry a licence nobody has established. LICENSE-data opens "Data, figures, model cards, and
the paper text in this repository are licensed under CC-BY-4.0" and .zenodo.json declared the
deposit open over the whole tree. Read literally, publishing it would have REDISTRIBUTED SIXTY
THIRD-PARTY DOCUMENTS UNDER A LICENCE THIS PROJECT CANNOT GRANT, and no test in the release
could see it. The OpenStreetMap ODbL carve-out beside it was careful and correct; this was the
gap next to it.

THESE ARE ABSOLUTE, NOT RATCHETED, and that is the point of the design. The deposit ships
products and not documents, so "every deposited file carries a licence we can grant" is a
promise kept BY CONSTRUCTION today rather than an aspiration. A ratchet would be the wrong
instrument: there is no acceptable non-zero count of files published without the right to
publish them.

Run:  python3 -m unittest discover tests -p "test_deposit_licensing.py"
"""

from pkinv.assets import asset_path
import csv
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from _support import release_time_check  # noqa: E402
from unittest.mock import patch

from pkinv.paths import OUTPUTS, ROOT
from pkinv.report import deposit_manifest as deposit
from pkinv.core.io import read_rows


def _rows(name):
    return read_rows(os.path.join(OUTPUTS, name))


class TestNothingShipsWithoutTheRightToShipIt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deposit = _rows("pakemis_deposit_manifest.csv")
        cls.register = _rows("pakemis_source_register.csv")

    def test_every_deposited_file_carries_a_grantable_licence(self):
        """The whole gate, in one assertion."""
        bad = sorted(r["path"] for r in self.deposit
                     if r["outbound_licence"] not in deposit.DEPOSITABLE)
        self.assertFalse(bad, "files in the deposit whose licence this project cannot grant, "
                              "which means they must not be published: %s" % bad[:20])

    def test_no_source_document_is_in_the_deposit(self):
        """sources/ is excluded by construction, and this is what keeps it so when someone
        adds a pattern to DEPOSIT_PATTERNS without thinking about rights."""
        leaked = sorted(r["path"] for r in self.deposit if r["path"].startswith("sources/"))
        self.assertFalse(leaked, "third-party documents reached the deposit: %s" % leaked[:20])

    def test_every_deposited_licence_is_from_the_vocabulary(self):
        for row in self.deposit:
            self.assertIn(row["outbound_licence"], deposit.OUTBOUND_VALUES, row["path"])

    def test_every_row_says_why_it_may_ship(self):
        for row in self.deposit:
            self.assertGreater(len(row["licence_reason"]), 20, row["path"])

    def test_the_deposit_and_the_working_tree_agree(self):
        release_time_check("the deposit manifest is regenerated at the release fixpoint")
        if not os.path.isdir(os.path.join(ROOT, ".git")):
            self.skipTest("compares the deposit with a git working tree; a validation package has none")
        for row in self.deposit:
            self.assertTrue(os.path.isfile(asset_path(ROOT, row["path"])),
                            "%s is in the deposit manifest and not on disk" % row["path"])

    def test_every_held_product_a_reader_must_seed_is_deposited(self):
        """rc68: 66 held products were seeded by the clean rebuild from the maintainer's
        checkout and absent from the deposit, so unpacking the archives could not build."""
        shipped = {row["path"] for row in self.deposit}
        # A declared exclusion stays out (outputs/figures/ is regenerable presentation; the
        # four held figures there are read by nothing the deposit build runs).
        missing = [path for path in deposit.held_product_paths()
                   if path not in shipped and not deposit._excluded(path)]
        self.assertEqual(missing, [])

    def test_a_held_document_location_does_not_depend_on_the_disk(self):
        """The rc68 clean rebuild has no data/pbs_census (documents are not deposited), and
        the disk-dependent resolver sent the register to the migrated CSV folder instead."""
        deposit._held_manifest_hashes()  # the manifest's own keys; then no further resolution
        with patch.object(deposit, "storage_path", side_effect=AssertionError("read the disk")):
            self.assertEqual(deposit.document_location("data/pbs_census"), "data/pbs_census")
            self.assertEqual(deposit.document_location("data/district_records/"),
                             "data/district_records")

    def test_every_deposited_checksum_list_names_only_deposited_files(self):
        """A SHA256SUMS a reader cannot run is a broken promise inside the package.

        The rc68 companion shipped the rc67 baseline's list and PDFs without its three .tex
        sources, which no input pattern matched; `shasum -c` failed on the deposited copy.
        """
        shipped = {row["path"] for row in self.deposit}
        from _support import readable
        for listed in sorted(path for path in shipped if path.endswith("/SHA256SUMS")
                             and readable(path)):
            base = os.path.dirname(listed)
            with open(asset_path(ROOT, listed), encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    named = line.split(None, 1)[1].strip().lstrip("*")
                    self.assertTrue(base + "/" + named in shipped, "%s names %s, which the "
                                    "deposit does not ship" % (listed, named))

    def test_every_deposited_file_is_hashed_or_says_where_its_hash_lives(self):
        """A deposit a reader cannot verify is a deposit they have to trust.

        ONE CLASS CANNOT BE HASHED HERE AND IT IS NOT A LOOPHOLE. This manifest listed ITSELF
        with its own digest - a fixpoint that cannot close, because writing the row changes
        the file the row describes - and the same held for everything written after it: the
        sixteen PDFs the release fixpoint builds, the paper-hash sidecar written after those,
        and release_manifest.json, which stamps the commit it describes. The clean-room
        rebuild caught all twenty. They keep their place in the deposit and point at the
        artefact that does hold their digest, which is exactly how release_manifest.py
        already handles the PDFs.
        """
        for row in self.deposit:
            if len(row["sha256"]) == 64:
                self.assertFalse(row["hash_recorded_in"], row["path"])
                continue
            self.assertTrue(deposit.context_stamped(row["path"]),
                            "%s carries no digest and is not a declared context-stamped "
                            "artefact" % row["path"])
            self.assertTrue(row["hash_recorded_in"],
                            "%s is undigested and does not say where its hash lives"
                            % row["path"])
            self.assertGreater(len(row["not_digested_because"]), 25, row["path"])

    def test_the_undigested_class_stays_small_and_declared(self):
        """It is the one exemption in this file, so it is bounded: the deposit manifest, the
        source register, the release manifest, the test record and the product facts."""
        undigested = [r for r in self.deposit if len(r["sha256"]) != 64]
        # 27 -> 5 (rc70): the typeset documents, their hash sidecar, the release cover and two
        # registers that described them left this repository; what remains is written after
        # this manifest.
        self.assertLessEqual(len(undigested), 5,
                             "the undigested class grew to %d; something that COULD be "
                             "hashed has been declared context-stamped instead"
                             % len(undigested))


class TestExclusionIsVisible(unittest.TestCase):
    """The artefact inventory found this shape a pass ago and the wording is worth repeating:
    the defect was never the silence, it was that silence was indistinguishable from
    omission. A document left out with no row saying so is one a reader cannot know to seek."""

    @classmethod
    def setUpClass(cls):
        cls.register = _rows("pakemis_source_register.csv")

    def test_every_registered_source_says_why_its_document_is_absent(self):
        for row in self.register:
            self.assertEqual(row["document_in_deposit"], "no", row["data_file"])
            self.assertGreater(len(row["document_not_deposited_because"]), 20,
                               row["data_file"])

    def test_every_archived_document_can_be_checked_by_hash(self):
        """'Re-acquire the publication and compare' is only a procedure if the comparison
        exists. archived_path is a DIRECTORY in 63 of 65 rows, so the register points at the
        manifest's per-file hashes rather than inventing a single digest."""
        archived = [r for r in self.register if r["archival_state"] == "archived"]
        self.assertGreater(len(archived), 60)
        for row in archived:
            self.assertTrue(row["document_sha256"],
                            "%s is archived and the register offers no way to verify it"
                            % row["data_file"])

    def test_every_source_says_how_to_obtain_it(self):
        for row in self.register:
            self.assertGreater(len(row["how_to_obtain"]), 10, row["data_file"])

    def test_inbound_and_outbound_are_answered_separately(self):
        """The two questions one column used to conflate. Deriving facts from a published
        statistic is not republishing it, and a register that cannot say both cannot justify
        a deposit."""
        for row in self.register:
            self.assertTrue(row["inbound_use"], row["data_file"])
            self.assertIn(row["outbound_redistribution"], deposit.OUTBOUND_VALUES,
                          row["data_file"])
            self.assertGreater(len(row["outbound_reason"]), 15, row["data_file"])

    def test_the_undetermined_sources_are_still_the_majority_and_that_is_fine(self):
        """Recorded rather than chased. `not-established` is the CORRECT answer for a
        government PDF with no stated terms, and the deposit is built so that answer costs
        nothing. If this ever fell to zero it would mean someone had asserted licences
        instead of designing around their absence."""
        not_established = [r for r in self.register
                           if r["outbound_redistribution"] == deposit.NOT_ESTABLISHED]
        self.assertGreater(len(not_established), 50)
        for row in not_established:
            self.assertEqual(row["document_in_deposit"], "no", row["data_file"])


class TestTheShareAlikeTrap(unittest.TestCase):
    """An ODbL input must not become a CC-BY output. LICENSE-data lists the OSM-derived
    databases; the test asserts the list and the register describe the same files rather than
    trusting two documents to have been edited together."""

    # A shipped CSV may carry a `licence` column for two completely different reasons,
    # and conflating them is how 71 ODbL rows nearly shipped under CC-BY. Both halves are
    # published lists so a new case has to be classified rather than defaulted.
    ROW_LICENSED = {
        "data/shared/lookups/facility_registry.csv":
            "the column qualifies each FACILITY: 71 rows are odbl-1.0 OSM derivatives",
        "outputs/pakemis_facility_registry.csv":
            "the published twin of the register above, same column, same 71 rows",
    }
    REGISTERS_ABOUT_OTHER_FILES = {
        "data/catalog/assets.csv":
            "its licence column is this project's redistribution DECISION about each "
            "asset, which is its own work however the asset is licensed",
        "data/catalog/raw_manifest.csv":
            "its licence column records what each RAW DOCUMENT's publisher states; the "
            "manifest row is this project's record of that, not the document",
    }

    def test_a_file_whose_own_rows_carry_licences_does_not_ship_under_one(self):
        """The defect this split exists to prevent, asserted over the shipped manifest.

        Both facility registries carry a `licence` column describing each facility, and
        71 of their 12,680 rows are odbl-1.0 OpenStreetMap derivatives - share-alike this
        project cannot waive. They shipped as plain `own-work` with the reason "this
        project's own code, product or prose", which is precisely the claim the
        limitations section says cannot be made. They must now ship as `mixed-per-row`
        with the per-row counts in the reason.
        """
        rows = {r["path"]: r for r in _rows("pakemis_deposit_manifest.csv")}
        for path, why in self.ROW_LICENSED.items():
            self.assertIn(path, rows, "%s is declared row-licensed and is not in the "
                                      "deposit manifest" % path)
            row = rows[path]
            self.assertEqual(row["outbound_licence"], "mixed-per-row",
                             "%s ships as %r; %s" % (path, row["outbound_licence"], why))
            self.assertIn("odbl", row["licence_reason"].lower(),
                          "%s ships mixed and its reason does not name the share-alike "
                          "rows, so a reader cannot see them" % path)

    def test_every_non_uniform_licence_column_is_classified_one_way_or_the_other(self):
        """The sweep behind the two lists, so a new case cannot default to own-work.

        A shipped CSV with a non-uniform `licence` column is either a register whose
        column describes OTHER artefacts, or a file whose column qualifies its own rows.
        Neither list may grow silently: the first would wrongly keep a single licence,
        the second would wrongly lose one.
        """
        declared = set(self.ROW_LICENSED) | set(self.REGISTERS_ABOUT_OTHER_FILES)
        found = set()
        for row in _rows("pakemis_deposit_manifest.csv"):
            path = row["path"]
            if not path.endswith(".csv"):
                continue
            full = os.path.join(ROOT, path)
            if not os.path.exists(full):
                continue
            with open(full, encoding="utf-8") as handle:
                reader = csv.DictReader(line for line in handle
                                        if not line.startswith("#"))
                columns = [c for c in (reader.fieldnames or [])
                           if c.strip().lower() in ("licence", "license")]
                if not columns:
                    continue
                values = {(r.get(columns[0]) or "").strip() for r in reader}
            if len(values - {""}) > 1:
                found.add(path)
        self.assertEqual(found - declared, set(),
                         "unclassified non-uniform licence column(s) %s: say whether the "
                         "column describes other artefacts (a register) or the file's own "
                         "rows (ships mixed-per-row)" % sorted(found - declared))
        self.assertEqual(declared - found, set(),
                         "declared but no longer non-uniform: %s; a stale allowance hides "
                         "the next one" % sorted(declared - found))

    def test_license_data_names_every_odbl_file_the_register_knows(self):
        text = open(os.path.join(ROOT, "LICENSE-data"), encoding="utf-8").read()
        odbl = [r["data_file"] for r in _rows("pakemis_source_register.csv")
                if "odbl" in (r["outbound_reason"] or "").lower()]
        self.assertGreater(len(odbl), 3, "the register knows of no ODbL files, which would "
                                         "mean the OSM carve-out has silently lapsed")
        for path in odbl:
            self.assertIn(os.path.basename(path), text,
                          "%s is ODbL and LICENSE-data does not name it, so the deposit "
                          "would offer it under CC-BY" % path)

    def test_the_manifest_carveouts_agree_with_license_data(self):
        """rc29 (a FAIR fix): the manifest's licences.odbl_carveouts and the
        LICENSE-data enumeration are two statements of one legal fact, and they had
        drifted - seven paths against eight (pak_landfill_coverage.csv was in the
        text file only). Every file path LICENSE-data names must appear in the
        manifest block, and vice versa."""
        import json
        import re as _re
        manifest = json.load(open(os.path.join(ROOT, "outputs",
                                               "release_manifest.json"),
                                  encoding="utf-8"))
        carveouts = manifest["licences"]["odbl_carveouts"]
        # Each whole-file entry now reads "<published identity> (ships at <path>)",
        # because the two differ and a reader searching the archive for the published
        # identity alone finds nothing. The published identity is what the two documents
        # must agree on; the shipped path is checked separately below.
        carveout_paths, shipped = set(), {}
        for entry in carveouts:
            if "/" not in entry:
                continue
            head = entry.split(" (ships at ")[0]
            if " " in head:
                continue                      # the row-level carve-out, stated in prose
            carveout_paths.add(head)
            if " (ships at " in entry:
                shipped[head] = entry.split(" (ships at ")[1].rstrip(")")
        text = open(os.path.join(ROOT, "LICENSE-data"), encoding="utf-8").read()
        block = text[text.index("OPENSTREETMAP-DERIVED DATABASES"):]
        block = block[:block.index("\n\n", block.index("pak_landfill_assets"))]
        licence_paths = set(_re.findall(r"data/[\w/\.-]+\.\w+", block))
        licence_paths -= set(shipped.values())        # the "ships at" lines
        licence_paths.discard("data/facility_registry.csv")   # the row-level carve-out,
        # named in prose in both files rather than as a whole-file path
        self.assertEqual(sorted(licence_paths), sorted(carveout_paths))
        # And the shipped path must be the one the deposit really uses, since the whole
        # point of printing it is that a reader can find the file.
        deposited = {r["path"] for r in _rows("pakemis_deposit_manifest.csv")}
        self.assertEqual(len(shipped), len(carveout_paths),
                         "a carve-out names no shipped path; the reader is left with a "
                         "published identity that does not appear in the archive")
        for published, path in sorted(shipped.items()):
            self.assertIn(path, deposited,
                          "%s is declared to ship at %s and the deposit manifest has no "
                          "such row" % (published, path))
            self.assertIn(path, text,
                          "LICENSE-data does not give %s's shipped path" % published)

    def test_the_committed_deposit_manifest_matches_a_regeneration(self):
        """The rc29 clean-room rebuild's first substantive catch: four registers were
        edited after the deposit manifest's last regeneration and nothing noticed -
        the committed manifest hashed files that no longer existed in that form.
        Regeneration enumerates the git index, so this runs only in a checkout.
        The release manifest has carried this guard since rc10; the deposit manifest
        never did. Regenerate in memory and compare."""
        release_time_check("the deposit manifest is regenerated at the release fixpoint")
        if not os.path.isdir(os.path.join(ROOT, ".git")):
            self.skipTest("regenerates from the git index; a validation package has none")
        from pkinv.report import deposit_manifest as dm
        committed = _rows("pakemis_deposit_manifest.csv")
        fresh = [{k: str(v) for k, v in row.items()} for row in dm.build_deposit()]
        self.assertEqual(len(committed), len(fresh),
                         "row count drifted: run python3 -m pkinv.report.deposit_manifest")
        for old_row, new_row in zip(committed, fresh):
            self.assertEqual(dict(old_row), new_row,
                             "outputs/pakemis_deposit_manifest.csv is stale against the "
                             "tree at %r: run python3 -m pkinv.report.deposit_manifest"
                             % old_row.get("path", "?"))

    def test_license_data_states_the_share_alike_obligation(self):
        text = open(os.path.join(ROOT, "LICENSE-data"), encoding="utf-8").read().lower()
        self.assertIn("share-alike", text)
        self.assertIn("odbl", text)

    def test_no_odbl_file_is_declared_own_work_in_the_deposit(self):
        odbl = {r["data_file"] for r in _rows("pakemis_source_register.csv")
                if "odbl" in (r["outbound_reason"] or "").lower()}
        for row in _rows("pakemis_deposit_manifest.csv"):
            if row["path"] in odbl:
                self.assertEqual(row["outbound_licence"], deposit.PUBLIC_LICENCE,
                                 "%s is an ODbL database and the deposit declares it %s"
                                 % (row["path"], row["outbound_licence"]))


class TestTheMetadataFilesAgree(unittest.TestCase):
    """Four files state this release's licence position. They drifted once already - the
    attribution in LICENSE-data still named a superseded nowcasting paper - and a reader
    meeting any one of them alone must not be misled."""

    def test_zenodo_describes_what_is_actually_deposited(self):
        with open(os.path.join(ROOT, ".zenodo.json"), encoding="utf-8") as handle:
            record = json.load(handle)
        description = record["description"].lower()
        self.assertRegex(description, r"source (?:documents|publications).*excluded",
                      ".zenodo.json does not tell a depositor that the source documents are "
                      "not in the deposit, which is the single most surprising thing about it")

    def test_license_data_attributes_this_project_and_not_a_superseded_one(self):
        text = open(os.path.join(ROOT, "LICENSE-data"), encoding="utf-8").read()
        self.assertNotIn("nowcasting", text.lower(),
                         "LICENSE-data still attributes the data to the superseded AI/ML "
                         "nowcasting paper rather than to PakEmis-GHG")
        self.assertIn("PakEmis", text)

    # Raised from 500 MB to 750 MB on 2026-10-05, with the reason.
    #
    # The deposit was 499.759 MB and closing the completeness table's universe added
    # 305 KB - a bigger coverage matrix, a longer gap register, a longer claims registry,
    # one new guard file - which put it at 500.064 MB. Nothing third-party moved: the diff
    # against the previous manifest is 1608 -> 1609 files, every changed path a file this
    # project wrote. A bound sitting 0.05 percent above the current size is a tripwire on
    # ordinary work, not a leak detector, and the pressure it creates is to shrink the
    # deposit rather than to look at what grew.
    #
    # The hazard this test NAMES - sources/ creeping back - is already caught directly and
    # exactly by test_the_deposit_excludes_every_source_document above, which fails on any
    # deposit path under sources/. That check does not wait for 3.8 GB to arrive. This one
    # remains as a second net for a leak with some OTHER prefix, and 750 MB still catches
    # that: the three largest single entries are 72.8, 47.9 and 44.4 MB, so an unnoticed
    # bulk import would have to be several of them to pass unremarked.
    # The completed rc68 manifest is 2,198 MB versus 506 MB at rc67 (2,288 versus
    # 1,761 paths). The largest measured increases are the four-configuration
    # ADM2-month semantic fact (+317 MB), native ADM2-month CSV (+250 MB), ADM1-month
    # fact (+121 MB), four 120-month air cubes (+375 MB), and licensed SPAM inputs
    # (+114 MB). These are named release products/inputs, not a sources/ leak.
    # Raw-document exclusion is checked separately; retain 202 MB headroom here.
    DEPOSIT_CEILING_BYTES = 2.4e9

    def test_the_published_deposit_count_matches_the_published_manifest(self):
        """The number the paper prints must be the number of rows in the file it cites.

        WHY THIS EXISTS, and it is a defect in the CASCADE rather than in any one artefact.
        The documented publication order ends with the deposit manifest, for a good reason:
        the manifest hashes everything else, so regenerating it earlier makes it stale. But
        pkinv.report.product_facts COUNTS that manifest to produce the `deposit_files` fact,
        and the limitations section prints that fact and cites the manifest by name. Running
        the manifest last therefore guarantees the fact is computed against the PREVIOUS
        manifest whenever the deposit's contents changed in the same pass.

        The loop that was being checked ran prose -> fact -> prose. The manifest sat outside
        it, so the two could agree with each other and disagree with the file they cite, and
        the claim matrix would report zero disagreements. rc59 shipped exactly that: the
        committed product_facts says 1609 deposit files and the committed manifest lists
        1610 rows, because one new source file (src/pkinv/core/gis/adm2_point.py) entered the
        deposit on the same pass and the count was taken before it did.

        The real order has a cycle in it - the manifest must be built after everything it
        hashes, and the count must be taken after the manifest - which is resolved the same
        way make release-fixpoint resolves the release manifest's: iterate until it settles.
        This test is what makes a non-settled state fail instead of ship.
        """
        rows = _rows("pakemis_deposit_manifest.csv")
        fact = [r for r in _rows("pakemis_product_facts.csv")
                if r["fact_id"] == "deposit_files"]
        self.assertTrue(fact, "pakemis_product_facts.csv has no deposit_files fact")
        self.assertEqual(
            int(fact[0]["value"]), len(rows),
            "the published deposit count (%s, from pakemis_product_facts.csv and printed in "
            "the limitations section) is not the number of rows in "
            "pakemis_deposit_manifest.csv (%d), which that sentence cites by name. Re-run "
            "the deposit manifest, THEN product_facts, THEN the claim matrix and the papers, "
            "and repeat until the count stops moving."
            % (fact[0]["value"], len(rows)))

    def test_the_deposit_is_a_small_fraction_of_the_tree(self):
        """A sanity check with teeth: if the deposit ever approached the size of the
        repository it would mean something bulky had crept into it."""
        total = sum(int(r["bytes"]) for r in _rows("pakemis_deposit_manifest.csv")
                    if r["bytes"])
        self.assertLess(total, self.DEPOSIT_CEILING_BYTES,
                        "the deposit grew to %.0f MB against a %.0f MB ceiling; the tree is "
                        "several GB and this is the shape a leak would take. Before raising "
                        "the ceiling, diff this manifest against the committed one and name "
                        "what grew - the raise above is only defensible because every "
                        "changed path was a file this project wrote"
                        % (total / 1e6, self.DEPOSIT_CEILING_BYTES / 1e6))


class TestTheAllowlistHasNoCatchAll(unittest.TestCase):
    """docs/product_catalog_design.md recorded the ruling for products. It matters more here:
    a catch-all is exactly how an unlicensed third-party file would ship."""

    def test_an_unknown_data_file_raises(self):
        with self.assertRaises(KeyError):
            deposit.data_family("data/somebody_elses_dataset_2026.csv")

    def test_every_family_carries_a_reason(self):
        for pattern, licence, reason in deposit.DATA_FAMILIES:
            self.assertIn(licence, deposit.OUTBOUND_VALUES, pattern)
            self.assertGreater(len(reason), 20, pattern)

    def test_an_unmapped_licence_status_raises(self):
        with self.assertRaises(KeyError):
            deposit.outbound_of({"licence_status": "some-new-licence"})

    def test_every_family_pattern_still_matches_something(self):
        """A pattern matching nothing is a rule about a file that no longer exists, and it
        would go on looking correct forever."""
        release_time_check("the deposit manifest is regenerated at the release fixpoint")
        import fnmatch
        from pkinv.assets import legacy_path
        paths = [legacy_path(r["path"], root=ROOT) for r in _rows("pakemis_deposit_manifest.csv")]
        for pattern, _licence, _reason in deposit.DATA_FAMILIES:
            self.assertTrue(any(fnmatch.fnmatch(p, pattern) for p in paths),
                            "family pattern %r matches no deposited file" % pattern)


class TestCanonicalInputLicensing(unittest.TestCase):
    def test_deposited_recipe_reconstructs_every_canonical_byte_offline(self):
        from pkinv.activity import build
        deposited = {path for _kind, path in deposit.deposit_files()}
        sources = deposit._canonical_source_paths()
        catalog = deposit.storage_path("data/canonical/catalog.json")
        required = deposit.canonical_recipe_inputs()
        self.assertLessEqual(required, deposited)
        self.assertFalse(set(sources) & deposited)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in required:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(Path(ROOT) / relative, target)
            self.assertEqual(set(build.build(root)), set(sources))
            self.assertEqual((root / catalog).read_bytes(), (Path(ROOT) / catalog).read_bytes())
            for relative in sources:
                self.assertEqual((root / relative).read_bytes(), (Path(ROOT) / relative).read_bytes(), relative)
            self.assertEqual(build.build(root, check=True), [])

    def test_every_canonical_copy_retains_its_upstream_licence(self):
        sources = {row["data_file"]: row for row in deposit.source_documents()}
        for canonical, source in deposit._canonical_source_paths().items():
            with self.subTest(path=canonical):
                expected = deposit.licence_of_deposited(source, sources)
                actual = deposit.licence_of_deposited(canonical, sources)
                self.assertEqual(actual[0], expected[0])
                self.assertIn(expected[1], actual[1])
                self.assertIn(source, actual[1])

    def test_canonical_copy_cannot_replace_odbl_with_own_work(self):
        canonical = "data/canonical/fixture.csv"
        source = "data/activity/fixture.csv"
        with patch.object(deposit, "_canonical_source_paths", return_value={canonical: source}):
            licence, reason = deposit.licence_of_deposited(
                canonical, {source: {"licence_status": "odbl"}})
        self.assertEqual(licence, deposit.PUBLIC_LICENCE)
        self.assertIn("odbl", reason.lower())

    def test_metadata_and_verified_crt_extracts_are_explicitly_classified(self):
        for name in ("canonical_tables.csv", "canonical_columns.csv", "canonical_consumers.csv",
                     "download_catalog.json", "canonical/catalog.json"):
            self.assertEqual(deposit.licence_of_deposited("data/" + name, {})[0], deposit.OWN_WORK)
        for path, (licence, reason) in deposit._extract_licences().items():
            self.assertEqual(licence, deposit.OWN_WORK if path.endswith(".json")
                             else deposit.PUBLIC_LICENCE)
            if path.endswith(".csv"):
                self.assertIn("unfccc-public", reason)
        for path in ("data/canonical/undeclared.csv", "data/extracted/unfccc/undeclared.csv",
                     "data/extracted/unfccc/undeclared.json"):
            with self.assertRaises(KeyError):
                deposit.licence_of_deposited(path, {})

    def test_source_hashes_come_from_upstream_inventory_without_document_reads(self):
        digest = "a" * 64
        hashes = {"sources/fixture/a.pdf": digest, "data/unrelated.csv": "b" * 64}
        with patch.object(deposit, "_MANIFEST_HASHES", {}), \
             patch.object(deposit, "_HELD_HASHES", hashes), \
             patch.object(deposit.release_manifest, "DOCUMENT_PATTERNS", ("sources/fixture/*.pdf",)), \
             patch.object(deposit.glob, "glob", side_effect=AssertionError("document tree read")), \
             patch("builtins.open", side_effect=AssertionError("document/release read")):
            self.assertEqual(deposit._document_hash("sources/fixture/a.pdf"), digest)
            self.assertEqual(deposit._document_hash("sources/fixture"),
                             "see release_manifest.json: 1 hashed files under sources/fixture")
            self.assertEqual(deposit._manifest_hashes(), {"sources/fixture/a.pdf": digest})


if __name__ == "__main__":
    unittest.main()

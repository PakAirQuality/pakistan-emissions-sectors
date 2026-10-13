"""The external verification bundle is declared, resolves, and carries results.

WHY. pakemis_verification_external/ hands an outside reviewer ten per-sector zips, and until
this round every one of them was INPUT-SIDE ONLY: the held documents and nothing the sector
concluded from them. It also had no builder - it was assembled by hand and gitignored, so the
bundle was its own registry. Nothing could say whether it still matched the tree, and no test
could fail when it stopped.

WHAT IS ASSERTED. The two halves of the selection, and the shape of what comes out:

  SOURCES   every rule in data/verification_bundle_sources.csv resolves to at least one file
            that exists. A rule that resolves to nothing is a document the bundle promises a
            reviewer and does not ship, which is the failure this file exists for. Drift in the
            COUNT is reported by the builder, not asserted here - a directory legitimately
            gains files - but a rule going empty is always wrong.

  VIEWS     every declared activity view names a file that exists and carries the columns the
            recipe reads. A view whose column was renamed upstream would otherwise fail at
            build time inside a zip nobody opens.

  MAX       is taken WITHIN the partition. The provincial vehicle panels do not end together
            (KP 2024, Punjab 2023, Sindh 2022, Balochistan 2023), and a global max silently
            emptied three provinces out of four - the first build of the fleet view answered
            "the ten highest-fleet districts of Punjab" with no Punjab in it. Asserted on the
            real registry, because that is where it happened.

  OUTPUTS   the derived sector ownership is a PARTITION: no output is claimed by two sectors,
            and every sector claims at least one. Ownership is inferred (the only sector
            package naming the file), so a refactor that moves a writer must not silently
            hand a file to nobody.

Run:  python3 -m unittest discover tests -p "test_verification_bundle.py"
"""

from pkinv.assets import asset_path
import os
import unittest

from _support import DATA, ROOT, data_rows, load_script

build = load_script("build_verification_bundle")


def _skip_outside_a_checkout():
    """The common archive is assembled from `git ls-files`; a built package is not a checkout.

    Absence by DESIGN, not by accident: scripts/build_validation_package.py ships a repo-shaped
    tree without .git, so these tests have nothing to enumerate there. The builder itself now
    raises in that situation rather than shipping outputs/ alone, which is why this is a skip
    here and not a KNOWN_EXCEPTIONS row - the defect it would mask is already guarded.
    """
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        raise unittest.SkipTest(
            "not a git checkout: the common archive is assembled from the tracked tree. "
            "Rebuild it in a checkout with: python3 scripts/build_verification_bundle.py")


def _skip_without_the_source_trees():
    """The bundle's source rules point into sources/ and data/raw/ - 15.8 GB the validation
    package deliberately does not ship (deposit_manifest: outbound rights not established)."""
    missing = [d for d in ("sources", "data/raw") if not os.path.isdir(asset_path(ROOT, d))]
    if missing:
        raise unittest.SkipTest(
            "the held document trees are not present (%s): the validation package ships them as "
            "register rows with digests, never as bytes. Rebuild the bundle in a checkout that "
            "holds them: python3 scripts/build_verification_bundle.py" % ", ".join(missing))


class SourceRules(unittest.TestCase):
    def test_every_rule_resolves_to_something(self):
        _skip_without_the_source_trees()
        empty = []
        for row in data_rows("verification_bundle_sources.csv"):
            if not build.expand(row["rule"], row["kind"]):
                empty.append("%s: %s" % (row["sector"], row["rule"]))
        self.assertEqual([], empty,
                         "these bundle rules resolve to no file - the bundle promises a "
                         "reviewer documents it would not ship:\n  " + "\n  ".join(empty))

    def test_every_sector_has_rules(self):
        declared = {r["sector"] for r in data_rows("verification_bundle_sources.csv")}
        self.assertEqual(set(build.SECTORS), declared)

    def test_kinds_are_the_three_the_builder_implements(self):
        kinds = {r["kind"] for r in data_rows("verification_bundle_sources.csv")}
        self.assertEqual(set(), kinds - {"tree", "directory", "file"})


class ActivityViews(unittest.TestCase):
    def views(self):
        return data_rows("verification_activity_views.csv")

    def test_sources_exist_and_carry_the_columns_the_recipe_reads(self):
        problems = []
        for spec in self.views():
            path = asset_path(ROOT, spec["source_path"])
            if not os.path.isfile(path):
                problems.append("%s: %s does not exist" % (spec["view_id"], spec["source_path"]))
                continue
            rows = build.read_rows(path)
            if not rows:
                problems.append("%s: %s is empty" % (spec["view_id"], spec["source_path"]))
                continue
            held = set(rows[0])
            wanted = set()
            for key in ("filter_column", "partition_by", "group_by", "class_column"):
                if spec.get(key):
                    wanted.add(spec[key])
            if spec["recipe"] == "top_n_wide":
                wanted |= {c.strip() for c in spec["value_columns"].split(";")}
            elif spec["recipe"] == "top_n_pivot":
                wanted.add(spec["value_columns"])
            missing = sorted(wanted - held)
            if missing:
                problems.append("%s: %s has no column %s"
                                % (spec["view_id"], spec["source_path"], ", ".join(missing)))
        self.assertEqual([], problems, "\n  ".join([""] + problems))

    def test_every_top_n_view_declares_what_it_ranks_on(self):
        """rank_by is declared because assuming the sum of the value columns was wrong twice.

        gas_mmcfd + capacity_mw adds MMCFD to megawatts; pop_total + pop_rural + pop_urban
        counts every person twice, because pop_total IS rural plus urban. Both shipped in the
        first build of these views, and both look like a plausible leaderboard.
        """
        for spec in self.views():
            if spec["recipe"] == "table":
                continue
            with self.subTest(view=spec["view_id"]):
                rank_by = spec["rank_by"]
                self.assertTrue(rank_by, "%s ranks on nothing declared" % spec["view_id"])
                if rank_by == "sum":
                    continue
                if spec["recipe"] == "top_n_wide":
                    columns = {c.strip() for c in spec["value_columns"].split(";")}
                    self.assertIn(rank_by, columns,
                                  "%s ranks on a column it does not publish" % spec["view_id"])

    def test_a_group_appears_at_most_once_per_partition(self):
        """top_n_wide aggregates to the group; a district must not hold two of its own ranks."""
        for spec in self.views():
            if spec["recipe"] == "table":
                continue
            with self.subTest(view=spec["view_id"]):
                rows, _fields, problem = build.build_activity(spec)
                self.assertIsNone(problem)
                seen = set()
                for row in rows:
                    key = (row.get(spec["partition_by"], ""), row[spec["group_by"]])
                    self.assertNotIn(key, seen, "%s appears twice in %s" % (key, spec["view_id"]))
                    seen.add(key)

    def test_recipes_are_the_three_the_builder_implements(self):
        recipes = {r["recipe"] for r in self.views()}
        self.assertEqual(set(), recipes - {"table", "top_n_wide", "top_n_pivot"})

    def test_every_sector_publishes_at_least_one_activity_view(self):
        declared = {r["sector"] for r in self.views()}
        self.assertEqual(set(), set(build.SECTORS) - declared)

    def test_every_view_builds_and_is_not_empty(self):
        for spec in self.views():
            with self.subTest(view=spec["view_id"]):
                rows, fields, problem = build.build_activity(spec)
                self.assertIsNone(problem)
                self.assertTrue(rows, "%s built no rows" % spec["view_id"])
                self.assertTrue(fields)

    def test_max_is_taken_within_the_partition_not_across_the_file(self):
        """The defect this guard is named for: one global latest year emptied three provinces.

        The vehicle panels end in different years by province, so a top-N-per-province view
        filtered on a single file-wide max keeps only the province that runs latest.
        """
        spec = [v for v in self.views()
                if v["view_id"] == "registered_fleet_by_class_top_districts"][0]
        self.assertEqual("MAX", spec["filter_value"])
        self.assertEqual("province", spec["partition_by"])
        source = build.read_rows(asset_path(ROOT, spec["source_path"]))
        ends = {}
        for row in source:
            ends[row["province"]] = max(ends.get(row["province"], ""), row["year"])
        self.assertGreater(len(set(ends.values())), 1,
                           "the panels now end together, so this guard no longer bites - "
                           "keep it only while a partition can end early")
        rows, _fields, problem = build.build_activity(spec)
        self.assertIsNone(problem)
        self.assertEqual(set(ends), {r["province"] for r in rows},
                         "a province declared in the panel is missing from the view")
        for row in rows:
            self.assertEqual(ends[row["province"]], row["year"],
                             "%s is not on its own latest year" % row["province"])


class OutputOwnership(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owned, cls.national = build.output_owners()

    def test_ownership_is_a_partition(self):
        seen = {}
        for sector, names in self.owned.items():
            for name in names:
                self.assertNotIn(name, seen,
                                 "%s is claimed by both %s and %s"
                                 % (name, seen.get(name), sector))
                seen[name] = sector

    def test_every_sector_owns_something(self):
        for sector in build.SECTORS:
            with self.subTest(sector=sector):
                self.assertTrue(self.owned.get(sector),
                                "%s owns no output; its writer may have moved" % sector)

    def test_unowned_files_are_reported_not_guessed_at(self):
        """A file no single sector writes is national. It must not land in a sector bundle."""
        for name in self.national:
            for sector in build.SECTORS:
                self.assertNotIn(name, self.owned.get(sector, ()))


class SourceManifest(unittest.TestCase):
    def test_the_registry_join_reproduces_a_known_row(self):
        """The manifest schema the rc47 bundle shipped, rebuilt from the two registries."""
        rows = build.source_manifest(["data/pbs_census/Table_4_District.xls"], build._notes())
        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual(64, len(row["sha256"]))
        self.assertEqual(str(os.path.getsize(
            os.path.join(ROOT, "data/pbs_census/Table_4_District.xls"))), row["bytes"])
        self.assertIn("PBS 7th Agricultural Census 2024", row["raw_manifest_note"])
        self.assertIn(" :: ", row["source_document_note"])


class DepositRights(unittest.TestCase):
    def test_both_registries_have_a_rights_answer(self):
        """data/*.csv in the deposit must resolve to a licence, or build_deposit raises."""
        from pkinv.report import deposit_manifest
        for name in ("verification_bundle_sources.csv", "verification_activity_views.csv"):
            with self.subTest(registry=name):
                self.assertTrue(os.path.exists(asset_path(DATA, name)))
                licence, _reason = deposit_manifest.data_family("data/" + name)
                self.assertTrue(licence)


class TheCommonPart(unittest.TestCase):
    """_common.zip carries the whole release, not the remainder.

    380 files - 222 MB, including 86 CANONICAL products, all four grid cubes, every Monte
    Carlo draw and the claim matrix - were in no archive at all, because the sector rule only
    ever claimed a file one sector's package writes. The first design for this shipped the
    national remainder and asserted a PARTITION with the sector zips; a partition is a property
    that stops holding quietly, and the failure mode is a shipped product nobody can see. So
    the assertion here is the stronger, structural one: every output ships, full stop.
    """

    @classmethod
    def setUpClass(cls):
        _skip_outside_a_checkout()
        cls.members = dict(build.common_members()[0])

    def test_every_output_ships(self):
        missing = [rel for rel in build.outputs_tree()
                   if ("outputs/" + rel[len("outputs/"):]) not in self.members]
        self.assertEqual([], missing,
                         "%d files under outputs/ are in no archive:\n  %s"
                         % (len(missing), "\n  ".join(missing[:20])))

    def test_the_semantic_layer_ships(self):
        """The builder QUERIES outputs/semantic to compute every results/ view; for two rounds
        it shipped the answers and never the layer they came from."""
        semantic = [a for a in self.members if a.startswith("outputs/semantic/")]
        self.assertGreater(len(semantic), 20)
        self.assertIn("outputs/semantic/semantic_release.json", self.members)

    def test_the_code_the_docs_and_the_papers_ship(self):
        for prefix, least in (("code/src/", 100), ("code/tests/", 100), ("code/scripts/", 50),
                              ("docs/", 20), ("papers/", 10), ("validation/", 4), ("data/", 100)):
            with self.subTest(prefix=prefix):
                self.assertGreaterEqual(
                    len([a for a in self.members if a.startswith(prefix)]), least)
        for name in ("code/Makefile", "code/run_all.py", "validation/reproduce.sh",
                     "validation/validate.sh"):
            self.assertIn(name, self.members)

    def test_the_held_document_trees_are_hashed_not_copied(self):
        """data/raw and data/cache are 11 GB and are hash-only in the deposit's own rule.
        A sector archive carries the documents it needs, with a SHA-256 for each."""
        for arc, rel in build.common_members()[0]:
            self.assertFalse(rel.startswith(("data/raw/", "data/cache/", "sources/")),
                             "%s should be hashed, not copied into the common archive" % rel)

    def test_nothing_ships_without_a_redistribution_answer(self):
        """The first build would have shipped 165 MB this project may not republish.

        Three SPAM rice grids, the GHSL built-up tiles, WorldPop, and the MNFSR and NFDC PDFs.
        The licence question is asked of deposit_manifest - the one authority - and a file with
        no answer is withheld, never guessed at.
        """
        deposit, registered = build._rights_answer()
        for _arc, rel in build.common_members()[0]:
            if not rel.startswith("data/"):
                continue
            allowed, _reason = build.may_ship(rel, deposit, registered)
            self.assertTrue(allowed, "%s ships with no redistribution answer" % rel)

    def test_everything_withheld_is_registered_with_a_digest(self):
        """Withheld is not missing: the register is what lets a reviewer re-acquire and check."""
        _members, withheld = build.common_members()
        self.assertTrue(withheld, "nothing withheld - has the licence rule stopped being applied?")
        # the withheld files are third-party bytes; a package that omits them omits these too
        for rel, reason in withheld:
            with self.subTest(rel=rel):
                self.assertTrue(reason)
                self.assertTrue(os.path.isfile(asset_path(ROOT, rel)))


class TheProcessFolder(unittest.TestCase):
    def test_every_declared_process_file_exists(self):
        for rel in build.PROCESS_FILES:
            with self.subTest(rel=rel):
                self.assertTrue(os.path.isfile(asset_path(ROOT, rel)), rel)

    def test_the_process_folder_carries_the_registries_byte_identical(self):
        """A registry shipped as a stale copy would describe a build nobody ran."""
        entries = build.process_entries(build.roles_by_artifact())
        for rel in build.PROCESS_FILES:
            name = "process/" + os.path.basename(rel)
            with self.subTest(rel=rel):
                self.assertIn(name, entries)
                with open(asset_path(ROOT, rel), "rb") as handle:
                    self.assertEqual(handle.read(), entries[name])
        self.assertIn("process/METHOD.md", entries)
        self.assertIn("process/manifest.csv", entries)


if __name__ == "__main__":
    unittest.main()

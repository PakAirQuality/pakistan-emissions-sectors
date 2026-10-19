"""One release, one year, one metric: the shipped tree describes itself.

The inventory's half of the release-integrity suite (rc70): the sector products equal a fresh
build, the README's generated blocks are current, and the committed release manifest describes
the committed content and names a reachable commit. Until rc70 these sat beside the checks on
checks that left this repository with the documents they read.
"""
import json
import os
import sys
import unittest

from _support import release_time_check, require_documents  # noqa: E402

from pkinv import paths
from pkinv.core.io import read_rows

ROOT = paths.ROOT
OUT = paths.OUTPUTS


def _rows(name):
    return read_rows(os.path.join(OUT, name), comments=False)


def _rows_banner(name):
    """Rows of an output that opens with a '#' commentary block."""
    return read_rows(os.path.join(OUT, name))


def _csv_rows(out_name):
    """Every row of one outputs/ CSV, as dicts, with any '#' banner skipped."""
    import csv as _csv
    with open(os.path.join(OUT, out_name), newline="", encoding="utf-8") as handle:
        return list(_csv.DictReader(line for line in handle
                                    if not line.startswith("#")))


def _sector_row(name):
    for r in _rows("national_all_sectors.csv"):
        if r["sector"] == name:
            return r
    raise KeyError(name)


def _sector(name, col="co2e_Mt_AR5"):
    return float(_sector_row(name)[col])


def _sector_alt(name, col="co2e_Mt_AR5"):
    """The same sector under configuration L, the retained alternative (the ledger rollup)."""
    for r in _rows("national_all_sectors_ledger.csv"):
        if r["sector"] == name:
            return float(r[col])
    raise KeyError(name)


def _cell(fname, key_col, key, col):
    """One value from any sector output, matched on a key column."""
    for r in _rows_banner(fname):
        if r[key_col] == key:
            return float(r[col])
    raise KeyError((fname, key))


def _transport_year():
    from pkinv.sectors.transport.data import TransportData
    return TransportData().year


def _waste_year():
    from pkinv.sectors.waste.data import WasteData
    return WasteData().year


def _load_repo_script(name):
    """Import a scripts/*.py generator as a module."""
    import importlib.util
    path = os.path.join(ROOT, "scripts", name)
    spec = importlib.util.spec_from_file_location(name[:-3], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_FRESH_MANIFEST = []
def _fresh_manifest():
    """One fresh release-manifest build per test process (rc69: two tests each built their
    own). Each caller gets a deep copy, because both pop the git block before comparing."""
    import copy
    from pkinv.report import release_manifest
    if not _FRESH_MANIFEST:
        _FRESH_MANIFEST.append(release_manifest.build())
    return copy.deepcopy(_FRESH_MANIFEST[0])
_DIRTY = None
def _tracked_clean(path):
    import subprocess
    run = subprocess.run(["git", "-C", ROOT, "ls-files", "--error-unmatch", "--", path],
                         capture_output=True)
    _edited_at(path)                       # fills _DIRTY
    return run.returncode == 0 and _DIRTY is not None and os.path.normpath(path) not in _DIRTY
def _edited_at(path):
    """When a file last changed: its last COMMIT time when git holds it unmodified, else its
    modification time. A fresh clone stamps every file with the moment of checkout, so
    mtimes there say nothing about which of two committed files was written first (rc69:
    development moved to the public repository, where every reader starts from a clone)."""
    import subprocess
    global _DIRTY
    if _DIRTY is None:
        run = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--untracked-files=all"],
                             capture_output=True, text=True)
        _DIRTY = (None if run.returncode else
                  {os.path.normpath(os.path.join(ROOT, line[3:].split(" -> ")[-1].strip('"')))
                   for line in run.stdout.splitlines()})
    if _DIRTY is not None and os.path.normpath(path) not in _DIRTY:
        run = subprocess.run(["git", "-C", ROOT, "log", "-1", "--format=%ct", "--", path],
                             capture_output=True, text=True)
        if run.returncode == 0 and run.stdout.strip():
            return float(run.stdout.strip())
    return os.path.getmtime(path)


class TestProductCatalogAndHoldings(unittest.TestCase):
    """The catalogued products exist, and the OCAC edition count matches the holdings."""

    def test_every_catalogued_product_has_an_artifact_and_an_anchor(self):
        """Exit criteria 5 and 6 of docs/product_catalog_design.md, for the catalogued slice."""
        from pkinv.report import product_catalog
        self.assertEqual([], product_catalog.missing_artifacts())
        for row in product_catalog.catalog():
            self.assertTrue(row["documentation_anchor"].strip(), row["product_id"])
            self.assertEqual(1, len(row["product_family"].split(";")), row["product_id"])

    def test_ocac_edition_inventory_matches_the_holdings(self):
        """rc18: two true edition counts of two different populations read as a
        contradiction until the inventory distinguished them - and a count that
        drifts from the holdings would re-create it."""
        require_documents("sources/Aviation/ocac_monthly", "data/raw/ocac/monthly_sector_province",
                          "data/raw/ocac/annual_controls", "data/raw/ocac/alternate_uploads")
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import make_ocac_edition_inventory as moi
        committed = {r["kind"]: int(r["count"])
                     for r in _csv_rows("ocac_edition_inventory.csv")}
        fresh = {r["kind"]: r["count"] for r in moi.build()}
        self.assertEqual(committed, fresh)
        self.assertEqual(committed["direct_monthly"], 36)
        self.assertEqual(committed["cumulative_monthly"], 48)


class TestEverySectorShipsWhatItComputes(unittest.TestCase):
    """The staleness guard, for every registered sector rather than two of them.

    Transport once shipped outputs a run behind its own engine - the published text, the
    committed CSVs and the anchors all agreed with each other and disagreed with the code
    by 0.18 Mt, because `make transport` had not been re-run after an edit landed. A
    per-sector version of that check existed for transport and waste only; this is the
    other eight, driven off the registry so a new sector is covered the day it registers.

    Two invariants per sector: the committed totals file equals a fresh in-process build,
    and it equals the national rollup's row for that sector. The second is the cheap
    cross-command check - those two files are written by different commands, so drift
    between them means a partial re-run shipped.

    The first invariant was, until the Round 8 rebuild, running on three sectors of nine.
    It looked for a row labelled TOTAL, six files do not carry one, and the absence was a
    `continue` rather than a failure. A guard whose coverage is decided by a naming
    accident, and which reports the same result either way, is the shape of defect the rest
    of this file exists to catch, so it is worth saying plainly that it was in here too.
    """

    # Sectors whose committed totals file is not named <sector>_totals_<YEAR>.csv, or
    # which do not write one at all. Listed rather than skipped silently.
    #
    # This map used to send fugitives to fugitives_totals_2020.csv, a vintage the build had
    # stopped writing when the sectors were harmonised onto one reporting period. The file
    # was still in outputs/ and still parsed, and it has no TOTAL row, so the check below
    # fell through to `continue` and the fugitives half of this guard did nothing at all -
    # a live test reading a dead artefact and passing. The vintage is retired and the entry
    # with it; NO_TOTAL_ROW now names the fall-through explicitly instead.
    TOTALS_FILE = {}
    # Agriculture's totals live in national_totals_2024.csv rather than an
    # agriculture_totals file; mapping it here brought the sector under the
    # fresh-build check after its products spent a round riding five stale Aug-5
    # artifacts that an exemption by name had made invisible.
    TOTALS_FILE_EXTRA = {"agriculture": "national_totals_2024.csv"}
    # WHICH ROWS ARE THE INVENTORY. Six of the nine totals files carry no row labelled
    # TOTAL, and the check used to read one, so for six sectors it found nothing, hit
    # `continue`, and asserted precisely nothing. It reported passing all the same.
    #
    # Summing the file instead would be wrong in the other direction: these files print the
    # sector's reportable categories BESIDE its sensitivities, diagnostics and excluded
    # memo items - residential's configuration S, railways' road-factor diagnostic,
    # aviation's international LTO - and adding those in double-counts or imports an
    # excluded number. The rows that are the inventory are the ones the registry declares
    # as that sector's reporting categories, so that is what this sums. Nine sectors
    # reconcile on it; a sector that renamed a category without renaming it in the registry
    # would now fail here rather than quietly stop being checked.

    def _sectors(self):
        from pkinv.core import registry
        return registry.all_sectors()

    def test_shipped_sector_totals_equal_a_fresh_build(self):
        problems = []
        for sector in self._sectors():
            # rc15: the fiscal-start sectors' files carry the PERIOD suffix, the
            # rest still carry their (unambiguous, fiscal-end) year - so ask the
            # period module for the name rather than assuming either form.
            from pkinv.core import period as _period
            default = "%s_totals_%s.csv" % (
                sector.NAME, _period.file_suffix(sector.YEAR, sector.YEAR_CONVENTION))
            if not os.path.exists(os.path.join(OUT, default)):
                default = "%s_totals_%d.csv" % (sector.NAME, sector.YEAR)
            fname = self.TOTALS_FILE_EXTRA.get(
                sector.NAME, self.TOTALS_FILE.get(sector.NAME, default))
            path = os.path.join(OUT, fname)
            if not os.path.exists(path):
                problems.append("%s: %s missing" % (sector.NAME, fname))
                continue
            comps = sector.build_components(sector.load_data())
            engine = sum(c["co2e_Mt_AR5"] for c in comps)
            declared = set(sector.CATEGORIES)
            matched = [r for r in _rows(fname)
                       if r.get("category") in declared and r.get("co2e_Mt_AR5")]
            if not matched:
                problems.append("%s: %s carries none of the sector's declared categories "
                                "(%s), so nothing here compares it against the engine"
                                % (sector.NAME, fname, sorted(declared)))
                continue
            shipped = sum(float(r["co2e_Mt_AR5"]) for r in matched)
            # national_totals prints category rows at 2 dp, so its sum can sit up
            # to half an ulp per row from the engine; the sector's own files are
            # written at full precision and keep the tight tolerance.
            tol = 0.02 if sector.NAME in self.TOTALS_FILE_EXTRA else 1e-4
            if abs(shipped - engine) > tol:
                problems.append("%s: shipped %.5f vs engine %.5f - run make %s"
                                % (sector.NAME, shipped, engine, sector.NAME))
        self.assertFalse(problems, "shipped sector outputs are stale:\n  "
                         + "\n  ".join(problems))

    def test_every_sector_matches_the_national_rollup(self):
        problems = []
        for sector in self._sectors():
            comps = sector.build_components(sector.load_data())
            engine = sum(c["co2e_Mt_AR5"] for c in comps)
            rolled = _sector(sector.NAME)
            if abs(rolled - engine) > 1e-4:
                problems.append("%s: rollup %.5f vs engine %.5f - run make national"
                                % (sector.NAME, rolled, engine))
        self.assertFalse(problems, "the national rollup disagrees with the engine:\n  "
                         + "\n  ".join(problems))

    def test_the_two_configurations_differ_only_in_residential(self):
        """S is a residential reading, so every other sector must be identical between
        the two rollups. If another sector moves, the configuration is leaking."""
        for sector in self._sectors():
            if sector.NAME == "residential":
                self.assertNotAlmostEqual(_sector(sector.NAME),
                                          _sector_alt(sector.NAME), places=3)
                continue
            self.assertAlmostEqual(_sector(sector.NAME), _sector_alt(sector.NAME),
                                   places=6, msg=sector.NAME)


class TestReleaseIntegrity(unittest.TestCase):
    """One release, one year set, one metric, one configuration.

    A reviewer found three national totals in simultaneous circulation - 454.48, 461 and
    455.14 - across the README, the national abstract and its results table. None was a
    calculation error; they were three vintages quoted in places nothing read. Every test
    here exists because some artefact was allowed to state a number that no code checked.
    """

    def test_stamped_products_carry_the_current_version(self):
        """The rc10 clean-room run caught the source-stream ledger stamped 1.0.0rc3 and
        the facility registry stamped 1.0.0rc8 inside an rc9 tree: version bumps had
        outrun their writers for six releases and nothing compared the stamp to
        pkinv.__version__. Every shipped product with a release_version column must
        stamp the version it ships in."""
        import pkinv
        for name in ("pakemis_source_streams.csv", "pakemis_facility_registry.csv"):
            rows = _rows(name)
            stamps = {r["release_version"] for r in rows}
            self.assertEqual(stamps, {pkinv.__version__},
                             "%s stamps %s inside a %s tree - its writer was not "
                             "rerun after the version bump"
                             % (name, sorted(stamps), pkinv.__version__))

    def test_the_committed_release_artifacts_claim_a_clean_tree(self):
        """The rc3 release shipped "Commit feb9fac (working tree modified)" as its
        provenance: the manifest was regenerated mid-work and committed as-is, so the
        printed commit did not identify the tree that built the release. The committed
        manifest may never say that. The assertion reads HEAD's
        BLOBS, not the working tree, so the transient dirty state during the
        release-fixpoint dance (scripts/release_fixpoint.py) passes and only COMMITTING
        the defect fails."""
        import subprocess
        try:
            manifest = json.loads(subprocess.check_output(
                ["git", "show", "HEAD:outputs/release_manifest.json"],
                cwd=ROOT, stderr=subprocess.DEVNULL))
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        self.assertFalse(manifest["git"]["tree_dirty"],
                         "the committed manifest was generated on a dirty tree")

    def test_the_commit_the_artifacts_name_is_reachable(self):
        """THE ASSERTION THAT WAS MISSING, and what its absence cost.

        The release dance is content commit, then `make release-fixpoint`, then an
        artifacts-only commit, so the shipped manifest names the CONTENT commit. Recovering
        from a mistake by amending the artifacts commit breaks that: the fixpoint had
        already recorded the pre-amend hash, and the amend left that hash on no branch.
        1.0.0rc59 shipped a manifest naming b719b0170680, which `git branch --contains`
        could not place anywhere - so a reader who cloned the repository could not resolve
        the commit the release prints.

        Every one of the other assertions here passed, because they compare the manifest
        against HEAD's CONTENT by hash and never ask whether the commit it names still
        exists. Reachability from HEAD is the property that was violated, and it holds at
        every stage of the dance, which is why it is the one asserted.
        """
        import subprocess
        try:
            manifest = json.loads(subprocess.check_output(
                ["git", "show", "HEAD:outputs/release_manifest.json"],
                cwd=ROOT, stderr=subprocess.DEVNULL))
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        named = manifest["git"]["describes_commit"]
        reachable = subprocess.run(
            ["git", "merge-base", "--is-ancestor", named, "HEAD"],
            cwd=ROOT, stderr=subprocess.DEVNULL).returncode == 0
        if not reachable:
            # rc69: releases through rc68 were made in the private repository, whose
            # history the restricted layers' checkout holds (pkinv.core.layers); a manifest
            # of one of them names a commit that is reachable THERE.
            from pkinv.core import layers
            _public, overlay = layers.repositories(ROOT)
            if overlay and overlay != _public:
                reachable = subprocess.run(
                    ["git", "-C", overlay, "merge-base", "--is-ancestor", named, "HEAD"],
                    stderr=subprocess.DEVNULL).returncode == 0
            elif not layers.present(ROOT):
                self.skipTest("restricted layers absent: the commit %s is in the private "
                              "history" % named[:12])
        self.assertTrue(reachable,
                        "the committed manifest names %s, which is not an ancestor of HEAD - "
                        "an amended or discarded commit. Re-run make release-fixpoint on the "
                        "clean content commit and commit the artifacts it produces." % named[:12])

    def test_the_committed_manifest_describes_the_committed_content(self):
        """THE ASSERTION NOTHING MADE, and the rc15/rc16 defect is what its absence cost.

        The release declared 1.0.0rc15, commit 53f307c and manifest digest
        706f8e90a2bcea6e while three commits of content had landed behind them: the
        manifest at HEAD was byte-identical to the rc15 artifact, and regenerating it
        moved 191 source hashes and every Monte-Carlo quantile. Four guards were blind at
        once. The manifest test compared the ON-DISK file to a fresh build, but CI
        regenerates the manifest before the tests run, so it compared fresh to fresh;
        release_manifest.json was not in CI's git-diff list; and the commit and digest
        lines were excluded from every regeneration check because they move on every push.
        Between them nothing asked whether the manifest COMMITTED at HEAD
        was generated from HEAD's CONTENT.

        This reads HEAD's blob, like the clean-tree check above, so the transient dirty
        state of the release-fixpoint dance passes and only committing a stale manifest
        fails. The git block itself is dropped: describes_commit is by construction the
        PARENT of the commit carrying the manifest, and tree_dirty is environmental -
        both are covered by the clean-tree assertion instead."""
        release_time_check("the release manifest is regenerated at the release fixpoint")
        import subprocess
        try:
            committed = json.loads(subprocess.check_output(
                ["git", "show", "HEAD:outputs/release_manifest.json"],
                cwd=ROOT, stderr=subprocess.DEVNULL))
            top = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=ROOT,
                                          stderr=subprocess.DEVNULL).decode().strip()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        # rc42: a validation package built inside the repository (dist/) is not a checkout of
        # its own - git walks up to the parent and this compares a vault-less package tree
        # against the release's manifest. Extracted anywhere else the package skips above;
        # inside the repository it must skip for the same reason, not fail by location.
        if os.path.realpath(top) != os.path.realpath(ROOT):
            self.skipTest("this tree is not its own git checkout (a package inside another "
                          "checkout); the committed manifest belongs to the parent")
        fresh = _fresh_manifest()
        committed.pop("git", None)
        fresh.pop("git", None)
        if committed == fresh:
            return
        drift = sorted(k for k in set(committed) | set(fresh)
                       if committed.get(k) != fresh.get(k))
        detail = []
        if "sources" in drift:
            was = {r["path"]: r["sha256"] for r in committed.get("sources", [])}
            now = {r["path"]: r["sha256"] for r in fresh.get("sources", [])}
            added = sorted(set(now) - set(was))
            changed = sorted(p for p in set(was) & set(now) if was[p] != now[p])
            detail.append("sources: %d added, %d re-hashed (%s)"
                          % (len(added), len(changed),
                             "; ".join((added + changed)[:4])))
        self.fail(
            "the committed release manifest does not describe the committed content - "
            "blocks that differ: %s. %s Run: commit your content, then "
            "make release-fixpoint, then commit the regenerated artifacts."
            % (", ".join(drift), " ".join(detail)))

    def test_the_readme_prose_outside_the_generated_blocks_is_current(self):
        """The README may not price an external inventory difference as missing mass."""
        root_readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
        self.assertIn("July 2015–June 2025", root_readme)
        self.assertIn("their residuals are not automatically estimates of missing", root_readme)
        self.assertNotRegex(root_readme, r"roughly \d+ Mt of industrial combustion")
        self.assertIn("S_TAN", root_readme)
        self.assertIn("Native CO2, CH4 and N2O", root_readme)

    def test_readme_generated_blocks_match_a_regeneration(self):
        """The README carried its own vintage for months, including a sector table whose
        rows summed to 448.80 against its own printed total of 454.48. Its numeric blocks
        are generated now, and this is the check that they are current."""
        mod = _load_repo_script("make_readme_tables.py")
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as handle:
            current = handle.read()
        self.assertEqual(current, mod.render(current),
                         "README generated blocks are stale; run "
                         "python3 scripts/make_readme_tables.py")

    def test_the_readme_sector_table_sums_to_its_own_total(self):
        """The defect that made the old table self-evidently wrong, pinned directly."""
        rows = [r for r in _rows("national_all_sectors.csv") if r["sector"] != "TOTAL"]
        total = _sector("TOTAL")
        self.assertAlmostEqual(sum(float(r["co2e_Mt_AR5"]) for r in rows), total, places=4)

    def test_the_release_manifest_regenerates_identically(self):
        """Byte-equality apart from nothing: the manifest carries no timestamp precisely
        so that this test can be exact. If it drifts, an output moved without the release
        record moving with it."""
        release_time_check("the release manifest is regenerated at the release fixpoint")
        import json
        # rc42: the manifest hashes every source document; without the vault the documents
        # block cannot regenerate, so this is a documents-gate test inside a package. The
        # package's own reading layer (data/SOURCE_MANIFEST.csv and the other views under
        # data/) is subtracted from the sources block: it is the package's index, not content.
        from pkinv.core import documents
        require_documents(*sorted(p for p in documents.registered() if p.startswith("sources/")))
        with open(os.path.join(OUT, "release_manifest.json"), encoding="utf-8") as handle:
            shipped = json.load(handle)
        fresh = _fresh_manifest()
        fresh.setdefault("schema", shipped.get("schema"))
        from _support import presentation_layer
        layer = presentation_layer()
        if layer:
            fresh["sources"] = [s for s in fresh["sources"] if s["path"] not in layer]
        # git state is environmental, not a property of the release contents
        for d in (shipped, fresh):
            d.pop("git", None)
        self.assertEqual(shipped, fresh,
                         "release_manifest.json is stale; run "
                         "python3 -m pkinv.report.release_manifest")

    def test_the_manifest_version_is_the_package_version(self):
        import json
        import pkinv
        with open(os.path.join(OUT, "release_manifest.json"), encoding="utf-8") as handle:
            shipped = json.load(handle)
        self.assertEqual(shipped["version"], pkinv.__version__)


class TestShippedTransportOutputsMatchTheEngine(unittest.TestCase):
    """The staleness guard. The August 2026 round found the shipped transport CSVs
    were a run behind the engine - the generator-petrol carve-out had landed in
    road.py but make transport had not been re-run, so the published text, the shipped
    outputs and the anchors agreed with each other and disagreed with the code by
    0.18 Mt. This test builds the sector in-process and compares."""

    def test_shipped_totals_equal_a_fresh_engine_build(self):
        from pkinv.core import registry
        sector = registry.get("transport")
        comps = sector.build_components(sector.load_data())
        by_cat = {}
        for c in comps:
            by_cat[c["category"]] = by_cat.get(c["category"], 0.0) + c["co2e_Mt_AR5"]
        for category, engine_value in by_cat.items():
            shipped = _cell("transport_totals_%d.csv" % _transport_year(), "category", category,
                            "co2e_Mt_AR5")
            self.assertAlmostEqual(
                shipped, engine_value, places=4,
                msg="%s: shipped %.5f vs engine %.5f - outputs are stale, run "
                    "make transport" % (category, shipped, engine_value))
        self.assertAlmostEqual(
            _cell("transport_totals_%d.csv" % _transport_year(), "category", "TOTAL", "co2e_Mt_AR5"),
            sum(by_cat.values()), places=4)

    def test_shipped_totals_equal_the_national_rollup(self):
        """The cheap cross-command invariant: transport_totals and
        national_all_sectors are written by different commands, so drift between
        them means a partial re-run shipped."""
        self.assertAlmostEqual(
            _cell("transport_totals_%d.csv" % _transport_year(), "category", "TOTAL", "co2e_Mt_AR5"),
            _sector("transport"), places=4)
        self.assertAlmostEqual(
            _cell("transport_totals_%d.csv" % _transport_year(), "category", "TOTAL", "co2e_Mt_AR6"),
            _sector("transport", "co2e_Mt_AR6"), places=4)


class TestShippedWasteOutputsMatchTheEngine(unittest.TestCase):
    """The staleness guard, cloned from transport: build the sector in-process
    and compare against the shipped CSVs, so a code change that lands without
    `make waste` fails here rather than shipping stale products."""

    def test_shipped_totals_equal_a_fresh_engine_build(self):
        from pkinv.core import registry
        sector = registry.get("waste")
        comps = sector.build_components(sector.load_data())
        by_cat = {}
        for c in comps:
            by_cat[c["category"]] = by_cat.get(c["category"], 0.0) + c["co2e_Mt_AR5"]
        for category, engine_value in by_cat.items():
            shipped = _cell("waste_totals_%d.csv" % _waste_year(), "category", category,
                            "co2e_Mt_AR5")
            self.assertAlmostEqual(
                shipped, engine_value, places=4,
                msg="%s: shipped %.5f vs engine %.5f - outputs are stale, run "
                    "make waste" % (category, shipped, engine_value))
        self.assertAlmostEqual(
            _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR5"),
            sum(by_cat.values()), places=4)

    def test_shipped_totals_equal_the_national_rollup(self):
        self.assertAlmostEqual(
            _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR5"),
            _sector("waste"), places=4)
        self.assertAlmostEqual(
            _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR6"),
            _sector("waste", "co2e_Mt_AR6"), places=4)


if __name__ == "__main__":
    unittest.main()

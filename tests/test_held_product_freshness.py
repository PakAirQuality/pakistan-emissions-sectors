"""The held registry proves a product is the one that was committed, not that it is current.

WHY THIS TEST EXISTS. outputs/eval/sensitivity.csv drifted 0.02 Mt away from what its
producer would now write, and two cycles of this campaign quoted the stale figure in the
manuscript before a regeneration caught it. Nothing was broken: test_held_products checked
exactly what it claims to, that the file on disk matches the sha256_at_release the registry
records. But that digest was taken FROM the stale file, so the check is a tautology - it
confirms the shipped bytes are the committed bytes and says nothing about whether the
producer still agrees with them.

That is the gap this measures. A held product is, by definition, one no build phase writes,
so nothing regenerates it on a normal build and nothing compares it against its producer.

WHAT THE FIRST VERSION OF THIS TEST GOT WRONG, and why the shape below is different. It
decided which products were verifiable by looking for the substring "--check" in the
registry's verify_command, ran those commands, and ratcheted the rest. Every part of that
was a proxy for the real question:

  - It counted MODES, not COVERAGE. Six commands carried --check; between them they
    compared TWO of the products registered against them. build_road_network.py --check
    diffed the raster, the ADM2 lengths and ROAD_SOURCES.json and returned, while the links
    CSV, the GeoParquet and the ADM2 weights were written further down - all three naming
    that command as their verification.
  - measure_sulfur_adoption_effect.py --check compared len(held) against len(rows) and
    printed "unchanged" whenever they matched, so no change to any VALUE could fail it.
  - build_verification_bundle.py --dry-run is side-effect-free and compares nothing at all;
    the substring filter excluded it by luck rather than by design, and a producer spelling
    its verifying flag --verify would have been excluded the same silent way.

THE MECHANISM behind all three: a check covers what its producer writes BEFORE its early
return, and adding a product below that return extends the write path without extending the
check. ingest_sir_generation.py shows it costing nothing - it returns before write_overlap(),
and power_sir_pbs_overlap.csv honestly records no verify command - which is how the shape was
identified rather than guessed.

THE CONTRACT THIS ENFORCES. A check must NAME what it compared, one
`checked: <repo-relative path>` line per product, and the registry is held to those names: a
row whose verify_command runs a producer that does not print that row's path fails here. A
product added below an early return is then impossible to miss, because the registry claims a
coverage the producer does not announce. The remaining rows - those with no verification at
all - are a ratchet with a written reason.

WHAT THIS DOES NOT DO. It does not re-run the producers that lack a check mode: for most of
them the registry's only instruction IS the producer, which would REWRITE the file rather
than verify it, and several need network access, a GIS extra, an 8.5 GB gitignored bundle or
a commit reachable only through git history. A test that rewrote products as a side effect of
checking them would be worse than the gap it closes. Nor does it prove a comparison is
MEANINGFUL - only that it happened and was declared; that the comparison is against the text
the writer would emit is a discipline held by pkinv.core.io.table_text, the one code path
write_table and write_or_check share.

WHAT WOULD CLOSE IT PROPERLY is a declared check on each producer, cheapest first. That is a
real programme rather than a fix, which is why the count is a ratchet with a written reason
instead of an assertion at zero.
"""
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path                                     # noqa: E402
from pkinv.core.io import read_rows                                     # noqa: E402

REGISTRY = asset_path(ROOT, "data", "held_products.csv")

# THE ONLY THING THIS TEST DISPATCHES ON. verify_mode is a declared, closed vocabulary in
# the registry: "checks" is side-effect-free and comparing, "rewrites" IS the producer, "none"
# is no instruction. Inferring this from the command string is what made the first rewrite of
# this test DANGEROUS: it dropped the "--check" substring filter without adding a declaration,
# ran seven producers, and overwrote four committed files (restored from git - nothing was
# lost, because they were committed). A mode is a fact about a command that only its author
# knows; it must be recorded, never guessed.
MODES = ("checks", "rewrites", "none")
SAFE_MODE = "checks"
# What a check prints, once per product it compared.
COVERED = re.compile(r"^checked:\s*(\S+)\s*$", re.M)

# Measured 2026-09-30 (rc64): 82 of the 95 held products are typed `none`, 7 `rewrites`
# (their command IS the producer, so it can never be run here) and 6 `checks`.
# The ceiling may only FALL. Lowering it means a producer gained a declared check, which is
# the only way this number should ever move.
#
# RAISED TO 83 AT rc60 (2026-10-08), WITH THE REASON THE RATCHET ASKS FOR. The new row is
# research_campaign/energy/plant_fuel_year.csv: the hand transcription of per-station coal
# masses, calorific values and generation out of NEPRA State of Industry Report editions
# that pkinv.sectors.power.fuel_reconciliation reads for the ledger years. It entered the
# registry because the 23rd review's item 2 made the reconciliation declare it as a `held:`
# read, and every `held:` read must name a registry row.
#
# It is typed `none` because NO COMMAND CAN VERIFY IT, not because one was not written. A
# check re-derives a product from its inputs; this file IS an input, read out of PDFs by
# hand, and the only producer that touches it - ingest_nepra_plants.py - is deliberately
# pinned to a single document (SoIR 2024) so that it can reproduce its own output byte for
# byte, which is precisely why the earlier years had to be transcribed separately. Its
# verification is its SHA-256 beside the editions it came from, which the registry carries.
# A `checks` command here would have to be a command that cannot fail, and the first attempt
# at this row did exactly that: it claimed `fuel_reconciliation --check`, which compares the
# PRODUCT against a fresh build of the product and says nothing about this file at all.
#
# LOWERED TO 81 AT rc65 (2026-10-12). The manuscript had to say that "some held validation
# products have only partial re-derivation checks", and a reviewer quoted it. Three hand-run
# validations that carried no instruction at all (the APCMA, FAO crop-calendar and OCAC
# direct-edition cross-checks) now re-derive and compare through pkinv.core.checkmode, and
# three whose "verification" was the producer overwriting them (ERA5 degree days, the
# limestone series, the power TOE ladder) do the same. One row moved the other way, and that
# is a correction: outputs/eval/validation/livestock_validation.json was typed `rewrites`
# with a command that returns before writing, because its input model card exists in no
# commit. It is `none` now, which is what it always was.
NO_CHECK_CEILING = 81
# And of those that do carry one, how many products they are collectively declared to cover.
# This may only RISE: it is the number the first version of this test got wrong by measuring
# modes instead of coverage (it read 6 where the answer was 2, and the fixes below make it 9).
# rc65: 9 -> 21 with the six validation producers (twelve files: the APCMA and OCAC ingests
# each write four, and all four are compared).
MIN_COVERED = 21

# Commands whose check needs something this suite cannot assume: network, a paid or keyed
# service, a GIS extra, a gitignored bundle, or a git ref. Named individually, with the
# reason, so the exemption cannot quietly widen.
SKIP_COMMANDS = {}


def _rows():
    return read_rows(REGISTRY)


def _command(row):
    return (row["verify_command"] or "").strip()


def _mode(row):
    return (row.get("verify_mode") or "").strip()


def _has_command(row):
    """Declared checkable. NOT "the command mentions --check"."""
    return _mode(row) == SAFE_MODE


class TestTheVerifiableSubsetIsVerified(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(REGISTRY):
            raise unittest.SkipTest("the held-product registry is not in this checkout")
        cls.rows = _rows()
        cls.checked = [r for r in cls.rows if _has_command(r)]
        # Each distinct command is RUN ONCE, however many rows name it. The first version ran
        # it once per row, so build_road_network.py --check - a 317 MB shapefile read - ran
        # four times for the four road rows it is registered against.
        cls.by_command = {}
        for r in cls.checked:
            cls.by_command.setdefault(_command(r), []).append(r["path"])
        cls.output = {}
        for cmd in sorted(cls.by_command):
            if cmd in SKIP_COMMANDS:
                continue
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=ROOT,
                                  env=dict(os.environ,
                                           PYTHONPATH=os.path.join(ROOT, "src")))
            cls.output[cmd] = proc

    def test_the_mode_vocabulary_is_closed_and_consistent(self):
        """The column this test dispatches on must mean what it says.

        A row typed "checks" that carries no command, or "none" that carries one, would
        either skip a runnable check or hand this test a producer to execute.
        """
        bad_mode = sorted((r["path"], _mode(r)) for r in self.rows if _mode(r) not in MODES)
        self.assertFalse(bad_mode, "held rows outside the verify_mode vocabulary: %s" % bad_mode)
        no_cmd = sorted(r["path"] for r in self.rows
                        if _mode(r) in ("checks", "rewrites")
                        and (not _command(r) or _command(r).startswith("-")))
        self.assertFalse(
            no_cmd, "these rows declare a verify_mode and carry no command: %s" % no_cmd)
        has_cmd = sorted(r["path"] for r in self.rows
                         if _mode(r) == "none"
                         and _command(r) and not _command(r).startswith("-"))
        self.assertFalse(
            has_cmd,
            "these rows are typed `none` and carry a command, so a real verification is "
            "going unrun - or a producer is one edit away from being executed here: %s"
            % has_cmd)

    def test_no_rewriting_producer_is_ever_run(self):
        """The guard on this test's own blast radius.

        Seven registry rows name their producer as the verification. Running one rewrites
        the product it was meant to verify, and on a clean tree that is indistinguishable
        from a real regeneration. This asserts the dispatch cannot reach them.
        """
        rewriting = {_command(r) for r in self.rows if _mode(r) == "rewrites"}
        self.assertTrue(rewriting, "no row is typed `rewrites` any more; check the registry")
        overlap = sorted(rewriting & set(self.by_command))
        self.assertFalse(
            overlap,
            "this test would EXECUTE these producers, overwriting the very products it "
            "claims to verify: %s" % overlap)

    def test_the_gap_is_measured_and_only_shrinks(self):
        without = sorted({r["path"] for r in self.rows if _mode(r) == "none"})
        self.assertLessEqual(
            len(without), NO_CHECK_CEILING,
            "held products typed `none` rose to %d (ceiling %d). A held "
            "product that no phase writes and no check verifies can go stale silently, "
            "which is what happened to outputs/eval/sensitivity.csv. Give the new product's "
            "producer a declared check rather than raising this.\n  %s"
            % (len(without), NO_CHECK_CEILING, "\n  ".join(without[:10])))

    def test_the_ceiling_is_not_slack(self):
        without = sum(1 for r in self.rows if _mode(r) == "none")
        self.assertGreaterEqual(
            without, NO_CHECK_CEILING - 4,
            "the live count is %d against a ceiling of %d; lower the ceiling so the next "
            "regression is caught" % (without, NO_CHECK_CEILING))

    def test_a_row_without_a_command_still_says_why_it_is_held(self):
        """A sentinel is an admission, not an instruction, so the reason must carry it.

        The first version asserted verify_command was non-blank and passed on "-" for 81 of
        the 95 rows - a guard written against false-passing assertions, false-passing.
        """
        thin = sorted(r["path"] for r in self.rows
                      if _mode(r) == "none"
                      and len((r["reason_held"] or "").strip()) < 30)
        self.assertFalse(
            thin, "held products with neither a verification command nor a reason: %s" % thin)

    def test_the_products_that_can_be_checked_are_current(self):
        """The whole verifiable subset, actually run.

        This is the part that would have caught the sensitivity drift on the cycle it
        happened, had that producer had a check mode.
        """
        self.assertTrue(self.by_command, "no held product declares a verification any more")
        stale = []
        for cmd, proc in sorted(self.output.items()):
            if proc.returncode != 0:
                text = (proc.stdout + proc.stderr).strip()
                stale.append("%s\n      %s"
                             % (cmd, text.splitlines()[-1][:200] if text else "(no output)"))
        self.assertFalse(
            stale,
            "%d held product group(s) no longer reproduce from their producers. A held "
            "product is written by no phase, so nothing else would notice:\n  %s"
            % (len(stale), "\n  ".join(stale)))

    def test_every_registered_row_is_named_by_the_check_it_claims(self):
        """THE COVERAGE CONTRACT, and the defect that made it necessary.

        Three road products named build_road_network.py --check while being written below its
        early return, so the command passed without ever reading them. Registering a
        verification is a claim about a PATH; this holds the producer to announcing it.
        """
        unclaimed = []
        for cmd, paths in sorted(self.by_command.items()):
            proc = self.output.get(cmd)
            if proc is None or proc.returncode != 0:
                continue                      # reported by the test above
            named = set(COVERED.findall(proc.stdout))
            for path in sorted(paths):
                if path not in named:
                    unclaimed.append("%s is registered against `%s`, which named %s"
                                     % (path, cmd,
                                        ", ".join(sorted(named)) if named
                                        else "no product at all"))
        self.assertFalse(
            unclaimed,
            "these held products claim a verification that does not compare them. A check "
            "covers what its producer writes BEFORE its early return; a product added below "
            "it extends the write path and not the check, and the check keeps passing "
            "because it still checks what it always did. Print `checked: <path>` for each "
            "product compared, or set the row's verify_command to the `-` sentinel with the "
            "reason:\n  %s" % "\n  ".join(unclaimed))

    def test_the_declared_coverage_only_grows(self):
        covered = set()
        for cmd, proc in self.output.items():
            covered |= set(COVERED.findall(proc.stdout))
        self.assertGreaterEqual(
            len(covered), MIN_COVERED,
            "the checks collectively compare %d products, below the %d recorded at rc64. "
            "This number measures COVERAGE, not how many commands carry a flag - the "
            "distinction the first version of this test got wrong.\n  %s"
            % (len(covered), MIN_COVERED, "\n  ".join(sorted(covered))))

    def test_the_registry_covers_every_hand_run_makefile_output(self):
        """The other half of the question: is anything hand-run and unregistered?

        Answered for rc64 - every outputs/ path the hand-run modules declare in their
        docstrings is in the registry. This keeps it that way.
        """
        import io
        def _read(path):
            with io.open(path, encoding="utf-8") as handle:
                return handle.read()
        mk = _read(os.path.join(ROOT, "Makefile"))
        ra = _read(os.path.join(ROOT, "src", "pkinv", "run_all.py"))
        phase_targets = set(re.findall(r'Phase\("[^"]*",\s*"([^"]+)"', ra))
        held = {r["path"] for r in self.rows}
        missing = []
        for mod in sorted(set(re.findall(r"python3 -m ([\w.]+)", mk))):
            if mod in phase_targets or mod in ("unittest", "pkinv.build"):
                continue
            path = os.path.join(ROOT, "src", *mod.split(".")) + ".py"
            if not os.path.exists(path):
                continue
            src = _read(path)
            end = src.find('"""', src.find('"""') + 3)
            doc = src[:end] if end > 0 else ""
            for w in sorted(set(re.findall(r"outputs/[\w/.\-]+", doc))):
                w = w.rstrip(".,;")
                # a declared directory or glob prefix is not a product path
                if w.endswith("/") or not os.path.splitext(w)[1]:
                    continue
                if w not in held:
                    missing.append("%s writes %s" % (mod, w))
        self.assertFalse(
            missing,
            "these hand-run Makefile modules declare outputs/ files that no phase writes "
            "and the held registry does not record, so nothing pins them at all:\n  %s"
            % "\n  ".join(missing))


if __name__ == "__main__":
    unittest.main()

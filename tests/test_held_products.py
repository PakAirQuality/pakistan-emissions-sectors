"""rc41: the held products are the ONLY manifest products no build phase writes, and they are named.

The rc40 reproduction copied outputs/ into its working tree and reported 82 of 83 products
identical while 59 of 107 phases had never run. A reproduction from an EMPTY outputs/
directory needs to know exactly which products it may seed, from where, and why. That is
data/held_products.csv, and this module holds it to three facts: every held file exists
with the digest the registry records; no Phase claims to write a held path (one producer
per artefact); and every product the release manifest hashes is EITHER written by some
Phase OR held here - never neither, which is the shape that let the rc40 report lie.
"""

from pkinv.assets import asset_path
import fnmatch
import glob
import hashlib
import os
import unittest

from _support import ROOT, read_rows
from pkinv import run_all
from pkinv.report import release_manifest
from pkinv.core.reporting_window import RETIRED_GHG_PANEL_PRODUCTS
from pkinv.build import DEPOSIT_SOURCE_PHASES
from _support import readable  # noqa: E402

REGISTRY = asset_path(ROOT, "data", "held_products.csv")
# The files scripts/release_fixpoint.py (and the record step after it) write on a clean
# content tree - hashed into the deposit manifest before they exist in their final form,
# so the registry can only ever hold their COMMITTED copies, never a digest.
FIXPOINT_WRITTEN = ("outputs/release_manifest.json", "outputs/pakemis_test_run.json",
                    "outputs/pakemis_paper_hashes.csv", "outputs/SHA256SUMS")


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_products():
    out = set()
    for pattern in release_manifest.PRODUCT_PATTERNS:
        for path in glob.glob(asset_path(ROOT, pattern)):
            rel = os.path.relpath(path, ROOT)
            if rel.endswith(("pakemis_paper_hashes.csv", "pakemis_test_run.json")):
                continue
            if rel in RETIRED_GHG_PANEL_PRODUCTS:
                continue
            out.add(rel)
    return out


class TestTheHeldProductRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(REGISTRY)
        cls.by_path = {r["path"]: r for r in cls.rows}
        cls.held = set(cls.by_path)
        cls.written = set()
        for phase in run_all.PHASES:
            if not phase.prints_only:
                cls.written.update(w.rstrip("/") for w in phase.writes)

    def test_every_held_file_exists_with_its_release_digest(self):
        for r in self.rows:
            if not readable(r["path"]):
                continue   # rc69: a restricted file a clone does not mount
            path = asset_path(ROOT, r["path"])
            self.assertTrue(os.path.exists(path), r["path"])
            if r["sha256_at_release"] == "committed-copy":
                # Only the fixpoint-written files may say this (FIXPOINT_WRITTEN). The
                # deposit manifest hashes the registry and the release manifest hashes the
                # deposit manifest, so a digest of the manifest recorded HERE can never reach
                # a fixpoint (rc41 found out: four manifest-consistency tests failed on the
                # fixpoint tree); the test-run record is written AFTER the fixpoint by
                # design. The seeded copy is the committed one and the release-integrity
                # tests verify both.
                self.assertIn(r["path"], FIXPOINT_WRITTEN, r["path"])
                continue
            self.assertEqual(_sha256(path), r["sha256_at_release"],
                             "%s differs from the digest the registry records; if the product was "
                             "legitimately regenerated, update sha256_at_release in the same commit" % r["path"])

    def test_every_row_says_who_makes_it_and_why_it_is_held(self):
        for r in self.rows:
            self.assertTrue(r["producer"], r["path"])
            self.assertGreater(len(r["reason_held"]), 30, r["path"])
            self.assertIn(r["reproducible_in_package"], ("no", "rewritten", "yes", "network", "hand-run"))

    def test_no_phase_writes_a_held_path(self):
        """One producer per artefact: a held product is held BECAUSE no phase writes it. The
        release manifest is the declared exception - seeded for the prior: read, then
        rewritten by its phase - and its row says so."""
        # The network phase's products are the second declared exception: --quick, the mode
        # a reproduction runs in, skips the FIRMS fetch, so its two tables are seeded from
        # the release (reproducible_in_package = network) and a full run rewrites them.
        network = {w for p in run_all.PHASES if p.network for w in p.writes}
        clash = sorted(p for p in self.held & self.written
                       if p != "outputs/release_manifest.json" and p not in network)
        self.assertEqual(clash, [], "held products that a Phase also declares writing")
        for path in sorted(self.held & network):
            self.assertEqual(self.by_path[path]["reproducible_in_package"], "network", path)

    def test_every_manifest_product_is_written_or_held(self):
        """THE CLOSURE. A manifest product with neither a writing phase nor a registry row is
        a file a reproduction can only copy - and then call identical."""
        products = manifest_products()
        covered = set()
        for rel in products:
            if rel in self.held:
                covered.add(rel)
                continue
            for w in self.written:
                if rel == w or rel.startswith(w + "/") or fnmatch.fnmatch(rel, w):
                    covered.add(rel)
                    break
        orphans = sorted(products - covered)
        self.assertEqual(orphans, [], "manifest products neither written by a phase nor held:\n  "
                         + "\n  ".join(orphans))

    def test_held_reads_in_run_all_name_registry_rows(self):
        """`held:` and `prior:` are different claims and are held to different proofs.

        `held:` says NO phase writes this - so it must be in the held registry, or an
        empty-outputs reproduction has no way to know it must be seeded. `prior:` says a
        phase DOES write it, later, and this reader deliberately takes the previous run's
        copy. Requiring a held-registry row for that would be a false claim (the file is
        not hand-run), and requiring nothing would let a typo through, so the proof is the
        one that makes the word true: some LATER phase must write it.
        """
        writers = {}
        for index, phase in enumerate(run_all.PHASES):
            for write in phase.writes or ():
                writers.setdefault(write.rstrip("/"), []).append((index, phase.label))
        held, prior, held_readers = set(), [], {}
        for index, phase in enumerate(run_all.PHASES):
            for read in phase.reads or ():
                kind, _, path = read.partition(":")
                if kind == "held":
                    held.add(path)
                    held_readers.setdefault(path, set()).add(phase.label)
                elif kind == "prior":
                    prior.append((index, phase.label, path))
        from pkinv.report.deposit_manifest import deposit_files
        software = {p for kind, p in deposit_files() if kind in ("code", "manuscript_source")}
        raw = {r["path"]: r for r in read_rows(os.path.join(ROOT, "data/catalog/raw_manifest.csv"))}
        proven_inputs = set()
        for path in held - self.held:
            if path in software:
                self.assertTrue(os.path.isfile(os.path.join(ROOT, path)), path)
                proven_inputs.add(path)
            elif path in raw and held_readers[path] <= set(DEPOSIT_SOURCE_PHASES):
                # Primary extraction phases are explicitly excluded at compiled-
                # input reproduction level. Their raw sources have independent
                # immutable provenance, not fabricated held-product ownership.
                self.assertEqual(len(raw[path]["sha256"]), 64, path)
                if os.path.isfile(os.path.join(ROOT, path)):
                    self.assertEqual(_sha256(os.path.join(ROOT, path)), raw[path]["sha256"], path)
                proven_inputs.add(path)
        self.assertEqual(held - self.held - proven_inputs, set(),
                         "held: reads lack product ownership, packaged software or declared primary-source provenance")
        wrong = []
        for index, label, path in prior:
            later = [l for i, l in writers.get(path, ()) if i > index]
            if not later and path not in self.held:
                wrong.append("%s reads prior:%s, which no later phase writes" % (label, path))
        self.assertEqual(wrong, [], "a prior: read must name a later phase's output "
                         "(or a held product):\n  " + "\n  ".join(wrong))


if __name__ == "__main__":
    unittest.main()

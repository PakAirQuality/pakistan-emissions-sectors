"""The data provenance audit: every product classed, none unregistered, the orphans frozen by name.

pkinv.report.data_provenance is the data/ counterpart of scripts/audit_outputs.py. What this
asserts is the contract the sector passes rely on: the audit's universe is the git-tracked
data products, every one resolves to a class, nothing is `unregistered` (no producer AND no
source_documents row), and the set of products read by nothing is a NAMED list that may
only shrink - a new orphan fails here instead of joining the shipped tree quietly, and a
retired one is a deliberate edit to this file.

Run:  python3 -m unittest discover tests -p "test_data_provenance_audit.py"
"""

from pkinv.assets import asset_path
import os
import unittest

from _support import OUTPUTS, ROOT, read_rows
from pkinv.report import data_provenance as audit

# Products read by nothing, each with the reason it is still shipped. The list may only
# shrink; a product that leaves it was either given a reader or retired.
ORPHANS = {
    "data/lulucf_transition_ef.csv":
        "the LULUCF exploratory module's transition factors; the module reads its parameter "
        "store instead - a retirement candidate for the agriculture pass",
    "data/validation/livestock_validation.csv":
        "the worksheet eval/validation/livestock_val.py writes beside its JSON metrics; a "
        "product living under data/, kept for the catalog row that names it",
    # rc46 Wave 0: acquisition lands inert BY CONTRACT - the wave's whole point is that
    # acquiring a series and letting it move a number are separate, gated events. Each row
    # below names the wave that wires it, and this list is how the ratchet makes an
    # acquisition that never gets wired VISIBLE instead of quietly forgotten.
    # rc46 Wave 5 consumed the LNG terminal coordinates (facilities:lng_terminals is a
    # live allocation basis now), so their Wave-0 entry left this list the way the
    # ratchet intends: by being wired, not by being forgotten.
}


class TestTheAuditCoversEveryProduct(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(os.path.join(OUTPUTS, "pakemis_data_provenance.csv"))

    def test_the_rows_are_the_universe(self):
        from _support import presentation_layer
        if not os.path.isdir(os.path.join(ROOT, ".git")):
            self.skipTest("the universe is enumerated from the git index; a validation package has none")
        index = presentation_layer()        # a validation package's reading index; empty here
        from _support import readable
        universe = [p for p in audit.universe() if os.path.normpath(p) not in index]
        # rc69: a clone without the restricted layers cannot see their files; it still holds
        # every other row of the shipped audit to the disk
        self.assertEqual([r["data_file"] for r in self.rows if readable(r["data_file"])],
                         [p for p in universe if readable(p)],
                         "the shipped audit and the tracked data products disagree; "
                         "run python3 -m pkinv.report.data_provenance")

    def test_every_class_is_from_the_vocabulary(self):
        allowed = {"producer", "hand:held-source", "hand:derived", "hand:no-source",
                   "hand:parameter", "sidecar", "schema", "unregistered"}
        for r in self.rows:
            self.assertIn(r["class"], allowed, r["data_file"])

    def test_nothing_is_unregistered(self):
        stray = [r["data_file"] for r in self.rows if r["class"] == "unregistered"]
        self.assertFalse(stray, "products with no producer and no source_documents row - "
                                "register or produce them:\n  " + "\n  ".join(stray))

    def test_the_orphans_are_the_named_ones(self):
        from pkinv.assets import legacy_path
        orphans = {legacy_path(r["data_file"], root=ROOT) for r in self.rows
                   if r["orphan"] == "yes" and r["class"] != "sidecar"}
        self.assertEqual(orphans, set(ORPHANS),
                         "read by nothing but not declared: %s; declared but now read: %s"
                         % (sorted(orphans - set(ORPHANS)), sorted(set(ORPHANS) - orphans)))
        for reason in ORPHANS.values():
            self.assertGreater(len(reason), 60)

    def test_every_named_producer_exists(self):
        """A producer string names scripts and modules; each must be a real file."""
        for r in self.rows:
            for token in r["producer"].replace(";", " ").replace("+", " ").split():
                if token.endswith(".py"):
                    self.assertTrue(os.path.exists(asset_path(ROOT, token)),
                                    "%s names producer %s, which does not exist"
                                    % (r["data_file"], token))

    def test_a_no_source_row_names_its_gap(self):
        for r in self.rows:
            if r["class"] == "hand:no-source":
                self.assertTrue(r["gap_id"], "%s has no held source and no gap_id"
                                % r["data_file"])


class TestTheClassifierFailsClosed(unittest.TestCase):
    """The detector, tested against inputs chosen to be nothing."""

    def test_a_product_with_nothing_behind_it_is_unregistered(self):
        self.assertEqual(audit.classify("data/activity/zz/nobody_wrote_this.csv", "", None),
                         "unregistered")

    def test_a_root_table_with_nothing_behind_it_is_a_parameter(self):
        self.assertEqual(audit.classify("data/zz_parameters.csv", "", None), "hand:parameter")

    def test_a_sidecar_is_a_sidecar_whatever_else_is_true(self):
        self.assertEqual(audit.classify("data/gis/x/ZZ_SOURCES.json", "scripts/x.py", None),
                         "sidecar")

    def test_the_register_states_map_to_the_hand_classes(self):
        for state, cls in (("archived", "hand:held-source"), ("derived", "hand:derived"),
                           ("not-archived", "hand:no-source")):
            self.assertEqual(audit.classify("data/activity/zz.csv", "",
                                            {"archival_state": state}), cls)

    def test_a_writes_block_continuation_line_counts(self):
        text = '"""\nWrites: data/manifests/first.csv (one row per x)\n        data/manifests/second.csv\n"""\n'
        self.assertTrue(audit.is_producer("data/manifests/second.csv", ["second\\.csv"], text))
        self.assertFalse(audit.is_producer("data/manifests/third.csv", ["third\\.csv"], text))

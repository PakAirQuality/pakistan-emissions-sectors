"""outputs/ is versioned, so a file outlives the code that wrote it.

scripts/audit_outputs.py is the check; this runs it in the suite so that an orphan or a
superseded vintage fails a commit rather than waiting for someone to run the script. See that
module's docstring for what prompted it: a FY2019-20 fugitives vintage that sat beside the
current one for three rounds, quoting 3.81 Mt against 24.69, with a live test reading it.
"""
import os
import sys
import unittest

from _support import scripts_on_path
scripts_on_path()
import audit_outputs                                                   # noqa: E402


class TestOutputsAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.accounted, cls.orphans, cls.declared = audit_outputs.audit()
        cls.twins = audit_outputs.twins()
        # A validation package's reading index (presentation copies and views under
        # outputs/) is not written by the build and is not an orphan; empty in the repo.
        from _support import presentation_layer
        index = presentation_layer()
        cls.orphans = [o for o in cls.orphans if os.path.normpath(o) not in index]
        cls.twins = [t for t in cls.twins if os.path.normpath(os.path.join("outputs", t[1])) not in index]

    def test_every_output_has_something_that_writes_it(self):
        self.assertFalse(
            self.orphans,
            "outputs/ carries files nothing in this repository writes. Retire them, or "
            "declare them in audit_outputs.KNOWN with the phase that produces them:\n  "
            + "\n  ".join(self.orphans))

    def test_no_superseded_vintage_sits_beside_a_current_one(self):
        self.assertFalse(
            self.twins,
            "a year-variant of a current output is still committed, and no source writes it "
            "by name. That is a second vintage under a plausible name:\n  "
            + "\n  ".join("outputs/%s" % name for _stem, name in self.twins))

    def test_the_audit_is_actually_looking_at_something(self):
        """A sweep that matched nothing would pass both tests above forever.

        rc36: the eval trees left KNOWN_TREES (their writers are in this repository and
        the per-file search finds them), so the declared-exempt count fell from 63 to
        49 and the accounted count rose to 568. The floors follow: fewer files are
        taken on trust and more are matched, which is the direction the audit exists
        to move in."""
        self.assertGreater(len(self.accounted), 500)
        self.assertGreater(len(self.declared), 40)

    def test_a_planted_orphan_would_be_caught(self):
        """The detector, tested. It reads its own tree, so it can be checked against a name
        chosen to appear nowhere - which is the only way to know the match is not vacuous."""
        planted = os.path.join(audit_outputs.OUTPUTS,
                               "zz_audit_selftest_no_generator_writes_this.csv")
        with open(planted, "w", encoding="utf-8") as f:
            f.write("check,value\nself-test,1\n")
        try:
            _accounted, orphans, _declared = audit_outputs.audit()
            self.assertIn(os.path.join("outputs", os.path.basename(planted)), orphans)
        finally:
            os.remove(planted)




class TestFiscalStartSuffixes(unittest.TestCase):
    """rc15 (the tenth review): the fiscal-start sectors' outputs carried bare
    single-year suffixes describing the same twelve months as the _2024 files
    beside them - aviation even shipped BOTH conventions at once. Their outputs
    now carry the period itself (period.file_suffix -> _fy2023_24), and a bare
    single-year suffix on a power/aviation output is banned. Year RANGES
    (_2006_2023 spans) keep their names: a range is not ambiguous."""

    def test_no_bare_year_suffix_on_fiscal_start_outputs(self):
        import os, re
        outputs = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "outputs")
        offenders = []
        for name in sorted(os.listdir(outputs)):
            if not name.startswith(("power_", "aviation_")):
                continue
            if re.search(r"_(?:19|20)\d{2}_(?:19|20)\d{2}\.", name):
                continue    # a span, e.g. _2006_2023
            if re.search(r"_(?:19|20)\d{2}(?:_\d{2})?\.(?:csv|json|png|nc)$", name):
                offenders.append(name)
        self.assertFalse(offenders,
                         "fiscal-start outputs with ambiguous bare-year names "
                         "(rename via period.file_suffix, delete the old file):"
                         "\n  " + "\n  ".join(offenders))

if __name__ == "__main__":
    unittest.main()

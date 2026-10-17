"""Sync paper figures skips the .tex files a build phase writes, and loses nothing by it.

WHY (rc69). The sync collects the PNG names a paper uses from its \\includegraphics lines. It
read every .tex file, including nine generated fragments written by phases that run after it,
so the strict build's order check refused to start: a read of a later phase's product. The
generated fragments now are skipped. That is only safe while none of them names a PNG, which
is what this asserts. The skip covers the phases' declared .tex writes and every file
under a generated/ folder (three supplement tables there are hand-run, kept current by their
own --check tests, and were missed by a declared-writes-only rule).
"""
import importlib.util
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PNG = re.compile(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+\.png)\}")


def _sync_module():
    spec = importlib.util.spec_from_file_location(
        "sync_figures", os.path.join(ROOT, "scripts", "sync_figures.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestGeneratedFragmentsNameNoFigure(unittest.TestCase):
    def test_the_skipped_files_include_no_png(self):
        skipped = _sync_module().generated_tex()
        self.assertTrue(skipped, "no phase writes a .tex file - the skip list is empty")
        for path in sorted(skipped):
            if os.path.exists(path):
                with open(path, encoding="utf-8", errors="replace") as handle:
                    self.assertFalse(PNG.findall(handle.read()),
                                     "%s is generated and includes a PNG; the sync would miss it"
                                     % os.path.relpath(path, ROOT))


if __name__ == "__main__":
    unittest.main()

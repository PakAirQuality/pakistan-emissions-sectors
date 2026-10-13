"""Every CSV under data/ and outputs/ is rectangular and header-first (rc41, D-1).

WHY. Ten committed payloads shipped with an unquoted comma in a note or a source, a
trailing-comma header, or a second table after a blank line; csv.DictReader tolerated all
of them and every reader silently truncated or padded the row. The strict readers now
raise, and this test runs the same rule over every CSV the tree ships - in the repository
and inside the validation package - so a malformed file cannot reach a reader first.
Comment lines start with '#' and may appear anywhere; the first non-comment line is the
header; every data row has exactly the header's field count.
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

from _support import ROOT

TREES = ("data", "outputs")
SKIP = ("data/raw/", "data/cache/")


def _csv_files():
    out = []
    for tree in TREES:
        for folder, _dirs, names in os.walk(asset_path(ROOT, tree)):
            for name in names:
                if not name.endswith(".csv"):
                    continue
                rel = os.path.relpath(os.path.join(folder, name), ROOT).replace(os.sep, "/")
                if rel.startswith(SKIP):
                    continue
                out.append(rel)
    return sorted(out)


class TestEveryCsvIsRectangular(unittest.TestCase):

    def test_every_csv_is_rectangular(self):
        problems = []
        for rel in _csv_files():
            with open(asset_path(ROOT, rel), newline="", encoding="utf-8", errors="replace") as handle:
                lines = [line for line in handle if not line.startswith("#")]
            if not lines or not lines[0].strip():
                continue
            rows = list(csv.reader(lines))
            header = rows[0]
            if header and header[-1] == "":
                problems.append("%s: trailing-comma header" % rel)
            width = len(header)
            for index, row in enumerate(rows[1:], 2):
                if not row:
                    continue
                if len(row) != width:
                    problems.append("%s row %d: %d fields against a %d-column header"
                                    % (rel, index, len(row), width))
                    break
        self.assertEqual(problems, [])

    def test_the_scan_found_the_tree(self):
        self.assertGreater(len(_csv_files()), 300)


if __name__ == "__main__":
    unittest.main()

"""Every documentation_anchor resolves to a label a reader can actually reach.

WHY THIS EXISTS. docs/product_catalog_design.md replaced "every shipped filename must be
cited in the manuscript" with "every core logical product must carry one
documentation_anchor". That is a better rule - it stops the paper reciting filenames - but it
moved the obligation into a field, and the only guard on the field asserted it was non-empty.

On 2026-10-05 eight of the twenty-three anchors resolved to nothing. Four read
`supp:products`, and the supplement has no product table: the table is `tab:products` in
sections/50_data_records.tex, in the MAIN document. Four read `main:spatial`, and no label
ending `:spatial` is reachable from paper_national.tex - the only `sec:spatial` in the tree
belongs to technical_supplement.tex, which neither manuscript inputs. So a third of the
catalog pointed a reader at a place that does not exist, and the mechanism this replaced -
citation coverage - was checked.

THE RULE. An anchor is `<doc>:<suffix>`, where `doc` is `main` (paper_national.tex) or `supp`
(supplement.tex), and `suffix` is what follows the colon in some `\\label{...}` reachable
through that document's `\\input` tree. The suffix rather than the whole label, because the
prefix is a LaTeX convention (sec:, tab:, app:) and the catalog should not have to track
whether its target is a section or a table.

Run:  python3 -m unittest discover tests -p "test_product_catalog_anchors.py"
"""
import csv
import io
import os
from pkinv.paths import PAPER_NATIONAL_MAIN  # noqa: E402
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

PAPER = PAPER_NATIONAL_MAIN
CATALOG = os.path.join(ROOT, "outputs", "pakemis_product_catalog.csv")
DOCUMENTS = {"main": "paper_national.tex", "supp": "supplement.tex"}


def _label_suffixes(main):
    """Every label suffix reachable from one manuscript through its \\input tree."""
    seen, out, stack = set(), set(), [main]
    while stack:
        name = stack.pop()
        path = os.path.join(PAPER, name if name.endswith(".tex") else name + ".tex")
        if path in seen or not os.path.exists(path):
            continue
        seen.add(path)
        text = io.open(path, encoding="utf-8").read()
        text = re.sub(r"(?<!\\)%.*", "", text)
        for label in re.findall(r"\\label\{([^}]+)\}", text):
            out.add(label.split(":", 1)[1] if ":" in label else label)
        for included in re.findall(r"\\input\{([^}]+)\}", text):
            if not included.startswith(".."):
                stack.append(included)
    return out


class TestEveryAnchorResolves(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(CATALOG):
            raise unittest.SkipTest("the product catalog has not been generated here")
        with io.open(CATALOG, encoding="utf-8") as handle:
            lines = [l for l in handle.read().split("\n") if not l.startswith("#")]
        cls.rows = list(csv.DictReader(io.StringIO("\n".join(lines))))
        cls.suffixes = {key: _label_suffixes(main) for key, main in DOCUMENTS.items()}

    def test_the_documents_were_actually_read(self):
        """A walk that found nothing would pass the real test forever."""
        for key, found in self.suffixes.items():
            self.assertGreater(
                len(found), 5,
                "only %d label suffixes reachable from %s; the \\input tree has changed "
                "shape and this guard is resolving against almost nothing"
                % (len(found), DOCUMENTS[key]))

    def test_every_anchor_names_a_known_document(self):
        unknown = sorted({r["documentation_anchor"] for r in self.rows
                          if r["documentation_anchor"].partition(":")[0] not in DOCUMENTS})
        self.assertFalse(unknown,
                         "these anchors name a document this guard cannot resolve (known: "
                         "%s): %s" % (sorted(DOCUMENTS), unknown))

    def test_every_anchor_resolves_to_a_reachable_label(self):
        problems = []
        for row in self.rows:
            anchor = row["documentation_anchor"]
            doc, _, suffix = anchor.partition(":")
            if doc not in DOCUMENTS:
                continue
            if suffix not in self.suffixes[doc]:
                problems.append("%s -> %s (no \\label ending :%s is reachable from %s)"
                                % (row["product_id"], anchor, suffix, DOCUMENTS[doc]))
        self.assertFalse(
            problems,
            "a documentation_anchor points a reader somewhere that does not exist. Either "
            "label the passage that documents the product or point the anchor at the passage "
            "that does - do not leave the field merely non-empty, which is how eight of these "
            "survived several releases:\n  " + "\n  ".join(problems))

    def test_every_core_product_carries_one(self):
        """The design's own rule, kept beside the resolution check."""
        for row in self.rows:
            self.assertTrue(row["documentation_anchor"].strip(),
                            "%s carries no documentation_anchor" % row["product_id"])


if __name__ == "__main__":
    unittest.main()

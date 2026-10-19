"""Every documentation_anchor resolves to a place a reader can actually reach.

WHY THIS EXISTS. docs/product_catalog_design.md replaced "every shipped filename must be
cited" with "every core logical product must carry one documentation_anchor". That is a better
rule, but it moved the obligation into a field, and the only guard on the field asserted it
was non-empty. On 2026-10-05 eight of the twenty-three anchors resolved to nothing: a third of
the catalog pointed a reader at a place that does not exist.

THE RULE (rc70). An anchor is `<file>` or `<file>#<slug>`: a tracked Markdown file in this
repository, and optionally the GitHub slug of one of its headings (lower case, punctuation
dropped, spaces to hyphens), which is the fragment GitHub renders for that heading.

Run:  python3 -m unittest discover tests -p "test_product_catalog_anchors.py"
"""
import csv
import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "outputs", "pakemis_product_catalog.csv")


def slug(heading):
    """GitHub's heading fragment: lower case, punctuation removed, spaces to hyphens."""
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def heading_slugs(path):
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return {slug(m) for m in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", text, flags=re.M)}


class TestEveryAnchorResolves(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(CATALOG):
            raise unittest.SkipTest("the product catalog has not been generated here")
        with io.open(CATALOG, encoding="utf-8") as handle:
            lines = [l for l in handle.read().split("\n") if not l.startswith("#")]
        cls.rows = list(csv.DictReader(io.StringIO("\n".join(lines))))

    def test_the_slug_rule_matches_github(self):
        """A slug function that drifted would pass every anchor or none."""
        self.assertEqual(slug("Reference-year GHG results"), "reference-year-ghg-results")
        self.assertEqual(slug("Coverage and fitness for use"), "coverage-and-fitness-for-use")

    def test_every_anchor_resolves(self):
        problems = []
        for row in self.rows:
            anchor = row["documentation_anchor"]
            path, _, fragment = anchor.partition("#")
            full = os.path.join(ROOT, path)
            if not path.endswith(".md") or not os.path.isfile(full):
                problems.append("%s -> %s (no such Markdown file)" % (row["product_id"], anchor))
            elif fragment and fragment not in heading_slugs(full):
                problems.append("%s -> %s (no heading with that slug in %s)"
                                % (row["product_id"], anchor, path))
        self.assertFalse(
            problems,
            "a documentation_anchor points a reader somewhere that does not exist. Point it at "
            "the heading that documents the product - do not leave the field merely non-empty, "
            "which is how eight of these survived several releases:\n  " + "\n  ".join(problems))

    def test_every_core_product_carries_one(self):
        """The design's own rule, kept beside the resolution check."""
        for row in self.rows:
            self.assertTrue(row["documentation_anchor"].strip(),
                            "%s carries no documentation_anchor" % row["product_id"])


if __name__ == "__main__":
    unittest.main()

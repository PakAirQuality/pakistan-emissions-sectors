"""The v3 technical supplement's product list is generated, so it must match a fresh render.

products_appendix.tex is what makes every canonical product named in a manuscript; a list
left behind by a re-typed or added product would make the citation register's answer depend
on when the file was last written.
"""
import importlib.util
import io
import os
import unittest
from _support import require_built  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _module():
    spec = importlib.util.spec_from_file_location(
        "make_v3_product_list", os.path.join(ROOT, "scripts", "make_v3_product_list.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestTheProductListIsCurrent(unittest.TestCase):
    def test_the_committed_list_matches_a_fresh_render(self):
        require_built()
        module = _module()
        with io.open(module.OUT, encoding="utf-8") as handle:
            current = handle.read()
        self.assertEqual(current, module.render(),
                         "paper_national/versions/v3/products_appendix.tex is stale; run "
                         "python3 scripts/make_v3_product_list.py")


if __name__ == "__main__":
    unittest.main()

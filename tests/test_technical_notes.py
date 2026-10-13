"""The sector manuscripts are Sector Technical Notes TN01-TN10 (v1.0.0), numbered in one place.

src/pkinv/release.py TECHNICAL_NOTES is the registry; every sector paper's \\title carries
its code, calls \\TNBanner with the same code, and no technical note states the national
headline totals as its own result (the generated release cover reproduces them as release
identity and is excluded; one pre-existing statement is listed, ratcheted, not hidden)."""

from pkinv.assets import asset_path
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from pkinv import release  # noqa: E402
from pkinv.core.io import read_rows  # noqa: E402

TITLE = re.compile(r"\\title\{PakEmis Sector Technical Note (TN\d\d)\\\\\[4pt\]")
BANNER = re.compile(r"\\TNBanner\{(TN\d\d)\}")

# Statements of a national-exclusive value in a technical note's own prose that predate the
# exclusivity rule. Ratchet: this list may only shrink. Each is a next-pass prose item.
KNOWN_STATEMENTS = {
    ("agriculture", "national_total_L"): "sections/00_abstract.tex states the sector share against the "
                                        "national total (49.4% of 452.35 Mt); rewrite as a share alone",
}


def _paper_text(sector):
    """The manuscript's own prose: paper.tex and its sections/, without the generated cover."""
    root = os.path.join(ROOT, "papers", sector)
    parts = []
    for folder, _dirs, names in os.walk(root):
        for name in sorted(names):
            if name.endswith(".tex") and "generated" not in name:
                with open(os.path.join(folder, name), encoding="utf-8") as handle:
                    parts.append(handle.read())
    return "\n".join(parts)


class TestTechnicalNotes(unittest.TestCase):
    def test_the_registry_is_ten_contiguous_codes(self):
        codes = sorted(release.TECHNICAL_NOTES.values())
        self.assertEqual(codes, ["TN%02d" % i for i in range(1, 11)])
        self.assertEqual(set(release.TECHNICAL_NOTES), set(release.SECTOR_ORDER) | set(release.RESERVED_TECHNICAL_NOTES))

    def test_every_written_note_carries_its_code_in_title_and_banner(self):
        problems = []
        for sector, code in release.TECHNICAL_NOTES.items():
            path = os.path.join(ROOT, "papers", sector, "paper.tex")
            if sector in release.RESERVED_TECHNICAL_NOTES:
                self.assertFalse(os.path.exists(path), "%s is reserved but papers/%s/paper.tex exists" % (code, sector))
                continue
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            title = TITLE.search(text)
            if not title or title.group(1) != code:
                problems.append("%s: title does not open with 'PakEmis Sector Technical Note %s'" % (sector, code))
            banners = BANNER.findall(text)
            if banners != [code]:
                problems.append("%s: \\TNBanner calls %s, expected exactly [%s]" % (sector, banners, code))
            if "\\input{../../paper_common/tn_banner}" not in text:
                problems.append("%s: does not input paper_common/tn_banner" % sector)
        self.assertFalse(problems, "\n  " + "\n  ".join(problems))

    def test_tn_pdf_names_are_derived_from_the_registry(self):
        self.assertEqual(release.tn_pdf("agriculture"), "PakEmis_TN01_agriculture.pdf")
        self.assertEqual(release.tn_pdf("aviation"), "PakEmis_TN10_aviation.pdf")
        with self.assertRaises(KeyError):
            release.tn_pdf("national")

    def test_no_technical_note_states_a_national_exclusive_value_as_its_own(self):
        """The registry rows allowed ONLY for the national document are national-exclusive.
        A technical note may print them only through the generated release cover."""
        rows = [r for r in read_rows(asset_path(ROOT, "data", "claims_registry.csv"))
                if r["allowed_documents"].strip() == "national" and r["claim_id"].startswith("national_total")]
        self.assertGreaterEqual(len(rows), 2)
        found = {}
        for r in rows:
            value = self._resolved(r)
            printed = "%.*f" % (int(r["rounding"]), value)
            pattern = re.compile(r"(?<![\d.])" + re.escape(printed) + r"(?![\d])")
            for sector in release.SECTOR_ORDER:
                if pattern.search(_paper_text(sector)):
                    found[(sector, r["claim_id"])] = printed
        new = {k: v for k, v in found.items() if k not in KNOWN_STATEMENTS}
        self.assertFalse(new, "technical notes state a national-exclusive value in their own prose: %s" % new)
        stale = {k: v for k, v in KNOWN_STATEMENTS.items() if k not in found}
        self.assertFalse(stale, "KNOWN_STATEMENTS lists statements that no longer exist (remove them): %s" % stale)

    @staticmethod
    def _resolved(row):
        """file.csv#k=v#column, the claims_registry pointer grammar, resolved under outputs/."""
        path, *selectors, column = row["numerator"].split("#")
        rows = read_rows(os.path.join(ROOT, "outputs", path))
        for selector in selectors:
            key, value = selector.split("=", 1)
            rows = [r for r in rows if r[key] == value]
        assert len(rows) == 1, (row["numerator"], len(rows))
        return float(rows[0][column])


if __name__ == "__main__":
    unittest.main()

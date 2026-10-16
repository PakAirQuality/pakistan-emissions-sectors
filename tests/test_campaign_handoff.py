"""The campaign's handoff surface is populated, consistent, and honest about gaps.

research_campaign/ carries six top-level deliverables that the campaign prompt names as
its handoff: a source register, a claim/evidence table, comparison results, a category
completeness view, a product manifest and the final report. At hour 15 five of the six
were HEADERS ONLY - every substantive finding was in DECISIONS.txt and in the products,
and a reader arriving at the named handoff would have found nothing. That is the one
defect in a campaign's own record that good work elsewhere does not repair.

These guards hold the four properties that make the surface worth having:

  it is populated, so the stub state cannot return;
  every claim names a command and a wording location, so a claim with no published home
  is visible rather than inferable;
  every comparison declares its independence class, because a comparison between two
  readings of one source is a transcription check and not a validation;
  the product manifest's digests agree with the release manifest AND with disk, and a
  product the release does not hash says so instead of being dropped.

The report itself is written at the deadline, so its guard only requires that it exists
and names the campaign.
"""
import csv
import hashlib
import json
import os
import unittest
from _support import require_layers  # noqa: E402
from _support import release_time_check  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMPAIGN = os.path.join(ROOT, "research_campaign")


def rows(name):
    path = os.path.join(CAMPAIGN, name)
    with open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheHandoffIsPopulated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # rc69: research_campaign/ is working notes, a restricted layer (pkinv.core.layers)
        require_layers("the research campaign's working notes")

    # Floors, not exact counts: the campaign may add rows and must not lose them.
    FLOORS = {"source_register.csv": 20, "claim_evidence.csv": 10,
              "comparison_results.csv": 25, "completeness.csv": 80}

    def test_no_table_is_a_stub(self):
        for name, floor in sorted(self.FLOORS.items()):
            self.assertGreaterEqual(
                len(rows(name)), floor,
                "research_campaign/%s has fewer than %d rows; the named handoff surface "
                "has gone back to being a header" % (name, floor))

    def test_every_claim_names_a_command_and_a_wording_location(self):
        for row in rows("claim_evidence.csv"):
            for field in ("claim", "scope", "numerical_output", "source", "command",
                          "result_status", "wording_location", "remaining_limitation"):
                self.assertTrue(row[field].strip(),
                                "%s leaves %s empty; an unfalsifiable claim row is worse "
                                "than no row" % (row["claim_id"], field))

    def test_every_comparison_declares_its_independence(self):
        classes = set()
        for row in rows("comparison_results.csv"):
            self.assertTrue(row["independence_class"].strip(),
                            "%s declares no independence class" % row["comparison_id"])
            self.assertTrue(row["interpretation"].strip(),
                            "%s has no interpretation" % row["comparison_id"])
            classes.add(row["independence_class"])
        self.assertGreater(
            len(classes), 1,
            "every comparison carries the same independence class, so the column has "
            "stopped distinguishing a validation from a transcription check")

    def test_every_source_carries_a_locator(self):
        """A source register without locators is a bibliography."""
        for row in rows("source_register.csv"):
            self.assertTrue(row["locator"].strip(),
                            "%s names no page, table, sheet, cell or query"
                            % row["source_id"])
            self.assertTrue(row["used_for"].strip(),
                            "%s does not say what it was used for" % row["source_id"])

    def test_the_product_manifest_agrees_with_the_release_and_with_disk(self):
        release_time_check("the release manifest digests are cut at the release fixpoint")
        with open(os.path.join(CAMPAIGN, "product_manifest.json"),
                  encoding="utf-8") as handle:
            manifest = json.load(handle)
        with open(os.path.join(ROOT, "outputs", "release_manifest.json"),
                  encoding="utf-8") as handle:
            release = json.load(handle)
        hashed = {r["path"]: r["sha256"] for r in release.get("products", [])
                  if r.get("path") and r.get("sha256")}
        self.assertGreaterEqual(len(manifest["products"]), 8)
        for product in manifest["products"]:
            path = product["path"]
            self.assertTrue(product["on_disk"],
                            "%s is declared and not on disk" % path)
            if product["sha256"]:
                self.assertEqual(
                    product["sha256"], hashed.get(path),
                    "%s carries a digest the release manifest does not; the campaign "
                    "manifest must never state one of its own" % path)
                with open(os.path.join(ROOT, path), "rb") as handle:
                    live = hashlib.sha256(handle.read()).hexdigest()
                self.assertEqual(product["sha256"], live,
                                 "%s: the release manifest's digest and the file on disk "
                                 "disagree" % path)
            else:
                self.assertNotIn(path, hashed,
                                 "%s IS hashed by the release manifest and the campaign "
                                 "manifest says it is not" % path)
                self.assertIn("not a release-manifest product", product["hashed_in"],
                              "%s has no digest and no reason" % path)

    def test_every_claims_numbers_appear_in_the_product_it_names(self):
        """"Names a command" is not enough: the command must reproduce the number.

        The earlier guard required each claim to NAME a command and a wording location,
        which a hollow row satisfies. Running the check for real caught one: CE-MIN-001
        quoted the twelve-month profile served for crude oil in FY2021-22 and the product
        published only its maximum, so a reader following the command found one figure of
        the twelve. The screening now publishes the profile, and the twelve are there.

        A claim whose evidence is structural rather than numeric - a count of controls by
        shape, a comparison against a copy this repository does not hold - says so with
        the word STRUCTURAL and is exempt, which keeps the exemption visible in the table
        itself rather than in this file.
        """
        import re
        problems = []
        for row in rows("claim_evidence.csv"):
            product = row["evidence_product"]
            self.assertTrue(product.strip(),
                            "%s names no evidence product" % row["claim_id"])
            if product.startswith("STRUCTURAL"):
                continue
            path = os.path.join(ROOT, product)
            self.assertTrue(os.path.exists(path),
                            "%s names %s, which is not there"
                            % (row["claim_id"], product))
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            # Two or more decimals: a bare integer appears in too many unrelated cells
            # for its presence to mean anything, and every substantive figure this
            # campaign states carries decimals.
            figures = re.findall(r"\d+\.\d{2,}", row["numerical_output"])
            missing = [f for f in figures if f not in text]
            if missing:
                problems.append("%s states %s, which %s does not contain"
                                % (row["claim_id"], ", ".join(missing), product))
        self.assertFalse(problems,
                         "claim(s) whose numbers are not in the product they name:\n  "
                         + "\n  ".join(problems))

    REPRODUCIBLE_STATES = {"yes", "derived-in-this-table", "external-copy",
                           "lane-precision"}

    def test_every_comparison_says_whether_its_figures_can_be_found(self):
        """The same check as for claims, and it flagged 26 of 32 rows for THREE reasons.

        Flattening those into one count would have been as misleading as the silence it
        replaced, so each row declares which it is: `yes` means every figure with two or
        more decimals is in the product it names, and this guard checks those for real;
        `derived-in-this-table` means the row states a difference no product prints, from
        two values that are both published; `external-copy` means it was measured against
        the served release, which this repository does not hold; `lane-precision` means it
        came from a worker lane at the lane's own precision, above what its product
        prints, with the lane's own tables beneath research_campaign/ carrying it.

        Both halves matter. Every state must occur - a vocabulary where one value never
        appears has stopped distinguishing anything - and every `yes` must hold.
        """
        import re
        seen, problems = set(), []
        for row in rows("comparison_results.csv"):
            state = row["figures_reproducible"]
            self.assertIn(state, self.REPRODUCIBLE_STATES,
                          "%s declares reproducibility %r, which is not one of the four"
                          % (row["comparison_id"], state))
            seen.add(state)
            if state != "yes":
                continue
            product = row["source_product"].split(";")[0].strip()
            path = os.path.join(ROOT, product)
            if not os.path.exists(path):
                problems.append("%s names %s, which is not there"
                                % (row["comparison_id"], product))
                continue
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            figures = set(re.findall(r"\d+\.\d{2,}",
                                     " ".join((row["pakemis_value"],
                                               row["comparator_value"],
                                               row["absolute_diff"]))))
            missing = sorted(f for f in figures if f not in text)
            if missing:
                problems.append("%s claims yes and %s lacks %s"
                                % (row["comparison_id"], product, ", ".join(missing)))
        self.assertFalse(problems, "comparison rows that claim reproducibility and are "
                                   "not reproducible:\n  " + "\n  ".join(problems))
        self.assertEqual(self.REPRODUCIBLE_STATES - seen, set(),
                         "reproducibility state(s) %s no longer occur; a vocabulary with "
                         "a dead value has stopped distinguishing anything"
                         % sorted(self.REPRODUCIBLE_STATES - seen))

    def test_no_table_points_at_something_that_is_not_there(self):
        """Every repository path and decision id a handoff row names must resolve.

        A handoff whose references dangle sends a reader nowhere, and this found two of
        its own: two rows named paths in the SERVING repository as bare `data/...`, which
        in this repository read as a path that does not exist. They now say which
        repository they mean.

        Three things the checker must do, each of which it got wrong first: resolve a
        LEGACY path through the asset catalog (data/stream_reporting_sector.csv is a
        published identity that lives under data/shared/lookups/), keep a parenthesised
        filename whole (the FAOSTAT archives end "E_All_Data_(Normalized).zip" and a
        naive scan stops at the bracket), and skip a path a row has explicitly placed in
        another repository rather than reporting it missing.
        """
        import re
        import sys as _sys
        _sys.path.insert(0, os.path.join(ROOT, "src"))
        from pkinv.assets import asset_path
        decisions = open(os.path.join(CAMPAIGN, "DECISIONS.txt"),
                         encoding="utf-8").read()
        known = set(re.findall(r"\bD0\d\d\b", decisions))
        self.assertGreater(len(known), 50, "the decision log has lost its entries")
        pattern = re.compile(r"(?:outputs|data|scripts|tests|src|papers|paper_national|"
                             r"research_campaign)/[\w./*()-]+")
        problems = []
        for name in sorted(self.FLOORS):
            for row in rows(name):
                blob = " ".join(str(v) for v in row.values())
                # URLs first: an API query path like
                # faostatservices.fao.org/api/v1/en/data/GL?area=165 contains "data/GL",
                # which is not a repository path. A checker that reads one as a file
                # reports a defect that is its own.
                blob = re.sub(r"https?://\S+", " ", blob)
                elsewhere = "SERVING REPOSITORY" in blob or "SERVING repository" in blob
                for ref in set(re.findall(r"\bD0\d\d\b", blob)):
                    if ref not in known:
                        problems.append("%s cites %s, which the log does not carry"
                                        % (name, ref))
                for path in set(pattern.findall(blob)):
                    if "*" in path or path.endswith("/") or elsewhere:
                        continue
                    path = path.rstrip(".,;)")
                    if os.path.exists(os.path.join(ROOT, path)):
                        continue
                    try:
                        if os.path.exists(asset_path(ROOT, path)):
                            continue
                    except Exception:
                        pass
                    problems.append("%s names %s, which is not in this repository"
                                    % (name, path))
        self.assertFalse(problems, "dangling handoff reference(s):\n  "
                                   + "\n  ".join(sorted(problems)))

    def test_the_final_report_exists_and_names_the_campaign(self):
        path = os.path.join(CAMPAIGN, "FINAL_REPORT.txt")
        self.assertTrue(os.path.exists(path))
        text = open(path, encoding="utf-8").read()
        self.assertIn("PAKEMIS RESEARCH CAMPAIGN", text)
        self.assertGreater(len(text.strip()), 100,
                           "the final report is shorter than its own heading")


if __name__ == "__main__":
    unittest.main()

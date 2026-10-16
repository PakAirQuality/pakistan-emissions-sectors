"""Can a reader find the figure in the document? Measured, with the denominator guarded.

The product is outputs/pakemis_citation_pointer_audit.csv, built by
scripts/build_citation_pointer_audit.py. It answers the standing reviewer objection that
this release cites DOCUMENTS and not TABLES, and the guards here protect the two things
that make the answer meaningful: the denominator, and the direction of travel.

The denominator matters more than the count. Scoring a file derived inside this
repository, or a satellite product, against a "table pointer" convention it does not have
would inflate the gap with rows no citation could ever close; declaring too much
not-applicable would hide the gap entirely. So both the unpointed count AND the
not-applicable count are ratchets, in opposite directions: the first may only fall, the
second may only fall as well. Widening the exemption to improve the headline is then a
visible edit rather than an improvement.
"""
import csv
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCT = os.path.join(ROOT, "outputs", "pakemis_citation_pointer_audit.csv")
BUILDER = os.path.join(ROOT, "scripts", "build_citation_pointer_audit.py")
VERDICTS = {"pointed", "unpointed", "not-applicable", "unverifiable"}

# Ratchets, both downward. Raised only with a written reason, and the second only
# alongside evidence that a source really cannot carry a table pointer.
#
# rc65 (2026-10-12): UNPOINTED 18 -> 16, NOT-APPLICABLE 80 -> 82, with the reason.
# The retention sweep held documents the register had called absent. Four sources left the
# `unverifiable` verdict by that route and landed on `not-applicable`, each because it is a
# dataset or not a document at all, which is the evidence this ratchet asks for: the GEM oil-
# and-gas workbook (.xlsx), the HydroWASTE archive (.zip) and the Zenodo kiln file (.csv) are
# now held files whose pointer is a file and a column, and hfc_inventory_import_contract.csv
# was found to be the compiler's own request schema (reclassified `derived`; the register had
# called it private correspondence). Two sources went the other way, to `pointed`
# (clinker_trade_annual.csv and population_district.csv), so the exemption grew by two while
# the pointed count rose from 106 to 111 and the unpointed count FELL. Nothing was exempted
# to improve the headline: the four had been scored `unverifiable`, which is not a failure
# the headline counts either.
UNPOINTED_CEILING = 16
# rc68 adds plant_fuel_year_controls.csv, an internally compiled control table.
# Its provenance is the derivation/verified source chain, not a single page
# pointer into an external publication. The other 82 exemptions are unchanged.
NOT_APPLICABLE_CEILING = 83


def rows():
    with open(PRODUCT, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheCitationPointerAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows()

    def test_it_covers_every_registered_source(self):
        """The positive control: the audit's universe is the register, exactly."""
        registered = set()
        with open(os.path.join(ROOT, "data", "catalog", "source_documents.csv"),
                  encoding="utf-8") as handle:
            for row in csv.DictReader(line for line in handle
                                      if not line.startswith("#")):
                registered.add(row["data_file"])
        self.assertEqual({r["data_file"] for r in self.rows}, registered,
                         "the audit and the source register describe different universes")

    def test_the_verdict_vocabulary_is_closed(self):
        seen = {r["verdict"] for r in self.rows}
        self.assertEqual(seen - VERDICTS, set(),
                         "undeclared verdict(s) %s" % sorted(seen - VERDICTS))
        self.assertEqual(VERDICTS - seen, set(),
                         "declared verdict(s) %s no longer occur" % sorted(VERDICTS - seen))

    def test_every_row_gives_its_evidence_or_its_reason(self):
        for row in self.rows:
            self.assertTrue(row["evidence_or_reason"].strip(),
                            "%s states a verdict with nothing behind it" % row["data_file"])
            if row["verdict"] == "pointed":
                self.assertIn(row["pointer_found_in"], ("register", "ingest rows"),
                              "%s is pointed from %r, which is not a place a pointer "
                              "lives" % (row["data_file"], row["pointer_found_in"]))

    def test_the_unpointed_count_has_not_grown(self):
        live = [r for r in self.rows if r["verdict"] == "unpointed"]
        self.assertLessEqual(
            len(live), UNPOINTED_CEILING,
            "sources with no table pointer rose to %d (ceiling %d). Either recover the "
            "pointer from the held document or say in the register why there is none:"
            "\n  %s" % (len(live), UNPOINTED_CEILING,
                        "\n  ".join(sorted(r["data_file"] for r in live))))

    def test_the_exemption_has_not_grown_either(self):
        """The ratchet that stops the headline being improved by exempting things.

        `not-applicable` is the honest answer for a file derived inside this repository
        and for a dataset whose pointer is a variable rather than a table. It is also the
        easiest place to hide a gap, so it is capped from the same direction.
        """
        live = [r for r in self.rows if r["verdict"] == "not-applicable"]
        self.assertLessEqual(
            len(live), NOT_APPLICABLE_CEILING,
            "sources exempted from needing a pointer rose to %d (ceiling %d); a wider "
            "exemption improves the pointed share without citing anything"
            % (len(live), NOT_APPLICABLE_CEILING))

    def test_pointed_rows_say_whether_a_reader_could_check_them_here(self):
        """`pointed` conflated two things until it was measured.

        A pointer is stated in the register whether or not this repository holds the
        document it points into, so the count mixed rows a reader can confirm by opening
        a held file with rows they cannot. 94 of the 104 are checkable here; 6 point into
        documents this project does not archive and 4 into files derived inside it.
        Separating them changes no verdict - a pointer into a document the reader must
        obtain is still a pointer - it only stops the audit's strongest number from
        implying more than it has.

        One was checked to the cell while this column was being added: the bagasse
        generation ingest against NEPRA's held State of Industry Report 2024, where
        Almoiz Industries reads 15.10 / 29.83 / 17.38 / 25.02 / 29.10 GWh in the source
        and the same five values in the ingest.
        """
        states = {}
        for row in self.rows:
            if row["verdict"] != "pointed":
                self.assertEqual(row["pointer_checkable_here"], "n.a.",
                                 "%s is %s and declares checkability"
                                 % (row["data_file"], row["verdict"]))
                continue
            head = row["pointer_checkable_here"].split(":")[0]
            self.assertIn(head, ("yes", "document-not-held", "derived-file"),
                          "%s declares checkability %r"
                          % (row["data_file"], row["pointer_checkable_here"]))
            states[head] = states.get(head, 0) + 1
        self.assertGreaterEqual(states.get("yes", 0), 90,
                                "fewer than 90 pointers are checkable from held "
                                "documents; the audit has lost its strongest rows")
        self.assertEqual(set(states), {"yes", "document-not-held", "derived-file"},
                         "a checkability state has stopped occurring, so the column no "
                         "longer distinguishes anything: %s" % sorted(states))

    def test_the_unfccc_submission_rows_are_pointed(self):
        """Closed from a document already open for another task.

        Both UNFCCC-sourced rows resolve to the held BTR transcription: the aviation
        controls to the International Bunkers block (line 841, with 1A3a1 on 842) and the
        fugitives benchmark controls to the same table. A pointer that costs nothing more
        than naming where you already read is the cheapest kind there is.
        """
        unfccc = [r for r in self.rows if r["publisher"] == "UNFCCC"]
        self.assertGreaterEqual(len(unfccc), 2, "the UNFCCC rows have left scope")
        unpointed = [r["data_file"] for r in unfccc if r["verdict"] == "unpointed"]
        self.assertEqual(unpointed, [],
                         "a UNFCCC-sourced row lost its pointer: %s" % unpointed)

    def test_the_pbs_minerals_family_is_fully_pointed(self):
        """The second batch closed by reading the held editions.

        The eight minerals editions are four PDFs carrying one running-head table
        ('MINERALS PRODUCTION DATA <edition>', 8 / 6 / 10 / 1 pages) and four workbooks
        with no table title at all, where the SHEET is the pointer - and one of them,
        FY2020-21, carries 'Electricity generation' beside 'mineral production', which is
        why the minerals parse and the generation parse read the same workbook for
        different tables.
        """
        pbs = [r for r in self.rows if r["publisher"] == "PBS"
               and "minerals" in r["primary_source"].lower()
               or "pbs_minerals" in r["data_file"]
               or r["data_file"].endswith("coal_production_by_province.csv")]
        self.assertGreaterEqual(len(pbs), 2, "the PBS minerals family has left scope")
        unpointed = [r["data_file"] for r in pbs if r["verdict"] == "unpointed"]
        self.assertEqual(unpointed, [],
                         "a PBS minerals extraction lost its recovered pointer: %s"
                         % unpointed)

    def test_the_ocac_family_is_fully_pointed(self):
        """The batch closed by reading the held PDFs, asserted so it cannot regress.

        Seven OCAC extractions had no pointer anywhere. The documents were held all
        along: each annual edition is two pages and each monthly edition is eighteen,
        nine areas of energy products followed by the same nine of non-energy. The
        pointers are now in the register, and the title drift between FY2019-20 and
        FY2020-21 is recorded with them.
        """
        ocac = [r for r in self.rows if "ocac" in r["data_file"].lower()
                or r["publisher"] == "OCAC"]
        self.assertGreaterEqual(len(ocac), 7, "the OCAC family has shrunk out of scope")
        unpointed = [r["data_file"] for r in ocac if r["verdict"] == "unpointed"]
        self.assertEqual(unpointed, [],
                         "an OCAC extraction lost its recovered pointer: %s" % unpointed)

    def test_it_regenerates_identically(self):
        before = open(PRODUCT, "rb").read()
        run = subprocess.run([sys.executable, BUILDER], cwd=ROOT,
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        self.assertEqual(before, open(PRODUCT, "rb").read(),
                         "the audit does not regenerate byte-identically")


if __name__ == "__main__":
    unittest.main()

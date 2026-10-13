"""The reference-year herd is the census's exact enumeration, and the residual is published.

rc39, pass A1. Until this release the national counts were the census rounded to three
significant figures - cattle 55,800,000 against 55,862,560 - while the district
transcription was exact. The rounding was declared rather than corrected because
correcting it moves the reference totals; an external audit asked for the re-base, so the
exact counts now drive the inventory and the pins moved with them.

Two things this file exists to stop coming back:

  * a rounded count silently replacing an enumeration, and
  * the two transcriptions being reconciled by EDITING one of them. The district sums run
    eight sheep over and eight camels under the national row (cattle and buffalo differ by
    one head each). Neither side is touched: the national table is the emissions control,
    the district table drives the spatial allocation, and the difference is published in
    outputs/agriculture_livestock_reconciliation_2024.csv with the normalisation factor
    the spatial weights carry. rc38 claimed the two agreed "within one head", which was
    true of cattle and buffalo and false of sheep and camels.

Run:  python3 -m unittest discover tests -p "test_livestock_rebase.py"
"""

from pkinv.assets import asset_path
import os
import unittest

from _support import DATA, OUTPUTS, read_rows

# PBS 7th Agricultural Census 2024, Table 6, PAKISTAN row - transcribed in
# data/pbs_census/national.txt and checked cell by cell in data/transcription_checks.csv.
EXACT = {"cattle": 55862560, "buffalo": 47738368, "sheep": 44584926,
         "goats": 95827177, "camels": 1511340}
RUMINANT_TOTAL = 245524371


def _livestock():
    return {r["species"]: r for r in read_rows(
        asset_path(DATA, "activity", "livestock_2024.csv"))}


class TestTheHerdIsTheExactEnumeration(unittest.TestCase):

    def test_every_census_species_is_the_exact_count(self):
        rows = _livestock()
        for species, exact in EXACT.items():
            self.assertEqual(int(rows[species]["head_value"]), exact,
                             "%s is not the census's exact count" % species)
            self.assertEqual(rows[species]["activity_basis"], "census_enumeration")
            self.assertEqual(rows[species]["reference_period"], "FY2023-24")

    def test_the_ruminant_total_is_exact(self):
        rows = _livestock()
        total = sum(int(rows[s]["head_value"]) for s in EXACT)
        self.assertEqual(total, RUMINANT_TOTAL)

    def test_no_count_is_a_three_significant_figure_rounding(self):
        """The shape of the defect, not just its instance: a national head count that is
        an exact multiple of 100,000 is a rounding wearing an enumeration's clothes."""
        rows = _livestock()
        for species in EXACT:
            head = int(rows[species]["head_value"])
            self.assertTrue(head % 100000, "%s = %d looks rounded" % (species, head))

    def test_poultry_is_the_survey_projection_for_the_reference_year(self):
        """Poultry is not enumerated by the census. It carries the Economic Survey's
        FY2023-24 figure - 2.065 billion - and says so; the 2.260 billion in the next
        column is FY2024-25 and is a year ahead of every other row in the file."""
        poultry = _livestock()["poultry"]
        self.assertEqual(int(poultry["head_value"]), 2065000000)
        self.assertEqual(poultry["activity_basis"], "economic_survey_projection")
        self.assertEqual(poultry["reference_period"], "FY2023-24")
        self.assertEqual(int(poultry["head_following_year"]), 2260000000)

    def test_the_loader_respects_the_declared_basis(self):
        from pkinv.sectors.agriculture.ef_library import InventoryData
        data = InventoryData()
        self.assertEqual(data.livestock["cattle"]["activity_basis"], "census_enumeration")
        self.assertEqual(data.livestock["poultry"]["activity_basis"],
                         "economic_survey_projection")
        for species, exact in EXACT.items():
            self.assertEqual(int(data.livestock[species]["head"]), exact)

    def test_an_undeclared_basis_is_refused(self):
        """The loader used to take whichever column was filled, which made the basis a
        label nobody enforced."""
        from pkinv.sectors.agriculture import ef_library
        rows = [{"species": "zz", "head_value": "1", "reference_period": "FY2023-24",
                 "activity_basis": "vibes", "source_document_id": "x",
                 "ad_uncert_pct": "10", "head_following_year": "", "source": "", "note": ""}]
        with self.assertRaises(ValueError):
            basis = rows[0]["activity_basis"]
            if basis not in ("census_enumeration", "economic_survey_projection"):
                raise ValueError(basis)


class TestTheReconciliationIsPublished(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = {r["species"]: r for r in read_rows(
            os.path.join(OUTPUTS, "agriculture_livestock_reconciliation_2024.csv"))}

    def test_every_census_species_has_a_row(self):
        self.assertEqual(set(self.rows), set(EXACT))

    def test_the_national_control_is_the_exact_count(self):
        for species, exact in EXACT.items():
            self.assertEqual(int(self.rows[species]["national_control_head"]), exact)

    def test_the_known_residuals_are_the_published_ones(self):
        """national minus district: the district table carries eight MORE sheep and eight
        FEWER camels than the national row."""
        self.assertEqual(int(self.rows["sheep"]["residual_head"]), -8)
        self.assertEqual(int(self.rows["camels"]["residual_head"]), 8)
        self.assertEqual(int(self.rows["goats"]["residual_head"]), 0)
        for species in ("cattle", "buffalo"):
            self.assertEqual(abs(int(self.rows[species]["residual_head"])), 1)

    def test_the_normalisation_factor_closes_the_district_sum_to_the_control(self):
        """What the spatial weights actually carry: district sum x factor = national."""
        for species in EXACT:
            row = self.rows[species]
            dsum = int(row["district_sum_head"])
            factor = float(row["spatial_normalisation_factor"])
            self.assertAlmostEqual(dsum * factor, float(row["national_control_head"]),
                                   places=3, msg=species)

    def test_no_claim_that_the_two_agree_within_one_head(self):
        """rc38 said so in the source register and in the capsule manifest. Sheep and
        camels are out by eight, so the claim was false and may not return."""
        import glob
        offenders = []
        for pattern in ("scripts/*.py", "src/pkinv/**/*.py", "papers/**/*.tex",
                        "data/*.csv", "docs/*.md"):
            for path in glob.glob(os.path.join(os.path.dirname(DATA), pattern),
                                  recursive=True):
                with open(path, encoding="utf-8", errors="replace") as handle:
                    text = handle.read()
                if "within one head" in text:
                    offenders.append(os.path.relpath(path, os.path.dirname(DATA)))
        self.assertFalse(offenders, "the retired 'within one head' claim survives in: %s"
                                    % sorted(set(offenders)))


class TestTheRawDistrictTranscriptionHasNoFalseHeader(unittest.TestCase):
    """rc40: data/pbs_census/livestock_by_district_2024.csv carried the PDF's column numbers
    as its second row - a district named "1" with 3 cattle, 4 buffalo and so on. Read by no
    engine consumer, so it moved no number; but a raw transcription that contains a row of
    numbers that are not data is a transcription a reader cannot trust by inspection."""

    def test_no_district_name_is_a_bare_integer(self):
        import csv
        from pkinv.paths import ROOT
        path = asset_path(ROOT, "data", "pbs_census", "livestock_by_district_2024.csv")
        with open(path, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        bad = [r for r in rows if r["name"].strip().isdigit()]
        self.assertFalse(bad, "rows whose name is a number: %s" % bad[:2])
        self.assertGreater(len(rows), 100)


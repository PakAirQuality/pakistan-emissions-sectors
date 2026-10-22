"""The evidence returned to the contribution-evidence handoff is what its documents print.

Three tables went into the public tree on 21 October 2026 (docs/contribution_evidence_returned.md):
- data/sectors/residential/evidence/hies/hies_dung_definitions.csv, from the HIES 2024-25
  questionnaire and manual;
- data/sectors/residential/evidence/cookstove_efficiency_evidence.csv, from the World Bank 2024
  Pakistan Energy Survey, Jetter et al. 2012 and Shen et al. 2017;
- data/sectors/agriculture/evidence/faostat_manure_nitrogen.csv, written from the held FAOSTAT
  Livestock Manure bulk by scripts/ingest_faostat_manure_nitrogen.py.
A second brief (22 October) added Pakistani stove rows, and three more agriculture tables:
- ipcc2006_indian_subcontinent_mms.csv, the IPCC 2006 default manure-system shares FAOSTAT applies to
  Pakistan's cattle and buffalo; FAOSTAT's pools are rebuilt from them here;
- faostat_crops_nitrogen.csv (scripts/ingest_faostat_crops_nitrogen.py);
- faostat_versions.csv (scripts/ingest_faostat_versions.py), each held FAOSTAT bulk against the catalogue.

The two transcriptions carry a short phrase per row copied from the document. A transcription is
only as good as the page it cites, so with the restricted layers mounted every phrase is looked
for ON THAT PAGE of the held bytes, not anywhere in the document. Without the layers the tables
are still checked for shape, and the FAOSTAT extract for the identities FAOSTAT's own pools obey.
"""
import html
import math
import os
import re
import shutil
import subprocess
import unittest

from _support import DATA, ROOT, load_script, read_rows, require_layers

HIES = os.path.join(DATA, "sectors", "residential", "evidence", "hies", "hies_dung_definitions.csv")
STOVES = os.path.join(DATA, "sectors", "residential", "evidence", "cookstove_efficiency_evidence.csv")
MANURE = os.path.join(DATA, "sectors", "agriculture", "evidence", "faostat_manure_nitrogen.csv")
MMS = os.path.join(DATA, "sectors", "agriculture", "evidence", "ipcc2006_indian_subcontinent_mms.csv")
CROPS = os.path.join(DATA, "sectors", "agriculture", "evidence", "faostat_crops_nitrogen.csv")
VERSIONS = os.path.join(DATA, "sectors", "agriculture", "evidence", "faostat_versions.csv")

# document key -> (held path, PDF page = printed page + offset); None offset = a web page
DOCUMENTS = {
    "questionnaire": ("sources/HIES/Male-Questionnaire-HIES-2024-25-English.pdf", 0),
    "manual": ("sources/HIES/Manual-of-Instruction-HIES-2024-25.pdf", 1),
    "wb2024": ("sources/Papers/worldbank_2024_pakistan_energy_survey.pdf", 22),
    "jetter2012": ("data/raw/literature/jetter_2012_est_cookstove_emissions_efficiency.pdf", 1),
    "shen2017": ("data/raw/literature/shen_2017_energy_fuels_pmc6145494.html", None),
    "aneeq2022": ("data/raw/literature/aneeq_mahmood_2022_hsd_v4i1_73.pdf", 0),
    "usman2023": ("data/raw/literature/usman_2023_eds_s10668_022_02273_y_landing.html", None),
    # printed pages are '10.77'-style: the PDF page is the part after the chapter number
    "ipcc2006v4ch10": ("sources/IPCC/ipcc2006_v4_ch10_livestock.pdf", "chapter"),
}


def _norm(text):
    # pdftotext breaks lines inside a phrase and renders some ligatures as control bytes
    return re.sub(r"[\s\x00-\x1f]", "", text).lower()


def _page_texts(path, page):
    """The cited page as pdftotext reads it, in reading order and in layout order."""
    out = []
    for flags in ([], ["-layout"]):
        out.append(subprocess.run(["pdftotext", "-q", "-f", str(page), "-l", str(page)] + flags + [path, "-"],
                                  capture_output=True, text=True, check=True).stdout)
    return out


class TestTheTranscriptionsAreWellFormed(unittest.TestCase):

    def test_every_hies_row_cites_a_held_document_and_page(self):
        rows = read_rows(HIES)
        self.assertGreaterEqual(len(rows), 15)
        for r in rows:
            self.assertIn(r["document"], ("questionnaire", "manual"), r)
            self.assertTrue(r["page"].isdigit(), r)
            self.assertTrue(r["quote"].strip() and r["reading"].strip(), r)
        self.assertIn("045404", {r["code"] for r in rows})

    def test_every_stove_row_cites_a_source_and_a_value(self):
        rows = read_rows(STOVES)
        for r in rows:
            self.assertIn(r["source"], ("wb2024", "jetter2012", "shen2017", "aneeq2022", "usman2023"), r)
            self.assertTrue(r["page"].isdigit() or (DOCUMENTS[r["source"]][1] is None and r["page"] == "html"), r)
            self.assertTrue(r["quote"].strip() and r["value"].strip(), r)
        efficiencies = [r for r in rows if r["record_kind"] == "efficiency"]
        # the gap the table records: no laboratory row is a dung fuel, and the survey measured none
        self.assertTrue(efficiencies)
        self.assertFalse([r for r in efficiencies if "dung" in r["stove_or_fuel"].lower()])
        self.assertIn("not collected", {r["value"] for r in rows if r["source"] == "wb2024"})


class TestTheQuotesAreOnTheCitedPage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        require_layers("the HIES documents, the World Bank survey and the two stove papers")
        if not shutil.which("pdftotext"):
            raise unittest.SkipTest("pdftotext (poppler-utils) is not installed")

    def _check(self, rows, key):
        for r in rows:
            path, offset = DOCUMENTS[r[key]]
            path = os.path.join(ROOT, path)
            with self.subTest(document=r[key], page=r["page"], quote=r["quote"]):
                if offset is None:
                    with open(path, encoding="utf-8", errors="replace") as handle:
                        texts = [html.unescape(re.sub(r"<[^>]+>", " ", handle.read()))]
                elif offset == "chapter":
                    texts = _page_texts(path, int(r["page"].split(".")[1]))
                else:
                    texts = _page_texts(path, int(r["page"]) + offset)
                self.assertTrue(any(_norm(r["quote"]) in _norm(t) for t in texts),
                                "%s p.%s does not print %r" % (r[key], r["page"], r["quote"]))

    def test_every_hies_quote(self):
        self._check(read_rows(HIES), "document")

    def test_every_stove_quote(self):
        self._check(read_rows(STOVES), "source")

    def test_every_ipcc_row_quote(self):
        rows = [dict(r, source="ipcc2006v4ch10") for r in read_rows(MMS)]
        self._check(rows, "source")

    def test_a_quote_on_the_wrong_page_is_caught(self):
        path, offset = DOCUMENTS["questionnaire"]
        texts = _page_texts(os.path.join(ROOT, path), 11 + offset)
        self.assertFalse(any(_norm("Dung cake (dry)") in _norm(t) for t in texts))


class TestTheFaostatManureExtract(unittest.TestCase):
    """FAOSTAT's pools, as published, obey FAOSTAT's own arithmetic in every year and item."""

    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(MANURE)
        cls.value = {(r["item_code"], r["year"], r["element_code"]): float(r["value"]) for r in cls.rows}

    def test_pakistan_only_and_the_inventory_years(self):
        self.assertEqual({r["area"] for r in self.rows}, {"Pakistan"})
        years = {int(r["year"]) for r in self.rows}
        self.assertEqual(min(years), 2015)
        self.assertEqual({r["unit"] for r in self.rows if r["element_code"] != "5111"}, {"kg"})

    def test_applied_is_treated_less_losses(self):
        for (item, year, element), treated in self.value.items():
            if element != "72386":
                continue
            applied = self.value[(item, year, "72381")]
            losses = self.value[(item, year, "72539")]
            with self.subTest(item=item, year=year):
                self.assertTrue(math.isclose(applied, treated - losses, rel_tol=1e-6, abs_tol=1.0))

    def test_excretion_is_not_all_assigned_and_the_remainder_is_bounded(self):
        """The N in neither pool is half the N in manure burned for fuel (the EMN methodological note
        books the other half as pasture): 14-15% nationally."""
        for year in sorted({r["year"] for r in self.rows}):
            excreted = self.value[("1755", year, "72538")]
            rest = excreted - self.value[("1755", year, "72386")] - self.value[("1755", year, "72380")]
            with self.subTest(year=year):
                self.assertTrue(0.13 < rest / excreted < 0.16, rest / excreted)

    def test_the_extract_reproduces_from_the_held_bulk(self):
        require_layers("the FAOSTAT Livestock Manure bulk")
        self.assertEqual(load_script("ingest_faostat_manure_nitrogen").main(["--check"]), 0)



class TestFaostatPoolsFollowTheIpccDefaults(unittest.TestCase):
    """FAOSTAT's Pakistan cattle and buffalo pools are IPCC 2006's Indian-subcontinent shares.

    The EMN methodological note: pasture N = excreted N x (PRP share + half the burned-for-fuel share);
    treated N = excreted N x the other systems' shares. The table rows sum to 99-101% as printed, so the
    shares are matched to the printed rounding, 0.006."""

    SPECIES = {"dairy cows": "960", "other cattle": "961", "buffalo": "946"}
    TREATED = ("lagoon", "liquid_slurry", "solid_storage", "drylot", "daily_spread", "digester", "other")

    def test_pasture_and_treated_shares_are_reproduced_in_every_year(self):
        value = {(r["item_code"], r["year"], r["element_code"]): float(r["value"]) for r in read_rows(MANURE)}
        for row in read_rows(MMS):
            share = {k: float(row[k]) / 100.0 for k in self.TREATED + ("pasture_range_paddock", "burned_for_fuel")}
            pasture = share["pasture_range_paddock"] + share["burned_for_fuel"] / 2.0
            treated = sum(share[k] for k in self.TREATED)
            item = self.SPECIES[row["animal"]]
            for year in sorted({y for i, y, _ in value if i == item}):
                excreted = value[(item, year, "72538")]
                with self.subTest(animal=row["animal"], year=year):
                    self.assertAlmostEqual(value[(item, year, "72380")] / excreted, pasture, delta=0.006)
                    self.assertAlmostEqual(value[(item, year, "72386")] / excreted, treated, delta=0.006)

    def test_the_default_burned_share_is_not_the_inventorys(self):
        """The inventory books 28% / 30% of excreted N as burned fuel; the default is 51-55%."""
        ipcc = {r["animal"]: float(r["burned_for_fuel"]) / 100.0 for r in read_rows(MMS)}
        booked = {(r["species"], r["system"]): float(r["share"]) for r in read_rows(
            os.path.join(DATA, "sectors", "agriculture", "parameters", "mms_shares.csv"))}
        self.assertGreater(ipcc["other cattle"] - booked[("cattle", "burned_fuel")], 0.2)
        self.assertGreater(ipcc["buffalo"] - booked[("buffalo", "burned_fuel")], 0.2)


class TestTheFaostatCropsAndVersions(unittest.TestCase):

    def test_crops_extract_is_pakistan_and_no_projection(self):
        rows = read_rows(CROPS)
        self.assertEqual({r["area"] for r in rows}, {"Pakistan"})
        self.assertLessEqual(max(int(r["year"]) for r in rows), 2025)
        synthetic = {r["year"]: float(r["value"]) for r in rows
                     if r["element_code"] == "5162" and r["item"] == "Nutrient nitrogen N (total)"}
        self.assertTrue(synthetic)

    def test_versions_name_every_bulk_once_and_flag_the_comparison(self):
        rows = read_rows(VERSIONS)
        codes = [r["dataset_code"] for r in rows]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue({"EMN", "GT", "RFN", "GCE"} <= set(codes))
        for r in rows:
            self.assertIn(r["size_vs_catalogue"], ("same-size", "differs"))
            self.assertIn(r["date_vs_catalogue"], ("predates-update", "after-update"))

    def test_both_reproduce_from_the_held_bytes(self):
        require_layers("the FAOSTAT crops bulk and bulk catalogue")
        for name in ("ingest_faostat_crops_nitrogen", "ingest_faostat_versions"):
            with self.subTest(script=name):
                self.assertEqual(load_script(name).main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()

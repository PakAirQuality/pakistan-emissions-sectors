"""Byte-equality guards for the transport paper's generated appendices.

The residential discipline: S2 (factors), S3 (completeness) and S4 (tiers) are
GENERATED .tex files, and the committed copy must match a fresh in-memory
regeneration - so a data edit that skips the generator, or a hand-edit to the .tex,
fails loudly instead of shipping a table that disagrees with the engine.

Run:  python3 -m unittest discover tests
"""

from pkinv.assets import asset_path
import csv
import importlib.util
import os
import unittest
from _support import ROOT



def _load_script(name):
    spec = importlib.util.spec_from_file_location(
        name.replace(".py", ""), os.path.join(ROOT, "scripts", name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFactorAppendix(unittest.TestCase):
    """S2: every factor, control and parameter, rendered from the data files."""

    def test_the_committed_table_matches_a_fresh_regeneration(self):
        mod = _load_script("make_transport_factor_table.py")
        committed = open(mod.OUT, encoding="utf-8").read()
        self.assertEqual(committed, mod.render())

    def test_every_engine_factor_appears(self):
        mod = _load_script("make_transport_factor_table.py")
        tex = open(mod.OUT, encoding="utf-8").read()
        with open(asset_path(ROOT, "data", "emission_factors.csv"),
                  newline="", encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f)
                    if r["category"] in mod.EF_CATEGORIES]
        self.assertGreaterEqual(len(rows), 10)
        for r in rows:
            self.assertIn(" %s &" % mod._fmt(r["value"]), tex,
                          "%s/%s missing from S2" % (r["category"], r["item"]))

    def test_the_factor_tables_carry_honest_provenance_labels(self):
        """The rule this guard was born to hold - factors are never attributed to a
        document nobody fetched - now cuts the other way: since the air program's
        Wave 2 the EMEP/EEA chapters ARE held (sources/EMEP/) and transcribed, so S2
        must present the Tier 1 tables as the layer's basis WITH their re-check
        claim, and the workbook g/km block must stand clearly superseded, still
        wearing its no-citation label, never dressed up as guidebook values."""
        mod = _load_script("make_transport_factor_table.py")
        tex = open(mod.OUT, encoding="utf-8").read()
        flat = " ".join(tex.split())
        self.assertIn("EMEP/EEA guidebook 2023 Tier~1 road-transport factors", flat)
        self.assertIn("check\\_transcriptions.py", flat)
        self.assertIn("SUPERSEDED per-kilometre factors", flat)
        self.assertIn("Punjab emissions workbook", flat)
        self.assertIn("no primary citation was ever located", flat)
        gkm_caption = flat[flat.find("SUPERSEDED per-kilometre factors"):
                           flat.find("\\label{tab:s2gkm}")]
        self.assertNotIn("EMEP", gkm_caption.replace(
            "EMEP/EEA Tier~1 tables above replaced them", ""),
            "the superseded block claims guidebook provenance for workbook values")


class TestCompletenessAppendix(unittest.TestCase):
    """S3: the transport-boundary rows of the national completeness table."""

    def test_the_committed_table_matches_the_engine(self):
        mod = _load_script("make_transport_completeness_table.py")
        committed = open(mod.OUT, encoding="utf-8").read()
        self.assertEqual(committed, mod.render())

    def test_the_boundary_spans_all_four_codes(self):
        """Road, off-road, the 1.A.2 rows the residual and unresolved diesel belong
        to, and the mobile-A/C IPPU row - the reviewer's boundary, not just 1.A.3.b."""
        mod = _load_script("make_transport_completeness_table.py")
        codes = {code for code, _cat in mod.ALLOW}
        self.assertEqual(codes,
                         {"1.A.3.a", "1.A.3.b", "1.A.3.c", "1.A.3.d", "1.A.4.c",
                          "1.A.2", "2.F.1", "(air)"})

    def test_every_allowlisted_row_resolves(self):
        mod = _load_script("make_transport_completeness_table.py")
        self.assertEqual(len(mod.rows()), len(mod.ALLOW))


class TestTierAppendix(unittest.TestCase):
    """S4: tier status by component, with quoted values asserted at generation."""

    def test_the_committed_table_matches_a_fresh_regeneration(self):
        mod = _load_script("make_transport_tier_table.py")
        committed = open(mod.OUT, encoding="utf-8").read()
        self.assertEqual(committed, mod.render())

    def test_no_row_calls_the_whole_sector_one_tier(self):
        """The table exists to retire the sector-wide shorthand: the class split and
        the spatial allocation must be labelled as allocations, not tiers."""
        mod = _load_script("make_transport_tier_table.py")
        by_comp = {c: s for c, s, _b in mod.rows()}
        self.assertIn("not a tier", by_comp["Class split"])
        self.assertIn("not a tier", by_comp["Spatial allocation"])


if __name__ == "__main__":
    unittest.main()
class TestClassAppendix(unittest.TestCase):
    """S5: the class-level calculation in full, computed from the engine."""

    def test_the_committed_table_matches_a_fresh_regeneration(self):
        mod = _load_script("make_transport_class_table.py")
        committed = open(mod.OUT_TEX, encoding="utf-8").read()
        self.assertEqual(committed, mod.render())

    def test_weights_sum_to_one_per_fuel_and_share_matches_the_engine(self):
        mod = _load_script("make_transport_class_table.py")
        rows, weights, der = mod.compute()
        from pkinv.sectors.transport import road
        from pkinv.sectors.transport.data import TransportData
        data = TransportData()
        for fuel in ("Petrol", "Diesel", "CNG"):
            total = sum(w["within_fuel_weight"] for w in weights
                        if w["fuel"] == fuel)
            self.assertAlmostEqual(total, 1.0, places=4, msg=fuel)
        self.assertAlmostEqual(
            der["share"],
            road.off_road_TJ(data) / road.fuel_TJ(data)["Diesel"], places=9)

    def test_the_published_weights_are_energy_weighted_not_distance_only(self):
        """The guard for the defect this round fixed, stated numerically.

        For two editions the methods section printed a class-share equation with a
        fuel-intensity term in it while the engine normalised vehicle-kilometres
        alone. No string check could catch that - the equation was right and the code
        was wrong. So this rebuilds BOTH normalisations from the parameter files and
        asserts which one the published weights actually came from: they must equal
        the energy-weighted construction exactly, and must differ materially from the
        distance-only one. If someone reverts the weighting, the second assertion
        fails; if someone changes the intensities without regenerating, the first does.
        """
        from pkinv.sectors.transport import road
        from pkinv.sectors.transport.data import TransportData
        mod = _load_script("make_transport_class_table.py")
        _rows, weights, _der = mod.compute()
        data = TransportData()
        vkt, _cells, _capped = road.effective_vkt(data)
        published = {(w["ei_class"], w["fuel"]): w["within_fuel_weight"]
                     for w in weights}

        def normalise(weighted):
            out = {}
            for fuel in road.FUELS:
                cells = {k: v for k, v in weighted.items() if k[1] == fuel}
                tot = sum(cells.values())
                for k, v in cells.items():
                    out[k] = v / tot if tot else 0.0
            return out

        energy = normalise({k: v * data.mjkm(k[0], k[1]) for k, v in vkt.items()})
        distance = normalise(dict(vkt))
        for key, value in published.items():
            self.assertAlmostEqual(
                value, energy[key], places=6,
                msg="%s: published weight is not the energy-weighted share" % (key,))
        differing = [k for k in published
                     if abs(distance[k] - energy[k]) > 1e-3]
        self.assertTrue(
            differing,
            "the two normalisations are indistinguishable - the intensity term is "
            "not doing anything, so the equation in the methods section overstates "
            "the calculation")

    def test_the_methods_equation_declares_the_intensity_term(self):
        """The prose half of the same invariant: the equation must keep a term the
        engine applies, and must say what it is."""
        path = os.path.join(ROOT, "papers", "transport", "sections",
                            "04_methods.tex")
        text = " ".join(open(path, encoding="utf-8").read().split())
        self.assertIn("e_{c,f}", text)
        self.assertIn("energy intensity", text)
        self.assertIn("megajoules", text)


if __name__ == "__main__":
    unittest.main()

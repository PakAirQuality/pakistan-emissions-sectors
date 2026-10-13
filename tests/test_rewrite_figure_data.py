"""The compact manuscript's figures are built from the products, and still agree with the
transcription they replaced.

WHY THIS TEST EXISTS. The October 2026 editorial rewrite arrived with six CSVs behind its four
figures, every row labelled "Transcribed from supplied manuscript; not independently
regenerated". Its manifest says those files "should not replace original inventory outputs",
and its editorial notes ask, as the first author action, to rebuild the figures from actual
outputs. scripts/build_rewrite_figure_data.py now does that, reading each value through the
same product pointer the registered claim for that value uses.

Two things then need holding, and they are different things.

First, the generated files must be what the script produces: a figure built from a stale CSV
is a figure that disagrees with the paper's own sentences, which is the whole failure the
claim registry exists to prevent, one level out.

Second - and this is the part worth keeping for longer than it seems - the generated values
must still match the transcription. When the rewiring was done all 39 values agreed exactly,
which is evidence the transcription was faithful. Keeping the comparison means that if the
engine's value moves, the disagreement surfaces HERE, as a question about which of the two is
right, rather than being silently overwritten by a regeneration. The transcription is the only
independent record of what the manuscript printed on 1 October 2026.

If a product legitimately changes, this test fails and the honest response is to update the
transcription WITH a note saying what moved and why - not to delete the comparison.
"""
import csv
import io
import os
from pkinv.paths import PAPER_NATIONAL_FIGURES  # noqa: E402
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

BASE = os.path.join(PAPER_NATIONAL_FIGURES, "rewrite_inputs")
GENERATED = os.path.join(BASE, "data")
TRANSCRIBED = os.path.join(BASE, "transcribed_csv")

# file -> (key column, value columns to compare)
COMPARE = {
    "module_totals.csv": ("module", ["emissions_Mt_CO2e"]),
    "annual_national_series.csv": ("period", ["emissions_Mt_CO2e"]),
    "national_uncertainty.csv": ("case", ["point_Mt_CO2e", "p025_Mt_CO2e", "p975_Mt_CO2e"]),
    "reference_temporal_evidence.csv": ("evidence_class", ["share_percent"]),
    "managed_soils_factor_scenarios.csv": ("case", ["emissions_Mt_CO2e"]),
    "provincial_so2_ratios.csv": ("region", ["pakemis_to_edgar_ratio"]),
}
# Rows a plot table has gained since the transcription, each for a stated reason.
ADDED_SINCE_TRANSCRIPTION = {
    "managed_soils_factor_scenarios.csv": {"2006 pasture"},
}
# Agreement was exact at the rewiring; the tolerance is the printed precision, not a band.
TOLERANCE = 0.005


def _load(path, key):
    with io.open(path, encoding="utf-8") as handle:
        return {r[key]: r for r in csv.DictReader(handle)}


class TestTheFigureInputsComeFromTheProducts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.isdir(GENERATED):
            raise unittest.SkipTest("the figure inputs have not been generated here")

    def test_the_generated_files_match_a_fresh_build(self):
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "build_rewrite_figure_data.py"),
             "--check"],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(
            r.returncode, 0,
            "the figure inputs are stale; run scripts/build_rewrite_figure_data.py.\n%s%s"
            % (r.stdout, r.stderr))
        self.assertIn("checked:", r.stdout,
                      "--check reported nothing as checked, so it compared nothing")

    def test_every_generated_value_still_matches_the_transcription(self):
        problems = []
        for name, (key, columns) in COMPARE.items():
            gpath, tpath = os.path.join(GENERATED, name), os.path.join(TRANSCRIBED, name)
            if not (os.path.exists(gpath) and os.path.exists(tpath)):
                problems.append("%s: missing one side of the comparison" % name)
                continue
            gen, old = _load(gpath, key), _load(tpath, key)
            # NOTHING THE MANUSCRIPT PRINTED MAY BE LOST; a row may be ADDED where declared. The
            # sets had to be equal, which also refused a figure a row it needed: rc63 shows the
            # pasture-factor substitution on its own, which the 1 October manuscript never
            # printed, so it has no transcription to agree with.
            added = set(gen) - set(old)
            if set(old) - set(gen) or added - ADDED_SINCE_TRANSCRIPTION.get(name, set()):
                problems.append("%s: rows differ - only generated %s, only transcribed %s"
                                % (name, sorted(added), sorted(set(old) - set(gen))))
                continue
            for row_key in sorted(old):
                for column in columns:
                    g, t = gen[row_key].get(column, ""), old[row_key].get(column, "")
                    if not g and not t:
                        continue
                    try:
                        if abs(float(g) - float(t)) <= TOLERANCE:
                            continue
                    except ValueError:
                        pass
                    problems.append("%s %s/%s: product gives %s, the manuscript printed %s"
                                    % (name, row_key, column, g or "(blank)", t or "(blank)"))
        self.assertFalse(
            problems,
            "the products no longer agree with what the manuscript printed. Decide which is "
            "right: if the product moved for a good reason, update the transcription WITH a "
            "note recording what moved - do not delete the comparison, it is the only "
            "independent record of the 1 October 2026 figures.\n  %s"
            % "\n  ".join(problems))

    def test_the_comparison_is_actually_comparing_something(self):
        """A registry that silently emptied would pass the test above forever."""
        total = 0
        for name, (key, columns) in COMPARE.items():
            path = os.path.join(GENERATED, name)
            if not os.path.exists(path):
                continue
            rows = _load(path, key)
            total += len(rows) * len(columns)
        self.assertGreater(
            total, 30,
            "only %d value comparisons are set up; 39 were in place when the figures were "
            "rewired to the products" % total)


if __name__ == "__main__":
    unittest.main()

class TestFigureOneClosesPerGas(unittest.TestCase):
    """Figure 1's closure holds gas by gas, at full precision, with no rounded zero.

    WHY. construction_quantities.csv printed unallocated CH4 and N2O as 0.0 while the
    unallocated product carries 0.001741 Gg CH4 and 0.006963 Gg N2O for FY2023-24 - and the
    companion text then called 249.46 Gg CO2 "0.251 Mt CO2e", which is the THREE-gas CO2e
    total (CO2 0.24946 + CH4 at GWP 30 + N2O at 265), not the CO2 conversion. Rounded zero is
    not exact zero, and a reader who takes the figure at its word concludes the other two
    gases are fully placed. The guard reads the product, not the figure's own summary.
    """
    PERIOD = "FY2023-24"
    MONTHS = {"2023%02d" % m for m in range(7, 13)} | {"2024%02d" % m for m in range(1, 7)}

    @classmethod
    def setUpClass(cls):
        path = os.path.join(GENERATED, "construction_quantities.csv")
        if not os.path.exists(path):
            raise unittest.SkipTest("construction_quantities.csv not generated here")
        cls.rows = list(csv.DictReader(io.open(path, encoding="utf-8")))
        unal = os.path.join(ROOT, "outputs", "pakemis_spatial_unallocated.csv")
        cls.unallocated = {}
        with io.open(unal, encoding="utf-8") as handle:
            for r in csv.DictReader(handle):
                if r["month"] in cls.MONTHS:
                    cls.unallocated[r["gas"]] = cls.unallocated.get(r["gas"], 0.0) + float(r["emissions_Gg"])

    def _q(self, node, gas):
        hits = [r for r in self.rows if r["node"] == node and r["gas"] == gas
                and r["period"] == self.PERIOD]
        self.assertEqual(len(hits), 1, "%s/%s: %d rows" % (node, gas, len(hits)))
        return float(hits[0]["quantity"]), hits[0]["quantity"]

    def test_ledger_equals_placed_plus_unallocated_for_every_gas(self):
        for gas in ("CO2", "CH4", "N2O"):
            ledger, _ = self._q("ledger_mass", gas)
            placed, _ = self._q("placed_mass", gas)
            unal, _ = self._q("unallocated_mass", gas)
            self.assertAlmostEqual(ledger, placed + unal, delta=max(1e-9 * ledger, 5e-4),
                                   msg="%s: %s != %s + %s" % (gas, ledger, placed, unal))

    def test_a_nonzero_unallocated_mass_is_never_printed_as_zero(self):
        """The product decides what is zero; the figure may not round it away."""
        for gas in ("CO2", "CH4", "N2O"):
            product = self.unallocated.get(gas, 0.0)
            printed_value, printed_text = self._q("unallocated_mass", gas)
            if product > 0.0:
                self.assertGreater(printed_value, 0.0,
                                   "%s: the product holds %.6g Gg unallocated but the figure "
                                   "prints %r - a rounded zero presented as exact"
                                   % (gas, product, printed_text))
                self.assertAlmostEqual(printed_value, product,
                                       delta=max(abs(product) * 1e-3, 5e-7),
                                       msg="%s: printed %s vs product %.6g" % (gas, printed_text, product))
            else:
                self.assertEqual(printed_value, 0.0, "%s: product is zero, figure prints %r" % (gas, printed_text))

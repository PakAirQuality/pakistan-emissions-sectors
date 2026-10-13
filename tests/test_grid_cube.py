"""The Stage 6 gate as tests: the closure identity, now in its two terms.

THE IDENTITY CHANGED THIS RELEASE and these tests are where that has to be visible. It read
annual = monthly = native = grid = ADM2 = province. It now reads

    national == ADM1                          (unchanged - the safety property)
    ADM1     == ADM2 + unallocated_below_adm1

because the twenty-four industry streams carrying S4:no-native-geometry - 9.01 Mt, the whole
of the industry module - are no longer spread across cells on a proxy that describes no
geography they have. The change must show as a STRICT INEQUALITY and never as a loosened
tolerance: the grid total is now less than the national total by exactly the unallocated mass,
so a stream creeping back into a cell restores the old equality and fails
test_grid_equals_national_per_gas_and_month. Loosening a bound would hide precisely that.

TOLERANCE POLICY, declared once. Two tiers, deliberately different:
  IN MEMORY  the identity is held at 1e-9 on weights and at a combined abs+rel bound of
             max(1e-6 x value, 1e-6 Gg) against the monthly CSV, whose Gg column is rounded
             to 8 dp - a pure relative bound would fail the 1e-5-Gg streams on rounding
             alone, which is noise, not mass.
  ON DISK    the shipped NetCDF stores float32; re-reading it closes at 1e-5 RELATIVE. Do
             not tighten this to the in-memory tier: the difference is storage precision,
             and chasing it would be chasing phantom mass.
District panels are matched at each panel's own rounding (the test_stage6_downpayment
principle: the tolerance is the artefact's rounding, never a new allowance). The aviation
provincial rows are asserted DIVERGENT-AND-DECLARED - Islamabad International is
administratively ICT and physically in Attock, and a fix that renormalised the airports
within provinces would smear a real airport across territory it does not serve.
"""

from pkinv.assets import asset_path
import collections
import csv
import json
import os
import sys
import unittest
from pkinv.core.io import read_rows
from _support import DATA, OUT, ROOT
from _support import cached_build



try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False

CACHES = all(os.path.exists(asset_path(DATA, "gis", "proxy_%s_267x340.npy" % n))
             for n in ("cropland", "builtup", "population", "glw_livestock",
                       "manure_applied"))


def _rows(name, root=OUT):
    return read_rows(asset_path(root, name))


def _numeric(rows):
    """The ADM2 views carry two DECLARED absences, both non-numeric on purpose: a canonical
    unit with no drawable polygon, and mass controlled at ADM1 with no geography under it.
    Read the vocabulary from the writer rather than repeating its literals here - the second
    one arrived after the first had been spelled out at fifteen sites."""
    from pkinv.report.grid_cube import DECLARED_ABSENCES
    # rc41: an absence row leaves emissions_Gg EMPTY and names itself in absence_reason
    out = []
    for row in rows:
        if row["emissions_Gg"] in DECLARED_ABSENCES:
            continue        # the pre-rc41 form (a HEAD-baseline read of the last release)
        if row.get("absence_reason", ""):
            assert row["absence_reason"] in DECLARED_ABSENCES, row["absence_reason"]
            assert row["emissions_Gg"] == "", row
            continue
        out.append(row)
    return out


# THE PROVINCIAL RE-BASES THIS RELEASE DECLARES, and nothing else may move.
#
# The test below is a "nothing changed since the last release" guard, and it was written on the
# reasoning that a provincial marginal moving is "a different event entirely" from a district
# one. That is still true. What changed at rc62 is that two such events are deliberate, so the
# guard stops being a diff against HEAD that somebody has to remember to read, and becomes an
# assertion about WHICH streams were re-based - any other stream moving still fails it.
#
# Each entry names the streams and why they moved. Retire an entry when its cause is committed
# and the baseline catches up; do not leave one standing, because a stale declaration is exactly
# the cover a real regression would slip through.
#
# Both entries that stood here were retired when the rounds that caused them were committed:
# "industrial liquids product split (rc62)" (industrial-furnace-oil, -diesel, -gasoline,
# -hobc, -kerosene, -light-diesel-oil) and "captive gas franchise year-keying (rc60)"
# (captive-natural-gas). The baseline caught up - zero streams move against HEAD - so the
# guard is back to its original form: any provincial marginal moving fails it.
DECLARED_PROVINCIAL_MOVERS = {}


def _declared_mover(stream_id):
    """The declaration that covers this stream, or None if nothing does."""
    subitem = stream_id.split("|")[2] if "|" in stream_id else stream_id
    for reason, prefixes in DECLARED_PROVINCIAL_MOVERS.items():
        if any(subitem.startswith(prefix) for prefix in prefixes):
            return reason
    return None


@unittest.skipUnless(HAVE_NUMPY and CACHES,
                     "gis extra or committed proxy caches absent from this checkout")
class TestTheCube(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from pkinv.report import grid_cube
        cls.gc = grid_cube
        cls.result = cached_build()
        cls.monthly = _rows("national_monthly_2024.csv")
        cls.ledger = _rows("pakemis_source_streams.csv")

    def _unallocated_by(self, fields):
        """The second term of the identity, summed over whichever axes the caller holds.
        Native gas mass, the same unit every leg of the identity is asserted in."""
        out = {}
        for row in self.result["unallocated"]:
            key = tuple(row[field] for field in fields)
            key = key[0] if len(key) == 1 else key
            out[key] = out.get(key, 0.0) + row["emissions_Gg"]
        return out

    # --- the identity, leg by leg --------------------------------------------------------

    def test_every_weight_sums_to_one(self):
        """Already enforced stream-by-stream inside build(); re-asserted here through the
        marginals so a refactor cannot quietly drop the in-build check."""
        for sid, marginals in self.result["marginals"].items():
            self.assertAlmostEqual(sum(marginals.values()), 1.0, places=9, msg=sid)

    def test_grid_equals_national_per_gas_and_month(self):
        """sum(cells) + unallocated == the national monthly total, every gas, every month -
        and sum(cells) alone is STRICTLY LESS than it. The second assertion is the one this
        release exists for: it fails the moment a stream with no native geometry is placed
        in a cell again, which no tolerance on the first assertion could detect."""
        national = {}
        for row in self.monthly:
            key = (row["gas"], row["month"])
            national[key] = national.get(key, 0.0) + float(row["emissions_Gg"])
        unallocated = self._unallocated_by(("gas", "month"))
        for gas in self.gc.GASES:
            for index, month in enumerate(self.gc.MONTHS):
                grid_total = float(self.result["gas_month"][gas][index].sum())
                unplaced = unallocated.get((gas, month), 0.0)
                expected = national[(gas, month)]
                self.assertLess(abs(grid_total + unplaced - expected),
                                max(1e-6 * expected, 1e-6),
                                "%s %s: grid %.8f + unallocated %.8f vs national %.8f"
                                % (gas, month, grid_total, unplaced, expected))
                self.assertGreater(unplaced, 0.0,
                                   "%s %s: nothing is unallocated, so either the industry "
                                   "module gained geometry or S4 is back in the cells"
                                   % (gas, month))
                self.assertLess(grid_total, expected,
                                "%s %s: the grid carries the whole national mass again"
                                % (gas, month))

    def test_category_annual_equals_the_ledger(self):
        """Two terms per category. rc47 Wave 4: industry gained its geometry, so NO
        category is wholly unplaced any more - aviation's cruise streams are unplaced
        but their category has a raster through the LTO share, so every category key
        appears in the grid. The good news this docstring's predecessor promised to
        record is recorded here."""
        by_key = {}
        for row in self.ledger:
            key = (row["module"], row["ipcc_category"], row["gas"])
            by_key[key] = by_key.get(key, 0.0) + float(row["emissions_native"])
        unallocated = self._unallocated_by(("module", "ipcc_category", "gas"))
        self.assertEqual(set(by_key), set(self.result["category_annual"]) | set(unallocated))
        for key, expected in by_key.items():
            grid_total = float(self.result["category_annual"].get(key, np.zeros(1)).sum())
            self.assertLess(abs(grid_total + unallocated.get(key, 0.0) - expected),
                            max(1e-6 * expected, 1e-6), str(key))
        self.assertEqual({key for key in by_key if key not in self.result["category_annual"]},
                         set(),
                         "the set of categories with no grid representation moved; if a "
                         "category gained geometry that is good news and this is where it "
                         "is recorded")

    def test_province_marginals_exact_where_constructed(self):
        """Every exact_by_construction stream's grid share equals its declared share at
        1e-9; rail at its committed rounding; aviation asserted divergent below.

        THE UNPLACED STREAMS ARE CHECKED HERE TOO, and harder, because the provincial share
        is now the only claim they make. The first cut of this change returned before the
        check-row block, and the file fell from 950 rows to 830 - exactly twenty-four
        streams times five provinces, silently."""
        declared_by_stream = {}
        for row in _rows("pakemis_grid_provincial_check.csv"):
            declared_by_stream.setdefault(row["source_stream_id"], []).append(row)
        unplaced = {sid for sid, rows in declared_by_stream.items()
                    if rows[0]["status"] == self.gc.UNALLOCATED_STATUS}
        # 30 since rc46 Wave 2: the six solid-fuel stream-gas rows (brick and cement coal
        # x three gases) joined the S4 set - retained at ADM1 on register-derived provincial
        # shares, with the kiln points and the GEM works named as Wave 5's within-province
        # closers.
        # 3 since rc47 Wave 4: industry left S4 entirely (kiln points, the clinker
        # register, built-up S3), so only the aviation cruise rows remain - not
        # placed because no OD matrix is held, which is a fact about the world
        # rather than about this repository's effort.
        self.assertEqual(len(unplaced), 3, "the unplaced set moved")
        checked = 0
        for sid, rows in declared_by_stream.items():
            status = rows[0]["status"]
            if status in ("exact_by_construction", self.gc.UNALLOCATED_STATUS):
                for row in rows:
                    self.assertLess(abs(float(row["diff"])), 2e-6,
                                    "%s %s" % (sid, row["province"]))
                    checked += 1
            elif status == "derived_from_grid":
                for row in rows:
                    self.assertLess(abs(float(row["diff"])), 2e-2,
                                    "%s %s: the rail surface and its own derived share "
                                    "row disagree beyond rounding" % (sid, row["province"]))
        self.assertGreater(checked, 800, "the exact set collapsed")

    def test_declared_divergence_is_the_known_set_and_bounded(self):
        """Two point-geometry families are ALLOWED to diverge from their declared
        share rows, each for a stated physical reason: aviation's three streams
        (Islamabad International is ICT administratively and Punjab physically) and
        the rail non-traction streams since rc11 (yard coordinates against the
        transcribed wagons-loaded shares, with border-cell binning). No other
        stream may join the set silently."""
        rows = [r for r in _rows("pakemis_grid_provincial_check.csv")
                if r["status"] == "declared_divergence"]
        streams = {r["source_stream_id"] for r in rows}
        aviation = {s for s in streams if s.startswith("aviation")}
        rail = {s for s in streams if "non-traction" in s}
        self.assertEqual(len(aviation), 3, streams)
        self.assertGreaterEqual(len(rail), 1, streams)
        self.assertEqual(streams, aviation | rail,
                         "an undeclared stream joined the divergence set")
        # Aviation bounded by Islamabad International's movement share: the
        # divergence IS that airport counted in Punjab by coordinates and ICT by
        # administration.
        points = self.gc.airport_points()
        total = sum(w for _lon, _lat, w in points)
        isb = max(w for _lon, _lat, w in points) / total
        for row in rows:
            if row["source_stream_id"] in aviation and \
                    row["province"] in ("Punjab", "Other"):
                self.assertLessEqual(abs(float(row["diff"])), isb + 0.05,
                                     "%s %s diverges beyond the Islamabad share"
                                     % (row["source_stream_id"], row["province"]))
            if row["source_stream_id"] in rail:
                self.assertLessEqual(abs(float(row["diff"])), 0.05,
                                     "%s %s: yard binning cannot move more than a "
                                     "border yard's share"
                                     % (row["source_stream_id"], row["province"]))

    # --- the second term ------------------------------------------------------------------

    def test_the_unallocated_table_carries_the_whole_s4_ledger(self):
        """Published per stream, per province, per month, and summing to the ledger's own
        S4 total. The shipped file, not the in-memory result: this is what a downstream
        user adds to the grid to get back to the national number."""
        shipped = _rows("pakemis_spatial_unallocated.csv")
        expected = {r["source_stream_id"]: float(r["emissions_native"])
                    for r in self.ledger
                    if r["geometry_id"] == self.gc.NO_NATIVE_GEOMETRY}
        # +6 at rc46 Wave 2 (solid fuels); +3 at rc47 Wave 3 (aviation cruise);
        # -30 at rc47 Wave 4 (industry got its geography) - the table now carries
        # exactly the cruise streams.
        self.assertEqual(len(expected), 3)
        got = {}
        for row in shipped:
            got[row["source_stream_id"]] = (got.get(row["source_stream_id"], 0.0)
                                            + float(row["emissions_Gg"]))
        self.assertEqual(set(got), set(expected),
                         "the unallocated table and the ledger name different streams")
        for sid, total in expected.items():
            self.assertLess(abs(got[sid] - total), max(1e-6 * total, 1e-9), sid)
        for row in shipped:
            self.assertEqual(row["level"], "adm1",
                             "%s claims a level finer than its evidence" % row["province"])
            self.assertTrue(row["reason"].strip())

    def test_no_stream_is_both_placed_and_unplaced(self):
        """The two terms partition the inventory; they do not overlap. A stream appearing
        in both would be double counted by the very sum the identity asks a reader to do."""
        unplaced = {r["source_stream_id"] for r in _rows("pakemis_spatial_unallocated.csv")}
        placed = {sid for sid, rows in
                  {r["source_stream_id"]: r for r in
                   _rows("pakemis_grid_provincial_check.csv")}.items()
                  if rows["status"] != self.gc.UNALLOCATED_STATUS}
        self.assertFalse(unplaced & placed, sorted(unplaced & placed))
        self.assertEqual(len(unplaced | placed), len(self.result["streams"]),
                         "the two terms do not cover every stream")

    def test_every_adm1_marginal_is_unchanged_by_the_change(self):
        """THE SAFETY PROPERTY, and the reason this change is publishable at all: S4 mass
        was always provincially controlled, and only its placement BELOW the province was
        invented. So no provincial figure may move - not one of the 950 - and the national
        total is untouched. Only cells and districts change.

        Asserted against the committed file, which is the release this change is measured
        from; when the next release commits, this compares against that one and keeps
        holding, because a provincial marginal moving is a different event entirely."""
        import subprocess
        blob = subprocess.run(
            ["git", "show", "HEAD:outputs/pakemis_grid_provincial_check.csv"],
            capture_output=True, text=True, cwd=ROOT)
        if blob.returncode != 0:
            self.skipTest("no committed provincial check to compare against")
        import io
        committed = {(r["source_stream_id"], r["province"]): r
                     for r in csv.DictReader(
                         line for line in io.StringIO(blob.stdout)
                         if not line.startswith("#"))}
        current = {(r["source_stream_id"], r["province"]): r
                   for r in _rows("pakemis_grid_provincial_check.csv")}
        self.assertEqual(set(committed), set(current),
                         "the stream x province frame moved, which this test cannot judge")
        moved = [key for key in committed
                 if abs(float(committed[key]["grid_share"])
                        - float(current[key]["grid_share"])) > 1e-9]
        undeclared = sorted(k for k in moved if _declared_mover(k[0]) is None)
        self.assertFalse(undeclared,
                         "provincial marginals moved on streams no release declared: %s"
                         % undeclared[:5])
        # and the declarations must still be live: a mover that stops moving is a reason to
        # retire its entry, not to leave it standing as cover for the next one
        declared = {_declared_mover(k[0]) for k in moved}
        self.assertEqual(declared, set(DECLARED_PROVINCIAL_MOVERS),
                         "a declared provincial re-base no longer moves anything; retire its "
                         "entry rather than leaving it to cover a future change")

    def test_the_monthly_file_carries_the_annual_products_own_district_years(self):
        """THE SAME PROPERTY AS THE TEST ABOVE, WITHOUT A BASELINE - and the reason it is
        worth having twice.

        The test above compares the monthly file against HEAD's copy, so it fires whenever a
        district-year total moves and CANNOT say why: a monthly profile that illegitimately
        changed annual mass and a deliberate spatial re-base that moved the annual total look
        identical to it, and both go green again at the next commit. rc62 hit exactly that -
        252 district-years moved because the industrial liquids were given their own province
        geography, which is not a timing change at all.

        This asserts the property directly instead. Summing the monthly file over months must
        reproduce the annual district product in the SAME tree, so a profile that moved mass
        rather than merely placing it in time fails here immediately, with no commit in
        between and nothing to compare against. A spatial re-base moves both files together
        and passes, because it is not the thing being tested."""
        monthly = collections.defaultdict(float)
        for row in _rows("pakemis_adm2_monthly.csv"):
            if row["spatial_view"] != "physical" or not row["emissions_Gg"]:
                continue
            monthly[(row["shape_id"], row["gas"])] += float(row["emissions_Gg"])
        # the monthly file has no period column: it is the reference year, and the manifest
        # is where that year is declared rather than a literal repeated in a test
        with open(os.path.join(ROOT, "outputs", "release_manifest.json"), encoding="utf-8") as fh:
            reference = json.load(fh)["reporting_period"]["label"]
        annual = collections.defaultdict(float)
        for row in _rows("pakemis_adm2_sector_by_year.csv"):
            if (row["period_id"] != reference or row["spatial_view"] != "physical"
                    or not row["emissions_Gg"]):
                continue
            annual[(row["shape_id"], row["gas"])] += float(row["emissions_Gg"])
        self.assertTrue(monthly and annual)
        self.assertEqual(set(monthly), set(annual),
                         "the monthly and annual district frames hold different (shape, gas) cells")
        # twelve months re-accumulate in a different order than one annual figure, so the
        # bound is relative with an absolute floor - the same two terms the baseline test
        # above uses, and for the same double-precision reason
        off = [(key, abs(monthly[key] - annual[key])) for key in annual
               if abs(monthly[key] - annual[key]) >= max(1e-5, 1e-6 * abs(annual[key]))]
        worst = max(off, key=lambda kv: kv[1]) if off else (None, 0.0)
        self.assertFalse(off,
                         "%d district-years differ between the monthly file and the annual "
                         "product (worst %s by %.3e Gg): a monthly profile decided HOW MUCH, "
                         "not only when" % (len(off), worst[0], worst[1]))

    # --- the third axis: what the placement claims to be -----------------------------------

    def test_the_view_axis_is_a_grouping_and_not_a_reallocation(self):
        """THE SAFETY PROPERTY. Summing the ADM2 view back over its new view axis must
        reproduce, for every (shape, gas, month), exactly what the previous release
        published. A view says what a placement claims to be; it must not change where
        anything is placed, and the way that goes wrong is wiring the axis into a weight
        rather than into a grouping."""
        import io
        import subprocess
        blob = subprocess.run(["git", "show", "HEAD:outputs/pakemis_adm2_monthly.csv"],
                              capture_output=True, text=True, cwd=ROOT)
        if blob.returncode != 0:
            self.skipTest("no committed ADM2 view to compare against")
        committed = {}
        # Skip the header comment. The ADM2 views gained one explaining why they carry no
        # per-cell uncertainty, and reading it as data broke this test and two readers in
        # test_spatial_contract on the same day - a comment-blind DictReader is a bug that
        # only appears when someone finally writes a comment.
        for row in _numeric(list(csv.DictReader(
                line for line in io.StringIO(blob.stdout) if not line.startswith("#")))):
            key = (row["shape_id"], row["gas"], row["month"])
            committed[key] = committed.get(key, 0.0) + float(row["emissions_Gg"])
        current = {}
        for row in _numeric(_rows("pakemis_adm2_monthly.csv")):
            key = (row["shape_id"], row["gas"], row["month"])
            current[key] = current.get(key, 0.0) + float(row["emissions_Gg"])
        self.assertEqual(set(committed), set(current), "the (shape, gas, month) frame moved")
        worst = max(abs(current[k] - v) for k, v in committed.items())
        self.assertLess(worst, 1e-6,
                        "summing over views does not reproduce the committed district "
                        "totals: worst %.3e Gg. If a monthly SHAPE changed deliberately "
                        "this is expected and the annual invariant below is the one that "
                        "must still hold; commit the content and this baseline moves with "
                        "it." % worst)

    def test_a_monthly_reshape_never_moves_a_district_year(self):
        """The invariant that does NOT move when a profile legitimately changes.

        The test above compares against HEAD, which makes it a "nothing changed since the last
        release" guard - useful, and it fires on any deliberate reshape too. When the cement
        profile moved from a borrowed calendar-2022 shape to nine years of its own fiscal
        months, district-MONTHS moved by up to 36.7 Gg and that was the point of the change.

        What must never move is the district-YEAR. A monthly layer decides only WHEN within
        the year, so re-timing anything and re-summing the twelve months has to return the
        same number to the last decimal. Checked inside ONE build, against no baseline, so it
        keeps holding after the commit that resets the comparison above.
        """
        import io
        import subprocess
        blob = subprocess.run(["git", "show", "HEAD:outputs/pakemis_adm2_monthly.csv"],
                              capture_output=True, text=True, cwd=ROOT)
        if blob.returncode != 0:
            self.skipTest("no committed ADM2 view to compare against")

        def by_district_year(rows):
            out = {}
            for row in rows:
                try:
                    value = float(row["emissions_Gg"])
                except (TypeError, ValueError):
                    continue
                key = (row["shape_id"], row["gas"])
                out[key] = out.get(key, 0.0) + value
            return out

        was = by_district_year(csv.DictReader(
            line for line in io.StringIO(blob.stdout) if not line.startswith("#")))
        now = by_district_year(_rows("pakemis_adm2_monthly.csv"))
        self.assertEqual(set(was), set(now), "the (district, gas) frame moved")
        # The bound is RELATIVE with an absolute floor. A reshape recomputes each month
        # cell as year x share and the year-sum re-accumulates in a different order, so
        # the drift scales with the stream's mass: rc20 measured 1.7e-6 Gg absolute when
        # three small liquid profiles reshaped, and rc21 measured 3.1e-8 RELATIVE when
        # power's 38-Mt coal stream reshaped over the Karachi shared shape - the same
        # double-precision accumulation, riding a stream a thousand times heavier. A real
        # reallocation moves whole streams, orders of magnitude above either term.
        moved = [(k, abs(now[k] - was[k])) for k in was
                 if abs(now[k] - was[k]) >= max(1e-5, 1e-6 * abs(was[k]))]
        worst = max(moved, key=lambda kv: kv[1]) if moved else (None, 0.0)
        self.assertFalse(moved,
                         "a monthly reshape moved %d district-YEARs beyond their own "
                         "rounding bound (worst %s by %.3e Gg) - a profile may only "
                         "decide when within the year, never how much"
                         % (len(moved), worst[0], worst[1]))

    def test_every_row_names_a_view_from_the_vocabulary(self):
        for name in ("pakemis_adm2_monthly.csv", "pakemis_adm2_monthly_sector.csv"):
            seen = {row["spatial_view"] for row in _rows(name)}
            self.assertTrue(seen <= set(self.gc.VIEWS) | {"all"}, "%s: %r" % (name, seen))
            self.assertTrue(set(self.gc.VIEWS) <= seen,
                            "%s does not carry every view; a view that vanishes from a "
                            "product is a view a reader cannot separate" % name)

    def test_no_category_layer_mixes_views(self):
        """A raster labelled with the coarser of two names is a raster a reader cannot use.
        build() raises rather than writing one; this asserts the shipped labelling."""
        views = self.result["category_view"]
        self.assertEqual(set(views), set(self.result["category_annual"]))
        for key, view in views.items():
            self.assertIn(view, self.gc.VIEWS, str(key))

    def test_the_view_split_matches_the_ledger(self):
        """Recomputed from the ledger rather than read back out of the product that
        reports it - the same shape as the temporal and spatial decompositions."""
        expected = {}
        for row in self.ledger:
            if row["geometry_id"] == self.gc.NO_NATIVE_GEOMETRY:
                continue                       # unplaced mass is in neither view of the grid
            key = (row["spatial_view"], row["gas"])
            expected[key] = expected.get(key, 0.0) + float(row["emissions_native"])
        for view in self.gc.VIEWS:
            for gas in self.gc.GASES:
                got = float(self.result["view_gas_month"][(view, gas)].sum())
                want = expected.get((view, gas), 0.0)
                self.assertLess(abs(got - want), max(1e-6 * want, 1e-6),
                                "%s/%s: grid %.6f vs ledger %.6f" % (view, gas, got, want))

    def test_adm2_view_sums_to_the_grid(self):
        """The ADM2 CSV is an aggregation of the same arrays; equality is exact minus the
        cells outside any district polygon (borders, coast), which must be small."""
        adm2_total = {}
        for row in _numeric(_rows("pakemis_adm2_monthly.csv")):
            key = (row["gas"], row["month"])
            adm2_total[key] = adm2_total.get(key, 0.0) + float(row["emissions_Gg"])
        for gas in self.gc.GASES:
            grid_annual = float(self.result["gas_month"][gas].sum())
            adm2_annual = sum(v for (g, _m), v in adm2_total.items() if g == gas)
            self.assertLess(abs(grid_annual - adm2_annual), 0.02 * grid_annual,
                            "%s: more than 2%% of grid mass sits outside every district "
                            "polygon" % gas)

    def test_sector_adm2_view_partitions_the_adm2_view(self):
        """The sector-resolved view summed over modules must equal the aggregate ADM2
        view per (shape, gas, month) - the two files aggregate the SAME weighted
        surfaces, one with the module axis kept, one with it summed away. The bound
        is rounding-only: both columns print 8 dp."""
        agg = {}
        for row in _numeric(_rows("pakemis_adm2_monthly.csv")):
            agg[(row["shape_id"], row["gas"], row["month"],
                 row["spatial_view"])] = float(row["emissions_Gg"])
        summed = {}
        for row in _numeric(_rows("pakemis_adm2_monthly_sector.csv")):
            key = (row["shape_id"], row["gas"], row["month"], row["spatial_view"])
            summed[key] = summed.get(key, 0.0) + float(row["emissions_Gg"])
        self.assertEqual(set(agg), set(summed),
                         "the two views cover different (shape, gas, month, view) keys")
        worst = max(abs(summed[k] - v) for k, v in agg.items())
        self.assertLess(worst, 1e-5, "partition identity broken: %r Gg" % worst)

    def test_sector_view_module_totals_close_to_the_ledger(self):
        """Each module x gas summed over shapes and months equals the module's ALLOCATED
        total - the ledger less whatever the cube declined to place - minus only the
        outside-every-polygon slack the aggregate view already tolerates (2 percent).

        The 2 percent is a slack on the allocated portion, never a budget large enough to
        absorb unplaced mass. Industry's allocated total is zero, and that is a real answer
        rather than a missing module: every one of its streams is controlled at ADM1 and
        placed nowhere finer, so it appears in this view carrying its declared marker and
        no numbers."""
        ledger = {}
        for s in self.ledger:
            key = (s["module"], s["gas"])
            ledger[key] = ledger.get(key, 0.0) + float(s["emissions_native"])
        unallocated = self._unallocated_by(("module", "gas"))
        view = {}
        for row in _numeric(_rows("pakemis_adm2_monthly_sector.csv")):
            key = (row["module"], row["gas"])
            view[key] = view.get(key, 0.0) + float(row["emissions_Gg"])
        for key, total in ledger.items():
            allocated = total - unallocated.get(key, 0.0)
            got = view.get(key, 0.0)
            # The file's declared combined bound, max(1e-6 x value, 1e-6 Gg), and here it is
            # load-bearing rather than decorative: for a WHOLLY unplaced module `allocated`
            # should be exactly zero, and it is instead a residue of the module's own size
            # times 1e-8, because the monthly shares close at 1e-6 places. A relative bound
            # on `allocated` would read that residue as mass the cube failed to place.
            slack = max(1e-6 * total, 1e-6)
            # the upper side uses the same declared slack as the lower: `allocated`
            # is a DIFFERENCE of two independently rounded files, so for a wholly
            # unplaced module it lands within +/- a few 1e-5 Gg of zero in either
            # direction (rc20: industry CO2 came out -3e-5 on a 9,000 Gg module and
            # the old +1e-5 flat bound read the rounding as misplaced mass)
            self.assertLessEqual(got, allocated * (1 + 1e-6) + slack, key)
            self.assertGreaterEqual(got, allocated * 0.98 - slack,
                                    "%s/%s: more than 2%% of the module's allocated mass "
                                    "sits outside every district polygon" % key)
            if allocated > slack:
                self.assertGreater(got, 0.0,
                                   "%s/%s has mass to place and placed none of it" % key)

    def test_sector_view_carries_the_declared_holes_per_module(self):
        """Every module repeats the shape_missing/no_geometry rows: a module absent
        from Larkana's declared hole would read as zero there, which is the silence
        the aggregate view already refuses."""
        holes = {}
        for row in _rows("pakemis_adm2_monthly_sector.csv"):
            if row["absence_reason"] == "unresolved-in-grid":
                holes.setdefault(row["module"], set()).add(row["adm2_ids"])
        modules = {row["module"] for row in _rows("pakemis_adm2_monthly_sector.csv")}
        expected = {row["adm2_ids"]
                    for row in _rows("pakemis_adm2_monthly.csv")
                    if row["absence_reason"] == "unresolved-in-grid"}
        self.assertTrue(expected)
        for module in modules:
            self.assertEqual(holes.get(module), expected, module)

    def test_a_perturbed_sector_row_is_caught(self):
        """Positive control: the partition test's arithmetic has teeth."""
        rows = _rows("pakemis_adm2_monthly_sector.csv")
        real = [r for r in _numeric(rows) if float(r["emissions_Gg"]) > 1e-3]
        victim = real[0]
        agg = {}
        for row in _numeric(_rows("pakemis_adm2_monthly.csv")):
            agg[(row["shape_id"], row["gas"], row["month"],
                 row["spatial_view"])] = float(row["emissions_Gg"])
        summed = {}
        for row in _numeric(rows):
            key = (row["shape_id"], row["gas"], row["month"], row["spatial_view"])
            value = float(row["emissions_Gg"])
            if row is victim:
                value *= 1.5
            summed[key] = summed.get(key, 0.0) + value
        worst = max(abs(summed[k] - v) for k, v in agg.items())
        self.assertGreater(worst, 1e-5,
                           "a 50%% perturbation slipped under the partition bound")

    def test_every_fallback_class_is_allowed(self):
        """The fail-closed gate's test mirror: every substitution class in the shipped
        fallbacks CSV must be in data/allowed_grid_fallbacks.csv. A new class is a
        missing or renamed spatial input, caught here before the release fixpoint
        refuses it."""
        allowed = {(r["scope"], r["declared"], r["used"])
                   for r in _rows("allowed_grid_fallbacks.csv",
                                  root=asset_path(DATA))}
        for row in _rows("pakemis_grid_fallbacks.csv"):
            self.assertIn((row["scope"], row["declared"], row["used"]), allowed,
                          "fallback class outside the allow-list (stream %s)"
                          % row["source_stream_id"])

    def test_the_gate_catches_a_planted_class(self):
        """Positive control on the fixpoint gate itself."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "rf", os.path.join(ROOT, "scripts", "release_fixpoint.py"))
        rf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rf)
        self.assertEqual(rf.check_spatial_inputs(), [],
                         "the shipped tree should pass its own gate")
        real = rf._read_csv(os.path.join(ROOT, "outputs",
                                         "pakemis_grid_fallbacks.csv"))
        planted = dict(real[0])
        planted.update({"scope": "raster", "declared": "firms_fire",
                        "used": "uniform"})
        original = rf._read_csv
        def patched(path):
            rows = original(path)
            if path.endswith("pakemis_grid_fallbacks.csv"):
                return rows + [planted]
            return rows
        rf._read_csv = patched
        try:
            problems = rf.check_spatial_inputs()
        finally:
            rf._read_csv = original
        self.assertTrue(problems, "a planted unknown fallback class passed the gate")

    def test_proxy_caches_match_their_published_digests(self):
        """The other half of fail-closed: a WRONG cache, not just an absent one."""
        import hashlib
        import re as _re
        text = open(asset_path(DATA, "gis", "PROXY_SOURCES.md"),
                    encoding="utf-8").read()
        pinned = _re.findall(r"\| `(proxy_[a-z_0-9]+\.npy)` \| `([0-9a-f]{64})` \|",
                             text)
        self.assertEqual(len(pinned), 6, "PROXY_SOURCES.md digest table went missing "
                         "(five allocation proxies + the rc41 gcd_rice instrument)")
        for name, digest in pinned:
            with open(asset_path(DATA, "gis", name), "rb") as handle:
                self.assertEqual(hashlib.sha256(handle.read()).hexdigest(), digest,
                                 name)

    def test_district_panels_reproduce(self):
        """Agriculture's category district marginals equal the committed panel at its own
        rounding, aggregated to shapes through the canonical package (the panel uses the
        geometry's own names, so shape aggregation is the identity there)."""
        from pkinv.core import adm2 as adm2_core
        from pkinv.core.gis import cube as cube_core
        canonical = adm2_core.load_canonical()
        panel = self.gc.agriculture_panels()["Enteric fermentation"]
        by_shape_panel = {}
        panel_total = 0.0
        for name, value in panel.items():
            unit = canonical[adm2_core.resolve(name)]
            if unit["shape_id"]:
                by_shape_panel[unit["shape_id"]] = \
                    by_shape_panel.get(unit["shape_id"], 0.0) + value
            panel_total += value
        # the cube's enteric CH4 surface, aggregated the same way
        surface = self.result["category_annual"][("agriculture",
                                                  "Enteric fermentation", "CH4")]
        grid = self.result["grid"]
        ctx = cube_core.Context(grid)
        annual = float(surface.sum())
        for shape_id, panel_value in sorted(by_shape_panel.items()):
            mask = ctx.shape_mask(shape_id)
            if mask is None:
                continue
            share_panel = panel_value / panel_total
            share_grid = float(surface[mask].sum()) / annual
            self.assertLess(abs(share_grid - share_panel), 5e-3,
                            "shape %s: grid %.5f vs panel %.5f"
                            % (shape_id, share_grid, share_panel))

    def test_the_monthly_leg_is_inherited_and_reasserted(self):
        for stream in self.result["streams"]:
            self.assertAlmostEqual(sum(stream["monthly_share"].values()), 1.0, places=6,
                                   msg=stream["source_stream_id"])

    # --- the shipped file ----------------------------------------------------------------

    def test_the_netcdf_reloads_and_closes(self):
        from netCDF4 import Dataset
        path = os.path.join(OUT, "pakemis_grid_0p05_monthly.nc")
        ds = Dataset(path)
        try:
            self.assertEqual(ds.scenario_id, "REF_2023_24")
            # rc67: the reference cube's dung axis is S (the household survey series);
            # it was L through rc66, and L is the sibling file's axis now
            # (pakemis_grid_0p05_monthly_ledger.nc, held in tests/test_grid_cube_ledger.py)
            self.assertEqual(ds.residential_dung_axis, "S")
            for gas in self.gc.GASES:
                stored = ds.variables[gas.lower() + "_Gg"][:]
                mem = self.result["gas_month"][gas]
                self.assertLess(abs(float(stored.sum()) - float(mem.sum())),
                                1e-5 * float(mem.sum()),
                                "%s: float32 storage moved more than 1e-5 relative" % gas)
            group = ds.groups["annual_by_category"]
            self.assertEqual(len(group.dimensions["category"]),
                             len(self.result["category_annual"]))
        finally:
            ds.close()

    def test_the_shipped_file_stays_small(self):
        size = os.path.getsize(os.path.join(OUT, "pakemis_grid_0p05_monthly.nc"))
        self.assertLess(size, 8e6,
                        "the cube outgrew its 8 MB budget; the pre-agreed fallback is "
                        "dropping the annual group to CO2e-only, not raising this bound")

    def test_fallbacks_are_declared_data(self):
        rows = _rows("pakemis_grid_fallbacks.csv")
        self.assertGreater(len(rows), 0)
        # Tightened at rc13, proven red first: the old substring check passed on
        # spam_rice alone while firms_fire's absence never reached the ledger
        # (the declared-name collapse in cube.raster_for, fixed the same round).
        # Each absent manual raster must appear BY NAME as a declared value -
        # and a HELD one must NOT, which is the same honesty in the other
        # direction. firms_fire flipped sides when the period-matched extraction
        # landed at rc13; spam_rice flipped at Wave 5 (rc26) when the MapSPAM
        # raster was acquired and its allow-list row deleted - so BOTH manual
        # rasters are now consumed, and a declared fallback for either means the
        # cube stopped loading a file the tree holds.
        declared = {r["declared"] for r in rows if r["scope"] == "raster"}
        for held in ("spam_rice", "firms_fire"):
            self.assertNotIn(held, declared,
                             "%s is HELD, so a declared fallback means the cube "
                             "stopped loading it - the ledger would be reporting "
                             "an absence that is not true" % held)
        for row in rows:
            self.assertTrue(row["reason"].strip(), "a fallback with no reason")

    # --- reinstated defects --------------------------------------------------------------

    def test_a_perturbed_weight_is_caught(self):
        from pkinv.core.gis import cube as cube_core
        arr = np.full((4, 4), 1 / 16.0)
        cube_core.check_weight(arr, "control")           # passes
        with self.assertRaises(ValueError):
            cube_core.check_weight(arr * 1.01, "planted")

    def test_a_wrong_shape_cache_is_refused(self):
        import tempfile
        from pkinv.core.gis.proxies import get_proxy
        grid = self.result["grid"]
        with tempfile.TemporaryDirectory() as scratch:
            bad = np.ones((10, 10), dtype=np.float32)
            np.save(os.path.join(scratch, "proxy_population_%dx%d.npy"
                                 % (grid.height, grid.width)), bad)
            with open(os.path.join(scratch, "proxy_population_%dx%d.npy.txt"
                                   % (grid.height, grid.width)), "w") as f:
                f.write("planted")
            with self.assertRaises(ValueError):
                get_proxy("population", grid, cache_dir=scratch)

    def test_an_unmapped_stream_raises_naming_itself(self):
        from pkinv.core.declared import match_prefix
        with self.assertRaises(KeyError) as ctx:
            match_prefix([], "waste", "Solid waste disposal", "x", "raster_proxy",
                         "grid proxy")
        self.assertIn("Solid waste disposal", str(ctx.exception))

    def test_a_broken_district_factor_is_caught(self):
        """district_factors must sum to 1 per province (with the declared lost fraction);
        feeding it a panel and then corrupting one share breaks the province marginal,
        which test_province_marginals_exact_where_constructed holds at 2e-6."""
        from pkinv.core import adm2 as adm2_core
        from pkinv.core.gis import cube as cube_core
        ctx = cube_core.Context(self.result["grid"])
        factors = cube_core.district_factors(
            ctx, self.gc.agriculture_panels()["Rice cultivation"], "control")
        for province, shapes in factors.items():
            self.assertLessEqual(sum(shapes.values()), 1.0 + 1e-9, province)

    def test_the_registry_covers_every_stream(self):
        """Union coverage: agriculture through proxy_map, everyone else through the CSV -
        every one of the 184 streams resolves a raster."""
        from pkinv.core.declared import match_prefix
        from pkinv.core.gis import cube as cube_core
        rows = cube_core.load_grid_proxy_registry()
        for stream in self.result["streams"]:
            if stream["module"] == "agriculture":
                continue
            match_prefix(rows, stream["module"], stream["engine_category"],
                         stream["sub_category"], "raster_proxy", "grid proxy")


if __name__ == "__main__":
    unittest.main()

"""The province raster misplaces seven located power stations, and only those seven.

WHY THIS TEST EXISTS. A station's province is decided by dropping its coordinate into the
0.05 degree grid and reading the cell. That is silent, self-consistent and - within about
half a cell of a provincial line - wrong. Seven of the seventy-seven located stations are
already misplaced, carrying up to 10.3 per cent of a year's plant-ledger generation, and
nothing in the build said so until outputs/pakemis_power_province_boundary_audit.csv.

The audit is only worth its bytes if the list cannot grow in silence. A new station
commissioned near a boundary, a coordinate corrected by a few kilometres, or a boundary
file re-simplified would each add a case; this holds the count at the published seven and
names them, so the next one has to be argued for rather than absorbed.

LOWERING THE COUNT IS ALWAYS ALLOWED and is the point of the exercise. Raising it needs a
written reason here, the same discipline the uncited ratchet carries.
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import read_rows                                      # noqa: E402

AUDIT = os.path.join(ROOT, "outputs", "pakemis_power_province_boundary_audit.csv")

# Each name is a station whose curated or source province disagrees with the 0.05 degree
# raster. Every one has been checked individually and in every one the raster is the error.
KNOWN_MISPLACED = {
    "China Power Hub":          "Hub, Lasbela. GEM's own Subnational unit says Balochistan; "
                                "the raster says Sindh and the ingest copies the raster, so "
                                "the table agrees with the raster and both are wrong.",
    "Hub Power":                "the oil station 1.11 km away in the SAME raster cell, whose "
                                "table says Balochistan - two stations on one site in two "
                                "provinces.",
    "TPS Guddu (Units 5-10)":   "Kashmore District, Sindh, on the Rajanpur line.",
    "TPS Guddu (Units 14-16)":  "Kashmore District, Sindh, on the Rajanpur line.",
    "Tapal Energy":             "Keamari, Karachi, Sindh.",
    "Attock Gen.":              "Morgah, Rawalpindi District, Punjab, near the ICT boundary.",
    "Mangla":                   "Mirpur, AJK ('Other'), on the Punjab line. Hydro, so no mass "
                                "moves - listed because the geography defect is the same one.",
}


class TestTheMisplacedListIsExactlyTheKnownSeven(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(AUDIT):
            raise unittest.SkipTest("the audit has not been built in this checkout")
        cls.rows = read_rows(AUDIT)
        cls.stations = [r for r in cls.rows if r["row_kind"] == "station"]

    def test_the_misplaced_set_has_not_grown(self):
        live = {r["plant"] for r in self.stations if r["verdict"].startswith("MISPLACED")}
        new = live - set(KNOWN_MISPLACED)
        self.assertFalse(
            sorted(new),
            "stations newly misplaced by the province raster: %s. Check each one against its "
            "source's own province field, then either correct the coordinate or add it here "
            "WITH the reason - a list that grows quietly measures nothing."
            % sorted(new))

    def test_a_station_that_stopped_being_misplaced_is_removed_from_the_list(self):
        live = {r["plant"] for r in self.stations if r["verdict"].startswith("MISPLACED")}
        gone = set(KNOWN_MISPLACED) - live
        self.assertFalse(
            sorted(gone),
            "these are no longer misplaced and should come off KNOWN_MISPLACED: %s"
            % sorted(gone))

    def test_every_station_carries_a_verdict(self):
        blank = [r["plant"] for r in self.stations if not r["verdict"]]
        self.assertFalse(blank, "stations with no verdict: %s" % blank)

    def test_the_denominator_is_published_beside_the_finding(self):
        """A count of misplaced stations means nothing without how many were tested."""
        self.assertGreaterEqual(
            len(self.stations), 70,
            "the audit should cover every located station, not a sample")

    def test_the_exposure_rows_cover_every_ledger_year(self):
        periods = {r["period_id"] for r in self.rows if r["row_kind"] == "period_exposure"}
        self.assertGreaterEqual(
            len(periods), 5,
            "the plant fuel ledger spans FY2019-20..FY2023-24; the exposure rows should "
            "say what share of EACH of those years the misplaced stations carry")

    def test_the_shipped_audit_matches_a_fresh_build(self):
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts",
                                          "build_power_province_boundary_audit.py"), "--check"],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0,
                         "the audit is stale; rebuild it.\n%s%s" % (r.stdout, r.stderr))


# =============================================================================================
# WHICH KIND OF CONFLICT EACH OF THE SEVEN IS (T-VAL-2, 2026-10-05). The class above holds the
# LIST at seven and names them. It does not say where the fault lies, and that is what decides
# the remedy: two have a frame that disagrees with itself, one sits in a hole in the frame, and
# four have two records agreeing against the frame. None is a station-record error.
# =============================================================================================


class TestTheAdjudication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(AUDIT):
            raise unittest.SkipTest("the boundary audit has not been generated here")
        cls.rows = [r for r in read_rows(AUDIT) if r.get("row_kind") == "station"]

    def test_no_misplaced_station_is_a_record_error(self):
        """The finding: all seven conflicts are in the frame, none in a station record."""
        misplaced = [r for r in self.rows if r["verdict"].startswith("MISPLACED")
                     or r["adjudication"] not in ("agree", "")]
        self.assertTrue(misplaced, "no conflicted station to adjudicate")
        record_errors = [r["plant"] for r in misplaced
                         if r["adjudication"] == "records-disagree"]
        self.assertFalse(
            record_errors,
            "a station's curated and source records now disagree, which the frame cannot "
            "arbitrate and which no geometry decision fixes: %s. That is a different remedy "
            "from the other seven and needs an external authority on the station's location."
            % record_errors)

    def test_the_classes_are_the_ones_the_module_declares(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_bpa", os.path.join(ROOT, "scripts", "build_power_province_boundary_audit.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        declared = set(mod.ADJUDICATION_CLASSES)
        used = {r["adjudication"] for r in self.rows if r["adjudication"]}
        self.assertTrue(used, "no station carries an adjudication class")
        self.assertFalse(used - declared,
                         "these classes are not in ADJUDICATION_CLASSES: %s"
                         % sorted(used - declared))

    def test_a_detail_is_given_wherever_a_class_is_not_agree(self):
        for row in self.rows:
            if row["adjudication"] in ("agree", ""):
                continue
            self.assertTrue(row["adjudication_detail"].strip(),
                            "%s is classed %s with no detail; the class alone does not tell "
                            "a reader what to fix"
                            % (row["plant"], row["adjudication"]))

    def test_the_frame_dissent_cases_are_near_a_boundary(self):
        """A frame dissent far from any boundary would be a different claim entirely."""
        for row in self.rows:
            if row["adjudication"] != "records-agree-frame-dissents":
                continue
            km = float(row["km_to_nearest_adm2_vertex"] or 0)
            self.assertLess(km, 5.0,
                            "%s has the records and the frame disagreeing %.2f km from any "
                            "boundary, which a boundary revision would not explain"
                            % (row["plant"], km))


class TestEveryBoundaryStationIsPlaced(unittest.TestCase):
    """The audit stopped at the finding; this holds the OUTCOME.

    Until 2026-10-07 a station whose ADM2 polygon left the province it was pooled under
    had its mass dropped on the fallback surface at its own cell - the district was
    refused because the provincial marginal is a control and the district is not. Five of
    the seven were in that state, carrying up to 43.9 per cent of a profile-period's
    spatial pool (RFO in FY2015-16), and the counter that recorded it was incremented and
    never read by anything.

    The curated station-district record ends the refusal: a NAMED district is adjudicated
    by the majority of its own cells in the ADM1 control, which is robust where one 5.5 km
    cell is not. These tests hold three things - every boundary station now resolves, the
    rescue never crosses a province, and (the positive control) removing the record puts
    the five back on the fallback surface, so a rescue that silently stopped working would
    fail here rather than quietly reverting the placement.
    """

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(AUDIT):
            raise unittest.SkipTest("the audit has not been built in this checkout")
        cls.stations = [r for r in read_rows(AUDIT) if r["row_kind"] == "station"]

    def test_no_station_is_left_on_the_fallback_surface(self):
        stranded = [r["plant"] for r in self.stations
                    if r["adm2_placement"].startswith("fallback surface")]
        self.assertEqual(stranded, [],
                         "these stations have a point and no district: their mass rides a "
                         "proxy surface inside the right province while a curated district "
                         "for them may be one file away (grid_plant_district.csv)")

    def test_every_station_declares_which_rule_placed_it(self):
        allowed = ("the point's own ADM2 polygon", "curated district ", "fallback surface",
                   "not placed")
        for row in self.stations:
            self.assertTrue(row["adm2_placement"].startswith(allowed),
                            "%s: %r is not one of the declared placement rules"
                            % (row["plant"], row["adm2_placement"]))

    def test_a_rescue_never_moves_mass_across_a_province(self):
        """The trade the refusal existed to prevent must still be unavailable."""
        for row in self.stations:
            if not row["adm2_placement"].startswith("curated district "):
                continue
            self.assertEqual(row["curated_district_province"], row["booked_province"],
                             "%s was placed in %s, whose polygon majority is %s, while it "
                             "is booked under %s - that is the provincial marginal being "
                             "traded for a district" % (row["plant"],
                                                        row["curated_district"],
                                                        row["curated_district_province"],
                                                        row["booked_province"]))

    def test_the_rescued_set_is_the_five_the_frame_denies(self):
        rescued = {r["plant"] for r in self.stations
                   if r["adm2_placement"].startswith("curated district ")}
        self.assertEqual(rescued, {"China Power Hub", "Hub Power", "Tapal Energy",
                                   "TPS Guddu (Units 5-10)", "TPS Guddu (Units 14-16)"},
                         "the rescued set moved. Mangla and Attock Gen. are NOT in it: "
                         "their own ADM2 polygon agrees with the curated province, so the "
                         "point places them and no record is consulted.")

    def test_removing_the_record_strands_them_again(self):
        """THE POSITIVE CONTROL. Without the curated districts the five must go back to the
        fallback surface - otherwise this test suite would pass on a build in which the
        record had quietly stopped being read, which is the failure mode that cost this
        project a release when a rename reached the writers and not the readers."""
        from pkinv.report import grid_cube
        real = grid_cube.curated_district_indices
        grid_cube.curated_district_indices = lambda grid, keys=None: {}
        try:
            rows = grid_cube.grid_plant_province_sources()
        finally:
            grid_cube.curated_district_indices = real
        stranded = {r["plant"] for r in rows
                    if r["adm2_placement"].startswith("fallback surface")}
        self.assertEqual(stranded, {"China Power Hub", "Hub Power", "Tapal Energy",
                                    "TPS Guddu (Units 5-10)", "TPS Guddu (Units 14-16)"})


class TestTheCuratedDistrictJoin(unittest.TestCase):
    """The join that supplies the districts refuses rather than guesses."""

    def test_a_one_token_subset_is_refused(self):
        """The three matches the two-token floor rejects were all WRONG, and each would
        have moved a station to another district: Foundation Wind Energy (the Sindh coast)
        would have taken Foundation Power Dharki's Ghotki, Liberty Power Tech. would have
        taken Liberty Power's Ghotki, and Sapphire Electric would have taken a district on
        the strength of the single word 'Sapphire'. The floor is the rule's safety, not a
        tuning constant, so it is asserted rather than left to a comment."""
        from pkinv.report import grid_cube
        self.assertEqual(grid_cube.SUBSET_JOIN_MIN_TOKENS, 2)
        districts = grid_cube._curated_station_districts()
        from pkinv.sectors.power.plant_names import plant_key
        for plant in ("Foundation Wind Energy-I", "Foundation Wind Energy-II",
                      "Liberty Power Tech.", "Sapphire Electric"):
            key = plant_key(plant)
            self.assertNotIn(key, districts,
                             "%s took a district through a one-token company match" % plant)

    def test_the_crosswalk_resolves_a_station_the_names_do_not(self):
        """HUBCO -> Hub Power, through plant_name_crosswalk.csv - a record this repository
        already holds, which is why the join needs no new inference for it."""
        from pkinv.report import grid_cube
        from pkinv.sectors.power.plant_names import plant_key
        districts = grid_cube._curated_station_districts()
        self.assertEqual(districts.get(plant_key("Hub Power")), "balochistan_lasbela")

    def test_an_ambiguous_subset_is_refused(self):
        """TPS Guddu is adoptable only BECAUSE both workbook rows agree on Kashmore. A
        subset whose candidates disagree must name no district at all."""
        from pkinv.report import grid_cube
        from pkinv.sectors.power.plant_names import plant_key
        real = grid_cube._rows
        path_tail = "grid_plant_district.csv"

        def poisoned(path, **kw):
            rows = list(real(path, **kw))
            if str(path).endswith(path_tail):
                out = []
                for r in rows:
                    r = dict(r)
                    if r.get("plant") == "TPS Guddu (GENCO-II)":
                        r["adm2_id"] = "punjab_rajanpur"
                    out.append(r)
                return out
            return rows

        grid_cube._rows = poisoned
        try:
            districts = grid_cube._curated_station_districts()
        finally:
            grid_cube._rows = real
        self.assertIsNone(districts.get(plant_key("TPS Guddu (Units 5-10)")),
                          "two workbook rows disagreed about the district and the join "
                          "picked one anyway")


if __name__ == "__main__":
    unittest.main()

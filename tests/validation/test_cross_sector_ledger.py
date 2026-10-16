"""The cross-sector ledger map resolves, and every ledger closes.

data/cross_sector_ledger_map.csv projects the sector ledgers into one schema by POINTING at
cells, never by restating them. Each pointer must resolve to exactly one row; and per
(ledger, configuration) the control must equal the transfers plus the unresolved remainder to
within the ledgers' own printed precision. Inside a built package the published registry
view is additionally recomputed from the pointers and must agree.
"""

from pkinv.assets import asset_path
import csv
import os
import unittest
from fnmatch import fnmatchcase
from pkinv.core import configurations

from _support import ROOT
from validation._package import IN_PACKAGE, data_rows

MAP = asset_path(ROOT, "data", "cross_sector_ledger_map.csv")
TOL = 2e-4          # the ledgers print four decimals; two half-ulps of rounding


def parse_key(text):
    return dict(part.split("=", 1) for part in text.split(";"))


def resolve(row):
    rows = data_rows(asset_path(ROOT, row["source_file"]))
    key = parse_key(row["row_key"])
    hits = [r for r in rows if all(r.get(c) == v for c, v in key.items())]
    return hits


class TestTheLedgerMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.map = data_rows(MAP)

    def test_every_pointer_resolves_to_exactly_one_row(self):
        bad = []
        for row in self.map:
            hits = resolve(row)
            if len(hits) != 1:
                bad.append("%s/%s -> %d rows" % (row["ledger_id"], row["row_id"], len(hits)))
            elif row["value_column"] not in hits[0]:
                bad.append("%s/%s -> no column %s" % (row["ledger_id"], row["row_id"], row["value_column"]))
        self.assertEqual(bad, [])

    def test_every_ledger_closes_per_configuration(self):
        sums = {}
        for row in self.map:
            if row["kind"] == "memo":
                # Explicitly unquantified retail claimants are descriptive and
                # are already inside a counted flow; they never enter closure.
                continue
            value = resolve(row)[0][row["value_column"]]
            self.assertNotIn(value, ("", None), "unknown ledger mass is not zero: " + row["row_id"])
            x = float(value)
            for cfg in row["configuration_id"].split(";"):
                d = sums.setdefault((row["ledger_id"], cfg), {"control": 0.0, "transfer": 0.0,
                                                               "unresolved": 0.0, "memo": 0.0})
                d[row["kind"]] += x
        open_ledgers = []
        for (ledger, cfg), d in sorted(sums.items()):
            residual = d["control"] - d["transfer"] - d["unresolved"]
            scale = max(abs(d["control"]), 1.0)
            if abs(residual) > TOL * max(1.0, scale / 100.0) and abs(residual) > TOL:
                open_ledgers.append("%s/%s residual %.6f" % (ledger, cfg, residual))
        self.assertEqual(open_ledgers, [], "ledgers that do not close")

    def test_every_resolved_transfer_lands_in_an_estimated_category(self):
        """rc42 (the twentieth review's P-4). A transfer marked resolved books its mass into
        its destination stream; if that stream's IPCC category is NE the mass is booked into
        a category that emits nothing - the fertiliser feedstock case, 7,813.8 million m3
        removed from every combustion module and landing in an unestimated 2.B.1. Such a
        row is unresolved, and says so."""
        streams = {r["source_stream_id"]: r["ipcc_code"]
                   for r in data_rows(os.path.join(ROOT, "outputs", "pakemis_source_streams.csv"))}
        # ALL the notation keys a code carries, not the last one read. Under IPCC 2006 a code
        # can hold more than one completeness row - 3.C.4 carries the estimated direct soils
        # N2O and the unestimated FSOM term, 3.C.5 the indirect N2O and the NH3 precursor - so
        # a dict comprehension here is last-write-wins and reported 3.C.4 as NE on the
        # strength of its second row. A transfer lands in an estimated category if ANY row of
        # that code is estimated, which is the question this test is actually asking.
        notation = {}
        for r in data_rows(os.path.join(ROOT, "outputs", "completeness.csv")):
            notation.setdefault(r["code"], set()).add(r["notation_key"])
        bad = []
        for row in self.map:
            if row["kind"] != "transfer" or not row["status"].startswith("resolved"):
                continue
            dest = row["destination_source_stream"]
            if not dest or dest == "-":
                continue
            codes = {code for sid, code in streams.items() if fnmatchcase(sid, dest)}
            if not codes:
                bad.append("%s/%s -> no estimated stream matching %s"
                           % (row["ledger_id"], row["row_id"], dest))
                continue
            for code in codes:
                # IE is a category reported elsewhere by design (the waste fate ledger's
                # collected-to-disposal row lands in one); only NE/NO/NA book mass nowhere
                keys = notation.get(code, {"E"})
                if not keys & {"E", "IE"}:
                    bad.append("%s/%s -> %s (%s is %s)"
                               % (row["ledger_id"], row["row_id"], dest, code,
                                  "/".join(sorted(keys))))
        self.assertEqual(bad, [], "resolved transfers into a category that is not estimated")

    def test_all_four_configurations_have_each_ledger(self):
        support = {(r["ledger_id"], cfg) for r in self.map for cfg in r["configuration_id"].split(";")}
        self.assertEqual(support, {(ledger, cfg) for ledger in self.LEDGERS for cfg in configurations.ALL})
        households = [r for r in self.map if r["ledger_id"] == "dung_transfer"
                      and r["row_id"].endswith("_households")]
        for row in households:
            source_basis = parse_key(row["row_key"])["configuration"]
            expected = {cfg for cfg in configurations.ALL
                        if configurations.dung_basis(cfg) == ("survey" if source_basis == "S" else "ledger")}
            self.assertEqual(set(row["configuration_id"].split(";")), expected)

    def test_diverted_nitrogen_is_not_an_observed_combustion_transfer(self):
        row = next(r for r in self.map if r["ledger_id"] == "nitrogen_excretion_ledger"
                   and r["row_id"] == "to_dung_fuel")
        self.assertEqual((row["kind"], row["status"]), ("unresolved", "unresolved"))
        self.assertEqual((row["destination_sector"], row["destination_source_stream"]), ("-", "-"))
        source = resolve(row)
        self.assertEqual(len(source), 1)
        self.assertIn("destinations unresolved", source[0]["flow"])
        self.assertGreater(float(source[0][row["value_column"]]), 0)

    def test_fertiliser_gas_is_two_resolved_transfers_now_that_ammonia_is_estimated(self):
        """Through rc66 one row, `fertilizer_feedstock`, was held unresolved "while ammonia
        is NE". 2.B.1 has been estimated since rc52, so the condition the row named was met
        fourteen releases before the row was changed. rc67 carries fertiliser gas as its two
        flows, both landing in 2.B.1, and only the burned one in the post-meter leak base."""
        rows = {r["row_id"]: r for r in self.map}
        for row_id in ("fertilizer_feedstock", "fertilizer_process_fuel"):
            self.assertEqual((rows[row_id]["kind"], rows[row_id]["status"]),
                             ("transfer", "resolved"), row_id)
        self.assertIn("outside the post-meter leak base",
                      rows["fertilizer_feedstock"]["origin_emissions_effect"])
        self.assertEqual(rows["fertilizer_process_fuel"]["origin_emissions_effect"],
                         "in the post-meter leak base")

    def test_every_map_row_is_one_of_four_kinds(self):
        self.assertEqual({r["kind"] for r in self.map} - {"control", "transfer", "unresolved", "memo"}, set())

    LEDGERS = ("dung_transfer", "crop_residue_transfer", "delivered_gas_combustion_fugitive_ledger",
               "generator_petrol_transfer", "road_diesel_offroad_partition", "waste_fate_ledger",
               "fertiliser_feedstock_combustion_urea_ledger", "nitrogen_excretion_ledger")

    def test_the_eight_ledgers_are_exactly_the_set(self):
        """rc41: assertIn over seven names let an eighth ledger (the nitrogen excretion
        ledger) ride unnamed and would let a ninth vanish unnoticed; the set is exact."""
        self.assertEqual({r["ledger_id"] for r in self.map}, set(self.LEDGERS))


class TestThePublishedRegistryView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not IN_PACKAGE:
            raise unittest.SkipTest("only inside a built validation package")
        cls.registry = data_rows(os.path.join(ROOT, "outputs", "cross_sector",
                                              "cross_sector_closure_registry.csv"))
        cls.map = data_rows(MAP)

    def test_the_view_has_one_row_per_map_row_with_the_pointed_value(self):
        by_id = {(r["ledger_id"], r["row_id"]): r for r in self.registry}
        self.assertEqual(len(by_id), len(self.map))
        for row in self.map:
            value = resolve(row)[0][row["value_column"]]
            got = by_id[(row["ledger_id"], row["row_id"])]["activity_mass_or_energy"]
            self.assertEqual(got, value, (row["ledger_id"], row["row_id"]))


if __name__ == "__main__":
    unittest.main()

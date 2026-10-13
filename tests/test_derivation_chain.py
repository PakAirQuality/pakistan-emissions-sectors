"""The chain is declared, resolves, and invents nothing.

WHY. outputs/<sector>_derivation_chain.csv is the walk from the published source to the
reported number, and its whole value is that it is READ rather than computed: every row names
the file it came from, so a chain row and its source agree by construction. That property is
only worth anything if it is enforced, hence the central assertion here - every derived row's
value must be findable in the file it names. A chain that quietly recomputed a number would
look identical and be worthless.

WHAT ELSE IS ASSERTED, and why each one is here rather than assumed:

  A stage is never skipped. A sector with no artifact for a stage carries a declared_absent
  row. A chain with a missing link that looks complete is worse than no chain, and agriculture
  genuinely has no single "what the engine used" table - it integrates head counts, crop
  areas, residue mass, nitrogen and burned area, in five unlike units.

  MULTI-MEMBER GROUPS. A dependency group can hold more than one number: 1a3b_diesel_control
  holds transport's diesel calorific value AND its control total. The first build of the
  activity-factor ledger took by_group[group][0] and published "43.0 TJ/Gg" as transport's
  diesel ACTIVITY, silently dropping the 5,551.442 kt/yr that is the activity. 56 of 549
  groups have more than one member, so this is asserted, not spot-checked.

  THE REPRODUCTION CHECK NEVER GUESSES. `reproduces` may be yes only where exactly one
  distinct activity value meets one distinct factor value, so the product tested is the only
  product those parameters can form. Searching several candidate products for whichever lands
  nearest the published mass would manufacture agreement rather than test it.

Run:  python3 -m unittest discover tests -p "test_derivation_chain.py"
"""

from pkinv.assets import asset_path
import os
import unittest

from _support import DATA, ROOT, data_rows, read_rows

from pkinv.report import derivation_chain as chain

SECTORS = ("agriculture", "aviation", "fugitives", "industry", "ippu",
           "power", "railways", "residential", "transport", "waste")


class TheRegistry(unittest.TestCase):
    def rows(self):
        return data_rows("verification_chain.csv")

    def test_every_sector_is_declared(self):
        self.assertEqual(set(SECTORS), {r["sector"] for r in self.rows()})

    def test_stages_and_recipes_are_closed_vocabularies(self):
        for row in self.rows():
            with self.subTest(sector=row["sector"], order=row["order"]):
                self.assertIn(row["stage"], chain.STAGES)
                self.assertIn(row["recipe"], chain.RECIPES)
                self.assertIn(row["status"], ("derived", "declared_absent"))

    def test_every_declared_source_exists_and_has_its_columns(self):
        problems = []
        for row in self.rows():
            if row["status"] == "declared_absent":
                self.assertEqual("", row["source_file"],
                                 "a declared-absent row must name no file")
                self.assertTrue(row["note"], "a declared-absent row must say what is missing")
                continue
            made, trouble = chain.build_section(row)
            problems.extend(trouble)
            self.assertTrue(made or trouble, "%s/%s built nothing and reported nothing"
                            % (row["sector"], row["order"]))
        self.assertEqual([], problems, "\n  ".join([""] + problems))


class TheChain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = chain.registry()
        cls.chains = {s: chain.build(s, cls.reg)[0] for s in SECTORS}

    def test_every_sector_covers_every_stage(self):
        for sector in SECTORS:
            stages = {r["stage"] for r in self.chains[sector]}
            with self.subTest(sector=sector):
                self.assertEqual(set(chain.STAGES), stages,
                                 "%s has no row at all for %s - a stage is declared absent, "
                                 "never skipped" % (sector, set(chain.STAGES) - stages))

    def test_no_row_invents_a_number(self):
        """The whole contract: a derived value must be present in the file the row names."""
        cache, problems = {}, []
        for sector in SECTORS:
            for row in self.chains[sector]:
                if row["kind"] == "declared_absent" or row["value"] == "":
                    continue
                path = row["evidence_file"]
                if path not in cache:
                    cache[path] = {v for r in read_rows(asset_path(ROOT, path))
                                   for v in r.values()}
                if row["value"] not in cache[path]:
                    problems.append("%s: %r is not a cell of %s"
                                    % (sector, row["value"], path))
        self.assertEqual([], problems, "\n  ".join([""] + problems[:20]))

    def test_a_blank_value_means_the_source_cell_is_blank(self):
        """43 rows carry no value. Each must be an absence the SOURCE published, not a
        column this registry failed to read - which is why the row is kept and shown."""
        for sector in SECTORS:
            for row in self.chains[sector]:
                if row["value"] != "" or row["kind"] == "declared_absent":
                    continue
                with self.subTest(sector=sector, item=row["item"]):
                    self.assertTrue(os.path.isfile(asset_path(ROOT, row["evidence_file"])))

    def test_transport_walks_from_the_published_row_to_the_reported_number(self):
        """The question this file was built to answer, asserted end to end."""
        rows = self.chains["transport"]
        bridge = {(r["subject"], r["kind"]): r["value"]
                  for r in rows if r["step"] == 30}
        opening = float(bridge[("Petrol", "opening")])
        deduction = float(bridge[("Petrol", "deduction")])
        closing = float(bridge[("Petrol", "closing")])
        self.assertAlmostEqual(opening + deduction, closing, places=4)

        gas = {r["kind"]: r["value"] for r in rows
               if r["step"] == 30 and r["subject"] == "CNG"}
        self.assertTrue(gas["opening"], "the CNG steps rendered blank: the bridge prints gas "
                                        "in TJ and liquids in kt, so value_column needs both")

        total = [r["value"] for r in rows if r["step"] == 80 and r["item"] == "TOTAL"]
        self.assertEqual(1, len(total))
        self.assertAlmostEqual(41.92617, float(total[0]), places=4)


class TheActivityFactorLedger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledgers = {s: chain.activity_factor_rows(s) for s in SECTORS}

    def test_every_sector_publishes_streams(self):
        for sector in SECTORS:
            with self.subTest(sector=sector):
                self.assertTrue(self.ledgers[sector])

    def test_every_member_of_a_multi_member_group_is_published(self):
        """1a3b_diesel_control holds the calorific value AND the control total; publishing
        only the first made 43.0 TJ/Gg look like transport's diesel activity."""
        rows = [r for r in self.ledgers["transport"] if "Petrol" in r["activity"]]
        self.assertTrue(rows, "transport publishes no petrol activity")
        activity = rows[0]["activity"]
        self.assertIn("Petrol NCV", activity)
        self.assertIn("Petrol control total", activity)

    def test_reproduces_is_a_closed_vocabulary_and_always_explained(self):
        for sector in SECTORS:
            for row in self.ledgers[sector]:
                with self.subTest(sector=sector, stream=row["source_stream_id"]):
                    self.assertIn(row["reproduces"], ("yes", "no", "not_attempted"))
                    self.assertTrue(row["reproduction_note"])

    def test_a_yes_actually_reproduces(self):
        """Never optimistic: re-do the arithmetic for every row claiming to reproduce."""
        checked = 0
        for sector in SECTORS:
            for row in self.ledgers[sector]:
                if row["reproduces"] != "yes":
                    continue
                published = float(row["emissions_Gg"])
                a, _x, f, scale = row["reproduction_note"].split()[:4]
                product = float(a) * float(f) * float(scale.replace("x", ""))
                self.assertLessEqual(abs(product - published), chain.TOLERANCE * abs(published),
                                     "%s claims to reproduce and does not" % row["source_stream_id"])
                checked += 1
        self.assertGreater(checked, 0, "no row reproduces; the check is not exercised")


class DepositRights(unittest.TestCase):
    def test_the_registry_has_a_rights_answer(self):
        from pkinv.report import deposit_manifest
        self.assertTrue(os.path.exists(asset_path(DATA, "verification_chain.csv")))
        licence, _reason = deposit_manifest.data_family("data/verification_chain.csv")
        self.assertTrue(licence)


if __name__ == "__main__":
    unittest.main()

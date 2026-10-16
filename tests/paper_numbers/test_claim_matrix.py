"""Current integrated manuscript claims resolve from independent released products.

The rc67 prose registry remains in version control. rc68 checks the actual quantitative
macros used by the maintained article/report, rather than obsolete sentence wording.
"""
import csv
import importlib.util
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

def renderer():
    spec = importlib.util.spec_from_file_location('claim_matrix', ROOT/'scripts/make_claim_matrix.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class TestCurrentManuscriptClaims(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = renderer()
        cls.rows = cls.module.load_registry(str(ROOT))
        cls.resolved = cls.module.build(str(ROOT))

    def test_all_claims_resolve_and_agree_at_printed_precision(self):
        self.assertEqual(len(self.rows), len(self.resolved))
        self.assertTrue(self.rows)
        self.assertEqual(len(self.rows), len({r['claim_id'] for r in self.rows}))
        failures = [(r['claim_id'], r['printed_value'], r['resolved_value']) for r in self.resolved if r['agrees_strict'] != 'yes']
        self.assertEqual(failures, [])

    def test_every_quantitative_macro_used_in_maintained_manuscripts_is_registered(self):
        sections = self.module.Sections(str(ROOT))
        macros = dict(re.findall(r'\\newcommand\{\\(\w+)\}\{([^{}]+)\}', sections.text('paper_national/versions/v3/generated/integrated_facts.tex')))
        visited = set()
        for entry in ('versions/v3/paper.tex', 'versions/v3/technical_supplement.tex',
                      'versions/v1/paper_national.tex', 'versions/v1/supplement.tex'):
            start = ROOT/'paper_national'/entry
            pending = [start]
            while pending:
                path = pending.pop().resolve()
                if path in visited or 'generated' in path.parts:
                    continue
                visited.add(path)
                name = str(path.relative_to(ROOT))
                text = re.sub(r'(?m)^\s*%.*$', '', path.read_text())
                expected = set(re.findall(r'\\(\w+)', text)) & set(macros) - {'PakEmisRelease', 'CoreEndYear'}
                registered = {r['printed_pattern'].split(':',1)[1] for r in self.rows if r['section_file'] == name}
                self.assertEqual(expected, registered, name)
                for included in re.findall(r'\\(?:input|include)\{([^}]+)\}', text):
                    for parent in (start.parent, path.parent):
                        child = parent/included
                        if not child.suffix:
                            child = child.with_suffix('.tex')
                        if child.is_file():
                            pending.append(child)
                            break

    def test_claims_resolve_from_inventory_not_figure_producer(self):
        for row in self.rows:
            self.assertTrue(row['source_pointer'])
            self.assertNotIn('integrated_facts', row['source_pointer'])
            self.assertIn(row['configuration'], ('S_TAN','L_TAN','S_IPCC','L_IPCC'))
        text=' '.join(r['source_pointer'] for r in self.rows)
        for source in ('ghg_configuration_atoms', 'air_annual', 'ghg_conditional', 'air_conditional'):
            self.assertIn(source, text)
        for row in self.rows:
            if 'DungCase' in row['quantity_refs']:
                self.assertIn('air_structural_sensitivities', row['source_pointer'])

    def test_national_aggregate_claims_do_not_assert_source_month_evidence(self):
        aggregates = [r for r in self.rows if r['source_pointer'].startswith(('sum_where:', 'scale:', 'change_pct:'))]
        self.assertTrue(aggregates)
        self.assertEqual({r['evidence_class'] for r in aggregates}, {'estimated-mixed'})
        self.assertIn('paper_AirLatestNHthree', {r['claim_id'] for r in aggregates})

    def test_shipped_claim_records_match_fresh_render(self):
        with tempfile.TemporaryDirectory() as directory:
            self.module.write_all(self.resolved, directory)
            for rel in (self.module.OUT_CSV,self.module.OUT_MD,self.module.OUT_TEX):
                self.assertEqual((ROOT/rel).read_bytes(), (Path(directory)/rel).read_bytes(), rel)

    def test_missing_macro_and_empty_source_do_not_become_zero(self):
        from pkinv.report.claims import resolve_expression
        row=dict(self.rows[0], printed_pattern='macro:AbsentQuantity')
        with self.assertRaises(LookupError):
            self.module.printed_value(row,self.module.Sections(str(ROOT)),())
        with self.assertRaises(AssertionError):
            resolve_expression(str(ROOT),'sum_where:pakemis_ghg_configuration_atoms.csv#period_id=FY2025-26#emission_native_mass')

    def test_printed_precision_does_not_hide_material_disagreement(self):
        self.assertFalse(self.module.compare('444.6','445.6',1,0)[0])
        self.assertTrue(self.module.compare('444.6','444.60775549',1,0)[0])

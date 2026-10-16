"""Every current article plot/table has a verifiable artifact identity."""
import csv
import importlib.util
import json
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[2]

class TestCurrentPaperArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('paper_artifacts',ROOT/'scripts/make_paper_artefacts.py')
        cls.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.module)
        cls.rows=cls.module.read_registry(str(ROOT))
        cls.text=(ROOT/'paper_national/versions/v3/paper.tex').read_text()

    def test_current_figure_set_is_exact(self):
        actual={Path(value).stem for value in re.findall(r'\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}',self.text)}
        registered={r['artefact_id'] for r in self.rows if r['image_file']}
        self.assertEqual(actual,registered)
        self.assertEqual(len(actual),5)

    def test_current_table_set_is_exact(self):
        actual=set()
        for block in re.findall(r'\\begin\{table\*?\}.*?\\end\{table\*?\}',self.text,re.S):
            actual.update(re.findall(r'\\label\{([^}]+)\}',block))
        registered={r['_params']['label'] for r in self.rows if 'label' in r['_params']}
        self.assertEqual(actual,registered)

    def test_shipped_artifact_hashes_match_current_bytes(self):
        shipped={r['artefact_id']:r for r in csv.DictReader((ROOT/'outputs/pakemis_paper_artefact_hashes.csv').open())}
        self.assertEqual(set(shipped),{r['artefact_id'] for r in self.rows})
        for row in self.rows:
            self.assertEqual(shipped[row['artefact_id']]['output_sha256'],self.module.static_hash(str(ROOT),row))
            self.assertNotIn('pending',row['_params'].get('status',''))

    def test_plotted_data_are_independently_checked(self):
        rows=list(csv.DictReader((ROOT/'paper_national/figures/integrated_inputs/figure_value_checks.csv').open()))
        self.assertGreater(len(rows),100)
        self.assertTrue(all(r['agrees']=='yes' for r in rows))

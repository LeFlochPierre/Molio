import copy
import json
from pathlib import Path
import tempfile
import unittest

from cyp_pipeline.benchmark import compare_scores, load_uma, source
from cyp_pipeline.core import ValidationError
from cyp_pipeline.exchange import ENZYMES, run_cycle
from test_exchange import Backend, fixture


CASES = [
    {'system_id': f'S-fadrozole-{isoform}', 'ligand': 'S-fadrozole', 'isoform': isoform}
    for isoform in ENZYMES
]


class NativeUMABenchmarkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def run_fixture(self, *, approved=False, fail=False):
        manifest = fixture()
        manifest['ligand'] = 'S-fadrozole'
        if approved:
            for parts in manifest['enzymes'].values():
                for component in parts.values():
                    component['review'] = {'approved': True, 'reviewer': 'test-only'}
        backend = Backend(fail=fail)
        # Exercise the native-result branch with a mock; all artifacts remain temporary.
        backend.metadata = {
            'name': 'test-only-mock', 'version': 'test-only',
            'checkpoint_sha256': '0' * 64, 'synthetic': False,
        }
        directory = self.root / 'run'
        result = run_cycle(manifest, backend, directory)
        return directory / 'result.json', result

    def test_current_exchange_output_imports_and_pairs_native_energies(self):
        path, native = self.run_fixture()
        rows = load_uma(path, CASES)

        self.assertEqual(native['status'], 'exploratory')
        self.assertEqual([row['value'] for row in rows], [-5, -8])
        self.assertEqual({row['system_id'] for row in rows}, {case['system_id'] for case in CASES})
        self.assertEqual(len({row['protocol_id'] for row in rows}), 1)
        for row in rows:
            self.assertEqual(row['replicate'], native['input_sha256'])
            self.assertEqual(row['input_sha256'], native['input_sha256'])
            self.assertEqual(row['source'], source(path))
            self.assertTrue(row['provisional'])
            self.assertEqual(row['model_version'], 'test-only-mock:test-only:' + '0' * 64)

        comparison = next(row for row in compare_scores(CASES, rows) if row['method'] == 'UMA-exchange')
        self.assertEqual(comparison['status'], 'single_replicate_pilot')
        self.assertEqual(comparison['mean_delta_B2_minus_B1'], -3)
        self.assertEqual(comparison['preference'], 'CYP11B2')
        self.assertTrue(comparison['provisional'])
        self.assertNotIn('predicted_IC50_ratio_B1_over_B2', comparison)

    def test_reviewed_preparation_is_not_marked_provisional(self):
        path, _ = self.run_fixture(approved=True)
        self.assertTrue(all(row['provisional'] is False for row in load_uma(path, CASES)))

    def test_failed_native_cycle_is_not_imported(self):
        path, native = self.run_fixture(fail=True)
        self.assertEqual(native['status'], 'unresolved')
        with self.assertRaisesRegex(ValidationError, 'unresolved'):
            load_uma(path, CASES)

    def test_native_arithmetic_and_component_status_are_checked(self):
        path, native = self.run_fixture()
        mutations = [
            ('component', lambda result: result['enzymes']['CYP11B1']['components']['cluster_ligand']
             .update(status='failed')),
            ('arithmetic', lambda result: result['enzymes']['CYP11B1'].update(exchange_energy_eV=0)),
            ('delta', lambda result: result.update(delta_B2_minus_B1_eV=3)),
            ('nonfinite', lambda result: result['enzymes']['CYP11B1']['components']['cluster_ligand']
             .update(energy_eV=float('nan'))),
        ]
        for name, mutate in mutations:
            with self.subTest(name=name):
                modified = copy.deepcopy(native)
                mutate(modified)
                path.write_text(json.dumps(modified))
                with self.assertRaises(ValidationError):
                    load_uma(path, CASES)

    def test_modified_exchange_input_is_not_imported(self):
        path, _ = self.run_fixture()
        input_path = path.parent / 'input.json'
        manifest = json.loads(input_path.read_text())
        manifest['preparation_protocol'] = 'changed-after-execution'
        input_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValidationError, 'input hash mismatch'):
            load_uma(path, CASES)


if __name__ == '__main__':
    unittest.main()

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cyp_pipeline.screening import (
    PROJECT_ROOT, PREPARED_PRESETS, build_plan, catalog_payload, load_catalog, main,
)


class ScreeningTests(unittest.TestCase):
    def request(self, **changes):
        return {'candidate_id': 'r_fadrozole', 'target_id': 'CYP11B2',
                'panel_id': 'steroidogenic_p450', **changes}

    def test_five_targets_and_only_existing_pair_available(self):
        # Integration against the actual in-repo prepared geometry, no model.
        result = build_plan(self.request())
        self.assertEqual(result['summary'], {
            'proteins': 5, 'prepared_proteins': 2, 'needs_preparation': 3,
            'new_predictions': 0, 'selectivity_conclusion': 'not_assessed',
        })
        self.assertEqual(result['status'], 'plan_only')
        self.assertFalse(result['panel']['automatic_discovery'])
        self.assertTrue(all(row['binding_prediction'] is None and row['assessment'] == 'not_run'
                            for row in result['targets']))
        self.assertTrue(result['targets'][0]['preparation']['provisional'])
        self.assertEqual(result['available_jobs'][0]['preset'], 'r_fadrozole')
        self.assertEqual(result['plan_id'], build_plan(self.request())['plan_id'])

    def test_target_order_and_sign_stay_explicit_for_b1(self):
        result = build_plan(self.request(target_id='CYP11B1'))
        self.assertEqual(result['targets'][0]['protein']['id'], 'CYP11B1')
        self.assertEqual(len({r['protein']['id'] for r in result['targets']}), 5)
        self.assertIn('B2 minus B1', result['available_jobs'][0]['sign_convention'])

    def test_new_target_does_not_inherit_cyp_pair_protocol(self):
        for target in ('CYP19A1', 'CYP17A1', 'CYP11A1'):
            with self.subTest(target=target):
                result = build_plan(self.request(target_id=target))
                self.assertEqual(result['summary']['prepared_proteins'], 0)
                self.assertEqual(result['available_jobs'], [])

    def test_saved_candidates_do_not_acquire_uma_inputs(self):
        for candidate in ('baxdrostat', 'osilodrostat'):
            result = build_plan(self.request(candidate_id=candidate))
            self.assertEqual(result['summary']['prepared_proteins'], 0)
            self.assertEqual(result['summary']['new_predictions'], 0)

    def test_custom_name_cannot_impersonate_preset(self):
        with patch.dict(sys.modules, {'rdkit': None}):
            result = build_plan(self.request(candidate_id='custom', candidate_name='R-fadrozole', smiles='CCO'))
        self.assertEqual(result['candidate']['smiles_validation']['status'], 'not_checked')
        self.assertEqual(result['summary']['prepared_proteins'], 0)
        self.assertEqual(result['available_jobs'], [])

    def test_rdkit_syntax_check_is_optional_and_not_preparation(self):
        from types import SimpleNamespace
        from contextlib import nullcontext
        molecule = SimpleNamespace(GetNumAtoms=lambda: 3)
        chemistry = SimpleNamespace(MolFromSmiles=lambda _: molecule,
                                    FindMolChiralCenters=lambda *a, **k: [(0, '?')],
                                    MolToSmiles=lambda *a, **k: 'CCO')
        # Tiny chemistry mock tests the adapter only, not chemical validity.
        fake = SimpleNamespace(Chem=chemistry, rdBase=SimpleNamespace(BlockLogs=nullcontext))
        with patch.dict(sys.modules, {'rdkit': fake}):
            result = build_plan(self.request(candidate_id='custom', smiles='CCO'))
            validation = result['candidate']['smiles_validation']
            self.assertEqual(validation['status'], 'syntax_checked')
            self.assertEqual(validation['unassigned_tetrahedral_centers'], 1)
            self.assertEqual(result['summary']['prepared_proteins'], 0)
            chemistry.MolFromSmiles = lambda _: None
            with self.assertRaisesRegex(ValueError, 'could not parse'):
                build_plan(self.request(candidate_id='custom', smiles='invalid'))

    def test_custom_sequence_is_extra_unassessed_target(self):
        result = build_plan(self.request(target_id='custom', target_sequence='>custom\n'+'A'*70))
        self.assertEqual(result['summary']['proteins'], 6)
        self.assertEqual(result['summary']['prepared_proteins'], 0)
        self.assertEqual(result['targets'][0]['protein']['sequence'], 'A'*70)
        self.assertIn('biologically relevant', result['limitations'][-1])

    def test_invalid_and_ambiguous_input_rejected(self):
        changes = [
            {'candidate_id': '../r_fadrozole'}, {'target_id': 'UNKNOWN'},
            {'panel_id': 'unknown'}, {'target_sequence': 'A'*60},
            {'candidate_name': 'Override preset'}, {'smiles': 'CCO'},
            {'candidate_id': 'custom'}, {'candidate_id': 'custom', 'smiles': 'CCO ethanol'},
            {'target_id': 'custom', 'target_sequence': 'X'*60},
            {'target_id': 'custom', 'target_sequence': '>one\n'+'A'*50+'\n>two\n'+'A'*50},
            {'target_id': 'custom', 'target_sequence': 'A'*5001},
            {'command': 'not allowed'}, {'candidate_id': ['r_fadrozole']},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                build_plan(self.request(**change))
        for value in (None, [], 'text'):
            with self.assertRaises(ValueError):
                build_plan(value)

    def test_missing_or_corrupt_manifest_does_not_claim_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            result = build_plan(self.request(), directory)
            self.assertEqual(result['targets'][0]['preparation']['status'], 'missing_inputs')
            source = Path(directory) / PREPARED_PRESETS['r_fadrozole']['manifest']
            source.parent.mkdir(parents=True)
            for bad in ('[]', '{', '{"ligand": "different molecule"}'):
                source.write_text(bad)
                result = build_plan(self.request(), directory)
                self.assertEqual(result['targets'][0]['preparation']['status'], 'invalid_inputs')
                self.assertEqual(result['available_jobs'], [])

    def test_catalog_extends_to_other_families_without_enabling_execution(self):
        catalog = copy.deepcopy(load_catalog())
        catalog['targets']['TEST_ENZYME'] = {
            'label': 'Test enzyme', 'family': 'test_fixture', 'reason': 'A test, not biological evidence.',
        }
        catalog['panels']['test_panel'] = {'label': 'Test panel', 'targets': ['TEST_ENZYME', 'CYP11B1']}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'catalog.json'
            path.write_text(json.dumps(catalog))
            result = build_plan(self.request(target_id='TEST_ENZYME', panel_id='test_panel'),
                                catalog=load_catalog(path))
            self.assertEqual(result['summary']['proteins'], 2)
            self.assertEqual(result['available_jobs'], [])
            catalog['panels']['test_panel']['targets'].append('unregistered')
            path.write_text(json.dumps(catalog))
            with self.assertRaises(ValueError):
                load_catalog(path)

    def test_planning_does_not_import_model_runtimes(self):
        subprocess.run([sys.executable, '-c',
                        "from cyp_pipeline.screening import build_plan; import sys; "
                        "build_plan({'candidate_id':'r_fadrozole','target_id':'CYP11B2'}); "
                        "assert 'torch' not in sys.modules and 'fairchem.core' not in sys.modules"],
                       cwd=PROJECT_ROOT, check=True, capture_output=True)
        self.assertFalse(catalog_payload()['gpu_required'])

    def test_cli_export_is_reproducible_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory, patch('sys.stdout'), patch('sys.stderr'):
            destination = Path(directory) / 'plan.json'
            args = ['--candidate', 's_fadrozole', '--out', str(destination)]
            self.assertEqual(main(args), 0)
            before = destination.read_text()
            self.assertEqual(json.loads(before)['summary']['prepared_proteins'], 2)
            self.assertEqual(main(args), 2)
            self.assertEqual(destination.read_text(), before)


if __name__ == '__main__':
    unittest.main()

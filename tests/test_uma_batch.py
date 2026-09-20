import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cyp_pipeline.uma_batch import export_exchange, run_batch, validate_batch, MAX_SYSTEMS
from cyp_pipeline.sentinel_server import JobManager

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    # Software-only geometry. Not a real protein, ligand or chemical preparation.
    return {'schema_version': 1, 'kind': 'uma_pocket_batch', 'label': 'Synthetic test only', 'systems': [{
        'id': 'fixture_1', 'protein_id': 'ARBITRARY_TEST_TARGET', 'ligand': 'synthetic fixture',
        'source': 'Unit test; not experimental evidence', 'preparation': 'Artificial coordinates for contract testing only',
        'atoms': [{'id': 'C', 'element': 'C', 'position': [0, 0, 0]},
                  {'id': 'H1', 'element': 'H', 'position': [1, 0, 0]},
                  {'id': 'H2', 'element': 'H', 'position': [0, 1, 0]},
                  {'id': 'H3', 'element': 'H', 'position': [0, 0, 1]}],
        'ligand_atom_ids': ['H1'], 'state': {'charge': 0, 'multiplicity': 2, 'convention': 'Test fixture only'},
        'review': {'approved': False, 'provisional': True},
        'coordination': [], 'covalent_bounds': [], 'chirality_checks': [],
    }]}


class FakeBackend:
    metadata = {'name': 'software_test', 'synthetic': True}
    max_atoms = 1000

    def evaluate(self, atoms, state):
        return -12.0, [[.1, 0, 0] for _ in atoms]


class BatchTests(unittest.TestCase):
    def test_any_protein_identifier_with_explicit_preparation(self):
        data = fixture()
        for target in ('CYP19A1', 'TEST_KINASE', 'user protein 1'):
            data['systems'][0]['protein_id'] = target
            audit = validate_batch(data)
            self.assertEqual(audit['systems'][0]['protein_id'], target)
            self.assertTrue(audit['provisional'])
            self.assertIn('not', audit['note'])

    def test_reject_missing_preparation_and_state(self):
        for key in ('source', 'preparation', 'review', 'state', 'ligand_atom_ids', 'coordination', 'chirality_checks'):
            data = fixture(); del data['systems'][0][key]
            with self.subTest(field=key), self.assertRaises(ValueError):
                validate_batch(data)
        for field, value in (('review', {'approved': False}),
                             ('state', {'charge': 0, 'multiplicity': 1, 'convention': 'wrong parity'}),
                             ('id', '../outside'), ('ligand_atom_ids', ['unknown'])):
            data = fixture(); data['systems'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_batch(data)

    def test_coordinate_and_geometry_guards(self):
        for mutate in (
            lambda s: s['atoms'][0].update(position=[float('nan'), 0, 0]),
            lambda s: s['atoms'][1].update(id='C'),
            lambda s: s['atoms'][1].update(position=[0, 0, 0]),
            lambda s: s['atoms'][1].update(element='NotElement'),
            lambda s: s.update(covalent_bounds=[{'ids':['C','H1'],'min_A':2,'max_A':3}]),
            lambda s: s.update(chirality_checks=[{'center':'C','neighbors':['H1','H2','H3'],'reference_volume_A3':-1}]),
        ):
            data = fixture(); mutate(data['systems'][0])
            with self.assertRaises(ValueError):
                validate_batch(data)

    def test_no_implicit_hydrogens_or_unbounded_inputs(self):
        data = fixture()
        for atom in data['systems'][0]['atoms']:
            atom['element'] = 'C'
        with self.assertRaisesRegex(ValueError, 'hydrogens'):
            validate_batch(data)
        with self.assertRaises(ValueError):
            validate_batch(fixture(), max_atoms=3)
        data = fixture(); data['systems'] *= MAX_SYSTEMS + 1
        with self.assertRaises(ValueError):
            validate_batch(data)
        data = fixture(); data['command'] = 'not accepted'
        with self.assertRaises(ValueError):
            validate_batch(data)

    def test_review_is_an_attestation_not_automatic_validation(self):
        data = fixture(); data['systems'][0]['review'] = {'approved': True, 'reviewer': 'Test reviewer'}
        audit = validate_batch(data)
        self.assertFalse(audit['provisional'])
        self.assertEqual(audit['status'], 'inputs_checked')

    def test_batch_keeps_raw_energies_separate_and_synthetic_labeled(self):
        data = fixture(); data['systems'].append(copy.deepcopy(data['systems'][0]))
        data['systems'][1].update(id='second', protein_id='OTHER_TEST_TARGET')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'result'
            result = run_batch(data, FakeBackend(), out)
            self.assertEqual(result['status'], 'synthetic_demo')
            self.assertEqual(len(result['systems']), 2)
            self.assertEqual(result['systems'][0]['energy_eV'], -12)
            self.assertNotIn('selectivity', result)
            self.assertIn('Do not rank', result['scope'])
            self.assertTrue((out/'second-forces.json').is_file())
            self.assertFalse(list(out.glob('*.pending')))
            with self.assertRaises(FileExistsError):
                run_batch(data, FakeBackend(), out)

    def test_failed_evaluation_has_no_usable_energy(self):
        backend = FakeBackend()
        with tempfile.TemporaryDirectory() as directory, patch.object(backend, 'evaluate', side_effect=ValueError('test failure')):
            result = run_batch(fixture(), backend, Path(directory)/'run')
        self.assertEqual(result['status'], 'failed')
        self.assertIsNone(result['systems'][0]['energy_eV'])
        self.assertIn('test failure', result['reasons'][0])

    def test_export_preserves_existing_coordinates_and_declarations(self):
        path = ROOT/'prepared/exchange-R-pilot-v1/manifest.json'
        original = json.loads(path.read_text())
        batch = export_exchange(path)
        self.assertEqual(len(batch['systems']), 2)
        for system in batch['systems']:
            source = original['enzymes'][system['protein_id']]['cluster_ligand']
            self.assertEqual(system['atoms'], source['atoms'])
            self.assertEqual(system['state'], source['state'])
            self.assertEqual(system['review'], source['review'])

    def test_server_requires_explicit_provisional_confirmation_and_enable_flag(self):
        manager = JobManager(ROOT, '/missing/python', ROOT/'configs/uma-s-1p1-cpu.json', False)
        with self.assertRaisesRegex(ValueError, 'Confirm provisional'):
            manager.start_batch(fixture())
        with self.assertRaisesRegex(PermissionError, 'disabled'):
            manager.start_batch(fixture(), True)
        self.assertEqual(manager.jobs, {})
        self.assertEqual(manager.check_batch(fixture())['status'], 'inputs_checked')


if __name__ == '__main__':
    unittest.main()

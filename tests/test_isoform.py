import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from cyp_pipeline.auto_inputs import build_inputs, bundle_zip
from cyp_pipeline.interpretation import exchange_preference
from cyp_pipeline.screening import PROJECT_ROOT, PREPARED_PRESETS
from cyp_pipeline.structure_library import REFERENCES, get_reference, inspect_reference, reference_views
from cyp_pipeline.uma_batch import validate_batch


class IsoFormTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'data/raw').mkdir(parents=True)
        for spec in REFERENCES.values():
            shutil.copyfile(PROJECT_ROOT / 'data/raw' / (spec['pdb']+'.pdb'), self.root / 'data/raw' / (spec['pdb']+'.pdb'))

    def request(self, **changes):
        return {'candidate_id': 'r_fadrozole', 'target_id': 'CYP11B2', 'panel_id': 'steroidogenic_p450', **changes}

    def test_all_five_references_are_distinct_verified_actual_coordinates(self):
        views = reference_views(self.root)
        self.assertEqual(set(views), set(REFERENCES))
        self.assertEqual(len({v['pdb'] for v in views.values()}), 5)
        for target in REFERENCES:
            reference = get_reference(target, self.root)
            self.assertEqual(reference['status'], 'available')
            self.assertGreater(len(reference['sequence']), 400)
            self.assertGreater(len(views[target]['backbone']), 400)

    def test_identity_mismatch_and_error_page_are_rejected(self):
        raw = (self.root / 'data/raw/3N9Y.pdb').read_bytes()
        with self.assertRaises(ValueError):
            inspect_reference(raw, REFERENCES['CYP17A1'])
        spec = {**REFERENCES['CYP11A1'], 'accession': 'P19099'}
        with self.assertRaisesRegex(ValueError, 'accession'):
            inspect_reference(raw, spec)
        with self.assertRaises(ValueError):
            inspect_reference(b'<html>error</html>', REFERENCES['CYP11A1'])

    def test_missing_download_offline_and_unknown_target_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory, patch('cyp_pipeline.structure_library.urlopen') as network:
            self.assertEqual(get_reference('CYP19A1', directory)['status'], 'download_available')
            self.assertEqual(get_reference('UNKNOWN', directory, True)['status'], 'unmapped')
            network.assert_not_called()

    def test_download_failure_leaves_no_fake_reference(self):
        with tempfile.TemporaryDirectory() as directory, patch('cyp_pipeline.structure_library.urlopen', side_effect=OSError('offline')):
            self.assertEqual(get_reference('CYP19A1', directory, True)['status'], 'unavailable')
            self.assertFalse((Path(directory)/'data/raw/3EQM.pdb').exists())

    def test_real_bundle_files_and_zip_are_idempotent_no_affinity_or_guessed_states(self):
        preset = PREPARED_PRESETS['r_fadrozole']['manifest']
        (self.root / preset).parent.mkdir(parents=True)
        shutil.copyfile(PROJECT_ROOT / preset, self.root / preset)
        with patch('cyp_pipeline.structure_library.urlopen') as network:
            result = build_inputs(self.request(), self.root, download=False)
            self.assertEqual(result['summary'], {'proteins': 5, 'structures': 5, 'boltz_inputs': 5, 'uma_ready': 2, 'new_predictions': 0})
            self.assertEqual(result, build_inputs(self.request(), self.root, download=False))
            network.assert_not_called()
        with zipfile.ZipFile(io.BytesIO(bundle_zip(result['bundle_id'], self.root))) as archive:
            self.assertEqual(len([name for name in archive.namelist() if name.endswith('.yaml')]), 5)
            self.assertEqual(len([name for name in archive.namelist() if name.endswith('.pdb')]), 5)
            audit = validate_batch(json.loads(archive.read('uma/prepared-pockets.json')))
            self.assertTrue(audit['provisional'])
            for target in REFERENCES:
                document = json.loads(archive.read(f'boltz/{target}.yaml'))
                self.assertNotIn('properties', document)  # Cofactor affinity deliberately disabled.
                self.assertEqual(document['sequences'][-1]['ligand']['ccd'], '0T3')
                self.assertEqual(document['sequences'][0]['protein']['msa'], 'empty')
                draft = json.loads(archive.read(f'reference-pockets/{target}.json'))
                self.assertFalse(draft['uma_runnable'])
                with self.assertRaises(ValueError):
                    validate_batch(draft)
            self.assertEqual(json.loads(archive.read('reference-pockets/CYP19A1.json'))['reference_ligand'], 'Androstenedione')
        self.assertTrue(all(row['binding_prediction'] is None for row in result['targets']))

    def test_custom_name_cannot_unlock_preset_and_smiles_without_rdkit_not_exported(self):
        with patch.dict(sys.modules, {'rdkit': None}):
            result = build_inputs(self.request(candidate_id='custom', candidate_name='R-fadrozole', smiles='CCO'), self.root, download=False)
        self.assertEqual(result['summary']['boltz_inputs'], 0)
        self.assertEqual(result['summary']['uma_ready'], 0)
        self.assertNotIn('uma/prepared-pockets.json', result['files'])

    def test_other_registered_molecules_get_their_own_ligand_not_crystal_ligands(self):
        for candidate, expected in [('s_fadrozole','JD7'), ('osilodrostat','YSY'), ('baxdrostat',None)]:
            result = build_inputs(self.request(candidate_id=candidate), self.root, download=False)
            self.assertEqual(result['summary']['boltz_inputs'], 5)
            document = json.loads((self.root / result['directory'] / 'boltz/CYP19A1.yaml').read_text())
            ligand = document['sequences'][-1]['ligand']
            if expected:
                self.assertEqual(ligand['ccd'], expected)
            else:
                self.assertIn('smiles', ligand)
                self.assertNotIn('ccd', ligand)

    def test_custom_sequence_does_not_borrow_structure_or_heme(self):
        result = build_inputs(self.request(target_id='custom', target_sequence='A'*70), self.root, download=False)
        self.assertEqual(result['summary']['proteins'], 6)
        row = result['targets'][0]
        self.assertEqual(row['reference']['status'], 'unmapped')
        doc = json.loads((self.root / result['directory'] / row['boltz_input']).read_text())
        self.assertEqual(len(doc['sequences']), 2)
        self.assertEqual(doc['sequences'][0]['protein']['sequence'], 'A'*70)

    def test_archive_path_and_modified_artifact_are_rejected(self):
        result = build_inputs(self.request(), self.root, download=False)
        with self.assertRaises(ValueError):
            bundle_zip('../anything', self.root)
        file = self.root / result['directory'] / 'boltz/CYP19A1.yaml'
        file.write_text('user edit')
        with self.assertRaisesRegex(ValueError, 'changed'):
            bundle_zip(result['bundle_id'], self.root)
        with self.assertRaisesRegex(ValueError, 'modified'):
            build_inputs(self.request(), self.root, download=False)
        self.assertEqual(file.read_text(), 'user edit')


class InterpretationTests(unittest.TestCase):
    def result(self, delta=-.2, **changes):
        return {'descriptor': 'ligand_water_exchange_eV', 'delta_B2_minus_B1_eV': delta,
                'synthetic': False, 'status': 'exploratory', **changes}

    def test_direction_and_no_invented_fold(self):
        for delta, preferred in ((-.2, 'CYP11B2'), (.2, 'CYP11B1'), (0, None), (-9.5845, 'CYP11B2')):
            value = exchange_preference(self.result(delta))
            self.assertEqual(value['preferred_in_energy_model'], preferred)
            self.assertEqual(value['energy_gap_eV'], abs(delta))
            self.assertIsNone(value['fold_selectivity'])
            self.assertEqual(value['fold_status'], 'not_identifiable_from_potential_energy')

    def test_invalid_synthetic_failed_and_raw_totals_have_no_preference(self):
        cases = [self.result(x) for x in (None, float('inf'), float('nan'), True)]
        cases += [self.result(synthetic=True), self.result(status='unresolved'),
                  self.result(descriptor='total_potential_energy'), {}]
        for result in cases:
            value = exchange_preference(result)
            self.assertEqual(value['status'], 'unavailable')
            self.assertIsNone(value['preferred_in_energy_model'])
            self.assertIsNone(value['fold_selectivity'])


if __name__ == '__main__':
    unittest.main()

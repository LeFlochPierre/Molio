import copy
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from cyp_pipeline.backends import HarmonicDemo, CommandBackend
from cyp_pipeline.core import ValidationError, validate, checked_evaluate, relax, digest
from cyp_pipeline.demo import system
from cyp_pipeline.workflow import run, compare, report

PROTOCOL = json.loads(Path('configs/protocol.json').read_text())


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.s = system('R-fadrozole', 'CYP11B1')

    def test_review_and_atom_mapping_required(self):
        self.s['review']['approved'] = False
        with self.assertRaises(ValidationError): validate(self.s)
        self.s['review']['approved'] = True
        self.s['fragment_ids'].append('missing')
        with self.assertRaises(ValidationError): validate(self.s)

    def test_nonfinite_forces_rejected(self):
        class Bad:
            def evaluate(self, atoms, state): return 0., [[math.nan]*3 for a in atoms]
        with self.assertRaises(ValidationError): checked_evaluate(Bad(), self.s['atoms'], {})

    def test_fixed_atoms_and_relaxation(self):
        initial = copy.deepcopy(self.s['atoms'])
        result = relax(HarmonicDemo(), initial, {}, ['fe'], PROTOCOL)
        self.assertTrue(result['converged'])
        self.assertEqual(result['atoms'][0], initial[0])
        self.assertLess(result['energy_eV'], 0.001)
        self.assertEqual(initial, self.s['atoms'])

    def test_full_path_identical_fragment_energy(self):
        with tempfile.TemporaryDirectory() as d:
            r = run(self.s, PROTOCOL, HarmonicDemo(), Path(d)/'run')
            self.assertEqual(r['status'], 'synthetic_demo')
            self.assertAlmostEqual(r['descriptor_eV'], 0.02, delta=0.0003)
            self.assertTrue((Path(d)/'run'/'result.json').exists())
            self.assertEqual(compare([r], PROTOCOL)[0]['status'], 'unresolved')
            with self.assertRaises(FileExistsError): run(self.s, PROTOCOL, HarmonicDemo(), Path(d)/'run')

    def test_coordination_loss_not_scored(self):
        self.s['atoms'][1]['demo_target'][2] = 10.
        with tempfile.TemporaryDirectory() as d:
            r = run(self.s, PROTOCOL, HarmonicDemo(), Path(d)/'run')
            self.assertEqual(r['status'], 'unresolved')
            self.assertIsNone(r['descriptor_eV'])
            self.assertIn('reference_coordination', r['reasons'])

    def test_failure_saved(self):
        class Bad(HarmonicDemo):
            def evaluate(self, atoms, state): raise ValueError('unavailable')
        with tempfile.TemporaryDirectory() as d:
            r = run(self.s, PROTOCOL, Bad(), Path(d)/'run')
            self.assertEqual(r['status'], 'failed')
            self.assertIn('unavailable', (Path(d)/'run'/'result.json').read_text())

    def test_unconverged_not_scored(self):
        with tempfile.TemporaryDirectory() as d:
            r = run(self.s, {**PROTOCOL, 'max_steps': 1}, HarmonicDemo(), Path(d)/'run')
            self.assertEqual(r['status'], 'unresolved')
            self.assertIsNone(r['descriptor_eV'])

    def test_model_protocol_and_missing_pair_guards(self):
        common = {'ligand': 'R', 'synthetic': False, 'status': 'exploratory',
                  'protocol_sha256': digest(PROTOCOL), 'backend': {'name': 'x'}, 'comparison_key': 'same'}
        a = {**common, 'isoform': 'CYP11B1', 'descriptor_eV': 0.2}
        b = {**common, 'isoform': 'CYP11B2', 'descriptor_eV': 0.05}
        self.assertEqual(compare([a, b], PROTOCOL)[0]['descriptor_preference'], 'CYP11B2')
        self.assertEqual(compare([a], PROTOCOL)[0]['status'], 'unresolved')
        for key, value in [('backend', {'name': 'different'}), ('comparison_key', 'other'),
                           ('protocol_sha256', 'other'), ('descriptor_eV', 0.19)]:
            self.assertEqual(compare([a, {**b, key: value}], PROTOCOL)[0]['status'], 'unresolved')
        self.assertEqual(compare([a, b, {**b, 'descriptor_eV': 0.4}], PROTOCOL)[0]['status'], 'unresolved')

    def test_subprocess_backend_contract(self):
        config = {'command': [sys.executable, '-c',
                  'import json,sys; x=json.load(sys.stdin); print(json.dumps({"energy_eV":1.,"forces_eV_A":[[0.,0.,0.] for a in x["atoms"]]}))'],
                  'metadata': {'name': 'test', 'version': '1', 'checkpoint_sha256': 'test',
                               'state_handling': 'test', 'supported_elements': ['Fe','N','S','C'],
                               'physical_energy_only': True, 'synthetic': False}}
        energy, forces = checked_evaluate(CommandBackend(config), self.s['atoms'], self.s['cluster_state'])
        self.assertEqual(energy, 1.)
        self.assertEqual(len(forces), 4)

    def test_report_escapes_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            self.s['system_id'] = '<script>bad()</script>'
            r = run(self.s, PROTOCOL, HarmonicDemo(), Path(d)/'run')
            report([r], [], Path(d)/'report.html')
            self.assertNotIn('<script>', (Path(d)/'report.html').read_text())


if __name__ == '__main__': unittest.main()

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cyp_pipeline.core import ValidationError
from cyp_pipeline.mlip import UMABackend, file_hash, preflight, smoke

HAS_ASE = importlib.util.find_spec('ase') is not None


class SetupTests(unittest.TestCase):
    def test_missing_weights_explained_without_loading(self):
        with patch('cyp_pipeline.mlip.package_versions', return_value={
                'torch': None, 'ase': None, 'fairchem-core': None, 'huggingface-hub': None}):
            result = preflight({'checkpoint': '/no/such/model.pt', 'device': 'cpu'})
        self.assertEqual(result['status'], 'blocked')
        self.assertFalse(result['checkpoint_present'])

    def test_missing_checkpoint_produces_smoke_artifact(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'smoke'
            result = smoke({'device': 'cpu', 'checkpoint': str(Path(root)/'missing.pt')}, path)
            self.assertEqual(result['status'], 'failed')
            self.assertTrue((path/'result.json').exists())
            self.assertIn('checkpoint missing', result['message'])

    def test_hash_mismatch_prevents_loading(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'model.pt'; path.write_bytes(b'test only')
            self.assertEqual(len(file_hash(path)), 64)
            with self.assertRaisesRegex(ValidationError, 'SHA-256'):
                UMABackend({'device':'cpu', 'checkpoint':str(path), 'checkpoint_sha256':'incorrect'})

    def test_smoke_checks_force_sign(self):
        class AnalyticTestBackend:
            metadata = {'name':'analytic-test-only'}
            def __init__(self, config): pass
            def evaluate(self, atoms, state):
                return sum(x*x/2 for a in atoms for x in a['position']), [
                    [-x for x in a['position']] for a in atoms]
        with tempfile.TemporaryDirectory() as root:
            with patch('cyp_pipeline.mlip.UMABackend', AnalyticTestBackend):
                self.assertEqual(smoke({}, Path(root)/'correct')['status'], 'passed')
            class WrongSign(AnalyticTestBackend):
                def evaluate(self, atoms, state):
                    e,f = super().evaluate(atoms,state)
                    return e,[[-x for x in row] for row in f]
            with patch('cyp_pipeline.mlip.UMABackend', WrongSign):
                self.assertEqual(smoke({}, Path(root)/'wrong')['status'], 'needs_investigation')


@unittest.skipUnless(HAS_ASE, 'Run with .venv-mlip/bin/python to test real ASE integration')
class ASEAdapterTests(unittest.TestCase):
    def setUp(self):
        from ase.calculators.calculator import Calculator, all_changes
        class RecordingCalculator(Calculator):
            implemented_properties = ['energy','forces']
            def calculate(self, atoms=None, properties=('energy',), system_changes=all_changes):
                super().calculate(atoms, properties, system_changes)
                self.received = atoms.copy()
                self.results = {'energy':float((atoms.positions**2).sum()/2), 'forces':-atoms.positions}
        self.backend = UMABackend.__new__(UMABackend)
        self.backend.max_atoms = 10
        self.backend.calculator = RecordingCalculator()
        self.atoms = [{'element':'O','position':[0.,0.,0.]},
                      {'element':'H','position':[1.,0.,0.]},
                      {'element':'H','position':[0.,1.,0.]}]
        self.state = {'charge':0,'multiplicity':1,'convention':'neutral singlet'}

    def test_state_units_order_and_no_constraints(self):
        energy, forces = self.backend.evaluate(self.atoms, self.state)
        self.assertEqual(energy, 1.)
        self.assertEqual(forces[1], [-1.,0.,0.])
        received = self.backend.calculator.received
        self.assertEqual(received.info, {'charge':0,'spin':1})
        self.assertFalse(received.pbc.any())
        self.assertEqual(received.constraints, [])
        self.backend.evaluate(self.atoms, {**self.state,'charge':1,'multiplicity':2})
        self.assertEqual(self.backend.calculator.received.info, {'charge':1,'spin':2})

    def test_invalid_state_and_budget_rejected(self):
        for changed in ({'multiplicity':2},{'charge':0.5},{'multiplicity':0}):
            with self.assertRaises(ValidationError):
                self.backend.evaluate(self.atoms,{**self.state,**changed})
        self.backend.max_atoms = 2
        with self.assertRaises(ValidationError): self.backend.evaluate(self.atoms,self.state)


if __name__ == '__main__': unittest.main()

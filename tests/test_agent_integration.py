"""Agent boundary tests; molecular equivalence is checked with the real model separately."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cyp_pipeline.agent_tools import IsoformClient
from cyp_pipeline.agent_server import comparison


class AgentBoundaryTests(unittest.TestCase):
    def test_no_remote_service_or_unknown_preset(self):
        for url in ('https://example.com', 'http://user:pass@localhost', 'file:///tmp/a'):
            with self.assertRaises(ValueError):
                IsoformClient(url)
        with patch('cyp_pipeline.agent_tools.urlopen') as network:
            with self.assertRaises(ValueError):
                IsoformClient().start_exchange('baxdrostat')
            with self.assertRaises(ValueError):
                IsoformClient().job_status('../../configs/secret')
            network.assert_not_called()

    def fixture(self, root):
        def enzyme(energy):
            values = {'cluster_ligand': energy, 'free_water': 0., 'cluster_water': 0., 'free_ligand': 0.}
            return {'exchange_energy_eV': energy, 'components': {
                key: {'status': 'completed', 'energy_eV': value} for key, value in values.items()}}
        manifest = {'preparation_protocol': 'same pocket v1', 'enzymes': {
            'CYP11B1': {'free_ligand': {'atoms': [{'element': 'N'}, {'element': 'N'}, {'element': 'C'}, {'element': 'H'}]}}}}
        (root/'input.json').write_text(json.dumps(manifest))
        result = {'descriptor': 'ligand_water_exchange_eV', 'synthetic': False, 'status': 'exploratory',
                  'ligand': 'fixture', 'input_sha256': 'fixture hash', 'geometry_mode': 'single_point',
                  'delta_B2_minus_B1_eV': -.1, 'enzymes': {'CYP11B1': enzyme(0), 'CYP11B2': enzyme(-.1)},
                  'backend': {'checkpoint_sha256': 'sha', 'task': 'omol', 'device': 'cuda',
                              'inference_settings': 'batch', 'engine': 'alchemi'}}
        return {'state': 'completed', 'kind': 'exchange', 'input_manifest': 'input.json', 'result': result}

    def test_completed_matched_comparison_counts_atoms_without_qsar_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job = self.fixture(root)
            manager = SimpleNamespace(root=root, status=lambda key: job)
            result = comparison(manager, ['abc'])
            self.assertEqual(result['rows'][0]['nitrogen_atoms'], 2)
            self.assertEqual(result['rows'][0]['heavy_atoms'], 3)
            self.assertEqual(result['rows'][0]['delta_B2_minus_B1_eV'], -.1)
            self.assertFalse(result['qsar']['trained'])
            self.assertIsNone(result['rows'][0]['preference']['fold_selectivity'])

    def test_unfinished_failed_synthetic_duplicate_and_protocol_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.fixture(root)
            second = copy.deepcopy(first)
            jobs = {'a': first, 'b': second}
            manager = SimpleNamespace(root=root, status=jobs.__getitem__)
            for value in ('running', 'failed'):
                first['state'] = value
                with self.assertRaises(ValueError):
                    comparison(manager, ['a'])
            first['state'] = 'completed'
            first['result']['synthetic'] = True
            with self.assertRaises(ValueError):
                comparison(manager, ['a'])
            first['result']['synthetic'] = False
            with self.assertRaises(ValueError):
                comparison(manager, ['a', 'a'])
            second['result']['backend']['checkpoint_sha256'] = 'different'
            with self.assertRaisesRegex(ValueError, 'Mixed preparation'):
                comparison(manager, ['a', 'b'])


if __name__ == '__main__':
    unittest.main()

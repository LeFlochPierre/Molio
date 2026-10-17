import hashlib
import json
import math
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from molecular_lab.evidence import normalize_observation, compare_observations
from molecular_lab.server import ROOT, Handler, export_comparisons, load_dataset


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.data = load_dataset()
        self.record = json.loads((ROOT / 'data/sources/activity.json').read_text())['activities'][0]

    def test_units_and_exact_relation(self):
        original = normalize_observation(self.record)
        changed = dict(self.record, standard_units='uM', standard_value=float(self.record['standard_value']) / 1000)
        self.assertAlmostEqual(original['p_activity'], normalize_observation(changed)['p_activity'])
        censored = normalize_observation(dict(self.record, standard_relation='>'))
        self.assertIsNone(censored['p_activity'])
        with self.assertRaises(ValueError):
            compare_observations(original, censored)

    def test_invalid_concentrations(self):
        for value in ['nan', 'inf', '0', '-1']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_observation(dict(self.record, standard_value=value))
        with self.assertRaises(ValueError):
            normalize_observation(dict(self.record, standard_units='mg/ml'))

    def test_comparability_and_validity_gates(self):
        original = normalize_observation(self.record)
        for key in ['assay_id', 'target_id', 'endpoint', 'document_id']:
            with self.subTest(key=key), self.assertRaises(ValueError):
                compare_observations(original, dict(original, **{key:'different'}))
        with self.assertRaises(ValueError):
            compare_observations(original, dict(original, validity_comment='review needed'))

    def test_ratios_reproduce_original_records(self):
        raw = json.loads((ROOT / 'data/sources/activity.json').read_text())['activities']
        by_id = {r['molecule_chembl_id']:r for r in raw}
        self.assertEqual(len(self.data['compounds']), 9)
        self.assertGreaterEqual(len(self.data['pairs']), 5)
        for pair in self.data['pairs']:
            a,b = by_id[pair['left']],by_id[pair['right']]
            self.assertEqual(a['assay_chembl_id'], b['assay_chembl_id'])
            expected = float(a['standard_value']) / float(b['standard_value'])
            self.assertAlmostEqual(pair['fold_lower_ic50_right'], expected)
            self.assertAlmostEqual(pair['delta_p_activity_right'], math.log10(expected))
        acid = next(p for p in self.data['pairs'] if 'carboxylic' in p['title'])
        self.assertLess(acid['fold_lower_ic50_right'], 1)

    def test_source_hashes_and_structure_provenance(self):
        for source in self.data['provenance']['sources']:
            self.assertEqual(hashlib.sha256((ROOT / 'data' / source['file']).read_bytes()).hexdigest(), source['sha256'])
        pdb = (ROOT / 'data/structures/3SVG.pdb').read_text()
        self.assertIn('O60885', pdb)
        ligand = [l for l in pdb.splitlines() if l.startswith('HETATM') and l[17:20]=='ODR' and l[21]=='A']
        self.assertEqual(len(ligand), 19)
        self.assertTrue(all(c['experimental_pose'] is None for c in self.data['compounds']))
        self.assertIn('unspecified', self.data['reference_structure']['identity'])

    def test_export_preserves_scientific_context(self):
        result = export_comparisons({'pair_ids':['pair-1','pair-1'], 'notes':{'pair-1':'Test neighbouring substitution.'}}, self.data)
        self.assertEqual(len(result['comparisons']), 1)
        self.assertEqual(len(result['compounds']), 2)
        self.assertEqual(result['comparisons'][0]['user_hypothesis'], 'Test neighbouring substitution.')
        self.assertEqual(result['predictions'], [])
        self.assertIn('sources', result['provenance'])
        for payload in [{'pair_ids':['fake']}, {'pair_ids':[]}, {'pair_ids':['pair-1'],'notes':{'pair-2':'wrong'}}, {'pair_ids':['pair-1'],'notes':{'pair-1':'a'*4001}}]:
            with self.subTest(payload=str(payload)[:100]), self.assertRaises(ValueError):
                export_comparisons(payload, self.data)


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_local_assets_and_data(self):
        for path in ['/', '/app.js', '/vendor/3Dmol-min.js', '/data/structures/3SVG.pdb', '/api/dataset']:
            with urllib.request.urlopen(self.url+path) as response:
                self.assertEqual(response.status, 200)
                self.assertTrue(response.read())
        with urllib.request.urlopen(self.url+'/api/dataset') as response:
            self.assertEqual(len(json.load(response)['pairs']), 7)

    def test_traversal_and_unknown_routes(self):
        for path in ['/data/../../README.md','/%2e%2e/server.py','/api/unknown']:
            with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(self.url+path)
            self.assertEqual(error.exception.code, 404)

    def test_export_errors_and_success(self):
        request = urllib.request.Request(self.url+'/api/export', data=b'{bad', headers={'Content-Type':'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 400)
        request = urllib.request.Request(self.url+'/api/export', data=b'{"pair_ids":["pair-1"]}', headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request) as response:
            self.assertEqual(json.load(response)['comparisons'][0]['id'], 'pair-1')


if __name__ == '__main__':
    unittest.main()

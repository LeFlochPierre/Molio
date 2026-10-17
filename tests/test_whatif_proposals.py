import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer
from molecular_lab.proposals import available, analyze, ProposalStore
from molecular_lab.server import Handler, load_dataset


@unittest.skipUnless(available(), 'RDKit chemistry extra not installed')
class ProposalTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        self.payload = dict(parent_id='CHEMBL1828979', smiles='Cc1noc(C)c1-c1ccccc1F', hypothesis='Test fluorination')

    def test_variant_has_no_inherited_activity_or_pose(self):
        result = analyze(self.payload, self.dataset)
        self.assertIsNone(result['activity'])
        self.assertIsNone(result['bound_pose'])
        self.assertFalse(result['same_as_parent'])
        self.assertGreater(result['descriptors']['molecular_weight'], result['parent_descriptors']['molecular_weight'])
        self.assertTrue(result['depiction']['changed_atoms'])
        self.assertIn('<svg', result['depiction']['svg'])
        self.assertEqual(len(result['neighbours']), 4)
        self.assertTrue(all(n['observation']['assay_id'] == 'CHEMBL1832996' for n in result['neighbours']))

    def test_known_structure_does_not_receive_measured_activity(self):
        known = self.dataset['compounds'][3]
        result = analyze(dict(self.payload, smiles=known['smiles']), self.dataset)
        self.assertTrue(result['neighbours'][0]['exact_identity'])
        self.assertIsNone(result['activity'])
        self.assertTrue(any('already appears' in w for w in result['warnings']))

    def test_invalid_unbounded_and_multifragment_inputs(self):
        for smiles in ['no molecule', '', 'C'*101, 'CC.[Na+]', '[Fe]CC', '*CC']:
            with self.subTest(smiles=smiles), self.assertRaises(ValueError):
                analyze(dict(self.payload, smiles=smiles), self.dataset)
        with self.assertRaises(ValueError):
            analyze(dict(self.payload, activity=123), self.dataset)
        with self.assertRaises(ValueError):
            analyze(dict(self.payload, parent_id='unknown'), self.dataset)

    def test_stereo_and_persistent_immutable_snapshots(self):
        result = analyze(dict(self.payload, smiles='Cc1noc(C)c1-c1cccc(C(C)O)c1'), self.dataset)
        self.assertTrue(any('stereocentre' in w for w in result['warnings']))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'project.sqlite3'
            saved = ProposalStore(path).save(result)
            reopened = ProposalStore(path).list()
            self.assertEqual(reopened[0]['id'], saved['id'])
            self.assertEqual(reopened[0]['hypothesis'], 'Test fluorination')
            self.assertEqual(reopened[0]['provenance'], self.dataset['provenance'])
            original = next(c for c in self.dataset['compounds'] if c['id']==self.payload['parent_id'])
            with self.assertRaises(ValueError):
                ProposalStore(path).save(analyze(dict(self.payload, smiles=original['smiles']), self.dataset))

    def test_api_revalidates_and_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
            server.proposal_store = ProposalStore(Path(directory)/'p.sqlite3')
            thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                def post(payload):
                    request=urllib.request.Request(base+'/api/proposals',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
                    return json.load(urllib.request.urlopen(request))
                with self.assertRaises(urllib.error.HTTPError) as error:
                    post(dict(self.payload, descriptors={'clogp':0}))
                self.assertEqual(error.exception.code,400)
                saved = post(self.payload)
                with urllib.request.urlopen(base+'/api/proposals') as response:
                    self.assertEqual(json.load(response)['proposals'][0]['id'],saved['id'])
            finally:
                server.shutdown();server.server_close();thread.join()


if __name__ == '__main__': unittest.main()

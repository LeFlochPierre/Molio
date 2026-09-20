"""Preview routing uses real prepared coordinates, never candidate-name aliases."""
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

from cyp_pipeline.sentinel_server import (
    JobManager, PRESETS, PROJECT_ROOT, make_handler, materialize_single_point_manifest,
)
from cyp_pipeline.uma_batch import export_exchange


class IsoformPreviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.manager = JobManager(self.root, '/unused/python', self.root / 'unused-backend.json')
        self.handler_class = make_handler(self.manager, self.root / 'demo.html')
        process_patch = patch('cyp_pipeline.sentinel_server.subprocess.Popen')
        self.process = process_patch.start()
        self.addCleanup(process_patch.stop)
        self.addCleanup(self.process.assert_not_called)

    def copy_preset(self, preset):
        relative = PRESETS[preset]['manifest']
        destination = self.root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT_ROOT / relative, destination)
        return destination

    def get(self, path):
        # Exercise the real route and JSON serialization but do not bind a port
        # or start a server thread/model process in unit tests.
        handler = self.handler_class.__new__(self.handler_class)
        handler.path = path
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.wfile = io.BytesIO()
        handler.do_GET()
        return handler.send_response.call_args.args[0], json.loads(handler.wfile.getvalue())

    def assert_exact_pockets(self, batch, manifest):
        self.assertEqual(batch['kind'], 'uma_pocket_batch')
        self.assertEqual({s['protein_id'] for s in batch['systems']}, {'CYP11B1', 'CYP11B2'})
        for system in batch['systems']:
            original = manifest['enzymes'][system['protein_id']]['cluster_ligand']
            self.assertEqual(system['ligand'], manifest['ligand'])
            self.assertEqual(system['atoms'], original['atoms'])
            self.assertEqual(system['state'], original['state'])
            self.assertEqual(system['chirality_checks'], original['chirality_checks'])
            self.assertEqual(system['ligand_atom_ids'], [
                atom['id'] for atom in original['atoms'] if atom['id'] not in original['scaffold_ids']])

    def test_r_and_s_previews_export_their_own_exact_candidate_coordinates(self):
        previews = {}
        for preset in ('r_fadrozole', 's_fadrozole'):
            with self.subTest(preset=preset):
                source = self.copy_preset(preset)
                status, preview = self.get('/api/prepared-example?preset=' + preset)
                self.assertEqual(status, 200)
                self.assert_exact_pockets(preview, json.loads(source.read_text()))
                previews[preset] = preview
        self.assertNotEqual(previews['r_fadrozole']['label'], previews['s_fadrozole']['label'])
        self.assertNotEqual(previews['r_fadrozole']['systems'][0]['atoms'],
                            previews['s_fadrozole']['systems'][0]['atoms'])
        self.assertEqual(self.manager.jobs, {})

    def test_default_example_still_resolves_only_to_r_fadrozole(self):
        source = self.copy_preset('r_fadrozole')
        status, preview = self.get('/api/prepared-example')
        self.assertEqual(status, 200)
        self.assert_exact_pockets(preview, json.loads(source.read_text()))

    def test_unknown_blank_duplicate_and_path_queries_never_read_files(self):
        invalid_queries = (
            '?preset=missing', '?preset=', '?preset',
            '?preset=r_fadrozole&preset=s_fadrozole',
            '?preset=r_fadrozole&preset=r_fadrozole',
            '?path=/tmp/private.json', '?preset=r_fadrozole&path=/tmp/private.json',
            '?preset=../../private.json', '?preset=%2Fetc%2Fpasswd',
        )
        with patch('cyp_pipeline.sentinel_server.export_exchange') as export:
            for query in invalid_queries:
                with self.subTest(query=query):
                    status, body = self.get('/api/prepared-example' + query)
                    self.assertEqual(status, 400)
                    self.assertIn('error', body)
            export.assert_not_called()

    def test_exchange_job_preview_uses_snapshot_even_if_preset_changes(self):
        source = self.copy_preset('r_fadrozole')
        original = json.loads(source.read_text())
        snapshot = self.root / 'runs/web-inputs/exact-job.json'
        materialize_single_point_manifest(source, snapshot, 'exact-job')
        self.manager.jobs['exact-job'] = {
            'kind': 'exchange', 'preset': 'r_fadrozole', 'input_manifest': snapshot,
        }
        # A later edit/replacement of the source must not change the 3D preview
        # of an already-launched job.
        shutil.copyfile(PROJECT_ROOT / PRESETS['s_fadrozole']['manifest'], source)
        self.assertEqual(json.loads(source.read_text())['ligand'], 'S-fadrozole')
        status, preview = self.get('/api/jobs/exact-job/pockets')
        self.assertEqual(status, 200)
        self.assert_exact_pockets(preview, original)
        self.assertIn('exact-job.json', preview['systems'][0]['source'])

    def test_batch_job_preview_uses_snapshot_not_current_preset_or_caller_object(self):
        batch = export_exchange(self.copy_preset('s_fadrozole'))
        snapshot = self.root / 'uploaded-job.json'
        snapshot.write_text(json.dumps(batch, allow_nan=False))
        self.manager.jobs['uploaded-job'] = {
            'kind': 'uma_pocket_batch', 'preset': 'r_fadrozole', 'input_manifest': snapshot,
        }
        expected = json.loads(snapshot.read_text())
        batch['systems'][0]['atoms'][0]['position'][0] += 99
        with patch('cyp_pipeline.sentinel_server.export_exchange') as export:
            status, preview = self.get('/api/jobs/uploaded-job/pockets')
            self.assertEqual(status, 200)
            self.assertEqual(preview, expected)
            export.assert_not_called()

    def test_unknown_job_ids_cannot_become_arbitrary_input_paths(self):
        for unknown in ('missing', '', '../private.json', '/etc/passwd', '%2Fetc%2Fpasswd'):
            with self.subTest(job_id=unknown), patch('cyp_pipeline.sentinel_server._read_json') as read, \
                    patch('cyp_pipeline.sentinel_server.export_exchange') as export:
                with self.assertRaises(KeyError):
                    self.manager.pockets(unknown)
                read.assert_not_called()
                export.assert_not_called()
        for path in ('/api/jobs/missing/pockets', '/api/jobs//pockets',
                     '/api/jobs/../private.json/pockets', '/api/jobs/%2Fetc%2Fpasswd/pockets'):
            status, body = self.get(path)
            self.assertEqual(status, 404)
            self.assertEqual(body, {'error': 'Unknown job'})

    def test_missing_and_malformed_prepared_files_return_json_errors(self):
        status, body = self.get('/api/prepared-example?preset=r_fadrozole')
        self.assertEqual(status, 400)
        self.assertIn('error', body)
        source = self.copy_preset('r_fadrozole')
        for text in ('{unfinished json', 'null', '[]', '"not a manifest"', '1', 'true', '{}'):
            with self.subTest(text=text):
                source.write_text(text)
                status, body = self.get('/api/prepared-example?preset=r_fadrozole')
                self.assertEqual(status, 400)
                self.assertIn('error', body)

    def test_missing_corrupt_and_nonfinite_job_snapshot_return_json_errors(self):
        snapshot = self.root / 'corrupt-job.json'
        self.manager.jobs['corrupt-job'] = {
            'kind': 'uma_pocket_batch', 'input_manifest': snapshot,
        }
        status, body = self.get('/api/jobs/corrupt-job/pockets')
        self.assertEqual(status, 400)
        self.assertIn('error', body)
        for text in ('{unfinished json', '{"energy_eV": NaN}', '{"energy_eV": Infinity}',
                     'null', '[]', '"not a batch"', '1', 'true', '{}',
                     '{"schema_version":1,"kind":"uma_pocket_batch","label":"Corrupt","systems":[]}'):
            with self.subTest(text=text):
                snapshot.write_text(text)
                status, body = self.get('/api/jobs/corrupt-job/pockets')
                self.assertEqual(status, 400)
                self.assertIn('error', body)

    def test_exchange_job_snapshot_rejects_scalar_list_and_invalid_shape_json(self):
        snapshot = self.root / 'corrupt-exchange.json'
        self.manager.jobs['corrupt-exchange'] = {
            'kind': 'exchange', 'input_manifest': snapshot,
        }
        for text in ('null', '[]', '"not a manifest"', '1', 'true', '{}'):
            with self.subTest(text=text):
                snapshot.write_text(text)
                status, body = self.get('/api/jobs/corrupt-exchange/pockets')
                self.assertEqual(status, 400)
                self.assertIn('error', body)


if __name__ == '__main__':
    unittest.main()

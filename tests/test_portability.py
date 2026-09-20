import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from cyp_pipeline.sentinel_server import default_backend, default_uma_python, main
from cyp_pipeline.mlip import main as mlip_main


class PortableRuntimeTests(unittest.TestCase):
    def test_explicit_checkpoint_selection_uses_matching_default_filename(self):
        with patch('cyp_pipeline.mlip.download',return_value={'checkpoint':'model-placeholder'}) as download:
            self.assertEqual(mlip_main(['download','--filename','checkpoints/uma-s-1p1.pt']),0)
            download.assert_called_once_with('models/uma-s-1p1.pt','checkpoints/uma-s-1p1.pt')

    def test_clean_checkout_uses_current_python_and_relative_model_config(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            root=Path(directory)
            self.assertEqual(default_uma_python(root), Path(sys.executable))
            self.assertEqual(default_backend(root),root/'configs/uma-s-1p1-cpu.json')

    def test_project_virtual_environment_entrypoint_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            root=Path(directory);entry=root/'.venv-mlip/bin/python'
            entry.parent.mkdir(parents=True);entry.symlink_to(sys.executable)
            self.assertEqual(default_uma_python(root),entry)
            self.assertNotEqual(default_uma_python(root),entry.resolve())

    def test_local_settings_and_environment_override(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            root=Path(directory);(root/'configs').mkdir()
            (root/'configs/runtime.local.json').write_text(json.dumps({'uma_python':'/local/env/bin/python'}))
            self.assertEqual(default_uma_python(root),Path('/local/env/bin/python'))
            with patch.dict(os.environ,{'ISOFORM_UMA_PYTHON':'/explicit/env/bin/python'}):
                self.assertEqual(default_uma_python(root),Path('/explicit/env/bin/python'))

    def test_bundled_demo_is_default_and_compute_remains_opt_in(self):
        with patch('cyp_pipeline.sentinel_server.serve') as serve:
            self.assertEqual(main([]),0)
            site,port,bind,root,python,backend,enabled,catalog=serve.call_args.args
            self.assertTrue(site.is_file())
            self.assertEqual(bind,'127.0.0.1')
            self.assertFalse(enabled)

    def test_portable_demo_configs_match_model_and_budget(self):
        root=Path(__file__).resolve().parents[1]
        for device in ('cpu','cuda'):
            config=json.loads((root/f'configs/uma-s-1p1-{device}.json').read_text())
            self.assertFalse(Path(config['checkpoint']).is_absolute())
            self.assertEqual(config['model_name'],'uma-s-1p1')
            self.assertEqual(config['device'],device)
            self.assertEqual(config['max_atoms'],1000)
            self.assertEqual(len(config['checkpoint_sha256']),64)

import json
import tempfile
import unittest
from pathlib import Path

from cyp_pipeline.sentinel_server import materialize_single_point_manifest


class SentinelServerTests(unittest.TestCase):
    def test_web_job_manifest_is_a_copy_with_frozen_coordinates(self):
        source_data = {
            "geometry_mode": "relax",
            "ligand": "candidate",
            "enzymes": {"CYP11B1": {}, "CYP11B2": {}},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "source.json", root / "nested" / "job.json"
            source.write_text(json.dumps(source_data))
            materialize_single_point_manifest(source, destination, "job-123")
            copied = json.loads(destination.read_text())
        self.assertEqual(source_data["geometry_mode"], "relax")
        self.assertEqual(copied["geometry_mode"], "single_point")
        self.assertEqual(copied["web_execution"]["job_id"], "job-123")
        self.assertIn("not a binding affinity", copied["web_execution"]["scope"])


if __name__ == "__main__":
    unittest.main()

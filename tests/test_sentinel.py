import json
from pathlib import Path
import tempfile
import unittest

from cyp_pipeline.sentinel import assess_candidate, load_panel


class SentinelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.panel_path = self.root / "panel.json"
        self.panel_path.write_text(json.dumps({
            "schema_version": 1,
            "target": {"id": "TARGET", "sequence": "A" * 50},
            "off_target_panel": [
                {"id": "PARALOG", "role": "mandatory_primary"},
                {"id": "NEXT", "role": "required_next_tier"},
            ],
            "policy": {"minimum_model_fold": 10, "minimum_validation_fold": 10},
        }))
        self.panel = load_panel(self.panel_path)
        self.experiment = {
            ("candidate", "TARGET"): {"system_id": "candidate-target", "isoform": "TARGET"},
            ("candidate", "PARALOG"): {"system_id": "candidate-paralog", "isoform": "PARALOG"},
        }
        self.run = self.root / "run"
        prediction = self.run / "seed-42/boltz_results_inputs/predictions"
        for system, value in (("candidate-target", -2.0), ("candidate-paralog", -1.0)):
            directory = prediction / system
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"affinity_{system}.json").write_text(json.dumps({
                "affinity_pred_value": value, "affinity_probability_binary": 0.9,
            }))
        (self.run / "seed-42/boltz.log").write_text(
            "Predicting DataLoader 0: 100%\nNumber of failed examples: 0\n"
        )
        (self.run / "run_manifest.json").write_text(json.dumps({"status": "running"}))

    def assay(self, target_value, paralog_value):
        path = self.root / "assays.json"
        path.write_text(json.dumps({"measurements": [
            {"ligand": "candidate", "isoform": "TARGET", "endpoint": "Ki", "value_nM": target_value,
             "assay_id": "paired", "source_url": "https://example.test"},
            {"ligand": "candidate", "isoform": "PARALOG", "endpoint": "Ki", "value_nM": paralog_value,
             "assay_id": "paired", "source_url": "https://example.test"},
        ]}))
        return path

    def test_validation_separates_selective_and_not_selective(self):
        selective = assess_candidate(self.panel, self.experiment, self.run, [self.assay(1, 100)], "candidate")
        self.assertEqual(selective["decision"], "validated_selective")
        self.assertEqual(selective["model_screen"]["status"], "supported")
        self.assertAlmostEqual(selective["boltz"]["target_over_off_target_fold"], 10)
        self.assertTrue(any("unassessed" in alert for alert in selective["alerts"]))

        nonselective = assess_candidate(self.panel, self.experiment, self.run, [self.assay(1, 5)], "candidate")
        self.assertEqual(nonselective["decision"], "validated_not_selective")
        self.assertEqual(nonselective["paired_assay_validation"][0]["target_over_off_target_fold"], 5)

    def test_invalid_sequence_or_primary_panel_is_rejected(self):
        invalid = json.loads(self.panel_path.read_text())
        invalid["target"]["sequence"] = "A" * 49 + "Z"
        self.panel_path.write_text(json.dumps(invalid))
        with self.assertRaisesRegex(ValueError, "amino-acid"):
            load_panel(self.panel_path)
        invalid["target"]["sequence"] = "A" * 50
        invalid["off_target_panel"].append({"id": "OTHER", "role": "mandatory_primary"})
        self.panel_path.write_text(json.dumps(invalid))
        with self.assertRaisesRegex(ValueError, "exactly one"):
            load_panel(self.panel_path)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from cyp_pipeline.sentinel_demo import interactive_html, structure_view


def pdb_line(record, serial, atom, residue, chain, number, x, y, z, element):
    return (
        f"{record:<6}{serial:>5} {atom:<4} {residue:>3} {chain}{number:>4}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {element:>2}\n"
    )


class SentinelDemoTests(unittest.TestCase):
    def test_coordinate_payload_is_actual_pdb_context(self):
        with tempfile.TemporaryDirectory() as directory:
            pdb = Path(directory) / "mini.pdb"
            pdb.write_text("".join([
                pdb_line("ATOM", 1, "CA", "ALA", "A", 1, 4, 0, 0, "C"),
                pdb_line("ATOM", 5, "CA", "GLY", "A", 3, 4, 3.8, 0, "C"),
                pdb_line("ATOM", 2, "SG", "CYS", "A", 2, 0, 0, 2, "S"),
                pdb_line("HETATM", 3, "FE", "HEM", "A", 601, 0, 0, 0, "FE"),
                pdb_line("HETATM", 4, "N01", "0T3", "A", 602, 0, 0, 1.9, "N"),
            ]))
            payload = structure_view(pdb)
        self.assertEqual(payload["pdb"], "mini")
        self.assertEqual(payload["pocket_residue_count"], 2)
        self.assertEqual(len(payload["backbone"]), 2, 'Every C-alpha is needed to preserve the connected protein trace')
        self.assertAlmostEqual(payload["iron_to_nearest_ligand_atom"], 1.9)
        self.assertAlmostEqual(payload["iron_to_axial_sulfur"], 2.0)

    def test_html_embeds_evidence_and_keeps_reference_pose_scope(self):
        report = {
            "panel": {
                "target": {"id": "TARGET", "sequence": "A" * 50, "binding_site": "site"},
                "policy": {"minimum_model_fold": 10, "minimum_validation_fold": 10},
                "off_target_panel": [{"id": "OFF", "role": "mandatory_primary"}],
            },
            "cards": [{
                "ligand": "candidate", "decision": "needs_assay", "decision_scope": "scope",
                "target": {"id": "TARGET"}, "mandatory_primary_off_target": {"id": "OFF"},
                "boltz": {"status": "unassessed"}, "model_screen": {"status": "unassessed"},
                "uma_local_chemistry": {"status": "unassessed"}, "boltz_geometry": {"status": "unassessed"},
                "paired_assay_validation": [], "alerts": ["alert"], "recommended_next_action": "assay",
            }],
        }
        structure = {"pdb": "TEST", "chain": "A", "ligand_code": "LIG", "ligand_label": "reference ligand",
                     "atoms": [], "backbone": [], "center": [0, 0, 0], "iron": [0, 0, 0],
                     "donor": [0, 0, 1], "sulfur": [0, 0, 2], "iron_to_nearest_ligand_atom": 1,
                     "iron_to_axial_sulfur": 2, "pocket_residue_count": 0}
        page = interactive_html(report, structure)
        self.assertIn("reference ligand", page)
        self.assertIn("not a predicted pose", page)
        self.assertIn("candidate", page)


if __name__ == "__main__":
    unittest.main()

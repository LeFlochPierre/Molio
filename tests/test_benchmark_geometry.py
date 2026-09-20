"""Geometry invariants; chemistry dependencies are optional for the core suite."""

from pathlib import Path
import unittest

try:
    import gemmi
    from rdkit import Chem
    from rdkit.Chem import AllChem
except ImportError:
    CHEMISTRY_AVAILABLE = False
else:
    CHEMISTRY_AVAILABLE = True

from cyp_pipeline.benchmark_geometry import _chirality, analyze_boltz_structure


@unittest.skipUnless(CHEMISTRY_AVAILABLE, 'Optional gemmi/RDKit dependencies unavailable')
class GeometryTests(unittest.TestCase):
    def setUp(self):
        molecule = Chem.AddHs(Chem.MolFromSmiles('N[C@@H](C)C(=O)O'))
        self.assertEqual(AllChem.EmbedMolecule(molecule, randomSeed=42), 0)
        for atom in molecule.GetAtoms():
            atom.SetProp('name', f'A{atom.GetIdx()}')
        self.reference = Chem.RemoveHs(molecule)
        self.coordinates = {atom.GetProp('name'): tuple(self.reference.GetConformer().GetAtomPosition(atom.GetIdx()))
                            for atom in self.reference.GetAtoms()}

    def test_coordinate_mirror_reverses_chirality(self):
        original = _chirality(self.reference, self.coordinates)
        mirrored = _chirality(self.reference, {name: (-x, y, z)
                                              for name, (x, y, z) in self.coordinates.items()})
        self.assertEqual(original['status'], 'matches_ccd')
        self.assertEqual(mirrored['status'], 'mismatch_or_unassigned')
        self.assertEqual(set(original['coordinate_centers']), set(mirrored['coordinate_centers']))
        for name, label in original['coordinate_centers'].items():
            self.assertEqual(mirrored['coordinate_centers'][name], {'R': 'S', 'S': 'R'}[label])

    def test_missing_atom_is_unresolved(self):
        coordinates = dict(self.coordinates)
        missing = next(iter(coordinates))
        del coordinates[missing]
        result = _chirality(self.reference, coordinates)
        self.assertEqual(result['status'], 'unresolved')
        self.assertEqual(result['missing_atom_names'], [missing])
        self.assertEqual(result['missing_atom_count'], 1)

    def test_native_reference_distances(self):
        root = Path(__file__).resolve().parents[1]
        for pdb, ligand, ligand_distance in [('6M7X', 'S-fadrozole', 2.3736893),
                                              ('4FDH', 'R-fadrozole', 1.8663111)]:
            path = root / 'data' / 'raw' / f'{pdb}.pdb'
            if not path.exists():
                self.skipTest('Local crystal structures unavailable')
            result = analyze_boltz_structure(path, ligand, ligand_chain='A', heme_chain='A')
            self.assertEqual(result['status'], 'diagnostic_only')
            self.assertTrue(result['ligand_ccd_matches_expected'])
            self.assertEqual(result['nearest_ligand_nitrogen']['atom_name'], 'N06')
            self.assertAlmostEqual(result['nearest_ligand_nitrogen']['distance_A'], ligand_distance, places=5)
            self.assertEqual(result['nearest_protein_cysteine_sulfur']['residue_id'], '450')
            self.assertEqual(result['chirality']['status'], 'unassessed')


if __name__ == '__main__':
    unittest.main()

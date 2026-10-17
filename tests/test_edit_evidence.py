import copy
import math
import unittest
from molio.proposals import available
from molio.server import load_dataset


@unittest.skipUnless(available(), 'RDKit required')
class EditEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.data = load_dataset()
        self.compounds = {c['id']: c for c in self.data['compounds']}

    def evidence(self, a, b, data=None):
        from molio.edit_evidence import evidence_for_edit
        return evidence_for_edit(self.compounds[a]['smiles'], self.compounds[b]['smiles'], data or self.data)

    def test_support_and_reverse_direction(self):
        forward = self.evidence('CHEMBL1828980', 'CHEMBL1828982')
        reverse = self.evidence('CHEMBL1828982', 'CHEMBL1828980')
        self.assertEqual(forward['counts'], {'lower':2,'higher':0,'unchanged':0})
        self.assertEqual(reverse['counts'], {'lower':0,'higher':2,'unchanged':0})
        for a,b in zip(forward['evidence'], reverse['evidence']):
            self.assertAlmostEqual(a['fold_lower_ic50_right'] * b['fold_lower_ic50_right'], 1)
        self.assertIsNone(forward['prediction'])
        self.assertIn('not independent',forward['summary'])

    def test_worse_result_is_retained(self):
        result = self.evidence('CHEMBL1828983', 'CHEMBL1828984')
        self.assertEqual(result['counts']['higher'], 1)
        self.assertAlmostEqual(result['evidence'][0]['fold_lower_ic50_right'],7700/51200)

    def test_whole_connectivity_must_match_one_edit(self):
        from molio.edit_evidence import evidence_for_edit, recognize
        parent = self.compounds['CHEMBL1828980']['smiles']
        # Alcohol plus an additional fluorine is not just ketone reduction.
        self.assertIsNone(recognize(parent, 'Cc1noc(C)c1-c1cc(F)cc(C(C)O)c1'))
        result = self.evidence('CHEMBL1828979', 'CHEMBL1828981')
        self.assertEqual(result['status'], 'unsupported_or_no_match')
        self.assertEqual(result['evidence'], [])
        self.assertIsNone(result['prediction'])
        self.assertIsNone(recognize(parent, parent))

    def test_conflicting_measurement_remains_visible(self):
        changed = copy.deepcopy(self.data)
        compound = next(c for c in changed['compounds'] if c['id']=='CHEMBL1828986')
        compound['observation']['value_M']=1e-3
        result = self.evidence('CHEMBL1828980','CHEMBL1828982',changed)
        self.assertEqual(result['counts']['higher'],1)
        self.assertEqual(result['counts']['lower'],1)

    def test_conformer_graph_and_coordinates(self):
        from rdkit import Chem
        from molio.conformers import conformer
        for cid in ['CHEMBL1828979','CHEMBL1828986']:
            smiles = self.compounds[cid]['smiles']
            result=conformer(smiles)
            self.assertEqual(result['status'],'generated')
            model=Chem.MolFromMolBlock(result['molblock'])
            self.assertTrue(model.GetConformer().Is3D())
            self.assertEqual(model.GetNumHeavyAtoms(),Chem.MolFromSmiles(smiles).GetNumHeavyAtoms())
            original=Chem.MolFromSmiles(smiles)
            Chem.RemoveStereochemistry(original);Chem.RemoveStereochemistry(model)
            self.assertEqual(Chem.MolToSmiles(original),Chem.MolToSmiles(model))
            self.assertTrue(all(math.isfinite(float(v)) for p in model.GetConformer().GetPositions() for v in p))
            self.assertIn('Not an experimental',result['provenance'])
        self.assertIsNotNone(conformer(self.compounds['CHEMBL1828986']['smiles'])['stereochemistry_note'])


if __name__ == '__main__': unittest.main()

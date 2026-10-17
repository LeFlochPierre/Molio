import tempfile
from pathlib import Path
import unittest
from molio.designs import explore, shortlist
from molio.proposals import ProposalStore, available
from molio.server import load_dataset

@unittest.skipUnless(available(),'RDKit required')
class DesignTests(unittest.TestCase):
    def setUp(self):
        self.data=load_dataset();self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=ProposalStore(Path(self.temp.name)/'proposals.sqlite3')

    def test_bounded_valid_scaffold_preserving_edits(self):
        from rdkit import Chem
        from rdkit.Chem.Scaffolds import MurckoScaffold
        for parent in self.data['compounds']:
            result=explore({'parent_id':parent['id']},self.data)
            self.assertLessEqual(len(result['candidates']),8)
            seen=set()
            core=Chem.MolToSmiles(MurckoScaffold.GetScaffoldForMol(Chem.MolFromSmiles(parent['smiles'])))
            for row in result['candidates']:
                self.assertNotIn(row['smiles'],seen);seen.add(row['smiles'])
                self.assertIsNone(row['activity'])
                self.assertEqual(Chem.MolToSmiles(MurckoScaffold.GetScaffoldForMol(Chem.MolFromSmiles(row['smiles']))),core)
                self.assertNotEqual(row['smiles'],Chem.MolToSmiles(Chem.MolFromSmiles(parent['smiles'])))
        ester=explore({'parent_id':'CHEMBL1828983'},self.data)
        self.assertEqual([c['rule'] for c in ester['candidates'][:2]],['shorten_ether','shorten_ester'])
        self.assertTrue(all(c['known_compound_id'] is None for c in ester['candidates'][:2]))

    def test_shortlist_preserves_baseline_and_unmeasured_provenance(self):
        parent='CHEMBL1828983';rows=explore({'parent_id':parent},self.data)['candidates']
        result=shortlist({'parent_id':parent,'design_ids':[c['id'] for c in rows[:2]]},self.data,self.store)
        self.assertEqual(result['candidate_ids'][0],parent)
        self.assertFalse(result['prediction_started'])
        saved={p['id']:p for p in self.store.list()}
        self.assertEqual(len(saved),2)
        for identifier,row in zip(result['candidate_ids'][1:],rows):
            self.assertEqual(saved[identifier]['canonical_smiles'],row['smiles'])
            self.assertEqual(saved[identifier]['design_origin']['design_id'],row['id'])
            self.assertIsNone(saved[identifier]['activity']);self.assertIsNone(saved[identifier]['bound_pose'])

    def test_forged_empty_or_oversized_selection_does_not_save(self):
        for ids in [[],['fake'],['fake']*3]:
            with self.assertRaises(ValueError):shortlist({'parent_id':'CHEMBL1828983','design_ids':ids},self.data,self.store)
        self.assertEqual(self.store.list(),[])
        with self.assertRaises(ValueError):explore({'parent_id':'CHEMBL1828983','smiles':'CC'},self.data)

if __name__=='__main__':unittest.main()

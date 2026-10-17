import unittest
from unittest.mock import patch
from molecular_lab.server import load_dataset
from molecular_lab.proposals import available, analyze
from molecular_lab.suggestions import suggest


@unittest.skipUnless(available(), 'RDKit required')
class GuidedEditTests(unittest.TestCase):
    def setUp(self):
        self.data=load_dataset()

    def test_forward_reverse_and_known_identity(self):
        for parent, destination in [('CHEMBL1828980','CHEMBL1828982'),('CHEMBL1828982','CHEMBL1828980'),('CHEMBL1828983','CHEMBL1828984'),('CHEMBL1828984','CHEMBL1828983')]:
            with self.subTest(parent=parent):
                result=suggest({'parent_id':parent},self.data)
                self.assertEqual(len(result['suggestions']),1)
                candidate=result['suggestions'][0]
                self.assertIn(destination,candidate['known_compound_ids'])
                analysis=analyze({'parent_id':parent,'smiles':candidate['smiles']},self.data)
                self.assertFalse(analysis['same_as_parent'])
                self.assertIsNone(analysis['activity'])
                self.assertEqual(analysis['edit_evidence']['status'],'evidence_found')

    def test_unsupported_parent_is_not_randomly_modified(self):
        self.assertEqual(suggest({'parent_id':'CHEMBL1828979'},self.data)['suggestions'],[])

    def test_input_and_missing_runtime(self):
        for payload in [{},{'parent_id':'other'},{'parent_id':'CHEMBL1828980','smiles':'CC'}]:
            with self.subTest(payload=payload),self.assertRaises(ValueError):
                suggest(payload,self.data)
        with patch('molecular_lab.suggestions.available',return_value=False),self.assertRaises(RuntimeError):
            suggest({'parent_id':'CHEMBL1828980'},self.data)


if __name__ == '__main__':unittest.main()

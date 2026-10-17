"""Compound sources must remain distinct from comparable measurements and predictions."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from molio.targets import PublicData
from molio.compound_lookup import library, pubchem_search, target_compounds, save_lookup, import_candidate
from molio.starter import build_starter
from molio.proposals import available
from molio.experiments import catalog


@unittest.skipUnless(available(), 'RDKit required')
class CompoundLookupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name);self.base=self.folder/'data'
        self.record={'primaryAccession':'P38801','organism':{'scientificName':'Saccharomyces cerevisiae'},
          'proteinDescription':{'recommendedName':{'fullName':{'value':'Exosome complex protein LRP1'}}},
          'sequence':{'length':80,'value':'ACDEFGHIKLMNPQRSTVWY'*4},
          'comments':[{'commentType':'FUNCTION','texts':[{'value':'Test function description'}]}],
          'uniProtKBCrossReferences':[{'database':'PDB','id':'5C0W','properties':[{'key':'Method','value':'X-ray'}]}]}
        with patch.object(PublicData,'json',side_effect=lambda url,name:self.record if 'uniprot' in url else []):
            self.data=build_starter('P38801',self.folder,'lab-0123456789ab',lambda m:None)
        (self.base/'sources/uniprot.json').write_text(json.dumps(self.record))

    def test_examples_are_runnable_without_network_or_measurements(self):
        with patch.object(PublicData,'read',side_effect=AssertionError('No network')):
            rows=library(self.base)
            added=import_candidate(self.base,self.data,'example-anisole')
        compound=added['compound']
        self.assertEqual(compound['origin']['source'],'Bundled example')
        self.assertNotIn('observation',compound);self.assertEqual(compound['supporting_records'],[])
        self.assertEqual(added['conformer']['status'],'generated')
        self.assertEqual(catalog(self.data,[])[0]['kind'],'input')
        self.assertEqual(rows['protein_context']['structures'][0]['id'],'5C0W')
        self.assertEqual(rows['protein_context']['function'],['Test function description'])
        with self.assertRaisesRegex(ValueError,'again'):import_candidate(self.base,self.data,'pubchem-unknown')

    def test_pubchem_preserves_stereochemistry_and_provenance(self):
        payload={'PropertyTable':{'Properties':[{'CID':123,'Title':'Test compound','SMILES':'C[C@H](O)c1ccccc1','ConnectivitySMILES':'CC(O)c1ccccc1'}]}}
        with patch.object(PublicData,'json',return_value=payload) as fetch:
            client,rows,message=pubchem_search('CID 123')
        self.assertIn('/cid/123/',fetch.call_args.args[0]);self.assertIn('@',rows[0]['smiles'])
        client.sources['pubchem-test.json']=('https://pubchem.ncbi.nlm.nih.gov/test',json.dumps(payload).encode())
        save_lookup(self.base,self.data,client,rows)
        imported=import_candidate(self.base,self.data,'pubchem-123')['compound']
        self.assertIn('@',imported['canonical_smiles']);self.assertEqual(imported['supporting_records'],[])
        self.assertEqual(imported['source_url'],'https://pubchem.ncbi.nlm.nih.gov/compound/123')
        saved=json.loads((self.base/'dataset.json').read_text())
        self.assertTrue(any(s['file']=='sources/pubchem-test.json' for s in saved['provenance']['sources']))
        self.assertEqual(library(self.base)['candidates'][0]['id'],'pubchem-123')

    def test_no_hit_is_distinct_from_provider_failure(self):
        original=HTTPError('https://pubchem.ncbi.nlm.nih.gov',404,'missing',{},None)
        failure=RuntimeError('missing');failure.__cause__=original
        with patch.object(PublicData,'json',side_effect=failure):
            self.assertEqual(pubchem_search('unknown')[1],[])
        with patch.object(PublicData,'json',side_effect=RuntimeError('HTTP 500')):
            with self.assertRaises(RuntimeError):pubchem_search('caffeine')

    def test_unlinked_target_needs_no_chembl_and_does_not_claim_no_research(self):
        with patch.object(PublicData,'json',side_effect=AssertionError('No request needed')):
            client,rows,status=target_compounds(self.data['target'])
        self.assertEqual(status['status'],'unlinked');self.assertIn('does not mean no research',status['message'])

    def test_broader_activity_records_keep_endpoint_relation_flags_and_identity(self):
        base={'molecule_chembl_id':'CHEMBL1','canonical_smiles':'COc1ccccc1','target_chembl_id':'CHEMBL2',
          'assay_chembl_id':'CHEMBL3','document_chembl_id':'CHEMBL4','assay_type':'F','standard_type':'EC50',
          'standard_relation':'>','standard_value':'100','standard_units':'uM','activity_id':42,
          'data_validity_comment':'Review','assay_variant_mutation':'A10V'}
        with patch.object(PublicData,'json',return_value={'activities':[base,dict(base,target_chembl_id='CHEMBL9',molecule_chembl_id='CHEMBL8'),dict(base,canonical_smiles='CC.[Na+]',molecule_chembl_id='CHEMBL5')]}):
            client,rows,status=target_compounds({'chembl_id':'CHEMBL2'})
        self.assertEqual(len(rows),1);evidence=rows[0]['evidence'][0]
        self.assertEqual(evidence['standard_relation'],'>');self.assertEqual(evidence['assay_type'],'F')
        self.assertEqual(evidence['data_validity_comment'],'Review');self.assertEqual(evidence['assay_variant_mutation'],'A10V')
        save_lookup(self.base,self.data,client,rows,status)
        added=import_candidate(self.base,self.data,'chembl-CHEMBL1')['compound']
        self.assertNotIn('observation',added);self.assertIsNone(added['activity'])
        self.assertEqual(added['supporting_records'][0],evidence)
        self.assertEqual(catalog(self.data,[])[0]['supporting_records'][0],evidence)
        self.assertEqual(library(self.base)['target_lookup']['status'],'found')

if __name__=='__main__':unittest.main()

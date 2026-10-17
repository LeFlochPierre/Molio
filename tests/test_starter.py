"""Sequence-first setup must work without measured data and retain explicit provenance."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from molio.targets import PublicData
from molio.starter import build_starter, add_compound, select_region, search_proteins
from molio.server import load_dataset
from molio.proposals import ProposalStore, available, analyze
from molio.designs import explore, shortlist
from molio.experiments import target_sequence, Experiments, catalog


@unittest.skipUnless(available(), 'RDKit required')
class StarterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.record = {'primaryAccession':'P13569', 'organism':{'scientificName':'Homo sapiens'},
            'proteinDescription':{'recommendedName':{'fullName':{'value':'Test protein'}}},
            'sequence':{'length':800,'value':'ACDEFGHIKLMNPQRSTVWY'*40}, 'features':[]}

    def build(self):
        def response(url, name):
            if 'rest.uniprot.org' in url: return self.record
            if 'alphafold.ebi.ac.uk' in url: raise RuntimeError('Model provider unavailable')
            self.fail('Setup must not request ChEMBL or RCSB: '+url)
        with patch.object(PublicData, 'json', side_effect=response):
            return build_starter('P13569', self.folder, 'lab-0123456789ab', lambda m:None)

    def test_setup_survives_missing_model_and_measurements(self):
        data = self.build()
        self.assertIsNone(data['assay']); self.assertIsNone(data['reference_structure'])
        self.assertEqual(data['compounds'], []); self.assertEqual(data['pairs'], [])
        self.assertFalse(data['model_status']['available'])
        self.assertEqual(load_dataset(self.folder/'data')['protein_sequence'], self.record['sequence']['value'])
        with self.assertRaisesRegex(ValueError, 'region'): target_sequence(data)

    def test_region_is_explicit_and_exact_and_small_proteins_use_full_sequence(self):
        data = self.build()
        for start,end in [(1,800),(0,80),(790,900),(1,3),(True,60)]:
            with self.assertRaises(ValueError): select_region(data,start,end)
        select_region(data,41,120)
        sequence, source = target_sequence(data)
        self.assertEqual(sequence, data['protein_sequence'][40:120]); self.assertEqual(source['start'],41)
        self.assertEqual(source['end'],120)
        self.record['sequence']={'length':80,'value':'ACDEFGHIKLMNPQRSTVWY'*4}
        data = self.build(); self.assertEqual(target_sequence(data)[0], self.record['sequence']['value'])

    def test_input_to_design_to_prediction_has_no_invented_measurements(self):
        data = self.build(); select_region(data,41,120)
        result = add_compound(self.folder/'data',data,{'name':'Starting idea','smiles':'CCOc1ccccc1'})
        cid = result['compound']['id']
        self.assertNotIn('observation', result['compound'])
        self.assertEqual(result['conformer']['status'],'generated')
        with self.assertRaisesRegex(ValueError,'already'):
            add_compound(self.folder/'data',data,{'name':'Duplicate','smiles':'CCOc1ccccc1'})
        for smiles in ('bad smiles','CC.[Na+]','[Fe]',''):
            with self.assertRaises(ValueError):add_compound(self.folder/'data',data,{'name':'invalid','smiles':smiles})
        design = explore({'parent_id':cid},data)['candidates'][0]
        preview = analyze({'parent_id':cid,'smiles':design['smiles']},data)
        self.assertIsNone(preview['activity']); self.assertIsNone(preview['assay'])
        self.assertEqual(preview['neighbours'], []); self.assertEqual(preview['edit_evidence']['evidence'], [])
        store=ProposalStore(self.folder/'proposals.sqlite3')
        chosen=shortlist({'parent_id':cid,'design_ids':[design['id']]},data,store)['candidate_ids']
        rows={r['id']:r for r in catalog(data,store.list())}
        self.assertEqual(rows[cid]['kind'],'input');self.assertIsNone(rows[cid]['observation'])
        jobs=Experiments(self.folder/'experiments',store); self.addCleanup(jobs.close)
        jobs.health={'ready':True,'version':'2.2.1'}
        with patch.object(jobs.pool,'submit'):
            job=jobs.submit({'candidates':[{'id':i,'smiles':rows[i]['stereo_options'][0]} for i in chosen], 'msa_mode':'empty'},data,store)
        self.assertIsNone(job['assay']);self.assertEqual(job['sequence'],data['protein_sequence'][40:120])
        self.assertEqual(job['pose_check_mode'],'generic');self.assertEqual(job['sequence_source']['start'],41)
        self.assertTrue(all(c['source']['observation'] is None for c in job['cases']))

    def test_search_does_not_require_a_chembl_cross_reference(self):
        with patch.object(PublicData,'json',return_value={'results':[self.record]}) as fetch:
            data=search_proteins('CFTR')
        self.assertEqual(data['targets'][0]['uniprot'],'P13569')
        self.assertIsNone(data['targets'][0]['chembl_id'])
        self.assertIn('rest.uniprot.org',fetch.call_args.args[0])

    def test_model_with_wrong_sequence_is_not_used(self):
        def response(url,name):
            if 'rest.uniprot.org' in url:return self.record
            return [{'uniprotAccession':'P13569','sequence':'A'*80,'sequenceStart':1,'sequenceEnd':80,'pdbUrl':'https://alphafold.ebi.ac.uk/files/test.pdb'}]
        with patch.object(PublicData,'json',side_effect=response),patch.object(PublicData,'read') as read:
            data=build_starter('P13569',self.folder,'lab-0123456789ab',lambda m:None)
        read.assert_not_called();self.assertIsNone(data['reference_structure'])

if __name__ == '__main__':unittest.main()

"""Target import boundaries and cross-workspace isolation; no public network or model inference."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch, MagicMock

from molio.targets import Workspaces,clean_activities,reference_choices,target_info,PublicData,structure_search_messages,search_targets
from molio.server import Handler,load_dataset
from molio.proposals import ProposalStore,available
from molio.experiments import Experiments,target_sequence,catalog


@unittest.skipUnless(available(),'RDKit required')
class TargetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.manager=Workspaces(self.root);self.addCleanup(self.manager.close)

    def test_activity_filters_do_not_merge_or_choose_replicates(self):
        source=json.loads((Path(__file__).parents[1]/'molio/data/sources/activity.json').read_text())['activities'][0]
        row=dict(source,molecule_chembl_id='CHEMBL1',canonical_smiles='CCO',assay_type='B',standard_value='10',standard_units='nM',standard_type='IC50',standard_relation='=',potential_duplicate=0,data_validity_comment=None)
        self.assertEqual(clean_activities([row],row['target_chembl_id']),[row])
        for change in ({'standard_relation':'<'},{'standard_value':'NaN'},{'target_chembl_id':'CHEMBL2'},
                       {'data_validity_comment':'flagged'},{'canonical_smiles':'CC.[Na+]'},
                       {'assay_variant_mutation':'T790M'},{'standard_units':'uM'},{'assay_type':'F'}):
            self.assertEqual(clean_activities([dict(row,**change)],row['target_chembl_id']),[])
        self.assertEqual(clean_activities([row,dict(row,standard_value='12')],row['target_chembl_id']),[])
        self.assertEqual(clean_activities([row],row['target_chembl_id'],'CHEMBL999'),[])

    def test_reference_requires_matching_chain_and_organic_ligand(self):
        text=(Path(__file__).parents[1]/'molio/data/structures/3SVG.pdb').read_text()
        entry={'rcsb_entry_info':{'resolution_combined':[1.68]},'struct':{'title':'Test structure'}}
        good=reference_choices(text,'3SVG',['A'],'A'*125,entry)
        self.assertEqual(good[0]['ligand'],'ODR');self.assertEqual(good[0]['ligand_heavy_atoms'],19)
        self.assertEqual(reference_choices(text,'3SVG',['Z'],'A'*125,entry),[])
        lines=text.splitlines()
        for i,line in enumerate(lines):
            if line.startswith('HETATM') and line[17:20]=='ODR':
                lines[i]=line[:76]+'HG'+line[78:];break
        self.assertEqual(reference_choices('\n'.join(lines),'3SVG',['A'],'A'*125,entry),[])

    def test_invalid_target_or_path_cannot_be_imported(self):
        with self.assertRaises(ValueError):target_info({'target_type':'PROTEIN FAMILY','target_components':[]})
        for key in ('../brd4','/tmp','lab-../../x'):
            with self.assertRaises(ValueError):self.manager.folder(key)
        with self.assertRaises(ValueError):self.manager.submit({'target_id':'https://example.com'})
        with self.assertRaises(ValueError):PublicData().read('http://127.0.0.1/','x')
        with self.assertRaises(ValueError):self.manager.submit({'plan_id':'unknown','assay_id':'CHEMBL1','reference_id':'x'},True)

    def test_generic_pose_checks_never_claim_reference_alignment(self):
        from molio.pose_checks import diagnose_generic
        from molio.repeats import summarize
        def atom(serial,name,residue,chain,x,element):
            return f'HETATM{serial:5d} {name:^4} {residue:3} {chain}{1:4d}    {x:8.3f}{0:8.3f}{0:8.3f}{1:6.2f}{20:6.2f}          {element:>2}'
        pose=self.root/'pose.pdb'
        pose.write_text('\n'.join([atom(1,'CA','ALA','A',0,'C'),atom(2,'C1','LIG','L',3,'C'),atom(3,'C2','LIG','L',4,'C'),atom(4,'O1','LIG','L',5,'O')]))
        checks=diagnose_generic(pose,'CCO')
        self.assertEqual(checks['status'],'limited')
        self.assertIsNone(checks['reference_overlay_pdb']);self.assertIsNone(checks['protein_ca_rmsd_A'])
        self.assertEqual(checks['nearby_residues'][0]['predicted_residue'],1)
        self.assertNotIn('uniprot_residue',checks['nearby_residues'][0])
        job={'settings':{'seed':42},'cases':[{'id':'candidate','source':{'name':'test'},'smiles':'CCO','status':'complete',
             'prediction':{'pose_checks':checks,'affinity':{'affinity_pred_value':1.0}}}]}
        self.assertEqual(summarize(job)['candidates'][0]['pose_unchecked_count'],1)

    def test_provider_failure_is_not_reported_as_missing_structures(self):
        messages=structure_search_messages([],['files.rcsb.org is unavailable.'])
        self.assertIn('incomplete',messages[0])
        self.assertIn('files.rcsb.org',messages[0])
        self.assertIn('first 12',structure_search_messages([],[])[0])
        self.assertEqual(structure_search_messages([{'id':'test'}],[]),[])

    def test_search_recovers_when_text_service_fails(self):
        target={'target_chembl_id':'CHEMBL4051','pref_name':'CFTR','organism':'Homo sapiens',
                'target_type':'SINGLE PROTEIN','target_components':[{'accession':'P13569'}]}
        def response(url,name):
            if '/search.json' in url:raise RuntimeError('HTTP 500')
            return {'targets':[target]} if 'component_synonym' in url else {'targets':[]}
        with patch.object(PublicData,'json',side_effect=response):
            rows=search_targets('cFTR')['targets']
        self.assertEqual(rows[0]['chembl_id'],'CHEMBL4051')
        with patch.object(PublicData,'json',side_effect=RuntimeError('HTTP 500')):
            with self.assertRaisesRegex(RuntimeError,'temporarily unavailable'):search_targets('CFTR')
        with patch.object(PublicData,'json',return_value={'targets':{'error':'service failure'}}):
            with self.assertRaisesRegex(RuntimeError,'temporarily unavailable'):search_targets('CFTR')

    def test_search_uses_uniprot_when_chembl_is_down(self):
        def response(url,name):
            if 'rest.uniprot.org' not in url:raise RuntimeError('HTTP 500')
            return {'results':[{'primaryAccession':'P13569','organism':{'scientificName':'Homo sapiens'},
                'proteinDescription':{'recommendedName':{'fullName':{'value':'CFTR'}}},
                'uniProtKBCrossReferences':[{'database':'ChEMBL','id':'CHEMBL4051'}]}]}
        with patch.object(PublicData,'json',side_effect=response):result=search_targets('cFTR')
        self.assertEqual(result['targets'][0]['chembl_id'],'CHEMBL4051')
        self.assertIn('UniProt',result['source'])

    def test_download_retries_transient_failure_but_not_missing_files(self):
        response=MagicMock();response.__enter__.return_value=response
        response.url='https://www.ebi.ac.uk/chembl/api/data/target.json';response.read.return_value=b'{}'
        with patch('molio.targets.urlopen',side_effect=[HTTPError(response.url,500,'error',{},None),response]) as fetch,patch('molio.targets.time.sleep'):
            self.assertEqual(PublicData().read(response.url,'search.json'),b'{}');self.assertEqual(fetch.call_count,2)
        with patch('molio.targets.urlopen',side_effect=HTTPError(response.url,404,'missing',{},None)) as fetch:
            with self.assertRaises(RuntimeError):PublicData().read(response.url,'missing.json')
            self.assertEqual(fetch.call_count,1)

    def imported_fixture(self):
        key='lab-0123456789ab';folder=self.manager.directory/key/'data';folder.mkdir(parents=True)
        data=load_dataset();data['workspace_id']=key;data['target']=dict(data['target'],name='Test target',chembl_id='CHEMBL999')
        data['prediction_target']={'sequence':'ACDEFGHIKLMNPQRSTVWY'*3,'provenance':{'pdb_id':'TEST','sequence_scope':'Test fixture'},'pose_checks':'generic'}
        for c in data['compounds']:c['observation']['target_id']='CHEMBL999'
        (folder/'dataset.json').write_text(json.dumps(data));(folder/'edit-evidence.json').write_text(json.dumps(data['edit_evidence']))
        return key,data

    def test_imported_sequence_cannot_fall_back_to_brd4(self):
        key,data=self.imported_fixture();seq,source=target_sequence(data)
        self.assertEqual(len(seq),60);self.assertEqual(source['pdb_id'],'TEST')
        with self.assertRaises(ValueError):target_sequence({'workspace_id':key})
        original=ProposalStore(self.root/'proposals.sqlite3');imported=ProposalStore(self.manager.folder(key)/'proposals.sqlite3')
        jobs=Experiments(self.root/'experiments',original);self.addCleanup(jobs.close);jobs.health={'ready':True,'version':'2.2.1'}
        candidate=next(r for r in catalog(data,[]) if len(r['stereo_options'])==1)
        with patch.object(jobs.pool,'submit'):
            job=jobs.submit({'candidates':[{'id':candidate['id'],'smiles':candidate['stereo_options'][0]}],'msa_mode':'empty'},data,imported)
        self.assertEqual(job['sequence'],seq);self.assertEqual(job['workspace_id'],key);self.assertEqual(job['pose_check_mode'],'generic')
        self.assertEqual(job['target']['chembl_id'],'CHEMBL999')

    def test_http_scopes_proposals_and_data_per_request(self):
        key,data=self.imported_fixture()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.workspaces=self.manager
        server.proposal_store=ProposalStore(self.root/'proposals.sqlite3')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def get(path):
            with urlopen(base+path) as response:return json.load(response)
        try:
            imported=ProposalStore(self.manager.folder(key)/'proposals.sqlite3')
            imported.save({'same_as_parent':False,'name':'Isolated idea','parent_id':'test'})
            self.assertEqual(get('/api/dataset')['target']['chembl_id'],'CHEMBL1163125')
            self.assertEqual(get('/api/dataset?workspace='+key)['target']['chembl_id'],'CHEMBL999')
            self.assertEqual(get('/api/proposals')['proposals'],[])
            self.assertEqual(get('/api/proposals?workspace='+key)['proposals'][0]['name'],'Isolated idea')
            with self.assertRaises(HTTPError):get('/api/dataset?workspace=missing')
            with self.assertRaises(HTTPError):get('/workspaces/'+key+'/data/%2e%2e/proposals.sqlite3')
            self.assertEqual(len(self.manager.list()),2)
            jobs=Experiments(self.root/'experiments',server.proposal_store);self.addCleanup(jobs.close)
            jobs.health={'ready':True,'version':'2.2.1'};server.experiments=jobs
            candidate=next(r for r in catalog(data,[]) if len(r['stereo_options'])==1)
            with patch.object(jobs.pool,'submit'):
                job=jobs.submit({'candidates':[{'id':candidate['id'],'smiles':candidate['stereo_options'][0]}],'msa_mode':'empty'},data)
            self.assertEqual(get('/api/experiments')['experiments'],[])
            self.assertEqual(get('/api/experiments?workspace='+key)['experiments'][0]['id'],job['id'])
            request=Request(base+'/api/experiment-cancel',data=json.dumps({'id':job['id']}).encode(),headers={'Content-Type':'application/json'})
            with self.assertRaises(HTTPError) as caught:urlopen(request)
            self.assertEqual(caught.exception.code,400)
            self.assertFalse(jobs.get(job['id']).get('cancel_requested',False))
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()

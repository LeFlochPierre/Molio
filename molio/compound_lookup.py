"""Starting chemistry with explicit source evidence, independent of comparable assays."""
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.error import HTTPError
from urllib.parse import quote, urlencode

from .targets import PublicData, CHEMBL, identifier
from .starter import add_compound, persist_sources, write_json

EXAMPLES = [
    {'id':'example-anisole', 'name':'Anisole', 'smiles':'COc1ccccc1'},
    {'id':'example-benzamide', 'name':'Benzamide', 'smiles':'NC(=O)c1ccccc1'},
    {'id':'example-pyridine', 'name':'Pyridine', 'smiles':'c1ccncc1'},
]
EXAMPLES = [dict(r, source='Bundled example', source_url=None, evidence=[],
    evidence_note='Example chemistry for trying the workflow. No activity on this target is known from this example.') for r in EXAMPLES]


def library(base):
    path = base/'compound-library.json'
    data = json.loads(path.read_text()) if path.exists() else {'candidates':[], 'target_lookup':None}
    data['examples'] = EXAMPLES
    record_path = base/'sources/uniprot.json'
    record = json.loads(record_path.read_text()) if record_path.exists() else {}
    data['protein_context'] = {
        'function': [t['value'] for c in record.get('comments', []) if c.get('commentType') == 'FUNCTION' for t in c.get('texts', []) if t.get('value')],
        'structures': [{'id':r['id'], 'url':'https://www.rcsb.org/structure/'+r['id'],
            'details':' · '.join(p['value'] for p in r.get('properties', []) if p.get('key') in ('Method','Resolution','Chains'))}
            for r in record.get('uniProtKBCrossReferences', []) if r.get('database') == 'PDB' and re.fullmatch('[A-Za-z0-9]{4}',r.get('id',''))][:30]}
    return data


def pubchem_search(query):
    if not isinstance(query,str) or not 1 <= len(query.strip()) <= 100:
        raise ValueError('Enter a compound name or PubChem CID (1–100 characters).')
    query = query.strip()
    match = re.fullmatch(r'(?:CID\s*:?\s*)?(\d{1,12})', query, re.I)
    namespace, term = ('cid', match[1]) if match else ('name', quote(query, safe=''))
    client = PublicData()
    name = 'pubchem-'+hashlib.sha256(query.encode()).hexdigest()[:16]+'.json'
    try:
        body = client.json(f'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/{namespace}/{term}/property/Title,SMILES/JSON',name)
    except RuntimeError as exc:
        if isinstance(exc.__cause__,HTTPError) and exc.__cause__.code == 404:
            return client, [], 'No compound matched that name or CID. Try its precise chemical name or paste SMILES.'
        raise
    rows = body.get('PropertyTable',{}).get('Properties') if isinstance(body,dict) else None
    if not isinstance(rows,list): raise RuntimeError('PubChem returned an unreadable response. Try again or use the offline examples.')
    result = []
    for row in rows[:8]:
        if type(row.get('CID')) is not int or row['CID'] <= 0: continue
        smiles = row.get('SMILES') or row.get('IsomericSMILES')
        if not isinstance(smiles,str) or not smiles: continue
        result.append({'id':f'pubchem-{row["CID"]}', 'name':row.get('Title') or f'PubChem CID {row["CID"]}',
            'smiles':smiles, 'source':'PubChem', 'source_url':f'https://pubchem.ncbi.nlm.nih.gov/compound/{row["CID"]}',
            'evidence':[], 'evidence_note':'Chemical identity from PubChem. Activity on this protein has not been established by this lookup.'})
    return client, result, f'{len(result)} chemical structures found. Review identity and stereochemistry before adding.'


def target_compounds(target):
    client = PublicData()
    tid = target.get('chembl_id')
    if not tid:
        return client, [], {'status':'unlinked', 'message':'No ChEMBL target link in this UniProt record. This does not mean no research exists. Use compound search, your own SMILES or the example molecules.'}
    identifier(tid)
    body = client.json(CHEMBL+'activity.json?'+urlencode({'target_chembl_id':tid,'limit':100,'order_by':'activity_id'}), 'compound-activities.json')
    if not isinstance(body,dict) or not isinstance(body.get('activities'),list): raise RuntimeError('ChEMBL returned an unreadable activity list.')
    from rdkit import Chem, rdBase
    found = {}
    for row in body['activities']:
        cid, smiles = row.get('molecule_chembl_id'), row.get('canonical_smiles')
        if row.get('target_chembl_id') != tid or not isinstance(cid,str) or not re.fullmatch(r'CHEMBL\d+',cid) or not isinstance(smiles,str): continue
        with rdBase.BlockLogs(): mol = Chem.MolFromSmiles(smiles)
        if mol is None or not 2<=mol.GetNumHeavyAtoms()<=80 or mol.GetNumAtoms()>100 or len(Chem.GetMolFrags(mol))!=1: continue
        if any(a.GetAtomicNum() not in (1,5,6,7,8,9,14,15,16,17,35,53) for a in mol.GetAtoms()):continue
        if cid not in found:
            if len(found)>=12:continue
            found[cid] = {'id':'chembl-'+cid, 'name':row.get('molecule_pref_name') or cid, 'smiles':smiles,
                'source':'ChEMBL target-associated record','source_url':f'https://www.ebi.ac.uk/chembl/explore/compound/{cid}',
                'evidence_note':'Reported assay records for this target; not a confirmed binder list. Assays, endpoints and constructs may differ. No values are averaged or used to rank molecules.', 'evidence':[]}
        if len(found[cid]['evidence'])<6:
            keys=('activity_id','target_chembl_id','assay_chembl_id','document_chembl_id','assay_description','assay_type',
                  'standard_type','standard_relation','standard_value','standard_units','data_validity_comment','potential_duplicate','assay_variant_mutation')
            found[cid]['evidence'].append({k:row.get(k) for k in keys})
    return client,list(found.values()),{'status':'found' if found else 'empty',
        'message':f'{len(found)} usable molecules in the first {len(body["activities"])} target-associated records. All assay types and endpoints were considered; up to 12 molecules and 6 records per molecule are shown. This is a bounded search, not the complete literature.'}


def save_lookup(base, data, client, rows, target_status=None):
    cached = library(base)
    known = {r['id']:r for r in cached['candidates']}
    known.update({r['id']:r for r in rows})
    # Cap saved search suggestions; imported molecules keep their own full provenance.
    cached = {'candidates':list(known.values())[-100:], 'target_lookup':cached['target_lookup']}
    if target_status is not None: cached['target_lookup'] = dict(target_status, checked_at=datetime.now(timezone.utc).isoformat())
    persist_sources(base,data,client)
    write_json(base/'compound-library.json',cached);write_json(base/'dataset.json',data)


def import_candidate(base, data, candidate_id):
    if not isinstance(candidate_id,str):raise ValueError('Choose a compound from the available results')
    rows = [*EXAMPLES,*library(base)['candidates']]
    row = next((r for r in rows if r['id']==candidate_id),None)
    if row is None:raise ValueError('Search for this compound again before importing')
    return add_compound(base,data,{'name':row['name'],'smiles':row['smiles']},origin=row)

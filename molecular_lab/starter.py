"""Sequence-first workspaces: measurements and a display model are optional."""
import hashlib
import json
from pathlib import Path
import re
import uuid

from .targets import PublicData, identifier

UNIPROT = 'https://rest.uniprot.org/uniprotkb/'


def protein_info(record):
    accession = identifier(record['primaryAccession'], r'[A-Z0-9]{6,10}')
    name = record.get('proteinDescription', {}).get('recommendedName', {}).get('fullName', {}).get('value') or accession
    links = [x['id'] for x in record.get('uniProtKBCrossReferences', [])
             if x.get('database') == 'ChEMBL' and re.fullmatch(r'CHEMBL\d+', x.get('id', ''))]
    return {'uniprot': accession, 'name': name, 'organism': record['organism']['scientificName'],
            'chembl_id': links[0] if links else None, 'length': record.get('sequence', {}).get('length')}


def search_proteins(term):
    from urllib.parse import urlencode
    if not isinstance(term, str) or not 2 <= len(term.strip()) <= 100:
        raise ValueError('Enter a protein name, gene symbol or UniProt accession (2–100 characters)')
    term = term.strip()
    if re.fullmatch(r'CHEMBL\d+', term.upper()):
        from .targets import search_targets
        return search_targets(term)
    words = ' '.join(re.findall(r'[\w-]+', term))
    if not words: raise ValueError('Enter a protein name or accession')
    query = f'(gene_exact:"{words}" OR protein_name:"{words}" OR accession:{words}) AND reviewed:true' if re.fullmatch(r'(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})', term.upper()) else f'(gene_exact:"{words}" OR protein_name:"{words}") AND reviewed:true'
    client = PublicData()
    body = client.json(UNIPROT+'search?'+urlencode({'query':query, 'format':'json', 'size':20}), 'protein-search.json')
    if not isinstance(body, dict) or not isinstance(body.get('results'), list):
        raise RuntimeError('Protein search is temporarily unavailable. Saved workspaces still work.')
    rows = [protein_info(r) for r in body['results']]
    rows.sort(key=lambda r: (r['organism'] != 'Homo sapiens', r['name'], r['organism']))
    return {'targets': rows, 'source': 'UniProt', 'scope': 'Sequence-first setup; measurements are optional.'}


def write_json(path, value):
    """Replace one complete snapshot, so readers never see partially written JSON."""
    path = Path(path)
    temporary = path.with_name('.'+path.name+'.'+uuid.uuid4().hex)
    try:
        temporary.write_text(json.dumps(value, indent=2, allow_nan=False))
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def persist_sources(base, data, client):
    (base/'sources').mkdir(exist_ok=True)
    known = {s['file']:s for s in data['provenance']['sources']}
    for name, (url, raw) in client.sources.items():
        (base/'sources'/name).write_bytes(raw)
        known['sources/'+name] = {'file':'sources/'+name, 'url':url, 'sha256':hashlib.sha256(raw).hexdigest()}
    data['provenance']['sources'] = list(known.values())


def download_model(base, data, client):
    """AFDB is display context, never an experimental ligand pose or a Boltz template."""
    accession = data['target']['uniprot']
    data['model_status'] = {'available':False, 'message':'No compatible full-sequence model was returned. You can still design and predict from the sequence.'}
    try:
        records = client.json(f'https://alphafold.ebi.ac.uk/api/prediction/{accession}', 'alphafold.json')
        if not isinstance(records, list): raise RuntimeError('AlphaFold DB returned an unreadable model list.')
        record = next((r for r in records if r.get('uniprotAccession') == accession
            and r.get('sequence', r.get('uniprotSequence')) == data['protein_sequence']
            and r.get('sequenceStart', r.get('uniprotStart')) == 1
            and r.get('sequenceEnd', r.get('uniprotEnd')) == len(data['protein_sequence']) and r.get('pdbUrl')), None)
        if record is None: return
        raw = client.read(record['pdbUrl'], 'alphafold.pdb')
        chain = record.get('chainId', 'A')
        # Confirm display coordinates cover the canonical sequence; do not silently display fragments.
        residues = [l for l in raw.decode('ascii').splitlines() if l.startswith('ATOM  ') and l[12:16].strip() == 'CA' and l[21:22] == chain and l[16:17] in (' ', 'A')]
        codes = dict(zip('ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL'.split(), 'ARNDCQEGHILKMFPSTWYV'))
        if (''.join(codes.get(l[17:20], '?') for l in residues) != data['protein_sequence']
                or [int(l[22:26]) for l in residues] != list(range(1, len(data['protein_sequence'])+1))):
            raise RuntimeError('Model coordinates do not match the full canonical sequence.')
        (base/'structures').mkdir(exist_ok=True)
        (base/'structures'/'alphafold.pdb').write_bytes(raw)
        data['reference_structure'] = {'id':record.get('entryId', record.get('modelEntityId', accession)),
            'kind':'predicted', 'chain':chain, 'ligand':None,
            'url':f'/workspaces/{data["workspace_id"]}/data/structures/alphafold.pdb',
            'source_url':f'https://alphafold.ebi.ac.uk/entry/{accession}',
            'label':'AlphaFold DB · predicted protein · no ligand',
            'caveat':'Precomputed model for viewing, not an experimental structure or binding result. Not used as a prediction template.'}
        data['model_status'] = {'available':True, 'message':'AlphaFold model downloaded for 3D viewing. No binding pocket is assigned.'}
    except (RuntimeError, ValueError, UnicodeDecodeError, KeyError) as exc:
        data['model_status']['message'] = f'Model download unavailable: {exc} Sequence workspace is usable; retry the model later.'


def select_region(data, start, end):
    sequence = data['protein_sequence']
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(sequence) or not 40 <= end-start+1 <= 600:
        raise ValueError('Choose an explicit region of 40–600 residues within this protein (inclusive UniProt positions).')
    selected = sequence[start-1:end]
    if not re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+', selected):
        raise ValueError('The selected sequence contains unsupported or ambiguous amino acids.')
    data['prediction_target'] = {'sequence':selected, 'pose_checks':'generic', 'provenance':{
        'uniprot':data['target']['uniprot'], 'source_url':f'https://www.uniprot.org/uniprotkb/{data["target"]["uniprot"]}/entry',
        'start':start, 'end':end, 'sequence_sha256':hashlib.sha256(selected.encode()).hexdigest(),
        'sequence_scope':f'Canonical UniProt residues {start}–{end} (inclusive). Model numbering starts at 1. A cropped region is not the full protein.'}}


def build_starter(accession, directory, workspace_id, progress):
    client = PublicData()
    accession = identifier(accession, r'[A-Z0-9]{6,10}')
    progress('Downloading the protein sequence from UniProt…')
    record = client.json(UNIPROT+accession+'.json', 'uniprot.json')
    target = protein_info(record)
    sequence = record['sequence']['value']
    if not isinstance(sequence, str) or not re.fullmatch('[A-Z]{1,10000}', sequence):
        raise ValueError('Unsupported protein sequence; use a protein with at most 10,000 residues.')
    domains = []
    for f in record.get('features', []):
        if f.get('type') != 'Domain': continue
        start, end = f['location']['start'], f['location']['end']
        if start.get('modifier') == end.get('modifier') == 'EXACT' and 1 <= start['value'] <= end['value'] <= len(sequence):
            domains.append({'name':f.get('description', 'Annotated domain'), 'start':start['value'], 'end':end['value']})
    base = Path(directory)/'data'; base.mkdir(parents=True, exist_ok=True)
    data = {'schema_version':1, 'workspace_id':workspace_id, 'mode':'starter', 'target':target,
        'protein_sequence':sequence, 'domains':domains, 'compounds':[], 'pairs':[],
        'assay':None, 'publication':None, 'reference_structure':None,
        'conformers_url':f'/workspaces/{workspace_id}/data/conformers.json',
        'dataset_url':f'/workspaces/{workspace_id}/data/dataset.json',
        'provenance':{'sources':[], 'data_license':'UniProt and AlphaFold DB: CC BY 4.0.', 'limitations':[
            'No measured activities have been imported. Added molecules are untested inputs.',
            'An AlphaFold model is predicted display context, not a verified bound pose.',
            'Local predictions omit MSA, templates, membrane, cofactors and other chains.',
            'Cropped-region predictions do not represent the full protein or establish functional modulation.']}}
    if 40 <= len(sequence) <= 600 and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+', sequence): select_region(data, 1, len(sequence))
    progress('Downloading an available AlphaFold model for 3D viewing…')
    download_model(base, data, client)
    persist_sources(base, data, client)
    write_json(base/'conformers.json', {}); write_json(base/'edit-evidence.json', {})
    write_json(base/'dataset.json', data)
    return data


def add_compound(base, data, payload, *, origin=None):
    from .proposals import available
    if not available(): raise RuntimeError('Adding molecules needs the chemistry environment (RDKit).')
    if not isinstance(payload, dict) or set(payload) != {'name','smiles'}:
        raise ValueError('Expected a name and SMILES')
    if any(not isinstance(payload[k], str) or len(payload[k]) > limit for k,limit in [('name',100),('smiles',1000)]):
        raise ValueError('Use a name up to 100 characters and SMILES up to 1,000 characters')
    if len(data['compounds']) >= 30: raise ValueError('This workspace supports up to 30 starting molecules.')
    from rdkit import Chem, rdBase
    from rdkit.Chem import Descriptors
    from .conformers import conformer
    with rdBase.BlockLogs(): mol = Chem.MolFromSmiles(payload['smiles'].strip())
    if mol is None or not 2 <= mol.GetNumHeavyAtoms() <= 80 or mol.GetNumAtoms() > 100 or len(Chem.GetMolFrags(mol)) != 1:
        raise ValueError('Enter one connected molecule with 2–80 heavy atoms; mixtures and salts are unsupported.')
    if any(a.GetAtomicNum() not in (1,5,6,7,8,9,14,15,16,17,35,53) for a in mol.GetAtoms()):
        raise ValueError('Use ordinary organic atoms; metals and unspecified atoms are unsupported.')
    for a in mol.GetAtoms(): a.SetAtomMapNum(0)
    smiles = Chem.MolToSmiles(mol)
    if any(c['canonical_smiles'] == smiles for c in data['compounds']): raise ValueError('This molecule is already in your workspace.')
    cid = 'input-'+uuid.uuid4().hex[:12]
    shape = conformer(smiles)
    data['compounds'].append({'id':cid, 'name':payload['name'].strip() or cid, 'smiles':smiles,
        'canonical_smiles':smiles, 'kind':'input', 'activity':None, 'experimental_pose':None,
        'molecular_weight':round(Descriptors.MolWt(mol),2), 'source':'User-supplied SMILES; no measured activity',
        'unassigned_stereocentres':sum(tag=='?' for _,tag in Chem.FindMolChiralCenters(mol,includeUnassigned=True))})
    if origin:
        data['compounds'][-1].update(source=origin['source'], source_url=origin.get('source_url'),
            origin=origin, supporting_records=origin.get('evidence', []))
    shapes = json.loads((base/'conformers.json').read_text()); shapes[cid] = shape
    write_json(base/'conformers.json', shapes); write_json(base/'dataset.json', data)
    return {'compound':data['compounds'][-1], 'conformer':shape}

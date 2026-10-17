"""Bounded public-data imports into isolated, reusable local workspaces."""
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import threading
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

CHEMBL = 'https://www.ebi.ac.uk/chembl/api/data/'
ALLOWED_HOSTS = {'www.ebi.ac.uk', 'search.rcsb.org', 'data.rcsb.org', 'files.rcsb.org', 'rest.uniprot.org', 'alphafold.ebi.ac.uk', 'pubchem.ncbi.nlm.nih.gov'}
MAX_RECORDS = 500
MAX_COMPOUNDS = 12


def identifier(value, pattern=r'CHEMBL\d+'):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError('Invalid public database identifier')
    return value


class PublicData:
    """Only fixed public providers; size/time bounds and exact source snapshots."""
    def __init__(self):
        self.sources = {}
        self.lock = threading.Lock()

    def read(self, url, name):
        if urlsplit(url).scheme != 'https' or urlsplit(url).hostname not in ALLOWED_HOSTS:
            raise ValueError('Unsupported public data provider')
        for attempt in range(2):
            try:
                request = Request(url, headers={'User-Agent': 'MolecularWhatIfLab/0.1', 'Accept': 'application/json,text/plain'})
                with urlopen(request, timeout=15) as response:
                    if urlsplit(response.url).hostname not in ALLOWED_HOSTS:
                        raise ValueError('Unexpected provider redirect')
                    raw = response.read(8_000_001)
                if len(raw) > 8_000_000:
                    raise ValueError('Source is too large for this local importer')
                break
            except HTTPError as exc:
                if attempt == 0 and exc.code in (429, 500, 502, 503, 504):
                    time.sleep(.5)
                    continue
                raise RuntimeError(f'Could not download {name} from {urlsplit(url).hostname} (HTTP {exc.code}).') from exc
            except (URLError, TimeoutError, OSError) as exc:
                if attempt == 0:
                    time.sleep(.5)
                    continue
                raise RuntimeError(f'{urlsplit(url).hostname} is unavailable. Try again when online.') from exc
        with self.lock:
            self.sources[name] = (url, raw)
        return raw

    def json(self, url, name):
        raw = self.read(url, name)
        try:
            return json.loads(raw) if raw else {'result_set': []}
        except (ValueError, UnicodeDecodeError) as exc:
            raise RuntimeError('The public provider returned an unreadable response. Try again later.') from exc


def target_info(record):
    components = record.get('target_components', [])
    if record.get('target_type') != 'SINGLE PROTEIN' or len(components) != 1 or not components[0].get('accession'):
        raise ValueError('Choose a single protein with a UniProt accession')
    return {'chembl_id': identifier(record['target_chembl_id']), 'name': record['pref_name'],
            'organism': record['organism'], 'uniprot': components[0]['accession']}


def uniprot_target_matches(client, term):
    """Recover target identity via reviewed UniProt records and their ChEMBL cross-references."""
    words = ' '.join(re.findall(r'[\w-]+', term))
    if not words: return []
    query = f'(gene_exact:"{words}" OR protein_name:"{words}") AND reviewed:true'
    data = client.json('https://rest.uniprot.org/uniprotkb/search?'+urlencode(
        {'query':query,'format':'json','size':10}), 'uniprot-search.json')
    records = []
    if not isinstance(data.get('results'),list): raise RuntimeError('UniProt search is temporarily unavailable')
    for record in data['results']:
        name = record.get('proteinDescription',{}).get('recommendedName',{}).get('fullName',{}).get('value')
        accession = record.get('primaryAccession')
        species = record.get('organism',{}).get('scientificName')
        if not all((name,accession,species)): continue
        for link in record.get('uniProtKBCrossReferences',[]):
            if link.get('database') == 'ChEMBL' and re.fullmatch(r'CHEMBL\d+',link.get('id','')):
                records.append({'target_type':'SINGLE PROTEIN','target_chembl_id':link['id'],
                    'pref_name':name,'organism':species,'target_components':[{'accession':accession}]})
    return records


def search_targets(term):
    if not isinstance(term, str) or not 2 <= len(term.strip()) <= 100:
        raise ValueError('Enter 2–100 characters: a protein name or ChEMBL target ID')
    client = PublicData()
    lookup_source = 'ChEMBL'
    def target_rows(url, name):
        body = client.json(url, name)
        rows = body.get('targets') if isinstance(body, dict) else None
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise RuntimeError('ChEMBL returned an invalid target-search response')
        return rows
    if re.fullmatch(r'CHEMBL\d+', term.strip().upper()):
        rows = [client.json(CHEMBL+'target/'+term.strip().upper()+'.json', 'search.json')]
    else:
        try:
            rows = target_rows(CHEMBL+'target/search.json?'+urlencode({'q': term.strip(), 'limit': 30}), 'search.json')
        except RuntimeError:
            rows = None
        if not rows:
            # Direct filters use a different ChEMBL route from its text-search service.
            # A gene acronym need not appear in the preferred protein name.
            def filtered(field):
                return target_rows(CHEMBL+'target.json?'+urlencode({field:term.strip(), 'limit':30}), field+'.json')
            successful, combined = 0, []
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(filtered, field) for field in (
                    'target_components__target_component_synonyms__component_synonym__iexact',
                    'pref_name__icontains')]
                for future in futures:
                    try:
                        combined.extend(future.result()); successful += 1
                    except RuntimeError:
                        pass
            if combined:
                rows = list({row['target_chembl_id']:row for row in combined}.values())
            else:
                try:
                    alternate = uniprot_target_matches(client, term)
                except RuntimeError:
                    alternate = []
                if alternate:
                    rows = alternate; lookup_source = 'UniProt with ChEMBL target links'
                elif rows is None or successful != 2:
                    raise RuntimeError('Public target search is temporarily unavailable. Automatic retries and alternative lookups did not return a result. Try again shortly; your saved workspaces still work.')
    result = []
    for row in rows:
        try:
            result.append(target_info(row))
        except ValueError:
            continue
    return {'targets': result[:15], 'source': lookup_source, 'scope': 'Single proteins with a UniProt accession; availability is checked next.'}


def clean_activities(records, target_id, assay_id=None):
    """Do not merge assays, censored values, flagged data or replicate measurements."""
    from rdkit import Chem, rdBase
    from .evidence import normalize_observation
    valid = []
    for row in records:
        if (row.get('target_chembl_id') != target_id or (assay_id and row.get('assay_chembl_id') != assay_id)
                or row.get('standard_type') != 'IC50' or row.get('standard_relation') != '='
                or row.get('standard_units') != 'nM' or row.get('assay_type') != 'B'
                or row.get('data_validity_comment') or row.get('potential_duplicate')
                or row.get('assay_variant_mutation') or not row.get('document_chembl_id')):
            continue
        try:
            normalize_observation(row)
            identifier(row['molecule_chembl_id']); identifier(row['assay_chembl_id']); identifier(row['document_chembl_id'])
            with rdBase.BlockLogs():
                mol = Chem.MolFromSmiles(row.get('canonical_smiles') or '')
            if mol is None or not 3 <= mol.GetNumHeavyAtoms() <= 80 or len(Chem.GetMolFrags(mol)) != 1:
                continue
            if any(a.GetAtomicNum() not in (1,5,6,7,8,9,14,15,16,17,35,53) for a in mol.GetAtoms()):
                continue
            valid.append(row)
        except (ValueError, TypeError, KeyError):
            continue
    # Exclude all repeated records of a molecule within an assay, rather than choosing a convenient value.
    counts = Counter((r.get('assay_chembl_id'), r.get('molecule_chembl_id')) for r in records)
    return [r for r in valid if counts[(r['assay_chembl_id'], r['molecule_chembl_id'])] == 1]


def structure_options(client, target):
    def terminal(attribute, operator, value):
        return {'type': 'terminal', 'service': 'text', 'parameters': dict(attribute=attribute, operator=operator, value=value)}
    query = {'query': {'type': 'group', 'logical_operator': 'and', 'nodes': [
        terminal('rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession', 'exact_match', target['uniprot']),
        terminal('rcsb_entry_info.nonpolymer_entity_count', 'greater', 0),
        terminal('entity_poly.rcsb_sample_sequence_length', 'range', {'from':40,'to':600}),
        terminal('entity_poly.rcsb_mutation_count', 'equals', 0),
        terminal('exptl.method', 'exact_match', 'X-RAY DIFFRACTION')]},
        'return_type': 'polymer_entity', 'request_options': {'paginate': {'start': 0, 'rows': 12},
            'sort': [{'sort_by': 'rcsb_entry_info.resolution_combined', 'direction': 'asc'}]}}
    hits = client.json('https://search.rcsb.org/rcsbsearch/v2/query?'+urlencode({'json': json.dumps(query)}), 'structure-search.json')

    def inspect(hit):
        code, entity = hit['identifier'].split('_')
        identifier(code, r'[A-Za-z0-9]{4}'); identifier(entity, r'\d+')
        polymer = client.json(f'https://data.rcsb.org/rest/v1/core/polymer_entity/{code}/{entity}', f'{code}-{entity}-polymer.json')
        ids = polymer['rcsb_polymer_entity_container_identifiers']
        accessions = [r['database_accession'] for r in ids.get('reference_sequence_identifiers', []) if r.get('database_name') == 'UniProt']
        if accessions != [target['uniprot']]: return []
        sequence = re.sub(r'\s', '', polymer['entity_poly']['pdbx_seq_one_letter_code_can'])
        if not 40 <= len(sequence) <= 600 or not re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+', sequence): return []
        if polymer.get('rcsb_polymer_entity', {}).get('pdbx_mutation') or polymer['entity_poly'].get('rcsb_mutation_count', 0): return []
        entry = client.json(f'https://data.rcsb.org/rest/v1/core/entry/{code}', f'{code}-entry.json')
        text = client.read(f'https://files.rcsb.org/download/{code}.pdb', f'{code}.pdb').decode('ascii')
        return reference_choices(text, code, ids.get('auth_asym_ids', []), sequence, entry)

    options, issues = [], []
    # A bounded search, not an exhaustive structure audit.
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(inspect, hit) for hit in hits.get('result_set', [])]
        for future in futures:
            try: options.extend(future.result())
            except (RuntimeError, ValueError, KeyError, UnicodeDecodeError) as exc: issues.append(str(exc))
    unique = {}
    for row in options:
        unique.setdefault(row['id'], row)
    return list(unique.values())[:6], issues


def reference_choices(text, code, chains, sequence, entry):
    """Find a resolved organic reference within 5 Å of the accession-matched chain."""
    atoms = []
    for line in text.splitlines():
        if line.startswith('ENDMDL'): break
        if not line.startswith(('ATOM  ', 'HETATM')) or line[16:17] not in (' ', 'A') or line[26:27].strip(): continue
        element = line[76:78].strip().title()
        if element in ('H', 'D') or not element: continue
        xyz = tuple(float(line[a:b]) for a,b in ((30,38),(38,46),(46,54)))
        if not all(math.isfinite(v) for v in xyz): continue
        atoms.append((line[:6].strip(), line[21], int(line[22:26]), line[17:20].strip(), element, xyz))
    grouped = defaultdict(list)
    for a in atoms:
        if a[0] == 'HETATM' and a[3] not in {'HOH','GOL','EDO','PEG','DMS','SO4','PO4','ACT','TRS','MPD','BME','BGC','GLC','NAG','MAN','GAL','FUC','MES','HEP'}:
            grouped[a[1:4]].append(a)
    result = []
    for chain in chains:
        if len(chain) != 1: continue
        protein = [a for a in atoms if a[0] == 'ATOM' and a[1] == chain]
        if not protein: continue
        for (lig_chain, residue, ligand), group in grouped.items():
            if not 8 <= len(group) <= 80 or not any(a[4] == 'C' for a in group): continue
            if any(a[4] not in {'B','C','N','O','F','Si','P','S','Cl','Br','I'} for a in group): continue
            distance = min(math.dist(a[5], b[5]) for a in group for b in protein)
            if distance > 5: continue
            result.append({'id': f'{code}-{chain}-{lig_chain}-{residue}', 'pdb_id': code,
                'chain': chain, 'ligand_chain': lig_chain, 'ligand_residue': residue, 'ligand': ligand,
                'ligand_heavy_atoms': len(group), 'sequence': sequence, 'length': len(sequence),
                'resolution_A': (entry.get('rcsb_entry_info', {}).get('resolution_combined') or [None])[0],
                'title': entry.get('struct', {}).get('title', code),
                'source_url': f'https://www.rcsb.org/structure/{code}'})
            break
        if result: break
    return result


def structure_search_messages(structures, issues):
    if issues:
        detail = ' '.join(dict.fromkeys(issues))
        return [f'Structure lookup was incomplete: {detail} Retry Check data. This is not evidence that suitable structures do not exist.']
    if not structures:
        return ['No compatible organic-ligand reference was found among the first 12 eligible X-ray constructs (40–600 residues, no annotated mutations). This bounded search does not cover every structure.']
    return []


def inspect_target(target_id, progress):
    from .proposals import available
    if not available(): raise RuntimeError('Target setup needs RDKit. Start with the chemistry environment.')
    client = PublicData()
    target = target_info(client.json(CHEMBL+'target/'+identifier(target_id)+'.json', 'target.json'))
    progress('Finding comparable measurements in ChEMBL…')
    response = client.json(CHEMBL+'activity.json?'+urlencode(dict(target_chembl_id=target_id,
        standard_type='IC50', standard_relation='=', standard_units='nM', assay_type='B',
        limit=MAX_RECORDS, order_by='assay_chembl_id')), 'activity-search.json')
    groups = defaultdict(list)
    for row in clean_activities(response['activities'], target_id):
        groups[(row['assay_chembl_id'], row['document_chembl_id'])].append(row)
    assays = []
    for (assay_id, doc_id), rows in sorted(groups.items(), key=lambda x: (-len(x[1]), x[0]))[:8]:
        if len(rows) < 2: continue
        record = client.json(CHEMBL+'assay/'+assay_id+'.json', assay_id+'.json')
        if (record.get('confidence_score') != 9 or record.get('target_chembl_id') != target_id
                or record.get('assay_type') != 'B' or record.get('variant_sequence')): continue
        assays.append({'id': assay_id, 'document_id': doc_id, 'description': record['description'],
                       'count': len(rows), 'organism': record.get('assay_organism'), 'confidence_score': 9})
        if len(assays) == 4: break
    progress('Checking experimental structures and protein identity…')
    structures, issues = structure_options(client, target)
    structure_messages = structure_search_messages(structures, issues)
    public = {'target': target, 'assays': assays, 'structures': [{k:v for k,v in row.items() if k != 'sequence'} for row in structures],
              'ready': bool(assays and structures), 'structure_search_warnings': structure_messages if structures else [],
              'scope': f'Preview scans at most {MAX_RECORDS} IC50 records and up to 12 X-ray constructs prefiltered by length and mutation annotations. Import uses up to {MAX_COMPOUNDS} molecules from one assay/publication. This is not the full target literature.',
              'limitations': ['Reference protein constructs and assay constructs may differ; review their descriptions.',
                  'Predictions use the selected PDB protein construct, without MSA, templates, cofactors or other protein chains.'],
              'issues': ([] if assays else ['No supported same-assay IC50 series found in the bounded search.'])
                        + ([] if structures else structure_messages)}
    return {'public': public, 'client': client, 'structures': structures}


def build_workspace(plan, assay_id, reference_id, directory, workspace_id, progress):
    from rdkit import Chem, DataStructs, rdBase
    from rdkit.Chem import Descriptors, rdDepictor, rdFMCS, rdFingerprintGenerator
    from rdkit.Chem.Draw import rdMolDraw2D
    from .evidence import normalize_observation, compare_observations
    from .conformers import conformer
    from .edit_evidence import evidence_for_edit
    target, client = plan['public']['target'], plan['client']
    selected = next((a for a in plan['public']['assays'] if a['id'] == assay_id), None)
    reference = next((r for r in plan['structures'] if r['id'] == reference_id), None)
    if not selected or not reference: raise ValueError('Choose an assay and structure from this target preview')
    progress('Downloading the selected assay and source records…')
    response = client.json(CHEMBL+'activity.json?'+urlencode({'assay_chembl_id': assay_id, 'limit': 1000}), 'activity.json')
    if response.get('page_meta', {}).get('next'):
        raise ValueError('This assay has more than 1,000 records. Choose a smaller assay to avoid an incomplete import.')
    records = [r for r in clean_activities(response['activities'], target['chembl_id'], assay_id)
               if r['document_chembl_id'] == selected['document_id']]
    mols = {r['molecule_chembl_id']: Chem.MolFromSmiles(r['canonical_smiles']) for r in records}
    # Remove duplicate chemical identities rather than quietly choosing a measurement.
    identities = Counter(Chem.MolToSmiles(m) for m in mols.values())
    records = [r for r in records if identities[Chem.MolToSmiles(mols[r['molecule_chembl_id']])] == 1]
    if len(records) < 2: raise ValueError('Fewer than two usable distinct molecules remain after checking the complete assay.')
    records.sort(key=lambda r: r['molecule_chembl_id'])
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    fps = {r['molecule_chembl_id']: gen.GetFingerprint(mols[r['molecule_chembl_id']]) for r in records}
    if len(records) > MAX_COMPOUNDS:
        anchor = max(records, key=lambda r: sum(DataStructs.TanimotoSimilarity(fps[r['molecule_chembl_id']], other) for other in fps.values()))
        records.sort(key=lambda r: (-DataStructs.TanimotoSimilarity(fps[anchor['molecule_chembl_id']], fps[r['molecule_chembl_id']]), r['molecule_chembl_id']))
        records = records[:MAX_COMPOUNDS]
    document = client.json(CHEMBL+'document/'+selected['document_id']+'.json', 'document.json')
    base = Path(directory) / 'data'
    for name in ('sources', 'depictions', 'structures'): (base/name).mkdir(parents=True, exist_ok=True)
    asset = f'/workspaces/{workspace_id}/data/'
    def draw(mol, filename, changed=()):
        drawer = rdMolDraw2D.MolDraw2DSVG(440,250); drawer.drawOptions().clearBackground=False
        drawer.drawOptions().setHighlightColour((.95,.65,.30,.65))
        rdMolDraw2D.PrepareAndDrawMolecule(drawer,mol,highlightAtoms=list(changed)); drawer.FinishDrawing()
        (base/'depictions'/filename).write_text(drawer.GetDrawingText())
        return asset+'depictions/'+filename
    progress('Preparing local chemistry and interactive 3D molecules…')
    compounds, shapes = [], {}
    for row in records:
        cid = row['molecule_chembl_id']; mol = mols[cid]; rdDepictor.Compute2DCoords(mol)
        compounds.append({'id':cid, 'smiles':row['canonical_smiles'], 'canonical_smiles':Chem.MolToSmiles(mol),
            'observation':normalize_observation(row), 'molecular_weight':round(Descriptors.MolWt(mol),2),
            'unassigned_stereocentres':sum(tag=='?' for _,tag in Chem.FindMolChiralCenters(mol,includeUnassigned=True)),
            'depiction':draw(mol,cid+'.svg'), 'source_url':f'https://www.ebi.ac.uk/chembl/explore/compound/{cid}', 'experimental_pose':None})
        shapes[cid] = conformer(row['canonical_smiles'])
    candidates = [(DataStructs.TanimotoSimilarity(fps[a['id']],fps[b['id']]),a,b)
                  for i,a in enumerate(compounds) for b in compounds[i+1:]]
    candidates.sort(key=lambda x: (-x[0],x[1]['id'],x[2]['id']))
    pairs = []
    for similarity, a, b in candidates[:8]:
        pid = 'pair-'+str(len(pairs)+1)
        common = rdFMCS.FindMCS([mols[a['id']],mols[b['id']]], timeout=1, ringMatchesRingOnly=True,
                               completeRingsOnly=True,bondCompare=rdFMCS.BondCompare.CompareOrderExact)
        query = Chem.MolFromSmarts(common.smartsString) if not common.canceled and common.numAtoms >= 3 else None
        if query is not None: rdDepictor.Compute2DCoords(query)
        mapping,pictures = {},{}
        for c in (a,b):
            cid=c['id']; mol=Chem.Mol(mols[cid]); match=mol.GetSubstructMatch(query) if query is not None else ()
            if match: rdDepictor.GenerateDepictionMatching2DStructure(mol,query)
            changed=[i for i in range(mol.GetNumAtoms()) if i not in match] if match else []
            mapping[cid]={'common_atoms':list(match),'changed_atoms':changed}
            pictures[cid]=draw(mol,pid+'-'+cid+'.svg',changed)
        pairs.append({'id':pid,'left':a['id'],'right':b['id'],'title':f"{a['id']} → {b['id']}",
            **compare_observations(a['observation'],b['observation']), 'common_smarts':common.smartsString if query is not None else None,
            'atom_mapping':mapping,'depictions':pictures,'similarity':round(similarity,3),
            'method':'Same-assay pair selected by fingerprint similarity; not an asserted single chemical edit.'})
    code = reference['pdb_id']; raw = client.sources[code+'.pdb'][1]
    resolved = '\n'.join(line for line in raw.decode('ascii').splitlines()
        if not line.startswith(('ATOM  ', 'HETATM')) or line[16:17] in (' ', 'A')) + '\n'
    (base/'structures'/f'{code}.pdb').write_text(resolved)
    warnings = [plan['public']['scope'], 'One assay and one publication; no independent validation.',
        'IC50 values are measured assay responses, not binding free energies.',
        'Pairs are selected by molecular similarity, not asserted matched single edits.',
        'Source assay stereochemistry is retained; generated shapes are illustrative, not bound poses.',
        *plan['public']['limitations']]
    data = {'schema_version':1,'workspace_id':workspace_id,'target':target,'title':'Explore a new target.',
        'assay':dict(id=assay_id,description=selected['description'],organism=selected['organism'],confidence_score=9,
                     url=f'https://www.ebi.ac.uk/chembl/explore/assay/{assay_id}'),
        'publication':{k:document.get(k) for k in ('title','authors','doi','year','document_chembl_id')},
        'compounds':compounds,'pairs':pairs,'conformers_url':asset+'conformers.json','dataset_url':asset+'dataset.json',
        'reference_structure':dict(reference,id=code,url=asset+f'structures/{code}.pdb',
            related_compound=None,label=f'Experimental reference · {code} / {reference["ligand"]}',
            caveat='Experimental reference ligand only. Neither selected compound is assigned this bound pose.'),
        'prediction_target':{'sequence':reference['sequence'],'provenance':{'pdb_id':code,'chain':reference['chain'],
            'uniprot':target['uniprot'],'source_url':reference['source_url'],
            'sequence_scope':'Deposited protein construct, including any expression tags. Model residues start at 1.',
            'sequence_sha256':hashlib.sha256(reference['sequence'].encode()).hexdigest(),
            'coordinate_policy':'Reference display retains blank/A alternate locations; original PDB preserved in sources.'}, 'pose_checks':'generic'},
        'provenance':{'rdkit':rdBase.rdkitVersion,'sources':[],
                      'data_license':'ChEMBL: CC BY-SA 3.0; PDB coordinates: CC0.','limitations':warnings}}
    del data['reference_structure']['sequence']
    evidence = {p['id']:evidence_for_edit(next(c['smiles'] for c in compounds if c['id']==p['left']),
                 next(c['smiles'] for c in compounds if c['id']==p['right']),data) for p in pairs}
    for name,(url,content) in client.sources.items():
        (base/'sources'/name).write_bytes(content)
        data['provenance']['sources'].append({'file':'sources/'+name,'url':url,'sha256':hashlib.sha256(content).hexdigest()})
    for name,value in [('dataset.json',data),('conformers.json',shapes),('edit-evidence.json',evidence)]:
        (base/name).write_text(json.dumps(value,indent=2,allow_nan=False))
    return data


class Workspaces:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()/'workspaces'; self.directory.mkdir(parents=True,exist_ok=True)
        self.pool = ThreadPoolExecutor(max_workers=1); self.lock=threading.RLock(); self.tasks={}; self.plans={}
        self.mutation_lock = threading.RLock()

    def folder(self, key):
        identifier(key,r'lab-[0-9a-f]{12}')
        folder=self.directory/key
        if folder.is_symlink() or folder.resolve().parent != self.directory:
            raise ValueError('Invalid workspace path')
        if not (folder/'data/dataset.json').is_file(): raise ValueError('Unknown workspace')
        return folder

    def delete(self, key, experiments=None):
        """Remove a user workspace and its terminal runs under the mutation lock."""
        from contextlib import nullcontext
        from .experiments import ACTIVE
        with self.mutation_lock, self.lock, (experiments.lock if experiments else nullcontext()):
            if key == 'brd4':
                raise ValueError('The bundled reference is read-only and cannot be deleted.')
            folder = self.folder(key)
            jobs = [j for j in experiments.list() if j.get('workspace_id', 'brd4') == key] if experiments else []
            if any(j['status'] in ACTIVE for j in jobs):
                raise ValueError('Wait for this project’s predictions to finish, or cancel them before deleting.')
            paths = []
            for job in jobs:
                path = experiments.directory / job['id']
                if path.is_symlink() or path.resolve().parent != experiments.directory:
                    raise ValueError('Invalid experiment path')
                paths.append(path)
            for path in paths:
                shutil.rmtree(path)
            shutil.rmtree(folder)
            for task in self.tasks.values():
                if (task.get('result') or {}).get('workspace_id') == key:
                    task.update(result=None, message='Workspace deleted.')
            return {'deleted': key, 'experiments_deleted': len(paths)}

    def list(self):
        with self.lock:
            rows=[{'id':'brd4','target':{'name':'BRD4 · bromodomain 1','organism':'Homo sapiens'},'compound_count':9,'bundled':True}]
            for path in sorted(self.directory.glob('lab-*/data/dataset.json')):
                data=json.loads(path.read_text()); rows.append({'id':data['workspace_id'],'target':data['target'],
                    'compound_count':len(data['compounds']),'assay_id':(data.get('assay') or {}).get('id'),'mode':data.get('mode','measured'),'bundled':False})
            return rows

    def task(self, key):
        with self.lock:
            if key not in self.tasks: raise ValueError('Unknown setup task')
            return dict(self.tasks[key])

    def submit(self, payload, importing=False, starter=False):
        allowed={'accession'} if starter else ({'plan_id','assay_id','reference_id'} if importing else {'target_id'})
        if not isinstance(payload,dict) or set(payload)!=allowed or not all(isinstance(v,str) for v in payload.values()):
            raise ValueError('Invalid target setup request')
        with self.lock:
            if any(t['status'] in ('queued','running') for t in self.tasks.values()):
                raise RuntimeError('A target setup is already running. Wait for it to finish.')
            if importing and payload['plan_id'] not in self.plans: raise ValueError('Preview this target again before importing')
            if starter: identifier(payload['accession'], r'[A-Z0-9]{6,10}')
            elif not importing: identifier(payload['target_id'])
            key=str(uuid.uuid4()); self.tasks[key]={'id':key,'status':'queued','message':'Preparing target setup…'}
            self.pool.submit(self._run,key,dict(payload),importing,starter)
            return dict(self.tasks[key])

    def _run(self,key,payload,importing,starter=False):
        staging=None
        def progress(message):
            with self.lock:self.tasks[key].update(status='running',message=message)
        try:
            if importing or starter:
                workspace_id='lab-'+uuid.uuid4().hex[:12]
                staging=self.directory/('.building-'+workspace_id)
                if starter:
                    from .starter import build_starter
                    data=build_starter(payload['accession'],staging,workspace_id,progress)
                else:
                    data=build_workspace(self.plans[payload['plan_id']],payload['assay_id'],payload['reference_id'],staging,workspace_id,progress)
                staging.rename(self.directory/workspace_id)
                result={'workspace_id':workspace_id,'target':data['target'],'compound_count':len(data['compounds'])}
            else:
                plan=inspect_target(payload['target_id'],progress)
                with self.lock:self.plans[key]=plan
                result=dict(plan['public'],plan_id=key)
            with self.lock:self.tasks[key].update(status='complete',message='Workspace ready.' if importing or starter else 'Target preview ready.',result=result)
        except Exception as exc:
            if staging and staging.exists():shutil.rmtree(staging)
            with self.lock:self.tasks[key].update(status='failed',message=str(exc))

    def close(self):
        self.pool.shutdown(wait=True)

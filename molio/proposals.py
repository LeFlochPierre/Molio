"""Bounded local molecular analysis and persistent proposal records."""
from contextlib import closing
import importlib.util
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def available():
    return importlib.util.find_spec('rdkit') is not None


def analyze(payload, dataset):
    if not available():
        raise RuntimeError('Variant editing needs RDKit. Install the chemistry extra and restart the server.')
    if not isinstance(payload, dict) or set(payload) - {'parent_id', 'smiles', 'name', 'hypothesis'}:
        raise ValueError('Expected parent_id, smiles, optional name and hypothesis')
    parent = next((c for c in dataset['compounds'] if c['id'] == payload.get('parent_id')), None)
    if parent is None:
        raise ValueError('Choose a starting molecule from this workspace')
    for key, limit in [('smiles', 1000), ('name', 100), ('hypothesis', 4000)]:
        value = payload.get(key, '')
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f'Invalid {key}; maximum {limit} characters')
    from rdkit import Chem, DataStructs, rdBase
    from rdkit.Chem import Descriptors, rdMolDescriptors, rdFingerprintGenerator, rdDepictor, rdFMCS
    from rdkit.Chem.Draw import rdMolDraw2D
    smiles = payload.get('smiles', '').strip()
    if not smiles:
        raise ValueError('Enter a SMILES structure to preview your variant')
    with rdBase.BlockLogs():
        molecule = Chem.MolFromSmiles(smiles)
    if molecule is None or molecule.GetNumHeavyAtoms() < 2:
        raise ValueError('Could not read this molecule. Check the SMILES syntax and atom valences.')
    if molecule.GetNumAtoms() > 100 or len(Chem.GetMolFrags(molecule)) != 1:
        raise ValueError('Use one connected molecule with at most 100 atoms; salts and mixtures are not supported yet.')
    if any(a.GetAtomicNum() not in (1, 5, 6, 7, 8, 9, 14, 15, 16, 17, 35, 53) for a in molecule.GetAtoms()):
        raise ValueError('This editor supports ordinary organic molecules, not metals or unspecified atoms.')
    for atom in molecule.GetAtoms():
        atom.SetAtomMapNum(0)
    original = Chem.MolFromSmiles(parent['smiles'])
    canonical = Chem.MolToSmiles(molecule)
    def descriptors(m):
        return dict(molecular_weight=round(Descriptors.MolWt(m), 2), clogp=round(Descriptors.MolLogP(m), 2),
                    tpsa=round(rdMolDescriptors.CalcTPSA(m), 2), hbd=rdMolDescriptors.CalcNumHBD(m),
                    hba=rdMolDescriptors.CalcNumHBA(m))
    common = rdFMCS.FindMCS([original, molecule], timeout=1, ringMatchesRingOnly=True,
                           completeRingsOnly=True, bondCompare=rdFMCS.BondCompare.CompareOrderExact)
    query = Chem.MolFromSmarts(common.smartsString) if not common.canceled and common.numAtoms else None
    template = Chem.Mol(query) if query is not None else None
    if template is not None:
        rdDepictor.Compute2DCoords(template)
    def drawing(m):
        m = Chem.Mol(m)
        rdDepictor.Compute2DCoords(m)
        match = m.GetSubstructMatch(query) if query is not None else ()
        if match:
            rdDepictor.GenerateDepictionMatching2DStructure(m, template)
        changed = [i for i in range(m.GetNumAtoms()) if i not in match] if match else []
        drawer = rdMolDraw2D.MolDraw2DSVG(440, 250)
        drawer.drawOptions().clearBackground = False
        drawer.drawOptions().setHighlightColour((0.95, 0.65, 0.30, 0.65))
        rdMolDraw2D.PrepareAndDrawMolecule(drawer, m, highlightAtoms=changed)
        drawer.FinishDrawing()
        return dict(svg=drawer.GetDrawingText(), changed_atoms=changed)
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    fingerprint = generator.GetFingerprint(molecule)
    neighbours = []
    for compound in dataset['compounds']:
        if not compound.get('observation'): continue
        other = Chem.MolFromSmiles(compound['smiles'])
        neighbours.append(dict(id=compound['id'], similarity=round(DataStructs.TanimotoSimilarity(fingerprint, generator.GetFingerprint(other)), 3),
            exact_identity=canonical == Chem.MolToSmiles(other), observation=compound['observation'], source_url=compound['source_url']))
    neighbours.sort(key=lambda x: (-x['similarity'], x['id']))
    unassigned = sum(tag == '?' for _, tag in Chem.FindMolChiralCenters(molecule, includeUnassigned=True))
    warnings = []
    if unassigned:
        warnings.append(f'{unassigned} tetrahedral stereocentre(s) unspecified. Choose stereochemistry before a future prediction.')
    if canonical == Chem.MolToSmiles(original):
        warnings.append('This is the same structure as the parent. Make a chemical edit before saving a variant.')
    if template is None:
        warnings.append('No complete common-core mapping available; drawings are not aligned or highlighted.')
    if any(n['exact_identity'] for n in neighbours):
        warnings.append('This structure already appears in the measured library. Its source record is shown below; no activity is assigned to your proposal.')
    from .edit_evidence import evidence_for_edit
    from .conformers import conformer
    return dict(edit_evidence=evidence_for_edit(parent['smiles'], canonical, dataset),
        conformer=conformer(canonical), parent_conformer=conformer(parent['smiles']), parent_id=parent['id'], input_smiles=smiles, canonical_smiles=canonical,
        same_as_parent=canonical == Chem.MolToSmiles(original), name=payload.get('name', '').strip(),
        hypothesis=payload.get('hypothesis', '').strip(), status='proposal', activity=None, bound_pose=None,
        descriptors=descriptors(molecule), parent_descriptors=descriptors(original),
        depiction=drawing(molecule), parent_depiction=drawing(original),
        common_core_available=template is not None, warnings=warnings, neighbours=neighbours[:4],
        neighbour_scope=f'Only the {len(neighbours)} measured compounds in this workspace; similarity does not predict activity.',
        rdkit_version=rdBase.rdkitVersion, assay=dataset['assay'], provenance=dataset['provenance'],
        descriptor_note='Calculated molecular descriptors, not binding, solubility, safety, or synthesis predictions.')


class ProposalStore:
    def __init__(self, path):
        self.path = Path(path)

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, timeout=10)
        con.execute('CREATE TABLE IF NOT EXISTS proposals (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, body TEXT NOT NULL)')
        return con

    def save(self, result):
        return self.save_batch([result])[0]

    def save_batch(self, results):
        prepared=[]
        for result in results:
            if result['same_as_parent']:
                raise ValueError('Change the parent structure before saving a variant')
            row=dict(result,id=str(uuid.uuid4()),created_at=datetime.now(timezone.utc).isoformat())
            if not row['name']:row['name']='Variant of '+row['parent_id']
            prepared.append(row)
        with closing(self.connect()) as con, con:
            for row in prepared:
                con.execute('INSERT INTO proposals VALUES (?, ?, ?)', (row['id'],row['created_at'],json.dumps(row,allow_nan=False)))
        return prepared

    def list(self):
        with closing(self.connect()) as con, con:
            return [json.loads(row[0]) for row in con.execute('SELECT body FROM proposals ORDER BY created_at DESC')]

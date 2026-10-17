"""Build the audited BRD4 fixture. Requires RDKit; the served app does not.

Usage: python scripts/build_whatif_dataset.py --source-dir /tmp/whatif-sources
Use --download to refresh the explicitly scoped public source records.
"""
import argparse
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

from rdkit import Chem, rdBase
from rdkit.Chem import Descriptors, rdDepictor, rdFMCS
from rdkit.Chem.Draw import rdMolDraw2D

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'molecular_lab' / 'data'
SOURCES = {
    'activity.json': 'https://www.ebi.ac.uk/chembl/api/data/activity.json?assay_chembl_id=CHEMBL1832996&limit=1000',
    'assay.json': 'https://www.ebi.ac.uk/chembl/api/data/assay/CHEMBL1832996.json',
    'document.json': 'https://www.ebi.ac.uk/chembl/api/data/document/CHEMBL1828554.json',
    '3SVG.pdb': 'https://files.rcsb.org/download/3SVG.pdb',
    'ODR.json': 'https://data.rcsb.org/rest/v1/core/chemcomp/ODR',
}


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def depiction(mol, path, highlight=()):
    drawer = rdMolDraw2D.MolDraw2DSVG(440, 250)
    drawer.drawOptions().clearBackground = False
    drawer.drawOptions().setHighlightColour((0.95, 0.65, 0.30, 0.65))
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol, highlightAtoms=list(highlight))
    drawer.FinishDrawing()
    path.write_text(drawer.GetDrawingText())


def build(source):
    from molecular_lab.evidence import normalize_observation, compare_observations
    for directory in [OUT, OUT / 'sources', OUT / 'depictions', OUT / 'structures']:
        directory.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, url in SOURCES.items():
        raw = (source / name).read_bytes()
        if (source / name).resolve() != (OUT / 'sources' / name).resolve():
            shutil.copyfile(source / name, OUT / 'sources' / name)
        manifest.append(dict(file=f'sources/{name}', url=url, sha256=hashlib.sha256(raw).hexdigest()))
    records = json.loads((source / 'activity.json').read_text())
    assert records['page_meta']['next'] is None, 'Incomplete assay download'
    assay = json.loads((source / 'assay.json').read_text())
    doc = json.loads((source / 'document.json').read_text())
    assert assay['target_chembl_id'] == 'CHEMBL1163125'
    assert assay['assay_organism'] == 'Homo sapiens'
    compounds, mols = [], {}
    for record in sorted(records['activities'], key=lambda a: a['molecule_chembl_id']):
        obs = normalize_observation(record)
        mol = Chem.MolFromSmiles(record['canonical_smiles'])
        assert mol is not None
        cid = record['molecule_chembl_id']
        assert cid not in mols, 'Handle replicates explicitly before adding this assay'
        rdDepictor.Compute2DCoords(mol)
        mols[cid] = mol
        depiction(mol, OUT / 'depictions' / f'{cid}.svg')
        compounds.append(dict(id=cid, smiles=record['canonical_smiles'],
            canonical_smiles=Chem.MolToSmiles(mol), observation=obs,
            molecular_weight=round(Descriptors.MolWt(mol), 2),
            unassigned_stereocentres=sum(tag == '?' for _, tag in Chem.FindMolChiralCenters(mol, includeUnassigned=True)),
            depiction=f'/data/depictions/{cid}.svg', source_url=f'https://www.ebi.ac.uk/chembl/explore/compound/{cid}',
            experimental_pose=None))
    byid = {c['id']: c for c in compounds}
    specs = [
        (979, 981, 'Add an ethoxy group'),
        (980, 982, 'Ketone → alcohol'),
        (981, 985, 'Add an acetyl group'),
        (985, 986, 'Ketone → alcohol, with ethoxy retained'),
        (983, 984, 'Ethyl ester → carboxylic acid'),
        (982, 986, 'Add ethoxy to the alcohol series'),
        (979, 980, 'Add an acetyl group to the parent'),
    ]
    pairs = []
    for number, (left, right, title) in enumerate(specs, 1):
        a, b = f'CHEMBL1828{left}', f'CHEMBL1828{right}'
        # Curated related pairs, not automatically asserted single-cut MMPs.
        common = rdFMCS.FindMCS([mols[a], mols[b]], timeout=5,
            ringMatchesRingOnly=True, completeRingsOnly=True,
            bondCompare=rdFMCS.BondCompare.CompareOrderExact)
        assert not common.canceled and common.numAtoms >= 10
        query = Chem.MolFromSmarts(common.smartsString)
        template = Chem.Mol(query)
        rdDepictor.Compute2DCoords(template)
        maps, pictures = {}, {}
        pid = f'pair-{number}'
        for cid in [a, b]:
            mol = Chem.Mol(mols[cid])
            match = mol.GetSubstructMatch(query)
            rdDepictor.GenerateDepictionMatching2DStructure(mol, template)
            changed = [i for i in range(mol.GetNumAtoms()) if i not in match]
            # Changed bond endpoints also matter for ketone/alcohol comparisons.
            maps[cid] = dict(common_atoms=list(match), changed_atoms=changed)
            filename = f'{pid}-{cid}.svg'
            depiction(mol, OUT / 'depictions' / filename, changed)
            pictures[cid] = '/data/depictions/' + filename
        result = compare_observations(byid[a]['observation'], byid[b]['observation'])
        pairs.append(dict(id=pid, left=a, right=b, title=title, **result,
            common_smarts=common.smartsString, atom_mapping=maps, depictions=pictures,
            method='Curated related pair; exact-bond maximum common substructure highlighting'))
    pdb = (source / '3SVG.pdb').read_text()
    assert any(l.startswith('DBREF') and 'O60885' in l for l in pdb.splitlines())
    assert any(l.startswith('HETATM') and l[17:20] == 'ODR' and l[21] == 'A' and int(l[22:26]) == 169 for l in pdb.splitlines())
    ccd = json.loads((source / 'ODR.json').read_text())
    ligand = Chem.MolFromSmiles(ccd['rcsb_chem_comp_descriptor']['SMILES_stereo'])
    assay_ligand = Chem.Mol(mols['CHEMBL1828986'])
    Chem.RemoveStereochemistry(ligand)
    Chem.RemoveStereochemistry(assay_ligand)
    assert Chem.MolToSmiles(ligand) == Chem.MolToSmiles(assay_ligand), 'Ligand connectivity mismatch'
    shutil.copyfile(source / '3SVG.pdb', OUT / 'structures' / '3SVG.pdb')
    dataset = dict(schema_version=1, title='Small change. Different activity.',
        target=dict(name='BRD4 · bromodomain 1', organism='Homo sapiens', uniprot='O60885', chembl_id='CHEMBL1163125'),
        assay=dict(id=assay['assay_chembl_id'], description=assay['description'], organism=assay['assay_organism'],
            confidence_score=assay['confidence_score'], url='https://www.ebi.ac.uk/chembl/explore/assay/CHEMBL1832996'),
        publication={k:doc[k] for k in ['title', 'authors', 'doi', 'year', 'document_chembl_id']},
        compounds=compounds, pairs=pairs,
        reference_structure=dict(id='3SVG', url='/data/structures/3SVG.pdb', source_url='https://www.rcsb.org/structure/3SVG',
            chain='A', ligand='ODR', ligand_residue=169, resolution_A=1.68,
            related_compound='CHEMBL1828986', identity='Same connectivity; assay stereochemistry unspecified, deposited ligand stereochemistry specified.',
            label='Experimental pocket reference · 3SVG / ODR',
            caveat='Reference context, not a predicted pose of the selected compound. The assay record does not specify the stereochemistry resolved in this crystal.'),
        provenance=dict(rdkit=rdBase.rdkitVersion, sources=manifest,
            data_license='ChEMBL data: CC BY-SA 3.0; PDB coordinates: CC0.',
            limitations=['One assay and one publication; no independent validation.',
                'IC50 differences describe this assay, not binding free energies.',
                'Experimental uncertainty is not supplied in these imported records.',
                'No selected compound has an exact stereochemically verified experimental pose in this fixture.']))
    save(OUT / 'dataset.json', dataset)
    from molecular_lab.conformers import conformer
    from molecular_lab.edit_evidence import evidence_for_edit
    save(OUT / 'conformers.json', {c['id']: conformer(c['smiles']) for c in compounds})
    save(OUT / 'edit-evidence.json', {p['id']: evidence_for_edit(byid[p['left']]['smiles'], byid[p['right']]['smiles'], dataset) for p in pairs})
    print(f'Built {len(compounds)} compounds, {len(pairs)} comparisons, 1 verified context structure')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    if args.download:
        args.source_dir.mkdir(parents=True, exist_ok=True)
        for name, url in SOURCES.items():
            with urllib.request.urlopen(url, timeout=90) as response:
                (args.source_dir / name).write_bytes(response.read())
    import sys
    sys.path.insert(0, str(ROOT))
    build(args.source_dir)

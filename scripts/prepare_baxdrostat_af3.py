"""Prepare the paired AF3 validation dataset from locally saved source records.

Run from the project root: python3 scripts/prepare_baxdrostat_af3.py
This writes inputs only; it does not execute AlphaFold 3.
"""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cyp_pipeline.benchmark_boltz import LIGANDS, TARGETS, _domain_sequence

DATASET = ROOT / 'data/validation/baxdrostat-af3-v1'
PATENT = 'https://patents.google.com/patent/WO2025002335A1/en'
PUBCHEM = ('https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/71535962/'
           'property/IsomericSMILES,InChIKey,MolecularFormula/JSON')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    chemical_path = DATASET / 'sources/pubchem-71535962.json'
    chemical = json.loads(chemical_path.read_text())['PropertyTable']['Properties'][0]
    if (chemical['CID'] != 71535962
            or chemical['InChIKey'] != 'VDEUDSRUMNAXJG-LJQANCHMSA-N'
            or chemical['MolecularFormula'] != 'C22H25N3O2'
            or chemical['SMILES'] != LIGANDS['Baxdrostat']['smiles']):
        raise ValueError('Baxdrostat identity differs from the verified reference')
    experiment = json.loads((ROOT / 'configs/extended-selectivity-benchmark.json').read_text())
    documents, cases, fasta = [], [], []
    for isoform, (pdb_id, accession) in TARGETS.items():
        source_path = DATASET / f'sources/{accession}.fasta'
        lines = source_path.read_text().splitlines()
        if not lines[0].startswith(f'>sp|{accession}|'):
            raise ValueError(f'Wrong UniProt record: {source_path}')
        full_sequence = ''.join(lines[1:])
        sequence, provenance = _domain_sequence(ROOT / f'data/raw/{pdb_id}.pdb', accession)
        if len(full_sequence) != 503 or sequence != full_sequence[33:503]:
            raise ValueError(f'{isoform}: PDB domain does not match UniProt 34-503')
        identifier = f'Baxdrostat-{isoform}'
        if not any(s['system_id'] == identifier and s['ligand'] == 'Baxdrostat'
                   and s['isoform'] == isoform for s in experiment['systems']):
            raise ValueError(f'Missing benchmark case: {identifier}')
        document = {
            'name': identifier, 'modelSeeds': [42, 43, 44],
            'sequences': [
                {'protein': {'id': 'A', 'sequence': sequence, 'templates': []}},
                {'ligand': {'id': 'H', 'ccdCodes': ['HEM']}},
                {'ligand': {'id': 'L', 'smiles': chemical['SMILES']}},
            ],
            'dialect': 'alphafold3', 'version': 1,
        }
        provenance['path'] = f'data/raw/{pdb_id}.pdb'
        cases.append({
            'system_id': identifier, 'ligand': 'Baxdrostat', 'isoform': isoform,
            'status': 'prepared_not_run', 'structure_path': None,
            'input_path': f'inputs/{identifier}.json',
            'sequence_source': provenance,
            'uniprot_verification': {
                'path': f'sources/{accession}.fasta', 'sha256': sha(source_path),
                'url': f'https://rest.uniprot.org/uniprotkb/{accession}.fasta',
                'matches_residues_34_503': True,
            },
        })
        documents.append(document)
        fasta.append(f'>{isoform}|{accession}|34-503|chain=A\n' +
                     '\n'.join(sequence[i:i + 80] for i in range(0, len(sequence), 80)))
    manifest_path = DATASET / 'manifest.json'
    if manifest_path.exists():
        raise FileExistsError('Dataset already prepared; preserve it and use a new version')
    (DATASET / 'inputs').mkdir(exist_ok=False)
    for document, case in zip(documents, cases):
        path = DATASET / case['input_path']
        write_json(path, document)
        case['input_sha256'] = sha(path)
    (DATASET / 'proteins.fasta').write_text('\n'.join(fasta) + '\n')
    write_json(manifest_path, {
        'schema_version': 1, 'dataset_id': 'baxdrostat-af3-v1',
        'model': 'AlphaFold 3', 'status': 'prepared_not_run',
        'source_retrieved_date': '2026-09-20',
        'path_convention': 'Relative to this dataset except sequence_source.path and project references, which are relative to the project root.',
        'experiment': 'configs/extended-selectivity-benchmark.json',
        'assay_reference': 'data/benchmarks/osilodrostat_baxdrostat_assays.json',
        'protein_fasta': {'path': 'proteins.fasta', 'sha256': sha(DATASET / 'proteins.fasta')},
        'ligand': {'name': 'Baxdrostat', **chemical,
                   'source_path': 'sources/pubchem-71535962.json',
                   'source_sha256': sha(chemical_path), 'source_url': PUBCHEM,
                   'user_supplied_patent': PATENT},
        'recipe': {'model_seeds': [42, 43, 44], 'templates': False,
                   'msa': 'AF3 database search; MSA fields deliberately omitted',
                   'protein_chain': 'A', 'heme_chain': 'H', 'ligand_chain': 'L',
                   'covalent_bonds_or_coordination_restraints': False},
        'cases': cases,
        'limitations': [
            'Inputs only: no AF3 structures or confidence scores have been generated.',
            'Two separate noncovalent protein-ligand complexes, not a protein fusion.',
            'Residues 34-503 match the existing benchmark; these are not full-length precursor sequences.',
            'The supplied patent describes baxdrostat solid forms, not CYP-bound coordinates.',
            'Predicted structures are candidates for pipeline validation, not experimental structural ground truth.',
            'AF3 confidence is not affinity; preserve the existing Ki endpoint when comparing assays.',
            'Before energy preparation, check ligand chirality, clashes, heme integrity, Fe-donor and Fe-axial sulfur geometry, protonation and spin.',
            'Training overlap is unestablished; this is a retrospective reference, not a held-out accuracy test.',
        ],
    })
    print(manifest_path)


if __name__ == '__main__':
    main()

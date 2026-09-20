"""Inspect every AF3 pose; run using .venv-boltz/bin/python for Gemmi/RDKit."""

from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cyp_pipeline.benchmark_geometry import _chirality, analyze_boltz_structure
from cyp_pipeline.benchmark_boltz import LIGANDS
import gemmi
from rdkit import Chem


def main():
    dataset = ROOT / 'data/validation/baxdrostat-af3-v1'
    reference = Chem.MolFromSmiles(LIGANDS['Baxdrostat']['smiles'])
    # Matches pinned AF3 rdkit_utils.assign_atom_names_from_graph.
    counts = Counter()
    for atom in reference.GetAtoms():
        element = atom.GetSymbol().upper()
        counts[element] += 1
        atom.SetProp('name', f'{element}{counts[element]}')
    records = []
    for path in sorted((dataset / 'predictions').rglob('*_model.cif')):
        diagnostic = analyze_boltz_structure(path, 'Baxdrostat')
        structure = gemmi.read_structure(str(path))
        atoms = {chain.name: [atom for residue in chain for atom in residue
                             if not atom.element.is_hydrogen] for chain in structure[0]}
        coordinates = {atom.name: (atom.pos.x, atom.pos.y, atom.pos.z) for atom in atoms['L']}
        diagnostic['chirality'] = _chirality(reference, coordinates, 'R')
        chirality = diagnostic['chirality']
        chirality['reference_source'] = 'Verified baxdrostat SMILES with pinned AF3 atom naming'
        chirality['reference_centers'] = chirality.pop('ccd_centers')
        chirality['expected_matches_reference'] = chirality.pop('expected_matches_ccd')
        if chirality['status'] == 'matches_ccd':
            chirality['status'] = 'matches_smiles'
        diagnostic['heavy_atom_counts'] = {chain: len(values) for chain, values in atoms.items()}
        distances = [(lig.pos.dist(protein.pos), lig.name, protein.name)
                     for lig in atoms['L'] for protein in atoms['A']]
        diagnostic['minimum_ligand_protein_heavy_atom_distance_A'] = min(d[0] for d in distances)
        diagnostic['ligand_protein_pairs_below_1_5_A'] = sum(d[0] < 1.5 for d in distances)
        flags = []
        if not chirality['coordinates_match_expected']:
            flags.append('baxdrostat_stereochemistry_mismatch_or_unassigned')
        if diagnostic['ligand_protein_pairs_below_1_5_A']:
            flags.append('ligand_protein_heavy_atom_contact_below_1_5_A')
        diagnostic['flags'] = flags
        diagnostic['screening_status'] = 'flagged_do_not_use' if flags else 'no_flags_requires_chemistry_review'
        diagnostic['source']['path'] = str(path.relative_to(dataset))
        confidence_path = path.with_name(path.name.replace('_model.cif', '_summary_confidences.json'))
        records.append({'structure': str(path.relative_to(dataset)),
                        'confidence': json.loads(confidence_path.read_text()),
                        'geometry': diagnostic})
    if len(records) != 32:
        raise ValueError(f'Expected 30 samples plus 2 selected models, found {len(records)}')
    (dataset / 'geometry_checks.json').write_text(json.dumps({
        'status': 'diagnostic_only',
        'notes': 'Atom mapping follows the pinned AF3 SMILES atom naming. Distances and short-contact counts are descriptive, not an energy-preparation approval.',
        'structures': records,
    }, indent=2, allow_nan=False) + '\n')
    for record in records:
        if '/seed-' not in record['structure']:
            print(record['structure'], json.dumps(record['geometry']))


if __name__ == '__main__':
    main()

"""Four small synthetic fixtures; intentionally not molecular structures."""
from .core import digest


def system(ligand, isoform):
    atoms = [
        {'id': 'fe', 'element': 'Fe', 'role': 'heme', 'position': [0., 0., 0.]},
        {'id': 'donor', 'element': 'N', 'role': 'ligand', 'position': [0., 0., 2.2]},
        {'id': 's', 'element': 'S', 'role': 'axial', 'position': [0., 0., -2.3]},
        {'id': 'boundary', 'element': 'C', 'role': 'pocket', 'position': [3., 0., 0.]},
    ]
    for atom in atoms:
        atom['demo_target'] = atom['position'][:]
    atoms[1]['demo_target'][2] = 2.0
    # Fixed donor emulates an imposed displacement for integration testing only.
    prep = {key: 'SYNTHETIC test fixture; no chemistry' for key in (
        'protonation', 'oxidation_state', 'caps', 'boundary', 'stereochemistry',
        'reference_coordination', 'fragment_definition', 'pocket_geometry')}
    return {'schema_version': 1, 'system_id': f'demo-{ligand}-{isoform}', 'ligand': ligand,
            'isoform': isoform, 'pose': {'kind': 'synthetic', 'source': 'cyp_pipeline.demo'},
            'review': {'approved': True, 'reviewer': 'synthetic fixture generator'}, 'atoms': atoms,
            'fragment_ids': ['fe', 'donor', 's'], 'fixed_ids': ['fe', 'donor', 'boundary'],
            'cluster_state': {'charge': 0, 'multiplicity': 1, 'convention': 'synthetic'},
            'fragment_state': {'charge': 0, 'multiplicity': 1, 'convention': 'synthetic'},
            'coordination': [{'ids': ['fe', 'donor'], 'min_A': 1.8, 'max_A': 2.5},
                             {'ids': ['fe', 's'], 'min_A': 2., 'max_A': 2.6}],
            'preparation': prep}

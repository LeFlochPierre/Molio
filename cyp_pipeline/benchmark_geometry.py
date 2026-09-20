"""Optional, descriptive geometry checks for a single Boltz CYP complex."""

import hashlib
import math
from pathlib import Path


LIGAND_IDENTITIES = {
    'R-fadrozole': {'ccd': '0T3', 'enantiomer': 'R'},
    'S-fadrozole': {'ccd': 'JD7', 'enantiomer': 'S'},
    'Osilodrostat (LCI699)': {'ccd': 'YSY', 'enantiomer': 'R'},
    # Boltz accepts baxdrostat as a SMILES string, so its output residue name
    # is not a stable CCD identifier. The known R stereocenter therefore
    # remains a manual review item rather than a false automated pass/fail.
    'Baxdrostat': {'ccd': None, 'enantiomer': None},
}


def _chirality(reference, coordinates, expected_enantiomer=None):
    from rdkit import Chem
    from rdkit.Chem import rdCIPLabeler

    reference = Chem.RemoveHs(Chem.Mol(reference))
    rdCIPLabeler.AssignCIPLabels(reference)
    names = [atom.GetProp('name') for atom in reference.GetAtoms()]
    if len(names) != len(set(names)) or set(names) != set(coordinates):
        missing = sorted(set(names) - set(coordinates))
        return {'status': 'unresolved', 'reason': 'CCD/prediction heavy-atom names differ',
                'missing_atom_names': missing, 'missing_atom_count': len(missing),
                'unexpected_atom_names': sorted(set(coordinates) - set(names))}
    expected = {atom.GetProp('name'): atom.GetProp('_CIPCode')
                for atom in reference.GetAtoms() if atom.HasProp('_CIPCode')}
    observed = Chem.Mol(reference)
    observed.RemoveAllConformers()
    Chem.RemoveStereochemistry(observed)
    conformer = Chem.Conformer(len(names))
    conformer.Set3D(True)
    for index, name in enumerate(names):
        conformer.SetAtomPosition(index, coordinates[name])
    observed.AddConformer(conformer)
    Chem.AssignStereochemistryFrom3D(observed, confId=0, replaceExistingTags=True)
    rdCIPLabeler.AssignCIPLabels(observed)
    actual = {atom.GetProp('name'): atom.GetProp('_CIPCode')
              for atom in observed.GetAtoms() if atom.HasProp('_CIPCode')}
    if not expected:
        status = 'unresolved'
    elif actual == expected:
        status = 'matches_ccd'
    else:
        status = 'mismatch_or_unassigned'
    result = {'status': status, 'ccd_centers': expected, 'coordinate_centers': actual,
              'missing_atom_names': [], 'missing_atom_count': 0}
    if expected_enantiomer:
        result['expected_enantiomer'] = expected_enantiomer
        result['expected_matches_ccd'] = list(expected.values()) == [expected_enantiomer]
        result['coordinates_match_expected'] = list(actual.values()) == [expected_enantiomer]
    return result


def analyze_boltz_structure(path, expected_ligand=None, *, ccd_dir=None, expected_enantiomer=None,
                            ligand_chain='L', heme_chain='H', protein_chain='A'):
    """Measure candidate coordination distances; optionally check CCD chirality.

    ``ccd_dir`` is the trusted molecule cache used by the installed Boltz model.
    Missing optional packages leave diagnostics unassessed. Distances alone do
    not establish coordination, binding, or a chemically valid complex.
    """
    if expected_ligand not in (None, *LIGAND_IDENTITIES):
        raise ValueError(f'Unknown expected ligand: {expected_ligand!r}')
    if expected_ligand is not None:
        ligand_spec = LIGAND_IDENTITIES[expected_ligand]
        if expected_enantiomer not in (None, ligand_spec['enantiomer']):
            raise ValueError('Conflicting expected ligand and enantiomer')
        expected_enantiomer = ligand_spec['enantiomer']
    if expected_enantiomer not in (None, 'R', 'S'):
        raise ValueError('expected_enantiomer must be R, S, or None')
    try:
        import gemmi
    except ImportError:
        return {'status': 'unavailable', 'reason': 'Optional gemmi dependency is unavailable'}
    path = Path(path)
    structure = gemmi.read_structure(str(path))
    if len(structure) != 1:
        raise ValueError('Geometry diagnostics require exactly one coordinate model')
    model = structure[0]

    def select(chain_name, residue_names, element=None, atom_name=None):
        return [(chain, residue, atom) for chain in model if chain.name == chain_name
                for residue in chain if residue.name in residue_names for atom in residue
                if (element is None or atom.element.name == element)
                and (atom_name is None or atom.name == atom_name)]

    iron = select(heme_chain, {'HEM'}, element='Fe')
    expected_ccd = LIGAND_IDENTITIES.get(expected_ligand, {}).get('ccd')
    ligands = [(chain, residue) for chain in model if chain.name == ligand_chain
               for residue in chain if expected_ccd is None or residue.name == expected_ccd]
    if len(iron) != 1 or len(ligands) != 1:
        raise ValueError('Expected exactly one HEM iron and one ligand residue in selected chains')
    _, ligand = ligands[0]
    heavy_atoms = [atom for atom in ligand if not atom.element.is_hydrogen]
    coordinates = {atom.name: (atom.pos.x, atom.pos.y, atom.pos.z) for atom in heavy_atoms}
    if len(coordinates) != len(heavy_atoms):
        raise ValueError('Duplicate/alternate ligand atom names require explicit selection')
    if not all(math.isfinite(value) for xyz in coordinates.values() for value in xyz):
        raise ValueError('Nonfinite ligand coordinates')
    fe = iron[0][2]

    def nearest(candidates):
        distances = [(fe.pos.dist(atom.pos), chain.name, str(residue.seqid), residue.name, atom.name)
                     for chain, residue, atom in candidates]
        if not distances:
            return None
        if not all(math.isfinite(row[0]) for row in distances):
            raise ValueError('Nonfinite candidate coordination distance')
        distance, chain, residue_id, residue_name, atom_name = min(distances)
        return {'distance_A': distance, 'chain': chain, 'residue_id': residue_id,
                'residue_name': residue_name, 'atom_name': atom_name}

    result = {'status': 'diagnostic_only',
              'source': {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()},
              'ligand_ccd': ligand.name, 'gemmi_version': gemmi.__version__,
              'nearest_ligand_nitrogen': nearest(select(ligand_chain, {ligand.name}, element='N')),
              'nearest_protein_cysteine_sulfur': nearest(select(protein_chain, {'CYS'}, atom_name='SG')),
              'chirality': {'status': 'unassessed', 'reason': 'No CCD cache supplied'},
              'interpretation': 'Candidate coordination distances only; no calibrated acceptance thresholds.'}
    if expected_ccd:
        result['expected_ligand'] = expected_ligand
        result['ligand_ccd_matches_expected'] = ligand.name == expected_ccd
    if expected_enantiomer:
        result['expected_enantiomer'] = expected_enantiomer
    if ccd_dir is not None:
        try:
            from boltz.data.mol import load_molecules
            from rdkit import rdBase
            reference_path = Path(ccd_dir) / f'{ligand.name}.pkl'
            reference = load_molecules(str(ccd_dir), [ligand.name])[ligand.name]
            result['chirality'] = _chirality(reference, coordinates, expected_enantiomer)
            result['chirality']['ccd_sha256'] = hashlib.sha256(reference_path.read_bytes()).hexdigest()
            result['chirality']['rdkit_version'] = rdBase.rdkitVersion
        except (ImportError, OSError, ValueError, KeyError, RuntimeError) as error:
            result['chirality'] = {'status': 'unassessed', 'reason': str(error)}
    return result

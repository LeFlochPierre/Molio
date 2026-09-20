"""Bounded UMA single-point evaluation of explicitly prepared protein pockets.

Protein identifiers are metadata, not an execution allow-list. A sequence or
raw PDB is not a prepared input. No caps, hydrogens, charge, spin or drug pose
are guessed here. Results are total potential energies/forces, NOT binding
affinities and NOT cross-protein selectivity scores.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import sys

from .core import checked_evaluate, digest, distance, finite, require

MAX_SYSTEMS = 8
MAX_ATOMS = 1000
MAX_BYTES = 4 * 1024 * 1024
ELEMENTS = ('H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn '
            'Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce '
            'Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At '
            'Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og').split()
ATOMIC_NUMBERS = {element: number for number, element in enumerate(ELEMENTS, 1)}
SCOPE = 'Prepared-pocket total potential energies and forces only. Do not rank proteins by these energies or interpret them as binding affinity/selectivity.'


def text(value, name, limit=2000):
    require(isinstance(value, str) and 0 < len(value.strip()) <= limit, f'{name}: nonempty text required (maximum {limit} characters)')
    require(value.strip().upper() not in {'TODO', 'REVIEW', 'UNKNOWN'}, f'{name}: replace the placeholder with a preparation statement')
    return value.strip()


def validate_batch(payload, max_atoms=MAX_ATOMS):
    """Validate data/declared geometry, never attest biological correctness."""
    require(isinstance(payload, dict), 'Upload a prepared batch JSON object')
    require(set(payload) <= {'schema_version', 'kind', 'label', 'systems'}, 'Unsupported batch fields')
    require(payload.get('schema_version') == 1 and payload.get('kind') == 'uma_pocket_batch', 'Expected schema_version 1 and kind uma_pocket_batch; raw PDB/FASTA is not calculation-ready')
    text(payload.get('label'), 'Batch label', 120)
    systems = payload.get('systems')
    require(isinstance(systems, list) and 1 <= len(systems) <= MAX_SYSTEMS, f'Provide 1–{MAX_SYSTEMS} prepared pockets')
    require(type(max_atoms) is int and max_atoms > 0, 'Atom budget must be a positive integer')
    cap = min(MAX_ATOMS, max_atoms)
    ids, summary = set(), []
    for system in systems:
        require(isinstance(system, dict), 'Each system must be an object')
        require(set(system) <= {'id', 'protein_id', 'ligand', 'atoms', 'ligand_atom_ids', 'state',
                                'review', 'source', 'preparation', 'coordination', 'covalent_bounds', 'chirality_checks'},
                'Unsupported system fields; commands, paths and backend settings are not accepted')
        key = text(system.get('id'), 'System id', 80)
        require(bool(re.fullmatch('[A-Za-z0-9_-]+', key)) and key not in ids, 'System IDs must be unique simple labels')
        ids.add(key)
        for name in ('protein_id', 'ligand', 'source', 'preparation'):
            text(system.get(name), name, 2000 if name in ('source', 'preparation') else 120)
        review = system.get('review')
        require(isinstance(review, dict), f'{key}: review declaration required')
        approved = review.get('approved') is True and isinstance(review.get('reviewer'), str) and bool(review['reviewer'].strip())
        provisional = review.get('provisional') is True
        require(approved or provisional, f'{key}: name a reviewer or explicitly declare provisional preparation')
        atoms = system.get('atoms')
        require(isinstance(atoms, list) and 1 <= len(atoms) <= cap, f'{key}: supply 1–{cap} atoms, including hydrogens and caps')
        positions, numbers = {}, []
        for atom in atoms:
            require(isinstance(atom, dict), f'{key}: atom must be an object')
            atom_id = text(atom.get('id'), 'Atom ID', 120)
            require(atom_id not in positions, f'{key}: duplicate atom ID')
            element = atom.get('element')
            require(isinstance(element, str) and element.capitalize() in ATOMIC_NUMBERS, f'{key}: invalid chemical element')
            position = atom.get('position')
            require(isinstance(position, list) and len(position) == 3 and all(finite(x) and abs(x) < 1e5 for x in position), f'{key}: finite xyz coordinates in Å required')
            positions[atom_id] = position
            numbers.append(ATOMIC_NUMBERS[element.capitalize()])
        require(1 in numbers, f'{key}: missing explicit hydrogens; a raw protein structure is not prepared')
        ligand_ids = system.get('ligand_atom_ids')
        require(isinstance(ligand_ids, list) and ligand_ids and all(isinstance(x, str) for x in ligand_ids), f'{key}: ligand atom IDs required')
        require(len(ligand_ids) == len(set(ligand_ids)) and set(ligand_ids) < set(positions), f'{key}: ligand must be a proper subset of the pocket atoms')
        state = system.get('state')
        require(isinstance(state, dict), f'{key}: electronic state required')
        charge, spin = state.get('charge'), state.get('multiplicity')
        require(type(charge) is int and -100 <= charge <= 100, f'{key}: explicit integer charge required')
        require(type(spin) is int and 1 <= spin <= 100, f'{key}: positive integer spin multiplicity required')
        text(state.get('convention'), f'{key}: state convention')
        electrons = sum(numbers) - charge
        require(electrons >= 0 and spin - 1 <= electrons and (electrons - spin + 1) % 2 == 0, f'{key}: charge/spin inconsistent with electron count')
        # Catch coincident atoms without claiming to infer bonding or chemistry.
        coords = list(positions.values())
        require(all(distance(a, b) > .1 for i, a in enumerate(coords) for b in coords[i+1:]), f'{key}: coincident or nearly coincident atoms')
        for field in ('coordination', 'covalent_bounds'):
            bonds = system.get(field)
            require(isinstance(bonds, list) and len(bonds) <= 5000, f'{key}: explicitly supply {field}, including [] if none applies')
            for bond in bonds:
                require(isinstance(bond, dict), f'{key}: invalid {field}')
                pair = bond.get('ids')
                require(isinstance(pair, list) and len(pair) == 2 and all(isinstance(x, str) for x in pair)
                        and len(set(pair)) == 2 and set(pair) <= set(positions), f'{key}: unknown bond atoms')
                low, high = bond.get('min_A'), bond.get('max_A')
                require(finite(low) and finite(high) and 0 < low < high, f'{key}: invalid bond bounds')
                require(low <= distance(positions[pair[0]], positions[pair[1]]) <= high, f'{key}: {field} check failed')
        checks = system.get('chirality_checks')
        require(isinstance(checks, list) and len(checks) <= 1000, f'{key}: explicitly supply chirality_checks')
        for check in checks:
            require(isinstance(check, dict), f'{key}: invalid chirality check')
            center, neighbors, volume = check.get('center'), check.get('neighbors'), check.get('reference_volume_A3')
            require(isinstance(center, str) and center in positions and isinstance(neighbors, list)
                    and len(neighbors) == 3 and all(isinstance(x, str) for x in neighbors)
                    and len(set(neighbors)) == 3 and set(neighbors) <= set(positions) and center not in neighbors,
                    f'{key}: invalid chirality atom IDs')
            require(finite(volume) and abs(volume) >= .1, f'{key}: invalid chirality reference')
        from .exchange import structure_valid
        require(structure_valid(atoms, system), f'{key}: chirality or bond geometry failed')
        warnings = []
        if not approved:
            warnings.append('Provisional preparation; no scientific validation.')
        if not checks:
            warnings.append('No stereocenters audited; supplied stereochemistry needs review.')
        summary.append({'id': key, 'protein_id': system['protein_id'], 'ligand': system['ligand'],
                        'atoms': len(atoms), 'charge': charge, 'multiplicity': spin,
                        'provisional': not approved, 'warnings': warnings})
    return {'status': 'inputs_checked', 'input_sha256': digest(payload), 'systems': summary,
            'provisional': any(row['provisional'] for row in summary), 'scope': SCOPE,
            'note': 'Checks cover supplied data, not completeness of the chemistry or suitability of the model.'}


def read_batch(path):
    path = Path(path)
    require(path.stat().st_size <= MAX_BYTES, 'Batch file exceeds 4 MiB')
    return json.loads(path.read_text())


def _save(path, value):
    # Status polls always see a complete JSON file.
    path = Path(path)
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def run_batch(payload, backend, out):
    audit = validate_batch(payload, getattr(backend, 'max_atoms', MAX_ATOMS))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    _save(out / 'input.json', payload)
    _save(out / 'input-audit.json', audit)
    result = {'schema_version': 1, 'kind': 'uma_pocket_batch_result', 'status': 'running',
              'label': payload['label'], 'input_sha256': audit['input_sha256'],
              'synthetic': bool(backend.metadata.get('synthetic', False)), 'backend': backend.metadata,
              'provisional': audit['provisional'], 'scope': SCOPE, 'systems': [],
              'total_systems': len(payload['systems']), 'reasons': []}
    _save(out / 'result.json', result)
    for system in payload['systems']:
        row = {'id': system['id'], 'protein_id': system['protein_id'], 'ligand': system['ligand'],
               'atoms': len(system['atoms']), 'status': 'failed', 'energy_eV': None}
        try:
            atoms = [{**atom, 'element': atom['element'].capitalize()} for atom in system['atoms']]
            energy, forces = checked_evaluate(backend, atoms, system['state'])
            _save(out / (system['id'] + '-forces.json'), {'forces_eV_A': forces})
            fmax = max(math.hypot(*f) for f in forces)
            require(finite(fmax), 'Nonfinite force norm')
            row.update(status='completed', energy_eV=energy, maximum_force_eV_A=fmax)
        except Exception as error:
            row['reason'] = f'{type(error).__name__}: {error}'
            result['reasons'].append(system['id'] + ': ' + row['reason'])
        result['systems'].append(row)
        _save(out / 'result.json', result)
    result['status'] = 'failed' if result['reasons'] else 'synthetic_demo' if result['synthetic'] else 'exploratory'
    _save(out / 'result.json', result)
    return result


def export_exchange(path):
    """Preserve existing chemistry as separate single-point pocket inputs."""
    from .exchange import validate_manifest
    raw = Path(path).read_bytes()
    manifest = json.loads(raw)
    require(isinstance(manifest, dict), 'Exchange manifest must be a JSON object')
    validate_manifest(manifest)
    systems = []
    for protein, components in manifest['enzymes'].items():
        s = components['cluster_ligand']
        systems.append({
            'id': protein, 'protein_id': protein, 'ligand': manifest['ligand'],
            'source': f'Existing exchange manifest {Path(path).name}; sha256={hashlib.sha256(raw).hexdigest()}',
            'preparation': s['preparation'], 'review': copy.deepcopy(s['review']),
            'atoms': copy.deepcopy(s['atoms']), 'state': copy.deepcopy(s['state']),
            'ligand_atom_ids': [a['id'] for a in s['atoms'] if a['id'] not in s['scaffold_ids']],
            **{key: copy.deepcopy(s.get(key, [])) for key in ('coordination', 'covalent_bounds', 'chirality_checks')},
        })
    payload = {'schema_version': 1, 'kind': 'uma_pocket_batch',
               'label': manifest['ligand'] + ' · prepared pockets', 'systems': systems}
    validate_batch(payload)
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    check = sub.add_parser('check'); check.add_argument('input', type=Path)
    export = sub.add_parser('export-exchange'); export.add_argument('input', type=Path); export.add_argument('--out', type=Path, required=True)
    run = sub.add_parser('run'); run.add_argument('input', type=Path)
    run.add_argument('--backend', type=Path, required=True); run.add_argument('--out', type=Path, required=True)
    run.add_argument('--allow-provisional', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.action == 'export-exchange':
            payload = export_exchange(args.input)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open('x') as handle:
                json.dump(payload, handle, indent=2, allow_nan=False)
            print(args.out)
            return 0
        payload = read_batch(args.input)
        audit = validate_batch(payload)
        if args.action == 'check':
            print(json.dumps(audit, indent=2)); return 0
        require(not audit['provisional'] or args.allow_provisional, 'Provisional inputs require --allow-provisional')
        from .mlip import UMABackend
        config = json.loads(args.backend.read_text())
        require(config.get('kind') == 'uma', 'Prepared batch execution requires a real UMA backend')
        validate_batch(payload, config.get('max_atoms', MAX_ATOMS))
        result = run_batch(payload, UMABackend(config), args.out)
        print(json.dumps(result, indent=2))
        return 0 if result['status'] == 'exploratory' else 1
    except (OSError, ValueError, TypeError) as error:
        print(f'error: {error}', file=sys.stderr); return 2


if __name__ == '__main__':
    raise SystemExit(main())

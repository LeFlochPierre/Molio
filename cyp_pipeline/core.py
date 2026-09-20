"""Validated data contract and deterministic constrained optimization (eV, Å)."""
import hashlib
import json
import math


class ValidationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def validate(system, allow_provisional=False):
    require(system.get('schema_version') == 1, 'Unsupported schema_version')
    for key in ('system_id', 'ligand', 'isoform', 'pose', 'review', 'atoms', 'fragment_ids',
                'cluster_state', 'fragment_state', 'fixed_ids', 'coordination', 'preparation'):
        require(key in system, f'Missing {key}')
    require(system['isoform'] in ('CYP11B1', 'CYP11B2'), 'Invalid isoform')
    require(system['pose'].get('kind') in ('experimental', 'modeled', 'synthetic'), 'Invalid pose kind')
    require(bool(system['pose'].get('source')), 'Pose source is required')
    reviewed = system['review'].get('approved') is True and bool(system['review'].get('reviewer'))
    provisional = system['review'].get('provisional') is True
    require(reviewed or (allow_provisional and provisional),
            'Preparation must be explicitly reviewed (or use --provisional for an assumption-based run)')
    for key in ('protonation', 'oxidation_state', 'caps', 'boundary', 'stereochemistry',
                'reference_coordination', 'fragment_definition', 'pocket_geometry'):
        require(bool(system['preparation'].get(key)), f'Preparation missing {key}')
    if system['pose']['kind'] != 'synthetic':
        require(bool(system.get('comparison_group')), 'Reviewed comparison_group is required')
    atoms = system['atoms']
    require(isinstance(atoms, list) and len(atoms) > 0, 'Atoms must be a nonempty list')
    ids = []
    for atom in atoms:
        require(isinstance(atom.get('id'), str) and atom['id'], 'Atom ID is required')
        require(isinstance(atom.get('element'), str) and atom['element'].isalpha(), 'Invalid element')
        require(atom.get('role') in ('ligand', 'heme', 'axial', 'pocket', 'cap'), 'Invalid atom role')
        p = atom.get('position', [])
        require(len(p) == 3 and all(finite(v) for v in p), 'Positions must be finite xyz triples')
        ids.append(atom['id'])
    require(len(set(ids)) == len(ids), 'Duplicate atom IDs')
    fragment = system['fragment_ids']
    require(fragment and len(set(fragment)) == len(fragment) and set(fragment) <= set(ids),
            'Fragment IDs must be unique and present')
    roles = {a['role'] for a in atoms if a['id'] in fragment}
    require({'ligand', 'heme', 'axial'} <= roles, 'Fragment requires ligand, heme, axial groups')
    require(set(system['fixed_ids']) <= set(ids), 'Unknown fixed atom')
    require(len(system['fixed_ids']) < len(atoms), 'At least one atom must be movable')
    for name in ('cluster_state', 'fragment_state'):
        state = system[name]
        require(type(state.get('charge')) is int, f'{name}: integer charge required')
        require(type(state.get('multiplicity')) is int and state['multiplicity'] > 0,
                f'{name}: positive multiplicity required')
        require(bool(state.get('convention')), f'{name}: electronic-state convention required')
    require(len(system['coordination']) >= 2, 'Review at least Fe-donor and Fe-S coordination')
    for bond in system['coordination']:
        require(len(bond.get('ids', [])) == 2 and len(set(bond['ids'])) == 2
                and set(bond['ids']) <= set(fragment), 'Coordination IDs must belong to fragment')
        low, high = bond.get('min_A'), bond.get('max_A')
        require(finite(low) and finite(high) and 0 < low < high, 'Invalid coordination range')
    return system


def validate_protocol(p):
    require(p.get('descriptor') == 'fragment_deformation_eV', 'Unsupported descriptor')
    for k in ('force_tolerance_eV_A', 'step_size_A2_eV', 'max_step_A',
              'clash_distance_A', 'signal_floor_eV'):
        require(finite(p.get(k)) and p[k] > 0, f'Invalid protocol {k}')
    require(type(p.get('max_steps')) is int and 0 < p['max_steps'] <= 10000, 'Invalid max_steps')
    return p


def distance(a, b):
    return math.sqrt(sum((x-y)**2 for x, y in zip(a, b)))


def geometry(atoms, coordination, clash_distance):
    by_id = {a['id']: a['position'] for a in atoms}
    bonds = [{**b, 'distance_A': distance(*(by_id[i] for i in b['ids']))} for b in coordination]
    valid = all(b['min_A'] <= b['distance_A'] <= b['max_A'] for b in bonds)
    ligand = [a for a in atoms if a['role'] == 'ligand']
    pocket = [a for a in atoms if a['role'] == 'pocket']
    pairs = [distance(a['position'], b['position']) for a in ligand for b in pocket]
    return {'coordination': bonds, 'coordination_valid': valid,
            'ligand_pocket_close_pairs': sum(d < clash_distance for d in pairs),
            'minimum_ligand_pocket_distance_A': min(pairs) if pairs else None}


def checked_evaluate(backend, atoms, state):
    energy, forces = backend.evaluate(atoms, state)
    require(finite(energy), 'Backend returned nonfinite energy')
    require(len(forces) == len(atoms) and all(len(f) == 3 and all(finite(x) for x in f) for f in forces),
            'Backend forces must be finite Nx3 values in eV/Å')
    return energy, forces


def relax(backend, atoms, state, fixed_ids, protocol):
    # Monotone gradient descent with backtracking. Fixed atoms never move.
    atoms = json.loads(json.dumps(atoms))
    free = [i for i, a in enumerate(atoms) if a['id'] not in fixed_ids]
    require(bool(free), 'No free atoms')
    history = []
    for step in range(protocol['max_steps'] + 1):
        energy, forces = checked_evaluate(backend, atoms, state)
        fmax = max(math.sqrt(sum(x*x for x in forces[i])) for i in free)
        history.append({'step': step, 'energy_eV': energy, 'free_fmax_eV_A': fmax})
        if fmax <= protocol['force_tolerance_eV_A']:
            return {'atoms': atoms, 'energy_eV': energy, 'converged': True, 'history': history}
        if step == protocol['max_steps']:
            break
        alpha = min(protocol['step_size_A2_eV'], protocol['max_step_A']/fmax)
        for _ in range(16):
            trial = json.loads(json.dumps(atoms))
            for i in free:
                trial[i]['position'] = [x + alpha*f for x, f in zip(atoms[i]['position'], forces[i])]
            trial_energy, _ = checked_evaluate(backend, trial, state)
            if trial_energy < energy:
                atoms = trial
                break
            alpha *= 0.5
        else:
            break
    return {'atoms': atoms, 'energy_eV': energy, 'converged': False, 'history': history}

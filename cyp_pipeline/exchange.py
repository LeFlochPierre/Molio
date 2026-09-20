"""Four-component ligand/water exchange energies for matched enzyme inputs."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
from .backends import load_backend
from .core import require, finite, checked_evaluate, relax, validate_protocol, digest, distance
from .workflow import save, xyz
from .interpretation import exchange_preference

COMPONENTS = ('cluster_ligand', 'free_water', 'cluster_water', 'free_ligand')
ENZYMES = ('CYP11B1', 'CYP11B2')


def composition(atoms):
    return Counter(a['element'] for a in atoms)


def validate_manifest(m):
    require(m.get('schema_version') == 1, 'Unsupported exchange schema')
    require(bool(m.get('ligand')), 'Ligand identity/stereochemistry required')
    require(bool(m.get('preparation_protocol')), 'Shared preparation protocol required')
    require(m.get('geometry_mode') in ('single_point', 'relax'), 'Choose geometry_mode: single_point or relax')
    validate_protocol(m['optimizer'])
    require(m['optimizer'].get('method', 'gradient_descent') in ('gradient_descent', 'ase_bfgs'), 'Unknown optimizer method')
    require(set(m.get('enzymes', {})) == set(ENZYMES), 'Both enzymes are required')
    for enzyme in ENZYMES:
        parts = m['enzymes'][enzyme]
        require(set(parts) == set(COMPONENTS), f'{enzyme}: exactly four components required')
        for name in COMPONENTS:
            s = parts[name]
            require(isinstance(s, dict), f'{enzyme}/{name}: prepared structure missing')
            require(bool(s.get('preparation')), f'{enzyme}/{name}: preparation rationale required')
            review = s.get('review', {})
            require((review.get('approved') is True and bool(review.get('reviewer'))) or
                    review.get('provisional') is True, f'{enzyme}/{name}: reviewed or explicitly provisional preparation required')
            atoms = s.get('atoms', [])
            require(bool(atoms), f'{enzyme}/{name}: atoms missing')
            ids = [a['id'] for a in atoms]
            require(all(isinstance(i, str) and i for i in ids) and len(ids) == len(set(ids)), 'Invalid/duplicate atom IDs')
            for a in atoms:
                require(isinstance(a['element'], str) and a['element'].isalpha(), 'Invalid element')
                require(len(a['position']) == 3 and all(finite(x) for x in a['position']), 'Invalid coordinates')
            state = s['state']
            require(type(state.get('charge')) is int and type(state.get('multiplicity')) is int
                    and state['multiplicity'] > 0 and bool(state.get('convention')), 'Explicit charge/spin convention required')
            require('fixed_ids' in s and set(s['fixed_ids']) <= set(ids), 'Explicit fixed_ids required')
            require(len(set(s['fixed_ids'])) < len(atoms), 'At least one movable atom required')
            if name.startswith('free_'):
                require(not s['fixed_ids'], 'Free molecules must have no fixed atoms')
            else:
                require(bool(s.get('scaffold_ids')), 'Cluster scaffold_ids required')
                require(set(s['scaffold_ids']) <= set(ids), 'Unknown scaffold atom')
                require(set(s['fixed_ids']) <= set(s['scaffold_ids']), 'Fix only scaffold boundary atoms')
                require(len(s.get('coordination', [])) >= 2, 'Cluster requires explicit Fe-donor and Fe-S bounds')
                for bond in s['coordination']:
                    require(len(bond['ids']) == 2 and len(set(bond['ids'])) == 2 and set(bond['ids']) <= set(ids), 'Invalid coordination atom IDs')
                    require(finite(bond['min_A']) and finite(bond['max_A']) and 0 < bond['min_A'] < bond['max_A'], 'Invalid coordination bounds')
        water = parts['free_water']
        require(composition(water['atoms']) == Counter({'H': 2, 'O': 1}) and water['state']['charge'] == 0
                and water['state']['multiplicity'] == 1, 'Free water must be neutral singlet H2O')
        cl, cw = parts['cluster_ligand'], parts['cluster_water']
        def scaffold(s):
            return {a['id']: a['element'] for a in s['atoms'] if a['id'] in s['scaffold_ids']}
        require(scaffold(cl) == scaffold(cw), 'Ligand/water clusters must use identical scaffold atoms/caps')
        for bound, free in ((cl, parts['free_ligand']), (cw, water)):
            guest = [a for a in bound['atoms'] if a['id'] not in bound['scaffold_ids']]
            require(composition(guest) == composition(free['atoms']), 'Non-scaffold atoms must match the free ligand/water composition')
        require(set(cl['fixed_ids']) == set(cw['fixed_ids']), 'Cluster boundary constraints must match')
        for atom_id in cl['fixed_ids']:
            pa = next(a['position'] for a in cl['atoms'] if a['id'] == atom_id)
            pb = next(a['position'] for a in cw['atoms'] if a['id'] == atom_id)
            require(pa == pb, 'Fixed scaffold coordinates must match')
        require(composition(cl['atoms']) + composition(water['atoms']) ==
                composition(cw['atoms']) + composition(parts['free_ligand']['atoms']), 'Exchange cycle is not atom-balanced')
        require(cl['state']['charge'] + water['state']['charge'] ==
                cw['state']['charge'] + parts['free_ligand']['state']['charge'], 'Exchange cycle is not charge-balanced')
    for name in ('free_water', 'free_ligand'):
        require(m['enzymes'][ENZYMES[0]][name] == m['enzymes'][ENZYMES[1]][name],
                f'Use identical {name} reference inputs for both enzymes')
    return m


def coordination_valid(atoms, bounds):
    positions = {a["id"]: a["position"] for a in atoms}
    return all(b["min_A"] <= distance(*(positions[i] for i in b["ids"])) <= b["max_A"] for b in bounds)



def structure_valid(atoms, s):
    p = {a['id']: a['position'] for a in atoms}
    if not coordination_valid(atoms, s.get('covalent_bounds', [])):
        return False
    for c in s.get('chirality_checks', []):
        center = p[c['center']]
        a,b,d = [[p[i][k]-center[k] for k in range(3)] for i in c['neighbors']]
        volume = a[0]*(b[1]*d[2]-b[2]*d[1])-a[1]*(b[0]*d[2]-b[2]*d[0])+a[2]*(b[0]*d[1]-b[1]*d[0])
        if volume*c['reference_volume_A3'] <= 0 or abs(volume) < 0.1:
            return False
    return True


def exchange_energy(energies):
    require(set(energies) == set(COMPONENTS) and all(finite(e) for e in energies.values()), 'Four finite energies required')
    return math.fsum((energies['cluster_ligand'], energies['free_water'],
                      -energies['cluster_water'], -energies['free_ligand']))


def run_cycle(m, backend, out):
    validate_manifest(m)
    out = Path(out); out.mkdir(parents=True, exist_ok=False)
    save(out/'input.json', m)
    result = {'descriptor': 'ligand_water_exchange_eV', 'ligand': m['ligand'],
              'geometry_mode': m['geometry_mode'], 'input_sha256': digest(m),
              'backend': backend.metadata, 'status': 'unresolved',
              'provisional': any(s['review'].get('approved') is not True for p in m['enzymes'].values() for s in p.values()),
              'synthetic': backend.metadata.get('synthetic', False),
              'formula': 'cluster_ligand + free_water - cluster_water - free_ligand',
              'sign_convention': 'delta = exchange(CYP11B2) - exchange(CYP11B1); negative favors B2 in this energy model',
              'interpretation': 'Potential-energy exchange descriptor; not a binding free energy or measured selectivity.',
              'enzymes': {}, 'delta_B2_minus_B1_eV': None, 'reasons': []}
    save(out/'result.json', result)
    for enzyme in ENZYMES:
        row = {'components': {}, 'exchange_energy_eV': None}
        result['enzymes'][enzyme] = row
        for name in COMPONENTS:
            s = m['enzymes'][enzyme][name]
            folder = out/enzyme/name; folder.mkdir(parents=True)
            save(folder/'input.json', s); xyz(folder/'before.xyz', s['atoms'])
            component = {'status': 'failed', 'energy_eV': None}
            try:
                bounds = s.get('coordination', [])
                require(structure_valid(s['atoms'], s), 'Initial covalent geometry/stereochemistry invalid')
                require(coordination_valid(s['atoms'], bounds), 'Initial coordination outside bounds')
                if m['geometry_mode'] == 'relax':
                    if m['optimizer'].get('method') == 'ase_bfgs':
                        from .ase_relax import relax_bfgs
                        calculation = relax_bfgs(backend, s['atoms'], s['state'], s['fixed_ids'], m['optimizer'], folder)
                    else:
                        calculation = relax(backend, s['atoms'], s['state'], s['fixed_ids'], m['optimizer'])
                    save(folder/'relaxation.json', calculation)
                    xyz(folder/'after.xyz', calculation['atoms'])
                    require(calculation['converged'], 'Relaxation did not converge')
                    require(coordination_valid(calculation['atoms'], bounds), 'Final coordination outside bounds')
                    require(structure_valid(calculation['atoms'], s), 'Final covalent geometry/stereochemistry invalid')
                    energy = calculation['energy_eV']
                else:
                    energy, forces = checked_evaluate(backend, s['atoms'], s['state'])
                    save(folder/'forces.json', forces)
                component.update(status='completed', energy_eV=energy)
            except Exception as exc:
                component['reason'] = f'{type(exc).__name__}: {exc}'
                result['reasons'].append(f'{enzyme}/{name}: {component["reason"]}')
            row['components'][name] = component
            save(folder/'result.json', component)
            save(out/'result.json', result)
        if all(v['status'] == 'completed' for v in row['components'].values()):
            row['exchange_energy_eV'] = exchange_energy({k:v['energy_eV'] for k,v in row['components'].items()})
    if not result['reasons']:
        delta = result['enzymes']['CYP11B2']['exchange_energy_eV'] - result['enzymes']['CYP11B1']['exchange_energy_eV']
        result.update(status='synthetic_demo' if result['synthetic'] else 'exploratory', delta_B2_minus_B1_eV=delta)
        result['energy_model_preference'] = None if result['synthetic'] else ('CYP11B2' if delta < 0 else 'CYP11B1' if delta > 0 else 'tie')
    result['preference_summary'] = exchange_preference(result)
    save(out/'result.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest'); p.add_argument('--backend'); p.add_argument('--out'); p.add_argument('--check-only', action='store_true')
    p.add_argument('--single-pose', action='store_true', help='Explicit legacy single-pose calculation')
    p.add_argument('--sampling-settings', type=Path, help='Shared pose-grid settings JSON')
    p.add_argument('--resume', action='store_true', help='Resume matching pose-search output')
    args = p.parse_args()
    try:
        m = validate_manifest(json.loads(Path(args.manifest).read_text()))
        sampling = m['geometry_mode'] == 'relax' and not args.single_pose
        settings = json.loads(args.sampling_settings.read_text()) if args.sampling_settings else m.get('pose_sampling')
        if sampling:
            from .pose_sampling import configuration, validate_sampling, run_search
            validate_sampling(m, configuration(settings))
        if args.check_only:
            print('Four-component exchange contract valid; chemistry is not independently validated.'); return 0
        require(args.backend and args.out, '--backend and --out required')
        require(args.resume or not Path(args.out).exists(), 'Output directory already exists')
        require(not args.resume or sampling, 'Resume requires pose sampling')
        config = json.loads(Path(args.backend).read_text())
        result = (run_search(m, load_backend(config), args.out, settings, args.resume) if sampling
                  else run_cycle(m, load_backend(config), args.out))
        save(Path(args.out)/'backend_config.json', config)
        print(json.dumps(result, indent=2))
        return 0 if result['status'] == 'exploratory' else 1
    except (ValueError, KeyError, TypeError, OSError, ImportError) as exc:
        print(f'error: {exc}'); return 2


if __name__ == '__main__':
    raise SystemExit(main())

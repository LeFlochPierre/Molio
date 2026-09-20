"""Symmetric pose ensembles around the unchanged exchange relaxation protocol."""
import argparse
import copy
import csv
import json
import math
from pathlib import Path
import numpy as np
from .core import digest, distance, finite, relax, require
from .exchange import COMPONENTS, ENZYMES, exchange_energy, validate_manifest, structure_valid
from .workflow import save, xyz

KB_EV_K = 8.617333262145e-5
DEFAULTS = dict(rotation_start_deg=0., rotation_stop_deg=360., rotation_step_deg=15.,
                tilt_start_deg=-20., tilt_stop_deg=20., tilt_step_deg=10.,
                rmsd_threshold_A=0.25, temperature_K=310.)


def configuration(overrides=None):
    overrides = overrides or {}
    require(not set(overrides) - set(DEFAULTS), 'Unknown pose-sampling setting')
    c = {**DEFAULTS, **overrides}
    require(all(finite(v) for v in c.values()), 'Sampling settings must be finite numbers')
    for k in ('rotation_step_deg', 'tilt_step_deg', 'rmsd_threshold_A', 'temperature_K'):
        require(c[k] > 0, f'{k} must be positive')
    require(0 < c['rotation_stop_deg'] - c['rotation_start_deg'] <= 360, 'Rotation range must be in (0, 360]')
    require(-90 < c['tilt_start_deg'] <= c['tilt_stop_deg'] < 90, 'Invalid tilt range')
    return c


def seed_grid(c):
    # Rotation endpoint excluded: 360 degrees is the same orientation as zero.
    rotations = np.arange(c['rotation_start_deg'], c['rotation_stop_deg'], c['rotation_step_deg']).tolist()
    tilts = np.arange(c['tilt_start_deg'], c['tilt_stop_deg'] + 1e-9, c['tilt_step_deg']).tolist()
    require(rotations and tilts and len(rotations)*len(tilts) <= 100000, 'Invalid or excessive seed count')
    # Interleave opposite sectors, and visit zero tilt first, for useful prefixes.
    order = []
    remaining = list(range(len(rotations)))
    while remaining:
        if not order:
            chosen = remaining[0]
        else:
            chosen = max(remaining, key=lambda i: min(min(abs(rotations[i]-rotations[j]),
                         360-abs(rotations[i]-rotations[j])) for j in order))
        order.append(chosen); remaining.remove(chosen)
    tilts.sort(key=lambda x: (abs(x), x))
    return [dict(seed_id=f'pose_{n:04d}', rotation_deg=rotations[i], tilt_deg=t)
            for n, (i, t) in enumerate((i, t) for i in order for t in tilts)]


def unit(v):
    v = np.asarray(v, dtype=float)
    require(np.linalg.norm(v) > 1e-10, 'Degenerate pose frame')
    return v / np.linalg.norm(v)


def rotation(axis, degrees):
    x, y, z = unit(axis); a = math.radians(degrees)
    cross = np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
    return np.eye(3)*math.cos(a) + (1-math.cos(a))*np.outer([x,y,z],[x,y,z]) + math.sin(a)*cross


def frame(s):
    p = {a['id']:np.asarray(a['position']) for a in s['atoms']}
    scaffold = set(s['scaffold_ids'])
    donors = [(a,b) if a in scaffold else (b,a) for bond in s['coordination']
              for a,b in [bond['ids']] if (a in scaffold) != (b in scaffold)]
    require(len(donors) == 1, 'Exactly one scaffold/guest coordination bond required')
    fe, donor = donors[0]
    require(next(a['element'] for a in s['atoms'] if a['id']==fe) == 'Fe', 'Pose axis must start at Fe')
    axis = unit(p[donor]-p[fe])
    heme_ids = s.get('sampling_frame', {}).get('heme_plane_ids', ['heme_NA','heme_NB','heme_NC','heme_ND'])
    require(len(heme_ids) >= 3 and set(heme_ids) <= set(p), 'Explicit heme-plane atom IDs required')
    heme = np.array([p[i] for i in heme_ids]); _,_,vh = np.linalg.svd(heme-heme.mean(0))
    normal = vh[-1]
    if np.dot(normal, axis) < 0: normal = -normal
    plane_ids = s.get('sampling_frame', {}).get('guest_plane_ids')
    if plane_ids is None:
        # Fadrozole imidazole ring or water molecular plane; other guests must specify IDs.
        plane_ids = ['ligand_N06','ligand_C05','ligand_C07'] if donor == 'ligand_N06' else [a['id'] for a in s['atoms'] if a['id'] not in scaffold]
    require(len(plane_ids) >= 3 and set(plane_ids) <= set(p), 'Guest plane needs at least three atom IDs')
    require(set(plane_ids).isdisjoint(scaffold), 'Guest plane must contain only guest atoms')
    guest = np.array([p[i] for i in plane_ids]); _, singular, vh = np.linalg.svd(guest-guest.mean(0))
    require(singular[1] > 1e-8, 'Guest plane atoms are collinear')
    return donor, axis, normal, vh[-1]


def make_pose(s, seed, bound_frame=None):
    result = copy.deepcopy(s)
    donor, axis, normal, guest_normal = bound_frame or frame(s)
    p = {a['id']:np.asarray(a['position'], dtype=float) for a in s['atoms']}
    if donor not in p:  # Free water IDs differ from bound water IDs.
        donors = [a['id'] for a in s['atoms'] if a['element'] == 'O']
        require(len(donors) == 1, 'Cannot map free-reference donor')
        donor = donors[0]
    origin = p[donor]
    twist = rotation(axis, seed['rotation_deg'])
    rotated_normal = twist @ guest_normal
    tilt_axis = np.cross(normal, rotated_normal)
    if np.linalg.norm(tilt_axis) < 1e-8:
        tilt_axis = np.cross(normal, np.eye(3)[np.argmin(abs(normal))])
    # Tilt is an offset from the azole-plane/heme-normal angle after twist.
    transform = rotation(tilt_axis, seed['tilt_deg']) @ twist
    scaffold = set(s.get('scaffold_ids', []))
    for a in result['atoms']:
        if a['id'] not in scaffold and a['id'] != donor:
            a['position'] = (origin + transform @ (p[a['id']]-origin)).tolist()
    return result


def audit(atoms, source):
    problems = []
    p = {a['id']:a for a in atoms}; initial = {a['id']:a for a in source['atoms']}
    if set(p) != set(initial) or any(p[i]['element'] != initial[i]['element'] for i in p):
        return ['atom_identity_changed']
    if any(len(a['position']) != 3 or not all(finite(x) for x in a['position']) for a in atoms):
        return ['nonfinite_coordinates']
    for label, bounds in [('coordination',source.get('coordination', [])),
                          ('bond_integrity',source.get('covalent_bounds', []) + source.get('audit_bonds', []))]:
        for b in bounds:
            d = distance(*(p[i]['position'] for i in b['ids']))
            if not b['min_A'] <= d <= b['max_A']:
                problems.append(f'{label}: {b["ids"]}, distance={d:.8f} A, bounds={b["min_A"]}:{b["max_A"]}')
    for i in source['fixed_ids']:
        if distance(p[i]['position'], initial[i]['position']) > 1e-10:
            problems.append(f'fixed_boundary: {i}')
    if not structure_valid(atoms, {**source, 'covalent_bounds': []}):
        problems.append('stereochemistry: signed-volume preservation failed')
    return problems


def heavy_rmsd(a, b, scaffold_ids=()):
    """Atom-ID correspondence; scaffold fit only, never fit the guest independently."""
    pa = {x['id']:x for x in a}; pb = {x['id']:x for x in b}
    require(set(pa)==set(pb), 'RMSD atom identities differ')
    ids = sorted(i for i in pa if pa[i]['element'] != 'H')
    x = np.array([pa[i]['position'] for i in ids]); y = np.array([pb[i]['position'] for i in ids])
    anchors = [i for i,k in enumerate(ids) if k in scaffold_ids]
    if not scaffold_ids:
        anchors = list(range(len(ids)))  # Free molecules: remove rigid-body motion.
    require(len(anchors) >= 1, 'No heavy RMSD anchors')
    xc = x[anchors].mean(0); yc = y[anchors].mean(0)
    u,_,vt = np.linalg.svd((x[anchors]-xc).T @ (y[anchors]-yc))
    correction = np.eye(3); correction[-1,-1] = np.linalg.det(u@vt)
    r = u @ correction @ vt
    return float(np.sqrt(np.mean(np.sum(((x-xc)@r-(y-yc))**2,axis=1))))


def ensemble(records, source, c):
    accepted = [r for r in records if r['status']=='accepted']
    if not accepted: return None
    # Energy-ordered leader clustering: every member is within threshold of its
    # lowest-energy representative; no single-linkage chaining or seed degeneracy.
    clusters = []
    for record in sorted(accepted, key=lambda r:(r['energy_eV'], r['seed_id'])):
        for group in clusters:
            if heavy_rmsd(record['atoms'], group[0]['atoms'], source.get('scaffold_ids', [])) <= c['rmsd_threshold_A']:
                group.append(record); break
        else: clusters.append([record])
    energies = np.array([g[0]['energy_eV'] for g in clusters]); minimum = float(energies.min())
    weights = np.exp(-(energies-minimum)/(KB_EV_K*c['temperature_K'])); weights /= weights.sum()
    raw = [r['energy_eV'] for r in accepted]
    return dict(minimum_energy_eV=minimum, boltzmann_energy_eV=float(weights@energies),
                energy_spread_eV=max(raw)-min(raw), deduplicated_spread_eV=float(energies.max()-energies.min()),
                accepted_count=len(accepted), rejected_count=len(records)-len(accepted), minima_count=len(clusters),
                minima=[dict(representative=g[0]['seed_id'], energy_eV=float(e), population=float(w),
                             members=[r['seed_id'] for r in g]) for g,e,w in zip(clusters,energies,weights)])


def calculate_pose(s, seed, backend, optimizer, folder, bound_frame=None):
    folder.mkdir(parents=True, exist_ok=True)
    record = {**seed, 'status':'rejected', 'reasons':[]}
    try:
        pose = make_pose(s, seed, bound_frame)
        save(folder/'input.json', pose); xyz(folder/'before.xyz',pose['atoms'])
        record['reasons'] = audit(pose['atoms'], s)
        require(not record['reasons'], 'Initial audits failed')
        if optimizer.get('method') == 'ase_bfgs':
            from .ase_relax import relax_bfgs
            calculation = relax_bfgs(backend,pose['atoms'],pose['state'],pose['fixed_ids'],optimizer,folder)
        else:
            calculation = relax(backend,pose['atoms'],pose['state'],pose['fixed_ids'],optimizer)
        save(folder/'relaxation.json',calculation); xyz(folder/'after.xyz',calculation['atoms'])
        record['reasons'] = audit(calculation['atoms'], s)
        if not calculation['converged']: record['reasons'].append('relaxation_not_converged')
        if not finite(calculation['energy_eV']): record['reasons'].append('nonfinite_energy')
        if not record['reasons']:
            record.update(status='accepted', energy_eV=calculation['energy_eV'],atoms=calculation['atoms'])
    except Exception as exc:
        record['reasons'].append(f'{type(exc).__name__}: {exc}')
    save(folder/'result.json',record)
    return record


def validate_sampling(m, c):
    validate_manifest(m)
    require(m['geometry_mode']=='relax','Pose sampling requires relaxation')
    seed_grid(c)
    for enzyme in ENZYMES:
        for name,s in m['enzymes'][enzyme].items():
            require(s.get('covalent_bounds'), f'{enzyme}/{name}: explicit covalent audits required')
            if name.startswith('cluster_'):
                frame(s)
                require(s.get('audit_bonds'), f'{enzyme}/{name}: source-topology/cap audit ledger required')
            if 'ligand' in name and m['ligand'].lower().startswith('s-'):
                require(s.get('chirality_checks'), 'S stereochemistry audit required')


def summarize(m, histories, c, count):
    rows = {}; complete = True
    for enzyme in ENZYMES:
        parts = {name:ensemble(histories[enzyme][name],m['enzymes'][enzyme][name],c) for name in COMPONENTS}
        row = dict(components=parts,exchange_energy_eV=None,minimum_exchange_energy_eV=None)
        if all(parts.values()):
            row['exchange_energy_eV'] = exchange_energy({k:v['boltzmann_energy_eV'] for k,v in parts.items()})
            row['minimum_exchange_energy_eV'] = exchange_energy({k:v['minimum_energy_eV'] for k,v in parts.items()})
        else: complete = False
        rows[enzyme] = row
    result = dict(status='unresolved', poses_included_per_component=count, enzymes=rows,
                  delta_B2_minus_B1_eV=None, minimum_delta_B2_minus_B1_eV=None, energy_model_preference=None)
    if complete:
        delta = rows[ENZYMES[1]]['exchange_energy_eV'] - rows[ENZYMES[0]]['exchange_energy_eV']
        # Free-reference spreads cancel exactly. Sum bound/apo ranges from both
        # isoforms gives the full independent pose-to-pose delta range width.
        spread = sum(rows[e]['components'][k]['energy_spread_eV'] for e in ENZYMES
                     for k in ('cluster_ligand','cluster_water'))
        floor = m['optimizer'].get('signal_floor_eV',0.)
        unresolved = abs(delta) <= max(spread,floor)
        result.update(delta_B2_minus_B1_eV=delta,
                      minimum_delta_B2_minus_B1_eV=rows[ENZYMES[1]]['minimum_exchange_energy_eV']-rows[ENZYMES[0]]['minimum_exchange_energy_eV'],
                      pose_to_pose_delta_spread_eV=spread,
                      status='unresolved' if unresolved else 'exploratory',
                      reason='Delta does not exceed pose spread/signal floor' if unresolved else None,
                      energy_model_preference=None if unresolved else ('CYP11B2' if delta<0 else 'CYP11B1'))
    return result


def run_search(m, backend, out, settings=None, resume=False):
    c = configuration(settings if settings is not None else m.get('pose_sampling'))
    validate_sampling(m,c)
    seeds = seed_grid(c); out = Path(out)
    signature = digest(dict(manifest=m,settings=c,backend=backend.metadata))
    if resume:
        require(json.loads((out/'search.json').read_text())['signature']==signature, 'Resume inputs/backend/settings changed')
    else:
        out.mkdir(parents=True,exist_ok=False)
        save(out/'input.json',m)
        save(out/'search.json',dict(signature=signature,settings=c,seeds=seeds,backend=backend.metadata))
    histories = {e:{k:[] for k in COMPONENTS} for e in ENZYMES}; convergence = []
    frames = {(e,k):frame(m['enzymes'][e][k]) for e in ENZYMES for k in ('cluster_ligand','cluster_water')}
    for seed in seeds:
        for enzyme in ENZYMES:
            for name in COMPONENTS:
                if name.startswith('free_') and enzyme == ENZYMES[1]:
                    histories[enzyme][name].append(histories[ENZYMES[0]][name][-1]); continue
                s = m['enzymes'][enzyme][name]
                folder = out/enzyme/name/seed['seed_id']
                cached = folder/'result.json'
                if resume and cached.exists():
                    record = json.loads(cached.read_text())
                else:
                    bound = frames[enzyme,name.replace('free_','cluster_')] if name.startswith('free_') else None
                    record = calculate_pose(s,seed,backend,m['optimizer'],folder,bound)
                histories[enzyme][name].append(record)
        result = summarize(m,histories,c,len(convergence)+1)
        convergence.append({k:v for k,v in result.items() if k!='enzymes'})
        result.update(completed_seed_count=len(convergence),total_seed_count=len(seeds),
                      sampling_complete=len(convergence)==len(seeds),settings=c,
                      descriptor='Boltzmann mean potential-energy ligand/water exchange; not binding free energy',
                      provisional=any(s['review'].get('approved') is not True for p in m['enzymes'].values() for s in p.values()),
                      synthetic=backend.metadata.get('synthetic',False),
                      shared_free_references='Calculated once per seed and used identically for both isoforms')
        if not result['sampling_complete'] or result['synthetic']:
            result['energy_model_preference'] = None
            result['status'] = 'running' if not result['sampling_complete'] else 'synthetic_demo'
        save(out/'result.json',result); save(out/'convergence.json',convergence)
        with (out/'convergence.csv').open('w') as f:
            fields=['poses_included_per_component','delta_B2_minus_B1_eV','minimum_delta_B2_minus_B1_eV','pose_to_pose_delta_spread_eV','status']
            writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); writer.writeheader(); writer.writerows(convergence)
        report(out,result,convergence)
    return result


def report(out, result, convergence):
    lines = ['# Pose sampling exchange result','',f"Status: **{result['status']}**. Completed {result['completed_seed_count']}/{result['total_seed_count']} seeds per component.",'',result['descriptor'], '',
             'Primary values use one Boltzmann weight per deduplicated minimum at '+str(result['settings']['temperature_K'])+' K; seed multiplicity is not a statistical weight.', '',
             '| Component | Accepted | Rejected | Minima | Minimum (eV) | Boltzmann mean (eV) | Spread (eV) |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for enzyme,row in result['enzymes'].items():
        for name,v in row['components'].items():
            if v:
                lines.append(f"| {enzyme}/{name} | {v['accepted_count']} | {v['rejected_count']} | {v['minima_count']} | {v['minimum_energy_eV']:.8f} | {v['boltzmann_energy_eV']:.8f} | {v['energy_spread_eV']:.8f} |")
    lines += ['',f"Numerical ΔΔE (B2−B1), Boltzmann: {result['delta_B2_minus_B1_eV']} eV; minimum-based: {result['minimum_delta_B2_minus_B1_eV']} eV.",
              f"Selectivity: {result.get('energy_model_preference') or 'unresolved (no directional claim)' }.",
              f"Pose-to-pose ΔΔE spread: {result.get('pose_to_pose_delta_spread_eV')} eV.", '',
              '## Lowest minima populations','']
    for enzyme,row in result['enzymes'].items():
        for name,v in row['components'].items():
            if v:
                lines.append(f"- {enzyme}/{name}: "+'; '.join(f"{g['representative']} {g['population']:.2%}" for g in v['minima'][:5]))
    lines += ['', '## Convergence', '', '| Seeds per component | Boltzmann ΔΔE (eV) | Minimum ΔΔE (eV) |','|---:|---:|---:|']
    for row in convergence:
        lines.append(f"| {row['poses_included_per_component']} | {row['delta_B2_minus_B1_eV']} | {row['minimum_delta_B2_minus_B1_eV']} |")
    lines += ['', 'Each rejected pose has a result.json containing its audit or relaxation failure reason. Convergence is diagnostic; completing the grid does not establish convergence outside the sampled domain.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path); parser.add_argument('--backend',type=Path)
    parser.add_argument('--out',type=Path); parser.add_argument('--settings',type=Path)
    parser.add_argument('--check-only',action='store_true'); parser.add_argument('--resume',action='store_true')
    args = parser.parse_args()
    m = json.loads(args.manifest.read_text())
    settings = json.loads(args.settings.read_text()) if args.settings else m.get('pose_sampling')
    c = configuration(settings); validate_sampling(m,c)
    if args.check_only:
        print(json.dumps(dict(seeds_per_component=len(seed_grid(c)),settings=c))); return
    require(args.backend and args.out,'--backend and --out required')
    from .backends import load_backend
    config = json.loads(args.backend.read_text())
    result = run_search(m,load_backend(config),args.out,c,args.resume)
    save(args.out/'backend_config.json',config)
    print(json.dumps({k:v for k,v in result.items() if k!='enzymes'},indent=2))


if __name__ == '__main__':
    main()

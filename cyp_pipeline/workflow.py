import copy
import datetime
import json
import platform
import time
from pathlib import Path
from . import __version__
from .core import validate, validate_protocol, require, digest, geometry, checked_evaluate, relax


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def xyz(path, atoms):
    lines = [str(len(atoms)), "CYP pipeline; coordinates in angstrom"]
    lines.extend(a["element"] + " " + " ".join(str(x) for x in a["position"]) for a in atoms)
    Path(path).write_text("\n".join(lines) + "\n")


def run(system, protocol, backend, output, provisional=False):
    validate(system, allow_provisional=provisional)
    validate_protocol(protocol)
    synthetic = system['pose']['kind'] == 'synthetic'
    require(synthetic == backend.metadata.get('synthetic', False),
            'Synthetic systems and real systems cannot share a backend')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'input.json', system)
    xyz(output / 'before.xyz', system['atoms'])
    save(output / 'protocol.json', protocol)
    started = time.monotonic()
    result = {'schema_version': 1, 'system_id': system['system_id'], 'ligand': system['ligand'],
              'isoform': system['isoform'], 'pose': system['pose'], 'synthetic': synthetic,
              'input_sha256': digest(system), 'protocol_sha256': digest(protocol),
              'backend': backend.metadata, 'pipeline_version': __version__,
              'python_version': platform.python_version(),
              'timestamp_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'status': 'failed', 'descriptor_eV': None, 'reasons': [],
              'provisional': provisional,
              'comparison_key': digest({
                  'group': system.get('comparison_group'),
                  'atoms': sorted((a['id'], a['element'], a['role']) for a in system['atoms']
                                  if a['id'] in system['fragment_ids']),
                  'state': system['fragment_state'],
                  'preparation': {k: system['preparation'][k] for k in
                      ('fragment_definition', 'caps', 'reference_coordination', 'protonation', 'stereochemistry')}
              })}
    try:
        before = geometry(system['atoms'], system['coordination'], protocol['clash_distance_A'])
        result['baseline_before'] = before
        require(before['coordination_valid'], 'Initial coordination outside reviewed limits')
        cluster = relax(backend, system['atoms'], system['cluster_state'], system['fixed_ids'], protocol)
        save(output / 'cluster_relaxation.json', cluster)
        xyz(output / 'after.xyz', cluster['atoms'])
        result['baseline_after'] = geometry(cluster['atoms'], system['coordination'], protocol['clash_distance_A'])
        fragment = [copy.deepcopy(a) for a in cluster['atoms'] if a['id'] in system['fragment_ids']]
        # Both energy terms use exactly these atoms and the same state/backend.
        imposed_energy, _ = checked_evaluate(backend, fragment, system['fragment_state'])
        reference = relax(backend, fragment, system['fragment_state'], [], protocol)
        save(output / 'fragment_reference.json', reference)
        xyz(output / 'reference.xyz', reference['atoms'])
        result['reference_geometry'] = geometry(reference['atoms'], system['coordination'], protocol['clash_distance_A'])
        result['energies_eV'] = {'fragment_imposed': imposed_energy,
                                 'fragment_reference': reference['energy_eV']}
        result['convergence'] = {'cluster': cluster['converged'], 'reference': reference['converged']}
        for name, ok in [('cluster_convergence', cluster['converged']),
                         ('reference_convergence', reference['converged']),
                         ('cluster_coordination', result['baseline_after']['coordination_valid']),
                         ('reference_coordination', result['reference_geometry']['coordination_valid'])]:
            if not ok:
                result['reasons'].append(name)
        if result['reasons']:
            result['status'] = 'unresolved'
        else:
            result['status'] = 'synthetic_demo' if synthetic else 'exploratory'
            result['descriptor_eV'] = imposed_energy - reference['energy_eV']
    except Exception as exc:
        result['reasons'].append(f'{type(exc).__name__}: {exc}')
    result['runtime_seconds'] = time.monotonic() - started
    save(output / 'result.json', result)
    return result


def compare(results, protocol):
    """Only matched protocols/models/fragment compositions may be contrasted."""
    comparisons = []
    for ligand in sorted({r['ligand'] for r in results}):
        group = [r for r in results if r['ligand'] == ligand]
        row = {'ligand': ligand, 'status': 'unresolved', 'delta_B2_minus_B1_eV': None}
        if any(r['synthetic'] for r in group):
            row['reason'] = 'Synthetic demo: no scientific preference assigned'
        elif any(r['descriptor_eV'] is None or r['status'] != 'exploratory' for r in group):
            row['reason'] = 'Failed or unresolved calculation'
        elif len({r['protocol_sha256'] for r in group}) != 1 or group[0]['protocol_sha256'] != digest(protocol):
            row['reason'] = 'Protocol mismatch'
        elif len({digest(r['backend']) for r in group}) != 1:
            row['reason'] = 'Backend mismatch'
        elif len({r.get('comparison_key') for r in group}) != 1 or not group[0].get('comparison_key'):
            row['reason'] = 'Fragment/state/preparation comparison contract mismatch'
        else:
            a = [r['descriptor_eV'] for r in group if r['isoform'] == 'CYP11B1']
            b = [r['descriptor_eV'] for r in group if r['isoform'] == 'CYP11B2']
            if not a or not b:
                row['reason'] = 'Missing isoform'
            else:
                low, high = min(b)-max(a), max(b)-min(a)
                row['delta_B2_minus_B1_eV'] = [low, high]
                floor = protocol['signal_floor_eV']
                if low > floor or high < -floor:
                    row.update(status='exploratory', descriptor_preference='CYP11B1' if low > floor else 'CYP11B2',
                               reason='Descriptor hypothesis only; accuracy and uncertainty unvalidated')
                else:
                    row['reason'] = 'Sensitivity range crosses zero or falls within signal floor'
        comparisons.append(row)
    return comparisons



# Preserve the public import used by CLI and callers.
from .reporting import report

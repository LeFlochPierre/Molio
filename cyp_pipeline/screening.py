"""CPU-only screening plans with explicit coverage and preparation gates.

This module plans work; it does not predict binding or run models. The catalog
can grow independently of the two deliberately allow-listed UMA executors.
Neither a matching candidate name nor a custom sequence unlocks a preset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = Path(__file__).with_name('data') / 'screening_catalog.json'
# Shared with the web executor. A catalog entry must never authorize execution.
PREPARED_PRESETS = {
    'r_fadrozole': {
        'label': 'R-fadrozole', 'manifest': 'prepared/exchange-R-pilot-v1/manifest.json',
    },
    's_fadrozole': {
        'label': 'S-fadrozole', 'manifest': 'prepared/exchange-pilot-v1/manifest.json',
    },
}
CANDIDATES = {
    **{key: {'label': value['label']} for key, value in PREPARED_PRESETS.items()},
    'osilodrostat': {'label': 'Osilodrostat (LCI699)'},
    'baxdrostat': {'label': 'Baxdrostat'},
}
PAIR = ('CYP11B2', 'CYP11B1')


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _text(value, name, limit=120):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{name} must be nonempty text of at most {limit} characters')
    return value.strip()


def load_catalog(path=DEFAULT_CATALOG):
    catalog = json.loads(Path(path).read_text())
    if not isinstance(catalog, dict) or catalog.get('schema_version') != 1:
        raise ValueError('Unsupported screening catalog')
    targets, panels = catalog.get('targets'), catalog.get('panels')
    if not isinstance(targets, dict) or not targets or not isinstance(panels, dict) or not panels:
        raise ValueError('Catalog needs targets and panels')
    if len(targets) > 100 or len(panels) > 25 or 'custom' in targets:
        raise ValueError('Catalog is too large or uses the reserved custom target ID')
    for key, row in targets.items():
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', key) or not isinstance(row, dict):
            raise ValueError('Invalid target catalog entry')
        for field in ('label', 'family', 'reason'):
            _text(row.get(field), f'{key}.{field}', 1000)
    for key, panel in panels.items():
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', key) or not isinstance(panel, dict):
            raise ValueError('Invalid panel catalog entry')
        _text(panel.get('label'), f'{key}.label')
        members = panel.get('targets')
        if (not isinstance(members, list) or not members or
                any(not isinstance(x, str) or x not in targets for x in members) or
                len(set(members)) != len(members)):
            raise ValueError('Panels need unique, registered targets')
    return catalog


def catalog_payload(catalog=None):
    catalog = load_catalog() if catalog is None else catalog
    return {'catalog': catalog, 'candidates': CANDIDATES,
            'default_panel': 'steroidogenic_p450' if 'steroidogenic_p450' in catalog['panels'] else next(iter(catalog['panels'])),
            'gpu_required': False, 'automatic_discovery': False}


def _sequence(value):
    value = _text(value, 'Custom target sequence', 12000)
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if sum(line.startswith('>') for line in lines) > 1 or any(line.startswith('>') for line in lines[1:]):
        raise ValueError('Provide one protein sequence, not a multi-record FASTA')
    sequence = re.sub(r'\s+', '', ''.join(line for line in lines if not line.startswith('>'))).upper()
    if not 50 <= len(sequence) <= 5000 or not re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+', sequence):
        raise ValueError('Use 50–5000 standard amino-acid letters for a custom target')
    return sequence


def _candidate(request):
    key = _text(request.get('candidate_id'), 'candidate_id')
    if key in CANDIDATES:
        if request.get('smiles') or request.get('candidate_name'):
            raise ValueError('Preset identity cannot be overridden; choose custom for a new molecule')
        return {'id': key, **CANDIDATES[key], 'identity_status': 'registered_preset', 'smiles': None}
    if key != 'custom':
        raise ValueError('Unknown candidate_id')
    name = _text(request.get('candidate_name') or 'New candidate', 'Candidate name')
    smiles = _text(request.get('smiles'), 'SMILES', 4096)
    if any(c.isspace() or not c.isprintable() for c in smiles):
        raise ValueError('SMILES must be a single string without whitespace or a name suffix')
    # The core demo has no chemistry dependency. Never claim syntax validity
    # from a regular expression; keep the gate closed if RDKit is absent.
    validation = {'status': 'not_checked', 'reason': 'RDKit is not installed in the server environment.'}
    try:
        from rdkit import Chem
    except ImportError:
        pass
    else:
        from rdkit import rdBase
        with rdBase.BlockLogs():
            molecule = Chem.MolFromSmiles(smiles)
        if molecule is None or not molecule.GetNumAtoms():
            raise ValueError('RDKit could not parse the SMILES')
        centers = Chem.FindMolChiralCenters(molecule, includeUnassigned=True)
        validation = {
            'status': 'syntax_checked', 'canonical_isomeric_smiles': Chem.MolToSmiles(molecule, isomericSmiles=True),
            'atom_count': molecule.GetNumAtoms(),
            'unassigned_tetrahedral_centers': sum(label == '?' for _, label in centers),
            'reason': 'Syntax only; full stereochemistry, protonation and 3D preparation still need review.',
        }
    return {'id': key, 'label': name, 'smiles': smiles, 'identity_status': 'new_unprepared_molecule',
            'smiles_validation': validation}


def _prepared_inputs(root, candidate_id):
    preset = PREPARED_PRESETS.get(candidate_id)
    if preset is None:
        return {'status': 'preparation_required', 'reason': 'No allow-listed UMA inputs for this candidate.'}
    path = Path(root) / preset['manifest']
    if not path.is_file():
        return {'status': 'missing_inputs', 'manifest': preset['manifest'], 'reason': 'Prepared manifest is missing on this machine.'}
    try:
        from .exchange import validate_manifest, structure_valid, coordination_valid
        raw = path.read_bytes()
        manifest = json.loads(raw)
        if not isinstance(manifest, dict) or manifest.get('ligand') != preset['label']:
            raise ValueError('Manifest candidate identity does not match the registered preset')
        validate_manifest(manifest)
        for parts in manifest['enzymes'].values():
            for structure in parts.values():
                if not structure_valid(structure['atoms'], structure) or not coordination_valid(structure['atoms'], structure.get('coordination', [])):
                    raise ValueError('Prepared geometry check failed')
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as error:
        return {'status': 'invalid_inputs', 'reason': f'Prepared input check failed: {error}', 'manifest': preset['manifest']}
    return {
        'status': 'prepared_inputs_available', 'manifest': preset['manifest'],
        'sha256': hashlib.sha256(raw).hexdigest(),
        'provisional': any(s['review'].get('approved') is not True for parts in manifest['enzymes'].values() for s in parts.values()),
        'reason': 'Existing pair inputs pass schema and geometry checks; this does not validate chemistry or model accuracy.',
    }


def build_plan(request, root=PROJECT_ROOT, catalog=None):
    """Return a deterministic, exportable plan without loading a model or GPU."""
    allowed = {'candidate_id', 'candidate_name', 'smiles', 'target_id', 'target_sequence', 'panel_id'}
    if not isinstance(request, dict) or set(request) - allowed:
        raise ValueError('Expected a screening request with only supported input fields')
    catalog = load_catalog() if catalog is None else catalog
    candidate = _candidate(request)
    target_id = _text(request.get('target_id'), 'target_id', 60)
    panel_id = _text(request.get('panel_id', 'steroidogenic_p450'), 'panel_id', 60)
    if panel_id not in catalog['panels']:
        raise ValueError('Unknown panel_id')
    if target_id == 'custom':
        sequence = _sequence(request.get('target_sequence'))
        target = {'id': 'custom', 'label': 'Custom target', 'family': 'unassigned',
                  'reason': 'User-supplied sequence; no identity mapping or structure prediction has been run.',
                  'sequence': sequence, 'sequence_sha256': hashlib.sha256(sequence.encode()).hexdigest()}
    else:
        if target_id not in catalog['targets']:
            raise ValueError('Unknown target_id; select custom and provide a sequence for a new target')
        if request.get('target_sequence'):
            raise ValueError('Sequence variants must use custom; they cannot inherit a registered target protocol')
        target = {'id': target_id, **catalog['targets'][target_id]}
    prepared = _prepared_inputs(root, candidate['id'])
    from .structure_library import library
    references = library(root)
    pair_in_scope = target_id in PAIR
    rows = []
    for protein_id in dict.fromkeys([target_id, *catalog['panels'][panel_id]['targets']]):
        protein = target if protein_id == target_id else {'id': protein_id, **catalog['targets'][protein_id]}
        use_preset = pair_in_scope and protein_id in PAIR
        preparation = dict(prepared) if use_preset else {
            'status': 'preparation_required',
            'reason': 'No applicable UMA protocol for this candidate / intended-target comparison.',
        }
        rows.append({
            'protein': protein, 'role': 'intended_target' if protein_id == target_id else 'counter_screen',
            'selection_basis': 'user_selected_target' if protein_id == target_id else 'curated_panel_member',
            'preparation': preparation, 'assessment': 'not_run', 'binding_prediction': None,
            'structure': {key: value for key, value in references.get(protein_id, {'status': 'unmapped'}).items()
                          if key not in ('sequence', 'dbref', 'sequence_modifications')},
            'boltz': {'status': 'not_run', 'reason': 'A prepared, checked complex and a benchmarked scoring protocol are required.'},
            'next_action': ('Optionally run the existing provisional B2/B1 UMA preset; it does not assess the wider panel.'
                            if preparation['status'] == 'prepared_inputs_available' else
                            'Prepare ligand states, protein structure and pocket; review cofactors/charge/spin and benchmark the protocol.'),
            'missing_requirements': [] if preparation['status'] == 'prepared_inputs_available' else [
                'A 3D protein–drug pose for this exact molecule and target',
                'A complete local pocket with hydrogens, caps and relevant cofactors',
                'Explicit charge, spin multiplicity and preparation provenance',
                'Reviewed geometry and stereochemistry, or an explicit provisional declaration',
                'Matched reference calculations and experimental benchmarking for any selectivity claim',
            ],
        })
    ready = sum(row['preparation']['status'] == 'prepared_inputs_available' for row in rows)
    jobs = []
    if pair_in_scope and ready == 2:
        jobs.append({'preset': candidate['id'], 'proteins': list(PAIR), 'components': 8,
                     'descriptor': 'frozen_coordinate_ligand_water_exchange',
                     'sign_convention': 'Always B2 minus B1, including when the intended target is B1.',
                     'execution': 'Explicit user submission and server runtime preflight required.'})
    plan = {
        'schema_version': 1, 'kind': 'screening_plan', 'status': 'plan_only',
        'candidate': candidate, 'target': target,
        'panel': {'id': panel_id, 'label': catalog['panels'][panel_id]['label'],
                  'selection_method': 'curated_not_predicted', 'automatic_discovery': False,
                  'catalog_sha256': _hash(catalog), 'provenance': catalog.get('provenance', 'User-supplied catalog')},
        'targets': rows, 'available_jobs': jobs,
        'summary': {'proteins': len(rows), 'prepared_proteins': ready, 'needs_preparation': len(rows) - ready,
                    'new_predictions': 0, 'selectivity_conclusion': 'not_assessed'},
        'hardware': {'planning': 'CPU only; no model weights required',
                     'uma': 'CPU supported for current small prepared jobs; GPU useful for larger workloads',
                     'boltz': 'GPU recommended for practical structural screening; not launched by this planner'},
        'limitations': [
            'Panel membership is a reason to investigate, not a prediction of binding.',
            'This plan creates no new scores and does not reassign saved assay evidence to a new target or molecule.',
            'Targets outside this selected panel remain unassessed; a custom sequence does not trigger automatic target discovery.',
            'Input availability is separate from runtime readiness and scientific validation.',
            'UMA potential energies are not binding free energies and must not rank unrelated proteins by raw total energy.',
        ],
    }
    if target_id == 'custom':
        plan['limitations'].append('The selected panel has not been shown to be biologically relevant to this custom sequence; review its membership before running models.')
    plan['plan_id'] = _hash(plan)[:16]
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', default='CYP11B2')
    parser.add_argument('--candidate', default='r_fadrozole', choices=[*CANDIDATES, 'custom'])
    parser.add_argument('--name')
    parser.add_argument('--smiles')
    parser.add_argument('--sequence-file', type=Path)
    parser.add_argument('--panel', default='steroidogenic_p450')
    parser.add_argument('--catalog', type=Path, default=DEFAULT_CATALOG)
    parser.add_argument('--root', type=Path, default=PROJECT_ROOT)
    parser.add_argument('--out', type=Path, help='New JSON file; existing files will not be overwritten')
    args = parser.parse_args(argv)
    try:
        request = {'target_id': args.target, 'candidate_id': args.candidate, 'panel_id': args.panel}
        for key, value in (('candidate_name', args.name), ('smiles', args.smiles)):
            if value is not None:
                request[key] = value
        if args.sequence_file:
            request['target_sequence'] = args.sequence_file.read_text()
        result = build_plan(request, args.root, load_catalog(args.catalog))
        body = json.dumps(result, indent=2, allow_nan=False) + '\n'
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open('x') as handle:
                handle.write(body)
            print(args.out)
        else:
            print(body, end='')
        return 0
    except (OSError, ValueError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

"""Build traceable IsoForm starting inputs, without pretending to prepare UMA chemistry.

Fetches curated references, extracts experimental construct sequences, exports
Boltz structure-only inputs and copies applicable existing UMA preparations.
Nothing here launches inference, submits sequences, invents a pose, or assigns
protonation/metal states. Reference pocket drafts cannot pass the UMA contract.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shlex
import threading
import zipfile

from .benchmark_boltz import LIGANDS
from .screening import PROJECT_ROOT, PREPARED_PRESETS, build_plan, load_catalog
from .structure_library import library

BUILD_LOCK = threading.Lock()


def _json(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def build_inputs(request, root=PROJECT_ROOT, catalog=None, download=True):
    root = Path(root)
    plan = build_plan(request, root, catalog)
    if len(plan['targets']) > 8:
        raise ValueError('Automatic input building supports up to 8 targets at a time')
    # Reuse the screening validator: names alone never grant preset identity.
    candidate = plan['candidate']
    ligand = LIGANDS.get(candidate['label']) if candidate['id'] != 'custom' else None
    if candidate['id'] == 'custom' and candidate['smiles_validation']['status'] == 'syntax_checked':
        ligand = {'smiles': candidate['smiles_validation']['canonical_isomeric_smiles'], 'url': 'User input'}
    references = library(root, download, [row['protein']['id'] for row in plan['targets']])
    files, rows = {}, []
    for item in plan['targets']:
        target = item['protein']['id']
        reference = references[target]
        sequence = reference.get('sequence') or item['protein'].get('sequence')
        row = {'target_id': target, 'role': item['role'], 'reference': reference,
               'boltz_input': None, 'uma_ready': item['preparation']['status'] == 'prepared_inputs_available',
               'pose_status': 'not_predicted', 'binding_prediction': None}
        if sequence:
            files[f'sequences/{target}.fasta'] = f'>{target} | '+reference.get('sequence_source', 'user-supplied sequence')+'\n'+sequence+'\n'
        if sequence and ligand:
            # Heme is retained for the curated P450s; custom proteins get no
            # invented cofactor assignment. Deliberately no affinity properties:
            # Boltz documents unreliable affinity for cofactor-containing targets.
            entities = [{'protein': {'id': 'A', 'sequence': sequence, 'msa': 'empty'}}]
            if reference['status'] == 'available':
                entities.append({'ligand': {'id': 'H', 'ccd': 'HEM'}})
            entities.append({'ligand': {'id': 'L', **{key: ligand[key] for key in ('ccd', 'smiles') if key in ligand}}})
            path = f'boltz/{target}.yaml'
            files[path] = _json({'version': 1, 'sequences': entities})
            row['boltz_input'] = path
            row['next_step'] = 'Predict a candidate pose, then inspect identity, stereochemistry and metal geometry.'
        else:
            row['next_step'] = ('Validate the custom SMILES with RDKit in the server environment.' if not ligand else
                                'Supply a mapped protein sequence or restore the reference download.')
        if reference['status'] == 'available':
            from .sentinel_demo import structure_view
            view = structure_view(root / reference['path'], reference['chain'], reference['ligand_code'])
            files[f"references/{reference['pdb']}.pdb"] = (root / reference['path']).read_text()
            files[f'reference-pockets/{target}.json'] = _json({
                'kind': 'reference_pocket_draft', 'uma_runnable': False,
                'protein_id': target, 'reference_ligand': reference['ligand_label'],
                'requested_candidate': candidate['label'],
                'scope': 'Crystal-ligand context only, NOT a prepared pocket for the requested candidate.',
                'source': reference, 'atoms_for_display': view['atoms'],
                'missing': ['Candidate-specific pose', 'Hydrogens, capped boundaries and reviewed protonation',
                            'Explicit total charge, heme / spin treatment', 'Chemistry and geometry review'],
            })
        rows.append(row)
    if plan['available_jobs']:
        from .uma_batch import export_exchange
        files['uma/prepared-pockets.json'] = _json(export_exchange(root / PREPARED_PRESETS[candidate['id']]['manifest']))
    warnings = [
        'No model has been run. No binding or selectivity prediction has been made.',
        'Reference structures contain their deposited ligands, not necessarily your candidate.',
        'Boltz files use the deposited experimental construct sequences, including tags / modifications; inspect DBREF and SEQADV provenance.',
        'Boltz inputs default to single-sequence mode (msa: empty), which reduces accuracy. No sequences are sent to external MSA services by this builder.',
        'Boltz affinity is intentionally disabled: its documentation warns of unreliable affinity with cofactor-containing targets.',
        'Boltz poses still need stereochemistry / heme geometry review and explicit chemical preparation before UMA.',
        'Reference pocket drafts contain incomplete heavy-atom context and are NOT executable UMA inputs.',
        'UMA energies are not affinities; do not rank unrelated proteins by raw total energies.',
    ]
    if candidate['id'] == 'custom':
        warnings.append('SMILES syntax checks do not fully validate stereochemistry, protonation or candidate identity.')
    manifest = {'schema_version': 1, 'kind': 'isoform_input_bundle', 'status': 'inputs_built_not_predictions',
                'candidate': candidate, 'target': plan['target'], 'panel': plan['panel'], 'targets': rows,
                'available_jobs': plan['available_jobs'], 'warnings': warnings,
                'summary': {'proteins': len(rows), 'structures': sum(r['reference']['status'] == 'available' for r in rows),
                            'boltz_inputs': sum(r['boltz_input'] is not None for r in rows),
                            'uma_ready': sum(r['uma_ready'] for r in rows), 'new_predictions': 0},
                'ligand_source': ligand, 'boltz_documentation': 'https://github.com/jwohlwend/boltz/blob/main/docs/prediction.md'}
    files['README.md'] = ('# IsoForm input bundle\n\n' + '\n'.join('- ' + warning for warning in warnings) +
                         '\n\nThe boltz/ directory contains JSON-compatible YAML files. After reviewing the construct sequences, '
                         'use `boltz predict boltz --out_dir predictions --accelerator gpu --devices 1`. '
                         'This command can download model weights and use substantial GPU resources. It is never launched by the builder. '
                         'To use an external MSA service, remove `msa: empty` and explicitly opt in with `--use_msa_server`. '
                         'For private sequences, prepare local MSAs instead.\n\n'
                         'The references/ and reference-pockets/ folders are experimental context only. '
                         'If present, uma/prepared-pockets.json copies the existing provisional R/S pair preparation unchanged. '
                         'Upload that file in IsoForm to run it with explicit provisional acknowledgement.\n')
    manifest['files'] = {path: hashlib.sha256(body.encode()).hexdigest() for path, body in files.items()}
    bundle_id = hashlib.sha256(_json(manifest).encode()).hexdigest()[:24]
    destination = root / 'runs/isoform-inputs' / bundle_id
    manifest.update(bundle_id=bundle_id, directory=str(destination.relative_to(root)),
                    download_url=f'/api/input-bundles/{bundle_id}.zip')
    manifest['boltz_command'] = ('boltz predict ' + shlex.quote(str(destination / 'boltz')) +
                                 ' --out_dir ' + shlex.quote(str(root / 'runs/isoform-predictions' / bundle_id)) +
                                 ' --accelerator gpu --devices 1') if manifest['summary']['boltz_inputs'] else None
    files['manifest.json'] = _json(manifest)
    # Deterministic cache; never overwrite edited artifacts or accept user paths.
    with BUILD_LOCK:
        destination.mkdir(parents=True, exist_ok=True)
        for name, body in files.items():
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                if path.read_text() != body:
                    raise ValueError(f'Existing input bundle was modified: {name}; keep it and use a new workspace')
            else:
                with path.open('x') as handle:
                    handle.write(body)
    return manifest


def bundle_zip(bundle_id, root=PROJECT_ROOT):
    if not re.fullmatch(r'[a-f0-9]{24}', bundle_id):
        raise ValueError('Invalid bundle identifier')
    base = Path(root) / 'runs/isoform-inputs' / bundle_id
    manifest = json.loads((base / 'manifest.json').read_text())
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in [*manifest['files'], 'manifest.json']:
            path = base / name
            if not path.resolve().is_relative_to(base.resolve()):
                raise ValueError('Invalid artifact path')
            raw = path.read_bytes()
            if name != 'manifest.json' and hashlib.sha256(raw).hexdigest() != manifest['files'][name]:
                raise ValueError('Input artifact changed since preparation')
            archive.writestr(name, raw)
    return buffer.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', default='r_fadrozole')
    parser.add_argument('--target', default='CYP11B2')
    parser.add_argument('--panel', default='steroidogenic_p450')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--root', type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)
    result = build_inputs({'candidate_id': args.candidate, 'target_id': args.target, 'panel_id': args.panel},
                          args.root, load_catalog(), not args.offline)
    print(_json({key: result[key] for key in ('directory', 'summary', 'boltz_command')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

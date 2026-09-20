"""Prepare and run traceable, exploratory Boltz-2 CYP11B comparisons."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


AMINO_ACIDS = dict(zip(
    'ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL'.split(),
    'ARNDCQEGHILKMFPSTWYV',
))
TARGETS = {'CYP11B1': ('6M7X', 'P15538'), 'CYP11B2': ('4FDH', 'P19099')}
LIGANDS = {
    'S-fadrozole': {'ccd': 'JD7', 'url': 'https://www.rcsb.org/ligand/JD7'},
    'R-fadrozole': {'ccd': '0T3', 'url': 'https://www.rcsb.org/ligand/0T3'},
    'Osilodrostat (LCI699)': {'ccd': 'YSY', 'url': 'https://www.rcsb.org/ligand/YSY'},
    'Baxdrostat': {
        'smiles': 'CCC(=O)N[C@@H]1CCCC2=C1C=NC=C2C3=CC4=C(C=C3)N(C(=O)CC4)C',
        'url': 'https://pubchem.ncbi.nlm.nih.gov/compound/71535962',
    },
}
DOCS = 'https://github.com/jwohlwend/boltz/blob/main/docs/prediction.md'


def _now():
    return datetime.now(timezone.utc).isoformat()


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def _domain_sequence(pdb_path, accession, chain='A', start=34, end=503):
    """Map continuous SEQRES using explicit DBREF and expression-tag metadata."""
    lines = Path(pdb_path).read_text().splitlines()
    rows = [line for line in lines if line.startswith('SEQRES') and line[11:12] == chain]
    if not rows:
        raise ValueError(f'No SEQRES chain {chain}: {pdb_path}')
    residues = [residue for row in rows for residue in row[19:70].split()]
    if {int(row[13:17]) for row in rows} != {len(residues)}:
        raise ValueError(f'Incomplete or inconsistent SEQRES: {pdb_path}')
    refs = [line for line in lines if line.startswith('DBREF ') and line[12:13] == chain]
    if len(refs) != 1 or refs[0][33:41].strip() != accession:
        raise ValueError(f'Expected one DBREF for {accession}: {pdb_path}')
    ref = refs[0]
    pdb_start, pdb_end = int(ref[14:18]), int(ref[20:24])
    db_start, db_end = int(ref[55:60]), int(ref[62:67])
    if pdb_end - pdb_start != db_end - db_start or not db_start <= start <= end <= db_end:
        raise ValueError(f'Unsupported DBREF residue mapping: {pdb_path}')
    if any(ref[index:index + 1].strip() for index in (18, 24, 60, 67)):
        raise ValueError(f'Insertion codes require explicit mapping: {pdb_path}')
    tags = {}
    for line in lines:
        if not line.startswith('SEQADV') or line[16:17] != chain:
            continue
        if 'EXPRESSION TAG' not in line[49:]:
            raise ValueError(f'Unexpected sequence modification: {line.strip()}')
        if line[22:23].strip():
            raise ValueError(f'Insertion code in expression tag: {line.strip()}')
        tags[int(line[18:22])] = line[12:15]
    positions = set(range(pdb_start, pdb_end + 1)) | set(tags)
    first, last = min(positions), max(positions)
    if len(positions) != len(residues) or positions != set(range(first, last + 1)):
        raise ValueError(f'SEQRES cannot be mapped from DBREF and SEQADV: {pdb_path}')
    for number, residue in tags.items():
        if residues[number - first] != residue:
            raise ValueError(f'SEQADV/SEQRES mismatch at {number}: {pdb_path}')
    offset = pdb_start - db_start
    selected = residues[start + offset - first:end + offset - first + 1]
    try:
        sequence = ''.join(AMINO_ACIDS[residue] for residue in selected)
    except KeyError as error:
        raise ValueError(f'Noncanonical SEQRES residue: {error.args[0]}') from error
    return sequence, {
        'path': str(Path(pdb_path).resolve()), 'sha256': _sha(pdb_path),
        'chain': chain, 'source': 'PDB SEQRES mapped by DBREF and SEQADV',
        'uniprot_accession': accession, 'uniprot_start': start, 'uniprot_end': end,
        'source_construct_length': len(residues), 'sequence_length': len(sequence),
        'sequence_sha256': hashlib.sha256(sequence.encode()).hexdigest(),
        'dbref': ref.strip(), 'expression_tags_removed': sorted(tags),
    }


def prepare_boltz(experiment_path, out_dir, msa_mode='server', raw_dir=None):
    """Write JSON-compatible YAML and a preparation manifest; never run inference."""
    if msa_mode not in ('server', 'empty'):
        raise ValueError('msa_mode must be server or empty')
    experiment_path = Path(experiment_path).resolve()
    experiment = json.loads(experiment_path.read_text())
    raw_dir = Path(raw_dir).resolve() if raw_dir else experiment_path.parent.parent / 'data/raw'
    out_dir = Path(out_dir).resolve()
    prepared = []
    seen = set()
    for system in experiment['systems']:
        identifier, ligand_name, isoform = (system[key] for key in ('system_id', 'ligand', 'isoform'))
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', identifier) or identifier in seen:
            raise ValueError(f'Unsafe or duplicate system_id: {identifier!r}')
        seen.add(identifier)
        if isoform not in TARGETS or ligand_name not in LIGANDS:
            raise ValueError(f'Unsupported benchmark system: {identifier}')
        pdb_id, accession = TARGETS[isoform]
        # Boltz co-folds from a sequence; this source is deliberately distinct
        # from a per-case crystal/scaffold PDB when that structure is a mutant.
        sequence_pdb = system.get('boltz_sequence_pdb', pdb_id)
        if sequence_pdb != pdb_id:
            raise ValueError(f'Unexpected Boltz sequence PDB for {isoform}: {sequence_pdb}')
        sequence, source = _domain_sequence(raw_dir / f'{pdb_id}.pdb', accession)
        protein = {'id': 'A', 'sequence': sequence}
        if msa_mode == 'empty':
            protein['msa'] = 'empty'
        ligand_spec = LIGANDS[ligand_name]
        ligand_entity = {'id': 'L', **{key: ligand_spec[key] for key in ('ccd', 'smiles') if key in ligand_spec}}
        document = {
            'version': 1,
            'sequences': [{'protein': protein}, {'ligand': {'id': 'H', 'ccd': 'HEM'}},
                          {'ligand': ligand_entity}],
            'properties': [{'affinity': {'binder': 'L'}}],
        }
        case = {'system_id': identifier, 'ligand': ligand_name, 'isoform': isoform,
                'starting_pdb': system.get('starting_pdb'), 'pose_kind': system.get('pose_kind'),
                'boltz_sequence_pdb': pdb_id,
                'input_path': str(out_dir / 'inputs' / f'{identifier}.yaml'),
                'sequence_source': source,
                'ligand_source': {key: ligand_spec[key] for key in ('ccd', 'smiles', 'url') if key in ligand_spec},
                'status': 'prepared_not_run'}
        prepared.append((document, case))
    if not prepared:
        raise ValueError('Experiment contains no systems')
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / 'inputs').mkdir()
    for document, case in prepared:
        _write(case['input_path'], document)
        case['input_sha256'] = _sha(case['input_path'])
    warnings = [
        'Exploratory inputs pending chemistry review; no metal oxidation/spin state is represented.',
        'Boltz-2 affinity for a cofactor-containing target is unvalidated; heme is retained.',
        'Source crystal constructs differ. Both sequences use mapped UniProt residues 34-503.',
        'Known crystal complexes may overlap training data; this is not a held-out accuracy test.',
        'One seed is a pilot; use at least three matched seeds to assess sampling variation.',
    ]
    if msa_mode == 'empty':
        warnings.append('Single-sequence mode reduces accuracy and is a separate benchmark protocol.')
    recipe = {'model': 'boltz2', 'msa_mode': msa_mode,
              'protein_domain': {'uniprot_start': 34, 'uniprot_end': 503},
              'chains': {'protein': 'A', 'heme': 'H', 'affinity_binder': 'L'},
              'heme_ccd': 'HEM', 'templates': False, 'coordination_constraints': False,
              'use_potentials': False, 'affinity_mw_correction': False}
    manifest = {'schema_version': 1, 'model': 'boltz2', 'status': 'prepared_not_run',
                'created_at': _now(), 'experiment': {'path': str(experiment_path),
                                                   'sha256': _sha(experiment_path)},
                'recipe': recipe, 'cases': [case for _, case in prepared], 'warnings': warnings,
                'documentation': DOCS,
                'pilot_command': ['python3', '-m', 'cyp_pipeline.benchmark_boltz', 'run',
                                  str(out_dir / 'manifest.json'), str(out_dir / 'pilot'),
                                  '--seeds', '42'],
                'replicate_seeds': [42, 43, 44]}
    _write(out_dir / 'manifest.json', manifest)
    return manifest


def _installed_version(executable):
    python = Path(executable).parent / 'python'
    if not python.is_file():
        return None
    result = subprocess.run(
        [str(python), '-c', 'import importlib.metadata; print(importlib.metadata.version("boltz"))'],
        text=True, capture_output=True, check=False, timeout=30,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def run_boltz(manifest_path, out_dir, *, seeds=(42,), boltz_executable='boltz',
              cache_dir=None, timeout_seconds=None, sampling_steps=200, diffusion_samples=1,
              recycling_steps=3, sampling_steps_affinity=200, diffusion_samples_affinity=5,
              no_kernels=False):
    """Run each seed in a fresh output directory and retain logs and artifact hashes."""
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('model') != 'boltz2' or manifest.get('schema_version') != 1:
        raise ValueError('Expected a Boltz-2 preparation manifest')
    if not seeds or len(set(seeds)) != len(seeds) or any(type(seed) is not int or seed < 0 for seed in seeds):
        raise ValueError('Provide distinct nonnegative integer seeds')
    settings = {'recycling_steps': recycling_steps, 'sampling_steps': sampling_steps,
                'diffusion_samples': diffusion_samples, 'sampling_steps_affinity': sampling_steps_affinity,
                'diffusion_samples_affinity': diffusion_samples_affinity, 'no_kernels': no_kernels}
    if any(type(value) is not int or value < 1 for key, value in settings.items() if key != 'no_kernels'):
        raise ValueError('Sampling and recycling counts must be positive integers')
    if timeout_seconds is not None and timeout_seconds <= 0:
        raise ValueError('timeout_seconds must be positive')
    for case in manifest['cases']:
        if _sha(case['input_path']) != case['input_sha256']:
            raise ValueError(f'Prepared input changed: {case["input_path"]}')
    executable = shutil.which(str(boltz_executable))
    if executable is None:
        raise FileNotFoundError(f'Boltz executable unavailable: {boltz_executable}')
    executable = str(Path(executable).resolve())
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=False)
    inputs = out_dir / 'inputs'
    inputs.mkdir()
    for case in manifest['cases']:
        shutil.copy2(case['input_path'], inputs / Path(case['input_path']).name)
    cache_dir = Path(cache_dir).resolve() if cache_dir else out_dir / 'cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    record = {'schema_version': 1, 'model': 'boltz2', 'status': 'running',
              'model_version': _installed_version(executable), 'created_at': _now(),
              'source_manifest': {'path': str(manifest_path), 'sha256': _sha(manifest_path)},
              'recipe': manifest['recipe'], 'settings': settings, 'seeds': list(seeds),
              'cases': manifest['cases'], 'runs': [], 'checkpoints': [],
              'warnings': list(manifest.get('warnings', []))}
    _write(out_dir / 'run_manifest.json', record)
    for seed in seeds:
        seed_dir = out_dir / f'seed-{seed}'
        seed_dir.mkdir()
        log_path = seed_dir / 'boltz.log'
        argv = [executable, 'predict', str(inputs), '--out_dir', str(seed_dir), '--model', 'boltz2',
                '--cache', str(cache_dir), '--seed', str(seed), '--accelerator', 'gpu',
                '--devices', '1', '--num_workers', '0', '--preprocessing-threads', '1',
                '--max_parallel_samples', '1']
        for key, value in settings.items():
            if key != 'no_kernels':
                argv.extend([f'--{key}', str(value)])
        if no_kernels:
            argv.append('--no_kernels')
        if manifest['recipe']['msa_mode'] == 'server':
            argv.append('--use_msa_server')
        run = {'seed': seed, 'status': 'running', 'command': argv, 'started_at': _now(),
               'out_dir': str(seed_dir), 'log_path': str(log_path), 'predictions': []}
        record['runs'].append(run)
        _write(out_dir / 'run_manifest.json', record)
        env = {**os.environ, 'BOLTZ_CACHE': str(cache_dir),
               'XDG_CACHE_HOME': str(cache_dir / 'xdg'), 'MPLCONFIGDIR': str(cache_dir / 'matplotlib')}
        with log_path.open('w') as log:
            try:
                result = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, check=False, shell=False,
                                        timeout=timeout_seconds, env=env)
                run['returncode'] = result.returncode
                run['status'] = 'completed' if result.returncode == 0 else 'failed'
            except subprocess.TimeoutExpired:
                run.update(status='timed_out', returncode=None)
            except OSError as error:
                run.update(status='failed', returncode=None, error=str(error))
        run['finished_at'] = _now()
        for case in manifest['cases']:
            identifier = case['system_id']
            affinity = list(seed_dir.rglob(f'affinity_{identifier}.json'))
            confidence = sorted(seed_dir.rglob(f'confidence_{identifier}_model_*.json'))
            structures = sorted(seed_dir.rglob(f'{identifier}_model_*.cif'))
            prediction = {'system_id': identifier,
                          'affinity_path': str(affinity[0]) if len(affinity) == 1 else None,
                          'confidence_paths': [str(path) for path in confidence],
                          'structure_paths': [str(path) for path in structures]}
            if prediction['affinity_path']:
                prediction['affinity_sha256'] = _sha(prediction['affinity_path'])
            run['predictions'].append(prediction)
        if run['status'] == 'completed' and any(not p['affinity_path'] for p in run['predictions']):
            run['status'] = 'incomplete_outputs'
        run['msa_files'] = [{'path': str(path), 'sha256': _sha(path)}
                            for path in sorted(seed_dir.rglob('*.a3m'))]
        _write(out_dir / 'run_manifest.json', record)
        if run['status'] in ('failed', 'timed_out'):
            break
    record['checkpoints'] = [{'path': str(path), 'sha256': _sha(path)}
                             for path in sorted(cache_dir.glob('boltz2_*.ckpt'))]
    ccd_codes = sorted({'HEM', *(case['ligand_source']['ccd'] for case in manifest['cases']
                                 if 'ccd' in case['ligand_source'])})
    record['ccd_files'] = [{'path': str(path), 'sha256': _sha(path)}
                           for ccd in ccd_codes
                           for path in sorted((cache_dir / 'mols').glob(f'{ccd}.*'))]
    record['protocol_id'] = _digest({'recipe': record['recipe'], 'settings': settings,
                                    'model_version': record['model_version'],
                                    'checkpoints': [item['sha256'] for item in record['checkpoints']],
                                    'ccd_files': {Path(item['path']).name: item['sha256']
                                                  for item in record['ccd_files']},
                                    'inputs': {case['system_id']: case['input_sha256']
                                               for case in manifest['cases']},
                                    'sequences': {case['isoform']: case['sequence_source']['sequence_sha256']
                                                  for case in manifest['cases']}})
    completed = sum(run['status'] == 'completed' for run in record['runs'])
    record['status'] = 'completed' if completed == len(seeds) else 'partial' if completed else 'failed'
    record['finished_at'] = _now()
    _write(out_dir / 'run_manifest.json', record)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('experiment')
    prepare.add_argument('out')
    prepare.add_argument('--msa-mode', choices=('server', 'empty'), default='server')
    prepare.add_argument('--raw-dir')
    run = commands.add_parser('run')
    run.add_argument('manifest')
    run.add_argument('out')
    run.add_argument('--boltz-executable', default='boltz')
    run.add_argument('--cache')
    run.add_argument('--seeds', nargs='+', type=int, default=[42])
    run.add_argument('--timeout-seconds', type=float)
    for option, default in [('recycling-steps', 3), ('sampling-steps', 200), ('diffusion-samples', 1),
                            ('sampling-steps-affinity', 200), ('diffusion-samples-affinity', 5)]:
        run.add_argument(f'--{option}', type=int, default=default)
    run.add_argument('--no-kernels', action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        record = prepare_boltz(args.experiment, args.out, args.msa_mode, args.raw_dir)
    else:
        record = run_boltz(args.manifest, args.out, seeds=args.seeds,
                           boltz_executable=args.boltz_executable, cache_dir=args.cache,
                           timeout_seconds=args.timeout_seconds, recycling_steps=args.recycling_steps,
                           sampling_steps=args.sampling_steps, diffusion_samples=args.diffusion_samples,
                           sampling_steps_affinity=args.sampling_steps_affinity,
                           diffusion_samples_affinity=args.diffusion_samples_affinity, no_kernels=args.no_kernels)
    print(json.dumps({'status': record['status'], 'cases': len(record['cases']), 'out': args.out}))
    return 1 if record['status'] in ('failed', 'partial') else 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Run the paired dataset using verified cached MSAs and retain native outputs.

Usage: python3 scripts/run_baxdrostat_af3.py
Requires the isolated AF3 installation and official weights in .cache/.
"""

import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / 'data/validation/baxdrostat-af3-v1'
AF3 = ROOT / '.cache/alphafold3'
RUN = ROOT / 'runs/baxdrostat-af3-v1'
MSA_ROOT = ROOT / 'runs/benchmark-extended-boltz-pilot-v1/seed-42/boltz_results_inputs/msa'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    manifest = json.loads((DATASET / 'manifest.json').read_text())
    prepared = []
    for case in manifest['cases']:
        path = DATASET / case['input_path']
        if sha(path) != case['input_sha256']:
            raise ValueError(f'Input modified: {path}')
        document = json.loads(path.read_text())
        protein = document['sequences'][0]['protein']
        msa_path = MSA_ROOT / f'{case["system_id"]}_0.csv'
        with msa_path.open() as handle:
            rows = list(csv.DictReader(handle))
        sequences = list(dict.fromkeys(row['sequence'] for row in rows))
        if not sequences or sequences[0] != protein['sequence']:
            raise ValueError(f'MSA query differs from input: {msa_path}')
        for sequence in sequences:
            aligned = ''.join(c for c in sequence if not c.islower())
            if len(aligned) != len(protein['sequence']):
                raise ValueError(f'MSA alignment length mismatch: {msa_path}')
            if set(sequence) - set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-'):
                raise ValueError(f'Invalid A3M characters: {msa_path}')
        protein['unpairedMsa'] = ''.join(f'>seq_{i}\n{s}\n' for i, s in enumerate(sequences))
        protein['pairedMsa'] = ''
        prepared.append((document, {
            'system_id': case['system_id'], 'msa_source': str(msa_path.relative_to(ROOT)),
            'msa_source_sha256': sha(msa_path), 'msa_rows': len(sequences),
        }))
    RUN.mkdir(exist_ok=False)
    (RUN / 'inputs').mkdir()
    cases = []
    for document, case in prepared:
        path = RUN / 'inputs' / f'{case["system_id"]}.json'
        write(path, document)
        case.update(input_path=str(path.relative_to(ROOT)), input_sha256=sha(path))
        cases.append(case)
    command = [str(AF3 / '.venv/bin/python'), str(AF3 / 'run_alphafold.py'),
               f'--input_dir={RUN / "inputs"}', f'--model_dir={ROOT / ".cache/af3-models"}',
               f'--output_dir={RUN / "outputs"}', '--run_data_pipeline=false',
               '--resolve_msa_overlaps=false', '--num_diffusion_samples=5']
    env_settings = {'XLA_FLAGS': '--xla_gpu_enable_triton_gemm=false',
                    'XLA_PYTHON_CLIENT_PREALLOCATE': 'true', 'XLA_CLIENT_MEM_FRACTION': '0.90'}
    record = {
        'model': 'AlphaFold 3', 'status': 'running',
        'started_at': datetime.now(timezone.utc).isoformat(),
        'af3_revision': subprocess.check_output(['git', '-C', str(AF3), 'rev-parse', 'HEAD'], text=True).strip(),
        'model_sha256': sha(ROOT / '.cache/af3-models/af3.bin'),
        'command': command, 'environment': env_settings, 'cases': cases,
        'protocol': 'Cached Boltz/MMseqs2 MSAs, exact query match, duplicate rows removed; templates disabled; 3 seeds x 5 diffusion samples per enzyme.',
    }
    write(RUN / 'run_manifest.json', record)
    with (RUN / 'inference.log').open('w') as log:
        result = subprocess.run(command, env={**os.environ, **env_settings}, stdout=log, stderr=subprocess.STDOUT)
    record.update(returncode=result.returncode, finished_at=datetime.now(timezone.utc).isoformat())
    record['status'] = 'failed'
    if result.returncode == 0:
        incomplete = []
        for case in cases:
            name = case['system_id']
            # This pinned AF3 revision preserves case and hyphens in names.
            directory = RUN / 'outputs' / name
            required = [directory / f'{name}_{suffix}' for suffix in
                        ('model.cif', 'summary_confidences.json', 'confidences.json', 'ranking_scores.csv', 'data.json')]
            for seed in (42, 43, 44):
                for sample in range(5):
                    tag = f'seed-{seed}_sample-{sample}'
                    required.extend(directory / tag / f'{name}_{tag}_{suffix}' for suffix in
                                    ('model.cif', 'summary_confidences.json', 'confidences.json'))
            incomplete.extend(str(p) for p in required if not p.is_file() or p.stat().st_size == 0)
        record['status'] = 'incomplete_outputs' if incomplete else 'completed'
        record['missing_outputs'] = incomplete
    record['artifacts'] = {str(p.relative_to(RUN)): sha(p)
                           for p in sorted((RUN / 'outputs').rglob('*')) if p.is_file()}
    write(RUN / 'run_manifest.json', record)
    if record['status'] != 'completed':
        raise SystemExit(f'AF3 failed; inspect {RUN / "inference.log"}')
    artifact_dir = DATASET / 'predictions'
    shutil.copytree(RUN / 'outputs', artifact_dir)
    shutil.copytree(RUN / 'inputs', DATASET / 'inference_inputs')
    shutil.copy2(RUN / 'run_manifest.json', DATASET / 'run_manifest.json')
    shutil.copy2(RUN / 'inference.log', DATASET / 'inference.log')
    manifest['status'] = 'predicted_pending_geometry_review'
    manifest['run_manifest'] = 'run_manifest.json'
    for case in manifest['cases']:
        name = case['system_id']
        model = next(artifact_dir.glob('*/' + name + '_model.cif'))
        case.update(status='predicted_pending_geometry_review',
                    structure_path=str(model.relative_to(DATASET)), structure_sha256=sha(model),
                    inference_input_path=f'inference_inputs/{name}.json')
    manifest['limitations'][0] = 'AF3 predictions generated; chemistry and geometry review are required before energy calculations.'
    write(DATASET / 'manifest.json', manifest)
    print(f'Predictions stored in {artifact_dir}')


if __name__ == '__main__':
    main()

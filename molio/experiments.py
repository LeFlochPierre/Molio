"""Bounded local Boltz comparison jobs; measurements never become predictions."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import fcntl
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import threading
import time
import uuid

from .repeats import summarize

ROOT = Path(__file__).resolve().parent
ACTIVE = {'queued', 'preparing', 'running', 'validating'}
SETTINGS = {'seed': 42, 'recycling_steps': 3, 'sampling_steps': 200,
            'diffusion_samples': 1, 'sampling_steps_affinity': 200,
            'diffusion_samples_affinity': 5}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def target_sequence(dataset=None):
    if dataset and dataset.get('prediction_target'):
        target = dataset['prediction_target']
        sequence = target['sequence']
        if not 40 <= len(sequence) <= 600 or any(a not in 'ACDEFGHIKLMNPQRSTVWY' for a in sequence):
            raise ValueError('Unsupported imported protein construct')
        return sequence, target['provenance']
    if dataset and dataset.get('workspace_id', 'brd4') != 'brd4':
        raise ValueError('Choose a supported prediction region (40–600 residues) in the workspace first')
    from .sequence import domain_sequence
    return domain_sequence(ROOT / 'data/structures/3SVG.pdb', 'O60885', start=44, end=168)


def catalog(dataset, proposals):
    from rdkit import Chem
    from rdkit.Chem.EnumerateStereoisomers import EnumerateStereoisomers, StereoEnumerationOptions
    rows = []
    for c in [*dataset['compounds'], *proposals]:
        smiles = c.get('canonical_smiles', c.get('smiles'))
        mol = Chem.MolFromSmiles(smiles)
        options = sorted({Chem.MolToSmiles(m) for m in EnumerateStereoisomers(mol,
            options=StereoEnumerationOptions(onlyUnassigned=True, maxIsomers=17))})
        if len(options) > 16:
            options = []  # Do not silently take a random subset of a large stereo space.
        rows.append({'id': c['id'], 'name': c.get('name') or c['id'], 'smiles': smiles,
            'observation': c.get('observation'), 'stereo_options': options,
            'supporting_records': c.get('supporting_records', []), 'input_origin':c.get('origin'),
            'stereo_note': 'Choose a defined stereoisomer. The assay record does not resolve these alternatives.'
                if len(options) > 1 else 'Recorded stereochemistry retained.',
            'parent_id': c.get('parent_id'), 'hypothesis': c.get('hypothesis'),
            'design_origin': c.get('design_origin'),
            'kind': 'measured' if c.get('observation') else c.get('kind', 'proposal')})
    return rows


def probe(executable, cache):
    path = shutil.which(str(executable)) if executable else None
    result = {'ready': False, 'model': 'Boltz-2', 'version': None, 'gpu': None,
              'weights_cached': all((cache / n).is_file() for n in ('boltz2_conf.ckpt', 'boltz2_aff.ckpt')),
              'issues': [], 'free_disk_gb': round(shutil.disk_usage(cache.parent).free / 1e9, 1)}
    if not path:
        result['issues'].append('Boltz is not configured. Start the server with --boltz-executable PATH.')
        return result
    python = Path(path).parent / 'python'
    try:
        check = subprocess.run([str(python), '-c',
            'import json,torch,importlib.metadata as m; print(json.dumps(dict(version=m.version("boltz"),gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)))'],
            capture_output=True, text=True, timeout=45, check=False)
        data = json.loads(check.stdout.strip().splitlines()[-1]) if check.returncode == 0 else {}
        result.update({k: data.get(k) for k in ('version', 'gpu')})
        if result['version'] != '2.2.1':
            result['issues'].append('This adapter requires Boltz 2.2.1 in its dedicated environment.')
        if not result['gpu']:
            result['issues'].append('The Boltz Python environment cannot access a CUDA GPU.')
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        result['issues'].append('Could not inspect the Boltz Python environment.')
    if result['free_disk_gb'] < 15:
        result['issues'].append('At least 15 GB of free disk is required for setup and results.')
    result['ready'] = not result['issues']
    return result


def read_result(directory, identifier, atom_count, smiles=None, pose_check_mode="brd4"):
    """Reject missing/nonfinite output; basic geometry checks are not pose validation."""
    def one(pattern):
        paths = list(directory.rglob(pattern))
        if len(paths) != 1:
            raise ValueError(f'Expected one {pattern}; found {len(paths)}')
        return paths[0]
    def native(path):
        value = json.loads(path.read_text())
        def check(v):
            if isinstance(v, float) and not math.isfinite(v):
                raise ValueError('Nonfinite model output')
            if isinstance(v, dict):
                for child in v.values(): check(child)
            if isinstance(v, list):
                for child in v: check(child)
        check(value)
        return value
    affinity_path = one(f'affinity_{identifier}.json')
    confidence_path = one(f'confidence_{identifier}_model_0.json')
    pose = one(f'{identifier}_model_0.pdb')
    affinity, confidence = native(affinity_path), native(confidence_path)
    for key, data in [('affinity_pred_value', affinity), ('affinity_probability_binary', affinity), ('confidence_score', confidence)]:
        if type(data.get(key)) not in (float, int) or not math.isfinite(data[key]):
            raise ValueError(f'Missing or invalid {key}')
    if not 0 <= affinity['affinity_probability_binary'] <= 1 or not 0 <= confidence['confidence_score'] <= 1:
        raise ValueError('Model probability/confidence outside [0, 1]')
    atoms = [line for line in pose.read_text().splitlines() if line.startswith(('ATOM  ', 'HETATM'))]
    ligand = [line for line in atoms if line[21:22] == 'L' and line[76:78].strip() not in ('H', 'D')]
    if len(ligand) != atom_count or not any(line[21:22] == 'A' for line in atoms):
        raise ValueError('Predicted chains or ligand heavy-atom count do not match input')
    for line in atoms:
        if not all(math.isfinite(float(line[a:b])) for a, b in ((30,38),(38,46),(46,54))):
            raise ValueError('Nonfinite coordinates')
    from .pose_checks import diagnose
    from .pose_checks import diagnose_generic
    checker = diagnose if pose_check_mode == 'brd4' else diagnose_generic
    checks = checker(pose, smiles) if smiles else None
    return {'pose_checks': checks, 'affinity': affinity, 'confidence': confidence, 'pose': str(pose.relative_to(directory)),
            'artifacts': [{'file': str(p.relative_to(directory)), 'sha256': sha(p)} for p in (pose, affinity_path, confidence_path)],
            'geometry_check': 'Finite coordinates, chains A/L and ligand heavy-atom count checked. Contacts, clashes and chemical identity of output bonds are not validated.'}


class Experiments:
    def __init__(self, directory, proposal_store, executable=None, cache=None):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self._closed = False
        self._lease = (self.directory / '.worker.lock').open('a')
        try:
            fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._lease.close()
            raise RuntimeError('Another prediction worker already owns this project directory.') from None
        self.cache = Path(cache or self.directory.parent / 'boltz-cache').resolve()
        self.cache.mkdir(parents=True, exist_ok=True)
        self.proposals = proposal_store
        self.executable = shutil.which(str(executable)) if executable else None
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.processes, self.cancelled = {}, set()
        self.health = probe(executable, self.cache)
        for job in self.list():
            if job['status'] in ACTIVE:
                job.update(status='interrupted', finished_at=now())
                for case in job['cases']:
                    if case['status'] in ACTIVE:
                        case['status'] = 'interrupted'
                self.save(job)

    def save(self, job):
        job['comparison'] = summarize(job)
        path = self.directory / job['id'] / 'job.json'
        path.parent.mkdir(exist_ok=True)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(job, indent=2, allow_nan=False))
        temp.replace(path)

    def enrich(self, job):
        for case in job['cases']:
            sidecar = self.directory / job['id'] / case['id'] / 'pose_checks.json'
            if case.get('prediction') and sidecar.is_file():
                checks = json.loads(sidecar.read_text())
                expected = next((a['sha256'] for a in case['prediction']['artifacts'] if a['file']==case['prediction']['pose']), None)
                if checks.get('pose_sha256') == expected:
                    case['prediction']['pose_checks'] = checks
        job['comparison'] = summarize(job)
        return job

    def get(self, identifier):
        try:
            if str(uuid.UUID(identifier)) != identifier: raise ValueError()
        except (ValueError, AttributeError, TypeError):
            raise ValueError('Unknown experiment') from None
        path = self.directory / identifier / 'job.json'
        if not path.is_file(): raise ValueError('Unknown experiment')
        with self.lock:
            return self.enrich(json.loads(path.read_text()))

    def list(self):
        with self.lock:
            return sorted([self.enrich(json.loads(p.read_text())) for p in self.directory.glob('*/job.json')], key=lambda j:j['created_at'], reverse=True)

    def submit(self, payload, dataset, proposal_store=None):
        if not isinstance(payload, dict) or set(payload) - {'candidates', 'msa_mode', 'repeats'} or 'candidates' not in payload or payload.get('msa_mode') != 'empty':
            raise ValueError('Expected candidates and msa_mode: empty (local single-sequence pilot)')
        repeats = payload.get('repeats', 1)
        if type(repeats) is not int or repeats not in (1, 3):
            raise ValueError('Choose one or three matched seeds')
        seeds = [42, 43, 44][:repeats]
        selected = payload['candidates']
        if not isinstance(selected, list) or not 1 <= len(selected) <= 3:
            raise ValueError('Choose one to three candidates')
        known = {r['id']: r for r in catalog(dataset, (proposal_store or self.proposals).list())}
        cases, seen = [], set()
        from rdkit import Chem
        for item in selected:
            if not isinstance(item, dict) or set(item) != {'id', 'smiles'} or not all(isinstance(v,str) for v in item.values()):
                raise ValueError('Select a source ID and an explicit stereochemical SMILES')
            source = known.get(item['id'])
            if not source or item['smiles'] not in source['stereo_options']:
                raise ValueError('Choose a stereoisomer from the candidate catalog')
            if item['smiles'] in seen:
                raise ValueError('Duplicate molecular structure in batch')
            seen.add(item['smiles'])
            mol = Chem.MolFromSmiles(item['smiles'])
            if mol.GetNumHeavyAtoms() > 80:
                raise ValueError('This pilot supports ligands with at most 80 heavy atoms')
            cases.append({'id': f'candidate_{len(cases)+1}', 'source': source, 'smiles': item['smiles'],
                          'heavy_atoms': mol.GetNumHeavyAtoms(), 'status': 'queued', 'prediction': None})
        cases = [dict(case, id=case['id'] + f'_seed{seed}', candidate_id=case['id'], seed=seed)
                 for seed in seeds for case in cases]
        sequence, provenance = target_sequence(dataset)
        with self.lock:
            if not self.health['ready']:
                raise RuntimeError(' '.join(self.health['issues']))
            if any(j['status'] in ACTIVE for j in self.list()):
                raise RuntimeError('An experiment is already active; wait or cancel it first.')
            job = {'id': str(uuid.uuid4()), 'schema_version': 2, 'seeds': seeds, 'created_at': now(), 'status': 'queued',
                   'model': 'Boltz-2', 'model_version': self.health['version'], 'settings': SETTINGS.copy(),
                   'sequence': sequence, 'sequence_source': provenance, 'cases': cases,
                   'workspace_id': dataset.get('workspace_id', 'brd4'), 'target': dataset['target'],
                   'pose_check_mode': dataset.get('prediction_target', {}).get('pose_checks', 'brd4'),
                   'msa_mode': 'empty', 'templates': False, 'use_potentials': False,
                   'assay': dataset['assay'], 'warnings': [
                       'Exploratory single-sequence pilot: no MSA, no template. This can reduce prediction quality.',
                       'Only one protein construct and the selected ligand are predicted; other chains, metals and cofactors are omitted.',
                       ('Three matched seeds per candidate measure sampling variation, not calibrated uncertainty.' if repeats == 3 else 'One seed per candidate; sampling variation has not been assessed.'),
                       'Selected stereoisomers do not inherit measurements from stereochemically unspecified assay records.',
                       'Known published compounds may overlap model training data. This is not a held-out validation.',
                       'Native affinity_pred_value is log10(IC50 in micromolar), lower is stronger; it is not a measured IC50.',
                       'A completed model run is not a validated binding prediction.']}
            self.save(job)
            self.pool.submit(self.run, job['id'])
            return job

    def cancel(self, identifier):
        with self.lock:
            job = self.get(identifier)
            if job['status'] not in ACTIVE: return job
            self.cancelled.add(identifier)
            process = self.processes.get(identifier)
            if process and process.poll() is None:
                try: os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
            job['cancel_requested'] = True
            self.save(job)
            return job

    def update(self, job):
        with self.lock:
            if job['id'] in self.cancelled: job['cancel_requested'] = True
            self.save(job)

    def run(self, identifier):
        job = self.get(identifier)
        folder = self.directory / identifier
        try:
            job['status'] = 'preparing'; self.update(job)
            for case in job['cases']:
                if identifier in self.cancelled: break
                input_path = folder / (case['id'] + '.yaml')
                document = {'version': 1, 'sequences': [
                    {'protein': {'id': 'A', 'sequence': job['sequence'], 'msa': 'empty'}},
                    {'ligand': {'id': 'L', 'smiles': case['smiles']}}], 'properties': [{'affinity': {'binder': 'L'}}]}
                input_path.write_text(json.dumps(document, indent=2))
                case['input_sha256'] = sha(input_path)
                out = folder / case['id']; out.mkdir()
                command = [str(Path(self.executable).resolve()), 'predict', str(input_path), '--out_dir', str(out),
                    '--cache', str(self.cache), '--model', 'boltz2', '--accelerator', 'gpu', '--devices', '1',
                    '--num_workers', '0', '--preprocessing-threads', '1', '--max_parallel_samples', '1',
                    '--output_format', 'pdb', '--no_kernels']
                for key, value in dict(job['settings'], seed=case['seed']).items(): command += ['--'+key, str(value)]
                case.update(status='running', started_at=now(), command=command)
                job['status'] = 'running'; self.update(job)
                with (out / 'process.log').open('w') as log:
                    with self.lock:
                        if identifier in self.cancelled: break
                        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                            env={**os.environ, 'BOLTZ_CACHE': str(self.cache), 'MPLCONFIGDIR': str(self.cache/'matplotlib'),
                                 'XDG_CACHE_HOME': str(self.cache/'xdg')})
                        self.processes[identifier] = process
                    start = time.monotonic(); stopping = None
                    while process.poll() is None:
                        if identifier in self.cancelled or time.monotonic()-start > 7200:
                            if stopping is None:
                                stopping = time.monotonic()
                                try: os.killpg(process.pid, signal.SIGTERM)
                                except ProcessLookupError: pass
                            elif time.monotonic()-stopping > 3:
                                try: os.killpg(process.pid, signal.SIGKILL)
                                except ProcessLookupError: pass
                        time.sleep(0.2)
                    case['returncode'] = process.returncode
                    if stopping is not None and identifier not in self.cancelled:
                        case['error'] = 'Two-hour per-candidate time limit reached'
                case['finished_at'] = now()
                if identifier in self.cancelled:
                    case['status'] = 'cancelled'; break
                if process.returncode != 0 or case.get('error'):
                    case.update(status='failed', error=case.get('error', 'Boltz failed; inspect this candidate’s local process.log'))
                else:
                    job['status'] = 'validating'; case['status'] = 'validating'; self.update(job)
                    try:
                        case['prediction'] = read_result(out, case['id'], case['heavy_atoms'], case['smiles'], job.get('pose_check_mode', 'brd4'))
                        case['status'] = 'complete'
                    except (ValueError, KeyError, OSError) as exc:
                        case.update(status='failed', error=str(exc))
                self.update(job)
            job['checkpoints'] = [{'file': p.name, 'sha256': sha(p)} for p in sorted(self.cache.glob('boltz2_*.ckpt'))]
            self.health['weights_cached'] = all((self.cache / n).is_file() for n in ('boltz2_conf.ckpt', 'boltz2_aff.ckpt'))
            job['protocol_sha256'] = hashlib.sha256(json.dumps({k: job[k] for k in (
                'model_version', 'settings', 'seeds', 'sequence', 'msa_mode', 'templates', 'use_potentials', 'checkpoints')}, sort_keys=True).encode()).hexdigest()
            job['status'] = 'cancelled' if identifier in self.cancelled else 'complete' if all(c['status']=='complete' for c in job['cases']) else 'partial' if any(c['status']=='complete' for c in job['cases']) else 'failed'
        except Exception as exc:
            job.update(status='failed', error=str(exc))
        finally:
            for case in job['cases']:
                if case['status'] in ACTIVE: case['status'] = 'cancelled' if identifier in self.cancelled else 'failed'
            job['finished_at'] = now(); self.update(job)
            with self.lock: self.processes.pop(identifier, None)

    def close(self):
        if self._closed: return
        self._closed = True
        for job in self.list():
            if job['status'] in ACTIVE: self.cancel(job['id'])
        self.pool.shutdown(wait=True)
        self._lease.close()

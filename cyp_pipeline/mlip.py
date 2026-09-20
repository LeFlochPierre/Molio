"""UMA OMol integration; optional dependencies are imported only when needed."""
import argparse
import copy
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
import os
from pathlib import Path
import sys
import time

from .core import require, checked_evaluate, finite
from .workflow import save

MODEL_FILE = 'checkpoints/uma-s-1p2p1.pt'
LOCAL_MODEL_FILE = 'uma-s-1p2p1.pt'
MODEL_REPO = 'facebook/UMA'


def configure_cache():
    os.environ.setdefault('FAIRCHEM_CACHE_DIR', str(Path('.cache/fairchem').resolve()))
    os.environ.setdefault('MPLCONFIGDIR', str(Path('.cache/matplotlib').resolve()))


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def package_versions():
    result = {}
    for name in ('fairchem-core', 'torch', 'ase', 'huggingface-hub'):
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = None
    return result


def preflight(config):
    """No checkpoint load, downloads or authentication access."""
    packages = package_versions()
    path = Path(config['checkpoint'])
    issues = []
    if any(v is None for v in packages.values()):
        issues.append('Install the MLIP environment with scripts/setup_mlip.sh cpu (or cuda).')
    if not path.is_file():
        issues.append('Model weights missing. Obtain UMA access, then use the download command.')
    available = False
    if packages['torch']:
        import torch
        available = torch.cuda.is_available()
    if config.get('device') == 'cuda' and not available:
        issues.append('CUDA requested but unavailable; use a working GPU or the CPU config.')
    return {'status': 'ready_to_load' if not issues else 'blocked', 'packages': packages,
            'checkpoint_present': path.is_file(), 'device': config.get('device'),
            'cuda_available': available, 'issues': issues,
            'note': 'Ready to load does not establish model accuracy or chemical preparation.'}


class UMABackend:
    def __init__(self, config):
        require(config.get('device') in ('cpu', 'cuda'), 'UMA device must be cpu or cuda')
        checkpoint = Path(config['checkpoint'])
        require(checkpoint.is_file(), 'UMA checkpoint missing; see docs/MLIP_QUICKSTART.md')
        require(config.get('task', 'omol') == 'omol', 'CYP calculations require the omol task')
        require(config.get('inference_settings', 'batch') == 'batch',
                'Use batch inference settings for changing cluster/fragment compositions and states')
        self.max_atoms = config.get('max_atoms', 256 if config['device'] == 'cpu' else 5000)
        require(type(self.max_atoms) is int and self.max_atoms > 0, 'max_atoms must be positive')
        threads = config.get('threads', 2)
        require(type(threads) is int and threads > 0, 'threads must be positive')
        actual_hash = file_hash(checkpoint)
        expected_hash = config.get('checkpoint_sha256')
        if expected_hash:
            require(actual_hash == expected_hash, 'Checkpoint SHA-256 mismatch')
        import torch
        configure_cache()
        from fairchem.core import FAIRChemCalculator, pretrained_mlip
        if config['device'] == 'cuda':
            require(torch.cuda.is_available(), 'CUDA is unavailable; refusing a silent CPU fallback')
        torch.set_num_threads(threads)
        self.calculator = FAIRChemCalculator(
            pretrained_mlip.load_predict_unit(str(checkpoint), device=config['device'],
                                             inference_settings='batch'), task_name='omol')
        self.metadata = {'name': config.get('model_name', MODEL_FILE),
                         'version': version('fairchem-core'), 'packages': package_versions(),
                         'checkpoint_sha256': actual_hash, 'task': 'omol',
                         'inference_settings': 'batch', 'device': config['device'],
                         'threads': threads, 'synthetic': False, 'physical_energy_only': True,
                         'state_handling': 'ASE atoms.info charge=integer charge, spin=spin multiplicity',
                         'energy_convention': 'Raw UMA OMol total energy, identical atoms in both descriptor terms'}

    def evaluate(self, atoms, state):
        from ase import Atoms
        require(0 < len(atoms) <= self.max_atoms, f'Atom count exceeds configured budget ({self.max_atoms})')
        charge, spin = state.get('charge'), state.get('multiplicity')
        require(type(charge) is int and -100 <= charge <= 100, 'UMA requires integer charge in [-100,100]')
        require(type(spin) is int and 1 <= spin <= 100, 'UMA requires integer multiplicity in [1,100]')
        require(bool(state.get('convention')), 'Explicit electronic-state convention is required')
        require(all(len(a['position']) == 3 and all(finite(v) for v in a['position']) for a in atoms),
                'Coordinates must be finite xyz triples')
        # PDB conventions often use uppercase element fields (e.g. ``FE``),
        # while ASE requires standard chemical capitalization (``Fe``).
        symbols = [
            {'FE': 'Fe', 'CL': 'Cl', 'BR': 'Br', 'SI': 'Si', 'NA': 'Na',
             'MG': 'Mg', 'CA': 'Ca', 'ZN': 'Zn', 'CU': 'Cu', 'MN': 'Mn',
             'CO': 'Co', 'NI': 'Ni'}.get(a['element'].upper(), a['element'])
            for a in atoms
        ]
        molecule = Atoms(symbols=symbols,
                         positions=[a['position'] for a in atoms], pbc=False)
        electrons = int(sum(molecule.numbers)) - charge
        require(electrons >= 0 and spin - 1 <= electrons and (electrons - (spin - 1)) % 2 == 0,
                'Charge/multiplicity inconsistent with electron count')
        molecule.info.update(charge=charge, spin=spin)
        # Reset ASE result caches explicitly when switching states or compositions.
        # This retains the loaded model, not prior energy/force results.
        self.calculator.reset()
        molecule.calc = self.calculator
        # No ASE constraints or artificial restraint energies are attached.
        return float(molecule.get_potential_energy()), molecule.get_forces().tolist()


def smoke(config, out):
    root = Path(out)
    root.mkdir(parents=True, exist_ok=False)
    save(root / 'backend-config.json', config)
    result = {'test': 'water_energy_force_smoke', 'status': 'failed', 'synthetic': False,
              'scope': 'Engineering check on water only; no CYP or selectivity validation.'}
    start = time.monotonic()
    try:
        backend = UMABackend(config)
        result['backend'] = backend.metadata
        atoms = [{'id': 'O', 'element': 'O', 'position': [0., 0., 0.]},
                 {'id': 'H1', 'element': 'H', 'position': [0.96, 0., 0.]},
                 {'id': 'H2', 'element': 'H', 'position': [-0.24, 0.93, 0.]}]
        state = {'charge': 0, 'multiplicity': 1, 'convention': 'Neutral singlet water'}
        save(root / 'input.json', {'atoms': atoms, 'state': state})
        energy, forces = checked_evaluate(backend, atoms, state)
        # One coordinate is sufficient to catch sign/unit/integration mistakes,
        # but is not a full force-validation suite.
        step = 0.005
        plus, minus = copy.deepcopy(atoms), copy.deepcopy(atoms)
        plus[1]['position'][0] += step
        minus[1]['position'][0] -= step
        ep, _ = checked_evaluate(backend, plus, state)
        em, _ = checked_evaluate(backend, minus, state)
        estimate = -(ep - em) / (2 * step)
        error = abs(estimate - forces[1][0])
        result.update(energy_eV=energy, forces_eV_A=forces,
                      finite_difference={'atom': 'H1', 'axis': 'x', 'step_A': step,
                                         'force_eV_A': estimate, 'absolute_error_eV_A': error,
                                         'tolerance_eV_A': 0.1})
        result['status'] = 'passed' if error <= 0.1 else 'needs_investigation'
    except Exception as exc:
        result['error_type'] = type(exc).__name__
        result['message'] = str(exc) if isinstance(exc, (ValueError, ImportError)) else 'Model initialization/evaluation failed; inspect the local setup.'
    result['runtime_seconds'] = time.monotonic() - start
    save(root / 'result.json', result)
    return result


def download(out, filename=MODEL_FILE):
    """Download only the named checkpoint; authentication is handled by HF itself."""
    from huggingface_hub import hf_hub_download
    path = Path(out)
    require(not path.exists(), 'Refusing to overwrite checkpoint')
    from huggingface_hub.errors import GatedRepoError, HfHubHTTPError
    try:
        cached = hf_hub_download(repo_id=MODEL_REPO, filename=filename,
                                 cache_dir=str(Path('.cache/huggingface').resolve()))
    except GatedRepoError:
        raise ValueError('UMA access required: accept terms at https://huggingface.co/facebook/UMA and authenticate with hf auth login. Do not paste tokens into chat.') from None
    except HfHubHTTPError as exc:
        raise ValueError(f'Model download failed (HTTP {exc.response.status_code if exc.response is not None else "unknown"}); verify model access and connectivity.') from None
    import shutil
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(cached, 'rb') as source, path.open('xb') as target:
        shutil.copyfileobj(source, target)
    save(str(path) + '.provenance.json', {'repo': MODEL_REPO, 'filename': filename,
                                       'sha256': file_hash(path), 'cache_snapshot': Path(cached).parent.name})
    return {'checkpoint': str(path), 'sha256': file_hash(path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description='UMA model setup and real-model smoke test')
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ('preflight', 'smoke'):
        p = sub.add_parser(name)
        p.add_argument('--backend', default='configs/uma-cpu.json')
        if name == 'smoke': p.add_argument('--out', required=True)
    p = sub.add_parser('download'); p.add_argument('--out', help='Destination; defaults to models/<selected checkpoint name>')
    p.add_argument('--filename', default=MODEL_FILE, choices=['checkpoints/uma-s-1p1.pt', MODEL_FILE],
                   help='Explicit upstream checkpoint; use 1p1 with the IsoForm demo configs')
    args = parser.parse_args(argv)
    try:
        if args.action == 'download':
            result = download(args.out or str(Path('models') / Path(args.filename).name), args.filename)
        else:
            config = json.loads(Path(args.backend).read_text())
            result = preflight(config) if args.action == 'preflight' else smoke(config, args.out)
        print(json.dumps(result, indent=2))
        return 1 if result.get('status') in ('blocked', 'failed', 'needs_investigation') else 0
    except (ValueError, OSError, ImportError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

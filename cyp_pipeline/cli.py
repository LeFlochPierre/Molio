import argparse
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from .backends import HarmonicDemo, load_backend
from .core import validate, validate_protocol, require
from .demo import system
from .workflow import run, save, compare, report


def read(path):
    return json.loads(Path(path).read_text())


def doctor():
    gpu = {'available': False, 'detail': 'nvidia-smi not found'}
    if shutil.which('nvidia-smi'):
        try:
            p = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.free', '--format=csv,noheader'],
                               text=True, capture_output=True, timeout=15)
            gpu = {'available': p.returncode == 0, 'detail': (p.stdout + p.stderr).strip()}
        except subprocess.TimeoutExpired:
            gpu['detail'] = 'nvidia-smi timed out'
    return {'hostname': platform.node(), 'cwd': str(Path.cwd()), 'python': platform.python_version(),
            'cpu_count': os.cpu_count(), 'gpu': gpu,
            'packages': {n: importlib.util.find_spec(n) is not None for n in ['numpy', 'torch', 'ase', 'rdkit']},
            'services': {'BioNeMo': 'unverified', 'Rosalind': 'unverified'}}


def fetch(pdb, out):
    require(re.fullmatch(r'[0-9][A-Za-z0-9]{3}', pdb), 'Expected four-character PDB ID')
    path = Path(out)
    require(not path.exists(), 'Refusing to overwrite structure')
    url = f'https://files.rcsb.org/download/{pdb.upper()}.pdb'
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(20_000_001)
    require(len(data) <= 20_000_000 and b'ATOM  ' in data, 'Invalid/oversized PDB response')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as handle:
        handle.write(data)
    import hashlib
    save(str(path) + '.provenance.json', {'source': url, 'sha256': hashlib.sha256(data).hexdigest()})


def inspect_pdb(path):
    counts, alternates, models = {}, 0, 0
    for line in Path(path).read_text().splitlines():
        if line.startswith('MODEL '):
            models += 1
        if line.startswith(('ATOM  ', 'HETATM')):
            key = f'{line[21:22]}:{line[22:27].strip()}:{line[17:20].strip()}'
            counts[key] = counts.get(key, 0) + 1
            alternates += bool(line[16:17].strip())
    return {'residue_atom_counts': counts, 'alternate_location_atom_records': alternates,
            'models': models or 1, 'note': 'Inventory only; no protonation, bonding or stereochemistry inferred.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description='CYP deformation-energy feasibility workflow')
    subs = parser.add_subparsers(dest='action', required=True)
    subs.add_parser('doctor')
    p = subs.add_parser('fetch'); p.add_argument('pdb'); p.add_argument('--out', required=True)
    p = subs.add_parser('inspect'); p.add_argument('pdb_file')
    p = subs.add_parser('validate'); p.add_argument('system'); p.add_argument('--provisional', action='store_true')
    for action in ('demo', 'run'):
        p = subs.add_parser(action)
        p.add_argument('--out', required=True)
        p.add_argument('--protocol', default='configs/protocol.json')
        if action == 'run':
            p.add_argument('system'); p.add_argument('--backend', required=True)
            p.add_argument('--provisional', action='store_true')
    p = subs.add_parser('report'); p.add_argument('results', nargs='+')
    p.add_argument('--protocol', default='configs/protocol.json'); p.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == 'doctor':
            print(json.dumps(doctor(), indent=2))
        elif args.action == 'fetch':
            fetch(args.pdb, args.out); print(args.out)
        elif args.action == 'inspect':
            print(json.dumps(inspect_pdb(args.pdb_file), indent=2))
        elif args.action == 'validate':
            validate(read(args.system), allow_provisional=args.provisional); print('Preparation contract valid (not chemical validation).')
        elif args.action == 'run':
            config = read(args.backend)
            require('REPLACE_' not in json.dumps(config), 'Fill in backend configuration first')
            prepared = validate(read(args.system), allow_provisional=args.provisional)
            protocol = validate_protocol(read(args.protocol))
            require(not Path(args.out).exists(), 'Output directory already exists')
            backend = load_backend(config)
            result = run(prepared, protocol, backend, args.out, provisional=args.provisional)
            print(json.dumps(result, indent=2))
            return 0 if result['status'] == 'exploratory' else 1
        elif args.action == 'demo':
            root = Path(args.out); root.mkdir(parents=True, exist_ok=False)
            protocol = read(args.protocol)
            results = [run(system(ligand, isoform), protocol, HarmonicDemo(), root / f'{ligand}-{isoform}')
                       for ligand in ('R-fadrozole', 'S-fadrozole') for isoform in ('CYP11B1', 'CYP11B2')]
            comparisons = compare(results, protocol)
            save(root / 'summary.json', {'results': results, 'comparisons': comparisons})
            report(results, comparisons, root / 'report.html')
            print(root / 'report.html')
            return 0 if all(r['status'] == 'synthetic_demo' for r in results) else 1
        elif args.action == 'report':
            results = [read(p) for p in args.results]
            report(results, compare(results, read(args.protocol)), args.out)
            print(args.out)
    except (ValueError, KeyError, TypeError, OSError, ImportError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    return 0

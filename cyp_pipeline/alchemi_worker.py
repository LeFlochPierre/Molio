"""Isolated ALCHEMI worker for existing exchange and prepared-batch protocols."""
import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+')
    parser.add_argument('--backend', required=True)
    parser.add_argument('--out')
    parser.add_argument('--single-pose', action='store_true')
    parser.add_argument('--allow-provisional', action='store_true')
    args = parser.parse_args(argv)
    config = json.loads(Path(args.backend).read_text())
    if args.inputs == ['preflight']:
        from importlib.metadata import version, PackageNotFoundError
        from .mlip import preflight
        result = preflight(config)
        try:
            result['packages']['nvalchemi-toolkit'] = version('nvalchemi-toolkit')
        except PackageNotFoundError:
            result['issues'].append('Install nvalchemi-toolkit in the isolated agent environment')
        result['engine'] = config.get('engine')
        if result['engine'] != 'alchemi':
            result['issues'].append('Expected engine=alchemi')
        result['status'] = 'blocked' if result['issues'] else 'ready_to_load'
    else:
        from .alchemi_backend import AlchemiUMABackend
        from .core import require
        require(bool(args.out), '--out is required')
        batch_mode = len(args.inputs) == 2 and args.inputs[0] == 'run'
        require(batch_mode or len(args.inputs) == 1, 'Invalid worker command')
        payload = json.loads(Path(args.inputs[-1]).read_text())
        if batch_mode:
            from .uma_batch import validate_batch, run_batch
            audit = validate_batch(payload, config.get('max_atoms', 1000))
            require(not audit['provisional'] or args.allow_provisional,
                    'Explicit provisional preparation confirmation required')
            result = run_batch(payload, AlchemiUMABackend(config), args.out)
        else:
            from .exchange import validate_manifest, run_cycle
            validate_manifest(payload)
            require(payload['geometry_mode'] == 'single_point' and args.single_pose,
                    'Interactive ALCHEMI worker supports frozen-coordinate single-pose exchange')
            result = run_cycle(payload, AlchemiUMABackend(config), args.out)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 1 if result.get('status') in ('blocked', 'failed', 'unresolved') else 0


if __name__ == '__main__':
    raise SystemExit(main())

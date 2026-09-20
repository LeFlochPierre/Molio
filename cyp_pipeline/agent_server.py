"""Serve the existing IsoForm UI with ALCHEMI jobs and a small agent API."""
import argparse
import copy
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from .sentinel_server import JobManager, make_handler, PROJECT_ROOT, DEFAULT_CATALOG
from .interpretation import exchange_preference


class AlchemiJobManager(JobManager):
    def _launch(self, payload, module, kind, label, **kwargs):
        config = json.loads(self.backend.read_text())
        if config.get('engine') != 'alchemi':
            raise ValueError('Agent server requires an explicit ALCHEMI backend')
        if kind == 'exchange' and kwargs.get('preset') in ('r_fadrozole', 's_fadrozole'):
            payload = copy.deepcopy(payload)
            # These two curated manifests describe the same cap/residue/state
            # recipe with different prose and stereochemical pose sources.
            payload['agent_protocol_family'] = 'capped-pocket-fadrozole-pilot-v1'
        return super()._launch(payload, 'cyp_pipeline.alchemi_worker', kind, label, **kwargs)

    def preflight(self):
        process = subprocess.run(
            [str(self.uma_python), '-m', 'cyp_pipeline.alchemi_worker', 'preflight',
             '--backend', str(self.backend)], cwd=self.root, capture_output=True, text=True, timeout=60)
        try:
            result = json.loads(process.stdout)
        except ValueError:
            result = {'status': 'blocked', 'issues': ['Preflight output was not JSON']}
        return {'command_status': 'completed', 'returncode': process.returncode, 'result': result}

    def health(self):
        result = super().health()
        result.update(service='IsoForm ALCHEMI agent tools', engine='alchemi',
                      agent_mode='External LLM agent via skill or MCP; no embedded LLM',
                      qsar='No trained QSAR in this integration',
                      generation='Existing candidate library ranking only; no generative model')
        return result


def protocol_signature(manifest):
    parts = {}
    for enzyme, components in manifest['enzymes'].items():
        parts[enzyme] = {}
        for name, component in components.items():
            scaffold = set(component.get('scaffold_ids', []))
            parts[enzyme][name] = {
                'scaffold': sorted((a['id'], a['element'].upper()) for a in component['atoms'] if a.get('id') in scaffold),
                'fixed_ids': sorted(component.get('fixed_ids', [])),
                'charge': component.get('state', {}).get('charge'),
                'multiplicity': component.get('state', {}).get('multiplicity'),
            }
    return [manifest.get('agent_protocol_family', manifest['preparation_protocol']), parts]


def comparison(manager, job_ids):
    if not 1 <= len(job_ids) <= 8 or len(set(job_ids)) != len(job_ids):
        raise ValueError('Provide 1 to 8 unique job IDs')
    rows, protocols = [], set()
    for job_id in job_ids:
        job = manager.status(job_id)
        if job['state'] != 'completed' or job['kind'] != 'exchange':
            raise ValueError('Every comparison job must be a completed exchange calculation')
        result = job['result']
        if result.get('status') != 'exploratory' or result.get('synthetic') is not False:
            raise ValueError('An unresolved or synthetic run cannot be compared')
        manifest = json.loads((manager.root / job['input_manifest']).read_text())
        meta = result['backend']
        protocols.add(json.dumps([protocol_signature(manifest), result['geometry_mode'],
                                  meta['checkpoint_sha256'], meta['task'],
                                  meta['inference_settings'], meta['device'], meta.get('engine')], sort_keys=True))
        ligand = manifest['enzymes']['CYP11B1']['free_ligand']['atoms']
        counts = Counter(atom['element'].upper() for atom in ligand)
        rows.append({'job_id': job_id, 'candidate': result['ligand'],
                     'nitrogen_atoms': counts['N'], 'heavy_atoms': sum(v for k, v in counts.items() if k != 'H'),
                     'delta_B2_minus_B1_eV': result['delta_B2_minus_B1_eV'],
                     'preference': exchange_preference(result),
                     'preparation_protocol': manifest['preparation_protocol'],
                     'exchanges_eV': {key: value['exchange_energy_eV'] for key, value in result['enzymes'].items()},
                     'input_sha256': result['input_sha256'], 'backend': meta})
    if len(protocols) != 1:
        raise ValueError('Mixed preparation protocols, model checkpoints, or numerical settings cannot be ranked together')
    return {'rows': rows, 'descriptor': 'frozen-coordinate ligand/water exchange potential energy',
            'scope': 'Exploratory energy comparison, not measured or predicted biological selectivity.',
            'qsar': {'trained': False, 'reason': 'These runs are observations, not a fitted or validated QSAR.'},
            'nitrogen_analysis': 'Atom counts are descriptive; they do not establish a causal nitrogen effect.'}


def candidate_suggestions(manager, target):
    if target not in ('CYP11B1', 'CYP11B2'):
        raise ValueError('Unknown target isoform')
    from .design import DEFAULT_CANDIDATES
    rows = [{key: row[key] for key in ('id', 'name', 'smiles', 'modification', 'rationale')}
            for row in DEFAULT_CANDIDATES if row.get('status') == 'proposed'][:5]
    return {'target': target, 'method': 'Unranked existing analog hypotheses',
            'library_origin': 'The existing library was designed around CYP11B1 hypotheses; these are not established CYP11B2 improvements.',
            'trained_qsar': False, 'de_novo_generation': False, 'scored_with_uma': False,
            'candidates': rows,
            'scope': 'Hypotheses for preparation and testing. Similarity uncertainty is not calibrated statistical confidence.'}


def agent_handler(manager, site):
    Base = make_handler(manager, site)

    class Handler(Base):
        def do_GET(self):
            url = urlparse(self.path)
            try:
                if url.path == '/api/agent/jobs':
                    with manager.lock:
                        jobs = list(manager.jobs)
                    return self.send_json(200, {'jobs': [manager.status(key) for key in jobs]})
                if url.path == '/api/agent/compare':
                    return self.send_json(200, comparison(manager, parse_qs(url.query).get('job_id', [])))
                if url.path == '/api/agent/suggest':
                    target = parse_qs(url.query).get('target', ['CYP11B2'])[0]
                    return self.send_json(200, candidate_suggestions(manager, target))
            except (ValueError, KeyError, OSError) as error:
                return self.send_json(400, {'error': str(error)})
            return super().do_GET()
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=PROJECT_ROOT)
    parser.add_argument('--site', type=Path, default=PROJECT_ROOT/'runs/selectivity-sentinel-demo-v3/demo.html')
    parser.add_argument('--backend', type=Path, default=PROJECT_ROOT/'configs/uma-s-1p1-alchemi-local.json')
    parser.add_argument('--uma-python', default=sys.executable)
    parser.add_argument('--port', type=int, default=8001)
    args = parser.parse_args()
    if not args.site.is_file():
        parser.error('Demo HTML does not exist')
    manager = AlchemiJobManager(args.root, args.uma_python, args.backend, True, DEFAULT_CATALOG)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), agent_handler(manager, args.site.resolve()))
    print(f'IsoForm ALCHEMI: http://127.0.0.1:{args.port}/', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

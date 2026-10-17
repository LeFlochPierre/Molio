"""Local evidence workspace with optional RDKit previews and persistent proposals."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs

from .evidence import compare_observations
from .proposals import ProposalStore, analyze, available
from .suggestions import suggest
from .designs import explore, shortlist
from .experiments import Experiments, catalog
from .targets import Workspaces, search_targets

ROOT = Path(__file__).resolve().parent


def load_dataset(directory=None):
    directory = Path(directory) if directory else ROOT / 'data'
    data = json.loads((directory / 'dataset.json').read_text())
    data['edit_evidence'] = json.loads((directory / 'edit-evidence.json').read_text())
    data.setdefault('workspace_id', 'brd4')
    compounds = {row['id']: row for row in data['compounds']}
    for pair in data['pairs']:
        pair.update(compare_observations(compounds[pair['left']]['observation'],
                                         compounds[pair['right']]['observation']))
    return data


def export_comparisons(payload, dataset):
    if not isinstance(payload, dict) or set(payload) - {'pair_ids', 'notes'}:
        raise ValueError('Expected pair_ids and optional notes')
    ids, notes = payload.get('pair_ids'), payload.get('notes', {})
    if not isinstance(ids, list) or not 1 <= len(ids) <= 20 or any(not isinstance(x, str) for x in ids):
        raise ValueError('Select 1–20 comparison IDs')
    if not isinstance(notes, dict) or any(not isinstance(v, str) or len(v) > 4000 for v in notes.values()):
        raise ValueError('Notes must be text of at most 4000 characters each')
    known = {p['id']: p for p in dataset['pairs']}
    if set(ids) - known.keys() or set(notes) - set(ids):
        raise ValueError('Unknown comparison or unrelated note')
    pairs = [dict(known[i], user_hypothesis=notes.get(i, ''), edit_evidence=dataset['edit_evidence'][i]) for i in dict.fromkeys(ids)]
    cids = {p[k] for p in pairs for k in ('left', 'right')}
    return dict(schema_version=1, kind='experimental_comparison_shortlist',
        target=dataset['target'], assay=dataset['assay'], publication=dataset['publication'],
        comparisons=pairs, compounds=[c for c in dataset['compounds'] if c['id'] in cids],
        reference_structure=dataset['reference_structure'], provenance=dataset['provenance'],
        predictions=[], interpretation='Measured same-assay IC50 comparisons; reference pocket only. No new prediction or proposed molecule is included.')


class Handler(BaseHTTPRequestHandler):
    def send_content(self, content, mime='application/json; charset=utf-8', status=200):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; worker-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        if self.command != 'HEAD':
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                # A newer edit can cancel an in-flight preview response.
                pass

    def json(self, value, status=200):
        self.send_content(json.dumps(value, allow_nan=False).encode(), status=status)

    def do_HEAD(self):
        self.do_GET()

    def workspace_id(self):
        return parse_qs(urlsplit(self.path).query).get('workspace', ['brd4'])[0]

    def workspace_folder(self):
        key = self.workspace_id()
        if key == 'brd4': return None
        manager = getattr(self.server, 'workspaces', None)
        if manager is None: raise ValueError('Target setup is not configured on this server')
        return manager.folder(key)

    def dataset(self):
        folder = self.workspace_folder()
        return load_dataset(folder / 'data' if folder else None)

    def store(self):
        folder = self.workspace_folder()
        return ProposalStore(folder / 'proposals.sqlite3') if folder else self.server.proposal_store

    def owned_job(self, identifier):
        job = self.server.experiments.get(identifier)
        if job.get('workspace_id', 'brd4') != self.workspace_id():
            raise ValueError('Experiment belongs to another workspace')
        return job

    def do_GET(self):
        try:
            self.get_route()
        except ValueError as exc:
            self.json({'error': str(exc)}, 400)
        except RuntimeError as exc:
            self.json({'error': str(exc)}, 503)

    def get_route(self):
        path = unquote(urlsplit(self.path).path)
        if path == '/api/workspaces':
            manager = getattr(self.server, 'workspaces', None)
            return self.json({'workspaces': manager.list() if manager else [], 'available': manager is not None})
        if path == '/api/targets/search':
            return self.json(search_targets(parse_qs(urlsplit(self.path).query).get('q', [''])[0]))
        if path == '/api/proteins/search':
            from .starter import search_proteins
            return self.json(search_proteins(parse_qs(urlsplit(self.path).query).get('q', [''])[0]))
        if path.startswith('/api/target-tasks/'):
            manager = getattr(self.server, 'workspaces', None)
            if manager is None: raise ValueError('Target setup is not configured')
            return self.json(manager.task(path.rsplit('/', 1)[-1]))
        # Validate the workspace before accessing any of its data or jobs.
        if path.startswith('/api/'): self.workspace_folder()
        if path == '/api/experiments':
            jobs = getattr(self.server, 'experiments', None)
            return self.json({'experiments': [j for j in jobs.list() if j.get('workspace_id', 'brd4') == self.workspace_id()] if jobs else [],
                              'runtime': jobs.health if jobs else {'ready': False, 'issues': ['Prediction worker is not configured.']}})
        if path == '/api/experiment-candidates':
            if not available():
                return self.json({'candidates': [], 'error': 'RDKit is required to select stereoisomers.'})
            return self.json({'candidates': catalog(self.dataset(), self.store().list())})
        if path.startswith('/api/experiment-pose/'):
            try:
                _, _, _, job_id, case_id = path.split('/')
                jobs = self.server.experiments
                job = self.owned_job(job_id)
                case = next(c for c in job['cases'] if c['id'] == case_id and c['status'] == 'complete')
                base = jobs.directory / job_id / case_id
                pose = (base / case['prediction']['pose']).resolve()
                if not pose.is_relative_to(base.resolve()): raise ValueError('Invalid artifact')
                return self.send_content(pose.read_bytes(), 'text/plain; charset=utf-8')
            except (ValueError, StopIteration, AttributeError, OSError):
                return self.json({'error': 'Pose not available'}, 404)
        if path == '/api/capabilities':
            return self.json({'chemistry': available()})
        if path == '/api/proposals':
            return self.json({'proposals': self.store().list()})
        if path == '/api/dataset':
            return self.json(self.dataset())
        if path == '/api/starter/library':
            from .compound_lookup import library
            if self.dataset().get('mode') != 'starter': raise ValueError('Open a sequence-first workspace')
            return self.json(library(self.workspace_folder()/'data'))
        if path.startswith('/api/'):
            return self.json({'error': 'Not found'}, 404)
        base = ROOT / ('data' if path.startswith('/data/') else 'web')
        relative = path[len('/data/'):] if path.startswith('/data/') else path.lstrip('/') or 'index.html'
        if path.startswith('/workspaces/'):
            parts = path.split('/')
            manager = getattr(self.server, 'workspaces', None)
            if len(parts) < 5 or parts[3] != 'data' or manager is None:
                return self.json({'error': 'Not found'}, 404)
            base = manager.folder(parts[2]) / 'data'
            relative = '/'.join(parts[4:])
        file = (base / relative).resolve()
        if not file.is_relative_to(base.resolve()) or not file.is_file():
            return self.json({'error': 'Not found'}, 404)
        types = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                 '.css': 'text/css; charset=utf-8', '.json': 'application/json',
                 '.svg': 'image/svg+xml', '.pdb': 'text/plain; charset=utf-8', '.LICENSE': 'text/plain'}
        if file.suffix not in types:
            return self.json({'error': 'Not found'}, 404)
        self.send_content(file.read_bytes(), types[file.suffix])

    def do_POST(self):
        route = urlsplit(self.path).path
        if route not in ('/api/export', '/api/preview', '/api/proposals', '/api/suggestions', '/api/experiments', '/api/experiment-cancel', '/api/designs', '/api/design-shortlist', '/api/targets/inspect', '/api/targets/import', '/api/targets/starter', '/api/starter/compound', '/api/starter/region', '/api/starter/model', '/api/starter/find-compounds', '/api/starter/target-compounds', '/api/starter/import-compound'):
            return self.json({'error': 'Not found'}, 404)
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            return self.json({'error': 'Use application/json'}, 415)
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self.json({'error': 'Cross-origin writes are not allowed'}, 403)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 100000:
                raise ValueError('Invalid request size')
            payload = json.loads(self.rfile.read(size))
            if route in ('/api/targets/inspect', '/api/targets/import', '/api/targets/starter'):
                manager = getattr(self.server, 'workspaces', None)
                if manager is None: raise RuntimeError('Restart the server to enable target setup.')
                return self.json(manager.submit(payload, importing=route.endswith('/import'), starter=route.endswith('/starter')), 202)
            self.workspace_folder()
            if route in ('/api/starter/find-compounds','/api/starter/target-compounds'):
                from .compound_lookup import pubchem_search, target_compounds, save_lookup
                data = self.dataset()
                if data.get('mode') != 'starter': raise ValueError('Open a sequence-first workspace')
                status = None
                # Provider requests must not hold the shared workspace lock.
                if route.endswith('/find-compounds'):
                    if not isinstance(payload,dict) or set(payload) != {'query'}: raise ValueError('Expected a compound name or CID')
                    client, rows, message = pubchem_search(payload['query'])
                else:
                    if payload != {}: raise ValueError('Expected an empty request')
                    if not available(): raise RuntimeError('Target compound lookup requires the chemistry environment (RDKit).')
                    client, rows, status = target_compounds(data['target']); message = status['message']
                with self.server.workspaces.lock:
                    save_lookup(self.workspace_folder()/'data', self.dataset(), client, rows, status)
                return self.json({'candidates':rows,'message':message,'target_lookup':status})
            if route.startswith('/api/starter/'):
                from .starter import add_compound, select_region, download_model, persist_sources, write_json
                from .targets import PublicData
                with self.server.workspaces.lock:
                    data = self.dataset()
                    if data.get('mode') != 'starter': raise ValueError('This action is for sequence-first workspaces')
                    base = self.workspace_folder()/'data'
                    if route.endswith('/import-compound'):
                        from .compound_lookup import import_candidate
                        if not isinstance(payload,dict) or set(payload) != {'id'}: raise ValueError('Choose one compound result')
                        return self.json(import_candidate(base,data,payload['id']))
                    if route.endswith('/compound'):
                        return self.json(add_compound(base, data, payload))
                    if route.endswith('/region'):
                        if not isinstance(payload, dict) or set(payload) != {'start','end'}: raise ValueError('Expected start and end')
                        select_region(data, payload['start'], payload['end'])
                    else:
                        if payload != {}: raise ValueError('Expected an empty request')
                        client = PublicData(); download_model(base, data, client); persist_sources(base, data, client)
                    write_json(base/'dataset.json', data)
                    return self.json(data)
            if route in ('/api/experiments', '/api/experiment-cancel'):
                jobs = getattr(self.server, 'experiments', None)
                if jobs is None: raise RuntimeError('Prediction worker is not configured.')
                if route == '/api/experiments':
                    result = jobs.submit(payload, self.dataset(), self.store())
                else:
                    if not isinstance(payload, dict) or set(payload) != {'id'}:
                        raise ValueError('Expected experiment id')
                    self.owned_job(payload['id'])
                    result = jobs.cancel(payload['id'])
            elif route == '/api/designs':
                result = explore(payload, self.dataset())
            elif route == '/api/design-shortlist':
                result = shortlist(payload, self.dataset(), self.store())
            elif route == '/api/export':
                result = export_comparisons(payload, self.dataset())
            elif route == '/api/suggestions':
                result = suggest(payload, self.dataset())
            else:
                result = analyze(payload, self.dataset())
                if route == '/api/proposals':
                    result = self.store().save(result)
        except RuntimeError as exc:
            return self.json({'error': str(exc)}, 503)
        except (ValueError, TypeError, KeyError) as exc:
            return self.json({'error': str(exc)}, 400)
        self.json(result)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Molecular What-If Lab · local evidence explorer')
    parser.add_argument('--port', type=int, default=8001)
    parser.add_argument('--project-dir', type=Path, default=Path('work/whatif'), help='Local proposal storage directory')
    parser.add_argument('--boltz-executable', type=Path, help='Dedicated Boltz 2.2.1 executable (optional)')
    parser.add_argument('--boltz-cache', type=Path, help='Model cache; default PROJECT/boltz-cache')
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.workspaces = Workspaces(args.project_dir)
    server.proposal_store = ProposalStore(args.project_dir / 'proposals.sqlite3')
    server.experiments = Experiments(args.project_dir / 'experiments', server.proposal_store, args.boltz_executable, args.boltz_cache)
    print(f'Molecular What-If Lab: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.workspaces.close()
        server.experiments.close()
        server.server_close()


if __name__ == '__main__':
    main()

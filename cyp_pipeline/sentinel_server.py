"""Local web server for the IsoForm interactive research workspace.

This dependency-free server serves ``demo.html``, plans counter-screens and,
when explicitly enabled, runs preset exchange jobs or bounded, validated
prepared-pocket batches. A sequence, raw PDB or SMILES is not executable input.
Uploaded JSON never controls commands, model paths, output paths or backend
configuration. All scientific preparation and state declarations stay explicit.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .screening import PREPARED_PRESETS, DEFAULT_CATALOG, build_plan, catalog_payload, load_catalog
from .uma_batch import validate_batch, export_exchange, MAX_BYTES, MAX_ATOMS, MAX_SYSTEMS
from .auto_inputs import build_inputs, bundle_zip
from .structure_library import reference_views
from .interpretation import exchange_preference
from .calibrated_selectivity import analyze_calibrated


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def default_uma_python(root=PROJECT_ROOT):
    """Use an explicit local override, project ML environment, or current Python.

    Keep virtual-environment entrypoints intact: resolving their symlinks loses
    the environment. The optional runtime.local.json is deliberately not shared.
    """
    explicit = os.environ.get('ISOFORM_UMA_PYTHON')
    settings = Path(root) / 'configs/runtime.local.json'
    if not explicit and settings.is_file():
        payload = json.loads(settings.read_text())
        explicit = payload.get('uma_python') if isinstance(payload, dict) else None
    if explicit:
        if not isinstance(explicit, str):
            raise ValueError('uma_python must be a Python executable path')
        return Path(explicit).expanduser()
    for relative in ('.venv-mlip/bin/python', '.venv-mlip/Scripts/python.exe'):
        candidate = Path(root) / relative
        if candidate.is_file():
            return candidate
    return Path(sys.executable)


def default_backend(root=PROJECT_ROOT):
    root = Path(root)
    local = root / 'configs/uma-s-1p1-cpu-local.json'
    return local if local.is_file() else root / 'configs/uma-s-1p1-cpu.json'


DEFAULT_UMA_PYTHON = default_uma_python()
PRESETS = {key: {**value, 'label': value['label'] + ' · CYP11B2 / CYP11B1 prepared pair'}
           for key, value in PREPARED_PRESETS.items()}


def _read_json(path):
    return json.loads(Path(path).read_text())


def materialize_single_point_manifest(source, destination, job_id):
    """Copy a reviewed/provisional manifest into an immutable web-job input.

    The web route uses frozen coordinates so an interactive CPU request stays
    bounded.  It is a genuine UMA energy evaluation of all four components in
    both enzymes, but it is not a relaxation, pose ensemble, affinity, or a
    selectivity validation.
    """
    manifest = copy.deepcopy(_read_json(source))
    manifest["geometry_mode"] = "single_point"
    manifest["web_execution"] = {
        "job_id": job_id,
        "mode": "frozen_coordinate_exchange_single_point",
        "scope": (
            "Interactive UMA execution. This is an exploratory potential-energy exchange descriptor, "
            "not a binding affinity or selectivity claim."
        ),
    }
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2) + "\n")
    return destination


class JobManager:
    def __init__(self, root, uma_python, backend, execution_enabled=False, catalog=DEFAULT_CATALOG):
        self.root = Path(root).resolve()
        # Keep the venv entrypoint path intact. Resolving its python symlink
        # jumps to the base interpreter and loses the venv's fairchem packages.
        self.uma_python = Path(uma_python).expanduser()
        self.backend = Path(backend).resolve()
        self.execution_enabled = execution_enabled
        self.catalog = load_catalog(catalog)
        self.jobs = {}
        self.lock = threading.Lock()
        self.input_lock = threading.Lock()

    def preflight(self):
        command = [str(self.uma_python), "-m", "cyp_pipeline.mlip", "preflight", "--backend", str(self.backend)]
        try:
            completed = subprocess.run(command, cwd=self.root, capture_output=True, text=True, timeout=60)
            text = (completed.stdout or "") + (completed.stderr or "")
            start, end = text.find("{"), text.rfind("}")
            payload = json.loads(text[start:end + 1]) if start >= 0 and end >= start else None
            return {"command_status": "completed", "returncode": completed.returncode, "result": payload,
                    "output": text[-2000:]}
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
            return {"command_status": "failed", "error": f"{type(error).__name__}: {error}"}

    def health(self):
        return {
            "service": "IsoForm local server",
            "execution_enabled": self.execution_enabled,
            "allowed_presets": [{"id": key, "label": value["label"]} for key, value in PRESETS.items()],
            "backend": str(self.backend),
            "uma_python": str(self.uma_python),
            "prepared_batches": {"enabled": self.execution_enabled, "max_systems": MAX_SYSTEMS, "max_atoms": MAX_ATOMS},
            "preflight": self.preflight(),
            "scope": (
                "Preset exchange jobs and checked prepared-pocket batches may run. Sequences and raw "
                "structures alone are not executable UMA inputs. Pocket totals are not affinity or selectivity."
            ),
        }

    def _running(self):
        return any(job["process"].poll() is None for job in self.jobs.values())

    def start_exchange(self, preset):
        if preset not in PRESETS:
            raise ValueError("Unknown UMA preset")
        source = self.root / PRESETS[preset]["manifest"]
        manifest = copy.deepcopy(_read_json(source))
        manifest['geometry_mode'] = 'single_point'
        return self._launch(manifest, 'cyp_pipeline.exchange', 'exchange', PRESETS[preset]['label'],
                            preset=preset, extra_args=['--single-pose'], total_components=8)

    def check_batch(self, payload):
        cap = MAX_ATOMS
        if self.backend.is_file():
            config = _read_json(self.backend)
            cap = config.get('max_atoms', MAX_ATOMS)
            if type(cap) is not int or cap < 1:
                raise ValueError('Backend atom budget is invalid')
        return validate_batch(payload, cap)

    def pockets(self, job_id):
        """Display the exact snapshotted inputs of a job, never a newly fitted pose."""
        job = self.jobs.get(job_id)
        if job is None:
            raise KeyError('Unknown job')
        if job.get('kind') == 'uma_pocket_batch':
            payload = _read_json(job['input_manifest'])
            validate_batch(payload)
            return payload
        return export_exchange(job['input_manifest'])

    def start_batch(self, payload, confirm_provisional=False):
        audit = self.check_batch(payload)
        if audit['provisional'] and confirm_provisional is not True:
            raise ValueError('Confirm provisional preparation before launching this batch')
        return self._launch(payload, 'cyp_pipeline.uma_batch', 'uma_pocket_batch', payload['label'],
                            extra_args=['--allow-provisional'] if audit['provisional'] else [],
                            total_components=len(payload['systems']))

    def _launch(self, payload, module, kind, label, preset=None, extra_args=None, total_components=0):
        if not self.execution_enabled:
            raise PermissionError("UMA is disabled. Restart this server with --enable-uma.")
        if not self.uma_python.is_file() or not self.backend.is_file():
            raise ValueError("Configured UMA interpreter or backend configuration is unavailable")
        if _read_json(self.backend).get('kind') != 'uma':
            raise ValueError('Web execution requires a real UMA backend')
        with self.lock:
            if self._running():
                raise RuntimeError("A UMA job is already running; wait for it before starting another")
            job_id = uuid.uuid4().hex[:12]
            if kind == 'exchange':
                payload = copy.deepcopy(payload)
                payload['web_execution'] = {'job_id': job_id, 'mode': 'frozen_coordinate_exchange_single_point',
                                            'scope': 'Exploratory exchange descriptor, not affinity or selectivity.'}
            inputs = self.root / "runs" / "selectivity-sentinel-web-inputs" / f"{job_id}.json"
            out = self.root / "runs" / "selectivity-sentinel-web-jobs" / job_id
            inputs.parent.mkdir(parents=True, exist_ok=True)
            with inputs.open('x') as handle:
                json.dump(payload, handle, indent=2, allow_nan=False)
            command = [str(self.uma_python), '-m', module]
            if kind == 'uma_pocket_batch':
                command.append('run')
            command.extend([str(inputs), '--backend', str(self.backend), '--out', str(out), *(extra_args or [])])
            process = subprocess.Popen(
                command, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            job = {
                "id": job_id, "preset": preset, "label": label, "process": process,
                "kind": kind, "total_components": total_components,
                "command": command, "input_manifest": inputs, "out": out, "started_at": time.time(), "log": [],
            }
            self.jobs[job_id] = job
            threading.Thread(target=self._collect_output, args=(job,), daemon=True).start()
            return self.status(job_id)

    @staticmethod
    def _collect_output(job):
        for line in job["process"].stdout:
            job["log"] = (job["log"] + [line.rstrip()])[-160:]

    def status(self, job_id):
        job = self.jobs.get(job_id)
        if job is None:
            raise KeyError("Unknown job")
        code = job["process"].poll()
        result_path = job["out"] / "result.json"
        try:
            result = _read_json(result_path) if result_path.is_file() else None
        except json.JSONDecodeError:
            # The exchange runner updates this file between components. A poll
            # can land during a write; retry on the next poll without losing the job.
            if code is not None:
                raise
            result = None
        if code is None:
            state = "running"
        elif code == 0 and result is not None:
            state = "completed"
        else:
            state = "failed"
        if result and job.get('kind', 'exchange') != 'uma_pocket_batch':
            result['preference_summary'] = exchange_preference(result)
        return {
            "id": job_id, "state": state, "preset": job["preset"], "label": job["label"], "exit_code": code,
            "elapsed_seconds": round(time.time() - job["started_at"], 1), "result": result,
            "kind": job.get('kind', 'exchange'), "total_components": job.get('total_components', 8),
            "log": job["log"][-40:], "output_directory": str(job["out"].relative_to(self.root)),
            "input_manifest": str(job["input_manifest"].relative_to(self.root)),
            "scope": (
                "Real UMA calculation on supplied prepared coordinates. Exploratory potential energy, "
                "not binding affinity or selectivity validation."
            ),
        }


def make_handler(manager, site):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(site.parent), **kwargs)

        def log_message(self, format, *args):
            # Keep a small, readable access log in the terminal that owns the demo.
            print("web: " + format % args)

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def send_json(self, status, payload):
            body = json.dumps(payload, indent=2, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                # Reloading/navigating away can close a health/status request.
                pass

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/api/structures':
                return self.send_json(HTTPStatus.OK, reference_views(manager.root))
            if path.startswith('/api/input-bundles/') and path.endswith('.zip'):
                try:
                    body = bundle_zip(path.rsplit('/', 1)[-1][:-4], manager.root)
                    self.send_response(HTTPStatus.OK)
                    self.send_header('Content-Type', 'application/zip')
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Content-Disposition', 'attachment; filename="isoform-inputs.zip"')
                    self.end_headers()
                    self.wfile.write(body)
                    return
                except (OSError, ValueError, KeyError) as error:
                    return self.send_json(HTTPStatus.BAD_REQUEST, {'error': str(error)})
            if path == "/api/screen-catalog":
                return self.send_json(HTTPStatus.OK, catalog_payload(manager.catalog))
            if path == '/api/prepared-example':
                try:
                    query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
                    if set(query) - {'preset'} or len(query.get('preset', ['r_fadrozole'])) != 1:
                        raise ValueError('Only one prepared preset may be requested')
                    preset = query.get('preset', ['r_fadrozole'])[0]
                    if preset not in PRESETS:
                        raise ValueError('Unknown prepared preset')
                    return self.send_json(HTTPStatus.OK, export_exchange(manager.root / PRESETS[preset]['manifest']))
                except (OSError, ValueError, KeyError, TypeError) as error:
                    return self.send_json(HTTPStatus.BAD_REQUEST, {'error': f'Prepared example unavailable: {error}'})
            if path == "/api/health":
                return self.send_json(HTTPStatus.OK, manager.health())
            if path.startswith("/api/jobs/"):
                try:
                    if path.endswith('/pockets'):
                        return self.send_json(HTTPStatus.OK, manager.pockets(path.split('/')[-2]))
                    return self.send_json(HTTPStatus.OK, manager.status(path.rsplit("/", 1)[-1]))
                except KeyError:
                    return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown job"})
                except (OSError, ValueError, TypeError) as error:
                    return self.send_json(HTTPStatus.BAD_REQUEST, {'error': str(error)})
            if path == "/":
                self.path = "/" + site.name
            return super().do_GET()

        def do_POST(self):
            path = urlparse(self.path).path
            if path not in {"/api/jobs", "/api/screen-plan", '/api/auto-inputs', '/api/prepared-check', '/api/prepared-jobs', '/api/calibrated-selectivity'}:
                return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown API endpoint"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                limit = MAX_BYTES if path in ('/api/prepared-check', '/api/prepared-jobs') else 32768 if path in ('/api/screen-plan', '/api/auto-inputs') else 4096
                if size <= 0 or size > limit:
                    raise ValueError("Request body must be a small JSON object")
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError('Expected a JSON object')
                if path == '/api/calibrated-selectivity':
                    return self.send_json(HTTPStatus.OK, analyze_calibrated(payload))
                if path == '/api/prepared-check':
                    return self.send_json(HTTPStatus.OK, manager.check_batch(payload))
                if path == '/api/prepared-jobs':
                    if set(payload) != {'batch', 'confirm_provisional'} or type(payload['confirm_provisional']) is not bool:
                        raise ValueError('Expected batch and boolean confirm_provisional only')
                    return self.send_json(HTTPStatus.ACCEPTED, manager.start_batch(payload['batch'], payload['confirm_provisional']))
                if path == '/api/screen-plan':
                    # CPU-only, read-only planning remains available without UMA.
                    return self.send_json(HTTPStatus.OK, build_plan(payload, manager.root, manager.catalog))
                if path == '/api/auto-inputs':
                    if not manager.input_lock.acquire(blocking=False):
                        raise RuntimeError('An input build is already running. Try again shortly.')
                    try:
                        result = build_inputs(payload, manager.root, manager.catalog)
                    finally:
                        manager.input_lock.release()
                    return self.send_json(HTTPStatus.OK, result)
                if set(payload) != {"preset"} or not isinstance(payload["preset"], str):
                    raise ValueError("Only a preset identifier is accepted")
                return self.send_json(HTTPStatus.ACCEPTED, manager.start_exchange(payload["preset"]))
            except PermissionError as error:
                return self.send_json(HTTPStatus.FORBIDDEN, {"error": str(error)})
            except RuntimeError as error:
                return self.send_json(HTTPStatus.CONFLICT, {"error": str(error)})
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            except OSError as error:
                return self.send_json(HTTPStatus.BAD_REQUEST, {'error': str(error)})

    return Handler


def serve(site, port, bind, root, uma_python, backend, enable_uma, catalog=DEFAULT_CATALOG):
    site = Path(site).resolve()
    if not site.is_file() or site.suffix != ".html":
        raise ValueError("--site must be an existing HTML file")
    manager = JobManager(root, uma_python, backend, enable_uma, catalog)
    server = ThreadingHTTPServer((bind, port), make_handler(manager, site))
    print(f"Open http://{bind}:{port}/  (serving {site.name})")
    print("UMA execution is " + ("ENABLED" if enable_uma else "DISABLED; add --enable-uma to permit allow-listed jobs"))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping IsoForm server.")
    finally:
        server.server_close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=PROJECT_ROOT / 'runs/selectivity-sentinel-demo-v3/demo.html',
                        help="Generated demo.html to serve (default: bundled IsoForm demo)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--uma-python", type=Path, default=DEFAULT_UMA_PYTHON)
    parser.add_argument("--backend", type=Path, default=default_backend())
    parser.add_argument("--enable-uma", action="store_true", help="Permit preset exchange jobs and validated prepared-pocket batches")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG, help="Curated screening catalog; never authorizes extra model jobs")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    try:
        serve(args.site, args.port, args.bind, args.root, args.uma_python, args.backend, args.enable_uma, args.catalog)
        return 0
    except (OSError, ValueError) as error:
        print(f"error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Start the loopback ALCHEMI demo service without changing the original server."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

root = Path(__file__).resolve().parents[1]
runtime = root / '.venv-alchemi-agent/bin/python'
url = 'http://127.0.0.1:8001/api/health'
try:
    with socket.create_connection(('127.0.0.1', 8001), timeout=1):
        occupied = True
except OSError:
    occupied = False
if occupied:
    with urlopen(url, timeout=75) as response:
        status = json.load(response)
    if status.get('engine') != 'alchemi':
        raise SystemExit('Port 8001 belongs to another service; no process was changed.')
    print('IsoForm ALCHEMI is already running on http://127.0.0.1:8001/')
    raise SystemExit(0)
logs = root / 'runs/alchemi-integration-check'
logs.mkdir(parents=True, exist_ok=True)
with (logs/'server.log').open('a') as stream:
    process = subprocess.Popen([str(runtime), '-u', '-m', 'cyp_pipeline.agent_server'],
                               cwd=root, stdout=stream, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, start_new_session=True)
(logs/'server.pid').write_text(str(process.pid)+'\n')
for _ in range(50):
    if process.poll() is not None:
        raise SystemExit('Server failed to start; inspect runs/alchemi-integration-check/server.log')
    try:
        with socket.create_connection(('127.0.0.1', 8001), timeout=.5):
            print(json.dumps({'pid': process.pid, 'url': 'http://127.0.0.1:8001/'}))
            break
    except OSError:
        time.sleep(.2)
else:
    raise SystemExit('Startup still pending; inspect server.log before retrying.')

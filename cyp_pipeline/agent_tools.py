"""Agent client: dependency-free CLI, or MCP stdio with the optional mcp SDK."""
import argparse
import json
import os
import re
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


class IsoformClient:
    def __init__(self, base_url=None):
        self.base_url = (base_url or os.environ.get('ISOFORM_AGENT_URL', 'http://127.0.0.1:8001')).rstrip('/')
        url = urlparse(self.base_url)
        if url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost') or url.username or url.password:
            raise ValueError('Use the local service or an SSH tunnel on localhost')

    def request(self, path, payload=None):
        data = json.dumps(payload, allow_nan=False).encode() if payload is not None else None
        req = Request(self.base_url + path, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=75) as response:
                return json.load(response)
        except HTTPError as error:
            raise ValueError(f'IsoForm HTTP {error.code}: {error.read(4096).decode()}') from None

    @staticmethod
    def job_id(value):
        if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{12}', value):
            raise ValueError('Invalid job ID')
        return value

    def capabilities(self):
        return self.request('/api/health')

    def plan_screen(self, request):
        return self.request('/api/screen-plan', request)

    def start_exchange(self, preset):
        if preset not in ('r_fadrozole', 's_fadrozole'):
            raise ValueError('Only r_fadrozole and s_fadrozole have prepared exchange presets')
        return self.request('/api/jobs', {'preset': preset})

    def job_status(self, job_id):
        return self.request('/api/jobs/' + self.job_id(job_id))

    def list_jobs(self):
        return self.request('/api/agent/jobs')

    def compare(self, job_ids):
        if not isinstance(job_ids, list) or not 1 <= len(job_ids) <= 8:
            raise ValueError('Provide 1 to 8 job IDs')
        return self.request('/api/agent/compare?' + urlencode([('job_id', self.job_id(j)) for j in job_ids]))

    def suggest(self, target='CYP11B2'):
        if target not in ('CYP11B1', 'CYP11B2'):
            raise ValueError('Unknown target')
        return self.request('/api/agent/suggest?' + urlencode({'target': target}))


def mcp_server(client):
    from mcp.server.fastmcp import FastMCP
    app = FastMCP('IsoForm ALCHEMI', instructions='Prepared CYP11B1/B2 UMA tools. Read capabilities first. Energy descriptors are not binding selectivity.')

    @app.tool()
    def isoform_capabilities() -> dict:
        """Inspect runtime readiness, engine and executable prepared presets."""
        return client.capabilities()

    @app.tool()
    def isoform_plan_screen(request: dict) -> dict:
        """Plan a screen using candidate_id, target_id, optional panel_id. Does not execute."""
        return client.plan_screen(request)

    @app.tool()
    def isoform_start_exchange(preset: str) -> dict:
        """Launch real ALCHEMI/UMA for r_fadrozole or s_fadrozole. One job at a time. Returns job ID."""
        return client.start_exchange(preset)

    @app.tool()
    def isoform_job_status(job_id: str) -> dict:
        """Poll a run and retrieve results; failed/unresolved results must not be ranked."""
        return client.job_status(job_id)

    @app.tool()
    def isoform_list_jobs() -> dict:
        """List jobs submitted to this running service, including IDs and results."""
        return client.list_jobs()

    @app.tool()
    def isoform_compare(job_ids: list[str]) -> dict:
        """Compare completed matched-protocol runs, including ligand nitrogen counts and energy direction."""
        return client.compare(job_ids)

    @app.tool()
    def isoform_suggest_analogs(target: str = 'CYP11B2') -> dict:
        """Return existing analog hypotheses. Not a trained QSAR or a generative model; none are automatically simulated."""
        return client.suggest(target)

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url')
    parser.add_argument('action', choices=['mcp', 'capabilities', 'plan', 'start', 'status', 'jobs', 'compare', 'suggest'])
    parser.add_argument('arguments', nargs='*')
    args = parser.parse_args()
    client = IsoformClient(args.url)
    if args.action == 'mcp':
        mcp_server(client).run(transport='stdio')
        return
    operations = {'capabilities': lambda: client.capabilities(), 'jobs': lambda: client.list_jobs(),
                  'plan': lambda: client.plan_screen(json.loads(args.arguments[0])),
                  'start': lambda: client.start_exchange(args.arguments[0]),
                  'status': lambda: client.job_status(args.arguments[0]),
                  'compare': lambda: client.compare(args.arguments),
                  'suggest': lambda: client.suggest(args.arguments[0] if args.arguments else 'CYP11B2')}
    print(json.dumps(operations[args.action](), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()

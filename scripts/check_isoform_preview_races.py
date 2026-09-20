"""Playwright regressions for preview races; all model APIs are mocked.

No inference, model preflight, or persistent result writes are performed. The
ephemeral loopback server serves only the generated demo's static files.
"""
import asyncio
import copy
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sys
import threading
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cyp_pipeline.sentinel_server import PRESETS
from cyp_pipeline.uma_batch import export_exchange
from playwright.async_api import async_playwright


class QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class Fixture:
    def __init__(self, embedded, prepared, *, preset, preset_delay=0, pocket_delay=0,
                 disconnect=False):
        self.embedded = embedded
        self.prepared = prepared
        self.preset = preset
        self.preset_delay = preset_delay
        self.pocket_delay = pocket_delay
        self.disconnect = disconnect
        self.id = 'preview-race-fixture'
        self.snapshot = copy.deepcopy(prepared[preset])
        # A provenance marker distinguishes the immutable snapshot from the
        # current preset without modifying or inventing any atomic coordinates.
        self.snapshot['label'] += ' · immutable snapshot UI fixture'
        self.status_calls = 0
        self.pocket_calls = 0
        self.preset_replies = 0
        self.unexpected = []

    async def handle(self, route):
        request = route.request
        parsed = urlparse(request.url)
        if request.method != 'GET':
            self.unexpected.append((request.method, parsed.path))
            await route.fulfill(status=405, json={'error': 'Model execution forbidden in this test'})
        elif parsed.path == '/api/health':
            await route.fulfill(json={'execution_enabled': True, 'preflight': {
                'result': {'status': 'ready_to_load', 'device': 'cpu'}}})
        elif parsed.path == '/api/screen-catalog':
            await route.fulfill(json=self.embedded['screening'])
        elif parsed.path == '/api/structures':
            await route.fulfill(json=self.embedded['structures'])
        elif parsed.path == '/api/prepared-example':
            preset = parse_qs(parsed.query).get('preset', ['r_fadrozole'])[0]
            await asyncio.sleep(self.preset_delay)
            self.preset_replies += 1
            await route.fulfill(json=self.prepared[preset])
        elif parsed.path == f'/api/jobs/{self.id}/pockets':
            self.pocket_calls += 1
            await asyncio.sleep(self.pocket_delay)
            await route.fulfill(json=self.snapshot)
        elif parsed.path == f'/api/jobs/{self.id}':
            self.status_calls += 1
            if self.disconnect and self.status_calls == 2:
                await route.fulfill(status=503, json={'error': 'Intentional test connection interruption'})
                return
            state = 'running' if self.disconnect and self.status_calls == 1 else 'failed'
            await route.fulfill(json={
                'id': self.id, 'kind': 'exchange', 'preset': self.preset,
                'state': state, 'label': self.snapshot['label'], 'result': None,
                'elapsed_seconds': 1, 'log': ['UI fixture only; no model was executed.'],
                'output_directory': 'UI fixture only', 'total_components': 8,
            })
        else:
            self.unexpected.append((request.method, parsed.path))
            await route.fulfill(status=404, json={'error': 'Unexpected fixture endpoint'})


async def open_resumed_page(browser, base, fixture):
    context = await browser.new_context(viewport={'width': 1280, 'height': 900})
    page = await context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    await page.route('**/api/**', fixture.handle)
    await page.add_init_script('''
        window.__previewEvents = [];
        sessionStorage.setItem('sentinelJob', 'preview-race-fixture');
        document.addEventListener('sentinel:prepared', event => {
          const value = event.detail;
          window.__previewEvents.push(value ? {
            label: value.label,
            ligands: value.systems.map(system => system.ligand),
            firstPositions: value.systems.map(system => system.atoms[0].position),
          } : null);
        });
    ''')
    await page.goto(base+'?workflow=live', wait_until='domcontentloaded')
    return context, page, errors


async def assert_snapshot(page, fixture):
    await page.wait_for_function(
        "label => window.__previewEvents.at(-1)?.label === label", arg=fixture.snapshot['label'])
    latest = await page.evaluate('window.__previewEvents.at(-1)')
    assert latest['ligands'] == [system['ligand'] for system in fixture.snapshot['systems']]
    assert latest['firstPositions'] == [system['atoms'][0]['position'] for system in fixture.snapshot['systems']]
    for note in ('#structureNote', '#compareNote'):
        assert fixture.snapshot['systems'][0]['ligand'] in await page.locator(note).inner_text()
    assert await page.locator('#molecule').get_attribute('data-rendered') == 'true'
    assert await page.locator('#compareMolecule').get_attribute('data-rendered') == 'true'


async def run_checks(base, embedded, prepared):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            delayed = Fixture(embedded, prepared, preset='s_fadrozole', pocket_delay=.8)
            context, page, errors = await open_resumed_page(browser, base, delayed)
            await page.wait_for_selector('#result:not([hidden])')
            await assert_snapshot(page, delayed)
            assert await page.locator('#candidate').input_value() == 'S-fadrozole'
            assert await page.locator('#run').is_enabled()
            assert await page.locator('#energyFoldProxy').count() == 0, 'Failed model must not show a fold proxy'
            assert not errors and not delayed.unexpected
            await context.close()
            print('PASS: delayed terminal snapshot renders exact S candidate; failed run has no fold proxy', flush=True)

            late = Fixture(embedded, prepared, preset='r_fadrozole', preset_delay=2, pocket_delay=.05)
            context, page, errors = await open_resumed_page(browser, base, late)
            await page.wait_for_selector('#result:not([hidden])')
            await assert_snapshot(page, late)
            await page.wait_for_timeout(2300)
            assert late.preset_replies > 0, 'Test must actually deliver a delayed preset reply'
            await assert_snapshot(page, late)
            events = await page.evaluate('window.__previewEvents.filter(Boolean)')
            assert all(event['label'] == late.snapshot['label'] for event in events), 'Late preset replaced a job snapshot'
            assert not errors and not late.unexpected
            await context.close()
            print('PASS: delayed same-candidate preset cannot overwrite exact job snapshot', flush=True)

            resumed = Fixture(embedded, prepared, preset='r_fadrozole', disconnect=True)
            context, page, errors = await open_resumed_page(browser, base, resumed)
            await assert_snapshot(page, resumed)
            await page.wait_for_function("document.querySelector('#runStatus').textContent === 'Connection interrupted'")
            initial_pocket_calls = resumed.pocket_calls
            await page.select_option('#candidate', 'S-fadrozole')
            assert await page.evaluate('window.__previewEvents.at(-1)') is None, 'Setup must clear the previous job view'
            assert 'Resume status' in await page.locator('#run').inner_text()
            await page.locator('#run').click()
            await page.wait_for_selector('#result:not([hidden])')
            await assert_snapshot(page, resumed)
            assert resumed.pocket_calls > initial_pocket_calls, 'Resume must reload the cleared snapshot'
            assert await page.locator('#candidate').input_value() == 'R-fadrozole'
            assert not errors and not resumed.unexpected
            await context.close()
            print('PASS: interrupted job restores its snapshot after user setup changes and resume', flush=True)
        finally:
            await browser.close()


def main():
    site = ROOT / 'runs/selectivity-sentinel-demo-v3/demo.html'
    html = site.read_text()
    if 'jobPreviewPending' not in html:
        raise SystemExit('Regenerate the demo with the current sentinel.js before running this regression.')
    embedded = json.loads(re.search(r'<script id="sentinelData" type="application/json">(.*?)</script>', html, re.S)[1])
    prepared = {preset: export_exchange(ROOT / item['manifest']) for preset, item in PRESETS.items()}
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietStaticHandler, directory=str(site.parent)))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        asyncio.run(run_checks(f'http://127.0.0.1:{server.server_address[1]}/{site.name}', embedded, prepared))
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


if __name__ == '__main__':
    main()

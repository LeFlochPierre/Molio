"""Check compound discovery and design in an isolated copy of an existing starter workspace. No inference."""
import argparse
from pathlib import Path
import shutil, sys, tempfile, threading
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from molio.paths import default_project_dir
from molio.server import Handler
from molio.targets import Workspaces
from molio.proposals import ProposalStore
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',required=True,help='Existing sequence-first workspace ID, copied into temporary storage')
    parser.add_argument('--live',action='store_true',help='Also exercise real PubChem name search')
    parser.add_argument("--project-dir", type=Path, default=default_project_dir())
    args=parser.parse_args()
    source=args.project_dir/'workspaces'/args.workspace
    with tempfile.TemporaryDirectory() as folder:
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.workspaces=Workspaces(folder);server.proposal_store=ProposalStore(Path(folder)/'proposals.sqlite3')
        shutil.copytree(source,server.workspaces.directory/args.workspace)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(args=['--enable-unsafe-swiftshader']);page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}/?workspace={args.workspace}#/starter')
                page.wait_for_selector('#example-molecules-panel');page.locator('#example-molecules-panel').evaluate('e=>e.open=true')
                page.wait_for_selector('[data-add-candidate="example-anisole"]')
                page.wait_for_function("() => !document.getElementById('target-chemistry-refresh').disabled")
                assert 'No ChEMBL target link' in page.locator('#target-chemistry-status').text_content(), page.locator('#target-chemistry-status').text_content()
                assert page.locator('#starter-structure-links a').count()>0
                page.screenshot(path='/tmp/lrp1-compound-options.png',full_page=True)
                page.locator('[data-add-candidate="example-anisole"]').click()
                page.wait_for_selector('[data-design-input]')
                assert 'COc1ccccc1' in page.locator('#starter-compounds').inner_text()
                assert 'No activity on this target' in page.locator('#starter-compounds').inner_text()
                page.locator('[data-design-input]').first.click();page.wait_for_selector('.design-card')
                assert 'COc1ccccc1' in page.locator('#design-smiles').inner_text()
                page.wait_for_selector('#design-properties .smiles-code')
                page.locator('.design-card input').first.check();page.locator('#compare-designs').click()
                page.wait_for_function("() => currentPage==='runs' && selectedCandidates().length===2")
                assert page.locator('#start-experiment').is_disabled() # This isolated server has no inference worker.
                page.locator('#open-explore').click()
                if args.live:
                    page.locator('#compound-search-query').fill('caffeine');page.locator('#compound-search-button').click()
                    page.locator('[data-add-candidate="pubchem-2519"]').wait_for(timeout=60000)
                    assert 'PubChem' in page.locator('#compound-search-results').inner_text()
                    assert page.locator('#compound-search-results .smiles-code').inner_text()
                    page.locator('[data-add-candidate="pubchem-2519"]').click()
                    page.wait_for_function("() => state.data.compounds.length===2")
                    assert page.evaluate("() => state.data.compounds[1].origin.id==='pubchem-2519' && !state.data.compounds[1].observation")
                    page.locator('[data-add-candidate="pubchem-2519"]').click()
                    page.wait_for_function("() => document.getElementById('compound-import-status').textContent.includes('already')")
                    assert page.evaluate('state.data.compounds.length')==2
                page.reload();page.wait_for_selector('#example-molecules-panel');page.locator('#example-molecules-panel').evaluate('e=>e.open=true')
                page.wait_for_selector('[data-add-candidate="example-anisole"]')
                assert 'COc1ccccc1' in page.locator('#starter-compounds').inner_text()
                if args.live:assert 'Previously found' in page.locator('#compound-search-status').inner_text()
                page.set_viewport_size({'width':390,'height':844})
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                page.screenshot(path='/tmp/lrp1-compounds-mobile.png',full_page=True)
                assert not errors,errors
                browser.close();print('PASS: unlinked target, protein research, offline example import, visible SMILES, design handoff, persistence, mobile layout'+(' and live PubChem import/duplicate handling' if args.live else '')+'. No prediction started.')
        finally:
            server.shutdown();server.server_close();server.workspaces.close();thread.join()

if __name__=='__main__':main()

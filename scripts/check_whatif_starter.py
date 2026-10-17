"""Live CFTR sequence-first setup and design handoff in a temporary workspace. No inference."""
from pathlib import Path
import sys, tempfile, threading
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from molecular_lab.server import Handler
from molecular_lab.targets import Workspaces
from molecular_lab.proposals import ProposalStore
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory() as folder:
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.workspaces=Workspaces(folder);server.proposal_store=ProposalStore(Path(folder)/'proposals.sqlite3')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(args=['--enable-unsafe-swiftshader']);page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                page.wait_for_selector('#welcome-start');page.locator('#welcome-start').click()
                page.wait_for_selector('[data-workspace="brd4"]')
                page.locator('#target-query').fill('CFTR');page.locator('#target-search-button').click()
                page.locator('[data-start-target="P13569"]').wait_for(timeout=60000)
                page.locator('[data-start-target="P13569"]').click()
                page.locator('#open-imported-target').wait_for(timeout=120000);page.locator('#open-imported-target').click()
                page.wait_for_function("() => typeof navigationReady!=='undefined' && navigationReady",timeout=60000)
                assert page.evaluate("() => currentPage==='home' && state.data.assay===null && state.data.compounds.length===0"), errors
                page.locator('#open-explore').click()
                page.wait_for_selector('#starter-protein-view[data-ready=true]')
                assert page.locator('#starter-protein-view').get_attribute('data-ready')=='true',page.locator('#starter-model-status').inner_text()
                assert page.evaluate("() => !state.data.prediction_target")
                page.screenshot(path='/tmp/starter-empty-desktop.png',full_page=True)
                page.locator('#starter-domains').select_option('423:646');page.locator('#starter-region-form button').click()
                page.wait_for_function("() => state.data.prediction_target?.sequence.length===224")
                assert page.evaluate("() => state.data.prediction_target.provenance.start===423")
                page.locator('#manual-compound-entry > summary').click()
                page.locator('#starter-compound-name').fill('Example input');page.locator('#starter-smiles').fill('CCOc1ccccc1');page.locator('#starter-add-compound').click()
                page.wait_for_selector('[data-edit-input]')
                assert page.evaluate("() => state.data.compounds[0].observation===undefined")
                page.locator('[data-edit-input]').click();page.wait_for_selector('#variant-preview:not([hidden])')
                assert 'UNMEASURED INPUT' in page.locator('#variant-preview').inner_text()
                page.locator('#close-variant').click()
                page.locator('#open-designs').click();page.wait_for_selector('.design-card')
                page.locator('.design-card input').first.check();page.locator('#compare-designs').click()
                page.wait_for_function("() => currentPage==='runs' && selectedCandidates().length===2")
                assert page.locator('#start-experiment').is_disabled() # No configured model worker in this isolated check.
                assert 'Example input' in page.locator('#experiment-candidates').inner_text()
                page.locator('#open-explore').click()
                assert page.evaluate("() => currentPage==='starter'")
                page.reload();page.wait_for_function("() => typeof navigationReady!=='undefined' && navigationReady")
                assert page.evaluate("() => state.data.compounds.length===1 && state.data.prediction_target.provenance.start===423")
                page.set_viewport_size({'width':390,'height':844})
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                page.screenshot(path='/tmp/starter-mobile.png',full_page=True)
                assert not errors,errors
                browser.close();print('PASS: live CFTR search/setup, full AlphaFold model, no assay dependency, explicit region, added molecule, variant preview, design handoff, persistence and mobile layout. No inference started.')
        finally:
            server.shutdown();server.server_close();server.workspaces.close();thread.join()

if __name__=='__main__':main()

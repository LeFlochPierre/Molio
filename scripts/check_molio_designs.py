"""Browser acceptance for generated designs, proposal save, and parent-baseline handoff; no inference."""
from pathlib import Path
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from molio.server import Handler
from molio.proposals import ProposalStore
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory() as folder:
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.proposal_store=ProposalStore(Path(folder)/'proposals.sqlite3')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(args=['--enable-unsafe-swiftshader'])
                page=browser.new_page(viewport={'width':1440,'height':1100});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}/?workspace=brd4#/explore')
                page.wait_for_function('() => window.molioViewerReady === true')
                page.locator('#open-designs').click()
                page.locator('#design-parent').select_option('CHEMBL1828983')
                page.wait_for_function("() => designData?.parent_id === 'CHEMBL1828983'")
                assert page.locator('.design-card').count()==5
                page.wait_for_function("() => moleculeViewers.has('design-new-shape')")
                assert 'Ethoxy' in page.locator('#design-selected-title').inner_text()
                for i in range(3):page.locator('.design-card input').nth(i).check()
                assert page.locator('#compare-designs').is_disabled()
                page.locator('.design-card input').nth(2).uncheck()
                assert page.locator('#compare-designs').is_enabled()
                page.locator('[data-inspect-design]').nth(1).click()
                page.wait_for_function("() => moleculeViewers.has('design-new-shape')")
                page.screenshot(path='/tmp/molio-design-explorer.png')
                page.locator('#compare-designs').click()
                page.wait_for_function('() => selectedCandidates().length === 3')
                selected=page.evaluate('() => selectedCandidates().map(c=>c.id)')
                assert selected[0]=='CHEMBL1828983'
                assert 'Parent selected first' in page.locator('#experiment-message').inner_text()
                saved=server.proposal_store.list()
                assert len(saved)==2 and all(p['activity'] is None and p['design_origin'] for p in saved)
                assert set(selected[1:])=={p['id'] for p in saved}
                assert page.locator('#start-experiment').is_disabled()  # No configured worker in this fixture.
                page.locator('#close-experiments').click()
                page.set_viewport_size({'width':390,'height':844})
                page.locator('#open-designs').click()
                page.wait_for_selector('.design-card')
                assert page.locator('#designs-dialog').evaluate('(el)=>el.scrollWidth<=el.clientWidth')
                page.locator('#close-designs').click()
                page.wait_for_function("() => !moleculeViewers.has('design-new-shape')")
                assert not errors,errors
                browser.close()
                print('PASS: generated designs, 3D preview, two-design bound, persistent proposals, parent-first comparison, mobile layout and viewer cleanup')
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__=='__main__':main()

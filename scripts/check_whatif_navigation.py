"""Browser checks for page navigation, preserved drafts, closable tabs and mobile layout."""
from pathlib import Path
import sys, tempfile, threading
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from molecular_lab.server import Handler
from molecular_lab.proposals import ProposalStore
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory() as folder:
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.proposal_store=ProposalStore(Path(folder)/'proposals.sqlite3')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(args=['--enable-unsafe-swiftshader']);page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}/?workspace=brd4#/explore');page.wait_for_function('() => navigationReady')
                assert page.locator('.workspace-page:visible').count()==1
                assert not page.evaluate('() => document.documentElement.scrollWidth > innerWidth')
                page.locator('#open-designs').click();page.wait_for_selector('.design-card')
                page.locator('.design-card input').first.check()
                parent=page.locator('#design-parent').input_value()
                page.locator('#open-experiments').click();page.wait_for_selector('.run-empty')
                assert page.locator('#run-setup-panel').is_hidden()
                page.locator('#run-setup-tab').click()
                page.wait_for_selector('.experiment-choice')
                page.locator('.experiment-choice input').first.check()
                page.locator('#open-designs').click()
                assert page.locator('.design-card input').first.is_checked()
                assert page.locator('#design-parent').input_value()==parent
                page.go_back();page.wait_for_function("() => currentPage === 'runs'")
                assert page.locator('.experiment-choice input').first.is_checked()
                page.go_forward();page.wait_for_function("() => currentPage === 'design'")
                page.locator('[data-close-page="design"]').click()
                assert page.locator('#designs-dialog').is_hidden()
                assert not page.evaluate("() => moleculeViewers.has('design-new-shape')")
                page.locator('#open-explore').click();page.locator('#open-evidence').click()
                page.locator('#hypothesis').fill('Remember this question')
                page.locator('#close-evidence').click()
                page.locator('.create-variant').first.click()
                page.wait_for_function('() => latestPreview !== null')
                page.locator('#variant-name').fill('Keep this draft')
                page.locator('#open-explore').click()
                page.locator('[data-activate-page="editor"]').click()
                assert page.locator('#variant-name').input_value()=='Keep this draft'
                page.locator('#close-variant').click()
                page.locator('#open-pocket-page').click()
                assert page.locator('#viewer').bounding_box()['height']>=480
                page.locator('#surface').click();page.locator('#surface').click()
                page.locator('#surface').click()
                page.wait_for_function("() => document.getElementById('viewer').dataset.surface === 'ready'")
                assert not page.locator('#toast').is_visible()
                page.screenshot(path='/tmp/studio-pocket.png',full_page=True)
                page.reload();page.wait_for_function("() => navigationReady && currentPage === 'pocket'")
                assert page.locator('#viewer').is_visible()
                page.set_viewport_size({'width':390,'height':844})
                page.locator('#open-explore').click()
                assert not page.evaluate('() => document.documentElement.scrollWidth > innerWidth')
                page.screenshot(path='/tmp/studio-mobile.png',full_page=True)
                page.locator('#toggle-reference').click();page.locator('#open-map').click()
                assert page.locator('#activity-map').is_visible()
                assert page.locator('.workspace-page:visible').count()==1
                page.locator('#close-map').click()
                page.locator('#open-designs').click();page.wait_for_selector('.design-card')
                assert not page.evaluate('() => document.documentElement.scrollWidth > innerWidth')
                page.screenshot(path='/tmp/studio-mobile-design.png',full_page=True)
                assert not errors,errors
                browser.close();print('PASS: page routes, Back/Forward, draft/selection preservation, tab closure, 3D pocket, reload and mobile navigation')
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':main()

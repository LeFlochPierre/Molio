"""Check that the app starts with a welcome and target selection without opening a workspace."""
from pathlib import Path
import sys,tempfile,threading
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from molio.server import Handler
from molio.targets import Workspaces
from molio.proposals import ProposalStore
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory() as folder:
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.workspaces=Workspaces(folder);server.proposal_store=ProposalStore(Path(folder)/'proposals.sqlite3')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(args=['--enable-unsafe-swiftshader']);page=browser.new_page(viewport={'width':1440,'height':1000});requests=[];errors=[]
                page.on('request',lambda r:requests.append(r.url));page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                page.wait_for_selector('#welcome-start');page.locator('#welcome-start').click()
                page.wait_for_selector('[data-workspace="brd4"]')
                assert page.evaluate("() => currentPage==='targets' && state.data===null && state.viewer===null")
                # Library cards may fetch protein data for their 3D thumbnails.
                assert page.locator('#open-explore').is_hidden()
                assert 'Current' not in page.locator('[data-workspace="brd4"]').inner_text()
                page.screenshot(path='/tmp/target-first-desktop.png')
                page.set_viewport_size({'width':390,'height':844});assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                page.screenshot(path='/tmp/target-first-mobile.png')
                page.locator('[data-workspace="brd4"]').click()
                page.wait_for_function("() => typeof navigationReady!=='undefined' && navigationReady && window.molioViewerReady===true")
                assert page.evaluate("() => !targetLanding && currentPage==='home' && state.data.workspace_id==='brd4'")
                page.go_back();page.wait_for_selector('[data-workspace="brd4"]')
                assert page.evaluate("() => targetLanding && state.data===null")
                assert not errors,errors
                browser.close();print('PASS: target-first startup, no workspace opened automatically, explicit demo selection, browser Back, desktop and mobile layout')
        finally:
            server.shutdown();server.server_close();server.workspaces.close();thread.join()

if __name__=='__main__':main()

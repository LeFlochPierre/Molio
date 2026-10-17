"""Molio welcome, workspace drill-down, real loading boundaries and mobile navigation; no inference."""
from pathlib import Path
import argparse,json,shutil,sys,tempfile,threading,time
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from molio.paths import default_project_dir
from molio.server import Handler
from molio.targets import Workspaces
from molio.proposals import ProposalStore
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="Existing sequence-first workspace to copy for this check")
    parser.add_argument("--project-dir", type=Path, default=default_project_dir())
    args=parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.workspaces=Workspaces(folder);server.proposal_store=ProposalStore(Path(folder)/'proposals.sqlite3')
        workspace=args.workspace;shutil.copytree(args.project_dir/'workspaces'/workspace,server.workspaces.directory/workspace)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(args=['--enable-unsafe-swiftshader']);page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)));base=f'http://127.0.0.1:{server.server_port}'
                page.goto(base);page.wait_for_selector('#welcome-start')
                assert page.evaluate("currentPage==='welcome' && state.data===null")
                assert page.locator('.app-navigation').is_hidden();assert page.locator('#boot-screen').is_hidden()
                page.screenshot(path='/tmp/molio-welcome.png',full_page=True)
                page.locator('#welcome-start').click();page.wait_for_selector('[data-workspace="'+workspace+'"]')
                assert page.evaluate("currentPage==='targets'")
                page.screenshot(path='/tmp/molio-workspaces.png',full_page=True)
                page.go_back();page.wait_for_selector('#welcome-start');page.go_forward();page.wait_for_selector('[data-workspace="'+workspace+'"]')
                page.locator('[data-workspace="'+workspace+'"]').click();page.wait_for_function("() => typeof navigationReady!=='undefined' && navigationReady && currentPage==='home'")
                assert page.locator('#home-page').is_visible()
                # Seed an isolated copy using the actual supported example import API.
                response=page.request.post(base+'/api/starter/import-compound?workspace='+workspace,data={'id':'example-anisole'})
                assert response.ok,response.text()
                page.reload();page.wait_for_selector('[data-open-molecule] .tile-art img')
                page.mouse.move(0,0);page.wait_for_selector('.tile-motion[data-angle]')
                moving=page.locator('.tile-motion').first
                before=moving.evaluate("e=>e.toDataURL()")
                page.wait_for_timeout(400)
                assert moving.evaluate("e=>e.toDataURL()")!=before
                page.locator('[data-open-molecule]').first.hover();page.wait_for_timeout(100)
                angle=moving.get_attribute('data-angle');page.wait_for_timeout(250)
                assert moving.get_attribute('data-angle')==angle
                page.mouse.move(0,0);page.locator('#gallery-motion').click()
                assert page.evaluate('galleryMotion===null')
                angle=moving.get_attribute('data-angle');page.wait_for_timeout(200)
                assert moving.get_attribute('data-angle')==angle
                page.locator('#gallery-motion').click();page.mouse.move(0,0)
                page.wait_for_function('() => galleryMotion!==null')
                assert page.locator('.thumbnail-renderer').count()==1
                page.screenshot(path='/tmp/molio-home.png',full_page=True)
                page.locator('[data-open-molecule]').first.click();page.wait_for_selector('#detail-molecule-shape[data-ready=true]')
                assert page.evaluate("currentPage==='molecule' && galleryMotion===null")
                assert 'COc1ccccc1' in page.locator('#molecule-smiles').inner_text()
                url=page.url;page.screenshot(path='/tmp/molio-molecule.png',full_page=True)
                page.reload();page.wait_for_selector('#detail-molecule-shape[data-ready=true]')
                assert page.url==url
                page.locator('#molecule-design').click();page.wait_for_selector('.design-card')
                page.locator('#back-to-workspace').click();assert page.evaluate("currentPage==='home'")
                page.locator('#home-add').click();page.wait_for_selector('#compound-search-query')
                # Delayed failure proves the request indicator begins and clears on errors.
                def fail_search(route):
                    time.sleep(1)
                    route.fulfill(status=503,content_type='application/json',body=json.dumps({'error':'Test provider unavailable'}))
                page.route('**/api/starter/find-compounds**',fail_search)
                page.evaluate("() => {window.sawActivity=false;new MutationObserver(()=>{if(!document.getElementById('activity-tray').hidden)window.sawActivity=true;}).observe(document.getElementById('activity-tray'),{attributes:true});}")
                page.locator('#compound-search-query').fill('test');page.locator('#compound-search-button').click()
                # route callbacks block this synchronous client; inspect event-driven DOM history too.
                page.wait_for_function("() => document.getElementById('compound-search-status').textContent.includes('Test provider unavailable')")
                assert page.evaluate('window.sawActivity');assert page.locator('#activity-tray').is_hidden()
                page.unroute('**/api/starter/find-compounds**')
                # Check progress presentation with a deterministic status fixture, no model execution.
                page.evaluate("() => {clearInterval(studioPoll);studioRuns=[{status:'running',cases:[{status:'complete'},{status:'running'},{status:'queued'}]}];renderRunOverview();}")
                assert '1 of 3' in page.locator('#run-dock-detail').inner_text()
                assert page.locator('#run-dock .clay-cog').first.evaluate("e=>getComputedStyle(e).animationPlayState")=='running'
                page.locator('#open-home').click();assert page.locator('#home-active-run progress').get_attribute('value')=='1'
                page.screenshot(path='/tmp/molio-running.png',full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                page.screenshot(path='/tmp/molio-mobile.png',full_page=True)
                page.locator('[data-open-molecule]').first.click();page.wait_for_selector('#detail-molecule-shape[data-ready=true]')
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                page.locator('#close-molecule').click();assert page.evaluate("currentPage==='home'")
                # Root remains a keyboard-usable welcome with reduced motion.
                page.emulate_media(reduced_motion='reduce')
                page.wait_for_function('() => galleryMotion===null && !galleryMotionEnabled')
                assert page.locator('#run-dock .clay-cog').first.evaluate("e=>getComputedStyle(e).animationName")=='none'
                page.evaluate("() => {studioRuns=[{status:'complete',cases:[]}];renderRunOverview();}")
                assert page.locator('#run-dock').is_hidden()
                assert page.locator('#home-runs').evaluate("e=>!e.classList.contains('is-running')")
                page.goto(base);page.wait_for_selector('#welcome-start')
                page.wait_for_selector('#molio-logo-view[data-ready=true]')
                assert page.evaluate('!molioLogoSpinning')
                assert not errors,errors
                browser.close();print('PASS: welcome/Start, history, workspace hub, molecule deep link, 3D, design handoff, provider error recovery, progress presentation, mobile and reduced motion. No inference started.')
        finally:server.shutdown();server.server_close();server.workspaces.close();thread.join()

if __name__=='__main__':main()

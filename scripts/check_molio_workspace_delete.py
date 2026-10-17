"""Offline deletion UX check using temporary projects; never touches saved work."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from molio.server import Handler, ROOT
from molio.targets import Workspaces
from molio.proposals import ProposalStore
from playwright.sync_api import sync_playwright, expect


def main():
    with tempfile.TemporaryDirectory() as folder:
        manager=Workspaces(folder)
        key='lab-123456789abc'
        base=manager.directory/key/'data'
        shutil.copytree(ROOT/'data',base)
        data=json.loads((base/'dataset.json').read_text())
        data['workspace_id']=key
        (base/'dataset.json').write_text(json.dumps(data))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.workspaces=manager
        server.proposal_store=ProposalStore(Path(folder)/'proposals.sqlite3')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(args=['--enable-unsafe-swiftshader'])
                page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                page.locator('#welcome-start').click()
                button=page.locator(f'[data-delete-workspace="{key}"]')
                page.once('dialog',lambda dialog:dialog.dismiss())
                button.click()
                assert base.exists()
                assert page.locator(f'[data-workspace="{key}"]').is_visible()
                assert page.locator('[data-delete-workspace="brd4"]').count()==0
                page.set_viewport_size({'width':390,'height':844})
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                page.once('dialog',lambda dialog:dialog.accept())
                button.click()
                expect(page.locator("#project-library-status")).to_have_text("Project deleted.")
                assert not base.exists()
                assert page.locator(f'[data-workspace="{key}"]').count()==0
                page.reload()
                page.wait_for_selector('[data-workspace="brd4"]')
                assert page.locator(f'[data-workspace="{key}"]').count()==0
                assert not errors,errors
                browser.close()
                print('PASS: cancel, confirm, removal after reload, reference protection and mobile layout')
        finally:
            server.shutdown();server.server_close();manager.close();thread.join()


if __name__=='__main__':main()

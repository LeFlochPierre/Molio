"""Check target setup in a real browser. --live-import downloads public data and saves a workspace; no inference."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8001')
    parser.add_argument('--workspace',help='Existing imported workspace to inspect')
    parser.add_argument('--live-import',action='store_true',help='Search and import carbonic anhydrase II through the real public APIs')
    parser.add_argument('--screenshots',type=Path,default=Path('/tmp/whatif-targets'))
    args=parser.parse_args()
    if not args.live_import and not args.workspace:parser.error('Choose --workspace or --live-import')
    args.screenshots.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(args=['--enable-unsafe-swiftshader'])
        context=browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page();errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(args.base_url);page.wait_for_function('() => typeof navigationReady !== "undefined" && navigationReady')
        page.locator('#welcome-start').click();page.wait_for_selector('.saved-workspace')
        if args.live_import:
            page.locator('[data-search-target="carbonic anhydrase II"]').click()
            page.locator('[data-inspect-target="CHEMBL205"]').wait_for(timeout=60000)
            page.locator('[data-inspect-target="CHEMBL205"]').click()
            page.wait_for_function('() => !targetBusy',timeout=240000)
            assert page.locator('#target-preview-options').is_visible(),page.locator('#target-preview-status').inner_text()
            page.screenshot(path=str(args.screenshots/'target-preview.png'),full_page=True)
            page.locator('#import-target').click()
            page.wait_for_function('() => !targetBusy',timeout=120000)
            assert page.locator('#open-imported-target').is_visible(),page.locator('#target-setup-message').inner_text()
            workspace=page.evaluate('() => importedWorkspace')
            page.locator('#open-imported-target').click()
        else:
            workspace=args.workspace;page.goto(args.base_url+'/?workspace='+workspace)
        page.wait_for_function('() => typeof navigationReady !== "undefined" && navigationReady && window.whatifViewerReady === true')
        page.locator('#open-explore').click()
        target=page.evaluate('() => state.data.target.name')
        assert target!='BRD4 · bromodomain 1'
        assert page.locator('#comparison .molecule-canvas[data-ready=true]').count()==2
        assert page.evaluate('() => state.data.compounds.every(c=>c.observation.target_id===state.data.target.chembl_id)')
        page.screenshot(path=str(args.screenshots/'imported-explore.png'),full_page=True)
        page.locator('#open-pocket-page').click()
        assert page.evaluate('() => state.viewer.selectedAtoms(ligandSelection()).length===state.data.reference_structure.ligand_heavy_atoms')
        page.screenshot(path=str(args.screenshots/'imported-pocket.png'),full_page=True)
        page.locator('#open-designs').click();page.wait_for_selector('.design-card')
        page.locator('.design-card input').first.check();page.locator('#compare-designs').click()
        page.wait_for_function("() => currentPage==='runs' && selectedCandidates().length===2")
        page.locator('.experiment-protocol > summary').click()
        assert target in page.locator('#prediction-target-label').inner_text()
        assert page.locator('#experiment-history .experiment-run').count()==0
        assert len(page.evaluate("async () => (await (await fetch('/api/proposals')).json()).proposals"))>=1
        assert page.evaluate('() => experimentBusy') is False
        # A second tab stays on the original target; no process-global switch or notes leakage.
        other=context.new_page();other.goto(args.base_url+'/?workspace=brd4');other.wait_for_function('() => typeof navigationReady !== "undefined" && navigationReady')
        assert other.evaluate('() => state.data.workspace_id')=='brd4'
        assert other.evaluate('() => state.data.target.uniprot')=='O60885'
        other.close()
        page.locator('#welcome-start').click();page.wait_for_selector('.saved-workspace')
        page.set_viewport_size({'width':390,'height':844})
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        page.screenshot(path=str(args.screenshots/'targets-mobile.png'),full_page=True)
        page.reload();page.wait_for_function("() => typeof navigationReady !== 'undefined' && navigationReady && currentPage==='targets'")
        page.locator('[data-workspace="brd4"]').click();page.wait_for_function("() => typeof navigationReady !== 'undefined' && navigationReady && activeWorkspace==='brd4'")
        assert page.evaluate('() => state.data.target.uniprot')=='O60885'
        assert not errors,errors
        print(f'PASS: {target} ({workspace}), target setup, verified 3D, design-to-prediction handoff, isolated workspace tabs and mobile switching. No model inference started.')
        browser.close()

if __name__=='__main__':main()

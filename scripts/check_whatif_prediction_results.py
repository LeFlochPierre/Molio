"""Inspect completed real model outputs in a running app; never starts inference.

Usage: python scripts/check_whatif_prediction_results.py --url http://127.0.0.1:8001
Requires Playwright/Chromium. A completed repeated-seed experiment must exist.
"""
import argparse
import json
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8001')
    parser.add_argument('--screenshots',type=Path)
    parser.add_argument('--job',help='Inspect a specific completed experiment, including one-seed design trials')
    args=parser.parse_args()
    base=args.url.rstrip('/')
    with urlopen(base+'/api/experiments') as response:
        jobs=json.load(response)['experiments']
    job=next((j for j in jobs if j['status']=='complete' and (j['id']==args.job if args.job else len(j.get('seeds',[]))==3)),None)
    if job is None:raise SystemExit('No matching completed experiment is available; nothing was run.')
    with sync_playwright() as p:
        browser=p.chromium.launch(args=['--enable-unsafe-swiftshader'])
        page=browser.new_page(viewport={'width':1440,'height':1100})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base+'/?workspace=brd4#/explore')
        page.wait_for_function('() => window.whatifViewerReady === true')
        page.locator('#open-experiments').click()
        run=page.locator('.experiment-run').filter(has=page.locator(f'[data-export-job="{job["id"]}"]'))
        run.wait_for()
        if run.locator('.run-details').get_attribute('open') is None:run.locator('.run-details > summary').click()
        if run.locator('.individual-predictions').get_attribute('open') is None:run.locator('.individual-predictions > summary').click()
        assert run.locator('.repeat-summary tbody tr').count()==len(job['comparison']['candidates'])
        assert run.locator('[data-pose-job]').count()==len(job['cases'])
        for c in job['cases']:
            page.locator('#run-results-tab').click()
            run.locator(f'[data-case="{c["id"]}"]').click()
            page.wait_for_function("expected => moleculeViewers.get('prediction-viewer')?.viewer.selectedAtoms({chain:'L'}).length === expected",arg=c['heavy_atoms'])
            page.wait_for_function("seed => document.getElementById('prediction-provenance').textContent.includes('seed '+seed+' ·')",arg=c['seed'])
        checks=job['cases'][-1]['prediction'].get('pose_checks')
        if checks and checks.get('reference_overlay_pdb'):
            page.locator('.pose-checks-disclosure > summary').click()
            assert page.locator('#pose-checks-panel .pose-metrics').count()==1
            page.locator('#prediction-reference').check()
            assert page.evaluate("() => moleculeViewers.get('prediction-viewer').viewer.selectedAtoms({chain:'R'}).length")>0
            assert page.evaluate("() => !!moleculeViewers.get('prediction-viewer').viewer.selectedAtoms({chain:'R'})[0].style.stick")
            page.locator('#prediction-reference').uncheck()
            assert not page.evaluate("() => !!moleculeViewers.get('prediction-viewer').viewer.selectedAtoms({chain:'R'})[0].style.stick")
            page.locator('#pose-checks-panel summary').click()
            page.locator('[data-pose-residue]').first.click()
            assert 'UniProt numbering' in page.locator('#prediction-hover').inner_text()
            if args.screenshots:
                args.screenshots.mkdir(parents=True,exist_ok=True)
                page.locator('#pose-checks-panel').scroll_into_view_if_needed()
                page.screenshot(path=str(args.screenshots/'pose-diagnostics.png'))
        page.locator('#run-results-tab').click()
        with page.expect_download() as download:
            run.locator('[data-export-job]').click()
        exported=json.loads(Path(download.value.path()).read_text())
        assert exported['comparison']==job['comparison']
        assert exported.get('seeds',[exported['settings']['seed']])==job.get('seeds',[job['settings']['seed']])
        assert len(exported['checkpoints'])==2
        if args.screenshots:
            args.screenshots.mkdir(parents=True,exist_ok=True)
            run.locator('.repeat-summary').scroll_into_view_if_needed()
            page.screenshot(path=str(args.screenshots/'repeat-results.png'))
        page.locator('#close-experiments').click()
        page.wait_for_function("() => !moleculeViewers.has('prediction-viewer')")
        page.set_viewport_size({'width':390,'height':844})
        page.locator('#open-experiments').click()
        run.wait_for()
        assert page.locator('#experiments-dialog').evaluate('(el) => el.scrollWidth <= el.clientWidth')
        assert not errors,errors
        browser.close()
        print(f'PASS: {len(job["cases"])} real predicted complexes, seed labels, repeat summary, available geometry checks/overlay, export, viewer cleanup and mobile layout. Run {job["id"]}')


if __name__=='__main__':main()

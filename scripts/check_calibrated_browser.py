"""Exercise the real energy-to-fold API and UI, without any model inference."""
import json
from pathlib import Path
import sys
import threading
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cyp_pipeline.sentinel_server import JobManager, make_handler, DEFAULT_UMA_PYTHON, default_backend
from playwright.sync_api import sync_playwright


def main():
    manager = JobManager(ROOT, DEFAULT_UMA_PYTHON, default_backend(ROOT), False)
    handler = make_handler(manager, ROOT/'runs/selectivity-sentinel-demo-v3/demo.html')
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width':1440,'height':1080})
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            base=f'http://127.0.0.1:{server.server_port}'
            page.goto(base)
            page.wait_for_selector('#compareMolecule[data-rendered=true]')
            assert page.locator('#mode').input_value()=='calibrated'
            for canvas in ('#molecule','#compareMolecule'):
                pixels=page.locator(canvas).evaluate('(c)=>Array.from(c.getContext("2d").getImageData(0,0,c.width,c.height).data).filter((v,i)=>i%4===3&&v>0).length')
                assert pixels>1000
            page.locator('#run').click()
            page.wait_for_selector('#calibratedFold')
            assert page.locator('#calibratedFold').inner_text()=='3.23×'
            assert 'Below the illustrative 10×' in page.locator('#calVerdict').inner_text()
            assert '33.93× IC50' in page.locator('#result').inner_text()
            assert 'Retrospective fit' in page.locator('#result').inner_text()
            page.select_option('#calibratedCandidate','baxdrostat')
            assert page.locator('#result').is_hidden(), 'Changing candidates must clear stale results'
            page.locator('#run').click();page.wait_for_selector('#calibratedFold')
            assert page.locator('#calibratedFold').inner_text()=='103.36×'
            assert 'Above the illustrative 10×' in page.locator('#calVerdict').inner_text()
            with page.expect_download() as download:
                page.locator('#downloadCalibrated').click()
            result=json.loads(Path(download.value.path()).read_text())
            assert result['candidate_id']=='baxdrostat'
            assert result['execution']['new_UMA_inference'] is False
            assert result['overall_status']=='unresolved'
            assert result['empirical_fit']['S_B1_over_B2']>100
            page.locator('#calComponents summary').click()
            assert '-609267.3114368811' in page.locator('#calComponents').inner_text()
            page.screenshot(path='/tmp/isoform-calibrated-desktop.png',full_page=True)
            page.select_option('#posePolicy','original_minima');page.locator('#run').click()
            page.wait_for_selector('#calibratedFold')
            assert page.locator('#calibratedFold').inner_text()=='5.86×'
            assert 'Below the illustrative 10×' in page.locator('#calVerdict').inner_text()
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.body.scrollWidth<=innerWidth')
            page.screenshot(path='/tmp/isoform-calibrated-mobile.png',full_page=True)
            page.select_option('#calibratedCandidate','metyrapone');page.locator('#run').click()
            page.wait_for_selector('#result:not([hidden])')
            assert page.locator('#calibratedFold').count()==0
            assert 'No reliable fold to report' in page.locator('#result').inner_text()
            assert page.request.post(base+'/api/calibrated-selectivity',data={'candidate_id':'r_fadrozole','pose_policy':'selected_fit'}).status==400
            assert not errors,errors
            assert not manager.jobs,'Reanalysis must never start UMA'
            browser.close()
            print('PASS: real API arithmetic, both fitted ratios, original minima, convergence gate, JSON export, mobile layout, both 3D canvases; zero UMA jobs')
    finally:
        server.shutdown();server.server_close()


if __name__=='__main__':
    main()

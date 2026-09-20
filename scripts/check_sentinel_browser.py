"""Browser regression checks. Requires the optional Playwright test dependency.

Use --live for a real R-fadrozole UMA CPU exchange or --live-batch for the new
two-pocket CPU batch. Default checks never launch a model calculation.
"""
import argparse
import json
from pathlib import Path
import sys
import threading
import zipfile
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cyp_pipeline.sentinel_server import JobManager, make_handler, DEFAULT_UMA_PYTHON, default_backend
from cyp_pipeline.interpretation import exchange_preference
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--live-batch', action='store_true', help='Run a real CPU UMA prepared-pocket batch')
    args = parser.parse_args()
    site = ROOT / 'runs/selectivity-sentinel-demo-v3/demo.html'
    manager = JobManager(ROOT, DEFAULT_UMA_PYTHON, default_backend(ROOT), args.live or args.live_batch)
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(manager, site))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_address[1]}'
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width':1440,'height':1050}, device_scale_factor=2)
            errors=[]
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base+'?workflow=live')
            page.wait_for_selector('#molecule[data-rendered=true]')
            page.wait_for_selector('#compareMolecule[data-rendered=true]')
            page.wait_for_function("document.querySelector('#structureNote').textContent.includes('R-fadrozole') && document.querySelector('#structureNote').textContent.toLowerCase().includes('prepared')")
            assert page.evaluate('document.body.scrollWidth <= innerWidth')
            pixels=page.evaluate('''() => {
                const canvas=document.querySelector('canvas');
                const pixels=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
                let count=0;for(let i=3;i<pixels.length;i+=4)if(pixels[i]>0)count++;
                return count;
            }''')
            assert pixels>1000, f'Protein did not draw: {pixels} nontransparent pixels'
            initial=page.locator('#molecule').evaluate('(canvas)=>canvas.toDataURL()')
            page.locator('#molecule').focus();page.keyboard.press('ArrowLeft')
            page.wait_for_timeout(100)
            assert initial != page.locator('#molecule').evaluate('(canvas)=>canvas.toDataURL()'), 'Rotation did not redraw'
            assert page.title().startswith('IsoForm')
            assert page.locator('#mode').input_value() == 'live'
            assert 'CYP11B1' in page.locator('#compareProteinTitle').inner_text()
            assert 'R-fadrozole' in page.locator('#compareNote').inner_text()
            compare_pixels=page.locator('#compareMolecule').evaluate('(c)=>Array.from(c.getContext("2d").getImageData(0,0,c.width,c.height).data).filter((v,i)=>i%4===3&&v>0).length')
            assert compare_pixels>1000
            page.select_option('#candidate','S-fadrozole')
            page.wait_for_function("document.querySelector('#structureNote').textContent.includes('S-fadrozole') && document.querySelector('#compareNote').textContent.includes('S-fadrozole')")
            page.select_option('#candidate','R-fadrozole')
            page.wait_for_function("document.querySelector('#structureNote').textContent.includes('R-fadrozole')")
            page.screenshot(path='/tmp/isoform-pair-desktop.png',full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.body.scrollWidth <= innerWidth')
            page.screenshot(path='/tmp/isoform-pair-mobile.png',full_page=True)
            page.set_viewport_size({'width':1440,'height':1050})
            page.select_option('#mode','plan')
            observed = set()
            for target, pdb in [('CYP11B2','4FDH'), ('CYP11B1','6M7X'), ('CYP11A1','3N9Y'), ('CYP17A1','3RUK'), ('CYP19A1','3EQM')]:
                page.select_option('#planTarget', target)
                assert target in page.locator('#proteinTitle').inner_text()
                assert pdb in page.locator('#viewChip').inner_text()
                page.wait_for_timeout(60)
                observed.add(page.locator('#molecule').evaluate('(canvas)=>canvas.toDataURL()'))
            assert len(observed) == 5, 'Targets must have distinct coordinate renders'
            page.select_option('#planTarget','custom')
            assert page.locator('#molecule').is_hidden(), 'Custom sequence must not show a different protein'
            assert 'No structure available' in page.locator('#viewerError').inner_text()
            page.select_option('#planTarget','CYP11B2')
            page.locator('#run').click();page.wait_for_selector('#downloadInputs',timeout=60000)
            assert '5 proteins' in page.locator('#result h2').inner_text()
            assert page.locator('.readiness-row:not(.readiness-head)').count()==5
            assert '5 Boltz pose inputs' in page.locator('#result').inner_text()
            assert '2 existing UMA preparations' in page.locator('#result').inner_text()
            with page.expect_download() as download_event:
                page.locator('#downloadInputs').click()
            with zipfile.ZipFile(download_event.value.path()) as archive:
                manifest=json.loads(archive.read('manifest.json'))
                assert manifest['summary']['new_predictions']==0
                assert len([x for x in archive.namelist() if x.endswith('.yaml')])==5
            page.locator('[data-view-target=CYP19A1]').click()
            assert '3EQM' in page.locator('#viewChip').inner_text()
            page.wait_for_function("!document.querySelector('#run').disabled")
            assert '3EQM' in page.locator('#viewChip').inner_text(), 'Library refresh must preserve the selected view'
            assert not manager.jobs, 'Input building must never start a model job'
            page.screenshot(path='/tmp/isoform-inputs-desktop.png',full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.body.scrollWidth <= innerWidth')
            page.screenshot(path='/tmp/isoform-inputs-mobile.png',full_page=True)
            page.set_viewport_size({'width':1440,'height':1050})
            page.select_option('#mode','reference');page.select_option('#candidate','Osilodrostat (LCI699)')
            page.locator('[data-protein=CYP11B1]').click();page.locator('#pocket').click()
            assert 'CYP11B1' in page.locator('#proteinTitle').inner_text()
            assert '6M7X' in page.locator('#structureNote').inner_text()
            page.locator('#run').click()
            assert page.locator('#result h2').inner_text() == 'Below the selectivity threshold'
            page.select_option('#candidate','Baxdrostat');page.locator('#run').click()
            assert page.locator('#result h2').inner_text() == 'Meets the assay threshold'
            assert 'model disagrees' in page.locator('#result').inner_text()
            page.select_option('#candidate','S-fadrozole');page.locator('#run').click()
            assert 'Not interpretable' in page.locator('#result').inner_text()
            assert 'preference for CYP11B1' in page.locator('#result').inner_text()
            assert 'Chirality flag' in page.locator('#steps').inner_text()
            page.select_option('#candidate','new');page.locator('#candidateName').fill('Unprepared candidate')
            page.locator('#run').click();assert 'More evidence needed' in page.locator('#result h2').inner_text()
            page.locator('#sequence').fill('ZZZ');page.locator('#run').click()
            assert page.locator('#result').is_hidden()
            assert 'Check the target sequence' in page.locator('#runStatus').inner_text()
            page.reload();page.wait_for_selector('#molecule[data-rendered=true]')
            page.screenshot(path='/tmp/sentinel-desktop-verified.png', full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            page.locator('#whole').click();page.wait_for_timeout(100)
            assert page.evaluate('document.body.scrollWidth <= innerWidth')
            page.screenshot(path='/tmp/sentinel-mobile-verified.png', full_page=True)
            # A usable static protein is present even with all scripts disabled.
            static=browser.new_context(java_script_enabled=False)
            fallback=static.new_page();fallback.goto(base)
            assert fallback.locator('#structureFallback svg').is_visible()
            static.close()
            print(f'PASS: 3D pixels={pixels}, rotation, B1/B2, reference decisions, input validation, mobile, no-JS fallback',flush=True)
            # UI failure-path fixture: this page never reaches the real job API.
            failure_page=browser.new_page()
            failure_page.route('**/api/health',lambda route:route.fulfill(json={
                'execution_enabled':True,'preflight':{'result':{'status':'ready_to_load','device':'cpu'}}}))
            failure_page.route('**/api/jobs',lambda route:route.fulfill(status=202,json={'id':'ui-failure-fixture','state':'running'}))
            failure_page.route('**/api/jobs/ui-failure-fixture',lambda route:route.fulfill(json={
                'id':'ui-failure-fixture','state':'failed','preset':'r_fadrozole','label':'R-fadrozole',
                'elapsed_seconds':1,'log':['Test fixture: calculation failed'],
                'result':None,'output_directory':'test fixture only','scope':'UI test; no scientific calculation.'}))
            failure_page.goto(base+'?workflow=live')
            failure_page.wait_for_function("document.querySelector('#connection').textContent.includes('UMA connected')")
            failure_page.select_option('#candidate','R-fadrozole');failure_page.select_option('#mode','live')
            failure_page.locator('#run').click()
            failure_page.wait_for_selector('#result:not([hidden])')
            assert failure_page.locator('#result h2').inner_text()=='Calculation needs attention'
            assert failure_page.locator('#steps .failed').count()==1
            assert failure_page.locator('#run').is_enabled()
            failure_page.close()
            print('PASS: failed-job UI shows failure and re-enables controls',flush=True)
            # Arithmetic-only UI fixtures: explicit proxy, never binding selectivity.
            for delta, title in [(-.2,'UMA exchange favors CYP11B2'),(.2,'UMA exchange favors CYP11B1'),(0,'No exchange-energy difference')]:
                signal_page=browser.new_page()
                signal_page.route('**/api/health',lambda route:route.fulfill(json={'execution_enabled':True,'preflight':{'result':{'status':'ready_to_load','device':'cpu'}}}))
                signal_page.route('**/api/jobs',lambda route:route.fulfill(status=202,json={'id':'signal-test','state':'running'}))
                result={'status':'exploratory','synthetic':False,'descriptor':'ligand_water_exchange_eV','delta_B2_minus_B1_eV':delta,'enzymes':{}}
                for protein, value in [('CYP11B1',0.),('CYP11B2',delta)]:
                    result['enzymes'][protein]={'exchange_energy_eV':value,'components':{component:{'status':'completed','energy_eV':value if component=='cluster_ligand' else 0.} for component in ['cluster_ligand','free_water','cluster_water','free_ligand']}}
                result['preference_summary']=exchange_preference(result)
                signal_page.route('**/api/jobs/signal-test',lambda route, _request, result=result:route.fulfill(json={'id':'signal-test','state':'completed','preset':'r_fadrozole','result':result,'log':[],'elapsed_seconds':1,'scope':'Test fixture only'}))
                signal_page.goto(base+'?workflow=live');signal_page.wait_for_function("document.querySelector('#connection').textContent.includes('UMA connected')")
                signal_page.select_option('#mode','live');signal_page.locator('#run').click()
                signal_page.wait_for_selector('#downloadExchangeResult')
                assert signal_page.locator('#result h2').inner_text()==title
                assert signal_page.locator('#energyFoldProxy').inner_text() != 'Unavailable'
                assert 'Not binding selectivity' in signal_page.locator('.proxy-scope').inner_text()
                assert 'Exploratory only' in signal_page.locator('#result').inner_text()
                if delta==0: assert signal_page.locator('#energyFoldProxy').inner_text()=='1×'
                signal_page.close()
            print('PASS: 5 structures, automatic ZIP, actual R/S paired pockets, B1/B2 direction and explicitly hypothetical fold proxy',flush=True)
            # Real CPU planning endpoint; no mocks, model jobs or GPU required.
            page.set_viewport_size({'width':1440,'height':1050})
            page.select_option('#candidate','R-fadrozole');page.select_option('#mode','plan')
            page.locator('#planSettings details').evaluate('(e)=>e.open=true')
            page.locator('#checkPlan').click();page.wait_for_selector('#downloadPlan')
            assert page.locator('#result h2').inner_text()=='2 UMA pockets prepared'
            assert page.locator('.screen-row').count()==5
            assert page.locator('.screen-state').filter(has_text='Prepared inputs available').count()==2
            assert 'No model was launched' in page.locator('#result').inner_text()
            with page.expect_download() as download_event:
                page.locator('#downloadPlan').click()
            artifact=json.loads(Path(download_event.value.path()).read_text())
            assert artifact['summary']['new_predictions']==0 and len(artifact['targets'])==5
            page.screenshot(path='/tmp/sentinel-screen-plan-desktop.png',full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.body.scrollWidth <= innerWidth')
            page.screenshot(path='/tmp/sentinel-screen-plan-mobile.png',full_page=True)
            page.select_option('#planTarget','CYP19A1');page.locator('#checkPlan').click()
            page.wait_for_selector('#downloadPlan')
            assert page.locator('.screen-state').filter(has_text='Prepared inputs available').count()==0
            page.select_option('#candidate','new')
            page.locator('#candidateName').fill('R-fadrozole')
            page.locator('#planSmiles').fill('CCO')
            page.select_option('#planTarget','custom')
            page.locator('#planSequence').fill('A'*60)
            page.locator('#checkPlan').click();page.wait_for_selector('#downloadPlan')
            assert page.locator('.screen-row').count()==6
            assert page.locator('.screen-state').filter(has_text='Prepared inputs available').count()==0
            assert page.evaluate('document.body.scrollWidth <= innerWidth')
            page.locator('#planSequence').fill('invalid');page.locator('#checkPlan').click()
            page.wait_for_function("document.querySelector('#runStatus').textContent==='Check planning inputs'")
            assert page.locator('#result').is_hidden() and page.locator('#run').is_enabled()
            for payload in ([], {'candidate_id':'r_fadrozole','target_id':'CYP11B2','command':'unrecognized'}):
                assert page.request.post(base+'/api/screen-plan',data=payload).status==400
            assert not manager.jobs, 'Planning must not launch any model jobs'
            print('PASS: real CPU panel planning, JSON export, custom inputs, invalid-input API, mobile, zero model jobs',flush=True)
            # Real prepared input checks and uploaded-coordinate viewer; no model job.
            page.set_viewport_size({'width':1440,'height':1050})
            page.select_option('#mode','batch');page.locator('#batchExample').click()
            page.wait_for_function("document.querySelector('#runLabel').textContent==='Run UMA · 2 pockets'")
            assert page.locator('#result h2').inner_text()=='2 pockets checked'
            assert 'prepared pocket' in page.locator('#proteinTitle').inner_text().lower()
            assert 'R-fadrozole' in page.locator('#structureNote').inner_text()
            assert page.locator('#candidateSettings').is_hidden()
            assert page.locator('#batchFile').input_value()==''
            page.locator('#run').click()
            assert 'Confirm' in page.locator('#formFeedback').inner_text()
            assert not manager.jobs
            page.screenshot(path='/tmp/sentinel-prepared-desktop.png',full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.body.scrollWidth <= innerWidth')
            page.screenshot(path='/tmp/sentinel-prepared-mobile.png',full_page=True)
            # Bad file must clear the prior usable audit and restore the reference viewer.
            page.locator('#batchFile').set_input_files({'name':'invalid.json','mimeType':'application/json','buffer':b'{"kind":"raw_pdb"}'})
            page.wait_for_function("document.querySelector('#runStatus').textContent==='Preparation required'")
            assert page.locator('#result').is_hidden()
            assert 'reference structure' in page.locator('#proteinTitle').inner_text()
            # Arbitrary IDs work only with full inputs. This checks plumbing, not new chemistry.
            payload=page.request.get(base+'/api/prepared-example').json()
            payload['systems'][0]['protein_id']='GENERIC_ID_TEST_ONLY'
            response=page.request.post(base+'/api/prepared-check',data=payload)
            assert response.status==200 and response.json()['systems'][0]['protein_id']=='GENERIC_ID_TEST_ONLY'
            assert page.request.post(base+'/api/prepared-jobs',data={'batch':payload,'confirm_provisional':False}).status==400
            assert not manager.jobs
            print('PASS: prepared-pocket upload, geometry/state checks, actual-coordinate viewer, confirmation gate, arbitrary-ID routing',flush=True)
            if args.live_batch:
                page.set_viewport_size({'width':1440,'height':1050})
                page.wait_for_function("document.querySelector('#connection').textContent.includes('UMA connected')",timeout=40000)
                page.locator('#batchExample').click()
                page.wait_for_function("document.querySelector('#runLabel').textContent==='Run UMA · 2 pockets'")
                page.locator('#provisionalConfirm').check();page.locator('#run').click()
                print('Started real UMA CPU batch via browser; waiting for result.',flush=True)
                page.wait_for_selector('#downloadBatchResult',timeout=600000)
                batch_job=list(manager.jobs.values())[-1]
                result=json.loads((batch_job['out']/'result.json').read_text())
                assert result['synthetic'] is False and result['status']=='exploratory',result.get('reasons')
                assert len(result['systems'])==2 and all(s['status']=='completed' for s in result['systems'])
                assert page.locator('#result h2').inner_text()=='Calculation complete'
                assert 'Do not rank proteins' in page.locator('#result').inner_text()
                page.screenshot(path='/tmp/sentinel-prepared-live.png',full_page=True)
                print('PASS: real browser → generic batch API → UMA CPU → two pocket results',batch_job['out'],flush=True)
            page.reload();page.wait_for_selector('#molecule[data-rendered=true]')
            if args.live:
                page.set_viewport_size({'width':1440,'height':1050})
                page.wait_for_function("document.querySelector('#connection').textContent.includes('UMA connected')",timeout=30000)
                page.select_option('#candidate','R-fadrozole');page.select_option('#mode','live')
                page.locator('#run').click()
                print('Started actual UMA run via browser; waiting for artifact.',flush=True)
                page.wait_for_selector('#activity:not([hidden])')
                page.screenshot(path='/tmp/isoform-live-progress.png',full_page=True)
                page.wait_for_function("document.querySelector('#result:not([hidden])') !== null",timeout=600000)
                print(page.locator('#result').inner_text(),flush=True)
                job=next(iter(manager.jobs.values()))
                result=json.loads((job['out']/'result.json').read_text())
                assert result['synthetic'] is False and result['status']=='exploratory', result.get('reasons')
                assert page.locator('#result h2').inner_text()=='UMA exchange favors CYP11B2'
                proxy=result['preference_summary']['energy_fold_proxy']
                assert proxy['status']=='hypothetical_energy_proxy' and proxy['extreme_magnitude']
                assert result['preference_summary']['fold_selectivity'] is None
                assert page.locator('#energyFoldProxy').inner_text()!='Unavailable'
                assert page.locator('.proxy-warning').is_visible()
                assert 'Not binding selectivity' in page.locator('.proxy-scope').inner_text()
                assert len(page.locator('#steps .done').all())==4
                page.screenshot(path='/tmp/isoform-live-result.png',full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.body.scrollWidth <= innerWidth')
                page.screenshot(path='/tmp/isoform-live-result-mobile.png',full_page=True)
                print('PASS: real browser → API → UMA → result',job['out'],flush=True)
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown();server.server_close()


if __name__=='__main__':
    main()

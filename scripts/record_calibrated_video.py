"""Record the real energy-to-fold app: supplied UMA outputs, no new inference.

Reuses the actual browser recorder and H.264 encoder; all visible quantities
come from the real API. Selected and original-minimum results remain distinct.
"""
import argparse
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cyp_pipeline.sentinel_server import JobManager, make_handler, DEFAULT_UMA_PYTHON, default_backend
from playwright.sync_api import sync_playwright
from record_isoform_video import Recorder, encode, RECORDING_CSS, WIDTH, HEIGHT, PRESENTATION

CSS=RECORDING_CSS+'''
.calibrated-result{padding:22px 30px}.cal-fold{font-size:77px}.cal-hero{padding:16px 0;gap:25px}
.cal-hero p{font-size:13px!important;margin:10px 0 0}.cal-energy-path{padding:15px 22px}
.cal-equation strong{font-size:25px}.cal-equation small{font-size:13px}.cal-verdict{margin:17px 0;padding:13px 20px;font-size:14px}
.cal-bottom-grid{margin:19px 0;gap:30px}.cal-bottom-grid h3{font-size:16px}.cal-comparison-row{margin:12px 0}
.cal-comparison-row b{font-size:13px}.cal-comparison-row small{font-size:11px}.cal-sensitivity{padding:18px}
.calibrated-result .field-note{font-size:12px!important}.cal-table-scroll table{font-size:12px}
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--encode-only',type=Path)
    args=parser.parse_args()
    if args.encode_only:
        saved=json.loads((args.encode_only/'recording.json').read_text())
        print(encode(args.encode_only,saved['scenes']));return
    output=(args.out or ROOT/'runs/isoform-video'/('energy-fold-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))).resolve()
    output.mkdir(parents=True,exist_ok=False)
    manager=JobManager(ROOT,DEFAULT_UMA_PYTHON,default_backend(ROOT),False)
    original=make_handler(manager,ROOT/'runs/selectivity-sentinel-demo-v3/demo.html')
    class Handler(original):
        def log_message(self,*_):pass
        def do_GET(self):
            if self.path=='/__presentation__':
                body=PRESENTATION.read_bytes()
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            else:super().do_GET()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    provenance={'created_utc':datetime.now(timezone.utc).isoformat(),'width':WIDTH,'height':HEIGHT,'fps':30,
                'audio':'none; burned-in presentation captions','source':'actual local IsoForm browser and API',
                'new_UMA_inference':False,'source_energies':'User-supplied team handoff dated 2026-09-20',
                'scientific_scope':'Retrospective two-compound fit; pose robustness unresolved; no superiority claim.',
                'presentation_only_changes':'Reflow CSS, cursor, editorial captions, scene pacing; no mocked endpoints or results',
                'results':[]}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch()
            context=browser.new_context(viewport={'width':WIDTH,'height':HEIGHT},device_scale_factor=1)
            page=context.new_page();errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}/__presentation__')
            # A focused element inside an iframe can scroll an overflow:hidden
            # ancestor programmatically. Clip keeps the recording stage fixed.
            page.add_style_tag(content='html,body{overflow:clip}')
            inner=page.frames[1]
            inner.locator('#molecule[data-rendered=true]').wait_for()
            inner.locator('#compareMolecule[data-rendered=true]').wait_for()
            inner.add_style_tag(content=CSS)
            recorder=Recorder(page,inner,output)
            page.evaluate("setScene({title:'From eV to fold preference.',caption:'Supplied UMA outputs · Traceable conversion · Experimental cross-check',badge:'Retrospective calibration',chapter:0})")
            page.evaluate('''() => {
              document.querySelector('#coverEyebrow').textContent='IsoForm / Energy to selectivity insight';
              document.querySelector('#coverTitle').innerHTML='From eV<br>to fold preference.';
              document.querySelector('#coverText').innerHTML='Trace the energy. Compare the signal.<br>Choose the next experiment.';
              document.querySelector('#coverPills').innerHTML='<span>UMA exchange energies</span><span>Empirical calibration</span><span>Experimental cross-check</span>';
              document.querySelector('#coverSmall').textContent='Supplied UMA outputs · Retrospective fit · Not an independent prediction';
            }''')
            page.evaluate('setCover(false)');page.wait_for_timeout(700)
            recorder.still('poster')
            print(f'OUTPUT {output}',flush=True)
            if args.preview:
                inner.locator('#run').click();inner.locator('#calibratedFold').wait_for()
                inner.locator('#result').evaluate('e=>window.scrollTo(0,window.scrollY+e.getBoundingClientRect().top-16)')
                page.wait_for_timeout(600)
                recorder.still('result-preview');browser.close();return

            def calculate(expected):
                with page.expect_response(lambda r:r.url.endswith('/api/calibrated-selectivity') and r.request.method=='POST') as response:
                    inner.locator('#run').click()
                result=response.value.json()
                assert response.value.status==200
                assert result['execution']['new_UMA_inference'] is False
                inner.locator('#result:not([hidden])').wait_for()
                if expected:assert inner.locator('#calibratedFold').inner_text()==expected
                provenance['results'].append(result)
                return result

            page.evaluate('setCover(true)')
            recorder.start('01-intro',3,'From eV to fold preference.',
                           'A real analysis workflow using the team’s supplied UMA outputs.','Retrospective calibration',0)
            recorder.hold(3)

            recorder.start('02-inputs',5,'01 / Choose a molecule and trace its energy inputs.',
                           'Osilodrostat · B2 target / B1 counter-screen · Team-selected poses','Supplied UMA energies / No new inference',0)
            page.evaluate('setCover(false)');recorder.focus('#calibratedSettings');recorder.point('#calibratedCandidate');recorder.hold(2.5);recorder.focus()

            recorder.start('03-structures',4,'02 / Inspect the protein reference pockets.',
                           'Experimental reference coordinates—not the selected relaxed drug poses.','Interactive 3D / References only',1)
            recorder.point('#rotate',click=True)
            inner.locator('#molecule').focus();page.keyboard.press('+')
            inner.locator('#compareMolecule').focus();page.keyboard.press('+')
            page.evaluate('hidePointer()');recorder.hold(2.7)
            recorder.still('reference-pockets')

            recorder.start('04-calculate',5,'03 / Recompute the exchange. Apply the fitted conversion.',
                           'X = E(cluster + ligand) + E(water) − E(cluster + water) − E(ligand)','Real backend calculation / No new UMA run',2)
            recorder.focus('#run');recorder.point('#run');calculate('3.23×');recorder.focus()
            recorder.scroll('.pipeline');recorder.hold(2.6)

            recorder.start('05-energy',6,'Four energy terms per enzyme. One matched difference.',
                           'Osilodrostat: X(B1) − X(B2) = +0.238037 eV. Positive favors B2 in this model.','Full-precision exchange arithmetic',2)
            recorder.focus('#calEnergyPath');recorder.hold(2)
            recorder.focus('.cal-equation');recorder.hold(2.6);recorder.focus()
            recorder.still('osilodrostat-fit')

            recorder.start('06-osilodrostat',5,'3.23× fitted B2 preference. Below the 10× screen.',
                           'O01 experimental IC50 ratio: 3.57×. This was a training target, not a held-out validation.','Osilodrostat / Retrospective fit',3)
            recorder.focus('#calVerdict');recorder.hold(2)
            recorder.focus('#calibratedFold');recorder.hold(2);recorder.focus()

            inner.select_option('#calibratedCandidate','baxdrostat');calculate('103.36×')
            recorder.start('07-baxdrostat',7,'103.36× fitted B2 preference. A stronger fitted signal.',
                           'B01 experimental Ki ratio: 100.77×. The same fitted coefficient is used for both compounds.','Baxdrostat / Retrospective fit',3)
            recorder.scroll('#result');recorder.focus('#calibratedFold');recorder.hold(2)
            recorder.focus('.cal-equation');recorder.hold(2);recorder.focus()
            with page.expect_download() as download:inner.locator('#downloadCalibrated').click()
            download.value.save_as(output/'baxdrostat-selected-fit.json')
            recorder.scroll('#result');recorder.hold(1.2);recorder.still('baxdrostat-fit')

            recorder.start('08-crosscheck',5,'04 / Compare models—and keep their provenance visible.',
                           'Boltz seeds: 1.87× / 1.69×. Uncalibrated Boltz vs fitted UMA is not an accuracy ranking.','Cross-check / Ki remains distinct from IC50',4)
            recorder.scroll('.cal-bottom-grid');recorder.focus('.cal-bottom-grid>section:first-child');recorder.hold(3.8);recorder.focus();recorder.still('model-crosscheck')

            inner.select_option('#posePolicy','original_minima');calculate('5.86×')
            recorder.start('09-sensitivity',6,'Pose choice matters: 103.36× becomes 5.86×.',
                           'Original baxdrostat minima, same coefficient. The fitted screen flips; pose robustness stays unresolved.','Sensitivity check / Not validated selectivity',4)
            recorder.scroll('#result');recorder.focus('#calibratedFold');recorder.hold(2)
            recorder.focus('#calSensitivity');recorder.hold(2.5);recorder.focus();recorder.still('pose-sensitivity')

            inner.select_option('#calibratedCandidate','metyrapone');calculate(None)
            recorder.start('10-quality-gate',3,'Missing convergence? Stop before reporting a fold.',
                           'Metyrapone: zero accepted B2 starts. No ratio invented.','Quality gate / Unresolved',5)
            recorder.scroll('#result');recorder.hold(2.2);recorder.still('quality-gate')

            recorder.start('11-outro',4,'Understand the signal. Design the next experiment.',
                           'IsoForm · Traceable energies, explicit assumptions, testable next steps.','Research preview',5)
            page.evaluate('''() => {
              document.querySelector('#coverTitle').innerHTML='A signal to test.<br>Not a verdict.';
              document.querySelector('#coverTitle').style.fontSize='94px';
              document.querySelector('#coverText').textContent='Next: held-out compounds, robust poses, paired experimental assays.';
              document.querySelector('#coverSmall').textContent='2-compound retrospective calibration · No validated transfer to other targets';
              hidePointer();setCover(true);
            }''');recorder.hold(4);recorder.still('closing-slide')
            assert not errors,errors
            assert not manager.jobs
            provenance.update(scenes=recorder.scenes,duration_seconds=sum(s['seconds'] for s in recorder.scenes),javascript_errors=errors)
            (output/'recording.json').write_text(json.dumps(provenance,indent=2)+'\n')
            browser.close()
    finally:
        server.shutdown();server.server_close()
    print(f'FINAL {encode(output,provenance["scenes"])}',flush=True)


if __name__=='__main__':main()

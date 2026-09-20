"""Record a real IsoForm browser workflow and export a captioned 1080p MP4.

Requires optional playwright + imageio-ffmpeg and installed Chromium. Starts an
isolated loopback server and one actual, eight-component UMA CPU exchange job.
No API fixtures, fabricated result values, or changes to application files.
Only presentation CSS is injected into this recording's browser context.

Example:
  python scripts/record_isoform_video.py
  python scripts/record_isoform_video.py --preview
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cyp_pipeline.sentinel_server import JobManager, make_handler, DEFAULT_UMA_PYTHON, default_backend
from playwright.sync_api import sync_playwright
import imageio_ffmpeg

WIDTH, HEIGHT, CAPTURE_FPS = 1920, 1080, 12
PRESENTATION = ROOT / 'scripts/video/presentation.html'
# Reflow only: the exact application text, scientific warnings and model state stay intact.
RECORDING_CSS = """
html{scroll-behavior:smooth;scrollbar-width:none}::-webkit-scrollbar{display:none}
.topbar,.intro{display:none}main{max-width:1600px;padding:18px 24px 20px}
.workspace{grid-template-columns:286px minmax(0,1fr);gap:18px}
.setup{padding:22px}.setup h2{margin:10px 0 10px}.setup-foot{padding-top:16px}
.molecule-stage{height:255px}.viewer-header{padding:20px 22px 0}
.viewer-navigation{padding-top:12px;padding-bottom:12px}.protein-heading{min-height:72px}
.viewer-bottom{padding:10px 22px 7px}.viewer-scope{margin-bottom:12px}
.structure-note{font-size:11px;min-height:32px;margin-bottom:10px}
.viewer-scope,.legend,.viewer-toolbar button,.mode-note,.setup-foot p{font-size:11px}
.pipeline{padding:19px 24px;margin-top:16px}.pipeline-heading{margin-bottom:17px}
.steps b{font-size:13px}.steps small{font-size:11px}.section-label{font-size:11px}
.pipeline-heading>span{font-size:12px}.activity{font-size:13px;margin-top:16px}
.activity progress{width:260px}.result{padding:24px 30px;margin-top:16px}
.result h2{font-size:30px}.result p,.result-source,.result-next{font-size:14px!important}
.result-tag{font-size:12px}.result-stats small{font-size:13px}
.result details summary{font-size:12px}.result .preference-summary{padding-top:15px}
.result .proxy-scope{font-size:15px!important}.result .proxy-warning{font-size:14px!important}
.result .preference-context p{font-size:13px!important}.readiness-row{font-size:14px}
.readiness-head{font-size:12px}.download-plan{font-size:13px}.purpose,footer{display:none}
.record-focus{outline:3px solid #8c84f1!important;outline-offset:5px;box-shadow:0 0 0 9px #8880ef15!important}
"""


class Recorder:
    def __init__(self, page, app, output):
        self.page, self.app, self.output = page, app, output
        self.scenes = []
        self.current = None

    def start(self, name, seconds, title, caption, badge, chapter):
        folder = self.output / 'frames' / name
        folder.mkdir(parents=True, exist_ok=False)
        self.current = {'name':name,'seconds':seconds,'frames':0,'folder':str(folder),
                        'title':title,'caption':caption,'badge':badge}
        self.scenes.append(self.current)
        self.page.evaluate('setScene', dict(title=title,caption=caption,badge=badge,chapter=chapter))
        print(f'SCENE {name}: {title}', flush=True)

    def frame(self):
        scene = self.current
        self.page.screenshot(path=str(Path(scene['folder']) / f"{scene['frames']:05d}.jpg"),
                             type='jpeg', quality=92, animations='allow')
        scene['frames'] += 1

    def hold(self, seconds):
        finish = time.monotonic() + seconds
        while time.monotonic() < finish:
            start = time.monotonic()
            self.frame()
            delay = max(0,1 / CAPTURE_FPS - (time.monotonic() - start))
            self.page.wait_for_timeout(delay * 1000)

    def scroll(self, selector, offset=16):
        self.app.locator(selector).evaluate('(e,offset)=>window.scrollTo({top:window.scrollY+e.getBoundingClientRect().top-offset,behavior:"smooth"})',offset)
        self.hold(.65)

    def point(self, selector, click=False):
        target=self.app.locator(selector)
        box=target.bounding_box()
        if not box:
            raise RuntimeError(f'No visible bounding box: {selector}')
        self.page.evaluate('([x,y])=>point(x,y)',[box['x']+box['width']/2,box['y']+box['height']/2])
        self.hold(.45)
        if click:
            self.page.evaluate('([x,y])=>point(x,y,true)',[box['x']+box['width']/2,box['y']+box['height']/2])
            target.click()
            self.hold(.2)
            self.page.evaluate('([x,y])=>point(x,y)',[box['x']+box['width']/2,box['y']+box['height']/2])

    def focus(self, selector=None):
        self.app.evaluate("document.querySelectorAll('.record-focus').forEach(e=>e.classList.remove('record-focus'))")
        if selector:
            self.app.locator(selector).evaluate("e=>e.classList.add('record-focus')")

    def still(self, name):
        self.page.screenshot(path=str(self.output / f'{name}.png'))


def encode(output, scenes):
    executable = imageio_ffmpeg.get_ffmpeg_exe()
    clips = output / 'clips'
    clips.mkdir(exist_ok=True)
    for scene in scenes:
        fps = scene['frames'] / scene['seconds']
        target = clips / (scene['name'] + '.mp4')
        if target.exists():
            info=subprocess.run([executable,'-hide_banner','-i',str(target)],capture_output=True,text=True)
            duration=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',info.stderr)
            seconds=(int(duration[1])*3600+int(duration[2])*60+float(duration[3])) if duration else None
            valid=subprocess.run([executable,'-hide_banner','-loglevel','error','-i',str(target),'-f','null','-'],capture_output=True)
            if valid.returncode==0 and seconds is not None and abs(seconds-scene['seconds'])<.05:
                print(f"Reusing verified clip {scene['name']}",flush=True)
                continue
            # Preserve partial output from an interrupted encoder; never silently overwrite it.
            target.rename(target.with_name(target.stem+f'.interrupted-{time.time_ns()}.mp4'))
        command = [executable,'-hide_banner','-loglevel','error','-n','-threads','2',
                   '-framerate',str(fps),'-i',str(Path(scene['folder']) / '%05d.jpg'),
                   '-vf',f"fps=30,fade=t=in:st=0:d=0.13:color=0x101526,fade=t=out:st={scene['seconds']-.13}:d=0.13:color=0x101526,format=yuv420p",
                   '-t',str(scene['seconds']),'-an','-c:v','libx264','-preset','fast','-crf','18',
                   '-profile:v','high','-level','4.1','-threads','2','-movflags','+faststart',str(target)]
        subprocess.run(command,check=True)
        print(f"Encoded {scene['name']} · {scene['seconds']} s · {scene['frames']} source frames",flush=True)
    listing=clips / 'concat.txt'
    listing.write_text(''.join(f"file '{s['name']}.mp4'\n" for s in scenes))
    destination=output / 'IsoForm-demo-1080p.mp4'
    subprocess.run([executable,'-hide_banner','-loglevel','error','-n','-f','concat','-safe','0','-i',str(listing),
                    '-c','copy','-movflags','+faststart',str(destination)],check=True)
    # Decode the entire final video to catch broken frames or truncated output.
    subprocess.run([executable,'-hide_banner','-loglevel','error','-i',str(destination),'-f','null','-'],check=True)
    probe=subprocess.run([executable,'-hide_banner','-i',str(destination)],capture_output=True,text=True)
    (output/'encoding-check.txt').write_text(probe.stderr)
    return destination


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview',action='store_true',help='Inspect the recording layout without launching a model')
    parser.add_argument('--out',type=Path,default=None)
    parser.add_argument('--encode-only',type=Path,help='Encode an already captured video directory; never reruns the model')
    args=parser.parse_args()
    if args.encode_only:
        output=args.encode_only.resolve()
        data=json.loads((output/'recording.json').read_text())
        print(encode(output,data['scenes']))
        return
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    output=(args.out or ROOT/'runs'/'isoform-video'/stamp).resolve()
    output.mkdir(parents=True,exist_ok=False)
    manager=JobManager(ROOT,DEFAULT_UMA_PYTHON,default_backend(ROOT),not args.preview)
    original=make_handler(manager,ROOT/'runs/selectivity-sentinel-demo-v3/demo.html')
    class Handler(original):
        def log_message(self,*_):
            pass
        def do_GET(self):
            if self.path=='/__presentation__':
                body=PRESENTATION.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Content-Length',str(len(body)))
                self.end_headers();self.wfile.write(body)
            else:
                super().do_GET()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    provenance={'created_utc':datetime.now(timezone.utc).isoformat(),'width':WIDTH,'height':HEIGHT,
                'fps':30,'audio':'none; captioned for presentation','source':'actual local IsoForm browser + API',
                'presentation_only_changes':'reflow CSS, cursor highlights, editorial titles and captions',
                'waiting':'actual computation captured at 1 frame/s, uniformly compressed to the stated scene length',
                'scientific_scope':'Frozen-coordinate UMA exchange. Fold is a hypothetical energy proxy, not binding selectivity.'}
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True)
            context=browser.new_context(viewport={'width':WIDTH,'height':HEIGHT},device_scale_factor=1)
            page=context.new_page()
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_address[1]}/__presentation__')
            app=page.frame_locator('#app')
            app.locator('#molecule[data-rendered=true]').wait_for()
            app.locator('#compareMolecule[data-rendered=true]').wait_for()
            inner=page.frames[1]
            inner.select_option('#mode','live')
            inner.add_style_tag(content=RECORDING_CSS)
            expected_connection='connected' if args.preview else 'UMA connected'
            inner.wait_for_function("text=>document.querySelector('#connection').textContent.includes(text)",arg=expected_connection,timeout=90000)
            recorder=Recorder(page,inner,output)
            page.evaluate('setCover(false)')
            page.wait_for_timeout(800)
            recorder.still('poster')
            print(f'OUTPUT {output}',flush=True)
            if args.preview:
                browser.close()
                return

            page.evaluate('setCover(true)')
            recorder.start('01-intro',3,'A second look at binding.','Explore computationally. Validate experimentally.','Research preview',0)
            recorder.hold(3)

            recorder.start('02-select',5,'01 / Choose a molecule. Define the comparison.',
                           'R-fadrozole · CYP11B2 target · CYP11B1 counter-screen','Prepared candidate pair',0)
            page.evaluate('setCover(false)')
            recorder.focus('#candidate');recorder.point('#candidate');recorder.hold(1)
            inner.select_option('#candidate','S-fadrozole')
            inner.wait_for_function("document.querySelector('#structureNote').textContent.includes('S-fadrozole')")
            recorder.hold(.6)
            inner.select_option('#candidate','R-fadrozole')
            inner.wait_for_function("document.querySelector('#structureNote').textContent.includes('R-fadrozole')")
            recorder.focus('#pairedTarget');recorder.hold(1.7);recorder.focus()

            recorder.start('03-structures',6,'02 / Inspect the same molecule in both pockets.',
                           'Actual prepared coordinates · Ligand in green · Heme in gold · Dashed lines show distances','Interactive 3D',1)
            recorder.point('#rotate',click=True)
            page.evaluate('hidePointer()')
            recorder.hold(1.8)
            recorder.point('#molecule')
            inner.locator('#molecule').focus();page.keyboard.press('+');page.keyboard.press('ArrowRight')
            recorder.hold(1.1)
            inner.locator('#compareMolecule').focus();page.keyboard.press('+')
            page.evaluate('hidePointer()');recorder.hold(1.2)
            recorder.still('structure-comparison')

            recorder.start('04-launch',3,'03 / Launch the real UMA calculation.',
                           'One browser action starts eight matched ligand/water energy evaluations.','Live UMA / CPU',2)
            recorder.focus('#run');recorder.point('#run',click=True);recorder.focus()
            inner.locator('#activity:not([hidden])').wait_for()
            recorder.scroll('.pipeline',offset=475)
            recorder.hold(1)
            assert len(manager.jobs)==1,'Recording must launch exactly one model job'
            job_id=next(iter(manager.jobs))
            print(f'ACTUAL UMA JOB {job_id}',flush=True)

            recorder.start('05-compute',8,'Real computation. Waiting accelerated.',
                           'Progress comes from completed UMA components; this waiting segment is sped up.','Live UMA / Waiting sped up',2)
            page.evaluate('hidePointer()')
            started=time.monotonic();last_done=-1
            while inner.locator('#result').is_hidden():
                recorder.frame()
                status=manager.status(job_id)
                done=sum(c.get('status')=='completed' for row in (status.get('result') or {}).get('enzymes',{}).values() for c in row.get('components',{}).values())
                if done!=last_done:
                    print(f'UMA {done}/8 · {status["elapsed_seconds"]} s · {status["state"]}',flush=True)
                    last_done=done
                if status['state']=='failed':
                    raise RuntimeError(f'Actual UMA failed: {status["log"][-10:]}')
                if time.monotonic()-started>900:
                    raise RuntimeError('UMA exceeded 15-minute recording budget; job left intact for inspection')
                page.wait_for_timeout(1000)
            status=manager.status(job_id)
            result=status['result']
            assert status['state']=='completed' and result['synthetic'] is False and result['status']=='exploratory'
            assert sum(c['status']=='completed' for row in result['enzymes'].values() for c in row['components'].values())==8
            assert result['preference_summary']['fold_selectivity'] is None
            assert result['preference_summary']['energy_fold_proxy']['status']=='hypothetical_energy_proxy'
            provenance.update(job_id=job_id,job_seconds=status['elapsed_seconds'],result_directory=status['output_directory'],
                              result=result,waiting_seconds=time.monotonic()-started)
            (output/'actual-uma-job.json').write_text(json.dumps(status,indent=2)+'\n')
            recorder.hold(.6)
            print(f'UMA COMPLETED {job_id} · {status["elapsed_seconds"]} s',flush=True)

            recorder.start('06-result',8,'04 / Read the energy signal—not a binding verdict.',
                           'The ×-fold is a hypothetical energy-weight proxy. Extreme values do not establish selectivity.','Actual UMA output / Exploratory',3)
            recorder.scroll('.pipeline')
            recorder.focus('.preference-summary');recorder.hold(2.2)
            recorder.focus('.proxy-warning');recorder.hold(2)
            recorder.focus();recorder.still('uma-result')
            recorder.point('#downloadExchangeResult')
            with page.expect_download() as download:
                inner.locator('#downloadExchangeResult').click()
            download.value.save_as(output/'downloaded-results.json')
            page.evaluate('hidePointer()');recorder.hold(1.8)

            # Native reference workflows, clearly distinguished from the live UMA run.
            inner.select_option('#mode','reference')
            inner.select_option('#candidate','Osilodrostat (LCI699)')
            inner.locator('#run').click()
            inner.locator('#result:not([hidden])').wait_for()
            assert inner.locator('#result h2').inner_text()=='Below the selectivity threshold'
            recorder.start('07-assay-alert',5,'05 / Cross-check the saved experimental evidence.',
                           'Osilodrostat · Paired IC50 reference falls below the app’s 10× assay threshold.','Saved assay evidence / Not a new run',4)
            recorder.scroll('.pipeline');recorder.focus('#result');recorder.hold(3.5)
            recorder.still('assay-alert');recorder.focus()

            inner.select_option('#candidate','Baxdrostat');inner.locator('#run').click()
            inner.locator('#result:not([hidden])').wait_for()
            assert inner.locator('#result h2').inner_text()=='Meets the assay threshold'
            assert 'model disagrees' in inner.locator('#result').inner_text()
            recorder.start('08-assay-contrast',5,'A stronger assay signal. A model disagreement to investigate.',
                           'Baxdrostat · Paired Ki reference clears 10×; saved Boltz evidence disagrees. Ki ≠ IC50.','Saved assay + model evidence',4)
            recorder.scroll('.pipeline');recorder.focus('.result-next');recorder.hold(3.6)
            recorder.still('assay-contrast');recorder.focus()

            inner.select_option('#candidate','R-fadrozole');inner.select_option('#mode','plan')
            inner.select_option('#planTarget','CYP19A1');inner.locator('#whole').click()
            inner.locator('.workspace').evaluate('e=>window.scrollTo({top:0,behavior:"instant"})')
            recorder.start('09-expand',7,'06 / Prepare a broader counter-screen.',
                           'Five reference structures + pose-prediction inputs. New pockets still need prediction and chemistry review.','Input preparation / No new predictions',5)
            recorder.hold(1.5)
            recorder.point('#run',click=True)
            inner.locator('#downloadInputs').wait_for(timeout=60000)
            assert 'Inputs built for 5 proteins' in inner.locator('#result h2').inner_text()
            recorder.scroll('#result')
            recorder.hold(2)
            with page.expect_download() as download:
                inner.locator('#downloadInputs').click()
            download.value.save_as(output/'downloaded-input-bundle.zip')
            recorder.hold(.8);recorder.still('expanded-panel')

            recorder.start('10-outro',4,'Explore computationally. Validate experimentally.',
                           'IsoForm / Research preview','Research preview',5)
            page.evaluate("""() => {
              document.querySelector('#coverEyebrow').textContent='IsoForm / From molecule to next experiment';
              document.querySelector('#coverTitle').innerHTML='See the evidence.<br>Choose what to test next.';
              document.querySelector('#coverTitle').style.fontSize='86px';
              document.querySelector('#coverText').textContent='Inspect pockets. Run supported calculations. Surface disagreement.';
              document.querySelector('#coverPills').innerHTML='<span>3D comparisons</span><span>Traceable outputs</span><span>Expandable input panel</span>';
              document.querySelector('#coverSmall').textContent='Exploratory research tool · Not validated binding selectivity · Experimental checks required';
              hidePointer();setCover(true);
            }""")
            recorder.hold(4);recorder.still('closing-slide')
            provenance['scenes']=recorder.scenes
            provenance['duration_seconds']=sum(s['seconds'] for s in recorder.scenes)
            provenance['javascript_errors']=errors
            assert not errors,errors
            (output/'recording.json').write_text(json.dumps(provenance,indent=2)+'\n')
            browser.close()
    finally:
        server.shutdown();server.server_close()
    destination=encode(output,provenance['scenes'])
    print(f'FINAL {destination} · {provenance["duration_seconds"]} seconds',flush=True)


if __name__=='__main__':
    main()

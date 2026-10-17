"""Record a real Molio design/prediction workflow with a visible cursor.

Requires --live: saves two BRD4 design proposals and starts three Boltz predictions.
Requires a running, configured Molio server, Playwright and imageio-ffmpeg.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT, FPS = 1440, 1000, 15
OVERLAY = r"""() => {
  document.addEventListener('DOMContentLoaded', () => {
    const style=document.createElement('style');style.textContent=`
      #video-cursor{position:fixed;top:0;left:0;width:30px;height:38px;z-index:2147483647;pointer-events:none;filter:drop-shadow(0 2px 3px #20113666)}
      #video-click{position:fixed;top:0;left:0;width:38px;height:38px;margin:-19px;border:3px solid #9571d7;background:#9571d733;border-radius:50%;z-index:2147483646;pointer-events:none;opacity:0}
      #video-caption{position:fixed;top:14px;left:50%;transform:translateX(-50%);padding:9px 18px;border:1px solid #dcd2e9;border-radius:999px;background:#fffffff5;color:#514060;font:600 13px system-ui,sans-serif;box-shadow:0 3px 15px #51406012;z-index:2147483645;pointer-events:none;white-space:nowrap}
    `;document.head.append(style);
    const cursor=document.createElement('div');cursor.id='video-cursor';cursor.innerHTML='<svg viewBox="0 0 30 38"><path d="M3 2v27l7-7 6 12 5-3-6-11h11Z" fill="#392f48" stroke="white" stroke-width="2" stroke-linejoin="round"/></svg>';
    const click=document.createElement('div');click.id='video-click';
    const caption=document.createElement('div');caption.id='video-caption';
    document.body.append(cursor,click,caption);
    window.videoPoint=(x,y)=>{cursor.style.transform=`translate(${x}px,${y}px)`;click.style.transform=`translate(${x}px,${y}px)`;};
    window.videoCaption=text=>{caption.textContent=text;};
    window.videoPoint(1080,180);
  });
}"""


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Save proposals and execute three real predictions')
    parser.add_argument('--url',default='http://127.0.0.1:8001')
    parser.add_argument('--out',type=Path,default=ROOT/'docs/media')
    parser.add_argument('--capture-dir',type=Path,default=Path('/tmp/molio-pipeline-capture'))
    args=parser.parse_args()
    if not args.live:parser.error('--live is required to start the real comparison')
    output=args.out.resolve();output.mkdir(parents=True,exist_ok=True)
    video=output/'molio-pipeline.mp4'
    if video.exists():parser.error('Output video exists; choose a new --out directory')
    scratch=args.capture_dir.resolve();scratch.mkdir(parents=True,exist_ok=False)
    url=args.url.rstrip('/')
    def jobs():
        with urllib.request.urlopen(url+'/api/experiments?workspace=brd4',timeout=20) as response:return json.load(response)
    preflight=jobs()
    if not preflight['runtime']['ready']:raise RuntimeError(preflight['runtime']['issues'])
    if any(j['status'] in ['queued','preparing','running','validating'] for j in preflight['experiments']):raise RuntimeError('Another run is active')
    scenes=[];errors=[];mutations=[];job_id=None
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'width':WIDTH,'height':HEIGHT,'encoded_fps':30,
              'audio':'none','new_predictions':True,'predictions':3,'seeds':[42],
              'source':'Actual local Molio UI, real proposal saves and new Boltz-2 outputs; no mocked results.',
              'presentation':'Visible cursor, click halo and chapter captions added for recording; interaction pacing edited.',
              'scenes':scenes,'runtime':preflight['runtime']}
    def save_manifest():
        (scratch/'recording.json').write_text(json.dumps(manifest,indent=2)+'\n')
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=shutil.which('google-chrome'),args=['--enable-unsafe-swiftshader'])
        context=browser.new_context(viewport={'width':WIDTH,'height':HEIGHT},device_scale_factor=1,accept_downloads=True)
        context.add_init_script('('+OVERLAY+')()')
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        def guard(route):
            request=route.request
            if request.method=='POST':
                path=request.url.split('?',1)[0].rsplit('/',1)[-1]
                if path not in ['designs','preview','design-shortlist','experiments']:
                    route.abort();raise RuntimeError('Unexpected write: '+request.url)
                mutations.append(path)
            route.continue_()
        context.route('**/api/**',guard)
        current=None;mouse=[1080.,180.]
        def begin(name,caption,seconds):
            nonlocal current
            folder=scratch/name;folder.mkdir()
            current={'name':name,'seconds':seconds,'frames':0,'caption':caption}
            scenes.append(current);page.evaluate('(text)=>window.videoCaption(text)',caption)
            print('SCENE '+name,flush=True);save_manifest()
        def frame():
            page.screenshot(path=str(scratch/current['name']/f"{current['frames']:05d}.jpg"),type='jpeg',quality=93,animations='allow')
            current['frames']+=1
        def hold(seconds):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                start=time.monotonic();frame();page.wait_for_timeout(max(0,1/FPS-(time.monotonic()-start))*1000)
        def move(x,y,seconds=.65):
            start=mouse.copy();steps=max(2,int(seconds*FPS))
            for step in range(1,steps+1):
                t=step/steps;t=t*t*(3-2*t)
                mouse[:]=[start[0]+(x-start[0])*t,start[1]+(y-start[1])*t]
                page.mouse.move(*mouse);page.evaluate('([x,y])=>window.videoPoint(x,y)',mouse);frame()
        def point(selector,click=False):
            el=page.locator(selector);el.scroll_into_view_if_needed();box=el.bounding_box()
            move(box['x']+box['width']/2,box['y']+box['height']/2)
            hold(.25)
            if click:
                page.evaluate("document.getElementById('video-click').style.opacity='1'")
                hold(.15);page.mouse.click(*mouse);page.wait_for_timeout(180)
                page.evaluate("document.getElementById('video-click').style.opacity='0'");frame()
        def scroll_to(selector,offset=150):
            el=page.locator(selector)
            y=el.evaluate('(e,offset)=>window.scrollY+e.getBoundingClientRect().top-offset',offset)
            start=page.evaluate('window.scrollY')
            for step in range(1,13):
                t=step/12;t=t*t*(3-2*t)
                page.evaluate('(y)=>window.scrollTo(0,y)',start+(y-start)*t);frame()

        page.goto(url);page.wait_for_selector('#molio-logo-view[data-ready=true]')
        begin('01-start','1 · Open your molecular workspace',4)
        hold(1);point('#welcome-start',True)
        page.wait_for_selector('.project-card');page.wait_for_function('()=>!!projectPreviewSession.cards[0].view')
        begin('02-project','2 · Choose a protein project',5)
        point('[data-workspace="brd4"]');hold(1);point('[data-workspace="brd4"]',True)
        page.wait_for_selector('#home-page:not([hidden])');page.wait_for_selector('#home-molecules .tile-art img')
        begin('03-parent','3 · Pick the parent molecule',6)
        if page.locator('#gallery-motion').get_attribute('aria-pressed')=='true':point('#gallery-motion',True)
        point('[data-open-molecule="CHEMBL1828983"]',True);page.wait_for_selector('#detail-molecule-shape canvas')
        hold(1);point('#molecule-design',True)
        page.wait_for_selector('#design-list .design-card');page.wait_for_selector('#design-parent-shape canvas')
        begin('04-designs','4 · Generate ideas and inspect the chemical changes',9)
        scroll_to('.design-layout');hold(1)
        point('#design-list .design-card:nth-child(2) [data-inspect-design]',True)
        page.wait_for_function('()=>document.querySelector("#design-selected-title").textContent.includes("methyl")')
        page.wait_for_selector('#design-new-shape canvas');hold(1)
        point('#design-list .design-card:nth-child(1) input',True)
        point('#design-list .design-card:nth-child(2) input',True)
        with page.expect_response(lambda r:'/api/design-shortlist' in r.url and r.request.method=='POST') as saved:
            point('#compare-designs',True)
        shortlist=saved.value.json();manifest['shortlist']=shortlist;save_manifest()
        page.wait_for_selector('#run-setup-panel:not([hidden])');page.wait_for_function('()=>!document.getElementById("start-experiment").disabled')
        begin('05-configure','5 · Parent + two designs · one seed each',6)
        point('#experiment-repeats');page.locator('#experiment-repeats').select_option('1');hold(.5)
        scroll_to('#experiment-candidates');hold(1)
        begin('06-launch','6 · Launch three real Boltz-2 predictions',4)
        with page.expect_response(lambda r:'/api/experiments' in r.url and r.request.method=='POST') as response:
            point('#start-experiment',True)
        submitted=response.value.json()
        if response.value.status!=200:raise RuntimeError(submitted)
        job_id=submitted['id'];manifest['job_id']=job_id;save_manifest()
        print('LIVE JOB '+job_id,flush=True)
        job_selector=f'.run-details[data-job="{job_id}"]'
        page.wait_for_selector(job_selector)
        if page.locator(job_selector).get_attribute('open') is None:point(job_selector+' > summary',True)
        scroll_to(job_selector,160);hold(.5)
        begin('07-inference','Boltz-2 running · WAITING TIME ACCELERATED',10)
        start=time.monotonic();last_report=0
        while True:
            job=next(j for j in jobs()['experiments'] if j['id']==job_id)
            if job['status'] not in ['queued','preparing','running','validating']:break
            if time.monotonic()-last_report>25:
                print('RUN '+job['status']+' '+str([c['status'] for c in job['cases']]),flush=True);last_report=time.monotonic()
            frame();page.wait_for_timeout(2000)
        current['actual_wait_seconds']=round(time.monotonic()-start,2)
        current['acceleration_factor']=round(current['actual_wait_seconds']/current['seconds'],2)
        manifest['job_status']=job['status'];manifest['job_created_at']=job['created_at'];manifest['job_finished_at']=job.get('finished_at')
        (output/'molio-pipeline-job.json').write_text(json.dumps(job,indent=2)+'\n');save_manifest()
        if job['status']!='complete':raise RuntimeError(f'Run {job_id} ended {job["status"]}; inspect the saved job record')
        page.evaluate('()=>refreshExperiments()')
        begin('08-results','7 · Compare model scores · one seed is exploratory',7)
        scroll_to(job_selector+' .repeat-summary',170)
        point(job_selector+' .repeat-summary');hold(2)
        page.screenshot(path=str(output/'molio-pipeline-results.png'))
        point(job_selector+' .individual-predictions > summary',True)
        begin('09-pose','8 · Inspect an actual predicted protein–ligand complex',9)
        point(job_selector+' .experiment-result:nth-child(3) [data-pose-job]',True)
        page.wait_for_selector('#prediction-viewer canvas');page.wait_for_timeout(500)
        scroll_to('#prediction-viewer',160)
        box=page.locator('#prediction-viewer').bounding_box()
        move(box['x']+box['width']*.45,box['y']+box['height']*.45)
        page.mouse.down();move(mouse[0]+130,mouse[1]+45,1.5);page.mouse.up();hold(1)
        page.screenshot(path=str(output/'molio-pipeline-pose.png'))
        begin('10-export','9 · Export the real run record',4)
        point('#run-results-tab',True)
        with page.expect_download() as download:point(f'[data-export-job="{job_id}"]',True)
        download.value.save_as(output/'molio-pipeline-export.json');hold(.5)
        browser.close()
    if errors:raise RuntimeError(errors)
    manifest['mutating_requests']=mutations;manifest['duration_seconds']=sum(s['seconds'] for s in scenes)
    save_manifest();encode(scratch,video,scenes)
    manifest['verification']='Final MP4 fully decoded; no browser errors. Native run and export retained.'
    (output/'molio-pipeline-recording.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('DONE '+str(video),flush=True)


def encode(scratch,video,scenes):
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();clips=[]
    for scene in scenes:
        clip=scratch/(scene['name']+'.mp4')
        subprocess.run([ffmpeg,'-v','error','-framerate',str(scene['frames']/scene['seconds']),
                        '-i',str(scratch/scene['name']/'%05d.jpg'),'-vf','fps=30','-c:v','libx264',
                        '-preset','fast','-crf','19','-pix_fmt','yuv420p','-an',str(clip)],check=True)
        clips.append(clip)
    listing=scratch/'clips.txt';listing.write_text(''.join(f"file '{p.name}'\n" for p in clips))
    subprocess.run([ffmpeg,'-v','error','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(video)],check=True)
    subprocess.run([ffmpeg,'-v','error','-i',str(video),'-f','null','-'],check=True)


if __name__=='__main__':main()

"""Record a real Molio design/prediction workflow with a visible cursor.

Requires --live: creates a protein workspace, saves molecules and designs, and runs nine predictions.
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
WIDTH, HEIGHT, FPS = 1440, 1000, 10
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
    parser.add_argument('--encode-only',action='store_true',help='Encode retained frames; does not open the app or run predictions')
    parser.add_argument('--live',action='store_true',help='Save proposals and execute nine real predictions')
    parser.add_argument('--url',default='http://127.0.0.1:8001')
    parser.add_argument('--out',type=Path,default=ROOT/'docs/media')
    parser.add_argument('--capture-dir',type=Path,default=Path('/tmp/molio-complete-tour-capture'))
    args=parser.parse_args()
    if args.encode_only:
        manifest=json.loads((args.capture_dir/'recording.json').read_text())
        args.out.mkdir(parents=True,exist_ok=True)
        video=args.out/'molio-complete-tour.mp4'
        if video.exists():parser.error('Output video exists; choose a new --out directory')
        encode(args.capture_dir.resolve(),video,manifest['scenes'])
        manifest['verification']='Final MP4 fully decoded; retained actual UI frames re-encoded.'
        (args.out/'molio-complete-tour-recording.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print('DONE '+str(video),flush=True)
        return
    if not args.live:parser.error('--live is required to create a project and start the comparison')
    output=args.out.resolve();output.mkdir(parents=True,exist_ok=True)
    video=output/'molio-complete-tour.mp4'
    if video.exists():parser.error('Output video exists; choose a new --out directory')
    scratch=args.capture_dir.resolve();scratch.mkdir(parents=True,exist_ok=False)
    url=args.url.rstrip('/')
    workspace='brd4'
    def jobs():
        with urllib.request.urlopen(url+'/api/experiments?workspace='+workspace,timeout=20) as response:return json.load(response)
    preflight=jobs()
    if not preflight['runtime']['ready']:raise RuntimeError(preflight['runtime']['issues'])
    if any(j['status'] in ['queued','preparing','running','validating'] for j in preflight['experiments']):raise RuntimeError('Another run is active')
    scenes=[];errors=[];mutations=[];job_id=None
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'width':WIDTH,'height':HEIGHT,'encoded_fps':30,
              'audio':'none','new_predictions':True,'predictions':9,'seeds':[42,43,44],
              'source':'Actual local Molio UI, real proposal saves and new Boltz-2 outputs; no mocked results.',
              'presentation':'Visible cursor, click halo and chapter captions added for recording; interaction pacing edited; selected scenes have a smooth 1.22x digital close-up.',
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
                if path not in ['designs','preview','design-shortlist','experiments','starter','compound','suggestions','proposals','target-compounds','find-compounds','import-compound','region']:
                    route.abort();raise RuntimeError('Unexpected write: '+request.url)
                mutations.append(path)
            route.continue_()
        context.route('**/api/**',guard)
        current=None;mouse=[1080.,180.]
        def begin(name,caption,seconds,zoom=False):
            nonlocal current
            folder=scratch/name;folder.mkdir()
            current={'name':name,'seconds':seconds,'frames':0,'caption':caption,'zoom':zoom}
            scenes.append(current);page.evaluate('(text)=>window.videoCaption(text)',caption)
            page.evaluate("document.getElementById('video-caption').style.display='block'")
            page.locator('#video-caption').screenshot(path=str(folder/'caption.png'))
            if zoom:
                page.evaluate("document.getElementById('video-caption').style.display='none'")
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

        def type_text(selector,text):
            point(selector,True);page.locator(selector).fill('')
            for char in text:
                page.locator(selector).press_sequentially(char);frame()
        def wait_visible(selector,seconds=180):
            start=time.monotonic()
            while not page.locator(selector).is_visible():
                if time.monotonic()-start>seconds:
                    page.screenshot(path=str(scratch/'failure.png'))
                    raise RuntimeError('Timed out: '+selector+'; '+page.locator('body').inner_text()[-3000:])
                frame();page.wait_for_timeout(1000)
            current['actual_wait_seconds']=round(time.monotonic()-start,2)
        def photo(name):page.screenshot(path=str(output/(name+'.png')))
        def drag(selector):
            box=page.locator(selector).bounding_box()
            move(box['x']+box['width']*.45,box['y']+box['height']*.48)
            page.mouse.down();move(mouse[0]+110,mouse[1]+40,1.4);page.mouse.up();hold(1)

        page.goto(url);page.wait_for_selector('#molio-logo-view[data-ready=true]')
        begin('01-welcome','MOLIO · From a question to a computational experiment',5)
        hold(1);point('#welcome-start',True);page.wait_for_selector('.project-card')
        begin('02-library','01 / YOUR LIBRARY · A separate workspace for each protein',6)
        point('[data-workspace="brd4"]');hold(1);point('#new-project',True)
        begin('03-search','02 / START FROM SCRATCH · Search UniProt for a protein',8,True)
        type_text('#target-query','P62942');point('#target-search-button',True)
        wait_visible('[data-start-target="P62942"]');hold(1)
        begin('04-download','DOWNLOAD · Protein sequence + available AlphaFold DB model · wait accelerated',6)
        point('[data-start-target="P62942"]',True)
        wait_visible('#open-imported-target',300);hold(1)
        point('#open-imported-target',True)
        page.wait_for_selector('#home-page:not([hidden])')
        workspace=page.evaluate('activeWorkspace');manifest['workspace']=workspace;save_manifest()
        begin('05-protein','03 / YOUR PROTEIN · Downloaded coordinates; no measured series required',9)
        point('#open-explore',True);page.wait_for_selector('#starter-page:not([hidden])')
        wait_visible('#starter-protein-view canvas');scroll_to('#starter-readiness',140)
        if page.locator('#starter-spin').inner_text()=='Pause rotation':point('#starter-spin',True)
        drag('#starter-protein-view');photo('molio-tour-protein')
        begin('06-sequence','INPUTS · Inspect the sequence and the region used for predictions',8)
        point('.starter-protein-context > summary',True)
        point('.starter-protein-context details > summary',True);hold(1)
        point('#starter-region-details > summary',True);scroll_to('#starter-region-details',220);hold(1)
        begin('07-molecule','04 / ADD A MOLECULE · Paste SMILES to start with your own chemistry',10,True)
        if not page.locator('#manual-compound-entry').get_attribute('open'):point('#manual-compound-entry > summary',True)
        scroll_to('#manual-compound-entry',170)
        type_text('#starter-compound-name','Ethyl benzoate · starting idea')
        type_text('#starter-smiles','CCOC(=O)c1ccccc1');hold(.7)
        with page.expect_response(lambda r:'/api/starter/compound' in r.url and r.request.method=='POST') as added:
            point('#starter-add-compound',True)
        compound=added.value.json()['compound'];manifest['input_compound']=compound;save_manifest()
        parent=compound['id'];wait_visible('[data-edit-input="'+parent+'"]')
        begin('08-input-shape','INSPECT · A generated 3D conformer, not a bound pose or a known binder',7)
        scroll_to('#starter-compounds',150);page.wait_for_selector('#starter-compounds canvas')
        drag('#starter-compounds .molecule-canvas');photo('molio-tour-input')
        point('[data-edit-input="'+parent+'"]',True)
        begin('09-custom-edit','05 / YOUR OWN DESIGN · Edit chemistry and preview the change',11,True)
        page.wait_for_selector('#variant-smiles');scroll_to('.variant-fields',170)
        type_text('#variant-name','Propyl benzoate · longer ester')
        type_text('#variant-smiles','CCCOC(=O)c1ccccc1')
        page.wait_for_function('()=>!document.getElementById("save-variant").disabled')
        scroll_to('#variant-preview',150);hold(1);photo('molio-tour-editor')
        begin('10-hypothesis','KEEP THE QUESTION · Save your idea with an explicit hypothesis',8)
        scroll_to('#variant-hypothesis',350)
        type_text('#variant-hypothesis','Does extending the ester change the predicted interaction? Test experimentally before drawing conclusions.')
        point('#save-variant',True);point('#open-proposals',True)
        page.wait_for_selector('.proposal-row');hold(1)
        begin('11-generate','06 / EXPLORE IDEAS · Generate small, rule-based chemical edits',10)
        point('#open-explore',True);point('[data-design-input="'+parent+'"]',True)
        page.wait_for_selector('#design-list .design-card');scroll_to('.design-layout',145)
        point('#design-list .design-card:nth-child(2) [data-inspect-design]',True)
        page.wait_for_selector('#design-new-shape canvas');hold(1);photo('molio-tour-designs')
        begin('12-compare-designs','COMPARE · Inspect 3D changes and calculated properties before predicting',8,True)
        point('#design-list .design-card:nth-child(1) input',True)
        point('#design-list .design-card:nth-child(2) input',True)
        with page.expect_response(lambda r:'/api/design-shortlist' in r.url and r.request.method=='POST') as saved:
            point('#compare-designs',True)
        manifest['shortlist']=saved.value.json();save_manifest()
        page.wait_for_selector('#run-setup-panel:not([hidden])')
        page.wait_for_function('()=>!document.getElementById("start-experiment").disabled')
        begin('13-configure','07 / MATCHED SEEDS · Three molecules × three seeds = nine predictions',10)
        point('#experiment-repeats');page.locator('#experiment-repeats').select_option('3');hold(.7)
        point('.experiment-protocol > summary',True);hold(1)
        scroll_to('#experiment-candidates',180);photo('molio-tour-setup')
        begin('14-launch','RUN · Boltz-2 predicts protein–ligand complexes and model scores',6)
        with page.expect_response(lambda r:'/api/experiments' in r.url and r.request.method=='POST') as response:
            point('#start-experiment',True)
        submitted=response.value.json()
        if response.value.status!=200:raise RuntimeError(submitted)
        job_id=submitted['id'];manifest['job_id']=job_id;save_manifest()
        print('LIVE JOB '+job_id,flush=True)
        job_selector=f'.run-details[data-job="{job_id}"]'
        page.wait_for_selector(job_selector)
        if page.locator(job_selector).get_attribute('open') is None:point(job_selector+' > summary',True)
        scroll_to(job_selector,170)
        begin('15-inference','COMPUTING · Nine actual predictions · WAITING TIME ACCELERATED',12)
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
        (output/'molio-complete-tour-job.json').write_text(json.dumps(job,indent=2)+'\n');save_manifest()
        if job['status']!='complete':raise RuntimeError(f'Run {job_id} ended {job["status"]}')
        page.evaluate('()=>refreshExperiments()')
        begin('16-consistency','08 / CONSISTENCY · Compare means, spread and matched-seed differences',11,True)
        scroll_to(job_selector+' .repeat-summary',190);point(job_selector+' .repeat-summary');hold(3)
        photo('molio-tour-results')
        begin('17-probability','09 / READ THE SCORES · Binder probability is a model output, not a verified chance',11,True)
        point(job_selector+' .individual-predictions > summary',True)
        scroll_to(job_selector+' .experiment-results',200);point(job_selector+' .experiment-result:nth-child(1) dl');hold(3)
        photo('molio-tour-probability')
        begin('18-pose','10 / INSPECT IN 3D · Rotate the actual predicted complex',10)
        point(job_selector+' .experiment-result:nth-child(2) [data-pose-job]',True)
        page.wait_for_selector('#prediction-viewer canvas');scroll_to('#prediction-viewer',180);drag('#prediction-viewer')
        page.mouse.wheel(0,-100);hold(1);photo('molio-tour-pose')
        begin('19-checks','REVIEW · Geometry checks, nearby residues and prediction provenance',9)
        point('.pose-checks-disclosure > summary',True);scroll_to('.pose-checks-disclosure',170);hold(2)
        if page.locator('[data-pose-residue]').count():point('[data-pose-residue]:first-child',True)
        point('.low-priority:has(#prediction-provenance) > summary',True);hold(1)
        begin('20-export','11 / KEEP THE EVIDENCE · Export settings, scores, seeds and source records',7)
        point('#run-results-tab',True)
        with page.expect_download() as download:point(f'[data-export-job="{job_id}"]',True)
        download.value.save_as(output/'molio-complete-tour-export.json');hold(.5)
        point('#open-explore',True)
        begin('20a-public-chemistry','ANOTHER START · Search PubChem by name instead of writing SMILES',10,True)
        if page.locator('#starter-spin').inner_text()=='Pause rotation':point('#starter-spin',True)
        scroll_to('#compound-search-form',160)
        type_text('#compound-search-query','caffeine');point('#compound-search-button',True)
        wait_visible('#compound-search-results [data-add-candidate]',180)
        scroll_to('#compound-search-results',180);hold(2);photo('molio-tour-search')
        with page.expect_response(lambda r:'/api/starter/import-compound' in r.url and r.request.method=='POST') as imported:
            point('#compound-search-results [data-add-candidate]:first-child',True)
        manifest['imported_compound']=imported.value.json()['compound'];hold(1)
        begin('20b-offline','OFFLINE OPTIONS · Example molecules; sources and workspace data stay available',8)
        point('#example-molecules-panel > summary',True);scroll_to('#example-molecules-panel',170);hold(2)
        point('.starter-sources > summary',True);scroll_to('.starter-sources',220)
        with page.expect_download() as download:point('#starter-download',True)
        download.value.save_as(output/'molio-tour-workspace.json');hold(1)
        point('#open-targets',True);page.wait_for_selector('[data-workspace="brd4"]')
        begin('21-measured','12 / ANOTHER STARTING POINT · Explore a measured series in the BRD4 project',8)
        point('[data-workspace="brd4"]',True);page.wait_for_selector('#home-page:not([hidden])')
        if page.locator('#gallery-motion').get_attribute('aria-pressed')=='true':point('#gallery-motion',True)
        point('#open-library',True);page.wait_for_selector('#compound-table');hold(2)
        begin('22-activity','MEASURED EVIDENCE · Compare experimental IC50 values within one assay',9,True)
        point('#open-map',True);page.wait_for_selector('#map-molecule canvas');hold(2);photo('molio-tour-measured')
        begin('23-pocket','13 / EXPERIMENTAL STRUCTURE · Explore the reference binding pocket',10)
        point('#open-pocket-page',True);page.wait_for_selector('#viewer canvas')
        if page.locator('#rotate').get_attribute('aria-pressed')=='true':point('#rotate',True)
        scroll_to('#viewer',160);drag('#viewer');point('#surface',True);hold(1)
        photo('molio-tour-reference')
        begin('24-finish','MOLIO · Explore → design → predict → inspect → choose your next experiment',7)
        point('#surface',True);point('#open-targets',True);hold(2)
        browser.close()
    if errors:raise RuntimeError(errors)
    manifest['mutating_requests']=mutations;manifest['duration_seconds']=sum(s['seconds'] for s in scenes)
    save_manifest();encode(scratch,video,scenes)
    manifest['verification']='Final MP4 fully decoded; no browser errors. Native run and export retained.'
    (output/'molio-complete-tour-recording.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('DONE '+str(video),flush=True)


def encode(scratch,video,scenes):
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();clips=[]
    for scene in scenes:
        clip=scratch/(scene['name']+'.mp4')
        command=[ffmpeg,'-v','error','-y','-framerate',str(scene['frames']/scene['seconds']),
                 '-i',str(scratch/scene['name']/'%05d.jpg')]
        if scene.get('zoom'):
            n=scene['seconds']*30-1
            effect=f"[0:v]fps=30,scale=2880:2000,zoompan=z='1+0.22*pow(sin(PI*on/{n}),2)':x='(iw-iw/zoom)*0.8':y='ih/2-ih/zoom/2':d=1:s=1440x1000:fps=30[z];[z][1:v]overlay=(W-w)/2:14"
            command+=['-i',str(scratch/scene['name']/'caption.png'),'-filter_complex',effect]
        elif (scratch/scene['name']/'caption.png').exists():
            command+=['-i',str(scratch/scene['name']/'caption.png'),'-filter_complex','[0:v]fps=30[z];[z][1:v]overlay=(W-w)/2:14']
        else:command+=['-vf','fps=30']
        command+=['-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-an',str(clip)]
        subprocess.run(command,check=True);clips.append(clip)
    listing=scratch/'clips.txt';listing.write_text(''.join(f"file '{p.name}'\n" for p in clips))
    chapters=scratch/'chapters.ffmeta';metadata=[';FFMETADATA1','title=Molio — from scratch to a computational experiment'];start=0
    for scene in scenes:
        end=start+round(scene['seconds']*1000)
        title=scene['caption'].replace('=',r'\=').replace(';',r'\;').replace('#',r'\#')
        metadata+=['[CHAPTER]','TIMEBASE=1/1000',f'START={start}',f'END={end}','title='+title];start=end
    chapters.write_text('\n'.join(metadata)+'\n')
    subprocess.run([ffmpeg,'-v','error','-f','concat','-safe','0','-i',str(listing),'-i',str(chapters),'-map_metadata','1','-map_chapters','1','-c','copy','-movflags','+faststart',str(video)],check=True)
    subprocess.run([ffmpeg,'-v','error','-i',str(video),'-f','null','-'],check=True)
    def timestamp(seconds):return f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}.000'
    subtitles=['WEBVTT',''];start=0
    for index,scene in enumerate(scenes,1):
        end=start+scene['seconds']
        subtitles += [str(index),f'{timestamp(start)} --> {timestamp(end)}',scene['caption'],''];start=end
    video.with_suffix('.vtt').write_text('\n'.join(subtitles))



if __name__=='__main__':main()

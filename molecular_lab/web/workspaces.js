'use strict';
const activeWorkspace=new URLSearchParams(location.search).get('workspace')||'brd4';
const workspaceStorageKey=activeWorkspace==='brd4'?'whatif-brd4-v1':`whatif-${activeWorkspace}-v1`;
// Scope every API request to this browser tab, never to a process-global active target.
const workspaceFetch=window.fetch.bind(window);
window.fetch=(resource,options)=>{
  if(activeWorkspace!=='brd4'&&typeof resource==='string'&&resource.startsWith('/api/')){
    const url=new URL(resource,location.origin);url.searchParams.set('workspace',activeWorkspace);resource=url.pathname+url.search;
  }
  return workspaceFetch(resource,options);
};
let targetPlan=null,targetBusy=false,targetSearchRevision=0,importedWorkspace=null;
function configureTargetWorkspace(){
  const {target,reference_structure:reference,compounds}=state.data;
  $('project-target').textContent=activeWorkspace==='brd4'?'BRD4 workspace':target.name;
  $('project-organism').textContent=target.organism;$('project-avatar').textContent=target.name[0];
  $('library-title').textContent=`${compounds.length} compounds. One assay.`;
  $('library-description').textContent=`${target.name} · ${compounds.length} measured molecules. Lower IC₅₀ means greater potency in this assay. Shapes are generated conformers.`;
  $('pocket-description').textContent=`${target.name} with an experimental reference ligand. Drag to rotate; hover to inspect.`;
  $('pdb-code').textContent=reference.id;$('pdb-source').href=reference.source_url;
  $('reference-badge').replaceChildren(document.createTextNode(`${reference.id} / ${reference.ligand}`));
  const subtitle=document.createElement('span');subtitle.textContent=`${reference.resolution_A??'—'} Å · X-ray · chain ${reference.chain}`;$('reference-badge').append(subtitle);
  $('download-dataset').href=state.data.dataset_url||'/data/dataset.json';
  if(state.data.prediction_target){$('imported-prediction-note').hidden=false;$('prediction-target-label').textContent=`Boltz-2 · ${target.name} · ${state.data.prediction_target.sequence.length} residues from ${reference.id}, chain ${reference.chain}`;}
  document.title=`${target.name} · Molio`;
}
function switchWorkspace(id){const url=new URL(location.href);url.searchParams.set('workspace',id);url.hash='/home';location.assign(url.href);}
function setTargetBusy(busy){targetBusy=busy;$('import-target').disabled=busy;$('target-search-button').disabled=busy;document.querySelectorAll('[data-inspect-target],[data-search-target],[data-start-target]').forEach(b=>b.disabled=busy);}
let workspaceListRevision=0;
async function loadWorkspaces(){
  const revision=++workspaceListRevision;
  $('project-library-status').textContent='Opening your library…';
  $('retry-project-library').hidden=true;
  let data;
  try{data=await experimentJSON('/api/workspaces');}
  catch(error){
    if(revision!==workspaceListRevision)return;
    $('project-library-status').textContent='Could not load projects. '+error.message;
    $('retry-project-library').hidden=false;return;
  }
  if(revision!==workspaceListRevision)return;
  stopProjectPreviews();
  $('project-library-status').textContent=data.workspaces.length?'':'Your first idea starts here. Choose New project to find a protein.';
  $('project-library-count').textContent=`${data.workspaces.length} ${data.workspaces.length===1?'project':'projects'} · on this computer`;
  $('workspace-list').innerHTML=data.workspaces.map(w=>`<button class="saved-workspace project-card ${!targetLanding&&w.id===activeWorkspace?'selected':''}" data-workspace="${escapeHTML(w.id)}" aria-label="Open project: ${escapeHTML(w.target.name)}"><span class="project-protein-art"><canvas width="420" height="260" hidden aria-hidden="true"></canvas><span class="project-preview-status">Preparing protein preview…</span></span><span class="project-card-copy"><strong>${escapeHTML(w.target.name)}</strong><small>${escapeHTML(w.target.organism)}</small><span class="project-card-bottom"><span>${w.compound_count} ${w.compound_count===1?'molecule':'molecules'}</span><span>${!targetLanding&&w.id===activeWorkspace?'Current project':'Open project ↗'}</span></span></span></button>`).join('');
  $('workspace-list').querySelectorAll('[data-workspace]').forEach(b=>b.onclick=()=>{if(targetLanding||b.dataset.workspace!==activeWorkspace)switchWorkspace(b.dataset.workspace);else goPage('home');});
  startProjectPreviews();
  if(!data.available){$('target-search-status').textContent='Restart the local server to enable online target setup.';$('target-search-button').disabled=true;}
}

async function runTargetTask(path,payload,onProgress){
  const taskActivity=beginStudioActivity('Preparing your workspace','Starting setup…');
  try{
    let task=await experimentJSON(path,payload);
    while(['queued','running'].includes(task.status)){
      onProgress(task.message);updateStudioActivity(taskActivity,task.message);
      await new Promise(resolve=>setTimeout(resolve,1000));task=await experimentJSON('/api/target-tasks/'+task.id);
    }
    if(task.status!=='complete')throw Error(task.message||'Target setup did not complete.');
    return task.result;
  }finally{endStudioActivity(taskActivity);}
}

async function searchProtein(event){
  event?.preventDefault();if(targetBusy)return;
  const query=$('target-query').value.trim();if(query.length<2)return;
  const revision=++targetSearchRevision;$('target-search-status').textContent='Searching UniProt for proteins…';$('target-search-results').replaceChildren();
  try{const data=await experimentJSON('/api/proteins/search?q='+encodeURIComponent(query));if(revision!==targetSearchRevision)return;
    $('target-search-status').textContent=data.targets.length?`${data.targets.length} single-protein targets · ${data.source}. Start empty, or optionally check measured data.`:'No proteins found. Try a gene symbol or UniProt accession.';
    $('target-search-results').innerHTML=data.targets.map(t=>`<article class="target-result"><div><strong>${escapeHTML(t.name)}</strong><small>${escapeHTML(t.organism)} · ${escapeHTML(t.uniprot)}${t.length?' · '+t.length+' residues':''}</small><small>${t.length?(t.length>=40&&t.length<=600?'Full sequence fits the local runner':'Choose a 40–600 residue region before predicting'):'Sequence length checked during setup'} · measurements optional</small></div><div class="target-actions"><button class="primary" data-start-target="${escapeHTML(t.uniprot)}">Start empty →</button>${t.chembl_id?`<button data-inspect-target="${escapeHTML(t.chembl_id)}">Check measured data</button>`:''}</div></article>`).join('');
    $('target-search-results').querySelectorAll('[data-inspect-target]').forEach(b=>b.onclick=()=>previewTarget(b.dataset.inspectTarget));
    $('target-search-results').querySelectorAll('[data-start-target]').forEach(b=>b.onclick=()=>startEmptyTarget(b.dataset.startTarget));
  }catch(e){if(revision===targetSearchRevision)$('target-search-status').textContent=e.message;}
}
function showTargetChoice(){
  if(!targetPlan)return;
  const assay=targetPlan.assays.find(a=>a.id===$('target-assay').value),reference=targetPlan.structures.find(r=>r.id===$('target-reference').value);
  $('target-assay-description').textContent=assay?.description||'';
  $('target-reference-description').textContent=reference?`${reference.title} · ${reference.length} residues · reference ligand ${reference.ligand}.`:'';
}
async function previewTarget(targetId){
  if(targetBusy)return;targetSearchRevision++;$('target-search-status').textContent='Measured data is optional. Start empty from a search result to skip this check.';targetPlan=null;setTargetBusy(true);$('target-preview').hidden=false;$('target-preview-options').hidden=true;$('target-setup-progress').hidden=true;$('open-imported-target').hidden=true;
  $('target-preview-title').textContent='Checking the available evidence…';$('target-preview-status').textContent='';
  $('target-preview').scrollIntoView({block:'start',behavior:'smooth'});
  try{
    targetPlan=await runTargetTask('/api/targets/inspect',{target_id:targetId},message=>$('target-preview-status').textContent=message);
    $('target-preview-title').textContent=targetPlan.target.name;
    $('target-preview-status').textContent=targetPlan.ready?`${targetPlan.structures.length} compatible references found. Choose a measured series and structure. ${(targetPlan.structure_search_warnings||[]).join(' ')}`:targetPlan.issues.join(' ');
    $('target-preview-options').hidden=!targetPlan.ready;
    $('target-assay').innerHTML=targetPlan.assays.map(a=>`<option value="${escapeHTML(a.id)}">${escapeHTML(a.id)} · ${a.count}+ candidate measurements</option>`).join('');
    $('target-reference').innerHTML=targetPlan.structures.map(r=>`<option value="${escapeHTML(r.id)}">${escapeHTML(r.pdb_id)} · chain ${escapeHTML(r.chain)} · ${r.resolution_A??'—'} Å · ${r.length} residues</option>`).join('');
    $('target-import-scope').textContent=targetPlan.scope;showTargetChoice();
  }catch(e){$('target-preview-title').textContent='Measured-data lookup is unavailable.';$('target-preview-status').textContent=e.message+' You can still choose Start empty from the search results.';}
  finally{setTargetBusy(false);}
}
document.addEventListener('DOMContentLoaded',()=>{
$('target-search-form').onsubmit=searchProtein;
$('new-project').onclick=()=>{setProjectSetup(true);$('target-query').focus();};
$('close-project-setup').onclick=()=>{setProjectSetup(false);$('new-project').focus();};
$('retry-project-library').onclick=loadWorkspaces;
$('toggle-project-motion').onclick=()=>{
  projectPreviewsPaused=!projectPreviewsPaused;
  $('toggle-project-motion').textContent=projectPreviewsPaused?'Resume motion':'Pause motion';
  $('toggle-project-motion').setAttribute('aria-pressed',String(projectPreviewsPaused));
  $('targets-page').classList.toggle('motion-paused',projectPreviewsPaused);
  projectPreviewSession?.refresh();
  libraryAtmosphereSession?.sync();
};
$('target-assay').onchange=showTargetChoice;$('target-reference').onchange=showTargetChoice;
document.querySelectorAll('[data-search-target]').forEach(button=>button.onclick=()=>{$('target-query').value=button.dataset.searchTarget;searchProtein();});
$('open-targets').onclick=()=>{openPage('targets-page');loadWorkspaces().catch(e=>$('target-search-status').textContent=e.message);};
$('close-targets').onclick=()=>closePage('targets-page');
$('import-target').onclick=async()=>{
  if(!targetPlan||targetBusy)return;setTargetBusy(true);$('target-setup-progress').hidden=false;$('target-assay').disabled=true;$('target-reference').disabled=true;
  try{
    const result=await runTargetTask('/api/targets/import',{plan_id:targetPlan.plan_id,assay_id:$('target-assay').value,reference_id:$('target-reference').value},message=>$('target-setup-message').textContent=message);
    importedWorkspace=result.workspace_id;$('target-setup-message').textContent=`Ready · ${result.compound_count} molecules downloaded. Your workspace is saved locally.`;
    $('open-imported-target').hidden=false;await loadWorkspaces();
  }catch(e){$('target-setup-message').textContent=e.message;}
  finally{setTargetBusy(false);$('target-assay').disabled=false;$('target-reference').disabled=false;}
};
$('open-imported-target').onclick=()=>{if(importedWorkspace)switchWorkspace(importedWorkspace);};

});

async function startEmptyTarget(accession){
  if(targetBusy)return;targetSearchRevision++;setTargetBusy(true);$('target-search-status').textContent='Preparing a sequence-first workspace…';
  $('target-preview').hidden=false;$('target-preview-options').hidden=true;$('target-setup-progress').hidden=true;$('open-imported-target').hidden=true;
  $('target-preview-title').textContent='Preparing your protein';$('target-preview-status').textContent='Downloading the sequence. Measurements are not required.';
  try{
    const result=await runTargetTask('/api/targets/starter',{accession},message=>$('target-preview-status').textContent=message);
    importedWorkspace=result.workspace_id;$('target-preview-title').textContent=result.target.name;
    $('target-preview-status').textContent='Workspace saved locally. Open it to inspect the protein, add molecules and prepare predictions.';
    $('target-search-status').textContent='Your empty workspace is ready.';$('open-imported-target').hidden=false;await loadWorkspaces();
  }catch(e){$('target-preview-status').textContent=e.message;$('target-search-status').textContent='Setup did not finish. You can retry.';}
  finally{setTargetBusy(false);}
}

function setProjectSetup(open){
  $('project-setup').hidden=!open;$('new-project').setAttribute('aria-expanded',String(open));
  if(open)$('project-setup').scrollIntoView({block:'nearest',behavior:'smooth'});
}
// Keep static thumbnails in the library. Move one live WebGL canvas into the
// hovered/focused card: no round-robin rendering or GPU-to-2D copy per frame.
let projectPreviewSession=null,projectPreviewsPaused=false;
function stopProjectPreviews(){
  const session=projectPreviewSession;projectPreviewSession=null;if(!session)return;
  session.abort.abort();session.observer.disconnect();cancelAnimationFrame(session.frame);
  session.viewer?.clear();
  const canvas=session.host.querySelector('canvas');
  const gl=canvas&&(canvas.getContext('webgl')||canvas.getContext('experimental-webgl'));
  gl?.getExtension('WEBGL_lose_context')?.loseContext();session.host.remove();
}
function startProjectPreviews(){
  if(currentPage!=='targets'||projectPreviewSession)return;
  const host=document.createElement('div');host.className='project-preview-renderer';host.setAttribute('aria-hidden','true');document.body.append(host);
  const session={host,viewer:null,abort:new AbortController(),cards:[],frame:0,active:null,hovered:null,focused:null};
  projectPreviewSession=session;
  const valid=()=>projectPreviewSession===session;
  const paint=(card,snapshot=true)=>{
    const viewer=session.viewer;
    session.cards.forEach(c=>c.model?.hide());card.model.show();
    const now=performance.now();
    if(!card.view){
      viewer.zoomTo({model:card.model});viewer.zoom(.85);viewer.render();
      card.view=viewer.getView();
    }else{
      // setView draws the cached scene directly; avoid three renders per frame
      // from calling setView, rotate and render in succession.
      if(!snapshot&&!projectPreviewsPaused&&!matchMedia('(prefers-reduced-motion: reduce)').matches){
        const angle=Math.min((now-card.last)/1000,.5)*Math.PI/30;
        const sin=Math.sin(angle),cos=Math.cos(angle),[x,y,z,w]=card.view.slice(4);
        card.view.splice(4,4,x*cos-z*sin,y*cos+w*sin,z*cos+x*sin,w*cos-y*sin);
      }
      viewer.setView(card.view);
    }
    card.last=now;
    if(snapshot){
      const canvas=host.querySelector('canvas');
      card.context.clearRect(0,0,420,260);card.context.drawImage(canvas,0,0,420,260);card.canvas.hidden=false;
    }
  };
  session.observer=new IntersectionObserver(entries=>{
    for(const entry of entries){
      const card=session.cards.find(c=>c.element===entry.target);card.visible=entry.isIntersecting;session.refresh();
      if(!card.visible||card.started)continue;card.started=true;
      (async()=>{
        try{
          // Bypass active-tab scoping: each card must read its own protein.
          const response=await workspaceFetch('/api/dataset?workspace='+encodeURIComponent(card.element.dataset.workspace),{signal:session.abort.signal});
          if(!response.ok)throw Error('Dataset unavailable');
          const data=await response.json(),reference=data.reference_structure;
          if(!valid())return;
          if(!reference?.url){card.status.textContent='Sequence saved · no 3D model yet';card.element.classList.add('sequence-only');return;}
          const coordinates=await workspaceFetch(reference.url,{signal:session.abort.signal});if(!coordinates.ok)throw Error('Coordinates unavailable');
          const raw=await coordinates.text();if(!valid())return;
          session.viewer||=$3Dmol.createViewer(host,{backgroundColor:'#ffffff',antialias:true});
          card.model=session.viewer.addModel(raw,'pdb');
          if(!card.model.selectedAtoms({hetflag:false}).length)throw Error('Protein coordinates unavailable');
          card.model.setStyle({},{});card.model.setStyle({hetflag:false},{cartoon:{color:'#a49ad8'}});card.model.hide();
          card.status.textContent=reference.kind==='predicted'?'Predicted structure':'Experimental structure';
          card.status.classList.add('ready');
          // Render the new thumbnail off-screen, then restore the active card.
          host.classList.remove('is-live');document.body.append(host);session.viewer.resize();
          paint(card);session.active=null;session.refresh();
        }catch(error){if(valid()&&error.name!=='AbortError'){card.model?.hide();card.model=null;card.status.textContent='Preview unavailable · open project';}}
      })();
    }
  },{threshold:.05});
  for(const element of $('workspace-list').querySelectorAll('[data-workspace]')){
    const canvas=element.querySelector('canvas');
    const card={element,canvas,context:canvas.getContext('2d'),status:element.querySelector('.project-preview-status'),visible:false};
    session.cards.push(card);session.observer.observe(element);
    const listen=(type,handler)=>element.addEventListener(type,handler,{signal:session.abort.signal});
    listen('pointerenter',event=>{if(event.pointerType==='mouse'){session.hovered=card;session.refresh();}});
    listen('pointerleave',()=>{if(session.hovered===card)session.hovered=null;session.refresh();});
    listen('focusin',()=>{session.focused=card;session.refresh();});
    listen('focusout',()=>{if(session.focused===card)session.focused=null;session.refresh();});
  }
  let lastFrame=0;
  const tick=time=>{
    session.frame=0;
    if(!valid()||!session.active)return;
    if(time-lastFrame>=1000/30){paint(session.active,false);lastFrame=time;}
    session.frame=requestAnimationFrame(tick);
  };
  session.refresh=()=>{
    if(!valid())return;
    const selected=session.hovered||session.focused;
    const next=!projectPreviewsPaused&&!document.hidden&&!matchMedia('(prefers-reduced-motion: reduce)').matches&&selected?.visible&&selected.model?selected:null;
    if(next===session.active)return;
    cancelAnimationFrame(session.frame);session.frame=0;
    if(session.active)paint(session.active); // Save its final orientation once.
    session.active=next;
    if(next){
      next.element.querySelector('.project-protein-art').prepend(host);host.classList.add('is-live');
      session.viewer.resize();next.last=performance.now();paint(next,false);
      lastFrame=performance.now();session.frame=requestAnimationFrame(tick);
    }else{
      host.classList.remove('is-live');document.body.append(host);session.viewer?.resize();
    }
  };
  document.addEventListener('visibilitychange',session.refresh,{signal:session.abort.signal});
  matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',session.refresh,{signal:session.abort.signal});

}
window.addEventListener('studio-page',event=>{
  if(event.detail.route==='targets'){startProjectPreviews();startLibraryAtmosphere();}
  else{stopProjectPreviews();stopLibraryAtmosphere();}
});

// Keep a small, steady population crossing the viewport. Web Animations handles
// transforms; JS only chooses a new trajectory when a molecule exits the screen.
let libraryAtmosphereSession=null,libraryAtmosphereTemplates=null;
function stopLibraryAtmosphere(){
  const session=libraryAtmosphereSession;libraryAtmosphereSession=null;
  if(!session)return;
  session.events.abort();cancelAnimationFrame(session.resizeFrame);
  session.particles.forEach(p=>p.animation?.cancel());session.host.replaceChildren();
}
function startLibraryAtmosphere(){
  if(libraryAtmosphereSession||currentPage!=='targets')return;
  const host=document.querySelector('.library-atmosphere');
  libraryAtmosphereTemplates||=[...host.querySelectorAll('svg')].slice(0,5).map(svg=>svg.cloneNode(true));
  const preference=matchMedia('(prefers-reduced-motion: reduce)');
  const session={host,events:new AbortController(),particles:[],resizeFrame:0};
  libraryAtmosphereSession=session;
  const valid=()=>libraryAtmosphereSession===session;
  const random=(low,high)=>low+Math.random()*(high-low);
  const paused=()=>projectPreviewsPaused||document.hidden||preference.matches;
  session.sync=()=>{
    if(!valid())return;
    host.classList.toggle('atmosphere-paused',paused());
    session.particles.forEach(p=>paused()?p.animation?.pause():p.animation?.play());
  };
  const travel=(particle,x,y)=>{
    if(!valid())return;
    const {size,element}=particle,width=host.clientWidth,height=host.clientHeight;
    const vx=random(9,15),vy=random(7,12);
    const seconds=Math.min((width+size-x)/vx,(y+size)/vy);
    particle.animation?.cancel();
    particle.animation=element.animate([
      {transform:`translate3d(${x}px,${y}px,0)`},
      {transform:`translate3d(${x+vx*seconds}px,${y-vy*seconds}px,0)`}
    ],{duration:seconds*1000,easing:'linear',fill:'forwards'});
    particle.animation.onfinish=()=>{
      if(!valid())return;
      // Weight the entry edges by their incoming flux for even screen coverage.
      if(Math.random()<height*vx/(height*vx+width*vy))travel(particle,-size,random(0,height));
      else travel(particle,random(-size,width-size),height);
    };
    if(paused())particle.animation.pause();
  };
  const populate=()=>{
    if(!valid())return;
    session.particles.forEach(p=>p.animation?.cancel());session.particles=[];host.replaceChildren();
    const columns=host.clientWidth<700?3:4,rows=3;
    const variantOffset=Math.floor(Math.random()*libraryAtmosphereTemplates.length);
    for(let index=0;index<columns*rows;index++){
      const size=random(130,host.clientWidth<700?190:245);
      const element=document.createElement('div');element.className='ambient-lane';
      element.style.setProperty('--size',size+'px');element.style.setProperty('--spin',random(40,75)+'s');
      element.style.setProperty('--delay',-random(0,75)+'s');element.style.setProperty('--turn',Math.random()<.5?'normal':'reverse');
      const svg=libraryAtmosphereTemplates[(index+variantOffset)%libraryAtmosphereTemplates.length].cloneNode(true);
      const gradient=svg.querySelector('radialGradient'),oldId=gradient.id,newId='ambient-live-'+index;
      gradient.id=newId;svg.querySelector(`[fill="url(#${oldId})"]`).setAttribute('fill',`url(#${newId})`);
      element.append(svg);host.append(element);
      const particle={element,size,animation:null};session.particles.push(particle);
      // Jitter within cells: different on every reload, with every region occupied.
      const x=((index%columns)+random(.15,.85))*host.clientWidth/columns-size/2;
      const y=(Math.floor(index/columns)+random(.15,.85))*host.clientHeight/rows-size/2;
      travel(particle,x,y);
    }
    session.sync();
  };
  const options={signal:session.events.signal};
  document.addEventListener('visibilitychange',session.sync,options);
  preference.addEventListener('change',session.sync,options);
  window.addEventListener('resize',()=>{
    cancelAnimationFrame(session.resizeFrame);session.resizeFrame=requestAnimationFrame(populate);
  },options);
  populate();
}

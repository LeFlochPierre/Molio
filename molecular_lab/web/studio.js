'use strict';
let currentMoleculeId=null, studioRuns=[], studioPoll=null, studioFetchingRuns=false;
const studioActivities=new Map();
const moleculeThumbnails=new Map();
let thumbnailRevision=0;
function beginStudioActivity(title,detail='You can keep exploring.'){
  const id=Symbol(title);studioActivities.set(id,{title,detail});renderStudioActivity();return id;
}
function updateStudioActivity(id,detail){const task=studioActivities.get(id);if(task){task.detail=detail;renderStudioActivity();}}
function endStudioActivity(id){studioActivities.delete(id);renderStudioActivity();}
function renderStudioActivity(){
  const task=[...studioActivities.values()][0];$('activity-tray').hidden=!task;
  document.body.classList.toggle('has-activity',!!task);
  if(task){$('activity-title').textContent=task.title;$('activity-detail').textContent=task.detail;}
}
// Actual requests drive this indicator; background polling never flashes a loader.
const studioFetch=window.fetch.bind(window);
window.fetch=async(resource,options)=>{
  const path=typeof resource==='string'?resource.split('?')[0]:'';
  const names={'/api/proteins/search':'Finding your protein','/api/targets/search':'Finding your protein','/api/starter/find-compounds':'Finding chemical structures','/api/starter/import-compound':'Preparing your molecule','/api/starter/compound':'Preparing your molecule','/api/starter/model':'Downloading the protein model','/api/preview':'Building the molecular preview','/api/designs':'Exploring structural variations','/api/design-shortlist':'Saving your selected ideas','/api/experiment-candidates':'Preparing your comparison','/api/proposals':options?.method==='POST'?'Saving your idea':null};
  const title=names[path]||(path.startsWith('/api/experiment-pose/')?'Opening the predicted complex':null);
  const id=title?beginStudioActivity(title):null;
  try{return await studioFetch(resource,options);}finally{if(id)endStudioActivity(id);}
};
function moleculeThumb(c){
  const thumbnail=moleculeThumbnails.get(c.id);
  if(thumbnail)return `<img src="${thumbnail}" alt="Generated free-molecule shape of ${escapeHTML(c.name||c.id)}"><span class="tile-shape-note">Open interactive 3D</span>`;
  return `<span class="thumbnail-placeholder">${state.conformers[c.id]?.status==='generated'?'Preparing shape…':'3D shape unavailable'}</span>`;
}
// One temporary renderer creates real conformer thumbnails, even for a large library.
// The cards themselves are images, so they never consume a WebGL context per molecule.
async function prepareMoleculeThumbnails(rows){
  const revision=++thumbnailRevision;
  if(currentPage!=='home')return;
  const pending=rows.filter(c=>!moleculeThumbnails.has(c.id)&&state.conformers[c.id]?.status==='generated');
  if(!pending.length){startGalleryMotion();return;}
  const host=document.createElement('div');host.className='thumbnail-renderer';host.setAttribute('aria-hidden','true');document.body.append(host);
  let viewer;
  try{
    viewer=$3Dmol.createViewer(host,{backgroundColor:'#ffffff',antialias:true});
    for(const c of pending){
      await new Promise(requestAnimationFrame);
      if(revision!==thumbnailRevision||currentPage!=='home')break;
      viewer.clear();viewer.addModel(state.conformers[c.id].molblock,'sdf');
      viewer.setStyle({},{stick:{radius:.14,colorscheme:'Jmol'},sphere:{scale:.24,colorscheme:'Jmol'}});
      viewer.zoomTo();viewer.zoom(1.2);viewer.render();moleculeThumbnails.set(c.id,viewer.pngURI());
      const card=[...$('home-molecules').querySelectorAll('[data-open-molecule]')].find(el=>el.dataset.openMolecule===c.id);
      if(card)card.querySelector('.tile-art').innerHTML=moleculeThumb(c);
    }
  }catch(_){
    $('home-molecules').querySelectorAll('.thumbnail-placeholder').forEach(el=>el.textContent='Open molecule to inspect');
  }finally{
    viewer?.clear();const canvas=host.querySelector('canvas');
    const gl=canvas&&(canvas.getContext('webgl')||canvas.getContext('experimental-webgl'));gl?.getExtension('WEBGL_lose_context')?.loseContext();host.remove();
    if(revision===thumbnailRevision)startGalleryMotion();
  }
}
function renderHome(){
  const d=state.data;if(!d)return;stopGalleryMotion();
  $('home-title').textContent='Room for your next idea.';
  $('home-subtitle').textContent=d.target.name+' · '+d.target.organism;
  $('home-protein-name').textContent=d.target.name;
  $('home-protein-info').textContent=(d.prediction_target?.sequence.length?d.prediction_target.sequence.length+' residues selected · ':'')+(d.mode==='starter'?(d.model_status.available?'Predicted model available':'Sequence workspace'):'Experimental reference available');
  $('home-add').textContent=d.mode==='starter'?'＋ Add molecule':'Explore measured series';
  $('home-molecule-count').textContent=d.compounds.length;
  const term=$('home-molecule-search').value.trim().toLowerCase();
  const rows=d.compounds.filter(c=>[c.id,c.name,c.smiles].join(' ').toLowerCase().includes(term));
  $('home-molecules').innerHTML=rows.map(c=>`<button class="molecule-tile" data-open-molecule="${escapeHTML(c.id)}"><span class="tile-top"><span class="tile-badge">${c.observation?'Measured compound':'Starting molecule'}</span><span aria-hidden="true">↗</span></span><span class="tile-art">${moleculeThumb(c)}</span><span class="tile-name">${escapeHTML(c.name||c.id)}</span><span class="tile-meta">${c.observation?number(c.observation.value)+' nM · measured IC₅₀':c.supporting_records?.length?'Assay records available · review source':'No measured activity assigned'}</span><span class="tile-bottom">${number(c.molecular_weight)} Da <span>Inspect molecule →</span></span></button>`).join('')||`<div class="home-empty"><span class="soft-emoji" aria-hidden="true">🧪</span><h3>${term?'No matching molecules':'A little space for something new.'}</h3><p>${term?'Try another name or clear your search.':'Find a compound by name, try an example, or bring your own SMILES.'}</p>${term?'':'<button class="primary" id="home-first-molecule">Add your first molecule ↗</button>'}</div>`;
  $('home-molecules').querySelectorAll('[data-open-molecule]').forEach(b=>b.onclick=()=>openMolecule(b.dataset.openMolecule));
  if($('home-first-molecule'))$('home-first-molecule').onclick=showMoleculeInputs;
  prepareMoleculeThumbnails(rows);
  renderRunOverview();
}
function showMoleculeInputs(){
  if(state.data?.mode==='starter'){goPage('starter');$('compound-search-form').scrollIntoView({block:'center',behavior:'smooth'});$('compound-search-query').focus({preventScroll:true});}
  else goPage('explore');
}
function openMolecule(id,push=true){
  const c=state.data?.compounds.find(c=>c.id===id);
  if(!c){activatePage('home',push);return;}
  currentMoleculeId=c.id;disposeMoleculeViews('detail-molecule-');$('detail-molecule-shape').replaceChildren();
  $('molecule-title').textContent=c.name||c.id;
  $('molecule-subtitle').textContent=state.data.target.name+' · '+(c.observation?'Measured source compound':'Starting molecule');
  $('molecule-facts').innerHTML=`<div><span>Molecular weight</span><strong>${number(c.molecular_weight)} <small>Da</small></strong></div><div><span>Measured activity</span><strong>${c.observation?number(c.observation.value)+' <small>nM IC₅₀</small>':'Not assigned'}</strong></div><div><span>Stereochemistry</span><strong>${c.unassigned_stereocentres?c.unassigned_stereocentres+' unspecified centres':'No unspecified tetrahedral centres'}</strong></div>`;
  $('molecule-smiles').innerHTML=smilesMarkup(c.canonical_smiles||c.smiles);bindSmilesCopies($('molecule-smiles'));
  $('molecule-source').innerHTML=`<p>${escapeHTML(c.origin?.evidence_note||c.source||'Compound from the workspace’s measured source series.')}</p>${c.source_url?`<a href="${escapeHTML(c.source_url)}" target="_blank" rel="noreferrer">Open source record ↗</a>`:''}${supportingRecordsMarkup(c.supporting_records)}`;
  $('molecule-design').onclick=()=>openDesigns(c.id);$('molecule-edit').onclick=()=>openVariant(c.id);$('molecule-predict').onclick=()=>openExperiments([c.id]);
  activatePage('molecule',push);moleculeView('detail-molecule-shape',state.conformers[c.id]);
}
function runProgress(job){
  const complete=(job.cases||[]).filter(c=>c.status==='complete').length,total=(job.cases||[]).length;
  const stage={queued:'In the queue',preparing:'Preparing model inputs',running:'Predicting molecular interactions',validating:'Checking prediction outputs'}[job.status]||job.status;
  return {complete,total,stage};
}
function renderRunOverview(){
  const active=studioRuns.find(j=>['queued','preparing','running','validating'].includes(j.status));
  $('home-runs').classList.toggle('is-running',!!active);
  $('run-dock').hidden=!active;$('home-active-run').hidden=!active;
  if(active){
    const p=runProgress(active);
    $('run-dock-title').textContent=p.stage;$('run-dock-detail').textContent=`${p.complete} of ${p.total} predictions complete · open runs`;
    $('home-active-run').innerHTML=`${labGearMarkup()}<div><strong>${escapeHTML(p.stage)}</strong><p>${p.complete} of ${p.total} predictions complete. You can keep exploring.</p><progress max="${p.total||1}" value="${p.complete}" aria-label="Completed predictions"></progress></div><button id="home-view-active">View run ↗</button>`;
    $('home-view-active').onclick=()=>openExperiments();
  }
  $('home-run-title').textContent=active?'An experiment is underway':studioRuns.length?studioRuns.length+' saved experiment'+(studioRuns.length===1?'':'s'):'Your next discovery';
  $('home-run-info').textContent=active?'Follow its progress while you explore.':studioRuns.length?'Open the results, inspect a pose, or try another idea.':'Prepare a prediction, then inspect the result.';
}
async function refreshStudioRuns(){
  if(!state.data||studioFetchingRuns||document.hidden)return;
  studioFetchingRuns=true;
  try{const response=await fetch('/api/experiments');if(!response.ok)throw Error();const data=await response.json();studioRuns=data.experiments;renderRunOverview();}
  catch(_){$('home-run-info').textContent='Run status unavailable. Open Experiments to retry.';if(!$('run-dock').hidden){$('run-dock-title').textContent='Reconnecting to your run';$('run-dock-detail').textContent='Status unavailable · open runs to check';}}
  finally{studioFetchingRuns=false;}
}
window.addEventListener('workspace-ready',()=>{
  document.body.classList.remove('is-booting');
  if(state.data){renderHome();refreshStudioRuns();clearInterval(studioPoll);studioPoll=setInterval(refreshStudioRuns,8000);}
});
window.addEventListener('studio-page',event=>{
  const route=event.detail.route;document.body.classList.toggle('welcome-mode',route==='welcome');
  $('back-to-workspace').hidden=targetLanding||['home','welcome'].includes(route);
  if(route==='home')renderHome();
});
document.addEventListener('DOMContentLoaded',()=>{
  $('welcome-start').onclick=()=>goPage('targets');$('back-to-workspace').onclick=()=>goPage('home');
  $('home-add').onclick=showMoleculeInputs;$('home-protein').onclick=()=>goPage(state.data.mode==='starter'?'starter':'pocket');
  $('home-runs').onclick=()=>openExperiments();$('home-saved').onclick=()=>$('open-proposals').click();
  $('home-molecule-search').oninput=renderHome;$('close-molecule').onclick=()=>closePage('molecule-page');
  $('molecule-page').addEventListener('close',()=>disposeMoleculeViews('detail-molecule-'));
  $('run-dock').onclick=()=>openExperiments();
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshStudioRuns();});
});

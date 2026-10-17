'use strict';
let guidedRevision = 0;
let variantParent = null, previewRevision = 0, previewController = null, previewTimer, latestPreview = null;
const svgImage = svg => 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
async function apiJSON(path, options={}) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw Error(data.error || 'The request could not be completed.');
  return data;
}
function variantPayload() {return {parent_id:variantParent,smiles:$('variant-smiles').value,name:$('variant-name').value,hypothesis:$('variant-hypothesis').value};}
function invalidatePreview() {
  disposeMoleculeViews('variant-');
  $('variant-edit-evidence').hidden=true;
  previewRevision++; clearTimeout(previewTimer); previewController?.abort(); latestPreview=null;
  $('save-variant').disabled=true; $('variant-preview').hidden=true;
  $('variant-status').classList.remove('error'); $('variant-status').textContent='Checking your structure…';
}
function openVariant(parentId) {
  if(!parentId){goPage('starter');return toast('Add a starting molecule first.');}
  invalidatePreview(); variantParent=parentId;
  const parent=state.data.compounds.find(c=>c.id===parentId);
  $('variant-title').textContent='Create a variant of '+parentId;
  $('variant-smiles').value=parent.smiles; $('variant-name').value=''; $('variant-hypothesis').value='';
  openPage('variant-dialog'); setRotation(false); previewVariant(); loadGuidedEdits(parentId);
}
async function previewVariant() {
  const revision=previewRevision; previewController=new AbortController();
  try {
    const data=await apiJSON('/api/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(variantPayload()),signal:previewController.signal});
    if(revision!==previewRevision || !isPageOpen('variant-dialog'))return;
    latestPreview=data;
    $('variant-status').textContent=data.warnings.join(' ') || 'Structure checked. Review the differences, then describe the experiment you have in mind.';
    $('variant-edit-evidence').innerHTML=evidenceMarkup(data.edit_evidence);$('variant-edit-evidence').hidden=false;
    const labels=[['molecular_weight','Molecular weight','Da'],['clogp','Calculated logP',''],['tpsa','Polar surface area','Å²'],['hbd','H-bond donors',''],['hba','H-bond acceptors','']];
    $('variant-preview').innerHTML=`<div class="preview-drawings"><article><small>PARENT · ${state.data.compounds.find(c=>c.id===variantParent)?.observation?'MEASURED COMPOUND':'UNMEASURED INPUT'}</small><div id="variant-parent" class="molecule-canvas"></div><details><summary>2D structure</summary><img alt="Parent structure with changes highlighted" src="${svgImage(data.parent_depiction.svg)}"></details></article><article><small>YOUR PROPOSAL · NO ACTIVITY ASSIGNED</small><div id="variant-proposal" class="molecule-canvas"></div><details><summary>2D structure</summary><img alt="Proposed structure with changes highlighted" src="${svgImage(data.depiction.svg)}"></details></article></div><p class="descriptor-help">${data.common_core_available?'Purple in 3D and amber in 2D mark atoms outside the shared core.':'A common-core alignment is unavailable.'}</p><table class="descriptor-table"><thead><tr><th>Calculated property</th><th>Parent</th><th>Proposal</th><th>Change</th></tr></thead><tbody>${labels.map(([key,label,unit])=>{const delta=Number((data.descriptors[key]-data.parent_descriptors[key]).toFixed(2));return `<tr><td>${label}${unit?' ('+unit+')':''}</td><td>${data.parent_descriptors[key]}</td><td>${data.descriptors[key]}</td><td>${delta>0?'+':''}${delta}</td></tr>`;}).join('')}</tbody></table><p class="descriptor-help">LogP estimates lipophilicity; polar surface area describes exposed polar atoms. These properties do not tell us whether the molecule will bind.</p><h3>Related measured compounds</h3><p>${escapeHTML(data.neighbour_scope)}</p><div class="neighbour-list">${data.neighbours.map(n=>`<a href="${n.source_url}" target="_blank" rel="noreferrer"><strong>${n.id}${n.exact_identity?' · same structure':''}</strong><span>${Math.round(n.similarity*100)}% fingerprint similarity · IC₅₀ ${number(n.observation.value)} nM</span></a>`).join('')}</div>`;
    $('variant-preview').hidden=false;
    moleculeView('variant-parent',data.parent_conformer,data.parent_depiction.changed_atoms);moleculeView('variant-proposal',data.conformer,data.depiction.changed_atoms);
    $('save-variant').disabled=data.same_as_parent;
  }catch(error){if(error.name==='AbortError'||revision!==previewRevision)return;$('variant-status').textContent=error.message;$('variant-status').classList.add('error');}
}
$('variant-smiles').oninput=()=>{invalidatePreview();previewTimer=setTimeout(previewVariant,450);};
$('close-variant').onclick=()=>closePage('variant-dialog');
$('variant-dialog').addEventListener('close',()=>{guidedRevision++;invalidatePreview();});
$('save-variant').onclick=async()=>{
  if(!latestPreview)return;
  const revision=previewRevision; const payload=variantPayload();
  $('save-variant').disabled=true;
  try {
    await apiJSON('/api/proposals',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(revision===previewRevision){closePage('variant-dialog');toast('Proposal saved locally. No activity or bound pose has been assigned.');}
  }catch(error){if(revision===previewRevision){$('variant-status').textContent=error.message;$('save-variant').disabled=false;}}
};
$('open-proposals').onclick=async()=>{
  openPage('proposals-dialog'); $('proposals-list').textContent='Loading saved ideas…';
  try {
    const {proposals}=await apiJSON('/api/proposals');
    $('proposals-list').innerHTML=proposals.length?proposals.map((p,i)=>`<article class="proposal-row"><div><strong>${escapeHTML(p.name)}</strong><span class="proposal-tag">PROPOSAL</span><p>${escapeHTML(p.hypothesis||'No experimental question recorded.')}</p><small>From ${escapeHTML(p.parent_id)} · ${new Date(p.created_at).toLocaleDateString()} · no activity assigned</small></div><button data-export-proposal="${i}">Export JSON</button></article>`).join(''):'<div class="proposal-empty">Your next experiment starts with a small change.<p>Choose “Create a variant” under either measured molecule.</p></div>';
    $('proposals-list').querySelectorAll('button').forEach(b=>b.onclick=()=>{const p=proposals[Number(b.dataset.exportProposal)];const url=URL.createObjectURL(new Blob([JSON.stringify(p,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='whatif-proposal-'+p.id+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  }catch(error){$('proposals-list').textContent=error.message;}
};
$('close-proposals').onclick=()=>closePage('proposals-dialog');

async function loadGuidedEdits(parentId) {
  const revision=++guidedRevision;
  $('guided-options').textContent='Finding supported changes…';$('guided-note').textContent='';
  try {
    const data=await apiJSON('/api/suggestions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({parent_id:parentId})});
    if(revision!==guidedRevision || !isPageOpen('variant-dialog'))return;
    $('guided-note').textContent=data.note;
    $('guided-options').innerHTML=data.suggestions.length?data.suggestions.map((s,i)=>`<button class="guided-option" data-suggestion="${i}"><strong>${escapeHTML(s.label)}</strong><span>${s.known_compound_ids.length?(state.data.assay?'Already measured in this library':'Already in this library'):'Untested structure in this library'} · preview →</span></button>`).join(''):'<p>No supported one-step edits for this parent yet. You can still enter a structure manually.</p>';
    $('guided-options').querySelectorAll('button').forEach(b=>b.onclick=()=>{
      const suggestion=data.suggestions[Number(b.dataset.suggestion)];
      invalidatePreview();$('variant-smiles').value=suggestion.smiles;
      if(!$('variant-name').value)$('variant-name').value=suggestion.label;
      if(!$('variant-hypothesis').value)$('variant-hypothesis').value=suggestion.hypothesis;
      previewVariant();
    });
  }catch(error){if(revision===guidedRevision)$('guided-options').textContent=error.message;}
}

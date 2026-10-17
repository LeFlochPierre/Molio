'use strict';
let designData=null, designRevision=0, designPreviewRevision=0, designSaving=false;
function chosenDesigns(){return [...$('design-list').querySelectorAll('input:checked')].map(i=>i.value);}
function updateDesignSelection(){const count=chosenDesigns().length;$('design-count').textContent=`${count} / 2 designs selected · parent included as baseline`;$('compare-designs').disabled=designSaving||count<1||count>2;}
async function inspectDesign(id){
  const row=designData?.candidates.find(c=>c.id===id);if(!row)return;
  const revision=++designPreviewRevision,parent=designData.parent_id;
  disposeMoleculeViews('design-');$('design-parent-shape').replaceChildren();$('design-new-shape').replaceChildren();$('design-properties').replaceChildren();$('design-selected-title').textContent=row.label;$('design-preview-status').textContent='Preparing the molecular comparison…';
  $('design-list').querySelectorAll('.design-card').forEach(el=>el.classList.toggle('inspecting',el.dataset.design===id));
  try{const result=await experimentJSON('/api/preview',{parent_id:parent,smiles:row.smiles});if(revision!==designPreviewRevision||!isPageOpen('designs-dialog'))return;
    moleculeView('design-parent-shape',result.parent_conformer,result.parent_depiction.changed_atoms);moleculeView('design-new-shape',result.conformer,result.depiction.changed_atoms);
    $('design-properties').innerHTML=smilesMarkup(row.smiles)+`<table class="descriptor-table"><thead><tr><th>Property</th><th>Parent</th><th>Design</th></tr></thead><tbody>${[['molecular_weight','Molecular weight (Da)'],['clogp','Calculated logP'],['tpsa','Polar surface area (Å²)']].map(([key,name])=>`<tr><td>${name}</td><td>${result.parent_descriptors[key]}</td><td>${result.descriptors[key]}</td></tr>`).join('')}</tbody></table><details class="low-priority"><summary>About these properties</summary><p>Calculated size, lipophilicity and polarity—not measured binding or safety.</p></details>`;
    bindSmilesCopies($('design-properties'));
    $('design-preview-status').textContent=result.warnings.join(' ')||'Valid molecular structure. No binding result is available yet.';
  }catch(e){if(revision===designPreviewRevision)$('design-preview-status').textContent=e.message;}
}
async function loadDesigns(){
  const parent=state.data.compounds.find(c=>c.id===$('design-parent').value);
  $('design-smiles').innerHTML=parent?'<span>Starting molecule</span>'+smilesMarkup(parent.canonical_smiles||parent.smiles):'';bindSmilesCopies($('design-smiles'));
  const revision=++designRevision;designPreviewRevision++;designData=null;disposeMoleculeViews('design-');$('design-parent-shape').replaceChildren();$('design-new-shape').replaceChildren();$('design-properties').replaceChildren();$('design-preview-status').textContent='';$('design-selected-title').textContent='Select an idea to inspect';$('design-list').replaceChildren();$('design-scope').textContent='';$('design-status').textContent='Generating a small set of one-step ideas…';updateDesignSelection();
  try{const data=await experimentJSON('/api/designs',{parent_id:$('design-parent').value});if(revision!==designRevision||!isPageOpen('designs-dialog'))return;designData=data;
    $('design-status').textContent=`${data.candidates.length} structural ideas · unranked · same ring scaffold`;$('design-scope').textContent=data.scope;
    $('design-list').innerHTML=data.candidates.map((c,i)=>`<article class="design-card" data-design="${c.id}"><div><label><input type="checkbox" value="${c.id}"><strong>${i+1}. ${escapeHTML(c.label)}</strong></label><button data-inspect-design="${c.id}">Inspect 3D ↗</button></div><small>${c.known_compound_id?'Already in this library: '+escapeHTML(c.known_compound_id):'Not measured in the local library'}</small><details><summary>Why this edit?</summary><p>${escapeHTML(c.reason)}</p><code>${escapeHTML(c.smiles)}</code><p>${escapeHTML(c.hypothesis)}</p></details></article>`).join('')||'<p>No supported edits for this parent. You can still create a variant manually.</p>';
    $('design-list').querySelectorAll('input').forEach(el=>el.onchange=updateDesignSelection);$('design-list').querySelectorAll('[data-inspect-design]').forEach(b=>b.onclick=()=>inspectDesign(b.dataset.inspectDesign));
    if(data.candidates.length)inspectDesign(data.candidates[0].id);
  }catch(e){if(revision===designRevision)$('design-status').textContent=e.message;}
}
function openDesigns(parentId=null){if(!state.data)return toast('The dataset is still loading.');if(!state.data.compounds.length){goPage('starter');$('compound-search-query').focus();$('compound-search-form').scrollIntoView({block:'center',behavior:'smooth'});return toast('Choose a compound by name, an offline example, or your own SMILES.');}$('design-parent').innerHTML=state.data.compounds.map(c=>`<option value="${c.id}">${escapeHTML(c.name||c.id)} · ${c.observation?number(c.observation.value)+' nM measured IC₅₀':'unmeasured input'}</option>`).join('');$('design-parent').value=parentId||state.pair?.left||state.data.compounds[0].id;openPage('designs-dialog');setRotation(false);loadDesigns();};
$('open-designs').onclick=()=>openDesigns();
$('design-parent').onchange=loadDesigns;
$('close-designs').onclick=()=>closePage('designs-dialog');
$('designs-dialog').addEventListener('close',()=>{designRevision++;designPreviewRevision++;disposeMoleculeViews('design-');});
$('compare-designs').onclick=async()=>{if(!designData||designSaving)return;const revision=designRevision;designSaving=true;updateDesignSelection();$('design-parent').disabled=true;
  try{const result=await experimentJSON('/api/design-shortlist',{parent_id:designData.parent_id,design_ids:chosenDesigns()});if(revision!==designRevision)return;closePage('designs-dialog');await openExperiments(result.candidate_ids);$('experiment-message').textContent='Parent selected first as baseline. Review stereochemistry and settings, then run the comparison.';}
  catch(e){if(revision===designRevision)$('design-status').textContent=e.message;}
  finally{designSaving=false;$('design-parent').disabled=false;updateDesignSelection();}
};

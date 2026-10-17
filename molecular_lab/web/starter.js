'use strict';
let starterViewer=null, starterSpinning=false;
function starterReadiness(){
  const d=state.data,p=d.prediction_target;
  if(typeof renderHome==='function')renderHome();
  $('starter-readiness').innerHTML=[['Sequence','Downloaded · '+d.protein_sequence.length+' residues'],['3D model',d.model_status.available?'Downloaded':'Optional · unavailable'],['Measurements','Optional · none imported'],['Prediction input',p?(d.compounds.length?'Sequence + molecules ready':'Choose a molecule below'):'Choose a smaller region']].map(([a,b])=>`<div><span>${a}</span><strong>${b}</strong></div>`).join('');
  $('starter-region-status').textContent=p?`Selected: UniProt ${p.provenance.start}–${p.provenance.end} · ${p.sequence.length} residues. Model residue 1 corresponds to UniProt ${p.provenance.start}.`:'No prediction region selected. Full protein remains available for viewing.';
  $('prediction-target-label').textContent=p?`Boltz-2 · ${d.target.name} · UniProt ${p.provenance.start}–${p.provenance.end}`:'Choose a prediction region in Workspace';
  $('imported-prediction-note').hidden=false;
}
function starterStyle(){
  if(!starterViewer)return;
  starterViewer.setStyle({}, {cartoon:{colorfunc:a=>a.b>=90?'#0053d6':a.b>=70?'#65cbf3':a.b>=50?'#ffdb13':'#ff7d45'}});
  const p=state.data.prediction_target;
  if(p&&p.sequence.length!==state.data.protein_sequence.length)starterViewer.addStyle({resi:Array.from({length:p.sequence.length},(_,i)=>p.provenance.start+i)},{cartoon:{color:'#7855c8'}});
}
async function showStarterProtein(){
  const d=state.data;$('starter-model-status').textContent=d.model_status.message;
  $('starter-retry-model').hidden=d.model_status.available;$('starter-spin').disabled=!d.model_status.available;$('starter-reset-view').disabled=!d.model_status.available;
  $('starter-model-source').hidden=!d.reference_structure;
  if(!d.reference_structure){$('starter-protein-view').textContent='Sequence ready. A 3D model is optional for starting a project.';return;}
  $('starter-model-source').href=d.reference_structure.source_url;
  try{
    const r=await fetch(d.reference_structure.url);if(!r.ok)throw Error('Stored model unavailable');
    const text=await r.text();$('starter-protein-view').replaceChildren();
    starterViewer=$3Dmol.createViewer($('starter-protein-view'),{backgroundColor:'#ffffff',antialias:true});starterViewer.addModel(text,'pdb');starterStyle();starterViewer.zoomTo();starterViewer.render();
    let label=null;
    starterViewer.setHoverDuration(100);starterViewer.setHoverable({atom:'CA'},true,a=>{
      starterViewer.spin(false);starterSpinning=false;$('starter-spin').textContent='Rotate';
      starterStyle();starterViewer.addStyle({resi:a.resi},{stick:{color:'#7855c8',radius:.2}});
      if(label)starterViewer.removeLabel(label);label=starterViewer.addLabel(`${a.resn} ${a.resi} · confidence ${Number(a.b).toFixed(0)}`,{position:a,fontSize:12,backgroundColor:'#274e45'});
      $('starter-protein-view').dataset.hoveredResidue=String(a.resi);starterViewer.render();
    },()=>{starterStyle();if(label)starterViewer.removeLabel(label);label=null;starterViewer.render();});
    const observer=new ResizeObserver(()=>{starterViewer.resize();starterViewer.render();});observer.observe($('starter-protein-view'));
    $('starter-protein-view').dataset.ready='true';
    $('starter-spin').onclick=()=>{starterSpinning=!starterSpinning;starterViewer.spin(starterSpinning?'y':false,.2);$('starter-spin').textContent=starterSpinning?'Pause rotation':'Rotate';};
    $('starter-reset-view').onclick=()=>{starterViewer.zoomTo();starterViewer.render();};
    if(!matchMedia('(prefers-reduced-motion: reduce)').matches)$('starter-spin').click();
    document.addEventListener('visibilitychange',()=>{if(document.hidden){starterViewer.spin(false);starterSpinning=false;$('starter-spin').textContent='Rotate';}});
    $('starter-protein-view').addEventListener('pointerdown',()=>{starterViewer.spin(false);starterSpinning=false;$('starter-spin').textContent='Rotate';});
  }catch(e){$('starter-model-status').textContent='3D display unavailable: '+e.message;}
}
function renderStarterCompounds(){
  if(typeof renderHome==='function')renderHome();
  disposeMoleculeViews('starter-molecule-');
  $('starter-compounds').innerHTML=state.data.compounds.map(c=>`<article class="starter-molecule"><div><strong>${escapeHTML(c.name||c.id)}</strong><small>${c.supporting_records?.length?'Assay source records available · not a compared series':'Unmeasured input'} · ${number(c.molecular_weight)} Da</small></div>${smilesMarkup(c.canonical_smiles||c.smiles)}${c.origin?`<p class="map-help">${escapeHTML(c.origin.evidence_note)} ${c.source_url?`<a href="${escapeHTML(c.source_url)}" target="_blank" rel="noreferrer">${escapeHTML(c.source)} ↗</a>`:escapeHTML(c.source)}</p>`:''}${supportingRecordsMarkup(c.supporting_records)}<div id="starter-molecule-${c.id}" class="molecule-canvas"></div><div class="starter-view-tools"><button data-design-input="${c.id}">Explore designs</button><button data-edit-input="${c.id}">Edit SMILES</button><button data-predict-input="${c.id}">Predict</button></div></article>`).join('')||'<p class="starter-empty">No molecules yet. Your first structure goes here.</p>';
  // Keep one live molecular viewer. Others open on demand to avoid exhausting WebGL contexts.
  $('starter-compounds').querySelectorAll('.molecule-canvas').forEach((el,i)=>{if(i===0)moleculeView(el.id,state.conformers[state.data.compounds[i].id]);else{const b=document.createElement('button');b.textContent='Inspect 3D';b.onclick=()=>{disposeMoleculeViews('starter-molecule-');renderStarterCompoundsFor(state.data.compounds[i].id);};el.append(b);}});
  bindSmilesCopies($('starter-compounds'));
  $('starter-compounds').querySelectorAll('[data-design-input]').forEach(b=>b.onclick=()=>openDesigns(b.dataset.designInput));
  $('starter-compounds').querySelectorAll('[data-edit-input]').forEach(b=>b.onclick=()=>openVariant(b.dataset.editInput));
  $('starter-compounds').querySelectorAll('[data-predict-input]').forEach(b=>b.onclick=()=>openExperiments([b.dataset.predictInput]));
}
function renderStarterCompoundsFor(id){
  // Rerender the buttons so a previous molecule can be opened again.
  $('starter-compounds').querySelectorAll('.molecule-canvas').forEach(el=>{el.replaceChildren();const cid=el.id.replace('starter-molecule-','');if(cid===id)moleculeView(el.id,state.conformers[cid]);else{const b=document.createElement('button');b.textContent='Inspect 3D';b.onclick=()=>{disposeMoleculeViews('starter-molecule-');renderStarterCompoundsFor(cid);};el.append(b);}});
}
async function startStarter(){
  const d=state.data;document.body.classList.add('starter-workspace');openedPages.clear();openedPages.add('home');currentPage='home';pageVisits=['home'];
  $('project-target').textContent=d.target.name;$('project-organism').textContent=d.target.organism;$('project-avatar').textContent=d.target.name[0];
  $('starter-title').textContent=d.target.name;$('starter-subtitle').textContent=`${d.target.organism} · ${d.target.uniprot} · a workspace for your own molecules`;
  $('starter-protein-source').href=`https://www.uniprot.org/uniprotkb/${d.target.uniprot}/entry`;
  $('starter-download').href=d.dataset_url;$('starter-limitations').innerHTML=d.provenance.limitations.map(x=>`<li>${escapeHTML(x)}</li>`).join('');
  document.title=d.target.name+' · Molio';$('open-explore').lastChild.textContent='Protein & inputs';$('open-explore').dataset.route='starter';
  $('starter-domains').innerHTML='<option value="">Choose an annotated domain…</option>'+d.domains.map(r=>`<option value="${r.start}:${r.end}" ${r.end-r.start+1<40||r.end-r.start+1>600?'disabled':''}>${escapeHTML(r.name)} · ${r.start}–${r.end}</option>`).join('');
  const region=d.prediction_target?.provenance;
  $('starter-region-start').value=region?.start||'';$('starter-region-end').value=region?.end||'';$('starter-region-start').max=d.protein_sequence.length;$('starter-region-end').max=d.protein_sequence.length;
  $('starter-region-details').open=!region;starterReadiness();
  $('starter-domains').onchange=()=>{const [a,b]=$('starter-domains').value.split(':');$('starter-region-start').value=a||'';$('starter-region-end').value=b||'';};
  $('starter-region-form').onsubmit=async event=>{event.preventDefault();const button=event.submitter;button.disabled=true;
    try{state.data=await experimentJSON('/api/starter/region',{start:Number($('starter-region-start').value),end:Number($('starter-region-end').value)});starterReadiness();starterStyle();starterViewer?.render();$('starter-region-message').textContent='Region saved. Highlighted purple in the model; confidence colours remain on the rest of the protein.';}
    catch(e){$('starter-region-message').textContent=e.message;}finally{button.disabled=false;}
  };
  $('starter-compound-form').onsubmit=async event=>{event.preventDefault();$('starter-add-compound').disabled=true;$('starter-compound-status').textContent='Checking chemistry and generating a 3D shape…';
    try{const r=await experimentJSON('/api/starter/compound',{name:$('starter-compound-name').value,smiles:$('starter-smiles').value});state.data.compounds.push(r.compound);state.conformers[r.compound.id]=r.conformer;renderStarterCompounds();starterReadiness();$('starter-compound-status').textContent='Molecule saved locally. Explore designs or prepare a prediction.';$('starter-compound-form').reset();}
    catch(e){$('starter-compound-status').textContent=e.message;}finally{$('starter-add-compound').disabled=false;}
  };
  $('starter-retry-model').onclick=async()=>{$('starter-retry-model').disabled=true;$('starter-model-status').textContent='Downloading the optional model…';try{state.data=await experimentJSON('/api/starter/model',{});starterReadiness();await showStarterProtein();}catch(e){$('starter-model-status').textContent=e.message;}finally{$('starter-retry-model').disabled=false;}};
  state.conformers=await (await fetch(d.conformers_url)).json();renderStarterCompounds();
  startCompoundLibrary();await showStarterProtein();
}

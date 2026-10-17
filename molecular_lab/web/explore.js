'use strict';
let mapSelection = null;
function selectMapCompound(id) {
  const compound=state.data.compounds.find(c=>c.id===id);if(!compound)return;
  mapSelection=id;
  document.querySelectorAll('.map-row').forEach(row=>{const active=row.dataset.compound===id;row.classList.toggle('selected',active);row.setAttribute('aria-pressed',active);});
  $('map-compound').textContent=id;$('map-value').textContent=number(compound.observation.value)+' nM IC₅₀';
  $('map-stereo').textContent=compound.unassigned_stereocentres?'Assay stereochemistry is unspecified. This 3D shape is one illustrative realization.':'Recorded molecular connectivity; one generated conformer shown.';
  $('map-source').href=compound.source_url;
  disposeMoleculeViews('map-');$('map-molecule').replaceChildren();moleculeView('map-molecule',state.conformers[id]);
}
$('open-map').onclick=()=>{
  if(!state.data)return toast('The dataset is still loading.');
  setRotation(false);openPage('activity-map');
  const compounds=[...state.data.compounds].sort((a,b)=>a.observation.value_M-b.observation.value_M||a.id.localeCompare(b.id));
  const values=compounds.map(c=>Math.log10(c.observation.value_M*1e9));
  const low=Math.floor(Math.min(...values)),high=Math.max(low+1,Math.ceil(Math.max(...values)));
  $('map-axis').innerHTML=[low,(low+high)/2,high].map(v=>`<span>${number(10**v)} nM</span>`).join('');
  $('map-rows').innerHTML=compounds.map(c=>{
    const percent=100*(Math.log10(c.observation.value_M*1e9)-low)/(high-low);
    return `<button class="map-row" data-compound="${c.id}" aria-pressed="false" aria-label="${c.id}, measured IC50 ${number(c.observation.value)} nanomolar"><span>${c.id.replace('CHEMBL','')}</span><span class="map-track"><span class="map-dot" style="left:${percent}%"></span></span><strong>${number(c.observation.value)}</strong></button>`;
  }).join('');
  $('map-rows').querySelectorAll('button').forEach(b=>b.onclick=()=>selectMapCompound(b.dataset.compound));
  selectMapCompound(mapSelection || state.pair.right);
};
$('close-map').onclick=()=>closePage('activity-map');
$('activity-map').addEventListener('close',()=>disposeMoleculeViews('map-'));
$('map-design').onclick=()=>{const id=mapSelection;closePage('activity-map');openVariant(id);};
function expandProtein(expanded) {
  document.body.classList.toggle('protein-expanded',expanded);
  $('expand-protein').setAttribute('aria-expanded',expanded);
  $('expand-protein').textContent=expanded?'Close expanded view ↙':'Expand view ↗';
  requestAnimationFrame(()=>{state.viewer?.resize();state.viewer?.render();});
}
$('expand-protein').onclick=()=>expandProtein(!document.body.classList.contains('protein-expanded'));
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&document.body.classList.contains('protein-expanded')){expandProtein(false);$('expand-protein').focus();}});

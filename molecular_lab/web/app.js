'use strict';
const $ = id => document.getElementById(id);
const state = {data: null, pair: null, viewer: null, pocket: true, surface: false, waters: false, measure: false, picked: [], pins: [], notes: {}, surfaceVersion: 0, rotating: false, conformers: {}, moleculeMode: '3d'};
const escapeHTML = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = value => Number(value).toLocaleString('en-GB', {maximumFractionDigits: 1});
let toastTimer;
function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 4000); }
function persist() {
  try { localStorage.setItem(workspaceStorageKey, JSON.stringify({pins: state.pins, notes: state.notes})); $('note-status').textContent = 'Saved in this browser · included in your export.'; }
  catch (_) { $('note-status').textContent = 'Browser storage unavailable. Export to save your notes.'; }
}
function restore() {
  try {
    const saved = JSON.parse(localStorage.getItem(workspaceStorageKey) || '{}');
    const ids = new Set(state.data.pairs.map(p => p.id));
    state.pins = Array.isArray(saved.pins) ? [...new Set(saved.pins.filter(id => ids.has(id)))] : [];
    state.notes = Object.fromEntries(Object.entries(saved.notes || {}).filter(([id, v]) => ids.has(id) && typeof v === 'string').map(([id, v]) => [id, v.slice(0, 4000)]));
  } catch (_) { state.pins = []; state.notes = {}; }
}
function updatePin() { const pinned = state.pins.includes(state.pair.id); $('pin').textContent = pinned ? '✓ Shortlisted' : '＋ Shortlist'; $('pin').setAttribute('aria-pressed', pinned); $('pin-count').textContent = state.pins.length; }
function renderList() {
  const term = $('search').value.toLowerCase().trim();
  const pairs = state.data.pairs.filter(p => `${p.title} ${p.left} ${p.right}`.toLowerCase().includes(term));
  $('pair-count').textContent = `${pairs.length} / ${state.data.pairs.length}`;
  $('pair-list').innerHTML = pairs.map(p => {
    const fold = p.fold_lower_ic50_right, magnitude = Math.max(fold, 1 / fold);
    return `<button class="pair-item ${state.pair?.id === p.id ? 'active' : ''}" data-pair="${p.id}" aria-pressed="${state.pair?.id === p.id}"><strong>${escapeHTML(p.title)}</strong><small><span>${p.left.slice(-3)} → ${p.right.slice(-3)}</span><b>${number(magnitude)}× ${fold >= 1 ? 'lower' : 'higher'} IC₅₀</b></small></button>`;
  }).join('');
  $('no-results').hidden = pairs.length !== 0;
  $('pair-list').querySelectorAll('button').forEach(button => button.onclick = () => selectPair(button.dataset.pair));
}
function selectPair(id) {
  const pair = state.data.pairs.find(p => p.id === id); if (!pair) return;
  disposeMoleculeViews('compound-');
  state.pair = pair;
  $('pair-title').textContent = pair.title;
  $('comparison').innerHTML = ['left', 'right'].map((side, i) => {
    const c = state.data.compounds.find(c => c.id === pair[side]);
    return `<article class="compound-card"><div class="compound-top"><span class="compound-label">${i ? 'B / COMPARE' : 'A / START HERE'}</span><a href="${c.source_url}" target="_blank" rel="noreferrer">${c.id} ↗</a></div><div id="compound-${c.id}" class="molecule-canvas" aria-label="Interactive generated 3D shape of ${c.id}"></div><img class="molecule-2d" src="${pair.depictions[c.id]}" alt="${c.id}; changed atoms highlighted" hidden><div class="shape-note">Generated free shape · not a bound pose</div><div class="stereo-note">${c.unassigned_stereocentres ? 'Stereochemistry unspecified in assay record' : 'No unspecified tetrahedral stereocentres'}</div><div class="compound-bottom"><div><span class="activity-number">${number(c.observation.value)}</span><span class="unit">nM</span></div><span class="activity-caption">MEASURED IC₅₀<br>ChEMBL activity ${c.observation.activity_id}</span></div><button class="create-variant" data-parent="${c.id}">Create a variant of ${i ? 'B' : 'A'} →</button></article>`;
  }).join('');
  $('edit-insight').innerHTML=evidenceMarkup(state.data.edit_evidence[pair.id]);
  for(const cid of [pair.left,pair.right])moleculeView('compound-'+cid,state.conformers[cid],pair.atom_mapping[cid].changed_atoms);
  setMoleculeMode(state.moleculeMode);
  const fold = pair.fold_lower_ic50_right;
  $('fold').textContent = `${number(Math.max(fold, 1 / fold))}×`;
  $('fold-label').textContent = `${fold >= 1 ? 'lower' : 'higher'} IC₅₀ for compound B`;
  $('hypothesis').value = state.notes[id] || '';
  const related = [pair.left, pair.right].includes(state.data.reference_structure.related_compound);
  $('reference-note').textContent = related
    ? 'ODR shares connectivity with CHEMBL1828986, but its resolved stereochemistry is not specified in the assay record. This is not an exact assay-to-pose match.'
    : 'The displayed ligand is ODR, a related member of the series. Neither selected compound is shown as a bound pose.';
  $('structure-context').textContent = related
    ? '3SVG shows BRD4 with a stereochemically specified form of the alcohol compound. The assay leaves that stereochemistry unspecified. We cannot assign its measured IC₅₀ to this individual form.'
    : 'The 3D view stays on the verified BRD4 / ODR experimental reference. There is no verified bound pose for either selected compound in this dataset.';
  if(activeWorkspace!=='brd4'){
    const r=state.data.reference_structure;
    $('reference-note').textContent=`${r.id} / ${r.ligand}: ${r.caveat}`;
    $('structure-context').textContent=`${state.data.target.name} · ${r.id}, protein chain ${r.chain}. ${r.caveat} Assay and structure constructs may differ.`;
  }
  updatePin(); renderList();
  document.querySelectorAll('.create-variant').forEach(b => b.onclick = () => openVariant(b.dataset.parent));
}
function setMoleculeMode(mode) {
  state.moleculeMode=mode;
  document.querySelectorAll('#comparison .molecule-canvas').forEach(el=>el.hidden=mode!=='3d');
  document.querySelectorAll('#comparison .molecule-2d').forEach(el=>el.hidden=mode!=='2d');
  for(const key of ['2d','3d']){$('mode-'+key).classList.toggle('active',key===mode);$('mode-'+key).setAttribute('aria-pressed',key===mode);}
}
function renderLibrary() {
  $('compound-table').innerHTML = `<div class="compound-grid">${[...state.data.compounds].sort((a,b) => a.observation.value_M - b.observation.value_M).map(c => `<article class="library-card"><a href="${c.source_url}" target="_blank" rel="noreferrer">${c.id} ↗</a><div id="library-${c.id}" class="library-molecule" aria-label="Generated shape of ${c.id}"></div><footer><strong>${number(c.observation.value)} nM</strong><span>IC₅₀</span></footer><small>${number(c.molecular_weight)} Da · ${c.unassigned_stereocentres ? 'unspecified stereochemistry' : 'no unspecified stereocentres'}</small></article>`).join('')}</div>`;
}
const proteinChain = () => state.data.reference_structure.chain;
const ligandSelection = () => {const r=state.data.reference_structure;return {chain:r.ligand_chain||r.chain,resn:r.ligand,resi:r.ligand_residue};};
function atomName(atom) { return `${atom.resn} ${atom.chain}:${atom.resi}${atom.icode || ''} · ${atom.atom}`; }
function setRotation(enabled) {
  if (!state.viewer) return;
  state.rotating = enabled;
  state.viewer.spin(enabled ? 'y' : false, 0.25);
  $('rotate').textContent = enabled ? 'Pause rotation' : 'Rotate model';
  $('rotate').setAttribute('aria-pressed', enabled);
}
function atomClick(atom) {
  setRotation(false);
  const v = state.viewer;
  if (!state.measure) { $('atom-info').textContent = atomName(atom); return; }
  if (state.picked.length >= 2) { state.picked = []; v.removeAllLabels(); v.removeAllShapes(); }
  state.picked.push(atom);
  v.addLabel(atomName(atom), {position: atom, fontSize: 10, backgroundColor: '#254d43', backgroundOpacity: 0.85});
  if (state.picked.length === 2) {
    const [a,b] = state.picked;
    const distance = Math.hypot(a.x-b.x, a.y-b.y, a.z-b.z);
    v.addLine({start:a, end:b, color:'#f2c375', dashed:true, linewidth:2});
    const description = `${atomName(a)} ↔ ${atomName(b)}: ${distance.toFixed(2)} Å`;
    $('atom-info').textContent = description;
    v.addLabel(`${distance.toFixed(2)} Å`, {position:{x:(a.x+b.x)/2,y:(a.y+b.y)/2,z:(a.z+b.z)/2}, fontSize:12, backgroundColor:'#254d43'});
  } else { $('atom-info').textContent = `${atomName(atom)} selected. Click a second atom.`; }
  v.render();
}
async function styleViewer(rebuildSurfaces=true) {
  const v = state.viewer; if (!v) return;
  const version = rebuildSurfaces ? ++state.surfaceVersion : state.surfaceVersion;
  if(rebuildSurfaces){v.removeAllSurfaces();$('viewer').dataset.surface='off';}
  v.setStyle({}, {});
  v.setStyle({chain:proteinChain(), hetflag:false}, {cartoon:{color:'#b6c4d8', opacity:state.pocket ? 0.42 : 0.95}});
  v.addStyle({chain:proteinChain(), resi:state.pocketResidues, hetflag:false}, {stick:{radius:0.13, colorscheme:'greyCarbon'}});
  v.setStyle(ligandSelection(), {stick:{radius:0.22, colorscheme:'orangeCarbon'}, sphere:{scale:0.24, colorscheme:'orangeCarbon'}});
  v.setStyle({hetflag:true,elem:['Zn','Mg','Mn','Fe','Ca','Cu','Co','Ni'],within:{distance:6,sel:ligandSelection()}},{sphere:{radius:.45,color:'#6c9da8'}});
  if (state.waters) v.setStyle({resn:'HOH', chain:proteinChain(), within:{distance:5,sel:ligandSelection()}}, {sphere:{radius:0.23,color:'#8bbfec'}});
  v.setClickable({}, true, atomClick);
  $('pocket').classList.toggle('active',state.pocket); $('pocket').setAttribute('aria-pressed',state.pocket);
  $('protein').classList.toggle('active',!state.pocket); $('protein').setAttribute('aria-pressed',!state.pocket);
  for (const key of ['surface','waters','measure']) { $(key).classList.toggle('active',state[key]); $(key).setAttribute('aria-pressed',state[key]); }
  v.render();
  if (state.surface && rebuildSurfaces) {
    $('viewer').dataset.surface='loading';
    try {
      const surface = await v.addSurface($3Dmol.SurfaceType.VDW, {opacity:0.35,color:'#b6c4e4'}, {chain:proteinChain(),resi:state.pocketResidues,hetflag:false});
      if (version !== state.surfaceVersion) {v.removeSurface(surface);return;}
      $('viewer').dataset.surface='ready';v.render();
    } catch (_) {
      // Removing a pending surface cancels its renderer promise.
      if(version!==state.surfaceVersion||!state.surface)return;
      $('viewer').dataset.surface='error';toast('Surface rendering failed. Atom and ribbon views are still available.');
    }
  }
}
async function initViewer() {
  try {
    const response = await fetch(state.data.reference_structure.url); if (!response.ok) throw Error('Coordinates unavailable');
    const pdb = await response.text();
    const v = $3Dmol.createViewer($('viewer'), {backgroundColor:'#ffffff', antialias:true});
    state.viewer = v;
    v.addModel(pdb, 'pdb');
    const atoms = v.selectedAtoms({chain:proteinChain(),hetflag:false});
    const ligand = v.selectedAtoms(ligandSelection());
    if (!atoms.length || ligand.length !== (state.data.reference_structure.ligand_heavy_atoms||19)) throw Error('Reference atom identity check failed');
    const nearest = new Map();
    for (const a of atoms) {
      const d = Math.min(...ligand.map(b => Math.hypot(a.x-b.x,a.y-b.y,a.z-b.z)));
      if (d <= 4.5 && (!nearest.has(a.resi) || nearest.get(a.resi).distance > d)) nearest.set(a.resi,{atom:a,distance:d});
    }
    const residues = [...nearest.values()].sort((a,b)=>a.distance-b.distance);
    state.pocketResidues = residues.map(r=>r.atom.resi);
    $('residues').innerHTML = residues.slice(0,8).map(r=>`<button data-resi="${r.atom.resi}" title="Closest atom ${r.distance.toFixed(2)} Å from ${escapeHTML(state.data.reference_structure.ligand)}">${r.atom.resn} ${r.atom.resi}</button>`).join('');
    $('residues').querySelectorAll('button').forEach(b=>b.onclick=()=>{
      setRotation(false); const resi=Number(b.dataset.resi); v.removeAllLabels();
      v.addResLabels({chain:proteinChain(),resi},{fontSize:12,backgroundColor:'#254d43'});
      v.zoomTo({or:[{chain:proteinChain(),resi},ligandSelection()]});v.render();
      $('atom-info').textContent = `${b.textContent} · distances are geometric context, not bond assignments`;
    });
    let hoverLabel=null;
    v.setHoverDuration(100);
    v.setHoverable({or:[{chain:proteinChain()},ligandSelection()]},true,(atom)=>{
      setRotation(false);
      if(hoverLabel)v.removeLabel(hoverLabel);
      const selection={chain:atom.chain,resi:atom.resi,resn:atom.resn};
      v.setStyle(selection,{cartoon:{color:'#a78bda',opacity:0.7},stick:{color:'#7955d8',radius:0.21},sphere:{color:'#b29bed',scale:0.28,opacity:0.8}});
      hoverLabel=v.addLabel(`${atom.resn} ${atom.chain}:${atom.resi}`,{position:atom,fontSize:12,fontColor:'#302545',backgroundColor:'#eee7ff',backgroundOpacity:0.95});
      $('viewer').dataset.hoveredResidue=`${atom.resn} ${atom.resi}`;
      if(!state.measure)$('atom-info').textContent=`${atom.resn} ${atom.chain}:${atom.resi} highlighted · ${atom.atom}`;
      v.render();
    },()=>{
      if(hoverLabel)v.removeLabel(hoverLabel);hoverLabel=null;delete $('viewer').dataset.hoveredResidue;
      styleViewer(false);
      if(!state.measure)$('atom-info').textContent='Drag to rotate · hover to highlight · scroll to zoom';
    });
    await styleViewer();v.zoomTo(ligandSelection());v.zoom(0.7);v.render();
    $('viewer-state').hidden = true;
    new ResizeObserver(()=>{v.resize();v.render();}).observe($('viewer'));
    $('rotate').onclick = () => {if (state.measure) {state.measure=false;styleViewer();} setRotation(!state.rotating);};
    $('viewer').addEventListener('pointerdown', () => setRotation(false));
    $('viewer').addEventListener('wheel', () => setRotation(false), {passive:true});
    document.addEventListener('visibilitychange', () => {if (document.hidden) setRotation(false);});
    setRotation(currentPage==='pocket'&&!matchMedia('(prefers-reduced-motion: reduce)').matches);
    window.whatifViewerReady = true;
  } catch(error) {
    $('viewer-state').textContent = `3D unavailable: ${error.message}. The source PDB remains downloadable.`;
    document.querySelectorAll('.viewer-tools button').forEach(b=>b.disabled=true);
  }
}
async function exportShortlist() {
  const ids = state.pins.length ? state.pins : [state.pair.id];
  const payload = {pair_ids:ids, notes:Object.fromEntries(ids.map(id=>[id,state.notes[id] || '']))};
  try {
    const response = await fetch('/api/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if (!response.ok) throw Error('Export request failed');
    const data = await response.json();
    const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=`whatif-${activeWorkspace}-shortlist.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    toast(state.pins.length ? 'Shortlist exported with sources and notes.' : 'Current comparison exported with sources and notes.');
  } catch(error) {toast(error.message);}
}
async function start() {
  if(targetLanding){
    document.body.classList.add('target-landing');
    $('project-target').textContent='Choose a target';$('project-organism').textContent='Start your workspace';$('project-avatar').textContent='+';
    window.dispatchEvent(new Event('workspace-ready'));return;
  }
  try {
    const response=await fetch('/api/dataset');if(!response.ok)throw Error('Dataset request failed');
    state.data=await response.json();
    if(state.data.mode==='starter'){await startStarter();window.dispatchEvent(new Event('workspace-ready'));return;}
    configureTargetWorkspace();
    const shapes=await fetch(state.data.conformers_url||'/data/conformers.json');if(!shapes.ok)throw Error('Molecular shapes unavailable');state.conformers=await shapes.json();restore();
    $('workspace').hidden=false;
    $('assay-description').textContent=state.data.assay.description;
    $('assay-link').href=state.data.assay.url;
    const publication=state.data.publication;
    $('publication').innerHTML=`${escapeHTML(publication.title)} (${publication.year}). <a target="_blank" rel="noreferrer" href="https://doi.org/${encodeURI(publication.doi)}">Read publication ↗</a>`;
    $('limitations').innerHTML=state.data.provenance.limitations.map(x=>`<li>${escapeHTML(x)}</li>`).join('');
    $('open-evidence').onclick=()=>{openPage('evidence');};
    $('close-evidence').onclick=()=>closePage('evidence');
    $('search').oninput=renderList;
    $('pin').onclick=()=>{const id=state.pair.id;state.pins=state.pins.includes(id)?state.pins.filter(x=>x!==id):[...state.pins,id];persist();updatePin();};
    $('hypothesis').oninput=()=>{state.notes[state.pair.id]=$('hypothesis').value;persist();};
    $('export').onclick=exportShortlist;
    $('open-library').onclick=()=>{openPage('library');for(const c of state.data.compounds)moleculeView('library-'+c.id,state.conformers[c.id]);};
    $('library').addEventListener('close',()=>disposeMoleculeViews('library-'));
    $('mode-3d').onclick=()=>setMoleculeMode('3d');$('mode-2d').onclick=()=>setMoleculeMode('2d');
    $('close-library').onclick=()=>closePage('library');
    $('pocket').onclick=()=>{state.pocket=true;styleViewer();state.viewer.zoomTo(ligandSelection());state.viewer.zoom(0.7);state.viewer.render();};
    $('protein').onclick=()=>{state.pocket=false;styleViewer();state.viewer.zoomTo({chain:proteinChain(),hetflag:false});state.viewer.render();};
    for(const key of ['surface','waters'])$(key).onclick=()=>{state[key]=!state[key];styleViewer();};
    $('measure').onclick=()=>{setRotation(false);state.measure=!state.measure;state.picked=[];state.viewer.removeAllLabels();state.viewer.removeAllShapes();$('atom-info').textContent=state.measure?'Click two visible atoms to measure a distance.':'Drag to rotate · scroll to zoom · click an atom to inspect';styleViewer();};
    $('reset').onclick=()=>{setRotation(false);state.pocket=true;state.surface=false;state.waters=false;state.measure=false;state.picked=[];state.viewer.removeAllLabels();state.viewer.removeAllShapes();styleViewer();state.viewer.zoomTo(ligandSelection());state.viewer.zoom(0.7);state.viewer.render();$('atom-info').textContent='Drag to rotate · scroll to zoom · click an atom to inspect';};
    selectPair(activeWorkspace==='brd4'?'pair-2':state.data.pairs[0].id);renderLibrary();await initViewer();window.dispatchEvent(new Event('workspace-ready'));
  }catch(error){$('load-error').textContent=`Unable to open this workspace: ${error.message}. Start the local server with python -m molecular_lab.`;$('load-error').hidden=false;document.body.classList.remove('is-booting');}
}
document.addEventListener('DOMContentLoaded',start);

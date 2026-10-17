'use strict';
const moleculeViewers = new Map();
const deferredMoleculeViews = new Map();
function disposeMoleculeViews(prefix) {
  for(const id of deferredMoleculeViews.keys())if(id.startsWith(prefix))deferredMoleculeViews.delete(id);
  for (const [id,item] of moleculeViewers) {
    if(!id.startsWith(prefix))continue;
    item.viewer.spin(false);item.observer.disconnect();item.viewer.clear();
    const canvas=item.element.querySelector('canvas');
    if(canvas){const gl=canvas.getContext('webgl')||canvas.getContext('experimental-webgl');gl?.getExtension('WEBGL_lose_context')?.loseContext();}
    moleculeViewers.delete(id);delete item.element.dataset.ready;
  }
}
function moleculeView(id, shape, changed=[]) {
  const element=document.getElementById(id);if(!element)return;
  if(!shape || shape.status!=='generated'){element.textContent=shape?.reason||'3D shape unavailable. Use the 2D drawing.';return;}
  if(element.closest('.workspace-page')?.hidden){deferredMoleculeViews.set(id,{shape,changed});return;}
  deferredMoleculeViews.delete(id);
  try {
    const viewer=$3Dmol.createViewer(element,{backgroundColor:'#ffffff',antialias:true});
    viewer.addModel(shape.molblock,'sdf');
    const base=()=>{viewer.setStyle({}, {stick:{radius:0.14,colorscheme:'Jmol'},sphere:{scale:0.24,colorscheme:'Jmol'}});if(changed.length)viewer.setStyle({index:changed},{stick:{radius:0.14,colorscheme:'Jmol'},sphere:{scale:0.34,color:'#9d83e9'}});};
    let hoverLabel=null;
    viewer.setHoverDuration(90);
    viewer.setHoverable({},true,(atom)=>{
      base();viewer.setStyle({index:atom.index},{stick:{radius:0.14,colorscheme:'Jmol'},sphere:{scale:0.43,color:'#7256db'}});
      if(hoverLabel)viewer.removeLabel(hoverLabel);
      hoverLabel=viewer.addLabel(`${atom.elem} · atom ${atom.index+1}`,{position:atom,fontSize:11,fontColor:'#322746',backgroundColor:'#f0ebff',backgroundOpacity:0.95});
      element.dataset.hoveredAtom=String(atom.index);viewer.render();
    },()=>{base();if(hoverLabel)viewer.removeLabel(hoverLabel);hoverLabel=null;delete element.dataset.hoveredAtom;viewer.render();});
    base();viewer.zoomTo();viewer.zoom(0.88);viewer.render();
    const observer=new ResizeObserver(()=>{viewer.resize();viewer.render();});observer.observe(element);
    moleculeViewers.set(id,{viewer,observer,element,shape,changed});element.dataset.ready='true';
    element.setAttribute('title','Generated free-molecule shape. Drag to rotate, scroll to zoom, hover to inspect atoms.');
  }catch(error){element.textContent='3D unavailable. The 2D structure remains available.';}
}
function evidenceMarkup(data) {
  if(!data)return '<p>Evidence is not available for this comparison.</p>';
  const rows=data.evidence;
  return `<div class="edit-evidence-heading"><span class="mini-tag">${rows.length?'MEASURED PRECEDENT':'EVIDENCE GAP'}</span><h3>${escapeHTML(data.edit?.label||'A new question to test')}</h3></div><p class="evidence-summary">${escapeHTML(data.summary)}</p>${rows.length?`<div class="edit-examples">${rows.map(row=>{const ratio=row.fold_lower_ic50_right;return `<div class="edit-example"><div><a href="${row.left_source}" target="_blank" rel="noreferrer">${row.left_id}</a><span> → </span><a href="${row.right_source}" target="_blank" rel="noreferrer">${row.right_id}</a><small>${number(row.left_observation.value)} → ${number(row.right_observation.value)} nM · same assay</small></div><strong class="${ratio<1?'worse':'better'}">${number(Math.max(ratio,1/ratio))}× ${ratio>=1?'lower':'higher'} IC₅₀</strong></div>`;}).join('')}</div>`:''}<div class="next-question"><span>AN EXPERIMENT TO CONSIDER</span><p>${escapeHTML(data.next_experiment)}</p></div><details class="evidence-scope"><summary>How strong is this evidence?</summary><p>${escapeHTML(data.scope)}</p><p>${escapeHTML(data.method)}</p><p>${escapeHTML(data.limitation||'No measurement found is not the same as a negative result. The current rules recognise ketone/alcohol and ethyl-ester/acid conversions only.')}</p></details>`;
}

function suspendMoleculePage(page){
  for(const [id,item] of [...moleculeViewers]){
    if(!item.shape||!page.contains(item.element))continue;
    const saved={shape:item.shape,changed:item.changed,view:item.viewer.getView()};
    disposeMoleculeViews(id);item.element.replaceChildren();deferredMoleculeViews.set(id,saved);
  }
}
function resumeMoleculePage(page){
  for(const [id,item] of [...deferredMoleculeViews]){
    const element=document.getElementById(id);if(!element||!page.contains(element))continue;
    moleculeView(id,item.shape,item.changed);const model=moleculeViewers.get(id);if(model&&item.view){model.viewer.setView(item.view);model.viewer.render();}
  }
}

'use strict';
// Locally drawn clay icons: no font-emoji or remote asset dependency.
let clayIconSerial=0;
function labGearMarkup(){
  const id='gear-'+(++clayIconSerial);
  const cog=(cx,cy,r,small=false)=>{
    const points=Array.from({length:48},(_,i)=>{const angle=i*Math.PI/24, radius=r*([0,3].includes(i%4)?.79:1);return `${cx+Math.cos(angle)*radius},${cy+Math.sin(angle)*radius}`;}).join(' ');
    return `<g class="clay-cog ${small?'cog-small':'cog-main'}" style="transform-origin:${cx}px ${cy}px"><polygon points="${points}" fill="${small?'#76a697':'#8a70aa'}" stroke="${small?'#76a697':'#8a70aa'}" stroke-width="3" stroke-linejoin="round" transform="translate(0 4)"/><polygon points="${points}" fill="url(#${id}-${small?'mint':'purple'})" stroke="${small?'#b8e0d1':'#d2bce8'}" stroke-width="2" stroke-linejoin="round"/><circle cx="${cx}" cy="${cy}" r="${r*.32}" fill="#837395"/><circle cx="${cx}" cy="${cy+2}" r="${r*.26}" fill="#f8f4fc"/></g>`;
  };
  return `<span class="clay-engine" aria-hidden="true"><svg viewBox="0 0 90 76"><defs><linearGradient id="${id}-purple" x2=".7" y2="1"><stop stop-color="#f0e3ff"/><stop offset=".45" stop-color="#ccb1e7"/><stop offset="1" stop-color="#9d7dbc"/></linearGradient><linearGradient id="${id}-mint" x2=".7" y2="1"><stop stop-color="#e8fff4"/><stop offset=".5" stop-color="#b3decc"/><stop offset="1" stop-color="#7eae9c"/></linearGradient></defs><ellipse cx="44" cy="69" rx="33" ry="5" fill="#89769d" opacity=".12"/>${cog(32,32,24)}${cog(67,51,17,true)}</svg></span>`;
}
function clayHelixMarkup(){
  return `<span class="clay-helix" aria-hidden="true"><span class="helix-turn">${Array.from({length:8},(_,i)=>`<i class="helix-rung" style="--rung:${i}"><b></b><b></b></i>`).join('')}</span></span>`;
}
function claySparkleMarkup(){
  const id='sparkle-'+(++clayIconSerial);
  const star='M32 6 Q36 25 53 29 Q36 33 32 54 Q28 33 11 29 Q28 25 32 6Z';
  return `<span class="clay-sparkle" aria-hidden="true"><svg viewBox="0 0 68 68"><defs><linearGradient id="${id}" x2=".8" y2="1"><stop stop-color="#fff9e3"/><stop offset=".4" stop-color="#f6d49c"/><stop offset="1" stop-color="#d89b6c"/></linearGradient></defs><ellipse cx="35" cy="60" rx="18" ry="4" fill="#b78c73" opacity=".12"/><path d="${star}" transform="translate(3 4)" fill="#c58c64" stroke="#c58c64" stroke-width="2" stroke-linejoin="round"/><path d="${star}" fill="url(#${id})" stroke="#ffe9c6" stroke-width="2" stroke-linejoin="round"/><path d="M32 9 32 29 14 29Q28 25 32 9Z" fill="#fff8df" opacity=".8"/><path d="M32 29 50 29Q36 33 32 51Z" fill="#bd815c" opacity=".2"/><path d="M55 5Q57 12 63 14Q57 16 55 23Q53 16 47 14Q53 12 55 5Z" fill="url(#${id})" stroke="#ffebcc" stroke-linejoin="round"/></svg></span>`;
}
// One WebGL renderer feeds lightweight 2D canvases for the visible cards only.
// We rotate atomic coordinates in 3D, not a flat picture of the molecule.
const galleryMotionPreference=matchMedia('(prefers-reduced-motion: reduce)');
let galleryMotionEnabled=!galleryMotionPreference.matches;
let galleryMotion=null;
function updateGalleryMotionButton(){
  const button=document.getElementById('gallery-motion');if(!button)return;
  button.textContent=galleryMotionEnabled?'Ⅱ Pause rotation':'↻ Rotate molecules';
  button.setAttribute('aria-pressed',String(galleryMotionEnabled));
}
function stopGalleryMotion(){
  const run=galleryMotion;if(!run)return;galleryMotion=null;
  cancelAnimationFrame(run.frame);run.observer.disconnect();run.viewer.clear();
  const canvas=run.host.querySelector('canvas');const gl=canvas&&(canvas.getContext('webgl')||canvas.getContext('experimental-webgl'));
  gl?.getExtension('WEBGL_lose_context')?.loseContext();run.host.remove();
}
function startGalleryMotion(){
  stopGalleryMotion();updateGalleryMotionButton();
  if(!galleryMotionEnabled||document.hidden||currentPage!=='home')return;
  const cards=[...document.querySelectorAll('[data-open-molecule]')].filter(el=>state.conformers[el.dataset.openMolecule]?.status==='generated');
  if(!cards.length)return;
  const host=document.createElement('div');host.className='thumbnail-renderer';host.setAttribute('aria-hidden','true');document.body.append(host);
  let viewer;
  try{viewer=$3Dmol.createViewer(host,{backgroundColor:'#ffffff',antialias:true,disableFog:true});}
  catch(_){host.remove();return;}
  const visible=new Set(),models=new Map();
  const observer=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting)visible.add(entry.target);else visible.delete(entry.target);}}, {threshold:.05});
  const run={host,viewer,observer,frame:0};galleryMotion=run;
  cards.forEach(card=>observer.observe(card));let previous=null,last=0;
  const tick=time=>{
    if(galleryMotion!==run)return;
    if(document.hidden||currentPage!=='home'){stopGalleryMotion();return;}
    // Cap redraws, skip off-screen/hovered cards, and retain each card's angle.
    if(time-last>=80){
      const elapsed=last?Math.min(time-last,200):0;last=time;
      try{
        for(const card of visible){
          if(card.matches(':hover,:focus-within'))continue;
          const id=card.dataset.openMolecule;let item=models.get(id);
          if(!item){
            previous?.hide();
            const model=viewer.addModel(state.conformers[id].molblock,'sdf');
            model.setStyle({},{stick:{radius:.14,colorscheme:'Jmol'},sphere:{scale:.24,colorscheme:'Jmol'}});
            viewer.setView([0,0,0,0,0,0,0,1]);
            viewer.zoomTo({model:model.getID()});viewer.zoom(1.2);viewer.setSlab(-50,50);
            let canvas=card.querySelector('.tile-motion');
            if(!canvas){canvas=document.createElement('canvas');canvas.className='tile-motion';canvas.width=360;canvas.height=190;canvas.setAttribute('aria-hidden','true');card.querySelector('.tile-art').append(canvas);}
            item={model,view:viewer.getView(),angle:0,canvas,context:canvas.getContext('2d')};models.set(id,item);
          }
          previous?.hide();item.model.show();previous=item.model;
          item.angle=(item.angle+elapsed*.016)%360;
          viewer.setView(item.view);viewer.rotate(item.angle,'y');viewer.render();
          item.context.drawImage(host.querySelector('canvas'),0,0,360,190);
          item.canvas.dataset.angle=item.angle.toFixed(2);
        }
      }catch(_){stopGalleryMotion();return;}
    }
    run.frame=requestAnimationFrame(tick);
  };
  run.frame=requestAnimationFrame(tick);
}
galleryMotionPreference.addEventListener('change',event=>{galleryMotionEnabled=!event.matches;startGalleryMotion();});
document.addEventListener('visibilitychange',()=>{document.body.classList.toggle('motion-suspended',document.hidden);if(document.hidden)stopGalleryMotion();else startGalleryMotion();});
window.addEventListener('studio-page',()=>{if(currentPage!=='home')stopGalleryMotion();});
document.addEventListener('DOMContentLoaded',()=>{
  document.getElementById('gallery-motion').onclick=()=>{galleryMotionEnabled=!galleryMotionEnabled;startGalleryMotion();};
  document.querySelectorAll('.soft-emoji,.floating-emoji').forEach(el=>{
    if(el.textContent==='🧬')el.innerHTML=clayHelixMarkup();
    else if(el.textContent==='🔬')el.innerHTML=labGearMarkup();
    else if(el.textContent==='✨')el.innerHTML=claySparkleMarkup();
  });
  document.querySelector('#run-dock>.loading-spinner').outerHTML=labGearMarkup();
});

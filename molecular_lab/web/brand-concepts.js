'use strict';
const concepts=[
  {id:'forma',name:'Forma',theme:'Sculptural · minimal',description:'A folded F, like a soft ribbon taking shape. Clean, quiet and closely tied to molecular design.',tagline:'Give your next idea a shape.',accent:'#785997',wash:'#f3eef8',ink:'#43364f',font:'sans'},
  {id:'orbia',name:'Orbia',theme:'Precise · exploratory',description:'Two crossing orbits with a small centre. A cooler, more technical identity for exploring interactions.',tagline:'Explore how things connect.',accent:'#456c91',wash:'#edf3f8',ink:'#2c465f',font:'sans'},
  {id:'avela',name:'Avela',theme:'Organic · warm',description:'Two folded leaves meeting at one point. Soft and living, with an editorial wordmark.',tagline:'A little curiosity. Room to grow.',accent:'#58816c',wash:'#eef4ef',ink:'#385447',font:'serif'},
  {id:'foldlet',name:'Foldlet',theme:'Playful · scientific',description:'A small faceted fold. The most direct link to protein structure, with a friendly workshop feel.',tagline:'Big questions. Small experiments.',accent:'#a36c74',wash:'#faf0ed',ink:'#68464e',font:'rounded'},
  {id:'morrow',name:'Morrow',theme:'Optimistic · spacious',description:'A sun inside an open doorway. Less literal chemistry, more about the discovery that comes next.',tagline:'Make room for what comes next.',accent:'#9a744d',wash:'#faf3e7',ink:'#614b36',font:'serif'},
  {id:'moduli',name:'Moduli',theme:'Inventive · structured',description:'A modular, faceted block with a small inset. A mark for building, adjusting and comparing designs.',tagline:'Build a better question.',accent:'#656b99',wash:'#eff0f8',ink:'#414568',font:'rounded'}
];
const grid=document.getElementById('concepts');
grid.innerHTML=concepts.map((c,i)=>`<button class="concept-card type-${c.font}" data-concept="${c.id}" aria-pressed="${i===0}" style="--accent:${c.accent};--wash:${c.wash};--ink:${c.ink}"><span class="card-top"><span>0${i+1}</span><span class="selection">Preview ↗</span></span><span class="identity"><img src="/brand-concepts/${c.id}.svg" alt="${c.name} logo"><strong>${c.name}</strong></span><span class="theme">${c.theme}</span><span class="description">${c.description}</span><span class="small-size"><span>AT APP SIZE</span><img src="/brand-concepts/${c.id}.svg" width="28" height="28" alt=""><img src="/brand-concepts/${c.id}.svg" width="16" height="16" alt=""></span></button>`).join('');
function selectConcept(c,index){
  grid.querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.concept===c.id)));
  const preview=document.getElementById('brand-preview');preview.className='brand-preview type-'+c.font;
  for(const key of ['accent','wash','ink'])preview.style.setProperty('--'+key,c[key]);
  document.getElementById('preview-heading').textContent=`0${index+1} · ${c.name}`;
  document.getElementById('preview-name').textContent=c.name;
  document.getElementById('preview-tagline').textContent=c.tagline;
  document.getElementById('preview-logo').src=`/brand-concepts/${c.id}.svg`;
  document.getElementById('hero-logo').src=`/brand-concepts/${c.id}.svg`;
  document.getElementById('hero-logo').alt=c.name+' logo preview';
  const download=document.getElementById('download-logo');download.href=`/brand-concepts/${c.id}.svg`;download.download=c.id+'-logo-concept.svg';
  document.getElementById('selection-note').textContent=`Previewing 0${index+1} · ${c.name}. This does not change your app’s branding.`;
}
grid.querySelectorAll('button').forEach((button,index)=>button.onclick=()=>selectConcept(concepts[index],index));
selectConcept(concepts[0],0);

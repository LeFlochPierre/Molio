'use strict';
const pageRoutes={welcome:{id:'welcome-page',label:'Molio'},home:{id:'home-page',label:'Workspace',launch:'open-home'},molecule:{id:'molecule-page',label:'Molecule'},starter:{id:'starter-page',label:'Protein & inputs',launch:'open-explore'},targets:{id:'targets-page',label:'Project library',launch:'open-targets'},explore:{id:'workspace',label:'Explore',launch:'open-explore'},design:{id:'designs-dialog',label:'Design',launch:'open-designs'},runs:{id:'experiments-dialog',label:'Runs',launch:'open-experiments'},saved:{id:'proposals-dialog',label:'Saved ideas',launch:'open-proposals'},library:{id:'library',label:'Library',launch:'open-library'},activity:{id:'activity-map',label:'Activity map',launch:'open-map'},pocket:{id:'pocket-page',label:'Protein pocket',launch:'open-pocket-page'},editor:{id:'variant-dialog',label:'Molecule editor'},notes:{id:'evidence',label:'Notes & sources',launch:'open-evidence'}};
const targetLanding=!new URLSearchParams(location.search).has('workspace')&&['','#/welcome','#/targets'].includes(location.hash);
const openedPages=new Set(targetLanding?[]:['home']);let currentPage=targetLanding?'welcome':'home',pageVisits=targetLanding?[]:['home'],navigationReady=false,suppressRouteHistory=false;
const pageScroll=new Map();
const icons={grid:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',spark:'m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z M20 2v4 M18 4h4',play:'m8 5 11 7-11 7Z',bookmark:'M6 3h12v18l-6-4-6 4Z',layers:'m12 3 10 5-10 5L2 8Z M2 12l10 5 10-5 M2 16l10 5 10-5',chart:'M4 3v17h17 M8 15l4-5 4 2 5-7',cube:'m12 2 9 5v10l-9 5-9-5V7Z M3 7l9 5 9-5 M12 12v10',download:'M12 3v12 m-5-5 5 5 5-5 M4 16v5h16v-5'};
function icon(name){return `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="${icons[name]||icons.grid}"/></svg>`;}
function routeForId(id){return Object.keys(pageRoutes).find(route=>pageRoutes[route].id===id);}
function isPageOpen(id){return openedPages.has(routeForId(id));}
function resizeWorkspaceViews(){requestAnimationFrame(()=>{for(const {viewer,element} of moleculeViewers.values()){if(element.getBoundingClientRect().width){viewer.resize();viewer.render();}}if(state.viewer&&currentPage==='pocket'){state.viewer.resize();if(!$('pocket-page').dataset.fitted){state.viewer.zoomTo(ligandSelection());state.viewer.zoom(.7);$('pocket-page').dataset.fitted='true';setRotation(!matchMedia('(prefers-reduced-motion: reduce)').matches);}state.viewer.render();}});}
function renderPageTabs(){
  $('workspace-tabs').innerHTML=[...openedPages].map(route=>`<div class="workspace-tab ${currentPage===route?'selected':''}"><button data-activate-page="${route}" ${currentPage===route?'aria-current="page"':''}>${pageRoutes[route].label}</button>${['home','welcome','explore','starter'].includes(route)||targetLanding?'':`<button class="tab-close" data-close-page="${route}" aria-label="Close ${pageRoutes[route].label}">×</button>`}</div>`).join('');
  $('workspace-tabs').querySelectorAll('[data-activate-page]').forEach(button=>button.onclick=()=>activatePage(button.dataset.activatePage));
  $('workspace-tabs').querySelectorAll('[data-close-page]').forEach(button=>button.onclick=()=>closePage(pageRoutes[button.dataset.closePage].id));
}
function activatePage(route,push=true){
  if(targetLanding&&!['welcome','targets'].includes(route))route='welcome';
  else if(!targetLanding&&route==='welcome')route='home';
  else if(state.data?.mode==='starter'&&['explore','pocket','activity','library','notes'].includes(route))route='starter';
  if(!pageRoutes[route]||(route==='starter'&&state.data?.mode!=='starter'))route='home';
  pageScroll.set(currentPage,window.scrollY);
  if(currentPage!==route)suspendMoleculePage(document.getElementById(pageRoutes[currentPage].id));
  if(document.body.classList.contains('protein-expanded'))expandProtein(false);
  if(currentPage!==route&&state.viewer)setRotation(false);
  if(currentPage==='starter'&&route!=='starter'&&typeof starterViewer!=='undefined'&&starterViewer){starterViewer.spin(false);starterSpinning=false;$('starter-spin').textContent='Rotate';}
  document.body.classList.remove('reference-menu-open');document.getElementById('toggle-reference').setAttribute('aria-expanded','false');
  currentPage=route;openedPages.add(route);pageVisits=pageVisits.filter(r=>r!==route);pageVisits.push(route);
  for(const [key,page] of Object.entries(pageRoutes))document.getElementById(page.id).hidden=key!==route;
  resumeMoleculePage(document.getElementById(pageRoutes[route].id));
  document.body.dataset.page=route;
  document.querySelectorAll('[data-route]').forEach(button=>{const selected=button.dataset.route===route;button.classList.toggle('selected',selected);if(selected)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');});
  $('current-page-label').textContent=pageRoutes[route].label;renderPageTabs();
  const nextHash='#/'+route+(route==='molecule'&&typeof currentMoleculeId!=='undefined'&&currentMoleculeId?'/'+encodeURIComponent(currentMoleculeId):'');
  if(push&&!suppressRouteHistory&&location.hash!==nextHash)history.pushState({page:route},'', nextHash);
  window.dispatchEvent(new CustomEvent('studio-page',{detail:{route}}));
  window.scrollTo({top:pageScroll.get(route)||0,behavior:'instant'});resizeWorkspaceViews();
  const heading=document.getElementById(pageRoutes[route].id).querySelector('h1,h2');if(heading){heading.tabIndex=-1;heading.focus({preventScroll:true});}
}
function openPage(id){const route=routeForId(id);if(route)activatePage(route);}
function closePage(id){
  const route=routeForId(id);if(targetLanding||!route||['home','welcome','explore','starter'].includes(route)||!openedPages.has(route))return;
  openedPages.delete(route);pageVisits=pageVisits.filter(r=>r!==route);pageScroll.delete(route);
  const element=document.getElementById(id);element.hidden=true;element.dispatchEvent(new Event('close'));
  if(currentPage===route)activatePage(pageVisits.at(-1)||'home');else renderPageTabs();
}
function goPage(route,push=true){
  if(!navigationReady)return;
  if(targetLanding&&!['welcome','targets'].includes(route))route='welcome';
  else if(!targetLanding&&route==='welcome')route='home';
  else if(state.data?.mode==='starter'&&['explore','pocket','activity','library','notes'].includes(route))route='starter';
  suppressRouteHistory=!push;
  try{if(route==='molecule'){let id='';try{id=decodeURIComponent(location.hash.split('/')[2]||'');}catch(_){activatePage('home',push);return;}openMolecule(id||currentMoleculeId,push);return;}
    if(openedPages.has(route)||['home','welcome','explore','pocket','starter'].includes(route)){activatePage(route,push);return;}
    const launch=pageRoutes[route]?.launch;
    if(launch)document.getElementById(launch).click();else if(route==='editor')openVariant(variantParent||state.pair?.left||state.data.compounds[0]?.id);else activatePage('home',push);
  }finally{suppressRouteHistory=false;}
}
function showRunView(view){
  if(!['setup','results','pose'].includes(view))return;
  if(view==='pose'&&$('run-pose-tab').disabled)return;
  $('run-setup-panel').hidden=view!=='setup';$('experiment-history').hidden=view!=='results';$('prediction-inspector').hidden=view!=='pose';
  document.querySelectorAll('[data-run-view]').forEach(b=>{b.classList.toggle('active',b.dataset.runView===view);b.setAttribute('aria-pressed',b.dataset.runView===view);});
  document.getElementById('experiments-dialog').dataset.view=view;resizeWorkspaceViews();
}
document.addEventListener('DOMContentLoaded',()=>{
  const stage=document.getElementById('page-stage');
  document.querySelector('.skip-link').onclick=event=>{event.preventDefault();stage.focus({preventScroll:true});};
  // Notes were previously nested in the comparison layout. All pages are now peers.
  for(const page of Object.values(pageRoutes)){const element=document.getElementById(page.id);if(element.parentElement!==stage)stage.append(element);}
  document.querySelectorAll('.app-navigation button').forEach(button=>button.setAttribute('aria-label',button.textContent.trim()));
  $('toggle-reference').onclick=()=>{const open=document.body.classList.toggle('reference-menu-open');$('toggle-reference').setAttribute('aria-expanded',open);};
  document.querySelectorAll('[data-icon]').forEach(el=>el.insertAdjacentHTML('afterbegin',icon(el.dataset.icon)));
  document.querySelectorAll('[data-go]').forEach(el=>el.onclick=()=>goPage(el.dataset.go));
  $('open-home').onclick=()=>goPage('home');
  $('open-explore').onclick=()=>goPage('explore');$('open-pocket-page').onclick=()=>goPage('pocket');
  // Returning to an open page preserves drafts, selection and camera state.
  document.querySelectorAll('[data-route]').forEach(button=>button.addEventListener('click',event=>{if(openedPages.has(button.dataset.route)){event.preventDefault();event.stopImmediatePropagation();activatePage(button.dataset.route);}},true));
  document.querySelectorAll('[data-run-view]').forEach(button=>button.onclick=()=>showRunView(button.dataset.runView));
  renderPageTabs();
});
window.addEventListener('workspace-ready',()=>{navigationReady=true;const route=location.hash.replace('#/','').split('/')[0];goPage(pageRoutes[route]?route:(targetLanding?'welcome':'home'),false);});
window.addEventListener('popstate',()=>{const route=location.hash.replace('#/','').split('/')[0];if(route!==currentPage||route==='molecule')goPage(pageRoutes[route]?route:(targetLanding?'welcome':'home'),false);});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!document.body.classList.contains('protein-expanded')&&currentPage!=='explore'){event.preventDefault();closePage(pageRoutes[currentPage].id);}});

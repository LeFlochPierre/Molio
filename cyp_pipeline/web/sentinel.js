(() => {
  'use strict';
  const $=id=>document.getElementById(id),data=JSON.parse($('sentinelData').textContent);
  const candidates=Object.values(data.candidates),stepNodes=[...$('steps').children];
  let runtime=null,busy=false,activeJob=null,currentResult=null,screening=data.screening,plannerOnline=false;
  let batchInput=null,batchAudit=null;
  const pairCache=new Map();let previewTicket=0,displayedJob=null,jobPreviewPending=null;
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fold=value=>Number.isFinite(value)?`${value.toFixed(value>=100?0:1)}×`:'Unavailable';
  const energy=value=>Number.isFinite(value)?`${value.toFixed(4)} eV`:'Unresolved';
  const preset=()=>({'R-fadrozole':'r_fadrozole','S-fadrozole':'s_fadrozole'}[$('candidate').value]);
  const selected=()=>data.candidates[$('candidate').value];
  function setStep(index,state,description){
    const node=stepNodes[index];node.className=state;
    node.querySelector('.step-icon').textContent=state==='done'?'✓':state==='failed'||state==='warning'?'!':String(index+1);
    if(description)node.querySelector('small').textContent=description;
  }
  function resetSteps(){
    const planning=$('mode').value==='plan',batch=$('mode').value==='batch',calibrated=$('mode').value==='calibrated';
    const titles=calibrated?['Load UMA outputs','Build exchange','Convert to fold','Cross-check']:planning?['Choose','Fetch structures','Build inputs','Next step']:batch?['Upload','Check pockets','Run UMA','Results']:['Check inputs','Inspect structure','Evaluate evidence','Read the result'];
    const notes=calibrated?['Supplied relaxed energies','Matched ligand / water','Empirical calibration','Assays & pose sensitivity']:planning?['Molecule & target','Reference library','Prediction files','Run / review']:batch?['Prepared JSON','Atoms & state','Energy & forces','Not binding affinity']:['Candidate & target','Geometry & identity','Model or UMA run','Signal & next step'];
    notes.forEach((s,i)=>{setStep(i,'',s);stepNodes[i].querySelector('b').textContent=titles[i];});
  }
  function setBusy(value){busy=value;document.body.classList.toggle('is-running',value);document.dispatchEvent(new CustomEvent('isoform:run-state',{detail:{busy:value,text:value?'Processing your inputs':'Ready'}}));['candidate','mode','sequence','candidateName','planTarget','planPanel','planSequence','planSmiles','run','batchFile','batchExample','provisionalConfirm','checkPlan','calibratedCandidate','posePolicy'].forEach(id=>$(id).disabled=value);document.querySelectorAll('[data-example]').forEach(b=>b.disabled=value);}
  function sequence(){return $('sequence').value.split('\n').filter(line=>!line.trim().startsWith('>')).join('').replace(/\s/g,'').toUpperCase();}
  function validateSequence(){const s=sequence(),valid=s.length>=50&&/^[ACDEFGHIKLMNPQRSTVWY]+$/.test(s),exact=s===data.target.sequence;
    $('sequenceCount').textContent=s.length+' aa';$('sequenceStatus').textContent=exact?'Matches the prepared CYP11B2 target.':valid?'Different sequence: a prepared structure is needed.':'Enter at least 50 standard amino-acid letters.';
    return {valid,exact};
  }
  function updateSetup(){
    if(busy)return;
    previewTicket++;displayedJob=null;
    const isNew=$('candidate').value==='new',planning=$('mode').value==='plan',batch=$('mode').value==='batch',calibrated=$('mode').value==='calibrated';
    $('calibratedSettings').hidden=!calibrated;
    document.querySelector('.viewer-header h2').textContent=calibrated?'The reference pockets.':'One molecule. Two pockets.';
    $('batchSettings').hidden=!batch;$('candidateSettings').hidden=batch||calibrated;$('savedExamples').hidden=batch||calibrated;
    $('candidateName').hidden=!isNew;$('nameLabel').hidden=!isNew;
    $('planSettings').hidden=!planning;$('pairedTarget').hidden=planning||batch;
    $('referenceSettings').hidden=planning;$('planViewerNote').hidden=!planning;
    $('customTargetSettings').hidden=$('planTarget').value!=='custom';$('smilesSettings').hidden=!isNew;
    $('sequenceSettings').hidden=calibrated||batch||(planning&&!isNew);
    if(isNew)$('sequence').closest('details').open=true;
    $('runLabel').textContent=activeJob?'Resume status':calibrated?'Calculate fold preference':batch?(batchAudit?`Run UMA · ${batchAudit.systems.length} pockets`:'Check pockets'):planning?'Build inputs':$('mode').value==='live'?'Run UMA':'View evidence';
    $('modeNote').textContent=calibrated?'Energy arithmetic. A traceable fitted ratio.':batch?'Your coordinates. Real UMA energies.':planning?'Collect references and prediction inputs.':$('mode').value==='live'?'Live UMA · provisional prepared pockets.':'Saved assays, not a new calculation.';
    document.dispatchEvent(new CustomEvent('sentinel:prepared',{detail:batch&&batchAudit?batchInput:null}));
    document.dispatchEvent(new CustomEvent('isoform:target',{detail:{target:planning?$('planTarget').value:'CYP11B2',targets:planning?[...new Set([$('planTarget').value,...(screening.catalog.panels[$('planPanel').value]?.targets||[])])]:['CYP11B2','CYP11B1']}}));
    $('formFeedback').textContent='';$('result').hidden=true;$('activity').hidden=true;$('runStatus').textContent='Ready when you are';currentResult=null;resetSteps();validateSequence();
    if($('mode').value==='live'&&preset()&&!activeJob)previewPair().catch(()=>{});
  }
  async function api(path,options={},timeout=15000){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeout);
    try{const response=await fetch(path,{...options,signal:controller.signal,cache:'no-store'});const body=await response.json();if(!response.ok)throw Error(body.error||'The server could not complete this request.');return body;}finally{clearTimeout(timer);}
  }
  async function pairInputs(key){
    if(!pairCache.has(key))pairCache.set(key,api('/api/prepared-example?preset='+encodeURIComponent(key)).catch(error=>{pairCache.delete(key);throw error;}));
    return pairCache.get(key);
  }
  async function previewPair(){
    const key=preset(),ticket=++previewTicket;
    if(!key||activeJob||location.protocol==='file:')return;
    const payload=await pairInputs(key);
    if(ticket===previewTicket&&!activeJob&&$('mode').value==='live'&&preset()===key)document.dispatchEvent(new CustomEvent('sentinel:prepared',{detail:{...payload,origin:'prepared-pair'}}));
    return payload;
  }
  async function previewJob(job){
    if(displayedJob===job.id)return;
    if(jobPreviewPending?.id===job.id&&jobPreviewPending.ticket===previewTicket)return jobPreviewPending.promise;
    const ticket=++previewTicket;
    const promise=api('/api/jobs/'+encodeURIComponent(job.id)+'/pockets').then(payload=>{
      if(activeJob===job.id&&ticket===previewTicket){displayedJob=job.id;document.dispatchEvent(new CustomEvent('sentinel:prepared',{detail:{...payload,origin:job.kind==='uma_pocket_batch'?'uploaded':'prepared-pair'}}));}
    }).finally(()=>{if(jobPreviewPending?.ticket===ticket)jobPreviewPending=null;});
    jobPreviewPending={id:job.id,ticket,promise};return promise;
  }
  async function connect(){
    if(location.protocol==='file:'){$('connection').lastChild.textContent='Saved evidence mode';return;}
    try{
      runtime=await api('/api/health',{},30000);const pre=runtime.preflight?.result;
      const ready=runtime.execution_enabled&&pre?.status==='ready_to_load';
      $('connection').classList.toggle('ready',ready);
      $('connection').lastChild.textContent=ready?`UMA connected · ${pre.device==='cuda'?'GPU':'CPU'}`:plannerOnline?'CPU planner connected':'Saved evidence mode';
      $('connection').title=ready?'Real calculations are available.':(pre?.issues||['Execution is disabled.']).join(' ');
    }catch(error){runtime=null;$('connection').lastChild.textContent=plannerOnline?'CPU planner connected':'Saved evidence mode';}
  }
  function planChoices(){
    const oldTarget=$('planTarget').value||'CYP11B2',oldPanel=$('planPanel').value||screening.default_panel;
    const fill=(node,rows)=>{node.replaceChildren();rows.forEach(([value,label])=>{const option=document.createElement('option');option.value=value;option.textContent=label;node.append(option);});};
    fill($('planTarget'),[...Object.entries(screening.catalog.targets).map(([id,t])=>[id,t.label]),['custom','New protein sequence']]);
    fill($('planPanel'),Object.entries(screening.catalog.panels).map(([id,p])=>[id,p.label]));
    if([...$('planTarget').options].some(o=>o.value===oldTarget))$('planTarget').value=oldTarget;
    if([...$('planPanel').options].some(o=>o.value===oldPanel))$('planPanel').value=oldPanel;
  }
  async function connectCatalog(){
    if(location.protocol==='file:')return;
    try{screening=await api('/api/screen-catalog');plannerOnline=true;planChoices();if(!runtime?.execution_enabled||runtime.preflight?.result?.status!=='ready_to_load')$('connection').lastChild.textContent='CPU planner connected';if($('mode').value==='plan'&&!busy)updateSetup();}catch{}
  }
  async function refreshStructures(){
    if(location.protocol==='file:')return;
    try{const structures=await api('/api/structures');document.dispatchEvent(new CustomEvent('isoform:library',{detail:structures}));}catch{}
  }
  function screenRequest(){
    const key=Object.entries(screening.candidates).find(([,c])=>c.label===$('candidate').value)?.[0];
    const request={candidate_id:$('candidate').value==='new'?'custom':key,target_id:$('planTarget').value,panel_id:$('planPanel').value};
    if(request.candidate_id==='custom'){request.candidate_name=$('candidateName').value.trim()||'New candidate';request.smiles=$('planSmiles').value.trim();}
    if(request.target_id==='custom')request.target_sequence=$('planSequence').value;
    return request;
  }
  function showInputs(bundle){
    const s=bundle.summary;
    $('result').className='result neutral';
    $('result').innerHTML=`<div class="result-top"><div><div class="section-label">${escape(bundle.candidate.label)} · INPUT BUILDER</div><h2>Inputs built for ${s.proteins} proteins</h2><p>${s.structures} references · ${s.boltz_inputs} Boltz pose inputs · ${s.uma_ready} existing UMA preparations</p></div><span class="result-tag">No predictions yet</span></div><div class="readiness-table"><div class="readiness-row readiness-head"><span>Protein</span><span>3D reference</span><span>Pose input</span><span>UMA pocket</span></div>${bundle.targets.map(row=>`<div class="readiness-row"><button class="text-button view-target" data-view-target="${escape(row.target_id)}" type="button">${escape(row.target_id)} ${row.role==='intended_target'?'↗':''}</button><span class="${row.reference.status==='available'?'ready-text':''}">${row.reference.status==='available'?escape(row.reference.pdb)+' ✓':'Not loaded'}</span><span class="${row.boltz_input?'ready-text':''}">${row.boltz_input?'Built ✓':'Needs review'}</span><span>${row.uma_ready?'Prepared*':'After pose + chemistry'}</span></div>`).join('')}</div><p class="result-next">${s.boltz_inputs?'Next: run pose prediction, then prepare and review the new pockets for UMA.':'Check the sequence or SMILES details below to build prediction inputs.'}</p><p class="result-source">${s.uma_ready?'*Existing UMA inputs are provisional. ':''}The 3D view shows crystal reference ligands—not newly predicted binding of your candidate.</p><div class="result-actions">${bundle.available_jobs.length?'<button class="secondary accent" id="runBuiltPair" type="button">Run prepared pair · UMA ↗</button>':''}<a class="download-plan" id="downloadInputs" href="${escape(bundle.download_url)}" download="isoform-inputs.zip">Download inputs ↓</a></div><details><summary>Prediction command &amp; remaining preparation</summary>${bundle.boltz_command?`<p>Run this separately after reviewing the inputs. Boltz must be installed; it can download weights and uses GPU resources. Single-sequence mode is an exploratory baseline.</p><pre>${escape(bundle.boltz_command)}</pre>`:''}<p>For new UMA pockets: candidate pose → hydrogens/caps → charge and spin → geometry/chemistry review. This builder does not guess these states.</p><ul>${bundle.targets.filter(row=>!row.boltz_input).map(row=>`<li>${escape(row.target_id)}: ${escape(row.next_step)}</li>`).join('')}</ul><p>Saved on this machine: ${escape(bundle.directory)}</p></details><details><summary>Sources &amp; scientific limits</summary><ul>${bundle.targets.map(row=>`<li>${escape(row.target_id)}: ${escape(row.reference.pdb||'No curated reference')} · ${escape(row.reference.accession||'User supplied')} · ${escape(row.reference.reason||row.reference.sequence_source||'No mapped sequence')}</li>`).join('')}</ul><ul>${bundle.warnings.map(w=>`<li>${escape(w)}</li>`).join('')}</ul></details>`;
    document.querySelectorAll('[data-view-target]').forEach(button=>button.onclick=()=>document.dispatchEvent(new CustomEvent('isoform:view',{detail:button.dataset.viewTarget})));
    if($('runBuiltPair'))$('runBuiltPair').onclick=()=>{$('mode').value='live';$('sequence').value=data.target.sequence;updateSetup();$('run').focus();};
    $('result').hidden=false;currentResult=bundle;
  }
  async function buildInputs(){
    if(location.protocol==='file:'){$('formFeedback').textContent='Open IsoForm through its Python server to build inputs.';return;}
    resetSteps();$('result').hidden=true;setBusy(true);setStep(0,'done','Selection captured');setStep(1,'running','Fetching / checking references');$('runStatus').textContent='Building real input files…';
    try{
      const bundle=await api('/api/auto-inputs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(screenRequest())},90000);
      setStep(1,bundle.summary.structures===bundle.summary.proteins?'done':'warning',`${bundle.summary.structures} structures available`);
      setStep(2,bundle.summary.boltz_inputs===bundle.summary.proteins?'done':'warning',`${bundle.summary.boltz_inputs} pose inputs built`);
      setStep(3,'done','Inputs saved · not predictions');showInputs(bundle);$('runStatus').textContent='Inputs built · no model run';await refreshStructures();
    }catch(error){setStep(1,'failed','Build needs attention');$('runStatus').textContent='Input build incomplete';$('formFeedback').textContent=error instanceof SyntaxError?'Restart the updated IsoForm server.':error.message;}
    finally{setBusy(false);}
  }
  function showPlan(plan){
    const s=plan.summary,labels={prepared_inputs_available:'Prepared inputs available',preparation_required:'Preparation needed',missing_inputs:'Inputs missing',invalid_inputs:'Input checks failed'};
    const validation=plan.candidate.smiles_validation;
    $('result').className='result neutral';
    $('result').innerHTML=`<div class="result-top"><div><div class="section-label">AVAILABILITY · ${escape(plan.candidate.label)}</div><h2>${s.prepared_proteins} UMA pockets prepared</h2><p>Build inputs to collect the other starting files automatically.</p></div><span class="result-tag">Not run</span></div><div class="screen-rows">${plan.targets.map(row=>`<div class="screen-row"><div><b>${escape(row.protein.label)}</b><small>${row.structure?.status==='available'?escape(row.structure.pdb)+' · reference available':'Reference not loaded'}</small></div><span class="screen-state">${escape(labels[row.preparation.status]||row.preparation.status)}</span><span class="screen-unassessed">Not assessed</span></div>`).join('')}</div><p class="result-source">No model was launched. A reference structure is not a prepared candidate pocket.</p>${validation?`<p class="result-source">SMILES: ${validation.status==='syntax_checked'?'syntax checked':'chemistry not checked'}.</p>`:''}<details><summary>What remains for UMA?</summary><ul>${(plan.targets.find(row=>row.missing_requirements?.length)?.missing_requirements||['Runtime setup and scientific validation are separate.']).map(note=>`<li>${escape(note)}</li>`).join('')}</ul></details><div class="result-actions">${plan.available_jobs.length?'<button class="secondary accent" id="openPair" type="button">Run prepared pair ↗</button>':''}<button class="secondary" id="openBatch" type="button">Upload pockets ↗</button><button class="download-plan" type="button" id="downloadPlan">Plan JSON ↓</button></div>`;
    if($('openPair'))$('openPair').onclick=()=>{$('mode').value='live';$('sequence').value=data.target.sequence;updateSetup();$('run').focus();};
    $('openBatch').onclick=()=>{$('mode').value='batch';updateSetup();$('batchFile').focus();};
    $('downloadPlan').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(plan,null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download=`screen-plan-${plan.plan_id}.json`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);};
    $('result').hidden=false;currentResult=plan;
  }
  function downloadJSON(value,name){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  function resetBatch(){batchInput=null;batchAudit=null;$('provisionalConfirm').checked=false;$('provisionalLabel').hidden=true;$('batchFileStatus').textContent='Complete atomistic inputs required.';document.dispatchEvent(new CustomEvent('sentinel:prepared',{detail:null}));}
  async function checkPrepared(){
    if(!batchInput){$('formFeedback').textContent='Choose a prepared JSON file or try the example.';return;}
    setBusy(true);$('result').hidden=true;$('formFeedback').textContent='';resetSteps();setStep(0,'done','File loaded');setStep(1,'running','Checking atoms & state');
    try{
      batchAudit=await api('/api/prepared-check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(batchInput)},30000);
      $('provisionalLabel').hidden=!batchAudit.provisional;$('batchFileStatus').textContent=`${batchAudit.systems.length} pockets · ${batchAudit.systems.reduce((n,s)=>n+s.atoms,0)} atoms`;
      setStep(1,'done','Input checks passed');$('runStatus').textContent='Inputs checked · not run';
      $('result').className='result neutral';$('result').innerHTML=`<div class="result-top"><div><div class="section-label">PREPARED INPUTS</div><h2>${batchAudit.systems.length} pockets checked</h2><p>${escape(batchInput.label)}</p></div><span class="result-tag">Not run</span></div><div class="screen-rows">${batchAudit.systems.map(s=>`<div class="screen-row"><div><b>${escape(s.protein_id)}</b><small>${escape(s.ligand)}</small></div><span class="screen-state">${s.atoms} atoms · charge ${s.charge} · multiplicity ${s.multiplicity}</span><span class="screen-unassessed">${s.provisional?'Provisional':'Review declared'}</span></div>`).join('')}</div><p class="result-source">Total energy and forces only. Not binding affinity or cross-protein ranking.</p><details><summary>Input audit</summary><p>${escape(batchAudit.note)}</p><ul>${batchAudit.systems.flatMap(s=>s.warnings.map(w=>`<li>${escape(s.protein_id)}: ${escape(w)}</li>`)).join('')}</ul><p>Input SHA-256: ${escape(batchAudit.input_sha256)}</p></details>`;
      $('result').hidden=false;document.dispatchEvent(new CustomEvent('sentinel:prepared',{detail:batchInput}));
    }catch(error){batchAudit=null;setStep(1,'failed','Inputs need attention');$('runStatus').textContent='Preparation required';$('formFeedback').textContent=error instanceof SyntaxError?'Use the updated IsoForm server for prepared inputs.':error.message;document.dispatchEvent(new CustomEvent('sentinel:prepared',{detail:null}));}
    finally{setBusy(false);$('runLabel').textContent=batchAudit?`Run UMA · ${batchAudit.systems.length} pockets`:'Check pockets';}
  }
  async function runPrepared(){
    if(!batchAudit){await checkPrepared();return;}
    if(batchAudit.provisional&&!$('provisionalConfirm').checked){$('formFeedback').textContent='Confirm the provisional-input declaration before running.';return;}
    if(!runtime?.execution_enabled){$('formFeedback').textContent='UMA is disabled. Restart the server with --enable-uma.';return;}
    if(runtime.preflight?.result?.status!=='ready_to_load'){$('formFeedback').textContent=runtime.preflight?.result?.issues?.join(' ')||'UMA runtime is unavailable. Check the interpreter and checkpoint.';return;}
    setBusy(true);$('result').hidden=true;$('activity').hidden=false;$('jobProgress').max=batchAudit.systems.length;$('jobProgress').value=0;$('activityText').textContent='Starting UMA…';
    try{
      const job=await api('/api/prepared-jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch:batchInput,confirm_provisional:$('provisionalConfirm').checked})},30000);
      activeJob=job.id;rememberJob(job.id);$('runStatus').textContent='UMA running';followJob(job.id);
    }catch(error){setBusy(false);$('activity').hidden=true;setStep(2,'failed','Not started');$('formFeedback').textContent=error.message;}
  }
  function showBatchResult(job){
    const r=job.result||{},rows=r.systems||[],ok=job.state==='completed'&&r.status==='exploratory'&&r.synthetic===false;
    $('result').className='result '+(ok?'':'neutral');
    $('result').innerHTML=`<div class="result-top"><div><div class="section-label">UMA · PREPARED POCKETS</div><h2>${ok?'Calculation complete':'Calculation needs attention'}</h2><p>${escape(job.label)}</p></div><span class="result-tag">${ok?'Real model output':'Check the run'}</span></div><div class="screen-rows">${rows.map(row=>`<div class="screen-row"><div><b>${escape(row.protein_id)}</b><small>${escape(row.ligand)}</small></div><div><b>${energy(row.energy_eV)}</b><small>Total potential energy</small></div><span class="screen-state">${row.status==='completed'?`${row.maximum_force_eV_A.toFixed(2)} eV/Å max force`:'Failed'}</span></div>`).join('')}</div><p class="result-source">Do not rank proteins by these total energies. This is not a binding-affinity or selectivity calculation.</p><details><summary>Run details</summary><p>${escape(job.output_directory)}</p><p>${escape(r.provisional?'Provisional prepared inputs.':'Review declarations are supplied by the preparer.')}</p><pre>${escape((r.reasons?.length?r.reasons:job.log||[]).slice(-8).join('\n'))}</pre></details><button class="download-plan" id="downloadBatchResult" type="button">Results JSON ↓</button>`;
    $('downloadBatchResult').onclick=()=>downloadJSON(job,'uma-pockets-'+job.id+'.json');$('result').hidden=false;currentResult=job;
  }
  async function planScreen(){
    if(location.protocol==='file:'){$('formFeedback').textContent='Run the IsoForm Python server to build a plan. A GPU and --enable-uma are not required.';return;}
    const key=Object.entries(screening.candidates).find(([,c])=>c.label===$('candidate').value)?.[0];
    const request={candidate_id:$('candidate').value==='new'?'custom':key,target_id:$('planTarget').value,panel_id:$('planPanel').value};
    if(request.candidate_id==='custom'){request.candidate_name=$('candidateName').value.trim()||'New candidate';request.smiles=$('planSmiles').value.trim();}
    if(request.target_id==='custom')request.target_sequence=$('planSequence').value;
    resetSteps();$('result').hidden=true;setBusy(true);setStep(0,'running','Checking request');$('runStatus').textContent='Building a CPU screening plan';
    try{
      const plan=await api('/api/screen-plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
      setStep(0,'done',plan.candidate.smiles_validation?.status==='not_checked'?'Chemistry review pending':'Plan inputs accepted');
      setStep(1,'done',`${plan.summary.proteins} proteins selected`);
      setStep(2,plan.summary.needs_preparation?'warning':'done',`${plan.summary.prepared_proteins}/${plan.summary.proteins} have UMA inputs`);
      setStep(3,'done','Plan ready · no predictions');showPlan(plan);$('runStatus').textContent='Plan ready · no GPU used';
    }catch(error){setStep(0,'failed','Plan not created');$('runStatus').textContent='Check planning inputs';$('formFeedback').textContent=error instanceof SyntaxError?'Planning needs the updated IsoForm Python server, not a static file server.':error.message;}
    finally{setBusy(false);}
  }
  function details(card){
    const alerts=card?.alerts||[];
    return `<details><summary>Evidence &amp; checks${alerts.length?` · ${alerts.length} notes`:''}</summary><p>Paired assay threshold: ${data.policy.minimum_validation_fold}×. Model scores and assay endpoints are evaluated separately.</p>${alerts.length?'<ul>'+alerts.map(a=>`<li>${escape(a)}</li>`).join('')+'</ul>':''}<p>UMA pose check: ${escape(card?.uma||'unassessed')}. Geometry: ${escape(card?.geometry||'unassessed')}. Boltz artifact: ${escape(card?.boltz_status||'unassessed')}.</p><p>Related targets ${escape(data.next_tier.join(', '))} remain unassessed.</p></details>`;
  }
  function showReference(card){
    const pass=card.decision==='validated_selective',hasAssay=Number.isFinite(card.assay_fold)&&card.assay_fold>0;
    const assayPreferred=hasAssay?(card.assay_fold>1?'CYP11B2':card.assay_fold<1?'CYP11B1':'Neither'):null;
    const assayMagnitude=hasAssay?Math.max(card.assay_fold,1/card.assay_fold):null;
    const title=hasAssay?(pass?'Meets the assay threshold':'Below the selectivity threshold'):'More evidence needed';
    const geometryFailed=card.geometry==='identity_or_chirality_failure';
    const description=hasAssay?(assayPreferred==='Neither'?`${card.label}: equal paired ${card.assay_endpoint} values.`:`${card.label}: ${fold(assayMagnitude)} preference for ${assayPreferred} in the paired ${card.assay_endpoint} reference.`):'Prepare this candidate against both proteins to start an analysis.';
    const conflict=hasAssay&&pass&&card.model_gate==='off_target_alert';
    $('result').className='result '+(pass?'':hasAssay?'risk':'neutral');
    $('result').innerHTML=`<div class="result-top"><div><div class="section-label">SAVED EVIDENCE · ${escape(card.label)}</div><h2>${title}</h2><p>${escape(description)}</p></div><span class="result-tag">${hasAssay?'Paired assay reference':'Awaiting evidence'}</span></div><div class="result-stats"><div><b>${fold(card.assay_fold)}</b><small>${escape(card.assay_endpoint||'Paired assay')} · experimental reference</small></div><div><b>${geometryFailed?'Not interpretable':fold(card.boltz_fold)}</b><small>Boltz · saved model comparison</small></div><div><b>${data.policy.minimum_validation_fold}×</b><small>Assay threshold</small></div></div><p class="result-next">${conflict?'The assay clears the threshold, but the model disagrees. Investigate the mismatch and expand the counter-screen.':hasAssay?(pass?'The paired reference supports selectivity against CYP11B1. Additional off-target assays are still needed.':'Do not advance this candidate as selective under the current policy. A paired counter-screen or redesign is the next step.'):'A new molecule needs a prepared pose, model calculations and a paired assay.'}</p><p class="result-source">Saved experimental evidence determines this outcome; no new calculation was launched.</p>${details(card)}`;
    if(hasAssay){const stats=$('result').querySelector('.result-stats');stats.children[0].querySelector('b').textContent=fold(assayMagnitude)+' · '+(assayPreferred==='Neither'?'Neither':assayPreferred.replace('CYP11',''));stats.children[0].querySelector('small').textContent=card.assay_endpoint+' ratio · experimental reference';}
    $('result').hidden=false;currentResult=card;
  }
  function missingEvidence(){
    const label=$('candidateName').value.trim()||'New candidate';
    showReference({label,decision:'needs_assay',assay_fold:null,boltz_fold:null,alerts:[],uma:'unassessed',geometry:'unassessed'});
  }
  function componentProgress(job){
    if(job.kind==='uma_pocket_batch'){const rows=job.result?.systems||[];return {done:rows.filter(s=>s.status==='completed').length,failed:rows.filter(s=>s.status==='failed').length,total:job.total_components||job.result?.total_systems||1};}
    const entries=Object.entries(job.result?.enzymes||{}).flatMap(([protein,row])=>Object.entries(row.components||{}).map(([component,r])=>({protein,component,...r})));
    const done=entries.filter(e=>e.status==='completed').length;
    const failed=entries.filter(e=>e.status==='failed').length;
    return {done,failed,total:8};
  }
  function showLive(job){
    if(job.kind==='uma_pocket_batch'){showBatchResult(job);return;}
    const r=job.result||{},ok=job.state==='completed'&&r.status==='exploratory'&&r.synthetic===false&&r.descriptor==='ligand_water_exchange_eV'&&Number.isFinite(r.delta_B2_minus_B1_eV);
    const lastReasons=r.reasons?.length?r.reasons:(job.log||[]).slice(-8);
    const delta=r.delta_B2_minus_B1_eV,preferred=ok?(delta<0?'CYP11B2':delta>0?'CYP11B1':null):null;
    const proxy=r.preference_summary?.energy_fold_proxy,hasProxy=ok&&proxy?.status==='hypothetical_energy_proxy';
    let magnitude='Unavailable';
    if(hasProxy){magnitude=Number.isFinite(proxy.fold_magnitude)&&proxy.fold_magnitude<10000?proxy.fold_magnitude.toLocaleString('en-US',{maximumSignificantDigits:3})+'×':escape(proxy.scientific_notation).replace(/\^([+-]?\d+)/g,'<sup>$1</sup>')+'×';}
    $('result').className='result '+(ok?'preference-card':'neutral');
    $('result').innerHTML=`<div class="result-top"><div><div class="section-label">${ok?'LIVE UMA · '+escape(r.ligand||job.label):'RUN STATUS'}</div><h2>${ok?(preferred?`UMA exchange favors ${preferred}`:'No exchange-energy difference'):'Calculation needs attention'}</h2></div><span class="result-tag">${ok?'Exploratory only':'Review the run'}</span></div>${ok?`<div class="preference-summary"><div><p class="section-label">EXPLORATORY FOLD PREFERENCE</p><div class="preference-value" id="energyFoldProxy">${magnitude}</div><p class="proxy-scope">Boltzmann energy proxy · ${escape(proxy?.temperature_K??298.15)} K<br>Not binding selectivity.</p></div><div class="preference-context"><strong>${preferred?preferred+' / '+(preferred==='CYP11B2'?'CYP11B1':'CYP11B2'):'Equal energy weights'}</strong><p>Lower-energy / higher-energy weight</p><strong>${energy(delta)}</strong><p>Exchange ΔE · B2 − B1</p></div></div>${hasProxy&&proxy.extreme_magnitude?'<p class="proxy-warning">Extreme proxy value. This is not evidence of extreme biological selectivity.</p>':''}${!hasProxy?'<p class="proxy-warning">The run does not meet the checks for a fold proxy. No fold value has been inferred.</p>':''}<p class="result-next">Next: check pose sensitivity and compare paired experimental assays.</p>`:'<p class="result-next">No usable comparison was produced. Inspect the run details below.</p>'}<details><summary>Assumptions &amp; run details</summary><p>The proxy is exp(|ΔE| / kBT), using matched ligand/water exchange potential energies as hypothetical statistical weights. It is not a binding-affinity ratio, calibrated selectivity prediction, or confidence score. Solvent, entropy and thermodynamic sampling are not supplied by this frozen-pocket calculation. <a href="https://goldbook.iupac.org/terms/view/S05915" target="_blank" rel="noopener">The equilibrium relation requires Gibbs free energies.</a></p><p>Binding fold selectivity: not determined. Provisional prepared inputs; no experimental validation has been performed by this run.</p><p>B2 exchange: ${energy(r.enzymes?.CYP11B2?.exchange_energy_eV)} · B1 exchange: ${energy(r.enzymes?.CYP11B1?.exchange_energy_eV)}</p><p>Job ${escape(job.id)} · ${escape(job.elapsed_seconds)} s · ${escape(r.backend?.device||'configured device')}</p><p>${escape(job.output_directory)}</p>${lastReasons.length?`<pre>${escape(lastReasons.join('\n'))}</pre>`:''}${proxy?.warnings?.length?'<ul>'+proxy.warnings.map(w=>'<li>'+escape(w)+'</li>').join('')+'</ul>':''}</details>${ok?'<button class="download-plan" id="downloadExchangeResult" type="button">Results JSON ↓</button>':''}`;
    if($('downloadExchangeResult'))$('downloadExchangeResult').onclick=()=>downloadJSON(job,'isoform-exchange-'+job.id+'.json');
    $('result').hidden=false;currentResult=job;
  }
  function rememberJob(id){try{if(id)sessionStorage.setItem('sentinelJob',id);else sessionStorage.removeItem('sentinelJob');}catch{}}
  async function followJob(id){
    try{
      const job=await api('/api/jobs/'+encodeURIComponent(id)),progress=componentProgress(job);
      if(job.kind==='uma_pocket_batch'&&$('mode').value!=='batch'){setBusy(false);$('mode').value='batch';updateSetup();setBusy(true);$('activity').hidden=false;setStep(0,'done','Saved input');}
      const runningCandidate={r_fadrozole:'R-fadrozole',s_fadrozole:'S-fadrozole'}[job.preset];
      if(runningCandidate&&data.candidates[runningCandidate])$('candidate').value=runningCandidate;
      if(displayedJob!==job.id){
        const preview=previewJob(job).catch(()=>{if(activeJob===job.id)$('formFeedback').textContent='Run results available; exact input preview could not be loaded.';});
        if(job.state!=='running')await preview;
      }
      $('jobProgress').max=progress.total;$('jobProgress').value=progress.done;
      $('activityText').textContent=progress.done?`${progress.done}/${progress.total} energies · ${job.elapsed_seconds}s`:`Loading UMA · ${job.elapsed_seconds}s`;
      document.dispatchEvent(new CustomEvent('isoform:run-state',{detail:{busy:job.state==='running',text:$('activityText').textContent}}));
      setStep(2,'running',`${progress.done}/${progress.total} energies`);
      if(progress.done||progress.failed)setStep(1,'running','Geometry checks in progress');
      if(job.state==='running'){setTimeout(()=>followJob(id),1500);return;}
      $('activity').hidden=true;setBusy(false);rememberJob(null);activeJob=null;
      const ok=job.state==='completed';setStep(1,ok?'done':'warning',ok?'Prepared geometry checked':'Inspect geometry / logs');setStep(2,ok?'done':'failed',ok?`${progress.done} energies calculated`:'Execution failed');setStep(3,ok?'done':'warning',ok?'Results saved':'Review required');
      $('runStatus').textContent=ok?'UMA run complete':'Run needs attention';showLive(job);
    }catch(error){
      $('activity').hidden=true;setBusy(false);$('runStatus').textContent='Connection interrupted';setStep(2,'warning','Status unavailable');
      $('formFeedback').textContent='The job may still be running. Reconnect using “Resume status”; this will not launch a second job.';
      $('runLabel').textContent='Resume status';
    }
  }
  async function analyze(event){
    event.preventDefault();if(busy)return;$('formFeedback').textContent='';
    if(activeJob){setBusy(true);$('activity').hidden=false;followJob(activeJob);return;}
    if($('mode').value==='calibrated'){await runCalibrated();return;}
    if($('mode').value==='plan'){await buildInputs();return;}
    if($('mode').value==='batch'){await runPrepared();return;}
    const seq=validateSequence();resetSteps();$('result').hidden=true;
    if(!seq.valid||!seq.exact){setStep(0,'failed',seq.valid?'Different target sequence':'Sequence invalid');$('formFeedback').textContent='Use the bundled CYP11B2 sequence. A different protein needs a prepared model before analysis.';$('runStatus').textContent='Check the target sequence';return;}
    setStep(0,'done','Target sequence matched');
    if($('mode').value==='reference'){
      const card=selected();
      if(!card){setStep(1,'warning','Structure needed');setStep(2,'warning','No model evidence');setStep(3,'warning','Prepare the candidate');missingEvidence();$('runStatus').textContent='Preparation needed';return;}
      const failed=card.geometry==='identity_or_chirality_failure',review=card.geometry!=='diagnostic_only';
      setStep(1,failed||review?'warning':'done',failed?'Chirality flag':review?'Review needed':'Saved audit read');
      setStep(2,'done','Saved model results');setStep(3,'done','Paired assay checked');
      showReference(card);$('runStatus').textContent='Saved evidence reviewed';return;
    }
    if(!preset()){$('formFeedback').textContent='Choose R- or S-fadrozole for a live calculation. The other candidates have saved evidence only.';setStep(1,'warning','Preparation needed');return;}
    if(!runtime?.execution_enabled||runtime.preflight?.result?.status!=='ready_to_load'){
      $('formFeedback').textContent=runtime?.preflight?.result?.issues?.join(' ')||'Start the IsoForm server with UMA enabled to run a new calculation. Saved evidence is available now.';setStep(2,'warning','UMA unavailable');return;
    }
    setBusy(true);$('activity').hidden=false;$('activityText').textContent='Submitting prepared structures…';$('jobProgress').value=0;$('runStatus').textContent='Starting a real UMA run';
    try{
      await previewPair();
      const job=await api('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preset:preset()})});
      activeJob=job.id;rememberJob(job.id);setStep(1,'running','Checking prepared geometry');setStep(2,'running','Loading UMA');followJob(job.id);
    }catch(error){setBusy(false);$('activity').hidden=true;setStep(2,'failed','Not started');$('formFeedback').textContent=error.message;$('runStatus').textContent='Unable to start UMA';}
  }
  async function runCalibrated(){
    if(location.protocol==='file:'){$('formFeedback').textContent='Start the Python server to calculate the fitted ratios. No GPU required.';return;}
    setBusy(true);resetSteps();$('result').hidden=true;setStep(0,'running','Reading supplied outputs');$('runStatus').textContent='Recomputing energy → fold…';
    try{
      const r=await api('/api/calibrated-selectivity',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({candidate_id:$('calibratedCandidate').value,pose_policy:$('posePolicy').value})});
      r.pipeline_steps.forEach((step,i)=>setStep(i,step.state,step.detail));
      $('result').className='result calibrated-result';$('result').innerHTML=window.renderCalibratedSelectivity(r);$('result').hidden=false;currentResult=r;
      $('downloadCalibrated').onclick=()=>downloadJSON(r,`isoform-${r.candidate_id}-${r.pose_policy}.json`);
      $('runStatus').textContent=r.empirical_fit?'Recomputed · retrospective fit · robustness unresolved':'Stopped · no valid B2 exchange';
    }catch(error){setStep(0,'failed','Analysis unavailable');$('runStatus').textContent='Check the calculation';$('formFeedback').textContent=error.message;}
    finally{setBusy(false);}
  }
  Object.values(data.calibrated_candidates||{}).forEach(card=>{const option=document.createElement('option');option.value=card.id;option.textContent=card.label;$('calibratedCandidate').append(option);});
  ['calibratedCandidate','posePolicy'].forEach(id=>$(id).onchange=updateSetup);
  candidates.forEach(card=>{const option=document.createElement('option');option.value=card.label;option.textContent=card.label;$('candidate').append(option);});
  const fresh=document.createElement('option');fresh.value='new';fresh.textContent='New candidate';$('candidate').append(fresh);
  $('candidate').value='R-fadrozole';
  $('sequence').value=data.target.sequence;
  $('candidate').onchange=()=>{
    if($('mode').value==='live'&&!preset())$('mode').value=$('candidate').value==='new'?'plan':'reference';
    updateSetup();
    if($('mode').value==='reference'&&selected())analyze({preventDefault(){}});
  };
  $('mode').onchange=updateSetup;$('sequence').oninput=updateSetup;$('candidateName').oninput=updateSetup;
  ['planTarget','planPanel'].forEach(id=>$(id).onchange=updateSetup);
  ['planSequence','planSmiles'].forEach(id=>$(id).oninput=updateSetup);
  $('batchFile').onchange=async()=>{const file=$('batchFile').files[0];resetBatch();updateSetup();if(!file)return;try{if(file.size>4*1024*1024)throw Error('Maximum file size is 4 MiB.');setBusy(true);batchInput=JSON.parse(await file.text());setBusy(false);await checkPrepared();}catch(error){setBusy(false);$('formFeedback').textContent=error.message;}};
  $('batchExample').onclick=async()=>{$('batchFile').value='';resetBatch();updateSetup();setBusy(true);try{batchInput=await api('/api/prepared-example');setBusy(false);await checkPrepared();}catch(error){setBusy(false);$('formFeedback').textContent=error.message;}};
  $('batchTemplate').onclick=()=>downloadJSON({schema_version:1,kind:'uma_pocket_batch',label:'My prepared pockets',systems:[{id:'target_1',protein_id:'YOUR_TARGET',ligand:'YOUR_MOLECULE',source:'',preparation:'',review:{approved:false,provisional:false,reviewer:''},atoms:[],ligand_atom_ids:[],state:{charge:null,multiplicity:null,convention:''},coordination:[],covalent_bounds:[],chirality_checks:[]}]},'prepared-pocket-template.json');
  document.querySelectorAll('[data-example]').forEach(button=>button.onclick=()=>{if(!data.candidates[button.dataset.example])return;$('candidate').value=button.dataset.example;$('mode').value='reference';updateSetup();analyze({preventDefault(){}});});
  $('checkPlan').onclick=planScreen;
  if(new URLSearchParams(location.search).get('workflow')==='live')$('mode').value='live';
  $('analysisForm').onsubmit=analyze;planChoices();updateSetup();connect();connectCatalog();refreshStructures();
  try{const stored=sessionStorage.getItem('sentinelJob');if(stored){activeJob=stored;$('mode').value='live';updateSetup();setBusy(true);$('activity').hidden=false;$('runStatus').textContent='Reconnecting to your UMA run';followJob(stored);}}catch{}
})();

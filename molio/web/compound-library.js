'use strict';
let compoundSearchRevision=0, compoundImportBusy=false;
function smilesMarkup(smiles){return `<div class="smiles-display"><span>SMILES</span><code class="smiles-code">${escapeHTML(smiles)}</code><button type="button" data-copy-smiles="${escapeHTML(smiles)}" aria-label="Copy SMILES">Copy</button></div>`;}
function bindSmilesCopies(element){element.querySelectorAll('[data-copy-smiles]').forEach(b=>b.onclick=async()=>{try{await navigator.clipboard.writeText(b.dataset.copySmiles);toast('SMILES copied.');}catch(_){toast('Select the displayed SMILES to copy it.');}});}
function supportingRecordsMarkup(records){return records?.length?`<details class="compound-evidence"><summary>${records.length} reported assay record${records.length===1?'':'s'} · not a binding verdict</summary>${records.map(r=>`<div><strong>${escapeHTML(r.standard_type||'Unspecified endpoint')} ${escapeHTML(r.standard_relation||'')} ${escapeHTML(r.standard_value??'not reported')} ${escapeHTML(r.standard_units||'')}</strong><p>${escapeHTML(r.assay_description||'No assay description supplied')}</p><small>Assay ${escapeHTML(r.assay_chembl_id||'unknown')} · type ${escapeHTML(r.assay_type||'unknown')} · activity ${escapeHTML(r.activity_id??'unknown')} · document ${escapeHTML(r.document_chembl_id||'unknown')}</small>${r.data_validity_comment||r.potential_duplicate||r.assay_variant_mutation?`<p>Source flags: ${escapeHTML(r.data_validity_comment||'')}${r.potential_duplicate?' · possible duplicate':''}${r.assay_variant_mutation?' · variant: '+escapeHTML(r.assay_variant_mutation):''}</p>`:''}</div>`).join('')}<p>Different assays are not directly comparable. Target attribution, construct and biological relevance have not been reviewed. No ranking or averaging is applied.</p></details>`:'';}
function candidateMarkup(row){return `<article class="compound-option"><div><strong>${escapeHTML(row.name)}</strong><small>${escapeHTML(row.source)}</small></div>${smilesMarkup(row.smiles)}<p class="map-help">${escapeHTML(row.evidence_note)}</p>${supportingRecordsMarkup(row.evidence)}<div class="starter-view-tools"><button class="primary" data-add-candidate="${escapeHTML(row.id)}">Add to workspace</button>${row.source_url?`<a href="${escapeHTML(row.source_url)}" target="_blank" rel="noreferrer">Source ↗</a>`:''}</div></article>`;}
function renderCandidates(id,rows){const el=$(id);el.innerHTML=rows.map(candidateMarkup).join('');bindSmilesCopies(el);el.querySelectorAll('[data-add-candidate]').forEach(b=>{b.disabled=compoundImportBusy;b.onclick=()=>importCompound(b.dataset.addCandidate);});}
async function importCompound(id){
  if(compoundImportBusy)return;compoundImportBusy=true;document.querySelectorAll('[data-add-candidate]').forEach(b=>b.disabled=true);$('compound-import-status').textContent='Preparing chemistry and a 3D shape…';
  try{const result=await experimentJSON('/api/starter/import-compound',{id});state.data.compounds.push(result.compound);state.conformers[result.compound.id]=result.conformer;renderStarterCompounds();starterReadiness();$('compound-import-status').textContent=`${result.compound.name} added. Use Design or Predict beside the molecule.`;$('starter-compounds').scrollIntoView({block:'start',behavior:'smooth'});}
  catch(e){$('compound-import-status').textContent=e.message;}
  finally{compoundImportBusy=false;document.querySelectorAll('[data-add-candidate]').forEach(b=>b.disabled=false);}
}
async function checkTargetChemistry(){
  $('target-chemistry-refresh').disabled=true;$('target-chemistry-status').textContent='Checking target-associated assay records. Other starting options remain available.';
  try{const result=await experimentJSON('/api/starter/target-compounds',{});$('target-chemistry-status').textContent=result.message;$('target-chemistry-count').textContent=`(${result.candidates.length})`;renderCandidates('target-chemistry-results',result.candidates);if(result.candidates.length)$('target-chemistry-details').open=true;}
  catch(e){$('target-chemistry-status').textContent='Could not check the provider: '+e.message+' This does not mean no chemistry exists. Compound search and offline examples are still available.';}
  finally{$('target-chemistry-refresh').disabled=false;}
}
async function startCompoundLibrary(){
  $('starter-protein-sequence').textContent=state.data.protein_sequence;
  $('target-chemistry-refresh').onclick=checkTargetChemistry;
  $('compound-search-form').onsubmit=async event=>{event.preventDefault();const revision=++compoundSearchRevision;$('compound-search-status').textContent='Looking up chemical structures in PubChem…';$('compound-search-button').disabled=true;
    try{const result=await experimentJSON('/api/starter/find-compounds',{query:$('compound-search-query').value});if(revision!==compoundSearchRevision)return;$('compound-search-status').textContent=result.message;renderCandidates('compound-search-results',result.candidates);}
    catch(e){if(revision===compoundSearchRevision)$('compound-search-status').textContent=e.message+' You can still use an offline example or paste SMILES.';}
    finally{if(revision===compoundSearchRevision)$('compound-search-button').disabled=false;}
  };
  try{
    const data=await experimentJSON('/api/starter/library');renderCandidates('compound-examples',data.examples);
    const targetRows=data.candidates.filter(r=>r.id.startsWith('chembl-'));renderCandidates('target-chemistry-results',targetRows);
    const searchRows=data.candidates.filter(r=>r.id.startsWith('pubchem-'));if(searchRows.length){renderCandidates('compound-search-results',searchRows.slice(-8));$('compound-search-status').textContent='Previously found chemical structures · saved locally';}
    $('starter-function').textContent=data.protein_context.function.join(' ')||'No function description was included in the downloaded record.';
    $('starter-structure-links').innerHTML=data.protein_context.structures.map(r=>`<a href="${escapeHTML(r.url)}" target="_blank" rel="noreferrer"><strong>${escapeHTML(r.id)} ↗</strong><small>${escapeHTML(r.details)}</small></a>`).join('')||'<p>No PDB cross-references in this UniProt snapshot.</p>';
    if(data.target_lookup){$('target-chemistry-status').textContent=data.target_lookup.message+' Checked '+new Date(data.target_lookup.checked_at).toLocaleDateString()+'.';$('target-chemistry-count').textContent=`(${targetRows.length})`;}
    else checkTargetChemistry();
  }catch(e){$('compound-import-status').textContent='Compound library unavailable: '+e.message;$('manual-compound-entry').open=true;}
}

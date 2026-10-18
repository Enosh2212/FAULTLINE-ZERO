import './public-ui.js';
import * as workspace from './workspace.js?v=final-ui-2';
import {HeroAgentScene} from './hero_agent.js';
import {setupProjectUnderstanding} from './project_understanding.js';

import {renderVerificationLoader} from './verification_loader.js';



import {EvidenceGraph, esc} from './evidence_graph.js';

import {renderReport, renderTraces, terminalLog, commandFor, reportKey, modeLabel, finding} from './report.js';

const $=id=>document.getElementById(id);

const state={view:'landing',key:'payment',demo:'payment',mode:'simple',reports:[],current:null,diff:null,evidence:{nodes:[],edges:[]},snapshot:{nodes:[],edges:[]},token:sessionStorage.getItem('fz_token')||'',running:false,loading:false,selection:0};

let graph,explorer,hero,toastTimer,project;

async function api(path,options={}) {

  const response=await fetch(path,{...options,headers:{...(options.body?{'Content-Type':'application/json'}:{}),...(state.token?{Authorization:`Bearer ${state.token}`}:{}) ,...(options.headers||{}),...(state.csrfToken?{'X-CSRF-Token':state.csrfToken}:{})},cache:'no-store'});

  if(!response.ok){let message=`HTTP ${response.status}`;try{const data=await response.json();message=typeof data.detail==='string'?data.detail:JSON.stringify(data.detail);}catch{}throw Error(message);}

  return response.json();

}

function toast(message,error=false){$('toast').textContent=message;$('toast').className=`toast show ${error?'error':'success'}`;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),4000);}

function setView(view){
  if(view==='saas')view='workspace/overview';
  if(view.startsWith('workspace')){
    hero?.stop();state.view='workspace';
    if(location.hash!==`#${view}`)history.replaceState(null,'',`#${view}`);
    workspace.show(view);return;
  }
  document.body.dataset.view=view;
  workspace.hide();
  const demoBanner=document.getElementById('demo-workspace-banner');
  if(demoBanner)demoBanner.hidden=view!=='investigation';
  if(state.view==='workspace'&&view!=='landing')refresh();
  if(view==='landing')hero?.start();else hero?.stop();

  if(!['landing','investigation','overview','history','memory','settings','project','saas'].includes(view))view='landing';state.view=view;

  document.querySelectorAll('.app-view').forEach(el=>el.classList.toggle('active',el.id===`view-${view}`));

  document.querySelectorAll('#view-nav [data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===view));

  document.querySelector('.liquid-command-bar').style.display=view==='investigation'?'flex':'none';

  document.querySelector('.workspace-shell').classList.toggle('landing-hidden',view==='landing');

  if(location.hash!==`#${view}`)history.replaceState(null,'',`#${view}`);



  if(view==='overview')requestAnimationFrame(()=>{explorer?.cy?.resize();explorer?.fit();});

  if(view==='history')renderHistory();

  if(view==='project'&&project)project.load();

  if(view==='saas'){ $('view-saas').style.visibility='hidden';loadSaasView(); }

}

function setDisplayMode(mode){

  state.mode=mode;document.querySelectorAll('.display-mode button').forEach(el=>el.setAttribute('aria-pressed',String(el.id===`${mode}-mode`)));

  $('view-investigation').dataset.mode=mode;

  if(mode==='technical'){['graph','diff','tools','reproduce'].forEach(name=>$(`${name}-disclosure`).open=true);requestAnimationFrame(()=>{graph?.cy?.resize();graph?.fit();});}

  else document.querySelectorAll('#view-investigation .evidence-disclosure').forEach(el=>el.open=false);

}

function openEvidence(name,scroll=true){const element=$(`${name}-disclosure`);element.open=true;if(scroll)element.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});if(name==='graph')requestAnimationFrame(()=>{graph?.cy?.resize();graph?.fit();});}

function updateRunButtons(){const disabled=state.running||state.loading||!state.diff;$('run-button').disabled=disabled;$('terminal-run').disabled=disabled;document.querySelectorAll('[data-action="run"]').forEach(btn=>btn.disabled=disabled);$('change-select').disabled=state.running;$('execution-mode').disabled=state.running;}

function reportContext(){return {nodes:state.evidence.nodes,diff:state.diff};}

function renderEmpty(text='Select a change and run an investigation to verify its behavior.'){

  $('report-root').innerHTML=`<section class="report-empty"><span class="section-kicker">REGRESSION VERIFICATION</span><h1>Understand what changed.<br><span>Verify what it could break.</span></h1><p>${esc(text)}</p><button class="hero-primary-btn empty-state-run" data-action="run">Run Investigation</button></section>`;

}

function resetReport(){state.current=null;state.diff=null;state.evidence={nodes:[],edges:[]};$('execution-status').textContent='Loading change…';$('diff-code-view').textContent='Loading Git diff…';$('diff-revisions').textContent='';$('tool-traces').innerHTML='<p>No tool calls recorded for the selected change.</p>';$('reproduction-command').textContent='Run an investigation first.';$('agent-terminal').textContent='Ready. No execution result for this selection.';$('execution-annotation').textContent='';$('scenario-specs').innerHTML='';renderFlyMemory([]);graph.setData({nodes:[],edges:[]});renderEmpty('Loading the selected change. Previous evidence has been cleared.');setDisplayMode('simple');}

async function loadSelected(selectedReport=null){

  $('toast').classList.remove('show');

  const token=++state.selection;const key=$('change-select').value;state.key=key;state.loading=true;resetReport();updateRunButtons();$('context-change').textContent=$('change-select').selectedOptions[0].textContent;

  try{

    const diff=await api(`/api/v1/git/changes/${key}`);if(token!==state.selection)return;state.diff=diff;$('diff-code-view').textContent=diff.diff||'No diff returned.';$('diff-revisions').textContent=`Original ${diff.revisions?.baseline||'unavailable'} → Modified ${diff.revisions?.candidate||'unavailable'}`;

    try{const evidence=await api(`/api/v1/graph/evidence/${key}`);if(token!==state.selection)return;state.evidence=evidence;}catch(error){if(token!==state.selection)return;graph.status(`Evidence graph unavailable: ${error.message}. Git and verification can still be reviewed.`);}

    if(token!==state.selection)return;

    const report=selectedReport||state.reports.find(r=>reportKey(r)===key&&r.revisions?.baseline===diff.revisions?.baseline&&r.revisions?.candidate===diff.revisions?.candidate);

    if(selectedReport){

      const recorded=selectedReport.steps?.find(step=>step.tool==='get_git_diff');

      try{const archived=JSON.parse(recorded?.result||'{}');if(archived.diff){state.diff=archived;$('diff-code-view').textContent=archived.diff;$('diff-revisions').textContent=`Saved report revisions: ${selectedReport.revisions?.baseline||'unavailable'} → ${selectedReport.revisions?.candidate||'unavailable'}`;}}catch{}

    }

    if(report)showReport(report);else {renderEmpty();$('execution-status').textContent='Ready · no saved result';refreshFocusedGraph();loadFlyMemoryForCurrentChange();}

  }catch(error){if(token!==state.selection)return;renderEmpty(`Could not load the Git change: ${error.message}`);$('execution-status').textContent='Change unavailable';toast(error.message,true);}

  finally{if(token===state.selection){state.loading=false;updateRunButtons();}}

}

function graphSnapshot(){const nodes=new Map(state.snapshot.nodes.map(n=>[n.id,n]));state.evidence.nodes.forEach(n=>nodes.set(n.id,n));const edges=new Map([...state.snapshot.edges,...state.evidence.edges].map(e=>[`${e.source}|${e.relation}|${e.target}`,e]));return {nodes:[...nodes.values()],edges:[...edges.values()]};}

function refreshFocusedGraph(){

  const path=(state.current?.cases||[]).flatMap(c=>c.evidence_path||[]);

  // The curated subgraph contract already contains only connected entities for this change.

  const ids=state.evidence.nodes.map(n=>n.id);

  graph.setData(graphSnapshot(),{ids,path});

  const c=state.current?.cases?.[0];$('execution-annotation').innerHTML=c?`<span class="section-kicker">EXECUTION ANNOTATION · NOT A DATABASE EDGE</span><p>Original code <strong>${esc(c.baseline.outcome.toUpperCase())}</strong> → Modified code <strong>${esc(c.candidate.outcome.toUpperCase())}</strong>. ${esc(c.candidate.observed)}</p>`:'';

}

function showReport(report){

  state.current=report;$('report-root').innerHTML=renderReport(report,reportContext());$('execution-status').textContent=`${report.status==='completed'?'Completed':report.status||'Reported'} · ${modeLabel(report)}`;$('execution-status').className=report.verdict==='reproduced'?'status-attention':'';

  $('run-text').textContent='Re-run Investigation';$('tool-traces').innerHTML=(report.project_context?.repository?`<details class="tool-trace context-package"><summary><span>Source-backed project context</span><span>${esc(report.project_context.status)}</span></summary><p>${esc(report.project_context.repository)} · revision ${esc(report.project_context.revision)} · ${report.project_context.validated_invariants?.length||0} approved rules · ${report.project_context.metrics?.retrieval_ms??'—'}ms retrieval</p><pre>${esc(JSON.stringify(report.project_context,null,2))}</pre></details>`:'')+renderTraces(report);$('agent-terminal').textContent=terminalLog(report);

  const flyStep = (report.steps||[]).find(s=>s.tool==='recall_similar_incidents');

  if(flyStep&&flyStep.status==='ok'){try{renderFlyMemory(JSON.parse(flyStep.result));}catch{renderFlyMemory([]);}}else{loadFlyMemoryForCurrentChange();}

  $('reproduction-command').textContent=report.cases?.length?report.cases.map(c=>`# ${c.testcase_id}\n${commandFor(report,c,'baseline')}\n${commandFor(report,c,'candidate')}`).join('\n\n'):'No approved executable scenario was available; no reproduction command has been invented.';

  $('scenario-specs').innerHTML=(report.discovered_scenarios||[]).map(spec=>`<details><summary>Approved scenario · ${esc(spec.id)}</summary><pre class="agent-terminal">${esc(JSON.stringify(spec,null,2))}</pre></details>`).join('');

  try{refreshFocusedGraph();}catch(error){graph.status(`Graph unavailable: ${error.message}. The verified report is still valid.`);}

  renderDemo();updateRunButtons();

}

async function runInvestigation(){

  if(state.running||state.loading||!state.diff)return;

  const key=state.key;const mode=$('execution-mode').value;state.running=true;state.current=null;updateRunButtons();$('run-text').textContent='Investigating…';$('execution-status').textContent='Running · waiting for verified execution';

  $('report-root').innerHTML=renderVerificationLoader();

  $('tool-traces').innerHTML='<p>Waiting for the current execution report…</p>';$('reproduction-command').textContent='Waiting for current execution evidence.';$('agent-terminal').textContent=`Requested investigation: ${key}\nRequested strategy: ${mode}\nWaiting for the server report…`;$('scenario-specs').innerHTML='';$('execution-annotation').textContent='';refreshFocusedGraph();

  const started=Date.now();const interval=setInterval(()=>{const el=$('elapsed-time');const seconds=Math.floor((Date.now()-started)/1000);if(el)el.textContent=`Elapsed: ${seconds} ${seconds===1?'second':'seconds'}`;},1000);

  try{

    const report=await api('/api/v1/git/investigations',{method:'POST',body:JSON.stringify({change:key,mode})});

    state.reports=[report,...state.reports.filter(r=>r.id!==report.id)];

    // Commit the verified report before optional visualization refreshes.

    showReport(report);

    try{state.evidence=await api(`/api/v1/graph/evidence/${key}`);refreshFocusedGraph();}catch(error){graph.status(`Graph refresh unavailable: ${error.message}. Verified report retained.`);}

    try{state.snapshot=await api('/api/v1/graph');resetExplorer();}catch(error){$('explorer-footnote').textContent=`Explorer refresh unavailable: ${error.message}`;}

    renderHistory();toast(`Investigation ${report.status||'finished'}: ${report.verdict.replaceAll('_',' ')}`);

  }catch(error){

    const report={id:'Unavailable',change_id:`GIT-${key.toUpperCase()}`,verdict:'investigation_error',status:error.message.toLowerCase().includes('provider')?'provider_unavailable':'error',mode,steps:[],cases:[],recommendation:error.message};

    showReport(report);$('agent-terminal').textContent+=`\nRequest error: ${error.message}`;toast(error.message,true);

  }finally{clearInterval(interval);state.running=false;$('run-text').textContent='Re-run Investigation';updateRunButtons();}

}

function resetExplorer(){const ids=state.snapshot.nodes.filter(n=>n.kind==='Service').map(n=>n.id);explorer.setData(state.snapshot,{ids});$('explorer-footnote').textContent=`${state.snapshot.nodes.length} persisted entities available in the loaded snapshot. Only ${ids.length} services are shown initially. Neighborhoods expand by up to 12 entities at a time.`;}

function renderDemo(){

  const report=state.reports.find(r=>reportKey(r)===state.demo);const root=$('evidence-display-card');

  document.querySelectorAll('[data-evidence]').forEach(btn=>{btn.classList.toggle('active',btn.dataset.evidence===state.demo);btn.setAttribute('aria-pressed',String(btn.dataset.evidence===state.demo));});

  if(!report?.cases?.length){root.innerHTML=`<h3>${esc(state.demo[0].toUpperCase()+state.demo.slice(1))} verification</h3><p>No saved executed evidence for this workflow is currently loaded. Open the investigation and run it to verify both revisions.</p><span class="demo-source">Controlled demo · result not available</span>`;return;}

  const c=report.cases[0];root.innerHTML=`<div class="demo-proof-header"><div><span class="demo-source">VERIFIED DEMO · ${esc(modeLabel(report))}</span><h3>${esc(report.title)}</h3></div><span class="report-state ${report.verdict==='reproduced'?'failure':'pass'}">${esc(report.verdict.replaceAll('_',' ').toUpperCase())}</span></div><div class="revision-comparison">${['baseline','candidate'].map(version=>`<article class="revision-result ${c[version].outcome}"><div class="revision-result-top"><h3>${version==='baseline'?'Original code':'Modified code'}</h3><span class="outcome-label">${esc(c[version].outcome.toUpperCase())}</span></div><p>${esc(c[version].observed)}</p><footer><code>${esc(report.revisions?.[version]?.slice(0,12)||'No revision identifier')}</code><span>${esc(c[version].duration_ms)}ms</span></footer></article>`).join('')}</div><p class="demo-source">Evidence: ${esc(c.invariant_id)} · saved report ${esc(report.id)} · ${esc(report.generated_at)}</p>`;

}

function renderHistory(){

  const query=$('history-filter-input').value.toLowerCase();const supported=[...$('change-select').options].map(option=>option.value);const reports=state.reports.filter(r=>supported.includes(reportKey(r))&&`${r.id} ${r.title}`.toLowerCase().includes(query));

  $('audit-table-body').innerHTML=reports.map(r=>`<tr><td><code>${esc(r.id)}</code></td><td>${esc(r.title||r.change_id)}</td><td>${esc(r.verdict.replaceAll('_',' '))}</td><td>${esc(modeLabel(r))}</td><td>${r.cases?.length||0}</td><td>${(r.steps||[]).reduce((sum,s)=>sum+(s.duration_ms||0),0)}ms</td><td>${esc(new Date(r.generated_at).toLocaleString())}</td><td><button class="copy-cmd-btn" data-report="${esc(r.id)}">Open Investigation</button></td></tr>`).join('')||'<tr><td colspan="8">No saved investigations match this search.</td></tr>';

}

async function copy(text){try{await navigator.clipboard.writeText(text);toast('Copied to clipboard.');}catch{toast('Copy unavailable. Select the visible command text to copy it.',true);}}

function handleAction(action){

  if(action==='run')runInvestigation();

  if(action==='evidence'){$('verification-evidence')?.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});}

  if(action==='diff')openEvidence('diff');

  if(action==='technical'){setDisplayMode('technical');openEvidence('graph');}

  if(action==='copy'){const c=state.current?.cases?.[0];if(c)copy(commandFor(state.current,c));else toast('No executable scenario is available for this report.',true);}

}

async function refresh(){

  try{

    await api('/api/v1/health/ready');$('graph-status-dot').className='indicator-dot online';

    const results=await Promise.allSettled([api('/api/v1/graph'),api('/api/v1/investigations'),api('/api/v1/meta')]);

    if(results[0].status==='fulfilled'){state.snapshot=results[0].value;resetExplorer();}else $('explorer-footnote').textContent=`Knowledge graph unavailable: ${results[0].reason.message}`;

    if(results[1].status==='fulfilled')state.reports=results[1].value;else toast(`Saved reports unavailable: ${results[1].reason.message}`,true);

    const meta=results[2].status==='fulfilled'?results[2].value:null;$('model-status-label').textContent=meta?.model_configured?'Model configured':'Deterministic available';

    renderHistory();renderDemo();await loadSelected();

  }catch(error){$('graph-status-dot').className='indicator-dot offline';$('execution-status').textContent='Backend unavailable';renderEmpty(`Backend connection failed: ${error.message}`);$('evidence-display-card').textContent=`Verified demo unavailable: ${error.message}`;toast(error.message,true);}

}

window.addEventListener('DOMContentLoaded',()=>{
  hero=new HeroAgentScene('hero-network-canvas');



  project=setupProjectUnderstanding({api,root:$('project-understanding'),onError:toast});

  const onEvidence=n=>{setView('investigation');openEvidence(n.kind==='Change'||n.kind==='Symbol'?'diff':n.kind==='Investigation'?'tools':'reproduce');};

  graph=new EvidenceGraph($('evidence-graph'),{onEvidence});explorer=new EvidenceGraph($('knowledge-graph'),{explorer:true,onEvidence:async n=>{if(state.running){toast('Wait for the active investigation to finish.');return;}if(n.kind==='Investigation'){try{const report=await api(`/api/v1/investigations/${encodeURIComponent(n.id)}`);const key=reportKey(report);if([...$('change-select').options].some(o=>o.value===key)){$('change-select').value=key;await loadSelected(report);setView('investigation');}else{setView('history');$('history-filter-input').value=n.id;renderHistory();}}catch(error){toast(error.message,true);}}else{setView('investigation');openEvidence('graph');const node=state.evidence.nodes.find(x=>x.id===n.id);if(node)graph.inspectNode(node.id);else toast('This entity belongs to the broader system context. Use its explorer relationships to inspect it.');}}});

  document.querySelectorAll('#view-nav [data-view]').forEach(btn=>btn.onclick=()=>setView(btn.dataset.view));

  $('nav-investigation').onclick=()=>setView('workspace/overview');
  const reposNav=$('nav-saas');reposNav.textContent='Repositories';reposNav.onclick=()=>setView('workspace/repositories');
  ['btn-hero-explore','btn-header-cta','btn-final-cta'].forEach(id=>$(id).onclick=()=>setView('investigation'));

  $('btn-hero-how').onclick=()=>$('section-how-it-works').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});

  $('public-how-link').onclick=event=>{event.preventDefault();setView('landing');requestAnimationFrame(()=>$('section-how-it-works').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'}));};
  $('brand-home-trigger').onclick=()=>setView('landing');$('brand-home-trigger').onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();setView('landing');}};

  $('run-button').onclick=runInvestigation;$('terminal-run').onclick=runInvestigation;$('change-select').onchange=()=>loadSelected();

  $('simple-mode').onclick=()=>setDisplayMode('simple');$('technical-mode').onclick=()=>setDisplayMode('technical');

  $('graph-disclosure').addEventListener('toggle',()=>{if($('graph-disclosure').open)requestAnimationFrame(()=>{graph.cy?.resize();graph.fit();});});

  $('report-root').onclick=e=>{const action=e.target.closest('[data-action]')?.dataset.action;if(action)handleAction(action);};

  $('explorer-home').onclick=resetExplorer;

  document.querySelectorAll('[data-evidence]').forEach(btn=>btn.onclick=()=>{state.demo=btn.dataset.evidence;renderDemo();});

  $('open-demo-investigation').onclick=async()=>{if(state.running){toast('Wait for the current investigation to finish.');return;}$('change-select').value=state.demo;setView('investigation');await loadSelected();window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});};

  $('copy-reproduction').onclick=()=>handleAction('copy');$('terminal-copy').onclick=()=>copy($('agent-terminal').textContent);

  $('history-filter-input').oninput=renderHistory;$('history-refresh-btn').onclick=async()=>{try{state.reports=await api('/api/v1/investigations');renderHistory();renderDemo();}catch(error){toast(error.message,true);}};

  $('audit-table-body').onclick=async e=>{const id=e.target.closest('[data-report]')?.dataset.report;if(!id)return;if(state.running){toast('Wait for the active investigation to finish.');return;}const report=state.reports.find(r=>r.id===id);const key=reportKey(report);if(![...$('change-select').options].some(o=>o.value===key)){toast('This historical legacy report is not a supported Git selection. Its saved payload remains available through the API.',true);return;}$('change-select').value=key;setView('investigation');await loadSelected(report);window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});};

  $('bearer-token-input').value=state.token;$('btn-save-token').onclick=()=>{state.token=$('bearer-token-input').value.trim();sessionStorage.setItem('fz_token',state.token);refresh();};

  $('btn-test-provider').onclick=async()=>{const btn=$('btn-test-provider');btn.disabled=true;$('provider-probe-output').textContent='Verifying provider…';try{const result=await api('/api/v1/verify_provider',{method:'POST'});$('provider-probe-output').textContent=JSON.stringify(result,null,2);}catch(error){$('provider-probe-output').textContent=`Provider unavailable: ${error.message}`;}finally{btn.disabled=false;}};

  $('open-explainer-btn').onclick=()=>$('explainer-modal').showModal();$('close-explainer-btn').onclick=()=>$('explainer-modal').close();

  const flyToggle = $('flymemory-toggle');

  if(flyToggle){

    flyToggle.checked = localStorage.getItem('fz_flymemory_enabled') === 'true';

    flyToggle.onchange = () => {

      localStorage.setItem('fz_flymemory_enabled', flyToggle.checked ? 'true' : 'false');

      toast(`Bio-inspired memory retrieval ${flyToggle.checked ? 'enabled' : 'disabled'}.`);

    };

  }

  window.addEventListener('hashchange',()=>setView(location.hash.slice(1)));setView(location.hash.slice(1)||(location.pathname==='/workspace'?'workspace/overview':'landing'));renderEmpty();if(state.view!=='workspace')refresh();

});

function renderFlyMemory(memories){

  const root=$('flymemory-list');

  if(!root)return;

  if(!memories||!memories.length){root.innerHTML='<div class="empty-memory-state">No similar verified incidents found for this change topology.</div>';return;}

  root.innerHTML=memories.map(m=>`

    <div class="flymemory-card">

      <div class="flymemory-card-header">

        <span class="flymemory-card-title">${esc(m.title)}</span>

        <div class="flymemory-scores">

          <span class="score-pill">${Math.round((m.similarity_score||0)*100)}% pattern overlap</span>

          ${m.graph_verified?'<span class="score-pill verified">FalkorDB Verified</span>':''}

        </div>

      </div>

      <p class="flymemory-explanation">${esc(m.relevance_explanation||'Historical incident matched via Fly-LSH sparse hashing.')}</p>

      ${m.historical_test_strategy?`<p class="flymemory-explanation"><strong>Previously effective test:</strong> <code>${esc(m.historical_test_strategy)}</code></p>`:''}

      <div class="flymemory-caveat">${esc(m.caveat||'Similarity hypothesis only; does not prove current regression without independent execution.')}</div>

    </div>

  `).join('');

}

async function loadFlyMemoryForCurrentChange(){

  if(!state.diff)return;

  try{

    const res=await api('/api/v1/flymemory/search',{

      method:'POST',

      body:JSON.stringify({

        symbols:state.diff.modified_symbols||[],

        services:(state.evidence?.nodes||[]).filter(n=>n.kind==='Service').map(n=>n.id),

        invariants:(state.evidence?.nodes||[]).filter(n=>n.kind==='Invariant').map(n=>n.id),

        diff_text:state.diff.diff||'',

        top_k:5

      })

    });

    renderFlyMemory(res);

  }catch{renderFlyMemory([]);}

}

async function loadSaasView(){

  try{

    const me = await api('/api/v1/auth/me').catch(()=>null);

    if(!me?.user){ location.assign('/login?next=%2Fworkspace');return; }

    if(me && me.user){

      if($('saas-org-name')) $('saas-org-name').textContent = me.current_organization?.name || 'Default Organization';

      if($('saas-org-slug')) $('saas-org-slug').textContent = me.current_organization?.slug || 'default-org';

      if($('saas-billing-tier')) $('saas-billing-tier').textContent = (me.current_organization?.billing_tier || 'ENTERPRISE').toUpperCase();

      if($('saas-user-email')) $('saas-user-email').textContent = me.user.email || 'developer@faultlinezero.local';

      if($('saas-user-role')) $('saas-user-role').textContent = (me.current_organization?.role || 'OWNER').toUpperCase();

      if($('tenant-status-label')) $('tenant-status-label').textContent = me.current_organization?.name || 'Default Org';

      state.csrfToken = me.csrf_token;

      if(state.view==='saas') $('view-saas').style.visibility='visible';

    }

    const installations = await api('/api/v1/github/installations').catch(()=>[]);

    if(installations && installations.length){

      if($('saas-install-id')) $('saas-install-id').textContent = `Install #${installations[0].id} (${installations[0].account_login})`;

      if($('saas-github-status')) {

        $('saas-github-status').textContent = 'CONNECTED';

        $('saas-github-status').className = 'badge-status-safe';

      }

    } else {

      if($('saas-install-id')) $('saas-install-id').textContent = 'Ready to Install';

      if($('saas-github-status')) $('saas-github-status').textContent = 'READY';

    }

    const repos = await api('/api/v1/github/repositories').catch(()=>[]);

    renderSaasRepos(repos);

  }catch(err){

    toast(`SaaS data unavailable: ${err.message}`, true);

  }

}

function renderSaasRepos(repos){

  const tbody = $('saas-repos-tbody');

  const count = $('saas-repo-count');

  if(!tbody) return;

  if(count) count.textContent = `${repos?.length || 0} codebases monitored`;

  if(!repos || !repos.length){

    tbody.innerHTML = '<tr><td colspan="5" style="padding:18px;text-align:center;color:#94a3b8;">No external repositories synced yet. Connect your GitHub App or click Install below.</td></tr>';

    return;

  }

  tbody.innerHTML = repos.map(r=>{

    const latest = r.latest_investigation;

    let verdictBadge = '<span style="color:#94a3b8;">No runs</span>';

    if(latest){

      const isFail = latest.verdict === 'REPRODUCED';

      const isClean = latest.verdict === 'CLEAN';

      const color = isFail ? '#f87171' : (isClean ? '#4ade80' : '#facc15');

      verdictBadge = `<span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600;background:${color}22;color:${color};border:1px solid ${color}44;">${esc(latest.verdict)} (${esc(latest.confidence||'HIGH')})</span>`;

    }

    return `

      <tr style="border-bottom:1px solid #ffffff0a;">

        <td style="padding:12px 14px;font-weight:600;color:#e2e8f0;">${esc(r.full_name)}</td>

        <td style="padding:12px 14px;"><span style="font-size:10px;padding:2px 6px;border-radius:3px;background:#1e293b;color:#94a3b8;">${r.is_private ? 'Private' : 'Public'}</span></td>

        <td style="padding:12px 14px;"><code>${esc(r.default_branch)}</code></td>

        <td style="padding:12px 14px;color:#38bdf8;">${r.open_prs_count || 0} active</td>

        <td style="padding:12px 14px;">${verdictBadge}</td>

      </tr>

    `;

  }).join('');

}

// Attach SaaS button handlers once DOM is ready

document.addEventListener('DOMContentLoaded', ()=>{

  const installBtn = $('btn-install-github-app');

  if(installBtn){

    installBtn.onclick = async ()=>{

      try{

        const data = await api('/api/v1/github/install/url');

        if(data && data.url) window.open(data.url, '_blank');

      }catch(err){

        toast(`Could not generate installation link: ${err.message}`, true);

      }

    };

  }

  const resyncBtn = $('btn-resync-repos');

  if(resyncBtn){

    resyncBtn.onclick = async ()=>{

      resyncBtn.disabled = true;

      try{

        toast('Syncing repositories with GitHub…');

        await loadSaasView();

        toast('Repositories synced successfully.');

      }catch(err){

        toast(`Sync failed: ${err.message}`, true);

      }finally{

        resyncBtn.disabled = false;

      }

    };

  }

  const logoutBtn = $('btn-saas-logout');

  if(logoutBtn){

    logoutBtn.onclick = async ()=>{

      try{

        await api('/api/v1/auth/logout', {method:'POST'});

        toast('Signed out of tenant session.');

        state.csrfToken=null;

        sessionStorage.removeItem('fz_token');

        location.replace('/login');

      }catch(err){

        toast(`Logout failed: ${err.message}`, true);

      }

    };

  }

});


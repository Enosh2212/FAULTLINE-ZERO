import {esc, kindName} from './evidence_graph.js';
export const reportKey = report => (report?.change_id || '').replace(/^git[:-]/i,'').toLowerCase();
export function commandFor(report, c, version='candidate') {
  const spec=(report.discovered_scenarios||[]).find(s=>s.id===c.testcase_id);
  const arg=spec?`--spec '${JSON.stringify(spec).replaceAll("'","''")}'`:c.testcase_id;
  return `python -m faultline.revision_runner ${reportKey(report)} ${version} ${arg}`;
}
export function modeLabel(report) {
  const text=`${report?.execution_mode||''} ${report?.mode||''} ${report?.status||''}`.toLowerCase();
  if(text.includes('provider_unavailable')||text.includes('provider unavailable'))return 'Provider unavailable';
  if(text.includes('fallback')||text.includes('deterministic'))return 'Deterministic fallback';
  if(text.includes('model'))return 'Model-driven';
  return 'Execution mode unavailable';
}
export function finding(report, context={}) {
  const c=report?.cases?.find(c=>c.baseline?.outcome==='pass'&&c.candidate?.outcome==='fail')||report?.cases?.[0];
  const nodes=context.nodes||[];const label=id=>nodes.find(n=>n.id===id)?.label||id;
  const service=c?label(c.affected_service):nodes.filter(n=>n.kind==='Service').map(n=>n.label).join(', ');
  const invariant=c?label(c.invariant_id):nodes.filter(n=>n.kind==='Invariant').map(n=>n.label).join('; ');
  const reproduced=report?.verdict==='reproduced'&&report.cases.some(c=>c.baseline?.outcome==='pass'&&c.candidate?.outcome==='fail');
  const error=report?.verdict==='investigation_error'||report?.status==='error'||report?.status==='provider_unavailable';
  const status=reproduced?'REGRESSION REPRODUCED':error?'VERIFICATION ERROR':report?.verdict==='not_reproduced'?'NO REGRESSION REPRODUCED':'INCONCLUSIVE';
  const title=reproduced?`Regression detected${service?' in '+service.toLowerCase():''}`:error?'Verification could not finish':report?.verdict==='not_reproduced'?'Selected verification passed':'This change needs more verification';
  const next=reproduced?'Needs fix before merge':error?'Retry verification':report?.verdict==='not_reproduced'?'Continue code review':'Add verification coverage';
  const recommendation=reproduced?`Review ${context.diff?.modified_symbols?.join(', ')||'the changed code'} and restore the ${invariant||'affected business rule'} guarantee before merging. Then re-run verification.`:error?'Verification could not finish. Inspect the error and retry when the unavailable dependency has recovered.':report?.verdict==='not_reproduced'?'Selected verification scenarios passed. Continue normal code review and CI checks. This does not rule out all possible regressions.':'No relevant validated verification scenario completed. Add coverage for the affected business rule before relying on this check.';
  const summary=c?`Original code: ${c.baseline.observed} Modified code: ${c.candidate.observed}`:error?(context.error||report?.recommendation||'The investigation did not produce valid execution evidence.'):'No executable verification was selected for the connected business rule.';
  return {c,service,invariant,reproduced,error,status,title,next,recommendation,summary,tone:reproduced||error?'failure':report?.verdict==='not_reproduced'?'pass':'neutral'};
}
// A reusable local PR-check presentation. It creates no remote check or branch action.
export function prCheck(report,context={},compact=false) {
  const f=finding(report,context);
  return `<article class="pr-check ${f.tone} ${compact?'compact-check':''}" aria-label="Local PR check presentation"><div class="pr-check-top"><span class="check-mark" aria-hidden="true">${f.reproduced||f.error?'!':f.tone==='pass'?'✓':'·'}</span><div><strong>FAULTLINE ZERO <span>/ Regression Verification</span></strong><small>Local PR-check preview · advisory only · not published to GitHub</small></div><span class="report-state ${f.tone}">${esc(f.status)}</span></div><div class="check-body"><span class="section-kicker">${esc(f.next)}</span><h1>${esc(f.title)}</h1><p class="finding-summary">${esc(f.summary)}</p><div class="check-actions"><button class="hero-primary-btn" data-action="evidence">Review Evidence</button><button class="hero-secondary-btn" data-action="diff">View Code Change</button><button class="text-action" data-action="run">Run Again</button><button class="text-action" data-action="copy">Copy Reproduction Command</button></div></div></article>`;
}
export function renderReport(report,context) {
  const f=finding(report,context);const symbols=context.diff?.modified_symbols||[];
  const stages=[
    {title:'Read the code change',tools:['get_git_diff'],text:'Identified modified functions and the actual Git differences.'},
    {title:'Checked connected components',tools:['trace_impact_graph','get_evidence_subgraph'],text:'Used FalkorDB relationships to find connected services and business rules.'},
    {title:'Selected verification',tools:['find_relevant_tests','find_uncovered_invariants','generate_counterexample','synthesize_counterexample'],text:'Reviewed available coverage and selected tests or constructed an approved scenario.'},
    {title:'Compared both revisions',tools:['compare_revisions','execute_counterexample'],text:'Executed the verification against the original and modified code.'},
    {title:'Recorded the outcome',tools:['finalize_investigation'],text:'Finalized the evidence-backed result for this investigation.'}
  ];
  if (!report.cases?.length) { stages[2].title='Checked verification coverage'; stages[2].text='Checked the available coverage. No approved executable verification was selected.'; }
  if ((report.discovered_scenarios||[]).length) stages[2].text='Constructed a constrained, approved counterexample for the connected business rule.';
  const timeline=stages.map(stage=>({...stage,steps:(report.steps||[]).filter(s=>stage.tools.includes(s.tool))})).filter(stage=>stage.steps.length);
  const cases=report.cases||[];
  return `${prCheck(report,context)}<div class="report-body"><section class="why-flagged"><div class="section-intro"><span class="section-kicker">CHANGE CONTEXT</span><h2>Why this change was ${f.reproduced?'flagged':'investigated'}.</h2></div><dl class="finding-facts"><div><dt>Changed function</dt><dd>${symbols.length?symbols.map(s=>`<code>${esc(s)}</code>`).join(', '):'Git symbols unavailable'}</dd></div><div><dt>Affected service</dt><dd>${esc(f.service||'No linked service found')}</dd></div><div><dt>Business rule</dt><dd>${esc(f.invariant||'No linked business rule found')}</dd></div><div><dt>Observed behavior</dt><dd>${esc(f.c?.candidate?.observed||'No completed verification output.')}</dd></div></dl></section><section id="verification-evidence" class="verification-section"><div class="section-intro"><span class="section-kicker">EXECUTABLE EVIDENCE</span><h2>Same scenario. Both revisions.</h2><p>Observed outputs from controlled execution, independent of the model's interpretation.</p></div>${cases.length?cases.map(c=>`<div class="case-label">${esc(c.testcase_id)} <span>Business rule: ${esc(c.invariant_id)}</span></div><div class="revision-comparison">${['baseline','candidate'].map(version=>`<article class="revision-result ${c[version].outcome}"><div class="revision-result-top"><h3>${version==='baseline'?'Original code':'Modified code'}</h3><span class="outcome-label">${esc(c[version].outcome.toUpperCase())}</span></div><p>${esc(c[version].observed)}</p><footer><code>${esc(report.revisions?.[version]?.slice(0,12)||'Revision unavailable')}</code><span>${esc(c[version].duration_ms)}ms</span></footer></article>`).join('')}</div>`).join(''):'<div class="no-verification">No completed execution evidence is available for this report. No passing or failing result has been inferred.</div>'}</section><section class="next-action"><span class="section-kicker">RECOMMENDED NEXT ACTION</span><h2>${esc(f.next)}</h2><p>${esc(f.recommendation)}</p><small>Advisory for this controlled demo. No remote merge gate or GitHub check has been created.</small></section><section class="investigated-section"><div class="section-intro"><span class="section-kicker">ACTUAL INVESTIGATION ACTIVITY</span><h2>What FAULTLINE investigated.</h2></div><ol class="plain-timeline">${timeline.map((stage,i)=>`<li><span class="timeline-number">${i+1}</span><div><h3>${esc(stage.title)}${stage.steps.some(s=>s.status==='error')?' · encountered an error':''}</h3><p>${esc(stage.text)}</p><details><summary>Technical details</summary>${stage.steps.map(s=>`<p><code>${esc(s.tool)}</code> · ${esc(s.status)} · ${esc(s.duration_ms)}ms</p>`).join('')}</details></div></li>`).join('')||'<li>No completed tool actions were returned.</li>'}</ol><button class="explore-technical" data-action="technical">Explore Technical Evidence <span aria-hidden="true">↗</span></button></section></div>`;
}
export function renderTraces(report) {
  return (report.steps||[]).map(s=>`<details class="tool-trace"><summary><span>${esc(s.tool.replaceAll('_',' '))}</span><span>${esc(s.status)} · ${esc(s.duration_ms)}ms</span></summary><h4>Arguments</h4><pre>${esc(JSON.stringify(s.arguments||{},null,2))}</pre><h4>Observed tool result</h4><pre>${esc(s.result)}</pre></details>`).join('')||'<p>No tool calls have been recorded.</p>';
}
export function terminalLog(report) {
  const lines=['FAULTLINE ZERO / INVESTIGATION TERMINAL',`Report: ${report.id}`,`Mode: ${modeLabel(report)}`,`Change: ${reportKey(report)}`,''];
  for(const s of report.steps||[])lines.push(`[${s.status}] ${s.tool} · ${s.duration_ms}ms`,s.result,'');
  lines.push('REPRODUCIBLE COMMANDS / RECORDED EXECUTION OBSERVATIONS','');
  for(const c of report.cases||[])for(const version of ['baseline','candidate'])lines.push('$ '+commandFor(report,c,version),`Revision: ${report.revisions?.[version]||'unavailable'}`,JSON.stringify(c[version]),'');
  lines.push(`VERDICT: ${report.verdict}`,report.recommendation||'');return lines.join('\n');
}

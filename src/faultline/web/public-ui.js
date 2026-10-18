import {observeSession, verifySession, logout} from './session-state.js';
const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const auth = document.getElementById('public-auth');
observeSession(({status,session}) => {
  if(!auth) return;
  auth.dataset.state=status;
  if(status==='loading') auth.innerHTML='<span class="public-session-status" role="status">Checking session…</span>';
  else if(status==='authenticated') {
    const name=session.user.display_name || session.user.email || 'Account';
    auth.innerHTML=`<a class="public-dashboard" href="/workspace">Open Dashboard <span aria-hidden="true">↗</span></a><details class="public-account"><summary aria-label="Account menu for ${esc(name)}"><span class="public-avatar">${esc(name[0].toUpperCase())}</span></summary><div><strong>${esc(name)}</strong><a href="/workspace">Workspace</a><a href="/workspace#workspace/settings">Settings</a><button type="button" data-public-logout>Log out</button></div></details>`;
    auth.querySelector('[data-public-logout]').onclick=async event=>{event.target.disabled=true;try{await logout();}catch(error){event.target.disabled=false;auth.querySelector('strong').textContent=error.message;}};
  } else if(status==='signed-out') auth.innerHTML='<a class="public-sign-in" id="landing-sign-in" href="/login">Sign In</a><a class="public-get-started" id="landing-create-account" href="/register">Get Started <span aria-hidden="true">↗</span></a>';
  else {auth.innerHTML='<button type="button" class="public-session-status" id="public-retry-session">Session unavailable · Retry</button>';auth.querySelector('button').onclick=()=>verifySession({fresh:true}).catch(()=>{});}
});
document.addEventListener('click', event=>{
  const menu=document.querySelector('.public-account');if(menu&&!menu.contains(event.target))menu.open=false;
});
document.addEventListener('keydown', event=>{if(event.key==='Escape'){const menu=document.querySelector('.public-account');if(menu?.open){menu.open=false;menu.querySelector('summary').focus();}}});
verifySession({fresh:true}).catch(()=>{});

const steps = [
  ['Connect GitHub','Authorize the App for repositories you administer.','Your Firebase sign-in secures your workspace. A separate GitHub App authorization grants access to selected repositories.','M9 19c-5 1-5-2-7-2 M9 22v-4c-6-1-7-11-3-13V2l5 2h4l5-2v3c4 2 3 12-3 13v4'],
  ['Index Repository','Map supported Python source into a snapshot.','Read-only parsing maps files, symbols and declared relationships at a specific commit. Dynamic dependencies and unsupported languages may remain unresolved.','M4 3h16v18H4z M8 7h8 M8 12h8 M8 17h4'],
  ['PR Detected','Receive an authorized repository’s pull-request event.','A verified GitHub webhook records the PR and queues analysis. New commits supersede older pending work.','M6 5v14 M6 5a2 2 0 1 0 .01 0 M6 19a2 2 0 1 0 .01 0 M15 5h3v12 M15 14l3 3 3-3'],
  ['Trace Impact','Follow recorded dependencies from the changed symbols.','Commit-specific static graph relationships identify potential callers, related tests and verified invariant references. A possible path is not runtime proof.','M4 5l8 7 8-7 M12 12v8 M2 3h4v4H2z M10 10h4v4h-4z M18 3h4v4h-4z'],
  ['Verify Evidence','Distinguish established facts from unverified behavior.','External repositories currently receive static analysis, not arbitrary test execution. Without approved execution evidence, runtime regression verification remains INCONCLUSIVE. The controlled demo supports constrained execution.','M12 2l8 4v6c0 5-8 10-8 10S4 17 4 12V6z M8 12l3 3 5-6'],
  ['Publish Check','Report the recorded verdict and its limits to GitHub.','When configured and authorized, the GitHub App publishes a PR Check. An inconclusive result is neutral and never a claim that the change is safe.','M4 3h16v18H4z M8 12l3 3 5-6']
];
const workflow=document.getElementById('faultline-workflow');
if(workflow) {
  workflow.innerHTML=steps.map(([title,sentence,explanation,path],i)=>`<button type="button" class="workflow-step${i===0?' selected':''}" aria-expanded="${i===0}" aria-controls="workflow-explanation" data-step="${i}"><span class="workflow-step-top"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${path}"/></svg><small>0${i+1}</small></span><strong>${title}</strong><span>${sentence}</span></button>`).join('');
  const explanation=document.getElementById('workflow-explanation');
  function select(index){workflow.querySelectorAll('button').forEach((button,i)=>{button.classList.toggle('selected',i===index);button.setAttribute('aria-expanded',String(i===index));});explanation.innerHTML=`<h3>${steps[index][0]}</h3><p>${steps[index][2]}</p>`;}
  workflow.onclick=event=>{const button=event.target.closest('[data-step]');if(button)select(Number(button.dataset.step));};select(0);
}

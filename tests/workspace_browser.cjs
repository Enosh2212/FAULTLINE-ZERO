/* Explicit browser response fixtures. Never imported or served by the application. */
const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const out='output/workspace-verification';fs.mkdirSync(out,{recursive:true});
const origin='http://localhost:8000';
const repo={id:'fixture-repo',full_name:'fixture-labs/risklens',default_branch:'main',is_private:true,is_active:true,account:'fixture-labs',installation_id:77,indexing_status:'indexed',indexed_commit_sha:'a'.repeat(40),indexed_at:'2026-10-18T03:00:00Z',languages:['Python'],index_summary:{indexed_files:18,languages:['Python']},monitoring:'Ready for webhooks'};
const inv={id:'fixture-inv',repository_id:repo.id,repository:repo.full_name,pr_id:'fixture-pr',pr_number:1,title:'Improve payment retry handling',commit_sha:'a'.repeat(40),base_sha:'b'.repeat(40),head_branch:'fix/retry',status:'completed',verdict:'INCONCLUSIVE',confidence:'LOW',summary:'Python source was parsed, but no applicable verified business invariants were found for this change.',created_at:'2026-10-18T03:01:00Z',completed_at:'2026-10-18T03:02:00Z',check_run_id:null,superseded:false};
const graph={repository:repo.full_name,revision:repo.indexed_commit_sha,coverage:'Static relationships from an explicit test fixture.',nodes:[{id:'node-a',label:'handle_retry',type:'Function',path:'src/payment.py',line:12},{id:'node-b',label:'capture',type:'Function',path:'src/payment.py',line:32},{id:'node-c',label:'test_retry',type:'Test',path:'tests/test_payment.py',line:4}],edges:[{source:'node-a',target:'node-b',label:'CALLS'},{source:'node-c',target:'node-a',label:'TESTS'}]};
const capabilities={github_app_configured:false,github_authorization_configured:false,webhook_configured:false,public_installation_verified:false,analysis:'Read-only Python AST and dependency analysis; external repository code is never executed.',limitations:'Runtime behavior requires verified invariant coverage.'};
const detail={...inv,evidence:{changed_components:[{name:'handle_retry',path:'src/payment.py',start:12,status:'MODIFIED'}],impacted_callers:[{caller_name:'capture',caller_path:'src/payment.py',caller_line:32,target_name:'handle_retry',depth:1}],covering_tests:[],protecting_invariants:[]},graph,scope:'Static source and graph analysis. No arbitrary external repository code was executed.',unverified_scope:'Runtime behavior is unverified. CLEAN applies only to reported scope.',activity:[{label:'Investigation recorded',at:inv.created_at},{label:'Analysis completed',at:inv.completed_at}],check_note:'No GitHub Check ID recorded.'};
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[],unexpected=[],checks=[];let empty=true,unavailable=false;
 page.on('pageerror',e=>errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('Failed to load resource'))errors.push(m.text());});
 await page.route('**/assets/workspace*',route=>{const name=new URL(route.request().url()).pathname.split('/').at(-1);return route.fulfill({path:'src/faultline/web/'+name});});
 await page.route('**/api/v1/**',async route=>{
   const path=new URL(route.request().url()).pathname;
   let data;
   if(path==='/api/v1/auth/me')data={user:{id:'fixture-user',email:'fixture@example.invalid',display_name:'Fixture workspace'},organizations:[{id:'fixture-org',name:'Engineering / Test fixture',role:'owner'}],current_organization:{id:'fixture-org'},csrf_token:'fixture-csrf'};
   else if(path==='/api/v1/workspace/overview'){
     if(unavailable){await route.fulfill({status:503,json:{detail:'Fixture service unavailable. Retry after restoring access.'}});return;}
     data={workspace:{id:'fixture-org',name:'Engineering / Test fixture',role:'owner'},metrics:{repositories:empty?0:1,prs_analyzed:empty?0:1,findings:0,inconclusive:empty?0:1},repositories:empty?[]:[repo],recent_investigations:empty?[]:[inv],active_jobs:0,capabilities};
   }else if(path==='/api/v1/workspace/pull-requests')data={items:empty?[]:[{id:'fixture-pr',repository_id:repo.id,repository:repo.full_name,number:1,title:inv.title,state:'open',head_sha:inv.commit_sha,head_branch:inv.head_branch,updated_at:inv.created_at,investigation:inv}]};
   else if(path==='/api/v1/workspace/investigations')data={items:empty?[]:[inv]};
   else if(path==='/api/v1/workspace/investigations/fixture-inv')data=detail;
   else if(path==='/api/v1/workspace/activity')data={items:empty?[]:[{id:'fixture-job',type:'index_repository',repository_id:repo.id,repository:repo.full_name,status:'failed',attempts:1,max_attempts:3,created_at:inv.created_at,updated_at:inv.completed_at,error:'The last attempt failed. Check access and service configuration, then retry.',retryable:true}]};
   else if(path==='/api/v1/workspace/repositories/fixture-repo/graph')data=graph;
   else if(path==='/api/v1/workspace/activity/fixture-job/retry')data={status:'queued'};
   else if(path==='/api/v1/auth/logout')data={status:'logged_out'};
   else{unexpected.push(path);await route.fulfill({status:404,json:{detail:'No fixture for this request'}});return;}
   await route.fulfill({status:200,json:data});
 });
 await page.goto(origin+'/?test=workspace#workspace/overview');
 await page.getByRole('heading',{name:'Your code changes deserve deeper investigation.'}).waitFor();
 assert.equal(await page.locator('#workspace-app').isVisible(),true);
 assert.equal(await page.locator('#main-header').isVisible(),false);
 checks.push('Empty authenticated workspace shows onboarding, not the commerce demo');
 for(const width of [1440,1024,768,390]){
   await page.setViewportSize({width,height:1000});
   await page.screenshot({path:`${out}/fixture-onboarding-${width}.png`,fullPage:true});
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);assert.equal(overflow,false,`Overflow at ${width}`);
   if(width===390){await page.getByRole('button',{name:'Open navigation'}).click();await page.getByRole('link',{name:'Repositories',exact:true}).click();await page.getByRole('heading',{name:'Repositories',exact:true}).waitFor();assert.equal(await page.locator('.ws-drawer-shade').isVisible(),false);await page.goto(origin+'/?test=workspace#workspace/overview');await page.getByRole('heading',{name:'Your workspace',exact:true}).waitFor();}
 }
 checks.push('1440 / 1024 / 768 / 390 responsive onboarding, mobile drawer and no document overflow');
 await page.getByRole('button',{name:'Connect GitHub',exact:true}).click();await page.getByRole('dialog').waitFor();assert.match(await page.getByRole('dialog').innerText(),/not configured/);await page.getByRole('button',{name:'Close connection dialog'}).click();checks.push('Missing GitHub configuration is explicitly blocked');
 empty=false;await page.setViewportSize({width:1440,height:1000});await page.goto(origin+'/?test=connected#workspace/overview');await page.getByRole('heading',{name:'Connected repositories'}).waitFor();await page.screenshot({path:`${out}/fixture-overview-1440.png`,fullPage:true});
 await page.getByRole('link',{name:'Repositories',exact:true}).click();await page.locator('.ws-strong-link').first().waitFor();await page.getByLabel('Find repository').fill('no-match');assert.equal(await page.locator('tbody tr:visible').count(),0);await page.getByLabel('Find repository').fill('risklens');await page.locator('.ws-strong-link').first().click();await page.getByRole('heading',{name:'Repository setup'}).waitFor();checks.push('Repository search and detail route');
 await page.getByRole('link',{name:'Pull Requests',exact:true}).click();await page.getByRole('heading',{name:'Pull Requests',exact:true}).waitFor();await page.locator('#ws-verdict-filter').selectOption('CLEAN');assert.equal(await page.locator('tbody tr:visible').count(),0);await page.locator('#ws-verdict-filter').selectOption('INCONCLUSIVE');await page.locator('.ws-strong-link').first().click();await page.getByRole('heading',{name:'INCONCLUSIVE',exact:true}).waitFor();await page.getByRole('button',{name:/handle_retry/}).first().click();assert.equal(await page.locator('#ws-evidence-detail a').count(),1);await page.screenshot({path:`${out}/fixture-investigation-1440.png`,fullPage:true});checks.push('PR verdict filters, INCONCLUSIVE scope, evidence source links and mini graph');
 await page.getByRole('link',{name:'Dependency Graph',exact:true}).click();await page.getByText('3 nodes · 2 relationships').waitFor();await page.locator('summary').filter({hasText:'Accessible node list'}).click();await page.getByRole('button',{name:'handle_retry Function'}).click();await page.getByRole('button',{name:'Expand neighborhood'}).click();await page.getByText('3 nodes · 2 relationships').waitFor();await page.getByRole('button',{name:'Fit graph'}).click();await page.screenshot({path:`${out}/fixture-graph-1440.png`,fullPage:true});checks.push('Graph list selection, inspector, bounded expansion and camera controls');
 await page.getByRole('link',{name:'Agent Activity',exact:true}).click();await page.getByRole('button',{name:'Retry',exact:true}).click();await page.getByText('Retry queued.',{exact:true}).waitFor();checks.push('Supported indexing retry interaction');
 await page.getByRole('link',{name:'Settings',exact:true}).click();await page.getByRole('heading',{name:'GitHub integration'}).waitFor();checks.push('Settings diagnostics');
 for(const width of [1024,768,390]){await page.setViewportSize({width,height:1000});await page.goto(origin+'/?test=detail-responsive#workspace/investigations/fixture-inv');await page.getByRole('heading',{name:'INCONCLUSIVE',exact:true}).waitFor();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);await page.screenshot({path:`${out}/fixture-investigation-${width}.png`,fullPage:true});}
 unavailable=true;await page.goto(origin+'/?test=unavailable#workspace/overview');await page.getByRole('heading',{name:'Workspace unavailable'}).waitFor();assert.equal(await page.getByRole('button',{name:'Try again'}).isVisible(),true);checks.push('API failure remains unavailable, not a fabricated zero state');
 assert.deepEqual(unexpected,[]);assert.deepEqual(errors,[]);checks.push('No demo API requests on workspace routes; no JavaScript console errors');
 await page.emulateMedia({reducedMotion:'reduce'});unavailable=false;await page.goto(origin+'/?test=reduced#workspace/graph');await page.getByText('3 nodes · 2 relationships').waitFor();checks.push('Reduced motion graph remains usable');
 // Separate, non-intercepted context verifies real server protection and preserved public pages.
 const real=await browser.newPage({viewport:{width:1440,height:1000}});const protectedResponse=await real.request.get(origin+'/api/v1/workspace/overview');assert.equal(protectedResponse.status(),401);await real.goto(origin+'/workspace');assert.match(real.url(),/\/login/);await real.goto(origin+'/?test=public#landing');await real.getByRole('heading',{name:'Your tests passed. Your code can still break.'}).waitFor();await real.getByRole('button',{name:'Explore sample investigation',exact:true}).click();await real.getByText('DEMO / PLAYGROUND · Isolated synthetic commerce repository',{exact:true}).waitFor();await real.screenshot({path:`${out}/real-investigation-1440.png`,fullPage:false});checks.push('REAL: protected API returns 401, /workspace redirects to login, public landing and isolated demo remain reachable');
 const report={fixtureOnly:checks.filter(x=>!x.startsWith('REAL:')),realServer:checks.filter(x=>x.startsWith('REAL:')),consoleErrors:errors,unexpectedRequests:unexpected};fs.writeFileSync(`${out}/browser-results.json`,JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});

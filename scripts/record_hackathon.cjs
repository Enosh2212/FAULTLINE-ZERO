// Real authenticated recording only. No response interception or synthetic product data.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path');
const dir=path.resolve('output/demo');fs.mkdirSync(path.join(dir,'raw'),{recursive:true});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const origin='http://localhost:8000';
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:false,args:['--window-size=1960,1180','--disable-notifications']});
 const prep=await browser.newContext({viewport:{width:1920,height:1080}});const login=await prep.newPage();await login.goto(origin+'/login?next=%2Fworkspace');
 console.log('LOGIN_REQUIRED: Sign in using the visible recording browser. Login itself is not recorded.');
 let me;
 for(let i=0;i<600;i++){const r=await prep.request.get(origin+'/api/v1/auth/me');if(r.ok()){me=await r.json();break;}await sleep(2000);}
 if(!me)throw Error('No authenticated recording session received');
 let chosen,overview;
 for(const org of me.organizations){const r=await prep.request.get(origin+'/api/v1/workspace/overview',{headers:{'X-Organization-Id':org.id}});if(!r.ok())continue;const data=await r.json();const repo=data.repositories.find(x=>x.full_name.toLowerCase().includes('risklens'));if(repo){chosen={org,repo};overview=data;break;}}
 if(!chosen)throw Error('The authenticated account has no authorized RiskLens repository. No fixtures will be substituted.');
 fs.writeFileSync(path.join(dir,'auth-ready.json'),JSON.stringify({ready:true,repository:chosen.repo.full_name}));console.log('AUTH_READY: real repository available; waiting for recording cue');
 while(!fs.existsSync(path.join(dir,'record.go')))await sleep(1000);
 const state=await prep.storageState();
 const context=await browser.newContext({viewport:{width:1920,height:1080},deviceScaleFactor:1,storageState:state,recordVideo:{dir:path.join(dir,'raw'),size:{width:1920,height:1080}}});
 const page=await context.newPage();const started=performance.now();const segments=[];const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const api=async p=>{const r=await context.request.get(origin+p,{headers:{'X-Organization-Id':chosen.org.id}});if(!r.ok())throw Error('Real API failed '+p+' '+r.status());return r.json();};
 const invs=(await api('/api/v1/workspace/investigations')).items;
 const inv=invs.find(i=>i.repository_id===chosen.repo.id&&!i.superseded)||invs.find(i=>i.repository_id===chosen.repo.id);
 if(!inv)throw Error('No genuine RiskLens investigation available');
 const detail=await api('/api/v1/workspace/investigations/'+inv.id);
 const graph=await api('/api/v1/workspace/repositories/'+chosen.repo.id+'/graph?limit=100');
 fs.writeFileSync(path.join(dir,'real-evidence.json'),JSON.stringify({repository:chosen.repo,workspace:{id:chosen.org.id,slug:chosen.org.slug},investigation:detail,graph},null,2));
 async function shot(name,seconds,setup,action){await setup();await sleep(500);const start=(performance.now()-started)/1000;console.log('RECORDING',name);if(action)await action(seconds);else await sleep(seconds*1000);segments.push({name,start,duration:seconds});}
 const goto=async hash=>{await page.goto(origin+'/?film=real#'+hash);await page.locator('#ws-main[aria-busy="false"]').waitFor();};
 await shot('landing',5,async()=>{await page.goto(origin+'/?film=real#landing');await page.getByRole('link',{name:'Open Dashboard'}).waitFor();},async()=>{await page.mouse.move(1450,420);await sleep(2400);await page.mouse.move(1580,540,{steps:35});await sleep(2600);});
 await shot('overview',6,async()=>{await goto('workspace/overview');await page.locator('#ws-workspace-picker').selectOption(chosen.org.id);await page.getByRole('heading',{name:'Connected repositories'}).waitFor();});
 await shot('repository',6,async()=>{await goto('workspace/repositories/'+chosen.repo.id);await page.getByRole('heading',{name:'Repository setup'}).waitFor();});
 await shot('coverage',10,async()=>{await page.locator('#ws-repo-coverage').scrollIntoViewIfNeeded();},async()=>{await page.mouse.move(1370,490,{steps:30});await sleep(10000);});
 await shot('repository-context',10,async()=>{await goto('workspace/repositories/'+chosen.repo.id);},async()=>{await sleep(5000);await page.locator('.ws-section-heading').last().scrollIntoViewIfNeeded();await sleep(5000);});
 await shot('graph-impact',10,async()=>{await goto('workspace/graph');await page.locator('[data-layout="elk.layered"]').waitFor();},async()=>{await sleep(4000);await page.locator('.ws-node-list summary').click();const candidates=page.locator('.ws-node-list [data-node]');if(await candidates.count()>1)await candidates.nth(1).click();await sleep(6000);});
 await shot('graph-neighbors',10,async()=>{await page.getByRole('button',{name:'Expand neighbors',exact:true}).click();await page.locator('[data-layout="elk.layered"]').waitFor();},async()=>{await sleep(4000);await page.getByRole('button',{name:'Fit graph',exact:true}).click();await sleep(6000);});
 await shot('graph-structure',10,async()=>{await page.getByLabel('Graph view',{exact:true}).selectOption('structure');await page.locator('[data-layout="elk.layered"]').waitFor();},async()=>{await sleep(3500);await page.getByRole('button',{name:'Expand file symbols'}).click();await sleep(3500);await page.getByRole('button',{name:'Collapse file symbols'}).click();await sleep(3000);});
 await shot('investigation',10,async()=>{await goto('workspace/investigations/'+inv.id);await page.getByRole('heading',{name:inv.verdict,exact:true}).waitFor();},async()=>{await sleep(4000);const sym=page.locator('[data-evidence-index]').first();if(await sym.count())await sym.click();await sleep(6000);});
 await shot('evidence',7,async()=>{await page.locator('#ws-evidence-detail').scrollIntoViewIfNeeded();},async()=>{await sleep(3500);await page.getByRole('heading',{name:'Recorded activity',exact:true}).scrollIntoViewIfNeeded();await sleep(3500);});
 let checkRecorded=false;
 await shot('github-check',8,async()=>{try{await page.goto(detail.check_url||'https://github.com/Enosh2212/risklens-ai/runs/117658118768',{waitUntil:'domcontentloaded',timeout:30000});await page.getByText(/INCONCLUSIVE|Inconclusive|No matching business invariant|No applicable verified|Scope is untested/).first().waitFor({timeout:15000});checkRecorded=true;}catch{await goto('workspace/investigations/'+inv.id);await page.getByRole('heading',{name:'INCONCLUSIVE',exact:true}).waitFor();}},async()=>{await sleep(8000);});
 // Finish with the actual illustrative workflow, clearly labeled as such.
 await shot('workflow',6,async()=>{await page.goto(origin+'/?film=real#landing');await page.getByRole('link',{name:'How It Works',exact:true}).click();await page.locator('#section-how-it-works').scrollIntoViewIfNeeded();},async()=>{await page.locator('.workflow-step[data-step="3"]').click();await sleep(3000);await page.locator('.workflow-step[data-step="4"]').click();await sleep(3000);});
 const video=page.video();await context.close();await video.saveAs(path.join(dir,'raw','software-recording.webm'));
 fs.writeFileSync(path.join(dir,'capture-manifest.json'),JSON.stringify({segments,repository:chosen.repo.full_name,commit:inv.commit_sha,verdict:inv.verdict,checkUrl:detail.check_url,checkRecorded,errors,footage:'Live authenticated browser. No mocked responses.'},null,2));
 console.log('CAPTURE_COMPLETE',JSON.stringify({segments:segments.length,checkRecorded,errors}));await browser.close();
})().catch(e=>{console.error('CAPTURE_FAILED',e.message);process.exit(1);});

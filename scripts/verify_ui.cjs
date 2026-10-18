const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require(process.env.FZ_PLAYWRIGHT_PATH||'playwright');
const base=process.env.FZ_BASE_URL||'http://localhost:8001';
const output=path.resolve('output');fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.FZ_BROWSER_CHANNEL||'msedge'});
 const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const checks=[];const check=(name,condition)=>{assert.ok(condition,name);checks.push(name);};
 const waitSelected=async key=>{await page.selectOption('#change-select',key);await page.waitForFunction(k=>document.getElementById('context-change').textContent.toLowerCase().includes(k)&&!document.getElementById('run-button').disabled,key==='control'?'pricing':key==='uncovered'?'shipping':key==='refund'?'refund':key);};
 await page.goto(base+'/#investigation');await page.waitForFunction(()=>!document.getElementById('run-button').disabled);
 check('Simple mode is default',await page.locator('#simple-mode').getAttribute('aria-pressed')==='true');
 check('Graph is initially collapsed',!await page.locator('#graph-disclosure').evaluate(e=>e.open));
 await page.selectOption('#execution-mode','deterministic');
 const outcomes={payment:'Regression detected',inventory:'Regression detected',refund:'Regression detected',control:'Selected verification passed',uncovered:'This change needs more verification'};
 const scenarios=[];
 for(const [key,title] of Object.entries(outcomes)){
  await waitSelected(key);
  await page.locator('#run-button').click();
  check(key+': duplicate submissions disabled',await page.locator('#run-button').isDisabled());
  check(key+': previous proof cleared while running',await page.locator('#report-root .revision-result').count()===0);
  await page.waitForFunction(()=>!document.getElementById('run-button').disabled&&document.getElementById('execution-status').textContent.includes('Completed'),null,{timeout:180000});
  const heading=await page.locator('#report-root h1').textContent();check(key+': correct finding',heading.includes(title));
  check(key+': actual fallback mode visible',(await page.locator('#execution-status').textContent()).includes('Deterministic fallback'));
  if(key!=='uncovered'){const labels=await page.locator('#verification-evidence .outcome-label').allTextContents();check(key+': both revisions compared',labels[0]==='PASS'&&labels[1]===(key==='control'?'PASS':'FAIL'));}
  else check('Uncovered: no invented verification panels',await page.locator('#verification-evidence .revision-result').count()===0);
  scenarios.push({key,heading,mode:await page.locator('#execution-status').textContent()});
  if(key==='refund'){
   await page.locator('#reproduce-disclosure > summary').click();check('Refund uses approved spec reproduction',(await page.locator('#reproduction-command').textContent()).includes('--spec'));
  }
 }
 await waitSelected('payment');await page.screenshot({path:path.join(output,'pr-report-desktop.png'),fullPage:true});
 await page.locator('#graph-disclosure > summary').click();await page.waitForFunction(()=>document.querySelector('#evidence-graph .graph-layout-status').textContent.includes('ELK'));
 const root=page.locator('#evidence-graph');
 check('Five-node focused evidence',await root.locator('.graph-node-select option').count()===6);
 check('Readable graph camera scale',Number(await root.getAttribute('data-zoom'))>=.85);
 await root.locator('.graph-node-select').selectOption('S-PAYMENTS');check('Keyboard node inspector',await root.locator('.graph-inspector').innerText().then(t=>t.includes('Why is it relevant?')&&t.includes('Payments')));
 await root.locator('[data-camera="selected"]').click();await root.locator('[data-camera="path"]').click();await root.locator('[data-camera="fit"]').click();await root.locator('[data-camera="in"]').click();await root.locator('[data-camera="out"]').click();await root.locator('[data-camera="reset"]').click();
 await root.locator('.text-path > summary').click();await root.locator('[data-edge]').last().click();check('Edge inspector shows persisted provenance',(await root.locator('.graph-inspector').innerText()).includes('returned by FalkorDB'));
 await root.locator('.text-path > summary').click();await root.locator('.graph-node-select').selectOption('S-PAYMENTS');
 await page.locator('#graph-disclosure').screenshot({path:path.join(output,'evidence-expanded.png')});
 await page.locator('#technical-mode').click();check('Technical mode opens detail sections',await page.locator('#tools-disclosure').evaluate(e=>e.open));await page.locator('#simple-mode').click();check('Simple mode collapses details',!await page.locator('#tools-disclosure').evaluate(e=>e.open));
 await page.locator('#nav-overview').click();await page.waitForFunction(()=>document.querySelector('#knowledge-graph .graph-layout-status').textContent.includes('ELK'));
 const explorer=page.locator('#knowledge-graph');const serviceCount=await explorer.locator('.graph-node-select option').count();
 check('Explorer starts with services only',serviceCount>1&&serviceCount<12);await explorer.locator('.graph-node-select').selectOption('S-PAYMENTS');await explorer.locator('.graph-expand-kind').selectOption('Invariant');await explorer.locator('.graph-expand').click();await page.waitForFunction(count=>document.querySelectorAll('#knowledge-graph .graph-node-select option').length>count,serviceCount);
 check('Neighbor expansion adds actual connected invariant',(await explorer.locator('.graph-node-select').innerText()).includes('Exactly one capture'));await explorer.locator('.graph-collapse').click();check('Collapse retains root services',await explorer.locator('.graph-node-select option').count()===serviceCount);
 await page.screenshot({path:path.join(output,'knowledge-explorer.png'),fullPage:true});
 const sizes=[];
 for(const [width,height] of [[1440,900],[1366,768],[390,844]]){
  await page.setViewportSize({width,height});await page.locator('#nav-landing').click();await page.waitForTimeout(150);
  check(width+': five landing sections',await page.locator('#view-landing > section').count()===5);
  check(width+': landing no overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(output,`landing-${width}.png`),fullPage:true});
  for(const key of ['payment','inventory','refund']){await page.locator(`[data-evidence="${key}"]`).click();check(`${width}: ${key} evidence comes from a saved report`,(await page.locator('#evidence-display-card').innerText()).includes('saved report'));}
  await page.locator('#nav-investigation').click();check(width+': report no overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(output,`report-${width}.png`),fullPage:true});
  await page.locator('#graph-disclosure > summary').click();check(width+': expanded graph no page overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.locator('#graph-disclosure').screenshot({path:path.join(output,`graph-${width}.png`)});await page.locator('#graph-disclosure > summary').click();
  sizes.push({width,height});
 }
 // Failure must clear stale evidence and retain a truthful error report.
 await page.route('**/api/v1/git/investigations',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Provider unavailable for UI resilience verification'})}));
 await page.locator('#run-button').click();await page.waitForFunction(()=>document.getElementById('execution-status').textContent.includes('Provider unavailable'));
 check('Provider failure is visible',(await page.locator('#report-root').innerText()).includes('Verification could not finish'));check('Failure does not reuse stale pass/fail',await page.locator('#verification-evidence .revision-result').count()===0);
 await page.unroute('**/api/v1/git/investigations');
 await page.route('**/api/v1/graph/evidence/payment',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Graph unavailable for UI resilience verification'})}));
 await page.setViewportSize({width:1440,height:900});await waitSelected('control');await waitSelected('payment');check('Graph failure keeps saved verified report',(await page.locator('#report-root h1').textContent()).includes('Regression detected'));
 await page.unroute('**/api/v1/graph/evidence/payment');
 await page.emulateMedia({reducedMotion:'reduce'});await page.reload();await page.waitForFunction(()=>!document.getElementById('run-button').disabled);check('Reduced motion preference supported',await page.evaluate(()=>matchMedia('(prefers-reduced-motion: reduce)').matches));
 const fallbackPage=await browser.newPage({viewport:{width:1440,height:900}});
 await fallbackPage.route('**/assets/vendor/elk.bundled.js',route=>route.fulfill({contentType:'application/javascript',body:'/* ELK intentionally unavailable for resilience verification */'}));
 await fallbackPage.goto(base+'/#investigation');await fallbackPage.waitForFunction(()=>document.getElementById('execution-status').textContent.includes('Completed'));
 await fallbackPage.locator('#graph-disclosure > summary').click();
 check('ELK failure uses disclosed horizontal fallback',(await fallbackPage.locator('#evidence-graph .graph-layout-status').textContent()).includes('Built-in horizontal layout'));
 await fallbackPage.close();
 const textPage=await browser.newPage({viewport:{width:390,height:844}});
 await textPage.route('**/assets/vendor/cytoscape.min.js',route=>route.fulfill({contentType:'application/javascript',body:'/* Renderer intentionally unavailable for resilience verification */'}));
 await textPage.goto(base+'/#investigation');await textPage.waitForFunction(()=>document.getElementById('execution-status').textContent.includes('Completed'));
 check('Renderer failure retains report',(await textPage.locator('#report-root h1').textContent()).includes('Regression detected'));
 await textPage.locator('#graph-disclosure > summary').click();await textPage.locator('#evidence-graph .graph-node-select').selectOption('S-PAYMENTS');
 check('Renderer failure keeps keyboard inspection',(await textPage.locator('#evidence-graph .graph-inspector').textContent()).includes('Why is it relevant?'));
 await textPage.close();
 check('No browser JavaScript errors',errors.length===0);
 const result={passed:checks.length,checks,scenarios,sizes,browser:'Microsoft Edge / Playwright',errors};fs.writeFileSync(path.join(output,'ui-verification.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});


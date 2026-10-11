'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage(),errors=[],checks=[];page.on('pageerror',error=>errors.push(error.message));
  let releaseCodex,installed=false,signedIn=false;
  await page.route('http://provider.test/**',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/account-gate.js')return route.fulfill({contentType:'text/javascript',body:fs.readFileSync(path.join(__dirname,'../ui/account-gate.js'),'utf8')});
   if(url.pathname==='/api/account'){
    const backend=url.searchParams.get('backend')||'codex';checks.push({backend,refresh:url.searchParams.get('refresh')});
    if(backend==='codex')await new Promise(resolve=>releaseCodex=resolve);
    return route.fulfill({json:{backend,installed:backend==='cursor'&&installed,login_required:backend!=='cursor'||!signedIn,account:backend==='cursor'&&signedIn?{type:'cursor'}:null}});
   }
   return route.fulfill({contentType:'text/html',body:`<script type="module">
    import {createAccountGate} from '/account-gate.js';
    window.backend='codex';window.setup=true;window.installCalls=0;window.loginCalls=[];
    window.superSurferDesktop={installCursor:async()=>{window.installCalls++;return{opened:false,command:'ssh -t research install-cursor'}},openProviderLogin:async backend=>({opened:false,command:'ssh -t research cursor-agent login',error:'Terminal could not open. Run the displayed command.'})};
    window.gate=createAccountGate({api:async route=>fetch('/api/'+route).then(r=>r.json()),action:async(op,p)=>{if(op==='account.choose'){window.backend=p.backend;window.setup=false;return{};}window.loginCalls.push(p.backend);return{backend:p.backend,type:'terminal',command:'cursor-agent login'}},onAccount:()=>{},readOnly:()=>false,getBackend:()=>backend,getSetupRequired:()=>setup});
    void gate.open('codex');
   </script>`});
  });
  await page.goto('http://provider.test/');await page.locator('#account-provider').waitFor();
  while(!releaseCodex)await page.waitForTimeout(10);
  await page.locator('#account-provider').selectOption('cursor');
  await page.locator('#account-install-cursor').waitFor({timeout:1500});
  assert.ok(checks.some(row=>row.backend==='cursor'),'Cursor check must proceed while Codex is stalled');
  await page.locator('#account-install-cursor').click();assert.equal(await page.evaluate(()=>installCalls),1);
  installed=true;await page.locator('#account-check').click();await page.waitForFunction(()=>!document.querySelector('#account-sign-in').disabled);
  await page.locator('#account-sign-in').click();await page.waitForFunction(()=>document.querySelector('#account-terminal-command').textContent.includes('ssh -t research'));
  assert.match(await page.locator('#account-gate-status').innerText(),/displayed command/);
  assert.deepEqual(await page.evaluate(()=>loginCalls),['cursor']);
  signedIn=true;await page.locator('#account-check').click();await page.waitForFunction(()=>!document.querySelector('#account-use').disabled);
  releaseCodex();await page.waitForTimeout(30);assert.equal(await page.locator('#account-provider').inputValue(),'cursor');
  await page.locator('#account-use').click();await page.locator('#account-gate').waitFor({state:'hidden'});
  assert.equal(await page.evaluate(()=>backend),'cursor');assert.ok(checks.some(row=>row.backend==='cursor'&&row.refresh==='1'));
  assert.deepEqual(errors,[]);console.log('PASS stalled other-provider check, explicit Cursor setup, host terminal fallback, fresh sign-in check and provider choice');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

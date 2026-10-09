'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage();await page.clock.install();let account={account:{type:'chatgpt'},login_required:false},broken=false,release,hold=false,logins=0;
  await page.route('http://account.test/**',async route=>{
   const pathname=new URL(route.request().url()).pathname;
   if(pathname==='/account-gate.js')return route.fulfill({contentType:'text/javascript',body:fs.readFileSync(path.join(__dirname,'../ui/account-gate.js'),'utf8')});
   if(pathname==='/api/account'){if(hold)await new Promise(resolve=>release=resolve);return route.fulfill({status:broken?503:200,json:broken?{error:'Host is restarting'}:account});}
   return route.fulfill({contentType:'text/html',body:`<script type="module">import {createAccountGate} from '/account-gate.js';window.loginCalls=0;window.modalOpens=0;const show=HTMLDialogElement.prototype.showModal;HTMLDialogElement.prototype.showModal=function(){window.modalOpens++;show.call(this)};window.gate=createAccountGate({api:async()=>{const r=await fetch('/api/account');const d=await r.json();if(!r.ok)throw new Error(d.error);return d},action:async()=>{window.loginCalls++;return {loginId:'one',userCode:'TEST',verificationUrl:'https://auth.openai.com/codex/device'}},onAccount:a=>window.account=a,readOnly:()=>!!window.readOnly});</script>`});
  });
  await page.goto('http://account.test');await page.waitForFunction(()=>window.gate);const gate=page.locator('#account-gate');assert.equal(await gate.isVisible(),false);
  hold=true;await page.evaluate(()=>{window.pendingCheck=gate.refresh()});while(!release)await new Promise(resolve=>setTimeout(resolve,10));
  await page.clock.fastForward(8000);assert.equal(await gate.isVisible(),false);hold=false;release();await page.evaluate(()=>window.pendingCheck);assert.equal(await page.evaluate(()=>gate.ready()),true);assert.equal(await page.evaluate(()=>modalOpens),0);
  // A transient reconnect fails closed but never asks for a new login.
  broken=true;await page.evaluate(()=>gate.refresh());assert.equal(await page.evaluate(()=>gate.ready()),false);assert.equal(await gate.isVisible(),false);
  await page.clock.fastForward(10000);broken=false;await page.evaluate(()=>gate.refresh());await page.waitForFunction(()=>gate.ready());assert.equal(await page.evaluate(()=>modalOpens),0);
  // A prolonged network problem is explicitly a reconnect screen, without a sign-in CTA.
  broken=true;await page.evaluate(()=>gate.refresh());await page.clock.fastForward(16000);await page.evaluate(()=>gate.refresh());await page.getByRole('heading',{name:'Reconnecting to ChatGPT'}).waitFor();assert.equal(await page.locator('#account-sign-in').isVisible(),false);
  broken=false;await page.evaluate(()=>gate.refresh());await gate.waitFor({state:'hidden'});
  // Expired or missing authentication gets its own fresh 15-second grace.
  account={account:null,login_required:true};await page.evaluate(()=>gate.refresh());assert.equal(await gate.isVisible(),false);await page.clock.fastForward(10000);await page.evaluate(()=>gate.refresh());assert.equal(await gate.isVisible(),false);await page.clock.fastForward(6000);await page.evaluate(()=>gate.refresh());await page.getByRole('heading',{name:'Connect ChatGPT'}).waitFor();assert.equal(await page.locator('#account-sign-in').isEnabled(),true);
  await page.keyboard.press('Escape');assert.equal(await gate.isVisible(),false);assert.equal(await page.evaluate(()=>gate.ready()),false);
  // Explicit Settings sign-in remains immediate, including during startup grace.
  await page.reload();await page.waitForFunction(()=>window.gate);await page.evaluate(()=>gate.open());await page.getByText('TEST',{exact:true}).waitFor();assert.equal(await page.evaluate(()=>loginCalls),1);
  account={account:{type:'chatgpt'},login_required:false,login:{loginId:'one',status:'completed'}};await page.evaluate(()=>gate.refresh());await gate.waitFor({state:'hidden'});
  account={account:null,login_required:true};await page.evaluate(()=>{window.readOnly=true;return gate.refresh()});await page.clock.fastForward(16000);assert.equal(await gate.isVisible(),false);
  console.log('PASS no startup flash; slow success; transient and persistent reconnect; delayed confirmed sign-out; explicit login; read-only access');
 }finally{for(const c of browser.contexts())for(const p of c.pages())await p.unrouteAll({behavior:'ignoreErrors'});await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});

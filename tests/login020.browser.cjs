'use strict';
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {install}=require('./fixtures/workspace-demo.cjs');
(async()=>{
 const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:900}});page.setDefaultTimeout(10000);await page.clock.install();
  const errors=[];page.on('pageerror',error=>errors.push(error.message));await install(page);
  let account={account:null,login_required:true},reads=0,logins=0,broken=false;
  await page.route('http://demo.test/api/account**',async route=>{reads++;return route.fulfill({status:broken?503:200,contentType:'application/json',body:JSON.stringify(broken?{error:'Host account check unavailable'}:account)});});
  await page.route('http://demo.test/api/action',async route=>{
   if(route.request().postDataJSON().op!=='account.login')return route.fallback();
   logins++;return route.fulfill({json:{loginId:'login-'+logins,userCode:'TEST-1234',verificationUrl:'https://auth.openai.com/codex/device'}});
  });
  await page.goto('http://demo.test/');const gate=page.locator('#account-gate');await page.waitForFunction(()=>document.querySelector('#account-gate-status')?.textContent.includes('Sign in on this machine'));assert.equal(await gate.isVisible(),false);await page.clock.fastForward(16000);await gate.waitFor();await page.getByText('Sign in on this machine to use ChatGPT.',{exact:true}).waitFor();
  assert.equal(await page.locator('#chat-send').isDisabled(),true);
  await page.keyboard.press('Escape');assert.equal(await gate.isVisible(),false);assert.equal(await page.locator('#chat-send').isDisabled(),true);await page.locator('[data-view=settings]').click();await page.locator('[data-account-login=codex]').click();await gate.waitFor();
  await page.getByText('TEST-1234',{exact:true}).waitFor();assert.equal(logins,1);
  await page.locator('#account-check').click();assert.equal(await gate.isVisible(),true);
  account={account:null,login_required:true,login:{loginId:'login-1',status:'failed',error:'Code expired'}};
  await page.locator('#account-check').click();await page.getByText('Code expired',{exact:true}).waitFor();assert.equal(await page.locator('#account-sign-in').isEnabled(),true);
  await page.locator('#account-sign-in').click();assert.equal(logins,2);
  account={account:{type:'chatgpt',email:'demo@example.test'},login_required:false,login:{loginId:'login-2',status:'completed'}};
  await page.locator('#account-check').click();await gate.waitFor({state:'hidden'});assert.equal(await page.locator('#chat-send').isEnabled(),true);
  await page.reload();await page.locator('#chat-send:enabled').waitFor();assert.equal(await gate.isVisible(),false);assert.equal(logins,2);
  // A second host has its own account even when this host is signed in.
  const other=await browser.newPage();await other.clock.install();await install(other);await other.route('http://demo.test/api/account**',route=>route.fulfill({json:{account:null,login_required:true}}));await other.goto('http://demo.test/');await other.waitForFunction(()=>document.querySelector('#account-gate-status')?.textContent.includes('Sign in on this machine'));await other.clock.fastForward(16000);await other.locator('#account-gate').waitFor();assert.equal(await gate.isVisible(),false);await other.unrouteAll({behavior:'wait'});await other.close();
  // Account check failures fail closed, preserve the draft, and recover without login when healthy.
  await page.locator('#chat-input').fill('Keep this direction');broken=true;
  await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await page.waitForFunction(()=>document.querySelector('#account-gate-status')?.textContent.includes('Retrying'));assert.equal(await gate.isVisible(),false);await page.clock.fastForward(16000);await gate.getByText('Host account check unavailable',{exact:true}).waitFor();
  assert.equal(await page.locator('#chat-send').isDisabled(),true);broken=false;await page.locator('#account-check').click();await gate.waitFor({state:'hidden'});assert.equal(await page.locator('#chat-input').inputValue(),'Keep this direction');
  assert.deepEqual(errors,[]);assert.ok(reads>=7);
  console.log('PASS required host login, dismissible dialog without send bypass, device-code expiry/retry, completion, reconnect, independent hosts, unavailable checks and draft preservation');
 }finally{for(const context of browser.contexts())for(const page of context.pages())await page.unrouteAll({behavior:'ignoreErrors'});await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

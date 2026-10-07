'use strict';
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
 const browser = await chromium.launch({executablePath:process.env.CHROME_PATH || '/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 const failures=[];
 async function scenario(name,options,check) {
  const context=await browser.newContext({viewport:{width:options.width||1100,height:800}});
  const errors=[];
  await context.addInitScript(options=>{
   window.calls=[];
   window.superSurferDesktop={
    configuration:async()=>{if(options.delay)await new Promise(r=>setTimeout(r,options.delay));if(options.configError)throw new Error('Saved connection unavailable');return options.config===undefined?{mode:'remote',target:'tulip'}:options.config;},
    listHosts:async()=>{if(options.hostError)throw new Error('SSH config unreadable');return {hosts:[{name:'Tulip <b>compute</b>',target:'tulip'}],warnings:[]};},
    onStatus:()=>()=>{},
    connect:async config=>{window.calls.push(config);await new Promise(r=>setTimeout(r,150));return {error:'Connection refused. Try again.'};}
   };
  },options);
  await context.route('http://setup.test/**',route=>{
   const file=path.join(__dirname,'../desktop',new URL(route.request().url()).pathname.slice(1)||'setup.html');
   return route.fulfill({contentType:file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html',body:fs.readFileSync(file)});
  });
  const page=await context.newPage();page.setDefaultTimeout(2500);page.on('pageerror',e=>errors.push(e.message));
  try {await page.goto('http://setup.test/setup.html');await check(page);assert.deepEqual(errors,[]);console.log('PASS',name);}
  catch(error){failures.push(name+': '+error.message);console.error('FAIL',name,error.message);}
  finally {await context.close();}
 }
 try {
  await scenario('startup cannot submit before configuration is loaded',{delay:800},async page=>{
   assert.equal(await page.locator('#connect-button').isDisabled(),true);
   await page.waitForFunction(()=>!document.querySelector('#connect-button').disabled);
  });
  await scenario('broken discovery preserves remote custom entry',{hostError:true},async page=>{
   await page.waitForFunction(()=>!document.querySelector('#connect-button').disabled);
   await page.locator('#host').selectOption('__custom');await page.locator('#target').fill('new-node');
   await page.locator('#connect-button').click();await page.getByText('Connection refused. Try again.',{exact:true}).waitFor();
   assert.equal(await page.evaluate(()=>calls[0].target),'new-node');
  });
  await scenario('null configuration falls back to usable local defaults',{config:null},async page=>{
   await page.waitForFunction(()=>!document.querySelector('#connect-button').disabled);
   assert.equal(await page.locator('#mode').inputValue(),'local');
   await page.locator('#connect-button').click();await page.getByText('Connection refused. Try again.',{exact:true}).waitFor();
   assert.equal(await page.evaluate(()=>calls[0].mode),'local');
  });
  await scenario('saved config failure still permits a new local connection',{configError:true},async page=>{
   await page.waitForFunction(()=>!document.querySelector('#connect-button').disabled);
   await page.locator('#mode').selectOption('local');await page.locator('#connect-button').click();
   await page.getByText('Connection refused. Try again.',{exact:true}).waitFor();
   assert.equal(await page.evaluate(()=>calls.length),1);
  });
  await scenario('repeated Enter dispatches one attempt and retry recovers',{},async page=>{
   await page.waitForFunction(()=>document.querySelector('#host').options.length>0);
   await page.evaluate(()=>{document.querySelector('#connect-form').requestSubmit();document.querySelector('#connect-form').requestSubmit();});
   await page.getByText('Connection refused. Try again.',{exact:true}).waitFor();
   assert.equal(await page.evaluate(()=>calls.length),1);
   await page.locator('#connect-button').click();await page.waitForFunction(()=>calls.length===2);
  });
  await scenario('narrow display preserves readable form without horizontal scrolling',{width:390},async page=>{
   await page.waitForFunction(()=>document.querySelector('#host').options.length>0);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   assert.equal(await page.locator('#host b').count(),0);
  });
 } finally {await browser.close();}
 if(failures.length)throw new Error(failures.join('\n'));
})().catch(error=>{console.error(error);process.exitCode=1;});

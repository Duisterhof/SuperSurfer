'use strict';
const {chromium}=require('playwright');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const {install}=require('./fixtures/workspace-demo.cjs');
(async()=>{
 const out=path.resolve(process.env.SUPERSURFER_QA_OUTPUT||'../../work/release019-checks');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1512,height:982}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  page.setDefaultTimeout(8000);await install(page);await page.goto('http://demo.test/');await page.frameLocator('#result-preview').getByText('Compare methods',{exact:true}).waitFor();
  for(const theme of ['light','dark']){
   await page.evaluate(t=>window.superSurferTheme.setPreference(t),theme);
   await page.locator('#result-preview').evaluate(el=>el.src=el.src);
   await page.frameLocator('#result-preview').getByText('Compare methods',{exact:true}).waitFor();
   await page.screenshot({path:path.join(out,`floating-${theme}-results.png`)});
   const layout=await page.evaluate(()=>{const b=s=>document.querySelector(s).getBoundingClientRect().toJSON();return {header:b('.topbar'),sidebar:b('.sidebar'),main:b('#main'),chat:b('#chat-panel'),radius:getComputedStyle(document.querySelector('#main')).borderRadius,scroll:document.documentElement.scrollWidth,width:innerWidth};});
   assert.ok(layout.header.bottom<layout.sidebar.top&&layout.sidebar.right<layout.main.left&&layout.main.right<layout.chat.left,JSON.stringify(layout));
   assert.equal(layout.radius,'16px');assert.ok(layout.scroll<=layout.width);
  }
  await page.evaluate(()=>window.superSurferTheme.setPreference('light'));
  await page.getByRole('button',{name:'Compute',exact:false}).first().click();await page.locator('.gpu-slot').first().waitFor();
  await page.getByRole('button',{name:'Toggle agent panel',exact:true}).click();
  await page.screenshot({path:path.join(out,'floating-compute.png')});
  await page.getByRole('button',{name:'Toggle agent panel',exact:true}).click();
  await page.getByRole('button',{name:'Maximize agent chat',exact:true}).click();
  for(const width of [1512,900,600,390]){
   await page.setViewportSize({width,height:850});
   const box=await page.locator('#chat-form').boundingBox();assert.ok(box.x>=0&&box.x+box.width<=width+1);
   assert.equal(await page.locator('#main').isVisible(),false);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  await page.setViewportSize({width:1512,height:982});
  await page.screenshot({path:path.join(out,'floating-fullscreen.png')});
  await page.getByRole('button',{name:'Restore agent panel',exact:true}).click();
  const cdp=await page.context().newCDPSession(page);
  await cdp.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-transparency',value:'reduce'}]});
  assert.equal(await page.locator('.sidebar').evaluate(el=>getComputedStyle(el).backdropFilter),'none');
  await cdp.send('Emulation.setEmulatedMedia',{features:[]});
  await page.emulateMedia({reducedMotion:'reduce',forcedColors:'active'});
  assert.equal(await page.locator('.workspace-landscape').isVisible(),false);
  await page.emulateMedia({forcedColors:'none'});
  await page.evaluate(()=>window.superSurferTheme.setPreference(window.superSurferTheme.themes.find(t=>t.type==='dark').id));
  assert.ok(await page.locator('html').getAttribute('data-vscode-theme'));
  const foreground=await page.locator('.button.primary').first().evaluate(e=>getComputedStyle(e).color).catch(()=>null);
  assert.deepEqual(errors,[]);console.log('PASS independent floating panels, light/dark and imported theme, compact Compute, fullscreen/narrow geometry, forced colors and no JS errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

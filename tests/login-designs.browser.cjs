'use strict';
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 const preview=path.resolve(__dirname,'../dist/login-designs.html');
 const output=process.env.SUPERSURFER_QA_OUTPUT||path.resolve(__dirname,'../../../work/overnight-qa');fs.mkdirSync(output,{recursive:true});
 let cases=0;
 try {
  for(const scheme of ['light','dark'])for(const width of [1440,1000,760,390]){
   const context=await browser.newContext({viewport:{width,height:940},colorScheme:scheme,reducedMotion:'reduce'});
   const page=await context.newPage(),errors=[],network=[];page.on('pageerror',error=>errors.push(error.message));page.on('request',request=>{if(/^https?:/.test(request.url()))network.push(request.url());});
   await page.goto(pathToFileURL(preview).href);
   for(const design of ['glass','observatory','paper']){
    await page.locator('[data-preview-design="'+design+'"]').click();
    await page.waitForFunction(()=>!document.querySelector('#connect-button').disabled);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${design} ${width} overflow`);
    for(const name of ['Workspace location','Computer'])assert.ok(await page.getByLabel(name,{exact:true}).isVisible());
    await page.locator('#solid-preview').check();
    assert.equal(await page.locator('.connection').evaluate(element=>getComputedStyle(element).backdropFilter),'none');
    await page.locator('#solid-preview').uncheck();
    await page.locator('#host').selectOption('__custom');await page.locator('#target').fill('user@host');
    await page.getByText('Connection options',{exact:true}).click();
    await page.getByLabel('Workspace port',{exact:true}).fill('99999');
    assert.equal(await page.getByLabel('Workspace port',{exact:true}).evaluate(element=>element.validity.valid),false);
    await page.getByLabel('Workspace port',{exact:true}).fill('8765');
    await page.getByText('Connection options',{exact:true}).click();
    await page.locator('#host').selectOption('tulip');
    if(width===1440&&scheme==='light')await page.screenshot({path:path.join(output,'login-'+design+'.png'),fullPage:true});
    cases++;
   }
   await page.locator('#connect-button').click();await page.getByText('Design preview only. No connection was made.',{exact:true}).waitFor();
   assert.deepEqual(errors,[]);assert.deepEqual(network,[]);await context.close();
  }
  const context=await browser.newContext({forcedColors:'active',viewport:{width:1000,height:800}});
  const page=await context.newPage();await page.goto(pathToFileURL(preview).href);
  assert.equal(await page.locator('.landscape').evaluate(element=>getComputedStyle(element).display),'none');
  await context.close();
  console.log('PASS',cases,'design/size/scheme combinations, reduced transparency, motion, forced colors, real form validation, no network');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

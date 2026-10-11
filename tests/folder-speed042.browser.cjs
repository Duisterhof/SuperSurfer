const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 try{
 const page=await browser.newPage();await page.route('http://fixture.test/**',async route=>{const path=new URL(route.request().url()).pathname;if(path==='/')return route.fulfill({contentType:'text/html',body:'<div id="tree"></div>'});const fs=require('node:fs');return route.fulfill({contentType:'text/javascript',body:fs.readFileSync('ui'+path,'utf8')});});
 await page.goto('http://fixture.test/');await page.evaluate(async()=>{
  const {createRepositoryExplorer}=await import('/code-tiles.js');window.calls=[];window.releaseSlow=null;
  const dir=name=>({name,path:name,kind:'directory'});
  window.explorer=createRepositoryExplorer({api:async url=>{const p=new URL('http://x/'+url).searchParams.get('path')||'';calls.push(p);if(p==='slow')await new Promise(res=>releaseSlow=res);return {entries:p?[{name:'file.txt',path:p+'/file.txt',kind:'file'}]:[dir('slow'),dir('fast')],truncated:false};}});
  await explorer.mount(document.querySelector('#tree'),{projectId:'p',repo:'/tmp/project'});
 });
 await page.locator('[data-tile-directory=slow]').click();await page.waitForFunction(()=>!!releaseSlow);
 const start=Date.now();await page.locator('[data-tile-directory=fast]').click();await page.locator('[data-tile-file="fast/file.txt"]').waitFor();assert.ok(Date.now()-start<1000,'Fast folder waited for unrelated slow folder');
 assert.deepEqual(await page.evaluate(()=>calls),['','slow','fast']);await page.locator('[data-tile-directory=fast]').click();await page.locator('[data-tile-directory=fast]').click();assert.deepEqual(await page.evaluate(()=>calls),['','slow','fast']);
 await page.evaluate(()=>releaseSlow());await page.locator('[data-tile-file="slow/file.txt"]').waitFor();console.log('PASS unrelated slow folder does not block expansion; one request per opened folder, cached reopen makes zero requests');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {install}=require('./fixtures/workspace-demo.cjs');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[],saves=[];
  page.on('pageerror',error=>errors.push(error.message));
  const {data}=await install(page,{tab:'overview'});
  data.settings.backends={manager:'codex',lead:'codex',worker:'codex'};
  data.settings.reasoning.worker='high';
  await page.route('http://demo.test/api/account*',route=>{const backend=new URL(route.request().url()).searchParams.get('backend')||'codex';return route.fulfill({json:{backend,installed:true,login_required:false,account:{type:backend==='codex'?'chatgpt':backend}}});});
  await page.route('http://demo.test/api/action',route=>{const call=route.request().postDataJSON();assert.equal(call.op,'settings.save');saves.push(call.params);Object.assign(data.settings,call.params);return route.fulfill({json:data.settings});});
  await page.goto('http://demo.test/');await page.locator('[data-view=settings]').click();
  await page.locator('.coding-backends [data-provider-account]').first().waitFor();
  assert.equal(await page.getByRole('heading',{name:'Coding backends',exact:true}).count(),1);
  assert.equal(await page.locator('.coding-backends [data-provider-account]').count(),3);
  assert.equal(await page.locator('.coding-backends .agent-default-row').count(),3);
  assert.equal(await page.getByRole('heading',{name:/Other accounts|Agent models/}).count(),0);
  for(const width of [1600,1100,850]){
   await page.setViewportSize({width,height:1000});
   const geometry=await page.locator('.agent-default-row').evaluateAll(rows=>rows.map(row=>{
    const rect=row.getBoundingClientRect(),controls=[...row.querySelectorAll('input,select')].map(n=>{const r=n.getBoundingClientRect();return{x:r.x,y:r.y,right:r.right,bottom:r.bottom};});
    return{left:rect.left,right:rect.right,controls};
   }));
   for(const row of geometry)for(const box of row.controls){assert.ok(box.x>=row.left-1&&box.right<=row.right+1,'Controls overflow the settings row: '+JSON.stringify({width,row,box}));}
   if(width===1600)for(const row of geometry){assert.ok(Math.max(...row.controls.map(b=>b.y))-Math.min(...row.controls.map(b=>b.y))<2,'Provider, model and effort must align');}
  }
  await page.setViewportSize({width:1600,height:1000});
  await page.locator('#model-worker').fill('saved-codex-model');
  await page.locator('#reasoning-worker').selectOption('high');
  await page.locator('[name=backend_worker]').selectOption('claude');
  assert.equal(await page.locator('#model-worker').isVisible(),false);
  assert.equal(await page.locator('[data-agent-role=worker] .agent-default-chat').isVisible(),true);
  await page.locator('[name=backend_worker]').selectOption('codex');
  assert.equal(await page.locator('#model-worker').inputValue(),'saved-codex-model');
  assert.equal(await page.locator('#reasoning-worker').inputValue(),'high');
  await page.locator('#settings-form button[type=submit]').click();
  await page.waitForFunction(()=>!document.querySelector('#settings-form button[type=submit]').disabled);
  assert.equal(saves.at(-1).models.worker,'saved-codex-model');
  await page.locator('#model-worker').fill('retained-codex-draft');
  await page.locator('[name=backend_worker]').selectOption('claude');
  await page.locator('[name=backend_lead]').selectOption('cursor');
  await page.locator('#settings-form button[type=submit]').click();
  await page.waitForFunction(()=>!document.querySelector('#settings-form button[type=submit]').disabled);
  assert.equal(saves.at(-1).backends.worker,'claude');assert.equal(saves.at(-1).backends.lead,'cursor');
  assert.equal(saves.at(-1).models.worker,'retained-codex-draft');assert.equal(saves.at(-1).reasoning.worker,'high');
  await page.reload();await page.locator('[data-view=settings]').click();await page.locator('[name=backend_worker]').waitFor();
  assert.equal(await page.locator('[name=backend_worker]').inputValue(),'claude');
  assert.equal(await page.locator('#model-worker').isVisible(),false);
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'/tmp/supersurfer-backend-settings.png'});
  console.log('PASS one provider section, aligned responsive defaults, honest provider controls, saved values and reload');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

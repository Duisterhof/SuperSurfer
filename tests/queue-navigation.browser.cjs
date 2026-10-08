// Keyboard navigation remains usable when the queue is below a large host list.
'use strict';
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{let browser;try{
 browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:900}}),calls=[],errors=[];page.setDefaultTimeout(10000);page.on('pageerror',error=>errors.push(error.message));
 const now=Date.now()/1000,runs=Array.from({length:200},(_,n)=>({id:'queued-'+n,name:'Arm '+n,status:'queued',ready:true,gpu_count:1,created:now-n,queue_order:n+1}));
 const data={connected:true,read_only:false,projects:[],experiments:[],agents:[],runs:[...runs,{id:'active',name:'Running',status:'running',gpu_count:1},{id:'done',name:'Done',status:'succeeded',gpu_count:1}],queue:{paused:false,run_ids:runs.map(row=>row.id)},monitoring:{},settings:{models:{},reasoning:{},approval_mode:'ask'},hosts:Array.from({length:40},(_,n)=>({id:'h'+n,name:'Node '+n,gpus:[0],devices:[{index:0,allowed:true,occupied:false,stale:false}],status:'online',stale:false,observed_at:now}))};
 await page.addInitScript(()=>localStorage.setItem('supersurfer-workspace',JSON.stringify({view:'compute',chatVisible:false})));
 await page.route('http://queue-navigation.test/**',route=>{
  const url=new URL(route.request().url());let body={};
  if(url.pathname==='/api/account')body={account:{type:'chatgpt'},login_required:false};
  else if(url.pathname==='/api/state')body=data;
  else if(url.pathname==='/api/chat')body={messages:[],busy:false,tasks:[],questions:[],approvals:[]};
  else if(url.pathname==='/api/models')body={models:[]};
  else if(url.pathname==='/api/action'){
   const call=route.request().postDataJSON();if(call.op==='settings.save'){Object.assign(data.settings,call.params);return route.fulfill({json:data.settings});}calls.push(call);assert.equal(call.op,'run.move');
   const ids=data.queue.run_ids;ids.splice(ids.indexOf(call.params.run_id),1);ids.splice(ids.indexOf(call.params.before_id),0,call.params.run_id);
  }else if(!url.pathname.startsWith('/api/')){
   const file=path.join(__dirname,'../ui',url.pathname==='/'?'index.html':url.pathname.slice(1));
   return route.fulfill({contentType:{'.js':'text/javascript','.css':'text/css','.json':'application/json'}[path.extname(file)]||'text/html',body:fs.readFileSync(file)});
  }
  return route.fulfill({json:body});
 });
 await page.goto('http://queue-navigation.test/');await page.locator('[data-host=h39]').waitFor();
 assert.ok(await page.locator('#compute-runs-heading').evaluate(el=>el.getBoundingClientRect().top>innerHeight*2));
 const before=[...data.queue.run_ids];await page.getByRole('button',{name:'Show 200 queued runs',exact:true}).focus();await page.keyboard.press('Enter');
 assert.equal(await page.locator('.run-row').count(),200);assert.deepEqual(data.queue.run_ids,before);assert.deepEqual(calls,[]);
 assert.equal(await page.evaluate(()=>document.activeElement.id),'compute-runs-heading');
 assert.ok(await page.locator('#compute-runs-heading').evaluate(el=>{const r=el.getBoundingClientRect();return r.top>=0&&r.bottom<innerHeight;}));
 console.log('PASS keyboard queue shortcut selects waiting runs, focuses/scolls below40 nodes and does not mutate scheduler order');
 const button=page.locator('[data-run=queued-3] [data-action=move-run-up]');await button.focus();
 for(let expected=2;expected>=1;expected--){
  await page.keyboard.press('Enter');await page.waitForFunction(index=>document.querySelectorAll('.run-row')[index].dataset.run==='queued-3',expected);
  await page.waitForFunction(()=>document.activeElement.dataset.action==='move-run-up'&&document.activeElement.dataset.id==='queued-3');
 }
 await page.keyboard.press('Enter');await page.waitForFunction(()=>document.querySelector('.run-row').dataset.run==='queued-3');
 await page.waitForFunction(()=>document.activeElement.dataset.run==='queued-3');
 assert.equal(calls.length,3);assert.ok(await page.locator('[data-run=queued-3] [data-action=move-run-up]').isDisabled());
 assert.equal(await page.locator('#modal').evaluate(el=>el.open),false);
 await page.keyboard.press('Enter');await page.locator('#modal[open]').waitFor();assert.equal(await page.locator('.run-stat').count(),0);
 assert.deepEqual(errors,[]);console.log('PASS repeated keyboard reorder retains the same button, falls back to first row, and opens its detail without extra mutations');
}finally{await browser?.close();}})().catch(error=>{console.error(error);process.exitCode=1;});

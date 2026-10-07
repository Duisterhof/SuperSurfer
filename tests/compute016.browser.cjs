'use strict';
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 try{
 const page=await browser.newPage({viewport:{width:1680,height:1050}}),errors=[],calls=[];
 page.on('pageerror',error=>errors.push(error.message));
 const now=Date.now()/1000,device=(index,extra={})=>({index,name:'NVIDIA A100 80GB',allowed:true,occupied:false,stale:false,memory_total_mib:81920,memory_free_mib:80000,utilization:0,...extra});
 const host=(id,gpus,devices,extra={})=>({id,name:id,target:id.toLowerCase(),gpus,devices,stale:false,status:'online',observed_at:now,age_seconds:25,next_refresh_at:now+275,...extra});
 const indices=Array.from({length:8},(_,i)=>i);
 const hosts=[host('Trinity',indices,[device(0),device(1,{occupied:true}),device(2,{reserved_by:'run_fixture'}),device(4,{stale:true}),device(5,{allowed:false}),device(6,{occupied:true}),device(7),device(9,{allowed:false})]),host('Tulip',[0,1],[device(0),device(1)],{stale:true}),host('Offline',[0,1],[device(0),device(1)],{error:'Connection refused',status:'offline'}),host('CPU',[],[]),host('A very long machine name that should never overflow',indices,indices.map(i=>device(i)))];
 for(let n=6;n<=12;n++)hosts.push(host('Node-'+String(n).padStart(2,'0'),indices,indices.map(i=>device(i,{occupied:i%2===1}))));
 const data={connected:true,read_only:false,projects:[],experiments:[],runs:[],agents:[],hosts,queue:{paused:false,run_ids:[]},monitoring:{},settings:{models:{},reasoning:{},approval_mode:'ask'},updated_at:now};
 await page.addInitScript(()=>localStorage.setItem('supersurfer-workspace',JSON.stringify({view:'compute',chatVisible:false})));
 await page.route('http://capacity.test/**',async route=>{
  const url=new URL(route.request().url());let body={};
  if(url.pathname==='/api/account')body={account:{type:'chatgpt'},login_required:false};
  else if(url.pathname==='/api/state')body=data;
  else if(url.pathname==='/api/action'){const call=route.request().postDataJSON();calls.push(call);if(call.op==='compute.refresh'){hosts[0].devices[1].occupied=false;}}
  else if(url.pathname==='/api/chat')body={messages:[],tasks:[],questions:[],approvals:[],busy:false};
  else if(url.pathname==='/api/models')body={models:[]};
  else if(!url.pathname.startsWith('/api/')){const file=path.join(__dirname,'../ui',url.pathname==='/'?'index.html':url.pathname.slice(1));return route.fulfill({contentType:{'.js':'text/javascript','.css':'text/css','.json':'application/json'}[path.extname(file)]||'text/html',body:fs.readFileSync(file)});}
  return route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('http://capacity.test/');await page.locator('[data-host=Trinity]').waitFor();
 assert.equal(await page.locator('.host-list .host-card').count(),12);
 assert.equal(await page.locator('.gpu-slot').count(),76);
 assert.equal(await page.locator('.gpu-slot[data-availability=free]').count(),38);
 assert.equal(await page.locator('.gpu-slot[data-availability=unknown]').count(),7);
 assert.equal(await page.locator('[data-host=Trinity] [data-gpu="2"]').getAttribute('data-availability'),'reserved');
 for(const index of [3,4,5])assert.equal(await page.locator(`[data-host=Trinity] [data-gpu="${index}"]`).getAttribute('data-availability'),'unknown');
 assert.equal(await page.locator('[data-host=Trinity] [data-gpu="9"]').count(),0,'Unregistered devices must not enter the capacity strip');
 assert.equal(await page.locator('[data-host=CPU] .host-count').innerText(),'CPU only');
 assert.ok((await page.locator('[data-host=Trinity] .host-count').innerText()).startsWith('2 / 8'));
 assert.ok((await page.locator('.compute-summary').innerText()).includes('38\nObserved available\n7 unknown'));
 const layout=await page.evaluate(()=>({rows:[...document.querySelectorAll('.compact-host>summary')].map(el=>el.getBoundingClientRect().height),bottom:document.querySelector('.host-list').getBoundingClientRect().bottom,runs:document.querySelector('.queue-header').getBoundingClientRect().top}));
 assert.ok(layout.rows.every(height=>height<=58),JSON.stringify(layout));assert.ok(layout.bottom<1050,JSON.stringify(layout));assert.ok(layout.bottom<layout.runs);
 assert.equal(await page.locator('.compact-host[open]').count(),0);
 const output=path.resolve(process.env.SUPERSURFER_QA_OUTPUT||path.join(__dirname,'../../../work'));
 await page.screenshot({path:path.join(output,'ui016-compute.png')});
 console.log('PASS 12 visible compact nodes, one bar per registered GPU, conservative free counts, reservations, stale/partial/offline readings and CPU-only nodes');
 await page.locator('[data-host=Trinity]>summary').click();await page.getByText('Not registered',{exact:true}).first().waitFor();
 await page.locator('[data-host=Trinity]>summary').click();
 await page.getByRole('button',{name:'Refresh availability',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('[data-host=Trinity] [data-gpu="1"]').dataset.availability==='free');assert.equal(calls.filter(call=>call.op==='compute.refresh').length,1);
 console.log('PASS expanded memory/utilization detail and availability refresh updates counts and GPU bars');
 await page.setViewportSize({width:1050,height:850});
 await page.evaluate(()=>{document.documentElement.dataset.theme='dark';});
 const fits=await page.evaluate(()=>['#main','.host-list',...Array.from({length:12},(_,i)=>`.host-card:nth-child(${i+1})`)].map(selector=>{const el=document.querySelector(selector);return{selector,width:el.clientWidth,scroll:el.scrollWidth};}));assert.ok(fits.every(item=>item.scroll<=item.width+1),JSON.stringify(fits));
 await page.screenshot({path:path.join(output,'ui016-compute-narrow.png')});assert.deepEqual(errors,[]);
 console.log('PASS narrow dark layout without horizontal overflow or JavaScript errors');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

'use strict';
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1100}});page.setDefaultTimeout(10000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const scope='experiment:e12';let name='E12 worker',taskStatus='working',archived=false,refreshes=0,failRefresh=false;const calls=[];
 const exp={id:'e12',project_id:'p1',name:'E12',summary:'Compact future forecasting',status:'running',version:1,markdown:'# Old launch logs\n\nHISTORICAL-NOISE',pages:[{id:'page_123abc',title:'Method details',version:'v1'}],brief:{version:1,objective:'Does compression preserve action information?',method:'Eight tasks, fifty scenes each.',findings:'Scoring in progress. No final result.',next_steps:'Produce failure videos.',activity:[{at:1,text:'Scoring started.'}]},wandb_url:'https://wandb.ai/test/vla/groups/e12'};
 const data={connected:true,read_only:false,projects:[{id:'p1',name:'VLA',repo:'/tmp/vla',initialized:true}],experiments:[exp],runs:[],hosts:[],agents:[],queue:{paused:false,run_ids:[]},monitoring:{},settings:{models:{manager:'',lead:'',worker:''},reasoning:{manager:'medium',lead:'medium',worker:'medium'},approval_mode:'ask',timezone:'America/New_York'}};
 await page.addInitScript(()=>{if(window!==window.top)return;localStorage.setItem('supersurfer-workspace',JSON.stringify({view:'workspace',projectId:'p1',experimentId:'e12',tab:'overview',chatVisible:true}));});
 await page.route('http://workspace.test/**',async route=>{
  const req=route.request(),url=new URL(req.url());let body={};
  if(url.pathname==='/api/state')body=data;
  else if(url.pathname==='/api/experiment')body=exp;
  else if(url.pathname==='/api/experiment-agents')body={selected_scope:scope,agents:[{scope,name,archived,owner:'supersurfer',status:'completed',task_state:taskStatus==='completed'?'completed':'incomplete',busy:false,can_resume:true}]};
  else if(url.pathname==='/api/chat')body={archived,busy:true,status:'working',agent:{name,model:'fixture'},tasks:[{id:'t1',title:'Produce failure videos',status:taskStatus,summary:taskStatus==='completed'?'Playback verified.':'Implementation in progress.'}],messages:[{id:'m1',role:'assistant',text:'Current work.',created:1}],questions:[],approvals:[],preferences:{editable:true,defaults:{model:'',reasoning:'medium',approval_mode:'ask'},overrides:{},effective:{model:'fixture',reasoning:'medium',approval_mode:'ask'},supported_reasoning:['medium']}};
  else if(url.pathname==='/api/models')body={models:[{id:'fixture',displayName:'Fixture',supportedReasoningEfforts:[{reasoningEffort:'medium'}]}]};
  else if(url.pathname==='/api/worker-wakeups')body={rules:[]};
  else if(url.pathname==='/api/results')body={pages:[{id:'result_123',title:'Interactive evidence',preview_url:'/result-preview/fixture123'}]};
  else if(url.pathname==='/api/experiment-page')body={id:'page_123abc',title:'Method details',version:'v1',markdown:'# Architecture\n\nA focused explanation.\n\n<script>window.PWNED=true</script>'};
  else if(url.pathname==='/result-preview/fixture123')return route.fulfill({contentType:'text/html',headers:{'Content-Security-Policy':"sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; connect-src https:; style-src 'unsafe-inline'; frame-ancestors 'self'"},body:`<!doctype html><body><h1>Measured evidence</h1><button id="counter">0</button><div id="isolation"></div><script>let n=0;document.querySelector('#counter').onclick=()=>document.querySelector('#counter').textContent=++n;try{parent.document.body.dataset.hacked='yes';document.querySelector('#isolation').textContent='unsafe';}catch{document.querySelector('#isolation').textContent='parent denied';}</script>`});
  else if(url.pathname==='/api/action'){
   const call=req.postDataJSON();calls.push(call.op);if(call.op==='chat.archive'){archived=call.params.archived;body={scope,archived};}else if(call.op==='compute.refresh'){refreshes++;if(failRefresh)return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Manager unavailable'})});body={requested:true};}else if(call.op==='chat.rename')name=call.params.name;else if(call.op==='experiment.brief.save'){Object.assign(exp.brief,call.params);exp.brief.version++;}else if(call.op!=='settings.save')throw Error('Unexpected mutation '+call.op);
  }else if(!url.pathname.startsWith('/api/')){const file=path.join(__dirname,'../ui',url.pathname==='/'?'index.html':url.pathname.slice(1));return route.fulfill({contentType:{'.js':'text/javascript','.css':'text/css','.json':'application/json'}[path.extname(file)]||'text/html',body:fs.readFileSync(file)});}
  return route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('http://workspace.test/');
 await page.locator('#chat-name').getByText('E12 worker',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Archive agent chat',exact:true}).click();
 await page.getByRole('button',{name:'Restore chat',exact:true}).waitFor();
 assert.equal(await page.locator('#chat-form').isVisible(),false);
 await page.getByRole('button',{name:'Expand agents section',exact:true}).click();
 assert.equal(await page.locator('.agent-list-row').count(),0);
 await page.getByRole('button',{name:'Archived · 1',exact:true}).click();
 assert.equal(await page.locator('.agent-list-row').count(),1);
 assert.ok((await page.locator('#chat-session-state').innerText()).includes('monitoring are preserved'));
 assert.equal(calls.filter(c=>c==='chat.stop'||c==='chat.send').length,0);
 await page.reload();await page.getByRole('button',{name:'Restore chat',exact:true}).waitFor();
 await page.getByRole('button',{name:'Restore chat',exact:true}).click();
 await page.getByRole('button',{name:'Archive agent chat',exact:true}).waitFor();
 assert.equal(await page.locator('#chat-form').isVisible(),true);
 assert.equal(await page.getByRole('button',{name:'Archived · 1',exact:true}).count(),0);
 console.log('PASS archive hides chat, saved history remains accessible, restore survives reload, no stop/send calls');
 await page.locator('[data-view="compute"]').click();
 await page.getByRole('button',{name:'Refresh availability',exact:true}).click();
 await page.getByText('GPU refresh requested. Readings update as each machine responds.',{exact:true}).waitFor();
 assert.equal(refreshes,1);assert.equal(await page.getByRole('button',{name:'Refresh availability',exact:true}).isEnabled(),true);
 failRefresh=true;await page.getByRole('button',{name:'Refresh availability',exact:true}).click();
 await page.locator('#toast').getByText('Manager unavailable',{exact:true}).waitFor();
 assert.equal(await page.getByRole('button',{name:'Refresh availability',exact:true}).isEnabled(),true);
 assert.deepEqual(errors,[]);console.log('PASS real compute refresh action, failure surfaced and retry remains available');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

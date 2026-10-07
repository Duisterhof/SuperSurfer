'use strict';
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1100}});page.setDefaultTimeout(10000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const scope='experiment:e12';let name='E12 worker',taskStatus='working';
 const exp={id:'e12',project_id:'p1',name:'E12',summary:'Compact future forecasting',status:'running',version:1,markdown:'# Old launch logs\n\nHISTORICAL-NOISE',pages:[{id:'page_123abc',title:'Method details',version:'v1'}],brief:{version:1,objective:'Does compression preserve action information?',method:'Eight tasks, fifty scenes each.',findings:'Scoring in progress. No final result.',next_steps:'Produce failure videos.',activity:[{at:1,text:'Scoring started.'}]},wandb_url:'https://wandb.ai/test/vla/groups/e12'};
 const data={connected:true,read_only:false,projects:[{id:'p1',name:'VLA',repo:'/tmp/vla',initialized:true}],experiments:[exp],runs:[],hosts:[],agents:[],queue:{paused:false,run_ids:[]},monitoring:{},settings:{models:{manager:'',lead:'',worker:''},reasoning:{manager:'medium',lead:'medium',worker:'medium'},approval_mode:'ask',timezone:'America/New_York'}};
 await page.addInitScript(()=>{if(window!==window.top)return;localStorage.setItem('supersurfer-workspace',JSON.stringify({view:'workspace',projectId:'p1',experimentId:'e12',tab:'overview',chatVisible:true}));});
 await page.route('http://workspace.test/**',async route=>{
  const req=route.request(),url=new URL(req.url());let body={};
  if(url.pathname==='/api/state')body=data;
  else if(url.pathname==='/api/experiment')body=exp;
  else if(url.pathname==='/api/experiment-agents')body={selected_scope:scope,agents:[{scope,name,owner:'supersurfer',status:'completed',task_state:taskStatus==='completed'?'completed':'incomplete',busy:false,can_resume:true}]};
  else if(url.pathname==='/api/chat')body={busy:false,status:'completed',agent:{name,model:'fixture'},tasks:[{id:'t1',title:'Produce failure videos',status:taskStatus,summary:taskStatus==='completed'?'Playback verified.':'Implementation in progress.'}],messages:[{id:'m1',role:'assistant',text:'Current work.',created:1}],questions:[],approvals:[],preferences:{editable:true,defaults:{model:'',reasoning:'medium',approval_mode:'ask'},overrides:{},effective:{model:'fixture',reasoning:'medium',approval_mode:'ask'},supported_reasoning:['medium']}};
  else if(url.pathname==='/api/models')body={models:[{id:'fixture',displayName:'Fixture',supportedReasoningEfforts:[{reasoningEffort:'medium'}]}]};
  else if(url.pathname==='/api/worker-wakeups')body={rules:[]};
  else if(url.pathname==='/api/results')body={pages:[{id:'result_123',title:'Interactive evidence',preview_url:'/result-preview/fixture123'}]};
  else if(url.pathname==='/api/experiment-page')body={id:'page_123abc',title:'Method details',version:'v1',markdown:'# Architecture\n\nA focused explanation.\n\n<script>window.PWNED=true</script>'};
  else if(url.pathname==='/result-preview/fixture123')return route.fulfill({contentType:'text/html',headers:{'Content-Security-Policy':"sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; connect-src https:; style-src 'unsafe-inline'; frame-ancestors 'self'"},body:`<!doctype html><body><h1>Measured evidence</h1><button id="counter">0</button><div id="isolation"></div><script>let n=0;document.querySelector('#counter').onclick=()=>document.querySelector('#counter').textContent=++n;try{parent.document.body.dataset.hacked='yes';document.querySelector('#isolation').textContent='unsafe';}catch{document.querySelector('#isolation').textContent='parent denied';}</script>`});
  else if(url.pathname==='/api/action'){
   const call=req.postDataJSON();if(call.op==='chat.rename')name=call.params.name;else if(call.op==='experiment.brief.save'){Object.assign(exp.brief,call.params);exp.brief.version++;}else if(call.op!=='settings.save')throw Error('Unexpected mutation '+call.op);
  }else if(!url.pathname.startsWith('/api/')){const file=path.join(__dirname,'../ui',url.pathname==='/'?'index.html':url.pathname.slice(1));return route.fulfill({contentType:{'.js':'text/javascript','.css':'text/css','.json':'application/json'}[path.extname(file)]||'text/html',body:fs.readFileSync(file)});}
  return route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('http://workspace.test/');
 await page.getByText('Does compression preserve action information?',{exact:true}).waitFor();
 assert.equal(await page.getByText('HISTORICAL-NOISE',{exact:true}).isVisible(),false);
 assert.equal(await page.locator('.agent-list-row small').textContent(),'Idle');
 assert.equal(await page.locator('#chat-tasks details').getAttribute('open'),null);
 await page.locator('#chat-tasks summary').click();
 await page.getByText('Produce failure videos',{exact:true}).waitFor();
 assert.equal(await page.locator('.agent-list').isVisible(),false);await page.getByRole('button',{name:'Expand agents section',exact:true}).click();assert.equal(await page.locator('.agent-list').isVisible(),true);await page.getByRole('button',{name:'Collapse agents section',exact:true}).click();
 console.log('PASS compact brief, separate technical history, task progress and persistent Idle agent');
 await page.getByRole('button',{name:'Rename agent',exact:true}).click();
 await page.getByLabel('Agent name',{exact:true}).fill('E12 failure analysis');
 await page.getByRole('button',{name:'Save name',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#chat-name').textContent==='E12 failure analysis');
 taskStatus='completed';await page.getByRole('button',{name:'Refresh connection',exact:true}).click();
 await page.getByText('Playback verified.',{exact:true}).waitFor();
 assert.equal(await page.locator('.agent-list-row small').textContent(),'Idle');
 console.log('PASS rename persists through refresh; completed deliverable does not finish conversation');
 await page.getByRole('button',{name:'Method details',exact:true}).click();
 await page.getByRole('heading',{name:'Architecture',exact:true}).waitFor();
 assert.equal(await page.evaluate(()=>window.PWNED),undefined);
 console.log('PASS custom Markdown tab renders without executing embedded script');
 await page.getByRole('button',{name:'Results',exact:true}).click();
 const frame=page.frameLocator('#result-preview');await frame.getByText('parent denied',{exact:true}).waitFor();
 await frame.locator('#counter').click();assert.equal(await frame.locator('#counter').innerText(),'1');
 await page.getByRole('button',{name:'Refresh connection',exact:true}).click();
 assert.equal(await frame.locator('#counter').innerText(),'1');
 assert.equal(await page.evaluate(()=>document.body.dataset.hacked),undefined);
 console.log('PASS interactive HTML executes in isolated frame and retains widget state across refresh');
 await page.getByRole('button',{name:'Overview',exact:true}).click();
 await page.getByRole('button',{name:'Edit brief',exact:true}).click();
 await page.getByLabel('Next steps',{exact:true}).fill('Analyze the final score.');
 await page.getByRole('button',{name:'Save brief',exact:true}).click();
 await page.getByText('Analyze the final score.',{exact:true}).waitFor();
 await page.screenshot({path:path.join(__dirname,'../../../work/ui019-experiment-brief.png'),fullPage:true});
 await page.setViewportSize({width:850,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 assert.deepEqual(errors,[]);console.log('PASS brief editing, narrow layout and no JavaScript errors');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

'use strict';
// Reproduces the active YOLO/steering layout from the reported Mac screenshot.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:2});
  const out=process.env.SUPERSURFER_QA_OUTPUT||path.resolve(__dirname,'../../../work/release015-checks');fs.mkdirSync(out,{recursive:true});
  const errors=[],calls=[];let busy=true,approval=false,question=false,settingsError=false,sendPending=false;
  const overrides={model:'gpt-6-astra',reasoning:'high',approval_mode:'yolo',fast_mode:false};
  const runtime={active:true,approval_mode:'yolo',runtime_approval_mode:'ask',active_sandbox:'workspace-write'};
  const data={connected:true,read_only:false,projects:[{id:'p1',name:'VLA',repo:'/tmp/vla',initialized:true}],experiments:[],runs:[],hosts:[],agents:[],queue:{paused:false,run_ids:[]},monitoring:{},settings:{models:{manager:'',lead:'',worker:''},reasoning:{manager:'medium',lead:'medium',worker:'medium'},approval_mode:'ask',timezone:'America/New_York'}};
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('http://composer.test/**',async route=>{
   const req=route.request(),url=new URL(req.url());let body={};
   if(url.pathname==='/api/state')body=data;
   else if(url.pathname==='/api/project-agents')body={agents:[{scope:'project:p1',name:'VLA lead',owner:'supersurfer',busy,status:busy?'working':'idle'}]};
   else if(url.pathname==='/api/chat')body={busy,steerable:busy,agent:{name:'VLA lead'},messages:[{id:'m1',role:'assistant',text:'Comparing the measured training curves.',created:1}],questions:question?[{id:'q',status:'pending',can_answer:true,questions:[{id:'choice',question:'Which comparison?',options:[]}]}]:[],approvals:approval?[{id:'a',status:'pending',message:'Read the results?'}]:[],preferences:{editable:true,role:'lead',defaults:{model:'gpt-6-astra',reasoning:'medium',approval_mode:'ask'},overrides,effective:{...overrides},supported_reasoning:['medium','high','xhigh'],runtime:{...runtime,active:busy},...(settingsError?{error:'Settings could not be saved. Try again.'}:{})}};
   else if(url.pathname==='/api/models')body={models:[{id:'gpt-6-astra',displayName:'GPT-6 Astra',supported_reasoning:['medium','high','xhigh']},{id:'long-model-name',displayName:'An unusually long model display name for overflow coverage',supported_reasoning:['medium','high','xhigh']}]};
   else if(url.pathname==='/api/action'){
    const call=req.postDataJSON();calls.push(call);
    if(call.op==='chat.steer'){
     sendPending=true;while(sendPending)await new Promise(resolve=>setTimeout(resolve,20));
     body={accepted:true,turn_id:'turn1'};
    }else if(call.op==='chat.stop'){busy=false;body={stopped:true};}
    else if(call.op==='chat.settings'){for(const key of ['model','reasoning','approval_mode','fast_mode'])if(key in call.params)overrides[key]=call.params[key];body={};}
    else if(call.op==='settings.save')Object.assign(data.settings,call.params);
    else throw new Error('Unexpected action '+call.op);
   }else if(!url.pathname.startsWith('/api/')){
    const file=path.join(__dirname,'../ui',url.pathname==='/'?'index.html':url.pathname.slice(1));
    return route.fulfill({contentType:{'.js':'text/javascript','.css':'text/css','.json':'application/json','.woff2':'font/woff2'}[path.extname(file)]||'text/html',body:fs.readFileSync(file)});
   }
   return route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.goto('http://composer.test/');await page.locator('#chat-model').waitFor();
  const refresh=async()=>{await page.getByRole('button',{name:'Refresh connection',exact:true}).click();};
  const geometry=async(wide)=>{
   const g=await page.evaluate(()=>{
    const box=el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height};};
    const ids=['#chat-model','#chat-reasoning','#chat-approval-mode','.chat-fast-button','.chat-defaults-button','#chat-send','#chat-stop'];
    return {form:box(document.querySelector('#chat-form')),controls:ids.filter(id=>!document.querySelector(id).hidden).map(id=>({id,...box(document.querySelector(id))})),note:document.querySelector('#chat-preference-notices').hidden?null:box(document.querySelector('#chat-preference-notices')),icon:box(document.querySelector('#chat-send svg, #chat-send .spinner')),width:innerWidth,height:innerHeight};
   });
   for(const r of g.controls){
    assert.ok(r.x>=g.form.x&&r.right<=g.form.right+1&&r.y>=g.form.y&&r.bottom<=g.form.bottom,`Outside composer: ${JSON.stringify(g)}`);
    for(const other of g.controls)if(other.id!==r.id)assert.ok(Math.min(r.right,other.right)-Math.max(r.x,other.x)<1||Math.min(r.bottom,other.bottom)-Math.max(r.y,other.y)<1,`Overlapping controls: ${JSON.stringify(g)}`);
   }
   const send=g.controls.find(r=>r.id==='#chat-send');assert.ok(g.icon.x>=send.x&&g.icon.right<=send.right&&g.icon.y>=send.y&&g.icon.bottom<=send.bottom,'Clipped action icon');
   assert.ok(g.form.right<=g.width+1&&g.form.bottom<=g.height+1,'Composer outside window');
   if(g.note)assert.ok(g.note.y>=Math.max(...g.controls.map(r=>r.bottom)),`Notice shares control row: ${JSON.stringify(g)}`);
   if(wide)assert.ok(Math.max(...g.controls.map(r=>r.y+r.height/2))-Math.min(...g.controls.map(r=>r.y+r.height/2))<1,'Controls not aligned');
   return g;
  };
  await page.locator('#chat-input').fill('Keep this draft while resizing.');
  assert.equal(await page.locator('#chat-send').getAttribute('aria-label'),'Steer current work');
  assert.equal((await page.locator('#chat-send').innerText()).trim(),'');
  await geometry(false);
  assert.ok((await page.locator('#chat-preference-notices').innerText()).includes('Full access starts next turn'));
  await page.locator('#chat-form').screenshot({path:path.join(out,'composer-narrow.png')});
  await page.getByRole('button',{name:'Maximize agent chat',exact:true}).click();
  for(const size of [{width:1840,height:1100},{width:1100,height:760},{width:700,height:800},{width:500,height:760},{width:390,height:760}]){
   await page.setViewportSize(size);await geometry(size.width>620);
   assert.equal(await page.locator('#chat-input').inputValue(),'Keep this draft while resizing.');
  }
  await page.setViewportSize({width:1440,height:900});await geometry(true);
  await page.locator('#chat-form').screenshot({path:path.join(out,'composer-wide.png')});
  await page.locator('#chat-send').click();await page.waitForFunction(()=>!!document.querySelector('#chat-send .spinner'));await geometry(true);
  assert.equal(await page.locator('#chat-send').isDisabled(),true);sendPending=false;
  await page.waitForFunction(()=>!document.querySelector('#chat-send .spinner'));
  assert.equal(calls.filter(call=>call.op==='chat.steer').length,1);
  assert.equal(calls.some(call=>call.op==='chat.stop'),false);
  console.log('PASS active YOLO transition, aligned wide/compact narrow rows, draft preservation, unclipped steering and pending-send state');
  await page.locator('#chat-model').selectOption('long-model-name');await page.locator('#chat-input').click();
  await page.waitForFunction(()=>document.querySelector('#chat-model').value==='long-model-name'&&!document.querySelector('#chat-model').disabled);
  await geometry(true);await page.getByRole('button',{name:'Restore agent panel',exact:true}).click();await geometry(false);
  settingsError=true;await refresh();await page.getByText('Settings could not be saved. Try again.',{exact:true}).waitFor();await geometry(false);settingsError=false;
  runtime.approval_mode='ask';await refresh();await page.getByRole('button',{name:'Apply now',exact:true}).waitFor();await geometry(false);runtime.approval_mode='yolo';
  question=true;await refresh();await page.locator('.question-card').waitFor();assert.equal(await page.locator('#chat-send').isDisabled(),true);await geometry(false);question=false;
  approval=true;await refresh();await page.locator('.approval-card').waitFor();assert.equal(await page.locator('#chat-send').isDisabled(),true);await geometry(false);approval=false;await refresh();
  await page.getByRole('button',{name:'Stop current work',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#chat-stop').hidden);
  assert.equal(calls.filter(call=>call.op==='chat.stop').length,1);
  assert.equal(await page.locator('#chat-send').getAttribute('aria-label'),'Send message');
  assert.equal(await page.locator('#chat-preference-notices').isVisible(),false);await geometry(false);
  await page.evaluate(()=>document.documentElement.dataset.theme='dark');await geometry(false);
  await page.locator('#chat-form').screenshot({path:path.join(out,'composer-dark.png')});
  assert.deepEqual(errors,[]);
  console.log('PASS long model names, settings error, permission mismatch action, question/approval gating, Stop and idle layout');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

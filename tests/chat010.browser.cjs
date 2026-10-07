'use strict';
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 try {
 const page=await browser.newPage({viewport:{width:1840,height:1100}});page.setDefaultTimeout(10000);
 const errors=[],external=[],fontRequests=[];page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(!r.url().startsWith('http://chat.test/'))external.push(r.url());if(r.url().endsWith('.woff2'))fontRequests.push(r.url());});
 const scope='experiment:e12';let questions=[],approvals=[],taskUpdate=0;
 const equation=String.raw`Inline: \(L_{\text{train}} = \frac{1}{N}\sum_i (y_i-\hat y_i)^2\), and $\alpha_1 + \beta_2$.

$$
\begin{aligned}
x_{t+1} &= A x_t + B u_t \\
L &= \lVert y - \hat{y}\rVert^2
\end{aligned}
$$

\[
\begin{pmatrix}1 & 2 \\ 3 & 4\end{pmatrix}
\]

Keep code literal: `+'`$HOME` and `\\(code\\)`.'+String.raw`

`+'```python\nprice = "$5"\n# $$x^2$$\n```'+String.raw`

Costs $5 and $10; escaped \$20.

Invalid: $\undefinedCommand{x}$.

Untrusted: $\href{javascript:alert(1)}{click}$ and $\includegraphics{https://evil.test/pixel.png}$.

Incomplete streaming: \(x_{t+1}`;
 const messages=[{id:'m1',role:'assistant',text:equation,created:1}];
 const exp={id:'e12',project_id:'p1',name:'E12',summary:'Forecasting',status:'running',version:1,markdown:'Old notes',pages:[],brief:{version:1,objective:'Does it predict?',method:'Measure.',findings:'Pending.',next_steps:'Inspect.',activity:[]}};
 const data={connected:true,read_only:false,projects:[{id:'p1',name:'VLA',repo:'/tmp/vla',initialized:true}],experiments:[exp],runs:[],hosts:[],agents:[],queue:{paused:false,run_ids:[]},monitoring:{},settings:{models:{manager:'',lead:'',worker:''},reasoning:{manager:'medium',lead:'medium',worker:'medium'},approval_mode:'ask',timezone:'America/New_York'}};
 await page.addInitScript(()=>{window.superSurferDesktop={};if(!localStorage.getItem('supersurfer-workspace'))localStorage.setItem('supersurfer-workspace',JSON.stringify({view:'workspace',projectId:'p1',experimentId:'e12',tab:'overview',chatVisible:true}));});
 await page.route('http://chat.test/**',async route=>{
  const url=new URL(route.request().url());let body={};
  if(url.pathname==='/api/state')body=data;
  else if(url.pathname==='/api/experiment')body=exp;
  else if(url.pathname==='/api/experiment-agents')body={selected_scope:scope,agents:[{scope,name:'E12 worker',owner:'supersurfer',status:'completed',task_state:'incomplete',busy:false,can_resume:true},...Array.from({length:9},(_,i)=>({scope:'conversation:'+i,name:'Previous worker '+i,owner:'supersurfer',status:'completed',busy:false}))]};
  else if(url.pathname==='/api/chat')body={busy:!!(questions.length||approvals.length),status:'completed',agent:{name:'E12 worker',model:'fixture'},tasks:[{id:'t1',title:'Evaluate the checkpoint and report measured evidence',status:'working',summary:'Scoring is in progress. '+taskUpdate},{id:'t2',title:'Watch the loss every ten minutes',status:'watching',summary:'Monitoring is enabled.'}],messages,questions,approvals,preferences:{editable:true,defaults:{model:'',reasoning:'medium',approval_mode:'ask'},overrides:{},effective:{model:'fixture',reasoning:'medium',approval_mode:'ask'},supported_reasoning:['medium']}};
  else if(url.pathname==='/api/models')body={models:[{id:'fixture',displayName:'Fixture',supportedReasoningEfforts:[{reasoningEffort:'medium'}]}]};
  else if(url.pathname==='/api/worker-wakeups')body={rules:[]};
  else if(url.pathname==='/api/action'){assert.equal(route.request().postDataJSON().op,'settings.save');}
  else if(!url.pathname.startsWith('/api/')){
   const file=path.join(__dirname,'../ui',url.pathname==='/'?'index.html':url.pathname.slice(1));
   return route.fulfill({contentType:{'.js':'text/javascript','.css':'text/css','.json':'application/json','.woff2':'font/woff2'}[path.extname(file)]||'text/html',headers:{'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'"},body:fs.readFileSync(file)});
  }
  return route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('http://chat.test/');await page.locator('#chat-messages .katex').first().waitFor();
 assert.equal(await page.locator('#chat-messages .katex-display').count(),2);
 assert.ok((await page.locator('#chat-messages').innerText()).includes('undefinedCommand'));
 assert.equal(await page.locator('#chat-messages pre code').innerText(),'price = "$5"\n# $$x^2$$');
 assert.equal(await page.locator('#chat-messages code .katex').count(),0);
 const text=await page.locator('#chat-messages').innerText();
 assert.ok(text.includes('Costs $5 and $10; escaped $20.'));
 assert.ok(text.includes('Incomplete streaming: \\(x_{t+1}'));
 assert.equal(await page.locator('#chat-messages a[href^="javascript:"], #chat-messages img').count(),0);
 await page.evaluate(()=>document.fonts.ready);assert.ok(fontRequests.length>0);assert.deepEqual(external,[]);
 console.log('PASS inline/display/matrix math, literal code/currency, incomplete or invalid math, isolated TeX and local fonts under app CSP');
 assert.equal(await page.locator('#chat-tasks details').evaluate(el=>el.open),false);
 assert.ok((await page.locator('.chat-header').boundingBox()).height<=58,'Worker header too tall');
 assert.ok((await page.locator('#chat-agent-list').boundingBox()).height<=34,'Collapsed agents too tall');
 await page.locator('#chat-tasks summary').click();taskUpdate++;
 await page.getByRole('button',{name:'Refresh connection',exact:true}).click();
 await page.getByText('Scoring is in progress. '+taskUpdate,{exact:true}).waitFor();
 assert.equal(await page.locator('#chat-tasks details').evaluate(el=>el.open),true,'Polling must retain an intentional expansion');
 await page.locator('#chat-tasks summary').click();
 console.log('PASS collapsed deliverables by default, compact worker/agent headers and retained explicit expansion');
 await page.getByRole('button',{name:'Maximize agent chat',exact:true}).click();
 await page.locator('#chat-input').fill('Keep this unsent direction.');
 const checkLayout=async()=>{
  const g=await page.evaluate(()=>{
   const box=s=>{const e=document.querySelector(s),r=e.getBoundingClientRect(),c=getComputedStyle(e);return {x:r.x,width:r.width,height:r.height,right:r.right,top:r.top,bottom:r.bottom,inner:r.x+parseFloat(c.paddingLeft),hidden:e.hidden};};
   return {width:innerWidth,height:innerHeight,scroll:document.documentElement.scrollWidth,head:box('.chat-header'),tasks:box('.chat-tasks'),agents:box('.chat-agent-list'),messages:box('.chat-messages'),form:box('.chat-composer'),questions:box('.chat-questions'),approvals:box('.chat-approvals'),breadcrumb:box('.breadcrumb')};
  });
  assert.ok(g.scroll<=g.width+1,JSON.stringify(g));
  for(const s of ['head','tasks','agents','messages']){
   assert.ok(Math.abs(g[s].inner-g.form.x)<2,`${s} misaligned: ${JSON.stringify(g)}`);
   assert.ok(Math.abs((g[s].x+g[s].right)/2-g.width/2)<2,`${s} not centered`);
  }
  for(const s of ['questions','approvals'])if(!g[s].hidden)assert.ok(Math.abs(g[s].inner-g.form.x)<2,`${s} misaligned`);
  assert.ok(g.form.bottom<=g.height+1,'composer clipped: '+JSON.stringify(g));
  assert.ok(g.messages.bottom<=g.form.top+1,'messages overlap composer');
  if(!g.questions.hidden)assert.ok(g.questions.height>=80,'question collapsed: '+JSON.stringify(g));
  assert.ok(g.breadcrumb.x>=100,'breadcrumb overlaps native window controls');
 };
 for(const viewport of [{width:1840,height:1100},{width:1280,height:800},{width:1000,height:680},{width:700,height:850}]){
  await page.setViewportSize(viewport);await checkLayout();
  assert.equal(await page.locator('#chat-input').inputValue(),'Keep this unsent direction.');
 }
 await page.setViewportSize({width:1440,height:1000});
 await page.getByRole('button',{name:'Expand agents section',exact:true}).click();await checkLayout();
 for(const row of await page.locator('.agent-list-row').all())assert.ok((await row.boundingBox()).height<=28,'Agent list row too tall');
 assert.ok((await page.locator('.agent-list').boundingBox()).height<=131,'Agent list consumes transcript space');
 await page.locator('#chat-agent-list').screenshot({path:path.join(__dirname,'../../../work/ui016-agents.png')});
 await page.locator('.chat-header').screenshot({path:path.join(__dirname,'../../../work/ui016-worker.png')});
 await page.getByRole('button',{name:'Collapse agents section',exact:true}).click();
 await page.locator('#chat-tasks summary').click();await checkLayout();await page.locator('#chat-tasks summary').click();
 await page.evaluate(()=>{document.querySelector('#chat-messages').scrollTop=0;});
 await page.screenshot({path:path.join(__dirname,'../../../work/ui010-fullscreen.png')});
 console.log('PASS centered fullscreen sections, Mac titlebar spacing, collapsible panels, resize and retained draft');
 questions=[{id:'q1',status:'pending',can_answer:true,questions:[{id:'choice',question:'Which result should we inspect?',options:[]}]}];
 await page.locator('[data-action=refresh]').dispatchEvent('click');await page.locator('.question-card').waitFor();
 await page.getByRole('textbox',{name:'Which result should we inspect?'}).fill('Inspect the failed scenes.');await checkLayout();
 // Short desktop window must still expose the composer and the scrollable pending question.
 await page.setViewportSize({width:1000,height:680});await page.getByRole('button',{name:'Expand agents section',exact:true}).click();await checkLayout();
 await page.getByRole('button',{name:'Restore agent panel',exact:true}).click();
 assert.equal(await page.locator('#chat-input').inputValue(),'Keep this unsent direction.');
 assert.equal(await page.getByRole('textbox',{name:'Which result should we inspect?'}).inputValue(),'Inspect the failed scenes.');
 await page.getByRole('button',{name:'Maximize agent chat',exact:true}).click();await checkLayout();
 console.log('PASS pending question alignment and draft preservation across fullscreen/restore in a short window');
 assert.deepEqual(errors,[]);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

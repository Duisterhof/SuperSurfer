'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
const {performance}=require('node:perf_hooks'),{install}=require('./fixtures/workspace-demo.cjs');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await install(page,{tab:'overview'});
  if(process.env.SS_BASELINE_APP)await page.route('http://demo.test/app.js',route=>route.fulfill({contentType:'text/javascript',body:fs.readFileSync(process.env.SS_BASELINE_APP)}));
  const count=600,messages=Array.from({length:count},(_,i)=>({id:'message-'+i,role:i%3===0?'user':'assistant',created:1700000000+i,text:'Attempt '+i+'\n\n'+('Compare train and validation losses on the same axes. Preserve the source commit and evaluation protocol.\n\n'.repeat(12))+'| Method | Train | Validation |\n| --- | --- | --- |\n| Baseline | 0.42 | 0.48 |\n| Revised | 0.38 | 0.44 |'}));
  let revision=0,reads=0,notModified=0;
  await page.route('http://demo.test/api/chat?*',route=>{
   reads++;const limit=Number(new URL(route.request().url()).searchParams.get('limit'))||count,tag='W/"fixture-'+revision+'-'+limit+'"';if(route.request().headers()['if-none-match']===tag){notModified++;return route.fulfill({status:304,headers:{ETag:tag}});}
   return route.fulfill({headers:{ETag:tag},json:{scope:'experiment:demo-e14',busy:false,agent:{name:'Research worker'},messages:messages.slice(-limit),message_count:count,questions:[],approvals:[],preferences:{editable:true,defaults:{model:'gpt-6-astra',reasoning:'high',approval_mode:'ask'},overrides:{},effective:{model:'gpt-6-astra',reasoning:'high',approval_mode:'ask'},supported_reasoning:['high']}}});
  });
  const start=performance.now();await page.goto('http://demo.test/');await page.locator('#chat-messages .message').last().getByText('Attempt 599',{exact:true}).waitFor();const initial=performance.now()-start;
  const durations=[];
  for(let i=1;i<=4;i++){
   revision++;messages.at(-1).text+='\n\nProgress sample '+i;
   const start=performance.now();await page.locator('[data-action=refresh]').first().click();await page.locator('#chat-messages').getByText('Progress sample '+i,{exact:true}).waitFor();durations.push(performance.now()-start);
  }
  await page.locator('[data-action=refresh]').first().click();await page.waitForTimeout(100);
  const rendered=await page.locator('#chat-messages .message').count();
  if(!process.env.SS_BASELINE_APP){
   assert.ok(rendered<=100,'Long chats should initially render a bounded recent history');
   const earlier=page.locator('[data-action=earlier-chat]');await earlier.click();await page.waitForFunction(count=>document.querySelectorAll('#chat-messages .message').length>count,rendered);assert.ok(await page.locator('#chat-messages .message').count()>rendered,'Earlier messages must remain accessible');
   assert.ok(notModified>0,'Unchanged authenticated chat reads should use304');
  }
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({case:process.env.SS_BASELINE_APP?'baseline':'optimized',history:count,rendered,initial_ms:Math.round(initial),update_ms:durations.map(Math.round),median_update_ms:Math.round((durations.sort((a,b)=>a-b)[1]+durations[2])/2),reads,not_modified:notModified}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

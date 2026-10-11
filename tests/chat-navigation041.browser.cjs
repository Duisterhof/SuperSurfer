'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {install}=require('./fixtures/workspace-demo.cjs');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));await install(page,{tab:'overview'});
  let releaseEarlier,held=false,canceled=false;
  page.on('requestfailed',request=>{if(new URL(request.url()).pathname==='/api/chat'&&new URL(request.url()).searchParams.get('limit')==='160')canceled=true;});
  await page.route('http://demo.test/api/chat?*',async route=>{
   const query=new URL(route.request().url()).searchParams,scope=query.get('scope'),limit=Number(query.get('limit'))||80;
   if(scope==='experiment:demo-e14'&&limit===160){held=true;await new Promise(resolve=>releaseEarlier=resolve);}
   const second=scope==='project:demo-world',messages=Array.from({length:200},(_,i)=>({id:scope+'-'+i,role:i%2?'assistant':'user',created:1700000000+i,text:(second?'New chat message ':'Previous history ')+i+'\n\n'+('Measured evidence. '.repeat(20))}));
   try{await route.fulfill({json:{scope,busy:false,messages:messages.slice(-limit),message_count:messages.length,questions:[],approvals:[],agent:{name:second?'New project lead':'Research worker'},preferences:{effective:{model:'gpt-6-astra',reasoning:'high',approval_mode:'ask'}}}});}catch(error){if(!canceled)throw error;}
  });
  await page.goto('http://demo.test/');await page.getByText('Previous history 199',{exact:false}).waitFor();
  await page.locator('[data-action=earlier-chat]').click();while(!held)await page.waitForTimeout(10);
  await page.locator('#project-tree [data-project=demo-world]').click();await page.getByText('New chat message 199',{exact:false}).waitFor();
  releaseEarlier();await page.waitForTimeout(150);
  assert.equal(canceled,true,'Leaving a chat must cancel its pending history read');
  assert.equal(await page.locator('#chat-messages').getByText('Previous history 199',{exact:false}).count(),0);
  const scroll=await page.locator('#chat-messages').evaluate(el=>({top:el.scrollTop,height:el.scrollHeight,client:el.clientHeight}));
  assert.ok(scroll.height-scroll.top-scroll.client<5,'An earlier-history reply must not move the new chat away from its bottom');
  assert.deepEqual(errors,[]);console.log('PASS superseded history read is canceled; switching scopes retains the new chat and its bottom scroll position');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

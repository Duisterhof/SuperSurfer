'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {install}=require('./fixtures/workspace-demo.cjs');
(async()=>{
 const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:950}});await install(page);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const stamp=Date.now()/1000,messages=[{id:'user',role:'user',text:'Monitor the existing run.',created:stamp-1000}];
  for(let i=0;i<60;i++)messages.push({id:'check'+i,role:i%2?'system':'user',assignment:true,...(i%2?{background_check:{rule_id:'w1',kind:'interval'}}:{}),text:'Perform this worker check explicitly scheduled by the user. Stay within the saved task;\n\nSaved task:\nMonitor training.\n\nWakeup evidence:\n{}',created:stamp+i}, {id:'start'+i,role:'assistant',text:'I will check the metrics now.',turn_id:'turn'+i,created:stamp+i+.1}, {id:'done'+i,role:'assistant',text:'Step '+i+': training continues.\n\nFull measured evidence for this check.',turn_id:'turn'+i,created:stamp+i+.2});
  let chat={busy:false,agent:{name:'Monitoring worker'},messages,tasks:[],questions:[],approvals:[],preferences:{role:'worker',effective:{model:'model-a',reasoning:'medium',approval_mode:'ask'}}};
  await page.route('http://demo.test/api/chat?*',route=>route.fulfill({json:chat}));await page.goto('http://demo.test/');
  const group=page.locator('.chat-checks');await group.waitFor();assert.equal(await group.count(),1);assert.equal(await group.getAttribute('open'),null);assert.equal(await page.locator('#chat-messages .message.user').count(),1);assert.match(await group.textContent(),/Monitoring · 60 checks/);assert.match(await group.textContent(),/Step 59/);assert.ok(await page.locator('#chat-messages *').count()<35);
  await group.locator(':scope>summary').click();await page.locator('.chat-check').first().waitFor();assert.equal(await page.locator('.chat-check').count(),60);await page.locator('.chat-check').last().locator('summary').click();await page.getByText('Full measured evidence for this check.',{exact:false}).waitFor();
  // Expanded history survives polling; later direct steering stays a full message
  // even though it has the same turn ID as the scheduled check.
  messages.push({id:'direct',role:'user',text:'Compare E12 and E15 and explain the gap.',steering:true,status:'sent',turn_id:'turn59',created:stamp+61},{id:'reply',role:'assistant',text:'The comparison needs the protocol differences.',turn_id:'turn59',created:stamp+62});
  await page.locator('[data-action="refresh"]').first().click();await page.getByText('Compare E12 and E15 and explain the gap.',{exact:true}).waitFor();assert.equal(await group.getAttribute('open'),'');assert.equal(await page.locator('.message.assistant').filter({hasText:'The comparison needs'}).count(),1);assert.equal(await page.locator('.chat-check .message.assistant').filter({hasText:'The comparison needs'}).count(),0);
  messages.push({id:'pasted',role:'user',origin:'user',assignment:true,text:messages[1].text,created:stamp+63});
  chat={...chat,error:'Check failed: metrics endpoint unavailable'};await page.locator('[data-action="refresh"]').first().click();await page.getByText('Check failed: metrics endpoint unavailable',{exact:true}).waitFor();
  assert.equal(await page.locator('#chat-messages>.message.user').count(),3);
  await group.locator(':scope>summary').click();assert.equal(await page.locator('.chat-check').count(),0);
  assert.deepEqual(errors,[]);console.log('PASS legacy/new monitoring grouped and lazy-rendered; 60 checks compact by default; latest outcome, full history, expansion preservation, direct steering and errors visible');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});

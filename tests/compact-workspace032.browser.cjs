
'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {install}=require('./fixtures/workspace-demo.cjs');
(async()=>{const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});try{
 const page=await browser.newPage({viewport:{width:1500,height:950}}),errors=[];page.on('pageerror',e=>errors.push(e.message));const {exp}=await install(page,{tab:'writing'});
 exp.view_layout={version:0,board_version:1,rows:[],pages:[{id:'writing',title:'Writing',tiles:[{id:'draft',kind:'overview',span:12,height:600}]}],available_tiles:[]};
 const messages=Array.from({length:80},(_,i)=>({id:'m'+i,role:i%2?'assistant':'user',text:'Message '+i+'\n\n'+('Retained conversation. '.repeat(15)),created:Date.now()/1000+i}));let chat={busy:false,agent:{name:'Writing worker'},messages,questions:[],approvals:[],tasks:[],preferences:{effective:{}}};
 await page.route('http://demo.test/api/chat?*',route=>route.fulfill({json:chat}));await page.goto('http://demo.test/');await page.locator('.tile-page-heading h1').getByText('Writing',{exact:true}).waitFor();
 let header=await page.locator('.tile-page-heading').boundingBox(),title=await page.locator('.tile-page-heading h1').boundingBox(),layout=await page.locator('.tile-page-heading [data-action=configure-layout]').boundingBox();assert.ok(header.height<45,JSON.stringify(header));assert.ok(Math.abs(title.y-layout.y)<10);assert.ok(layout.x>title.x);
 const scroll=page.locator('#chat-messages'),atBottom=()=>scroll.evaluate(el=>el.scrollHeight-el.scrollTop-el.clientHeight<3);await page.waitForFunction(()=>{const el=document.querySelector('#chat-messages');return el.scrollHeight-el.scrollTop-el.clientHeight<3});
 await scroll.evaluate(el=>el.scrollTop=0);await page.locator('[data-action=refresh]').first().click();await page.waitForTimeout(250);assert.equal(await scroll.evaluate(el=>el.scrollTop),0,'Polling must preserve intentional history reading');
 await page.locator('#chat-toggle').click();await page.locator('#chat-toggle').click();await page.waitForFunction(()=>{const el=document.querySelector('#chat-messages');return el.scrollHeight-el.scrollTop-el.clientHeight<3});
 await scroll.evaluate(el=>el.scrollTop=0);await page.locator('[data-action=toggle-agent-list]').click();await page.locator('[data-conversation="conversation:demo-analysis"]').click();await page.waitForFunction(()=>{const el=document.querySelector('#chat-messages');return el.scrollHeight-el.scrollTop-el.clientHeight<3});assert.equal(await atBottom(),true);
 await page.setViewportSize({width:840,height:950});header=await page.locator('.tile-page-heading').boundingBox();assert.ok(header.height<45);assert.equal(await page.locator('.tile-page-tabs').evaluate(el=>el.scrollWidth<=el.clientWidth+2),true);assert.deepEqual(errors,[]);
 console.log('PASS title and controls share compact row at wide/narrow widths; opening/reopening/switching chats starts at latest message and polling retains intentional scroll');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});

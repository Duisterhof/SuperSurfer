'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||path.resolve(__dirname,'../../../work/browsers/chromium-1243/chrome-linux64/chrome'),headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.route('http://editor.test/**',route=>{
   const url=new URL(route.request().url());if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:`<div id="editor" style="height:700px"></div><script type="module">
    import {createWorkbenchEditor} from '/workbench-editor.js';
    window.saves=[];window.selections=[];let polls=0;window.releaseSave=null;window.phase='first';
    window.editor=createWorkbenchEditor({readOnly:()=>false,action:async op=>op==='editor.open'?{id:'fixture',url:'/frame.html',approved_trust_paths:['/tmp/project']}:{},api:async(route,unused,request={})=>{if(!route.startsWith('editor/session?'))return{};if(phase==='hold'){window.oldSignal=request.signal;return new Promise(resolve=>window.pendingPoll=()=>resolve({connected:true,dirty:false,events:[]}));}if(phase==='new')return{connected:true,dirty:true,events:[]};return{connected:true,dirty:false,events:++polls===1?[{sequence:1,kind:'saved',project_id:'p',path:'main.tex'},{sequence:2,kind:'selection',project_id:'p',path:'main.tex',label:'Selected text',text:'Requested passage'}]:[]};},onSave:record=>{saves.push(record);return new Promise(resolve=>releaseSave=resolve)},onAskAgent:record=>selections.push(record)});
    await editor.mount(document.querySelector('#editor'),{projectId:'p',experimentId:'task',repo:'/tmp/project',viewKind:'code'});
   </script>`});
   if(url.pathname==='/frame.html')return route.fulfill({contentType:'text/html',body:'<div>Isolated editor frame</div>'});
   const file=path.join(__dirname,'../ui',url.pathname.slice(1));return route.fulfill({contentType:file.endsWith('.js')?'text/javascript':'text/css',body:fs.readFileSync(file)});
  });
  await page.goto('http://editor.test/');await page.waitForFunction(()=>window.selections?.length===1,{},{timeout:2000});
  const data=await page.evaluate(()=>({save:saves[0],selection:selections[0],pending:typeof releaseSave==='function'}));
  assert.equal(data.pending,true);assert.equal(data.save.experimentId,'task');assert.equal(data.selection.text,'Requested passage');
  await page.evaluate(()=>{releaseSave();phase='hold';});await page.waitForFunction(()=>typeof pendingPoll==='function');
  await page.evaluate(async()=>{phase='new';const second=document.createElement('div');document.body.append(second);await editor.mount(second,{projectId:'p',experimentId:'task',repo:'/tmp/project',viewKind:'code'});});
  await page.waitForFunction(()=>editor.hasUnsaved('p'));assert.equal(await page.evaluate(()=>oldSignal.aborted),true);
  await page.evaluate(()=>pendingPoll());await page.waitForTimeout(80);assert.equal(await page.evaluate(()=>editor.hasUnsaved('p')),true,'A canceled old response must not overwrite current dirty state');
  await page.evaluate(()=>editor.dispose());assert.deepEqual(errors,[]);
  console.log('PASS selection reaches chat while save/autocompile is still pending, with original task context preserved');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

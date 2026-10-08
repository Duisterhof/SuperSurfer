/* Real locally bundled Monaco, isolated HTTP fixtures; never writes a user repo. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const ui=path.resolve(__dirname,'../ui');
const initial='def greet():\n    return "hello"\n';
const files=new Map([['p1/main.py',{content:initial,revision:'r1'}],['p1/src/util.js',{content:'export const value = 1;\n',revision:'u1'}],['p1/image.bin',{binary:true,content:null,revision:null}],['p2/main.py',{content:'other project\n',revision:'p2'}]]);
const calls=[],reviewed=new Set();let serial=2,readonly=false,delaySave=false,lateCreate=false,delayRead=false,readStarted=false,deletedDir=false,failTree=false;
const file=(pid,name)=>({path:name,exists:true,language:name.endsWith('.py')?'python':'javascript',...files.get(pid+'/'+name)});
const json=(res,data,status=200)=>{res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(data));};
const html=`<!doctype html><html><head><link rel="stylesheet" href="/vendor/monaco/editor.css"><link rel="stylesheet" href="/code-editor.css"><style>:root{--bg:#fff;--text:#242424;--muted:#777;--line:#ddd;--green:#0078d4;--soft:#f5f5f5}html,body{margin:0;height:100%}#editor{height:calc(100% - 2px)}body.dark{--bg:#171b24;--text:#f4f5f6;--muted:#9ba5b2;--line:#313946;--soft:#202733}</style></head><body><main id="editor"></main><script type="module">
import {createCodeEditor} from '/code-editor.js';
window.asked=[];window.saved=[];window.readonly=false;
const api=async path=>{const response=await fetch('/api/'+path);const data=await response.json();if(!response.ok){const error=new Error(data.error);error.status=response.status;throw error;}return data;};
const action=async(op,params)=>{const response=await fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({op,params})});const data=await response.json();if(!response.ok){const error=new Error(data.error);error.status=response.status;throw error;}return data;};
window.code=createCodeEditor({api,action,readOnly:()=>window.readonly,onAskAgent:text=>window.asked.push(text),onSave:event=>window.saved.push(event)});
window.mount=projectId=>code.mount(document.querySelector('#editor'),{projectId,experimentId:'e1'});
await mount('p1');window.monaco=await import('/vendor/monaco/editor.js');window.ready=true;
</script></body></html>`;
const server=http.createServer(async(req,res)=>{
 try {
  const url=new URL(req.url,'http://fixture'),pid=url.searchParams.get('project_id')||'p1',name=url.searchParams.get('path')||'';
  if(url.pathname==='/') {res.writeHead(200,{'Content-Type':'text/html'});return res.end(html);}
  if(url.pathname==='/api/code/file'){if(lateCreate&&name==='late.txt')await new Promise(resolve=>setTimeout(resolve,150));const snapshot=files.has(pid+'/'+name)?file(pid,name):null;if(delayRead&&name==='main.py'){readStarted=true;await new Promise(resolve=>setTimeout(resolve,300));}return snapshot?json(res,snapshot):json(res,{error:'File not found'},404);}
  if(url.pathname==='/api/code/tree') {
   if(failTree)return json(res,{error:'Temporary tree read failure'},503);
   if(deletedDir&&name==='src')return json(res,{error:'Directory not found'},404);
   const query=url.searchParams.get('query');let entries;
   if(query)entries=[...files.keys()].filter(key=>key.startsWith(pid+'/')&&key.includes(query)).map(key=>({path:key.slice(pid.length+1),name:key.split('/').at(-1),kind:'file'}));
   else if(name==='src')entries=[{name:'util.js',path:'src/util.js',kind:'file'}];
   else entries=pid==='p1'?[{name:'src',path:'src',kind:'directory'},{name:'main.py',path:'main.py',kind:'file'},{name:'image.bin',path:'image.bin',kind:'file'}]:[{name:'main.py',path:'main.py',kind:'file'}];
   if(deletedDir)entries=entries.filter(entry=>entry.path!=='src');return json(res,{path:name,entries,truncated:false});
  }
  if(url.pathname==='/api/code/changes')return json(res,{branch:'fixture',files:[{path:'main.py',status:'modified',staged:true,unstaged:true}]});
  if(url.pathname==='/api/code/diff')return json(res,{path:name,status:'modified',language:'python',original:initial,modified:files.get(pid+'/'+name).content,staged:url.searchParams.get('staged')==='1'});
  if(url.pathname==='/api/code/agents')return json(res,{coverage:'Only recorded agent patches. Shell edits remain unattributed.',agents:[
   {scope:'conversation:one',name:'Implementer',changes:[{id:'edit1',path:'main.py',kind:'update',created:1791406800,turn_id:'turn-1',reviewed:reviewed.has('edit1')}]},
   {scope:'conversation:two',name:'Reviewer',changes:[{id:'edit2',path:'main.py',kind:'update',truncated:true}]},
  ]});
  if(url.pathname==='/api/code/agent-diff')return json(res,url.searchParams.get('change_id')==='edit1'?{path:'main.py',original:initial,modified:initial.replace('hello','agent edit'),language:'python',source:'recorded_patch'}:{path:'main.py',diff:'@@ -2 +2 @@\n-    return "hello"\n+    return "reviewed"\n',truncated:true,partial:true});
  if(url.pathname==='/api/action') {
   let raw='';for await(const part of req)raw+=part;const call=JSON.parse(raw);calls.push(call);const p=call.params;
   if(readonly)return json(res,{error:'Read-only workspace'},403);
   if(call.op==='code.review'){p.reviewed?reviewed.add(p.change_id):reviewed.delete(p.change_id);return json(res,{reviewed:p.reviewed});}
   if(call.op==='code.mkdir')return json(res,{path:p.path,created:true});
   if(call.op==='code.save') {
    if(delaySave)await new Promise(resolve=>setTimeout(resolve,150));
    const prior=files.get(p.project_id+'/'+p.path);
    if((prior?.revision??null)!==p.revision)return json(res,{error:'File changed on disk; revision conflict'},409);
    files.set(p.project_id+'/'+p.path,{content:p.content,revision:'r'+serial++});return json(res,file(p.project_id,p.path));
   }
   return json(res,{});
  }
  const target=path.resolve(ui,'.'+url.pathname);if(!target.startsWith(ui+path.sep))return json(res,{error:'Forbidden'},403);
  const ext=path.extname(target);res.writeHead(200,{'Content-Type':ext==='.js'?'text/javascript':ext==='.css'?'text/css':ext==='.ttf'?'font/ttf':'application/octet-stream'});fs.createReadStream(target).on('error',()=>res.destroy()).pipe(res);
 }catch(error){json(res,{error:error.message},500);}
});
(async()=>{let browser;try {
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:850}}),errors=[];page.setDefaultTimeout(12000);page.on('pageerror',e=>{errors.push(e.message);console.error('BROWSER ERROR',e.stack);});
 await page.goto('http://127.0.0.1:'+server.address().port);await page.waitForFunction(()=>window.ready);
 const model=async (method,...args)=>page.evaluate(({method,args})=>{const model=monaco.editor.getModels().find(row=>row.uri.path.endsWith('/p1/main.py'));return model[method](...args);},{method,args});
 await page.locator('.code-tree-entry[data-code-open="main.py"]').click();await page.locator('.monaco-editor').waitFor();
 assert.equal(await model('getValue'),initial);
 await page.locator('.monaco-editor').click({position:{x:150,y:30}});await page.keyboard.press('Control+End');await page.keyboard.type('# typed in Monaco');
 assert.ok(await page.evaluate(()=>code.hasUnsaved()));await page.keyboard.press('Control+s');
 await page.waitForFunction(()=>!code.hasUnsaved());assert.ok(files.get('p1/main.py').content.includes('# typed in Monaco'));assert.equal(calls.at(-1).op,'code.save');
 assert.equal(await page.evaluate(()=>saved.length),1);assert.deepEqual(await page.evaluate(()=>({projectId:saved[0].projectId,path:saved[0].path})),{projectId:'p1',path:'main.py'});console.log('PASS actual Monaco edit, dirty indicator, successful scoped onSave callback and keyboard save with revision');

 await model('setValue','unsaved draft\n');await page.evaluate(()=>{code.unmount();});await page.evaluate(()=>mount('p2'));
 await page.locator('.code-tree-entry[data-code-open="main.py"]').click();await page.waitForFunction(()=>monaco.editor.getModels().some(row=>row.uri.path.endsWith('/p2/main.py')));
 assert.ok(await page.evaluate(()=>code.hasUnsaved()));await page.evaluate(()=>mount('p1'));assert.equal(await model('getValue'),'unsaved draft\n');
 assert.equal(await page.evaluate(()=>code.hasUnsaved('p1')),true);assert.equal(await page.evaluate(()=>code.hasUnsaved('p2')),false);console.log('PASS navigation preserves unsaved models and separates projects');

 files.set('p1/main.py',{content:'external agent edit\n',revision:'external1'});await page.evaluate(()=>code.refresh());
 await page.locator('.code-conflict').waitFor({state:'visible'});assert.equal(await model('getValue'),'unsaved draft\n');assert.ok(await page.locator('[data-code="save"]').isDisabled());
 await page.locator('[data-code="compare"]').click();await page.locator('.monaco-diff-editor').waitFor();assert.match(await page.locator('.code-diff-heading').innerText(),/Disk ↔ Your/);
 page.once('dialog',dialog=>dialog.dismiss());await page.locator('[data-code="reload"]').click();assert.equal(await model('getValue'),'unsaved draft\n');
 page.once('dialog',dialog=>dialog.accept());await page.locator('[data-code="reload"]').click();assert.equal(await model('getValue'),'external agent edit\n');
 files.set('p1/main.py',{content:'clean refresh\n',revision:'external2'});await page.evaluate(()=>code.refresh());assert.equal(await model('getValue'),'clean refresh\n');
 console.log('PASS external clean reload; dirty conflict compare and explicit discard, cancel preserves draft');

 await model('setValue','my latest\n');files.set('p1/main.py',{content:'save race\n',revision:'external3'});await page.locator('[data-code="save"]').click();
 await page.locator('.code-conflict').waitFor({state:'visible'});assert.equal(files.get('p1/main.py').content,'save race\n');assert.equal(await page.evaluate(()=>saved.length),1,'Conflict must not invoke the successful-save callback');
 page.once('dialog',dialog=>dialog.accept());await page.locator('[data-code="keep-mine"]').click();await page.locator('[data-code="save"]').click();await page.waitForFunction(()=>!code.hasUnsaved());
 assert.equal(files.get('p1/main.py').content,'my latest\n');
 delaySave=true;await model('setValue','saved snapshot\n');await page.locator('[data-code="save"]').click();await model('setValue','typed while saving\n');await page.waitForTimeout(220);delaySave=false;
 assert.equal(files.get('p1/main.py').content,'saved snapshot\n');assert.equal(await model('getValue'),'typed while saving\n');assert.ok(await page.evaluate(()=>code.hasUnsaved()));
 delayRead=true;readStarted=false;await page.evaluate(()=>{window.pendingRefresh=code.refresh();});for(let i=0;i<30&&!readStarted;i++)await new Promise(resolve=>setTimeout(resolve,10));assert.ok(readStarted);
 await page.locator('[data-code="save"]').click();await page.waitForFunction(()=>!code.hasUnsaved());delayRead=false;await page.evaluate(()=>pendingRefresh);
 assert.equal(await model('getValue'),'typed while saving\n');assert.ok(await page.locator('.code-conflict').isHidden());
 await model('setValue','typed while saving\n# unsaved selection');
 console.log('PASS save races never overwrite silently; typing during save stays dirty');

 await page.evaluate(()=>{const ed=monaco.editor.getEditors().find(ed=>ed.getModel()?.uri.path.endsWith('/p1/main.py'));ed.setSelection(new monaco.Selection(1,1,1,6));});
 await page.evaluate(()=>mount('p1'));assert.equal(await page.evaluate(()=>monaco.editor.getEditors().find(ed=>ed.getModel()?.uri.path.endsWith('/p1/main.py')).getSelection().endColumn),6);
 await page.locator('.code-selection-action').click();assert.match(await page.evaluate(()=>asked.at(-1)),/lines 1–1/);assert.match(await page.evaluate(()=>asked.at(-1)),/unsaved editor changes/);assert.ok(!calls.some(call=>call.op==='chat.send'));
 await page.locator('[data-code="changes"]').click();await page.locator('[data-code-diff="main.py"]').click();await page.locator('.monaco-diff-editor').waitFor();assert.match(await page.locator('.code-diff-heading').innerText(),/HEAD ↔ Working/);
 await page.locator('[data-code="split"]').click();await page.locator('[data-code-staged="main.py"]').click();await page.locator('.code-diff-heading>span').filter({hasText:'HEAD ↔ Index'}).waitFor();
 await page.locator('[data-code="agents"]').click();await page.locator('[data-code-agent-diff="edit1"]').click();await page.locator('.code-diff-heading>span').filter({hasText:'Implementer'}).waitFor();assert.match(await page.locator('.code-diff-heading').innerText(),/Recorded agent edit.*Implementer/);
 assert.match(await page.locator('[data-code-agent-diff="edit1"]').getAttribute('title'),/Turn turn-1/);await page.locator('[data-code-review="edit1"]').click();await page.locator('[data-code-review="edit1"][aria-pressed="true"]').waitFor();assert.ok(reviewed.has('edit1'));
 await page.locator('.code-agent-select').selectOption('conversation:two');await page.locator('[data-code-agent-diff="edit2"]').click();await page.locator('.code-diff-heading>span').filter({hasText:'Reviewer'}).waitFor();assert.match(await page.locator('.code-diff-heading').innerText(),/partial patch.*Reviewer/);
 await page.evaluate(()=>mount('p1'));assert.equal(await page.locator('.code-agent-select').inputValue(),'conversation:two');assert.match(await page.locator('.code-diff-heading').innerText(),/partial patch.*Reviewer/);
 await page.locator('[data-code="ask"]').click();assert.match(await page.evaluate(()=>asked.at(-1)),/recorded change.*Reviewer/);assert.match(await page.evaluate(()=>asked.at(-1)),/Recorded patch:/);assert.match(await page.evaluate(()=>asked.at(-1)),/return \"reviewed\"/);await page.evaluate(()=>{const patch=monaco.editor.getEditors().find(ed=>ed.getModel()?.getValue().startsWith('@@'));patch.setSelection(new monaco.Selection(3,1,3,25));patch.focus();});await page.keyboard.press('Control+i');assert.match(await page.evaluate(()=>asked.at(-1)),/Selected text from the recorded change/);assert.equal(await page.locator('[data-code="save"]').isDisabled(),true);assert.equal(await model('getValue'),'typed while saving\n# unsaved selection');console.log('PASS Git/staged and named-agent patches remain separate, partial provenance and composer-only handoff');

 await page.evaluate(()=>code.openFile('main.py',{line:2,column:3,endLine:999,endColumn:999}));const selectedRange=await page.evaluate(()=>monaco.editor.getEditors().find(ed=>ed.getModel()?.uri.path.endsWith('/p1/main.py')).getSelection());assert.equal(selectedRange.startLineNumber,2);assert.equal(selectedRange.endLineNumber,2);assert.equal(await model('getValue'),'typed while saving\n# unsaved selection');
 await page.locator('[data-code="files"]').click();await page.getByLabel('Find file by name').fill('util');await page.locator('.code-tree-entry[data-code-open="src/util.js"]').click();await page.waitForFunction(()=>monaco.editor.getModels().some(row=>row.uri.path.endsWith('/src/util.js')));
 await page.getByLabel('Find file by name').fill('');await page.locator('.code-tree-entry[data-code-open="image.bin"]').click();await page.getByText('This binary file cannot be edited as text.').waitFor();assert.ok(await page.locator('[data-code="save"]').isDisabled());
 await page.locator('[data-code="new-file"]').click();await page.locator('.code-create input').fill('empty.txt');await page.locator('.code-create button[type="submit"]').click();await page.locator('.code-tab.selected[data-code-tab="empty.txt"]').waitFor();assert.ok(await page.evaluate(()=>code.hasUnsaved()));await page.locator('[data-code="save"]').click();await page.waitForTimeout(100);assert.equal(files.get('p1/empty.txt').content,'');
 await page.locator('[data-code="new-folder"]').click();await page.locator('.code-create input').fill('new-folder');await page.locator('.code-create button[type="submit"]').click();await page.waitForTimeout(50);assert.equal(calls.at(-1).op,'code.mkdir');
 console.log('PASS recursive file search, binary protection, new empty file and directory');

 lateCreate=true;await page.locator('[data-code="new-file"]').click();await page.locator('.code-create input').fill('late.txt');await page.locator('.code-create button[type="submit"]').click();await page.evaluate(()=>mount('p2'));await page.waitForTimeout(220);lateCreate=false;
 assert.equal(await page.locator('[data-code-tab="late.txt"]').count(),0);await page.evaluate(()=>mount('p1'));await page.locator('[data-code-tab="late.txt"]').waitFor();
 page.once('dialog',dialog=>dialog.dismiss());await page.locator('[data-code-close="late.txt"]').click();await page.locator('[data-code-tab="late.txt"]').waitFor();
 await page.locator('[data-code-open="main.py"]').first().click();console.log('PASS late create stays with owning project; cancelling tab close preserves edits');

 await page.locator('[data-code-dir="src"]').click();await page.locator('.code-tree-entry[data-code-open="src/util.js"]').waitFor();
 deletedDir=true;files.delete('p1/src/util.js');files.set('p1/main.py',{content:'agent edited while folder disappeared\n',revision:'directory-race'});
 await page.evaluate(()=>code.refresh());assert.equal(await page.locator('[data-code-dir="src"]').count(),0);assert.ok(await page.locator('.code-conflict').isVisible());assert.equal(await model('getValue'),'typed while saving\n# unsaved selection');
 await page.evaluate(()=>code.refresh());await page.locator('[data-code="changes"]').click();await page.locator('[data-code-diff="main.py"]').waitFor();
 failTree=true;files.set('p1/main.py',{content:'another external change\n',revision:'tree-read-failure'});await page.evaluate(()=>code.refresh());assert.ok(await page.locator('.code-conflict').isVisible());assert.match(await page.locator('.code-status').innerText(),/Temporary tree read failure/);failTree=false;await page.evaluate(()=>code.refresh());assert.doesNotMatch(await page.locator('.code-status').innerText(),/Temporary tree read failure/);
 console.log('PASS removed expanded folders are pruned; other tree failures preserve file conflict checks and Git refresh');

 readonly=true;await page.evaluate(()=>{window.readonly=true;return code.refresh();});assert.ok(await page.locator('[data-code="new-file"]').isDisabled());assert.ok(await page.locator('[data-code="save"]').isDisabled());
 await page.evaluate(()=>{document.body.classList.add('dark');document.documentElement.dataset.theme='dark';});await page.setViewportSize({width:390,height:650});
 const sizes=await page.evaluate(()=>['.code-editor','.code-toolbar','.code-body','.code-workbench'].map(selector=>{const el=document.querySelector(selector);return {selector,width:el.clientWidth,scroll:el.scrollWidth};}));assert.ok(sizes.every(row=>row.scroll<=row.width+2),JSON.stringify(sizes));
 const output=process.env.SUPERSURFER_QA_OUTPUT||path.resolve(__dirname,'../../../work/code-editor-qa');fs.mkdirSync(output,{recursive:true});await page.screenshot({path:path.join(output,'code-editor-narrow.png')});
 assert.deepEqual(errors,[]);await page.evaluate(()=>code.dispose());console.log('PASS read-only mode, compact dark layout and zero JavaScript errors');
 }finally {await browser?.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});

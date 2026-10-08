/* Independent repository tiles connected to one actual Monaco editor. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const ui=path.resolve(__dirname,'../ui'),calls=[],reads=[];
let reviewed=false,removed=false;
let releaseMonaco;const monacoGate=new Promise(resolve=>{releaseMonaco=resolve;});
const files={'p1/main.py':'print("shared source")\n','p1/src/util.py':'VALUE = 1\n','p2/main.py':'print("other project")\n'};
const json=(res,data,status=200)=>{res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(data));};
const html=`<!doctype html><html><head><link rel="stylesheet" href="/vendor/monaco/editor.css"><link rel="stylesheet" href="/code-editor.css"><style>:root{--bg:#fff;--text:#222;--muted:#777;--line:#ddd;--soft:#f4f6f7;--green:#087d8a}body{margin:0}#page{display:grid;grid-template-columns:230px minmax(0,1fr) 250px;gap:8px;padding:8px;height:calc(100vh - 16px)}#page>div{min-width:0;min-height:0}#elsewhere{height:80vh}#elsewhere:empty{display:none}@media(max-width:800px){#page{grid-template-columns:150px minmax(0,1fr);grid-template-rows:1fr 200px}#agents{grid-column:1/-1}}</style></head><body><div id="page"><div id="files"></div><div id="editor"></div><div id="agents"></div></div><div id="elsewhere"></div><script type="module">
import {createCodeEditor} from '/code-editor.js';import {createRepositoryExplorer,createAgentChanges} from '/code-tiles.js';
window.readonly=false;window.projectId='p1';window.fallbacks=0;
const api=async value=>{const res=await fetch('/api/'+value);const data=await res.json();if(!res.ok)throw Object.assign(new Error(data.error),{status:res.status});return data;};
const action=async(op,params)=>{const res=await fetch('/api/action',{method:'POST',body:JSON.stringify({op,params})});const data=await res.json();if(!res.ok)throw Object.assign(new Error(data.error),{status:res.status});return data;};
window.code=createCodeEditor({api,action,readOnly:()=>window.readonly});
const ensureEditor=async()=>{if(!document.querySelector('#editor .code-monaco')){window.fallbacks++;await code.mount(document.querySelector('#editor'),{projectId:window.projectId,experimentId:'e1',mode:'editor'});}};
window.explorer=createRepositoryExplorer({api,onOpenFile:async path=>{await ensureEditor();return code.openFile(path);}});
window.agents=createAgentChanges({api,action,readOnly:()=>window.readonly,onOpenChange:async(scope,id)=>{await ensureEditor();return code.showAgentChange(scope,id);}});
window.mountPage=async pid=>{window.projectId=pid;return Promise.all([code.mount(document.querySelector('#editor'),{projectId:pid,experimentId:'e1',mode:'editor'}),explorer.mount(document.querySelector('#files'),{projectId:pid,experimentId:'e1'}),agents.mount(document.querySelector('#agents'),{projectId:pid,experimentId:'e1'})]);};
await mountPage('p1');window.monaco=await import('/vendor/monaco/editor.js');window.ready=true;
</script></body></html>`;
const server=http.createServer(async(req,res)=>{try{
 const url=new URL(req.url,'http://fixture'),pid=url.searchParams.get('project_id'),name=url.searchParams.get('path')||'';
 if(url.pathname==='/'){res.writeHead(200,{'Content-Type':'text/html'});return res.end(html);}
 if(url.pathname.startsWith('/api/'))reads.push(url.pathname+url.search);
 if(url.pathname==='/api/code/tree') {
  if(removed&&name==='src')return json(res,{error:'Directory not found'},404);
  let entries=name==='src'?[{name:'util.py',path:'src/util.py',kind:'file'}]:[{name:'main.py',path:'main.py',kind:'file'},...(removed||pid==='p2'?[]:[{name:'src',path:'src',kind:'directory'}])];
  if(url.searchParams.has('query'))entries=Object.keys(files).filter(key=>key.startsWith(pid+'/')&&key.includes(url.searchParams.get('query'))).map(key=>({name:key.split('/').at(-1),path:key.slice(pid.length+1),kind:'file'}));
  return json(res,{path:name,entries});
 }
 if(url.pathname==='/api/code/file')return Object.hasOwn(files,pid+'/'+name)?json(res,{path:name,exists:true,content:files[pid+'/'+name],revision:'r1',language:'python'}):json(res,{error:'File not found'},404);
 if(url.pathname==='/api/code/agents')return json(res,{coverage:'Recorded edits; shell changes are unattributed.',agents:[{scope:'conversation:'+pid,name:pid==='p1'?'Implementer':'Other worker',changes:[{id:'edit-one',path:'main.py',kind:'update',created:1791406800,turn_id:'turn-one',reviewed}]}]});
 if(url.pathname==='/api/code/agent-diff')return json(res,{path:'main.py',agent_name:pid==='p1'?'Implementer':'Other worker',diff:'@@ -1 +1 @@\n-print("before")\n+print("after")',source:'recorded_patch',partial:true});
 if(url.pathname==='/api/action') {let text='';for await(const chunk of req)text+=chunk;const call=JSON.parse(text);calls.push(call);if(call.op==='code.review')reviewed=call.params.reviewed;return json(res,{reviewed});}
 if(url.pathname==='/vendor/monaco/editor.js')await monacoGate;
 const file=path.resolve(ui,'.'+url.pathname);if(!file.startsWith(ui+path.sep))return json(res,{error:'Forbidden'},403);
 const ext=path.extname(file);res.writeHead(200,{'Content-Type':ext==='.js'?'text/javascript':ext==='.css'?'text/css':'application/octet-stream'});fs.createReadStream(file).on('error',()=>res.destroy()).pipe(res);
}catch(error){json(res,{error:error.message},500);}});
(async()=>{let browser;try{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1380,height:850}}),errors=[];page.setDefaultTimeout(12000);page.on('pageerror',error=>errors.push(error.message));
 await page.goto('http://127.0.0.1:'+server.address().port,{waitUntil:'commit'});await page.locator('[data-tile-file="main.py"]').click();assert.equal(await page.evaluate(()=>Boolean(window.ready)),false);releaseMonaco();await page.waitForFunction(()=>window.ready);await page.locator('#editor .monaco-editor').waitFor();
 assert.ok(await page.locator('#editor .code-sidebar').isHidden());assert.ok(await page.locator('#editor [data-code="files"]').isVisible());await page.locator('#editor [data-code="files"]').click();assert.ok(await page.locator('#editor .code-sidebar').isVisible());await page.locator('#editor [data-code="files"]').click();assert.ok(await page.locator('#editor .code-sidebar').isHidden());
 await page.evaluate(()=>{const editor=monaco.editor.getEditors().find(ed=>ed.getModel()?.uri.path.endsWith('/p1/main.py'));editor.setValue('draft shared between tiles\n');editor.setSelection(new monaco.Selection(1,2,1,7));});
 const counts=await page.evaluate(()=>monaco.editor.getModels().length);await page.evaluate(()=>mountPage('p1'));assert.equal(await page.evaluate(()=>monaco.editor.getEditors().find(ed=>ed.getModel()?.uri.path.endsWith('/p1/main.py')).getSelection().endColumn),7);
 assert.equal(await page.evaluate(()=>monaco.editor.getModels().length),counts);console.log('PASS independent explorer drives sidebar-free editor; same-page refresh preserves one model and caret');

 await page.locator('[data-tile-directory="src"]').click();await page.locator('[data-tile-file="src/util.py"]').click();await page.waitForFunction(()=>monaco.editor.getModels().some(model=>model.uri.path.endsWith('/src/util.py')));
 await page.evaluate(async()=>{explorer.unmount();agents.unmount();await code.mount(document.querySelector('#elsewhere'),{projectId:'p1',experimentId:'e1',mode:'full'});});
 await page.evaluate(()=>mountPage('p1'));assert.ok(await page.locator('[data-tile-directory="src"]').getAttribute('aria-expanded')==='true');
 await page.locator('[data-tile-file="main.py"]').click();assert.equal(await page.evaluate(()=>monaco.editor.getModels().find(model=>model.uri.path.endsWith('/p1/main.py')).getValue()),'draft shared between tiles\n');
 assert.equal(await page.evaluate(()=>monaco.editor.getModels().filter(model=>model.uri.path.endsWith('/p1/main.py')).length),1);console.log('PASS page/mode switches retain dirty files and explorer expansion without duplicate buffers');

 await page.locator('[data-tile-change="edit-one"]').click();await page.locator('.code-diff-heading>span').filter({hasText:'Implementer'}).waitFor();assert.match(await page.locator('.code-diff-heading').innerText(),/partial patch/);
 await page.locator('[data-tile-review="edit-one"]').click();await page.locator('[data-tile-review="edit-one"][aria-pressed="true"]').waitFor();assert.equal(calls.at(-1).op,'code.review');assert.equal(calls.at(-1).params.scope,'conversation:p1');
 assert.equal(await page.evaluate(()=>monaco.editor.getModels().find(model=>model.uri.path.endsWith('/p1/main.py')).getValue()),'draft shared between tiles\n');
 assert.ok(reads.some(url=>url.startsWith('/api/code/agents?')&&url.includes('experiment_id=e1')));console.log('PASS separate agent changes opens recorded patch and marks reviewed without changing source');

 await page.evaluate(()=>code.unmount());await page.locator('[data-tile-file="main.py"]').click();await page.locator('#editor .monaco-editor').waitFor();assert.equal(await page.evaluate(()=>fallbacks),1);
 await page.evaluate(()=>mountPage('p2'));await page.locator('[data-tile-file="main.py"]').click();await page.waitForFunction(()=>monaco.editor.getModels().some(model=>model.uri.path.endsWith('/p2/main.py')));
 assert.match(await page.locator('#agents .code-agent-select').innerText(),/Other worker/);assert.ok(await page.evaluate(()=>code.hasUnsaved()));await page.evaluate(()=>mountPage('p1'));
 console.log('PASS explorer can request a missing editor; project switches keep buffers and agent scope separate');

 removed=true;delete files['p1/src/util.py'];await page.evaluate(()=>explorer.refresh());assert.equal(await page.locator('[data-tile-directory="src"]').count(),0);
 await page.locator('#files .code-tile-search').fill('main');await page.locator('[data-tile-file="main.py"]').waitFor();await page.evaluate(()=>mountPage('p1'));assert.equal(await page.locator('#files .code-tile-search').inputValue(),'main');
 await page.evaluate(()=>{window.readonly=true;return mountPage('p1');});assert.ok(await page.locator('[data-tile-review="edit-one"]').isDisabled());
 await page.setViewportSize({width:720,height:750});const fits=await page.evaluate(()=>['#page','#files','#editor','#agents'].map(selector=>{const node=document.querySelector(selector);return {selector,width:node.clientWidth,scroll:node.scrollWidth};}));assert.ok(fits.every(row=>row.scroll<=row.width+2),JSON.stringify(fits));
 const output=process.env.SUPERSURFER_QA_OUTPUT||path.resolve(__dirname,'../../../work/code-editor-qa');fs.mkdirSync(output,{recursive:true});await page.screenshot({path:path.join(output,'code-tiles.png')});assert.deepEqual(errors,[]);
 await page.evaluate(()=>{code.dispose();explorer.dispose();agents.dispose();});console.log('PASS deleted folders recover, tile state survives remount, read-only reviews and compact tile layout');
}finally{releaseMonaco();await browser?.close();await new Promise(resolve=>server.close(resolve));}})().catch(error=>{console.error(error);process.exitCode=1;});

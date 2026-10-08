const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const py=code=>JSON.parse(execFileSync('python3',['-c',code],{cwd:root,encoding:'utf8'}));
const fixture=py('import json; from server.surfboards import catalog,templates,compile_layouts; boards=templates(); print(json.dumps({"catalog":catalog(),"templates":boards,"layouts":[compile_layouts(b) for b in boards]}))');
const clone=value=>JSON.parse(JSON.stringify(value));
(async()=>{let browser;try {
 browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:900}});page.setDefaultTimeout(10000);const errors=[],calls=[];page.on('pageerror',e=>errors.push(e.message));
 let record={project_id:'p1',version:0,board:clone(fixture.templates[0]),draft:null,catalog:fixture.catalog,templates:fixture.templates};let sequence=0;
 await page.exposeFunction('getLayoutRecord',()=>clone(record));
 await page.exposeFunction('layoutAction',(op,params)=>{calls.push({op,params});assert.equal(params.expected_version,record.version);assert.equal(params.expected_draft_version,record.draft?.draft_version||0);
  if(op==='surfboard.draft'){const validated=JSON.parse(execFileSync('python3',['-c','import json,sys;from server.surfboards import validate;print(json.dumps(validate(json.load(sys.stdin),allow_pending=True)))'],{cwd:root,input:JSON.stringify(params.board),encoding:'utf8'}));record.draft={board:validated,draft_version:++sequence,errors:[]};}
  if(op==='surfboard.apply'){assert.ok(record.draft);record.board=record.draft.board;record.draft=null;record.version++;}
  return clone(record);
 });
 await page.route('http://layout.test/**',route=>{const url=new URL(route.request().url());if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:`<!doctype html><html><head><link rel="stylesheet" href="/surfboard.css"><style>:root{--bg:#f7f8fa;--soft:#eef0f4;--text:#263044;--muted:#738099;--line:#d8deea;--green:#007f83;--strong-line:#98aabc;--orange-bg:#fff5db}*{box-sizing:border-box}html,body{margin:0;height:100%;font-family:system-ui}#editor{height:100%;max-width:1200px;margin:auto}button,input,select{font:inherit}[hidden]{display:none!important}</style></head><body><div id="editor"></div><script type="module">import * as module from '/surfboard.js';window.module=module;window.editor=module.createSurfboardEditor({api:()=>window.getLayoutRecord(),action:window.layoutAction});window.editor.mount(document.querySelector('#editor'),'p1');</script></body></html>`});const file=path.join(root,'ui',url.pathname);return route.fulfill({contentType:url.pathname.endsWith('.js')?'text/javascript':'text/css',body:fs.readFileSync(file)});});
 await page.goto('http://layout.test');await page.locator('.sb-node[data-node="wandb"]').waitFor();
 const parity=await page.evaluate(boards=>boards.map(board=>({project:module.viewLayoutRows(board,'project'),item:module.viewLayoutRows(board,'item')})),fixture.templates);
 assert.deepEqual(parity,fixture.layouts,'Browser defaults and server compilation must agree across all workflows');
 await page.locator('[data-sb="mode-layout"]').first().click();await page.locator('.sb-dock-settings > summary').click();await page.locator('.sb-layout-main [data-layout-id="overview"]').waitFor();
 assert.equal(await page.locator('.sb-layout-right [data-layout-id="chat"]').count(),1);
 await page.locator('[data-layout-id="results"] select').selectOption('main');assert.equal(calls.length,0);assert.equal(record.board.layouts,undefined);
 assert.equal(await page.locator('.sb-layout-main [data-layout-id="results"]').count(),1,'Moving Results to main updates the dock preview');
 await page.locator('[data-layout-id="chat"]').dragTo(page.locator('.sb-layout-main [data-layout-id="results"]'));
 assert.deepEqual(await page.locator('.sb-layout-main [data-layout-id]').evaluateAll(elements=>elements.map(el=>el.dataset.layoutId)),['overview','compute','artifacts','chat','results']);
 await page.locator('[data-sb="layout-item"]').click();assert.equal(await page.locator('.sb-layout-right [data-layout-id="chat"]').count(),1);assert.equal(await page.locator('.sb-layout-main [data-layout-id="results"]').count(),1);
 await page.locator('[data-layout-id="overview"] select').selectOption('hidden');
 await page.locator('[data-sb="add-editor"]').click();assert.equal(await page.locator('.sb-layout-main [data-layout-id="editor"]').count(),1);
 await page.locator('[data-layout-id="editor"] [data-layout-move="up"]').click();
 assert.equal(await page.locator('.sb-layout-main [data-layout-id]').first().getAttribute('data-layout-id'),'runs');
 await page.locator('[data-sb="review"]').click();assert.match(await page.locator('.sb-review').innerText(),/Arrange project views/);assert.match(await page.locator('.sb-review').innerText(),/Arrange work-item views/);
 await page.locator('[data-sb="apply"]').click();await page.waitForFunction(()=>document.querySelector('.sb-save-state').textContent==='Active · v1');
 assert.equal(record.board.layouts.project.find(r=>r.id==='chat').placement,'main');assert.equal(record.board.layouts.item.find(r=>r.id==='chat').placement,'right');assert.equal(record.board.layouts.item.find(r=>r.id==='overview').placement,'hidden');assert.equal(record.board.nodes.filter(n=>n.kind==='editor').length,1);
 console.log('PASS layout drag, reorder, independent scopes, palette editor, draft review and explicit apply');
 // A normal workspace refresh preserves the active layout editor and unsaved changes.
 await page.locator('[data-layout-id="results"] select').selectOption('right');await page.evaluate(()=>editor.refresh());assert.equal(await page.locator('.sb-layout-right [data-layout-id="results"]').count(),1);assert.equal(record.board.layouts.item.find(r=>r.id==='results').placement,'main');
 await page.locator('[data-sb="mode-workflow"]').click();const editorId=record.board.nodes.find(n=>n.kind==='editor').id;await page.locator(`[data-node="${editorId}"]`).dispatchEvent('click');assert.equal(await page.locator('.sb-inspector').getByText('supersurfer-code-editor').count(),1);assert.equal(await page.locator('.sb-inspector [data-sb="add-argument"]').count(),0);
 await page.locator('[data-sb="delete"]').click();await page.locator('[data-sb="save"]').click();await page.waitForFunction(()=>document.querySelector('.sb-save-state').textContent==='Draft saved');for(const rows of Object.values(record.draft.board.layouts))assert.ok(!rows.some(r=>r.id==='editor'));
 console.log('PASS workflow switches preserve local layout; removing a view block cleans scope references');
 await page.locator('.sb-palette [data-kind="editor"]').click();await page.locator('[data-sb="save"]').click();await page.waitForFunction(()=>document.querySelector('.sb-save-state').textContent==='Draft saved');for(const rows of Object.values(record.draft.board.layouts))assert.equal(rows.find(r=>r.id==='editor').placement,'main');console.log('PASS graph editor palette adds visible views to explicit scope layouts');
 await page.locator('[data-sb="mode-layout"]').first().click();await page.setViewportSize({width:1000,height:700});await page.screenshot({path:path.resolve(root,'../../work/surfboard-layout-1000.png')});
 await page.setViewportSize({width:600,height:700});assert.ok(await page.locator('.sb-view-layout').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
 // Mount the public component exactly as the per-item overrides panel does.
 await page.evaluate(({rows,available})=>{editor.unmount();window.changed=[];window.locked=false;window.override=module.createViewLayoutEditor({readOnly:()=>locked,onChange:value=>changed.push(value)});override.mount(document.querySelector('#editor'),{rows,available});},{rows:fixture.layouts[1].item,available:fixture.layouts[1].item});
 await page.locator('[data-layout-id="editor"] select').selectOption('right');assert.equal(await page.locator('.sb-layout-right [data-layout-id="editor"]').count(),1);assert.equal(await page.evaluate(()=>changed.length),1);
 await page.locator('[data-layout-id="chat"] select').selectOption('hidden');assert.equal(await page.locator('.sb-layout-hidden [data-layout-id="chat"]').count(),1);
 await page.evaluate(()=>{locked=true;override.mount(document.querySelector('#editor'),{rows:override.rows(),available:module.viewLayoutCatalog({nodes:[{id:'editor',kind:'editor'}],workflow:'software'},'item')});});assert.equal(await page.locator('[data-layout-id="editor"] select').isDisabled(),true);
 assert.deepEqual(errors,[]);console.log('PASS reusable task override editor, hidden chat, read-only controls, compact layout and no JS errors');
 }finally{await browser?.close();}})().catch(error=>{console.error(error);process.exit(1)});

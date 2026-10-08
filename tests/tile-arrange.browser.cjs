'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
(async()=>{
 const root=path.resolve(__dirname,'..'),child=spawn('python3',['tests/layout_runtime_fixture.py'],{cwd:root,stdio:['pipe','pipe','pipe']});let stderr='';child.stderr.on('data',chunk=>stderr+=chunk);let browser;
 try{
  const service=await new Promise((resolve,reject)=>{let out='';child.stdout.on('data',chunk=>{out+=chunk;if(out.includes('\n'))resolve(JSON.parse(out.split('\n')[0]))});child.on('exit',code=>reject(new Error(code+' '+stderr)));});
  const token=fs.readFileSync(path.join(service.directory,'token'),'utf8').trim(),base='http://127.0.0.1:'+service.port,pid=service.projects.software;
  browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1700,height:1050}});page.setDefaultTimeout(15000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(({token,pid})=>{sessionStorage.setItem('supersurfer-token',token);if(!localStorage.getItem('supersurfer-workspace'))localStorage.setItem('supersurfer-workspace',JSON.stringify({view:'workspace',projectId:pid,tab:'desk',chatVisible:true}));},{token,pid});
  const request=async(route,body)=>{const r=await fetch(base+'/api/'+route,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const d=await r.json();assert.ok(r.ok,JSON.stringify(d));return d};
  const read=()=>request('view-layout?project_id='+pid);
  const save=async pages=>{const r=await read();return request('action',{op:'view-layout.save',params:{project_id:pid,experiment_id:null,version:r.version,board_version:r.board_version,pages}})};
  const initial=await read(),desk={id:'desk',title:'My desk',tiles:[{id:'files',kind:'file_explorer',span:3,height:500},{id:'code',kind:'editor',span:9,height:500},{id:'notes',kind:'documents',span:12,height:300}]};await save([...initial.pages,desk]);
  await page.goto(base);await page.locator('#repository-explorer-tile [data-tile-file="main.py"]').click();await page.locator('.monaco-editor').waitFor();
  await page.evaluate(async()=>{const m=await import('/vendor/monaco/editor.js');window.dirtyModel=m.editor.getModels().find(m=>m.uri.path.endsWith('/main.py'));dirtyModel.setValue('print("keep my unsaved work")\n')});
  await page.locator('#chat-input').fill('Keep my message draft');await page.locator('#arrange-page').click();await page.locator('[data-tile-command="save"]').waitFor();
  await page.locator('[data-tile-grip="files"]').dragTo(page.locator('#page-left-tiles .tile-drop-placeholder'));
  await page.locator('#page-left-tiles [data-tile-id="files"]').waitFor();
  await page.locator('[data-tile-grip="notes"]').dragTo(page.locator('#page-right-tiles .tile-drop-placeholder'));
  await page.locator('#page-right-tiles [data-tile-id="notes"]').waitFor();
  const before=await page.locator('[data-tile-id="code"]').boundingBox(),handle=await page.locator('.tile-resize[data-tile-resize="code"]').boundingBox();await page.mouse.move(handle.x+10,handle.y+10);await page.mouse.down();await page.mouse.move(handle.x-95,handle.y+95,{steps:10});await page.mouse.up();
  const after=await page.locator('[data-tile-id="code"]').boundingBox();assert.ok(after.height>before.height+60,{before,after});assert.ok(after.width<before.width,{before,after});
  await page.locator('.tile-resize[data-tile-resize="files"]').scrollIntoViewIfNeeded();const leftBefore=await page.locator('.sidebar').boundingBox(),leftHandle=await page.locator('.tile-resize[data-tile-resize="files"]').boundingBox();await page.mouse.move(leftHandle.x+10,leftHandle.y+10);await page.mouse.down();await page.mouse.move(leftHandle.x+100,leftHandle.y+10,{steps:10});await page.mouse.up();assert.ok((await page.locator('.sidebar').boundingBox()).width>leftBefore.width+60);
  // Move an active Monaco editor out and back, retaining the exact model and buffer.
  await page.locator('[data-tile-placement="code"]').selectOption('right');await page.locator('#page-right-tiles .monaco-editor').waitFor();
  assert.equal(await page.evaluate(()=>dirtyModel.getValue()),'print("keep my unsaved work")\n');
  await page.locator('[data-tile-placement="code"]').selectOption('main');await page.locator('#main .monaco-editor').waitFor();assert.equal(await page.locator('#chat-input').inputValue(),'Keep my message draft');
  await page.locator('[data-tile-command="save"]').click();await page.locator('[data-tile-command="save"]').waitFor({state:'detached'});
  let stored=(await read()).pages.find(p=>p.id==='desk');assert.equal(stored.tiles.find(t=>t.id==='files').placement,'left');assert.equal(stored.tiles.find(t=>t.id==='notes').placement,'right');assert.ok(stored.tiles.find(t=>t.id==='code').height>560);assert.ok(stored.left_width>280);
  assert.equal((await request('code/file?project_id='+pid+'&path=main.py')).content,'print("hello")\n');
  await page.screenshot({path:path.resolve(root,'../../work/release029-tile-layout.png'),fullPage:true});
  await page.reload();await page.locator('#page-left-tiles [data-tile-id="files"]').waitFor();await page.locator('#page-right-tiles [data-tile-id="notes"]').waitFor();
  console.log('PASS drag into both sidebars, corner resize and sidebar width, saved project layout, preserved editor and composer drafts');
  // Cancel does not write; a racing agent edit is retained and blocks stale Save.
  await page.locator('#arrange-page').click();await page.locator('[data-tile-placement="notes"]').selectOption('left');await page.locator('[data-tile-command="cancel"]').click();assert.equal((await read()).pages.find(p=>p.id==='desk').tiles.find(t=>t.id==='notes').placement,'right');
  await page.locator('#arrange-page').click();await page.locator('[data-tile-placement="notes"]').selectOption('left');const racing=await read();racing.pages.find(p=>p.id==='desk').title='Agent updated title';await save(racing.pages);
  await page.locator('[data-tile-command="save"]').click();await page.getByRole('alert').filter({hasText:'another window or agent'}).waitFor();assert.equal((await read()).pages.find(p=>p.id==='desk').title,'Agent updated title');await page.locator('[data-tile-command="cancel"]').click();await page.locator('#main h1').getByText('Agent updated title',{exact:true}).waitFor();
  // Project and item layouts remain independent. Sidebar tiles disappear on ordinary pages.
  await page.locator('#main [data-tab="overview"]').click();assert.equal(await page.locator('#page-left-tiles').isVisible(),false);assert.equal(await page.locator('#page-right-tiles').isVisible(),false);
  const item=await request('view-layout?project_id='+pid+'&experiment_id='+service.items.software);assert.equal(item.pages.some(p=>p.id==='desk'),false);
  await page.locator('#main [data-tab="desk"]').click();await page.locator('#page-left-tiles [data-tile-id="files"]').waitFor();
  console.log('PASS cancel, concurrent agent edit conflict, fresh layout after cancel, project/item separation and sidebar cleanup');
  // Add a standalone PDF from a non-writing project. Verify its authenticated route and live viewer.
  const project=(await request('state')).projects.find(p=>p.id===pid);fs.writeFileSync(path.join(project.repo,'paper.pdf'),require('./fixtures/pdf.cjs')());
  const pdfLayout=await read();pdfLayout.pages.find(p=>p.id==='desk').tiles.push({id:'paper',kind:'pdf',path:'paper.pdf',placement:'main',span:12,height:600});await save(pdfLayout.pages);
  await page.locator('[data-action="refresh"]').first().click();await page.locator('#standalone-pdf-tile .pdf-sheet canvas').waitFor();await page.waitForFunction(()=>document.querySelector('#standalone-pdf-tile .textLayer')?.textContent);assert.ok(await page.locator('#standalone-pdf-tile .textLayer').textContent());
  const unauth=await fetch(base+'/api/code/pdf?project_id='+pid+'&path=paper.pdf');assert.equal(unauth.status,401);
  await page.locator('#arrange-page').click();await page.locator('[data-tile-placement="paper"]').selectOption('right');await page.locator('#page-right-tiles .pdf-sheet canvas').waitFor();await page.locator('[data-tile-command="save"]').click();await page.locator('[data-tile-command="save"]').waitFor({state:'detached'});
  const download=page.waitForEvent('download');await page.locator('#standalone-pdf-tile .pdf-download').click();const file=await download;assert.equal(file.suggestedFilename(),'paper.pdf');
  // The ordinary dock divider continues to resize a page with a saved width.
  await page.locator('#arrange-page').click();const dockWidth=await page.locator('#view-dock').evaluate(e=>e.clientWidth);await page.locator('#chat-resizer').focus();await page.keyboard.press('ArrowLeft');assert.ok((await page.locator('#view-dock').evaluate(e=>e.clientWidth))>dockWidth);await page.locator('[data-tile-command="save"]').click();await page.locator('[data-tile-command="save"]').waitFor({state:'detached'});assert.ok((await read()).pages.find(p=>p.id==='desk').right_width>dockWidth);
  // A project whose first page is custom still exposes Arrange immediately.
  await save([(await read()).pages.find(p=>p.id==='desk')]);await page.locator('#project-tree [data-project="'+pid+'"]').click();await page.locator('#arrange-page').waitFor({state:'visible'});
  assert.deepEqual(errors,[]);console.log('PASS repository PDF tile outside LaTeX workflow, authenticated read/download, PDF sidebar docking, zero browser errors');
 }finally{await browser?.close();child.stdin.end();}
})().catch(e=>{console.error(e);process.exitCode=1});

const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'..'),{_electron:electron}=require('playwright');
(async()=>{
 const profile=fs.mkdtempSync(path.join(os.tmpdir(),'supersurfer-sidebar-native-'));
 const child=spawn('python3',['tests/layout_runtime_fixture.py'],{cwd:root,stdio:['pipe','pipe','inherit']});let app;
 try{
  const fixture=await new Promise((resolve,reject)=>{let output='';child.stdout.on('data',chunk=>{output+=chunk;if(output.includes('\n'))resolve(JSON.parse(output.split('\n')[0]));});child.on('error',reject);child.on('exit',code=>reject(Error('Fixture exited '+code)));});
  const origin='http://127.0.0.1:'+fixture.port,token=fs.readFileSync(fixture.directory+'/token','utf8').trim();
  const packaged=root+'/dist/SuperSurfer-linux-x64',runtime=profile+'/runtime',appDir=runtime+'/resources/app';fs.mkdirSync(appDir,{recursive:true});
  for(const name of fs.readdirSync(packaged))if(name!=='resources'){const from=packaged+'/'+name,to=runtime+'/'+name;if(name==='SuperSurfer')fs.copyFileSync(from,to,fs.constants.COPYFILE_FICLONE);else fs.symlinkSync(from,to);}
  fs.writeFileSync(appDir+'/package.json',JSON.stringify({name:'supersurfer',version:'0.1.41',main:'fixture.cjs'}));
  fs.writeFileSync(appDir+'/fixture.cjs',`
   const {EventEmitter}=require('node:events');
   require('electron').app.setPath('userData',${JSON.stringify(profile+'/userdata')});
   const connection=require(${JSON.stringify(packaged+'/resources/app/desktop/connection.cjs')});
   connection.connect=async(raw)=>{const config=connection.validateConfig(raw),child=new EventEmitter();child.exitCode=null;child.kill=()=>{child.exitCode=0;};return {config,origin:${JSON.stringify(origin)},token:${JSON.stringify(token)},child};};
   require(${JSON.stringify(packaged+'/resources/app/desktop/main.cjs')});
  `);
  app=await electron.launch({executablePath:runtime+'/SuperSurfer',chromiumSandbox:true,args:['--disable-dev-shm-usage'],env:{...process.env,XDG_CONFIG_HOME:profile+'/config',XDG_CACHE_HOME:profile+'/cache'}});
  const page=await app.firstWindow();page.setDefaultTimeout(15000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.waitForFunction(()=>!document.querySelector('#connect-button')?.disabled);
  await page.evaluate(projectId=>superSurferDesktop.setWorkspace({view:'workspace',projectId,tab:'overview',chatVisible:true}),fixture.projects.software);
  await page.locator('#mode').selectOption('remote');await page.locator('#host').selectOption('__custom');await page.locator('#target').fill('fixture');await page.locator('#connect-button').click();
  const sidebar=page.locator('.sidebar'),divider=page.locator('#sidebar-resizer');await divider.waitFor();
  await page.waitForFunction(()=>document.body.classList.contains('desktop-app')&&document.querySelector('#sidebar-resizer')?.getAttribute('aria-valuenow'));
  const before=await sidebar.boundingBox(),handle=await divider.boundingBox();assert.ok(handle.height>before.height*.9);
  await page.mouse.move(handle.x+handle.width/2,handle.y+handle.height/2);await page.mouse.down();await page.mouse.move(handle.x+handle.width/2+85,handle.y+handle.height/2,{steps:8});await page.mouse.up();
  const width=(await sidebar.boundingBox()).width;assert.equal(width,before.width+85);
  await page.reload();await page.waitForFunction(()=>document.body.classList.contains('desktop-app')&&document.querySelector('#sidebar-resizer')?.getAttribute('aria-valuenow'));assert.equal((await sidebar.boundingBox()).width,width);
  await divider.focus();await page.keyboard.press('Home');assert.equal((await sidebar.boundingBox()).width,160);
  const api=async(route,body)=>{const r=await fetch(origin+'/api/'+route,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const data=await r.json();assert.ok(r.ok,JSON.stringify(data));return data;};
  const pid=fixture.projects.software,project=(await api('state')).projects.find(p=>p.id===pid),layout=await api('view-layout?project_id='+pid);
  fs.writeFileSync(path.join(project.repo,'paper.pdf'),require('./fixtures/pdf.cjs')());
  await api('action',{op:'view-layout.save',params:{project_id:pid,experiment_id:null,version:layout.version,board_version:layout.board_version,pages:[{id:'review',title:'Review',layout:{axis:'x',ratio:.5,first:{tile:'editor'},second:{tile:'pdf'}},tiles:[{id:'editor',kind:'editor',span:6,height:500},{id:'pdf',kind:'pdf',path:'paper.pdf',span:6,height:500}]}]}});
  await page.evaluate(projectId=>superSurferDesktop.setWorkspace({view:'workspace',projectId,tab:'review',chatVisible:false}),pid);await page.reload();await page.locator('#workspace-files-tree [data-tile-file="main.py"]').waitFor();
  const files=page.locator('#workspace-files-section'),filesHandle=page.locator('#workspace-files-divider'),filesBefore=await files.boundingBox(),filesBar=await filesHandle.boundingBox();
  await page.mouse.move(filesBar.x+filesBar.width/2,filesBar.y+4);await page.mouse.down();await page.mouse.move(filesBar.x+filesBar.width/2,filesBar.y+39,{steps:8});await page.mouse.up();
  assert.equal((await files.boundingBox()).height,filesBefore.height+35);const filesHeight=(await files.boundingBox()).height;await page.reload();await page.locator('#workspace-files-tree [data-tile-file="main.py"]').waitFor();assert.equal((await files.boundingBox()).height,filesHeight);
  const pdf=page.locator('[data-tile-kind=pdf]'),opened=app.waitForEvent('window');await pdf.locator('.editor-panel-handle>summary').click();await pdf.getByRole('button',{name:/separate window/}).click();const panel=await opened;await panel.locator('body.detached-panel').waitFor();await pdf.waitFor({state:'detached'});await page.waitForTimeout(300);
  await page.bringToFront();await page.locator('#workspace-files-tree [data-tile-file="main.py"]').click();await page.locator('.code-monaco .view-lines').first().click();
  const font=await page.locator('.code-monaco .view-lines').first().evaluate(el=>parseFloat(getComputedStyle(el).fontSize));
  await app.evaluate(({Menu})=>Menu.getApplicationMenu().items.find(item=>item.label==='View').submenu.items.find(item=>item.label==='Zoom In').click());
  await page.waitForFunction(font=>parseFloat(getComputedStyle(document.querySelector('.code-monaco .view-lines')).fontSize)>font,font);
  assert.equal(await app.evaluate(({BrowserWindow})=>BrowserWindow.getFocusedWindow().webContents.getZoomLevel()),0);
  await app.evaluate(({Menu})=>Menu.getApplicationMenu().items.find(item=>item.label==='View').submenu.items.find(item=>item.label==='Reset Zoom').click());
  console.log('PASS native menu zoom changes focused editor text without scaling the app');
  await page.evaluate(()=>{window.zoomRatios=[];const editor=document.querySelector('[data-tile-kind=editor]'),canvas=document.querySelector('#page-tile-grid');window.zoomProbe=new ResizeObserver(()=>zoomRatios.push(editor.getBoundingClientRect().width/canvas.getBoundingClientRect().width));zoomProbe.observe(editor);});
  for(const zoom of [1.1,.9,1]){await app.evaluate(({BrowserWindow},{origin,zoom})=>BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().startsWith(origin+'/')&&!w.webContents.getURL().includes('panel_tile=')).webContents.setZoomFactor(zoom),{origin,zoom});await page.waitForTimeout(100);}
  const ratios=await page.evaluate(()=>{zoomProbe.disconnect();return zoomRatios;});assert.ok(ratios.length>=3,JSON.stringify(ratios));assert.ok(ratios.every(r=>r>.95),JSON.stringify(ratios));await panel.close();await pdf.waitFor();
  assert.deepEqual(errors,[]);console.log('PASS actual Linux Electron sidebar pointer drag, persisted reload and keyboard shrink with sandboxed renderer and isolated workspace');
  console.log('PASS native Files height persistence and Electron zoom with a detached PDF retains full editor width');
 }finally{await app?.close();child.stdin.end();fs.rmSync(profile,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});

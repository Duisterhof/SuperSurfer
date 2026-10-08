'use strict';
// Real native beforeunload + Monaco buffer. Only the OS modal response is driven
// programmatically; the source file and remote workspace are never saved/stopped.
const {_electron:electron}=require('playwright');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
(async()=>{
 const root=path.resolve(__dirname,'..'),profile=fs.mkdtempSync(path.join(os.tmpdir(),'supersurfer-native-editor-'));let app,service;
 const child=spawn('python3',['tests/layout_runtime_fixture.py'],{cwd:root,stdio:['pipe','pipe','pipe']});let fixtureErrors='';child.stderr.on('data',chunk=>fixtureErrors+=chunk);
 try{
  service=await new Promise((resolve,reject)=>{let output='';child.stdout.on('data',chunk=>{output+=chunk;if(output.includes('\n'))try{resolve(JSON.parse(output.split('\n')[0]));}catch(error){reject(error);}});child.on('error',reject);child.on('exit',code=>reject(new Error('Fixture stopped '+code+' '+fixtureErrors)));});
  const token=fs.readFileSync(path.join(service.directory,'token'),'utf8').trim(),origin='http://127.0.0.1:'+service.port;
  const executable=process.env.ELECTRON_PATH||path.join(root,'dist/SuperSurfer-linux-x64/SuperSurfer'),packaged=path.dirname(executable),runtime=path.join(profile,'runtime'),fixture=path.join(runtime,'resources/app');fs.mkdirSync(fixture,{recursive:true});
  for(const name of fs.readdirSync(packaged))if(name!=='resources'){const from=path.join(packaged,name),to=path.join(runtime,name);if(name===path.basename(executable))fs.copyFileSync(from,to,fs.constants.COPYFILE_FICLONE);else fs.symlinkSync(from,to);}
  fs.writeFileSync(path.join(fixture,'package.json'),JSON.stringify({name:'supersurfer',productName:'SuperSurfer',version:'0.1.25',main:'fixture.cjs'}));
  fs.writeFileSync(path.join(fixture,'fixture.cjs'),`
   const {EventEmitter}=require('node:events'),{dialog}=require('electron');
   global.__fixture={choice:0,dialogs:[],killed:0,connects:0,child:null};
   dialog.showMessageBoxSync=(_window,options)=>{__fixture.dialogs.push(options);return __fixture.choice;};
   require('electron').app.setPath('userData',${JSON.stringify(path.join(profile,'userdata'))});
   const connection=require(${JSON.stringify(root+'/desktop/connection.cjs')});
   connection.connect=async(raw)=>{const config=connection.validateConfig(raw),child=new EventEmitter();__fixture.child=child;__fixture.connects++;child.exitCode=null;child.kill=()=>{if(child.exitCode===null){child.exitCode=0;__fixture.killed++;}};return {config,origin:${JSON.stringify(origin)},token:${JSON.stringify(token)},child};};
   require(${JSON.stringify(root+'/desktop/main.cjs')});
  `);
  app=await electron.launch({executablePath:path.join(runtime,path.basename(executable)),chromiumSandbox:true,colorScheme:null,args:['--disable-dev-shm-usage'],env:{...process.env,XDG_CONFIG_HOME:path.join(profile,'config'),XDG_CACHE_HOME:path.join(profile,'cache')}});
  const page=await app.firstWindow();page.setDefaultTimeout(15000);const errors=[],actions=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',()=>{});page.on('request',req=>{if(req.url().endsWith('/api/action'))actions.push(req.postDataJSON());});
  await page.waitForFunction(()=>!document.querySelector('#connect-button')?.disabled);
  await page.evaluate(projectId=>superSurferDesktop.setWorkspace({view:'workspace',projectId,tab:'editor',chatVisible:true}),service.projects.software);
  await page.locator('#mode').selectOption('remote');await page.locator('#host').selectOption('__custom');await page.locator('#target').fill('fixture');await page.locator('#connect-button').click();
  await page.locator('[data-code-open="main.py"]').waitFor();await page.locator('[data-code-open="main.py"]').click();await page.locator('.monaco-editor').waitFor();
  assert.equal((await page.evaluate(()=>superSurferDesktop.getWorkspace())).tab,'editor');
  const original=await page.evaluate(async projectId=>fetch('/api/code/file?project_id='+projectId+'&path=main.py').then(r=>r.json()),service.projects.software);
  assert.equal(original.content,'print("hello")\n');
  await page.evaluate(()=>import('/vendor/monaco/editor.js').then(module=>{const model=(module.monaco||module).editor.getModels().find(model=>model.uri.path.endsWith('/main.py'));model.setValue(model.getValue()+'# unsaved native buffer');}));await page.locator('.code-status').getByText(/Unsaved changes/).waitFor();
  const before=await page.evaluate(()=>import('/vendor/monaco/editor.js').then(module=>(module.monaco||module).editor.getModels().find(model=>model.uri.path.endsWith('/main.py')).getValue()));assert.ok(before.includes('# unsaved native buffer'));
  // Cancel navigation to connection settings using the same native guard.
  await app.evaluate(({Menu})=>{const find=items=>{for(const item of items){if(item.label==='Connection Settings…')return item;if(item.submenu){const match=find(item.submenu.items);if(match)return match;}}};const item=find(Menu.getApplicationMenu().items);if(!item)throw new Error('Connection settings menu missing');item.click();});
  await page.waitForTimeout(150);assert.equal(await app.evaluate(()=>__fixture.dialogs.length),1);assert.equal(await app.evaluate(()=>__fixture.killed),0);assert.ok(page.url().startsWith(origin));
  const settingsBuffer=await page.evaluate(()=>import('/vendor/monaco/editor.js').then(module=>(module.monaco||module).editor.getModels().find(model=>model.uri.path.endsWith('/main.py')).getValue()));assert.equal(settingsBuffer,before);
  assert.equal(await page.evaluate(async projectId=>(await fetch('/api/code/file?project_id='+projectId+'&path=main.py')).status,service.projects.software),200);
  console.log('PASS Connection Settings cancellation preserves unsaved buffer and authenticated live connection');
  // Clear only the local buffer, then simulate a dropped tunnel. Cancellation
  // must not leave the native window stuck in connection-editing mode.
  await page.evaluate(original=>import('/vendor/monaco/editor.js').then(module=>(module.monaco||module).editor.getModels().find(model=>model.uri.path.endsWith('/main.py')).setValue(original)),original.content);
  await app.evaluate(()=>{__fixture.child.exitCode=1;__fixture.child.emit('exit',1);});
  for(let i=0;i<150;i++){if(await app.evaluate(()=>__fixture.connects)===2)break;await new Promise(resolve=>setTimeout(resolve,20));}
  assert.equal(await app.evaluate(()=>__fixture.connects),2,'Cancelled settings navigation must preserve automatic reconnect');await page.locator('[data-code-open="main.py"]').waitFor();await page.locator('[data-code-open="main.py"]').click();await page.locator('.monaco-editor').waitFor();
  await page.evaluate(value=>import('/vendor/monaco/editor.js').then(module=>(module.monaco||module).editor.getModels().find(model=>model.uri.path.endsWith('/main.py')).setValue(value)),before);
  console.log('PASS cancelling settings preserves automatic tunnel reconnect afterward');

  // Keep a second native window alive so closed-window state can be inspected.
  const opened=app.waitForEvent('window');await page.evaluate(()=>superSurferDesktop.newWindow());await opened;
  await app.evaluate(({BrowserWindow},origin)=>BrowserWindow.getAllWindows().find(window=>window.webContents.getURL().startsWith(origin)).close(),origin);
  await page.waitForTimeout(100);
  assert.equal(page.isClosed(),false);assert.equal(await app.evaluate(()=>__fixture.killed),0);
  const options=await app.evaluate(()=>__fixture.dialogs[0]);assert.deepEqual(options.buttons,['Keep editing','Discard unsaved changes']);assert.equal(options.defaultId,0);assert.equal(options.cancelId,0);
  const after=await page.evaluate(()=>import('/vendor/monaco/editor.js').then(module=>(module.monaco||module).editor.getModels().find(model=>model.uri.path.endsWith('/main.py')).getValue()));assert.equal(after,before);
  const userData=await app.evaluate(({app})=>app.getPath('userData')),windows=JSON.parse(fs.readFileSync(path.join(userData,'windows.json'),'utf8'));
  const savedWindow=windows.windows.find(window=>window.config?.target==='fixture');assert.equal(savedWindow.workspace.tab,'editor');assert.equal(savedWindow.open,true);
  const diskAfterCancel=await page.evaluate(async projectId=>fetch('/api/code/file?project_id='+projectId+'&path=main.py').then(r=>r.json()),service.projects.software);assert.equal(diskAfterCancel.content,original.content);
  console.log('PASS native dirty close Keep editing preserves Monaco buffer, source, connection and editor navigation');
  await app.evaluate(()=>__fixture.choice=1);const closed=page.waitForEvent('close');await app.evaluate(({BrowserWindow},origin)=>BrowserWindow.getAllWindows().find(window=>window.webContents.getURL().startsWith(origin)).close(),origin);await closed;
  assert.equal(await app.evaluate(()=>__fixture.killed),1);assert.equal(await app.evaluate(()=>__fixture.dialogs.length),3);
  const response=await fetch(origin+'/api/code/file?project_id='+service.projects.software+'&path=main.py',{headers:{Authorization:'Bearer '+token}});assert.equal((await response.json()).content,original.content);
  assert.ok(!actions.some(call=>['code.save','chat.stop','run.stop'].includes(call.op)));assert.deepEqual(errors,[]);
  const saved=JSON.parse(fs.readFileSync(path.join(userData,'windows.json'),'utf8'));assert.equal(saved.windows.find(window=>window.config?.target==='fixture').open,false);
  console.log('PASS native Discard closes only this window without saving the file or stopping remote work');
 }finally{if(app){await app.evaluate(()=>{if(global.__fixture)__fixture.choice=1;}).catch(()=>{});await app.close().catch(()=>{});}child.stdin.end();fs.rmSync(profile,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});

'use strict';
// Real Electron main process + sandboxed renderer, with a temporary user profile.
const {_electron:electron}=require('playwright');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const profile=fs.mkdtempSync(path.join(os.tmpdir(),'supersurfer-native-qa-'));
 const root=path.resolve(__dirname,'..');let app;
 const packaged=path.dirname(process.env.ELECTRON_PATH || path.join(root,'dist/SuperSurfer-linux-x64/SuperSurfer'));
 const runtime=path.join(profile,'runtime');fs.mkdirSync(runtime);
 for(const name of fs.readdirSync(packaged))if(name!=='resources'){
  const from=path.join(packaged,name),to=path.join(runtime,name);
  if(name===path.basename(process.env.ELECTRON_PATH || 'SuperSurfer'))fs.copyFileSync(from,to,fs.constants.COPYFILE_FICLONE);
  else fs.symlinkSync(from,to);
 }
 fs.mkdirSync(path.join(runtime,'resources'));fs.symlinkSync(path.join(packaged,'resources/app'),path.join(runtime,'resources/app'));
 const launch=()=>electron.launch({executablePath:path.join(runtime,path.basename(process.env.ELECTRON_PATH || 'SuperSurfer')),chromiumSandbox:true,colorScheme:null,args:['--disable-dev-shm-usage'],env:{...process.env,HOME:profile,XDG_CONFIG_HOME:path.join(profile,'config'),XDG_CACHE_HOME:path.join(profile,'cache')}});
 try{
  app=await launch();let page=await app.firstWindow();await page.waitForFunction(()=>!document.querySelector('#connect-button')?.disabled);
  const actual=await app.evaluate(({app,BrowserWindow})=>({userData:app.getPath('userData'),preferences:BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences()}));
  assert.ok(actual.userData.startsWith(profile));assert.equal(actual.preferences.sandbox,true);assert.equal(actual.preferences.contextIsolation,true);assert.equal(actual.preferences.nodeIntegration,false);
  assert.equal(await page.evaluate(()=>typeof require),'undefined');
  await page.evaluate(()=>superSurferDesktop.setWorkspace({view:'workspace',tab:'page:page_f1abcd',projectId:'p1',experimentId:'e1',chatWidth:600,chatMaximized:true}));
  await page.evaluate(()=>superSurferDesktop.setTheme('dark'));
  assert.equal(await page.evaluate(()=>matchMedia('(prefers-color-scheme: dark)').matches),true);
  await app.close();app=await launch();page=await app.firstWindow();await page.waitForFunction(()=>!document.querySelector('#connect-button')?.disabled);
  const saved=await page.evaluate(()=>superSurferDesktop.getWorkspace());assert.equal(saved.tab,'page:page_f1abcd');assert.equal(saved.chatWidth,600);assert.equal(saved.chatMaximized,true);
  assert.equal(await page.evaluate(()=>superSurferDesktop.getTheme()),'dark');
  await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].loadURL('data:text/html,<h1>Untrusted page</h1>'));
  await assert.rejects(page.evaluate(()=>superSurferDesktop.configuration()),/setup window/);
  await assert.rejects(page.evaluate(()=>superSurferDesktop.connect({mode:'local'})),/setup window/);
  console.log('PASS native Linux Electron isolation, separate profile, custom-tab/layout/theme persistence, untrusted-page connection denial');
 }finally{if(app)await app.close();fs.rmSync(profile,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});

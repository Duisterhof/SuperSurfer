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
  assert.deepEqual(errors,[]);console.log('PASS actual Linux Electron sidebar pointer drag, persisted reload and keyboard shrink with sandboxed renderer and isolated workspace');
 }finally{await app?.close();child.stdin.end();fs.rmSync(profile,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});

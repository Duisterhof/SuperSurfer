'use strict';
// Real desktop cancellation/retry; controlled connection promises, no SSH.
const {_electron:electron}=require('playwright');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'..'),profile=fs.mkdtempSync(path.join(os.tmpdir(),'ss-reconnect-status-'));let app;
 try{
  const executable=process.env.ELECTRON_PATH||path.join(root,'dist/SuperSurfer-linux-x64/SuperSurfer');
  const packaged=path.dirname(executable),runtime=path.join(profile,'runtime'),fixture=path.join(runtime,'resources/app');fs.mkdirSync(fixture,{recursive:true});
  for(const name of fs.readdirSync(packaged))if(name!=='resources'){
   const from=path.join(packaged,name),to=path.join(runtime,name);
   if(name===path.basename(executable))fs.copyFileSync(from,to,fs.constants.COPYFILE_FICLONE);else fs.symlinkSync(from,to);
  }
  fs.writeFileSync(path.join(fixture,'package.json'),JSON.stringify({name:'supersurfer',version:'0.1.43',main:'fixture.cjs'}));
  fs.writeFileSync(path.join(fixture,'fixture.cjs'),`
   require('electron').app.setPath('userData',${JSON.stringify(path.join(profile,'userdata'))});
   global.__attempts=[];
   require(${JSON.stringify(root+'/desktop/connection.cjs')}).connect=async(_raw,onStatus,{signal})=>new Promise((_resolve,reject)=>{
    __attempts.push({onStatus,signal,reject});onStatus(__attempts.length===1?'Old upload in progress':'Checking saved workspace');
   });
   require(${JSON.stringify(root+'/desktop/main.cjs')});
  `);
  app=await electron.launch({executablePath:path.join(runtime,path.basename(executable)),chromiumSandbox:true,args:['--disable-dev-shm-usage'],env:{...process.env,XDG_CONFIG_HOME:path.join(profile,'config'),XDG_CACHE_HOME:path.join(profile,'cache')}});
  const page=await app.firstWindow();page.setDefaultTimeout(10000);
  await page.waitForFunction(()=>!document.querySelector('#connect-button')?.disabled);
  await page.locator('#mode').selectOption('local');await page.locator('#connect-button').click();
  await page.locator('#status').getByText('Old upload in progress',{exact:true}).waitFor();
  await page.locator('#cancel-connect').click();
  assert.equal(await app.evaluate(()=>__attempts[0].signal.aborted),true);
  await page.locator('#connect-button').click();await page.locator('#status').getByText('Checking saved workspace',{exact:true}).waitFor();
  await app.evaluate(()=>{__attempts[0].onStatus('SSH connected. Uploading the workspace bundle…');__attempts[0].reject(new Error('Old attempt stopped'));});
  await page.waitForTimeout(100);
  assert.equal(await page.locator('#status').textContent(),'Checking saved workspace');
  assert.equal(await page.locator('#connect-button').isDisabled(),true);
  await app.evaluate(()=>__attempts[1].reject(new Error('Fixture retry finished')));
  await page.locator('#status').getByText('Fixture retry finished',{exact:true}).waitFor();
  assert.equal(await page.locator('#connect-button').isEnabled(),true);
  console.log('PASS cancelled connection cannot overwrite a newer attempt with stale upload progress');
 }finally{if(app)await app.close();fs.rmSync(profile,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});

'use strict';
// Run after package:mac on macOS. Verify the delivered archive, not a source overlay.
const {_electron:electron}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {execFileSync}=require('node:child_process');
(async()=>{
  if(process.platform!=='darwin')throw new Error('This packaged-app check requires macOS.');
  const root=path.resolve(__dirname,'..'),version=require('../package.json').version;
  const arch=process.env.SUPERSURFER_ARCH||'arm64';
  const bundle=path.join(root,'dist',`SuperSurfer-darwin-${arch}`,'SuperSurfer.app');
  const archive=path.join(root,'dist',`SuperSurfer-${version}-mac-${arch}.zip`);
  const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'supersurfer-mac-qa-'));
  const extracted=path.join(temporary,'extracted');
  fs.mkdirSync(extracted);
  let application;
  const close = async () => {
    if (!application) return;
    const current = application; application = null;
    const watchdog = setTimeout(() => current.process().kill('SIGKILL'), 10000);
    try { await current.close(); } finally { clearTimeout(watchdog); }
  };
  try{
    execFileSync('ditto',['-x','-k',archive,extracted]);
    for(const [index,appPath] of [bundle,path.join(extracted,'SuperSurfer.app')].entries()){
      console.log(`Checking ${index?'extracted':'original'} bundle signature`);
      execFileSync('codesign',['--verify','--deep','--strict',appPath],{stdio:'pipe',timeout:60000});
      const profile=path.join(temporary,`profile-${index}`);
      console.log(`Launching ${index?'extracted':'original'} bundle`);
      application=await electron.launch({executablePath:path.join(appPath,'Contents/MacOS/SuperSurfer'),chromiumSandbox:true,args:[`--user-data-dir=${profile}`],timeout:30000});
      const page=await application.firstWindow({timeout:30000});
      console.log('Window opened:',page.url());
      const errors=[];page.on('pageerror',error=>errors.push(error.message));
      try {
        await page.waitForFunction(()=>document.querySelector('#connect-button')&&!document.querySelector('#connect-button').disabled, null, {timeout:45000});
      } catch (error) {
        console.error('Setup did not become ready:', await page.evaluate(()=>({url:location.href,status:document.querySelector('#status')?.textContent,bridge:typeof window.superSurferDesktop,body:document.body?.innerText.slice(0,1200)})).catch(()=>({renderer:'unresponsive'})), errors);
        throw error;
      }
      console.log('Setup ready');
      const actual=await application.evaluate(({app,BrowserWindow})=>({profile:app.getPath('userData'),preferences:BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences()}));
      assert.equal(fs.realpathSync(actual.profile),fs.realpathSync(profile));
      assert.equal(actual.preferences.sandbox,true);
      assert.equal(actual.preferences.contextIsolation,true);
      assert.equal(actual.preferences.nodeIntegration,false);
      assert.equal(await page.evaluate(()=>typeof require),'undefined');
      assert.match(page.url(),/desktop\/setup\.html$/);
      assert.deepEqual(errors,[]);
      await close();
      console.log(`PASS ${index?'ZIP-extracted':'original'} Mac app: strict signature, isolated-profile launch and sandboxed setup screen`);
    }
  }finally{
    await close();
    fs.rmSync(temporary,{recursive:true,force:true});
  }
})().catch(error=>{console.error(error);process.exitCode=1;});

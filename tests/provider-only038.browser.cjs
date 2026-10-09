'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
(async()=>{
 const root=path.resolve(__dirname,'..');
 for(const provider of ['cursor','claude']){
  const fixture=spawn('python3',['tests/backend_runtime_fixture.py','--only-provider',provider],{cwd:root,stdio:['pipe','pipe','pipe']});let browser,stderr='';fixture.stderr.on('data',data=>stderr+=data);
  try{
   const meta=await new Promise((resolve,reject)=>{let output='';fixture.stdout.on('data',data=>{output+=data;if(output.includes('\n'))resolve(JSON.parse(output.split('\n')[0]));});fixture.on('exit',code=>reject(Error(code+' '+stderr)));});
   const base='http://127.0.0.1:'+meta.port,token=fs.readFileSync(path.join(meta.directory,'token'),'utf8').trim(),fixtureRoot=path.dirname(meta.directory);
   assert.equal(fs.existsSync(path.join(fixtureRoot,'codex')),false);assert.equal(fs.existsSync(path.join(fixtureRoot,provider==='cursor'?'claude':'cursor')),false);
   const api=async(route,body)=>{const response=await fetch(base+'/api/'+route,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const data=await response.json();assert.equal(response.ok,true,JSON.stringify(data));return data;};
   browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',error=>errors.push(error.message));page.setDefaultTimeout(20000);
   await page.addInitScript(({token,experiment})=>{sessionStorage.setItem('supersurfer-token',token);if(!localStorage.getItem('supersurfer-workspace'))localStorage.setItem('supersurfer-workspace',JSON.stringify({view:'workspace',projectId:'p1',experimentId:experiment,tab:'overview',chatVisible:true}));},{token,experiment:meta.experiment});
   await page.goto(base);await page.getByLabel('Conversation backend').selectOption(provider);await page.waitForFunction(()=>!document.querySelector('#chat-send').disabled);
   await page.locator('#chat-input').fill('hello');await page.locator('#chat-send').click();await page.getByText('Hello world',{exact:true}).waitFor();await page.waitForFunction(()=>!document.querySelector('#chat-send').disabled);
   await page.locator('[data-view=settings]').click();await page.locator('#settings-form').waitFor();assert.equal(await page.locator('#workspace-approval-mode option').count(),3);
   for(const role of ['manager','lead','worker'])await page.getByLabel(role+' backend',{exact:true}).selectOption(provider);
   const saved=page.waitForResponse(response=>response.url().endsWith('/api/action')&&response.request().postDataJSON()?.op==='settings.save');await page.locator('#settings-form button[type=submit]').click();assert.equal((await saved).ok(),true);
   const settings=(await api('state')).settings;for(const role of ['manager','lead','worker'])assert.equal(settings.backends[role],provider);
   await page.reload();await page.locator('#settings-form').waitFor();for(const role of ['manager','lead','worker'])assert.equal(await page.getByLabel(role+' backend',{exact:true}).inputValue(),provider);
   const worker=await api('action',{op:'experiment.agent.create',params:{experiment_id:meta.experiment,name:'Provider-only worker'}});
   for(const scope of ['manager','project:p1',worker.scope]){
    assert.equal((await api('chat?scope='+encodeURIComponent(scope))).preferences.backend,provider);
    await api('action',{op:'chat.send',params:{scope,text:'hello'}});let chat;
    for(let attempt=0;attempt<100;attempt++){chat=await api('chat?scope='+encodeURIComponent(scope));if(!chat.busy)break;await page.waitForTimeout(100);}
    assert.equal(chat.status,'completed',JSON.stringify({scope,status:chat.status,error:chat.error}));assert.equal(chat.backend,provider);
   }
   assert.equal(fs.existsSync(path.join(fixtureRoot,'codex-wire.jsonl')),false);assert.deepEqual(errors,[]);
   console.log('PASS '+provider+' only: Codex/other CLI absent; chat, Settings, persisted role defaults and manager/lead/new worker all complete');
  }catch(error){if(browser){const page=browser.contexts()[0]?.pages()[0];if(page){console.error('Provider-only failure '+provider+': '+await page.locator('body').innerText());await page.screenshot({path:'/tmp/ss038-'+provider+'-only-failure.png'});}}throw error;}finally{fixture.stdin.end();await browser?.close();await new Promise(resolve=>fixture.once('exit',resolve));}
 }
})().catch(error=>{console.error(error);process.exitCode=1;});

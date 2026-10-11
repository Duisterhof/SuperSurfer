'use strict';
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'..'),child=spawn('python3',['tests/layout_runtime_fixture.py'],{cwd:root,stdio:['pipe','pipe','inherit']});let browser;
 try{
  const fixture=await new Promise((resolve,reject)=>{let out='';child.stdout.on('data',chunk=>{out+=chunk;if(out.includes('\n'))resolve(JSON.parse(out.split('\n')[0]));});child.on('error',reject);child.on('exit',code=>reject(Error('Fixture exited '+code)));});
  const token=fs.readFileSync(fixture.directory+'/token','utf8').trim(),pid=fixture.projects.software,id=fixture.items.software,base='http://127.0.0.1:'+fixture.port;
  const api=async(route,body)=>{const r=await fetch(base+'/api/'+route,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const data=await r.json();assert.ok(r.ok,JSON.stringify(data));return data;};
  const before=await api('experiment?id='+id);
  browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],actions=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().endsWith('/api/action'))actions.push(r.postDataJSON().op);});
  await page.addInitScript(({pid,token})=>{sessionStorage.setItem('supersurfer-token',token);if(!localStorage.getItem('supersurfer-workspace'))localStorage.setItem('supersurfer-workspace',JSON.stringify({projectId:pid,tab:'overview',view:'workspace',chatVisible:true}));},{pid,token});
  await page.goto(base);const task=page.locator('#project-tree [data-experiment="'+id+'"]'),dialog=page.locator('#modal'),input=dialog.getByRole('textbox',{name:'Task name',exact:true});
  await task.waitFor();await page.locator('#chat-input').fill('Keep my chat draft');
  const openRename=async()=>{await task.click({button:'right'});await page.getByRole('menuitem',{name:'Rename task…',exact:true}).click();await input.waitFor();};
  await openRename();assert.equal(await input.inputValue(),before.name);await input.fill('Do not save this');await dialog.getByRole('button',{name:'Cancel',exact:true}).click();assert.equal((await api('experiment?id='+id)).name,before.name);
  await openRename();const name='E18 — Café: train / test (v2) 🏄';await input.fill(name);
  const current=await api('experiment?id='+id);await api('action',{op:'experiment.rename',params:{id,version:current.version,name:'Another window’s title'}});
  await dialog.getByRole('button',{name:'Rename',exact:true}).click();await dialog.getByRole('alert').getByText(/This task changed/).waitFor();assert.equal(await input.inputValue(),name);assert.equal((await api('experiment?id='+id)).name,'Another window’s title');
  await dialog.getByRole('button',{name:'Rename',exact:true}).click();await dialog.waitFor({state:'hidden'});await task.getByText(name,{exact:true}).waitFor();assert.equal(await page.locator('#chat-input').inputValue(),'Keep my chat draft');
  const renamed=await api('experiment?id='+id);for(const field of ['id','project_id','document_path','markdown','task_ids','wandb_url'])assert.deepEqual(renamed[field],before[field]);
  await page.reload();await task.getByText(name,{exact:true}).waitFor();
  await task.click({button:'right'});await page.getByRole('menuitem',{name:'Archive task',exact:true}).click();const archived=page.locator('.archived-task-folder');await archived.locator(':scope>summary').click();await openRename();await input.fill('Archived notes — v3');await dialog.getByRole('button',{name:'Rename',exact:true}).click();await dialog.waitFor({state:'hidden'});assert.equal((await api('experiment?id='+id)).archived,true);
  assert.ok(!actions.some(op=>['chat.stop','chat.send','run.stop','run.queue','run.cancel'].includes(op)));assert.deepEqual(errors,[]);console.log('PASS right-click task rename, free-form names, cancel, concurrent title conflict/retry, draft preservation, reload and archived rename');
 }finally{await browser?.close();child.stdin.end();}
})().catch(error=>{console.error(error);process.exitCode=1;});
